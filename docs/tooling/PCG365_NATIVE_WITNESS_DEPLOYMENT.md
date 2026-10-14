# PCG365 native witness: isolated Windows build and deployment boundary

**Issue:** #365, **PR:** #474, **branch:** `codex/365-world-graph`. This is a preparatory procedure, **not** authorization to restart the owner Editor or install new DLLs.

## Why the normal Windows CI may be waiting

The `CyclingSim CI` Unreal job in `.github/workflows/reusable-unreal.yml` uses `[self-hosted, yacs-ue58]` and checks `Get-YacsUnrealHostState.ps1`. A local/unknown interactive Editor has priority. When a Live Host owns the workstation, the job can remain queued or fail as `LOCAL_BUSY`. Neither outcome is permission to stop the running Editor. The 243-script Python lane and CodeQL checks are distinct from native Windows proof.

## Separate build from deployment

Authoring source: `D:\yacs\project`. The existing, running owner Editor uses a separately installed project rooted under `D:\yacs\work\level-editor-review\b9fddea3f602-y473save01`. These are distinct; verify the running process command line and loaded DLL location before every build. A previous successful UBT build applies only to its exact earlier source revision; never reuse its `PASS` for a changed C++ HEAD.

Use `scripts/ue/Prepare-YacsPcgWitnessStage.ps1` in the **local Windows source checkout**, with the 40-character SHA of the current PR HEAD:

```powershell
pwsh -NoProfile -File D:\yacs\project\scripts\ue\Prepare-YacsPcgWitnessStage.ps1 -ExpectedHead <exact-40-char-head> -Action Inspect
```

`Inspect` is read-only: it verifies clean tracked Git HEAD, the five immutable checkpoint package hashes, running Editor ownership, loaded editor-module locations and the separate build path. It never calls UE MCP, modifies the scene, or writes an output directory.

Only after that inspection is satisfactory, and with sufficient free space on D:, run:

```powershell
pwsh -NoProfile -File D:\yacs\project\scripts\ue\Prepare-YacsPcgWitnessStage.ps1 -ExpectedHead <exact-40-char-head> -Action BuildStage
```

`BuildStage` runs UBT for `YetAnotherCyclingSimEditor Win64 Development` using pinned UE 5.8.2, with `-NoHotReloadFromIDE` and `Assert-YacsBuildIsolation.ps1`. It requires a newly linked editor DLL, engine/project BuildId equality, clean tracked source, matching protected checkpoint hashes, and byte-for-byte verification of copied artifacts. It creates a **new** `D:\yacs\work\pcg365-native-witness-stage\<SHA>` folder containing the DLL, `UnrealEditor.modules`, optional PDB, UBT log, and `staging-manifest.json`. An existing stage directory is never overwritten. It **does not copy** anything to the running editor project.

### Important limitations

- A successful isolated UBT result proves compilation/linking of the exact source, not that the new class is loaded or callable from the Live Host.
- `UYacsPcgWitnessInspectionLibrary` is a `UBlueprintFunctionLibrary`. `BlueprintCallable` does not automatically expose an authenticated Epic MCP tool. A narrow, reviewed native-in-process invocation bridge is still required. Do not enable arbitrary Python/code execution over Live Host.
- `attest_live_reduced_node()` can use `unreal.YacsPcgWitnessInspectionLibrary` only from inside a Python-enabled Unreal process. Its Python object registry and HMAC secret are process-local and cannot authenticate an external-process object by simple copying. The production `SafeMcpAdapter` must remain blocked until a trusted, session-bound bridge verifies a specific reduction node **before** any `GetNodeDataView`.
- The C++ `generation_token` is currently a newly generated UUID per inspection, **not a persistent graph-generation identity**. Until that is replaced or revalidated under an appropriate in-editor generation/dispatch lock, do not treat it as proof of the same data generation.
- The stage script does not inspect the in-memory dirty level state. Before any eventual restart, obtain a read-only Live Host/editor unsaved-work and asset hash receipt. No automatic save of the canonical `L_RoadSurface`, road or terrain is authorized.

## Controlled deployment (separate, owner-approved maintenance window)

1. Verify latest exact-HEAD UBT and GitHub CI; inspect the staged manifest, DLL hash, module BuildId, current Editor command line, session identity and loaded-module path.
2. Read-only check the unsaved world state. Preserve source packages, original release DLL/module metadata and current Live Host session evidence. Prepare a rollback to the **same previous immutable release**; no blind overwrite of shared modules.
3. Only after explicit approval for interruption, stop the specific owned Editor through the project's supported owner-control mechanism. Do not kill an arbitrary PID or let GitHub runner own the Live Host.
4. With no Editor process using the target binary, deploy through a separately reviewed versioned release transaction. Never do a hot-reload or copy individual binaries into a live project.
5. Reopen exactly the derived `L_PCG365_Rollout` consumer in the approved editor, prove that the expected module is actually loaded, then verify the fixed probe graph via in-process C++ (real `GetNumPoints`, graph topology, exact actor/graph/pin identity, <=256 points).
6. Verify trusted in-process-to-external witness binding and bounded `SafeMcpAdapter` dispatch, then perform the 65 × 65 m cliff pilot with native geometry/contact/hole/clearance/visual evidence. Stop and roll back on any mismatch.
7. Only after pilot admission, deploy the 63 bounded native PCGEx batches; preserve the road, source masks and globally frozen Landscape. Keep `performance_pass=false` until the separately approved benchmark.

## Acceptance statuses

`NATIVE_BUILD_PASS` applies to an exact-head UBT build with receipts. `STAGED_NOT_DEPLOYED` is not production acceptance. Until the controlled deployment and trusted witness-bridge proof, mark `NATIVE_WITNESS_BLOCKED`, `SAFE_MCP_BLOCKED`, `PILOT_NATIVE_BLOCKED` and `WHOLE_AREA_BLOCKED`. PR #474 remains Draft; do not merge or claim owner visual PASS.
