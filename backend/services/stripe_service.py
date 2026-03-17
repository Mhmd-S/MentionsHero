"""Stripe integration service for subscription management."""

import logging
from datetime import datetime, timezone
from typing import Any

import stripe

from backend.config import get_settings
from backend.core.database import get_supabase

logger = logging.getLogger(__name__)


def _extract_period(subscription: dict) -> tuple[int | None, int | None]:
    """Extract current_period_start/end from a Stripe subscription.

    Newer Stripe API versions moved these fields from the top-level
    subscription object to items.data[].
    """
    start = subscription.get("current_period_start")
    end = subscription.get("current_period_end")
    if start and end:
        return start, end
    # Fall back to first subscription item
    items = subscription.get("items", {})
    for item in (items.get("data", []) if isinstance(items, dict) else []):
        start = start or item.get("current_period_start")
        end = end or item.get("current_period_end")
        if start and end:
            break
    return start, end


def _get_stripe():
    """Initialize Stripe with secret key."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    return stripe


async def create_checkout_session(
    user_id: str,
    email: str,
) -> str:
    """Create a Stripe Checkout session for monthly subscription."""
    s = _get_stripe()
    settings = get_settings()
    base = settings.frontend_url.rstrip("/")
    success_url = f"{base}/account?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/pricing"
    supabase = get_supabase()

    # Check if user already has a Stripe customer ID
    profile = (
        supabase.table("profiles")
        .select("stripe_customer_id")
        .eq("id", user_id)
        .single()
        .execute()
    )

    customer_id = profile.data.get("stripe_customer_id") if profile.data else None

    if not customer_id:
        # Create Stripe customer
        customer = s.Customer.create(email=email, metadata={"user_id": user_id})
        customer_id = customer.id

        # Save to profiles
        supabase.table("profiles").update(
            {"stripe_customer_id": customer_id}
        ).eq("id", user_id).execute()

    session = s.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"user_id": user_id},
    )

    return session.url


async def handle_webhook(payload: bytes, signature: str) -> None:
    """Process Stripe webhook events."""
    s = _get_stripe()
    settings = get_settings()

    event = s.Webhook.construct_event(
        payload, signature, settings.stripe_webhook_secret
    )

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        await _handle_subscription_change(data)

    logger.info("Processed Stripe event: %s", event_type)


async def _handle_checkout_completed(session: dict) -> None:
    """Handle successful checkout — create subscription record."""
    s = _get_stripe()
    supabase = get_supabase()
    user_id = session.get("metadata", {}).get("user_id")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id or not subscription_id:
        logger.warning("Checkout session missing user_id or subscription_id")
        return

    # Fetch full subscription from Stripe to get period dates
    record: dict[str, Any] = {
        "user_id": user_id,
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "status": "active",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        sub = s.Subscription.retrieve(subscription_id)
        period_start, period_end = _extract_period(sub)
        if period_start:
            record["current_period_start"] = datetime.fromtimestamp(
                period_start, tz=timezone.utc
            ).isoformat()
        if period_end:
            record["current_period_end"] = datetime.fromtimestamp(
                period_end, tz=timezone.utc
            ).isoformat()
    except Exception:
        logger.warning("Could not fetch subscription details from Stripe")

    # Upsert subscription
    supabase.table("subscriptions").upsert(
        record,
        on_conflict="stripe_subscription_id",
    ).execute()


async def _handle_subscription_change(subscription: dict) -> None:
    """Handle subscription updated/deleted events."""
    supabase = get_supabase()
    subscription_id = subscription.get("id")
    status = subscription.get("status", "inactive")

    # Map Stripe statuses to our simplified statuses
    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "inactive",
        "incomplete": "inactive",
        "incomplete_expired": "inactive",
        "trialing": "active",
    }
    mapped_status = status_map.get(status, "inactive")

    period_start, period_end = _extract_period(subscription)

    updates: dict[str, Any] = {
        "status": mapped_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if period_start:
        updates["current_period_start"] = datetime.fromtimestamp(
            period_start, tz=timezone.utc
        ).isoformat()
    if period_end:
        updates["current_period_end"] = datetime.fromtimestamp(
            period_end, tz=timezone.utc
        ).isoformat()

    supabase.table("subscriptions").update(updates).eq(
        "stripe_subscription_id", subscription_id
    ).execute()


async def _sync_subscription_from_stripe(
    user_id: str, supabase: Any
) -> dict[str, Any] | None:
    """Check Stripe for an active subscription and sync it to the DB.

    Returns the synced subscription record, or None if no active sub found.
    """
    try:
        profile = (
            supabase.table("profiles")
            .select("stripe_customer_id")
            .eq("id", user_id)
            .single()
            .execute()
        )
        customer_id = profile.data.get("stripe_customer_id") if profile.data else None
        if not customer_id:
            return None

        s = _get_stripe()
        subs = s.Subscription.list(customer=customer_id, status="active", limit=1)
        if not subs.data:
            return None

        stripe_sub = subs.data[0]
        period_start, period_end = _extract_period(stripe_sub)

        record: dict[str, Any] = {
            "user_id": user_id,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": stripe_sub["id"],
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if period_start:
            record["current_period_start"] = datetime.fromtimestamp(
                period_start, tz=timezone.utc
            ).isoformat()
        if period_end:
            record["current_period_end"] = datetime.fromtimestamp(
                period_end, tz=timezone.utc
            ).isoformat()

        supabase.table("subscriptions").upsert(
            record, on_conflict="stripe_subscription_id"
        ).execute()

        # Re-fetch the upserted record to return complete data
        result = (
            supabase.table("subscriptions")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    except Exception:
        logger.warning("Stripe subscription sync failed for user %s", user_id)
        return None


async def get_subscription_status(user_id: str) -> dict[str, Any] | None:
    """Get current subscription status for a user.

    If the DB has no active subscription, falls back to checking Stripe
    directly and syncs the result back to the DB. This handles cases where
    the webhook for checkout.session.completed was missed.
    """
    supabase = get_supabase()

    response = (
        supabase.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    db_record = response.data[0] if response.data else None

    # Fast path: DB says active — no Stripe call needed
    if db_record and db_record.get("status") == "active":
        return db_record

    # Unhappy path: DB has no active record — verify against Stripe
    synced = await _sync_subscription_from_stripe(user_id, supabase)
    if synced:
        return synced

    return db_record


async def create_portal_session(user_id: str) -> str | None:
    """Create a Stripe Customer Portal session for subscription management."""
    s = _get_stripe()
    supabase = get_supabase()

    profile = (
        supabase.table("profiles")
        .select("stripe_customer_id")
        .eq("id", user_id)
        .single()
        .execute()
    )

    customer_id = profile.data.get("stripe_customer_id") if profile.data else None
    if not customer_id:
        return None

    session = s.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{get_settings().frontend_url.rstrip('/')}/account",
    )

    return session.url
