# Smackover lithium — impact summary

Of the **11.32 Mt** of median in-place lithium predicted in Smackover brines (p50 grade, 20% porosity), **5.89 Mt (52.0%)** lies beneath HUC12s that are populated, contain a community-water-system intake, or drain (within 2 hops) to one — leaving **5.43 Mt (48.0%)** in lower-impact watersheds.

## Headline table (by impact tier)

| impact_tier   |   n_huc12 |   li_ton_p5_por20 |   li_ton_p50_por20 |   li_ton_p95_por20 |   li_area_km2 |   huc12_area_km2 |   population |   cws_pop_served |   li_ton_per_km2_mean |   pct_of_ton_p50 |   pct_of_area |
|:--------------|----------:|------------------:|-------------------:|-------------------:|--------------:|-----------------:|-------------:|-----------------:|----------------------:|-----------------:|--------------:|
| high          |        65 |       5.33656e+06 |        5.88742e+06 |        6.50644e+06 |       4847.15 |          6472.4  |     179373   |           198684 |               1058.64 |            52.02 |         48.01 |
| low           |        76 |       4.82267e+06 |        5.43067e+06 |        6.18728e+06 |       5248.85 |          7059.04 |      30282.5 |                0 |                917.66 |            47.98 |         51.99 |

## Porosity invariance (% of tonnage in 'high' tier, p50 grade)

|   porosity_pct |   pct_tonnage_high |
|---------------:|-------------------:|
|             10 |             52.018 |
|             20 |             52.018 |
|             30 |             52.018 |

## Grade-percentile band (% of tonnage in 'high' tier, 20% porosity)

| grade   |   pct_tonnage_high |
|:--------|-------------------:|
| p5      |              52.53 |
| p50     |              52.02 |
| p95     |              51.26 |

## Decomposition by impact_reasons

| impact_reasons        |   n_huc12 |   li_ton_p50_por20 |   population |   pct_tonnage |
|:----------------------|----------:|-------------------:|-------------:|--------------:|
| none                  |        76 |        5.43067e+06 |     30282.5  |         47.98 |
| gw_intake             |        54 |        4.96551e+06 |     46842.9  |         43.87 |
| population;gw_intake  |         3 |   484382           |     31749.3  |          4.28 |
| sw_intake             |         1 |   269730           |      1017.1  |          2.38 |
| population            |         4 |   103988           |     99456.1  |          0.92 |
| upstream_sw           |         2 |    63275.7         |       118.71 |          0.56 |
| gw_intake;upstream_sw |         1 |      528.5         |       188.85 |          0    |

## Population-threshold sensitivity

|   count_threshold |   density_threshold |   n_huc12 |   pct_tonnage |
|------------------:|--------------------:|----------:|--------------:|
|              5000 |                  50 |         9 |          8.07 |
|             10000 |                 100 |         7 |          5.2  |
|             20000 |                 200 |         1 |          0.26 |

## Upstream-distance sensitivity (headline: k ≤ 2 hops)

| k_hops             |   n_huc12 |   pct_tonnage | is_headline   |
|:-------------------|----------:|--------------:|:--------------|
| 1                  |        64 |         51.51 | False         |
| 2                  |        65 |         52.02 | True          |
| 3                  |        74 |         61.14 | False         |
| 5                  |        88 |         71.6  | False         |
| 10                 |       118 |         82.2  | False         |
| inf (any distance) |       141 |        100    | False         |

## Top 15 HUC12s by median in-place lithium

|        HUC12 | NAME                        |   li_ton_p50_por20 |   li_area_km2 |   population |   cws_pop_served | impact_tier   | impact_reasons       |
|-------------:|:----------------------------|-------------------:|--------------:|-------------:|-----------------:|:--------------|:---------------------|
| 111402010404 | Lower Field Bayou           |             412294 |         120.5 |         94.1 |                0 | low           | none                 |
| 111402030110 | Holly Creek-Bayou Dorcheat  |             333339 |         145.8 |        734   |              290 | high          | gw_intake            |
| 111402030109 | Chaffin Branch-Big Creek    |             332765 |         114.1 |        806.5 |                0 | low           | none                 |
| 111402030201 | Kings Creek-Horsehead Creek |             283553 |         152.4 |        807.6 |             1145 | high          | gw_intake            |
| 111402010302 | Moccasin Bayou-Old Channel  |             276861 |         132.8 |        288.3 |              342 | high          | gw_intake            |
| 111402030105 | Beech Creek                 |             269730 |         127.6 |       1017.1 |            11355 | high          | sw_intake            |
| 111402050202 | Tatum Branch-Bodcau Creek   |             256027 |         126.4 |       2067.1 |             1633 | high          | gw_intake            |
| 111402030108 | Barlow Branch-Big Creek     |             252707 |          83.5 |      10194.8 |             1630 | high          | population;gw_intake |
| 111402010301 | Beech Creek-McKinney Bayou  |             247683 |         135.4 |       2232.2 |                0 | low           | none                 |
| 111402030107 | Nations Creek               |             234178 |          68   |       4693.2 |            11355 | high          | gw_intake            |
| 111402010303 | Fish Lake-Old Channel       |             224573 |          96.7 |        181.7 |                0 | low           | none                 |
| 111403020707 | Lower Days Creek            |             218527 |         109   |       2381   |                0 | low           | none                 |
| 111402010402 | Copeland Lake-Red River     |             216551 |          82   |         59.3 |                0 | low           | none                 |
| 111402050203 | Heirs Branch-Bodcau Creek   |             212718 |          96.6 |        152.5 |                0 | low           | none                 |
| 080402010301 | Mill Creek-Smackover Creek  |             190040 |         144.5 |        199.9 |                0 | low           | none                 |
