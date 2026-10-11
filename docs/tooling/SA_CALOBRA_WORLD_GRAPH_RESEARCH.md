# Sa Calobra #365 — primary research, tutorials and API ledger

**Status:** research supporting the [execution plan](SA_CALOBRA_WORLD_GRAPH_PLAN.md),
not native proof or implementation permission. Owner session date: 2026-10-11.
Code inspected: `8aca8d873f7a9f59e31ecc3b64d50ec5dbe99c7d`.

This is an original synthesis. “Save everything 1:1” means preserve the full
project plan, decisions, limitations and handoff in repository documentation;
it does not mean reproduce copyrighted tutorial text or pretend a video was
watched. The sources below were read as web documentation. No sample project,
asset pack or plugin was downloaded or installed for this planning task.

## Source hierarchy and retrieval limits

YACS SSOT owns scope, geography, physics and acceptance. Epic documentation and
installed engine source establish native capability; official PCGEx documentation
and authenticated pinned source establish extension behavior. Tutorials explain
mechanics but cannot license assets, select YACS terrain, define clearance or
prove an implementation. Public production examples inform boundaries, never
reveal an assumed internal recipe.

Canonical Epic pages below were accessible and identified **Unreal Engine 5.8**.
Several explicit `?application_version=5.8` variants returned `Internal Error` /
`not accessible via this tool`. Installed 5.8.2 headers provide patch-level API
inspection; native behavior remains NOT RUN.

PCGEx `llms.txt` and `llms-full.txt` were attempted first as repository policy
requires. Both returned `not accessible via this tool`; an independent read-only
HTTP attempt returned `Nieznany host. (pcgex.gitbook.io:443)`. Exact indexed node
pages were accessible. The indexes were **not** successfully read. Public GitBook
pages are rolling and cannot be represented as documentation pinned to 0.79.

The local GitHub CLI returned `error connecting to api.github.com`; the connected
GitHub API succeeded for issue/PR metadata and predecessor closeout. That CLI
failure is not a claim that all GitHub capabilities are unavailable.

## Practical tutorial sequence

Read in this order before future implementation. Each exercise is proposed and
must run only after implementation is resumed, in owned diagnostic content.
The first three entries are actual Epic step-by-step tutorials, not search leads.

| Tutorial | Learn / bounded exercise | Exclude from YACS adoption | Required local evidence |
|---|---|---|---|
| [Epic PCG Overview — Create a Simple Forest Volume](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-overview) | Follow graph/volume assignment, Landscape input, sampling, transform, spawner and Inspect/debug mechanics on an isolated fixture | Landscape creation/sculpting, tutorial trees, arbitrary density/scale and unqualified Fab assets | Actual graph assignment, completed generation and native point-to-instance mapping; repeat on authenticated masks only after qualification |
| [Epic FBX Static Mesh Pipeline](https://dev.epicgames.com/documentation/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine?lang=en-US) | Inspect import units, pivot, triangulation, materials and named collision meshes for one selected asset | Assuming a tutorial pivot or import preset is correct for every root/support shape | Native bounds/units/pivot, dependency inventory and reproducible import identity |
| [Epic Setting Up Collisions With Static Meshes](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-collisions-with-static-meshes-in-unreal-engine) | Inspect simple/complex collision and responses in the Static Mesh Editor | Assuming collision matches the visible surface or enables physical road admission | Explicit collision policy and independent support/render contact cases |
| [Epic Using PCG Generation Modes](https://dev.epicgames.com/documentation/unreal-engine/using-pcg-generation-modes-in-unreal-engine) | Compare bounded non-partitioned and partitioned output; inspect ownership and downstream grid behavior | Copying grid size/radii, enabling runtime generation or changing world streaming | Border/order/dedup/local-invalidation tests; all relevant packages survive reload |
| [Epic PCG Biome Quick Start](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-quick-start-guide-in-unreal-engine?lang=en-US) | Study data-driven separation of definitions, generators, filters and transforms | Installing Experimental Biome Core/Sample or taking sample flora/recursive generation as an approved dependency | Pattern evaluation only; any real dependency requires its own bounded decision |

The goal is not to reproduce a tutorial forest. The exit from tutorial study is
an API/assumption checklist for the actual #365 contract: authenticated input,
qualified footprint/contact, stable identity, owned generation and persistence.

## Primary reference ledger

| Reference | Verified technical point / use | Limitation |
|---|---|---|
| [Epic PCG Node Reference](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-framework-node-reference-in-unreal-engine) | Inspect available data/attribute/filter/projection/spawn operations before writing an adapter | Stock nodes do not automatically authenticate categorical raster/CRS/NoData or YACS clearance |
| [Epic FPCGProjectionParams](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PCG/FPCGProjectionParams?lang=en-US) | Position, rotation, scale and attribute policies are distinct controls | Declare them explicitly; local header defaults and native output must also be checked |
| [Epic UPCGComponent](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PCG/UPCGComponent) | Generation, cancellation, cleanup and managed resources have separate interfaces | Idle state alone is not successful generation |
| [Epic GenerateLocal](https://dev.epicgames.com/documentation/unreal-engine/API/Plugins/PCG/UPCGComponent/GenerateLocal) | Generation can be delayed/scheduled | A call return does not admit finished output |
| [Epic Using PCG with World Partition](https://dev.epicgames.com/documentation/unreal-engine/using-pcg-with-world-partition-in-unreal-engine) | Generated actor layer/HLOD/reference ownership needs explicit configuration | No automatic permission to change World Partition; enumerate saved external packages |
| [Epic PCG Biome Reference](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-pcg-biome-core-and-sample-plugins-reference-guide-in-unreal-engine) | Separate local generation and downstream spawning; inspect data-driven asset definitions | Defaults and painted subtype data are not Sa Calobra source truth |
| [Epic Electric Dreams Environment](https://dev.epicgames.com/documentation/unreal-engine/electric-dreams-environment-in-unreal-engine) | Reference for commented procedural assemblies and hybrid authored/procedural work | Sample geography, hardware budgets, assets and rendering configuration are not transferable admission |
| [Epic PCG Editor Mode](https://dev.epicgames.com/documentation/unreal-engine/pcg-editor-mode-in-unreal-engine) | Optional example of parameters/presets and authored tool data | Experimental mode is not a required dependency; painting cannot replace source masks |
| [Epic loading/saving utilities](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Editor/UnrealEd/UEditorLoadingAndSavingUtils) | Map loading and saving are explicit editor operations; load may discard unsaved context without a save dialog | Use isolated owned processes; direct SaveMap detail URL was unavailable, so only the class page was used |
| [Epic SavePackages](https://dev.epicgames.com/documentation/unreal-engine/API/Editor/UnrealEd/UEditorLoadingAndSavingUtils/SavePackages) | Supports an explicit package collection | Enumerate the whole owned graph/map/output closure and check actual bytes |
| [Epic SaveDirtyPackages](https://dev.epicgames.com/documentation/unreal-engine/API/Editor/UnrealEd/UEditorLoadingAndSavingUtils/SaveDirtyPackages) | Operates on loaded dirty packages | Too broad for owner-session bounded proof; never use as implicit Save All |
| [PCGEx Working with PCGEx](https://pcgex.gitbook.io/pcgex/working-with-pcgex) | Organization of configuration/filter, sampling and staging operations | Rolling docs; check the approved pin before adopting a node |
| [PCGEx Sampling](https://pcgex.gitbook.io/pcgex/node-library/sampling) | Sampling transfers query results into point data for later decisions | Sampled data is not World Authority by itself |
| [PCGEx Sample: Nearest Surface](https://pcgex.gitbook.io/pcgex/node-library/sampling/nearest/sample-nearest-surface) | Candidate for explicit collision-surface queries and output metadata | Nearest surface is not necessarily vertical ground; failure semantics conflict with readable local source |
| [PCGEx agent index](https://pcgex.gitbook.io/pcgex/llms.txt), [full index](https://pcgex.gitbook.io/pcgex/llms-full.txt) | Required discovery starting points for a future successful retry | Retrieval failed during this plan; no content claims made |

No Reddit/forum answer, search snippet, secondary video or DeepWiki summary is
used as API authority. Inaccessible `Sample : Texture` / `Selecting Entries`
pages are not cited as read; the relevant observations below came from local
source inspection and retain its authentication limit.

## Installed-source ledger

Engine root observed read-only: `D:/yacs/engine/UE_5.8/Engine`.
`Build/Build.version`: **5.8.2, Changelist 56702186**, compatible CL55116800.
Resolve that root through the current workspace configuration when resuming;
the path is evidence, not a portable hard-coded interface.

Paths below are relative to the engine root unless explicitly repository-owned.

| Capability and source | Source-level finding | Required future verification |
|---|---|---|
| `Plugins/PCG/Source/PCG/Public/PCGGraph.h` | `AddNodeOfType` and `AddEdge` are declared | Exact selected classes, pins, graph settings and saved graph readback |
| `Plugins/PCG/Source/PCG/Public/PCGComponent.h` and `Private/PCGComponent.cpp` | Delayed generation/cleanup, cancellation and separate generated/cancelled/cleaned notification paths exist | Observe terminal state for every component/tile; timeout must not imply success |
| `Plugins/PCG/Source/PCG/Public/Elements/PCGProjectionParams.h` | Position/rotation default true; scale false; attributes default `ExcludeAttributes` with empty list, merge `TargetValue` | Explicit policy must protect `stable_id`, `asset_id`, source provenance and qualified orientation |
| `Plugins/PCG/Source/PCG/Public/Data/PCGWorldData.h` | `bIgnorePCGHits=false`, `bIgnoreSelfHits=true`, `WorldStatic`, simple trace by default; landscape/actor/class/tag/input filtering exists | Filter the exact accepted owner, ignore generated content, declare collision/ray policy and verify miss/hit metadata |
| `Plugins/PCG/Source/PCG/Public/Elements/PCGWorldRaycast.h` | `UPCGWorldRaycastElementSettings`, direction/length settings and world query parameters exist | Prove finite query bounds, selected settings and actual contact behavior |
| `Plugins/PCG/Source/PCG/Public/Helpers/PCGWorldQueryHelpers.h` | Common hit/overlap filtering and metadata helpers exist | Wrong-owner and no-hit cases must fail closed |
| `Plugins/PCG/Source/PCG/Public/Elements/PCGStaticMeshSpawner.h` | Mesh bounds may be applied to output points; output attribute can overwrite a matching name; identical-spawn warning exists | Pre-spawn clearance must already use the real footprint; warnings are not duplicate prevention |
| `Plugins/PCG/Source/PCGEditor/Private/WorldPartitionBuilder/PCGBuilderSettings.*` | Native builder settings source exists | Exact command/arguments, coverage and resource effects were not qualified; no runnable builder command is claimed |

### PCGEx retained source: authentication remains open

Readable source was found at:

```text
D:/yacs/runner/_work/YetAnotherCyclingSim/YetAnotherCyclingSim/_phase2c-pcgex-cliff/Plugins/PCGExtendedToolkit
```

The research subagent could read files but `git -C ... rev-parse HEAD` and
`git -C ... status --short` returned `Permission denied`. The pinned GitHub
source fetch also failed. Thus the approved pin in the YACS bootstrap is known,
but this retained checkout's revision was **not independently authenticated in
this planning pass**. Prior kickoff claims and readable source are not upgraded
to an exact-pin or runtime PASS.

| Readable file relative to plugin root | Observation | Consequence |
|---|---|---|
| `Source/PCGExElementsSampling/Public/Elements/PCGExSampleNearestSurface.h` | Surface source, actor input, finite sampling distance, apply-sampling controls, result outputs and failed-sample pruning | Audit these exact settings on authenticated pin and installed reflection before graph authoring |
| `Source/PCGExElementsSampling/Private/Elements/PCGExSampleNearestSurface.cpp` | Uses collision overlap/closest-point operations and optional traces; readable failure path writes `Success=false` | Do not equate nearest with downward ground; do not rely on current web warning that failure leaves success unchanged |
| `Source/PCGExElementsSampling/Public/Elements/PCGExSampleTexture.h` | UV/failure controls exist; implementation uses sampled texture data | Does not establish categorical raster/no-data/grid authentication |
| `Source/PCGExCollections/Private/Elements/PCGExStagingDistribute.cpp` | Some material micro-selection paths incorporate point index as well as seed | Filtering/reordering may change variants; prove each chosen selection mode or keep stock deterministic selection |
| `Source/PCGExElementsSampling/Public/Elements/PCGExSelfPruning.h` | File exists | Algorithm/settings were not audited; no verified pruning recipe claimed |

**Unresolved mismatch:** nearest-surface web documentation and retained source
describe different failed-sample success behavior. Resolve against authenticated
`39a8f1bdc65b2c4613a1e87b71d93b4576db0a66` plus the exact allowed patch. Initialize
fresh contact metadata and test misses explicitly in either case. Do not copy a
warning into an executable contract without this check.

## Repository patterns and hazards inspected

- `scripts/ue/stage3g_author_pcg_forest.py`: useful graph/spawner pattern; deletes
  an existing graph before replacement. Do not replay it against accepted assets.
- `Source/YetAnotherCyclingSimEditor/Private/PCG/YacsPatchCandidatesSettings.cpp`:
  sequential RNG and accepted-count/rejection loops can shift later choices after
  a local exclusion edit. This is not stable-locality proof for #365.
- `scripts/ue/yacs_scene_composer.py`: root-offset or constant-Z fallback is not
  qualified terrain contact; a texture catalog entry is not a StaticMesh.
- `Source/YetAnotherCyclingSimEditor/Private/PCG/YacsPassoGiauPcgExGraphCommandlet.cpp`
  and `YacsSaCalobraPcgExCliffCommandlet.cpp`: delayed generation/tick/timeout
  patterns exist for commandlets. They do not authorize manual ticking of a live
  owner Editor or production reuse of old road/cliff recipes.
- `scripts/worldgen/Bootstrap-YacsPcgEx.ps1`: approved pin/license/patch identity
  exists; installation uses a destructive reset on an existing checkout and
  Validate rejects expected patched state. Future safe/idempotent correction is
  required before normal replay; none was made during planning.
- `scripts/ue/sa_calobra_geometry_collision_witness.py`: distinguishes nominated
  Landscape from whole-world hits but does not establish rendered contact.
- `scripts/ue/bob_road_earthworks_cut.py`: inspect Landscape identity/query patterns
  only; do not invoke its earthworks authoring or reuse its road contact tolerance.
- `scripts/ue/sa_calobra_saved_material_consumer.py`: useful independent prepare,
  reload and rendered-readback pattern; no PCG-specific persistence proof yet.

## Research conclusions and remaining decisions

| Decision | Planning conclusion | Must be settled before execution |
|---|---|---|
| Graph foundation | Stock native PCG, bounded source adapter where necessary | Selected 5.8.2 node/pin/settings and parity proof |
| PCGEx | Prepare the approved authoring dependency and useful native canary | Exact source/patch authentication, safe bootstrap, build/load and actual node behavior |
| Terrain contact | Separate authenticated source ground and accepted visible owner | Real datum/Z mapping, owner inventory, asset-specific numeric tolerances |
| Identity/locality | Source-anchored candidate ID, independent random channels, separate recipe fingerprint | Canonical schema and per-tile/halo contract; no sequential-index dependence |
| World scale | Full existing 2016.5 m square; sparse proof content first | Existing streaming/partition setup and complete coverage evidence |
| Persistence | Explicit owned packages; independent stored-state readback and real render | Actual PCG save behavior, external package closure and no regeneration masking persistence failure |
| Acceptance | Native technical delivery under current Gumball/CI, with final owner/FPS debt retained | Proper #365 proof routing on trusted default branch; exact-head results and review |

Research does not select a new asset provider, authorize plugin installation,
change proof policy, edit a source mask, or establish visual/performance admission.
