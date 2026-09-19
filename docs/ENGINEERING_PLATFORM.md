# Shared engineering platform

## Decision

4VELO and YetAnotherCyclingSim stay in separate application repositories.
They share governance, CI/security policy and reusable automation through:

```text
karnalooch/
├── stunning-pancake
├── YetAnotherCyclingSim
└── engineering-platform
```

This keeps the Unreal Engine source/assets lifecycle independent from the 4VELO
web/mobile/backend monorepo while reusing common engineering controls.

## Active platform contract

CyclingSim consumes the shared platform from the immutable reviewed commit:

`b34fda2ef31bf62e00422f8531202e2cccc3bc73`

Do not replace that reference with `@main`.

Shared workflows now come from `karnalooch/engineering-platform`:

- reusable repository/LFS policy;
- reusable security baseline;
- reusable OpenSSF Scorecard.

Application-specific checks remain local. In particular,
`.github/workflows/reusable-python.yml` still owns the Python 3.14
reference-model checks and no-op discovery protection.

The public entrypoint remains `.github/workflows/ci.yml`, whose final required
check is named exactly `Aggregate CI gate`.

## Fail-closed baseline

The baseline requires:

1. repository hygiene and Git LFS policy;
2. Python 3.14 reference-model tests with a minimum discovered test count;
3. correctness-focused Ruff checks;
4. pull-request dependency review at HIGH/CRITICAL threshold;
5. license checks blocking strong copyleft licenses incompatible with the
   current proprietary distribution intent;
6. CodeQL for Python and C/C++ using build-mode `none`;
7. Trivy filesystem vulnerability, secret and misconfiguration scanning;
8. CycloneDX source SBOM generation on non-PR runs;
9. OpenSSF Scorecard supply-chain posture audits;
10. a final local aggregate job that fails unless every required dependency
    reports `success`.

The CodeQL `none` build is deliberately not presented as proof that the UE5
project compiles. It is a hosted-runner static-analysis layer.

## Unreal-specific repository policy

Git, not generated Unreal state, is canonical. Generated IDE/UE paths such as
`Binaries`, `Intermediate`, `Saved`, `DerivedDataCache` and `.vs` must
not be tracked.

Binary source/game assets with known large/binary formats use Git LFS.
Additionally, any tracked Git blob above 10 MiB must use Git LFS even when its
extension is not on the standard asset list.

These Unreal-specific values are passed as inputs to the generic platform
repository-policy workflow rather than hard-coded into the shared platform.

## Rollout

CyclingSim is the first consumer used to prove the cross-repository contract.
After this migration is live-proven, common 4VELO controls may be migrated
incrementally. Do not replace 4VELO's working CI in one step.

Product-specific jobs stay in their application repositories.

## Branch protection

Protect `main` with:

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
