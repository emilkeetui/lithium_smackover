"""09_violation_utility_tables.py — two paper-ready tables for the
bivariate_p50_mean.png HUC12/utility sample.

Table 1 (violation comparison): MR / MCL / TT violation incidence in the last
5 years of SDWIS enforcement data, comparing the 46 groundwater-primary CWS
that drive the bivariate maps' population axis (pws_ids_gw, GW_SW_CODE=='GW',
Arkansas primacy only) against the other 622 active Arkansas CWS. Styled on
Z:/ek559/mining_wq/output/sum/syr2_mr_comparison.tex.

Table 2 (descriptive statistics): Mean/Median/Min/Max of n_cells, HUC12 area,
and p5/p50/p95 mean-of-cells brine Li concentration across the 141-HUC12
sample in outputs/huc12_li_concentration.csv. Styled on
Z:/ek559/mining_wq/output/sum/mining_exposure_covariates_k2.tex.

    outputs/tables/huc12_utility_violation_comparison.tex / .csv
    outputs/tables/huc12_sample_covariates.tex / .csv
"""
from __future__ import annotations

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from scipy import stats

from utils import (
    OUT,
    SDWA_SYSTEMS_CSV,
    SDWA_VIOLATIONS_PARQUET,
    VIOLATION_CATEGORIES,
    VIOLATION_WINDOW_YEARS,
    parse_pwsids,
)

TABLES = OUT / "tables"
CONC_CSV = OUT / "huc12_li_concentration.csv"

EXPECTED_GROUP_A_N = 46


def stars(p: float) -> str:
    if p < 0.01:
        return "$^{***}$"
    if p < 0.05:
        return "$^{**}$"
    if p < 0.1:
        return "$^{*}$"
    return ""


def fmt_pct(x: float) -> str:
    return f"{100 * x:.1f}\\%"


def fmt_diff_pct(a: float, b: float, p: float) -> str:
    return f"{100 * (a - b):.1f}\\%{stars(p)}"


def fmt_num(x: float) -> str:
    return f"{x:.2f}"


def fmt_diff_num(a: float, b: float, p: float) -> str:
    return f"{a - b:.2f}{stars(p)}"


def ttest(a: pd.Series, b: pd.Series) -> float:
    return float(stats.ttest_ind(a, b, equal_var=False, nan_policy="omit").pvalue)


# ---------------------------------------------------------------------------
def build_violation_table() -> tuple[pd.DataFrame, str]:
    conc = pd.read_csv(CONC_CSV, dtype={"HUC12": str})
    raw_pwsids = parse_pwsids(conc["pws_ids_gw"])

    sys_df = pd.read_csv(
        SDWA_SYSTEMS_CSV,
        dtype={"PWSID": str},
        usecols=["PWSID", "PRIMACY_AGENCY_CODE", "PWS_TYPE_CODE", "PWS_ACTIVITY_CODE", "GW_SW_CODE"],
        low_memory=False,
    )
    ar_active = sys_df[
        (sys_df["PRIMACY_AGENCY_CODE"] == "AR")
        & (sys_df["PWS_TYPE_CODE"] == "CWS")
        & (sys_df["PWS_ACTIVITY_CODE"] == "A")
    ]
    universe = set(ar_active["PWSID"])
    true_gw = set(ar_active.loc[ar_active["GW_SW_CODE"] == "GW", "PWSID"])

    group_a = raw_pwsids & true_gw & universe
    group_b = universe - group_a
    n_dropped = len(raw_pwsids) - len(group_a)
    print(f"Raw pws_ids_gw PWSIDs: {len(raw_pwsids)}   AR active CWS universe: {len(universe)}")
    print(f"Group A (map GW utilities, AR active CWS, GW_SW_CODE=='GW'): {len(group_a)}   "
          f"({n_dropped} of the raw PWSIDs excluded: non-AR primacy or not true-GW)")
    print(f"Group B (rest of Arkansas CWS): {len(group_b)}")
    assert len(group_a) == EXPECTED_GROUP_A_N, (
        f"Group A = {len(group_a)}, expected {EXPECTED_GROUP_A_N} — sample definition drifted, "
        f"check pws_ids_gw / SDWA join upstream"
    )

    vio = pd.read_parquet(
        SDWA_VIOLATIONS_PARQUET,
        columns=["PWSID", "VIOLATION_CATEGORY_CODE", "COMPL_PER_BEGIN_DATE"],
    )
    vio = vio[
        vio["PWSID"].isin(universe) & vio["VIOLATION_CATEGORY_CODE"].isin(VIOLATION_CATEGORIES)
    ].copy()
    vio["date"] = pd.to_datetime(vio["COMPL_PER_BEGIN_DATE"], format="%m/%d/%Y", errors="coerce")
    assert vio["date"].isna().sum() == 0, "unparsed COMPL_PER_BEGIN_DATE values in the universe subset"

    window_end = vio["date"].max()
    window_start = window_end - pd.DateOffset(years=VIOLATION_WINDOW_YEARS)
    win = vio[(vio["date"] > window_start) & (vio["date"] <= window_end)]
    print(f"Violation window: ({window_start.date()}, {window_end.date()}]   "
          f"rows in window: {len(win):,}   distinct PWSID: {win['PWSID'].nunique()}")

    outcomes = pd.DataFrame(index=sorted(universe))
    outcomes.index.name = "PWSID"
    for cat in VIOLATION_CATEGORIES:
        counts = win[win["VIOLATION_CATEGORY_CODE"] == cat].groupby("PWSID").size()
        outcomes[f"n_{cat}"] = counts.reindex(outcomes.index).fillna(0).astype(int)
        outcomes[f"ever_{cat}"] = (outcomes[f"n_{cat}"] > 0).astype(int)
    outcomes["vio_indicator_sum"] = outcomes[[f"ever_{c}" for c in VIOLATION_CATEGORIES]].sum(axis=1)

    a = outcomes.loc[sorted(group_a)]
    b = outcomes.loc[sorted(group_b)]

    rows = []
    for cat in VIOLATION_CATEGORIES:
        col = f"ever_{cat}"
        pa, pb = a[col].mean(), b[col].mean()
        p = ttest(a[col], b[col])
        rows.append({
            "metric": f"Ever {cat} violation", "group_a": pa, "group_b": pb,
            "diff": pa - pb, "p_value": p, "kind": "pct",
        })
    col = "vio_indicator_sum"
    pa, pb = a[col].mean(), b[col].mean()
    p = ttest(a[col], b[col])
    rows.append({
        "metric": "Mean violations (indicator sum, 0-3)", "group_a": pa, "group_b": pb,
        "diff": pa - pb, "p_value": p, "kind": "num",
    })
    table = pd.DataFrame(rows)

    body_lines = []
    for i, r in table.iterrows():
        if r["kind"] == "pct":
            line = (f"{r['metric']} & {fmt_pct(r['group_a'])} & {fmt_pct(r['group_b'])} & "
                    f"{fmt_diff_pct(r['group_a'], r['group_b'], r['p_value'])} & "
                    f"{r['p_value']:.3f} \\\\")
        else:
            line = (f"{r['metric']} & {fmt_num(r['group_a'])} & {fmt_num(r['group_b'])} & "
                    f"{fmt_diff_num(r['group_a'], r['group_b'], r['p_value'])} & "
                    f"{r['p_value']:.3f} \\\\")
        body_lines.append(line)
    # Mean-violations row sits below its own \hline, mirroring the reference table.
    body = "\n".join(body_lines[:-1]) + "\n\\hline\n" + body_lines[-1]

    tex = f"""\\begin{{table}}[htbp]
\\centering
\\caption{{MR, MCL, and TT violation incidence, last 5 years, groundwater utilities in the Smackover impact sample vs. rest of Arkansas}}
\\label{{tab:huc12_utility_violation_comparison}}
\\begin{{adjustbox}}{{max width=\\textwidth}}
\\begin{{tabular}}{{lrrrr}}
\\toprule
 & \\multicolumn{{2}}{{c}}{{Utility in bivariate\\_p50\\_mean.png sample}} & & \\\\
\\cmidrule(lr){{2-3}}
 & Yes & No & Diff. & $p$-value \\\\
 & \\multicolumn{{1}}{{c}}{{(1)}} & \\multicolumn{{1}}{{c}}{{(2)}} & \\multicolumn{{1}}{{c}}{{(3)}} & \\multicolumn{{1}}{{c}}{{(4)}} \\\\
\\hline
{body}
\\bottomrule
\\end{{tabular}}
\\end{{adjustbox}}
\\begin{{minipage}}{{\\linewidth}}
\\vspace{{4pt}}
\\footnotesize
\\raggedright
\\textit{{Notes:}} Sample: active Arkansas community water systems (CWS; SDWA\\_PUB\\_WATER\\_SYSTEMS.csv, 2024Q4, PRIMACY\\_AGENCY\\_CODE=='AR', PWS\\_TYPE\\_CODE=='CWS', PWS\\_ACTIVITY\\_CODE=='A', N=668). \\textit{{Yes}} = the {len(group_a)} groundwater-primary (GW\\_SW\\_CODE=='GW') CWS with a well in a Smackover-impact HUC12, i.e. the utilities whose population served drives the map \\texttt{{outputs/bivariate/bivariate\\_p50\\_mean.png}} ({len(raw_pwsids)} raw PWSIDs listed in \\texttt{{pws\\_ids\\_gw}} across the 141 analysis HUC12s; {n_dropped} excluded here as Louisiana/Texas systems or non-true-groundwater sources). \\textit{{No}} = the remaining {len(group_b)} active Arkansas CWS. MR violation: monitoring and reporting violation. MCL violation: maximum contaminant level violation. TT violation: treatment technique violation. Violation window: ({window_start.date()}, {window_end.date()}], the 5 years ending at the latest COMPL\\_PER\\_BEGIN\\_DATE among MR/MCL/TT violations for active Arkansas CWS (SDWA\\_VIOLATIONS\\_ENFORCEMENT.parquet, 2024Q4). A system with no violation record in the window is coded compliant (0) for that category. Mean violations (indicator sum, 0--3): sum of the three ever-violation indicators (MR, MCL, TT) per utility. Diff.\\ stars from two-sample Welch $t$-test: *** $p<0.01$, ** $p<0.05$, * $p<0.1$.
\\end{{minipage}}
\\end{{table}}
"""
    csv_out = table.copy()
    csv_out["n_group_a"] = len(group_a)
    csv_out["n_group_b"] = len(group_b)
    csv_out["window_start"] = window_start.date().isoformat()
    csv_out["window_end"] = window_end.date().isoformat()
    return csv_out, tex


# ---------------------------------------------------------------------------
def build_covariate_table() -> tuple[pd.DataFrame, str]:
    conc = pd.read_csv(CONC_CSV, dtype={"HUC12": str})
    print(f"\nHUC12 sample rows: {len(conc)}")

    specs = [
        ("n_cells", "Number of raster cells overlapping HUC12"),
        ("huc12_area_km2", "HUC12 area (km$^2$)"),
        ("Li_p5_mean_mgL", "Predicted brine Li, p5 (mg/L, mean of cells)"),
        ("Li_p50_mean_mgL", "Predicted brine Li, p50 (mg/L, mean of cells)"),
        ("Li_p95_mean_mgL", "Predicted brine Li, p95 (mg/L, mean of cells)"),
    ]
    rows = []
    for col, label in specs:
        v = conc[col]
        assert v.isna().sum() == 0, f"{col} has NaNs in the 141-HUC12 sample"
        rows.append({
            "variable": label, "column": col,
            "mean": v.mean(), "median": v.median(), "min": v.min(), "max": v.max(),
        })
    table = pd.DataFrame(rows)

    body = "\n".join(
        f"{r['variable']} & {r['mean']:.2f} & {r['median']:.2f} & {r['min']:.2f} & {r['max']:.2f} \\\\"
        for _, r in table.iterrows()
    )
    tex = f"""\\begin{{table}}[htbp]
\\raggedright
\\caption{{Descriptive statistics, Smackover HUC12 impact sample}}
\\label{{tab:huc12_sample_covariates}}
\\small
\\begin{{tabular}}{{>{{\\raggedright\\arraybackslash}}p{{6cm}} *{{4}}{{>{{\\centering\\arraybackslash}}p{{1.6cm}}}}}}
\\toprule
\\textbf{{Variable}} & \\textbf{{Mean}} & \\textbf{{Median}} & \\textbf{{Min}} & \\textbf{{Max}} \\\\
\\hline
{body}
\\bottomrule
\\end{{tabular}}
\\begin{{minipage}}{{\\linewidth}}
\\vspace{{4pt}}
\\footnotesize
\\raggedright
\\textit{{Notes:}} Sample: the {len(conc)} HUC12 watersheds intersecting the predicted Smackover Formation brine lithium footprint (\\texttt{{outputs/huc12\\_li\\_concentration.csv}}). Number of raster cells: count of valid 2\\,km USGS model-domain cells overlapping each HUC12. Predicted brine Li concentration (p5/p50/p95, mg/L) is the mean across all valid cells overlapping the HUC12, from the USGS Knierim et al. (2024) percentile rasters.
\\end{{minipage}}
\\end{{table}}
"""
    return table, tex


def main() -> None:
    TABLES.mkdir(exist_ok=True)

    print("=== 09_violation_utility_tables ===")
    print("\n--- Table 1: violation comparison ---")
    vio_csv, vio_tex = build_violation_table()
    vio_csv.to_csv(TABLES / "huc12_utility_violation_comparison.csv", index=False)
    (TABLES / "huc12_utility_violation_comparison.tex").write_text(vio_tex, encoding="utf-8")

    print("\n--- Table 2: HUC12 descriptive statistics ---")
    cov_csv, cov_tex = build_covariate_table()
    cov_csv.to_csv(TABLES / "huc12_sample_covariates.csv", index=False)
    (TABLES / "huc12_sample_covariates.tex").write_text(cov_tex, encoding="utf-8")
    print(cov_csv.to_string(index=False))

    print(f"\nWrote {TABLES / 'huc12_utility_violation_comparison.tex'} / .csv")
    print(f"Wrote {TABLES / 'huc12_sample_covariates.tex'} / .csv")


if __name__ == "__main__":
    main()
