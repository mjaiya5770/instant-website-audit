#!/usr/bin/env python3
"""Instant Website Audit — $29/report.

Free: enter any URL, get a 0-100 score + teaser.
Paywalled: the full PDF audit report (fix tips, priority list, check detail).

Run:  python3 app.py [--port 8080]
Demo: http://localhost:8080

Payment: see payments.py. While STRIPE_ENABLED is False the /buy page
shows the payment stub with a DEMO unlock button so the flow is testable
end to end. Flip STRIPE_ENABLED and implement the two marked functions
to take real money.
"""

import json
import os
import secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import audit
import payments
import state
from report import build_report_pdf

HERE = os.path.dirname(os.path.abspath(__file__))

# In-memory stores (swap for a DB in production).
AUDITS = {}        # audit_id -> {"data":..., "result":...}
PAID = set()       # audit_ids with completed payment
DEMO_TOKENS = {}   # audit_id -> set(tokens)


def new_id():
    return secrets.token_hex(8)


def send_json(handler, code, obj):
    body = json.dumps(obj).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def serve_file(handler, path, ctype):
    try:
        with open(path, "rb") as f:
            body = f.read()
    except FileNotFoundError:
        handler.send_error(404)
        return
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
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
            serve_file(self, os.path.join(HERE, "static", "index.html"),
                       "text/html; charset=utf-8")
        elif path == "/api/config":
            send_json(self, 200, {"stripe_enabled": payments.STRIPE_ENABLED,
                                  "price": "$29"})
        elif path == "/buy":
            self.handle_buy(qs.get("state", [""])[0],
                            qs.get("audit_id", [""])[0])
        elif path.startswith("/report/"):
            self.handle_report(path[len("/report/"):], qs, "")
        elif path == "/report":
            self.handle_report("", qs, qs.get("state", [""])[0])
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
            aid = new_id()
            AUDITS[aid] = {"data": data, "result": result}
            teaser = audit.teaser_for(result)
            teaser.update({"ok": True, "audit_id": aid, "url": data["url"],
                           "state": state.encode(data, result),
                           "paid": aid in PAID})
            send_json(self, 200, teaser)

        elif parsed.path == "/api/demo-unlock":
            if payments.STRIPE_ENABLED:
                send_json(self, 403, {"ok": False,
                                      "error": "Demo unlock disabled."})
                return
            tok_state = (body.get("state") or "").strip()
            aid = (body.get("audit_id") or "").strip()
            token = None
            if tok_state and state.decode(tok_state):
                # Stateless: the signed state IS the PDF token.
                token = tok_state
            elif aid in AUDITS:
                # Legacy audit_id path: mint a signed state token for it.
                rec = AUDITS[aid]
                token = state.encode(rec["data"], rec["result"])
            if not token:
                send_json(self, 404, {"ok": False, "error": "Unknown audit."})
                return
            send_json(self, 200, {"ok": True, "token": token})

        elif parsed.path == "/webhooks/stripe":
            # [IMPLEMENT] verify signature + mark paid (see payments.py).
            self.send_response(501)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Stripe webhook not implemented. "
                             b"See payments.py handle_webhook().")

        else:
            self.send_error(404)

    # -- handlers ----------------------------------------------------------
    def handle_buy(self, token, audit_id=""):
        decoded = state.decode(token) if token else None
        if not decoded and audit_id not in AUDITS:
            self.send_error(404, "Unknown audit")
            return
        # The demo button posts back whichever identifier we were given.
        post_back = (json.dumps({"state": token}) if decoded
                     else json.dumps({"audit_id": audit_id}))
        link_token = token if decoded else audit_id
        if payments.STRIPE_ENABLED:
            # [IMPLEMENT] real checkout:
            #   url = payments.create_checkout_session(
            #       audit_id,
            #       success_url=<public>/buy-success,
            #       cancel_url=<public>/buy?audit_id=<id>)
            #   redirect buyer to url
            try:
                checkout_url = payments.create_checkout_session(audit_id, "", "")
            except NotImplementedError as e:
                self._html(501, "<h1>Payments not wired</h1><p>%s</p>" % e)
                return
            self.send_response(302)
            self.send_header("Location", checkout_url)
            self.end_headers()
            return
        # --- payment stub (demo) -----------------------------------------
        page = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Checkout - Instant Website Audit</title>
<style>body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;
display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.card{background:#1e293b;border:1px solid #334155;border-radius:16px;
padding:32px;max-width:420px;text-align:center}
.price{font-size:44px;font-weight:800;color:#22c55e;margin:8px 0}
.stub{background:#422006;color:#fdba74;border:1px solid #92400e;
border-radius:8px;padding:10px;font-size:13px;margin:16px 0}
button{background:#22c55e;color:#052e16;border:0;border-radius:10px;
padding:14px 28px;font-size:16px;font-weight:700;cursor:pointer;width:100%}
a{color:#94a3b8;font-size:13px}</style></head><body>
<div class="card">
<h2>Full Audit Report</h2>
<div class="price">$29</div>
<p style="color:#94a3b8">The complete PDF: every fix explained, priority order,
copy-ready snippets.</p>
<div class="stub"><strong>PAYMENT STUB</strong> - Stripe Checkout is not
connected. In production this button opens Stripe's hosted checkout.
Wire it up per <code>payments.py</code>.</div>
<button id="demo">DEMO: simulate successful payment</button>
<p style="margin-top:14px"><a href="/">Back</a></p>
</div>
<script>
document.getElementById('demo').onclick = async () => {
  const r = await fetch('/api/demo-unlock', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body: __POST_BACK__});
  const j = await r.json();
  if (j.ok) location.href = '/report?state=' + encodeURIComponent(j.token);
  else alert(j.error || 'failed');
};
</script></body></html>"""
        page = page.replace("__POST_BACK__", post_back)
        page = page.replace("__AID_JSON__", json.dumps(link_token))
        page = page.replace("__AID__", link_token)
        self._html(200, page)

    def handle_report(self, audit_id, qs, token=""):
        decoded = state.decode(token) if token else None
        if decoded:
            data, result = decoded
            pdf = build_report_pdf(data, result)
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(pdf)))
            self.send_header("Content-Disposition",
                             'attachment; filename="website-audit-report.pdf"')
            self.end_headers()
            self.wfile.write(pdf)
            return
        if token:
            # A state token was given but its signature is invalid.
            self._locked_report()
            return
        rec = AUDITS.get(audit_id)
        if not rec:
            self.send_error(404, "Unknown audit")
            return
        token = qs.get("token", [""])[0]
        session_id = qs.get("session_id", [""])[0]
        authorized = audit_id in PAID or token in DEMO_TOKENS.get(audit_id, set())
        if not authorized and session_id and payments.STRIPE_ENABLED:
            # [IMPLEMENT] real verification:
            #   verified_id = payments.verify_payment(session_id)
            #   if verified_id: PAID.add(verified_id); authorized = True
            try:
                verified_id = payments.verify_payment(session_id)
                if verified_id:
                    PAID.add(verified_id)
                    authorized = audit_id in PAID
            except NotImplementedError:
                pass
        if not authorized:
            self._locked_report()
            return
        pdf = build_report_pdf(rec["data"], rec["result"])
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(pdf)))
        self.send_header("Content-Disposition",
                         'attachment; filename="website-audit-report.pdf"')
        self.end_headers()
        self.wfile.write(pdf)

    def _locked_report(self):
        self._html(402, """<!doctype html><html><head><meta charset="utf-8">
<title>Report locked</title><style>body{font-family:system-ui,sans-serif;
background:#0f172a;color:#e2e8f0;display:flex;align-items:center;
justify-content:center;min-height:100vh;margin:0;text-align:center}
a{color:#22c55e}</style></head><body><div>
<h2>This report is locked</h2>
<p>The full PDF audit report is $29. Payments are launching soon.</p>
<p><a href="/">Back to the free audit</a></p>
</div></body></html>""")

    def _html(self, code, html):
        body = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print("Instant Website Audit running at http://localhost:%d" % args.port)
    print("Stripe enabled: %s" % payments.STRIPE_ENABLED)
    srv.serve_forever()


if __name__ == "__main__":
    main()
