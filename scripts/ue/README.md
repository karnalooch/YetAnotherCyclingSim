# YACS Stage 2 automation proof (`scripts/ue/`)

This directory contains the unattended automation layer for the Stage 2
performance / runtime integration proof.

## Entry point

```powershell
pwsh ./scripts/ue/Invoke-YacsProof.ps1
```

That single command will, in order:

1. Run `Preflight-YacsProof.ps1` (deterministic environment check):
   - repository root;
   - branch (`test/stage2-integration-performance-proof`);
   - HEAD (`a47d6e54ce2f4d72d774bcecc7c971b674b2ee53`);
   - dirty state (only the four pre-existing items are tolerated);
   - Unreal Engine installation and version;
   - project path;
   - machine / GPU;
   - resolution / profile context (recorded, not enforced).
2. Build `YetAnotherCyclingSimEditor` for `Win64 / Development` via
   `Engine/Build/BatchFiles/Build.bat`.
3. Run the documented Stage 2 Automation tests from the command line via
   `RunUAT.bat RunUnreal`:
   - `CyclingPhysics`
   - `CyclingSession`
   - `CyclingInput`
   - `CyclingRuntime` (incl. `CyclingRuntime.PausePreservesMotionState`,
     `CyclingRuntime.ZeroPowerCoastsOnFlat`,
     `CyclingRuntime.ZeroPowerDownhillDoesNotMeanStop`,
     `CyclingRuntime.FramePacing`)
   - `CyclingDiagnostics`
4. Export the machine-readable Automation report to
   `Saved/RuntimeProof/Issue49/Tranche4/AutomationReport/` using
   `-ReportExportPath`.
5. Parse the discovered/passed/failed counts from `index.json` and write
   `summary.json` + `summary.txt`.
6. Exit non-zero (`1`) on any genuine proof failure (test failure OR
   `RunUAT` exit code != 0).

All artifacts are written **only** under
`Saved/RuntimeProof/Issue49/Tranche4/`. That path is already covered by
`.gitignore` (the `Saved/*` rule), so the proof leaves no trace in the
working tree and requires no commit.

## Files

| Path | Purpose |
| --- | --- |
| `Preflight-YacsProof.ps1` | Standalone deterministic environment check. Dot-sourced by `Invoke-YacsProof.ps1`. Exits 2 on hard failure. |
| `Invoke-YacsProof.ps1` | Top-level orchestrator. The single command the owner runs. Exits 1 on any genuine proof failure. |
| `Invoke-YacsInsightsProof.ps1` | Issue #49 performance proof. Drives a rendered PIE pass at 1920x1080, captures `yacs_performance.utrace` (Insights), `yacs_performance.uestats` (`stat startfile`/`stat stopfile`), runs headless Insights analysis to TSV, and lets the surrounding `CyclingRuntime.RemoteProof` Automation test request a viewport screenshot. |
| `README.md` | This file. |

## Issue #49 performance proof

```powershell
pwsh ./scripts/ue/Invoke-YacsInsightsProof.ps1
```

This is independent from the Automation test pass. It uses the standard
engine-supported trace channels `cpu,gpu,frame,stats` (no permanent
custom trace instrumentation is required in C++). The CSV Profiler is
**not** used because the local install reports:

    StudioTelemetry.Provider.CSV is disabled for this application

The classic `stat startfile` / `stat stopfile` commands are still
honoured by the engine and emit `.uestats` regardless of StudioTelemetry
settings, so we capture that as an independent fallback artifact.

The viewport screenshot is requested by the surrounding
`CyclingRuntime.RemoteProof` Automation test, which also enables
`stat unit` / `stat unitgraph` via `GEngine->Exec`. The screenshot is the
visual acceptance evidence; the Insights TSV is the numeric source of
truth.

## Common flags

| Flag | Effect |
| --- | --- |
| `-SkipBuild` | Skip the editor build (assume an existing Development build is current). |
| `-TestFilter <filter>` | Override the default test filter. Example: `-TestFilter 'CyclingRuntime.PausePreservesMotionState+CyclingRuntime.ZeroPowerCoastsOnFlat+CyclingRuntime.ZeroPowerDownhillDoesNotMeanStop'`. |
| `-ExpectedBranch <branch>` | Override the expected branch (default: `test/stage2-integration-performance-proof`). |
| `-ExpectedHead <sha>` | Override the expected HEAD SHA. |
| `-ArtifactRoot <path>` | Override the artifact output directory (must be under `Saved/*`). |

## Artifacts produced

After a successful run the following files exist under
`Saved/RuntimeProof/Issue49/Tranche4/`:

```
preflight.json            # Machine-readable environment context
preflight.txt             # Human-readable environment context
build_editor.log          # UBT build output
automation_run.log        # RunUAT output
AutomationReport/         # RunUAT exported Automation report tree
index.json                # RunUAT top-level summary
summary.json              # Machine-readable proof summary
summary.txt               # Human-readable proof summary
```

## Pre-existing items that are allowed to be dirty

The preflight permits ONLY these four items to be modified relative to
`HEAD` (`a47d6e54...`):

- `Config/DefaultGame.ini`
- `Content/Prototype/Maps/L_CyclingTest.umap`
- `.kilo/`
- `YetAnotherCyclingSim/`

Any other dirty or untracked path causes the preflight to fail with exit
code 2 and the proof is aborted before the build runs. This is the
mechanism that protects the pre-existing tracked diff from being
overwritten.
