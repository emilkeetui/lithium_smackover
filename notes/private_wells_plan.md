# Plan v2: private-well population per HUC12 + bivariate map (Li × private wells)

Implementer: Sonnet. Follow [CLAUDE.md](../CLAUDE.md) (interpreter path, CRS rules, LandScan rules). This plan replaces v1. v1's headline formula (LandScan pop − **area-weighted** utility pop) was tested on the real data and fails (see §0). This plan still computes it, but only as a diagnostic.

Build **one script, `code/10_private_wells.py`**, plus a small parameterisation of `08_concentration_bivariate.py`. Add 10 to `run_all.py` after 09. The script is idempotent and writes only under `outputs/`.

---

## 0. What the feasibility check found (2026-09-30; use these as regression numbers)

Inputs load fast. Clipped by bbox to the 471 study HUC12s, the service-area file has **481 polygons**:
- 0 duplicate PWSIDs and 1 invalid geometry.
- Boundary source (`Method`): State 273, Random Forest 197, Decision Tree 10, Parcel 1.
- Primacy agency: LA 201, AR 178, TX 96, OK 6.

Service areas overlap each other very little: Σ area / union area = 1.008. `outputs/huc12_population.csv` already covers all 141 analysis HUC12s. The whole check runs in under 2 minutes.

Three estimators were compared. `pop` is LandScan population. `SA` is a service-area polygon. `LS(x)` is the LandScan sum over polygon x. Each utility's reported population is the `Population` field.

| | Definition | Analysis 141: HUC12s negative / zero | Floored Σ private-well pop (share of pop) | Study 471: negative |
|---|---|---|---|---|
| **A** (v1, user-specified) | pop_h − Σᵢ popᵢ · area(i∩h)/area(i) | 92 negative | 53,430 (25.5 %) | 305 of 471 |
| **B** | pop_h − Σᵢ popᵢ · LS(i∩h)/LS(i) | 81 negative | 15,644 (7.5 %) | 256 of 471 |
| **C** | LS(h) − LS(h ∩ ∪ SA), i.e. LandScan people outside every service area | 0 negative, 5 zero | 33,610 (16.0 %) | 0 |

**Why A and B fail.** In the median service area, the reported served population is **2.3×** the LandScan population inside its polygon; 267 of 481 are above 2×. Two causes:
- The reported count includes people outside the drawn polygon. For example, Texarkana Water Utilities reports 67,267 people, but only 34,004 LandScan people fall inside its polygon; the reported count probably includes the Texas side.
- Rural water associations report more customers than their modeled polygons contain.

Spreading that inflated count by area (A) pushes city customers onto empty fringe HUC12s. For example, HUC12 111403020707 has LandScan pop 2,381, but A assigns it 23,984 served. With A, the median HUC12 gets private-well pop = 0 and the upper tercile starts at about 2. That makes a 3-class map axis impossible. B is better but still gives zero for 81 of 141 HUC12s.

**Decision (recommended; the user can override):** make **C** the map variable and the headline. Report A and B in the output table and the summary as a sensitivity band. B is the low bound, since reported utility counts are over-inclusive. Describe C honestly: it measures "population living outside any mapped community-water-system service area", which is the standard proxy for domestic-well users. Its error runs the other way: C is **high** wherever modeled polygons under-cover rural water lines.

---

## 1. Inputs

| Input | Path | Notes |
|---|---|---|
| Study HUC12s | `outputs/intermediate/huc12_study.gpkg`, layer `huc12` (471 rows, `CRS_ALBERS`) | `HUC12` → `utils.zpad_huc12` |
| Analysis HUC12s | `outputs/huc12_lithium_impact.gpkg`, layer `huc12_impact` (141 rows) | Membership, plus `NAME` and `huc12_area_km2` |
| HUC12 population | `outputs/huc12_population.csv` (`HUC12, huc12_area_km2, population, pop_density`) | Reuse it. It already follows the LandScan rules (exactextract in 4326). |
| LandScan | `utils.LANDSCAN_TIF` (EPSG:4326) | **Never warp.** Reproject polygons to 4326 for extraction. |
| Service areas | `Z:/ek559/mining_wq/raw_data/CWS_Boundaries_Latest/EPA_CWS_V1/EPA_CWS_V1.shp` | **EPSG:3857.** Fields: `PWSID, PWS_Name, Primacy_Ag, Population, Service_Co, Method`. Add a `SERVICE_AREA_SHP` constant to `utils.py`. |
| Li concentration | `outputs/huc12_li_concentration.csv` (from 08) | Use `Li_p50_mean_mgL` for the map |

## 2. Script `code/10_private_wells.py`

Log with `print(..., flush=True)`. Structure: `main()` plus small helpers, in the style of 08.

**2a. Load and prep service areas**
```python
bb = tuple(gpd.GeoSeries([shapely.box(*huc12.total_bounds)], crs=CRS_ALBERS).to_crs(3857).total_bounds)
sa = pyogrio.read_dataframe(SERVICE_AREA_SHP, bbox=bb,
        columns=["PWSID", "PWS_Name", "Primacy_Ag", "Population", "Service_Co", "Method"])
sa = sa.to_crs(CRS_ALBERS)                       # areas only ever in Albers
sa["geometry"] = shapely.make_valid(sa.geometry.values)
sa = sa[~sa.geometry.is_empty].reset_index(drop=True)
sa = sa.rename(columns={"Population": "sa_pop_reported"})
sa["sa_area_km2"] = sa.area / 1e6
```
- Assert there are no duplicate PWSIDs. If a future data pull introduces any, dissolve them by PWSID and take the first population.
- Keep every polygon, whatever its state or source type. Do not filter to AR.
- Keep rows with a null or 0 population for C, which uses geometry only. Their `sa_pop_reported` is 0 in A and B. Log how many there are.

**2b. LandScan helper.** One function used everywhere:
```python
def landscan_sum(gdf) -> np.ndarray:
    g = gdf[["geometry"]].to_crs(4326).reset_index(drop=True)
    g["k"] = range(len(g))
    r = exact_extract(str(LANDSCAN_TIF), g, "sum", include_cols=["k"], output="pandas")
    return r.set_index("k")["sum"].reindex(range(len(g))).fillna(0).to_numpy()
```
Compute `sa["sa_pop_landscan"] = landscan_sum(sa)` and `sa["reported_to_landscan"] = sa_pop_reported / sa_pop_landscan.clip(lower=1)`. Write `outputs/intermediate/service_areas_study.csv` without geometry. It is the audit table for the inflation diagnosis.

**2c. HUC12 × service-area pieces**
```python
pieces = gpd.overlay(huc12[["HUC12", "geometry"]], sa[["PWSID", "geometry"]],
                     how="intersection", keep_geom_type=True)
pieces = pieces[pieces.area > 0]
pieces["piece_km2"] = pieces.area / 1e6
pieces["piece_landscan"] = landscan_sum(pieces)
pieces = pieces.merge(sa[["PWSID", "sa_pop_reported", "sa_area_km2", "sa_pop_landscan"]], on="PWSID")
pieces["served_area_wt"] = pieces.sa_pop_reported * pieces.piece_km2 / pieces.sa_area_km2           # A
pieces["served_pop_wt"]  = pieces.sa_pop_reported * pieces.piece_landscan / pieces.sa_pop_landscan.clip(lower=1e-9)  # B
```
Expect about 1,145 pieces. Write them without geometry to `outputs/intermediate/huc12_serviceareas_pairs.csv`.

**2d. Coverage union per HUC12 (for C)**
```python
cov = pieces.dissolve("HUC12")[["geometry"]]          # union of all SA inside each HUC12
cov["pop_in_service_area"] = landscan_sum(cov)
cov["sa_cover_km2"] = cov.area / 1e6
```

**2e. Assemble one row per study HUC12.** Start from `huc12_population.csv`, left-join the grouped sums and `cov`, and fill missing values with 0. Columns:
- `population`, `huc12_area_km2`, `n_utilities`, `sa_cover_frac = sa_cover_km2 / huc12_area_km2`
- `pop_in_service_area`, **`private_well_pop = max(population − pop_in_service_area, 0)`** (C, headline), `private_well_frac`
- `served_area_wt`, `private_well_pop_area_wt_raw` (A, may be negative), `private_well_pop_area_wt` (floored)
- `served_pop_wt`, `private_well_pop_pop_wt_raw` (B), `private_well_pop_pop_wt` (floored)
- `in_analysis` (bool, one of the 141 HUC12s)

`population − pop_in_service_area` can be slightly negative from float noise only, because both are exactextract sums on the same raster. **Assert it is ≥ −1** before flooring. A larger negative means a CRS or geometry bug.

Outputs:
- `outputs/huc12_private_wells.csv`
- `outputs/huc12_private_wells.gpkg`, layer `huc12_private_wells`, `CRS_ALBERS`

**2f. Summary: `outputs/private_wells_summary.md` and `.csv`**
- For the analysis 141 and the study 471: total population, and for each of A, B and C the negative count, zero count, floored sum and share. These should reproduce the §0 table to within rounding.
- Distribution of `reported_to_landscan` (median, 90th percentile, count > 2) by `Method`.
- The 10 most negative HUC12s under A, each with its top-contributing utility. Texarkana and Magnolia should appear.
- The share of `pop_in_service_area` that falls in State-supplied vs modeled polygons.
- The class breaks used for the map and the HUC12 count in each class.

## 3. Figure

**3a. Parameterise 08 without changing its output.** Give `pop_class`, `_legend_grid`, `draw_bivariate` and `make_single_map` keyword arguments with defaults equal to today's values:
- `pop_col` (default `POP_COL`)
- `pop_breaks` (default `POP_SERVED_BREAKS`)
- `pop_labels` (default the global `POP_LABELS`)
- `y_label` (default `"GW utility pop. served →"`)
- `title` (default `MAP_TITLE`)
- `notes` (default: output of `single_map_notes`)
- `source` (default: the current source string)

After editing, re-run 08. Confirm that `concentration_bivariate_summary.csv` is byte-identical: take `git stash` or a copy before the edit, then `diff`. Also eyeball `bivariate_p50_mean.png`.

**3b. In 10**, import 08 with `importlib.import_module("08_concentration_bivariate")`, the same way 08 imports 07. Set it up as follows:
- Merge `Li_p50_mean_mgL` onto the 141 analysis HUC12s.
- Add `PRIVATE_WELL_BREAKS = (75.0, 200.0)` to `utils.py`. These are near-tercile breaks for C: the 33rd and 67th percentiles are 71 and 199. Print the per-class counts and keep the breaks if every class has at least 35 HUC12s; otherwise adjust to round numbers and record the change in the summary.
- Labels: `["0–75", "76–200", f"201–{max:,.0f}"]`. Use the class rule 08 already uses: `<= lo`, `<= hi`, then above.
- y label: `"Private-well pop. →"`
- Title: `"Predicted watershed brine lithium and size of population relying on private wells"`
- Notes: "Private-well population is LandScan 2024 population living outside every mapped community water system service area (EPA CWS Service Area Boundaries v1). Lithium is the mean of the 50th-percentile cell estimates from Knierim et al. (2024) intersecting each HUC12."
- Source: `"Li: USGS Knierim et al. 2024 | HUC12: USGS WBD | Population: ORNL LandScan 2024 | Service areas: EPA CWS boundaries v1"`
- Save to `outputs/bivariate/bivariate_p50_mean_private_wells.png` (same figsize and dpi as 08).
- Also write `outputs/bivariate/private_wells_class_counts.csv`: HUC12 count and area for each Li class × private-well class.
- Open the PNG with Read and check that the legend and labels do not overlap, and that the high-Li, high-well corner is visibly used.

Do **not** make maps for A or B.

## 4. Docs

- `notes/methods.md`: add a "Private-well population" subsection. Cover:
  - Definition C and why A and B were rejected, citing the 2.3× median reported-to-LandScan ratio and the Texarkana example.
  - Albers areas.
  - LandScan handling.
  - Vintages: LandScan 2024, EPA SA v1 created 2024-06.
- `notes/interpretation.md`: add caveats:
  - LandScan is ambient, not residential, population.
  - 208 of 481 polygons are modeled, and rural water lines are under-drawn, so C over-states well users there. B (7.5 %) and C (16 %) bracket the analysis-area share.
  - Private wells are not in SDWIS, so there is no HUC12-level validation.
  - The service-area file is national, so LA, TX and OK HUC12s are handled the same way as AR ones.
- Do not edit the LaTeX writeup, and do not commit, unless asked.

## 5. Acceptance checks

- [ ] 471 rows, unique `HUC12`, no NaN in `population`, `pop_in_service_area` or `private_well_pop`.
- [ ] `private_well_pop` ≥ 0 everywhere, and the raw C difference is ≥ −1.
- [ ] §0 table reproduced: C analysis floored sum ≈ 33.6 k; A has 92 negatives and B has 81.
- [ ] 08 outputs are unchanged after the refactor.
- [ ] Map PNG written and visually checked.
- [ ] Only the venv interpreter from CLAUDE.md was used, and nothing was pip-installed.
