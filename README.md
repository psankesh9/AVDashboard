# AV Validation Gap — Dashboard

**Live:** https://av-validation-gap-site.vercel.app

UC Berkeley MIDS 210 capstone. California has authorized driverless AV service (Waymo, 18
counties as of August 2026) — but most of that authorization has no public safety record behind
it. This dashboard scores every census tract in San Francisco and Los Angeles, the two markets
with enough real driving history to score responsibly, on a 1-100 crash-risk percentile, so city
and county transportation staff have a real, data-backed signal instead of nothing before a filing
deadline.

It is not a safety certification. Scores are a relative ranking with a 90% confidence range, not a
forecast, and not a judgment on whether any AV company is "safe."

## What's in this repo

- **`index.html`** — the deployed dashboard. Self-contained single file (data is embedded as JSON
  at build time), so it can be opened directly or served as a static site.
- **`source/template.html`** — the unbuilt template `index.html` is generated from. The actual
  data-injection build step lives in the full modeling pipeline (separate repo), which also
  produces the CSVs this template is built against.
- **`REPORT.md`** — the full results write-up: the negative binomial crash-risk model, its
  equation, validation numbers, calibration, equity findings, and limitations.
- **`VALIDATION_REPORT.md`** — a point-by-point response to real course-staff feedback, plus a
  self-directed audit against the project's own documented weak points.
- **`PROFESSOR_RESPONSE.md`** — the team's drafted reply to the original proposal critique: why the
  original framing ("disengagement risk by tract") didn't hold up, what was built instead, and how
  it was tested.

## The model, in one paragraph

A negative binomial regression predicts expected collisions per census tract per quarter, from
land area, housing density, service maturity, and marked-crosswalk density. It's validated four
independent ways: a spatial hold-out (41% better than a naive baseline), a temporal hold-out (39%),
an out-of-time test against a second operator's crash data the model never trained on (Spearman
0.39, including 0.34 on that operator alone), and a cross-check against NHTSA's independent federal
crash database (0.74 correlation). Known, disclosed limits: it measures exposure to conflict, not
fault; cross-metro levels can be off by ×/÷2.6, so only within-county ranking is reliable; and
demand/ridership is a real confound in both the equity finding and the risk score that can't be
fully removed with public data alone.
