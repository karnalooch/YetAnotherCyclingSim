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

CyclingSim consumes engineering-platform **v0.3.1** from the immutable reviewed
commit:

`d9bc67e2b17436e9df1319a6345d0ec388f407fb`

The previous live-proven CyclingSim contract was **v0.2.0** at
`a4c0f579aa10b495835dca3f78f84a79538392cf`.

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

## Gumball v0.6 Proof Broker

YACS adopts the trusted Gumball **v0.6.0 Proof Broker** consumer pattern from
canonical Gumball commit:

`6c94ec9f4817df430c3b6d5fdbbc025578ebf950`

This adoption is intentionally narrow and preserve-local. Existing shared
repository/security/governance workflows remain pinned to the reviewed v0.3.1
consumer SHA above; this change does not silently move those reusable workflow
pins.

Broker orchestration is local and trusted on the YACS default branch:

- `.github/workflows/proof-broker.yml` runs default-branch broker code only;
- `.gumball/proof-broker.json` is the proof allow-list;
- `scripts/ops/proof_broker.py` binds an authorized request to the exact open
  PR HEAD SHA and deterministic request id;
- heavy target workflows remain read-only and receive the exact SHA as an
  explicit input;
- matching proof artifacts/successful runs are reused, queued/running work is
  deduplicated, and failed work requires explicit `retry`;
- ordinary target-workflow `workflow_dispatch` remains an emergency fallback.

The first enabled consumer proof is `r4-1b3-geometry`. An authorized
write/maintain/admin actor can request it from the PR conversation with:

```text
/gumball proof r4-1b3-geometry
```

The broker does not make heavyweight Unreal work automatic on every PR update.

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
project compiles. It is a hosted-runner static-analysis layer. A real Windows/Unreal
build + Automation lane remains tracked in #24.

## Unreal self-hosted runner rollout

The real Unreal lane is introduced in phases; the current target is **Phase 1**.
The detailed operational and security plan lives in
[`UNREAL_SELF_HOSTED_RUNNER_PLAN.md`](UNREAL_SELF_HOSTED_RUNNER_PLAN.md).

Phase 1 deliberately does **not** join the normal PR gate:

- home PC is registered as a repository-scoped self-hosted runner with the
  dedicated `yacs-ue58` label;
- execution is manual through `workflow_dispatch`;
- no arbitrary `pull_request` event may schedule code on the home PC;
- checkout/proof is pinned to an exact trusted SHA;
- generated Stage 3G source assets are returned as workflow artifacts first;
  the runner does not receive repository write credentials merely to commit them;
- Stage 3G / #80 is the first canary workload;
- only after green and intentional-red canaries do we consider trusted automatic
  triggers and, later, inclusion in `Aggregate CI gate`.

This staged rollout keeps the public repository from turning a personal Windows
machine into a general-purpose executor for untrusted contributions.

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

CyclingSim is the canary consumer for engineering-platform v0.3.1.
4VELO must not adopt v0.3.1 until this canary PR has live-proven the complete
consumer CI and has been manually merged.

Product-specific jobs stay in their application repositories.

## Branch protection

**Current status (2026-09-25): not yet enforced.** GitHub currently reports `main.protected = false`; the remaining repository-admin work is tracked in #22.

Protect `main` with:

- pull request required;
- direct pushes blocked;
- exact required check: `Aggregate CI gate`;
- also require the exact Governance Guard check as defense in depth;
- branch required to be up to date before merge;
- conversations resolved;
- force pushes blocked;
- branch deletion blocked.

CI/security/workflow/toolchain/dependency-policy changes remain manual-merge.
Safe auto-merge should be added only after the shared platform can independently
re-check risk, review state, required checks and mergeability.
