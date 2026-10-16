# Sa Calobra: Houdini / Pegasus / SideFX Labs build guide

**Status:** current agent execution guide, adopted by owner request on 2026-10-17.
**Authority:** subordinate to the [World Building Bible](../../WORLD_BUILDING_BIBLE.md), [SideFX execution workflow](README.md), [Roadmap](../../ROADMAP.md) and geographic/physics contracts. This guide makes the selected direction actionable; it does not create a competing roadmap or grant production acceptance.
**Source supplement:** [reviewed SideFX Labs 22.0.466 package](SIDEFX_LABS_22_0_466.md).
**Delivery at adoption:** #365 / M3, existing Draft PR #474, `codex/365-world-graph`; inspected base `11d93a9dcb7a52386e961456c33620ae7c7fec96`. Recheck current issue/PR state when resuming.

## 1. Direction and division of responsibility

**Reconstruct the real Sa Calobra with Houdini, not a procedurally invented island inspired by it.**

Verified DTM and route/GIS evidence determine geography. Domain authorities determine placement constraints and source confidence. Houdini executes the selected original Pegasus recipe with native SideFX nodes and suitable Labs tools. Unreal consumes the resulting terrain, layers and assets. Independent technical checks and the owner decide acceptance.

Pegasus is the method/reference corpus; SideFX Labs is a supporting Houdini toolbox, not a second world generator or a ready-made Sa Calobra scene. Start from the relevant original HIP/HDA and tutorial step. Inspect native Houdini and the pinned Labs package before writing an adapter. Adopt a Labs node only for a named operation, with its actual version, dependencies, parameter changes and measured result recorded in the [recipe](RECIPE_TEMPLATE.md). A tutorial's outdated node may need a documented, verified successor rather than literal replication.

Python/HOM may orchestrate nodes, imports, paths, cooking, cache checks and measurements. It must not hide a replacement terrain, erosion, road, biome or cliff algorithm. Use existing tools where they cover the operation; research an official SideFX solution for a concrete gap. If the gap remains unresolved, block that dependent operation and report it without redesigning the entire pipeline.

BOB keeps road/earthworks constraints; route geometry and Road Physics Profile keep physical truth. PCG/PCGEx may support an explicitly selected consumer/integration recipe, not silently resume primary generation. Blender remains supporting preparation/inspection. Material Forge remains the existing surface-material toolchain unless a separately justified recipe needs another supported operation.

## 2. Active scope versus later direction

The active task remains **terrain, masks, boundaries and separately controlled subtle detail only**: the complete supplied Ma-2141 reference, a 500 m horizontal working buffer on each side, and surrounding terrain context. No road mesh, road earthworks, cliff dressing, vegetation or buildings are authorized by this documentation update.

The following is an execution sequence within the existing roadmap, not simultaneous authorization for every row:

| Stage | Direction | Exit evidence before expanding |
|---|---|---|
| Current: source and terrain | Resume the existing real-DTM Houdini project; verify geographic registration and source validity | Source identity, units/axes/origin, grid/extent, all route parts covered; source-relative height comparison |
| Current: masks and subtle detail | Build/inspect named layers using the selected Pegasus method, native HeightField nodes and suitable Labs mask helpers | Mask meaning and range, hard boundaries preserved, disableable detail, measured displacement inside/outside corridor |
| Current: cache and terrain handoff | Cache separate stages; consume an explicitly versioned terrain candidate in an isolated Unreal destination when the applicable gates permit | Fresh HIP/cache reopen; tile edges, effective import settings, saved/fresh-reopened Unreal data and actual collision target |
| Later, separately activated: road and earthworks | Adapt the source-aligned Pegasus road recipe; consider Labs Road Generator or Unreal Spline only where demonstrated suitable | Canonical XY retained, width/profile/banking and hairpin continuity, cut/fill/support and road/terrain contact |
| Later, separately activated: cliffs and rocks | Adapt original Pegasus cliff methods and suitable native/Labs mesh preparation | Region and source provenance, actual mesh quality/contact, no floating bases or cosmetic concealment of terrain defects |
| Later, separately activated: materials and vegetation | Reuse Material Forge; evaluate current SideFX baking and Labs Biome tools for named gaps | Material scale/roughness/normal checks; sourced vegetation domains, species choices, exclusions and deterministic placement |
| Later, separately activated: structures and assembled-world closeout | Source-led reconstruction, engine consumption and whole-area review | Actual saved world, owner review, then the existing M3 performance protocol |

The 8 km source coverage is available context, not an instruction to regenerate or render every cell at full detail. Background simplification is a representation choice, not permission to move ridges or valleys. Any visibility-based trimming needs actual route-camera evidence.

## 3. Resume an existing project before building another one

Start with `Ma2141_SaCalobra_Houdini/SaCalobra_Pegasus.hiplc` and its recorded caches, resolving the real host path from the current workspace records. Do not recreate the terrain because a new session lacks context. A missing local path means locate/restore the documented project or report the missing dependency, not synthesize a substitute.

For each bounded work session:

1. Read root `AGENTS.md`, this guide and the selected recipe/source portion. Confirm the approved issue, active stage, exact checkout SHA, existing HIP/output identities and host ownership.
2. Locate the retained Pegasus corpus and [Labs package](SIDEFX_LABS_22_0_466.md). Verify the package actually loaded in the process and the selected node definition; a file on disk is not a successful installation.
3. Reopen and inspect the existing output. State one concrete defect or deliverable and which graph branch/layer may change.
4. Exercise the smallest representative case, including a relevant difficult boundary, then extend to the authorized area after checking the result. A local pass is not whole-area acceptance.
5. Save an independent versioned candidate, check fresh-process reopen and present real before/after views plus relevant measurements. Do not mark visual acceptance on behalf of the owner.
6. Commit only the scoped source/docs/compact receipts on the canonical delivery branch and report the remaining gap. Do not create a parallel implementation PR, new proof framework or generic orchestration layer to avoid finishing the terrain.

## 4. Source, layer and geographic discipline

Keep original `Base_DTM`, CRS/vertical metadata and accepted checkpoints unchanged. Separate the source baseline, validity, working corridor, reversible presentation detail and background coverage in the graph. These are conceptual responsibilities, not a demand to rename existing layers or rebuild a working HDA.

Source equality on the imported grid is not a claim that the survey itself is error-free. Record coordinate transforms, axis orientation, metric scale, resolution, bounds and NoData behavior explicitly. Preserve all canonical road parts; a pathfinder must not reroute Ma-2141. NoData cannot become invented measured ground.

A mask must state its producer, source, layer name, units/range and meaning. Keep validity, corridor, land-cover, material weights and consumer visibility distinct. Copying or blending a layer does not establish spatial registration. Check matching origins and cell spacing first. After blur, resampling or combination, recheck hard exclusions and the corridor boundary; soft blending must not leak changes into protected areas.

Detail stays in a separate adjustable branch/layer that can return exactly to the source baseline. Report maximum, mean and relevant percentile displacement, the affected area and any change outside the permitted mask. The previously measured approximately 0.178 m maximum is historical candidate evidence, not a permanent target. The earlier proposed 0.5 m bound is not an owner-defined or SideFX accuracy standard. Never copy fictional-island erosion/noise amplitudes that replace real macro relief.

Geometry must be inspected directly. Material blending, vegetation, extra rocks and shadows cannot repair incorrect heights, support gaps, overlapping background collision or a wrong route.

## 5. Select tools by operation, not by availability

The [package review](SIDEFX_LABS_22_0_466.md) records the actual bundled help paths and limitations. Capability descriptions are not proof that these nodes are loaded or cooked in YACS.

| Need | Candidate implementation | YACS constraint |
|---|---|---|
| Real terrain import and reversible layers | Original Pegasus import/layer/cache method; native HeightField File, Mask by Geometry, Layer, Crop and Output as appropriate | Verify the existing source baseline; no replacement macro terrain |
| Combine/copy named terrain masks | Labs HF Combine Masks and HF Insert Mask | Register grids first; preserve layer meaning, validity and hard exclusions |
| Slope/cost/avoidance diagnostics | Native analysis or Labs Terrain Analysis for an identified need | Derived diagnostics only; never authority to relocate the real road |
| Optional terrain mesh or tiled map output | Labs Terrain Mesh ROP / Terrain Texture ROP, only if the consumer needs that representation | Check lattice, shared edges and fidelity; heightfield conversion alone does not author overhangs or cliffs |
| Unreal height/layer handoff | Existing Houdini Engine transfer; Labs Terrain Layer Import/Export only for a verified file-based alternative | Validate orientation, height range and units; do not apply both conversion paths blindly |
| Future curve/road handling | Source-matched PEG-13 parts; Labs Road Generator / Unreal Spline after suitability tests | Retain measured alignment and physics; spline JSON is an interchange product, not geographic authority |
| Future vegetation domains/scatter | Current Biome Define/Region Assign, Attributes to Terrain, Plant Define/Plant Scatter chain where applicable | Source-led domain masks and exclusions; sample library species are not evidence for Mallorca |
| Future mesh UV/LOD/bake | Suitable native nodes, Labs Auto UV / LOD Create after inspection; current SideFX bakers for new baking work | Do not make deprecated Maps Baker the new default; retain Material Forge and test dependency closure |

Use the installed node's exact type/version and definition file, not a guessed type from a help filename. The package contains historical help and compatibility aliases. Check replacements, hidden nodes, beta labels and third-party dependencies before adoption.

## 6. Cache, scope and engine boundaries

Cache source import, derived masks, detail and engine-ready output independently using the existing recipe's Houdini file/ROP/PDG mechanisms. Include actual source hashes, node/package versions, effective parameters/seeds, transforms, masks and sampling in invalidation decisions. Reuse a verified unchanged cache. Recompute only the affected dependency branch; neither full-area cooking on every edit nor unverified stale-cache reuse is acceptable.

Retain portable project-relative paths where the existing project supports them. Store heavy tools, originals and caches outside Git under the established D: workspace/tool roots, not new default C: locations. Record unresolved host paths rather than inventing an installation.

Unreal integration must preserve the [configuration separation](UNREAL_CONFIGURATION.md): the old checkpoint's `DefaultEngine.ini` and hashes are not a place to install new Houdini settings. The optional `scripts/houdini/unreal-engine.args` profile is explicit and session-specific; effective settings and HAPI behavior still require native readback. Standalone Houdini authoring does not need that Unreal profile.

Houdini Engine for Unreal and the optional SideFX Labs Unreal content plugin are different dependencies. Do not enable the Labs plugin just because its files are present, copy UE 5.7 binaries into UE 5.8, or install main and Legacy packages together. Adopt only the integration needed by the selected recipe and preserve active owner sessions and existing host arbitration.

For tiled/terrain handoff, verify shared sample edges, transforms, height quantization/range, visibility conventions and which actual actor each collision trace hits. Do not turn historical background-collision failures into a clean result without a fresh measurement of the final candidate.

## 7. Evidence and repository hygiene

Keep stages separate: source inspected; definition resolved; graph cooked; HIP/cache reopened; geographic result checked; Unreal import/save/reopen checked; owner accepted. Record `NOT RUN`, `FAILED` or `UNVERIFIED` where appropriate. An index, successful setter, screenshot, old producer receipt or green documentation check cannot certify a different current output.

Use the existing [recipe template](RECIPE_TEMPLATE.md), CI and proof system, not another parallel receipt framework. Each iteration should return the exact source revision, changed graph/parameters, actual cache/output identities, reproducible reopen path, meaningful views, relevant source/geometry checks and remaining blocker. The first goal is a correct visible deliverable, not expanding infrastructure.

The uploaded `sidefx_packages.7z`, complete Labs distribution, compiled binaries, `Intermediate`/`Binaries` content and full help corpus stay outside the product repository. Retain concise metadata, source paths/hashes and authored guidance. Existing [JSON storage rules](../../evidence/JSON_STORAGE.md) remain in force, including the 1 MiB raw-documentation JSON budget and byte-preserving archival. Do not delete recipes, interchange inputs or failed evidence simply because they use JSON.

M3 performance remains `DEFERRED_AFTER_M3`, `performance_pass: false`. This guide grants neither a merge to `main` nor world/visual/performance acceptance, and records no new Houdini or Unreal execution.
