# Shared engineering platform

## Decision

4VELO and YetAnotherCyclingSim stay in separate application repositories.
They should share governance, CI/security policy and reusable automation through
a dedicated repository:

```text
karnalooch/
├── stunning-pancake
├── YetAnotherCyclingSim
└── engineering-platform
```

This avoids coupling the Unreal Engine source/assets lifecycle to the 4VELO
web/mobile/backend monorepo while still reusing the mature engineering controls
developed for 4VELO.

## Bootstrap in this repository

Until the dedicated `engineering-platform` repository is available, the shared
workflows are intentionally shaped as local reusable workflows:

- `.github/workflows/reusable-repo-policy.yml`
- `.github/workflows/reusable-python.yml`
- `.github/workflows/reusable-security.yml`

The public entrypoint is `.github/workflows/ci.yml`, whose final required check
is named exactly `Aggregate CI gate`.

Moving these workflows to `engineering-platform` should therefore be a small
caller change rather than another CI redesign.

## Fail-closed baseline

The bootstrap requires:

1. repository hygiene and Git LFS policy;
2. Python 3.14 reference-model tests with a minimum discovered test count;
3. correctness-focused Ruff checks;
4. pull-request dependency review at HIGH/CRITICAL threshold;
5. license checks blocking strong copyleft licenses incompatible with the
   current proprietary distribution intent;
6. CodeQL for Python and C/C++ using build-mode `none`;
7. Trivy filesystem vulnerability, secret and misconfiguration scanning;
8. a final aggregate job that fails unless every required workflow call reports
   `success`.

The CodeQL `none` build is deliberately not presented as proof that the UE5
project compiles. It is a hosted-runner static-analysis layer.

## Unreal-specific repository policy

Git, not generated Unreal state, is canonical. Generated IDE/UE paths such as
`Binaries`, `Intermediate`, `Saved`, `DerivedDataCache` and `.vs` must
not be tracked.

Binary source/game assets with known large/binary formats use Git LFS.
Additionally, any tracked Git blob above 10 MiB must use Git LFS even when its
extension is not on the standard asset list.

## Next platform step

Create `karnalooch/engineering-platform`, move generic reusable workflows and
policy documentation there, then consume an immutable/versioned reference from
CyclingSim. After CyclingSim proves the platform contract, migrate the common
parts of 4VELO incrementally; do not replace its working CI in one step.

The platform repository should own common action pins, token-permission policy,
dependency/license policy, Scorecard configuration and future safe auto-merge
logic. Application-specific jobs remain in each application repository.

## Branch protection after bootstrap

Once this PR is merged and the check exists on `main`, protect `main` with:

- pull request required;
- direct pushes blocked;
- exact required check: `Aggregate CI gate`;
- branch required to be up to date before merge;
- conversations resolved;
- force pushes blocked;
- branch deletion blocked.

CI/security/workflow/toolchain/dependency-policy changes remain manual-merge.
Safe auto-merge should be added only after the shared platform can independently
re-check risk, review state, required checks and mergeability.
