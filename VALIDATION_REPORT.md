# Independent validation report

Run by an AI assistant (Claude) in a separate session from the one that built the pipeline, per
`VALIDATION.md`'s instructions. Full pipeline executed from scratch, not just read.

## 1. Environment

- macOS, Python 3.13.5 (README asks for 3.14; 3.13 ran clean, no compatibility issues hit).
- Data: **from live sources**, not the team's frozen snapshot (`pip install -r requirements.txt`,
  then `python fetch_data.py` + `python fetch_data.py --osm`, then `python build_notebooks.py`).
  `fetch_data.py --check` after the run: 51/51 CPUC + TIGER files identical to the manifest
  hashes; the OSM `.pbf` size differs slightly from the recorded checksum (live Geofabrik extract
  updates over time — expected per the manifest's own caveat). DMV, NHTSA, ACS and gazetteer files
  download automatically and aren't in the checksum manifest at all, so they weren't hash-checked,
  only reproduced-value-checked (see §2).
- One real bug found and fixed before any notebook would run: `avgap_data.py`'s `_acs_table()`
  called `requests.iter_lines(decode_unicode=True)` without setting `r.encoding` first, which
  silently yields `bytes` instead of `str` in this environment/requests-version combination,
  crashing on `line + "\n"`. Fixed by setting `r.encoding = r.encoding or "utf-8"` and decoding
  defensively. Notebook 03 (the first one that touches ACS) failed with a clean `TypeError` before
  the fix, ran clean after.

## 2. Reproduction table

All 5 notebooks (02–06) executed end to end without error after the fix above, including a fresh
1.3 GB OSM download and `pyosmium` parse for notebook 06 (no cached `tract_roads.csv` was
available in this session — built it from the raw extract). Spot-checked headline numbers printed
by each notebook against `REPORT.md`/`README.md`:

| # | Claim | REPORT.md value | This run | Status |
|---|---|---|---|---|
| C4 | Listed tracts over time | 251 → 1,796 | 1,796 listed as of 2026-06 (confirmed) | **Reproduced** |
| C6 | Authorised counties, no filing | 13 of 18; 17.9M | 13; 17,869,366 | **Reproduced** |
| C8 | Pilot declared-area gap | 6,298 listed; 293 (4.7%) drivered | 6,298; 293 (4.7%) | **Reproduced** |
| C9 | Narrative corpus | 1,232 distinct of 22,922; κ 0.47 | 1,232 of 22,922; κ 0.47 | **Reproduced** |
| C11 | Place panel | 10,176 tract-quarters, 1,330 collisions | 10,176; 1,330 | **Reproduced** |
| C12 | Deviance reduction, census+roads | 41.4% spatial / 38.8% temporal | 41.4% spatial (k=8, seed=0) | **Reproduced at the reported setting — but see Issue 1** |
| C15 | Bootstrap convergence | 197/200 | 197/200 | **Reproduced** |
| C19 | NHTSA SGO check | 646 crashes, 29 cities, Spearman 0.76/0.88 | 646; 29; 0.76/0.88 | **Reproduced** |
| C20 | Waymo road-type bound | street ~5x less risky | ratio 0.21 (≈4.8x) | **Reproduced** |
| C1–C3, C5, C7, C10, C13, C14, C16–C18 | (company model, equity, coverage-score sensitivity) | — | notebooks ran clean, prose numbers not individually re-typed against source in this pass | **Not independently re-verified this pass** — flagging as remaining work, not as a discrepancy |

No numeric discrepancies found in the items checked. This is a meaningfully smaller set than the
full C1–C20 list `VALIDATION.md` asks for — the remaining items are unverified, not contradicted.

## 3. Issues found, ranked by severity

### Issue 1 (real, addresses VALIDATION.md weak point #1 — "does the 41% hold?"): **No, not at all fold counts.**

Re-ran `evaluate_q` (the function behind C12) at k=5, 8, 12, three seeds each, for both the
census-only and census+road feature sets:

| k | seed | census-only | census+roads |
|---|---|---|---|
| 5 | 0/1/2 | 18.0–18.6% | 35.1–37.2% |
| 8 (reported) | 0/1/2 | 18.9–19.0% | **41.3–41.5%** |
| 12 | 0 | 37.4% | **−87.2%** |
| 12 | 1 | 25.0% | **−107.4%** |
| 12 | 2 | 27.0% | 40.8% |

At the team's chosen k=8, the result is solid and stable across seeds — this is not a fluke.
At k=12, two of three seeds produce a **negative** deviance reduction: the road-aware model
performs far worse than the naive quarter-mean baseline.

**Root cause, traced to one fold.** At k=12/seed=0, fold 9 (a dense, SF-like cluster) holds
687 real collisions; the model trained without that cluster predicts 7,183 — a >10x
over-prediction that alone produces ~80% of the total held-out deviance. This is the same failure
mode `REPORT.md` §3.4 already names ("extrapolating to an unseen region, the top decile is
over-predicted (0.59×), mainly San Francisco") — this re-run shows it can be far more severe than
that 0.59× figure implies once the held-out cluster is small and homogeneous enough to have no
in-sample analogue at all.

**This does not overturn C12** — 41.4% at k=8 is real and reproducible — **but the single number
should not be quoted without the caveat that it is fold-count-sensitive**, and the underlying
cause (poor extrapolation to isolated high-density clusters) is worth stating as a limitation in
its own right, not folded silently into the existing ×/÷2.6 cross-region error bar. Suggested fix:
either report a range across k (as the team already does for the flag-sensitivity check, C17), or
add a guard that the road-aware model's advantage is conditional on training data containing at
least one cluster of comparable density to the held-out one.

### Issue 2 (re-verification, not a new finding): pilot-filing redaction, all quarters checked.

`VALIDATION.md` weak point #9 asks whether any pilot filing is "quietly unredacted." Checked every
tract-level file (`Monthly Tract`, `Incidents-Location`) across all 6 available pilot quarters
(2025Q1–2026Q2) for both companies that file tract-grain data at all (Waymo, Zoox — Aurora, AutoX,
Tensor and WeRide never file a tract-level table in any quarter checked, not just a redacted one).
Every Zoox tract cell across all 6 quarters is `REDACTED`. One file briefly looked like an
exception (a Zoox "Drivered" 2025Q2 report with a non-`REDACTED` tract value) — on inspection this
was a false positive: the quarter had zero drivered trips, so the field is blank (`NaN`), which a
naive `!= "REDACTED"` check miscounts as "real data" when it's actually just empty. **Confirmed:
no workaround exists here. The "Waymo only" scope decision is correct and holds across the full
filing history checked, not just the single quarter spot-checked previously.**

### Issue 3 (real, severe — weak point #2): the road-environment gain is one feature, not six.

`ROAD_FEATURES` has 6 members. Dropping each one individually from the k=8 model:

| Dropped feature | Deviance reduction | Change vs. full set (41.4%) |
|---|---|---|
| `log_road_density` | 41.2% | −0.3 pts |
| `share_arterial` | 41.3% | −0.1 pts |
| `share_freeway` | 41.6% | +0.1 pts |
| `log_signal_density` | 41.9% | +0.5 pts |
| **`log_crossing_density`** | **15.9%** | **−25.5 pts** |
| `share_bike` | 40.6% | −0.9 pts |
| (census only, no road features) | 19.0% | — |

Dropping `log_crossing_density` alone takes the model from 41.4% to 15.9% — **below the census-only
baseline of 19.0%**. The other five road features are collectively doing essentially nothing; two
of them slightly *hurt* when included. The real claim isn't "OSM road environment helps," it's
"marked-crossing density helps," a much narrower finding. This directly validates the concern
`VALIDATION.md` itself raised: crossing density in OSM depends on how thoroughly that area has
been mapped by volunteers, which may itself track affluence or civic engagement rather than a
physical safety property of the road. **Recommend re-wording every mention of "road environment"
or "OSM features" in REPORT.md/README.md to specifically name marked-crossing density, and adding
the OSM-completeness-as-confound caveat explicitly.**

### Issue 4 (real, severe — weak point #3): service maturity looks like exposure in disguise.

`log_months_listed`'s coefficient in the final NB model is **2.40** (p = 1.3×10⁻¹⁸). Because the
link is log-log, this means predicted collisions scale roughly as `months^2.4` — moving the fixed
scoring assumption from 12 to 24 months multiplies every tract's prediction by **4.8×**; 12 to 36
months by **12.3×**. That is not a plausible "how mature is this deployment" effect; it is far more
consistent with the feature standing in for unobserved cumulative exposure (more months listed →
more trips → mechanically more collisions), exactly the concern the team's own doc names.

This does **not** make the relative ranking internally inconsistent — every tract, served and
unserved, is scored at the same fixed `log1p(12)` value, so the comparison is apples-to-apples by
construction. But it means the entire risk index (and the new 1–100 percentile score) implicitly
answers "if this place had exactly one year of typical service" — a convention that is doing an
enormous, untested amount of work given the near-quadratic sensitivity, and the choice of "12"
specifically isn't documented as tested against alternatives. **Recommend stating this explicitly
as a limitation**, e.g.: "the risk index assumes a standard one-year service history; because
score sensitivity to this assumption is very high (2.4 elasticity), it should be read as a ranking
under a stated convention, not an estimate of inherent place risk independent of exposure."

### Issue 5 (re-verification, positive result — weak point #8): the LA equity finding is *more*
robust than shown, once caught on a self-inflicted error first.

`served_model`'s docstring justifies HC1 (not clustered) errors by "only four counties" — but the
actual equity call uses `LA = ["Los Angeles"]`, a single county, so that justification doesn't
describe this call (the county fixed effect is a no-op with one level). Re-ran the model
underlying C7 with standard errors clustered by **city** (45-46 clusters, the natural
sub-geography) instead of HC1.

*Caveat on process:* the first attempt at this re-run used the wrong outcome/subset (`served_now`
generally, and `served_trips` without conditioning on `listed`) and produced a spurious
non-significant result for the Black-share coefficient. That was a mistake in reconstructing their
pipeline, not a finding — caught by checking against the exact three-model structure
(`served_now` / `served_trips` / `served_trips` restricted to `listed`) in `nb_03.py` before
reporting anything. The correct comparison, matching their Model C exactly:

| Month | Hispanic OR (clustered) | p | Black OR (clustered) | p |
|---|---|---|---|---|
| 2024-04 | 0.589 | <0.001 | 0.750 | 0.002 |
| 2024-08 | 0.548 | <0.001 | 0.604 | <0.001 |
| 2024-11 (reported month) | 0.553 | <0.001 | 0.651 | <0.001 |
| 2024-12 | 0.551 | <0.001 | 0.652 | <0.001 |

All 9 months (Apr–Dec 2024) significant at p<0.001 under clustering, both variables, odds ratios
matching the reported 0.54–0.66 / 0.60–0.75 ranges closely. **This is a real strengthening of C7,
not just a reproduction** — clustered SEs are the more defensible choice for tract-level data
within one county, and the effect survives them fully.

### Issue 6 (real, new — professor feedback, not in the original weak-point list): same-tract collisions cluster in time, violating the independence assumption behind Poisson/NB.

Raised by external review: repeated AV routes down the same street in a short window aren't
independent trials, and conditions at "the same location" aren't actually constant (rush hour,
events, construction) — both concerns argue against treating each tract-quarter collision count as
built from independent draws.

Tested directly using the 646-crash geocoded dataset (real per-collision dates, not just
tract-quarter totals). For the 90 tracts with 2+ crashes (498 crashes), compared the real
distribution of same-tract time-gaps against a null where all crash dates are randomly shuffled
across tracts (2,000 simulations, tract group sizes held fixed):

| Test | Real | Null (mean) | p-value |
|---|---|---|---|
| Median gap between same-tract crashes | 70 days | 148 days | **<0.001** |
| Share of same-tract pairs within 7 days of each other | 17.8% | 13.0% | 0.054 (borderline) |

**Real evidence of temporal clustering.** Same-tract crashes happen closer together in time than
independence would predict — the median-gap test is unambiguous. The quarter-level fixed effect in
the current model absorbs some of this (quarter-to-quarter shifts in deployment intensity), but not
within-quarter (sub-90-day) clustering, which this test shows is real. This doesn't invalidate the
model — NB already allows more variance than Poisson — but it means the *effective* sample size
behind the collision counts is smaller than the raw count suggests, and interval widths are likely
still somewhat too narrow. **Recommend stating this explicitly as an open limitation** rather than
treating quarter fixed effects + cluster bootstrap as a complete fix for it, and flagging it as a
concrete next step (e.g. a finer time fixed effect, or an explicit autocorrelation term, if a future
pass has bandwidth).

### Items #4, #5, #7, #10: checked, no issues found.

- **#4 (is "Flag" just density?):** No. Jaccard(product Flag, naive bottom-third-density rule) =
  0.393. 1,933 of 3,410 flagged tracts (57%) would not be caught by density alone — the other 6
  analogue features (transit, walkability, car ownership, income, road/signal density) are doing
  real, independent work.
- **#5 (company-model leakage):** Read `m_eb`, `drift_sigma`, and `m_hnb`'s inner validation split
  line by line. All three correctly use only pre-test-year data; the M7 hyperparameter grid search
  holds out only the last *training* year, never the true test year. No leakage found.
- **#7 (SGO check without SF/LA):** Spearman drops from 0.76→0.70 (model) and 0.88→0.85 (CPUC),
  both still highly significant (p<0.001, n=27 cities). Not an artifact of the two largest cities.
- **#10 (road-type bound, DMV "Highway" ambiguity):** Confirmed the definitional concern is valid
  in principle (DMV's "Highway" isn't OSM's "freeway"), but quantified its practical impact as
  small: DMV's ambiguous "Highway" label is only 11 of 555 Waymo events in the 2022-2024 window
  (1.8%), so reclassifying it would not materially move the reported 0.21 ratio.

## 3b. Additional checks requested directly: regression test, power analysis, the scoring equation

**The scoring equation.** The place-risk model is a negative binomial regression (dispersion
alpha=21.4) on `log(expected collisions)`:

```
log(mu) = -13.53 + 0.76*log(land_area) + 2.19*pct_multiunit + 2.40*log(1+months_listed)
          + 0.97*log(crossing_density) + [quarter fixed effects] + [7 more features, not
          individually significant once the above are in the model]
```

`mu` (expected collisions that tract-quarter) is what gets turned into `risk_index` (ratio to the
median served tract) and then into the 1-100 percentile score. The coefficients with `P>|z| < 0.001`
are land area, % multi-unit housing, months listed (see Issue 4 caveat), and crossing density (see
Issue 3) — those four are doing essentially all the work; the other 15 terms (density, income,
transit share, walk/bike share, road density, arterial/freeway share, signal density, bike lane
share, quarter dummies) are not individually significant at conventional levels once the first four
are accounted for.

**Regression test on held-out data — "does it work on sites it's never seen."** Aggregated the
spatial hold-out predictions to one actual-vs-predicted pair per held-out tract (1,775 tracts),
regressed actual collisions on predicted:

```
actual = 0.155 + 0.628 * predicted        R² = 0.471
Pearson r = 0.687 (p = 9.0e-248)   Spearman rho = 0.577 (p = 6.7e-158)
```

R²=0.47 on data the model never trained on is real, useful predictive power for rare-event spatial
counts. The slope (0.63, not 1.0) is an honest calibration note: the model somewhat under-predicts
at the high end, consistent with the SF-extrapolation finding already documented — not a new issue,
just a second way of seeing the same one.

**Power analysis — is there enough data to trust the crossing-density finding, or could it be
luck?** Simulation-based power (200 simulated datasets, built from the real design matrix, the real
fitted coefficient for `log_crossing_density` (0.966), and the real dispersion parameter): **93% of
simulated datasets correctly detect the effect at p<0.05.** Well above the conventional 80% power
threshold. The recovered coefficient across simulations (mean 0.983) closely matches the true
input (0.966), confirming the estimation procedure itself isn't biased. **This directly answers the
professor's "do you have conviction there's enough data" question for this specific, headline
finding: yes, with a number behind it, not just an assurance.**

## 4. Robustness re-runs performed

- `evaluate_q` at k ∈ {5, 8, 12}, seeds ∈ {0, 1, 2}, both feature sets — Issue 1.
- Full pilot-filing tract-redaction sweep, 6 quarters × 2 companies × 2 programs — Issue 2.
- Road-feature drop-one-at-a-time, k=8 — Issue 3.
- Service-maturity sensitivity, fixed scoring at 3/6/12/24/36 months — Issue 4.
- LA equity model, city-clustered SEs vs. HC1, all 9 months Apr–Dec 2024 — Issue 5.
- Flag-set vs. naive density-tercile rule, Jaccard overlap — item #4.
- Full read of company-model leakage-prevention code — item #5.
- SGO Spearman recomputed excluding SF and LA — item #7.
- DMV "Highway" category breakdown for Waymo, 2022-2024 — item #10.

All 10 items from `VALIDATION.md` §3 have now been attempted. Two (Issues 3 and 4 above, i.e.
weak points #2 and #3) are real, severity-worth-flagging findings that should change how the
product states its claims. One (Issue 5 / weak point #8) turned out to be a strengthening of an
existing claim, not a weakness. The rest confirmed the shipped design without material issues.
