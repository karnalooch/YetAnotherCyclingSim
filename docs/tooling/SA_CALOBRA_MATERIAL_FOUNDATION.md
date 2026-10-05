# Sa Calobra material foundation

Issue [#363](https://github.com/karnalooch/YetAnotherCyclingSim/issues/363)
implements the Landscape material step after completed #335 / merged #362.
Methodology authority: [World Building Bible](../WORLD_BUILDING_BIBLE.md).
Delivery order: [Roadmap](../ROADMAP.md). This workflow describes a candidate,
not completed visual, reload or performance admission.

**2026-10-05 decision:** the current material appearance is rejected. The recipe
and mechanics below describe the retained prototype, not the accepted target.
Work has returned to [references and candidate discovery](../experiments/sa-calobra-material-reference-review-2026-10-05.md).
Unknown ground must receive a deliberately selected, visually approved fallback;
the prototype's reuse of `sparse_grass` is not that approval. Complete reference
and surface-library review before acquisition and controlled Unreal samples,
then admit samples before authoring the replacement whole-Landscape blend.

## Inputs and evidence boundaries

Resolve project, data, work and map through `scripts/manage_local_workspace.py`
and the host's `workspace.json`. Author only in the canonical live project.
The current consumer is `/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004`:
4033 x 4033 samples at 0.5 m, EPSG:25831, covering the whole 2016.5 m square.

`scripts/assets/prepare_sa_calobra_material_inputs.py` verifies the frozen PCG
and historical-cover manifests and their output hashes before packing weights.
R is a low-vegetation visual fallback, G a medium/high-class forest-floor
fallback, B the dated SIOSE open-rock share outside those vegetation selections.
A records accepted sample availability, not calibrated confidence.

These are presentation amplitudes, never current land-cover classification,
species evidence or planting authority. Missing classes remain named neutral
ground fallbacks. All hard exclusions and unknowns suppress RGB before and
after a radius-2-pixel presentation box filter (2.5 m window). Filtering neither
changes source masks nor fills unknown pixels. Quantized RGB sums stay <=255;
the material uses the remaining weight for neutral ground. The deferred red
review overlay and unadmitted diagnostic rock/soil candidates are not inputs.

The neutral ground is a configurable decorative PBR fallback reusing
`sparse_grass`, with separate neutral tint/roughness scale. Its normal and
roughness detail avoids a flat-color boundary against textured ground. This
does not assert grass/soil cover in excluded or unknown pixels; their evidence
and planting weights remain zero. Full source uncertainty is retained in the
manifests and the deferred diagnostic review, not encoded as a false biome.

An existing output directory is never overwritten. New recipe/input revisions
retain preceding evidence. Each manifest records producer, sources, bytes,
logical raster hash, grid and world mapping.

## Authoring and live review

`worldgen/materials/sa_calobra_foundation.json` owns texture families, metric
tiling, native functions, package and input identity. Existing Stage 3G Poly
Haven texture families have recorded CC0 provenance in the
[dependency ledger](../legal/DEPENDENCY_PROVENANCE.md). Their suitability for
Sa Calobra limestone remains unverified; an imported Alpine family name grants
no geographic admission.

`scripts/ue/inspect_sa_calobra_material_foundation.py` reads the installed
functions' pins/default descriptions and the current actor inventory.
It also follows each component's generated `MaterialInstances` parent chains.
The installed UE 5.8 `GetMaterial(0)` implementation returns the assigned
Landscape material and cannot by itself establish generated render-instance
consumption. Earlier GetMaterial-based 1024-component readbacks prove assignment;
they are not generated-instance or rendered-frame admission. The corrected
instance readback is required independently of the actor property.
UE Python's `get_editor_property` rejects these non-editor-visible arrays.
`UYacsTextureAuditLibrary::DescribeLandscapeMaterialInstances` therefore reads
their existing reflected native objects without mutation and follows constant
and dynamic instance parents. It adds no module/plugin dependency. Its source
contracts are installed UE 5.8.2 `LandscapeComponent.h`, `LandscapeEdit.cpp`,
`UnrealType.h` and `MaterialInstance.h`. Old authoring binaries can still inspect
assignment but explicitly report native instance verification unavailable.
The saved consumer requires the newly built audit and fails before material
application when it is absent. Build and run in the isolated verification
checkout; do not substitute Live Coding for new UFUNCTION reflection registration.
`scripts/ue/sa_calobra_material_foundation.py` runs in the existing editor:

```python
import runpy
foundation = runpy.run_path('D:/yacs/project/scripts/ue/sa_calobra_material_foundation.py')
foundation['apply_foundation']()
# Restore the preceding Landscape material without loading/saving a map:
foundation['apply_foundation']('original')
```

The producer rejects the wrong project, engine, map, grid, stale input hashes,
changed producer identity or asset collisions. Texture weights use linear color,
uncompressed BGRA8, nearest filtering, clamped addressing and no mipmaps.
Native WorldAlignedTexture/WorldAlignedNormal provide configurable metric
projection. Convex weighted color/roughness/normal blending preserves the
neutral residual. No displacement or WorldPositionOffset is connected.

Before/after checks compare actor transforms, Landscape component identities,
edit-layer names, nine height traces and the saved map hash. This is a bounded
live invariant check, not a replacement for full checkpoint geometry proof.
Default application saves neither assets nor the map; UE may independently
autosave recovery copies under ignored `Saved/Autosaves`. Preserve the owner's
other dirty packages. Asset saving is explicit and limited to the new material
and packed texture; never use Save All or save the owner's map as a shortcut.
The portable receipt `worldgen/materials/sa_calobra_foundation_asset.json` pins
the saved candidate, recipe, producer and input identities. Saved assets and
live component readback do not establish fresh reload, visual acceptance or
performance admission; those remain explicitly pending in the receipt.

`scripts/ue/review_sa_calobra_material_foundation.py` moves only the viewport
to nine distributed grid positions, keeping the camera above a separately
traced local surface. It uses native Look At rotation, verifies the camera
readback, completes the native loading barrier and compares the frozen scene.
These ground views supplement overview and road/rider inspection; they do not
constitute whole-area acceptance by themselves. Restore the original camera
with `review(restore=True)`; no actor is spawned or saved.

```python
review = runpy.run_path('D:/yacs/project/scripts/ue/review_sa_calobra_material_foundation.py')['review']
review(4)  # Central ground; 0 through 8 select distributed grid views.
review(restore=True)
```

`capture_ground_views(<new output directory>)` captures those nine views
serially with native editor screenshot tasks and records PNG hashes. It checks
task completion, a bounded timeout and the current run's engine errors. A
completed capture is not clean render admission. The first nine-view run
produced every PNG but logged UE's handled ensure at `RayTracing.cpp:1031`:
`Dynamic ray tracing instance skipped because geometry 'None' is evicted.`
The editor remained open; the cause and affected geometry are unverified.
Retain the diagnostic log, isolate the same camera/material consumer and resolve
or explicitly triage the renderer issue before runtime admission. Do not infer
an out-of-memory cause or disable ray tracing to manufacture a passing proof.

`scripts/ue/consume_saved_sa_calobra_material_foundation.py` verifies saved asset,
recipe, producer and map hashes before loading the saved material onto an
already loaded map. It verifies all component roots and the frozen scene, without
authoring another material or saving a map. Its `require_fresh=True` option
rejects an already resident candidate, so a live reapplication cannot be called
a fresh-process reload. Run fresh-consumer proof in an isolated verification
checkout; preserve the owner's existing editor session.

For an A/B comparison in the current authoring session, `baseline=True` selects
only the original material retained by the authoring cache; `restore=True`
returns to the material present before that comparison. Both paths verify all
1024 component roots and the frozen scene. The first same-camera comparison
showed grid artifacts in the preceding diagnostic material as well as sharp
rock transitions in the PBR candidate. This is diagnostic evidence, not permission
to repair frozen geometry or promote deferred cover classes. Missing engine-log
diagnostics are explicitly reported as unavailable rather than a clean capture.

`verify_saved_sa_calobra_material_foundation.py` is the fresh-process entrypoint.
It rejects the canonical authoring checkout, an unexpected Git HEAD or existing
evidence, loads only the pinned saved map and calls the saved consumer with
`require_fresh=True`. Set `YACS_2B_EXPECTED_HEAD` and `YACS_2B_RELOAD_REPORT` in
an isolated checkout and execute via UE's Python commandlet. A NullRHI run proves
saved data consumption and bounded scene invariants, not shaders, a rendered
frame, GPU performance or a compiled future C++ revision. Reuse binaries only
under the existing compile-reuse policy; never build the open authoring project.
Loading follows UE 5.8's installed `FileHelpers.h` and Epic's
[Python command-line workflow](https://dev.epicgames.com/documentation/en-us/unreal-engine/scripting-the-unreal-editor-using-python).

An isolated project build may use UE 5.8.2's supported `-NoHotReloadFromIDE`
option. Installed UBT `BuildConfiguration.cs` binds that option and
`HotReload.cs` otherwise checks a Live Coding mutex for the shared engine
executable, even when project outputs are separate. First verify that project
object/DLL outputs belong to the isolated checkout; preserve the authoring DLL
hash before/after. Never apply this option to build the open authoring project.
The first local attempt exited 6 at that guard; its retained retry succeeded
without changing the authoring editor DLL. Existing Stage 3G PCG deprecation
warnings are outside this material audit and remain unresolved.

At `43fecdbff5bd2cf250808e5153eed3147ba883cb`, the isolated fresh NullRHI
consumer exited 0, verified 1024 generated instance parent chains and rejected
both an incorrect expected parent and a null component. The frozen map hash
and bounded scene snapshot matched. GitHub run `37248459778` also passed its
Unreal build and 26 Automation tests. These are native integration checks;
they do not admit rendered frames, owner appearance acceptance or performance.
External evidence remains under the canonical work directory; the saved asset
receipt stays an immutable candidate receipt, not a fabricated admission.

Use `Invoke-YacsSaCalobraMaterialReload.ps1 -ExpectedHead <sha> -ArtifactRoot
<new absolute directory> -WorkspaceConfig <canonical workspace.json>` from that
isolated checkout after preparing verified reusable modules. The wrapper
resolves engine/cache paths through the workspace configuration and explicitly
passes `-ZenDataPath`, matching the normal workspace launcher. Without that
argument, the first attempted commandlet selected the default user cache and
restarted Zen with a different run context; it was stopped before Python ran.
The corrected invocation retains the canonical cache path. Process exit, fresh
asset consumption and renderer/performance admission remain separate results.
The next attempt read the candidate and all component roots but exited 1 because
other mounted Content packages were still LFS pointers (`Invalid value for
PACKAGE_FILE_TAG`). Hydrate the complete mounted Unreal Content tree, not just
selected map dependencies. The wrapper rejects those pointers before launch;
successful consumer JSON from an erroneous process is not reload admission.

## Version-matched tools audit

Verified editor: UE 5.8.2, changelist 56702186. Consulted Epic's
[MaterialEditingLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialEditingLibrary),
[texturing functions](https://dev.epicgames.com/documentation/en-us/unreal-engine/texturing-material-functions-in-unreal-engine),
and matching installed `MaterialEditingLibrary.h` / material expression headers.
Native function pins were additionally inspected in that running editor.
Viewport operations follow UE 5.8's
[UnrealEditorSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/UnrealEditorSubsystem),
[MathLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MathLibrary)
and [AutomationLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AutomationLibrary).
The installed recompile API returns compiler errors; empty means compilation
succeeded, but does not establish visual or performance acceptance.

GitHub API verified the reference revisions of Embark
[SkyHook](https://github.com/EmbarkStudios/skyhook/tree/fa8a44d51518303c0563d03b433b10145af7e51d)
and [UnrealClaudeFileHelper](https://github.com/EmbarkStudios/UnrealClaudeFileHelper/tree/2c87c3b4c433ab710b64ae348d0c0c55a927a641).
SkyHook separates transport from commands and uses UE Remote Control for Unreal;
the indexer is read/search tooling. Neither is a new dependency in this slice.

PCGEx GitHub API verified pinned revision
`39a8f1bdc65b2c4613a1e87b71d93b4576db0a66`, descriptor 0.79 / UE 5.8.0.
Official [Sampling documentation](https://pcgex.gitbook.io/pcgex/node-library/sampling)
was reviewed. Its agent indexes returned HTTP 403 during this audit; the pinned
descriptor/source remains independently accessible. No PCGEx graph executes in
this material-only step. Embark references do not establish Embark's PCGEx use.

## Required closeout

`prepare_sa_calobra_material_proof_map.py` prepares the existing isolated
checkout's map for a later standalone consumer. It first runs the fresh native
consumer verification, then calls UE 5.8.2 `EditorLoadingAndSavingUtils.save_map`
only in that checkout. Installed `FileHelpers.h` / `FileHelpers.cpp` define the
API. Native Landscape instances created in `LandscapeEdit.cpp` belong to the
saved world; rebuild APIs use editor-only setters and must not be called in
standalone Game mode.

Set `YACS_2B_PROOF_MAP_ACTION=prepare` or `reload`,
`YACS_2B_PROOF_MAP_REPORT` to a new absolute report path and the usual workspace,
exact-SHA and fresh-consumer report variables. Reload additionally requires
`YACS_2B_PREPARED_MAP_REPORT`. Use separate fresh commandlet processes for both
actions. Reports bind the original canonical hash and the derived proof-map
hash separately, plus material asset hashes, instance parents and bounded scene
invariants. Saving changes proof-map bytes; never describe the derived map as
byte-identical to the frozen source. It is a test consumer, not a new terrain
target or authoring map. Preserve its unique bytes before checkout cleanup under
the existing retention policy. No canonical save, terrain import, road builder,
ray-tracing change or performance measurement is part of this preparation.

Review different environments, steep surfaces, demanding overviews and rider
views across the whole Landscape; retain the Golden Kilometer as an additional
check. Resolve visible material defects before owner visual acceptance.
Prove saved assets and a fresh consumer reload separately from live review.
Execute the deferred 2A/2B performance measurement on this actual map/material
at the exact candidate SHA, using existing budgets, reference hardware and raw
Frame/GPU evidence. A legacy terrain-baseline map cannot prove this consumer.
Run source tests, all four documentation guards and the required Unreal/asset
proofs. Keep the PR draft until required admission passes. Step #364 remains
blocked until #363 is completed and its implementation merged with proof.
