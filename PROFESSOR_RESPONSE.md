# Reply to the proposal critique (draft for the team to edit and send)

**To:** [Professor name]
**From:** Malachi Nguyen, Pratheek Sankeshi, Nithya Srinivasan
**Re:** "Predict disengagement risk by census tract and condition" (your comment on our proposal)

---

Thank you for the critique. We checked it against the data, and **you were right**. Here is what
we found, what we changed, and how we tested the result.

## 1. Why the original framing fails

- **Disengagements have no location.** The DMV disengagement form records only a six-value
  road-type field (Street, Freeway, Highway, …): no address, city or ZIP. A tract-level
  disengagement rate cannot be computed from it.
- **The miles have no location either.** DMV mileage is reported per vehicle per month, with no
  geography, so there is no tract-level denominator to pair with any count.
- **Weather adds little.** Only about 4% of Waymo's California crash reports to NHTSA flag rain,
  and service is coastal. We have cut NOAA from scope.

## 2. What we built instead

We kept your "risk by location" goal but moved it to data that has locations: **crash risk by census tract**, from two independent crash records. The table shows how the question splits along the lines the data supports.

| Question | Data that supports it | Model |
|---|---|---|
| Which **companies** have worse records? | DMV disengagements and miles, company × month, 2020–24 (including the DMV's separate first-time-filer reports) | Empirical-Bayes rate with a year-to-year drift term. Tested year-ahead on 2022, 2023 and 2024. |
| Which **places** are riskier for driverless service? (the main deliverable) | CPUC filings: Waymo collisions *per census tract per quarter* (2025–26). DMV collision reports: every company, 2019–24, re-geocoded. | Negative binomial on census and OpenStreetMap features, fitted on each record separately. Each predicts the other (0.49 and 0.39). |
| Where has driverless service been **authorised without evidence**? | CPUC filings, and the 18-county authorisation of 14 Aug 2026 | Validation coverage score: are a tract's closest built-environment analogues in the driven footprint? |

The product is the third row. It separates "how risky is this place" from "has anything like it
actually been driven". About **15.5 million residents** (11–19M depending on thresholds) live in
authorised tracts with no driven analogue.

## 3. How we tested it

1. **Held-out neighbourhoods.** Holding out whole geographic regions, the place model cuts
   prediction error by 41% against a no-information baseline (39–44% however the regions are drawn), and it improves in all 8 regions.
2. **A second regulator.** At city level, the model's held-out predictions rank cities the way
   NHTSA's independent crash reports do (Spearman 0.74).
3. **Out of time, and a different operator.** This is the test we'd most like you to look at. We
   took the DMV's own collision reports for **2019–2024** (every company; compiled by Xu, Jiao &
   Chen, 2025). The model, fitted only on **2025–26 Waymo** data, ranks where autonomous-mode
   crashes happened within each county:
   - Spearman 0.39;
   - about 7× more crashes in the top fifth of San Francisco tracts than in the bottom fifth;
   - on **Cruise's** crashes alone, a company absent from the training data: Spearman 0.34.

   Simple exposure proxies (land area, road length, population, density) score near zero.
   Before running this test we had to repair the compiled dataset: 42% of its crashes sat at
   fallback coordinates. We re-geocoded them from the DMV forms' own intersection addresses.
4. **A consistency check on the flags, not an independent test.** Flagged tracts had 0.2
   DMV-reported AV crashes per 100 tracts over 2019–24, against 32 per 100 in the driven
   footprint. Flags are defined as places unlike where AVs have driven, so this mostly confirms
   the label is internally consistent. We don't count it as validation.

## 4. What we do not claim

- The place model is **Waymo-only** in training, and it counts collisions of **any fault**. In
  about half of NHTSA's reports the Waymo was stopped. So the score measures *exposure to
  conflict*, not the AV's fault.
- Across metros its level can be off by about ×/÷2.6. **Rankings within a county are the reliable
  use.** The product says so.
- **Part of the "risk" is demand.** Where 2024 trip counts were still public, they correlate 0.60
  with 2025–26 collisions, and 0.66 with crossing density, our strongest feature.
  - Controlling for trips, the built-environment effects shrink but remain significant (crossings
    0.91 → 0.63).
  - Out of sample, observed demand predicts a new region's collision *level* better than built
    environment does.

  Our index is therefore best read as *expected conflict exposure if served*. It is a public-risk
  quantity, and it is not a per-mile hazard rate.
- The 2019–24 test cannot observe where companies drove, so it limits but cannot exclude an
  exposure explanation.
- On equity, we claim only a scoped finding. In Los Angeles in 2024, among tracts Waymo listed,
  Hispanic and Black neighbourhoods were less likely to see a trip, after controlling for density,
  income and car ownership. Rider demand is a confound we cannot remove.

We also tested three simpler alternatives: a one-year company GLM, "served ~ poverty", and
"crashes ~ poverty per resident". We found their headline effects either reverse within counties
or rest on invalid standard errors. Notebook 07 documents this.

## 5. Where we'd value your judgement

1. Is out-of-time, cross-operator validation the right bar for a place model when true exposure
   is unobservable? Or would you want a different design?
2. Is a coverage score (evidence, not risk) a defensible primary deliverable for this capstone?

Everything is reproducible from public data (`python build_notebooks.py`). The prototype is at
[MVP link, once shared]. We're happy to walk through any part of it.

— Malachi, Pratheek, Nithya
