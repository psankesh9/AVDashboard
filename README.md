# AV Validation Gap — Dashboard

**Live:** https://av-validation-gap-site-disengagemen.vercel.app
**All dashboards:** https://av-validation-gap-landing.vercel.app (collision-risk model, full view, pooled-data experiment, and this one)

UC Berkeley MIDS 210 capstone. This is the disengagement-risk dashboard: scores California
census tracts (SF, LA, Santa Clara) by road type — freeway, arterial, local street — against how
much CA DMV disengagement reports concentrate on each type statewide, across 39 companies. Waymo
is 1.8% of the underlying data; this is an industry-wide pattern, not a Waymo-specific one.

No public dataset has miles-by-road-type for any company, so OpenStreetMap road length stands in
for it — stated on the dashboard itself. A leave-one-company-out check found the pattern beats a
naive baseline on only 8 of 15 companies tested, close to chance. Shipped anyway, with that stated
plainly, because the underlying collision-risk model (the other dashboards) is unaffected and the
professor's ask was specifically to try this, framed as risk rather than event prediction.

## What's in this repo

- **`index.html`** — this dashboard, self-contained (data embedded as JSON at build time).
- **`disengagement_risk.py`** — the model: fleet base rate, road-type concentration ratios with a
  cluster-bootstrap 90% range, and the exposure-proxy assumption, documented inline.
- **`source/template.html`** — the shared dashboard template all four variants build from.
- **`REPORT.md`, `VALIDATION_REPORT.md`, `PROFESSOR_RESPONSE.md`** — the collision-risk model's
  full results, validation, and response to course feedback (still the more rigorously validated
  of the two models here).

The **`dashboards`** branch has all four variants as separate files (collision-risk, full,
combined, disengagement) plus a landing page linking them.

## The two models, in one paragraph each

**Collision risk** (the original model): negative binomial regression on expected collisions per
census tract per quarter, from land area, housing density, service maturity, and marked-crosswalk
density. Validated four ways — spatial hold-out (41%), temporal hold-out (39%), an out-of-time test
against a different operator's crash data (Spearman 0.39), and an NHTSA cross-check (0.74). Only
Waymo-trained; exposure is real (actual trip counts).

**Disengagement risk** (this dashboard): a relative-risk multiplier from CA DMV disengagement
reports, road type as the only location signal, cross-company. No fitted regression, no real
exposure data — see above. Treat rankings as directional, not precise.
