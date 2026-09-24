# Instant Website Audit — $29/report

A standalone web app: a visitor enters any URL, gets a **free 0–100 SEO score
+ teaser** (the 9 checks from the Local SEO Quick Check Chrome extension,
ported server-side), and the **full PDF audit report is paywalled at $29**.

## Quick start (demo)

```bash
cd ~/workspace/side-hustle/audit-tool
python3 app.py              # or: python3 app.py --port 8080
# open http://localhost:8080
```

No dependencies — pure Python standard library. Python 3.8+.

Demo flow: enter a URL → see the free score → click
**"Get the full report — $29"** → the payment stub page explains Stripe
isn't connected yet → **DEMO: simulate successful payment** → the real
PDF downloads. The whole funnel works end to end; only the money step
is stubbed.

Dev-only: `AUDIT_TOOL_ALLOW_PRIVATE=1 python3 app.py` skips the SSRF
guard so you can audit `localhost`/staging URLs while developing.
**Never set this in production.**

## Files

| File | What it is |
|---|---|
| `app.py` | Web server + routes (`/`, `/api/audit`, `/buy`, `/report/<id>`, `/webhooks/stripe`) |
| `audit.py` | Fetch → parse → score. The extension's 9 checks, server-side |
| `report.py` | Paywalled PDF generator (hand-rolled, stdlib only) |
| `payments.py` | **Payment integration stub** — exactly where Stripe Checkout plugs in |
| `static/index.html` | Landing page + audit UI (inline CSS/JS, no build step) |

## The 9 checks (same as the extension)

Title tag · Meta description · Mobile viewport · Headings (H1) ·
Image alt text · Structured data (JSON-LD) · Google Business Profile link ·
Page speed (server fetch time) · HTTPS.
Weighted score: pass = 1, needs work = 0.5, missing = 0.

The free teaser shows every check's name, status, and one-line detail —
**the fix tips, priority ordering, and PDF are paywalled** (`teaser_for()`
strips tips; verified by test).

## Payments — current state: STUB

`payments.STRIPE_ENABLED = False`. The `/buy` page shows a clearly-labeled
payment stub and a demo-unlock button. No keys exist anywhere in this repo
(none were invented).

### Going live with Stripe — exact steps

1. **Stripe account** (muni): create/log in at dashboard.stripe.com,
   complete business + payout details.
2. **Create the product**: Products → New → "Instant Website Audit —
   Full PDF Report", one-time payment, **$29.00 USD** → copy the
   **Price ID** (`price_...`).
3. **Get keys**: Developers → API keys → copy the **secret key**
   (`sk_live_...`); Developers → Webhooks → add endpoint
   `https://<your-domain>/webhooks/stripe`, listen for
   `checkout.session.completed` → copy the **signing secret** (`whsec_...`).
4. **On the server**, set env vars (never commit them):
   `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`.
   `pip install stripe`.
5. **In `payments.py`**: set `STRIPE_ENABLED = True` and implement the
   two `[IMPLEMENT]` functions using the commented recipes
   (`create_checkout_session`, `verify_payment`, `handle_webhook`).
6. **In `app.py`**: uncomment the `[IMPLEMENT]` blocks in `handle_buy`
   (redirect to Checkout) and `handle_report` (verify `session_id`).
   Remove the demo-unlock route or gate it behind a dev flag.
7. **Persistence**: `AUDITS`/`PAID` are in-memory dicts — swap for SQLite/
   Postgres before real traffic (process restart currently loses audits).
8. **Deploy** (see below), then run a live $29 test purchase and refund it.

## Deploy options (pick one)

- **VPS (simplest)**: `nohup python3 app.py --port 8080 &` behind nginx/
  Caddy as a reverse proxy with HTTPS. Add a systemd unit for restarts.
- **Render/Fly.io**: this is a single process with no build step —
  set the start command to `python3 app.py --port $PORT` and bind
  `0.0.0.0` (change `ThreadingHTTPServer(("127.0.0.1", ...))` to
  `("0.0.0.0", ...)` in `app.py` for hosted deploys).
- **Docker**: trivially containerizable (`python:3.12-slim`, copy dir,
  `CMD ["python3", "app.py", "--port", "8080"]`).

## Verified

- Scoring matches the extension's logic (unit-tested on fixture HTML).
- End-to-end: audit → teaser (tips hidden) → 402-locked report →
  demo unlock → valid multi-page PDF (visually inspected).
- Edge cases: empty URL, non-http scheme, unreachable host, unknown
  audit IDs, SSRF guard blocking private IPs — all return clean errors.
- PDF: header, score box, page snapshot, priority fix list, full check
  detail with status badges, disclaimer footer. Page counts correct.

## Money math

$29/report. Stripe's standard fee (~2.9% + $0.30) → **~$27.86 net per
sale**. Zero marginal cost per audit (a few seconds of server CPU).
Every website-prospect mockup in the sales pipeline is a natural
upsell: "your site scored 61/100 — full fix-it report, $29."
