# GitHub Actions CI platform

## Status

GitHub Actions is the single active CI control plane for YACS.

CircleCI is fully retired and disconnected. The repository contains no
`.circleci` configuration and no active CircleCI helpers, caches, workspaces or
runner bootstrap path.

## Workload split

### GitHub-hosted

Use GitHub-hosted runners for lightweight, reproducible work:

- change classification;
- Python/reference tests;
- repository/governance policy;
- CodeQL and dependency/security checks;
- LFS pointer validation;
- branch/project automation;
- optional manual Windows host probe.

These jobs must not download Unreal Engine or large project asset payloads.

### Self-hosted `yacs-ue58`

Use the repository-scoped Windows runner for workloads that require the local
Unreal Engine 5.8 installation:

- manual code-only Unreal canary;
- intentional-red fail-closed canary;
- Stage3G author/proof;
- map smoke;
- visual proof;
- cook/package/full asset proof.

The engine stays installed locally on the runner. Do not package or copy it into
GitHub Actions cache, artifacts, or another hosted CI storage layer.

## LFS policy

Code-only Unreal canaries use:

- `GIT_LFS_SKIP_SMUDGE=1`;
- checkout with `lfs: false`;
- `Test-YacsCodeOnlyCheckout.ps1` before the Editor starts.

Asset-heavy workflows explicitly use a full LFS checkout and remain manual/
trusted-only during Phase 1.

## Cost model

The design is private-repository ready:

- short/light hosted jobs consume the included GitHub Actions allowance;
- heavy UE jobs run self-hosted and do not consume hosted runner minutes;
- no multi-gigabyte UE cache/workspace transport;
- artifacts are limited to concise logs, JSON, text and screenshots unless an
  explicit asset-authoring workflow requires source assets.

## Proven self-hosted baseline

On 2026-09-26 the repository-scoped `yacs-home-ue58` runner completed the
combined normal + fail-closed proof on workflow run `36240146312`, exact SHA
`9826b0f82d2a895a0a5d6fbf358aac162e199aa5`.

The normal canary built UE 5.8.2 and passed all **13/13** scoped Automation tests.
The controlled nonexistent-filter run discovered zero tests and was verified as
an expected fail-closed result. Artifact upload and unconditional workspace cleanup
also passed.

The one-shot workflow used only to obtain this baseline is retired. Permanent
manual Unreal execution remains available through `manual-unreal.yml`.

## Promotion to automatic Unreal gating

During Phase 1, Unreal execution is manual and is not part of Aggregate CI.

Before enabling automatic Unreal gating:

1. [x] prove a normal green canary;
2. [x] prove the intentional-red canary fails closed;
3. [ ] finish Stage 3G authoring/final proof under the Phase 1 trust model;
4. [ ] complete unattended Task Scheduler + reboot recovery proof before Phase 2;
5. [ ] document runner outage/break-glass behavior;
6. [ ] restrict automatic execution to trusted same-repository revisions;
7. [ ] add the Unreal lane to Aggregate CI only after the runner is considered
   operationally reliable and #22 branch protection is verified.

## CircleCI retirement

CircleCI has been disconnected and its repository configuration removed.
No production CI logic should be reintroduced there without an explicit
architecture decision.
