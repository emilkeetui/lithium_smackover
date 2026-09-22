# HUC12 Li concentration × groundwater utility population served — class counts

Li breaks (mg/L): ['< 100', '100–200', '≥ 200']. Population-served breaks: ['0', '1–1,000', '> 1,000']. Each HUC12's Li value is the median or mean of every valid 2 km cell overlapping it (equal weight per cell).

**Population served counts groundwater utilities only.** A utility counts toward a HUC12's population served only if it has a well on file there *and* SDWA classifies its primary source as groundwater (`GW_SW_CODE == 'GW'`). Utilities with only a surface-water intake are excluded because they never appear in the groundwater facility list to begin with; utilities that do have a well on file but whose primary source is surface water — typically because they purchase most of their water from a surface-water-only utility — are excluded explicitly. See `08_concentration_bivariate.py` and `notes/methods.md`.

## p5 raster, median — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| > 1,000            |      20 |        13 |       1 |
| 1–1,000            |      18 |         2 |       1 |
| 0                  |      60 |        20 |       6 |

## p5 raster, mean — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| > 1,000            |      20 |        13 |       1 |
| 1–1,000            |      15 |         5 |       1 |
| 0                  |      59 |        22 |       5 |

## p50 raster, median — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| > 1,000            |      18 |        13 |       3 |
| 1–1,000            |      12 |         6 |       3 |
| 0                  |      57 |        20 |       9 |

## p50 raster, mean — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| > 1,000            |      16 |        16 |       2 |
| 1–1,000            |      13 |         6 |       2 |
| 0                  |      54 |        24 |       8 |

## p95 raster, median — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| > 1,000            |      16 |        14 |       4 |
| 1–1,000            |      11 |         7 |       3 |
| 0                  |      50 |        22 |      14 |

## p95 raster, mean — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| > 1,000            |      16 |        14 |       4 |
| 1–1,000            |      11 |         8 |       2 |
| 0                  |      49 |        26 |      11 |
