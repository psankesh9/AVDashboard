import numpy as np, pandas as pd
import avgap_place as P, avgap_osm as O, avgap_explain as E
from avgap_coverage import tract_table

AUTH_2026 = ["Alameda","Contra Costa","Marin","Napa","Sacramento","San Francisco","San Mateo",
             "Santa Clara","Santa Cruz","Solano","Sonoma","Yolo","Los Angeles","Orange",
             "Riverside","San Bernardino","San Diego","Ventura"]

t, latest = tract_table()
t = t.merge(P.load_built_env(), on="GEOID", how="left")
t = P.add_model_features(t)
t["log_land"] = np.log(t.land_sqmi.clip(lower=0.01))
t["authorised_2026"] = t.county.isin(AUTH_2026)
roads = O.tract_roads()
t = O.add_road_features(t, roads)

d = P.tract_quarter_panel(t)
F1 = P.Q_FEATURES + O.ROAD_FEATURES
nb = P.fit_q_nb(d, F1)

X = t.set_index("GEOID")
ref = E.reference_profile(X, X.served_now, E.FEATURES)
contrib = E.contributions(nb.params, X, ref, E.FEATURES)
fam = E.family_sums(contrib, E.FAMILIES)

top2 = []
for geoid, row in fam.iterrows():
    r = row.sort_values(key=abs, ascending=False)
    top2.append({"GEOID": geoid, "driver1": r.index[0], "driver1_dir": "+" if r.iloc[0] > 0 else "-",
                "driver2": r.index[1], "driver2_dir": "+" if r.iloc[1] > 0 else "-"})
out = pd.DataFrame(top2)
out.to_csv("outputs/tract_drivers.csv", index=False)
print(f"wrote outputs/tract_drivers.csv ({len(out):,} tracts)")
print(fam.abs().mean().sort_values(ascending=False))
