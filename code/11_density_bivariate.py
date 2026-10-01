"""11_density_bivariate.py — HUC12 Li concentration (mg/L) x LandScan population density.

Same design as 08's bivariate maps; only the vertical axis changes: instead of
population served by groundwater utilities, HUC12s are classed by residential
population density (LandScan 2024 residents / HUC12 Albers km²). Reads the Li
columns from 08's output, so run 08 first. Does not modify 08's outputs.

    outputs/huc12_li_density.csv
    outputs/density_bivariate_summary.csv / .md
    outputs/bivariate_density/bivariate_density_{p5,p50,p95}_{median,mean}.png
    outputs/bivariate_density/bivariate_density_panel.png
"""
from __future__ import annotations

import importlib
import sys
import textwrap

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch, Rectangle

from utils import (
    CRS_ALBERS,
    GRADES,
    OUT,
    OUT_INT,
    POP_DENSITY_BREAKS,
    assert_crs,
    zpad_huc12,
)

_m07 = importlib.import_module("07_summary_and_map")
_m08 = importlib.import_module("08_concentration_bivariate")

BIVAR = _m08.BIVAR
LI_LABELS = _m08.LI_LABELS
li_class = _m08.li_class
value_col = _m08.value_col
ORDINAL = _m08.ORDINAL
panel_subtitle = _m08.panel_subtitle
_base_context_gw = _m08._base_context_gw
STATS = _m08.STATS

# Set in main(): the top class label ends at the data maximum.
DENS_LABELS: list[str] = []

MAP_TITLE = "Predicted watershed brine lithium and population density"
Y_LABEL = "Population density (people/km²) →"
SOURCE = ("Li: USGS Knierim et al. 2024 | HUC12: USGS WBD | "
          "Population: ORNL LandScan Global 2024")
PANEL_NOTES = _m08.PANEL_NOTES + (
    " Population density is LandScan 2024 ambient population in the watershed "
    "divided by watershed area."
)
EXPECTED_DENS_COUNTS = [90, 39, 12]


def density_class(v: pd.Series) -> pd.Series:
    lo, hi = POP_DENSITY_BREAKS
    return pd.Series(np.select([v < lo, v < hi], [0, 1], 2), index=v.index)


def single_map_notes(grade: str, stat: str) -> str:
    return (
        f"Notes: Predicted brine lithium values present in the watershed is the "
        f"{stat} {ORDINAL[grade]} percentile estimates of brine lithium cell values "
        f"from Knierim et al. (2024) intersecting watershed boundaries. Population "
        f"density is LandScan 2024 ambient population in the watershed divided by "
        f"watershed area. Watersheds are HUC12s."
    )


def _legend_grid(ax, rotate_x: int = 0) -> None:
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
    inset.set_yticks([0.5, 1.5, 2.5], DENS_LABELS, fontsize=6.5)
    inset.set_xlabel("Li in brine (mg/L) →", fontsize=7)
    inset.set_ylabel(Y_LABEL, fontsize=7)
    inset.tick_params(length=0, pad=2)
    for s in inset.spines.values():
        s.set_visible(False)


def draw_bivariate(ax, df, col, huc12_study, study_area, states, title, fontsize=11) -> None:
    _base_context_gw(ax, huc12_study, study_area, states)
    colors = [BIVAR[p][li] for p, li in
              zip(density_class(df["pop_density"]), li_class(df[col]))]
    df.plot(ax=ax, color=colors, edgecolor="white", linewidth=0.3, zorder=3)
    _m07._add_landmarks(ax)
    ax.set_title(title, fontsize=fontsize)
    ax.set_axis_off()


def make_single_map(df, grade, stat, huc12_study, study_area, states, out_path) -> None:
    fig, ax = plt.subplots(figsize=(10, 7.7))
    notes = "\n".join(textwrap.wrap(single_map_notes(grade, stat), width=100))
    draw_bivariate(ax, df, value_col(grade, stat), huc12_study, study_area, states,
                   notes, fontsize=7.5)
    fig.suptitle(MAP_TITLE, fontsize=13, y=0.995)
    _legend_grid(ax)
    ax.legend(
        handles=[
            Patch(edgecolor="#555555", facecolor="none", linestyle="--",
                  label="Smackover model domain"),
            Patch(edgecolor="black", facecolor="none", label="State boundaries"),
        ],
        loc="lower right", bbox_to_anchor=(1.0, 0.04), fontsize=7.5, frameon=True,
    )
    ax.text(0.99, 0.01, SOURCE, transform=ax.transAxes, ha="right", va="bottom",
            fontsize=6.5, color="#444")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_panel(df, huc12_study, study_area, states, out_path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(18, 9.7))
    for r, stat in enumerate(STATS):
        for c, grade in enumerate(GRADES):
            draw_bivariate(axes[r, c], df, value_col(grade, stat), huc12_study,
                           study_area, states, panel_subtitle(grade, stat), fontsize=11)
    _legend_grid(axes[0, 0], rotate_x=45)
    fig.suptitle(MAP_TITLE, fontsize=15, y=0.998)
    fig.text(0.5, 0.955, "\n".join(textwrap.wrap(PANEL_NOTES, width=160)),
             ha="center", va="top", fontsize=9, color="#333")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def class_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dc = density_class(df["pop_density"])
    for grade in GRADES:
        for stat in STATS:
            lc = li_class(df[value_col(grade, stat)])
            for d in range(3):
                for li in range(3):
                    sel = (dc == d) & (lc == li)
                    rows.append({
                        "raster": grade, "stat": stat,
                        "li_class_mgL": LI_LABELS[li], "density_class": DENS_LABELS[d],
                        "n_huc12": int(sel.sum()),
                        "huc12_area_km2": df.loc[sel, "huc12_area_km2"].sum(),
                        "population": df.loc[sel, "population"].sum(),
                    })
    return pd.DataFrame(rows)


def main() -> None:
    path = OUT / "huc12_li_concentration.gpkg"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — run 08_concentration_bivariate.py first")
    df = gpd.read_file(path, layer="huc12_li_conc")
    assert_crs(df, CRS_ALBERS, "huc12_li_conc")
    df["HUC12"] = df["HUC12"].map(zpad_huc12)

    print("=== 11_density_bivariate ===")
    df["pop_density"] = df["population"] / df["huc12_area_km2"]

    ref = pd.read_csv(OUT / "huc12_population.csv", dtype={"HUC12": str})
    ref["HUC12"] = ref["HUC12"].map(zpad_huc12)
    chk = df[["HUC12", "pop_density"]].merge(
        ref[["HUC12", "pop_density"]], on="HUC12", how="left", suffixes=("", "_ref"))
    assert chk["pop_density_ref"].notna().all(), "HUC12s missing from huc12_population.csv"
    assert (chk["pop_density"] - chk["pop_density_ref"]).abs().max() < 1e-6
    assert len(df) == 141, len(df)
    assert df["pop_density"].notna().all()
    assert round(df["population"].sum()) == 209_656, df["population"].sum()

    global DENS_LABELS
    lo, hi = POP_DENSITY_BREAKS
    dmax = df["pop_density"].max()
    DENS_LABELS = [f"< {lo:g}", f"{lo:g}–{hi:g}", f"{hi:g}–{dmax:.0f}"]

    dc = density_class(df["pop_density"])
    counts = np.bincount(dc, minlength=3).tolist()
    print(df["pop_density"].describe().round(2).to_string())
    print("HUC12s per density class:", dict(zip(DENS_LABELS, counts)))
    assert counts == EXPECTED_DENS_COUNTS, counts
    lc50 = li_class(df[value_col("p50", "mean")])
    print("\ndensity class x Li class (p50 mean):")
    print(pd.crosstab(pd.Series(dc.map(dict(enumerate(DENS_LABELS))), name="density"),
                      pd.Series(lc50.map(dict(enumerate(LI_LABELS))), name="Li")).to_string())

    vcols = [value_col(g, s) for g in GRADES for s in STATS]
    out = df[["HUC12", "NAME", "huc12_area_km2", "population", "pop_density", *vcols]].copy()
    out.insert(5, "density_class", dc.map(dict(enumerate(DENS_LABELS))))
    out["li_class_p50_mean"] = lc50.map(dict(enumerate(LI_LABELS)))
    out.to_csv(OUT / "huc12_li_density.csv", index=False)

    summary = class_summary(df)
    summary.to_csv(OUT / "density_bivariate_summary.csv", index=False)
    md = ["# HUC12 Li concentration × population density — class counts\n",
          f"Li breaks (mg/L): {LI_LABELS}. Population-density breaks (people/km²): "
          f"{DENS_LABELS}; classes are half-open, lower-inclusive. Density is the LandScan "
          "2024 population of the whole HUC12 divided by its equal-area (Albers) area. "
          "Each HUC12's Li value is the median or mean of every valid 2 km cell "
          "overlapping it (equal weight per cell).\n"]
    for grade in GRADES:
        for stat in STATS:
            sub = summary[(summary["raster"] == grade) & (summary["stat"] == stat)]
            tab = sub.pivot(index="density_class", columns="li_class_mgL", values="n_huc12")
            tab = tab.loc[DENS_LABELS[::-1], LI_LABELS]
            md.append(f"## {grade} raster, {stat} — number of HUC12s\n")
            md.append(tab.to_markdown() + "\n")
    (OUT / "density_bivariate_summary.md").write_text("\n".join(md), encoding="utf-8")

    fig_dir = OUT / "bivariate_density"
    fig_dir.mkdir(exist_ok=True)
    huc12_study = gpd.read_file(OUT_INT / "huc12_study.gpkg", layer="huc12")
    huc12_study["HUC12"] = huc12_study["HUC12"].map(zpad_huc12)
    study_area = gpd.read_file(OUT_INT / "study_area.gpkg", layer="domains")
    states = _m07._load_states()
    for grade in GRADES:
        for stat in STATS:
            make_single_map(df, grade, stat, huc12_study, study_area, states,
                            fig_dir / f"bivariate_density_{grade}_{stat}.png")
    make_panel(df, huc12_study, study_area, states, fig_dir / "bivariate_density_panel.png")
    print(f"\nWrote density CSV/summary and 7 maps in {fig_dir}")


if __name__ == "__main__":
    main()
