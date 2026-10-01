# Plan — Li concentration × HUC12 population density bivariate map

**For:** the implementing model (Sonnet). Read this file, then `code/08_concentration_bivariate.py`
and `code/utils.py` before writing anything. Follow `CLAUDE.md` → "Environment" exactly: run Python only as
`"Z:/ek559/nys_algal_bloom/NYS algal bloom/code2/Scripts/python.exe" <script>` from `code/`. Do not pip-install.

## Goal

Produce a figure identical in design to `outputs/bivariate/bivariate_p50_mean.png` (the paper's
`fig:bivariate_p50_mean`), with **only the vertical axis changed**:

| | Existing (08) | New (10) |
|---|---|---|
| x-axis (red) | HUC12 mean of p50 Li (mg/L), breaks `< 100 / 100–200 / ≥ 200` | **unchanged** |
| y-axis (blue) | `gw_utility_pop_served` — pop. served by GW-primary CWS with a well in the HUC12 | **`pop_density`** — LandScan 2024 residents per km² of the whole HUC12 |

Same 141 analysis HUC12s, same palette (`BIVAR`), same basemap, landmarks, state labels, legend
placement, figure size, dpi. Produce all six grade×stat variants plus the panel, like 08 does, but
`p50_mean` is the one the paper will use.

## Facts already verified (use as regression checks)

- `outputs/huc12_li_concentration.gpkg` (layer `huc12_li_conc`, written by 08) has all 141 HUC12s, the six
  `Li_{p5,p50,p95}_{median,mean}_mgL` columns, `population`, `huc12_area_km2`, and geometry (CRS_ALBERS).
  **It does not have `pop_density`**, but `population / huc12_area_km2` equals `pop_density` in
  `outputs/huc12_population.csv` to 1e-13 for all 141 rows (areas identical). 0 missing values.
- Σ `population` over the 141 HUC12s = **209,656**.
- `pop_density` over the 141: min 0.11, median 3.18, mean 15.5, max 621 people/km². Heavily right-skewed —
  equal-interval or the project's high-pop threshold (100/km²) would put almost everything in one class.

## Class breaks — decision

Add to `code/utils.py`, directly under `POP_SERVED_BREAKS`, with a comment in the same style:

```python
# Population density (LandScan 2024 residents / HUC12 Albers km²) for 11_density_bivariate.py:
# < 5 | 5–25 | >= 25 people/km². 25 ≈ Arkansas statewide density (~22/km²), so the top class
# is "at or above state-average density"; 5 splits sparse rural from small-town watersheds.
POP_DENSITY_BREAKS = (5.0, 25.0)
```

Expected counts over the 141 HUC12s: **90 / 39 / 12**. Assert this in the script (it is a regression check;
if the upstream data change, update the numbers deliberately, don't delete the assert).
Class rule: `< 5` → 0, `< 25` → 1, else 2 (half-open, lower-inclusive — note this differs from 08's
`<=` rule for population served; that's intended because density is continuous).
Legend labels: `"< 5"`, `"5–25"`, `"25–{max}"` — the top class shows a closed range up to the data's
maximum density, the same way 08 labels population served `"5,001–21,123"`. Build the breaks from the
constant and `max` from `df["pop_density"].max()`, rounded to a whole number (currently **621**, so
`"25–621"`). Like 08's `POP_LABELS`, `DENS_LABELS` therefore has to be set in `main()` once the data are
loaded, not at import time. Use the same labels in the summary CSV/MD.

## Implementation — new script `code/11_density_bivariate.py`

Do **not** modify 08's behaviour or outputs. Reuse its pieces via
`_m08 = importlib.import_module("08_concentration_bivariate")` (same trick 08 uses for 07), and
`_m07` for `_load_states`, `_landmark_points`, `_add_landmarks`.

Reuse from `_m08` unchanged: `BIVAR`, `LI_LABELS`, `li_class`, `value_col`, `ORDINAL`,
`panel_subtitle`, `_base_context_gw`, `STATS`.

Write locally in 10 (because 08's versions hard-code the population-served axis via the global
`POP_LABELS`, `POP_COL`, and the y-axis label):

1. `density_class(v)` using `POP_DENSITY_BREAKS`.
2. `DENS_LABELS` — module-level empty list, filled in `main()` from the breaks and the data maximum (see
   "Class breaks" above).
3. `_legend_grid(ax, rotate_x=0)` — copy of 08's, but y tick labels `DENS_LABELS` and
   ylabel `"Population density (people/km²) →"`. x-axis identical (`"Li in brine (mg/L) →"`).
4. `draw_bivariate(...)` — copy of 08's, colouring by `BIVAR[density_class][li_class]`.
5. `make_single_map` / `make_panel` — copies of 08's with these text changes only:
   - `MAP_TITLE = "Predicted watershed brine lithium and population density"`
   - Single-map notes: `"Notes: Predicted brine lithium values present in the watershed is the {stat}
     {ORDINAL} percentile estimates of brine lithium cell values from Knierim et al. (2024) intersecting
     watershed boundaries. Population density is LandScan 2024 ambient population in the watershed divided
     by watershed area. Watersheds are HUC12s."`
   - Source line (bottom right): `"Li: USGS Knierim et al. 2024 | HUC12: USGS WBD | Population: ORNL LandScan Global 2024"`
   - Keep the lower-right legend (model domain dashed, state boundaries).

`main()`:

1. Read `OUT / "huc12_li_concentration.gpkg"` layer `huc12_li_conc`; `assert_crs(df, CRS_ALBERS, ...)`;
   zero-pad `HUC12` with `zpad_huc12`. If the file is missing, raise with a message to run 08 first.
2. `df["pop_density"] = df["population"] / df["huc12_area_km2"]`.
3. Cross-check against `OUT / "huc12_population.csv"` (read `HUC12` as `str`, zero-pad): merge on HUC12,
   assert every row matched and `max |diff| < 1e-6`. Assert `len(df) == 141`, no NaN density,
   `round(df.population.sum()) == 209_656`.
4. Print density `describe()`, class counts per density class (assert `[90, 39, 12]`), and a 3×3
   crosstab of density class × Li class for `p50_mean`.
5. Write `OUT / "huc12_li_density.csv"` (no geometry): HUC12, NAME, huc12_area_km2, population, pop_density,
   density_class, the six Li columns, and `li_class_p50_mean`.
6. Write `OUT / "density_bivariate_summary.csv"` and `.md` mirroring 08's `class_summary` layout
   (raster, stat, li_class_mgL, density_class, n_huc12, huc12_area_km2, **population** summed — population
   is additive across HUC12s, unlike `cws_pop_served`, so a sum is valid here). Markdown: one pivot table
   per grade×stat, rows = density classes high→low, columns = Li classes; a short header paragraph stating
   the breaks and the density definition.
7. Figures to a new folder `OUT / "bivariate_density"`:
   `bivariate_density_{grade}_{stat}.png` (×6) and `bivariate_density_panel.png`.

Register in `code/run_all.py` after the "10" entry, in the same tuple format:
`("11", "11_density_bivariate.py", "HUC12 Li concentration × LandScan population density bivariate maps")`.

## Verification (do all, report results)

1. Run `11_density_bivariate.py` directly; all asserts pass.
2. Li-class counts for each grade×stat must equal those printed by 08 (the x-axis is shared) — compare
   against `outputs/concentration_bivariate_summary.csv` summed over population class.
3. Open `outputs/bivariate_density/bivariate_density_p50_mean.png` with the Read tool and compare to
   `outputs/bivariate/bivariate_p50_mean.png`: same extent, landmarks, state labels, legend position; legend
   y-axis reads `< 5`, `5–25`, `25–621` from bottom to top; no text overlaps. "City of El Dorado-Bayou de Loutre"
   (119/km²) and "Upper Days Creek" (621/km²) must be in the top density row.
4. The working tree already has uncommitted changes from other work (08, utils.py, run_all.py, main.tex,
   10_private_wells.py). Your diff must add only: one constant in `code/utils.py`, one line in `code/run_all.py`,
   new `code/11_density_bivariate.py`, new outputs, and (after the writeup step) the `main.tex` insertions
   plus `writeup/.../figures/bivariate_density_p50_mean.png`. Do not touch or re-run 08 or 10.

## Add the figure to the writeup

Do this only after the verification above passes. Writeup folder:
`writeup/Competition_for_space__water__and_lithium_brine_in_Arkansas/` (call it `W/`).

1. Copy `outputs/bivariate_density/bivariate_density_p50_mean.png` to `W/figures/bivariate_density_p50_mean.png`
   (a plain file copy; don't re-render).
2. In `W/main.tex`, section "Estimated brine lithium and drinking water utility customers", append one
   paragraph **after** the existing private-wells paragraph (the one starting
   `Figure \ref{fig:bivariate_p50_mean_private_wells} repeats ...`) and before `\printbibliography`:

   ```latex
   Figure \ref{fig:bivariate_p50_mean_density} repeats the classification using the residential population density of each watershed in place of drinking water users: the LandScan 2024 population in the watershed divided by its area. Density is grouped into fewer than 5, 5--25, and 25 or more people per km$^2$; 25 people per km$^2$ is close to the Arkansas statewide average.
   ```

3. In the "Tables and Figures" section, insert a new figure block **after** the private-wells figure's
   `\clearpage` and before `% ---------- Tables ----------`, matching the existing blocks exactly in form:

   ```latex
   \begin{figure}[H]
   \centering
   \includegraphics[width=\linewidth]{figures/bivariate_density_p50_mean.png}
   \caption{\raggedright Bivariate map of HUC12 watersheds by predicted Smackover Formation brine lithium concentration (mean across overlapping 2~km cells of the USGS 50th-percentile prediction raster) and population density, measured as LandScan 2024 population in the watershed divided by watershed area (people per km$^2$).}
   \label{fig:bivariate_p50_mean_density}
   \end{figure}
   \clearpage
   ```

4. Change nothing else in `main.tex`. It also carries Overleaf edits and other uncommitted work, so use
   targeted Edit insertions, never a full-file rewrite. If the anchor text above isn't found verbatim, stop
   and report rather than guessing a location.
5. There is no LaTeX toolchain check required. Just confirm by `grep` that the label is defined once and
   referenced once, and that the figure path exists.

## Out of scope unless the user asks

- Changing `POP_DENSITY_THRESHOLD` (100/km²) used by the impact tiering in 05–07 — that is a separate,
  already-decided screen; the bivariate breaks are display classes only.
- Committing. Leave changes uncommitted for the user to review.
