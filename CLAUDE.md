# Lithium Mining vs. Population & Drinking Water — Smackover US

Writing a paper for Water and Energy in Transition for Environment and Planning E on the impact of lithium brine extraction in the smackover formation on people and their drinking water. What places are high impact vs. the remaining lower-impact.

## Environment — how to run Python (non-negotiable)

**Use this interpreter, by full path, for every invocation:**

```
"Z:/ek559/nys_algal_bloom/NYS algal bloom/code2/Scripts/python.exe" script.py
```

Do **not** use `python`, `python3`, or `py` — they resolve to `C:\Program Files\Python314`
or `C:\ProgramData\anaconda3`, neither of which has a geospatial stack. Verified present in
this venv (Python 3.13.1): `geopandas` 1.0.1, `rasterio` 1.4.3, `shapely` 2.1.0, `pyogrio`
0.10.0, `pyproj` 3.7.1, `exactextract` 0.3.0, `networkx` 3.6.1, `pandas` 2.2.3, `numpy` 2.2.4,
`openpyxl` 3.1.5, `matplotlib` 3.10.1. **Missing:** `rasterstats` (not needed — use
`exactextract`) and `mapclassify` (so compute quantile/natural-breaks map bins with `numpy`
rather than `geopandas`' `scheme=` argument; the venv is shared with another project, so do
not pip-install into it without asking).

## Goal

**Unit of analysis: HUC12.** Every headline number is a sum over HUC12 watersheds classified
high-impact vs. low-impact. The 2 km USGS model cells are an *intermediate* used only to carry
in-place lithium tonnage onto HUC12s without losing mass.

Produce, for the smackover formation:
1. A **map** showing HUC12s over the predicted lithium-brine footprint, classified by impact tier (high-impact vs. low-impact for people/drinking water), plus a companion map graduated by in-place Li tonnage.
2. A **shapefile/GeoPackage** of those HUC12s with per-watershed attributes (in-place Li tons p5/p50/p95 × 10/20/30% porosity, footprint area, population, density, CWS-intake flags, upstream-of-CWS-intake flag, impact tier and reasons).
3. An **analysis** comparing the in-place lithium tonnage (and area, and population) of "high-impact" vs. "low-impact" HUC12s, so the paper can quote a defensible number for "X% of predicted lithium sits in places we probably shouldn't mine."

"High impact" = HUC12 that **(a)** is a high-population/high-density watershed, **(b)** contains a community water system (CWS) surface-water intake, **(c)** contains a CWS groundwater well, or **(d)** drains into a CWS-surface-intake HUC12. "Low impact" = none of the above.

> **How this differs from the northern-Appalachian sibling project** ([`z:/ek559/Lithium_mining_US_northeast/`](../Lithium_mining_US_northeast/), which this analysis mirrors). There, the "predicted lithium" is a set of **vector permissive tracts** (High/Medium/Low) for hard-rock Li-pegmatite deposits, and the resource is weighted by a Monte-Carlo tonnage distribution attached to the tract system as a whole. Here, the predicted lithium is a **raster of machine-learning-predicted Li concentration in Smackover Formation brine**, and — crucially — the USGS release lets us compute **recoverable lithium mass (metric tons) per grid cell**, so we can weight the impact result by *actual resource tonnage per cell* instead of by area or by a coarse rank. The "mining" is **brine extraction / direct lithium extraction (DLE)** from produced water rather than open-pit pegmatite mining. The only real methodological change is **Step 1–2 (building the "lithium polygons")**: instead of reading three tract shapefiles, we grid the prediction raster onto the model-domain fishnet and attach per-cell recoverable tonnage. Everything downstream — HUC12 clip, CWS intakes, upstream traversal, LandScan population, overlay, classification, map — is identical, and the supporting datasets (WBD HUC12, SDWIS PWS↔HUC12, LandScan) are the same files.
>
> **Why not High/Medium/Low here.** In the pegmatite project those ranks encode *permissibility* — the probability a deposit exists at all. In the Smackover, lithium is known to be present throughout the formation; existence is not the question. The natural axis is **how much recoverable lithium is in each place**, which is a mass (tons), not a likelihood class. So we make **per-cell recoverable Li tonnage the primary resource measure** and let the paper's headline be resource-weighted ("X% of the median predicted recoverable lithium sits in high-impact areas"). Grade (`Li_mgL`) and the USGS qualitative-uncertainty class (`qualunc`, see the Data table) are kept only as descriptive attributes, not as the classification axis.

## Data

All paths are relative to the repo root [`z:/ek559/lithium_mining_smackover/`](./).

### Lithium — USGS Smackover Formation Brine Assessment (Knierim et al., 2024)
- Data release: Knierim, K.J., and others, 2024, *Lithium observations, machine-learning predictions, and mass estimates from the Smackover Formation brines in southern Arkansas*, USGS data release, https://doi.org/10.5066/P9QPRYZN.
- Interpretive paper: [Knierim et al 2024.pdf](Knierim%20et%20al%202024.pdf) (Science Advances, v. 10, no. 39, doi:10.1126/sciadv.adp8149).
- Model archive: [sar_li/](sar_li/). Predictions describe Li concentration in brine at the **mid-point depth of the Reynolds oolite unit** of the Smackover Formation (≈3,500–11,300 ft deep, 0–400 ft thick) across southern Arkansas.

The prediction data are **rasters and a grid**, not deposit polygons:

| File | What it is | Use for impact analysis? |
|---|---|---|
| `smackover_Li_uncertainty_p5.tif` / `_p50.tif` / `_p95.tif` | 5th / 50th / 95th percentile of predicted Li (**mg/L**), 2 km cells, 32×90 grid. `-99` = masked/out-of-domain sentinel. | **Yes — grade inputs to the per-cell tonnage** (low/median/high). |
| [sar_li/output/smackover_Li_preds.tif](sar_li/output/smackover_Li_preds.tif) | RF point-prediction of Li concentration (mg/L); valid range ≈13–389. | Descriptive attribute (`Li_mgL`); p50 is the value used for median tonnage. |
| **`smackover_thick`** (column in [sar_li/input/exvars/SAR_modeldomain_rasterstack.txt](sar_li/input/exvars/SAR_modeldomain_rasterstack.txt)) | Reynolds-oolite unit **thickness (m)** per cell (0–124 m, mean ≈52 m). | **Yes — reservoir volume input to tonnage.** |
| [sar_li/input/brine/smackover_H2Oratios.tif](sar_li/input/brine/smackover_H2Oratios.tif) | Water:oil ratio per cell (0.9 outside oil fields). | **Yes — brine fraction of pore volume.** |
| [sar_li/input/brine/smackover_H2Oprod_2022.tif](sar_li/input/brine/smackover_H2Oprod_2022.tif) | 2022 brine production (barrels) per cell. | Optional — "already-extracted" / activity context, not the in-place resource. |
| [sar_li/grid/SAR_modeldomain_mask.tif](sar_li/grid/SAR_modeldomain_mask.tif) | Model-domain mask (valid = 1). | **Yes** — defines valid cells for all rasters. |
| [sar_li/grid/SAR_modeldomain_4269.shp](sar_li/grid/SAR_modeldomain_4269.shp) | Fishnet of the model domain, **one polygon per raster cell** (2,880 cells, `Id`/`gridcode`), EPSG:4269 (NAD83). | **Yes** — vector frame to carry raster values; also the study-area boundary (dissolved). |
| [sar_li/output/smackover_Li_uncertainty_qualunc.tif](sar_li/output/smackover_Li_uncertainty_qualunc.tif) | Qualitative likelihood the cell exceeds 100 mg/L: `0` very likely <100, `1` likely <100, `2` likely ≥100, `3` likely >100 (`-99` masked). | Descriptive attribute (`qualunc`) — a grade-likelihood flag, **not** the resource measure. |
| `smackover_Li_uncertainty_rngp.tif` | p95 − p5 spread (mg/L) — prediction uncertainty width. | Context / optional attribute. |
| [sar_li/output/SAR_smackover_Liestimate.csv](sar_li/output/SAR_smackover_Liestimate.csv) | Domain-**total** Li mass (tons Li, LCE) for low/median/high × 10/20/30% porosity. | Cross-check that per-cell tons sum to the published totals. |
| [sar_li/output/SAR_Lipreds.csv](sar_li/output/SAR_Lipreds.csv) | Observed vs. predicted Li at brine-sample sites (train/test). | Optional overlay (sample points); not used to define footprint. |
| [sar_li/4_SARLi_estimate.py](sar_li/4_SARLi_estimate.py) | USGS script that computes per-cell brine volume and **per-cell Li mass (metric tons)** rasters. | **Port / re-run** to produce `li_ton_{p5,p50,p95}` per cell (see Plan step 2). |
| `sar_li/1_*.py`, `2_SARLi_RFmodel.R`, `3_*.py` | Scripts that built the predictions (dataprep, RF model, uncertainty). | Reference only; not re-run for v1. |

- **Projection of all rasters**: USA Contiguous Albers Equal Area Conic (lat_of_center 23°, lon −96°, SP 29.5°/45.5°, WGS84 datum), units = **meters**, 2,000 m cells. This is functionally equivalent to **ESRI:102039** (the CRS the sibling project standardizes on); the only difference is the geodetic datum (WGS84 here vs. NAD83/GRS80 in ESRI:102039), a sub-meter offset in this region that is negligible for HUC12-scale overlay. See "Key implementation notes → CRS".
- Domain corners (Albers, m): UL (180955, 1171285) → LR (360955, 1107285). See [sar_li/modelgeoref.txt](sar_li/modelgeoref.txt).

### HUC12 watersheds — USGS WBD (CONUS, 2020-10-26 pull)
- [WBD_HUC12_CONUS_pulled10262020/WBD_HUC12_CONUS_pulled10262020.shp](WBD_HUC12_CONUS_pulled10262020/WBD_HUC12_CONUS_pulled10262020.shp)
- Provides HUC12 polygons + the `TOHUC` attribute (downstream HUC12), which is what makes the upstream traversal possible.

### Community water system intakes — EPA SDWIS (PWS↔HUC12 join, 2022Q2)
- [cws_intake_hucs/PWS_Loctations_HUC12_A_I_2022Q2.xlsx](cws_intake_hucs/PWS_Loctations_HUC12_A_I_2022Q2.xlsx) — table of public water system facilities with `HUC_12`, `WATER_TYPE_CODE` (SW = surface water, GW = groundwater), `FACILITY_TYPE_NAME` (Well, Intake, Reservoir, …), `PWS_ACTIVITY_CODE`, `FACILITY_ACTIVITY_CODE`.
- (`cws_hucs.parquet` in the same folder is an R-side artifact and contains no data — ignore.)
- **This file alone cannot identify *community* water systems.** Its 12 columns (OBJECTID, SUBMISSIONYEARQUARTER, PWSID, FACILITY_ID, HUC_12, PRIMACY_AGENCY_CODE, PWS_ACTIVITY_CODE, FACILITY_ACTIVITY_CODE, PWS_DEACTIVATION_DATE, WATER_TYPE_CODE, FACILITY_TYPE_CODE, FACILITY_TYPE_NAME) contain no `PWS_TYPE_CODE`, so CWS cannot be separated from non-transient and transient non-community systems (schools, campgrounds, truck stops).

### PWS system attributes — EPA SDWA / ECHO bulk download (2024Q4)
- [`Z:/ek559/sdwa_violations/SDWA_latest_downloads/SDWA_PUB_WATER_SYSTEMS.csv`](Z:/ek559/sdwa_violations/SDWA_latest_downloads/SDWA_PUB_WATER_SYSTEMS.csv) — 431,754 rows, one per PWS per quarter. Join on **`PWSID`** to the HUC12 xlsx to recover `PWS_TYPE_CODE` (`CWS` / `NTNCWS` / `TNCWS`), `PWS_ACTIVITY_CODE`, `GW_SW_CODE`, `OWNER_TYPE_CODE`, **`POPULATION_SERVED_COUNT`**, `SERVICE_CONNECTIONS_COUNT`, `CITY_NAME`, `STATE_CODE`.
  - **This is what makes the "CWS" label true**: filter `PWS_TYPE_CODE == 'CWS'` and `PWS_ACTIVITY_CODE == 'A'`. Arkansas has **668 active CWS** (369 GW / 299 SW) serving 2,933,136 people. Of the 572 active AR PWSIDs in the HUC12 xlsx, **all 572 match** the inventory and **386 are active CWS** — so the CWS filter removes about a third of the facilities and is worth doing.
  - `POPULATION_SERVED_COUNT` is the project's only genuine **water-use** variable: population served by CWS whose intakes sit in each HUC12. Carry it as `cws_pop_served` alongside the LandScan resident population — they answer different questions (who lives there vs. who drinks from there).
  - **Vintage mismatch to document**: the HUC12 crosswalk is 2022Q2, this inventory is 2024Q4. Join on `PWSID` and note it in methods; a PWS deactivated between the two is caught by the 2024Q4 `PWS_ACTIVITY_CODE`.
- Sibling files in that folder (`SDWA_FACILITIES.csv`, `SDWA_GEOGRAPHIC_AREAS.csv`, `SDWA_SERVICE_AREAS.csv`, `SDWA_VIOLATIONS_ENFORCEMENT.parquet`) are available if we later want facility-level detail, counties served, or a violations-history angle. Not used in v1.
- We filter to **active CWS surface-water intakes** for the upstream analysis. Groundwater wells don't have a HUC12-based upstream concept and are handled separately (or out of scope for v1).
- **Note for Smackover:** southern Arkansas is the study area, so the relevant SDWIS primacy code is **AR** (plus any neighboring-state HUC12s that fall inside the buffered domain — e.g., LA, TX, MS). Groundwater CWS wells are especially important here: much of the rural Gulf Coastal Plain relies on aquifers (Sparta, Cockfield), so the `I_gw` set is likely to dominate the drinking-water-conflict footprint.

### Population — ORNL LandScan Global 2024
- [population_distribution/landscan-global-2024-assets/landscan-global-2024.tif](population_distribution/landscan-global-2024-assets/landscan-global-2024.tif) — ~1 km grid of ambient population count per cell, global; EPSG:4326.
- The `-colorized.tif` is for display only; use the data raster for analysis.

## Plan

1. **Standardize CRS.** Work in the rasters' native Albers (equal-area, meters) — call it `CRS_ALBERS` and treat it as ESRI:102039-equivalent. Reproject the model-domain grid (EPSG:4269) and the WBD HUC12 layer into `CRS_ALBERS`; leave LandScan in native EPSG:4326 and never warp it.
2. **Define "lithium polygons" and per-cell recoverable tonnage.** The model-domain fishnet ([SAR_modeldomain_4269.shp](sar_li/grid/SAR_modeldomain_4269.shp)) already has one polygon per raster cell, so join raster values to it by cell index (verify row-major alignment against a few known cells). Keep only **valid** cells (mask == 1). For each cell compute recoverable Li mass exactly as [4_SARLi_estimate.py](sar_li/4_SARLi_estimate.py) does:

   ```
   vol_L   = thickness_m·(3.28) · (2000·3.28) · (2000·3.28) · 28.3168   # pore-space cell volume, liters
           · (porosity/100) · water_oil_ratio                          # → brine volume
   li_ton  = vol_L · Li_mgL / 1e9                                       # metric tons Li in the cell
   ```

   Attach to each cell polygon:
   - **`li_ton_p50`** (median), **`li_ton_p5`** (low), **`li_ton_p95`** (high) — from the p50/p5/p95 grade rasters at the chosen porosity (**default 20%**; carry 10%/30% as a sensitivity band). This is the **primary resource measure** and the weight for every headline statistic.
   - `Li_mgL` (= p50 grade), `qualunc`, `thick_m`, `area_km2 = geom.area/1e6` (≈4.0 km²/cell) — descriptive attributes.
   - **Cross-check:** `sum(li_ton_p50)` over all cells must match the published domain total in [SAR_smackover_Liestimate.csv](sar_li/output/SAR_smackover_Liestimate.csv) (median, 20% porosity) to rounding. If it doesn't, the raster↔fishnet alignment or the unit conversions are off.

   The **predicted lithium footprint** = all valid cells (~2,524 cells, ~10,096 km²). There is no need to threshold it into High/Med/Low; the tonnage weight already down-weights thin, low-grade cells to near zero. If a discrete legend is wanted for the map, bin `li_ton_p50` into **tonnage classes by quantile or natural breaks** (display only) — do not let those bins drive the statistic. Keep per-cell polygons for the overlay so tonnage and area math stay exact; dissolve only for cartography.
3. **Clip HUC12 layer** to the model domain ([SAR_modeldomain_4269.shp](sar_li/grid/SAR_modeldomain_4269.shp) dissolved) buffered ~50 km, to capture downstream HUC12s that drain out of the study area (the Ouachita/Saline river systems flow south toward Louisiana).
4. **Identify "intake HUC12s"**: from the SDWIS xlsx, keep rows where `PWS_ACTIVITY_CODE == 'A'` and `FACILITY_ACTIVITY_CODE == 'A'`, then **inner-join to `SDWA_PUB_WATER_SYSTEMS.csv` on `PWSID` and keep `PWS_TYPE_CODE == 'CWS'` with `PWS_ACTIVITY_CODE == 'A'`** — this is what makes "community water system" literally true rather than "any public water system". Carry `POPULATION_SERVED_COUNT` through so each intake HUC12 gets a `cws_pop_served`. Split by water type:
   - **`I_sw`** = distinct `HUC_12`s where `WATER_TYPE_CODE == 'SW'` (surface-water intakes — Intakes, Reservoirs, Springs, Infiltration Galleries).
   - **`I_gw`** = distinct `HUC_12`s where `WATER_TYPE_CODE == 'GW'` (groundwater intakes — Wells, primarily). The SDWIS pull already attributes each well to the HUC12 it sits in, so we use that as the spatial footprint of the well field for v1.
5. **Upstream traversal — surface water only**: build a directed graph from HUC12 → `TOHUC` **from the national WBD attribute table** (`pyogrio` with `read_geometry=False`, ~90k rows, seconds) — *not* from the 50 km-clipped subset. The Ouachita and Saline drain south into Louisiana and the Mississippi, so a Smackover HUC12 can sit upstream of an intake far outside any buffer; clipping the graph first silently drops exactly those links. Clip geometry, never the graph. For each HUC12 in `I_sw`, walk *upstream* (reverse edges) and collect every ancestor; union → **upstream set** `U_sw`. Groundwater intakes do **not** get upstream propagation — the HUC12 surface-flow graph is not a model of aquifer flow paths, so we exclude only the HUC12 the well sits in (a conservative spatial proxy for the well's capture zone).
   - **Drinking-water-conflict set** `W = I_sw ∪ U_sw ∪ I_gw`. Any lithium polygon intersecting `W` is flagged "drinking-water conflict."
6. **Population aggregation** (see "LandScan handling rules" below — ORNL gives explicit warnings we have to respect): leave the LandScan raster in its native **EPSG:4326** and *never* warp it. Sum population per HUC12 by reprojecting the HUC12 polygons into 4326 and using `exactextract` (cell-fraction-weighted sum) against the native raster. Compute density as `huc12_pop / huc12_area_km²`, where `huc12_area_km²` is measured on the polygon in **`CRS_ALBERS`** (equal-area). Build a high-pop HUC12 set `P` by thresholding (default: HUC12 pop > 10,000 OR HUC12 density > 100 people/km²).
7. **Build the HUC12 analysis table** — two stages, because the unit of analysis is the HUC12 but the tonnage lives on 2 km cells:
   - **7a. Move tonnage onto HUC12s without losing mass.** `gpd.overlay(cells, huc12, how='identity')` so each piece belongs to exactly one HUC12, then **apportion by area fraction** (`li_ton_piece = li_ton_cell · piece_area / cell_area`) for all nine tonnage columns. Assert `Σ pieces == Σ cells` to <0.01%. Keep the split layer as an intermediate — it is the cartographic layer and the audit trail.
   - **7b. Dissolve to one row per HUC12** intersecting the lithium footprint, carrying:
     - `li_ton_p50` / `_p5` / `_p95` (× 10/20/30% porosity) — in-place Li tons in that watershed; **the primary weight**.
     - `li_area_km2` (Smackover footprint inside the HUC12), `huc12_area_km2`, `li_frac`, `li_ton_per_km2`.
     - `population`, `pop_density` — LandScan totals for the whole HUC12 (from step 6; no sub-polygon population step is needed once HUC12 is the unit).
     - `cws_pop_served`, `n_sw_facilities`, `n_gw_facilities` — SDWIS/SDWA water-use context.
     - `Li_mgL_mean`, `thick_m_mean`, `qualunc_max`, `h2o_prod_bbl_2022` — descriptive.
     - `in_sw_intake_huc` (HUC12 ∈ `I_sw`), `in_gw_intake_huc` (∈ `I_gw`), `upstream_of_sw_intake` (∈ `U_sw \ I_sw`), `high_pop_flag`.
     - `impact_tier` — "high" if **any** of the four flags; else "low". Plus `impact_reasons` (e.g. `"gw_intake;upstream_sw"`) so the paper can decompose *why* a watershed is flagged, and `n_reasons` (0–4) as a graded column.
8. **Outputs**:
   - `outputs/huc12_lithium_impact.gpkg` (+ `.shp`, `.csv`) — one row per HUC12 with every field above.
   - `outputs/intermediate/lithium_cells_split.gpkg` — the cell × HUC12 split layer (audit trail + cartography).
   - `outputs/impact_map.png` — high-impact red, low-impact green HUC12s, Smackover footprint outline, CWS intakes as points; plus `tonnage_map.png` graduated by `li_ton_p50` (resource magnitude) so the reader sees *where the lithium actually is* relative to the conflict areas.
   - `outputs/impact_summary.csv` (+ `.md`) — the **headline table**: in-place Li tons (p5/p50/p95), area (km²), population, and CWS population served per `impact_tier`, with the percentage of median tonnage in each tier. Report the porosity sensitivity (10/20/30%), the population-threshold sensitivity grid, and a decomposition by `impact_reasons`.
   - `notes/methods.md` and `notes/interpretation.md` — short, paper-ready methods + the "what low-impact does / does not mean" caveats (adapt the sibling project's [interpretation.md](../Lithium_mining_US_northeast/notes/interpretation.md), adding the brine-specific caveats in "Open decisions").

## Lithium data assessment — how the resource is measured

The sibling project chose among mixed vector layers; here the choice is which raster products define the resource vs. which are context.

- **Primary resource measure**: **in-place lithium resource per cell (metric tons)** = brine volume × predicted grade, computed per [4_SARLi_estimate.py](sar_li/4_SARLi_estimate.py) from `smackover_thick` (thickness), the water:oil ratio raster, an assumed porosity, and the p5/p50/p95 grade rasters. Median = `li_ton_p50` at 20% porosity; p5/p95 and 10%/30% porosity give the uncertainty band. This is the honest analog of the sibling project's Monte-Carlo tonnage — except we get it **per cell**, not just as a domain total, so it can be intersected with the impact geography directly.
  - **This is in-place resource, NOT engineering-extractable tons.** It applies no brine-recovery factor and no DLE lithium-recovery efficiency — it is the total Li dissolved in the brine fraction of the cell's pore space. Extractable tonnage would be `in_place × brine_recovery × Li_recovery` (both < 1). We deliberately keep in-place because (a) it is what the USGS release publishes, (b) a recovery factor scales every cell by ~the same constant and therefore **cancels out of the high-vs-low percentage**, and (c) it is the resource that would motivate extraction. Label every output and figure "in-place" and never call it "extractable."
  - The script's *other* mass number — `sumLi_ton_ext`, lithium coproduced with oil in 2022 (~0.03–0.09% of in-place) — is **not** the resource; it is current incidental production. Do not use it as the denominator.
- **Descriptive attributes (not the resource axis)**: `Li_mgL` (grade), `qualunc` (grade-likelihood class), `thick_m`, `rngp` (grade uncertainty width). `qualunc` is *not* used to classify size because it ignores reservoir volume — a thick, moderate-grade cell can hold more recoverable Li than a thin, high-grade one.
- **Validation**: `SAR_smackover_Liestimate.csv` domain totals must equal the sum of the per-cell tons (same porosity/grade). `SAR_Lipreds.csv` sample points are an optional overlay.

**Decision for v1**: the "predicted lithium footprint" is all valid model-domain cells, each carrying `li_ton_p50/_p5/_p95`. The impact statistic is **tonnage-weighted** (% of median recoverable Li tons in high-impact vs. low-impact cells), with area (km²) reported alongside for context. No High/Medium/Low tiering is used; if the map needs a discrete legend, bin `li_ton_p50` for display only.

## Pipeline (concrete)

Stack: Python — `geopandas`, `shapely` (2.x), `rasterio`, `exactextract`, `networkx`, `pyogrio`, `pandas`, all present in the venv named under "Environment" above (invoke it by full path; `rasterstats` and `mapclassify` are *not* installed). Run from `code/`. Mirror the sibling project's [`code/`](../Lithium_mining_US_northeast/code/) — copy `utils.py`, `02`–`07` almost verbatim (only path constants and the study-area/state names change); **rewrite `01` to build tracts from the raster** instead of reading tract shapefiles.

```
code/
  utils.py                  # CRS constant (native Albers ≈ ESRI:102039), paths, thresholds, buffer/IO helpers
  01_load_lithium.py        # NEW LOGIC: grid p5/p50/p95 grade + thickness + water-ratio onto SAR_modeldomain
                            #   fishnet (mask==1); compute li_ton_p5/p50/p95 x 10/20/30% porosity per cell
                            #   (port 4_SARLi_estimate.py); assert sums == published USGS totals;
                            #   write outputs/intermediate/lithium_cells.gpkg + study_area.gpkg (domain dissolved)
  02_load_huc12.py          # read national HUC12, clip to model-domain buffer (+50 km) -> huc12_study.gpkg
  03_intake_hucs.py         # PWS xlsx x SDWA_PUB_WATER_SYSTEMS join -> active CWS only; split by WATER_TYPE_CODE
                            #   -> intake_hucs_sw/gw.csv with cws_pop_served
  04_upstream_hucs.py       # TOHUC DiGraph from the NATIONAL WBD dbf; nx.ancestors from I_sw only
                            #   -> W = I_sw ∪ U_sw ∪ I_gw -> conflict_hucs.csv
  05_population_by_huc.py   # exactextract LandScan over study HUC12s -> huc12_population.csv; threshold -> P
  06_impact_dataset.py      # overlay lithium cells x HUC12 (identity), apportion tonnage by area fraction,
                            #   dissolve to HUC12; join W & P flags; classify impact_tier + impact_reasons
                            #   -> huc12_lithium_impact.gpkg + .shp + .csv
  07_summary_and_map.py     # tonnage/area/pop-by-tier CSV/MD, sensitivity grids, matplotlib map PNGs,
                            #   top-15 HUC12s by tonnage with their impact flags
  run_all.py                # linear driver
```

Run order is linear (each script writes to `outputs/` and is idempotent).

### Key implementation notes
- **CRS**: standardize on the rasters' native Albers (equal-area, meters); set `CRS_ALBERS` to that WKT (from [modelgeoref.txt](sar_li/modelgeoref.txt)) or to `ESRI:102039` and rely on the datum offset being negligible. Reproject the WBD HUC12 layer, the model-domain grid, and (for extraction only) polygons into LandScan's 4326; never reproject the LandScan or the prediction rasters themselves.
- **Building tracts + tonnage from the raster** (`01`): the domain fishnet has exactly one polygon per raster cell in row-major order, so read the arrays flat and attach by cell index (cleanest), or `rasterio.sample` cell centers — verify alignment by checking a few known cells. Keep cells where `mask == 1`. Compute `li_ton_p5/p50/p95` with the volume→mass formula in [4_SARLi_estimate.py](sar_li/4_SARLi_estimate.py) (thickness·cell·porosity·water_ratio·grade / 1e9); porosity is a `utils.py` constant (default 20). Give every cell a `tract_id`, `li_ton_*`, `Li_mgL`, `qualunc`, `thick_m`, and `area_km2 = geom.area/1e6` (≈4.0 km²/cell). **Assert** `sum(li_ton_p50)` matches the published median/20% total in `SAR_smackover_Liestimate.csv`.
- **Upstream traversal**: WBD's `TOHUC` is `HUC12 -> downstream HUC12`. Build a `DiGraph` with edges `u -> TOHUC[u]`, then `nx.ancestors(G, h)` for each `h ∈ I_sw` gives every upstream HUC12 in one call. Special `TOHUC` codes (`OCEAN`, `CLOSED BASIN`, `CANADA`, `MEXICO`) are sinks — leave them as terminal nodes. **Do not** call `nx.ancestors` for `I_gw`; groundwater wells get only the colocated HUC12 as their footprint, because the surface-flow graph is not a valid aquifer-flow model.
- **Polygon split at HUC12 lines**: use `gpd.overlay(lithium, huc12, how='identity')` so each output polygon belongs to exactly one HUC12 — makes the flag joins a simple merge on `HUC12`.
- **Population zonal stats**: `exactextract` against the **native** LandScan raster (EPSG:4326), with polygons reprojected *into* 4326 for the extraction. `exactextract`'s `sum` is fraction-of-cell weighted, which is the correct apportionment rule for count-valued cells (a polygon covering 40% of a cell receives 40% of that cell's people, and the totals across a partition of cells are preserved). Compute pop per HUC12 and pop per split-lithium polygon this way.
- **LandScan handling rules** (from ORNL's FAQ — non-negotiable):
  1. **Do not warp/reproject the raster.** Any reprojection resamples cell values and leaks population. Keep the raster in its delivered EPSG:4326 grid.
  2. **Cell values are population counts, not density.** Reading "density" off a cell is wrong because 30 arc-sec cells get narrower toward the poles. Density must be derived as `polygon_pop / polygon_area_km²` with `polygon_area_km²` measured on the polygon **in `CRS_ALBERS` (equal-area)** — not from cell counts.
  3. **Do not raster→polygon convert** using the default ArcGIS/`gdal_polygonize` behavior: it merges adjacent equal-valued cells into one polygon while keeping the single value, silently dropping population. If we ever need a vector form of the raster, use **point centroids** (one point per cell, value = cell population) and project the points — never polygon dissolve.
  4. **Strict-mode fallback** (matches ORNL's recommended recipe exactly, if anyone disputes the `exactextract` shortcut): rasterio→cell centers as points → reproject points to `CRS_ALBERS` → spatial-join to polygons → groupby-sum. This is equivalent in total-population to the `exactextract` approach but is the literal procedure ORNL writes down; keep it as a validation cross-check on a small AOI before trusting the fast path.
  5. **Sanity check**: after step 5, sum the per-HUC12 populations across the study-area HUC12s and compare to the sum of LandScan cells whose centers fall inside the study area. They should agree to within a small fraction of a percent; if not, the extraction is leaking population.
- **Performance**: clip the national HUC12 layer (~90k features) to the study-area buffer before anything else; everything downstream becomes cheap.
- **Resource (tonnage) weighting — v1 primary**: computed per cell in `01` by porting [4_SARLi_estimate.py](sar_li/4_SARLi_estimate.py) (thickness × cell area × porosity × water:oil ratio × grade / 1e9), for p5/p50/p95 grade. Do **not** approximate by apportioning the domain total by area share — the real per-cell math is cheap here (2,880 cells) and the thickness raster makes cells genuinely unequal. The final statistic sums `li_ton_p50` by `impact_tier`; carry p5/p95 (and 10%/30% porosity) for the uncertainty band.

## Open decisions before coding

> **Status:** steps 01–06 are built, run, and validated; `07_summary_and_map.py`, `run_all.py`, and the two notes files are not. Read [notes/implementation_plan.md](notes/implementation_plan.md) — it is the handoff document and carries the verified numbers to use as regression checks. Step 08 (`08_concentration_bivariate.py`) also exists: it builds concentration-based (mg/L) bivariate maps, Li × CWS population served, from the published p5/p50/p95 rasters.

- **The upstream screen is degenerate as a binary — must be resolved before `07`.** Run as originally specified it flags **140 of 141** analysis HUC12s, giving a 100 %-high-impact headline, which is a broken screen rather than a finding ("upstream of *some* CWS intake" is near-universal in CONUS; the sibling project has the same pathology at 99.4 %). `04` now also emits **`steps_to_sw_intake`** (HUC12 hops to the nearest downstream CWS surface intake; median 6, max 30 across the study area), so distance can do the discriminating. Recommended: `upstream_near = steps_to_sw_intake <= 2` for the headline tier, with k = 1/2/3/5/∞ as a sensitivity row. For reference, direct-conflict-only tiering (population + SW intake + GW well, no upstream) gives **51.5 % of tonnage high-impact**, 63 of 141 HUC12s. See [notes/implementation_plan.md](notes/implementation_plan.md) §11.
- **Unit of analysis — decided**: **HUC12**. Cells are an intermediate; tonnage is apportioned to HUC12s by area fraction and every headline statistic is a sum over watersheds.
- **CWS filtering — decided**: join the HUC12 crosswalk to [`SDWA_PUB_WATER_SYSTEMS.csv`](Z:/ek559/sdwa_violations/SDWA_latest_downloads/SDWA_PUB_WATER_SYSTEMS.csv) on `PWSID` and keep active `PWS_TYPE_CODE == 'CWS'`, carrying `POPULATION_SERVED_COUNT` as the water-use variable. Document the 2022Q2 ↔ 2024Q4 vintage mismatch.
- **Resource measure — decided**: per-cell recoverable Li mass (metric tons), median = p50 at 20% porosity, uncertainty band from p5/p95 and 10%/30% porosity. This replaces the High/Medium/Low tiering; `qualunc` is retained only as a descriptive attribute. The headline is **tonnage-weighted** ("% of median predicted recoverable lithium in high-impact areas").
- **Porosity default**: 20% (mid of the USGS 10/20/30% range). The porosity choice scales *all* tonnages linearly, so it cancels out of the high-vs-low **percentage** — report 20% for absolute tons and note the percentage split is porosity-invariant.
- **Map legend**: the primary map colors by `impact_tier` (red/green). If a resource legend is wanted, add a second panel graduated by `li_ton_p50` (quantile or natural-breaks bins, display only). Decide whether one combined figure or two panels.
- **Population threshold for "high-impact populated area"** — pick a number and document it (suggest: HUC12 population > 10,000 *or* mean density > 100/km²; sensitivity check at half and double). Note the study area is rural southern Arkansas, so an absolute-count threshold may flag almost nothing — the density knob and the `I_gw` set will do most of the work.
- **Groundwater dominance / brine-specific caveats**: GW wells contribute the colocated HUC12 only (no upstream propagation) — decided, per the sibling project's [interpretation.md](../Lithium_mining_US_northeast/notes/interpretation.md). For Smackover, additionally document that (a) the drinking-water aquifers (shallow Coastal Plain) are hydrologically distinct from the deep (>3,500 ft) Smackover brine zone, so the surface-overlay screen measures *where the resource projects to the surface*, not a demonstrated contamination pathway; (b) the real DLE risks are induced seismicity, brine-reinjection well integrity, and surface spills, which a HUC12 overlay does not model; and (c) private wells are not in SDWIS.
