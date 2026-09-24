"""Instant Website Audit — PAYMENT INTEGRATION STUB.

Price: $29 per full PDF audit report.

Nothing here is wired to real money. This module documents EXACTLY where
Stripe Checkout plugs in. Steps to go live are in README.md under
"Going live with Stripe".

To integrate:
  1. pip install stripe
  2. Set env vars STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_ID
     (create a $29 one-time product/price in the Stripe Dashboard).
  3. Set STRIPE_ENABLED = True below.
  4. Implement the two functions marked [IMPLEMENT] using the commented
     recipes provided.
  5. Point a Stripe webhook at https://<your-domain>/webhooks/stripe
     listening for checkout.session.completed.
"""

STRIPE_ENABLED = False          # flip to True after wiring real keys
STRIPE_CURRENCY = "usd"
PRICE_CENTS = 2900              # $29.00 per report
PRODUCT_NAME = "Instant Website Audit — Full PDF Report"

# NOTE: Stripe secret keys are NEVER committed to this repo.
# Read from environment only: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET.


def create_checkout_session(audit_id, success_url, cancel_url):
    """[IMPLEMENT] Create a Stripe Checkout session for one $29 report.

    Recipe (after `pip install stripe`):

        import os, stripe
        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": os.environ["STRIPE_PRICE_ID"], "quantity": 1}],
            metadata={"audit_id": audit_id},
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
        )
        return session.url

    Returns the hosted Checkout URL the buyer is redirected to.
    """
    raise NotImplementedError(
        "Stripe is not wired up yet. See payments.py docstring + "
        "README.md 'Going live with Stripe'.")


def verify_payment(session_id):
    """[IMPLEMENT] Confirm a Checkout session actually paid.

    Recipe:

        import os, stripe
        stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            return session.metadata.get("audit_id")
        return None

    Returns the audit_id from the session metadata, or None if unpaid.
    Prefer the webhook below as the source of truth for fulfillment.
    """
    raise NotImplementedError(
        "Stripe is not wired up yet. See payments.py docstring + "
        "README.md 'Going live with Stripe'.")


def handle_webhook(payload, sig_header):
    """[IMPLEMENT] Stripe webhook: checkout.session.completed -> unlock report.

    Recipe:

        import os, stripe
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ["STRIPE_WEBHOOK_SECRET"])
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            audit_id = session["metadata"]["audit_id"]
            # mark audit_id as paid in your store (see app.py: mark_paid)
        return True

    Returns True if the event was handled.
    """
    raise NotImplementedError(
        "Stripe is not wired up yet. See payments.py docstring + "
        "README.md 'Going live with Stripe'.")


# ----------------------------------------------------------------------------
# Demo unlock (development ONLY — remove/disable in production)
# ----------------------------------------------------------------------------

def demo_unlock_token(audit_id):
    """Demo-mode stand-in for a completed payment.

    The live app never calls this: it is only used by the /buy page while
    STRIPE_ENABLED is False, so the PDF flow can be demoed end to end.
    """
    import secrets
    return "demo_" + secrets.token_hex(8)
