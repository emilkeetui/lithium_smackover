"""10_private_wells.py — private-well population per HUC12 + bivariate map (Li x private wells).

Private-well population is estimated three ways (see notes/private_wells_plan.md §0):
  A  pop_h - sum_i reported_pop_i * area(i ∩ h)/area(i)           (area-weighted; diagnostic)
  B  pop_h - sum_i reported_pop_i * LS(i ∩ h)/LS(i)               (LandScan-weighted; low bound)
  C  LS(h) - LS(h ∩ union of service areas)                       (HEADLINE; map variable)
where LS(x) is the LandScan sum over polygon x (exactextract on the native 4326 raster)
and i indexes EPA CWS service-area polygons. C = LandScan people living outside every
mapped community-water-system service area.

    outputs/huc12_private_wells.csv / .gpkg       — one row per study HUC12 (471)
    outputs/private_wells_summary.csv / .md
    outputs/intermediate/service_areas_study.csv, huc12_serviceareas_pairs.csv
    outputs/bivariate/bivariate_p50_mean_private_wells.png, private_wells_class_counts.csv
"""
from __future__ import annotations

import importlib
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from exactextract import exact_extract

from utils import (
    CRS_ALBERS,
    LANDSCAN_TIF,
    OUT,
    OUT_INT,
    PRIVATE_WELL_BREAKS,
    SERVICE_AREA_SHP,
    assert_crs,
    zpad_huc12,
)

_m08 = importlib.import_module("08_concentration_bivariate")

PW_COL = "private_well_pop"
Y_LABEL = "Private-well pop. →"
TITLE = "Predicted watershed brine lithium and size of population relying on private wells"
NOTES = (
    "Notes: Private-well population is LandScan 2024 population living outside every "
    "mapped community water system service area (EPA CWS Service Area Boundaries v1). "
    "Lithium is the mean of the 50th-percentile cell estimates from Knierim et al. "
    "(2024) intersecting each HUC12."
)
SOURCE = ("Li: USGS Knierim et al. 2024 | HUC12: USGS WBD | Population: ORNL LandScan 2024 "
          "| Service areas: EPA CWS boundaries v1")


def landscan_sum(gdf: gpd.GeoDataFrame) -> np.ndarray:
    """LandScan sum per row. Polygons go to 4326; the raster is never warped."""
    g = gdf[["geometry"]].to_crs(4326).reset_index(drop=True)
    g["k"] = range(len(g))
    r = exact_extract(str(LANDSCAN_TIF), g, "sum", include_cols=["k"], output="pandas")
    return r.set_index("k")["sum"].reindex(range(len(g))).fillna(0).to_numpy()


def load_service_areas(huc12: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    bb = tuple(gpd.GeoSeries([shapely.box(*huc12.total_bounds)], crs=CRS_ALBERS)
               .to_crs(3857).total_bounds)
    sa = pyogrio.read_dataframe(
        SERVICE_AREA_SHP, bbox=bb,
        columns=["PWSID", "PWS_Name", "Primacy_Ag", "Population", "Service_Co", "Method"])
    sa = sa.to_crs(CRS_ALBERS)
    sa["geometry"] = shapely.make_valid(sa.geometry.values)
    sa = sa[~sa.geometry.is_empty].reset_index(drop=True)
    sa = sa.rename(columns={"Population": "sa_pop_reported"})
    sa["sa_pop_reported"] = sa["sa_pop_reported"].fillna(0)
    assert not sa["PWSID"].duplicated().any(), "duplicate PWSIDs in service-area file"
    sa["sa_area_km2"] = sa.area / 1e6
    n0 = int((sa["sa_pop_reported"] <= 0).sum())
    print(f"service areas in study bbox: {len(sa)}   null/0 reported population: {n0}   "
          f"by Method: {sa['Method'].value_counts().to_dict()}", flush=True)
    sa["sa_pop_landscan"] = landscan_sum(sa)
    sa["reported_to_landscan"] = sa["sa_pop_reported"] / sa["sa_pop_landscan"].clip(lower=1)
    sa.drop(columns="geometry").to_csv(OUT_INT / "service_areas_study.csv", index=False)
    return sa


def build_pieces(huc12: gpd.GeoDataFrame, sa: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    pieces = gpd.overlay(huc12[["HUC12", "geometry"]], sa[["PWSID", "geometry"]],
                         how="intersection", keep_geom_type=True)
    pieces = pieces[pieces.area > 0].reset_index(drop=True)
    pieces["piece_km2"] = pieces.area / 1e6
    pieces["piece_landscan"] = landscan_sum(pieces)
    pieces = pieces.merge(sa[["PWSID", "sa_pop_reported", "sa_area_km2", "sa_pop_landscan"]],
                          on="PWSID")
    pieces["served_area_wt"] = (pieces.sa_pop_reported * pieces.piece_km2 / pieces.sa_area_km2)
    pieces["served_pop_wt"] = (pieces.sa_pop_reported * pieces.piece_landscan
                               / pieces.sa_pop_landscan.clip(lower=1e-9))
    print(f"HUC12 x service-area pieces: {len(pieces):,}", flush=True)
    pieces.drop(columns="geometry").to_csv(OUT_INT / "huc12_serviceareas_pairs.csv", index=False)
    return pieces


def assemble(huc12: gpd.GeoDataFrame, pieces: gpd.GeoDataFrame, analysis: set) -> gpd.GeoDataFrame:
    pop = pd.read_csv(OUT / "huc12_population.csv", dtype={"HUC12": str})
    pop["HUC12"] = pop["HUC12"].map(zpad_huc12)
    df = huc12[["HUC12", "geometry"]].merge(pop[["HUC12", "huc12_area_km2", "population"]],
                                            on="HUC12", how="left")
    assert df["population"].notna().all(), "huc12_population.csv misses study HUC12s"

    grp = pieces.groupby("HUC12").agg(n_utilities=("PWSID", "nunique"),
                                      served_area_wt=("served_area_wt", "sum"),
                                      served_pop_wt=("served_pop_wt", "sum"))
    cov = pieces.dissolve("HUC12")[["geometry"]]
    cov["pop_in_service_area"] = landscan_sum(cov)
    cov["sa_cover_km2"] = cov.area / 1e6
    df = (df.merge(grp, left_on="HUC12", right_index=True, how="left")
            .merge(cov.drop(columns="geometry"), left_on="HUC12", right_index=True, how="left"))
    fill = ["n_utilities", "served_area_wt", "served_pop_wt", "pop_in_service_area", "sa_cover_km2"]
    df[fill] = df[fill].fillna(0)
    df["sa_cover_frac"] = df["sa_cover_km2"] / df["huc12_area_km2"]

    raw_c = df["population"] - df["pop_in_service_area"]
    assert raw_c.min() >= -1, f"population < pop_in_service_area by {raw_c.min():.1f}: CRS/geometry bug"
    df[PW_COL] = raw_c.clip(lower=0)
    df["private_well_frac"] = df[PW_COL] / df["population"].clip(lower=1)
    df["private_well_pop_area_wt_raw"] = df["population"] - df["served_area_wt"]
    df["private_well_pop_area_wt"] = df["private_well_pop_area_wt_raw"].clip(lower=0)
    df["private_well_pop_pop_wt_raw"] = df["population"] - df["served_pop_wt"]
    df["private_well_pop_pop_wt"] = df["private_well_pop_pop_wt_raw"].clip(lower=0)
    df["in_analysis"] = df["HUC12"].isin(analysis)
    return gpd.GeoDataFrame(df, geometry="geometry", crs=CRS_ALBERS)


def estimator_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, sub in (("analysis 141", df[df.in_analysis]), ("study 471", df)):
        for name, raw, floored in (
            ("A area-weighted", "private_well_pop_area_wt_raw", "private_well_pop_area_wt"),
            ("B pop-weighted", "private_well_pop_pop_wt_raw", "private_well_pop_pop_wt"),
            ("C outside service areas", None, PW_COL),
        ):
            r = sub[raw] if raw else sub["population"] - sub["pop_in_service_area"]
            rows.append({
                "scope": scope, "estimator": name, "n_huc12": len(sub),
                "total_population": sub["population"].sum(),
                "n_negative": int((r < -1e-9).sum()) if raw else int((r < -1).sum()),
                "n_zero": int((sub[floored] == 0).sum()),
                "floored_sum": sub[floored].sum(),
                "share_of_pop": sub[floored].sum() / sub["population"].sum(),
            })
    return pd.DataFrame(rows)


def write_summary(df, sa, pieces, tab, breaks_info) -> None:
    tab.to_csv(OUT / "private_wells_summary.csv", index=False)
    md = ["# Private-well population per HUC12 — summary\n",
          "A and B are sensitivity bounds; **C is the headline** (LandScan people outside every "
          "mapped CWS service area).\n",
          tab.to_markdown(index=False, floatfmt=",.3f") + "\n"]

    by = (sa.groupby("Method")["reported_to_landscan"]
            .agg(n="size", median="median", p90=lambda s: s.quantile(0.9),
                 n_gt2=lambda s: int((s > 2).sum())))
    md += ["## Reported population / LandScan population inside polygon, by boundary Method\n",
           by.to_markdown(floatfmt=".2f") + "\n",
           f"Overall median {sa['reported_to_landscan'].median():.2f}; "
           f"{int((sa['reported_to_landscan'] > 2).sum())} of {len(sa)} polygons above 2×.\n"]

    worst = df.nsmallest(10, "private_well_pop_area_wt_raw")[
        ["HUC12", "population", "served_area_wt", "private_well_pop_area_wt_raw"]].copy()
    top = (pieces.sort_values("served_area_wt", ascending=False)
                 .drop_duplicates("HUC12").set_index("HUC12")["PWSID"])
    names = sa.set_index("PWSID")["PWS_Name"]
    worst["top_utility"] = worst["HUC12"].map(top).map(names)
    md += ["## Ten most negative HUC12s under estimator A\n", worst.to_markdown(index=False, floatfmt=",.0f") + "\n"]

    pm = pieces.merge(sa[["PWSID", "Method"]], on="PWSID")
    pm["is_state"] = pm["Method"].eq("State")
    # share of LandScan people in service areas that sit in State-supplied vs modeled polygons
    ls = pm.groupby("is_state")["piece_landscan"].sum()
    md += ["## Where the service-area population sits (sum of piece LandScan)\n",
           f"State-supplied polygons: {ls.get(True, 0):,.0f} "
           f"({ls.get(True, 0) / ls.sum():.1%}); modeled/other: {ls.get(False, 0):,.0f} "
           f"({ls.get(False, 0) / ls.sum():.1%}).\n"]
    md += ["## Map class breaks (analysis HUC12s)\n", breaks_info + "\n"]
    (OUT / "private_wells_summary.md").write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    print("=== 10_private_wells ===", flush=True)
    huc12 = gpd.read_file(OUT_INT / "huc12_study.gpkg", layer="huc12")
    assert_crs(huc12, CRS_ALBERS, "huc12")
    huc12["HUC12"] = huc12["HUC12"].map(zpad_huc12)
    impact = gpd.read_file(OUT / "huc12_lithium_impact.gpkg", layer="huc12_impact")
    impact["HUC12"] = impact["HUC12"].map(zpad_huc12)
    analysis = set(impact["HUC12"])

    sa = load_service_areas(huc12)
    pieces = build_pieces(huc12, sa)
    df = assemble(huc12, pieces, analysis)

    # --- acceptance checks ---
    assert len(df) == 471 and df["HUC12"].is_unique, "expected 471 unique study HUC12s"
    assert df[["population", "pop_in_service_area", PW_COL]].notna().all().all()
    assert (df[PW_COL] >= 0).all()

    tab = estimator_table(df)
    print(tab.to_string(index=False), flush=True)

    df.to_file(OUT / "huc12_private_wells.gpkg", layer="huc12_private_wells", driver="GPKG")
    df.drop(columns="geometry").to_csv(OUT / "huc12_private_wells.csv", index=False)

    # --- bivariate map (analysis HUC12s only, like 08) ---
    conc = pd.read_csv(OUT / "huc12_li_concentration.csv", dtype={"HUC12": str})
    conc["HUC12"] = conc["HUC12"].map(zpad_huc12)
    m = impact[["HUC12", "geometry"]].merge(
        conc[["HUC12", "Li_p50_mean_mgL", "huc12_area_km2"]], on="HUC12", how="inner").merge(
        df[["HUC12", PW_COL]], on="HUC12", how="left")
    m = gpd.GeoDataFrame(m, geometry="geometry", crs=CRS_ALBERS)

    lo, hi = PRIVATE_WELL_BREAKS
    cls = _m08.pop_class(m[PW_COL], PRIVATE_WELL_BREAKS)
    counts = np.bincount(cls, minlength=3)
    print(f"private-well class counts {counts.tolist()} for breaks {PRIVATE_WELL_BREAKS}; "
          f"33/67th pct: {m[PW_COL].quantile([1/3, 2/3]).round(0).tolist()}", flush=True)
    labels = [f"0–{lo:,.0f}", f"{lo + 1:,.0f}–{hi:,.0f}", f"{hi + 1:,.0f}–{m[PW_COL].max():,.0f}"]
    breaks_info = (f"Breaks {PRIVATE_WELL_BREAKS}; classes {labels}; HUC12 counts {counts.tolist()}."
                   + ("" if counts.min() >= 35 else
                      " WARNING: a class has fewer than 35 HUC12s — consider adjusting breaks."))
    write_summary(df, sa, pieces, tab, breaks_info)

    fig_dir = OUT / "bivariate"
    fig_dir.mkdir(exist_ok=True)
    study_area = gpd.read_file(OUT_INT / "study_area.gpkg", layer="domains")
    states = _m08._m07._load_states()
    _m08.make_single_map(
        m, "p50", "mean", huc12, study_area, states,
        fig_dir / "bivariate_p50_mean_private_wells.png",
        col="Li_p50_mean_mgL", pop_col=PW_COL, pop_breaks=PRIVATE_WELL_BREAKS,
        pop_labels=labels, y_label=Y_LABEL, title=TITLE, notes=NOTES, source=SOURCE)

    lc = _m08.li_class(m["Li_p50_mean_mgL"])
    rows = []
    for p in range(3):
        for li in range(3):
            sel = (cls == p) & (lc == li)
            rows.append({"li_class_mgL": _m08.LI_LABELS[li], "private_well_class": labels[p],
                         "n_huc12": int(sel.sum()),
                         "huc12_area_km2": m.loc[sel, "huc12_area_km2"].sum()})
    pd.DataFrame(rows).to_csv(fig_dir / "private_wells_class_counts.csv", index=False)
    print(f"Wrote {OUT/'huc12_private_wells.csv'}, summary, and map in {fig_dir}", flush=True)


if __name__ == "__main__":
    main()
