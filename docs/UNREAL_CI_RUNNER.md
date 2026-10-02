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

## Desktop notifications and local diagnostics

Issue #329 adds an optional, read-only desktop companion in `scripts/runner/`.
This is a local candidate until Windows host acceptance is recorded. The current
runner execution mode must be inspected on the host; historical notes do not
prove that a native service is installed or active.

The companion runs as a limited interactive logon task, independently of the
runner. It uses Windows Forms NotifyIcon (included in Windows PowerShell/.NET;
no gallery module or additional backend). It reads `_diag/Runner_*.log` final
job markers, not individual step results. Its parser was checked against
GitHub Runner `v2.329.0` JobDispatcher terminal messages. Unknown future log
formats remain unrecognized rather than reporting success. This is best-effort
local observability, never CI/proof authority.

Features:

- tray status and completion notifications, preserving failed/canceled/abandoned
  results and distinguishing `SucceededWithIssues` from plain success;
- one warning after 20 minutes without diagnostic writes during an observed job;
  silence is not proof of a hang and never triggers a restart;
- live Worker diagnostics, runner diagnostic folder and GitHub Actions links;
- RAM/disk/service snapshots every 60 seconds;
- structured `logs/monitor.jsonl`, rotated at 2 MiB into five archives plus the
  current file; this retention applies only to companion logs;
- a test popup, mute control and an exit command that leaves the runner running.

Clicking a popup opens the repository Actions page, not an inferred run URL.
BOB has no separate semantic result integration in this version. Completion
means the runner reported a job result, not that a human accepted a visual proof.
Windows notification settings and Do Not Disturb can suppress popups. Notifications
require a logged-in desktop. Old results are not replayed at companion startup.
An interrupted runner may leave the last observed job until another event;
check GitHub for authoritative state. Raw diagnostics remain local and can contain
sensitive workload information; the companion never uploads them.

Install from a reviewed checkout in the intended logged-in user's PowerShell 7.4+:

```powershell
pwsh -NoProfile -File .\scripts\runner\Install-YacsRunnerMonitor.ps1
```

Defaults: runner `D:\actions-runner-yacs`, installed companion
`D:\yacs-runner-monitor`. Both paths are configurable. The installer copies only
companion scripts, registers `YACS Runner Monitor-<user SID>` and starts that
limited interactive task. It does not change runner credentials, hooks, debug
variables, services, Unreal or workflow execution. Reinstallation stops/replaces
only that user's companion task. Installed scripts should remain writable only
by the intended user/administrators, never by an untrusted workload account.

Remove the task without deleting logs or touching the runner:

```powershell
pwsh -NoProfile -File .\scripts\runner\Install-YacsRunnerMonitor.ps1 -Uninstall
```

For an **already registered native runner service**, an administrator may run:

```powershell
pwsh -NoProfile -File .\scripts\runner\Set-YacsRunnerService.ps1 -WhatIf
pwsh -NoProfile -File .\scripts\runner\Set-YacsRunnerService.ps1
```

This configures automatic startup and service recovery delays of 60/120/300
seconds. It refuses any active Runner.Worker, never restarts a running service,
and starts an existing stopped service. A missing `.service` file fails with an
explicit registration prerequisite. It does not convert the visual runner into
a service or re-register it. Capture the existing service startup/recovery
settings before applying this administrative change. A restarted service does
not resume a terminated job.

GPU/visible-editor workloads retain the interactive-session requirement until a
separate host proof validates service compatibility. The pending unattended
reboot/GPU acceptance above is not satisfied by installing the companion.

Validation:

```powershell
pwsh -NoProfile -File .\scripts\runner\Test-RunnerMonitor.ps1
```

The portable tests cover parser authority, unknown/failure/cancellation results,
partial lines and UTF-8, truncation, bounded reads, duplicate suppression, log
rotation and PowerShell syntax. Before rollout completion, verify on Windows:
tray/menu and test popup, one real green and red job, mute, log rollover, logoff/
logon startup, task uninstall, permissions and the actual service configuration.
Do not launch a heavy Unreal build solely to test notification presentation.
