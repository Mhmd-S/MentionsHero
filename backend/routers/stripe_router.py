"""Stripe integration API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Any

from backend.core.auth import require_user_auth
from backend.services import stripe_service

router = APIRouter(prefix="/api/stripe", tags=["stripe"])


@router.post("/checkout")
async def create_checkout(
    user: dict = Depends(require_user_auth),
) -> dict[str, str]:
    """Create a Stripe Checkout session for subscription."""
    url = await stripe_service.create_checkout_session(
        user_id=user["sub"],
        email=user["email"],
    )
    return {"url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle Stripe webhook events (no auth — verified by Stripe signature)."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    try:
        await stripe_service.handle_webhook(payload, signature)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "ok"}


@router.get("/subscription")
async def get_subscription(
    user: dict = Depends(require_user_auth),
) -> dict[str, Any]:
    """Get current user's subscription status."""
    sub = await stripe_service.get_subscription_status(user["sub"])
    if not sub:
        return {"status": "none", "is_subscribed": False}

    return {
        **sub,
        "is_subscribed": sub.get("status") == "active",
    }


@router.post("/portal")
async def create_portal(
    user: dict = Depends(require_user_auth),
) -> dict[str, str]:
    """Create a Stripe Customer Portal session."""
    url = await stripe_service.create_portal_session(user["sub"])
    if not url:
        raise HTTPException(status_code=400, detail="No subscription found")
    return {"url": url}
