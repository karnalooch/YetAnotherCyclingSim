# SC-P01 — Roadside wall: readable planes and contact

[Review index](../README.md) | [Atlas contract](../../../tooling/SA_CALOBRA_SURFACE_DETAIL_ATLAS.md)

**AI_PROPOSED · owner review PENDING · physical identity PROVISIONAL · world mapping UNRESOLVED**  
Window 0103, local station 34.54702 m; not route chainage. `surface_id`, canonical `review_tags` and patch relationships remain unassigned.

## Original evidence

The near wall occupies much of the right-hand view. Its large planes, corners and road-side transition are readable. The reverse near wall may continue the same land-side formation; identity is not established.

Anchor: `window-0103-forward-00002` (forward, 1280 × 720).

![Unchanged original anchor](../frames/window-0103-forward-00002.png)

Paired station context: `window-0103-reverse-00002` (reverse). **Correspondence: possible_match**; this does not establish the same physical surface.

![Unchanged paired context](../frames/window-0103-reverse-00002.png)

## Proposed treatment

| Region | Band | Proposed tags | Required detail | Candidate omissions |
|---|---|---|---|---|
| Near wall | A | HERO_DETAIL;MATERIAL_TEST_CANDIDATE | Local planes, corners, shelves and convincing rock-ground contact; preserve broad shape and material scale. | Pores and tiny cracks may use material detail where they do not change the visible shape. No blanket wall simplification. |

## Approximate observation boundary

The following separate vector diagram marks an image ROI on the anchor, not a segmentation mask, physical boundary or PCGEx selector. Coordinates use unchanged 1280 × 720 pixels, top-left origin, x right/y down. Frame-edge truncation and intervening road/ground leave geometry unresolved.

![Approximate image ROI](../overlays/SC-P01.svg)

**Near wall (A):** `[[712,0],[1279,0],[1279,719],[1112,630],[980,533],[871,453],[783,396],[657,353],[483,330],[474,247],[545,184],[623,103]]`

## Google Street View reference

Both requested views are **NOT_INSPECTED**. Interactive panoramas could not be opened through the available web tool. No actual pano ID, imagery date, camera match or visual comparison is recorded. The link may select the nearest available panorama; it does not prove coverage.

[Anchor direction](https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=39.8325923%2C2.8129085&heading=320.785&pitch=-11.389&fov=76) · [Paired direction](https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=39.8325923%2C2.8129085&heading=140.785&pitch=-4.348&fov=76)

The request uses the road station; heading/pitch are orientation hints copied from the displaced native camera, not matched rays from the eventual panorama. The requested 76° FOV is not verified panorama calibration. The capture target is not the ROI surface position. Coordinate provenance and camera offset are in [proposal data](../surface-proposals.json). Compare landform outline, exposed rock forms, road-side contact and broad rock/soil/vegetation distribution after recording the actual panorama/date; temporary vegetation, lighting and capture materials can differ.

## Remaining review

Resolve physical ownership and matching appearances before defining a world footprint. Review closer views, other roads, look-around and indirect shadow/reflection contribution. No confirmed D surface, GEO_FIX or BACKGROUND_LOW_PRIORITY assignment is supported here. Human confirmation is required before populating the original review annotation fields.

Original anchor SHA-256: `fc5c66f6c747ce862545816eda59716e91c4610b91350d047d8ea2c4aa7d4588`. Paired SHA-256: `48c1936bc3671240ae98d109bb06999f6e4947a88dec920c10309b661891adfe`. [Complete provenance](../manifest.json).
