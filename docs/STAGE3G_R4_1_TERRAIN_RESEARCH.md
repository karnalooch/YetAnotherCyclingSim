# Stage 3G R4.1 — Terrain / Landscape research playbook

**Status:** active working research for R4.1B  
**Scope:** Passo Giau DEM -> Unreal Engine 5.8 Landscape visual-quality diagnosis  
**Rule:** this document informs presentation only; route/physics truth remains independent.

## 1. Why this exists

R4.1B has now proven both the original bootstrap path and the higher-resolution
active Landscape path.

Historical merged baseline:

- TINITALY 1.1 / INGV, 800x800 at 10 m;
- deterministic 1009x1009 R16 candidate;
- licensed source/provenance and remote preparation proof on `main`.

Active PR #215 candidate:

- Regione del Veneto, `DTM 5 m derivato dai rilievi LiDAR`, IODL 2.0;
- 33 official tiles for the bounded Passo Giau AOI;
- native 1600x1600 working grid at 5 m;
- deterministic 4033x4033 unsigned-16 / little-endian R16 presentation grid;
- native `ALandscape::Import` succeeds;
- 32x32 components / 1024 components;
- the isolated map is persisted without mutating `L_CyclingTest`;
- source A/B run `36395015722` is GREEN;
- latest diagnostic authoring run `36399060374` is GREEN;
- deterministic 3840x2160 lighting-only / forced-LOD0 / FXAA capture succeeds.

The remaining problem is **visual interpretation and level-design use**, not
"make CI green".

The earlier 1080p proof contained dense repetitive herringbone/striping. The
4K/FXAA diagnostic substantially reduces that pattern while the source and
prepared 4033 hillshades remain natural. Screen-space aliasing was therefore a
real contributor.

Visible stepping/ribbing remains on very steep cliff faces. That residual is
now treated primarily as a heightfield/spatial-resolution representation
constraint until disproven, not as evidence that the uint16 encoding is broken.

Do not hide unresolved geometry with broad blur, production vegetation,
post-processing or Nanite.

## 2. Hard facts from Epic documentation

### Valid 4033 topology

Epic's Landscape Technical Guide supports the same 63-quad section /
2x2-subsection component pattern used by the current candidate.

For the active 4033x4033 Passo Giau Landscape:

- 63 quads per section;
- 4 sections per component (2x2);
- 126x126 quads per component;
- 1024 components (32x32);
- 4033 vertices per side = 32 * 126 + 1.

That matches the current R4.1B topology.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine

### Height precision and Z scale

Epic documents the Landscape height domain as approximately -256..+255.992
local height units stored with 16-bit precision, with the imported height then
scaled by Landscape Z scale.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine

For the active Veneto source proof:

- source min: 1168.833 m;
- source max: 2715.996 m;
- relief: 1547.163 m;
- encoded range: 65536 possible uint16 levels;
- prepared 4033 raster: 64756 unique uint16 values;
- exact-flat adjacent-sample share: about 0.026%.

The ideal full-range vertical quantization is therefore approximately:

`1547.163 m / 65535 ~= 0.02361 m`

or about **2.36 cm per encoded level**.

This is far smaller than the visually obvious large terraces in the current
proof. Therefore "16-bit is inherently too coarse" is **not** an acceptable
root-cause conclusion without additional evidence.

### Supported formats

Epic explicitly supports:

- 16-bit grayscale PNG;
- 8-bit r8;
- 16-bit r16.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/importing-and-exporting-landscape-heightmaps-in-unreal-engine

### Native import API

`ALandscapeProxy::Import` accepts imported height data as
`TMap<FGuid, TArray<uint16>>`.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Landscape/ALandscapeProxy/Import

The editor also exposes `FLandscapeImportHelper` and the Landscape file-format
interfaces. These are useful as an A/B oracle against our manual R16 reader.

References:

- https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/LandscapeEditor/FLandscapeImportHelper
- https://dev.epicgames.com/documentation/unreal-engine/creating-custom-landscape-importers-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/API/Editor/LandscapeEditor/ILandscapeFileFormat

## 3. Current observation: screen aliasing is separated from residual geometry

The commandlet still keeps production terrain materials out of the proof:

`Landscape->LandscapeMaterial = nullptr;`

The latest capture additionally enforces:

- Landscape LOD0;
- lighting-only view mode;
- proof sun shadows disabled;
- 3840x2160 spatial capture;
- deterministic high-quality FXAA.

Compared with the earlier 1920x1080 proof, the dense herringbone/striping is
substantially reduced. That is direct evidence that the old screenshot
overstated terrain defects because of screen-space/render aliasing.

What remains is concentrated on steep cliff faces: staircase/rib structures
that are plausible consequences of representing a steep 5 m DTM as a
single-valued Landscape heightfield. The 4033 grid is a presentation resample
to about 1.98 m/vertex; it does **not** create new measured detail beyond the
native 5 m source.

### Production trap: Landscape grid density is not source-data resolution

**Do not confuse the 4033x4033 Unreal Landscape grid with a 2 m measured DEM.**

For the current 8 km extent:

- 4033 Landscape vertices imply about **1.98 m/vertex** in Unreal;
- the authoritative Veneto DTM still contains measured terrain information at
  **5 m source spacing**;
- vertices introduced by resampling between native samples are interpolated;
- the denser Unreal grid improves editability, spline/patch shaping and
  representation of authored local changes, but it does **not** create new
  surveyed geological detail.

Consequences:

- never describe the active source as a "2 m DEM";
- never justify a full terrain restart solely because the UE grid is denser
  than the source;
- evaluate source sufficiency from visible macro-form errors that remain after
  the road-corridor and environment-art passes, not from vertex count alone;
- Nanite/LOD changes cannot manufacture source detail that was never measured.

This is a permanent production guardrail for R4.1 and later terrain work.

### Adopted terrain-detail hierarchy

The current production model is deliberately layered:

1. **Veneto 5 m DTM = macro terrain truth**
   - mountain massing;
   - ridges, valleys, passes and broad slope shape;
   - full 8 km x 8 km baseline.

2. **SP638 GIS spline + Landscape Splines/Patches = road-corridor engineering**
   - road bench;
   - uphill cut;
   - downhill fill/embankment;
   - shoulder transitions, drainage-scale shaping and hairpin cleanup.

3. **Static/Nanite meshes = non-heightfield geology**
   - vertical cliffs;
   - overhangs;
   - rock faces and retaining structures;
   - shapes that cannot be represented correctly by a single-valued Landscape
     heightfield.

4. **PCG/material dressing = near-field natural detail**
   - rocks and boulders;
   - scree;
   - grass, shrubs and trees;
   - slope/elevation/road-distance-driven distribution.

The base DEM is therefore not expected to be a finished cyclist-height scene.
A raw heightfield is the macro foundation, not the final environment.

### Higher-resolution source escalation rule

Do **not** replace the full Veneto 5 m baseline pre-emptively.

Consider a higher-resolution source (for example a local 1 m DTM/LiDAR patch)
only when all of the following are true:

1. the SP638 cut/fill corridor has been authored;
2. necessary cliff/rock geometry has been added;
3. material + scree/rock/vegetation dressing has been evaluated from
   cyclist-height cameras;
4. a specific bounded area still has a demonstrably wrong **macro shape**
   traceable to missing source data rather than missing environment art.

If that happens, prefer a **bounded local patch/replacement/mesh solution**
for the affected corridor or cliff instead of rebuilding the entire 8 km
Landscape.

This yields the production rule:

`good 5 m macro DTM + high-quality authored road corridor + local geological detail`

is preferred over

`globally denser DEM + untreated road corridor`.

### P0 diagnostic trap: independent road and terrain grids

Do not confuse Landscape vertex spacing with either source accuracy or source
alignment.

The SP638 road geometry and the Veneto DTM were measured independently. The
selected road source is in an approximately 4 m positional-accuracy class while
the canonical DTM is a 5 m raster. On steep Alpine slopes, that combination is
large enough that a small XY displacement can select materially different
terrain heights. A road of similar width to one DTM cell can also lie largely
between measured terrain samples.

Therefore:

- do not snap SP638 XY to DTM cells or Unreal Landscape vertices;
- do not treat a 4033-grid vertex (~1.98 m spacing) as a new measured terrain
  point;
- keep canonical road XY independent, sample/interpolate DTM Z continuously,
  and solve the rider-close road bench/cut/fill with local geometry;
- if a visual mismatch disappears only after moving the canonical road onto the
  terrain grid, treat that as a failed diagnostic, not a valid fix;
- any deliberate correction of canonical road XY requires separate evidence
  that the road source itself is wrong;
- do not estimate road curvature, tangent frames or road-cut widths from a
  sampling window smaller than the source-position uncertainty. Densifying the
  centerline to 2 m stations does not create 2 m positional truth. For the
  current proof, source-scale road geometry analysis uses a 6 m half-window
  while preserving every canonical centerline station unchanged.

This trap is especially important at tight hairpins, where local curvature,
road width, independent XY uncertainty and the 5 m terrain grid can all be on
the same spatial scale.

### Required next diagnostic only if R4.1D cannot cover the residual cleanly

1. capture a representative steep-face crop with wireframe/component boundaries;
2. check whether any repeated defect aligns with 63/126-quad boundaries;
3. compare the same location against the prepared 4033 hillshade/source samples;
4. use Unreal-native import-reader parity only if the evidence suggests a data
   interpretation defect.

Do not save diagnostic-only overrides into the canonical map.

## 4. Diagnostic ladder — run in this order

### A. Prove the source and R16 numerically

Add deterministic report fields for both source float32 DEM and prepared R16:

- unique-value count;
- min/max;
- smallest non-zero elevation delta;
- p50/p95/p99 adjacent-sample delta;
- count/share of exact flat plateaus;
- decoded R16 -> meters round-trip RMSE and max error;
- horizontal/vertical scanline samples through the visible problem area;
- slope histogram before and after resampling.

Acceptance principle:

- R16 round-trip error should stay on the order implied by the ~2.35 cm
  quantization step;
- visible meter-scale terraces must have a measurable source/data cause if they
  are real geometry.

### B. Compare our R16 reader with Unreal's own file-import path

Use `FLandscapeImportHelper::GetHeightmapImportDescriptor` /
`GetHeightmapImportData` (or the registered R16 file-format implementation)
to load the same file.

Compare the resulting `TArray<uint16>` byte-for-byte with
`ReadR16LittleEndian`.

Outcomes:

- identical -> our endian/row reader is not the cause;
- different -> stop and fix the importer contract before any art pass.

### C. Test component/subsection continuity

Epic's Landscape architecture duplicates shared boundary vertices between
components. Component boundaries are therefore a high-value diagnostic area.

For the current topology:

- subsection size: 63 quads;
- component size: 126 quads;
- component grid: 32x32.

Instrument seam probes around X/Y multiples of 126 and, separately, subsection
multiples of 63. Compare the source samples on both sides of each boundary and
look for periodic error correlated with the visible pattern.

A defect aligned exactly to 63/126 intervals is much more suspicious than
ordinary DEM detail.

### D. Neutral geometry capture

Only after A-C:

- force Landscape LOD0;
- keep camera, resolution and seed fixed;
- use no-grid neutral material;
- disable production decoration;
- capture lit and unlit/debug variants.

The geometry proof should read like the source hillshade at macro scale.

### E. Only then consider controlled preprocessing

Do **not** apply a broad Gaussian blur simply because a screenshot looks
terraced.

Community experience repeatedly identifies true 8-bit/poor-gradient data as a
cause of terracing, but experienced Unreal users also warn that indiscriminate
blur destroys terrain data and recommend diagnosing the data/source first.

Useful discussion:
https://forums.unrealengine.com/t/landscape-heighmap-blocky-even-grayscale-16bit-blur/1706783

If smoothing is ultimately justified, prefer a bounded, measured,
slope-aware/feature-aware operation with BEFORE/AFTER numerical and visual
evidence.

## 5. External terrain-tool guidance worth keeping

### Gaea

Gaea's Unreal output path explicitly auto-levels its 32-bit height data before
conversion to Unreal's 16-bit Landscape range so that the available 16-bit
precision is not wasted on unused headroom.

Reference:
https://docs.gaea.app/reference/nodes/output/unreal

This supports the current YACS strategy of mapping the useful DEM range across
the available uint16 domain.

### World Machine

World Machine's Unreal workflow recommends RAW16 and Unreal-compatible
Landscape resolutions.

Reference:
https://help.world-machine.com/topic/export-to-unreal-engine/

This is useful as an independent terrain-authoring reference, not as a reason
to replace the deterministic Python pipeline.

## 6. Do not use Nanite as a geometry-quality band-aid

Epic states that Nanite Landscape uses the same source Landscape data and users
should not expect a visual-quality improvement or downgrade merely from enabling
Nanite. It primarily changes rendering/performance behavior.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/using-nanite-with-landscapes-in-unreal-engine

Therefore:

- do not enable Nanite to "fix" terracing;
- first make the base Landscape geometry visually correct;
- evaluate Nanite later as an R5/R7 performance/rendering decision.

## 7. Material and level-design direction after geometry passes

Once the neutral proof is clean, switch from engineering diagnosis to level
design.

Epic Landscape Materials support layer-based blending and are appropriate for
the R4.1 material family.

References:

- https://dev.epicgames.com/documentation/unreal-engine/landscape-materials-in-unreal-engine
- https://dev.epicgames.com/documentation/unreal-engine/landscape-material-expressions-in-unreal-engine

R4.1 material order remains:

1. meadow / low vegetation base;
2. forest floor;
3. dirt / gravel;
4. exposed rock;
5. scree;
6. optional high-altitude snow.

Use slope/elevation/macroscale variation to support geological readability,
not to conceal broken terrain geometry.

## 8. Visual-debug acceptance gate

R4.1B Landscape path A is technically and visually acceptable only if:

- the neutral no-grid capture has no obvious periodic artificial terracing;
- no recurring defect correlates with 63/126-quad section/component intervals;
- Unreal-native R16 import data agrees with our deterministic reader, or any
  difference is understood and deliberately resolved;
- source -> prepared R16 round-trip error is measured and documented;
- the silhouette and major ridges agree with the source hillshade;
- the diagnostic proof remains 3840x2160 and deterministic;
- `L_CyclingTest` remains byte/hash protected;
- the owner/human review explicitly accepts the visual result.

Green CI remains necessary but is not visual acceptance.

## 9. Working hypothesis priority after the 4K/FXAA proof

Current evidence changes the priority order:

1. **steep-face heightfield / native 5 m spatial-resolution limit** — primary
   residual hypothesis; Landscape cannot represent overhangs and the 4033
   resample does not add measured terrain detail;
2. **component/subsection boundary correlation** — check only if the residual
   shows periodic alignment with 63/126-quad boundaries;
3. **native-import vs manual-reader parity** — keep as a fail-closed oracle if
   data interpretation becomes suspect;
4. **bounded meso cliff geometry** — use R4.1D Rock Face / cliff / scree assets
   for inspectable steep faces while keeping the DEM for macro massing;
5. **renderer aliasing** — proven to have contributed to the old 1080p
   herringbone, but no longer the main residual after 4K/FXAA;
6. **Nanite** remains a later performance/rendering decision, not a geometry
   repair.

Broad terrain smoothing is still rejected: it would destroy source structure
without addressing the core heightfield limitation.

## 10. Source hierarchy

Prefer sources in this order:

1. Epic UE 5.8 documentation/API;
2. source code / reproducible engine behavior;
3. terrain-tool vendor documentation (Gaea / World Machine);
4. Epic Developer Community forum experience;
5. Reddit/community discussion only as symptom vocabulary or anecdotal hints.

Community advice is not an acceptance criterion unless reproduced in YACS.
