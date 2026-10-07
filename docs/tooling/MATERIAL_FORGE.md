# YACS Material Forge

**Status:** exact-SHA render proof in progress  
**Issue:** #387  
**Scope:** offline procedural PBR authoring, material-local masks, deterministic validation and bounded UE import

Material Forge answers one question:

> How should a surface look, once YACS already knows what that surface is and where it belongs?

It is deliberately not another world generator.

## Ownership boundary

| Subsystem | Owns |
|---|---|
| BOB | road/terrain geometry, cut/fill and earthworks |
| PCG/PCGEx | world semantics, classification, placement and authoritative spatial masks |
| Material Forge | surface appearance, procedural PBR and material-local detail masks |

The non-negotiable rule is:

> **PCG/PCGEx owns WHO / WHAT / WHERE. Material Forge owns HOW IT LOOKS.**

## Runtime/tool boundary

Material Forge uses:

- the pinned Material Maker 1.7 install directory only as reviewed authoring input
  (`nodes/material.mmg`, executable identity and licence evidence);
- the reviewed Material Maker source commit
  `4d29a815489866aae483281cf44b2cfe48d3cc3e` as the render runtime;
- pinned Godot 4.7.2 to first prime that source project's import/script-class
  cache and then execute the bounded YACS render adapter;
- no Godot fork and no Material Maker fork.

A clean Material Maker source checkout is **not render-ready by itself**. Exact-SHA
proof established that it must first be opened through
`Godot --headless --path <source> --import`, which creates
`.godot/global_script_class_cache.cfg` and imported resource cache. Rendering
before that priming produced unresolved Material Maker classes and timed out.

The alternative Material Maker 1.7 release CLI path was also tested and rejected
for this automation path: upstream `dry_earth.ptex`, the earlier YACS limestone
graph and the new Forge asphalt graph all exited with Windows access violation
`0xC0000005` both from the runner service and from the logged-on desktop
session. That A/B/C result isolates the crash from Forge graph generation.

## Phase-A families

The catalog `worldgen/materials/material_forge/families.json` defines three
families with three deterministic variants each:

1. aged mountain asphalt — base, worn cracked, patched/repaired;
2. regional pale limestone — weathered, fractured, karst-weathered;
3. dry Mediterranean mineral soil — fine, stony, dry-crusted.

Each variant records its seed, physical tile size and surface parameters.

## Output contract

Each rendered variant contains:

| Output | Contract |
|---|---|
| BaseColor | sRGB colour |
| Normal_DX | DirectX tangent-space normal |
| ORM | R=AO, G=Roughness, B=Metallic |
| Height | EXR authoring/inspection height; not Landscape displacement |
| DetailMasks | material-local RGB detail semantics |

Phase A requires metallic to remain zero. Detail masks never own world
classification.

## Authoring and render pipeline

```text
families.json + upstreams.json
              |
              v
material_forge.py author
              |
              v
editable Material Maker .ptex graphs
              |
              v
pinned Material Maker source checkout
              |
      Godot 4.7.2 --import
              |
      script/import cache receipt
              |
              v
render_material_forge.py + render_material_forge.gd
              |
              v
5 maps + native Godot decode/hash receipt
              |
              v
CPU validation + run manifest
              |
              v
second clean run -> byte determinism compare
              |
              v
UE importer / bounded canary
```

The renderer refuses to run if the source class/import cache is absent.

## Reproducibility and validation

Every run records graph/output SHA-256 values, upstream/catalog fingerprints,
seeds and validation receipts. Native Godot decode evidence for all five maps is
bound to the exact output bytes and requested dimensions.

Two complete runs are compared with:

```text
python scripts/assets/material_forge.py compare --left <run-a> --right <run-b>
```

Any graph/fingerprint/output drift fails determinism.

CPU gates reject missing outputs, wrong dimensions, wrap discontinuities, blank
signals, non-zero metallic, invalid normal vectors, non-DirectX metadata, missing
Height EXR, stale decode receipts or semantic-ownership violations.

Visual quality remains a separate exact-SHA human gate.

## World-mask boundary

Material Forge may pack already-authoritative PCG/PCGEx masks and may gate local
surface detail with them. It may not threshold, grow, erode or invent world
classes. Receipts preserve input hashes and record
`classification_changed=false`.

## UE importer and bounded canary

`scripts/ue/import_material_forge_variant.py` accepts only CPU-validated
variants, verifies hashes again, imports BaseColor/Normal/ORM/DetailMasks with
the required UE settings and defaults to unsaved assets.

`scripts/ue/preview_material_forge_canary.py` targets only
`LandscapeComponent_230`, verifies the frozen accepted Sa Calobra map, never
saves the level and restores the original component override on replay.

## Current proof evidence

The source-cache-prime proof on commit
`0ac2afe2d6f929a3f9911e1f4fc8c0f4378b326b` passed:

- pinned source checkout: PASS;
- Godot import/script-class cache creation: PASS;
- Forge authoring: PASS;
- first `aged_mountain_asphalt/base` render: PASS;
- CPU validation of that rendered variant: PASS.

The same commit also removes the reserved GLSL identifier `patch` from the
asphalt shader (`patch_mask` is used instead).

Still required for admission: all nine variants twice, byte determinism, UE
import/compile, canary assignment/rollback, visual review and later whole-area
performance.
## Blender ground-scale reference proof

Issue #399 uses the already-admitted Blender 4.5.9 headless lane as a
reference renderer only. It consumes the CPU-validated
`regional_limestone/base` and `mediterranean_soil/fine` outputs from the
current deterministic Material Forge proof and verifies their recorded hashes
again before rendering.

The reference scene preserves the catalog's physical 4 m tile scale, converts
the DirectX normal map convention for Blender preview by flipping the green
channel, uses BaseColor + Normal + ORM, and deliberately leaves Height out of
geometry displacement. Fixed context, grazing, rock-close and soil-close views
are written below `D:\\yacs\\work\\blender\\material-forge-reference` with a
machine-readable receipt and output hashes.

This stage does not open or save the accepted Sa Calobra map, does not create
world semantics and does not admit visual quality by itself. Its output is an
owner-review reference between deterministic Material Forge map validation and
the bounded Unreal consumer/canary.

## Refinement A — Issue #400

The first Landscape-targeted refinement keeps the existing 4033×4033
`material-weights.png` as spatial authority. Blue remains the rock appearance
weight and soil remains `1 - rock`; Material Forge does not create a new world
classification.

Two new A/B-safe variants are added without replacing the previous baseline:

- `regional_limestone/refined_a` — darker/warmer than the chalky baseline,
  stronger fracture/mineral separation and stronger roughness/AO response;
- `mediterranean_soil/refined_a` — more pebble/crust signal, reduced broad
  albedo waviness and stronger dry granular response.

Generator version 3 adds optional per-variant refinement scales for albedo,
roughness and AO. Variants without a refinement block retain the baseline
response.

The exact-SHA proof chain is:

```text
Material Forge author/render x 2
        -> dynamic catalog-count determinism
        -> pinned Blender 4.5.9 refined-pair reference
        -> UE refined limestone import canary + rollback
        -> real Landscape rock/soil blend on LandscapeComponent_230
        -> verify mask/projection/scene invariants
        -> rollback without saving map or assets
```

The Landscape proof uses WorldAlignedTexture/WorldAlignedNormal and the existing
bilinear + five-tap appearance-only smoothing. It changes neither geometry nor
PCG/PCGEx semantic ownership. Visual and whole-area performance acceptance
remain separate gates.

## Production-loop transfer optimization — Issue #402

The Material Forge proof keeps two artifact surfaces:

- a complete determinism/archive artifact containing the full catalog, both
  deterministic runs, Blender review evidence and logs;
- a slim UE canary artifact containing only the exact-SHA proof summary,
  run manifest and the two selected `refined_b` variants required by Unreal.

The UE canary verifies the slim artifact digest and receipt before use and records
the slim/full artifact sizes plus transfer duration.

Git LFS uses a persistent local object store at
`D:\yacs\cache\git-lfs\YetAnotherCyclingSim`. Disposable checkouts still
materialize the required packages, but repeated runs reuse verified LFS objects
and only fetch missing OIDs from the network. Receipts record selected objects,
cache hits/misses and fetch duration. Normal checkout cleanup does not own this
cache.

The canary deliberately retains `Content/**` as the proven editor startup set:
Unreal's Asset Registry scans Content during startup and LFS pointers are not
valid packages. Narrowing this set requires a separately proven startup-package
contract rather than guessing dependencies.

The refined single-material canary and the real rock/soil Landscape blend now
run in one UnrealEditor process. The accepted map loads once; the second phase
reuses the same editor/world, then both phases roll back transient assignments.
Separate sub-receipts remain available, plus one aggregate single-session
receipt recording phase timings and `editor_process_count=1`.

### Memory-safe single-session ordering

The first #402 benchmark proved that running the importer-only canary before the
Landscape blend left only ~4.17 GiB free physical memory, so the existing 8 GiB
Landscape preparation gate correctly failed closed.

The single-session order is therefore:

```text
load accepted map once
  -> real refined rock/soil Landscape blend + rollback
  -> Unreal garbage collection of unreferenced transient objects
  -> importer-only refined limestone canary + rollback
  -> aggregate receipt
```

The 8 GiB Landscape preparation threshold is not reduced. The importer-only
check reuses the already loaded accepted map and records `map_reloaded=false`.

## Interrupted self-hosted proof recovery

If a self-hosted Material Forge worker disappears mid-run while GitHub still
shows the job as `in_progress`, treat that run as stale evidence. Start a new
exact-SHA proof from the branch rather than reusing partial outputs; the workflow
concurrency contract will supersede the stale run when GitHub accepts the new
job. Never promote partial render/proof directories after a runner interruption.

### Compile-drain memory control

The refined Landscape proof must not overlap asynchronous texture compilation
with material/shader compilation. The editor diagnostics library now exposes two
explicit drains:

1. `FinishTextureCompilation` for the eight imported refined rock/soil texture
   objects (BaseColor, Normal, ORM and DetailMasks for both surfaces) before
   constructing the blended material graph.
2. `DrainAssetCompilationAndCollectGarbage` after material recompilation. It
   calls UE's `FAssetCompilingManager::FinishAllCompilation()`, runs full
   garbage collection and returns a JSON receipt containing outstanding compile
   counts and available memory before/after the drain.

The existing 8 GiB prepare and 6 GiB apply physical-memory gates remain
unchanged. The Landscape assignment is allowed only after all compilation has
drained and the post-drain memory measurement is recorded.

### Shader-memory checkpointing

The Material Forge Landscape proof distinguishes normal asset/texture compilation
from material shader compilation. The native diagnostics drain explicitly calls
UE 5.8 `FShaderCompilingManager::FinishAllCompilation()` and records:

- outstanding shader jobs before/after;
- local worker count;
- external ShaderCompileWorker physical/virtual memory;
- active worker count and maximum worker memory;
- host available physical/virtual memory before/after the drain.

The Python proof also records memory checkpoints after the appearance-mask
texture import, each refined surface import, texture compilation drain, material
graph construction, material recompilation and final asset/shader drain. These
measurements are diagnostic only and do not weaken the 8 GiB prepare / 6 GiB
apply fail-closed gates.

### Fixed-master bootstrap A/B proof

Run #16 isolated the catastrophic memory cliff to live
`MaterialEditingLibrary` graph authoring: free physical memory fell from about
12.35 GiB after texture compilation to about 0.95 GiB immediately after the
rock/soil graph was constructed, while shader jobs and external shader-worker
memory were both zero.

The next bounded proof therefore separates master authoring from Landscape
consumption. A first offscreen editor process builds and saves the exact
parameterized `M_MaterialForgeLandscapeBlend` master inside the disposable CI
checkout, then exits. A fresh second editor process loads that compiled master,
imports the exact refined rock/soil maps and appearance mask, creates only a
Material Instance, assigns it to the one-component Landscape canary and rolls
back.

This two-process form is temporary bootstrap evidence, not the final #402
single-session architecture. If it restores safe memory headroom and the
Landscape proof passes, promote the compiled master as a normal Git-LFS technical
UE asset and remove the bootstrap editor process so the production canary returns
to one editor process and one map load.

## Refinement B — Issue #413 owner visual pass

Refinement B is a visual-only follow-up to the technically admitted fixed-master
pipeline. It does not alter BOB geometry, the accepted map, or the PCG/PCGEx
semantic mask contract.

The selected pair is:

- `regional_limestone/refined_b` — neutralizes the warm cream/yellow bias and
  keeps limestone in a light mineral grey/cream family;
- `mediterranean_soil/refined_b` — lowers luminance and keeps a warmer
  ochre-brown mineral response so soil remains readable from medium and overview
  distances.

The earlier Refinement A variation mostly lived inside the 4 m surface tile.
Refinement B adds a second, deliberately larger appearance scale in the fixed
Landscape master. The existing material-local `DetailMasks.B` signal is sampled
again at a per-surface macro tile size and used only as a subtle BaseColor gain:

- rock: 24 m macro tile, 0.14 gain strength;
- soil: 12 m macro tile, 0.16 gain strength.

Both values are fail-closed to the 8–30 m range requested by visual review.
This remains a material-local appearance signal: it cannot classify, grow,
erode, or replace the authoritative 4033×4033 world mask.

The exact-SHA proof chain switches its Blender reference, slim UE input,
fixed-master canary and whole-Landscape 4K capture from `refined_a` to
`refined_b`. The same four cameras remain the owner-facing comparison surface.

Cliff cavities and vertical streaking are **not** considered solved by the color
pass. Their suspected sources remain geometry, normal response, AO/shadowing and
projection. Refinement B deliberately avoids hiding those defects with an
arbitrary albedo lift.

The same close camera therefore emits three additional diagnostic captures in
the whole-Landscape proof: `Unlit`, `Lighting Only` and `Detail Lighting`.
In Unreal 5.8, Unlit exposes Base Color without scene lighting; Lighting Only
uses a neutral material and omits material normal maps; Detail Lighting uses a
neutral material while retaining the original normal maps.

Interpretation is therefore explicit:

- defect persists in Unlit -> inspect BaseColor/projection;
- defect disappears in Unlit but remains in Lighting Only -> inspect scene
  lighting, geometry and self-shadowing;
- Detail Lighting is materially worse than Lighting Only -> normal-map response
  is contributing.

These three debug images are recorded separately from the four owner-acceptance
views and do not change the visual gate.

Admission is unchanged:

```text
Material Forge deterministic render x2
        -> Blender quick reference
        -> fixed-master UE canary + rollback
        -> whole-Landscape 4K four-camera capture
        -> owner A/B visual acceptance
```

Until that proof and owner review are green, PR #381 stays draft.

## Cliff lighting response pass

The three fixed-camera cliff diagnostics establish that the near-black cavities
are a lighting/geometry response, not a BaseColor defect: they disappear in
Unlit, remain in Lighting Only, and Detail Lighting only adds fine normal-map
structure.

The owner-review capture therefore uses a bounded, session-only outdoor lighting
stack before judging the material:

- ensure a Sky Atmosphere exists for the review session;
- preserve the existing Directional Light, or create the existing fallback sun
  only when the map has none;
- preserve an existing Sky Light, or create a transient fallback Sky Light at
  intensity 1.35;
- configure the transient fallback Sky Light at intensity 1.15 and disable the
  black lower hemisphere so the movable review light approximates sky/ground
  bounce instead of producing cut-out black cavities;
- explicitly call `RecaptureSky` after the atmosphere/light stack is ready;
- capture the same four acceptance views and three diagnostics;
- destroy all transient environment actors and recapture any pre-existing
  Sky Light during rollback.

This follows the UE 5.8 outdoor-lighting model rather than compensating with
BaseColor. The accepted map is still never saved, Material Forge does not own
lighting semantics, and geometry remains unchanged by this proof.

## FAST cliff visual loop

Issue #417 splits Material Forge review into two lanes.

**FAST** is an iterative, non-production lane for lighting/material review. It
reuses the latest successful `refined_c` slim canary input only when
`plan-rebuild` proves the current Material Forge fingerprint is unchanged and
the source-to-execution Git diff is limited to the approved visual-loop files.
It requires the warm verified editor binaries, fixed master and LFS cache from
the latest FULL proof; missing warm state fails closed as
`FAST_VISUAL_WARM_CACHE_REQUIRED`.

FAST applies the fixed-master instance only to canonical
`LandscapeComponent_230`, captures one 1920x1080 close cliff view, rolls back
the component override and transient lighting, records both artifact source SHA
and execution SHA, and marks its receipt `NON_PRODUCTION_FAST_VISUAL` with
`full_production_proof_required=true`.

**FULL** remains the production authority: deterministic catalog render x2,
Blender reference, exact-SHA UE proof, whole-Landscape 1024-component
assignment, four 4K acceptance views, three diagnostics and rollback.

The FULL artifact is also compacted. Raw `run-a` and `run-b` texture trees
are no longer uploaded twice after determinism is proven. The retained
`material-forge-mallorca-*` evidence contains both run manifests,
`comparison.json`, `proof-summary.json`, review evidence, Blender evidence
and a compact-evidence receipt. The two selected UE variants remain in the
separate slim canary artifact. Compact FULL evidence is fail-closed above
200 MiB uncompressed.

