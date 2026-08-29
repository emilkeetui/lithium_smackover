"""03_intake_hucs.py — Derive I_sw and I_gw community-water-system HUC12 sets.

The 2022Q2 PWS<->HUC12 crosswalk has no PWS_TYPE_CODE, so on its own it cannot
distinguish a community water system from a campground's well. We join it on PWSID
to the EPA SDWA/ECHO system inventory (2024Q4) to keep only active CWS and to pick up
POPULATION_SERVED_COUNT — the project's only genuine water-use variable.

Writes outputs/intake_hucs_sw.csv and outputs/intake_hucs_gw.csv.
"""
from __future__ import annotations

import pandas as pd

from utils import (
    CWS_XLSX,
    OUT,
    OUT_INT,
    SDWA_SYSTEMS_CSV,
    STUDY_PRIMACY_CODES,
    zpad_huc12,
)

XLSX_COLS = [
    "PWSID", "FACILITY_ID", "HUC_12", "PRIMACY_AGENCY_CODE",
    "PWS_ACTIVITY_CODE", "FACILITY_ACTIVITY_CODE", "WATER_TYPE_CODE",
    "FACILITY_TYPE_CODE", "FACILITY_TYPE_NAME",
]
SDWA_COLS = [
    "PWSID", "PWS_NAME", "PWS_ACTIVITY_CODE", "PWS_TYPE_CODE", "GW_SW_CODE",
    "OWNER_TYPE_CODE", "POPULATION_SERVED_COUNT", "SERVICE_CONNECTIONS_COUNT",
    "CITY_NAME", "STATE_CODE",
]


def _load_facilities() -> pd.DataFrame:
    """Active PWS facilities with their HUC12, cached to CSV (the xlsx is slow)."""
    cache = OUT_INT / "pws_facilities_active.csv"
    if cache.exists():
        return pd.read_csv(cache, dtype=str)
    df = pd.read_excel(CWS_XLSX, usecols=XLSX_COLS, dtype=str)
    df = df[(df["PWS_ACTIVITY_CODE"] == "A") & (df["FACILITY_ACTIVITY_CODE"] == "A")].copy()
    df["HUC12"] = df["HUC_12"].map(zpad_huc12)
    df.to_csv(cache, index=False)
    return df


def _aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """One row per HUC12: facility/system counts, population served, PWSIDs.

    Population served is summed over *distinct systems* in the HUC12 — a system with
    five wells in one watershed must not be counted five times.
    """
    per_system = (
        df.drop_duplicates(subset=["HUC12", "PWSID"])
        .groupby("HUC12")
        .agg(
            n_systems=("PWSID", "nunique"),
            cws_pop_served=("POPULATION_SERVED_COUNT", "sum"),
            pws_ids=("PWSID", lambda s: ";".join(sorted(set(s)))),
        )
    )
    per_fac = df.groupby("HUC12").agg(n_facilities=("FACILITY_ID", "count"))
    out = per_fac.join(per_system).reset_index()
    return out.sort_values("cws_pop_served", ascending=False)


def main() -> None:
    fac = _load_facilities()
    systems = pd.read_csv(SDWA_SYSTEMS_CSV, usecols=SDWA_COLS, dtype=str, low_memory=False)
    systems["POPULATION_SERVED_COUNT"] = pd.to_numeric(
        systems["POPULATION_SERVED_COUNT"], errors="coerce"
    ).fillna(0.0)
    cws = systems[
        (systems["PWS_TYPE_CODE"] == "CWS") & (systems["PWS_ACTIVITY_CODE"] == "A")
    ].drop_duplicates(subset="PWSID")

    merged = fac.merge(
        cws[["PWSID", "PWS_NAME", "POPULATION_SERVED_COUNT", "OWNER_TYPE_CODE", "CITY_NAME"]],
        on="PWSID",
        how="inner",
    )

    print("=== 03_intake_hucs ===")
    print(f"active PWS facility rows (2022Q2 crosswalk): {len(fac):,}  "
          f"({fac['PWSID'].nunique():,} systems)")
    print(f"active CWS in SDWA inventory (2024Q4): {len(cws):,}")
    matched = fac["PWSID"].isin(set(systems["PWSID"])).mean()
    print(f"crosswalk PWSIDs found in the inventory: {matched:.1%}")
    print(f"facility rows surviving the CWS filter: {len(merged):,} "
          f"({len(merged)/max(len(fac),1):.1%})")
    present = set(merged["PRIMACY_AGENCY_CODE"].dropna())
    missing = STUDY_PRIMACY_CODES - present
    if missing:
        print(f"WARN: expected primacy codes absent from the CWS set: {sorted(missing)}")
    ar = merged[merged["PRIMACY_AGENCY_CODE"] == "AR"]
    print(f"Arkansas CWS facilities: {len(ar):,} in {ar['HUC12'].nunique():,} HUC12s "
          f"({ar['PWSID'].nunique():,} systems)")

    sw_agg = _aggregate(merged[merged["WATER_TYPE_CODE"] == "SW"])
    gw_agg = _aggregate(merged[merged["WATER_TYPE_CODE"] == "GW"])

    out_sw = OUT / "intake_hucs_sw.csv"
    out_gw = OUT / "intake_hucs_gw.csv"
    sw_agg.to_csv(out_sw, index=False)
    gw_agg.to_csv(out_gw, index=False)

    print(f"\n|I_sw| = {len(sw_agg):,} HUC12s   |I_gw| = {len(gw_agg):,} HUC12s")
    print("Top 5 SW intake HUC12s by CWS population served:")
    print(sw_agg.head(5)[["HUC12", "n_facilities", "n_systems", "cws_pop_served"]].to_string(index=False))
    print("Top 5 GW intake HUC12s by CWS population served:")
    print(gw_agg.head(5)[["HUC12", "n_facilities", "n_systems", "cws_pop_served"]].to_string(index=False))

    bad = int((sw_agg["HUC12"].str.len() != 12).sum() + (gw_agg["HUC12"].str.len() != 12).sum())
    if bad:
        raise AssertionError(f"{bad} aggregated rows have a HUC12 that is not 12 characters")
    if sw_agg.empty or gw_agg.empty:
        raise AssertionError("Empty intake set — the CWS join or the water-type split failed")
    print(f"Wrote {out_sw} and {out_gw}")


if __name__ == "__main__":
    main()
