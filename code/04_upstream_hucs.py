"""04_upstream_hucs.py — Flow graph; upstream-of-intake set; drinking-water conflict set W.

The graph is built from the NATIONAL WBD attribute table, not the clipped study area:
the Ouachita and Saline drain south into Louisiana and the Mississippi, so a Smackover
HUC12 can sit upstream of a community-water-system intake far outside any buffer.
Clipping the graph first would silently drop exactly the links this paper is about.

Surface water propagates upstream; groundwater does not — the HUC12 surface-flow graph
is not a model of aquifer flow paths, so a CWS well contributes only its own HUC12.

    W = I_sw  u  U_sw  u  I_gw

Writes outputs/conflict_hucs.csv (study-area rows only).
"""
from __future__ import annotations

import networkx as nx
import pandas as pd
import pyogrio

from utils import OUT, OUT_INT, TOHUC_SINKS, dedup_pop_served, norm_tohuc, zpad_huc12

SUPER_SOURCE = "__SW_INTAKES__"


def main() -> None:
    nat = pd.read_csv(OUT_INT / "huc12_tohuc_national.csv", dtype=str).fillna("")
    nat["HUC12"] = nat["HUC12"].map(zpad_huc12)
    nat["TOHUC"] = nat["TOHUC"].map(norm_tohuc)

    G = nx.DiGraph()
    G.add_nodes_from(nat["HUC12"])
    G.add_edges_from(
        (h, t) for h, t in nat[["HUC12", "TOHUC"]].itertuples(index=False) if t
    )

    sw = pd.read_csv(OUT / "intake_hucs_sw.csv", dtype={"HUC12": str})
    gw = pd.read_csv(OUT / "intake_hucs_gw.csv", dtype={"HUC12": str})
    sw["HUC12"] = sw["HUC12"].map(zpad_huc12)
    gw["HUC12"] = gw["HUC12"].map(zpad_huc12)
    I_sw = set(sw["HUC12"])
    I_gw = set(gw["HUC12"])

    # Upstream set in one reversed multi-source traversal rather than |I_sw| calls.
    # The BFS depth is also the number of HUC12 hops downstream to the nearest CWS
    # surface intake, which is what makes the upstream screen discriminating: "upstream
    # of an intake" is near-universal in CONUS, "two hops upstream" is not.
    rev = G.reverse(copy=True)
    present = [h for h in I_sw if h in rev]
    rev.add_edges_from((SUPER_SOURCE, h) for h in present)
    depth = nx.single_source_shortest_path_length(rev, SUPER_SOURCE)
    steps = {h: d - 1 for h, d in depth.items() if h != SUPER_SOURCE}  # 0 == is an intake HUC12
    U_sw = set(steps) - I_sw - TOHUC_SINKS

    W = I_sw | U_sw | I_gw

    study = pyogrio.read_dataframe(
        OUT_INT / "huc12_study.gpkg", columns=["HUC12"], read_geometry=False
    )
    study["HUC12"] = study["HUC12"].map(zpad_huc12)
    study_set = set(study["HUC12"])

    rows = pd.DataFrame({"HUC12": sorted(study_set)})
    rows["in_I_sw"] = rows["HUC12"].isin(I_sw)
    rows["in_U_sw"] = rows["HUC12"].isin(U_sw)
    rows["in_I_gw"] = rows["HUC12"].isin(I_gw)
    rows["in_W"] = rows["HUC12"].isin(W)
    # HUC12 hops to the nearest downstream CWS surface intake (0 = is one; NA = none).
    rows["steps_to_sw_intake"] = rows["HUC12"].map(steps).astype("Int64")
    rows = rows.merge(
        sw[["HUC12", "n_facilities", "n_systems", "cws_pop_served", "pws_ids"]].rename(
            columns={"n_facilities": "n_sw_facilities", "n_systems": "n_sw_systems",
                     "cws_pop_served": "cws_pop_served_sw", "pws_ids": "pws_ids_sw"}),
        on="HUC12", how="left",
    ).merge(
        gw[["HUC12", "n_facilities", "n_systems", "cws_pop_served", "pws_ids"]].rename(
            columns={"n_facilities": "n_gw_facilities", "n_systems": "n_gw_systems",
                     "cws_pop_served": "cws_pop_served_gw", "pws_ids": "pws_ids_gw"}),
        on="HUC12", how="left",
    )
    for c in ("n_sw_facilities", "n_sw_systems", "cws_pop_served_sw",
              "n_gw_facilities", "n_gw_systems", "cws_pop_served_gw"):
        rows[c] = rows[c].fillna(0)
    for c in ("pws_ids_sw", "pws_ids_gw"):
        rows[c] = rows[c].fillna("")
    # cws_pop_served (sw + gw, summed per HUC12) is fine as a per-HUC12 attribute, but
    # is a per-system value repeated on every HUC12 that system touches — do not sum
    # it across HUC12s (see the total below and utils.dedup_pop_served).
    rows["cws_pop_served"] = rows["cws_pop_served_sw"] + rows["cws_pop_served_gw"]

    out_path = OUT / "conflict_hucs.csv"
    rows.to_csv(out_path, index=False)

    print("=== 04_upstream_hucs ===")
    print(f"national graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    missing = len(I_sw - set(G.nodes))
    print(f"|I_sw|={len(I_sw):,}  |U_sw|={len(U_sw):,}  |I_gw|={len(I_gw):,}  |W|={len(W):,}")
    print(f"I_sw HUC12s absent from the national graph: {missing:,} "
          f"({missing/max(len(I_sw),1):.1%}; expected small — AK/HI/PR/tribal codes)")
    n_study = len(study_set)
    print(f"\nstudy HUC12s: {n_study:,}   in W: {int(rows['in_W'].sum()):,} "
          f"({rows['in_W'].mean():.1%})")
    print("  breakdown: "
          f"I_sw {int(rows['in_I_sw'].sum())}, "
          f"U_sw-only {int((rows['in_U_sw'] & ~rows['in_I_sw']).sum())}, "
          f"I_gw {int(rows['in_I_gw'].sum())}")
    pop_lookup = pd.read_csv(OUT_INT / "cws_pwsid_population.csv").set_index("PWSID")["POPULATION_SERVED_COUNT"]
    print(f"  CWS population served by systems with intakes in the study area "
          f"(distinct systems, de-duplicated by PWSID): "
          f"{dedup_pop_served(rows, pop_lookup):,.0f}")
    print("\nhops to the nearest downstream CWS surface intake (study HUC12s):")
    dist = rows["steps_to_sw_intake"].dropna()
    print("  distribution:", dist.value_counts().sort_index().to_dict())
    print(f"  median {dist.median():.0f}   max {dist.max()}   "
          f"unreachable {int(rows['steps_to_sw_intake'].isna().sum())}")
    for k in (1, 2, 3, 5, 10):
        print(f"  within {k:>2d} hops: {int((dist <= k).sum()):>4d} / {len(rows)} HUC12s")

    # A worked downstream chain, as a check that the traversal is sane.
    example = rows[rows["in_U_sw"] & ~rows["in_I_sw"] & ~rows["in_I_gw"]]
    if not example.empty:
        h = example.iloc[0]["HUC12"]
        chain, seen = [h], {h}
        while chain[-1] in G:
            nxt = list(G.successors(chain[-1]))
            if not nxt or nxt[0] in seen or nxt[0] in TOHUC_SINKS:
                break
            chain.append(nxt[0])
            seen.add(nxt[0])
            if chain[-1] in I_sw or len(chain) > 40:
                break
        print(f"\nexample upstream chain: {' -> '.join(chain)}")
        print(f"  terminates in an I_sw intake HUC12: {chain[-1] in I_sw}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
