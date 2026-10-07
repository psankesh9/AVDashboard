# AV Validation Gap: where has driverless operation been authorised without a public safety record?

**Final report: draft for team editing.** UC Berkeley data science capstone: Malachi Nguyen,
Pratheek Sankeshi, Nithya Srinivasan. Built from notebooks 02–08 in this folder, and every number
below is reproduced by `python build_notebooks.py`. The interactive MVP is at
https://claude.ai/artifact/85GFe5Hrkfm9wymgJtzGfJ (private until shared).

---

## 1. Question and product

On 14 August 2026 the CPUC authorised driverless passenger service in 18 California counties.
Public safety evidence for driverless vehicles comes from a narrow footprint:

- DMV disengagement reports (2019–2025, discontinued July 2026);
- CPUC deployment filings;
- NHTSA crash reports.

**Direction (team decision, 2026-09-29): crash risk by census tract.** The project predicts where
driverless-car crashes are most likely, tract by tract, in San Francisco and Los Angeles. This is
Model 3 from the review package, rebuilt properly.

It keeps the proposal's original idea, risk by location, using the data that actually supports
it:
- the DMV's disengagement reports have no location, and the professor was right that they can't
  carry a location model;
- **crashes do have locations**, in two independent public records:
  - Waymo's per-tract collision counts filed with the CPUC (2025–26);
  - the DMV's collision reports from every company (2019–24).

The project asks where crash risk concentrates, and whether that answer holds up across both
records, across time, and across operators. The authorisation gap is the context: most of
the 18 authorised counties have no crash record to model at all.

**What it is not** (framing by M. Nguyen after the professor's feedback):
- **It does not decide where AVs are safe to operate.** That stays a regulator's call.
- **It is built for one user:** city and county transportation staff, not a broad audience of
  "regulators, insurers and planners". Its job is to give them an evidence-based starting point
  where today there is none.
- **So the bar is "better than chance", not a target accuracy.** Replacing zero public information
  with a tested, uncertainty-bounded ranking adds value on its own. The professor suggested this
  framing.

**Scope.** Tract-level risk is only supported where Waymo has driven: San Francisco, Los Angeles
and the Peninsula. The live product (https://av-validation-gap-site.vercel.app) is scoped to San
Francisco and Los Angeles, following the professor's advice to start there. The statewide finding
(13 of 18 authorised counties with no deployment filing, 17.9M residents) remains the project's
motivation.

The product is a **tract-level crash-risk score**. For each of the 2,742 census tracts in San
Francisco and Los Angeles it reports:

1. **Crash risk.** A 1–100 percentile of expected collisions per quarter if the tract were served
   at a typical level, with a 90% range. It comes from the CPUC-trained model (§3.4).
2. **A second opinion.** The percentile from an independent model trained on the DMV's 2019–24
   crash reports (§3.7).
3. **Evidence context.** Whether the tract is in Waymo's service area, and its validation status
   (Covered / Watch / Flag, §3.5).

The output is a map and a ranked, downloadable list of the highest-risk tracts, which can be
filtered to places not yet in the service area. (The statewide build, `build_app.py --statewide`,
keeps every California tract.)

## 2. Data

| Source | Use | Key defect found and fixed |
|---|---|---|
| CA DMV disengagement and mileage reports, 2020–2024 | Company risk model | No coordinates. Miles are not split by road type. Company names vary across years. |
| CPUC AV deployment quarterly filings, Mar 2022–Jun 2026 | Coverage layer; place-risk outcome | 171 tract IDs from 2010 mixed into 2020-vintage filings (crosswalk applied). Trip counts redacted from 2025. |
| CPUC AV pilot filings, 2025–26 | Robustness of the coverage definition | Tract lists are declared areas. Zoox redacts every tract. |
| NHTSA Standing General Order ADS crash reports | Independent validation | Address and ZIP redacted, so the check is city level only. |
| ACS 2019–23 5-year tables, Census tract and place geography | Demographics, built environment | The Census API now needs a key, so the keyless table-based summary files are used. |
| OpenStreetMap (Geofabrik California extract) | Road environment per tract | Midpoint assignment of 12.1M road segments to 2020 tract polygons. |

## 3. Methods and results

### 3.1 Company risk (notebook 02)

- **Setup.** A company × month panel with a log-miles offset, evaluated rolling-origin year-ahead
  (test years 2022, 2023 and 2024). Eleven models were compared, from a pooled fleet rate to a
  hierarchical negative binomial.
- **Data completeness.** The DMV's main annual CSVs omit two sets of reports.
  - **First-time filers** add 29,892 supervised-testing disengagements, mostly the shuttle
    operators May Mobility and Beep (2023–24), and are included.
  - **Driverless-programme (AVDT) reports** are tabulated but excluded: without a safety driver, a
    "disengagement" is a different event. Cruise drove about 2.1M driverless test miles in 2023
    and reported none.
- **Key finding: company rates drift between years.** The SD of the year-to-year log rate is
  about 1.0. Without a drift term, the company-specific models' 90% intervals cover only 38–54% of
  outcomes (M5: 46%).
- **Product model: M5, an empirical-Bayes rate** with a 6-month half-life and a company-year drift
  term. Median error ≈ 1.6×, rank correlation 0.74, and 90% interval coverage 0.87. That is one
  standard error below nominal on 74 test company-years.
- **Alternatives:**
  - The hierarchical NB (M7) ranks best (0.81) but covers only 0.84.
  - The M5/M7 ensemble (M8) has a lower pooled median error (0.41 vs 0.47) at the same coverage.
    But M5 is better in 2 of the 3 test years and has the lower deviance, so M8 is the documented
    alternative.
- **Road type.** Road-type rates are not identifiable, because miles are never split by road
  type. The notebook shows each company's break-even street share instead. For Waymo, the only
  company with a public service area, OpenStreetMap bounds it: streets were no more
  disengagement-prone per mile than highways, and possibly about 5× less, unless more than a
  third of its test miles were on highways.

### 3.2 Coverage and equity (notebook 03)

- **Growth.** Listed tracts went from 251 (Mar 2022) to 1,796 (Jul 2025 onward, 19.7% of the state).
- **Listed ≠ driven, especially in new areas.** Until Feb 2024, 95–98% of the ~250 listed San
  Francisco tracts had a trip. When the footprint expanded to 1,498 tracts (Mar 2024), only 13–40%
  had any trip through Dec 2024. Newly authorised areas are listed long before they are driven.
  - Pilot filings are looser still. Waymo's pilot lists 6,298 tracts, but only 293 (4.7%) saw a
    drivered trip in Q1 2026, all of them already in the deployment footprint.
  - "Covered" therefore means *authorised service area in a deployment filing*, never "tested".
- **13 of the 18 authorised counties have no deployment filing at all: 17.9M residents.**
- **Equity (LA County, the only partially covered county).** *(Holds with standard errors
  clustered by city, the stricter choice within one county: p < 0.001 for Hispanic share and
  p ≤ 0.002 for Black share in all 9 months. The check was suggested in external review.)* Among listed tracts, +10 points of
  Hispanic share → odds of any trip ×0.54–0.66, and Black share → ×0.60–0.75. This controls for
  density, income and car ownership, and held every month from Apr to Dec 2024. Rider demand is a
  confound, so this is a gap in evidence, not evidence of intent.

### 3.3 Cause taxonomy (notebook 04)

- 52,814 narratives contain only **1,513 distinct texts**, so the whole corpus can be
  hand-labelled. May Mobility alone filed 20,694 using 3 templates.
- Keyword rules agree with companies' own labels 63% of the time (κ 0.47).
- A supervised TF-IDF classifier trained on 272 weak labels, tested leave-one-company-out, reaches
  κ 0.10 and is not adopted.
- The κ ≥ 0.7 gate depends on the two-annotator sample (`outputs/kappa_sample_sheet.csv`).

### 3.4 Place risk (notebooks 05–06)

**Why the obvious design fails.** A pre-2025 design, using trip-ends as exposure, has only 77
usable collisions and does not converge.

**The design used.** Waymo collisions per tract per quarter, 2025Q1–2026Q2. That is 10,176
tract-quarters and 1,330 collisions, about 10–12 per million driverless VMT. The model is a
negative binomial on:

- census built environment;
- OpenStreetMap road environment;
- log months since the tract was first listed (service maturity).

**Held-out reduction in Poisson deviance vs the quarter mean:**

| Model | Unseen neighbourhoods (8 geographic clusters) | Next two quarters |
|---|---|---|
| Census features | 11.6% | 32.5% |
| **Census + OSM roads (product)** | **41.4%** (better in 8 of 8 regions) | **38.8%** |
| Gradient boosting + roads | 5.1% | 36.2% |
| Tract's own shrunk history | n/a | 28.7% |

**Stable across region splits.** Split into 5, 8 or 12 regions with three seeds each (9 splits),
the product model's spatial result is **39–44%**, and its within-county rank correlation is
0.32–0.34 every time. **Quote the range.**

A bug fix sits behind that stability (2026-09-29). The model's dispersion had been set by an
unstable moment estimator (α = 20.7 against a maximum-likelihood 0.44). External review found two
12-region splits where the old fit failed catastrophically, over-predicting one dense cluster more
than tenfold. With α estimated by likelihood, those splits score 44%. The fix also lowered the
census-only model's spatial result from a previously reported 19.0% to 11.6%.

**Drivers.**
- **Marked pedestrian crossings per square mile carries nearly all of the road gain.** NB and SHAP
  agree it is the strongest feature. Dropping it alone takes the model from 41% to 5%, below
  census-only. Dropping any other road feature barely matters.
- That feature has two confounds:
  - OSM crossings are mapped by volunteers, so mapping effort varies by place;
  - crossing density correlates 0.66 with robotaxi trip volume (below).
- Next come service maturity, tract area and multi-unit housing.

**Calibration.**
- Good within served regions: the busiest deciles are within 0.81–1.28× observed/predicted.
- When extrapolating to an unseen region, the top decile is over-predicted (0.56×), mainly San
  Francisco.
- The region-level level error is SD ≈ 0.58 on the log scale: ×/÷1.8 at 1 SD, ×/÷2.6 at 90%.
- Clamping features to the training range over-corrects and was rejected.

**Uncertainty.** A cluster bootstrap (200 refits, all converged; 40 geographic clusters) gives
each tract a 90% range, with a median width of 2.4×. The product also shows a 1–100 percentile
of the risk index, with the range looked up against the same distribution (M. Nguyen).

**Independence (the professor's concern).** Repeated routes and changing local conditions could
make crashes at one place dependent. External review tested it on dated crash reports and found
same-tract crashes closer in time than a random shuffle predicts. It proposed widening every
interval 1.45×. That null ignores *when* each company operated where.
- On re-geocoded, autonomous-mode crashes, with dates shuffled only within the same company and
  year, the gap matches chance (183 vs 178 days, p ≈ 0.65, notebook 07 §3c).
- The clustering is service timing, not dependence between crashes, so the widening is not adopted.
- Unmeasured changing conditions (events, construction, rush hour) remain a limitation of
  quarterly data.

**Independent validation.** Against NHTSA SGO crash reports across 29 cities, held-out predictions
reach a rank correlation of 0.74. The two regulators' own counts agree at 0.88. Without San
Francisco and Los Angeles the correlations are 0.70 and 0.85 (external review). In NHTSA's reports
the Waymo was stopped in 52% of crashes and parked in 10%, so the score measures exposure to
conflict, not fault.

**Out-of-time, cross-operator validation (notebook 07).** The strongest test uses the DMV's own
collision reports (OL 316, 2019–2024, all companies; compiled by Xu, Jiao & Chen 2025). None of
it was used to build the model.

- **The data first needed repair.** 42% of the compiled crashes sit at fallback coordinates (one
  point carries 39 different addresses). The DMV form's own intersection addresses were
  re-geocoded against OpenStreetMap:
  - 333 of 358 autonomous-mode crashes were located;
  - the two sources agree to about 25 m where both are good;
  - every disagreement over 1 km is the dataset's error.
- **Result.** The strict (out-of-fold) score ranks tracts by their 2019–24 autonomous-mode
  crashes within county:
  - Spearman **0.39**, elasticity **0.80** (95% CI 0.67–0.94);
  - about 6–7× from the bottom to the top fifth of San Francisco tracts;
  - exposure proxies (area, road length, population, density) score about zero.
- **It transfers across operators.** Trained only on Waymo, it ranks *Cruise's* crash locations
  (Spearman 0.34, elasticity 0.67).
- **Part of it is demand (notebook 07 §3b).** On the 1,453 tracts with public 2024 trip counts:
  - 2024 trip volume correlates 0.60 with 2025–26 collisions;
  - controlling for it roughly halves the crossing (0.91 → 0.63) and multi-unit (1.53 → 0.72)
    effects, which stay significant;
  - in spatial hold-out, trips + area + maturity beat the built-environment model (24% vs 4%).

  The index is best read as *expected conflict exposure if served*: a public-risk quantity, not a
  per-mile hazard rate.

### 3.5 The coverage score (notebooks 05–06)

- **Method.** Nearest-analogue matching in standardised census + road-environment space (k = 25).
  An out-of-distribution distance measures how far a tract is from anything driven.
- **Status in the 18 authorised counties:**
  - Covered: 1,796 tracts, 7.0M residents.
  - Watch: 2,078 tracts, 8.9M.
  - **Flag: 3,407 tracts, 15.5M.**
- **Sensitivity.** Across 27 settings of k and the two cut-offs, 11.4–19.3M residents are
  flagged, with overlap with the baseline flag set (Jaccard) of 0.73–1.00. **Quote the range.**
  The coverage cut-off drives it, and the OOD cut-off barely matters.
- **What the flags are.** Flagged tracts are mostly lower-density suburbs (median risk index
  0.18). The flag list ranks the minority that are not. All 40 on the list have a 90% lower bound
  above the median served tract.
- **Consistency check (not independent).** Flagged tracts had 0.2 DMV-reported AV crashes per
  100 tracts over 2019–24, against 32 for covered tracts. Flags are defined as places unlike
  where AVs drove, and crashes occur where AVs drove, so this confirms the label is internally
  consistent but is not evidence that the coverage concept is valid.
- **Is "Flag" just density?** No. Its overlap with a simple bottom-third-density rule is Jaccard
  0.39 (external review).

### 3.6 Review of alternative models (notebook 07)

A separate package proposed three models in response to the proposal critique. Each was rebuilt
from primary sources, and each reproduces.

- **Company rate by GLM.** Its p-value is overstated by about 200 orders of magnitude
  (overdispersion), and it is in-sample on one year. Section 3.1 is the tested version.
- **Coverage ~ poverty.** The negative association is a between-county contrast. **Within the
  served counties it reverses.**
- **Crashes ~ poverty with a population offset.** Its p-values are invalid, 44% of its crashes are
  human-driven, and 42% sit at fallback coordinates. **With county fixed effects the poverty
  effect reverses.**

None of the three is adopted. Their data contributions are kept: the crash dataset (repaired) and
the CDC SVI.

### 3.7 A second crash model, and coverage prediction (notebook 08)

**Model 3: crash risk from the DMV collision reports (2019–24, every company).**

Built on the same data the review package used, with every defect fixed:
- autonomous-mode crashes only;
- re-geocoded and split at tract boundaries;
- restricted to the 1,481 tracts where AVs were actually driving (all of San Francisco, plus
  tracts in a filing by December 2024);
- county fixed effects, and negative binomial dispersion by maximum likelihood.

**It finds the same drivers as the CPUC-trained model:**

| Feature | DMV 2019–24 model | CPUC 2025–26 model |
|---|---|---|
| Crosswalk density | 0.63 | 0.91 |
| Multi-unit share | 0.79 | 1.77 |
| Land area | 0.74 | 0.76 |

**Held out spatially** within its own data, it cuts deviance 32.5% against the county mean.

**The two records agree in both directions:**
- DMV-trained model → CPUC 2025–26 collisions, within county: Spearman **0.49** (LA 0.46,
  SF 0.54).
- CPUC-trained model → DMV 2019–24 crashes: **0.39** (§3.4).

Different regulators, years and operators give the same ranking. Poverty has no association with
crashes once the built environment and county are held fixed (0.03 per SD, p = 0.84). The package's
"poorer tracts have fewer crashes" came from its defects.

**Model 2: which tracts Waymo lists (coverage prediction).**
- **Service areas are geography.** Distance to the county's dense core alone ranks Los Angeles
  tracts with AUC 0.98 on a held-out county. Demographics add nothing that transfers.
- **Within counties, poorer, more Hispanic and more Black tracts are *more* likely to be
  listed.** The package's opposite claim is a between-county contrast.
- **The equity gap is in use, not listing** (§3.2).

**Frozen prediction.** Model 2's San Diego ranking is saved and hashed before Waymo's 2026Q3
filing (`outputs/preregistration_2026Q3/`). A pass is AUC ≥ 0.80 against the tracts that filing
lists.

## 4. Scope decisions

| Decision | Reason |
|---|---|
| **NOAA weather cut** | Only 4.2% of Waymo's California SGO crash reports flag rain, and none snow. Service is coastal, and 1,330 collisions give no power to estimate a tract-quarter weather effect. |
| **Pilot listings not counted as coverage** | They are declared areas: only 4.7% of listed tracts saw a trip, and none outside the deployment footprint. |
| **No Zoox place layer** | Zoox redacts every tract in its pilot filings. |
| **Risk shown as a relative index, not a count** | Two regulators count differently (SGO has about 0.63× the CPUC's count), and the cross-region level error is ×/÷2.6. |
| **PDF export cut** | First item on the scope ladder. The flag list is downloadable as CSV instead. |
| **SHAP as global importances** | Scope-ladder fallback. Delivered in notebook 06. |
| **Driverless-programme DMV reports excluded from the company model** | Without a safety driver, a "disengagement" is a different event, and the programme reports almost none. The reports are tabulated in notebook 02 §1b. |
| **DMV crash reports used for validation, not training** | Keeping them out of the model is what makes the out-of-time test meaningful. |

## 5. Relation to prior work

Sinha et al. (2021, *Scientific Data*) published cleaned California disengagement and crash data
joined to OpenStreetMap through 2019. It is the closest prior art. This project differs in six
ways:

- It extends the record to 2026.
- It adds the CPUC deployment layer, whose tract geography the DMV data lacks.
- It builds a held-out-evaluated risk model rather than a dataset.
- It introduces a coverage metric that separates *risk* from *evidence*.
- It adds a demographic overlay.
- It validates against an independent regulator's crash reports, and out of time against the
  DMV's own collision reports.

Xu, Jiao & Chen (2025, Zenodo) compiled and geocoded the DMV collision reports for 2019–2024. This
project uses their compilation and documents a geocoding defect in it (42% fallback coordinates),
repaired with an intersection geocoder built from OpenStreetMap.

## 6. Limitations

1. **Waymo only.** Every 2025–26 deployment filing with tract geography is Waymo's. The place model
   describes one operator's experience.
2. **Collisions of any fault.** The outcome includes crashes the AV did not cause (most NHTSA
   reports have it stopped).
3. **"Listed" is an upper bound on "driven"**, and the gap is large and unmeasurable after 2025.
4. **Cross-metro level error** (×/÷2.6 at 90%). Ranking within a county is more reliable than
   across counties.
5. **The disengagement record is closed.** Reporting ended July 2026, so the company model
   describes the supervised-testing era.
6. **Equity result is scoped** to LA County, 2024, trips given listing, with a rider-demand
   confound.
7. **Three test years** for the company model. The 2019 and 2025 DMV files would add a fourth.
8. **The out-of-time test cannot observe 2019–24 exposure.** Part of the signal could reflect
   where companies chose to drive. Area, road length, population and density score near zero,
   but those are weak proxies for AV traffic. Evidence from Los Angeles is thin (27 crashes).
9. **Part of the place "risk" is demand.** On the 1,453 tracts with public 2024 trip counts:
   - 2024 trip volume correlates 0.60 with 2025–26 collisions, and 0.66 with crossing density.
   - Adding it to the model roughly halves the built-environment coefficients (crossings 0.91 →
     0.63, multi-unit share 1.53 → 0.72), though both stay significant.
   - In spatial hold-out, trip volume + area + maturity beat the built-environment model (24% vs
     4% deviance reduction on that subset).

   The index measures expected conflict exposure if a place were served at typical intensity. For
   an unserved region, that intensity is an operator decision the model cannot know.

## 7. What remains for the team

- Two annotators complete `outputs/kappa_sample_sheet.csv` (see `ANNOTATION_GUIDE.md`), then run
  notebook 04's scoring cell.
- Stakeholder interviews (`outreach/`).
- Request the 2019 and 2025 DMV files (`outreach/dmv_data_request.md`).
- Share the MVP from its Share menu. Update the proposal document to match sections 4–6.
