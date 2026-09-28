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
- hero vista blocked by uncontrolled PCG scatter.

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

Preferred approach is hybrid: real-world terrain data may provide strong macro forms, while YACS keeps its own fictional road, route physics, PCG biomes, materials, roadside dressing and art direction.

## Current implementation status — Passo Giau terrain source (2026-09-28)

The R4.1 macro-terrain recovery now has a proven remote source/preparation path.

### Merged repository work

- PR #211 — `feat(assets): add Passo Giau DEM bootstrap` — **MERGED** as `7db3a63e11b83c3d33f86f80e1d6687c05b8ea78`.
- PR #212 — `feat(terrain): prepare Passo Giau R4.1 heightmap pipeline` — **MERGED** as `a98162fd590c5d3dc597a5c625d70e9860bb46c7`.
- downloader: `scripts/assets/download_passo_giau_dem.py`;
- preparation pipeline: `scripts/assets/prepare_passo_giau_heightmap.py`;
- remote integration workflow: `.github/workflows/passo-giau-r4-1-terrain-spike.yml`.

### Proven remote source

Provider: **TINITALY 1.1 / INGV**  
License: **CC BY 4.0**  
AOI: approximately **8 x 8 km around Passo Giau**  
Source grid: **800 x 800 at 10 m**  
Source DEM SHA-256:

`9a58a8aca8b1856507b4ca3e656f8c975518cbd89bd273036ef2483c148db610`

Remote download/preparation run: **GitHub Actions #36357523138 — PASS**.

Observed terrain range:

- minimum: **1171.353 m**;
- maximum: **2713.832 m**;
- relief: **1542.479 m**;
- mean elevation: **1993.256 m**.

Prepared Unreal candidate:

- **1009 x 1009** 16-bit heightmap;
- matching little-endian `.r16`;
- native-resolution 16-bit PNG;
- hillshade preview;
- `terrain-report.json`;
- recommended XY scale: **793.651 cm/vertex**;
- recommended Z Scale: **301.265**.

The successful remote evidence is retained as GitHub Actions artifact
`passo-giau-r4-1-terrain-spike`.

This evidence proves the external terrain source and preparation path only. It
does **not** constitute Unreal visual acceptance.

### Active next step

Issue #213 — **R4.1B — import Passo Giau DEM into isolated Unreal Landscape spike**.

The first UE integration must use a separate map such as
`/Game/Prototype/Maps/L_PassoGiauTerrainSpike`. It must not mutate
`/Game/Prototype/Maps/L_CyclingTest`, route truth or physics.

The Landscape spike is path A of the documented R4.1 terrain A/B. Geometry
Script / generated tiled terrain remains path B until a rendered vertical slice
is reviewed.

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
