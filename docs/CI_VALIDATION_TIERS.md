# CI Validation Tiers

YACS uses staged validation so world/art iteration stays fast without weakening the merge gate.

## Tier 0 — static / lightweight on every PR update

Runs for draft and ready PRs as applicable:

- change classification;
- repository and governance policy;
- Python/C++ security lanes when their paths change;
- code-only Unreal build for C++ and explicitly build-affecting Unreal changes;
- lightweight asset/LFS-pointer validation for asset changes.

Draft PRs are the normal iteration mode for world-building work.

### Gumball CI Cost Governor routing

The classifier emits a machine-readable `ci_cost_class`:

- `light` — documentation-only work;
- `standard` — Python, ordinary CI/tooling, proof/editor tooling and regular
  asset validation;
- `heavy` — compiled/build-affecting Unreal changes or `asset_full` world
  changes.

`scripts/ue/**` is **not** an automatic code-build trigger. Most scripts in
that directory are authoring/proof/editor tooling and remain on hosted
CI/contract lanes unless the exact path is part of the automatic code-build
contract. The build-sensitive exceptions are documented in
[`ci/CHANGE_CLASSIFIER.md`](ci/CHANGE_CLASSIFIER.md).

Unknown paths inside runtime-sensitive `Source/`, `Config/`, `Plugins/`
or `Build/` fail closed to the heavy `ue_code` path. Ordinary unknown
repository paths remain visible as `unknown=true` and receive conservative
security/contract validation without automatically burning the Unreal runner.

### Executable workflow lifecycle

The set of executable GitHub Actions workflows is governed by
[`ci/WORKFLOW_LIFECYCLE.md`](ci/WORKFLOW_LIFECYCLE.md) and the machine-readable
`.gumball/workflow-lifecycle.json` registry.

Historical Stage/R experiments remain valid evidence in PRs, docs and retained
scripts, but their branch-specific workflow files are not kept executable after
their branch/workstream is finished. Current M3 SP638/MASE proofs, explicit
performance/source-asset audits, manual recovery tools and broker targets remain
available.

The two legacy-named Passo Giau author workflows currently marked `UNKNOWN`
are retained only while active PR #256 owns their disposition. They must become
branch-independent CURRENT workflows or be retired when that workstream closes.

## Tier 1 — heavy Stage 3G proof at merge-candidate readiness

The full Stage 3G self-hosted proof is required only when both conditions are true:

1. the PR contains a path classified as `asset_full`; and
2. the PR is not a draft.

Transitioning a draft to **Ready for review** explicitly triggers CI, so the exact current head receives the full proof even when no new commit is pushed. Any later push to a non-draft PR re-runs the proof for the new exact head.

For `main` pushes, `asset_full` changes continue to run the full proof.

This means vegetation, material, water, lighting and other world-art iteration can be accumulated in a draft PR without paying for a full LFS checkout, authoring pass and three-point Stage 3G proof after every small commit.

## Gumball Proof Broker — explicit heavy proof intent

R4.1 heavyweight proof requests use the trusted Gumball v0.6 Proof Broker
instead of routine Actions-UI clicking.

Current configured proof:

```text
/gumball proof r4-1b3-geometry
```

The broker runs from trusted default-branch code, authorizes the requester,
resolves the open same-repository PR HEAD to an exact 40-character SHA, verifies
the allow-listed target workflow contract, then dispatches that workflow with
the exact SHA and a deterministic request id.

For one proof + PR + exact SHA:

- existing matching artifact -> reuse;
- successful matching run -> reuse;
- queued/running matching run -> do not duplicate;
- failed matching run -> explicit `retry` is required;
- explicit authorized request -> dispatch;
- non-critical automatic heavy request -> defer.

The target R4.1B.3 workflow keeps `workflow_dispatch` as a recovery fallback,
but broker-driven dispatch is the normal path. Heavy proof still runs only when
explicitly requested; this changes the control plane, not the evidence bar.

## R4.1 prepared proof-suite reuse

For the bounded Stage 3G R4.1 terrain/road diagnostics, the canonical heavy manual lane uses **build once, boot once, prove many** inside one trusted runner job:

1. exact-SHA clean checkout once;
2. targeted materialization of the persisted Passo Giau map once;
3. one `YetAnotherCyclingSimEditor Win64 Development` build;
4. one `UnrealEditor.exe` process for the complete bounded proof bundle;
5. Geometry Script capability -> SP638 topology -> bounded hairpin -> rider-close local visual proof inside that same Editor process;
6. evidence-only validation after the Editor exits, with no second UE boot.

The prepared-workspace stamp is valid only inside that exact worktree/job and records the exact HEAD, map byte count and editor build identity. The in-editor dispatcher is fixed-scope and repository-owned; it accepts no arbitrary Python, console commands, map paths or asset paths. Every proof JSON is annotated with the exact HEAD and the single Editor process id. Existing child wrappers retain their standalone cold path, but the canonical suite invokes them in `-ValidateOnly` mode so their assertions are reused without reopening Unreal.

The single-Editor session is **job-local**, not a daemon and not a cross-commit warm cache. A new exact SHA still gets a fresh clean checkout and a fresh Editor boot. This preserves reproducibility while eliminating repeated startup/shutdown inside one proof run.

The R4.1 heavy visual suite remains an explicit `workflow_dispatch` checkpoint. Deterministic kernel/contract tests stay automatic. This reduces runner cost and visible Editor churn without weakening the later human visual gate, performance checkpoint or Stage 3G full closeout proof.

## Tier 2 — visual acceptance checkpoint

Visual History captures at 1200 / 4900 / 8000 m are produced when a world slice is a review candidate, not for every art edit.

The candidate must retain:

- BEFORE / NOW / AFTER provenance;
- exact SHA / PR / CI provenance;
- repository-retained images and SHA-256;
- AFTER = PENDING until visual acceptance.

## Tier 3 — performance / package / release evidence

Performance, package/cook and other long-running proofs run when their evidence is decision-relevant:

- before closing a performance-sensitive roadmap slice;
- before merge when the slice has an explicit performance budget;
- on `main` / release checkpoints;
- manually when investigating a regression.

Stage-specific authoring/performance workflows should default to `workflow_dispatch` or another explicit milestone trigger unless an automatic run is required to produce a deterministic generated asset.

## Fail-closed rule

Tiering changes *when* expensive proof runs, not *whether* it is required.

A draft PR cannot merge. A ready PR with `asset_full=true` cannot satisfy the aggregate gate unless the exact-head Stage 3G full proof succeeds. If more commits are pushed after review readiness, the exact-head heavy proof is required again.

Code-only Unreal validation remains independent from the Stage 3G full-LFS lane so C++ correctness can still fail fast without materializing the world asset set.

## World-stage operating model

For Stage 3G R4/R5 world-art work, one long-lived **Draft stage integration PR** is the normal iteration surface.

The lifecycle is:

1. **Iteration — lightweight**
   - add or tune vegetation, water, rocks, terrain dressing, materials, lighting, fog and similar world elements;
   - run static/contract/policy/LFS-pointer checks;
   - keep code-only Unreal validation for C++ and build-contract changes; keep ordinary proof/editor tooling on hosted CI/contract validation;
   - do not run the full map/world proof after every art commit.

2. **Owner visual acceptance — performance checkpoint**
   - when the owner accepts the candidate look, freeze that candidate SHA;
   - capture the stable 1200 / 4900 / 8000 m views and record Visual History NOW;
   - run the stage performance budget on that exact SHA;
   - if performance fails, optimize the accepted visual candidate rather than silently changing art direction.

3. **Stage closeout — full proof**
   - only when the stage is ready to close, mark the stage integration PR Ready for review;
   - run the exact-head full Unreal/Automation/full-LFS/Map Check/save-reopen/Stage 3G proof;
   - require the full proof before merge.

If the final full proof runs on the same tree that already passed the accepted performance checkpoint, performance does not need to be repeated merely because the full proof ran. A material visual/runtime change after the accepted performance checkpoint invalidates that checkpoint and requires a new one.

The intent is to make **world iteration cheap and stage acceptance strict**.
