# PCG365 native witness: isolated Windows build and deployment boundary

**Issue:** #365, **PR:** #474, **branch:** `codex/365-world-graph`. This is a preparatory procedure, **not** authorization to restart the owner Editor or install new DLLs.

**Current owner direction (reaffirmed 2026-10-20): Houdini FIRST.** Houdini leads world generation and Pegasus lessons 06/07. Material Forge supplies surface appearance, Blender supports preparation and inspection, and Unreal Engine consumes the resulting world. This optional PCG365 diagnostic must not become a competing generator or delay the ordinary Editor's Landscape readback. The historical PCG pilot and rollout below remain deferred; this module repair does not authorize them.

## Why the normal Windows CI may be waiting

The `CyclingSim CI` Unreal job in `.github/workflows/reusable-unreal.yml` uses `[self-hosted, yacs-ue58]` and checks `Get-YacsUnrealHostState.ps1`. A local/unknown interactive Editor has priority. When a Live Host owns the workstation, the job can remain queued or fail as `LOCAL_BUSY`. Neither outcome is permission to stop the running Editor. The 243-script Python lane and CodeQL checks are distinct from native Windows proof.

## Separate build from deployment

Authoring source: `D:\yacs\project`. The existing, running owner Editor uses a separately installed project rooted under `D:\yacs\work\level-editor-review\b9fddea3f602-y473save01`. These are distinct; verify the running process command line and loaded DLL location before every build. A previous successful UBT build applies only to its exact earlier source revision; never reuse its `PASS` for a changed C++ HEAD.

### Byte-pinned historical launcher and independent PCG365 Editor target

The original `YetAnotherCyclingSim.uproject` is an immutable dependency of the accepted #364 launcher snapshot. It must remain **exactly 1152 bytes, SHA256 `09fbd6cd85fbdd299a3e37cfb65658e1210183878516599c90b783acc1d8099b`**. This is not a changeable fixture or migration hash.

PCG365 opts into the disabled-by-default project plugin `Plugins/YacsPcgWitness/YacsPcgWitness.uplugin`, together with Epic's `ToolsetRegistry` and `ModelContextProtocol`, through the **separate** `Source/YetAnotherCyclingSimPcg365Editor.Target.cs` (`TargetRules.EnablePlugins`). The reflected toolset, inspection library and registration lifecycle live entirely in that plugin's Editor module. The ordinary `YetAnotherCyclingSimEditor` module has no toolset header or dependency; restricting only its Build.cs dependency is insufficient because UHT must resolve reflected parent classes.

The standard `YetAnotherCyclingSimEditor.Target.cs` and the original `.uproject` stay unchanged. The native stager compiles `YetAnotherCyclingSimPcg365Editor Win64 Development` with the **original, byte-pinned** `.uproject` and prepares a dedicated candidate stage. Epic documents the [module boundary](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-modules), [plugin descriptors](https://dev.epicgames.com/documentation/en-us/unreal-engine/plugins-in-unreal-engine) and [target rules](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-build-tool-target-reference). Fresh UHT/UBT receipts are required for both the ordinary and opt-in target; a source declaration is not native runtime proof.

The ordinary Editor isolation first passed at `10e182ca9ab12894ba73787c9d9b6042cbef33fa`: [run 39411137356, job 118589885665](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39411137356/job/118589885665). A fresh ordinary build at `e2aed213870a7151106049a7b56953eaba919d6f`, [run 39413855349, job 118599568420](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39413855349/job/118599568420), also compiled the new L07 component-layout getter and passed 28/28 Automation tests (zero failed/skipped/errors, two warnings, including `CyclingInput.ErrorSafety`'s missing-route diagnostic). [Artifact 12261661100](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39413855349/artifacts/12261661100) has SHA256 `efcd65f69bbfdbec6d66d1fa05e3441c3bf696945a4cb92ab7e1ef57abf2a064`. The separate PCG365 target, optional plugin load and MCP discovery remain unverified. Subsequent native source changes require fresh evidence.

The first L07 consumer attempt on that source, [run 39413841851](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39413841851), stopped at its first 30 GiB disk-reserve guard before candidate creation, map hashing or Editor launch. Its [receipt and current recovery boundary](sidefx/LESSON07_MATERIAL_SETUP.md#isolated-consumer-readback-and-remaining-transfer-contract) do not establish geometry, collision or unchanged-map hashes. The ordinary consumer remains the priority; this disk blocker does not activate the deferred PCG365 rollout.

The eventual derived review Editor must explicitly enable `YacsPcgWitness` through its versioned deployment/launch contract, using the stage's `required_runtime_enable_argument=-EnablePlugins=YacsPcgWitness`. Its descriptor declares the supporting plugins. The stage records that argument and does not execute it. Do not modify, repin or regenerate the historical accepted launcher project or its proof metadata to make CI green.

Use `scripts/ue/Prepare-YacsPcgWitnessStage.ps1` in the **local Windows source checkout**, with the 40-character SHA of the current PR HEAD:

```powershell
pwsh -NoProfile -File D:\yacs\project\scripts\ue\Prepare-YacsPcgWitnessStage.ps1 -ExpectedHead <exact-40-char-head> -Action Inspect
```

`Inspect` is read-only: it verifies clean tracked Git HEAD, the five immutable checkpoint package hashes, running Editor ownership, loaded editor-module locations and the separate build path. It never calls UE MCP, modifies the scene, or writes an output directory.

Only after that inspection is satisfactory, and with sufficient free space on D:, run:

```powershell
pwsh -NoProfile -File D:\yacs\project\scripts\ue\Prepare-YacsPcgWitnessStage.ps1 -ExpectedHead <exact-40-char-head> -Action BuildStage
```

`BuildStage` runs UBT for `YetAnotherCyclingSimPcg365Editor Win64 Development` using pinned UE 5.8.2, with `-NoHotReloadFromIDE` and `Assert-YacsBuildIsolation.ps1`. It requires a newly linked witness DLL, module-to-DLL mappings and BuildId equality for both the project and plugin against the engine, clean tracked source, matching protected checkpoint hashes, and byte-for-byte verification of copied artifacts. It creates a **new** `D:\yacs\work\pcg365-native-witness-stage\<SHA>` folder; an existing stage is never overwritten.

The stage preserves **project-relative paths** for the plugin descriptor and four source files, plugin binaries, project runtime and ordinary Editor binaries, the pinned `.uproject` and the opt-in target. Optional PDBs, the UBT log and `staging-manifest.json` accompany them. In particular, `Binaries/Win64/UnrealEditor.modules` and `Plugins/YacsPcgWitness/Binaries/Win64/UnrealEditor.modules` remain separate. The manifest uses `schema_version=2`, `artifacts[].relative_path`, `module_manifests`, `witness_plugin` and `witness_module`. Its state is `STAGED_NOT_DEPLOYED`, `stage_layout=PROJECT_RELATIVE_OVERLAY_NOT_DEPLOYED` and `native_reader_loaded=false`. This is a binary/source overlay, not a self-contained map or runtime receipt. It **does not copy** anything to the running editor project.

### Important limitations and resolutions

- A successful isolated UBT result proves compilation/linking of the exact source, not that the new class is loaded or callable from the Live Host.
- `UYacsPcgWitnessInspectionLibrary` is a `UBlueprintFunctionLibrary`. `BlueprintCallable` does not automatically expose an authenticated Epic MCP tool. To bridge this safely without arbitrary remote execution, `UYacsPcgWitnessToolset` was implemented deriving from `UToolsetDefinition` (`#include "ToolsetRegistry/ToolsetDefinition.h"`) with `UFUNCTION(meta = (AICallable))`. It registers with `UToolsetRegistry` and is directly invokable by Epic's in-engine MCP server under `call_tool`.
- `attest_live_reduced_node()` can use `unreal.YacsPcgWitnessInspectionLibrary` only from inside a Python-enabled Unreal process. Its Python object registry and HMAC secret are process-local and cannot authenticate an external-process object by simple copying. The production `SafeMcpAdapter` must remain blocked until a trusted, session-bound bridge verifies a specific reduction node **before** any `GetNodeDataView`. For external callers, `BoundedPcgMcpClient.call_bounded` bridges to `YacsPcgWitness.YacsPcgWitnessToolset.InspectReducedNodeOutput`, validating the receipt against the live session PID and minting authentic in-session witness tokens. The previous common-module identity is rejected.
- The C++ `generation_token` was previously a newly generated UUID per inspection, **not a persistent graph-generation identity**. It now uses a deterministic MD5 content fingerprint over `(ActorPath, GraphPath, ReductionNodePath, OutputPin, TotalPointCount, TaggedDataCount, CombinedDataCrc)`. Identical data regenerated in the same graph can produce the **same** fingerprint; it is not a generation epoch or proof that no regeneration occurred. Treat it only as data-identity evidence and require fresh native re-attestation under exclusive graph access immediately before each bounded read. Pending that exact session/dispatch proof, `SAFE_MCP_BLOCKED` and `NATIVE_WITNESS_BLOCKED` remain engaged.
- The stage script does not inspect the in-memory dirty level state. Before any eventual restart, obtain a read-only Live Host/editor unsaved-work and asset hash receipt. No automatic save of the canonical `L_RoadSurface`, road or terrain is authorized.

## Staged deployment packages: source SHA first

**Do not use an old staged binary after any source change.** The previous `c4899ee0` stage and its UBT report were generated before the immutable-launcher compatibility fix. They are historical evidence, **not** deployable binaries for a future HEAD. A previous documentation revision listed a DLL SHA256 of `79dfa395...`, while the build report listed `d390bd39...`; neither is accepted without rehashing the exact stage bytes.

- Candidate stage: `D:\yacs\work\pcg365-native-witness-stage\<CURRENT_EXACT_HEAD>`.
- Trusted artifact identity is the **actual current stage** `staging-manifest.json`, cross-checked with independently recomputed `Get-FileHash -Algorithm SHA256` values for every listed artifact and both module manifests. Follow `relative_path`; do not flatten the overlay.
- Verify `source_sha` equals `git rev-parse HEAD`, `build_target` equals `YetAnotherCyclingSimPcg365Editor`, `build_exit_code=0` and `engine_build_id` equals the installed engine's BuildId.
- Confirm that none of the three candidate module DLLs (`YetAnotherCyclingSim`, `YetAnotherCyclingSimEditor`, `YacsPcgWitness`) is loaded from the source build workspace, that the current owner Editor's binaries match its freshly recorded preflight hashes, and that all five source checkpoint hashes remain unchanged. The historical `706edb198abecb81...` hash is not a substitute for current process identity.
- Do **not** copy from an older SHA-named stage, overwrite an existing stage, switch source world or claim `READY_FOR_CONTROLLED_DEPLOYMENT` merely because the old UBT build succeeded.
- The ordinary pinned `YetAnotherCyclingSim.uproject` is not a destination for MCP plugin registration changes.

### Rollback boundary

Before any authorized deployment, preserve the complete previous versioned release, its plugin enablement contract, both module manifests and all affected binaries. Roll back that same complete release and reverify its recorded hashes; do not combine old shared modules with a new plugin manifest. Staging alone does not authorize changing the accepted #364 review project.

The earlier single-module procedure referenced `D:\yacs\work\level-editor-review\b9fddea3f602-y473save01\Binaries\Win64\backup-706edb198abecb81\` and Editor DLL SHA256 `706edb198abecb81b339498b0fb8847205cd4b66d4ef34829026ec593a4d97d5`. Those values are retained as historical evidence, not a rollback plan for the new plugin overlay.

## Historical native registration startup race (2026-10-14)

The owner Windows audit reports a new running **derived-map** Unreal Editor process
(PID `45048` at observation time) with the staged `2b8b3784` DLL actually
loaded (SHA256 `02cea22e336213b8ceb7f009817b2c428cfceaa07b8cedd9c5823c0741c388e7`),
MCP HTTP port 8000 responding and Pixel Streaming signalling port 8888 active.
These are **owner-agent observations**, not fresh runtime measurements from a
GitHub code-review session. The independent `YACS Live Host` scheduled task
was reportedly stopped, and the self-hosted GitHub Actions runner service was
also stopped during maintenance; restoring approved task/runner ownership
requires a separate, non-disruptive operational audit.

The new C++ UClass exists in Unreal reflection but its toolset was **absent**
from MCP `list_toolsets`. The editor startup log records:
`LogToolsetRegistry: Warning: IsAvailable: Editor is not available`.
The existing module called `RegisterToolsetClass` only in `StartupModule()`
when `IsAvailable()` was true, then silently abandoned registration when
the editor subsystem was not yet ready.

UE 5.8's `FCoreDelegates::OnPostEngineInit` may **already have fired** before
a `PostEngineInit` module is loaded. Merely installing an `OnPostEngineInit`
listener in `StartupModule` is therefore not sufficient. The Editor module now
tries once and schedules a bounded **game-thread core ticker** to retry when
`UToolsetRegistry::IsAvailable()` eventually becomes true. It checks
`IsToolsetClassRegistered`, registers at most once, tracks ownership so
`ShutdownModule` never unregisters somebody else's toolset, and removes its
ticker on shutdown. A 120-second readiness timeout remains **blocked**, never
an automatic editor restart.

**Epic UE 5.8 MCP caches Tool definitions at startup.** After the class
reports `PCG365_WITNESS_TOOLSET_REGISTERED` in the editor log, execute the
documented editor-console command `ModelContextProtocol.RefreshTools`
through a supported authorized editor control and open a **new MCP session**.
Read-only verify `list_toolsets` and `describe_toolset` report the
**exact native toolset class and `InspectReducedNodeOutput` tool**.
Source code, UClass reflection, a compiling DLL and an open port alone
do not count as `NATIVE_WITNESS_PASS`.

**Important:** The previously deployed/staged DLL with SHA256
`02cea22e336213b8ceb7f009817b2c428cfceaa07b8cedd9c5823c0741c388e7`
is built from `2b8b3784` and **does not contain** the deferred-registration
source fix. The registration lifecycle now lives in the optional plugin's
`Private/YacsPcgWitnessModule.cpp`. Any source change needs its own isolated
exact-HEAD UHT/UBT build, fresh `staging-manifest.json`,
hash verification, and a newly authorized maintenance transaction.
**Do not overwrite that DLL while PID 45048 is active**, do not perform
hot-reload, do not kill the editor, and do not claim that repository code has
already modified the running process.

No `GetNodeDataView`, 65x65 m wall authoring or 63-batch rollout until the
native probe is genuinely registered, MCP discovery is refreshed and the
native graph/point-count/session safeguards have succeeded. The map
`L_RoadSurface` and five canonical package hashes must remain unchanged.

## Deferred historical PCG deployment sequence

This sequence records the previous PCG pilot plan. The current Houdini-first decision does not activate steps 5–7; closing Pegasus 06/07 takes priority. A future diagnostic-only deployment still needs its own concrete versioned release and authorized maintenance window.

1. Verify latest exact-HEAD UBT, full GitHub CI and byte-pinned `.uproject`; inspect the staged manifest, DLL hash, module BuildId, current Editor command line, session identity and loaded-module path. The PCG365 opt-in target is distinct from the ordinary Editor target.
2. Read-only check the unsaved world state. Preserve source packages, original release DLL/module metadata and current Live Host session evidence. Prepare a rollback to the **same previous immutable release**; no blind overwrite of shared modules.
3. Only after explicit approval for interruption, stop the specific owned Editor through the project's supported owner-control mechanism. Do not kill an arbitrary PID or let GitHub runner own the Live Host.
4. With no Editor process using the target binary, deploy through a separately reviewed versioned release transaction. Never do a hot-reload or copy individual binaries into a live project.
5. Reopen exactly the derived `L_PCG365_Rollout` consumer in the approved editor, prove that the expected module is actually loaded, then verify the fixed probe graph via in-process C++ (real `GetNumPoints`, graph topology, exact actor/graph/pin identity, <=256 points).
6. Verify trusted in-process-to-external witness binding and bounded `SafeMcpAdapter` dispatch, then perform the 65 × 65 m cliff pilot with native geometry/contact/hole/clearance/visual evidence. Stop and roll back on any mismatch.
7. Only after pilot admission, deploy the 63 bounded native PCGEx batches; preserve the road, source masks and globally frozen Landscape. Keep `performance_pass=false` until the separately approved benchmark.

## Acceptance statuses

`NATIVE_BUILD_PASS` applies to an exact-head UBT build with receipts. `STAGED_NOT_DEPLOYED` is not production acceptance. Until the controlled deployment and trusted witness-bridge proof, mark `NATIVE_WITNESS_BLOCKED`, `SAFE_MCP_BLOCKED`, `PILOT_NATIVE_BLOCKED` and `WHOLE_AREA_BLOCKED`. PR #474 remains Draft; do not merge or claim owner visual PASS.

