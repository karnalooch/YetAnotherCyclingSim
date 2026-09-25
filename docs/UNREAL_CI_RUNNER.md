# Unreal Engine self-hosted CI runner

Issue: #24

## Status

This defines the runner contract before the lane is connected to Aggregate CI gate.
The reusable workflow is intentionally dormant until a real runner is registered
and a local/canary proof is green.

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
2. Run a trusted canary using the exact reusable workflow.
3. Prove one normal green run.
4. Prove one intentional fail-closed canary; never weaken the test to make it green.
5. Only then call .github/workflows/reusable-unreal.yml from .github/workflows/ci.yml.
6. Add the Unreal job to Aggregate CI gate and require exact success.
7. Reconfirm branch protection after #22 is completed.

## Workspace hygiene

The reusable job checks out with clean: true and runs git reset --hard plus
git clean -ffdx after artifact upload. No source-tree state from a previous job
is trusted. Build/test logs are retained for seven days.
