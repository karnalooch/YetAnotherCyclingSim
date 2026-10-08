# Sa Calobra original-PNG surface detail proposals — 2026-10-08

**Current scope:** Street View excluded by owner; use the [detail planning map](../sa-calobra-detail-planning-map-20261008/README.md).

**Status:** AI_PROPOSED; owner review and physical mapping pending. Six location cards, twelve unchanged original PNGs, seven approximate image-space regions.

Authority: [World Building Bible](../../WORLD_BUILDING_BIBLE.md), [surface atlas](../../tooling/SA_CALOBRA_SURFACE_DETAIL_ATLAS.md). Source: [TPP survey](../sa-calobra-tpp-survey-20261008/README.md). This is an evidence review, with no geometry/material changes or performance measurement. Accepted Component 230 v8 remains the baseline.

Open a card below on GitHub to inspect original PNGs and its separate outline diagram. The [offline interactive viewer](review.html) overlays vector ROIs on unchanged images when this directory is downloaded together. GitHub displays HTML source rather than executing it. [Machine-readable proposals](surface-proposals.json) and [provenance manifest](manifest.json) accompany the cards.

| Card | Requirement | Proposed tags | Google comparison |
|---|---|---|---|
| [SC-P01 — Roadside wall: readable planes and contact](cards/SC-P01.md) | A | HERO_DETAIL; MATERIAL_TEST_CANDIDATE | NOT_INSPECTED |
| [SC-P02 — Dominant massif above a separate close bank](cards/SC-P02.md) | B | SILHOUETTE_CRITICAL | NOT_INSPECTED |
| [SC-P03 — Close rock and broad slope need different scales](cards/SC-P03.md) | A / B | HERO_DETAIL; MATERIAL_TEST_CANDIDATE | NOT_INSPECTED |
| [SC-P04 — Dominant peak: protect faces as well as skyline](cards/SC-P04.md) | B | SILHOUETTE_CRITICAL | NOT_INSPECTED |
| [SC-P05 — Near bank and distant slope: preserve transitions](cards/SC-P05.md) | A | HERO_DETAIL; MATERIAL_TEST_CANDIDATE | NOT_INSPECTED |
| [SC-P06 — Sea-facing ridge and foreground banks are separate](cards/SC-P06.md) | C | SILHOUETTE_CRITICAL | NOT_INSPECTED |

## What this review establishes

Roadside walls/banks in 0103, 0168 and 0039 need readable local forms and contact. The 0132 massif and 0181 peak require broad faces and characteristic outlines. The 0077 distant ridge supports C treatment in that view, while its separate foreground banks still need A. Window 0181 is revised from the earlier thumbnail C proposal to B; all bands remain proposals.

Fine pores, grain and tiny cracks are candidates for material detail rather than uniform geometric finishing. No confirmed geometry defect, hidden D region or approved background simplification is assigned. Seven ROIs do not imply eight established physical surfaces or a complete A–D map. Diagnostic colours do not classify natural materials.

## Historical Street View links — excluded from current scope

The owner excluded Street View from this work. The following prepared-link record is retained as history; these comparisons are not required or scheduled.

Each card has two Google Maps Street View request links. All twelve views currently remain **NOT_INSPECTED**: the available web tool could not open interactive Google Maps panoramas. Links are prepared references, not completed comparisons or proof of imagery coverage. Actual pano IDs, imagery dates, positions, match distances and observations remain null.

Coordinates follow the existing frozen source mapping: `E = 483000.25 + X_cm/100`, `N = 4409516.25 - Y_cm/100` (EPSG:25831), transformed to EPSG:4326 using pyproj 3.7.2. The origin is recorded in `scripts/assets/prepare_sa_calobra_road_masks.py` and `scripts/assets/prepare_sa_calobra_cliff_erosion_handoff.py`; native centimetres and poses come from the survey CSV. Heading uses the WGS84 geodesic from camera to target; pitch is geometric. The requested viewpoint is the road station, about 5 m horizontally from the native camera. These orientation hints originate at the displaced survey camera, not at the eventual panorama. The requested 76° FOV is not panorama calibration; the capture target is not an annotated surface point. This follows existing source mapping, without independently proving capture-origin rebasing or geographic accuracy. It is a link-generation transform, not a physical surface mapping or precision claim.

Google chooses a nearby panorama when only `viewpoint` is supplied; camera position, height, imagery date and visible vegetation may differ. Before comparison, record the actual panorama ID/date/location, approximate direction and the road landmark used for alignment. Mark missing coverage or a weak match separately. Inspect skyline, large faces/ledges, road-side transitions and broad material distribution; do not infer geometry errors from lighting or temporary vegetation. Google imagery is not copied into this evidence directory. [Official Google Maps URL contract](https://developers.google.com/maps/documentation/urls/get-started).

## Provenance and next action

Twelve selected original PNGs were extracted through standard Git LFS byte-range reads and matched against captured sizes, dimensions and SHA-256 values. The whole 1.6 GB archive was not rehashed during this extraction; its earlier verified object identity is retained. The source CSV/template, original archive and viewing aids are unchanged. [Manifest](manifest.json).

Next: use the [detail planning map](../sa-calobra-detail-planning-map-20261008/README.md), resolve repeated physical appearances, and review the proposed detail requirements with the owner. Only reviewed world-mapped surfaces may enter a later PCG/PCGEx handoff under existing eligibility and protected-interface contracts. This review creates no executable selector and authorizes no whole-Landscape treatment.
