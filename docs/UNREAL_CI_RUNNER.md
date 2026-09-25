# Unreal Engine self-hosted CI runner

Issue: #24

## Status

This defines the runner contract before the lane is connected to Aggregate CI gate.
The reusable workflow remains dormant for automatic CI. Phase 1 uses the manual
trusted entrypoint documented in `UNREAL_RUNNER_PHASE1.md` until a real runner is
registered and the normal + intentional-red canaries are proven.

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


## CircleCI machine-runner host bootstrap

CircleCI built-in steps such as `persist_to_workspace` run inside the task-agent,
not inside the PowerShell process spawned for a `run` step. Therefore job-level
`PATH` changes are not enough to provide `gzip` to workspace handling.

The current YACS runner is operated as a foreground/manual machine runner, not a
Windows service. It does not require administrator access.

Before launching the runner, configure the current user/process environment:

    powershell.exe -ExecutionPolicy Bypass -File scripts/ci/Configure-YacsCircleCiRunnerHost.ps1

The bootstrap keeps CircleCI working data on `D:`:

- `CIRCLECI_RUNNER_WORK_DIR=D:\CircleCI\YACS-Runner\Workdir`
- `CIRCLECI_RUNNER_TASK_AGENT_DIRECTORY=D:\CircleCI\YACS-Runner\TaskAgent`
- `C:\Program Files\Git\usr\bin` is added to the current user's PATH so a newly
  launched runner/task-agent can use the already-installed Git for Windows
  `gzip.exe` and `tar.exe`.

After running the bootstrap, launch/relaunch `circleci-runner` from that PowerShell
window (or from a fresh shell that inherits the user environment) before starting a
pipeline. No Windows service restart is expected.

The UE seed archive, persistent seed, job scratch, working directory, and task-agent
downloads remain on `D:`. No UE payload is copied to `C:`.

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

1. Register a repository-scoped self-hosted runner with the labels above.
2. Use `Actions -> Manual Unreal proof` from `main` for the Phase 1 trusted canary.
3. Prove one normal green run.
4. Prove one intentional fail-closed canary; never weaken the test to make it green.
5. Only then call .github/workflows/reusable-unreal.yml from .github/workflows/ci.yml.
6. Add the Unreal job to Aggregate CI gate and require exact success.
7. Reconfirm branch protection after #22 is completed.

## Workspace hygiene

The reusable job checks out with clean: true and runs git reset --hard plus
git clean -ffdx after artifact upload. No source-tree state from a previous job
is trusted. Build/test logs are retained for seven days.
