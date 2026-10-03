# Unreal Engine self-hosted CI runner

Issue: #24

## Status

This defines the GitHub Actions self-hosted runner contract while generic Unreal
code validation is still being promoted toward a required Aggregate CI gate.
GitHub is the single CI control plane.

The generic normal + intentional-red runner canaries are proven. The Stage 3G
authoring/final-proof **mechanism** is also proven: PR #155 / workflow run
`36258791131` completed exact trusted full-LFS authoring/final validation,
Automation, Map Check, visual capture and cleanup. This infrastructure proof does
not by itself satisfy the reopened Stage 3G visual/asset acceptance in #80.

## Required host

- Windows x64.
- Unreal Engine 5.8.x in a location discoverable by scripts/ue/Preflight-YacsProof.ps1.
- Git and Git LFS on PATH.
- PowerShell 7 (pwsh).
- Enough disk/RAM for a clean Development Editor build and Automation.
- No personal API keys, cloud credentials, browser profiles, SSH keys or unrelated secrets available to the runner account.

Required custom label:

    yacs-ue58

GitHub also applies its normal self-hosted label. The custom yacs-ue58 label is the workload gate and must be attached only to the intended Windows x64 UE 5.8 host; it must not be shared with unrelated public repositories.


## GitHub Actions execution model

YACS uses one CI control plane: GitHub Actions.

Lightweight checks run on GitHub-hosted runners:

- path classification;
- Python/reference tests;
- repository/governance policy;
- CodeQL and lightweight security;
- LFS pointer validation;
- optional manual Windows host probe.

Unreal workloads run on the repository-scoped self-hosted Windows runner with
the custom label `yacs-ue58`. The Unreal Engine installation stays on the
runner host and is never packaged into CI cache/workspace storage.

For code-only canaries, project LFS payloads remain unmaterialized and
`Test-YacsCodeOnlyCheckout.ps1` must pass before the Editor build starts.
Asset-heavy workflows such as Stage3G author/proof and `asset-full` may perform
an explicit full LFS checkout.

The runner remains restricted to trusted repository-controlled execution. No
public/fork PR code is allowed to execute on it. Canonical high-risk Stage 3G
asset changes may use the repository's trusted automatic `asset_full` path;
generic C++ PRs still require a separate exact-SHA Unreal proof until #24 Phase 3
is complete.

## Trust policy

The repository is public. Never execute untrusted fork PR code on this runner.
The first production caller must run the reusable Unreal job only for trusted
same-repository revisions. Fork PRs must be promoted/copied to a trusted branch
and revalidated before they can satisfy the final merge contract.

Do not add pull_request_target execution of PR code.

## Local canary before GitHub registration

From a clean checkout of the exact candidate commit:

    $head = (git rev-parse HEAD).Trim()
    pwsh ./scripts/ci/Invoke-YacsUnrealCi.ps1 -ExpectedHead $head

Pass requires:

- preflight green;
- UE version resolves to 5.8.x;
- YetAnotherCyclingSimEditor Win64 Development builds;
- requested Automation suites discover at least one test;
- no Automation failures/errors;
- Saved/RuntimeProof/CI/Unreal/unreal_ci_summary.json exists.

## GitHub rollout

Completed generic runner baseline:

1. [x] Register repository-scoped `yacs-home-ue58` with label `yacs-ue58`.
2. [x] Prove exact-SHA code-only checkout on the real home runner.
3. [x] Prove a normal green UE build + Automation run.
4. [x] Prove intentional zero-discovery fails closed.
5. [x] Prove artifact upload and unconditional workspace cleanup.

Canonical proof: workflow run `36240146312`, SHA
`9826b0f82d2a895a0a5d6fbf358aac162e199aa5`, UE `5.8.2`, normal canary
`13/13` passed.

Next:

6. [x] Prove Stage 3G authoring/final-proof mechanics on the trusted runner — PR #155 / run `36258791131`.
7. [ ] Reuse that proven lane for the reopened #80 asset/PCG visual recovery and require the same exact-SHA/LFS/visual evidence.
8. [ ] Complete Phase 2 readiness, including unattended Task Scheduler reboot proof.
9. [ ] Promote the reusable generic C++ Unreal lane to automatic trusted execution.
10. [ ] Add generic Unreal C++ validation to Aggregate CI only in Phase 3 and reconfirm #22 branch protection first.

## Adaptive Unreal build parallelism

Tracked by issue #257.

The generic self-hosted Unreal lane keeps UBA disabled because PR #143 recorded
a real Windows error 1455 / `VirtualAlloc failed` when the host was near its
virtual-memory commit limit. The CI profile therefore does **not** re-enable UBA
as a speed optimization.

The previous fixed `MaxParallelActions=2` cap was replaced by a bounded,
memory-aware policy using the preflight `FreeVirtualGb` value:

- below 8 GiB free virtual memory: 2 actions;
- 8 to <14 GiB: 3 actions;
- 14 GiB or more: 4 actions;
- the result is also capped to roughly two-thirds of reported logical CPUs.

The selected cap is written only to the run-local
`Saved/UnrealBuildTool/BuildConfiguration.xml` and is printed in the build log.
If memory pressure returns, CI automatically falls back toward 2 actions rather
than requiring another repository change.

The optimization baseline from 2026-09-29 was a green 22-action editor build on
the trusted runner with 6 physical/6 logical CPUs and 31.92 GiB RAM:
`MaxParallelActions=2`, UBA disabled, UBT execution time **165.07 s**. Changes
to this policy should compare against that baseline and keep the exact-head
Automation gate green.

## R4.1 in-job prepared workspace reuse

Issue #234 adds a narrow exception to repeated setup work, not to trust boundaries. A single manually dispatched R4.1 proof-suite job may reuse one prepared exact-SHA worktree across capability, topology, bounded hairpin and rider-close visual proofs.

The suite must:

- materialize the required Passo Giau LFS map once;
- build `YetAnotherCyclingSimEditor Win64 Development` once;
- write a prepared-workspace stamp containing the exact HEAD, worktree path, map byte count and build identity;
- require every child proof that skips standalone preparation to validate that stamp;
- never reuse that stamp or build state across jobs, worktrees or different SHAs;
- run unconditional `git reset --hard` plus `git clean -ffdx` cleanup after artifact upload.

Standalone proof wrappers remain self-contained when no prepared-workspace stamp is supplied.

## Workspace hygiene

The reusable job checks out with clean: true and runs git reset --hard plus
git clean -ffdx after artifact upload. No source-tree state from a previous job
is trusted. Build/test logs are retained for seven days.

## Clean Windows host recovery and bounded disk cleanup

Issue #341 adds three local operator tools. They install no third-party software,
store no credentials and do not change Unreal/world architecture.

After cloning the repository, audit a clean Windows host:

```powershell
pwsh -NoProfile -File .\scripts\runner\Test-YacsWindowsHost.ps1
```

The audit requires Windows x64, PowerShell 7.4+, Git/LFS, authenticated GitHub
CLI, Python 3.12+, Visual Studio C++ tooling, a Windows SDK, UE 5.8.2, an active
page file, a detected GPU and at least 50 GiB free on the runner drive. It is
read-only and fails closed when a required capability is absent.

Restore the admitted Sa Calobra CNIG source snapshot after authenticating `gh`:

```powershell
# Preview local/remote state; download nothing.
pwsh -NoProfile -File .\scripts\assets\Restore-YacsSaCalobraWorldData.ps1

# Download missing raw files, then verify all 17 files by size and SHA-256.
pwsh -NoProfile -File .\scripts\assets\Restore-YacsSaCalobraWorldData.ps1 -Apply
```

Existing files are never overwritten. An unexpected, wrong-sized or hash-invalid
file fails closed. The restore reads the unpublished draft release and writes only
the persistent `_yacs-world-data/sa-calobra-working-v1/manual-cnig` cache.

Preview bounded cleanup of versioned build/proof output:

```powershell
pwsh -NoProfile -File .\scripts\runner\Clear-YacsRunnerWorkspace.ps1
```

Deletion requires a second, explicit invocation. Copy `candidate_count` and
`estimated_reclaim_bytes` from the immediately preceding preview; apply mode
fails before deletion if either value changed:

```powershell
pwsh -NoProfile -File .\scripts\runner\Clear-YacsRunnerWorkspace.ps1 `
  -ExpectedCandidateCount $reviewedPreview.candidate_count `
  -ExpectedReclaimBytes $reviewedPreview.estimated_reclaim_bytes `
  -Apply
```

Set `$reviewedPreview` from a fresh `-Json` preview after inspecting its targets.
Only `Intermediate` and `DerivedDataCache` subdirectories inside direct workspace
children matching `_unreal-build-<run>-<attempt>` or
`_unreal-region-<run>-<attempt>` and older than the configured minimum age are
eligible. Entire workspaces are never deletion targets. Path ancestors and
candidate trees are checked for reparse points before inventory and apply.
Apply mode refuses an active `Runner.Worker` or workspace-scoped Unreal
process. It preserves runner registration/credentials, `_yacs-world-data`,
`_yacs-retained-lfs`, `_yacs-sa-calobra-assets`, Git LFS objects, known terrain
worktrees, `_unreal-ci-warm`, repository source, Content, Binaries, Saved/evidence
and all unknown directories. Byte totals are logical deleted-file sizes;
free-before/free-after is a separate measured volume observation.

The initial 2026-10-03 preview found 11 allow-listed directories totalling
14,308,989,232 bytes under the older whole-directory proposal. That proposal was
superseded by generated-subdirectory-only cleanup; its count and size must not be
used for current apply. No real runner deletion was performed for this change.

## Silent desktop monitor and local diagnostics

Issue #329 / PR #330 adds a read-only desktop companion in `scripts/runner/`.
**Owner update, 2026-10-02: no automatic popups.** The tray icon, explicit status
window, live logs and bounded health records remain. There is no toast/balloon
call, test-popup menu or automatic notification toggle.

The companion runs as a limited interactive logon task independently of the
runner, using built-in Windows Forms NotifyIcon without additional dependencies.
It reads `_diag/Runner_*.log` final job markers, never individual step successes.
The parser was checked against GitHub Runner v2.329.0 JobDispatcher and deployed
on v2.337.0. Unknown formats remain unknown; this monitor is not CI/proof authority.

Features:

- tray status/icons for observed jobs and their final results;
- diagnostic-silence records after 20 minutes during an observed job; silence is
  not proof of a hang and never triggers a restart;
- an explicit Status menu, live Worker diagnostics and Actions/diagnostic links;
- RAM/disk/service snapshots every 60 seconds;
- local `logs/monitor.jsonl`, rotated at 2 MiB into five archives plus current;
- Exit stops only the monitor, leaving the runner running.

No BOB semantic/visual acceptance is inferred. Old results are not replayed at
startup. A crashed listener can leave a last-observed job; GitHub is authoritative.
Raw diagnostic logs remain local and may contain sensitive workload information.

### Installation

Use PowerShell 7.4+ in the intended logged-in desktop:

```powershell
pwsh -NoProfile -File .\scripts\runner\Install-YacsRunnerMonitor.ps1 -Verify
```

Defaults: runner `D:\actions-runner-yacs`, companion `D:\yacs-runner-monitor`.
The task `YACS Runner Monitor-<user SID>` uses a limited interactive principal.
The installer copies only companion scripts outside mutable job workspaces.
It preserves runner credentials, hooks, debug settings, Unreal and service mode.
The dedicated directory permits the desktop user, Administrators and SYSTEM.
DACL changes are idempotent and do not modify audit policy/SACL. Installation
validates the directory before stopping the previous companion.

To remove the task while retaining logs and leaving the runner untouched:

```powershell
pwsh -NoProfile -File .\scripts\runner\Install-YacsRunnerMonitor.ps1 -Uninstall
```

### Native service configuration

An administrator can inspect/apply configuration for an already registered service:

```powershell
pwsh -NoProfile -File .\scripts\runner\Set-YacsRunnerService.ps1 -WhatIf
pwsh -NoProfile -File .\scripts\runner\Set-YacsRunnerService.ps1
```

This sets automatic startup and recovery delays of 60/120/300 seconds. It refuses
active workers and refuses to start a stopped service while its listener already
runs interactively. It never restarts a running service or re-registers a runner.
Capture prior startup/recovery settings before applying changes. Service recovery
does not resume a terminated job. GPU/editor service compatibility and reboot
acceptance remain separate; installing a tray monitor does not establish either.

### Remote installation and verification

The owner authorized host installation on 2026-10-02. `runner-monitor.yml` uses
the existing `yacs-home-ue58`, exact SHA, isolated Git config and a separate sparse
code checkout. It accepts only repository-owner manual dispatch from main. The temporary rollout
branch push trigger was retired after successful installation.
No Unreal build or service restart is part of deployment.

`Deploy-YacsRunnerMonitor.ps1` runs portable tests on Windows, resolves the logged-in
console identity and invokes the installer with `-DesktopUser` and `-Verify`.
Missing console users, unexpected hosts, SHA mismatches, service identities or
non-interactive startup fail. No account password is requested or stored.
Verification requires a running interactive process, running task, fresh health
record and explicit `popupsEnabled=false` from the current process. Receipts record
source SHA, file hashes, task/session/process, silent mode and prior-monitor survival.
They contain no raw runner logs or Windows account names.

Validation:

```powershell
pwsh -NoProfile -File .\scripts\runner\Test-RunnerMonitor.ps1
```

Portable tests cover result authority, unknown/failure/cancellation results,
partial lines/UTF-8, truncation, bounded reads, duplicate suppression, retention
and syntax. Initial installation run `37051642508` passed on Windows, but a
repeat install exposed an unnecessary SeSecurityPrivilege requirement in Set-Acl.
The DACL-only fix passed in run `37052190396`. These historical builds included
popups and are not evidence of the subsequently requested silent mode.
The service was observed **Stopped** while the interactive runner executed jobs.
No service migration was performed. Logoff/reboot behavior and manual menu visual
inspection remain unverified; do not describe them as tested.

Silent deployment run `37052438001` at `e7be03008b1f64c63472ab0f8f210dc42b1869fc`
passed on 2026-10-02: task Running, interactive session 1, fresh health and
`notification=disabled-by-owner`. The prior monitor remained alive between jobs
and observed a real Failed completion; earlier rollout observed Succeeded.
Installed runtime script bytes are unchanged by the documentation/workflow
closeout. Artifacts retain installed script hashes. Reinstallation with the
DACL fix succeeded, including run `37052190396` attempt 2. No popup API remains
in the deployed silent companion. Native service mode remains unchanged.

## Persistent isolated-build cache (Issue #355)

The serialized Unreal lane selects `_yacs-unreal-ci/active.json` before checkout
and isolated-build cleanup. It can point to `_unreal-ci-warm` or a verified
`_unreal-build-<run>-<attempt>`; do not manually delete the active worktree.
A missing or malformed pointer target fails closed and preserves build
worktrees for diagnosis. Selection is not cache approval: the normal resolver
still owns environment, fingerprints and binary checks. Publication happens
after green Automation/state recording and before terrain import, so a later
terrain failure does not lose successful compile evidence. See the
[validation-tier contract](CI_VALIDATION_TIERS.md#general-unreal-static--runtime--compile-reuse).
