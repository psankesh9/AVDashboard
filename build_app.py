"""
Builds the MVP page: injects the notebook outputs into app/template.html.

    python build_app.py              ->  app/av-validation-gap-mvp.html  (San Francisco + Los Angeles)
    python build_app.py --statewide  ->  every California tract

Inputs (written by notebooks 02, 03, 05, 06, 07 and 08):
    outputs/tract_coverage_equity.csv
    outputs/tract_scores.csv            (crash-risk model trained on CPUC 2025-26 collisions)
    outputs/tract_scores_dmv_model.csv  (second crash-risk model, DMV collision reports 2019-24)
    outputs/tract_crash_history.csv
    outputs/company_risk_forecast.csv
    outputs/coverage_series.csv

Product scope (team decision 2026-09-29, following the professor's feedback and M. Nguyen's site):
tract-level crash risk is shown for San Francisco, Los Angeles and Santa Clara, the three counties with enough
driving history to support it. Percentiles are ranked within the scope, so "riskier than 62% of
tracts" refers to tracts actually on the map. Statewide context (the authorisation gap) is passed
in as numbers.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "outputs")
SCOPE_COUNTIES = ["San Francisco", "Los Angeles", "Santa Clara"]


def r(v, n):
    return None if pd.isna(v) else round(float(v), n)


def ip(v):
    return None if pd.isna(v) else int(v)


def tract_polygons(geoids, tol=0.0004):
    """Simplified [[lon,lat],...] exterior ring per GEOID, same order as `geoids`. None if missing."""
    from avgap_osm import read_polygons
    ids, geoms, _ = read_polygons(os.path.join(HERE, "av_data", "tl_2023_06_tract.zip"), "GEOID")
    gmap = dict(zip(ids, geoms))
    out = []
    for g in geoids:
        geom = gmap.get(g)
        if geom is None:
            out.append(None)
            continue
        s = geom.simplify(tol, preserve_topology=True)
        poly = max(s.geoms, key=lambda p: p.area) if s.geom_type == "MultiPolygon" else s
        out.append([[round(x, 5), round(y, 5)] for x, y in poly.exterior.coords])
    return out


def percentile(ref_values, values):
    """1-100 rank of `values` within the sorted reference distribution (same rule as nb 06)."""
    ref = np.sort(pd.Series(ref_values).dropna().to_numpy())
    out = pd.Series(np.nan, index=values.index)
    ok = values.notna()
    out[ok] = (np.searchsorted(ref, values[ok].to_numpy(), side="left") / len(ref) * 99 + 1).round()
    return out


def main(statewide=False, simple=False, combined=False, disengagement=False):
    t = pd.read_csv(os.path.join(OUT, "tract_coverage_equity.csv"), dtype={"GEOID": str})
    sc = pd.read_csv(os.path.join(OUT, "tract_scores.csv"), dtype={"GEOID": str})
    t = t.merge(sc[["GEOID", "status", "risk_index", "analogue_coverage", "ood_distance",
                    "risk_reliable", "risk_lo", "risk_hi", "city"]], on="GEOID", how="left")
    t = t.merge(pd.read_csv(os.path.join(OUT, "tract_crash_history.csv"), dtype={"GEOID": str}),
                on="GEOID", how="left")
    t = t.merge(pd.read_csv(os.path.join(OUT, "tract_scores_dmv_model.csv"), dtype={"GEOID": str})
                [["GEOID", "risk316_q"]], on="GEOID", how="left")
    t = t.merge(pd.read_csv(os.path.join(OUT, "tract_drivers.csv"), dtype={"GEOID": str}),
                on="GEOID", how="left")

    if combined:
        # Experimental: swap in the pooled CPUC+DMV "incident" model's risk_index. Status/coverage
        # (real-world evidence) stays as-is - that's about driven history, not which model scores
        # the risk. No bootstrap range and no separate "second model" exist for this variant yet.
        cb = pd.read_csv(os.path.join(OUT, "tract_scores_combined.csv"), dtype={"GEOID": str})
        t = t.drop(columns=["risk_index"]).merge(cb[["GEOID", "risk_index"]], on="GEOID", how="left")
        t["risk_lo"] = np.nan
        t["risk_hi"] = np.nan
        t["risk316_q"] = np.nan

    if disengagement:
        # Second, separate dashboard: cross-company disengagement risk (road-type composition,
        # not Waymo-specific - Waymo is 1.8% of this dataset). Does NOT replace the collision map.
        dg = pd.read_csv(os.path.join(OUT, "tract_scores_disengagement.csv"), dtype={"GEOID": str})
        dg = dg.rename(columns={"risk_multiplier": "risk_index", "risk_multiplier_lo": "risk_lo",
                                "risk_multiplier_hi": "risk_hi"})
        t = t.drop(columns=["risk_index", "risk_lo", "risk_hi"]).merge(
            dg[["GEOID", "risk_index", "risk_lo", "risk_hi", "n_sample", "pct_freeway",
                "pct_arterial", "pct_local", "disengagements_per_million_miles"]],
            on="GEOID", how="left")
        t["risk316_q"] = np.nan
        t["analogue_coverage"] = np.nan
        t["ood_distance"] = np.nan
        t["risk_reliable"] = True
    else:
        for c in ["n_sample", "pct_freeway", "pct_arterial", "pct_local", "disengagements_per_million_miles"]:
            t[c] = np.nan

    # statewide context, computed before any scoping
    auth = sorted(t.loc[t.authorised_2026, "county"].unique())
    by = t.groupby("county").agg(listed=("served_now", "sum"), pop=("population", "sum"))
    no_filing = [c for c in auth if by.loc[c, "listed"] == 0]
    context = {"authorised": len(auth), "noFiling": len(no_filing),
               "noFilingResidents": int(by.loc[no_filing, "pop"].sum()),
               "statewideTracts": len(t), "statewideListed": int(t.served_now.sum()),
               "scope": "California" if statewide else " + ".join(SCOPE_COUNTIES)}

    if not statewide:
        t = t[t.county.isin(SCOPE_COUNTIES)].copy()
    # percentiles within the tracts on the map; range bounds looked up in the same distribution
    ref = t.risk_index
    t["pct"], t["pct_lo"], t["pct_hi"] = (percentile(ref, t.risk_index), percentile(ref, t.risk_lo),
                                          percentile(ref, t.risk_hi))
    t["pct316"] = percentile(t.risk316_q, t.risk316_q)

    status = {"Covered": 0, "Watch": 1, "Flag": 2, "Not authorised": 3}
    counties = sorted(t.county.dropna().unique())
    cidx = {c: i for i, c in enumerate(counties)}
    tracts = [[r(x.lon, 4), r(x.lat, 4), cidx.get(x.county, -1), int(x.population or 0),
               r(x.median_income, -2), r(x.pct_hispanic, 3), r(x.pct_nh_black, 3),
               r(x.pct_no_vehicle, 3), int(bool(x.served_now)), x.GEOID,
               status.get(x.status, 3), r(x.risk_index, 2), r(x.analogue_coverage, 2),
               r(x.ood_distance, 2), int(x.risk_reliable == True),  # noqa: E712 (numpy bool)
               r(x.risk_lo, 2), r(x.risk_hi, 2), x.city if isinstance(x.city, str) else None,
               r(x.ol316_autonomous_2019_24, 1), r(x.ol316_all_2019_24, 1),
               ip(x.pct), ip(x.pct_lo), ip(x.pct_hi), ip(x.pct316), ip(x.n_sample),
               r(x.pct_freeway, 3), r(x.pct_arterial, 3), r(x.pct_local, 3),
               r(x.disengagements_per_million_miles, 0),
               x.driver1 if isinstance(x.driver1, str) else None,
               x.driver1_dir if isinstance(x.driver1_dir, str) else None,
               x.driver2 if isinstance(x.driver2, str) else None,
               x.driver2_dir if isinstance(x.driver2_dir, str) else None]
              for x in t.itertuples()]
    tract_polys = tract_polygons(t.GEOID.tolist())

    risk = pd.read_csv(os.path.join(OUT, "company_risk_forecast.csv"))
    risk = risk.rename(columns={risk.columns[0]: "company"})
    risk = [{k: (None if pd.isna(v) else (int(v) if isinstance(v, (int, np.integer)) else v))
             for k, v in row.items()} for row in risk.to_dict("records")]

    cs = pd.read_csv(os.path.join(OUT, "coverage_series.csv"))
    series = [{"m": row.month, "listed": int(row["Any operator"]),
               "trips": None if pd.isna(row.share_listed_with_trips)
               else round(row["Any operator"] * row.share_listed_with_trips)}
              for _, row in cs.iterrows()]

    outline_path = os.path.join(HERE, "av_data", "ca_outline.json")
    outline = json.load(open(outline_path)) if os.path.exists(outline_path) else []

    data = {"counties": counties, "authorised": [c for c in auth if c in counties], "tracts": tracts,
            "tractPolys": tract_polys, "risk": risk, "series": series, "asOf": series[-1]["m"],
            "context": context, "outline": outline,
            "variant": "disengagement" if disengagement else ("combined" if combined else "collision")}
    blob = json.dumps(data, separators=(",", ":"))
    tpl = open(os.path.join(HERE, "app", "template.html"), encoding="utf-8").read()
    html = tpl.replace("/*__DATA__*/null", blob)
    html = html.replace("/*__LANDING__*/#", "https://av-validation-gap-landing.vercel.app")

    if combined:
        html = html.replace(
            '<h1>Where are driverless-car disengagements most likely?</h1>',
            '<h1>Experimental: a pooled disengagement + collision model</h1>')
        html = html.replace(
            "<p class=\"lede\">Expected autonomous vehicle (AV) collisions for every census tract in "
            "San Francisco, Los Angeles and Santa Clara.\n"
            "      The model is trained on Waymo's 2025–26 collision filings to the CPUC and "
            "checked against an independent record: the DMV's 2019–24 crash reports from every company.\n"
            "      Scores are relative (a 1–100 percentile with a 90% range). They rank places; "
            "they do not rate whether AVs are safe.</p>",
            '<p class="lede">Not presentation-ready — a test of whether pooling helps. CPUC collisions '
            '(Waymo, 2025–26) and DMV crash reports (every company, 2019–24) are pooled into one '
            '“incident” outcome, with each company’s disengagement rate added as a feature '
            '(disengagements have no location, so they can’t enter the map directly). '
            'Held-out deviance reduction: 32.4%, versus 41% for the Waymo-only model — pooling adds '
            'companies and years but costs some accuracy. No uncertainty range yet; treat percentiles as directional.</p>')

    if disengagement:
        html = html.replace(
            '<th title="Percentile from the second model, trained on DMV crash reports 2019–24 from every company">Second model</th>',
            '<th title="Disengagement reports behind this tract\'s road-mix estimate, statewide">Sample size</th>')
        html = html.replace(
            '"Similar tracts driven" compares each tract to its 25 closest look-alikes by density, income, transit, car ownership and averages how long those 25 have actually been driven.',
            'This score comes from a road-type concentration ratio (freeway/arterial/local street), not a built-environment look-alike comparison — so "similar tracts" doesn’t apply here. See the lede above for the method.')
        html = html.replace(
            '<h1>Where are driverless-car disengagements most likely?</h1>',
            '<h1>Disengagement risk, by road type</h1>')
        html = html.replace(
            "<p class=\"lede\">Expected autonomous vehicle (AV) collisions for every census tract in "
            "San Francisco, Los Angeles and Santa Clara.\n"
            "      The model is trained on Waymo's 2025–26 collision filings to the CPUC and "
            "checked against an independent record: the DMV's 2019–24 crash reports from every company.\n"
            "      Scores are relative (a 1–100 percentile with a 90% range). They rank places; "
            "they do not rate whether AVs are safe.</p>",
            '<p class="lede">An industry-wide pattern, not a Waymo-specific one — Waymo is only '
            '1.8% of the underlying disengagement reports (39 companies, CA DMV, 2020–24). '
            'Scores a tract by its road-type mix (freeway/arterial/local street, from OpenStreetMap) '
            'against how much disengagements concentrate on each type statewide (freeways run '
            '1.8× their road-length share; arterials run 0.4×). No mile-by-road-type data '
            'exists publicly for any company, so this uses road length as the exposure stand-in — '
            'stated plainly, not hidden. Ranges are wide on purpose.</p>')

    if simple:
        # map + ranked list only: hide (not delete) the other sections, so no JS that
        # populates them has to change - [hidden] is already display:none!important.
        for needle in ('<header>', '<section class="stats" aria-label="Headline figures">',
                       '<section class="panel card" aria-label="Flag list">',
                       '<section class="two">', '<section class="panel method" aria-label="How to read this">'):
            tag, rest = needle.split(">", 1)
            html = html.replace(needle, tag + " hidden>" + rest, 1)

    name = "av-validation-gap-mvp"
    if combined:
        name += "-combined"
    if disengagement:
        name += "-disengagement"
    if simple:
        name += "-simple"
    dst = os.path.join(HERE, "app", name + ".html")
    open(dst, "w", encoding="utf-8").write(html)
    print(f"wrote {dst} ({os.path.getsize(dst)/1e6:.2f} MB, {len(tracts):,} tracts, scope: {context['scope']})")


if __name__ == "__main__":
    main(statewide="--statewide" in sys.argv, simple="--simple" in sys.argv, combined="--combined" in sys.argv,
         disengagement="--disengagement" in sys.argv)
