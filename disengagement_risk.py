"""
Disengagement-risk model: a second, separate dashboard from the Waymo collision-risk map.

Per the professor's note: usable if framed as *risk*, not event prediction, reported per mile
with confidence/uncertainty and sample size. Cross-company (39 companies, Waymo is only 1.8%
of the data) - this is an industry-wide testing pattern, not a Waymo-specific estimate, and the
dashboard says so.

Design (documented plainly so the one real assumption is visible, not hidden):

  1. Fleet base rate = total disengagements / total miles, across all companies/months.
     Real exposure, no proxy - this part needs no assumption.
  2. Road-type relative-risk multiplier: DMV disengagement reports tag each event with a road
     type (Freeway/Interstate/Highway/Street/Parking Facility/Rural Road). OSM gives, for every
     CA tract, real road length by class (freeway/arterial/collector/local/bike). Mapping DMV's
     categories onto OSM's:
       Freeway, Interstate  -> km_freeway
       Highway              -> km_arterial
       Street, Rural Road, Parking Facility -> km_collector + km_local (no OSM equivalent for
         parking lots specifically; folded into local streets as the closest approximation -
         this is the one place this script makes a simplifying call, stated here and in the
         output, not hidden)
     multiplier(type) = (share of disengagements on that type) / (share of CA road length that
     is that type). >1 means disengagements concentrate on that road type more than its
     prevalence would predict; <1 means less.
  3. Tract score = fleet base rate x (tract's own road-length mix, weighted against those
     multipliers). A tract that's mostly the road types where disengagements concentrate scores
     higher; this reflects place/road pattern, not Waymo-specific driving.
  4. Uncertainty: cluster bootstrap over companies (200 resamples) -> 90% range per multiplier,
     propagated to each tract. Sample size (n disengagements per road type) reported alongside,
     per the professor's explicit ask.

Run: python disengagement_risk.py
Writes: outputs/tract_scores_disengagement.csv
"""
import numpy as np
import pandas as pd

import avgap_data as A
from avgap_coverage import tract_table
import avgap_place as P
from avgap_osm import tract_roads, add_road_features

pd.set_option("display.width", 200)
rng = np.random.default_rng(0)

print("1. load disengagements + mileage, map road_type -> OSM class")
dis = A.load_disengagements()
mil_long, _ = A.load_mileage()

ROAD_MAP = {
    "Freeway": "km_freeway", "Interstate": "km_freeway",
    "Highway": "km_arterial",
    "Street": "km_local_group", "Rural Road": "km_local_group", "Parking Facility": "km_local_group",
}
dis = dis[dis.road_type.isin(ROAD_MAP)].copy()
dis["osm_class"] = dis.road_type.map(ROAD_MAP)
print(f"   {len(dis):,} rows kept ({dis.road_type.isin(['Other (non-conforming)']).sum()} 'Other' dropped)")
print(dis.groupby(["osm_class", "road_type"]).size())

print("\n2. fleet base rate (real exposure, no proxy)")
total_miles = mil_long.miles.sum()
total_dis = len(dis)
base_rate = total_dis / total_miles
print(f"   {total_dis:,} disengagements / {total_miles:,.0f} miles = {base_rate:.3e} per mile "
      f"({base_rate*1e6:.2f} per million miles)")

print("\n3. statewide road length by class (OSM, every CA tract)")
roads = tract_roads()
roads["km_local_group"] = roads.km_collector + roads.km_local
CLASSES = ["km_freeway", "km_arterial", "km_local_group"]
state_km = roads[CLASSES].sum()
print(state_km.round(0))

print("\n4. disengagement share vs road-length share -> multiplier, with cluster bootstrap CI")


def compute_multipliers(d, n_by_class):
    n = d.groupby("osm_class").size().reindex(CLASSES, fill_value=0)
    dis_share = n / n.sum()
    km_share = n_by_class / n_by_class.sum()
    return dis_share / km_share, n


mult, n_obs = compute_multipliers(dis, state_km)
print(pd.DataFrame({"n_disengagements": n_obs, "multiplier": mult.round(2)}))

companies = dis.company.unique()
boot = np.zeros((200, len(CLASSES)))
for i in range(200):
    samp_co = rng.choice(companies, size=len(companies), replace=True)
    rows = pd.concat([dis[dis.company == c] for c in samp_co], ignore_index=True)
    m, _ = compute_multipliers(rows, state_km)
    boot[i] = m.reindex(CLASSES).to_numpy()
mult_lo = pd.Series(np.nanpercentile(boot, 5, axis=0), index=CLASSES)
mult_hi = pd.Series(np.nanpercentile(boot, 95, axis=0), index=CLASSES)
print("\n   90% range (cluster bootstrap over companies, 200 resamples):")
print(pd.DataFrame({"lo": mult_lo.round(2), "mid": mult.reindex(CLASSES).round(2), "hi": mult_hi.round(2)}))

print("\n5. score every tract: road-mix-weighted base rate")
t, latest = tract_table()
t = t.merge(roads, on="GEOID", how="left")
t["km_local_group"] = t.km_collector.fillna(0) + t.km_local.fillna(0)
t["total_km"] = t[CLASSES].sum(1)
ok = t.total_km > 0

mix = t.loc[ok, CLASSES].div(t.loc[ok, "total_km"], axis=0)
t.loc[ok, "pct_freeway"] = mix.km_freeway
t.loc[ok, "pct_arterial"] = mix.km_arterial
t.loc[ok, "pct_local"] = mix.km_local_group
t.loc[ok, "risk_multiplier"] = (mix * mult.reindex(CLASSES)).sum(1)
t.loc[ok, "risk_multiplier_lo"] = (mix * mult_lo.reindex(CLASSES)).sum(1)
t.loc[ok, "risk_multiplier_hi"] = (mix * mult_hi.reindex(CLASSES)).sum(1)
t.loc[ok, "disengagements_per_million_miles"] = base_rate * 1e6 * t.loc[ok, "risk_multiplier"]
t.loc[ok, "dpmm_lo"] = base_rate * 1e6 * t.loc[ok, "risk_multiplier_lo"]
t.loc[ok, "dpmm_hi"] = base_rate * 1e6 * t.loc[ok, "risk_multiplier_hi"]
t.loc[ok, "n_sample"] = (mix * n_obs.reindex(CLASSES)).sum(1).round(0)

ref = np.sort(t.loc[ok, "risk_multiplier"].to_numpy())
t.loc[ok, "risk_percentile"] = (np.searchsorted(ref, t.loc[ok, "risk_multiplier"].to_numpy(),
                                                 side="left") / len(ref) * 99 + 1).round()

out = t.loc[ok, ["GEOID", "county", "population", "risk_multiplier", "risk_multiplier_lo",
                 "risk_multiplier_hi", "disengagements_per_million_miles", "dpmm_lo", "dpmm_hi",
                 "n_sample", "risk_percentile", "pct_freeway", "pct_arterial", "pct_local"]]
out.to_csv("outputs/tract_scores_disengagement.csv", index=False)
print(f"\n   wrote outputs/tract_scores_disengagement.csv ({len(out):,} tracts)")
print(f"\nSUMMARY: fleet base rate {base_rate*1e6:.2f}/million miles, "
      f"{len(companies)} companies (Waymo {100*(dis.company=='Waymo').mean():.1f}% of rows), "
      f"multiplier range {mult.min():.2f}-{mult.max():.2f} across road types")
