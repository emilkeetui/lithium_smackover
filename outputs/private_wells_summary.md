# Private-well population per HUC12 — summary

A and B are sensitivity bounds; **C is the headline** (LandScan people outside every mapped CWS service area).

| scope        | estimator               |   n_huc12 |   total_population |   n_negative |   n_zero |   floored_sum |   share_of_pop |
|:-------------|:------------------------|----------:|-------------------:|-------------:|---------:|--------------:|---------------:|
| analysis 141 | A area-weighted         |       141 |        209,655.502 |           92 |       92 |    53,429.794 |          0.255 |
| analysis 141 | B pop-weighted          |       141 |        209,655.502 |           81 |       81 |    15,643.909 |          0.075 |
| analysis 141 | C outside service areas |       141 |        209,655.502 |            0 |        3 |    33,609.665 |          0.160 |
| study 471    | A area-weighted         |       471 |        693,839.353 |          305 |      305 |   112,585.754 |          0.162 |
| study 471    | B pop-weighted          |       471 |        693,839.353 |          256 |      256 |    64,889.402 |          0.094 |
| study 471    | C outside service areas |       471 |        693,839.353 |            0 |       11 |   171,093.984 |          0.247 |

## Reported population / LandScan population inside polygon, by boundary Method

| Method        |      n |   median |    p90 |   n_gt2 |
|:--------------|-------:|---------:|-------:|--------:|
| Decision Tree |  10.00 |     6.19 |   9.70 |    8.00 |
| Parcel        |   1.00 |    27.16 |  27.16 |    1.00 |
| Random Forest | 197.00 |     5.36 | 180.28 |  143.00 |
| State         | 273.00 |     1.83 |   4.74 |  115.00 |

Overall median 2.31; 267 of 481 polygons above 2×.

## Ten most negative HUC12s under estimator A

|        HUC12 |   population |   served_area_wt |   private_well_pop_area_wt_raw | top_utility               |
|-------------:|-------------:|-----------------:|-------------------------------:|:--------------------------|
| 111403020707 |        2,381 |           24,101 |                        -21,720 | TEXARKANA WATER UTILITIES |
| 111403040303 |       18,280 |           29,124 |                        -10,843 | SHREVEPORT WATER SYSTEM   |
| 111402010201 |       10,508 |           16,815 |                         -6,307 | TEXARKANA WATER UTILITIES |
| 111402010204 |        2,994 |            9,001 |                         -6,008 | TEXARKANA WATER UTILITIES |
| 080402070201 |        9,009 |           14,946 |                         -5,936 | GOWC NORTH WATER SYSTEM   |
| 080402060907 |        2,120 |            7,725 |                         -5,605 | WEST HWY 80 ARK ROAD WS   |
| 080402070202 |       20,526 |           25,876 |                         -5,350 | MONROE WATER SYSTEM       |
| 080402060904 |        5,884 |           11,087 |                         -5,202 | FARMERVILLE WATER SYSTEM  |
| 111403020705 |       11,441 |           16,639 |                         -5,198 | TEXARKANA WATER UTILITIES |
| 111403020701 |        4,478 |            9,451 |                         -4,973 | MACEDONIA EYLAU MUD 1     |

## Where the service-area population sits (sum of piece LandScan)

State-supplied polygons: 337,145 (63.5%); modeled/other: 194,045 (36.5%).

## Map class breaks (analysis HUC12s)

Breaks (75.0, 200.0); classes ['0–75', '76–200', '201–2,272']; HUC12 counts [50, 45, 46].
