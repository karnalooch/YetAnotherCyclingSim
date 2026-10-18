# Sa Calobra: Houdini / Pegasus / SideFX Labs build guide

**Status:** current agent execution guide, adopted by owner request on 2026-10-17; clarified the same day: base first, details afterwards, following the Pegasus workflow itself.
**Authority:** subordinate to the [World Building Bible](../../WORLD_BUILDING_BIBLE.md), [SideFX execution workflow](README.md), [Roadmap](../../ROADMAP.md) and geographic/physics contracts. This guide makes the selected direction actionable; it does not create a competing roadmap or grant production acceptance.
**Source supplement:** [reviewed SideFX Labs 22.0.466 package](SIDEFX_LABS_22_0_466.md).
**Delivery at adoption:** #365 / M3, existing Draft PR #474, `codex/365-world-graph`; inspected base `11d93a9dcb7a52386e961456c33620ae7c7fec96`. Recheck current issue/PR state when resuming.

## 1. Direction and division of responsibility

**Reconstruct the real Sa Calobra with Houdini, not a procedurally invented island inspired by it.**

Verified DTM and route/GIS evidence determine geography. Domain authorities determine placement constraints and source confidence. Houdini executes the selected original Pegasus recipe with native SideFX nodes and suitable Labs tools. Unreal consumes the resulting terrain, layers and assets. Independent technical checks and the owner decide acceptance.

Pegasus is the method/reference corpus; SideFX Labs is a supporting Houdini toolbox, not a second world generator or a ready-made Sa Calobra scene. Start from the relevant original HIP/HDA and tutorial step. Inspect native Houdini and the pinned Labs package before writing an adapter. Adopt a Labs node only for a named operation, with its actual version, dependencies, parameter changes and measured result recorded in the [recipe](RECIPE_TEMPLATE.md). A tutorial's outdated node may need a documented, verified successor rather than literal replication.

Python/HOM may orchestrate nodes, imports, paths, cooking, cache checks and measurements. It must not hide a replacement terrain, erosion, road, biome or cliff algorithm. Use existing tools where they cover the operation; research an official SideFX solution for a concrete gap. If the gap remains unresolved, block that dependent operation and report it without redesigning the entire pipeline.

BOB keeps road/earthworks constraints; route geometry and Road Physics Profile keep physical truth. PCG/PCGEx may support an explicitly selected consumer/integration recipe, not silently resume primary generation. Blender remains supporting preparation/inspection. Material Forge remains the existing surface-material toolchain unless a separately justified recipe needs another supported operation.

### Owner clarification: base first, details afterwards

The owner explicitly wants **the Pegasus workflow, not merely a landscape made with Houdini**. First establish and inspect the base terrain, then develop it through separate detail passes. An imported DTM, a diagnostic corridor overlay or a low-amplitude noise preview is a base/test result, not the finished Landscape. The detail passes are part of the intended terrain workflow, not an optional afterthought.

Keep the Pegasus **Source / Manual Edits / Procedural Detail** separation. In Sa Calobra the geographic DTM supplies the source stage; manual corrections remain separately recorded and can be empty when unnecessary. Surface detail is a downstream stage, not a rewrite of Source. These are workflow responsibilities, not a claim that three identically named native UE layers already exist or that every operation is simple addition.

Use [PEG-01 Landscape Creation](catalog/PEG-01.md) for base construction and handoff, and [PEG-02 Landscape Workflow](catalog/PEG-02.md) for the actual follow-on process: lesson 2 for pipeline organization; lessons 3-4 for material-heightmap detail and layered masks; lesson 5 for scree masks; lessons 6-7 for IDMap and Unreal material setup. Consult the [original series](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/) and the corresponding retained HIP/HDA before implementation. Global colour and near-surface material detail must remain distinct outputs where the selected recipe uses both. Reuse licensed inputs and record any material-source substitution; the owner is adopting the method, not granting new asset licenses.

The execution order below is our explicit Sa Calobra application of those references, not a claim that every Pegasus team member or asset was produced in one strictly linear chronology. For later cliffs, the [original cliff workflow](https://www.sidefx.com/tutorials/project-pegasus-cliff-generation/) derives mesh sections from terrain and adds subdivision/displacement; it is downstream geometry, not a replacement base generator.

A historical detail blend of `0.001`, a measured approximately `0.178 m` displacement and the earlier assistant-proposed `0.5 m` bound describe prior experiments. They are **not permanent specifications for all later detail** and must not become a reason to omit the material-heightmap workflow. Choose and record operation-appropriate scale, masks and displacement while retaining the existing macro-geography and physics boundaries. This clarification does not authorize arbitrary macro deformation.

## 2. Active scope versus later direction

The active terrain workflow is **base first, then masks, separately controlled surface detail and terrain surfacing**: the complete supplied Ma-2141 reference, a 500 m horizontal working buffer on each side, and surrounding terrain context. The immediate local pass is to reopen, inspect and checkpoint the existing base before adding more detail. No base or detail PASS is conferred by this document. Road geometry, road earthworks, cliff meshes, vegetation and buildings remain later workstreams under the existing roadmap.

Complete one pass with its appropriate evidence, retain its cache, and then move downstream. Do not demand finished materials or cliff meshes before a base checkpoint can be useful; equally, do not call that checkpoint the final world. The following ordering replaces the earlier table that grouped all materials with later vegetation:

| Ordered pass | Direction | Output / check |
|---|---|---|
| 1. Base / Source | Resume the existing real-DTM HeightField; establish scale, origin, coverage and macro relief without final surface dressing | Viewable base and reusable cache; source identity, grid, validity and route coverage checked |
| 2. Manual Edits and control masks | Keep any necessary bounded correction separate; derive the masks needed by the next operation | Recorded corrections or explicit no-op; named masks with checked registration and exclusions |
| 3. Procedural terrain detail | Follow PEG-02 material-heightmap layering and scree-mask methods; use erosion/noise only where the selected recipe and required effect justify them | Independently controlled surface-detail result, measured height delta and before/after views at useful scales |
| 4. Terrain appearance | Follow the selected Pegasus IDMap/material workflow, including global colour versus close-range surface detail; reuse suitable Material Forge inputs with recorded adapters | Material selection and physical scale checked; coherent overview and near views; no diagnostic mask confused with final surfacing |
| 5. Terrain consumer check | Inspect the corresponding versioned base/detail outputs in an isolated Unreal destination as needed during iteration | Fresh HIP/cache reopen, shared edges, effective import settings, save/reopen and correct collision targets |
| Later: cliffs and rocks | Derive and detail cliff sections using the original Pegasus workflow | Sourced regions, mesh quality/contact and no concealed terrain defects |
| Later: road and earthworks | Adapt the source-aligned Pegasus road recipe within its domain constraints | Canonical XY, width/profile/banking, hairpin continuity and cut/fill/contact checked |
| Later: vegetation and structures | Use the relevant source-led Pegasus methods and suitable tools when those workstreams are active | Coherent ground/vegetation relationships, sourced placement, then assembled-world review |

The base-to-detail order is mandatory; consumer checks may happen between passes and are not a one-way prohibition on returning to a specific defect. The later rows do not reorder issue dependencies or activate every world system at once. A base repair invalidates its actual dependants, not unrelated caches. The 8 km source coverage is available context, not an instruction to regenerate or render every cell at full detail. Background simplification is a representation choice, not permission to move ridges or valleys. Any visibility-based trimming needs actual route-camera evidence.

## 3. Resume an existing project before building another one

Start with `Ma2141_SaCalobra_Houdini/SaCalobra_Pegasus.hiplc` and its recorded caches, resolving the real host path from the current workspace records. Do not recreate the terrain because a new session lacks context. A missing local path means locate/restore the documented project or report the missing dependency, not synthesize a substitute.

For each bounded work session:

1. Read root `AGENTS.md`, this guide and the selected recipe/source portion. Confirm the approved issue, active stage, exact checkout SHA, existing HIP/output identities and host ownership.
2. Locate the retained Pegasus corpus and [Labs package](SIDEFX_LABS_22_0_466.md). Verify the package actually loaded in the process and the selected node definition; a file on disk is not a successful installation.
3. Reopen and inspect the existing output. State the current base/detail pass, one concrete defect or deliverable and which graph branch/layer may change. At the base pass, show the base without final detail; at a detail pass, show its difference from the cached base.
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
| Material-driven terrain detail and appearance | Original PEG-02 Heightfield Materials, Materials Workflow, Scree Slopes and IDMap/Material Setup recipes | Required downstream terrain passes; verify original HDA, licensed maps, metric texture/displacement scale and independent base/detail control |
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

The bounded [Lesson04 Unreal consumer repair](LESSON04_UNREAL_REPAIR.md) records the isolated 2026-10-18 height, seam, UV, runtime collision and fresh-reopen measurements. Its native receipt is separate from owner visual acceptance and production promotion.

The [Lesson05 scree plan with Material Forge](LESSON05_SCREE_PLAN.md) records the next source-mapped pass, original dependencies, surface adapter, checkpoints and native verification gates. It is a plan only: Lesson05 execution and acceptance remain NOT RUN.
