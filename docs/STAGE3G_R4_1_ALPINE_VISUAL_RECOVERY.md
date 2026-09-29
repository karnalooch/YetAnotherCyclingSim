# Stage 3G R4.1 — Alpine Visual Recovery

**Status:** required before R5  
**Trigger:** R4 technical merge passed, post-merge human visual review rejected the rendered world as an acceptable Stage 3G visual closeout  
**Reference target:** owner-provided alpine-road reference image reviewed on 2026-09-28  
**Primary captures:** 1200 m / 4900 m / 8000 m  
**Reference performance target:** 1920×1080 / stable 60 FPS on RTX 2070 SUPER  
**Authoritative simulation/route source remains:** FRouteGeometryProfile / Road Physics Profile

## 1. Decision

Stage 3G R4 is retained as a valid technical integration milestone, but it is not the immutable visual baseline required to enter R5.

The current route-aware support surface solved an important grounding problem: PCG vegetation and rocks can follow a deterministic presentation surface without mutating route physics. It did not create enough macro- or meso-scale terrain structure to read as a convincing Alpine landscape.

R4.1 is therefore a bounded visual recovery pass before R5. It must improve world presentation without rewriting route physics, simulation ownership or Stage 4 cornering.

R5 remains blocked until R4.1 produces a human-accepted visual closeout and exact-SHA performance evidence.

## 2. Failure diagnosis

The merged R4 presentation surface uses one flat road corridor plus three rising bands per side. Current maximum support rise is approximately:

| Biome | Half-width | Max presentation rise |
|---|---:|---:|
| Valley | 110 m | +10 m |
| Forest | 60 m | +8 m |
| High Alpine | 220 m | +28 m |

This representation is useful for deterministic grounding but is too weak to represent Alpine macro terrain.

The reference scene succeeds at four spatial scales:

1. **Macro** — mountain ranges, valley walls, large ridges, skyline mass.
2. **Meso** — road cuts, cliffs, benches, steep local slopes, forested hillsides.
3. **Local** — boulders, roadside embankments, gravel shoulders, drainage and retaining forms.
4. **Micro** — grass, rubble, scree, small stones, surface breakup and vegetation transitions.

R4 currently covers parts of local/meso grounding but lacks enough macro terrain and material/atmospheric layering.

## 3. Visual target

R4.1 does not attempt to reproduce the full Stage 7 postcard scene. It must, however, belong clearly to the same visual family.

Required visual read:

- a mountain road embedded in terrain rather than a ribbon laid on a slab;
- large mountain masses occupying a meaningful part of the skyline;
- coherent valley -> forest -> high-Alpine progression;
- layered conifer forest instead of rows of repeated trees;
- ground materials that match each biome and hide obvious tiling;
- exposed cliffs, boulders, scree and rock clusters that feel geologically grounded;
- a readable asphalt/gravel/terrain transition;
- atmospheric depth from sky, cloud and fog systems;
- different visual identity at 1200 m, 4900 m and 8000 m without relying on the HUD.

R4.1 does not require the Stage 7 village, traffic, crowds, full roadside prop catalogue or final weather system.

## 4. Technology policy

### Keep

Preserve:

- native UE PCG;
- PCG_Valley;
- PCG_Forest;
- PCG_HighAlpine;
- PCG_RouteExclusion;
- deterministic WorldSpec / generation seed;
- editor-time generation and persistence;
- route/physics independence;
- Visual History and Performance History gates.

### Use in R4.1

**Geometry Script** may be used for deterministic presentation geometry:

- continuous/tiled terrain helper meshes;
- cliff or rock helper generation;
- slope/mask analysis;
- road-cut/retaining prototypes;
- mesh cleanup/analysis.

Generated persistent results must remain reproducible from versioned inputs.

**UE Landscape** gets a bounded A/B spike on one 300–500 m vertical slice:

- A: Landscape-based terrain;
- B: deterministic Geometry Script / generated tiled terrain mesh.

Choose based on visual result, authoring reliability, CI reproducibility, performance and future Stage 7 streaming compatibility. Do not migrate the whole route before this spike proves a clear win.

Use the native atmosphere stack:

- SkyAtmosphere;
- Volumetric Clouds;
- Exponential Height Fog;
- current Lumen lighting path.

### Defer

Do not use R4.1 merely to introduce:

- runtime PCG as an MVP requirement;
- full World Partition/HLOD production acceptance;
- DLSS/FSR/XeSS renderer integration;
- Frame Generation;
- large third-party world-generation frameworks;
- full Stage 7 settlement/traffic/life pass;
- Water/Landmass unless a specific accepted composition requires water.

## 5. Terrain architecture

The road is a constraint on the terrain, not the generator of the entire visible landscape.

Use route-local coordinates S = distance along route and D = signed lateral offset. A presentation height function may combine:

    H(S,D) =
        road_support(S,D)
      + macro_ridge(S,D)
      + valley_shape(S,D)
      + deterministic_terrain_noise(S,D)
      + biome_modifier(S,D)
      + local_features(S,D)

Rules:

- preserve a smooth road-support corridor;
- never derive authoritative grade/banking from rendered terrain;
- make left/right terrain intentionally asymmetric;
- allow one side to rise into a road cut while the other opens into a valley;
- expose slope and elevation masks to material/PCG consumers;
- author large forms first, then vegetation and local dressing.

### Spatial quality rings

| Distance from road | Goal |
|---|---|
| 0–25 m | high-quality road/shoulder/ground/hero detail |
| 25–100 m | medium-detail vegetation, boulders, cliffs |
| 100–300 m | forest mass and meso terrain |
| 300 m+ | silhouette, cheap mountain mass, atmospheric depth |

The MVP is a cycling corridor, not a free-roam walking simulator. Spend detail where the camera can inspect it.


### Hybrid production-terrain contract

R4.1 adopts a **hybrid production-terrain architecture**. One Landscape
heightfield is not expected to provide macro terrain, roads, cliffs, road cuts
and camera-close geological detail simultaneously.

This is an intentional production decision, not a temporary workaround.

Responsibilities are separated as follows:

- **MASE PST LiDAR DTM grigliato 1x1** -> canonical macro terrain skeleton,
  valley mass, ridges, mountain silhouettes and continuous ground;
- **Regione del Veneto LiDAR-derived DTM 5 m** -> reproducible fallback and
  A/B baseline;
- **official real-road GIS geometry** -> preferred presentation alignment for
  SP638 / Passo Giau;
- **UE Landscape** -> continuous macro terrain and terrain beneath vegetation;
- **Landscape Spline / non-destructive edit layer** -> road embedding, road
  cuts, embankments and bounded terrain adjustment;
- **road spline mesh** -> asphalt, markings and shoulder presentation;
- **Static Mesh / Geometry Script / PCG geometry** -> cliffs, overhang-like
  forms, road cuts, rock faces, hero rocks, rubble and scree where a heightfield
  is visually insufficient;
- **materials / RVT where justified** -> hide system boundaries rather than
  hide broken geometry;
- **FRouteGeometryProfile / Road Physics Profile** -> authoritative simulation
  truth until an explicit reviewed migration says otherwise.

The active 4033 x 4033 Landscape candidate is a presentation resample of the
MASE PST source after an explicit EPSG:4326 -> EPSG:32632 metric reprojection.
The UE grid improves Landscape topology compatibility; it does **not** create
measured terrain detail beyond the source samples.

#### P0 guardrail — SP638 / DTM spatial-grid trap

The official SP638 presentation centerline and the terrain raster are
**independent spatial measurements**. Their grids must never be treated as if
they share vertices or exact sample locations.

For the current Passo Giau sources, keep these scales explicit during review:

- official road geometry has metre-scale positional uncertainty (approximately
  the 4 m class documented for the selected road source);
- the canonical Veneto terrain source is sampled on a 5 m x 5 m grid;
- the prepared Unreal 4033 x 4033 Landscape is about 1.98 m/vertex, but those
  extra vertices are interpolated presentation samples rather than new terrain
  measurements.

On a steep slope or hairpin, shifting a road sample by only a few metres can
move it across materially different terrain elevations or even across opposite
sides of a road cut. A road roughly one DTM-cell wide can therefore fall between
terrain samples even when the final Unreal Landscape grid looks visually dense.

**Never snap the road centerline, road edges, or authoritative road XY to DTM or
Landscape vertices.** Preserve the canonical road XY, interpolate/sample terrain
Z continuously from the canonical DTM, and author the road bench, cut, fill,
embankment and rider-close tie-in as separate local presentation geometry.

Corollaries:

- 5 m DTM -> ~1.98 m/vertex Landscape resampling does not remove the original
  5 m source spacing;
- a denser Landscape cannot resolve disagreement caused by independent road and
  terrain sampling;
- local road/terrain mismatch is not evidence that the road should be warped to
  the Landscape grid;
- review any proposed terrain/road fix that changes canonical road XY as a
  **P0 architecture violation** unless a separately verified source defect is
  being corrected deliberately;
- never infer production curvature or local cross-section frames from a window
  smaller than the road source's positional-accuracy scale. Dense 2 m spline
  samples are useful mesh stations, not independent 2 m survey observations.
  R4.1B.3 therefore keeps those exact stations but estimates curvature/tangent
  frames over a 6 m half-window.

#### Real-road alignment policy

The Passo Giau road should be sourced from real GIS geometry instead of being
manually invented from the Landscape where reliable licensed data exists.

Preferred source hierarchy:

1. official Regione del Veneto road network for canonical presentation
   alignment;
2. OpenStreetMap only as optional QA/enrichment when useful and license
   obligations are understood;
3. manual correction only for a verified source defect or deliberate art
   direction.

The deterministic road pipeline should be:

    official GIS centerline
      -> crop to the Passo Giau AOI
      -> reproject to the terrain CRS
      -> canonical centerline snapshot + provenance/hash
      -> sample Z from the canonical DTM
      -> Unreal road spline
      -> bounded road cut / edit layer
      -> asphalt / markings / shoulder
      -> roadside dressing

Do not silently derive simulation grade, banking or cornering truth from the
rendered GIS/terrain pipeline.

#### Heightfield limitation policy

Landscape is the macro-terrain system, not a requirement to render every steep
surface as a heightfield.

Where the rider can inspect steep terrain and the heightfield exposes visible
stepping, ribbing, square structure or implausible road-cut geometry, use the
appropriate meso geometry instead of globally smoothing the DEM.

Preferred fixes include:

- Rock Face / cliff meshes;
- Geometry Script helper geometry;
- slope/composition-driven rock placement;
- rubble and scree;
- retaining / cut geometry;
- material blending at the Landscape/mesh boundary.

Do **not** blanket-scatter cliff meshes over the map. Detail follows visibility,
slope and composition.

#### Rider-camera acceptance gate

The production acceptance view is the moving cyclist camera, not an editor
top-down view and not a static technical Landscape proof.

A route segment is rejected if normal riding reveals obvious:

- Landscape component boundaries;
- square terrain tiles or grid structure;
- staircase / Minecraft-like terrain silhouettes;
- repeating heightfield ribbing at inspectable distance;
- a floating road;
- severe road/terrain intersection;
- exposed raw heightfield on a camera-close cliff that needs dedicated geometry.

If the player can perceive the terrain grid while riding, that segment does not
pass R4.1.

Do not solve this gate by globally blurring the DEM. Fix the local presentation
with the correct system: spline deformation, road-cut geometry, cliff meshes,
rocks, scree, vegetation, material blending or composition.

Nanite may later be evaluated for rendering/LOD benefits, but it is **not** a
source-detail recovery mechanism. It does not turn a 5 m DTM into high-resolution
geological geometry.

#### Production references

This architecture follows documented Unreal / procedural-environment practice:

- Epic Games — Landscape Splines:
  https://dev.epicgames.com/documentation/unreal-engine/landscape-splines-in-unreal-engine
- Epic Games — Landscape Edit Layers:
  https://dev.epicgames.com/documentation/unreal-engine/landscape-edit-layers-in-unreal-engine
- Epic Games — Nanite with Landscapes:
  https://dev.epicgames.com/documentation/unreal-engine/using-nanite-with-landscapes-in-unreal-engine
- SideFX — Procedural World Generation in Far Cry 5:
  https://www.sidefx.com/learn/talks/procedural-world-generation-far-cry-5/
- SideFX — Houdini Engine for Unreal Landscape workflow:
  https://www.sidefx.com/docs/houdini/unreal/landscape/index.html

## 6. Road integration

R4.1 road minimum:

- darker believable asphalt with fine normal/roughness variation;
- center dashed marking where appropriate;
- edge lines;
- roughly 0.5–0.9 m visual gravel shoulder where geometry allows;
- irregular gravel/dirt -> grass/rock transition;
- one simple European delineator;
- spline/procedural guardrail only where a drop-off or corner needs it;
- uphill-side road cuts where terrain rises;
- downhill-side open views/guarding where terrain falls.

If the road/terrain seam remains unacceptable after overlap + gravel transition, run a bounded RVT blending spike. RVT is not a default requirement.

## 7. Asset plan for R4.1

### Existing assets

**Sparse Grass** — valley/meadow terrain base. Use normal/roughness and macro variation. It is not the full meadow vegetation solution.

**Forest Ground 03** — forest-floor base under dense conifers with organic/dirt transitions and rock intersections.

**Rocky Terrain** — high-Alpine base blended with exposed rock, scree and sparse vegetation.

**Fir Sapling Medium** — validated mass-forest workhorse. Keep as the primary repeated conifer; use layered density and scale, not rows.

**Boulder 01** — hero/medium rock source. Rotate, vary scale, bury plausibly and prefer geological clusters over evenly spaced single props.

### Next source-asset priorities

**Rock Face 01 — highest next import/validation priority.**

Use for uphill road cuts, exposed cliff faces and high-Alpine meso terrain. Placement should be slope/composition driven, not broad random scatter.

**Grass Medium 01** — validate for near-road meadow/foreground clusters with aggressive density/cull control.

**Fir Sapling** — understory and meadow -> forest transition.

**Fir Tree 01** — do not use as the mass forest mesh. Run a source-isolation spike to import one practical variant only; if it passes, use sparsely as a hero conifer.

**Mountainside** — compare against cheaper generated/authored mountain mass. Adopt only when visual gain beats cost.

## 8. Material foundation

Create/extend one coherent terrain material family with layers for:

- meadow;
- forest floor;
- dirt;
- gravel;
- exposed rock;
- scree;
- optional high-elevation snow.

Required capabilities:

- macro color/value variation;
- distance tiling breakup;
- slope-aware rock/scree blend;
- optional altitude-aware snow;
- sensible normal/roughness intensity;
- world-aligned/triplanar strategy for steep rock/cliff surfaces where UV stretching is visible.

A lightweight height/slope/noise snow mask is preferred over a dedicated snow subsystem.

## 9. Forest composition

The goal is forest mass, not maximum tree count.

Use:

- low density nearest the road for readability;
- stronger primary canopy in the mid band;
- background forest mass farther from the road;
- understory/saplings at edges;
- deterministic clearings and view windows;
- transition ramps rather than hard biome switches.

Preferred progression:

    meadow -> saplings -> scattered fir -> dense canopy -> thinning alpine forest -> rock/scree

Long-distance foliage should not pay full near-field WPO/wind cost by default. Preserve distance-policy hooks for R5.

## 10. Rocks, cliffs and scree

Use three visual scales:

| Layer | Approximate scale | Purpose |
|---|---:|---|
| hero | 2–6 m | composition landmarks |
| medium | 0.5–2 m | geological grouping |
| rubble | 0.05–0.5 m | ground transition / scree |

Slope rules:

- steeper slope -> more exposed rock/cliff;
- cliff base -> higher rubble/boulder probability;
- high Alpine -> larger scree fields;
- meadow/forest -> sparser visible rock except at cuts/outcrops.

Floating or fully perched repeated boulders are a visual reject.

## 11. Mountains and skyline

R4.1 must establish:

1. detailed near/mid mountain mass;
2. cheaper far mountain mass;
3. distant skyline peaks.

The farthest layer may use aggressively simplified static geometry/materials because atmosphere supplies much of the depth cue.

Do not spend foreground-level shader/material complexity on distant peaks.

## 12. Atmosphere and lighting

Create one deterministic R4.1 art-direction setup for proof captures:

- clear/partly cloudy Alpine daylight;
- lower side-lighting rather than flat noon;
- readable cliff/tree shadow modelling;
- subtle valley fog;
- aerial perspective that reduces contrast with distance;
- no heavy LUT/HDRI dependency unless a BEFORE/AFTER test proves a real gain.

Weather variability remains Stage 8 work.

## 13. Scenic composition controls

Pure random scatter is not enough for hero views.

Plan a small data-driven scenic constraint layer such as DA_ScenicAnchors with:

- route distance S;
- preferred view direction;
- view-corridor width;
- hero landmark category;
- vegetation-clearance rule.

A future PCG view-corridor exclusion can keep important peaks or valley reveals readable.

Allow a small amount of deterministic hand-authored hero composition. Procedural generation should handle the majority of the corridor.

## 14. Canonical capture goals

### 1200 m — Valley golden vertical slice

This is the first R4.1 art-direction gate.

Must show:

- real-road presentation alignment where the official GIS spike has passed;
- road embedded in real terrain;
- believable shoulder;
- meadow foreground;
- scattered/transition conifers;
- grounded boulders;
- large mountain forms;
- atmospheric depth.

Do not spread the new system across 10 km until this slice is visually credible.

### 4900 m — Forest

Must show:

- layered canopy mass;
- forest floor;
- road readability;
- rock/terrain interaction;
- no repeated tree rows;
- controlled depth beyond the road corridor.

### 8000 m — High Alpine

Must clearly differ:

- sparse or absent forest;
- exposed rock/cliff;
- scree;
- high-Alpine ground;
- optional snow on high peaks;
- stronger skyline exposure and atmospheric depth.

## 15. Visual reject criteria

Reject the candidate if a canonical capture contains obvious:

- large empty flat slab;
- visible end of terrain support;
- geometric terrain bands;
- repeated rocks at regular spacing;
- floating vegetation/rocks;
- road/ground seam reading as unrelated systems;
- plantation-like tree rows;
- visible terrain texture tiling;
- empty skyline where mountain mass should exist;
- three biomes reading as the same environment with different density;
- insufficient atmospheric depth;
- hero vista blocked by uncontrolled PCG scatter;
- visible Landscape component/grid boundaries from the rider camera;
- square, staircase or Minecraft-like terrain silhouettes;
- camera-close steep faces exposing heightfield stepping/ribbing that should be meso geometry.

Green CI does not override visual rejection.

## 16. Performance policy

Hard gate remains:

- Frame p95 <= 16.667 ms;
- GPU p95 <= 16.667 ms;
- <= 5% frames above budget.

Development headroom target remains about 14 ms p95 where practical.

Spend budget in this order:

1. macro terrain/silhouette;
2. atmosphere/depth;
3. road/shoulder coherence;
4. forest composition;
5. cliffs/rock mass;
6. micro foliage only where the camera benefits.

Do not rescue poor composition with dense grass, excessive dynamic shadows or vendor upscaling.

## 17. Execution slices

1. **R4.1A — SSOT / visual rejection**
   Record R4 as technically merged but visually rejected/incomplete. Keep R5 blocked.

2. **R4.1B — 300–500 m terrain vertical-slice spike**
   Compare Landscape vs generated/tiled terrain; select one path.

2a. **R4.1B.1 — real-road alignment spike**
   Import a licensed official SP638/Passo Giau centerline into the same AOI/CRS
   as the Veneto DTM, sample presentation Z from the DTM, create a deterministic
   UE spline and prove road/terrain alignment before broad material dressing.

3. **R4.1C — terrain material foundation**
   Meadow / forest floor / rock / scree / gravel / optional snow.

4. **R4.1D — rock and cliff pass**
   Validate Rock Face 01; geological boulder clustering and scree.

5. **R4.1E — forest composition**
   Mass conifer + understory + optional hero conifer source-isolation proof.

6. **R4.1F — roadside minimum kit**
   Asphalt/markings/gravel shoulder/delineator/guardrail/road-cut logic.

7. **R4.1G — atmosphere and deterministic lighting**.

8. **R4.1H — propagate accepted language to 1200/4900/8000 and the full corridor**.

9. **R4.1I — Visual History candidate**
   Freeze exact SHA only when the owner accepts the visual result.

10. **R4.1J — exact-SHA performance + full closeout**
    Run performance evidence and one final heavy Stage 3G proof on the accepted tree.

## 18. External terrain / real-pass policy

Do not import a complete real-world pass merely to avoid building the YACS world pipeline.

A real DEM/heightmap may be used as:

- macro-terrain reference;
- source for a bounded terrain prototype;
- silhouette/massing inspiration;
- optional base heightfield adapted around the fictional YACS route.

Requirements:

- known license/provenance;
- documented coordinate/unit conversion;
- no coupling of physics truth to imported terrain triangles;
- deterministic import/conversion;
- reasonable source resolution and memory footprint;
- ability to simplify/retile for the corridor;
- visual proof that it beats project-generated terrain.

Preferred approach is hybrid: real-world terrain data provides strong macro forms and,
where licensed reliable GIS data exists, a real road centerline may drive the
**presentation alignment**. YACS still keeps route physics authoritative and
independent, while PCG biomes, materials, roadside dressing and art direction
remain project-owned. A presentation-road import must never silently replace
`FRouteGeometryProfile` or the Road Physics Profile.

## Current implementation status — Passo Giau terrain source (2026-09-28)

The R4.1 macro-terrain recovery has moved from source/bootstrap proof into an
isolated UE Landscape visual-debug spike. The original TINITALY work remains the
merged provenance/preparation baseline; PR #215 now carries the better-resolution
active Landscape candidate.

### Merged baseline on `main`

- PR #211 — `feat(assets): add Passo Giau DEM bootstrap` — **MERGED** as `7db3a63e11b83c3d33f86f80e1d6687c05b8ea78`;
- PR #212 — `feat(terrain): prepare Passo Giau R4.1 heightmap pipeline` — **MERGED** as `a98162fd590c5d3dc597a5c625d70e9860bb46c7`;
- baseline source: **TINITALY 1.1 / INGV**, CC BY 4.0;
- baseline AOI: approximately **8 x 8 km around Passo Giau**;
- baseline source grid: **800 x 800 at 10 m**;
- baseline source DEM SHA-256:
  `9a58a8aca8b1856507b4ca3e656f8c975518cbd89bd273036ef2483c148db610`;
- preparation run **36357523138 — GREEN**;
- baseline UE candidate: **1009 x 1009**, XY **793.651 cm/vertex**.

This baseline proved licensed remote source acquisition and deterministic Unreal
heightmap preparation. It is historical evidence, not the currently preferred
Landscape source.

### Active PR #215 candidate — MASE PST LiDAR DTM 1x1

PR #215 now uses the corrected MASE PST Passo Giau source checkpoint as its
canonical terrain input. The earlier `1372707` / 89-tile checkpoint is
superseded; package `1372858` is DTM-only and contains 204 GeoTIFFs.

Current source contract:

- release tag: `data-mase-pst-passo-giau-dtm-2026-09-28`;
- archive size: **853,162,557 bytes**;
- archive SHA-256:
  `4215d1d37fb8540c44442aedd164b6cda3f1845f3552413a975a6b7b1461e93c`;
- **204** GeoTIFF DTM tiles, all `*_DTM.tiff`, zero DSM tiles;
- Float32, source-defined tile dimensions (the pinned package is heterogeneous; fixed 1000 x 1000 dimensions are not part of the contract), NoData `-9999`;
- source CRS **EPSG:4326**;
- observed source pixel spacings `0.00001 degrees` and `0.000005 degrees`; the corrected package mixes 1000- and 2000-sample tiles, so spacing is validated against this pinned fail-closed set before reprojection;
- target working CRS **EPSG:32632**;
- target working grid **8000 x 8000 at 1 m** over the bounded 8 km AOI;
- prepared UE Landscape target **4033 x 4033**;
- topology remains **32 x 32 components = 1024 components**;
- XY scale remains **198.412698 cm/vertex**;
- isolated map only: `/Game/Prototype/Maps/L_PassoGiauTerrainSpike`;
- `L_CyclingTest`, route truth and physics remain protected and unchanged.

The raw archive stays outside Git/LFS as an immutable prerelease checkpoint.
The authoring lane verifies byte size and SHA-256 before extracting the 204
GeoTIFFs. It then mosaics them and performs an explicit geographic-to-metric
reprojection. Degrees are never interpreted as metres.

The older Veneto 5 m candidate remains valuable historical evidence:

- source A/B run **36395015722 — GREEN**;
- first complete Veneto UE authoring run **36395726623 — GREEN**;
- diagnostic authoring run **36399060374 — GREEN**;
- the 5 m proof established the current 4033 topology, native
  `ALandscape::Import`, mutation guards and deterministic 4K/FXAA geometry
  capture contract.

Those runs do **not** prove the new MASE source path. A fresh exact-SHA
authoring/render run is required before visual acceptance.
### Current visual conclusion

The existing Veneto 5 m proof remains the comparison baseline. Its source and
prepared 4033 raster do **not** show the dense herringbone
pattern seen in the earlier 1080p UE proof. The 4K/FXAA diagnostic substantially
reduces that artifact, which identifies screen-space/render aliasing as a real
part of the earlier failure.

Steep cliff faces still show visible heightfield stepping/ribbing in perspective.
That remaining limitation should not be hidden by blur or by pretending 16-bit
precision is the cause. The data uses nearly the full uint16 domain and the
measured vertical quantization step is only about **2.36 cm**.

### Priority source discovery — `DTM_2m_Cortina` (2026-09-28)

The terrain-source decision changed after new official-source research.

Regione del Veneto commissioned a dedicated aerial photogrammetry + LiDAR survey
covering Cortina d'Ampezzo and the neighboring municipalities **Colle Santa
Lucia, Borca di Cadore, Selva di Cadore and San Vito di Cadore**. The official
procurement specifies **4 LiDAR points/m²** and production of both DSM and DTM
products.

Official source:
https://bur.regione.veneto.it/BurvServices/Pubblica/DettaglioDgr.aspx?id=426837

The Veneto geoportal currently exposes a layer named **`DTM_2m_Cortina`**.
That layer is now the priority candidate for a source-resolution A/B over the
Passo Giau / SP638 AOI.

Geoportal:
https://idt2.regione.veneto.it/idt/webgis/viewer?webgisId=246

The existing harmonized regional DTM remains the proven baseline and is
officially published with **5 m cells**:
https://idt2.regione.veneto.it/nuovo-dtm-derivato-da-dati-lidar/

This matters because the current 4033 x 4033 Landscape over ~8 km has about
**1.984 m/vertex**, but the existing source still contains measured terrain only
at 5 m spacing. A verified 2 m DTM would make the source sampling scale closely
match the UE Landscape vertex spacing instead of merely interpolating a coarser
surface.

For reference:

- current 2017 candidate: `8000 / 2016 ~= 3.968 m/vertex`;
- target 4033 candidate: `8000 / 4032 ~= 1.984 m/vertex`;
- Epic explicitly lists **4033 x 4033** as a recommended Landscape size.

Epic reference:
https://dev.epicgames.com/documentation/unreal-engine/landscape-technical-guide-in-unreal-engine

### Geospatial pipeline decision

**QGIS/GDAL becomes the master preprocessing layer for YACS world data.**

The intended pipeline is now:

`official DEM -> QGIS/GDAL Float working raster -> one CRS/resample step -> final Float DEM -> UInt16/R16 transport -> Unreal Landscape`

Rules:

- keep the source DEM immutable;
- keep elevation in Float32/Float64 through crop/reprojection/resampling;
- use one metric CRS for terrain, SP638, orthophoto and future world masks;
- prefer **EPSG:7795 / RDN2008 Zone 12 (E-N)** as the working candidate when
  consistent with downloaded source metadata;
- do not render QGIS imagery and reuse it as height data;
- perform at most one deliberate reprojection/resample;
- test `cubic` and `cubicspline` for elevation rather than chaining arbitrary
  resize operations;
- convert to UInt16 only at the Unreal transport boundary;
- choose elevation min/max deliberately with documented headroom;
- preserve SP638 XY independently from the raster grid.

GDAL supports explicit target resolution and resampling algorithms:
https://gdal.org/en/stable/programs/gdalwarp.html

GDAL UInt16 range mapping:
https://gdal.org/en/stable/programs/gdal_translate.html

For the 8 km / 4033 target:

`XY Scale ~= 198.412698 cm`

For an encoded vertical range `R` metres:

`Z Scale = R * 100 / 512`

per Epic's Landscape height-domain contract.

### P0 next experiment — 5 m vs real 2 m

Do **not** continue adding terrain art, runtime smoothing or local replacement
skins until this source-resolution experiment is complete.

Build two otherwise identical neutral Landscape proofs:

1. **Baseline A**
   - current harmonized Veneto 5 m DTM;
   - 4033 x 4033;
   - same AOI;
   - same UE import path;
   - same forced LOD / lighting-only camera.

2. **Candidate B**
   - verified `DTM_2m_Cortina`;
   - same physical AOI;
   - QGIS/GDAL deterministic preprocessing;
   - 4033 x 4033;
   - ~1.984 m/vertex;
   - same UE import path and camera.

No production material, foliage, rocks, cliff meshes, procedural noise,
road cut/fill or runtime terrain-skin replacement is allowed in this A/B.

Interpretation:

- if B removes or dramatically reduces the Minecraft-like faceting, the
  horizontal resolution of the source is confirmed as the dominant problem and
  the 2 m DTM becomes the macro-terrain candidate;
- if B looks materially the same, investigate Landscape triangulation, LOD and
  importer behavior before resuming art work.

The current 16-bit path remains unlikely to be the root cause because the
measured vertical quantization is already centimetric.

### Status of the R4.1B.3 local terrain-skin experiment

The R4.1B.3 world-aligned rider-close terrain-skin path reached technical green:

- deterministic kernel tests passed;
- UE 5.8 Geometry Script capability passed;
- real SP638 topology proof passed;
- 4K terrain-skin render completed.

However, **technical green did not produce an acceptable rider-camera terrain**.
The terrain-skin path is therefore retained as diagnostic/prototyping evidence,
not promoted as the production terrain solution.

This is a useful negative result: Unreal-side runtime/local smoothing should not
become the default repair for a source-resolution problem that can be solved
upstream in GIS.

### Revised decision for R4.1

- promote the MASE PST 1x1 source to the **canonical macro-terrain path A**
  input, subject to a fresh exact-SHA authoring/render proof;
- retain Veneto 5 m as the reproducible fallback/A-B baseline;
- do not propagate the new candidate across the canonical route yet;
- do not unblock R5;
- use R4.1C material work and especially R4.1D `Rock Face 01` / cliff / scree
  geometry to replace or mask inspectable steep heightfield faces rather than
  destructively smoothing the DEM;
- require a route-level 1200 m golden slice before final human visual acceptance.

Issue #213 / PR #215 history remains valid evidence of the 5 m baseline. The
new 2 m A/B is the priority source-selection gate before final R4.1 propagation.


### Historical P0 source-resolution gate — Cortina 2021 LiDAR / 2 m WebGIS

> This section records the pre-MASE investigation. It is superseded by the
> immutable MASE PST 1x1 source checkpoint above; its blocked/raw-source wording
> is historical and no longer the current execution gate.

The controlled source A/B has produced a valid **negative source-gate result**
rather than a new terrain import.

Official Veneto evidence now separates three different concepts that must not
be conflated:

- **acquisition density:** the Cortina + neighboring-municipalities airborne
  LiDAR project specifies **4 points/m²**, with DSM and DTM production over
  about **39,010 ha**;
- **terrain product lineage:** Veneto states that the Olympic WebGIS terrain
  rasters derive from the 2021 LiDAR survey;
- **WebGIS raster resolution:** the Olympic portfolio explicitly calls the DTM,
  DSM and CHM **"ricampionati a 2m"** — resampled to 2 m.

Primary official references:

- https://bur.regione.veneto.it/BurvServices/Pubblica/DettaglioDgr.aspx?id=426837
- https://idt2.regione.veneto.it/portfolio/webgis-olimpiadi-2026-in-veneto/
- https://idt2.regione.veneto.it/idt/webgis/viewer?webgisId=86

The viewer exposes `DTM_2m_Cortina`; live WMS discovery resolves the
technical layer `rv:DTM_2m_clip`, whose advertised geographic extent contains
Passo Giau. That proves relevance and publication, **not a native 2 m
elevation grid**.

The live fail-closed source probe has further established:

- the raw-looking layer advertises EPSG:6876 / RDN2008 Zone 12 (N-E);
- WMS `DescribeLayer` calls it WCS-backed;
- both public WCS routes tested by YACS return the terminal GeoServer error
  **`Service WCS is disabled`** for direct `DescribeCoverage`;
- source-contract run **36453219301 / #26** exercised global/workspace WCS,
  versions 2.0.1 / 1.1.1 / 1.0.0 and the known Cortina aliases before the
  probe was optimized to fast-fail a disabled endpoint;
- the WMS layer provides no direct `MetadataURL` or `DataURL`;
- Veneto's anonymous download catalog currently returns 932 entries and no
  exact `DTM_2m_Cortina` / `DTM_2m_clip` item;
- the public CSW catalog returns no exact metadata record for either identifier;
- Veneto's public downloader exposes a documented first-party download path for
  the established **5 m LiDAR DTM**, but no equivalent public 2 m DTM
  distribution has been discovered.

Therefore the current classification is:

**2021 high-density LiDAR acquisition -> official DTM/DSM -> Olympic WebGIS
derivative resampled to 2 m -> raw/lossless DTM transport not publicly proven.**

The 2 m product is still valuable evidence: it proves that better source
material exists upstream of the old 5 m public download. It does **not** justify
manufacturing a DEM from styled WMS pixels or claiming that a provider-side
2 m resample adds measured terrain detail.

This fixes the execution order:

1. keep the Veneto 5 m Landscape as the reproducible A/B baseline;
2. keep the 2 m source candidate blocked until a documented official raw DTM
   distribution or equivalent provider metadata is obtained;
3. if obtained, validate raster spacing, datatype, NoData, CRS/axis order,
   vertical datum, provenance/license, AOI coverage and immutable hash;
4. record whether the provider raster is native to the DTM production chain or
   itself resampled;
5. only then prepare a deterministic 4033 R16 candidate and render the exact
   same neutral UE proof against the 5 m baseline;
6. independently continue bounded road cut/fill and cliff/scree investigation
   where those tasks do not depend on pretending the 2 m source is solved.

Do **not**:

- use WMS `GetMap` pixels as elevation;
- infer a hidden DTM filename from other public LiDAR derivatives;
- call the 2 m WebGIS layer a native 2 m DEM;
- move this GIS experiment into PR #224 / the local-mesh path.

PR #215 remains the single legal slot for this source decision. PR #224 remains
a documented local-mesh experiment/dead end for this question.


## 19. Terrain research / visual-debug SSOT

The current Passo Giau Landscape spike now has a dedicated research and
troubleshooting playbook:

`docs/STAGE3G_R4_1_TERRAIN_RESEARCH.md`

It captures:

- Epic UE 5.8 Landscape topology and height-precision references;
- official import APIs to use as an oracle against the custom R16 reader;
- a neutral-material geometry-proof requirement;
- source/R16 quantization and round-trip diagnostics;
- 63/126-quad subsection/component seam probes;
- guidance against blind Gaussian-blur "fixes";
- Gaea / World Machine terrain-export references;
- a rule that Nanite is not a geometry-quality repair;
- the ordered diagnostic ladder for the current Passo Giau visual artifact.

For R4.1B, this playbook is the visual-debug SSOT. No terrain smoothing,
material camouflage, Nanite change or full-route propagation should bypass its
diagnostic order.

## R4.1B.2 — bounded SP638 hairpin corridor spike (2026-09-28)

The first persisted-SP638 cyclist-height proof was technically valid but visually
rejected. R4.1B.2 therefore stops broad world propagation and tests one bounded
hairpin before any material/asset dressing.

### Research-backed implementation contract

The spike follows four external signals:

- Epic Landscape Splines: spline-driven Landscape deformation supports smooth
  raise/lower cut-fill with side falloff:
  https://dev.epicgames.com/documentation/unreal-engine/landscape-splines-in-unreal-engine
- Epic Landscape Patch: if spline cut-fill is insufficient, a later bounded
  patch/edit-layer implementation can procedurally change the heightmap and bake
  the result without runtime cost:
  https://dev.epicgames.com/documentation/unreal-engine/landscape-patch-system
- RoadBuilder uses separate road/ground geometry and exposes a boundary spline
  for PCG, reinforcing the project decision to separate road presentation from
  macro Landscape responsibility:
  https://github.com/fullike/RoadBuilder
- A community report shows Landscape spline roads can still clip on uneven terrain
  even with Raise/Lower enabled. This is not an authority, but it is a useful
  failure-mode warning: the proof remains rider-camera visual evidence, not an
  assumption that the tool must work:
  https://www.reddit.com/r/unrealengine/comments/1lag5w5/

### Fast proof scope

The R4.1B.2 proof deliberately reuses the already-persisted
`L_PassoGiauTerrainSpike.umap`. It does **not** redownload the 33 Veneto DTM
tiles and does **not** rebuild the 8 km x 8 km Landscape.

The proof:

1. materializes only the persisted LFS map;
2. finds the official SP638 spline and selects the maximum-curvature hairpin;
3. crops the working spline to approximately 700 m;
4. hides the old full-road debug spline meshes;
5. applies transient `LandscapeProxy.editor_apply_spline(...)` deformation with
   bounded raise/lower and side falloff;
6. renders a neutral 6 m road plus a 10 m shoulder/roadbed proof surface;
7. replaces the checkerboard Landscape material with a neutral diagnostic material;
8. captures a deterministic 3840 x 2160 cyclist-height PNG;
9. does not save the transient Landscape deformation back into the map.

This keeps iteration cost bounded to LFS map materialization + incremental editor
build + one Unreal capture.

### Result — run 36415573299

The second R4.1B.2 attempt completed **GREEN** after the first attempt exposed
two proof-harness API mistakes (invalid edit-layer name and an incorrect Python
material setter). The successful proof used edit layer `Layer`, a 685.369 m
maximum-curvature SP638 slice centered around source distance 15.525 km,
transient raise/lower spline deformation, and a 3840 x 2160 rider capture.

The result is **VISUAL FAIL** despite the green technical proof.

What improved:

- the road is immediately readable from cyclist height;
- the bounded cut/fill path executes deterministically;
- the fast proof no longer rebuilds the whole 8 km x 8 km terrain;
- transient proof changes leave tracked map assets untouched.

What remains unacceptable:

- rider-visible uphill faces still show severe heightfield ribbing/terracing;
- the uniform proof shoulder/roadbed becomes a large artificial wedge/slab;
- the local road cut/embankment still does not read as believable Alpine terrain.

Decision: retain the bounded proof loop and spline deformation primitive, but do
not promote the box-strip corridor. R4.1B.3 must generate dedicated high-detail
local ground/cut/embankment geometry for the same hairpin and demote Landscape
to macro background beneath/behind that local corridor. Do not add vegetation or
production materials before that geometry passes the rider-camera gate.

### Acceptance gate

The candidate passes only if the rider-height PNG shows all of the following:

- the hairpin reads immediately as a mountain road;
- no obvious road/terrain clipping;
- no floating road slab;
- cut/fill transition is smoother than the rejected R4.1B.1 proof;
- the immediate road corridor no longer exposes the previous Minecraft-like
  heightfield failure as the dominant foreground read;
- the road remains presentation-only and does not alter
  `FRouteGeometryProfile` or Road Physics Profile truth.

A technically green run can still be recorded as `VISUAL_FAIL`.

If this spike passes visually, the next implementation promotes the method into
persistent bounded road-cut/corridor authoring. If it fails, the experiment is
kept in the journal and the next spike moves to Landscape Patch / generated
ground-mesh treatment rather than increasing global Landscape resolution.


## R4.1B.3 — high-detail local ground / cut / embankment corridor

Issue: [#223](https://github.com/karnalooch/YetAnotherCyclingSim/issues/223)

R4.1B.2 proved the bounded hairpin loop but failed visually. The next terrain
step therefore keeps Landscape as macro terrain and replaces the rider-close
box-strip roadbed with dedicated local corridor geometry around the exact same
official SP638 hairpin.

### Tool ownership

Use the following systems with deliberately separate responsibilities:

1. **MASE PST 1372858 DTM-primary UE Landscape** — canonical macro mountain
   mass, valley continuity and distant terrain; Veneto 5 m remains only the
   bounded fallback/A-B source where measured MASE coverage is absent.
2. **Landscape Spline / non-destructive edit layer** — broad bounded raise/lower
   so the macro heightfield does not pierce the road corridor.
3. **Landscape Patch System** — bounded evaluation for localized deterministic
   height correction where spline deformation alone cannot form a clean bench.
   Patch data must remain editor-time, reproducible and presentation-only.
4. **Geometry Script / Dynamic Mesh** — primary candidate for the camera-close
   uphill cut, ditch/bench, shoulder-to-ground transition, downhill embankment
   and other local earthwork geometry.
5. **RoadForge mesh core** — asphalt, shoulders and markings only after the
   terrain/centerline contract passes. RoadForge must not own terrain or restore
   its OSM/city/PCG subsystems.
6. **PCG + materials** — dressing only after neutral geometry passes: rock
   faces, scree, rubble, grass, conifers and transition masking.

Epic's UE 5.8 documentation confirms that Landscape Patch is an editor-side
procedural height/weight modification system whose results bake into the
Landscape without runtime patch cost. Geometry Script provides Dynamic Mesh
construction operations suitable for swept local presentation geometry.

References:

- Epic — Landscape Patch System:
  https://dev.epicgames.com/documentation/unreal-engine/landscape-patch-system
- Epic — Landscape Edit Layers:
  https://dev.epicgames.com/documentation/unreal-engine/landscape-edit-layers-in-unreal-engine
- Epic — Geometry Scripting Reference:
  https://dev.epicgames.com/documentation/unreal-engine/geometry-scripting-reference-in-unreal-engine

### Cross-section contract

The local corridor is not a symmetric road slab. Each stable spline sample
constructs an oriented frame and supports independent left/right earthwork:

    uphill terrain
      -> cut face
      -> ditch / bench
      -> shoulder
      -> asphalt
      -> shoulder
      -> embankment
      -> downhill terrain

The implementation must preserve per-sample elevation and allow one side to be a
cut while the other side is a fill. Dense sampling is required at the
maximum-curvature hairpin.

### Hairpin adaptive-offset rule

For the bounded maximum-curvature hairpin, **road-edge and shoulder offsets are
protected**. Only earthwork points outside the shoulder may contract on the
inside of a bend.

The deterministic spike uses signed sampled XY curvature to derive the local
radius. On the inside of a bend it preserves the road/shoulder first, then keeps
**65% of the remaining clearance between the protected shoulder and the local
curvature radius** for earthwork; the other 35% stays as a singularity margin.
The contraction is tapered across neighboring stations to avoid an abrupt width
step. If the local radius cannot leave at least **0.15 m** outside the protected
shoulder, the proof fails closed rather than shrinking or pinching the
road/shoulder presentation.

These values are bounded R4.1B.3 geometry defaults, not route/physics truth.
Cross-section role order remains stable while outer earthwork lateral offsets
may vary per station. The deterministic mesh hash covers the resulting actual
vertices and triangle ordering.

### Geometry reject conditions

Reject or rework the local-mesh candidate if the neutral proof shows:

- miter spikes or self-intersection on the inside of the hairpin;
- inverted/degenerate triangles;
- pinched shoulders;
- visible regular segment blocks;
- a rectangular downhill wedge;
- camera-close Landscape ribbing still dominating the cut face;
- discontinuous normals or obvious seams;
- a second, competing SP638 centerline.

### Execution order

1. Reuse the #217 maximum-curvature hairpin selector and persisted official
   SP638 spline.
2. Keep the proven transient Landscape spline cut/fill as broad macro
   accommodation.
3. Generate the local asymmetric earthwork corridor in neutral geometry.
4. Capture the same deterministic 3840x2160 cyclist-height proof.
5. Record topology/determinism evidence and human visual status.
6. Only after the neutral ground geometry passes, layer in RoadForge road
   surface and then materials/PCG dressing.

### R4.1B.3 proof-suite execution

The final B.3/scenic rerun uses the #234 **build-once / prove-many** lane. One
trusted exact-SHA worktree materializes the persisted Passo Giau map once and
builds the UE 5.8 editor once, then runs the Geometry Script capability,
real-SP638 topology, bounded hairpin and rider-close local visual proofs from
that same prepared workspace.

Prepared-workspace reuse is job-local only. Each child wrapper validates a
stamp bound to the exact HEAD, worktree, materialized map byte count and editor
build identity before skipping its normal standalone preparation. No build or
stamp may be reused across a different SHA or runner job.

### R4.1B.3.1 — overlap / road-occlusion correction

Issue: [#238](https://github.com/karnalooch/YetAnotherCyclingSim/issues/238)

The latest B.3 rider-camera proof is a material visual improvement over B.2, so
the hybrid MASE Landscape + bounded DynamicMesh direction is retained. It is
still not visually accepted. The remaining black road fragments can be caused
by either non-local swept-surface overlap or rider-close terrain covering the
road/shoulder envelope, so the correction must diagnose both instead of
assuming one cause.

B.3.1 therefore adds these fail-closed presentation contracts:

- non-adjacent swept corridor bands are checked for overlapping XY footprint
  when their Z ranges are not safely separated;
- only terminal, non-protected earthwork may contract automatically to resolve
  such overlap; protected road edges, shoulder contract and canonical SP638 XY
  are not moved;
- the world-aligned terrain skin is lowered only where required to preserve a
  bounded vertical clearance below the asphalt/shoulder presentation envelope.
  The B.3.1 hairpin proof keeps a **4.0 m fail-closed maximum correction**:
  exact-SHA proof evidence measured a required 3.362 m cut, so the earlier
  provisional 3.0 m cap was below the real bounded hairpin geometry; corrections
  above 4.0 m remain rejected rather than silently excavating arbitrary terrain;
- terrain-skin smoothing adjustments taper back to zero near the outer skin
  boundary so the local mesh converges to the sampled MASE macro Landscape
  instead of reading as a hard sheet;
- the visual proof uses a plain neutral lit material treatment rather than the
  checker-like editor fallback, so slope, occlusion and seams are easier to
  judge.

The deterministic hairpin contraction keeps the documented **65%** of usable
inside clearance beyond the protected road edge. This value is presentation
geometry only and does not change route/physics truth.

B.3.1 is still a neutral-geometry gate. RoadForge, production materials,
foliage and PCG dressing remain blocked until the same rider-camera proof is
human-accepted.

Do not start broad propagation, production materials or foliage before this
geometry gate passes. A green workflow remains insufficient without human visual
acceptance.

## 20. Definition of Done

R4.1 is complete only when:

- the 1200 m golden slice is accepted before full-route propagation;
- 1200/4900/8000 are visually distinct and credible;
- road/terrain/PCG read as one world;
- no reject criterion remains obvious in canonical captures;
- Visual History contains comparable BEFORE/NOW/AFTER evidence;
- technical and visual status are both accepted;
- the exact accepted SHA passes the unchanged Stage 3G performance contract;
- the exact accepted SHA passes the required full Stage 3G closeout proof;
- the accepted R4.1 tree becomes the immutable pre-optimization baseline for R5.
