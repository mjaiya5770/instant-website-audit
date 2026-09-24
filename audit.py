"""Instant Website Audit — audit engine.

Server-side port of the 9 SEO checks from the Local SEO Quick Check
Chrome extension (~/workspace/side-hustle/extension/local-seo-check/).
Fetches the target URL, extracts on-page signals with stdlib html.parser,
and scores them with the same weighted logic as the extension.

scoreAudit(data) returns { score: 0-100, checks: [ {id, name, status, detail, tip} ] }
status in: pass | warn | fail | na
"""

import json
import os
import time
import socket
import ipaddress
import urllib.request
import urllib.parse
from html.parser import HTMLParser

# Dev-only escape hatch: AUDIT_TOOL_ALLOW_PRIVATE=1 skips the SSRF guard so
# you can audit localhost / staging sites during development. NEVER set this
# in production.
_ALLOW_PRIVATE = os.environ.get("AUDIT_TOOL_ALLOW_PRIVATE") == "1"

USER_AGENT = (
    "Mozilla/5.0 (compatible; InstantWebsiteAudit/1.0; "
    "+https://example.com/audit-bot) SEO-audit-tool"
)
FETCH_TIMEOUT = 12
MAX_BYTES = 2 * 1024 * 1024  # 2 MB cap on downloaded HTML


# ----------------------------------------------------------------------------
# Fetching (with basic SSRF guard)
# ----------------------------------------------------------------------------

def _is_public_ip(ip_str):
    try:
        ip = ipaddress.ip_address(ip_str)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_multicast or ip.is_reserved)
    except ValueError:
        return False


def _doh_ips(hostname):
    """Resolve hostname via DNS-over-HTTPS (Cloudflare) -> [ip strings].

    Used only for the SSRF safety decision: some hosting sandboxes
    intercept local DNS and answer every query with a NAT/proxy IP, which
    would make the guard reject every public host. The real DNS answer
    tells us whether the hostname genuinely points at public space.
    Raises on any failure (caller falls back to local resolution).
    """
    url = ("https://cloudflare-dns.com/dns-query?name=%s&type=A"
           % urllib.parse.quote(hostname))
    req = urllib.request.Request(
        url, headers={"Accept": "application/dns-json",
                      "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.load(resp)
    ips = [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]
    if not ips:
        raise ValueError("no A records")
    return ips


def _ips_public(ips):
    ips = list(ips)
    return bool(ips) and all(_is_public_ip(ip) for ip in ips)


def _host_resolves_public(hostname):
    # Prefer the real-DNS (DoH) answer for the safety decision; fall back
    # to local resolution (fail closed) if DoH is unreachable.
    try:
        return _ips_public(_doh_ips(hostname))
    except Exception:
        pass
    try:
        ips = []
        for family, _, _, _, sockaddr in socket.getaddrinfo(hostname, None):
            ip_str = sockaddr[0]
            if family == socket.AF_INET6 and ip_str.startswith("::ffff:"):
                ip_str = ip_str[7:]
            ips.append(ip_str)
        return _ips_public(ips)
    except (socket.gaierror, socket.herror):
        return False


def fetch_page(url):
    """Return (final_url, html, load_ms). Raises ValueError on problems."""
    if "://" not in url:
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http(s) URLs can be audited.")
    if not parsed.hostname:
        raise ValueError("Could not parse a hostname from that URL.")
    if not _ALLOW_PRIVATE and not _host_resolves_public(parsed.hostname):
        raise ValueError("That host can't be reached for auditing.")

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    start = time.perf_counter()
    try:
        resp = urllib.request.urlopen(req, timeout=FETCH_TIMEOUT)
    except Exception as e:
        raise ValueError("Could not load the page: %s" % _short_err(e))
    load_ms = int((time.perf_counter() - start) * 1000)

    ctype = (resp.headers.get("Content-Type") or "").lower()
    if "text/html" not in ctype and "text/" not in ctype:
        raise ValueError("That URL did not return an HTML page.")

    raw = resp.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Page is too large to audit.")
    charset = resp.headers.get_content_charset() or "utf-8"
    html = raw.decode(charset, errors="replace")
    return resp.geturl(), html, load_ms


def _short_err(e):
    s = str(e)
    return s[:120] if s else type(e).__name__


# ----------------------------------------------------------------------------
# HTML signal extraction
# ----------------------------------------------------------------------------

GBP_PATTERNS = ("google.com/maps", "goo.gl/maps", "maps.google.",
                "business.google.com", "g.page/", "maps.app.goo.gl")


class SeoParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self.meta = {}
        self.has_viewport = False
        self.canonical = ""
        self.h1_count = 0
        self.h2_count = 0
        self._in_h1 = False
        self._h1_buf = ""
        self.h1_texts = []
        self.images_total = 0
        self.images_missing_alt = 0
        self.json_ld_types = []
        self.microdata_count = 0
        self.has_gbp_link = False
        self._in_json_ld = False
        self._json_ld_buf = ""
        self._in_body = False
        self._skip_depth = 0  # inside script/style
        self._text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self._skip_depth += 1
            if (tag == "script" and
                    attrs.get("type", "").lower() == "application/ld+json"):
                self._in_json_ld = True
                self._json_ld_buf = ""
            return
        if tag == "body":
            self._in_body = True
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (attrs.get("name") or attrs.get("property") or "").lower()
            content = (attrs.get("content") or "").strip()
            if name:
                self.meta.setdefault(name, content)
            if name == "viewport":
                self.has_viewport = True
        elif tag == "link" and attrs.get("rel", "").lower() == "canonical":
            self.canonical = (attrs.get("href") or "").strip()
        elif tag == "h1":
            self.h1_count += 1
            self._in_h1 = True
            self._h1_buf = ""
        elif tag == "h2":
            self.h2_count += 1
        elif tag == "img":
            self.images_total += 1
            alt = attrs.get("alt")
            if alt is None or not alt.strip():
                self.images_missing_alt += 1
        elif tag == "a":
            href = (attrs.get("href") or "").lower()
            if any(p in href for p in GBP_PATTERNS):
                self.has_gbp_link = True
        if "itemscope" in attrs:
            self.microdata_count += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip_depth = max(0, self._skip_depth - 1)
            if self._in_json_ld and tag == "script":
                self._in_json_ld = False
                self._harvest_json_ld(self._json_ld_buf)
        elif tag == "title":
            self._in_title = False
        elif tag == "h1":
            if self._in_h1:
                text = self._h1_buf.strip()[:80]
                if text:
                    self.h1_texts.append(text)
                self._in_h1 = False
        elif tag == "body":
            self._in_body = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_h1:
            self._h1_buf += data
        if self._in_json_ld:
            self._json_ld_buf += data
        if self._in_body and self._skip_depth == 0:
            self._text_parts.append(data)

    def _harvest_json_ld(self, text):
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and "@type" in item:
                types = item["@type"]
                if not isinstance(types, list):
                    types = [types]
                for t in types:
                    if t not in self.json_ld_types:
                        self.json_ld_types.append(str(t))

    def word_count(self):
        return len(" ".join(self._text_parts).split())


def extract_signals(final_url, html, load_ms):
    p = SeoParser()
    p.feed(html)
    title = p.title.strip()
    desc = (p.meta.get("description") or "").strip()
    return {
        "url": final_url,
        "protocol": urllib.parse.urlparse(final_url).scheme + ":",
        "title": title,
        "titleLength": len(title),
        "metaDescription": desc,
        "metaDescriptionLength": len(desc),
        "hasViewport": p.has_viewport,
        "h1Count": p.h1_count,
        "h1Texts": p.h1_texts[:3],
        "h2Count": p.h2_count,
        "canonical": p.canonical,
        "imagesTotal": p.images_total,
        "imagesMissingAlt": p.images_missing_alt,
        "jsonLdTypes": p.json_ld_types,
        "microdataCount": p.microdata_count,
        "hasGbpLink": p.has_gbp_link,
        "loadTimeMs": load_ms,
        "ogTitle": (p.meta.get("og:title") or "").strip(),
        "ogDescription": (p.meta.get("og:description") or "").strip(),
        "ogImage": (p.meta.get("og:image") or "").strip(),
        "robotsMeta": (p.meta.get("robots") or "").strip(),
        "wordCount": p.word_count(),
    }


# ----------------------------------------------------------------------------
# Scoring — same 9 checks / weights as the Chrome extension
# ----------------------------------------------------------------------------

def score_audit(d):
    checks = []

    def add(cid, name, status, detail, tip=""):
        checks.append({"id": cid, "name": name, "status": status,
                       "detail": detail, "tip": tip})

    # 1. Title tag
    if not d["title"]:
        add("title", "Title tag", "fail", "No <title> set.",
            "Add a unique title, 30-60 characters, with your main keyword + city.")
    elif d["titleLength"] < 30 or d["titleLength"] > 60:
        add("title", "Title tag", "warn",
            "Title is %d characters (ideal: 30-60)." % d["titleLength"],
            "Trim or expand to 30-60 characters; put the keyword near the front.")
    else:
        add("title", "Title tag", "pass",
            "Title is %d characters - in the ideal range." % d["titleLength"])

    # 2. Meta description
    if not d["metaDescription"]:
        add("meta", "Meta description", "fail", "No meta description.",
            "Write a 50-160 character description with a call to action - "
            "it controls your Google snippet.")
    elif d["metaDescriptionLength"] < 50 or d["metaDescriptionLength"] > 160:
        add("meta", "Meta description", "warn",
            "Description is %d characters (ideal: 50-160)." % d["metaDescriptionLength"],
            "Aim for 50-160 characters so Google shows it in full.")
    else:
        add("meta", "Meta description", "pass",
            "Description is %d characters - in the ideal range." % d["metaDescriptionLength"])

    # 3. Mobile viewport
    if d["hasViewport"]:
        add("viewport", "Mobile viewport", "pass",
            "Viewport meta tag present - page is mobile-ready.")
    else:
        add("viewport", "Mobile viewport", "fail", "No viewport meta tag.",
            'Add <meta name="viewport" content="width=device-width, initial-scale=1">.')

    # 4. H1
    if d["h1Count"] == 1:
        h1 = d["h1Texts"][0] if d["h1Texts"] else ""
        add("h1", "Headings (H1)", "pass", 'Exactly one H1: "%s".' % h1)
    elif d["h1Count"] == 0:
        add("h1", "Headings (H1)", "fail", "No H1 found.",
            "Add one H1 describing the page's main topic (service + city works well).")
    else:
        add("h1", "Headings (H1)", "warn", "%d H1s found." % d["h1Count"],
            "Keep a single H1 per page; demote extras to H2.")

    # 5. Image alt text
    if d["imagesTotal"] == 0:
        add("alt", "Image alt text", "na", "No images on this page.")
    else:
        pct = round((d["imagesTotal"] - d["imagesMissingAlt"])
                    / d["imagesTotal"] * 100)
        if pct >= 90:
            add("alt", "Image alt text", "pass",
                "%d%% of %d images have alt text." % (pct, d["imagesTotal"]))
        elif pct >= 50:
            add("alt", "Image alt text", "warn",
                "Only %d%% of %d images have alt text." % (pct, d["imagesTotal"]),
                "Describe each image in its alt attribute - it helps image "
                "search and accessibility.")
        else:
            add("alt", "Image alt text", "fail",
                "Only %d%% of %d images have alt text." % (pct, d["imagesTotal"]),
                "Add descriptive alt text to every image.")

    # 6. Structured data
    if d["jsonLdTypes"]:
        add("schema", "Structured data", "pass",
            "JSON-LD found: %s." % ", ".join(d["jsonLdTypes"]))
    elif d["microdataCount"] > 0:
        add("schema", "Structured data", "warn",
            "Microdata found but no JSON-LD.",
            "Prefer JSON-LD; add LocalBusiness schema for rich results.")
    else:
        add("schema", "Structured data", "fail", "No schema.org markup detected.",
            "Add JSON-LD LocalBusiness schema so Google can show rich results "
            "(hours, ratings).")

    # 7. Google Business Profile link
    if d["hasGbpLink"]:
        add("gbp", "Google Business Profile link", "pass",
            "Page links to Google Maps / Business Profile.")
    else:
        add("gbp", "Google Business Profile link", "warn",
            "No link to your Google Maps listing found.",
            "Link your Google Business Profile (maps link) in the footer or "
            "contact section.")

    # 8. Fetch time (server-side proxy for page speed)
    ms = d["loadTimeMs"]
    if ms is None or ms <= 0:
        add("speed", "Page speed", "na", "Could not measure load time.")
    else:
        s = ms / 1000.0
        if ms < 2500:
            add("speed", "Page speed", "pass", "Page fetched in ~%.1fs." % s)
        elif ms < 4000:
            add("speed", "Page speed", "warn",
                "Page fetched in ~%.1fs (aim under 2.5s)." % s,
                "Compress images, defer non-critical scripts, and enable caching.")
        else:
            add("speed", "Page speed", "fail",
                "Page fetched in ~%.1fs - too slow." % s,
                "Compress images, defer non-critical scripts, and consider "
                "better hosting.")

    # 9. HTTPS
    proto = d["protocol"]
    if proto == "https:":
        add("https", "HTTPS", "pass", "Served over HTTPS.")
    elif proto == "file:" or "localhost" in d["url"] or "127.0.0.1" in d["url"]:
        add("https", "HTTPS", "na", "Local/test URL - HTTPS check not applicable.")
    else:
        add("https", "HTTPS", "fail", "Page is not served over HTTPS.",
            "Install an SSL certificate - HTTPS is a Google ranking factor.")

    # Weighted score: pass=1, warn=0.5, fail=0; na excluded.
    scored = [c for c in checks if c["status"] != "na"]
    points = sum(1 if c["status"] == "pass" else 0.5 if c["status"] == "warn" else 0
                 for c in scored)
    score = round(points / len(scored) * 100) if scored else 0
    return {"score": score, "checks": checks}


def run_audit(url):
    """Full pipeline: fetch -> signals -> score. Returns (data, result)."""
    final_url, html, load_ms = fetch_page(url)
    data = extract_signals(final_url, html, load_ms)
    result = score_audit(data)
    return data, result


def teaser_for(result):
    """Free teaser: everything except the fix tips (those are paywalled)."""
    return {
        "score": result["score"],
        "checks": [
            {"id": c["id"], "name": c["name"], "status": c["status"],
             "detail": c["detail"]}
            for c in result["checks"]
        ],
        "fails": sum(1 for c in result["checks"] if c["status"] == "fail"),
        "warns": sum(1 for c in result["checks"] if c["status"] == "warn"),
    }
