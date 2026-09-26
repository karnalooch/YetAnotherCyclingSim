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

## Workspace hygiene

The reusable job checks out with clean: true and runs git reset --hard plus
git clean -ffdx after artifact upload. No source-tree state from a previous job
is trusted. Build/test logs are retained for seven days.
