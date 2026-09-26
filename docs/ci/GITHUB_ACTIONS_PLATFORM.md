# GitHub Actions CI platform

## Status

GitHub Actions is the single active CI control plane for YACS.

CircleCI is retired. While the external CircleCI project remains connected, the
checked-in `.circleci/config.yml` is only a zero-workload tombstone so pushes do
not spend compute or persist storage.

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

## Promotion to automatic Unreal gating

During Phase 1, Unreal execution is manual and is not part of Aggregate CI.

Before enabling automatic Unreal gating:

1. prove a normal green canary;
2. prove the intentional-red canary fails closed;
3. document runner outage/break-glass behavior;
4. restrict automatic execution to trusted same-repository revisions;
5. add the Unreal lane to Aggregate CI only after the runner is considered
   operationally reliable.

## CircleCI retirement

After the CircleCI project is disconnected in its UI, delete
`.circleci/config.yml`. No production CI logic should be reintroduced there.
