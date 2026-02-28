"""Stripe integration service for subscription management."""

import logging
from datetime import datetime, timezone
from typing import Any

import stripe

from backend.config import get_settings
from backend.core.database import get_supabase

logger = logging.getLogger(__name__)


def _get_stripe():
    """Initialize Stripe with secret key."""
    settings = get_settings()
    stripe.api_key = settings.stripe_secret_key
    return stripe


async def create_checkout_session(
    user_id: str,
    email: str,
    success_url: str = "http://localhost:3000/account?session_id={CHECKOUT_SESSION_ID}",
    cancel_url: str = "http://localhost:3000/pricing",
) -> str:
    """Create a Stripe Checkout session for monthly subscription."""
    s = _get_stripe()
    settings = get_settings()
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
    supabase = get_supabase()
    user_id = session.get("metadata", {}).get("user_id")
    customer_id = session.get("customer")
    subscription_id = session.get("subscription")

    if not user_id or not subscription_id:
        logger.warning("Checkout session missing user_id or subscription_id")
        return

    # Upsert subscription
    supabase.table("subscriptions").upsert(
        {
            "user_id": user_id,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
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

    current_period_start = subscription.get("current_period_start")
    current_period_end = subscription.get("current_period_end")

    updates: dict[str, Any] = {
        "status": mapped_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if current_period_start:
        updates["current_period_start"] = datetime.fromtimestamp(
            current_period_start, tz=timezone.utc
        ).isoformat()
    if current_period_end:
        updates["current_period_end"] = datetime.fromtimestamp(
            current_period_end, tz=timezone.utc
        ).isoformat()

    supabase.table("subscriptions").update(updates).eq(
        "stripe_subscription_id", subscription_id
    ).execute()


async def get_subscription_status(user_id: str) -> dict[str, Any] | None:
    """Get current subscription status for a user."""
    supabase = get_supabase()

    response = (
        supabase.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return response.data[0]


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
        return_url="http://localhost:3000/account",
    )

    return session.url
