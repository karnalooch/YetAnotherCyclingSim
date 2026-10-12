# Natural20 contact process batching — #365 / M3

Status: local implementation candidate; native execution of this action is NOT RUN.
This changes process grouping only. It does not diagnose or claim to repair the
intermittent post-log-close access violation, or admit failed earlier receipts.

## Evidence and scope

Exact prior producer `d0e76c6026befb82c3862d96f8f3b719cfb4d8ed`, stage
`natural20-contact03`, completed batches 00–06 with clean process exit. Batch 07
wrote its raw measurements and receipt but exited `-1073741819` after normal log
close; its launcher completion marker is absent. Its result cannot be promoted.
The ten-point measurement-to-receipt spans for 00–07 were 9.752–12.110 seconds
per batch, 89.104 seconds total. This suggests the fixed 420-second process bound
can accommodate one complete 100-case measurement, but does not prove that run.

Installed UE 5.8.2 CL56702186 sources explicitly support `quit_editor()` after
`set_keep_python_script_alive(True)`: EditorPythonScriptingLibrary.h and
EditorPythonExecuter.cpp. The current script unregisters its Slate quit callback
before requesting editor exit. No concrete source-owned lifecycle defect or
current matching crash stack was established. The last log line is not process
success. Grouping reduces ten shutdown boundaries to one; it is not an AV fix.

## Single-process contract

After the unchanged inspect/material/material-reload/rock-collection/
rock-collection-reload prerequisites, `collection-contact-all` invokes the same
existing ten two-mesh batch measurements sequentially in one owned UE process.
It uses the same twenty saved meshes and five authenticated diagnostic sites,
33/65 grids, convergence-only 129 refinement, frozen physical gates, map/package
identities, raw serialization and terrain no-mutation boundary. No existing raw
file is copied or reused. All earlier stages and failures remain untouched.

Output layout:

- `proof/collection-contact-all/collection-contact-all-receipt.json`: one final
  receipt with ten ordered `batches` entries. Each contains `directory: batch-NN`
  and the complete original batch `result`, including all ten cases/raw identities.
- `proof/collection-contact-all/batch-NN/<mesh>-point<P>-grid<G>.json`: new raw
  samples. Child directories have no independent process completion markers.
- `proof/collection-contact-all/launcher-completed.json`: written by the existing
  launcher only after actual exit zero, expected status and exact source HEAD,
  unchanged staged/mesh/Forge bytes, dependency-load checks and receipt validation.

The unchanged launcher timeout remains 420 seconds. A crash, timeout, missing
batch or missing final marker rejects the entire all-action; partial files are
retained only as failed diagnostics. The old ten-process layout remains readable,
but a stage containing both layouts is rejected without fallback or promotion.

Fresh reload validates the final all-action marker and receipt, ten ordered batch
identities, all 100 unique mesh/point keys, every raw hash/size, source/catalog/
package/contact/map identities and consistent Landscape transforms. Its aggregate
binds the complete all-receipt hash and reports
`contact_execution_mode: SINGLE_PROCESS_ALL_BATCHES`. Render calls that same
reader before comparing the saved aggregate and selecting measured cases, then
rechecks source-receipt hashes after each capture. One
all-action marker does not claim ten independently exited processes.

## Retained limitations and verification

The five sites retain vegetation-selector diagnostic semantics; this change adds
no rock-mask/exclusion admission, fit adjustment, source-cap alternative or new
negative-control proof. Sampled contact is not continuous support, full asset
qualification, visual acceptance or scatter admission. `placement: false`,
`qualified_assets: []`, `DEFERRED_AFTER_M3` and `performance_pass: false` remain.
No terrain, road, source geometry, Material Forge appearance or engine/plugin
installation is changed. Local validation on 2026-10-12: 26 CPU tests passed
(contact 14, frozen policy 7, catalog 5); critical/default Ruff checks, PowerShell
parser, Git diff whitespace and all four docs-index guards passed. The reader
fixtures cover altered/missing exit markers, source/mesh/head drift, incomplete
or duplicate cases, altered/escaped raw files, mixed layouts, false child exit
claims and the existing ten-process readback path. Native execution of the new
action, real process completion, reload and GPU proof remain NOT RUN and require
a fresh committed exact-SHA stage.
