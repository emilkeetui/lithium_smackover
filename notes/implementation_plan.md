# Implementation plan — Smackover lithium vs. population & drinking water

**Handoff document.** Steps 0–6 are written, run, and validated; step 7 and the notes
are not. An implementing model should read §0 (environment), §10 (status), §11 (the one
open decision), then build §8–§9. Everything numbered below has been executed at least
once against real data — the numbers quoted are actual outputs, use them as regression
checks.

**Unit of analysis: HUC12.** Every headline number is a sum over HUC12 watersheds
classified high-impact vs. low-impact. The 2 km USGS model cells are an *intermediate*
used only to carry in-place lithium tonnage onto HUC12s without losing mass.

Mirrors `z:/ek559/Lithium_mining_US_northeast/code/`. Scripts 02, 03, 05 port closely;
01 was rewritten (raster → cells → tonnage), 04 was improved (national flow graph +
downstream distance), 06 re-aggregates to HUC12.

---

## 0. Environment — use the existing venv, by full path

No new environment is needed. Every script runs under:

```
"Z:/ek559/nys_algal_bloom/NYS algal bloom/code2/Scripts/python.exe" code/01_load_lithium.py
```

Never `python` / `python3` / `py` — those resolve to `C:\Program Files\Python314` or
`C:\ProgramData\anaconda3`, and **neither has a geospatial stack**. `run_all.py` must
invoke steps with `sys.executable` so launching the driver with this interpreter
propagates it.

Verified in the venv (Python 3.13.1): `geopandas` 1.0.1 · `rasterio` 1.4.3 ·
`shapely` 2.1.0 · `pyogrio` 0.10.0 · `pyproj` 3.7.1 · `exactextract` 0.3.0 ·
`networkx` 3.6.1 · `pandas` 2.2.3 · `numpy` 2.2.4 · `openpyxl` 3.1.5 ·
`matplotlib` 3.10.1.

Consequences for the code:
- **`rasterstats` absent** — irrelevant, everything uses `exactextract`.
- **`mapclassify` absent** — compute map bins with `numpy.quantile`, never
  `geopandas`' `scheme="Quantiles"`. The venv is shared with the NYS algal-bloom
  project; do not pip-install into it without asking.
- **GeoPandas 1.0 API** — use `gdf.geometry.union_all()`, not the removed
  `unary_union`; `gpd.overlay(..., keep_geom_type=True)`.
- Everything lives on a network share (`\\ccssbpp.file.core.windows.net\…`). Interpreter
  start-up is ~60–90 s cold. Scripts are slow to launch, not slow to run — do not
  mistake this for a hang, and give any run a generous timeout.

---

## 1. `utils.py` — constants  ✅ built

| Constant | Value | Note |
|---|---|---|
| `CRS_ALBERS` | literal WKT of the raster CRS | Albers EAC, lat_0 23, lon_0 −96, SP 29.5/45.5, WGS84, metres. Not `ESRI:102039` — the literal WKT makes the raster↔vector join exact. |
| `CRS_WGS84` | `EPSG:4326` | LandScan native. Never warp the raster. |
| `POROSITY_DEFAULT` / `POROSITIES` | `20` / `(10, 20, 30)` | percent |
| `GRADES` | `("p5", "p50", "p95")` | grade percentiles |
| `TON_MAIN` | `li_ton_p50_por20` | the headline resource measure |
| `STUDY_BUFFER_M` | `50_000` | HUC12 clip buffer |
| `POP_COUNT_THRESHOLD` / `POP_DENSITY_THRESHOLD` | `10_000` / `100.0` | per HUC12 |
| `POP_SENSITIVITY` | `((5k,50),(10k,100),(20k,200))` | reported grid |
| `TOHUC_SINKS` | `{OCEAN, CLOSED BASIN, CANADA, MEXICO}` | terminal nodes |
| `USGS_TOTALS`, `TONNAGE_TOLERANCE` | published totals, `0.001` | validation gate |

Helpers: `to_albers`, `to_wgs`, `assert_crs`, `zpad_huc12`, `norm_tohuc`, `ton_col`.
`zpad_huc12` matters — Excel drops leading zeros on 12-digit HUC codes, so every join
goes through it.

---

## 2. `01_load_lithium.py` — cells + in-place tonnage  ✅ built and validated

Reads the fishnet ([SAR_modeldomain_4269.shp](../sar_li/grid/SAR_modeldomain_4269.shp),
2,880 polygons, EPSG:4269), the nine 32×90 rasters, and `smackover_thick` from
[SAR_modeldomain_rasterstack.txt](../sar_li/input/exvars/SAR_modeldomain_rasterstack.txt).

Per cell, exactly as [4_SARLi_estimate.py](../sar_li/4_SARLi_estimate.py):

```
vol_L  = (thick_m*3.28) * (2000*3.28)**2 * 28.3168 * (porosity/100) * water_ratio
li_ton = vol_L * Li_mgL / 1e9
```

for 3 grades × 3 porosities = nine tonnage columns. We do **not** round per cell (the
USGS script does; that is the only source of disagreement).

**Alignment is verified, not assumed**: every one of the 2,880 cell centroids is
sampled against the p50 raster and compared to the row-major flattened array. It
matches exactly, so fishnet row *i* = flat index *i*. Keep this assertion.

**Validation gate — reproduced exactly:**

| porosity | p5 | p50 | p95 |
|---|---|---|---|
| 10 % | 5,079,612 (pub. 5,079,600) | 5,659,042 (5,659,046) | 6,346,861 (6,346,850) |
| 20 % | 10,159,225 (10,159,251) | **11,318,084 (11,318,086)** | 12,693,722 (12,693,716) |
| 30 % | 15,238,837 (15,238,848) | 16,977,126 (16,977,164) | 19,040,583 (19,040,582) |

Max relative deviation **2.6 × 10⁻⁶** — pure rounding. Any future change that moves
these numbers is a bug.

Other verified outputs: **2,524 valid cells** of 2,880, footprint **10,096 km²**,
every cell exactly 4.000 km²; per-cell p50/20 % tonnage min 124 t / median 3,612 t /
max 21,544 t; grade 13–389 mg/L (mean 109); thickness mean 73.6 m, max 122 m;
`qualunc` classes {0: 1315, 1: 170, 2: 163, 3: 876}.

→ `outputs/intermediate/lithium_cells.gpkg`, `study_area.gpkg`

---

## 3. `02_load_huc12.py` — clip WBD + cache the national flow table  ✅ built

`pyogrio.read_dataframe(WBD, mask=…)` with the dissolved domain buffered 50 km. The
national `.shp` is 1.9 GB; the spatial mask is what keeps this cheap. Column names are
resolved case-insensitively (`_resolve`) because WBD casing varies.

Also caches **the national HUC12 → TOHUC table** (`read_geometry=False`, 87,020 rows)
to `outputs/intermediate/huc12_tohuc_national.csv` for step 04.

Verified: **471** study HUC12s (46,653 km²), of which **141 intersect the lithium
footprint — those are the analysis rows**. Zero sink TOHUCs, zero empty TOHUCs.

---

## 4. `03_intake_hucs.py` — CWS intake HUC12s  ✅ built

The 2022Q2 crosswalk
([PWS_Loctations_HUC12_A_I_2022Q2.xlsx](../cws_intake_hucs/PWS_Loctations_HUC12_A_I_2022Q2.xlsx))
has 12 columns and **no `PWS_TYPE_CODE`**, so alone it cannot tell a community water
system from a campground's well. Joined on `PWSID` to
`Z:/ek559/sdwa_violations/SDWA_latest_downloads/SDWA_PUB_WATER_SYSTEMS.csv` (EPA
SDWA/ECHO, 2024Q4) to keep active `PWS_TYPE_CODE == 'CWS'` and to pick up
`POPULATION_SERVED_COUNT`.

Verified: 224,442 active facility rows → **100 % of PWSIDs match** the inventory →
**114,524 rows (51.0 %) survive the CWS filter**. Arkansas: 855 CWS facilities in 411
HUC12s (386 systems). **|I_sw| = 3,790**, **|I_gw| = 21,026** HUC12s nationally.

Population served is summed over *distinct systems* per HUC12 — a system with five
wells in one watershed must not count five times. The xlsx read is cached to
`outputs/intermediate/pws_facilities_active.csv` (openpyxl on 406 k rows is slow).

**Document the vintage mismatch**: crosswalk 2022Q2, inventory 2024Q4. Joining on
`PWSID` is stable; a system deactivated in between is caught by the 2024Q4
`PWS_ACTIVITY_CODE`, which errs conservative.

`cws_pop_served` is the project's only genuine **water-use** variable and answers a
different question from LandScan population (who *drinks from* a watershed's supply vs.
who *lives* in it). Both belong in the HUC12 table.

---

## 5. `04_upstream_hucs.py` — flow graph + downstream distance  ✅ built

Graph built from the **national** WBD table, not the clipped subset: the Ouachita and
Saline drain south into Louisiana and the Mississippi, so a Smackover HUC12 can sit
upstream of an intake far outside any buffer. Clip geometry, never the graph.

- 87,047 nodes / 87,020 edges; sinks terminal.
- `U_sw` from **one** reversed multi-source BFS off a super-source node, not 3,790
  separate `nx.ancestors` calls.
- The BFS depth is kept as **`steps_to_sw_intake`** — HUC12 hops to the nearest
  downstream CWS surface intake (0 = is one). This is what rescues the upstream screen;
  see §11.
- **No upstream propagation for `I_gw`** — the surface-flow graph is not an aquifer
  model; a CWS well contributes only its own HUC12.
- `W = I_sw ∪ U_sw ∪ I_gw`.

Verified: `|U_sw|` = 62,440, `|W|` = 71,502. 3.5 % of `I_sw` HUC12s are absent from the
CONUS graph (AK/HI/PR/tribal codes) — expected, and reported rather than silently
dropped. A worked example chain is printed and terminates in an intake HUC12.

→ `outputs/conflict_hucs.csv`

---

## 6. `05_population_by_huc.py` — LandScan  ✅ built

`exactextract` `sum` over the **native EPSG:4326** raster with HUC12s reprojected
*into* 4326. Density = `population / huc12_area_km2(Albers)`. ORNL's rules hold: never
warp the raster, never polygonize it, cell values are counts not density.

Verified: 471 HUC12s, **693,839** people (bbox window 1,257,674 — larger by
construction; the leak assertion is `poly ≤ bbox × 1.005`). Densest watersheds are
Upper Days Creek (66,052), Tupawek Bayou–Ouachita River (33,050), Upper Flat River
(32,292). `high_pop_huc` fires on **14 / 471** at the default threshold; the
sensitivity grid gives 36 / 14 / 5 HUC12s at (5k,50) / (10k,100) / (20k,200).

The strict ORNL centroid cross-check runs on the top-10 HUC12s and returns 237,727 vs
240,512 from `exactextract` — **1.2 % apart, as expected**, because `exactextract`
splits a boundary cell by area fraction while the centroid method assigns it whole.
That is agreement, not a leak. Keep both and report the difference in methods.

→ `outputs/huc12_population.csv`

---

## 7. `06_impact_dataset.py` — the HUC12 analysis table  ✅ built

**7a. Tonnage onto HUC12s without losing mass.** `gpd.overlay(cells, huc12,
how='identity')`, then apportion by area fraction
(`li_ton_piece = li_ton_cell × piece_area / cell_area`) for all nine tonnage columns
and for `h2o_prod_bbl_2022`. Verified: 2,524 cells → **4,336 pieces** across 141
HUC12s, tonnage loss **0.000 %**, area loss **0.000 %**. Keep both assertions.

> **Known warning to check, not ignore:** 513 identity pieces have no HUC12 and are
> dropped, yet area is conserved to 0.000 % — they are zero-area slivers on the
> footprint edge. If that warning ever appears alongside a nonzero area loss, the
> HUC12 clip is too tight.

**7b. Dissolve to one row per HUC12** (141 rows). Descriptive means are
**area-weighted**, so a sliver cannot outvote a whole cell. Fields:

| field | meaning |
|---|---|
| `HUC12`, `NAME`, `TOHUC` | identity |
| `huc12_area_km2`, `li_area_km2`, `li_frac` | watershed area, Smackover footprint inside it, ratio |
| `li_ton_p50_por20` | **primary resource measure** (in-place Li, metric tons) |
| `li_ton_{p5,p95}_por20`, `li_ton_*_por{10,30}` | grade and porosity uncertainty band |
| `li_ton_per_km2` | tonnage intensity, for the map |
| `Li_mgL_mean`, `Li_p50_mgL_mean`, `thick_m_mean`, `qualunc_max`, `h2o_prod_bbl_2022` | descriptive |
| `population`, `pop_density`, `high_pop_flag` (+ sensitivity columns) | LandScan residents |
| `cws_pop_served`, `n_sw_facilities`, `n_gw_facilities`, `n_sw_systems`, `n_gw_systems` | SDWA water use |
| `in_sw_intake_huc`, `in_gw_intake_huc`, `upstream_of_sw_intake`, `steps_to_sw_intake` | drinking-water screens |
| `n_reasons` (0–4), `impact_reasons` (`"gw_intake;upstream_sw"`) | decomposition |
| `impact_tier`, `impact_tier_direct` | classification (see §11) |

→ `outputs/huc12_lithium_impact.{gpkg,shp,csv}`, `outputs/intermediate/lithium_cells_split.gpkg`

> **Shapefile field names truncate to 10 characters** (`impact_reasons` → `impact_rea`,
> `impact_tier_direct` → `impact_t_1`). The `.gpkg` and `.csv` are authoritative; the
> `.shp` exists for ArcGIS users. Say so in methods rather than renaming fields.

### Verified results from the current run (141 analysis HUC12s)

- in-place Li carried onto HUC12s: **11,318,084 t** (p50/20 %) — conserved from step 01
- footprint 10,096 km² inside 13,531 km² of HUC12 area
- resident population **209,656**; CWS population served **198,684**

| screen | HUC12s | % of tonnage |
|---|---|---|
| population | 7 | 5.2 % |
| CWS surface intake in the HUC12 | 1 | 2.4 % |
| CWS groundwater well in the HUC12 | 58 | 48.2 % |
| upstream of a surface intake (any distance) | 140 | 97.6 % |

`n_reasons`: 79 HUC12s fire one screen, 59 fire two, 3 fire three.
Population sensitivity over the analysis rows: (5k,50) → 9 HUC12s / 8.1 % of tonnage;
(10k,100) → 7 / 5.2 %; (20k,200) → 1 / 0.3 %.

---

## 8. `07_summary_and_map.py` — TO BUILD

**Headline table** (`outputs/impact_summary.csv` / `.md`), rows = `impact_tier`,
columns: n HUC12s, `li_ton_p50_por20` and % of total, p5/p95 band, `li_area_km2` and %,
`population`, `cws_pop_served`, mean `li_ton_per_km2`. Headline sentence:

> Of the **11.3 Mt** of median in-place lithium predicted in Smackover brines
> (p50 grade, 20 % porosity), **X Mt (Y %)** lies beneath HUC12s that are populated,
> contain a community-water-system intake, or drain to one — leaving **Z Mt (W %)** in
> lower-impact watersheds.

Because porosity scales every cell identically, the **percentage is porosity-invariant**
— assert it (the 10 % and 30 % columns must reproduce the same %) and state it, so the
headline does not hinge on a guessed porosity. Do the same for the p5/p95 band: report
the % under each grade percentile.

Supporting tables, all of which the dataset already supports:
1. decomposition by `impact_reasons` — which mechanism does the work;
2. population-threshold sensitivity grid;
3. **`steps_to_sw_intake` sensitivity** — % of tonnage flagged at k = 1, 2, 3, 5, 10, ∞
   (this is the §11 decision made legible);
4. top 15 HUC12s by `li_ton_p50_por20` with their flags — the "which specific
   watersheds are the fight" table.

**Figures** (`outputs/`, matplotlib, `numpy.quantile` for bins — no mapclassify):
1. `impact_map.png` — HUC12s red (high) / green (low), Smackover footprint outline,
   CWS intake HUC12s marked, state/county lines, El Dorado / Magnolia / Camden labelled.
2. `tonnage_map.png` — HUC12s graduated by `li_ton_p50_por20` (quantile bins, display
   only), same overlay: where the lithium actually is against the conflict map.
3. `tonnage_by_tier.png` — stacked bar with the p5–p95 whisker.
4. optional `bivariate_map.png` — 3×3 tonnage × impact panel.

Basemap note: the sibling's `07` imports `pygris` for state boundaries. **`pygris` is
not installed here** and it downloads from the Census over the network. Either drop
state lines or source them from a local file; do not add a hard dependency on a
network fetch.

## 9. `run_all.py`, `notes/methods.md`, `notes/interpretation.md` — TO BUILD

`run_all.py`: linear driver, `subprocess` with `sys.executable`, fail fast, echo each
step's stdout.

`methods.md`: provenance, the tonnage formula and its validation against the published
totals, the CWS join and its vintage caveat, the flow-graph rule and the distance
threshold chosen in §11, the LandScan rules and the 1.2 % centroid cross-check, every
threshold.

`interpretation.md` — the sibling's caveats plus the brine-specific ones:
- **In-place, not extractable.** No brine-recovery or DLE-efficiency factor. Both are
  <1 and roughly constant across cells, so they cancel from the percentage — but never
  call this "extractable" or "reserves."
- **The screen is vertical projection, not a demonstrated pathway.** The Smackover sits
  3,500–11,300 ft down; drinking water comes from the shallow Sparta/Cockfield Coastal
  Plain aquifers. Overlap says *the resource is beneath people and their water*, which
  is where risk would be realized — not that contamination is occurring.
- **The real DLE risks are not in this overlay**: induced seismicity from reinjection,
  injection-well integrity, surface spills of spent brine, DLE's own freshwater demand.
- **Private wells are invisible** — SDWIS covers public systems only, and rural south
  Arkansas has many domestic wells. The GW footprint is a floor, not a ceiling.
- **CWS wells get the co-located HUC12 only** — a spatial proxy for a capture zone, not
  a model of one.
- **"Low impact" ≠ "no impact"** — it means none of these screens fired.

---

## 10. Status

| file | state |
|---|---|
| `code/utils.py` | ✅ built |
| `code/01_load_lithium.py` | ✅ built, run, tonnage validated to 2.6e-6 |
| `code/02_load_huc12.py` | ✅ built, run — 471 study / 141 analysis HUC12s |
| `code/03_intake_hucs.py` | ✅ built, run — CWS join at 100 % PWSID match |
| `code/04_upstream_hucs.py` | ✅ built, run — national graph + `steps_to_sw_intake` |
| `code/05_population_by_huc.py` | ✅ built, run — 693,839 people, cross-checked |
| `code/06_impact_dataset.py` | ✅ built, run — 141-row dataset, mass conserved |
| `code/07_summary_and_map.py` | ❌ **to build** (§8) |
| `code/run_all.py` | ❌ **to build** (§9) |
| `notes/methods.md`, `notes/interpretation.md` | ❌ **to build** (§9) |

Outputs currently on disk: `lithium_cells.gpkg`, `study_area.gpkg`,
`huc12_study.gpkg`, `huc12_tohuc_national.csv`, `pws_facilities_active.csv`,
`intake_hucs_sw.csv`, `intake_hucs_gw.csv`, `conflict_hucs.csv`,
`huc12_population.csv`, `lithium_cells_split.gpkg`,
`huc12_lithium_impact.{gpkg,shp,csv}`.

**Note:** `06` currently writes `impact_tier` and `impact_tier_direct` but does not yet
use `steps_to_sw_intake`. Whoever resolves §11 must add the distance-limited flag to
`06` and rerun it before building `07`.

---

## 11. The one real open decision — the upstream screen is degenerate

**The problem, with numbers.** Run as specified, the upstream screen flags **140 of 141**
analysis HUC12s and the tier collapses:

| tier definition | high | low | % of tonnage high |
|---|---|---|---|
| any screen (incl. upstream, any distance) | 141 | 0 | **100.0 %** |
| direct conflict only (population, SW intake, GW well) | 63 | 78 | **51.5 %** |

"Upstream of a CWS surface intake" is a near-universal condition in CONUS — nearly
every watershed drains to *some* intake eventually — so as a binary it carries no
information. A 100 % headline is not a finding, it is a broken screen. (The sibling
northern-Appalachian project has the same pathology: 99.4 % of High-rank tract area is
"high impact." Worth a sentence in the paper.)

**The fix, already instrumented.** `steps_to_sw_intake` from `04` makes distance the
discriminator. Across the 471 study HUC12s the distribution is genuinely spread —
median **6** hops, max **30**, none unreachable:

| within k hops | HUC12s (of 471) |
|---|---|
| 0 (is an intake HUC12) | 14 |
| ≤ 1 | 39 |
| ≤ 2 | 71 |
| ≤ 3 | 111 |
| ≤ 5 | 196 |
| ≤ 10 | 351 |

**Recommendation:** define `upstream_near = steps_to_sw_intake <= 2` for the headline
tier, report k = 1/2/3/5/∞ as a sensitivity row, and state plainly that *every*
Smackover watershed is upstream of an intake at some distance — that fact belongs in
the text as a finding, not in the classifier as a constant. k = 2 is defensible on
attenuation-and-dilution grounds and keeps the screen informative; k is a `utils.py`
constant so the sensitivity table is one loop.

**Alternatives if k feels arbitrary:** (a) report `impact_tier_direct` as the headline
and treat upstream purely as narrative; (b) restrict propagation to intakes within the
same HUC8/HUC4; (c) abandon the binary and rank HUC12s by a continuous score
(tonnage × people-at-risk), calling the top tercile "high." All three are supported by
the fields already in the dataset.

**Also settled:**
- Unit of analysis = HUC12.
- Python = the `nys_algal_bloom/code2` venv, by full path (§0).
- Water systems = real CWS filter via the SDWA inventory join (§4), with
  `cws_pop_served` carried as the water-use variable.
- Resource = **in-place** Li tons, p50 grade at 20 % porosity, p5/p95 and 10/30 % as the
  uncertainty band; the percentage split is porosity-invariant.
- Population threshold = 10,000 people or 100/km², with the sensitivity grid published.
- Tiering = binary for the headline, `n_reasons` (0–4) kept as a graded column.
