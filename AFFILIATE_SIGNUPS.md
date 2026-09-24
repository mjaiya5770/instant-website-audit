# Affiliate program signups for Instant Website Audit

The live tool (`docs/index.html`) shows a "Recommended tool" link under every
failed/warned check, currently pointing at clearly-marked placeholder URLs
(`https://AFFILIATE_LINK_TODO_*`). Apply to the programs below, then swap the
real tracked URLs into the `AFFILIATE_TOOLS` map in `docs/index.html`, keeping
`rel="nofollow sponsored noopener"` on every link.

**Apply in this order** — free online approval, no phone call, no tax forms
required to *apply* (tax paperwork only comes up at first payout, which is
normal and handled then).

## 1. Hostinger Affiliate Program — hosting + SSL (speed, https checks)
- Signup: https://www.hostinger.com/affiliates
- Commission: 40–60% per sale. Quick online signup, approval usually fast.
- Placeholder to replace: `AFFILIATE_LINK_TODO_hosting`

## 2. ShortPixel Affiliate Program — image optimization (alt-text check)
- Signup: https://shortpixel.com/free-sign-up-affiliate
- Commission: 30% of all new sales, including recurring. Free account signup,
  team reviews and approves via email.
- Placeholder to replace: `AFFILIATE_LINK_TODO_image_optimizer`

## 3. Mangools Affiliate Program — SEO suite (title, meta, h1, schema checks)
- Signup: https://mangools.com/affiliate
- Commission: 30% lifetime recurring. No manual approval gate — affiliate
  access comes with the free account.
- Placeholder to replace: `AFFILIATE_LINK_TODO_seo_suite`

## 4. Surfer SEO Affiliate Program — on-page optimizer (title, meta, h1 checks)
- Signup: https://surferseo.com/affiliate-program/
- Commission: 75–125% of a monthly subscriber's first payment (tiered), 90-day
  cookie. Application reviewed manually (1–3 days), managed via PartnerStack.
- Placeholder to replace: `AFFILIATE_LINK_TODO_seo_suite`
- Note: Surfer and Mangools map to the same placeholder — pick whichever
  approves first, then point the URL at the winner.

## 5. Semrush Affiliate Program — local SEO / listings (Google Business Profile check)
- Signup: https://www.semrush.com/partner/
- Commission: $200 per sale / $10 per trial. Runs on Impact; online approval,
  tax info only needed before first payout.
- Placeholder to replace: `AFFILIATE_LINK_TODO_local_seo`
- Note: BrightLocal's affiliate program is currently closed to new
  applications, so Semrush (Listing Management) is the fallback here.

## 6. Namecheap Affiliate Program — hosting / SSL / domains (speed, https checks)
- Signup: https://www.namecheap.com/affiliates/ (enroll via Impact or CJ)
- Commission: 20–50% depending on product (hosting 35%, SSL 35%, domains 20%).
  Free signup, application review takes a few days.
- Alternate placeholder for `AFFILIATE_LINK_TODO_hosting` if Hostinger declines.

## Mobile viewport check — website builder
- Placeholder `AFFILIATE_LINK_TODO_website_builder` is currently unassigned.
  Candidates with easy online approval: **Systeme.io**
  (https://systeme.io/affiliate-program/, 60% recurring, open to anyone) or
  **Strikingly** — apply once traffic justifies it. Until then the template-pack
  cross-promo covers this audience.

---

## Lower priority (require tax info or a call at signup — do later)

- **Bluehost** (https://www.bluehost.com/affiliates) — $65+ per hosting sale,
  but signup runs through Impact.com and asks for tax/company info up front.
- **Cloudways** — up to $125/sale, but enrollment requires creating a
  Cloudways account first; apply from inside the dashboard.

## After approval checklist

1. Grab each program's tracked link.
2. Replace the matching `AFFILIATE_LINK_TODO_*` URL in `docs/index.html`
   (`AFFILIATE_TOOLS` map near the top of the `<script>`).
3. Keep `rel="nofollow sponsored noopener"` and `target="_blank"`.
4. The footer already carries an affiliate disclosure — update its wording if
   a program requires specific disclosure text.
5. Commit + push to `main`; GitHub Pages redeploys automatically.
