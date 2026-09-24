"""Instant Website Audit — PDF report generator.

Writes the paywalled $29 audit report as a real PDF using only the
Python standard library (hand-rolled minimal PDF writer: no pip deps).

build_report_pdf(data, result, generated) -> bytes
"""

import datetime

# A4 points
PAGE_W, PAGE_H = 595.0, 842.0
MARGIN = 48.0

NAVY = (0.10, 0.15, 0.27)
DARK = (0.16, 0.19, 0.24)
GRAY = (0.42, 0.45, 0.50)
LGRAY = (0.94, 0.95, 0.97)
GREEN = (0.10, 0.62, 0.33)
AMBER = (0.85, 0.47, 0.02)
RED = (0.86, 0.15, 0.15)
WHITE = (1.0, 1.0, 1.0)

STATUS_STYLE = {
    "pass": (GREEN, "PASS"),
    "warn": (AMBER, "NEEDS WORK"),
    "fail": (RED, "MISSING"),
    "na": (GRAY, "N/A"),
}


def _esc(s):
    return (s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
             .encode("latin-1", errors="replace").decode("latin-1"))


class PDFWriter:
    def __init__(self):
        self.objs = []
        self.fonts = {}

    def _new(self, body):
        self.objs.append(body)
        return len(self.objs)

    def _ref(self, n):
        return "%d 0 R" % n

    def add_font(self, base):
        n = self._new("<< /Type /Font /Subtype /Type1 /BaseFont /%s >>" % base)
        self.fonts[base] = self._ref(n)
        return n

    def add_stream(self, content):
        raw = content.encode("latin-1", errors="replace")
        n = self._new("<< /Length %d >>\nstream\n" % len(raw)
                      + raw.decode("latin-1") + "\nendstream")
        return n

    def render(self, page_stream_refs):
        # fonts
        self.add_font("Helvetica")
        self.add_font("Helvetica-Bold")
        # pages
        page_refs = []
        for stream_ref in page_stream_refs:
            p = self._new(
                "<< /Type /Page /Parent %s /MediaBox [0 0 %d %d] "
                "/Resources << /Font << /F1 %s /F2 %s >> >> "
                "/Contents %s >>"
                % ("PAGES", PAGE_W, PAGE_H,
                   self.fonts["Helvetica"], self.fonts["Helvetica-Bold"],
                   self._ref(stream_ref)))
            page_refs.append(self._ref(p))
        pages = self._new("<< /Type /Pages /Kids [%s] /Count %d >>"
                          % (" ".join(page_refs), len(page_refs)))
        catalog = self._new("<< /Type /Catalog /Pages %s >>" % self._ref(pages))
        # fix parent ref
        self.objs[pages - 1] = self.objs[pages - 1].replace("PAGES", self._ref(pages))

        out = ["%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
        offsets = []
        for i, body in enumerate(self.objs, start=1):
            offsets.append(sum(len(x) for x in out))
            out.append("%d 0 obj\n%s\nendobj\n" % (i, body))
        xref_pos = sum(len(x) for x in out)
        out.append("xref\n0 %d\n" % (len(self.objs) + 1))
        out.append("0000000000 65535 f \n")
        for off in offsets:
            out.append("%010d 00000 n \n" % off)
        out.append("trailer\n<< /Size %d /Root %s >>\nstartxref\n%d\n%%%%EOF\n"
                   % (len(self.objs) + 1, self._ref(catalog), xref_pos))
        return "".join(out).encode("latin-1", errors="replace")


class Report:
    def __init__(self):
        self.w = PDFWriter()
        self.streams = []
        self.ops = []
        self.y = 0.0
        self.new_page(first=True)

    # -- drawing primitives -------------------------------------------------
    def rect(self, x, y, w, h, color, fill=True):
        self.ops.append("%.1f %.1f %.1f rg %.1f %.1f %.1f %.1f re %s"
                        % (color + (x, y, w, h, "f" if fill else "S")))

    def text(self, x, y, s, size=10, bold=False, color=DARK, max_w=None):
        s = _esc(s)
        f = "F2" if bold else "F1"
        c = "%.2f %.2f %.2f rg" % color
        if max_w:
            # crude truncation
            while len(s) > 8 and len(s) * size * 0.55 > max_w:
                s = s[:-1]
            if len(s) * size * 0.55 > max_w:
                s = s[:max(0, int(max_w / (size * 0.55)) - 1)] + "."
        self.ops.append("BT /%s %d Tf %s %.1f %.1f Td (%s) Tj ET"
                        % (f, size, c, x, y, s))

    def wrapped(self, x, y, s, size=10, bold=False, color=DARK,
                width=PAGE_W - 2 * MARGIN, leading=None):
        leading = leading or size * 1.45
        words = s.split()
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * size * 0.52 > width and line:
                self.text(x, y, line, size, bold, color)
                y -= leading
                line = word
                self.need(y)
            else:
                line = test
        if line:
            self.text(x, y, line, size, bold, color)
            y -= leading
        return y

    def need(self, y_after, min_gap=60):
        if y_after < MARGIN + min_gap:
            self.new_page()

    def new_page(self, first=False):
        if not first:
            self.streams.append(self.w.add_stream("\n".join(self.ops)))
        self.ops = []
        self.y = PAGE_H - MARGIN

    def finish(self):
        self.streams.append(self.w.add_stream("\n".join(self.ops)))
        return self.w.render(self.streams)


def _short_host(url):
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
        return u.hostname or url[:40]
    except Exception:
        return url[:40]


def build_report_pdf(data, result, generated=None):
    """Return the full audit report as PDF bytes."""
    generated = generated or datetime.datetime.now().strftime("%B %d, %Y")
    score = result["score"]
    color = GREEN if score >= 80 else AMBER if score >= 50 else RED

    r = Report()
    host = _short_host(data["url"])

    # --- header band -------------------------------------------------------
    r.rect(0, PAGE_H - 130, PAGE_W, 130, NAVY)
    r.text(MARGIN, PAGE_H - 58, "Instant Website Audit", 26, True, WHITE)
    r.text(MARGIN, PAGE_H - 84, "Full SEO report  -  %s" % host, 12, False,
           (0.75, 0.80, 0.88), max_w=PAGE_W - 2 * MARGIN)
    r.text(MARGIN, PAGE_H - 106, "Generated %s" % generated, 10, False,
           (0.65, 0.70, 0.78))

    r.y = PAGE_H - 170

    # --- score box ---------------------------------------------------------
    r.rect(MARGIN, r.y - 74, PAGE_W - 2 * MARGIN, 74, LGRAY)
    r.text(MARGIN + 18, r.y - 52, str(score), 44, True, color)
    r.text(MARGIN + 92, r.y - 34, "/ 100", 18, True, GRAY)
    label = ("Excellent - minor polish left." if score >= 80 else
             "Decent foundation - several quick wins available." if score >= 50
             else "Major gaps found - start with the reds below.")
    r.y = r.wrapped(MARGIN + 92, r.y - 58, label, 11, False, DARK,
                    width=PAGE_W - 2 * MARGIN - 110)
    r.y -= 18

    # --- page snapshot -----------------------------------------------------
    r.text(MARGIN, r.y, "Page snapshot", 14, True, NAVY)
    r.y -= 20
    snap = [
        ("URL", data["url"][:80]),
        ("Title", (data["title"] or "(none)")[:90]),
        ("Word count", str(data["wordCount"])),
        ("H1s / H2s", "%d / %d" % (data["h1Count"], data["h2Count"])),
        ("Images", "%d total, %d missing alt text"
         % (data["imagesTotal"], data["imagesMissingAlt"])),
    ]
    for k, v in snap:
        r.text(MARGIN, r.y, k + ":", 10, True, DARK)
        r.text(MARGIN + 110, r.y, v, 10, False, DARK,
               max_w=PAGE_W - 2 * MARGIN - 110)
        r.y -= 16
    r.y -= 10

    # --- priority fixes (fails first, then warns) --------------------------
    r.text(MARGIN, r.y, "Fix these first (priority order)", 14, True, NAVY)
    r.y -= 20
    ordered = ([c for c in result["checks"] if c["status"] == "fail"]
               + [c for c in result["checks"] if c["status"] == "warn"])
    if not ordered:
        r.y = r.wrapped(MARGIN, r.y,
                        "Nothing urgent - every scored check passed. "
                        "Keep content fresh and monitor speed.", 11)
    for i, c in enumerate(ordered, 1):
        r.need(r.y - 70)
        r.text(MARGIN, r.y, "%d. %s" % (i, c["name"]), 11, True, DARK)
        r.y -= 15
        r.y = r.wrapped(MARGIN + 12, r.y, c["detail"], 10, False, GRAY)
        if c["tip"]:
            r.y = r.wrapped(MARGIN + 12, r.y, "How to fix: " + c["tip"], 10,
                            False, DARK)
        r.y -= 8

    # --- full check detail -------------------------------------------------
    r.new_page()
    r.text(MARGIN, r.y, "Full check detail", 16, True, NAVY)
    r.y -= 24
    for c in result["checks"]:
        r.need(r.y - 80)
        badge_color, badge_label = STATUS_STYLE[c["status"]]
        r.rect(MARGIN, r.y - 16, 92, 20, badge_color)
        r.text(MARGIN + 6, r.y - 12, badge_label, 9, True, WHITE)
        r.text(MARGIN + 104, r.y, c["name"], 12, True, DARK)
        r.y -= 28  # clear the badge rect before detail text
        r.y = r.wrapped(MARGIN, r.y, c["detail"], 10, False, DARK)
        if c["tip"]:
            r.y = r.wrapped(MARGIN, r.y, "How to fix: " + c["tip"], 10, False,
                            GRAY)
        r.y -= 10

    # --- footer note -------------------------------------------------------
    r.need(r.y - 60)
    r.text(MARGIN, r.y, "About this report", 12, True, NAVY)
    r.y -= 16
    r.y = r.wrapped(
        MARGIN, r.y,
        "This audit checks 9 on-page SEO signals: title tag, meta description, "
        "mobile viewport, headings, image alt text, structured data, Google "
        "Business Profile link, page speed, and HTTPS. Scores are a weighted "
        "average (pass = 1, needs work = 0.5, missing = 0). This is general "
        "guidance, not a guarantee of rankings.", 9, False, GRAY)

    return r.finish()
