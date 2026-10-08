# SC-P06 — Sea-facing ridge and foreground banks are separate

[Review index](../README.md) | [Atlas contract](../../../tooling/SA_CALOBRA_SURFACE_DETAIL_ATLAS.md)

**AI_PROPOSED · owner review PENDING · physical identity PROVISIONAL · world mapping UNRESOLVED**  
Window 0077, local station 25.36397 m; not route chainage. `surface_id`, canonical `review_tags` and patch relationships remain unassigned.

## Original evidence

The small distant sea-facing ridge needs a coherent outline in this view. The forward frame contains close banks requiring A treatment; they are not the ridge and do not share its C proposal.

Anchor: `window-0077-reverse-00000` (reverse, 1280 × 720).

![Unchanged original anchor](../frames/window-0077-reverse-00000.png)

Paired station context: `window-0077-forward-00002` (forward). **Correspondence: context_only**; this does not establish the same physical surface.

![Unchanged paired context](../frames/window-0077-forward-00002.png)

## Proposed treatment

| Region | Band | Proposed tags | Required detail | Candidate omissions |
|---|---|---|---|---|
| Distant sea-facing ridge | C | SILHOUETTE_CRITICAL | Skyline, large divisions, broad colour structure and coherent apparent texture scale. | Fine interior geometry is unsupported in this view. BACKGROUND_LOW_PRIORITY is withheld until closer appearances and indirect contributions are reviewed. |

## Approximate observation boundary

The following separate vector diagram marks an image ROI on the anchor, not a segmentation mask, physical boundary or PCGEx selector. Coordinates use unchanged 1280 × 720 pixels, top-left origin, x right/y down. Frame-edge truncation and intervening road/ground leave geometry unresolved.

![Approximate image ROI](../overlays/SC-P06.svg)

**Distant sea-facing ridge (C):** `[[783,337],[817,310],[883,288],[944,288],[990,282],[1061,278],[1114,270],[1100,291],[1041,307],[1004,323],[912,331]]`

## Google Street View reference

Both requested views are **NOT_INSPECTED**. Interactive panoramas could not be opened through the available web tool. No actual pano ID, imagery date, camera match or visual comparison is recorded. The link may select the nearest available panorama; it does not prove coverage.

[Anchor direction](https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=39.8274153%2C2.8180242&heading=170.830&pitch=-7.024&fov=76) · [Paired direction](https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=39.8274153%2C2.8180242&heading=350.830&pitch=-8.741&fov=76)

The request uses the road station; heading/pitch are orientation hints copied from the displaced native camera, not matched rays from the eventual panorama. The requested 76° FOV is not verified panorama calibration. The capture target is not the ROI surface position. Coordinate provenance and camera offset are in [proposal data](../surface-proposals.json). Compare landform outline, exposed rock forms, road-side contact and broad rock/soil/vegetation distribution after recording the actual panorama/date; temporary vegetation, lighting and capture materials can differ.

## Remaining review

Resolve physical ownership and matching appearances before defining a world footprint. Review closer views, other roads, look-around and indirect shadow/reflection contribution. No confirmed D surface, GEO_FIX or BACKGROUND_LOW_PRIORITY assignment is supported here. Human confirmation is required before populating the original review annotation fields.

Original anchor SHA-256: `039cea8eb87ec9822580dfaa45a55be99f4901ee5e315a97fb2a22fff2aeafc3`. Paired SHA-256: `6ffb6fe1fcaf21c8b711994e27c11c2b50be78e359ab2e1f2160251a63c26a21`. [Complete provenance](../manifest.json).
