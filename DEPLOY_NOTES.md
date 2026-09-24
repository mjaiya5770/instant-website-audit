# Instant Website Audit — Deploy Notes

**Date:** 2026-09-24
**Live URL:** https://mjaiya5770.github.io/instant-website-audit/
**Hosting:** GitHub Pages (free tier), served from `/docs` on branch `main`
**Repo:** https://github.com/mjaiya5770/instant-website-audit (public)

## What is deployed

A **static edition** of the Instant Website Audit tool (`docs/index.html`,
fully self-contained, no build step). It runs the same 9 on-page SEO checks
as the Python server edition:

1. Title tag (30–60 chars) · 2. Meta description (50–160) · 3. Mobile viewport
4. Single H1 · 5. Image alt text · 6. Structured data (JSON-LD/microdata)
7. Google Business Profile link · 8. Page speed (fetch time) · 9. HTTPS

The page is fetched **client-side through a public CORS proxy**
(primary: `https://api.allorigins.win/raw?url=…`, fallback:
`https://api.cors.lol/?url=…`), parsed with `DOMParser`, scored with the
same weights as `audit.py` (pass=1, warn=0.5, fail=0, na excluded).

## Deployed behavior

- **Free audit: fully working.** Enter any public http(s) URL → 0–100 score
  ring + all 9 checks with pass/warn/fail badges and finding details.
- **Fix tips stay paywalled.** Failing/warning checks show
  "🔒 How to fix this: included in the full report (coming soon)." No tip
  text is present anywhere in the client bundle (verified by grep).
- **Payments: disabled.** There is no Stripe code, no checkout, no price
  ID, no webhook in the deployed build. The paywall panel reads
  "**Payments launching soon** — the $29 full PDF report will be available
  here shortly."
- **Hygiene guards:** `localhost` / `127.x` / `10.x` / `192.168.x` /
  `172.16–31.x` / non-http(s) schemes are rejected client-side. 2 MB page
  cap, 25 s fetch timeout.

## Why static instead of the Python server

The sandbox running this agent cannot host an inbound server publicly:

- Vercel: the connected credential is scoped to the `bone` project only —
  project creation returns HTTP 403. (Do NOT deploy over the Bone project.)
- Cloudflare Quick Tunnel: registration worked, but the sandbox blocks all
  UDP (kills cloudflared's SRV edge discovery) and intercepts direct TCP;
  only `CONNECT host:443` through the egress HTTP proxy is allowed, which
  cloudflared (static Go binary) does not honor.
- localtunnel: its data channel uses a dynamic non-443 port, which the
  egress proxy refuses (`CONNECT` allowed to 443 only).
- ngrok / Render / Fly / Railway / Deno / Netlify / Cloudflare Workers all
  need an account signup (and Fly needs a card) — not done without muni.

GitHub Pages needed no new account (used the existing GitHub connection)
and is durable: no tunnel to keep alive, no idle shutdowns.

## Verification done (2026-09-24)

- `node --check` on the page script: syntax OK.
- Node harness test of pure logic: URL normalization, private-host
  blocking (`localhost`, `127.0.0.1`, `192.168.x`, `10.x`, `ftp:` all
  rejected), 9-check scoring on synthetic signals (score 63, correct
  statuses), zero tip leakage.
- Proxy fetch from this network: allorigins returned `example.com` HTML
  (HTTP 200). `corsproxy.io` now needs an API key; `codetabs` errored —
  both dropped from the fallback list.
- Live: `https://mjaiya5770.github.io/instant-website-audit/` returns
  HTTP 200 and is **byte-identical** to `docs/index.html`.
- **Not yet done:** an in-browser click-through of the Audit button
  (this agent has no live-browser control) — worth one quick visual pass.

## Local dev server (Python edition, unchanged)

The original server implementation (`app.py`, `api/` for Vercel) is intact
in this repo for the future server deployment.

```bash
cd ~/workspace/side-hustle/audit-tool
python3 app.py          # serves on http://localhost:8080
```

Note: local `app.py` still exposes the dev-only demo unlock — never expose
that process publicly; the production behavior lives in `api/index.py`
(demo unlock → 403, PDF locked until verified Stripe payment).

## Stripe enablement checklist (for later, unchanged)

1. Create one-time Stripe product: "Instant Website Audit — Full PDF
   Report", **$29 USD**.
2. Obtain `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`.
3. Add webhook endpoint `/webhooks/stripe` for `checkout.session.completed`.
4. Install Stripe SDK; implement `create_checkout_session`,
   `verify_payment`, `handle_webhook` in `payments.py`.
5. Serverless fulfillment must verify the paid Checkout session before
   releasing the PDF.
6. Keep `AUDIT_SIGNING_KEY` stable and secret.
7. Add persistent order/payment records before real sales.
8. Set `STRIPE_ENABLED = True`.
9. Remove/permanently disable all demo-unlock functionality in production.
10. Run a real $29 test purchase, verify PDF delivery + webhook, then refund.

## Known limitations of the static edition

- Page fetch depends on the public CORS proxy: if allorigins is down or
  rate-limits, audits fail with a clear error. Very large pages (>2 MB),
  JS-rendered sites, and bot-protected sites may not audit cleanly.
- Page-speed check measures proxy fetch time, labeled "(via proxy)".
- No server-side PDF yet — the $29 report ships with Stripe (checklist above).
- When the server edition deploys (Vercel/etc.), `docs/index.html` can be
  retired or kept as the free-tier frontend.
