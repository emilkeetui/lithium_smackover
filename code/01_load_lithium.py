"""01_load_lithium.py — Build lithium cell polygons with in-place Li tonnage.

Ports sar_li/4_SARLi_estimate.py onto the model-domain fishnet, one polygon per
2 km raster cell, and asserts the per-cell tonnages sum to the published USGS
domain totals. Writes:

    outputs/intermediate/lithium_cells.gpkg   (2,524 valid cells, tonnage + attributes)
    outputs/intermediate/study_area.gpkg      (those cells dissolved = Smackover footprint)
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely import make_valid

from utils import (
    CELL_M,
    CRS_ALBERS,
    GRADES,
    GRID_COLS,
    GRID_ROWS,
    GRID_SHP,
    H2OPROD_TIF,
    LI_P5_TIF,
    LI_P50_TIF,
    LI_P95_TIF,
    LI_PRED_TIF,
    LI_QUALUNC_TIF,
    LI_RNGP_TIF,
    MASK_TIF,
    OUT_INT,
    POROSITIES,
    RASTERSTACK_TXT,
    TONNAGE_TOLERANCE,
    USGS_TOTALS,
    WRATIO_TIF,
    assert_crs,
    ton_col,
    to_albers,
)


def _read(path) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(1)


def _verify_alignment(cells_albers: gpd.GeoDataFrame, p50: np.ndarray) -> None:
    """Assert fishnet row i corresponds to raster flat index i (row-major).

    Sampling every cell centroid is cheap at 2,880 cells and is the only thing
    standing between us and a silently transposed resource map.
    """
    cent = np.array([(pt.x, pt.y) for pt in cells_albers.geometry.centroid])
    with rasterio.open(LI_P50_TIF) as src:
        sampled = np.array([v[0] for v in src.sample(cent)], dtype="float64")
    flat = p50.ravel().astype("float64")
    if not np.array_equal(sampled, flat):
        bad = int(np.count_nonzero(sampled != flat))
        raise AssertionError(
            f"Fishnet/raster misalignment: {bad} of {flat.size} cells disagree between "
            "centroid-sampled and row-major-flattened p50 values."
        )
    print(f"alignment: verified row-major for all {flat.size} cells (centroid sample == flat index)")


def main() -> None:
    # --- rasters, flat and row-major -------------------------------------------------
    mask = _read(MASK_TIF)
    if mask.shape != (GRID_ROWS, GRID_COLS):
        raise AssertionError(f"mask shape {mask.shape} != ({GRID_ROWS}, {GRID_COLS})")
    grade = {"p5": _read(LI_P5_TIF), "p50": _read(LI_P50_TIF), "p95": _read(LI_P95_TIF)}
    preds = _read(LI_PRED_TIF)
    qualunc = _read(LI_QUALUNC_TIF)
    rngp = _read(LI_RNGP_TIF)
    wratio = _read(WRATIO_TIF)
    prod = _read(H2OPROD_TIF)

    # Reynolds-oolite thickness (m) lives in the explanatory-variable table, not a tif.
    evdf = pd.read_csv(RASTERSTACK_TXT)
    thick = evdf["smackover_thick"].to_numpy().reshape(GRID_ROWS, GRID_COLS)

    valid = mask == 1

    # --- fishnet ---------------------------------------------------------------------
    cells = to_albers(gpd.read_file(GRID_SHP))
    if len(cells) != mask.size:
        raise AssertionError(f"fishnet has {len(cells)} polygons, raster has {mask.size} cells")
    cells["geometry"] = cells.geometry.apply(make_valid)
    _verify_alignment(cells, grade["p50"])

    # --- per-cell in-place lithium mass (port of 4_SARLi_estimate.py) ---------------
    # vol_ft3 = thickness_ft * cell_ft * cell_ft ; 1 m = 3.28 ft, 1 ft^3 = 28.3168 L
    pore_L_unit = (thick * 3.28) * (CELL_M * 3.28) * (CELL_M * 3.28) * 28.3168
    tonnage = {}
    for por in POROSITIES:
        brine_L = np.where(valid, pore_L_unit * (por / 100.0) * wratio, np.nan)
        for g in GRADES:
            li_mgL = np.where(valid, grade[g], np.nan)
            tonnage[(g, por)] = brine_L * li_mgL / 1e9  # mg/L * L / 1e9 = metric tons

    # --- validation against the published domain totals ------------------------------
    # The USGS script rounds tons to whole numbers per cell before summing; we do not,
    # so compare our unrounded sums against theirs within 0.1 %.
    print("\nvalidation vs SAR_smackover_Liestimate.csv (metric tons of in-place Li):")
    worst = 0.0
    for (por, g), published in sorted(USGS_TOTALS.items()):
        ours = float(np.nansum(tonnage[(g, por)]))
        rel = abs(ours - published) / published
        worst = max(worst, rel)
        print(f"  porosity {por:2d}%  {g:>3s}:  ours {ours:14,.0f}   published {published:14,.0f}   rel {rel:.2e}")
        if rel > TONNAGE_TOLERANCE:
            raise AssertionError(
                f"Tonnage mismatch at porosity {por}%, grade {g}: {ours:,.0f} vs {published:,.0f} "
                f"({rel:.3%}). Check raster/fishnet alignment and unit conversions."
            )
    print(f"  max relative deviation: {worst:.2e}  (tolerance {TONNAGE_TOLERANCE:.1%})")

    # --- assemble the cell table ------------------------------------------------------
    flat = lambda a: a.ravel()  # noqa: E731
    cells["cell_id"] = [f"C{i:05d}" for i in range(len(cells))]
    cells["row"] = np.repeat(np.arange(GRID_ROWS), GRID_COLS)
    cells["col"] = np.tile(np.arange(GRID_COLS), GRID_ROWS)
    cells["valid"] = flat(valid)
    for (g, por), arr in tonnage.items():
        cells[ton_col(g, por)] = flat(arr)
    cells["Li_mgL"] = flat(np.where(valid, preds, np.nan))
    cells["Li_p50_mgL"] = flat(np.where(valid, grade["p50"], np.nan))
    cells["Li_p5_mgL"] = flat(np.where(valid, grade["p5"], np.nan))
    cells["Li_p95_mgL"] = flat(np.where(valid, grade["p95"], np.nan))
    cells["qualunc"] = flat(np.where(valid, qualunc, np.nan))
    cells["rngp"] = flat(np.where(valid, rngp, np.nan))
    cells["thick_m"] = flat(np.where(valid, thick, np.nan))
    cells["water_ratio"] = flat(np.where(valid, wratio, np.nan))
    cells["h2o_prod_bbl_2022"] = flat(np.where(valid, prod, np.nan))
    cells["area_km2"] = cells.geometry.area / 1e6

    cells = cells[cells["valid"]].drop(columns=["valid", "Id", "gridcode"]).reset_index(drop=True)
    cells = gpd.GeoDataFrame(cells, geometry="geometry", crs=CRS_ALBERS)
    assert_crs(cells, CRS_ALBERS, "lithium_cells")

    out_cells = OUT_INT / "lithium_cells.gpkg"
    cells.to_file(out_cells, layer="cells", driver="GPKG")

    # --- dissolved footprint = study area ---------------------------------------------
    study = gpd.GeoDataFrame(
        {"name": ["Smackover Reynolds oolite model domain (valid cells)"]},
        geometry=[cells.geometry.union_all()],
        crs=CRS_ALBERS,
    )
    study["geometry"] = study.geometry.apply(make_valid)
    out_study = OUT_INT / "study_area.gpkg"
    study.to_file(out_study, layer="domains", driver="GPKG")

    # --- report -------------------------------------------------------------------------
    main_col = ton_col("p50", 20)
    print("\n=== 01_load_lithium ===")
    print(f"valid cells: {len(cells):,} of {mask.size:,}   footprint area: {cells['area_km2'].sum():,.0f} km2")
    print(f"cell area: min {cells['area_km2'].min():.3f}  max {cells['area_km2'].max():.3f} km2")
    print(f"in-place Li (p50, 20% porosity): {cells[main_col].sum():,.0f} t "
          f"[p5 {cells[ton_col('p5', 20)].sum():,.0f} – p95 {cells[ton_col('p95', 20)].sum():,.0f}]")
    print(f"per-cell tons (p50/20%): min {cells[main_col].min():,.0f}  median "
          f"{cells[main_col].median():,.0f}  max {cells[main_col].max():,.0f}")
    print(f"grade Li_mgL: min {cells['Li_mgL'].min():.0f}  mean {cells['Li_mgL'].mean():.0f}  "
          f"max {cells['Li_mgL'].max():.0f}")
    print(f"thickness m: mean {cells['thick_m'].mean():.1f}  max {cells['thick_m'].max():.0f}")
    print("qualunc classes:", cells["qualunc"].value_counts().sort_index().to_dict())
    print(f"study area (dissolved): {study.geometry.area.iloc[0] / 1e6:,.0f} km2")
    print(f"Wrote {out_cells} and {out_study}")


if __name__ == "__main__":
    main()
