"""06_impact_dataset.py — Build the HUC12 lithium / population / drinking-water dataset.

Unit of analysis is the HUC12. Two stages:

  a) overlay the 2 km lithium cells with HUC12s (identity, so each piece belongs to
     exactly one HUC12) and apportion in-place tonnage by area fraction, so no mass is
     created or lost at a watershed boundary;
  b) dissolve to one row per HUC12 and attach population, CWS flags, and impact tier.

Writes outputs/huc12_lithium_impact.{gpkg,shp,csv} and the split layer as an
intermediate (cartography + audit trail).
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import make_valid

from utils import (
    CRS_ALBERS,
    GRADES,
    OUT,
    OUT_INT,
    POROSITIES,
    POP_SENSITIVITY,
    TON_MAIN,
    UPSTREAM_K_SENSITIVITY,
    UPSTREAM_NEAR_K,
    assert_crs,
    dedup_pop_served,
    ton_col,
    zpad_huc12,
)

TON_COLS = [ton_col(g, p) for p in POROSITIES for g in GRADES]
# Headline tier uses the distance-limited upstream screen (see notes/implementation_plan.md
# §11): "upstream of a CWS surface intake" at any distance flags ~100% of tonnage and is not
# a discriminating screen. upstream_near = upstream_of_sw_intake AND within UPSTREAM_NEAR_K
# hops. upstream_of_sw_intake (any distance) is kept as a descriptive column, not a reason.
REASON_FLAGS = [
    ("high_pop_flag", "population"),
    ("in_sw_intake_huc", "sw_intake"),
    ("in_gw_intake_huc", "gw_intake"),
    ("upstream_near", "upstream_sw"),
]


def main() -> None:
    cells = gpd.read_file(OUT_INT / "lithium_cells.gpkg", layer="cells")
    huc12 = gpd.read_file(OUT_INT / "huc12_study.gpkg", layer="huc12")
    assert_crs(cells, CRS_ALBERS, "cells")
    assert_crs(huc12, CRS_ALBERS, "huc12")

    # --- a) split cells at HUC12 lines, apportioning tonnage by area fraction ---------
    splits = gpd.overlay(
        cells, huc12[["HUC12", "NAME", "geometry"]], how="identity", keep_geom_type=True
    )
    dropped = int(splits["HUC12"].isna().sum())
    if dropped:
        print(f"WARN: {dropped} split pieces fall outside the buffered HUC12 layer — dropped")
    splits = splits[splits["HUC12"].notna()].copy()
    splits["geometry"] = splits.geometry.apply(make_valid)
    splits = splits[~splits.geometry.is_empty].copy()
    splits["HUC12"] = splits["HUC12"].map(zpad_huc12)

    parent_area = cells.set_index("cell_id")["area_km2"]
    splits["piece_area_km2"] = splits.geometry.area / 1e6
    frac = (splits["piece_area_km2"] / splits["cell_id"].map(parent_area)).to_numpy()
    for c in TON_COLS:
        splits[c] = splits[c].to_numpy() * frac
    splits["h2o_prod_bbl_2022"] = splits["h2o_prod_bbl_2022"].to_numpy() * frac

    lost = 1.0 - splits[TON_MAIN].sum() / cells[TON_MAIN].sum()
    print("=== 06_impact_dataset ===")
    print(f"cells {len(cells):,} -> split pieces {len(splits):,} across "
          f"{splits['HUC12'].nunique():,} HUC12s")
    print(f"tonnage conservation (p50/20%): {splits[TON_MAIN].sum():,.0f} of "
          f"{cells[TON_MAIN].sum():,.0f} t   loss {lost:.3%}")
    if abs(lost) > 1e-4:
        raise AssertionError(f"Tonnage not conserved across the overlay: {lost:.4%}")
    area_lost = 1.0 - splits["piece_area_km2"].sum() / cells["area_km2"].sum()
    print(f"area conservation: {splits['piece_area_km2'].sum():,.1f} of "
          f"{cells['area_km2'].sum():,.1f} km2   loss {area_lost:.3%}")

    splits.to_file(OUT_INT / "lithium_cells_split.gpkg", layer="split", driver="GPKG")

    # --- b) dissolve to HUC12 ---------------------------------------------------------
    agg = {c: (c, "sum") for c in TON_COLS}
    agg.update(
        li_area_km2=("piece_area_km2", "sum"),
        n_cell_pieces=("cell_id", "count"),
        h2o_prod_bbl_2022=("h2o_prod_bbl_2022", "sum"),
        qualunc_max=("qualunc", "max"),
    )
    grouped = splits.groupby("HUC12").agg(**agg)

    # Area-weighted descriptive means (a thin sliver must not outvote a whole cell).
    w = splits["piece_area_km2"]
    for src, dst in (("Li_mgL", "Li_mgL_mean"), ("Li_p50_mgL", "Li_p50_mgL_mean"),
                     ("thick_m", "thick_m_mean")):
        num = splits.assign(_x=splits[src] * w).groupby("HUC12")["_x"].sum()
        grouped[dst] = num / splits.groupby("HUC12")[["piece_area_km2"]].sum()["piece_area_km2"]

    geom = splits.dissolve(by="HUC12").geometry  # lithium footprint within each HUC12
    grouped["li_footprint_geom"] = geom

    out = huc12.merge(grouped.reset_index(), on="HUC12", how="inner")

    conflict = pd.read_csv(OUT / "conflict_hucs.csv", dtype={"HUC12": str})
    conflict["HUC12"] = conflict["HUC12"].map(zpad_huc12)
    pop = pd.read_csv(OUT / "huc12_population.csv", dtype={"HUC12": str})
    pop["HUC12"] = pop["HUC12"].map(zpad_huc12)

    out = out.merge(conflict, on="HUC12", how="left").merge(
        pop.drop(columns=["huc12_area_km2"]), on="HUC12", how="left"
    )
    out = out.rename(columns={
        "in_I_sw": "in_sw_intake_huc",
        "in_I_gw": "in_gw_intake_huc",
        "in_U_sw": "upstream_of_sw_intake",
        "high_pop_huc": "high_pop_flag",
    })
    for c in ("in_sw_intake_huc", "in_gw_intake_huc", "upstream_of_sw_intake", "high_pop_flag"):
        out[c] = out[c].fillna(False).astype(bool)
    for c in ("population", "pop_density", "cws_pop_served",
              "n_sw_facilities", "n_gw_facilities", "n_sw_systems", "n_gw_systems"):
        out[c] = out[c].fillna(0.0)
    for c in ("pws_ids_sw", "pws_ids_gw"):
        out[c] = out[c].fillna("")
    out["steps_to_sw_intake"] = out["steps_to_sw_intake"].astype("Int64")

    # --- classification ----------------------------------------------------------------
    out["upstream_near"] = (
        out["upstream_of_sw_intake"]
        & out["steps_to_sw_intake"].notna()
        & (out["steps_to_sw_intake"] <= UPSTREAM_NEAR_K)
    )
    flags = out[[c for c, _ in REASON_FLAGS]]
    out["n_reasons"] = flags.sum(axis=1).astype(int)
    out["impact_reasons"] = [
        ";".join(label for (col, label) in REASON_FLAGS if row[col]) or "none"
        for _, row in flags.iterrows()
    ]
    out["impact_tier"] = np.where(out["n_reasons"] > 0, "high", "low")

    # Direct-conflict variant: drop the upstream screen, which is near-universal in CONUS.
    out["impact_tier_direct"] = np.where(
        out[["high_pop_flag", "in_sw_intake_huc", "in_gw_intake_huc"]].any(axis=1), "high", "low"
    )

    out["li_frac"] = out["li_area_km2"] / out["huc12_area_km2"]
    out["li_ton_per_km2"] = out[TON_MAIN] / out["li_area_km2"]

    out = out.drop(columns=["li_footprint_geom"])
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=CRS_ALBERS)

    gpkg = OUT / "huc12_lithium_impact.gpkg"
    out.to_file(gpkg, layer="huc12_impact", driver="GPKG")
    out.to_file(OUT / "huc12_lithium_impact.shp")
    out.drop(columns="geometry").to_csv(OUT / "huc12_lithium_impact.csv", index=False)

    # --- report ------------------------------------------------------------------------
    total = out[TON_MAIN].sum()
    print(f"\nanalysis HUC12s (intersecting the lithium footprint): {len(out):,}")
    print(f"in-place Li (p50/20%) carried onto HUC12s: {total:,.0f} t")
    print(f"lithium footprint area: {out['li_area_km2'].sum():,.0f} km2   "
          f"HUC12 area: {out['huc12_area_km2'].sum():,.0f} km2")
    pop_lookup = pd.read_csv(
        OUT_INT / "cws_pwsid_population.csv"
    ).set_index("PWSID")["POPULATION_SERVED_COUNT"]
    print(f"resident population: {out['population'].sum():,.0f}   "
          f"CWS population served (sum of per-HUC12 values; double-counts systems with "
          f"facilities in >1 HUC12): {out['cws_pop_served'].sum():,.0f}   "
          f"distinct systems (de-duplicated by PWSID): {dedup_pop_served(out, pop_lookup):,.0f}")

    print("\nscreens fired, over the analysis HUC12s (n, % of tonnage):")
    for col, label in REASON_FLAGS:
        sel = out[out[col]]
        print(f"  {label:<12s} {len(sel):>4d} HUC12s   {sel[TON_MAIN].sum()/total:6.1%} of tonnage")
    print(f"\nimpact_tier (headline; upstream limited to <= {UPSTREAM_NEAR_K} hops): "
          f"{dict(out['impact_tier'].value_counts())}")
    print(f"impact_tier_direct (no upstream at all): "
          f"{dict(out['impact_tier_direct'].value_counts())}")
    for tier_col in ("impact_tier", "impact_tier_direct"):
        share = out.groupby(tier_col)[TON_MAIN].sum() / total
        print(f"  {tier_col}: " + "  ".join(f"{k}={v:.1%}" for k, v in share.items()))
    degenerate = out["upstream_of_sw_intake"] | out["in_sw_intake_huc"] | out["in_gw_intake_huc"] | out["high_pop_flag"]
    print(f"  diagnostic only — upstream at ANY distance: "
          f"{int(degenerate.sum())}/{len(out)} HUC12s, "
          f"{out.loc[degenerate, TON_MAIN].sum()/total:.1%} of tonnage "
          "(this is the degenerate screen §11 warns about; not used for impact_tier)")
    print("\nn_reasons distribution:", dict(out["n_reasons"].value_counts().sort_index()))
    print("\npopulation-threshold sensitivity over analysis HUC12s:")
    for count_thr, dens_thr in POP_SENSITIVITY:
        c = f"high_pop_{count_thr}_{int(dens_thr)}"
        sel = out[out[c].fillna(False).astype(bool)]
        print(f"  {count_thr:>6,} / {dens_thr:>5g}: {len(sel):>3d} HUC12s, "
              f"{sel[TON_MAIN].sum()/total:5.1%} of tonnage")
    print(f"\nsteps_to_sw_intake sensitivity (direct screens + upstream <= k hops):")
    base = out["high_pop_flag"] | out["in_sw_intake_huc"] | out["in_gw_intake_huc"]
    for k in UPSTREAM_K_SENSITIVITY:
        if k is None:
            sel_mask = base | out["upstream_of_sw_intake"]
            label = " inf"
        else:
            near_k = out["upstream_of_sw_intake"] & out["steps_to_sw_intake"].notna() & (out["steps_to_sw_intake"] <= k)
            sel_mask = base | near_k
            label = f"{k:>4d}"
        sel = out[sel_mask]
        print(f"  k={label}: {len(sel):>3d} HUC12s, {sel[TON_MAIN].sum()/total:5.1%} of tonnage")
    print(f"\nWrote {gpkg}, .shp and .csv")


if __name__ == "__main__":
    main()
