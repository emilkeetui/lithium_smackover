"""02_load_huc12.py — Clip national WBD HUC12 to the buffered study area.

Also caches the *national* HUC12 -> TOHUC attribute table (no geometry), which
04_upstream_hucs.py needs: the Ouachita and Saline drain south into Louisiana and
the Mississippi, so a Smackover HUC12 can sit upstream of an intake far outside any
buffer. Clip the geometry, never the flow graph.

Writes:
    outputs/intermediate/huc12_study.gpkg        (HUC12s within domain + 50 km)
    outputs/intermediate/huc12_tohuc_national.csv (HUC12, TOHUC for all of CONUS)
"""
from __future__ import annotations

import geopandas as gpd
import pyogrio
from shapely import make_valid

from utils import (
    CRS_ALBERS,
    OUT_INT,
    STUDY_BUFFER_M,
    TOHUC_SINKS,
    WBD_HUC12,
    assert_crs,
    norm_tohuc,
    to_albers,
    zpad_huc12,
)


def _resolve(columns, *candidates) -> str:
    """Find a column by case-insensitive name, tolerating WBD casing differences."""
    lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    raise KeyError(f"none of {candidates} in {list(columns)}")


def main() -> None:
    study = to_albers(gpd.read_file(OUT_INT / "study_area.gpkg", layer="domains"))
    mask_albers = study.geometry.union_all().buffer(STUDY_BUFFER_M)

    info = pyogrio.read_info(WBD_HUC12)
    wbd_crs = info["crs"]
    fields = list(info["fields"])
    huc_f = _resolve(fields, "HUC12", "huc12")
    tohuc_f = _resolve(fields, "TOHUC", "tohuc")
    name_f = _resolve(fields, "NAME", "name")

    # --- national attribute table (flow graph input; no geometry, so it is cheap) ---
    nat = pyogrio.read_dataframe(WBD_HUC12, columns=[huc_f, tohuc_f], read_geometry=False)
    nat = nat.rename(columns={huc_f: "HUC12", tohuc_f: "TOHUC"})
    nat["HUC12"] = nat["HUC12"].map(zpad_huc12)
    nat["TOHUC"] = nat["TOHUC"].map(norm_tohuc)
    out_nat = OUT_INT / "huc12_tohuc_national.csv"
    nat.to_csv(out_nat, index=False)

    # --- clipped geometry ---------------------------------------------------------
    mask_native = gpd.GeoSeries([mask_albers], crs=CRS_ALBERS).to_crs(wbd_crs).iloc[0]
    huc = to_albers(pyogrio.read_dataframe(WBD_HUC12, mask=mask_native))
    huc = huc.rename(columns={huc_f: "HUC12", tohuc_f: "TOHUC", name_f: "NAME"})
    huc["HUC12"] = huc["HUC12"].map(zpad_huc12)
    huc["TOHUC"] = huc["TOHUC"].map(norm_tohuc)
    huc = huc[["HUC12", "NAME", "TOHUC", "geometry"]].copy()
    huc["geometry"] = huc.geometry.apply(make_valid)
    huc["huc12_area_km2"] = huc.geometry.area / 1e6
    huc = huc.drop_duplicates(subset="HUC12").reset_index(drop=True)
    assert_crs(huc, CRS_ALBERS, "huc12_study")

    # Which of these actually sit over the lithium footprint — the analysis rows.
    over = huc[huc.intersects(study.geometry.union_all())]

    out_path = OUT_INT / "huc12_study.gpkg"
    huc.to_file(out_path, layer="huc12", driver="GPKG")

    print("=== 02_load_huc12 ===")
    print(f"national HUC12 rows (attributes only): {len(nat):,} -> {out_nat.name}")
    print(f"study HUC12s (domain + {STUDY_BUFFER_M/1000:.0f} km): {len(huc):,}")
    print(f"  of which intersect the lithium footprint: {len(over):,}  <- analysis rows")
    print(f"  study area covered: {huc['huc12_area_km2'].sum():,.0f} km2")
    sink = huc["TOHUC"].isin(TOHUC_SINKS)
    print(f"  sink TOHUC rows: {int(sink.sum())}; normal: {int((~sink).sum())}")
    if sink.any():
        print("  sink values:", huc.loc[sink, "TOHUC"].value_counts().to_dict())
    empty = int((huc["TOHUC"] == "").sum())
    if empty:
        raise AssertionError(f"TOHUC has {empty} empty entries in the study set")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
