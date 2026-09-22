"""07_summary_and_map.py — Headline summary tables + map figures.

Reads outputs/huc12_lithium_impact.gpkg (the 141-row analysis table from
06_impact_dataset.py) and produces:

    outputs/impact_summary.csv / .md   — headline table + supporting tables
    outputs/impact_map.png             — HUC12s red (high) / green (low) impact
    outputs/tonnage_map.png            — HUC12s graduated by li_ton_p50_por20
    outputs/tonnage_by_tier.png        — bar chart, p5-p95 whisker

No pygris / Census network fetch (not installed, and the plan forbids adding a
hard network dependency here) — state/county lines are dropped; three anchor
towns (El Dorado, Magnolia, Camden) are labelled from hard-coded coordinates
for reader orientation only, not used in any computation.
"""
from __future__ import annotations

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

from utils import (
    CRS_ALBERS,
    GRADES,
    NE_STATES_SHP,
    OUT,
    OUT_INT,
    POP_SENSITIVITY,
    POROSITIES,
    STUDY_PRIMACY_CODES,
    TON_MAIN,
    UPSTREAM_K_SENSITIVITY,
    UPSTREAM_NEAR_K,
    assert_crs,
    dedup_pop_served,
    to_albers,
    ton_col,
    zpad_huc12,
)

# Anchor towns for map orientation only (approximate centers; not analysis inputs).
LANDMARKS = {
    "El Dorado": (-92.6663, 33.2076),
    "Magnolia": (-93.2385, 33.2662),
    "Camden": (-92.8340, 33.5843),
}

TIER_COLOR = {"high": "#d62728", "low": "#2ca02c"}


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------
def headline_table(df: pd.DataFrame, pop_lookup: pd.Series) -> pd.DataFrame:
    rows = []
    for tier, g in df.groupby("impact_tier"):
        rows.append({
            "impact_tier": tier,
            "n_huc12": len(g),
            "li_ton_p5_por20": g[ton_col("p5", 20)].sum(),
            "li_ton_p50_por20": g[TON_MAIN].sum(),
            "li_ton_p95_por20": g[ton_col("p95", 20)].sum(),
            "li_area_km2": g["li_area_km2"].sum(),
            "huc12_area_km2": g["huc12_area_km2"].sum(),
            "population": g["population"].sum(),
            # Distinct-system total, NOT g["cws_pop_served"].sum(): cws_pop_served is a
            # per-system value repeated on every HUC12 that system touches, so summing
            # it across the tier's HUC12s would double-count any system with facilities
            # in more than one HUC12 of the same tier. See utils.dedup_pop_served.
            "cws_pop_served": dedup_pop_served(g, pop_lookup),
            "li_ton_per_km2_mean": g["li_ton_per_km2"].mean(),
        })
    out = pd.DataFrame(rows).set_index("impact_tier")
    out["pct_of_ton_p50"] = 100 * out["li_ton_p50_por20"] / out["li_ton_p50_por20"].sum()
    out["pct_of_area"] = 100 * out["li_area_km2"] / out["li_area_km2"].sum()
    return out.loc[[t for t in ("high", "low") if t in out.index]]


def porosity_invariance(df: pd.DataFrame) -> pd.DataFrame:
    """% of tonnage in the 'high' tier at each porosity (p50 grade). Must be
    identical across porosities: porosity scales every cell's tonnage by the
    same constant, and it cancels out of a tier that is defined independently
    of tonnage (population/CWS/upstream flags only)."""
    rows = []
    for por in POROSITIES:
        col = ton_col("p50", por)
        share = df.groupby("impact_tier")[col].sum()
        pct_high = 100 * share.get("high", 0.0) / share.sum()
        rows.append({"porosity_pct": por, "pct_tonnage_high": pct_high})
    out = pd.DataFrame(rows)
    spread = out["pct_tonnage_high"].max() - out["pct_tonnage_high"].min()
    if spread > 1e-6:
        raise AssertionError(
            f"Porosity is not invariant to the high/low split ({spread:.2e} pct-point "
            "spread) — the tier must not depend on tonnage magnitude."
        )
    return out


def grade_band(df: pd.DataFrame) -> pd.DataFrame:
    """% of tonnage in the 'high' tier at each grade percentile, 20% porosity."""
    rows = []
    for grade in GRADES:
        col = ton_col(grade, 20)
        share = df.groupby("impact_tier")[col].sum()
        pct_high = 100 * share.get("high", 0.0) / share.sum()
        rows.append({"grade": grade, "pct_tonnage_high": pct_high})
    return pd.DataFrame(rows)


def reason_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    total = df[TON_MAIN].sum()
    grp = df.groupby("impact_reasons").agg(
        n_huc12=("HUC12", "count"),
        li_ton_p50_por20=(TON_MAIN, "sum"),
        population=("population", "sum"),
    )
    grp["pct_tonnage"] = 100 * grp["li_ton_p50_por20"] / total
    return grp.sort_values("li_ton_p50_por20", ascending=False)


def pop_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    total = df[TON_MAIN].sum()
    rows = []
    for count_thr, dens_thr in POP_SENSITIVITY:
        c = f"high_pop_{count_thr}_{int(dens_thr)}"
        sel = df[df[c].fillna(False).astype(bool)]
        rows.append({
            "count_threshold": count_thr, "density_threshold": dens_thr,
            "n_huc12": len(sel), "pct_tonnage": 100 * sel[TON_MAIN].sum() / total,
        })
    return pd.DataFrame(rows)


def steps_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    """% of tonnage flagged as direct-conflict + upstream-within-k-hops, for
    k = 1, 2, 3, 5, 10, inf. Makes the §11 decision (k=2 for the headline)
    legible against its neighbors."""
    total = df[TON_MAIN].sum()
    base = df["high_pop_flag"] | df["in_sw_intake_huc"] | df["in_gw_intake_huc"]
    rows = []
    for k in UPSTREAM_K_SENSITIVITY:
        if k is None:
            mask = base | df["upstream_of_sw_intake"]
            label = "inf (any distance)"
        else:
            near = (
                df["upstream_of_sw_intake"]
                & df["steps_to_sw_intake"].notna()
                & (df["steps_to_sw_intake"] <= k)
            )
            mask = base | near
            label = str(k)
        rows.append({
            "k_hops": label, "n_huc12": int(mask.sum()),
            "pct_tonnage": 100 * df.loc[mask, TON_MAIN].sum() / total,
            "is_headline": (k == UPSTREAM_NEAR_K),
        })
    return pd.DataFrame(rows)


def top15(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["HUC12", "NAME", TON_MAIN, "li_area_km2", "population",
            "cws_pop_served", "impact_tier", "impact_reasons"]
    return df.sort_values(TON_MAIN, ascending=False).head(15)[cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def _landmark_points() -> gpd.GeoDataFrame:
    names = list(LANDMARKS)
    lons = [LANDMARKS[n][0] for n in names]
    lats = [LANDMARKS[n][1] for n in names]
    pts = gpd.GeoDataFrame(
        {"name": names}, geometry=gpd.points_from_xy(lons, lats), crs="EPSG:4326"
    )
    return pts.to_crs(CRS_ALBERS)


def _add_landmarks(ax) -> None:
    pts = _landmark_points()
    pts.plot(ax=ax, color="black", markersize=18, marker="s", zorder=6)
    for _, row in pts.iterrows():
        ax.annotate(
            row["name"], (row.geometry.x, row.geometry.y),
            xytext=(5, 5), textcoords="offset points",
            fontsize=8, fontweight="bold", zorder=6,
        )


def _load_states() -> gpd.GeoDataFrame:
    """State boundaries for map context, from a local Natural Earth file already on
    disk (no pygris / Census network fetch, per notes/implementation_plan.md §8)."""
    states = gpd.read_file(NE_STATES_SHP, columns=["postal", "iso_a2", "name", "geometry"])
    states = states[(states["iso_a2"] == "US") & (states["postal"].isin(STUDY_PRIMACY_CODES))]
    return to_albers(states)


def _base_context(ax, huc12_study: gpd.GeoDataFrame, study_area: gpd.GeoDataFrame, states: gpd.GeoDataFrame) -> None:
    states.boundary.plot(ax=ax, color="black", linewidth=1.0, zorder=2)
    huc12_study.boundary.plot(ax=ax, color="#bbbbbb", linewidth=0.3, zorder=1)
    study_area.boundary.plot(ax=ax, color="#555555", linewidth=1.0, linestyle="--", zorder=4)
    # States span multiple state extents, far larger than the study area; without an
    # explicit crop the autoscaled view shrinks the study area to an unreadable dot.
    minx, miny, maxx, maxy = huc12_study.total_bounds
    pad_x, pad_y = 0.08 * (maxx - minx), 0.08 * (maxy - miny)
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)


def _intake_overlays(ax, huc12_study: gpd.GeoDataFrame, sw_hucs: set, gw_hucs: set) -> None:
    sw_layer = huc12_study[huc12_study["HUC12"].isin(sw_hucs)]
    gw_layer = huc12_study[huc12_study["HUC12"].isin(gw_hucs)]
    if len(sw_layer):
        sw_layer.boundary.plot(ax=ax, color="#1f77b4", linewidth=1.1, zorder=5)
    if len(gw_layer):
        gw_layer.boundary.plot(ax=ax, color="#ff7f0e", linewidth=0.6, alpha=0.8, zorder=2)


def make_impact_map(df, huc12_study, study_area, states, sw_hucs, gw_hucs, out_path) -> None:
    fig, ax = plt.subplots(figsize=(10, 10))
    _base_context(ax, huc12_study, study_area, states)

    for tier, color in TIER_COLOR.items():
        sub = df[df["impact_tier"] == tier]
        if len(sub):
            sub.plot(ax=ax, color=color, alpha=0.65, edgecolor="white",
                      linewidth=0.2, zorder=3)

    _intake_overlays(ax, huc12_study, sw_hucs, gw_hucs)
    _add_landmarks(ax)

    ax.set_title(
        "Smackover in-place lithium vs. population & CWS drinking water\n"
        "HUC12 impact tier (upstream limited to ≤ "
        f"{UPSTREAM_NEAR_K} hops from a surface intake)",
        fontsize=12,
    )
    ax.set_axis_off()

    legend_items = [
        Patch(facecolor=TIER_COLOR["high"], alpha=0.65, label="High impact"),
        Patch(facecolor=TIER_COLOR["low"], alpha=0.65, label="Low impact"),
        Patch(edgecolor="#1f77b4", facecolor="none", linewidth=1.1, label="HUC12 w/ CWS surface intake"),
        Patch(edgecolor="#ff7f0e", facecolor="none", linewidth=0.6, label="HUC12 w/ CWS groundwater well"),
        Patch(edgecolor="#555555", facecolor="none", linestyle="--", label="Smackover Li footprint (dissolved)"),
        Patch(edgecolor="#bbbbbb", facecolor="none", label="Study-area HUC12s"),
        Patch(edgecolor="black", facecolor="none", linewidth=1.0, label="State boundaries"),
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=8, frameon=True)

    ax.text(
        0.99, 0.01,
        "Li: USGS Knierim et al. 2024 | HUC12: USGS WBD | Intakes: EPA SDWIS 2022Q2 / SDWA 2024Q4"
        " | Population: ORNL LandScan 2024",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5, color="#444",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_tonnage_map(df, huc12_study, study_area, states, sw_hucs, gw_hucs, out_path) -> None:
    fig, ax = plt.subplots(figsize=(10, 10))
    _base_context(ax, huc12_study, study_area, states)

    vals = df[TON_MAIN].to_numpy()
    edges = np.quantile(vals, [0, 0.2, 0.4, 0.6, 0.8, 1.0])
    edges[0] -= 1.0  # so the minimum value is included in the first bin
    labels = [f"{edges[i]:,.0f}–{edges[i+1]:,.0f} t" for i in range(5)]
    df = df.copy()
    df["_bin"] = pd.cut(df[TON_MAIN], bins=edges, labels=labels, include_lowest=True)

    cmap = plt.get_cmap("YlOrRd")
    colors = [cmap(x) for x in np.linspace(0.25, 0.95, 5)]
    for lab, color in zip(labels, colors):
        sub = df[df["_bin"] == lab]
        if len(sub):
            sub.plot(ax=ax, color=color, edgecolor="white", linewidth=0.2, zorder=3)

    _intake_overlays(ax, huc12_study, sw_hucs, gw_hucs)
    _add_landmarks(ax)

    ax.set_title(
        "In-place lithium tonnage by HUC12 (p50 grade, 20% porosity)\n"
        "Quantile bins, display only",
        fontsize=12,
    )
    ax.set_axis_off()

    legend_items = [Patch(facecolor=c, label=lab) for lab, c in zip(labels, colors)]
    legend_items += [
        Patch(edgecolor="#1f77b4", facecolor="none", linewidth=1.1, label="HUC12 w/ CWS surface intake"),
        Patch(edgecolor="#ff7f0e", facecolor="none", linewidth=0.6, label="HUC12 w/ CWS groundwater well"),
        Patch(edgecolor="#555555", facecolor="none", linestyle="--", label="Smackover Li footprint (dissolved)"),
        Patch(edgecolor="black", facecolor="none", linewidth=1.0, label="State boundaries"),
    ]
    ax.legend(handles=legend_items, loc="lower left", fontsize=7.5, frameon=True,
               title="li_ton_p50_por20 (quantile bins)", title_fontsize=8)

    ax.text(
        0.99, 0.01,
        "Li: USGS Knierim et al. 2024 | HUC12: USGS WBD | Intakes: EPA SDWIS 2022Q2 / SDWA 2024Q4"
        " | Population: ORNL LandScan 2024",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5, color="#444",
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def make_tonnage_bar(headline: pd.DataFrame, out_path) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 5))
    tiers = list(headline.index)
    p50 = headline["li_ton_p50_por20"].to_numpy() / 1e6
    p5 = headline["li_ton_p5_por20"].to_numpy() / 1e6
    p95 = headline["li_ton_p95_por20"].to_numpy() / 1e6
    yerr = np.vstack([p50 - p5, p95 - p50])
    colors = [TIER_COLOR[t] for t in tiers]

    ax.bar(tiers, p50, color=colors, alpha=0.75, width=0.55, zorder=2)
    ax.errorbar(tiers, p50, yerr=yerr, fmt="none", ecolor="black",
                capsize=6, linewidth=1.3, zorder=3)
    ax.set_ylim(0, float(np.max(p95)) * 1.35)
    for i, (t, v) in enumerate(zip(tiers, p50)):
        ax.text(i, v + yerr[1, i] + 0.15, f"{v:.2f} Mt\n({headline.loc[t,'pct_of_ton_p50']:.1f}%)",
                 ha="center", va="bottom", fontsize=9)

    ax.set_ylabel("In-place Li, metric tons (millions)")
    ax.set_title("Median in-place lithium by impact tier\n(whiskers: p5–p95 grade band)", fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
def main() -> None:
    df = gpd.read_file(OUT / "huc12_lithium_impact.gpkg", layer="huc12_impact")
    assert_crs(df, CRS_ALBERS, "huc12_impact")
    df["HUC12"] = df["HUC12"].map(zpad_huc12)

    print("=== 07_summary_and_map ===")

    pop_lookup = pd.read_csv(
        OUT_INT / "cws_pwsid_population.csv"
    ).set_index("PWSID")["POPULATION_SERVED_COUNT"]
    headline = headline_table(df, pop_lookup)
    print("\nHeadline table (impact tier):")
    print(headline.round(2).to_string())

    hi = headline.loc["high"] if "high" in headline.index else None
    lo = headline.loc["low"] if "low" in headline.index else None
    if hi is not None and lo is not None:
        headline_sentence = (
            f"Of the **{headline['li_ton_p50_por20'].sum()/1e6:.2f} Mt** of median in-place "
            "lithium predicted in Smackover brines (p50 grade, 20% porosity), "
            f"**{hi['li_ton_p50_por20']/1e6:.2f} Mt ({hi['pct_of_ton_p50']:.1f}%)** lies beneath "
            "HUC12s that are populated, contain a community-water-system intake, or drain "
            f"(within {UPSTREAM_NEAR_K} hops) to one — leaving "
            f"**{lo['li_ton_p50_por20']/1e6:.2f} Mt ({lo['pct_of_ton_p50']:.1f}%)** in "
            "lower-impact watersheds."
        )
    else:
        headline_sentence = "Both impact tiers must be non-empty to state the headline."
    print("\n" + headline_sentence.replace("**", ""))

    por_inv = porosity_invariance(df)
    print("\nPorosity invariance check (% of tonnage in 'high' tier, p50 grade):")
    print(por_inv.to_string(index=False))
    print("  (asserted identical across 10/20/30% porosity — porosity cancels out of the "
          "tier percentage because the tier is defined independently of tonnage.)")

    gband = grade_band(df)
    print("\n% of tonnage in 'high' tier by grade percentile (20% porosity):")
    print(gband.to_string(index=False))

    reasons = reason_decomposition(df)
    print("\nDecomposition by impact_reasons:")
    print(reasons.round(2).to_string())

    pop_sens = pop_sensitivity(df)
    print("\nPopulation-threshold sensitivity:")
    print(pop_sens.round(2).to_string(index=False))

    steps_sens = steps_sensitivity(df)
    print("\nsteps_to_sw_intake sensitivity (k hops; headline marked):")
    print(steps_sens.round(2).to_string(index=False))

    top = top15(df)
    print("\nTop 15 HUC12s by li_ton_p50_por20:")
    print(top.round(1).to_string(index=False))

    # --- write CSV + MD ------------------------------------------------------------
    headline.to_csv(OUT / "impact_summary.csv")

    md = []
    md.append("# Smackover lithium — impact summary\n")
    md.append(headline_sentence + "\n")
    md.append("## Headline table (by impact tier)\n")
    md.append(headline.round(2).to_markdown() + "\n")
    md.append(
        "`cws_pop_served` above is the population served by the **distinct** CWS "
        "(de-duplicated by PWSID) with a facility in any HUC12 of that tier — a system "
        "with facilities in several same-tier HUC12s is counted once, not once per "
        "HUC12. Per-HUC12 `cws_pop_served` values elsewhere (the gpkg/csv and the "
        "concentration bivariate maps) are still per-system totals repeated on every "
        "HUC12 that system touches, and must not be summed across HUC12s directly.\n"
    )
    md.append("## Porosity invariance (% of tonnage in 'high' tier, p50 grade)\n")
    md.append(por_inv.round(3).to_markdown(index=False) + "\n")
    md.append("## Grade-percentile band (% of tonnage in 'high' tier, 20% porosity)\n")
    md.append(gband.round(2).to_markdown(index=False) + "\n")
    md.append("## Decomposition by impact_reasons\n")
    md.append(reasons.round(2).to_markdown() + "\n")
    md.append("## Population-threshold sensitivity\n")
    md.append(pop_sens.round(2).to_markdown(index=False) + "\n")
    md.append(f"## Upstream-distance sensitivity (headline: k ≤ {UPSTREAM_NEAR_K} hops)\n")
    md.append(steps_sens.round(2).to_markdown(index=False) + "\n")
    md.append("## Top 15 HUC12s by median in-place lithium\n")
    md.append(top.round(1).to_markdown(index=False) + "\n")
    (OUT / "impact_summary.md").write_text("\n".join(md), encoding="utf-8")

    # --- figures ---------------------------------------------------------------------
    huc12_study = gpd.read_file(OUT_INT / "huc12_study.gpkg", layer="huc12")
    huc12_study["HUC12"] = huc12_study["HUC12"].map(zpad_huc12)
    study_area = gpd.read_file(OUT_INT / "study_area.gpkg", layer="domains")
    states = _load_states()

    sw_csv = pd.read_csv(OUT / "intake_hucs_sw.csv", dtype={"HUC12": str})
    gw_csv = pd.read_csv(OUT / "intake_hucs_gw.csv", dtype={"HUC12": str})
    sw_hucs = set(sw_csv["HUC12"].map(zpad_huc12))
    gw_hucs = set(gw_csv["HUC12"].map(zpad_huc12))

    make_impact_map(df, huc12_study, study_area, states, sw_hucs, gw_hucs, OUT / "impact_map.png")
    make_tonnage_map(df, huc12_study, study_area, states, sw_hucs, gw_hucs, OUT / "tonnage_map.png")
    make_tonnage_bar(headline, OUT / "tonnage_by_tier.png")

    print(f"\nWrote {OUT/'impact_summary.csv'}, {OUT/'impact_summary.md'}, "
          f"{OUT/'impact_map.png'}, {OUT/'tonnage_map.png'}, {OUT/'tonnage_by_tier.png'}")


if __name__ == "__main__":
    main()
