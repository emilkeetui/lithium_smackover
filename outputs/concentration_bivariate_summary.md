# HUC12 Li concentration × groundwater utility population served — class counts

Li breaks (mg/L): ['< 100', '100–200', '≥ 200']. Population-served breaks: ['0–1,000', '1,001–5,000', '5,001–21,123']. Each HUC12's Li value is the median or mean of every valid 2 km cell overlapping it (equal weight per cell).

**Population served counts groundwater utilities only.** A utility counts toward a HUC12's population served only if it has a well on file there *and* SDWA classifies its primary source as groundwater (`GW_SW_CODE == 'GW'`). Utilities with only a surface-water intake are excluded because they never appear in the groundwater facility list to begin with; utilities that do have a well on file but whose primary source is surface water — typically because they purchase most of their water from a surface-water-only utility — are excluded explicitly. See `08_concentration_bivariate.py` and `notes/methods.md`.

## p5 raster, median — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| 5,001–21,123       |       6 |         0 |       0 |
| 1,001–5,000        |      14 |        13 |       1 |
| 0–1,000            |      78 |        22 |       7 |

## p5 raster, mean — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| 5,001–21,123       |       6 |         0 |       0 |
| 1,001–5,000        |      14 |        13 |       1 |
| 0–1,000            |      74 |        27 |       6 |

## p50 raster, median — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| 5,001–21,123       |       6 |         0 |       0 |
| 1,001–5,000        |      12 |        13 |       3 |
| 0–1,000            |      69 |        26 |      12 |

## p50 raster, mean — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| 5,001–21,123       |       5 |         1 |       0 |
| 1,001–5,000        |      11 |        15 |       2 |
| 0–1,000            |      67 |        30 |      10 |

## p95 raster, median — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| 5,001–21,123       |       5 |         1 |       0 |
| 1,001–5,000        |      11 |        13 |       4 |
| 0–1,000            |      61 |        29 |      17 |

## p95 raster, mean — number of HUC12s

| pop_served_class   |   < 100 |   100–200 |   ≥ 200 |
|:-------------------|--------:|----------:|--------:|
| 5,001–21,123       |       5 |         1 |       0 |
| 1,001–5,000        |      11 |        13 |       4 |
| 0–1,000            |      60 |        34 |      13 |
