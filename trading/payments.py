"""
Stripe Checkout integration for real wallet deposits.

Required env vars:
  STRIPE_SECRET_KEY     — sk_test_... or sk_live_...
  STRIPE_WEBHOOK_SECRET — whsec_... (from Stripe CLI or dashboard)
"""
from __future__ import annotations
import os


def is_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def create_checkout_session(user_id: int, amount_usd: float, base_url: str) -> str:
    """Create a Stripe Checkout session and return the hosted checkout URL."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "Codon Trader — Wallet Deposit",
                    "description": f"Add ${amount_usd:.2f} to your trading wallet",
                },
                "unit_amount": int(amount_usd * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{base_url}/?funded=1&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/?funded=0",
        client_reference_id=str(user_id),
        metadata={"user_id": str(user_id), "amount_usd": str(amount_usd)},
    )
    return session.url  # type: ignore[return-value]


def parse_webhook(payload: bytes, sig_header: str) -> dict | None:
    """Verify Stripe webhook signature and return the event, or None on failure."""
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    try:
        if webhook_secret:
            return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        import json
        return json.loads(payload)      # dev mode: trust without signature
    except Exception:
        return None
