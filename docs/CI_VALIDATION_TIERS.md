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

### M3 Embark terrain proof sub-tiers

The dedicated Passo Giau Embark/PCGEx proof refines the central change
classification into three execution modes without weakening exact-SHA evidence:

- `cheap` — documentation, policy and contract-only changes run hosted
  classification/contract checks and do not reserve the Unreal runner;
- `render` — native-DTM preparation, bounded geometry/Python capture changes,
  proof-camera changes and other presentation inputs prepare current data and
  rerun author/render evidence against a previously validated compiled binary
  state when its fingerprint still matches;
- `heavy` — compiled Unreal source, `.Build.cs` / `.Target.cs`,
  `.uproject`, the PCGEx build/bootstrap wrapper or the proof workflow contract
  itself require a fresh PCGEx-enabled Editor build before author/render.

The compile fingerprint is SHA-256 over the pinned UE/PCGEx identity plus the
project descriptor and compiled source/build inputs. A render run may skip
compilation only when the fingerprint matches a runner-local ignored cache
stamp **and** the expected project and PCGEx binaries still exist. Missing,
invalid or stale cache state falls back to a fresh build; it never converts a
required build into a pass.

The persistent state is compile output only. Exact-SHA checkout, prepared
SP638/DTM inputs, graph execution, rider render, evidence upload and deviation
validation still run for the current revision when the proof mode requires
them. The cache is not accepted across a fingerprint change.

### General Unreal STATIC / RUNTIME / COMPILE reuse

The normal code-only Unreal lane now separates binary work from runtime proof:

- **STATIC** — the current exact HEAD has the same compile and proof
  fingerprints as a previously green run. CI verifies the current checkout,
  installed UE build identity and expected project DLLs, then emits a fresh
  exact-head equivalence artifact without launching Unreal.
- **RUNTIME** — compiled inputs are unchanged but runtime-critical Config or
  the proof/orchestration contract changed. CI reuses verified DLLs and reruns
  scoped Automation with `-SkipBuild`.
- **COMPILE** — compiled project/plugin source, project/plugin descriptors,
  Build/Target rules or another binary-contract input changed, or verified
  binaries cannot be proven reusable. COMPILE then splits again:
  - **WARM COMPILE** preserves trusted project/plugin `Binaries` and
    `Intermediate` and lets UnrealBuildTool/UBA compute the minimal outdated
    action graph. Source/header/Build.cs/Target.cs/.uproject/.uplugin edits and
    a missing final DLL use this path when the engine/toolchain identity still
    matches.
  - **COLD COMPILE** purges project/plugin build outputs first. It is reserved
    for missing/malformed cache provenance or engine/toolchain drift.

The runner-local warm worktree is serialized by repository-wide Unreal CI
concurrency. Every run resets tracked files to the requested SHA and removes all
untracked/ignored residue except the explicit warm-state allow-list: project and
plugin `Binaries`, `Intermediate`, and `Saved/BuildCache/UnrealCi`. The
code-only LFS contract and exact HEAD are then rechecked. Preserved outputs are
only candidates for reuse; they are never trusted without fingerprint and
environment checks. A compile-fingerprint mismatch is **not** cache corruption:
when engine/toolchain provenance still matches, the lane invalidates the green
stamp but keeps `Intermediate/Binaries` and performs a WARM COMPILE. Missing
final project DLLs are handled the same way because UBT can relink/rebuild them
from trusted intermediates. Only an untrusted cache state or environment drift
requests COLD purge. Before mutable COMPILE/RUNTIME work starts, the
corresponding previous green state is invalidated so cancellation or failure
cannot leave reusable proof behind.

The compile fingerprint covers the project descriptor, compiled project/plugin
inputs and the build/engine-selection orchestration used by the normal Unreal lane.
`scripts/ci/Resolve-YacsUnrealEngine.ps1` is the single engine-discovery authority
for both preflight/build and cache validation: it requires the `.uproject`
`EngineAssociation` and identities the resolved installation from its root plus
hashed `Build.version`, `Build.bat` and `UnrealEditor-Cmd.exe` evidence.
The cache resolver separately identities the active MSVC compiler/linker and
Windows resource tool. The resulting environment identity is the COLD/WARM
boundary: source/build-graph drift with the same environment is WARM; engine or
toolchain drift is COLD. The proof fingerprint extends the compile identity with
runtime-critical Config and the remaining code-only Unreal proof tooling.
Unknown or malformed state fails closed.

World/runtime cost is independent from compilation. A normal tree, house,
material or similar asset does not imply a C++ rebuild. A world change that
crosses an `asset_full` boundary is RUNTIME work at its configured readiness
checkpoint, and becomes COMPILE only when a binary-contract input also changed.

#### PR #290 validation evidence

The first live validation of this policy on `yacs-ue58` established the cost
difference directly:

- COLD seed: `compileKind=cold`, `reason=missing-cache-state`, purge enabled;
  UBT total execution **146.16 s**, including **135.59 s** in the local UBA
  executor.
- WARM build after a legitimate build-contract fingerprint change:
  `compileKind=warm`, `reason=compile-fingerprint-mismatch`, purge disabled;
  UBT total execution **1.54 s**, including **0.12 s** in local UBA, followed by
  26/26 Automation tests passing.
- RUNTIME after a proof-only fingerprint change: `mode=runtime`,
  `compileKind=none`, purge disabled and the build phase explicitly
  **skipped** before Automation.

These timings are evidence from that runner/revision, not a guaranteed future
performance budget. The architectural invariant is the cache decision and
fail-closed provenance, not a specific duration.

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

Current configured proof commands:

```text
/gumball proof r4-1b3-geometry
/gumball proof m3-hairpin-corridor
/gumball proof world-authoring-sp638
/gumball proof environment-performance
/gumball proof source-asset-audit
```

All five are explicit, heavy and non-automatic. Successful exact-revision
artifacts may be reused; failed runs require explicit `retry`.

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

Each broker target keeps `workflow_dispatch` as a recovery fallback, but
broker-driven dispatch is the normal operator path. Heavy proof still runs only
when explicitly requested; this changes the control plane, not the evidence bar.

Mutating asset-author workflows, `asset-full.yml`, manual Unreal recovery,
runner-space recovery and Project/bootstrap operations are deliberately **not**
Proof Broker targets. Their purpose is mutation, release/full validation or
administrative recovery rather than reusable PR proof.

Explicit current exceptions are:

- `reusable-stage3g-full.yml` — merge-critical, classifier-driven exact-head
  proof; it belongs in the local Aggregate graph rather than explicit broker
  intent;
- `asset-full.yml` — release/full-asset entrypoint;
- `stage3g-forest-target-density-author.yml` — mutating author workflow owned
  by its still-live dedicated branch;
- `stage3g-forest-target-density-performance.yml` — paired with that live
  dedicated-branch workstream and still has its own automatic branch trigger;
- `passo-giau-r4-1-landscape-author.yml` and
  `passo-giau-r4-1-road-author.yml` — disposition remains owned by active
  PR #256 and is tracked as `UNKNOWN` in workflow lifecycle policy;
- `manual-unreal.yml`, `runner-space-recovery.yml`, Project bootstrap and
  remote-editor command — administrative/recovery controls, not reusable PR
  evidence.

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
