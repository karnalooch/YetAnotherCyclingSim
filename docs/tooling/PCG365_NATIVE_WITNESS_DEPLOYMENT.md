# PCG365 native witness: isolated Windows build and deployment boundary

**Issue:** #365, **PR:** #474, **branch:** `codex/365-world-graph`. This is a preparatory procedure, **not** authorization to restart the owner Editor or install new DLLs.

## Why the normal Windows CI may be waiting

The `CyclingSim CI` Unreal job in `.github/workflows/reusable-unreal.yml` uses `[self-hosted, yacs-ue58]` and checks `Get-YacsUnrealHostState.ps1`. A local/unknown interactive Editor has priority. When a Live Host owns the workstation, the job can remain queued or fail as `LOCAL_BUSY`. Neither outcome is permission to stop the running Editor. The 243-script Python lane and CodeQL checks are distinct from native Windows proof.

## Separate build from deployment

Authoring source: `D:\yacs\project`. The existing, running owner Editor uses a separately installed project rooted under `D:\yacs\work\level-editor-review\b9fddea3f602-y473save01`. These are distinct; verify the running process command line and loaded DLL location before every build. A previous successful UBT build applies only to its exact earlier source revision; never reuse its `PASS` for a changed C++ HEAD.

### Byte-pinned historical launcher and independent PCG365 Editor target

The original `YetAnotherCyclingSim.uproject` is an immutable dependency of the accepted #364 launcher snapshot. It must remain **exactly 1152 bytes, SHA256 `09fbd6cd85fbdd299a3e37cfb65658e1210183878516599c90b783acc1d8099b`**. This is not a changeable fixture or migration hash.

PCG365 now opts into Epic's `ToolsetRegistry` and `ModelContextProtocol` through the **separate** `Source/YetAnotherCyclingSimPcg365Editor.Target.cs` (`TargetRules.EnablePlugins`). The standard `YetAnotherCyclingSimEditor.Target.cs` and the original `.uproject` stay unchanged. The native stager compiles `YetAnotherCyclingSimPcg365Editor Win64 Development` with the **original, byte-pinned** `.uproject` and places any new output only in the dedicated candidate stage. Epic UE 5.8 UBT officially supports `TargetRules.EnablePlugins`; whether this target builds and loads with the pinned engine must be independently demonstrated by a fresh UHT/UBT receipt. A source declaration is not native runtime proof.

The eventual derived review Editor must explicitly enable those plugins through a separate, approved deployment/launch contract. Do not modify, repin or regenerate the historical accepted launcher project or its proof metadata to make CI green.

Use `scripts/ue/Prepare-YacsPcgWitnessStage.ps1` in the **local Windows source checkout**, with the 40-character SHA of the current PR HEAD:

```powershell
pwsh -NoProfile -File D:\yacs\project\scripts\ue\Prepare-YacsPcgWitnessStage.ps1 -ExpectedHead <exact-40-char-head> -Action Inspect
```

`Inspect` is read-only: it verifies clean tracked Git HEAD, the five immutable checkpoint package hashes, running Editor ownership, loaded editor-module locations and the separate build path. It never calls UE MCP, modifies the scene, or writes an output directory.

Only after that inspection is satisfactory, and with sufficient free space on D:, run:

```powershell
pwsh -NoProfile -File D:\yacs\project\scripts\ue\Prepare-YacsPcgWitnessStage.ps1 -ExpectedHead <exact-40-char-head> -Action BuildStage
```

`BuildStage` runs UBT for `YetAnotherCyclingSimPcg365Editor Win64 Development` using pinned UE 5.8.2, with `-NoHotReloadFromIDE` and `Assert-YacsBuildIsolation.ps1`. It requires a newly linked editor DLL, engine/project BuildId equality, clean tracked source, matching protected checkpoint hashes, and byte-for-byte verification of copied artifacts. It creates a **new** `D:\yacs\work\pcg365-native-witness-stage\<SHA>` folder containing the DLL, `UnrealEditor.modules`, optional PDB, UBT log, and `staging-manifest.json`. An existing stage directory is never overwritten. It **does not copy** anything to the running editor project.

### Important limitations and resolutions

- A successful isolated UBT result proves compilation/linking of the exact source, not that the new class is loaded or callable from the Live Host.
- `UYacsPcgWitnessInspectionLibrary` is a `UBlueprintFunctionLibrary`. `BlueprintCallable` does not automatically expose an authenticated Epic MCP tool. To bridge this safely without arbitrary remote execution, `UYacsPcgWitnessToolset` was implemented deriving from `UToolsetDefinition` (`#include "ToolsetRegistry/ToolsetDefinition.h"`) with `UFUNCTION(meta = (AICallable))`. It registers with `UToolsetRegistry` and is directly invokable by Epic's in-engine MCP server under `call_tool`.
- `attest_live_reduced_node()` can use `unreal.YacsPcgWitnessInspectionLibrary` only from inside a Python-enabled Unreal process. Its Python object registry and HMAC secret are process-local and cannot authenticate an external-process object by simple copying. The production `SafeMcpAdapter` must remain blocked until a trusted, session-bound bridge verifies a specific reduction node **before** any `GetNodeDataView`. For external callers, `BoundedPcgMcpClient.call_bounded` now bridges to `YetAnotherCyclingSimEditor.YacsPcgWitnessToolset.InspectReducedNodeOutput`, validating the receipt against the live session PID and minting authentic in-session witness tokens.
- The C++ `generation_token` was previously a newly generated UUID per inspection, **not a persistent graph-generation identity**. It now uses a deterministic MD5 content fingerprint over `(ActorPath, GraphPath, ReductionNodePath, OutputPin, TotalPointCount, TaggedDataCount, CombinedDataCrc)`. Identical data regenerated in the same graph can produce the **same** fingerprint; it is not a generation epoch or proof that no regeneration occurred. Treat it only as data-identity evidence and require fresh native re-attestation under exclusive graph access immediately before each bounded read. Pending that exact session/dispatch proof, `SAFE_MCP_BLOCKED` and `NATIVE_WITNESS_BLOCKED` remain engaged.
- The stage script does not inspect the in-memory dirty level state. Before any eventual restart, obtain a read-only Live Host/editor unsaved-work and asset hash receipt. No automatic save of the canonical `L_RoadSurface`, road or terrain is authorized.

## Staged deployment packages: source SHA first

**Do not use an old staged binary after any source change.** The previous `c4899ee0` stage and its UBT report were generated before the immutable-launcher compatibility fix. They are historical evidence, **not** deployable binaries for a future HEAD. A previous documentation revision listed a DLL SHA256 of `79dfa395...`, while the build report listed `d390bd39...`; neither is accepted without rehashing the exact stage bytes.

- Candidate stage: `D:\yacs\work\pcg365-native-witness-stage\<CURRENT_EXACT_HEAD>`.
- Trusted artifact identity is the **actual current stage** `staging-manifest.json`, cross-checked with independently recomputed `Get-FileHash -Algorithm SHA256` values for the DLL, module descriptor, optional PDB and UBT log.
- Verify `source_sha` equals `git rev-parse HEAD`, `build_target` equals `YetAnotherCyclingSimPcg365Editor`, `build_exit_code=0` and `engine_build_id` equals the installed engine's BuildId.
- Confirm that `UnrealEditor-YetAnotherCyclingSimEditor.dll` is **not loaded from the source build workspace**, that the current owner Editor's loaded binary hash remains the previously observed `706edb198abecb81...`, and that all five source checkpoint hashes remain unchanged.
- Do **not** copy from an older SHA-named stage, overwrite an existing stage, switch source world or claim `READY_FOR_CONTROLLED_DEPLOYMENT` merely because the old UBT build succeeded.
- The ordinary pinned `YetAnotherCyclingSim.uproject` is not a destination for MCP plugin registration changes.

### Rollback Plan

1. **Backup before deployment:** Before copying staged binaries to `D:\yacs\work\level-editor-review\b9fddea3f602-y473save01\Binaries\Win64\`, back up existing files to `D:\yacs\work\level-editor-review\b9fddea3f602-y473save01\Binaries\Win64\backup-706edb198abecb81\`.
2. **Emergency rollback:** In case of editor load failure or witness discrepancy, restore `UnrealEditor-YetAnotherCyclingSimEditor.dll` and `UnrealEditor.modules` from `backup-706edb198abecb81\`.
3. **Audit receipt:** Verify running editor module hash equals `706edb198abecb81b339498b0fb8847205cd4b66d4ef34829026ec593a4d97d5`.

## Controlled deployment (separate, owner-approved maintenance window)

1. Verify latest exact-HEAD UBT, full GitHub CI and byte-pinned `.uproject`; inspect the staged manifest, DLL hash, module BuildId, current Editor command line, session identity and loaded-module path. The PCG365 opt-in target is distinct from the ordinary Editor target.
2. Read-only check the unsaved world state. Preserve source packages, original release DLL/module metadata and current Live Host session evidence. Prepare a rollback to the **same previous immutable release**; no blind overwrite of shared modules.
3. Only after explicit approval for interruption, stop the specific owned Editor through the project's supported owner-control mechanism. Do not kill an arbitrary PID or let GitHub runner own the Live Host.
4. With no Editor process using the target binary, deploy through a separately reviewed versioned release transaction. Never do a hot-reload or copy individual binaries into a live project.
5. Reopen exactly the derived `L_PCG365_Rollout` consumer in the approved editor, prove that the expected module is actually loaded, then verify the fixed probe graph via in-process C++ (real `GetNumPoints`, graph topology, exact actor/graph/pin identity, <=256 points).
6. Verify trusted in-process-to-external witness binding and bounded `SafeMcpAdapter` dispatch, then perform the 65 × 65 m cliff pilot with native geometry/contact/hole/clearance/visual evidence. Stop and roll back on any mismatch.
7. Only after pilot admission, deploy the 63 bounded native PCGEx batches; preserve the road, source masks and globally frozen Landscape. Keep `performance_pass=false` until the separately approved benchmark.

## Acceptance statuses

`NATIVE_BUILD_PASS` applies to an exact-head UBT build with receipts. `STAGED_NOT_DEPLOYED` is not production acceptance. Until the controlled deployment and trusted witness-bridge proof, mark `NATIVE_WITNESS_BLOCKED`, `SAFE_MCP_BLOCKED`, `PILOT_NATIVE_BLOCKED` and `WHOLE_AREA_BLOCKED`. PR #474 remains Draft; do not merge or claim owner visual PASS.

