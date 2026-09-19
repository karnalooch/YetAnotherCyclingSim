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

CyclingSim consumes engineering-platform **v0.2.0** from the immutable reviewed
commit:

`a4c0f579aa10b495835dca3f78f84a79538392cf`

The previous live-proven contract was **v0.1.0** at
`b34fda2ef31bf62e00422f8531202e2cccc3bc73`.

Do not replace the active reference with `@main`, a moving major tag, or any
other mutable ref.

Shared workflows now come from `karnalooch/engineering-platform`:

- reusable repository/LFS policy;
- reusable governance guard;
- reusable security baseline;
- reusable OpenSSF Scorecard.

Application-specific checks remain local. In particular,
`.github/workflows/reusable-python.yml` still owns the Python 3.14
reference-model checks and no-op discovery protection.

The public entrypoint remains `.github/workflows/ci.yml`, whose final required
check is named exactly `Aggregate CI gate`.

## Governance guard

The shared Governance Guard protects rules that should not depend on memory:

- high-risk pull requests require `Auto-merge: manual`;
- external Actions and reusable workflows must use immutable 40-character SHAs;
- mutable engineering-platform refs such as `@main` or tags are rejected;
- fail-open `continue-on-error: true` is rejected in workflows;
- workflow-level `permissions: write-all` is rejected;
- a real caller-local `Aggregate CI gate` with a job-level `always()`
  fail-closed path must remain present.

CyclingSim adds Unreal-specific high-risk surfaces without weakening the
platform defaults:

- `*.uproject` / `*.uplugin`;
- module/toolchain files `*.Build.cs` and `*.Target.cs`;
- `Config/DefaultEngine.ini`.

Normal gameplay and physics source changes are not automatically classified as
high-risk only because they live under `Source/`.

## Fail-closed baseline

The baseline requires:

1. repository hygiene and Git LFS policy;
2. governance/risk guard;
3. Python 3.14 reference-model tests with a minimum discovered test count;
4. correctness-focused Ruff checks;
5. pull-request dependency review at HIGH/CRITICAL threshold;
6. license checks blocking strong copyleft licenses incompatible with the
   current proprietary distribution intent;
7. CodeQL for Python and C/C++ using build-mode `none`;
8. Trivy filesystem vulnerability, secret and misconfiguration scanning;
9. CycloneDX source SBOM generation on non-PR runs;
10. OpenSSF Scorecard supply-chain posture audits;
11. a final local aggregate job that fails unless every required dependency
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

CyclingSim is the canary consumer for engineering-platform v0.2.0.
4VELO must not adopt v0.2.0 until this canary PR has live-proven the complete
consumer CI and has been manually merged.

Product-specific jobs stay in their application repositories.

## Branch protection

Protect `main` with:

- pull request required;
- direct pushes blocked;
- exact required check: `Aggregate CI gate`;
- after v0.2.0 canary proof, also require the exact Governance Guard check as
  defense in depth;
- branch required to be up to date before merge;
- conversations resolved;
- force pushes blocked;
- branch deletion blocked.

CI/security/workflow/toolchain/dependency-policy changes remain manual-merge.
Safe auto-merge should be added only after the shared platform can independently
re-check risk, review state, required checks and mergeability.
