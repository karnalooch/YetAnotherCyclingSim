# Stage 3G R4.1 — Terrain / Landscape research playbook

**Status:** active working research for R4.1B  
**Scope:** Passo Giau DEM -> Unreal Engine 5.8 Landscape visual-quality diagnosis  
**Rule:** this document informs presentation only; route/physics truth remains independent.

## 1. Why this exists

The Passo Giau R4.1B spike has already proven the mechanical pipeline:

- official TINITALY source is downloaded deterministically;
- the source DEM is float32, 800x800 at 10 m;
- it is bilinearly resampled to a 1009x1009 Unreal candidate;
- little-endian R16 is produced deterministically;
- native `ALandscape::Import` succeeds;
- the result has 64 components in an 8x8 grid;
- the isolated map is persisted without mutating `L_CyclingTest`;
- deterministic 1920x1080 capture now succeeds.

The remaining problem is **visual diagnosis**, not "make CI green".

The current proof contains repetitive banding/step-like detail that is visually
unacceptable. R4.1B stays open until we can prove whether that pattern comes
from:

1. fallback material / shading;
2. source or conversion quantization;
3. import interpretation;
4. Landscape component/subsection boundaries;
5. renderer/LOD state;
6. actual source DEM resolution.

Do not hide the symptom with production materials, vegetation or post-processing.

## 2. Hard facts from Epic documentation

### Valid 1009 topology

Epic's Landscape Technical Guide lists **1009x1009** as a recommended size with:

- 63 quads per section;
- 4 sections per component (2x2);
- 126x126 quads per component;
- 64 components (8x8).

That matches the current R4.1B topology.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine

### Height precision and Z scale

Epic documents the Landscape height domain as approximately -256..+255.992
local height units stored with 16-bit precision, with the imported height then
scaled by Landscape Z scale.

Reference:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine

For our source relief:

- source min: 1171.353 m;
- source max: 2713.832 m;
- relief: 1542.479 m;
- encoded range: 65536 possible uint16 levels.

The ideal full-range vertical quantization is therefore approximately:

`1542.479 m / 65535 ~= 0.02354 m`

or about **2.35 cm per encoded level**.

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

## 3. Critical current observation: do not confuse material pattern with geometry

The current commandlet sets:

`Landscape->LandscapeMaterial = nullptr;`

That means the visual proof is not using an intentionally authored neutral
geometry-diagnostic material.

The current screenshot contains fine repetitive striping/herringbone detail
that can visually amplify or mimic height stepping. The silhouette also needs
inspection, but a lit screenshot with an engine fallback material is **not a
sufficient geometry verdict**.

### Required next A/B

Capture the exact same imported map and camera with:

1. **neutral no-grid lit material** — constant base color, controlled roughness,
   no texture pattern;
2. **neutral unlit/debug pass** — removes lighting as a source of apparent
   relief;
3. optional **wireframe/component-boundary pass** for topology inspection;
4. the current fallback-material proof retained only as a comparison.

Do not save diagnostic capture-only material overrides into the canonical map
unless the material becomes an explicit versioned R4.1 asset.

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
- component grid: 8x8.

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
- the proof remains 1920x1080 and deterministic;
- `L_CyclingTest` remains byte/hash protected;
- the owner/human review explicitly accepts the visual result.

Green CI remains necessary but is not visual acceptance.

## 9. Working hypothesis priority for the current screenshot

Investigate in this order:

1. **fallback material / shading false positive** — high priority because the
   current Landscape has no authored neutral diagnostic material;
2. **source/R16 numeric distribution** — verify instead of assuming;
3. **native-import vs manual-reader parity**;
4. **component/subsection boundary correlation**;
5. **actual DEM 10 m source limitation**;
6. renderer/Nanite only after the above.

This ordering minimizes destructive "fixes" and keeps the diagnosis falsifiable.

## 10. Source hierarchy

Prefer sources in this order:

1. Epic UE 5.8 documentation/API;
2. source code / reproducible engine behavior;
3. terrain-tool vendor documentation (Gaea / World Machine);
4. Epic Developer Community forum experience;
5. Reddit/community discussion only as symptom vocabulary or anecdotal hints.

Community advice is not an acceptance criterion unless reproduced in YACS.
