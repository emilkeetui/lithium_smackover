# Interpretation of the Smackover lithium-vs-population/CWS result

This note explains what the impact-tier split actually means — and, just as
importantly, what it does **not** mean. The point is to keep the paper's headline
number (**52.0% of median in-place lithium sits in high-impact HUC12s**) defensible.
See [methods.md](methods.md) for the pipeline and [implementation_plan.md](implementation_plan.md)
for the build log.

## What is being flagged

A HUC12 is **high-impact** if it fires any of:

| Screen | Source | Meaning |
|---|---|---|
| high population | LandScan 2024, threshold | HUC12 population > 10,000 or density > 100/km². |
| `in_sw_intake_huc` | SDWIS × SDWA, active CWS, `WATER_TYPE_CODE == 'SW'` | HUC12 contains an active community surface-water intake. |
| `in_gw_intake_huc` | SDWIS × SDWA, active CWS, `WATER_TYPE_CODE == 'GW'` | HUC12 contains an active community groundwater well. |
| `upstream_near` | WBD `TOHUC` graph, ≤2 hops from `I_sw` | HUC12 drains to a surface-intake HUC12 within 2 watershed hops. |

A HUC12 is **low-impact** only if it satisfies *none* of the above. "Low impact" is a
statement about which screens fired, not an assessment of consequence-free extraction.

## Why the resource axis is tonnage, not a permissibility rank

The sibling northern-Appalachian project weights its result by USGS permissive-tract
rank (High/Medium/Low), because for hard-rock pegmatites the open question is *whether a
deposit exists at all*. In the Smackover, lithium is known to be present in brine
throughout the formation — existence is not the question, quantity is. The USGS release
lets us compute **per-cell recoverable Li mass**, so the impact result is weighted by
actual in-place resource tonnage rather than by area or by a coarse likelihood rank. The
qualitative uncertainty class (`qualunc`) is retained only as a descriptive attribute
because it ignores reservoir volume — a thick, moderate-grade cell can hold more Li than
a thin, high-grade one.

## Why the headline uses a distance-limited upstream screen

Run with unlimited upstream propagation, "drains to a CWS surface intake" flags 140 of
141 analysis HUC12s (100% of tonnage) — a near-universal condition in CONUS, since
nearly every watershed eventually drains to *some* intake. That is not a finding, it is
a broken screen (the sibling project shows the identical pathology at 99.4%). The
headline instead uses `steps_to_sw_intake ≤ 2`: HUC12s within two watershed hops of a
surface intake. This is a threshold choice on attenuation-and-dilution grounds, not a
physical boundary, so the paper should present the full sensitivity table (k = 1, 2, 3,
5, 10, ∞) alongside the headline and state plainly that *every* Smackover watershed is
upstream of an intake at some distance — that fact belongs in the text as a finding, not
baked into the classifier as an unlimited constant.

## What "low impact" does NOT mean

1. **Not "no lithium beneath people."** The screen subtracts named, mappable
   conflicts — population density, CWS intakes, and nearby upstream drainage. It does
   not certify seismic, ecological, or other non-water impacts.
2. **In-place, not extractable.** No brine-recovery factor or DLE (direct lithium
   extraction) recovery efficiency is applied anywhere in the tonnage. Both factors are
   < 1 and roughly constant per cell, so they scale — and therefore cancel out of — the
   high-vs-low **percentage**, but the absolute tons quoted are never "reserves" or
   "extractable resource."
3. **A vertical-projection screen, not a demonstrated contamination pathway.** The
   Smackover Reynolds oolite sits roughly 3,500–11,300 ft below ground; drinking water in
   this region comes from the shallow (typically <1,000 ft) Sparta and Cockfield
   Coastal Plain aquifers. These are hydrologically distinct systems. Overlap in this
   analysis means *the resource is beneath people and their water supply* — i.e., where
   consequences of a failure would be realized — not that brine has migrated upward or
   that contamination is occurring today.
4. **The real DLE risks are not in this overlay.** Induced seismicity from brine
   reinjection, injection- and production-well integrity over decades of operation,
   surface spills of spent brine, and DLE's own freshwater demand are all real risk
   pathways for brine extraction that a static HUC12 population/intake overlay does not
   model.
5. **Private domestic wells are invisible.** SDWIS covers public water systems only.
   Rural south Arkansas has a substantial share of households on private wells with no
   record in this dataset — the groundwater-conflict footprint here is a **floor, not a
   ceiling**.
6. **CWS wells get the co-located HUC12 only — a proxy, not a delineated capture
   zone.** The WBD `TOHUC` graph encodes surface drainage, not aquifer flow, which can
   run in a different direction, cross HUC12 boundaries, or be decoupled entirely from
   the surface network in a confined aquifer. Flagging "upstream of a well" through the
   surface-flow graph would be neither hydrogeologically meaningful nor defensible, so
   the honest rule is: flag the HUC12 the well physically sits in, and document the
   limitation rather than fake an aquifer-flow model. Bounding groundwater risk properly
   would need wellhead-protection-area (WHPA) or MODFLOW-style capture-zone modeling,
   outside this analysis's scope.
7. **Population threshold is a knob, not a truth.** The default (population > 10,000 OR
   density > 100/km²) is calibrated for a rural study area; report the sensitivity grid
   at (5,000/50) and (20,000/200) alongside it rather than the single cutoff alone. In
   this rural setting the density knob and the groundwater-well screen do essentially
   all of the classifying — an absolute population-count threshold alone flags almost
   nothing.
8. **HUC12 resolution is coarse.** Analysis HUC12s here average roughly 96 km². A
   polygon adjoining a high-impact HUC12 but just outside its boundary may still sit
   over the same shallow aquifer or share a small tributary the HUC12 line doesn't
   follow. Site-specific siting decisions need catchment- or parcel-level hydrology, not
   this screen.

9. **Private-well population is a proxy.** It is LandScan *ambient* (not residential)
   population outside mapped service areas, not a count of well users. 208 of the 481
   service-area polygons are modeled (Random Forest / Decision Tree / Parcel) rather than
   state-supplied, and rural water lines are under-drawn, so the measure over-states well
   users where polygons under-cover real service. The lower-bound alternative B (7.5 % of
   analysis-area population) and the headline C (16 %) bracket the share. Private wells
   are not in SDWIS, so there is no HUC12-level validation. The service-area file is
   national, so LA, TX and OK HUC12s are treated exactly like Arkansas ones.

## Recommended paper framing

> Of the 11.3 Mt of median in-place lithium the USGS predicts in Smackover Formation
> brines (p50 grade, 20% porosity), **52.0%** sits beneath HUC12 watersheds that are
> densely populated, contain a community water-system intake (surface or groundwater),
> or drain within two watershed hops to a surface intake — leaving **48.0%** in
> lower-impact watersheds. This is a first-pass screen bounding where Smackover brine
> extraction could proceed with the lowest expected conflict against community drinking
> water and population centers — **not** a site-suitability map, **not** a statement
> that extraction in the remaining watersheds would be impact-free, and **not** an
> assessment of the seismicity, well-integrity, and spill risks that are DLE's most
> material hazards. Private domestic wells, within-HUC12 hydrologic connectivity, and
> the choice of upstream-distance threshold are each knobs or blind spots that a reader
> relying on this number should understand before treating "low impact" as "safe to
> mine."
