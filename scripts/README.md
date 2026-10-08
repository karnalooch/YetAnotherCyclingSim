# YACS scripts

Run maintained tools from `D:\yacs\project`. The machine-specific
`D:\yacs\workspace.json` supplies engine, data and cache locations.
Use the project Python environment (`.venv\Scripts\python.exe`) and PowerShell
7.4 or newer. Start with [the workspace guide](../docs/tooling/LOCAL_WORKSPACE.md).

## Everyday entry points

| Task | Entry point | Effect |
|---|---|---|
| Check the saved project before opening | `python scripts/manage_local_workspace.py doctor` | Checks paths, materialized assets and checkpoint identity; does not open UE |
| Open the accepted scene | `python scripts/manage_local_workspace.py open` or `D:\yacs\Open-YACS.cmd` | Opens the configured map; refuses a second editor |
| Start the GitHub runner | `pwsh -File scripts/runner/Start-YacsRunner.ps1` | Reuses an existing runner identity or starts one interactive listener |
| Check the Windows build host | `pwsh -File scripts/runner/Test-YacsWindowsHost.ps1` | Read-only host/toolchain and 50 GiB reserve checks |
| Bootstrap pinned PowerShell | `powershell -File scripts/runner/Install-YacsPortablePowerShell.ps1` | Installs/verifies PowerShell 7.6.6 under `D:\yacs\tools` without MSI/system PATH mutation |
| Verify pinned Blender headless lane | `python scripts/blender/run_headless.py smoke` | Runs the Blender 4.5.9 bpy smoke job and emits workspace proof receipts |
| Inspect disposable runner outputs | `pwsh -File scripts/runner/Clear-YacsRunnerWorkspace.ps1` | Preview only; applying requires the exact inspected plan and an idle worker |
| Install/update the runner tray monitor | `pwsh -File scripts/runner/Install-YacsRunnerMonitor.ps1 -Verify` | Installs the per-user task and verifies fresh monitor health |

Everyday scene changes update the existing UE session through Live Coding or
the appropriate data/material consumer. Opening a map is not rebuilding roads.

## Checkpoint and recovery tools

| Tool | Purpose |
|---|---|
| `ue/create_accepted_scene_checkpoint.py` | Run inside UE only for the authorized frozen-scene checkpoint procedure; creates persistent accepted content and refuses overwriting an existing checkpoint |
| `ue/verify_accepted_scene_checkpoint.py` | Run inside a fresh UE editor on the configured accepted map; checks stored geometry/materials/CUT traces, writes a receipt and closes that verification editor |
| `assets/restore_workspace_data.py` | Checks or restores the hash-verified external-data snapshot; preview by default, `--apply` restores missing files without overwriting existing files |
| `assets/Restore-YacsSaCalobraWorldData.ps1` | Restores the separately pinned CNIG source bundle; CI must pass its destination explicitly |

Read the workspace guide's restore procedure before running a checkpoint tool.
One-off migration scripts and old experiments belong in the local
`D:\yacs\archive\scripts` history, outside this maintained interface.

## Folder map and naming

For read-only road inspection, see the
[accepted cliff survey contract](../docs/tooling/SA_CALOBRA_CLIFF_EROSION_PASS.md#bidirectional-tpp-survey-of-the-current-scene).
`proof/sa_calobra_tpp_survey.py` plans both directions from verified frozen
outputs. `ue/sa_calobra_tpp_survey_capture.py` runs only inside its owning cliff
proof scene. `proof/package_sa_calobra_tpp_survey.py --root <survey-directory>
--expected-sha <capture-sha>` verifies and packages the captured evidence for
offline review; it never generates terrain or assigns visual acceptance.
`proof/retain_sa_calobra_tpp_survey.py --source <evidence-root>
--expected-sha <capture-sha> --run-id <run> --attempt <attempt>
--workspace-config <workspace.json>` retains verified completed evidence in the
configured persistent work directory without rerendering or overwriting notes.

| Folder | Responsibility |
|---|---|
| `runner` | Windows runner lifecycle, health, monitor and bounded maintenance |
| `ci` | Workflow admission, isolated build/cache handling and CI tests |
| `ue` | Unreal editor consumers, authoring and runtime proof scripts |
| `assets` | External source acquisition, provenance, preparation and restore |
| `geometry`, `worldgen`, `houdini`, `blender` | Geometry calculations and deterministic DCC/world-data producers |
| `proof`, `evidence` | Proof collection and durable evidence utilities |
| `ops` | Repository operations |

New PowerShell commands use `Verb-YacsPurpose.ps1`; Python commands use
`verb_subject.py`, with `test_<subject>.py` for tests. Shared Python modules may
use a subject name. Keep public names stable and update callers, imports, docs
and local launchers together when renaming. Historical filenames in old
receipts are evidence and must not be rewritten to imply a newer execution.
Internal runner hooks (`Invoke-YacsJobStarted.ps1`) and `Assert-*` helpers are
called by their owner scripts; they are not separate everyday commands.
