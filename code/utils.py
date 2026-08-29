"""Shared constants and helpers for the Smackover lithium-vs-population/CWS pipeline.

Import this in every pipeline script. Do not redefine CRS strings or thresholds
elsewhere — change them here and the whole pipeline picks them up.

Unit of analysis is the HUC12. The 2 km USGS model cells are an intermediate used
only to carry in-place lithium tonnage onto HUC12s without losing mass.

Run everything with the project venv, by full path:
    "Z:/ek559/nys_algal_bloom/NYS algal bloom/code2/Scripts/python.exe" code/01_load_lithium.py

See notes/implementation_plan.md for context.
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from pyproj import CRS as _PyCRS

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT
OUT = ROOT / "outputs"
OUT_INT = OUT / "intermediate"
OUT.mkdir(exist_ok=True)
OUT_INT.mkdir(exist_ok=True)

# --- USGS Smackover model archive (Knierim et al., 2024; doi:10.5066/P9QPRYZN) ---
SAR = DATA / "sar_li"
GRID_SHP = SAR / "grid" / "SAR_modeldomain_4269.shp"
MASK_TIF = SAR / "grid" / "SAR_modeldomain_mask.tif"
LI_P5_TIF = SAR / "output" / "smackover_Li_uncertainty_p5.tif"
LI_P50_TIF = SAR / "output" / "smackover_Li_uncertainty_p50.tif"
LI_P95_TIF = SAR / "output" / "smackover_Li_uncertainty_p95.tif"
LI_PRED_TIF = SAR / "output" / "smackover_Li_preds.tif"
LI_QUALUNC_TIF = SAR / "output" / "smackover_Li_uncertainty_qualunc.tif"
LI_RNGP_TIF = SAR / "output" / "smackover_Li_uncertainty_rngp.tif"
WRATIO_TIF = SAR / "input" / "brine" / "smackover_H2Oratios.tif"
H2OPROD_TIF = SAR / "input" / "brine" / "smackover_H2Oprod_2022.tif"
RASTERSTACK_TXT = SAR / "input" / "exvars" / "SAR_modeldomain_rasterstack.txt"
LIESTIMATE_CSV = SAR / "output" / "SAR_smackover_Liestimate.csv"

# --- Supporting datasets ---
WBD_HUC12 = DATA / "WBD_HUC12_CONUS_pulled10262020" / "WBD_HUC12_CONUS_pulled10262020.shp"
CWS_XLSX = DATA / "cws_intake_hucs" / "PWS_Loctations_HUC12_A_I_2022Q2.xlsx"
# EPA SDWA/ECHO bulk download (2024Q4) — supplies PWS_TYPE_CODE and POPULATION_SERVED_COUNT,
# which the 2022Q2 HUC12 crosswalk lacks. Joined on PWSID; see notes/implementation_plan.md §4.
SDWA_SYSTEMS_CSV = Path(r"Z:/ek559/sdwa_violations/SDWA_latest_downloads/SDWA_PUB_WATER_SYSTEMS.csv")
LANDSCAN_TIF = DATA / "population_distribution" / "landscan-global-2024-assets" / "landscan-global-2024.tif"
# Natural Earth state/province boundaries, already on disk from the sibling project —
# used only for map context (07). No pygris / Census network fetch.
NE_STATES_SHP = Path(
    r"Z:/ek559/Lithium_mining_US_northeast/temp_ne_data/ne_10m_admin_1_states_provinces.shp"
)

# ---------------------------------------------------------------------------
# CRSs
# ---------------------------------------------------------------------------
# The USGS rasters' native CRS: USA Contiguous Albers Equal Area Conic on the WGS84
# datum, metres, 2,000 m cells (see sar_li/modelgeoref.txt). Equal-area, so area and
# density math is honest. Functionally ESRI:102039 but for the WGS84-vs-NAD83 datum;
# we use the literal raster WKT so the raster<->vector join is exact.
CRS_ALBERS = (
    'PROJCS["Albers_Conic_Equal_Area",'
    'GEOGCS["WGS 84",DATUM["WGS_1984",'
    'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],'
    'AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0],'
    'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],'
    'PROJECTION["Albers_Conic_Equal_Area"],'
    'PARAMETER["latitude_of_center",23],PARAMETER["longitude_of_center",-96],'
    'PARAMETER["standard_parallel_1",29.5],PARAMETER["standard_parallel_2",45.5],'
    'PARAMETER["false_easting",0],PARAMETER["false_northing",0],'
    'UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH]]'
)

# LandScan native CRS — geographic, WGS84. NEVER reproject the LandScan raster.
CRS_WGS84 = "EPSG:4326"

# ---------------------------------------------------------------------------
# Model-grid geometry (sar_li/modelgeoref.txt)
# ---------------------------------------------------------------------------
GRID_ROWS = 32
GRID_COLS = 90
CELL_M = 2000.0
NODATA_SENTINEL = -99.0  # value used in the USGS prediction rasters outside the domain

# ---------------------------------------------------------------------------
# Pipeline knobs (change here, not in scripts)
# ---------------------------------------------------------------------------
# Porosity (percent) used for the headline tonnage; 10/30 carried as a sensitivity band.
# Porosity scales every cell identically, so the high-vs-low PERCENTAGE is invariant to it.
POROSITY_DEFAULT = 20
POROSITIES = (10, 20, 30)
GRADES = ("p5", "p50", "p95")

# Distance (metres) to buffer the study area when clipping the national HUC12 layer.
STUDY_BUFFER_M = 50_000

# A HUC12 is "high population" if EITHER threshold is met.
POP_COUNT_THRESHOLD = 10_000        # people per HUC12
POP_DENSITY_THRESHOLD = 100.0       # people per km^2 per HUC12
# Sensitivity grid reported alongside the default (count, density).
POP_SENSITIVITY = ((5_000, 50.0), (10_000, 100.0), (20_000, 200.0))

# WBD TOHUC special codes — terminal nodes in the flow graph.
TOHUC_SINKS = {"OCEAN", "CLOSED BASIN", "CANADA", "MEXICO"}

# --- Upstream-of-CWS-surface-intake screen (see notes/implementation_plan.md §11) ---
# Run with no distance limit, "upstream of a CWS surface intake" flags 140/141 analysis
# HUC12s (100% of tonnage) — a near-universal condition in CONUS, so as a binary it
# carries no information. steps_to_sw_intake (HUC12 hops downstream to the nearest CWS
# surface intake; from 04_upstream_hucs.py) makes distance the discriminator instead.
# k=2 is the headline threshold (attenuation-and-dilution grounds; keeps the screen
# informative — median distance across the study area is 6 hops, max 30).
UPSTREAM_NEAR_K = 2
# Sensitivity row reported by 07_summary_and_map.py; None means "any distance" (the
# degenerate, unlimited-propagation screen kept only as a diagnostic, not the headline).
UPSTREAM_K_SENSITIVITY = (1, 2, 3, 5, 10, None)

# Primacy codes expected around the study area (sanity check only, never a filter).
STUDY_PRIMACY_CODES = {"AR", "LA", "TX", "MS", "OK", "MO", "TN"}

# Published USGS domain totals, metric tons of in-place Li (SAR_smackover_Liestimate.csv).
# 01_load_lithium.py asserts the per-cell sums reproduce these.
USGS_TOTALS = {
    (10, "p5"): 5_079_600.0, (10, "p50"): 5_659_046.0, (10, "p95"): 6_346_850.0,
    (20, "p5"): 10_159_251.0, (20, "p50"): 11_318_086.0, (20, "p95"): 12_693_716.0,
    (30, "p5"): 15_238_848.0, (30, "p50"): 16_977_164.0, (30, "p95"): 19_040_582.0,
}
TONNAGE_TOLERANCE = 0.001  # 0.1 % — the only slack is the USGS per-cell rounding


def ton_col(grade: str, porosity: int) -> str:
    """Column name for in-place Li tons at a given grade percentile and porosity."""
    return f"li_ton_{grade}_por{porosity}"


TON_MAIN = ton_col("p50", POROSITY_DEFAULT)   # the headline resource measure


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _crs_equal(a, b) -> bool:
    try:
        return _PyCRS.from_user_input(a) == _PyCRS.from_user_input(b)
    except Exception:
        return False


def to_albers(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject to the model's native Albers. No-op if already there."""
    if gdf.crs is not None and _crs_equal(gdf.crs, CRS_ALBERS):
        return gdf
    return gdf.to_crs(CRS_ALBERS)


def to_wgs(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject to EPSG:4326 (for LandScan extraction only). No-op if already there."""
    if gdf.crs is not None and _crs_equal(gdf.crs, CRS_WGS84):
        return gdf
    return gdf.to_crs(CRS_WGS84)


def assert_crs(gdf: gpd.GeoDataFrame, expected: str, name: str = "gdf") -> None:
    """Hard assertion that gdf is in the expected CRS (or an authority-equivalent)."""
    if gdf.crs is None:
        raise ValueError(f"{name}: CRS is None; expected {expected}")
    if not _crs_equal(gdf.crs, expected):
        raise ValueError(f"{name}: CRS is {gdf.crs}; expected {expected}")


def zpad_huc12(value) -> str:
    """Normalize a HUC12 to a zero-padded 12-character string.

    Excel coerces 12-digit codes that start with 0 to int and drops the leading
    zero. Always pass HUC_12 columns through this before joining or set-membership.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return ""
    if s.endswith(".0"):
        s = s[:-2]
    return s.zfill(12)


def norm_tohuc(value) -> str:
    """Normalize a TOHUC value: zero-pad numeric codes, leave sink tokens alone."""
    s = str(value).strip() if value is not None else ""
    return zpad_huc12(s) if s.isdigit() else s
