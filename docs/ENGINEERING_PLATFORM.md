# Shared engineering platform

## Decision

4VELO and YetAnotherCyclingSim stay in separate application repositories.
They share governance, CI/security policy and reusable automation through the
Gumball platform, hosted at the compatibility coordinate:

```text
karnalooch/
├── stunning-pancake
├── YetAnotherCyclingSim
└── engineering-platform   # product name: Gumball
```

This keeps the Unreal Engine source/assets lifecycle independent from the
4VELO web/mobile/backend monorepo while reusing common engineering controls.

YACS adopts Gumball in **preserve-local** mode. Shared contracts may strengthen
the repository, but they must not silently replace stronger YACS-specific
Project automation, branch hygiene, Unreal proof, runtime acceptance or
product-specific CI.

## External tooling decision policy

Gumball remains the governance and proof plane, while YACS may reuse external
tooling for editor automation, DCC integration, project indexing and world
authoring.

For those external-tooling decisions YACS applies:

```text
Embark-first review
        |
        v
Epic-native Unreal capability
        |
        v
proven OSS
        |
        v
small YACS-specific tool only for the remaining gap
```

This is a review/adoption order, not permission to copy public source. Embark
projects are especially valuable as production-oriented architecture references,
but any code adoption still requires an exact revision, license evidence and
the provenance workflow. Public repositories must not be described as the full
internal ARC Raiders toolchain unless Embark documents that explicitly.

The preferred shape is a small set of high-level domain tools guarded by
Gumball, not a second broad automation framework.

## Active platform contract

YACS consumes the current reviewed **Gumball v0.6 line** from the immutable
commit:

`03eb6f6bc6cd2260349386489bffb005c44b3236`

That commit includes the v0.6 Proof Broker generation plus the later reusable
security-cost routing work. Shared workflow consumers must stay pinned to a
reviewed 40-character commit SHA; `@main`, moving tags and other mutable refs
are forbidden.

The previous repository-wide shared-workflow pin was Gumball/engineering-platform
v0.3.1 at:

`d9bc67e2b17436e9df1319a6345d0ec388f407fb`

Shared workflows consumed from Gumball are:

- reusable repository/LFS policy;
- reusable governance guard;
- reusable security baseline;
- reusable OpenSSF Scorecard.

Application-specific validation remains local. In particular:

- `.github/workflows/reusable-python.yml` owns the Python 3.14 reference-model checks;
- `.github/workflows/reusable-unreal.yml` owns the YACS code-only Unreal build/Automation lane;
- `.github/workflows/reusable-stage3g-full.yml` owns the YACS full world/asset proof contract;
- world, visual, performance and editor proofs remain YACS-owned.

The public CI entrypoint remains `.github/workflows/ci.yml`. Its final required
check is named exactly `Aggregate CI gate` and remains caller-local.

## Repository OS

YACS now declares the Gumball Unreal consumer profile through `gumball.yaml`.

The shared repository-operating policy lives in:

- `.gumball/repository-os.json`;
- `.github/workflows/repository-ops.yml`;
- `scripts/ops/repository_os.py`;
- `scripts/ops/github_ops.py`.

The current YACS policy deliberately keeps **Projects reconciliation disabled
inside generic Repository OS**. The existing YACS-specific
`project_automation.py`, `project-bootstrap.yml` and `project-status.yml`
remain the Project-board authority until a separate migration proves that the
generic Gumball reconciler is at least as strong.

Likewise, `branch-hygiene.yml` and `cleanup_merged_branches.py` remain valid
stronger local controls. Generic Repository OS may reconcile lifecycle metadata
and safe housekeeping, but must not weaken the YACS branch-safety contract.

Trusted Repository Ops owns the canonical shared PR label dimensions:

- `type:*`;
- `area:*`;
- `risk:*`;
- `ci:*`;
- lifecycle labels where applicable.

Proof-request/status labels remain owned by the Proof Broker and are not
managed by the generic label reconciler.

## Gumball v0.6 Proof Broker

YACS adopted the trusted Gumball v0.6.0 Proof Broker consumer pattern from
canonical Gumball commit:

`6c94ec9f4817df430c3b6d5fdbbc025578ebf950`

The broker remains preserve-local and has since received YACS-proven fixes.
Do not overwrite the YACS broker runtime/workflow with the generic platform
copy without reviewing those downstream differences first.

Broker orchestration is trusted on the YACS default branch:

- `.github/workflows/proof-broker.yml` runs trusted default-branch broker code only;
- `.gumball/proof-broker.json` is the proof allow-list;
- `scripts/ops/proof_broker.py` binds an authorized request to the exact open
  PR HEAD SHA and deterministic request id;
- heavy target workflows remain read-only unless a specific write capability is
  explicitly allow-listed;
- matching proof artifacts/successful runs are reused;
- queued/running work is deduplicated;
- failed work requires explicit `retry`;
- target-workflow `workflow_dispatch` remains an emergency fallback.

The enabled broker-managed heavy proof set is:

```text
/gumball proof r4-1b3-geometry
/gumball proof m3-hairpin-corridor
/gumball proof world-authoring-sp638
/gumball proof environment-performance
/gumball proof source-asset-audit
```

These targets are read-only proof workflows with exact-SHA/request-id inputs,
success-only reusable artifacts and separate failure diagnostics. The broker
does not make heavyweight Unreal work automatic on every PR update.

Mutating authoring workflows, release/full-asset validation and administrative
recovery remain outside the broker by design.

Reusable improvements discovered in YACS are recorded under
`.gumball/candidates/` for explicit downstream -> Gumball promotion.

## Governance guard

The shared Governance Guard protects rules that should not depend on memory:

- high-risk pull requests require `Auto-merge: manual`;
- external Actions and reusable workflows must use immutable 40-character SHAs;
- mutable Gumball/engineering-platform refs are rejected;
- fail-open `continue-on-error: true` is rejected in workflows;
- workflow-level `permissions: write-all` is rejected;
- a real caller-local `Aggregate CI gate` with a job-level `always()`
  fail-closed path must remain present.

Current Gumball policy also treats platform/governance surfaces such as
`AGENTS.md`, `gumball.yaml`, `.gumball/**` and `.github/**` as high-risk.

YACS adds Unreal-specific high-risk surfaces without weakening the platform
defaults:

- `*.uproject` / `*.uplugin`;
- module/toolchain files `*.Build.cs` and `*.Target.cs`;
- `Config/DefaultEngine.ini`.

Normal gameplay and physics source changes are not automatically high-risk
only because they live under `Source/`.

## Fail-closed baseline

The repository baseline requires:

1. repository hygiene and Git LFS policy;
2. governance/risk guard;
3. Python 3.14 reference-model tests with anti-no-op discovery protection;
4. correctness-focused Ruff checks;
5. dependency review where applicable;
6. incompatible-license checks for new dependencies;
7. CodeQL for Python and C/C++ using build mode `none`;
8. Trivy filesystem vulnerability, authentication-material and misconfiguration scanning;
9. CycloneDX source SBOM generation on non-PR runs;
10. OpenSSF Scorecard supply-chain posture audits;
11. YACS-specific Unreal/asset/runtime proof selected by the local change classifier;
12. a final local aggregate job that fails unless the expected proof graph is satisfied.

CodeQL build mode `none` is static analysis. It is never proof that the UE5
project compiles.

## Unreal self-hosted runner model

The old Phase-1/manual-only runner description is historical. Current YACS
validation is defined by `CI_VALIDATION_TIERS.md` and the local workflow graph.

Current operating model:

- same-repository pull requests classified as `ue_code` may run the trusted
  code-only Unreal build + Automation lane;
- `asset_full` world changes stay lightweight while the PR is Draft;
- moving an `asset_full` PR to Ready for review requires the exact-head full
  Stage 3G/YACS world proof before the aggregate gate can pass;
- explicit visual/performance/editor proofs remain separate decision-relevant
  checkpoints;
- broker-managed heavyweight proofs use exact-SHA intent/dedupe/reuse;
- self-hosted execution must never become a general executor for untrusted fork
  code with write credentials.

The exact cadence and acceptance contract lives in
[`CI_VALIDATION_TIERS.md`](CI_VALIDATION_TIERS.md). Historical runner rollout
documents remain useful evidence but do not override that SSOT.

## CI cost model

YACS follows the Gumball rule: **the cheapest trustworthy proof wins**.

Current strengths already present downstream include:

- superseded PR runs are cancelled;
- heavyweight world proofs are separated from cheap draft iteration;
- the R4.1 proof suite uses job-local **build once / boot once / prove many**;
- Proof Broker deduplicates and reuses exact-revision heavy proof evidence.

The local classifier now separates `ue_code` from `ue_tooling`.
Broad `scripts/ue/**` proof/editor/authoring changes no longer schedule the
automatic Unreal code build merely because of their directory. Only compiled,
critical-config or explicitly build-contract tooling paths set `ue_code=true`.

The classifier also emits `ci_cost_class=light|standard|heavy`, and the local
Aggregate gate validates that heavy Unreal/full-world impact cannot be
mislabeled as a cheaper class. Runtime-sensitive unknown paths fail closed to
the Unreal build path; ordinary unknown repository paths remain conservative
without automatically consuming the self-hosted runner.

## Unreal-specific repository policy

Git, not generated Unreal state, is canonical. Generated IDE/UE paths such as
`Binaries`, `Intermediate`, `Saved`, `DerivedDataCache` and `.vs`
must not be tracked.

Binary source/game assets with known large/binary formats use Git LFS.
Additionally, any tracked Git blob above 10 MiB must use Git LFS even when its
extension is not on the standard asset list.

These Unreal-specific values are passed as inputs to the generic platform
repository-policy workflow rather than hard-coded into Gumball.

## Tool capability contract

`tools/capabilities.yaml` declares generic tool capabilities and trust
boundaries. It does not replace the YACS-specific `ue-mcp.yml` configuration
or Unreal editor tooling.

Gumball owns the reusable capability vocabulary. YACS owns its editor/runtime
commands, environment-specific configuration and proof acceptance.

## Branch protection

**Current status (2026-09-30): enforced.**

Repository ruleset `main protection` (ruleset id `24173006`) targets the
default branch and currently enforces:

- pull requests for changes to `main`;
- strict required-status freshness;
- exact required status check: `Aggregate CI gate`;
- branch deletion protection;
- non-fast-forward/force-push protection;
- no configured bypass actors.

The current ruleset does **not** require a positive approval count or resolved
review threads. Those controls must not be claimed as enforced unless the
ruleset changes.

The Governance Guard remains inside the caller-local aggregate proof graph
rather than being configured as a second standalone required status check.

CI/security/workflow/toolchain/dependency-policy changes remain manual-merge
through the Governance Guard's `Auto-merge: manual` contract.

## Downstream -> Gumball feedback

YACS is both a Gumball consumer and an incubation environment.

After a reusable improvement to CI, governance, security, documentation,
tooling, MCP usage or agent workflow:

1. keep the YACS-specific implementation downstream;
2. extract the reusable invariant and failure behavior;
3. record downstream evidence under `.gumball/candidates/` when appropriate;
4. generalize and contract-test it in Gumball separately;
5. do not copy YACS-specific maps, thresholds, paths or acceptance rules into
   the shared platform.

Product-specific jobs remain in YACS.
