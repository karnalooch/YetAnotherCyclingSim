# Unreal Engine self-hosted CI runner

Issue: #24

## Status

This defines the GitHub Actions self-hosted runner contract before the Unreal
lane is connected to Aggregate CI gate. GitHub is the single CI control plane.
Phase 1 uses the manual trusted entrypoint documented in
`UNREAL_RUNNER_PHASE1.md`. The generic normal + intentional-red runner
canaries are proven; Stage 3G authoring/final proof remains before Phase 1 is
complete.

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

The runner is operated manually/trusted-only during Phase 1. No public PR code
is allowed to execute on it automatically.

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

6. [ ] Run Stage 3G authoring against `feat/stage3g-reference-environment`.
7. [ ] Commit/review authored LFS assets and run the final Stage 3G proof.
8. [ ] Complete Phase 2 readiness, including unattended Task Scheduler reboot proof.
9. [ ] Only then consider calling the reusable Unreal lane automatically from normal trusted CI.
10. [ ] Add Unreal to Aggregate CI only in Phase 3 and reconfirm #22 branch protection first.

## Workspace hygiene

The reusable job checks out with clean: true and runs git reset --hard plus
git clean -ffdx after artifact upload. No source-tree state from a previous job
is trusted. Build/test logs are retained for seven days.
