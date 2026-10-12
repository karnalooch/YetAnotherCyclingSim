# Local runner workspace retention

**Status: PENDING execution evidence.** The owner authorized cleanup of stale
local runner work while active work remains unaffected. This document defines
the retention boundary; it does not claim any deletion, reclaimed space,
verified archive or successful restore. The coordinator must bind the execution
packet to its approved issue, exact code SHA and preview/apply receipts.

## Scope and protected state

Cleanup targets explicitly inventoried stale paths under `D:/yacs/runner/_work`
only. It does not delete remote branches, tags, releases or Git history. Preserve
the local canonical repository, `main` and the owner-designated release
`v0.3.1`, including their required LFS objects. Resolve their actual repository
and commit identities in the preview; do not confuse this retention instruction
with the historical Gumball v0.3.1 workflow pin described in
[Engineering Platform](../ENGINEERING_PLATFORM.md).

Always preserve active runner workers/jobs, editor sessions, native/GPU/build
owners and their workspaces. A failed or unavailable process query is UNKNOWN,
not idle. Never terminate an editor or worker to make cleanup possible.
Recheck activity immediately before each mutation; abort that candidate if
ownership, files or references have changed since preview.

Protect active cache pointers and their targets, runner configuration/credentials,
`_actions`, `_tool`, `_PipelineMapping`, retained LFS payloads and unknown paths.
Age, a leading underscore or a failed workflow are insufficient deletion proof.
Do not follow junctions, symlinks or other reparse points. Resolve every candidate
to an absolute path and verify containment in the explicit approved workspace.

Outside the cleanup scope, preserve `D:/yacs/project`, `worktrees`, `engine`,
`data`, `checkpoints`, `work`, `material-forge-v2-final`, `cache`, `archive` and
`runner/_yacs-retained-lfs`. Workspace configuration and every current cache,
checkpoint or evidence pointer must be inventoried before deciding that a
similarly named local copy is disposable.

## Existing tool boundary

[Clear-YacsRunnerWorkspace.ps1](../../scripts/runner/Clear-YacsRunnerWorkspace.ps1)
defaults to preview and requires `-Apply` for removal. Its present allowlist is
narrow: `Intermediate` and `DerivedDataCache` under versioned direct-child
`_unreal-build-*` / `_unreal-region-*` outputs in the canonical runner repository.
It does not authorize general deletion of old session directories, source,
Content, Saved or proof trees. Any broader session-retention implementation
needs its own explicit allowlist and reviewed execution manifest within the
owner's authorized local scope.

## Preview, archive, apply and rollback

The confirmed stale-probe design is **same-volume verified quarantine**, not
TAR/gzip copying or destruction. It moves reviewed stale run trees out of
`_work` to a dedicated retention directory under `D:/yacs/work`. This avoids
duplicating many old clones while approximately 38 GiB is available; that
observation is not a standing free-space guarantee. Moving directories on the
same volume does not reclaim their allocated bytes. Do not report disk-space
recovery or destroyed bytes from quarantine.

The [stale-probe helper](../../scripts/runner/archive_stale_probe_runs.py)
supports preview via `--plan-output`, followed by `--apply-plan` (alias
`--apply-reviewplan`) and the exact `--expected-plan-sha256`. The helper's name
does not imply a compressed archive. Its `--queue-owned-run` mode queues bounded
job work; it cannot apply a global cleanup. Use the implemented interfaces,
not ad-hoc filesystem sweeps.

1. Inventory absolute paths, owner/activity state, newest modification time,
   file/byte counts, source commit/run IDs and inbound pointers. Classify each
   item as protected, reproducible cache, archive-required evidence or UNKNOWN.
   UNKNOWN remains protected. Preview must list exact candidates and exclusions,
   expected counts/bytes and the selected archive destination outside candidates.
2. Before moving stale sessions, produce full relative-path, byte-size and
   file-SHA256 inventories, including directory structure, outside the source
   tree. Use a fresh same-volume quarantine destination; never overwrite an
   existing destination. Move the reviewed tree, then independently inventory
   the retained destination and verify exact before/after equality. File count
   or move exit0 alone is insufficient. All source assets and useful evidence
   remain recoverable; no content is intentionally discarded.
3. Apply only the immutable reviewed candidate set. Revalidate path containment,
   no-reparse constraints, activity, pointers and file identities. Abort on
   drift; do not broaden matching patterns or silently replace the preview.
   Use native PowerShell literal-path operations throughout, with no cross-shell
   string-built deletion. Record each result and preserve failures.
4. Record source/destination paths, retained logical bytes, protected-state
   checks and both inventories. Disk free space may be observed independently,
   but quarantine is not a disk-reclaim operation. Report partial completion
   and any post-move verification failure honestly; retain both locations and
   receipts for recovery rather than deleting either copy.
5. Rollback restores the verified quarantine tree to its original path only after
   checking that restoration cannot overwrite new active work. If the original
   path is occupied, restore to a separate diagnostic directory and reconcile
   explicitly. Recompute all manifest hashes after restoration; never claim
   rollback from quarantine existence alone.

## Job-local completion and manual preview

[Invoke-YacsJobCompleted.ps1](../../scripts/runner/Invoke-YacsJobCompleted.ps1)
handles exactly six known paths belonging to the completed run, preserving all
bytes through verified moves. [Start-YacsRunner.ps1](../../scripts/runner/Start-YacsRunner.ps1)
exports the completed-job hook. This narrow post-job retention is distinct from
a global sweep: a running worker cannot safely perform general host cleanup.
Hook configuration alone does not prove that any particular run was retained;
require its actual completion and before/after inventory receipts.

The coordinator's replacement `runner-space-recovery.yml` is owner-only,
`main`-only **PREVIEW ONLY**. It must not mutate stale sessions while its worker
is active. Applying an exact reviewed stale-probe plan remains a separate
idle-host operation. Deployment, hook execution, preview and actual quarantine
results are PENDING until their own receipts are attached.

## Phase 2: verified compression and retained-copy pruning

[compress_retained_probe_runs.py](../../scripts/runner/compress_retained_probe_runs.py)
is read-only by default. Its separate `--archive <verified-quarantine-receipt>`
mode requires `--expected-receipt-sha256 <SHA>` and writes a gzip-level1 TAR
outside `_work` without deleting the retained tree. An explicit owner-reviewed
`--minimum-age-hours 0` may admit a newly quarantined tree; it is not an implied
global retention default. Archive creation preflights available capacity and
verifies gzip CRC, all file SHA256/bytes and directory inventory. Links,
duplicate or escaping paths and nonempty NTFS alternate data streams reject.

Only a subsequent `--apply <compression-receipt>` with its exact
`--expected-receipt-sha256` may prune the retained directory. It repeats complete
archive readback and source/receipt verification immediately before removal;
the verified archive remains outside `_work`. This is the first phase that may
reclaim space. Report reclaim only after an actual successful prune receipt and
independent disk measurement. No prune has been evidenced in this document.

Restore verifies file bytes and directory structure. **NTFS ACLs are not
restored**; this is not a full NTFS metadata backup. Do not represent compression
or archive existence as a tested complete host restore.

## Current bounded retention observations

The owner additionally authorized removal of incomplete probe clones. Explicit
`--include-unborn-probes` is limited to dynamic official MCP source probe and
road-material source-proof runs with standalone Git metadata, exactly unborn
`master`, no refs files or packed refs, and no resolvable HEAD. Main/release and
shared metadata protections remain mandatory. Default previews still block
these cases. The diagnosed pair is `_official-mcp-source-probe-38044002365-1`
and `_road-material-source-proof-38044002446-1`; their surviving object packs
must pass the same complete archive verification before pruning.

The separately reviewed `--include-reviewed-remnants` opt-in admits only
numeric `b384` run directories ending in `-session-plugin`, `-input-boundary`
or `-input-boundary-plugin`, plus the exact older checkout
`_unreal-build-37639995352-1` and `_portable-powershell-bootstrap` in the
canonical runner repository. Active pointer, main/release and shared Git
protections still apply. Defaults and previously reviewed plans do not expand.

Minimal canonical fetch preserved `main` and `v0.3.1`, both resolving to
`4dd792219bfc2eaf7dc216bd60cbde6628bba792`; the canonical working checkout
remained at its separate `504bâ€¦` identity. The canonical checkout and accepted source assets are not cleanup targets. Active cache `_unreal-build-37690136030-1` remains protected.

The shared `s384` root has a Git-file relationship to the parent
`_official-mcp-native-probe` registry, so both are protected. These exclusions
must remain in preview/apply reports; do not claim all stale trees were removed.
Live preview03 is still RUNNING at this update. The separate two-entry
incomplete-clone plan has completed: both source trees were removed from
`_work`, full archives passed CRC and per-member SHA readback, and retained
copies were pruned. The archives contain 255,954,344 original file bytes in
251,172,263 compressed bytes. This byte difference is not an independent
filesystem free-space measurement.

Execution evidence is under
`D:/yacs/work/proofs/runner-retention-20261012/`:
`unborn-plan.json` SHA256
`856703f0b8d388f02f4ad94568161ccec0e4680fb62ceef801fc52ca6aada31e`,
`unborn-plan-execution-attempt01.json` (aborted before data mutation),
`unborn-plan-execution.json` (verified archives, readonly-file prune failure),
and `unborn-plan-recovery-execution.json` (COMPLETED, listener restored).
The recovery ran code `0d6f7b62` and restored missing entries from the verified
archives before repeating full source verification and normal prune. Initial
Windows `WinError 5` affected readonly Git pack index files; the fix retries
only the exact validated failed removal after setting its writable bit.
The recovered archive hashes are
`638bcdb1be3118a358832de7be91c627471c05de32df192a958a7eac6b9bb0f0`
and `3571b2fe127aedca5dbcdf2ab577aff07cbe9f8ed86836a04f32c6144a22e5de`.

The completed-job hook has been copied to stable
`D:/yacs/tools/runner-retention/Invoke-YacsJobCompleted.ps1` and runner `.env`
configuration updated. The listener was restarted with the stable hook path
explicitly inherited and a fresh listener PID verified after maintenance.
A real subsequent completed CI job has not yet proven hook execution.
The two incomplete-clone phase2 prunes passed; the main stale-tree sweep is
still PENDING execution.

## Evidence that is not disposable cache

Real GPU PNGs, native save/reload receipts, exact-head launch logs, failed crash
receipts and negative contact cases are historical observations; rebuilding
code does not reproduce their original bytes or replace their evidential role.
Saved diagnostic `.umap`/`.uasset` packages, uncatalogued local geometry, source
acquisition/license receipts and manually accepted checkpoints may have no
other recoverable copy. Preserve or hash-archive them before any session removal.

Concrete useful retained roots include `D:/yacs/work/proofs` (notably the accepted
#363 saved material consumer), `D:/yacs/work/pcg365`,
`D:/yacs/work/level-editor-review`, `D:/yacs/checkpoints` and
`D:/yacs/material-forge-v2-final`. Similar evidence inside `_work` remains
archive-required, even when its build caches are reproducible. Git-tracked
summary documents do not guarantee that all binary packages, raw measurements,
source files and GPU captures have been retained.

Read-only inventory observed `_work` children `_actions`, `_PipelineMapping`,
`_temp`, `_tool`, `b384`, `s384` and `YetAnotherCyclingSim`, plus multiple native
experiment directories in the repository workspace. This is inventory only;
none is classified as stale or safe to remove by its name. Execution and active
process verification remain PENDING in this document.
