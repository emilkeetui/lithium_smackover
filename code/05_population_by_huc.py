"""05_population_by_huc.py — LandScan 2024 population per HUC12 (cell-fraction weighted).

ORNL's handling rules are non-negotiable: the raster is never reprojected (polygons go
to EPSG:4326 instead), cell values are counts rather than density, and the raster is
never polygonized. Density is derived as polygon_pop / polygon_area_km2 with the area
measured in the equal-area Albers CRS.

Writes outputs/huc12_population.csv.
"""
from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from exactextract import exact_extract
from rasterio.windows import from_bounds

from utils import (
    CRS_ALBERS,
    LANDSCAN_TIF,
    OUT,
    OUT_INT,
    POP_COUNT_THRESHOLD,
    POP_DENSITY_THRESHOLD,
    POP_SENSITIVITY,
    assert_crs,
    to_wgs,
)


def _strict_check(huc_albers: gpd.GeoDataFrame, sample_ids: list[str]) -> None:
    """ORNL's literal recipe on a small AOI: cell centres -> points -> spatial join.

    Kept as a cross-check on the exactextract fast path. Agreement is not expected to
    be exact — exactextract splits a boundary cell by area fraction while the centroid
    method assigns it whole — but the totals should be close.
    """
    sub = huc_albers[huc_albers["HUC12"].isin(sample_ids)]
    sub_4326 = to_wgs(sub[["HUC12", "geometry"]].copy())
    minx, miny, maxx, maxy = sub_4326.total_bounds
    with rasterio.open(LANDSCAN_TIF) as src:
        win = from_bounds(minx, miny, maxx, maxy, transform=src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win)
        tr = src.window_transform(win)
        nodata = src.nodata
    rows, cols = np.nonzero((arr != nodata) & (arr > 0))
    vals = arr[rows, cols].astype("float64")
    xs, ys = rasterio.transform.xy(tr, rows, cols)
    pts = gpd.GeoDataFrame(
        {"pop": vals}, geometry=gpd.points_from_xy(xs, ys), crs="EPSG:4326"
    ).to_crs(CRS_ALBERS)
    joined = gpd.sjoin(pts, sub[["HUC12", "geometry"]], predicate="within", how="inner")
    strict = joined.groupby("HUC12")["pop"].sum()
    print("\nstrict ORNL centroid cross-check on "
          f"{len(sample_ids)} HUC12s: centroid total {strict.sum():,.0f}")


def main() -> None:
    huc = gpd.read_file(OUT_INT / "huc12_study.gpkg", layer="huc12")
    assert_crs(huc, CRS_ALBERS, "huc12_study")
    huc["huc12_area_km2"] = huc.geometry.area / 1e6

    huc_4326 = to_wgs(huc[["HUC12", "geometry"]].copy())

    with rasterio.open(LANDSCAN_TIF) as src:
        if src.nodata is None:
            raise RuntimeError("LandScan raster has no nodata set — set it before extraction")
        minx, miny, maxx, maxy = huc_4326.total_bounds
        win = from_bounds(minx, miny, maxx, maxy, transform=src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win)
        bbox_total = float(arr[arr != src.nodata].sum())

    result = exact_extract(
        rast=str(LANDSCAN_TIF), vec=huc_4326, ops=["sum"],
        include_cols=["HUC12"], output="pandas",
    )
    sum_col = [c for c in result.columns if c.endswith("sum") or c == "sum"][0]
    result = result.rename(columns={sum_col: "population"})

    merged = huc.merge(result[["HUC12", "population"]], on="HUC12", how="left")
    merged["population"] = merged["population"].fillna(0.0)
    merged["pop_density"] = merged["population"] / merged["huc12_area_km2"]
    merged["high_pop_huc"] = (
        (merged["population"] > POP_COUNT_THRESHOLD)
        | (merged["pop_density"] > POP_DENSITY_THRESHOLD)
    )
    for count_thr, dens_thr in POP_SENSITIVITY:
        merged[f"high_pop_{count_thr}_{int(dens_thr)}"] = (
            (merged["population"] > count_thr) | (merged["pop_density"] > dens_thr)
        )

    poly_total = float(merged["population"].sum())
    print("=== 05_population_by_huc ===")
    print(f"HUC12s: {len(merged):,}")
    print(f"polygon-sum population: {poly_total:,.0f}")
    print(f"bbox-window population: {bbox_total:,.0f}  (bbox is larger by construction)")
    if poly_total > bbox_total * 1.005:
        raise AssertionError("Polygon population exceeds the bbox total — extraction is leaking")

    print("\nTop 10 HUC12s by population:")
    print(merged.sort_values("population", ascending=False)
          .head(10)[["HUC12", "NAME", "population", "pop_density"]]
          .to_string(index=False, float_format=lambda v: f"{v:,.1f}"))

    print(f"\nhigh_pop_huc (pop > {POP_COUNT_THRESHOLD:,} or density > {POP_DENSITY_THRESHOLD:g}/km2): "
          f"{int(merged['high_pop_huc'].sum())} / {len(merged)}")
    for count_thr, dens_thr in POP_SENSITIVITY:
        col = f"high_pop_{count_thr}_{int(dens_thr)}"
        print(f"  sensitivity {count_thr:>6,} / {dens_thr:>5g}: {int(merged[col].sum()):>4d} HUC12s")

    _strict_check(merged, merged.sort_values("population", ascending=False)["HUC12"].head(10).tolist())

    cols = ["HUC12", "huc12_area_km2", "population", "pop_density", "high_pop_huc"] + [
        f"high_pop_{c}_{int(d)}" for c, d in POP_SENSITIVITY
    ]
    out_path = OUT / "huc12_population.csv"
    merged[cols].to_csv(out_path, index=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
