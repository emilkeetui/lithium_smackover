# Methods — Smackover lithium vs. population & drinking water

Unit of analysis: **HUC12**. Every headline number is a sum over HUC12 watersheds
classified high-impact vs. low-impact. The USGS 2 km model cells are an intermediate,
used only to carry in-place lithium tonnage onto HUC12s without losing mass. See
[implementation_plan.md](implementation_plan.md) for the full build log and regression
numbers; this note is the paper-ready summary.

## Data

- **Lithium resource**: Knierim, K.J., and others, 2024, *Lithium observations,
  machine-learning predictions, and mass estimates from the Smackover Formation brines
  in southern Arkansas*, USGS data release, https://doi.org/10.5066/P9QPRYZN. Machine-learning
  predicted Li concentration (mg/L) at the mid-point depth of the Reynolds oolite unit,
  p5/p50/p95 percentiles, on a 2,000 m fishnet (2,880 cells, 2,524 valid).
- **HUC12 watersheds**: USGS Watershed Boundary Dataset, CONUS pull 2020-10-26.
- **Community water system (CWS) intakes**: EPA SDWIS PWS↔HUC12 crosswalk (2022Q2)
  joined on `PWSID` to the EPA SDWA/ECHO bulk system inventory (2024Q4) to filter to
  active `PWS_TYPE_CODE == 'CWS'` and to recover `POPULATION_SERVED_COUNT`.
- **Population**: ORNL LandScan Global 2024, ~1 km ambient-population raster.

## Step 1 — in-place lithium tonnage per model cell

For each of the 2,524 valid fishnet cells, at grade percentile *g* ∈ {p5, p50, p95} and
porosity *φ* ∈ {10%, 20%, 30%}:

```
vol_L  = thickness_ft · cell_ft · cell_ft · 28.3168   (pore-space cell volume, liters)
       · (φ/100) · water:oil_ratio                     (-> brine volume)
li_ton = vol_L · Li_mgL(g) / 1e9                        (metric tons Li)
```

reproducing the USGS domain-total assessment
([`sar_li/4_SARLi_estimate.py`](../sar_li/4_SARLi_estimate.py)) exactly, cell by cell.
Fishnet-to-raster alignment (row-major, index *i* ↔ cell *i*) is verified by sampling
every cell centroid against the raster and checking exact agreement. Summed per-cell
tonnage reproduces the nine published USGS domain totals
([`SAR_smackover_Liestimate.csv`](../sar_li/output/SAR_smackover_Liestimate.csv)) to
within **2.6 × 10⁻⁶** relative error — the only discrepancy is that the USGS script
rounds tons to whole numbers per cell before summing and we do not. **20% porosity, p50
grade is the headline resource measure**; p5/p95 and 10%/30% porosity are carried as an
uncertainty band. The domain total is **11,318,084 t** in-place Li (p50/20%).

**In-place, not extractable.** No brine-recovery factor or DLE lithium-recovery
efficiency is applied — this is the total Li dissolved in the brine fraction of each
cell's pore space, not a reserves estimate. See
[interpretation.md](interpretation.md) for why this is the right resource measure for
this analysis and why it does not bias the headline percentage.

## Step 2 — HUC12s and the national flow graph

The national WBD HUC12 layer is clipped to the Smackover footprint buffered 50 km (to
catch downstream watersheds that drain out of the study area — the Ouachita and Saline
flow south into Louisiana). Of 471 study HUC12s, **141 intersect the lithium footprint**
and form the analysis rows. The HUC12→`TOHUC` attribute table is cached from the
**national** (unclipped) WBD layer — 87,020 rows — because clipping first would silently
drop upstream links to intakes far outside any buffer.

## Step 3 — community water system intakes

The 2022Q2 SDWIS PWS↔HUC12 crosswalk has no `PWS_TYPE_CODE` column, so on its own it
cannot separate a community water system from a school or campground well. Joined on
`PWSID` to the 2024Q4 SDWA/ECHO system inventory and filtered to active `PWS_TYPE_CODE
== 'CWS'`, **100% of crosswalk PWSIDs matched** the inventory and **51.0% of facility
rows survived** the CWS filter (removing non-community systems). Split by
`WATER_TYPE_CODE`: `I_sw` = HUC12s with an active CWS surface-water intake (intake,
reservoir, spring, infiltration gallery); `I_gw` = HUC12s with an active CWS groundwater
well. `cws_pop_served` (`POPULATION_SERVED_COUNT`, summed over distinct systems per
HUC12) is carried as the project's water-use variable, separate from LandScan resident
population.

**Vintage mismatch**: the HUC12 crosswalk is 2022Q2, the system inventory is 2024Q4.
Joining on the stable `PWSID` and applying the 2024Q4 `PWS_ACTIVITY_CODE` errs
conservative — a system deactivated between the two vintages is dropped.

## Step 4 — upstream propagation and the distance-limited screen

Surface-water intakes propagate upstream: a directed graph is built from the national
HUC12→`TOHUC` table, and `U_sw` is every HUC12 that is an ancestor of some HUC12 in
`I_sw` (single reversed multi-source BFS off a super-source node, not one traversal per
intake). Groundwater intakes do **not** propagate upstream — the surface-flow graph is
not a model of aquifer flow paths, so a CWS well contributes only its own HUC12 (a
conservative spatial proxy for its capture zone, not a delineated wellhead protection
area).

**Run with no distance limit, this screen is degenerate**: 140 of 141 analysis HUC12s
(100% of tonnage) sit upstream of *some* CWS surface intake at *some* distance, because
nearly every watershed in CONUS eventually drains to one. A 100% headline is not a
finding, it is a broken screen (the same pathology appears in the sibling
northern-Appalachian analysis, at 99.4%). The BFS depth — **`steps_to_sw_intake`**, HUC12
hops to the nearest downstream CWS surface intake — supplies the missing discriminator.
Across the 471 study HUC12s the distribution is genuinely spread (median 6 hops, max 30,
none unreachable), so distance separates "drains to a nearby intake" from "drains to
some intake eventually, six watersheds and dozens of kilometers downstream."

**Decision: the headline `upstream_near` screen is `steps_to_sw_intake ≤ 2`.** k=2 is
defensible on attenuation-and-dilution grounds (a spill loses concentration and gains
travel time with every additional confluence) and keeps the screen informative rather
than universal. This is a threshold choice, not a physical law, so the paper reports the
full sensitivity table (k = 1, 2, 3, 5, 10, ∞) alongside it — the headline percentage
moves from 51.5% (k=1, ≈ no upstream propagation at all) to 52.0% (k=2) to 100% (k=∞).
`impact_tier_direct` (population + SW intake + GW well, no upstream propagation at all)
is retained as an alternate, more conservative headline.

## Step 5 — population

LandScan is left in its native EPSG:4326 grid and never reprojected (ORNL's non-negotiable
rule — any warp resamples and leaks population). `exactextract`'s fraction-of-cell-weighted
`sum`, over HUC12 polygons reprojected *into* 4326, gives population per HUC12; density is
`population / huc12_area_km2` measured on the polygon in the equal-area Albers CRS, never
read off a raster cell. A "high population" HUC12 exceeds **10,000 residents or 100
people/km²** (either threshold; sensitivity reported at (5,000/50) and (20,000/200)). A
strict ORNL centroid cross-check (cell centers → points → spatial join, on the top-10
HUC12s by population) agrees with the `exactextract` fast path to within 1.2% — the
residual is `exactextract`'s correct area-fraction split of boundary cells versus the
centroid method's whole-cell assignment, not a leak.

## Step 6 — apportioning tonnage onto HUC12s

`gpd.overlay(cells, huc12, how='identity')` splits each 2 km cell at HUC12 boundaries;
every nine-column tonnage value (and 2022 brine production) is apportioned to each piece
by its area share of the parent cell. 2,524 cells become 4,336 pieces across 141 HUC12s
with **0.000% tonnage loss and 0.000% area loss** (asserted, not just reported). Rows
are then dissolved to one row per HUC12, with descriptive means (grade, thickness)
area-weighted so a boundary sliver cannot outvote a whole cell.

## Classification

A HUC12 is **high-impact** if it fires any of four screens: high population, contains a
CWS surface intake, contains a CWS groundwater well, or is within `UPSTREAM_NEAR_K` (=2)
hops upstream of a CWS surface intake. `impact_reasons` records which; `n_reasons` (0–4)
is the graded version. Everything else is **low-impact**.

## Headline result (current run)

| screen | HUC12s | % of median tonnage |
|---|---|---|
| population | 7 | 5.2% |
| CWS surface intake in the HUC12 | 1 | 2.4% |
| CWS groundwater well in the HUC12 | 58 | 48.2% |
| upstream (≤2 hops) of a surface intake | 3 | 0.6% |
| **any of the above (headline `impact_tier`)** | **65 / 141** | **52.0%** |
| direct conflict only, no upstream (`impact_tier_direct`) | 63 / 141 | 51.5% |

Groundwater wells do essentially all of the discriminating work here — expected for
rural south Arkansas, where much of the Gulf Coastal Plain depends on the Sparta and
Cockfield aquifers rather than surface intakes.

**The percentage is porosity-invariant by construction** — porosity scales every cell's
tonnage by the same constant and the tier is defined independently of tonnage (by
population/CWS/upstream flags only), so it cancels exactly out of a high-vs-low share.
`07_summary_and_map.py` asserts this (10%/20%/30% porosity reproduce the identical
52.02% split to floating-point precision) rather than merely stating it.

## Outputs

- `outputs/huc12_lithium_impact.{gpkg,shp,csv}` — one row per analysis HUC12 (141),
  every field described above (`.shp` field names truncate to 10 characters; `.gpkg`
  and `.csv` are authoritative).
- `outputs/intermediate/lithium_cells_split.gpkg` — the cell × HUC12 split layer, kept
  as the cartography source and audit trail.
- `outputs/impact_map.png`, `outputs/tonnage_map.png`, `outputs/tonnage_by_tier.png`.
- `outputs/impact_summary.csv` / `.md` — headline table, porosity/grade invariance
  checks, screen decomposition, population and upstream-distance sensitivity grids, top
  15 HUC12s by tonnage.

State boundaries on the map figures are drawn from a Natural Earth admin-1 shapefile
already on disk from the sibling project (`temp_ne_data/`) — no `pygris`/Census network
fetch, which is unavailable in this venv and which the plan explicitly avoids adding as
a hard dependency. Three anchor towns (El Dorado, Magnolia, Camden) are labelled from
hard-coded coordinates for reader orientation only.
