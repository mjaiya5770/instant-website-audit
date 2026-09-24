"""Instant Website Audit — Vercel serverless entrypoint.

Vercel's Python runtime invokes `Handler(BaseHTTPRequestHandler)` for each
request routed here (see vercel.json rewrites). This is the stateless twin
of app.py (which remains the local dev server):

  - No in-memory AUDITS/PAID dicts: audit data travels in HMAC-signed
    `state` tokens (state.py), so any instance can serve /buy and /report.
  - /api/demo-unlock is DISABLED (403) on the live site.
  - /buy shows a "payments coming soon" page; no checkout, no charges.

Routes: /  /api/config  /api/audit  /buy?state=  /report?state=[&session_id=]
         /webhooks/stripe (501 until Stripe is wired)
"""

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import audit  # noqa: E402
import payments  # noqa: E402
import state  # noqa: E402
from report import build_report_pdf  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")

with open(os.path.join(ROOT, "static", "index.html"), "rb") as f:
    INDEX_HTML = f.read()


def send_json(handler, code, obj):
    body = json.dumps(obj).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_html(handler, code, html):
    body = html.encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "AuditTool/1.0"

    def log_message(self, fmt, *args):
        pass  # quiet

    # -- routing -----------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path, qs = parsed.path, urllib.parse.parse_qs(parsed.query)

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(INDEX_HTML)))
            self.end_headers()
            self.wfile.write(INDEX_HTML)
        elif path == "/api/config":
            send_json(self, 200, {"stripe_enabled": payments.STRIPE_ENABLED,
                                  "price": "$29"})
        elif path == "/buy":
            self.handle_buy(qs.get("state", [""])[0])
        elif path.startswith("/report/"):
            # legacy /report/<id> form has no state -> locked
            self.handle_report("", qs)
        elif path == "/report":
            self.handle_report(qs.get("state", [""])[0], qs)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode() or "{}")
        except ValueError:
            body = {}

        if parsed.path == "/api/audit":
            url = (body.get("url") or "").strip()
            if not url:
                send_json(self, 400, {"ok": False,
                                      "error": "Enter a website URL."})
                return
            try:
                data, result = audit.run_audit(url)
            except ValueError as e:
                send_json(self, 200, {"ok": False, "error": str(e)})
                return
            except Exception:
                send_json(self, 200, {"ok": False,
                                      "error": "Something went wrong auditing "
                                               "that page. Try again."})
                return
            teaser = audit.teaser_for(result)
            teaser.update({"ok": True, "url": data["url"],
                           "state": state.encode(data, result),
                           "paid": False})
            send_json(self, 200, teaser)

        elif parsed.path == "/api/demo-unlock":
            # Disabled on the live site: no free PDFs without payment.
            send_json(self, 403, {"ok": False,
                                  "error": "Demo unlock is disabled on the "
                                           "live site."})

        elif parsed.path == "/webhooks/stripe":
            # [IMPLEMENT] verify signature + fulfill (see payments.py).
            self.send_response(501)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Stripe webhook not implemented. "
                             b"See payments.py handle_webhook().")

        else:
            self.send_error(404)

    # -- handlers ----------------------------------------------------------
    def handle_buy(self, token):
        if not state.decode(token):
            self.send_error(404, "Unknown audit")
            return
        if payments.STRIPE_ENABLED:
            # [IMPLEMENT] real checkout:
            #   url = payments.create_checkout_session(
            #       <audit id from decoded state>,
            #       success_url=<public>/report?state=<token>&session_id={CHECKOUT_SESSION_ID},
            #       cancel_url=<public>/buy?state=<token>)
            #   redirect buyer to url
            try:
                checkout_url = payments.create_checkout_session("", "", "")
            except NotImplementedError as e:
                send_html(self, 501,
                          "<h1>Payments not wired</h1><p>%s</p>" % e)
                return
            self.send_response(302)
            self.send_header("Location", checkout_url)
            self.end_headers()
            return
        # --- payments coming soon (live stub) ------------------------------
        send_html(self, 200, """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Full report coming soon - Instant Website Audit</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.card{background:#1e293b;border:1px solid #334155;border-radius:16px;
padding:32px;max-width:440px;text-align:center}
.price{font-size:44px;font-weight:800;color:#22c55e;margin:8px 0}
.soon{background:#1e3a2f;color:#86efac;border:1px solid #166534;
border-radius:8px;padding:12px;font-size:14px;margin:16px 0}
ul{text-align:left;color:#cbd5e1;font-size:14px;padding-left:20px}
a{color:#94a3b8;font-size:13px}</style></head><body>
<div class="card">
<h2>Full Audit Report</h2>
<div class="price">$29</div>
<div class="soon"><strong>Payments launching soon.</strong><br>
Online checkout isn't connected yet &mdash; your free score above is yours
to keep, and the full PDF report will be purchasable here shortly.</div>
<ul>
<li>Every issue explained in plain English with step-by-step fixes</li>
<li>Priority-ordered: fix the highest-impact items first</li>
<li>Copy-ready snippets (title tags, meta descriptions, schema)</li>
</ul>
<p style="margin-top:18px"><a href="/">Run another free audit</a></p>
</div></body></html>""")

    def handle_report(self, token, qs):
        decoded = state.decode(token)
        session_id = qs.get("session_id", [""])[0]
        authorized = False
        data = result = None
        if decoded:
            data, result = decoded
            if session_id and payments.STRIPE_ENABLED:
                # [IMPLEMENT] real verification:
                #   if payments.verify_payment(session_id): authorized = True
                try:
                    if payments.verify_payment(session_id):
                        authorized = True
                except NotImplementedError:
                    pass
        if not authorized:
            send_html(self, 402, """<!doctype html><html><head><meta charset="utf-8">
<title>Report locked</title><style>body{font-family:system-ui,sans-serif;
background:#0f172a;color:#e2e8f0;display:flex;align-items:center;
justify-content:center;min-height:100vh;margin:0;text-align:center}
a{color:#22c55e}</style></head><body><div>
<h2>This report is locked</h2>
<p>The full PDF audit report is $29. Payments are launching soon.</p>
<p><a href="/">Back to the free audit</a></p>
</div></body></html>""")
            return
        pdf = build_report_pdf(data, result)
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf)))
        self.send_header("Content-Disposition",
                         'attachment; filename="website-audit-report.pdf"')
        self.end_headers()
        self.wfile.write(pdf)
