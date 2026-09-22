"""08_concentration_bivariate.py — HUC12 Li concentration (mg/L) x groundwater utility
population served.

Assigns each HUC12 the predicted Smackover brine Li concentration from the USGS
p5 / p50 / p95 rasters (Knierim et al. 2024), read separately. Every valid 2 km
cell that overlaps the HUC12 contributes its value with equal weight — including
cells that only partly overlap along the border. Cells that merely touch the
HUC12 boundary (zero shared area) do not count. Each HUC12 then gets the median
and the mean of its cells for each raster: six values.

For each of the six values, a 3x3 bivariate map shades HUC12s by Li concentration
class x population served by GROUNDWATER utilities with a well in that HUC12.
The population axis deliberately excludes (a) utilities whose only facility is a
surface-water intake, and (b) utilities that do have a well on file but whose
SDWA-classified primary source (GW_SW_CODE) is surface water — i.e. they draw
their water from a purchased surface-water connection despite the incidental
well. Only utilities SDWA classifies as primary-source groundwater count toward
the mapped population. Class breaks are fixed in utils.py and shared by all maps.

    outputs/huc12_li_concentration.gpkg / .csv   — one row per HUC12
    outputs/concentration_bivariate_summary.csv / .md  — HUC12 counts per class
    outputs/bivariate/bivariate_{p5,p50,p95}_{median,mean}.png
    outputs/bivariate/bivariate_panel.png        — all six on one figure

Note: cws_pop_served (and cws_pop_served_gw/_sw) are kept in the output table as
reference columns, but they are whole-system populations (SDWA reports it per
system, not per facility) and a system with facilities in several HUC12s is
counted in each — do not sum them across HUC12s without de-duplicating systems
(see utils.dedup_pop_served). gw_utility_pop_served, the column the maps
actually use, is per-HUC12 only and is not a system-level total.
"""
from __future__ import annotations

import importlib

import geopandas as gpd
import matplotlib.patheffects as path_effects
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely
from matplotlib.patches import Patch, Rectangle

from utils import (
    CRS_ALBERS,
    GRADES,
    LI_CONC_BREAKS,
    OUT,
    OUT_INT,
    POP_SERVED_BREAKS,
    assert_crs,
    zpad_huc12,
)

# Map context helpers shared with 07 (module name starts with a digit).
_m07 = importlib.import_module("07_summary_and_map")

STATS = ("median", "mean")
GRADE_COL = {g: f"Li_{g}_mgL" for g in GRADES}

# Joshua Stevens' 3x3 bivariate palette. Index [pop_class][li_class];
# Li runs light grey -> red, population served light grey -> blue.
BIVAR = [
    ["#e8e8e8", "#e4acac", "#c85a5a"],
    ["#b0d5df", "#ad9ea5", "#985356"],
    ["#64acbe", "#627f8c", "#574249"],
]
LI_LABELS = [
    f"< {LI_CONC_BREAKS[0]:.0f}",
    f"{LI_CONC_BREAKS[0]:.0f}–{LI_CONC_BREAKS[1]:.0f}",
    f"≥ {LI_CONC_BREAKS[1]:.0f}",
]
POP_LABELS = ["0", f"1–{POP_SERVED_BREAKS[1]:,.0f}", f"> {POP_SERVED_BREAKS[1]:,.0f}"]
POP_COL = "gw_utility_pop_served"


def value_col(grade: str, stat: str) -> str:
    return f"Li_{grade}_{stat}_mgL"


def li_class(v: pd.Series) -> pd.Series:
    lo, hi = LI_CONC_BREAKS
    return pd.Series(np.select([v < lo, v < hi], [0, 1], 2), index=v.index)


def pop_class(v: pd.Series) -> pd.Series:
    zero, hi = POP_SERVED_BREAKS
    return pd.Series(np.select([v <= zero, v <= hi], [0, 1], 2), index=v.index)


def gw_utility_pop_served(pws_ids_gw: pd.Series, pop_by_pwsid: pd.Series, true_gw: set) -> pd.Series:
    """Per-HUC12 population served by GROUNDWATER-primary utilities only.

    Sums POPULATION_SERVED_COUNT for the PWSIDs in each HUC12's pws_ids_gw list
    (already the utilities with a well on file there), keeping only PWSIDs whose
    SDWA GW_SW_CODE == 'GW'. Utilities coded 'SW' — their real primary source is
    surface water, typically a purchased surface-water connection, despite having
    a well on file somewhere — are dropped. Utilities with no well at all never
    appear in pws_ids_gw to begin with.
    """
    def _sum(ids: str) -> float:
        total = 0.0
        for p in str(ids).split(";"):
            if p and p in true_gw:
                total += pop_by_pwsid.get(p, 0.0)
        return total

    return pws_ids_gw.fillna("").map(_sum)


# ---------------------------------------------------------------------------
def cell_values_by_huc12(cells: gpd.GeoDataFrame, huc12: gpd.GeoDataFrame) -> pd.DataFrame:
    """One row per (HUC12, cell) with positive overlap area."""
    pairs = gpd.sjoin(
        cells[["cell_id", *GRADE_COL.values(), "geometry"]],
        huc12[["HUC12", "geometry"]],
        how="inner", predicate="intersects",
    )
    huc_geom = huc12.set_index("HUC12").geometry
    overlap = shapely.area(shapely.intersection(
        pairs.geometry.values, huc_geom.loc[pairs["HUC12"]].values))
    n_touch = int((overlap <= 0).sum())
    pairs = pairs[overlap > 0]
    print(f"cell x HUC12 pairs: {len(pairs):,} with overlap "
          f"({n_touch} edge-only touches dropped)")
    return pd.DataFrame(pairs.drop(columns=["geometry", "index_right"]))


def summarize(pairs: pd.DataFrame) -> pd.DataFrame:
    g = pairs.groupby("HUC12")
    out = pd.DataFrame({"n_cells": g["cell_id"].nunique()})
    for grade, src in GRADE_COL.items():
        for stat in STATS:
            out[value_col(grade, stat)] = g[src].agg(stat)
    return out.reset_index()


# ---------------------------------------------------------------------------
def _legend_grid(fig, ax, rotate_x: int = 0) -> None:
    """3x3 legend inset in the lower-left corner of ax."""
    inset = ax.inset_axes([0.03, 0.05, 0.16, 0.24])
    for p in range(3):
        for li in range(3):
            inset.add_patch(Rectangle((li, p), 1, 1, facecolor=BIVAR[p][li],
                                      edgecolor="white", linewidth=1.5))
    inset.set_xlim(0, 3)
    inset.set_ylim(0, 3)
    inset.set_aspect("equal")
    inset.set_xticks([0.5, 1.5, 2.5], LI_LABELS, fontsize=6.5, rotation=rotate_x,
                     ha="right" if rotate_x else "center")
    inset.set_yticks([0.5, 1.5, 2.5], POP_LABELS, fontsize=6.5)
    inset.set_xlabel("Li in brine (mg/L) →", fontsize=7)
    inset.set_ylabel("GW utility pop. served →", fontsize=7)
    inset.tick_params(length=0, pad=2)
    for s in inset.spines.values():
        s.set_visible(False)


def _add_state_labels(ax, states: gpd.GeoDataFrame, avoid_xy=()) -> None:
    """State-name labels, placed at the representative point of each state's
    portion actually visible in the current axis window (not its full-state
    centroid, which can fall off-map for a state the crop only clips a corner
    of). Nudged upward, repeatedly if needed, to clear any point in avoid_xy
    (e.g. the anchor-town landmarks), since Arkansas's representative point
    otherwise lands right on top of Camden."""
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    window = shapely.box(xmin, ymin, xmax, ymax)
    min_sep = 0.06 * ((xmax - xmin) ** 2 + (ymax - ymin) ** 2) ** 0.5
    step = 0.07 * (ymax - ymin)
    for _, row in states.iterrows():
        clipped = row.geometry.intersection(window)
        if clipped.is_empty:
            continue
        pt = clipped.representative_point()
        x, y = pt.x, pt.y
        for _ in range(6):
            if all(((x - ax_) ** 2 + (y - ay) ** 2) ** 0.5 >= min_sep for ax_, ay in avoid_xy):
                break
            y += step
        txt = ax.text(
            x, y, row["name"], fontsize=10, fontweight="bold",
            color="#333333", ha="center", va="center", zorder=7,
        )
        txt.set_path_effects([path_effects.withStroke(linewidth=2.5, foreground="white")])


def _base_context_gw(ax, huc12_study: gpd.GeoDataFrame, study_area: gpd.GeoDataFrame,
                      states: gpd.GeoDataFrame) -> None:
    """Like 07's _base_context, but skip the grey outline of the 471 study-area
    HUC12s: only the 141 analysis HUC12s are plotted/colored here (their white
    cell edges from df.plot already delineate them), so drawing every study HUC12
    boundary would clutter the map with HUC12s outside the analysis. Also labels
    states, which 07's shared helper does not."""
    states.boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=2)
    study_area.boundary.plot(ax=ax, color="#555555", linewidth=1.0, linestyle="--", zorder=4)
    minx, miny, maxx, maxy = huc12_study.total_bounds
    pad_x, pad_y = 0.08 * (maxx - minx), 0.08 * (maxy - miny)
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)
    landmarks = _m07._landmark_points()
    avoid_xy = list(zip(landmarks.geometry.x, landmarks.geometry.y))
    _add_state_labels(ax, states, avoid_xy=avoid_xy)


def draw_bivariate(ax, df, col, huc12_study, study_area, states, title, fontsize=11) -> None:
    _base_context_gw(ax, huc12_study, study_area, states)
    colors = [BIVAR[p][li] for p, li in zip(pop_class(df[POP_COL]), li_class(df[col]))]
    df.plot(ax=ax, color=colors, edgecolor="white", linewidth=0.3, zorder=3)
    _m07._add_landmarks(ax)
    ax.set_title(title, fontsize=fontsize)
    ax.set_axis_off()


def make_single_map(df, grade, stat, huc12_study, study_area, states, out_path) -> None:
    col = value_col(grade, stat)
    fig, ax = plt.subplots(figsize=(10, 7.5))
    draw_bivariate(
        ax, df, col, huc12_study, study_area, states,
        f"Predicted Smackover brine lithium ({grade} raster, {stat} of intersecting cells)\n"
        "× population served by groundwater utilities with a well in the HUC12",
    )
    _legend_grid(fig, ax)
    ax.legend(
        handles=[
            Patch(edgecolor="#555555", facecolor="none", linestyle="--",
                  label="Smackover model domain"),
            Patch(edgecolor="black", facecolor="none", label="State boundaries"),
        ],
        loc="lower right", bbox_to_anchor=(1.0, 0.04), fontsize=7.5, frameon=True,
    )
    ax.text(
        0.99, 0.01,
        "Li: USGS Knierim et al. 2024 | HUC12: USGS WBD | Utility (groundwater only): "
        "EPA SDWIS 2022Q2 / SDWA 2024Q4",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5, color="#444",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_panel(df, huc12_study, study_area, states, out_path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(18, 9.5))
    for r, stat in enumerate(STATS):
        for c, grade in enumerate(GRADES):
            draw_bivariate(axes[r, c], df, value_col(grade, stat), huc12_study,
                           study_area, states, f"{grade} raster — {stat} of cells", fontsize=11)
    _legend_grid(fig, axes[0, 0], rotate_x=45)
    fig.suptitle(
        "Predicted Smackover brine lithium (mg/L) × population served by "
        "groundwater utilities with a well in each HUC12",
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
def class_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    pc = pop_class(df[POP_COL])
    for grade in GRADES:
        for stat in STATS:
            lc = li_class(df[value_col(grade, stat)])
            for p in range(3):
                for li in range(3):
                    sel = (pc == p) & (lc == li)
                    rows.append({
                        "raster": grade, "stat": stat,
                        "li_class_mgL": LI_LABELS[li], "pop_served_class": POP_LABELS[p],
                        "n_huc12": int(sel.sum()),
                        "huc12_area_km2": df.loc[sel, "huc12_area_km2"].sum(),
                    })
    return pd.DataFrame(rows)


def main() -> None:
    cells = gpd.read_file(OUT_INT / "lithium_cells.gpkg", layer="cells")
    huc12 = gpd.read_file(OUT_INT / "huc12_study.gpkg", layer="huc12")
    assert_crs(cells, CRS_ALBERS, "cells")
    assert_crs(huc12, CRS_ALBERS, "huc12")
    huc12["HUC12"] = huc12["HUC12"].map(zpad_huc12)

    print("=== 08_concentration_bivariate ===")
    pairs = cell_values_by_huc12(cells, huc12)
    conc = summarize(pairs)

    impact = gpd.read_file(OUT / "huc12_lithium_impact.gpkg", layer="huc12_impact")
    impact["HUC12"] = impact["HUC12"].map(zpad_huc12)
    keep = ["HUC12", "NAME", "huc12_area_km2", "cws_pop_served", "cws_pop_served_gw",
            "cws_pop_served_sw", "n_gw_systems", "n_sw_systems", "population",
            "pws_ids_gw", "geometry"]
    missing = set(conc["HUC12"]) - set(impact["HUC12"])
    if missing:
        raise AssertionError(f"{len(missing)} HUC12s have cells but no row in 06 output: "
                             f"{sorted(missing)[:5]}")
    df = impact[keep].merge(conc, on="HUC12", how="inner")
    df = gpd.GeoDataFrame(df, geometry="geometry", crs=CRS_ALBERS)
    print(f"HUC12s with Li values: {len(df)}   cells per HUC12: "
          f"min {df['n_cells'].min()} / median {df['n_cells'].median():.0f} / "
          f"max {df['n_cells'].max()}")

    # Population axis for the maps: groundwater-primary utilities only. Drop any
    # PWSID in pws_ids_gw whose SDWA GW_SW_CODE says its real primary source is
    # surface water (own or purchased) despite a well on file somewhere.
    lookup = pd.read_csv(OUT_INT / "cws_pwsid_population.csv", dtype={"PWSID": str})
    pop_by_pwsid = lookup.set_index("PWSID")["POPULATION_SERVED_COUNT"]
    true_gw = set(lookup.loc[lookup["GW_SW_CODE"] == "GW", "PWSID"])
    gw_listed = set(p for ids in df["pws_ids_gw"].fillna("") for p in str(ids).split(";") if p)
    excluded = gw_listed - true_gw
    df[POP_COL] = gw_utility_pop_served(df["pws_ids_gw"], pop_by_pwsid, true_gw)
    print(f"\ngroundwater-listed utilities in the analysis HUC12s: {len(gw_listed)}   "
          f"excluded (GW_SW_CODE != 'GW', i.e. really surface-water sourced): {len(excluded)}")
    print(f"population served, groundwater utilities only: {df[POP_COL].sum():,.0f}   "
          f"vs. unfiltered cws_pop_served_gw: {df['cws_pop_served_gw'].sum():,.0f}")

    vcols = [value_col(g, s) for g in GRADES for s in STATS]
    # p5 <= p50 <= p95 holds per cell, so it must hold for the median and mean too.
    n_bad = 0
    for stat in STATS:
        lo, mid, hi = (df[value_col(g, stat)] for g in ("p5", "p50", "p95"))
        n_bad += int(((lo > mid + 1e-9) | (mid > hi + 1e-9)).sum())
    print(f"p5 <= p50 <= p95 ordering violations: {n_bad}")
    assert n_bad == 0, "percentile ordering violated"
    print("\nHUC12 Li values (mg/L):")
    print(df[vcols].describe().round(1).to_string())
    print("\nHUC12s per population-served class (groundwater utilities only):",
          dict(zip(POP_LABELS, np.bincount(pop_class(df[POP_COL]), minlength=3))))
    for c in vcols:
        print(f"HUC12s per Li class, {c}:",
              dict(zip(LI_LABELS, np.bincount(li_class(df[c]), minlength=3))))

    df.to_file(OUT / "huc12_li_concentration.gpkg", layer="huc12_li_conc", driver="GPKG")
    df.drop(columns="geometry").to_csv(OUT / "huc12_li_concentration.csv", index=False)

    summary = class_summary(df)
    summary.to_csv(OUT / "concentration_bivariate_summary.csv", index=False)
    md = ["# HUC12 Li concentration × groundwater utility population served — class counts\n",
          f"Li breaks (mg/L): {LI_LABELS}. Population-served breaks: {POP_LABELS}. "
          "Each HUC12's Li value is the median or mean of every valid 2 km cell overlapping "
          "it (equal weight per cell).\n",
          "**Population served counts groundwater utilities only.** A utility counts "
          "toward a HUC12's population served only if it has a well on file there "
          "*and* SDWA classifies its primary source as groundwater (`GW_SW_CODE == "
          "'GW'`). Utilities with only a surface-water intake are excluded because "
          "they never appear in the groundwater facility list to begin with; "
          "utilities that do have a well on file but whose primary source is "
          "surface water — typically because they purchase most of their water "
          "from a surface-water-only utility — are excluded explicitly. See "
          "`08_concentration_bivariate.py` and `notes/methods.md`.\n"]
    for grade in GRADES:
        for stat in STATS:
            sub = summary[(summary["raster"] == grade) & (summary["stat"] == stat)]
            tab = sub.pivot(index="pop_served_class", columns="li_class_mgL", values="n_huc12")
            tab = tab.loc[POP_LABELS[::-1], LI_LABELS]
            md.append(f"## {grade} raster, {stat} — number of HUC12s\n")
            md.append(tab.to_markdown() + "\n")
    (OUT / "concentration_bivariate_summary.md").write_text("\n".join(md), encoding="utf-8")

    fig_dir = OUT / "bivariate"
    fig_dir.mkdir(exist_ok=True)
    huc12_study = huc12
    study_area = gpd.read_file(OUT_INT / "study_area.gpkg", layer="domains")
    states = _m07._load_states()
    for grade in GRADES:
        for stat in STATS:
            make_single_map(df, grade, stat, huc12_study, study_area, states,
                            fig_dir / f"bivariate_{grade}_{stat}.png")
    make_panel(df, huc12_study, study_area, states, fig_dir / "bivariate_panel.png")
    print(f"\nWrote {OUT/'huc12_li_concentration.gpkg'}, .csv, "
          f"{OUT/'concentration_bivariate_summary.md'}, and 7 maps in {fig_dir}")


if __name__ == "__main__":
    main()
