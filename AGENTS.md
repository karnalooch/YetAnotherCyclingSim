# YetAnotherCyclingSim — AI development rules

## Project context

YetAnotherCyclingSim is a realistic indoor cycling simulator built with Unreal Engine 5.

Before making changes, read:

- `docs/PRODUCT_REQUIREMENTS.md`
- `docs/ROADMAP.md`
- for world/terrain/road work: `docs/WORLD_BUILDING_BIBLE.md`

The product owner is a beginner programmer. Explanations intended for the product owner must be written in clear Polish. Code, identifiers, filenames, commit messages and technical names must be written in English.

## Scope control

- Implement only the task explicitly requested.
- Do not add speculative features.
- Do not expand MVP scope without updating the requirements.
- Do not start future product milestones early.
- Prefer the smallest working solution.
- Do not introduce a service, framework, plugin or dependency without explaining why it is needed.
- Do not create a separate backend process unless measurements or requirements justify it.
- Do not implement multiplayer before the single-player MVP is stable.
- Do not implement real trainer connectivity before the simulated input is stable.

## Working method

Before editing:

1. Explain in Polish what will change.
2. Inspect existing files and conventions.
3. State assumptions and risks.
4. Propose a small implementation plan.
5. Wait for approval when the change affects architecture, dependencies or scope.

After editing:

1. Build or validate the changed component.
2. Run relevant tests.
3. Describe the result in Polish.
4. List changed files.
5. Report any unverified behavior.
6. Suggest one logical commit message.

### Roadmap and world-building nomenclature

- `docs/ROADMAP.md` uses only product milestones `M0` through `M10`.
- Do not create recursive planning identifiers such as `M3.1.2`, `R4.1B.3` or equivalent.
- Concrete work is tracked by GitHub Issue number plus a human-readable title.
- Existing Stage/R/B identifiers may remain in historical documents, workflow names and proof artifacts for traceability.
- For any terrain, road, earthwork, Landscape, PCG, material, cliff, world-streaming or world-performance change, `docs/WORLD_BUILDING_BIBLE.md` is the methodology SSOT.
- Before creating or materially extending a custom world-building subsystem, follow the Bible's tools-first audit and architecture evidence ladder. External production evidence increases confidence but never replaces a bounded YACS proof against YACS inputs.
- `docs/YACS_WORLD_AUTHORING_LIBRARY.md` defines reusable implementation/catalog systems; it does not override the Bible's world architecture.
- New or substantially revised architecture/workflow diagrams must follow `docs/DIAGRAM_STYLE.md`, the YACS adoption of the Gumball Blueprint Mermaid language.

### Passo Giau terrain-recovery guardrails

For Issue #287 / PR #288, Gate B is an established road-authoring baseline, not an
open smoothing experiment. The pinned PCGEx graph has executed against prepared
official SP638 presentation data, produced bounded deviation evidence and fed the
rider-close consumer. Until a concrete regression proves otherwise:

- do not change PCGEx resample/smoothing/corridor behavior merely to improve terrain appearance;
- do not move canonical road XY, route authority or Road Physics Profile truth to repair a visual seam;
- keep PCGEx presentation-only and authoring-only; it is not physics authority.

Before introducing another terrain generator, another smoothing stack or another
global-resolution change, isolate the owning surface with the same exact-SHA
camera/light/FOV proof. For the current hairpin this means the A-E diagnostic matrix:

- A: macro Landscape only;
- B: macro Landscape + road corridor;
- C: local/near-field ground only;
- D: local/near-field ground + road corridor;
- E: full combined baseline.

Use the result to identify the owning layer before changing architecture.

Rider-close terrain must follow these rules:

- prefer a bounded near-field surface derived directly from the prepared native
  metric DTM over line-tracing/resampling a known-bad Landscape;
- use finer bounded spacing where the rider camera can inspect the ground rather
  than increasing the entire world to the same resolution;
- select `Road_Earthworks` explicitly by semantic name; missing, duplicate or
  accidental `Base_DTM` selection fails closed;
- one place has one visual ground owner: do not rely on two coincident surfaces,
  arbitrary Z lift or overlap to hide disagreement between Landscape and a local mesh;
- connect near-field to macro terrain with a deterministic transition band whose
  outer boundary is constrained to the macro surface;
- apply road/cut/fill constraints to the local ground before final triangulation
  where that produces a single coherent surface;
- do not use materials, RVT, vegetation, fog, AA or lighting to conceal unresolved geometry.

A terrain recovery is not accepted because one hairpin looks good. After the
baseline hairpin passes, prove at least a normal/moderate slope corridor and a
large-elevation-difference/earthworks case. Run the relevant performance proof
after neutral geometry passes visually, not as a substitute for visual acceptance.

### Documentation SSOT and freshness

Documentation verification is mandatory for every repository-changing task.

Before implementation:

- Start from `docs/README.md` and use it to identify the current authoritative SSOT for the affected area.
- Do not treat takeover notes, snapshots, historical handoffs, or anything under `archive/` as current truth unless the current SSOT explicitly points to it as authoritative.
- If `docs/README.md` is missing or does not identify an authoritative source for the affected area, report that as a documentation-governance defect instead of guessing which document is current.

After implementation:

- Re-check the relevant SSOT against the resulting code, configuration, workflows and CI behavior.
- If the implementation makes the documentation stale, incomplete or misleading, update the affected documentation in the **same pull request**.
- Do not defer a required documentation correction to a later task merely because the code change is already working.

When any documentation changes, run all required documentation guards:

- links;
- i18n;
- structure;
- freshness.

Do not silently skip a required guard. If a guard is unavailable, missing or broken, report that explicitly with the command/workflow attempted and the resulting evidence.

The final status/report for the task must state:

- which current SSOT was identified through `docs/README.md` and verified;
- whether implementation required documentation updates;
- the result of each documentation guard: links, i18n, structure and freshness.

## Gumball repository baseline

YACS consumes shared engineering contracts through Gumball (`karnalooch/engineering-platform`). The repository-specific authority for that integration is `docs/ENGINEERING_PLATFORM.md`.

- Adopt Gumball in `preserve-local` mode: never replace a stronger YACS-specific control merely because a generic platform equivalent exists.
- Keep all external Actions and shared workflow references pinned to reviewed immutable 40-character SHAs.
- Keep the final `Aggregate CI gate` caller-local and fail closed.
- Treat `.gumball/repository-os.json` as the shared lifecycle/label/CI-cost policy, while preserving existing YACS Project automation and branch hygiene when they are stronger or more specific.
- Active pull requests should normally carry the canonical Gumball `type:*`, `area:*`, `risk:*` and `ci:*` dimensions once trusted Repository Ops has classified them.
- Heavy runtime, visual, hardware or editor proofs must follow the YACS validation tiers and exact-SHA policy. When a proof is broker-managed, use the trusted Proof Broker intent path and keep manual `workflow_dispatch` only as fallback.
- After completing a CI, governance, security, documentation, tooling, MCP or agent-workflow improvement, decide whether the reusable invariant should be promoted back to Gumball. Record a downstream candidate under `.gumball/candidates/` when appropriate.
- Promote reusable invariants and failure behavior, not YACS-specific map names, machine paths or product-specific acceptance thresholds.

### Problem reporting

If any problem, failure, blocker, unexpected behavior, or incomplete validation occurs, describe it precisely in the status or final report. Do not reduce it to a vague statement such as "it failed", "UE hung", or "the test did not work".

For every relevant problem, report:

- what operation was being performed and the exact command, test, script, or workflow involved;
- what was expected to happen;
- what actually happened;
- the exact error message, exit code, failing assertion, relevant log excerpt, or other evidence when available;
- whether the problem is in product code, tests, build/tooling, CI, Unreal/editor/runtime environment, local machine setup, or still unknown;
- the current diagnosis and the evidence supporting it;
- every meaningful fix or workaround attempted and its result;
- any files or configuration changed while investigating;
- what remains unverified or blocked;
- the smallest recommended next action to continue safely.

Clearly distinguish a confirmed root cause from a hypothesis. Do not claim a blocker is resolved until the relevant build, test, runtime proof, or other required validation has actually passed.

Never claim that code works without running an appropriate check.

## Code rules

- Keep gameplay and physics logic independent from rendering.
- Physics results must not depend on frame rate.
- Use SI units internally.
- Document units in public interfaces.
- Prefer deterministic calculations.
- Avoid logic in Unreal Level Blueprints.
- Use Blueprints for presentation, configuration and rapid prototyping.
- Use C++ for stable domain logic, physics and testable systems.
- Avoid Tick when an event, timer or fixed-step system is sufficient.
- Avoid hard-coded asset paths and unexplained magic numbers.
- Store tunable values in data assets, configuration or clearly named structures.
- Keep classes and functions focused on one responsibility.
- Treat warnings as problems to investigate.
- Do not silently ignore errors.

## Physics rules

- The cycling physics core must be testable without rendering a UE level.
- Separate rider input, environment, route state and physics output.
- Use a fixed simulation step.
- Include tests for flat road, climb, descent, coasting and wind.
- Cornering outcomes must be deterministic for the same inputs.
- Crashes are outside the MVP.
- MVP cornering consequences are line widening, controlled slip, speed loss, time loss and technique score.

## Unreal Engine rules

Do not commit generated Unreal directories:

- `Binaries/`
- `DerivedDataCache/`
- `Intermediate/`
- `Saved/`
- `.vs/`

Track Unreal binary assets through Git LFS:

- `*.uasset`
- `*.umap`

Before adding an asset:

- verify its license;
- record its source;
- update `docs/legal/DEPENDENCY_PROVENANCE.md` when the source is external;
- preserve any required notice in `THIRD_PARTY_NOTICES.md`;
- check its performance cost;
- confirm that it is required by the current product milestone or an explicitly approved supporting workstream.

Target performance is 60 FPS at 1920×1080 on:

- Intel Core i5 10th generation;
- 32 GB RAM;
- NVIDIA RTX 2070 Super.

Performance must be measured, not guessed.

## Third-party provenance rules

- Publicly visible code or assets are not automatically reusable.
- Before copying, vendoring, adapting or redistributing external code, plugins,
  datasets or assets, verify the exact source revision and license.
- Record external material in `docs/legal/DEPENDENCY_PROVENANCE.md` before it
  becomes part of YACS.
- Update `THIRD_PARTY_NOTICES.md` whenever redistribution or attribution
  obligations apply.
- Do not copy from a source marked `reference`, `candidate` or `blocked`
  in the provenance ledger.
- AI-generated or AI-rewritten output does not bypass third-party license and
  provenance review.

## Git rules

- Never commit credentials, API keys, tokens or private user data.
- Never rewrite shared Git history without explicit approval.
- Do not use destructive Git commands.
- Keep commits small and focused.
- Use English Conventional Commit messages where practical.
- Review `git status` and the diff before committing.
- Do not commit unrelated files.

Examples:

- `docs: update product requirements`
- `feat: add fixed-step cycling physics`
- `test: cover coasting on negative grade`
- `fix: prevent speed from becoming negative`
- `chore: configure Unreal asset tracking`

### GitHub Markdown / CLI rules

- For substantial multiline pull-request bodies, issue bodies, and comments, write the content to a UTF-8 Markdown file and use the CLI's `--body-file` option (or the equivalent file-backed API mechanism).
- Do not pass long multiline Markdown through an inline `--body` argument.
- Do not encode intended line breaks as literal `\\n` sequences.
- Preserve real blank lines around headings, lists, tables, and code blocks so GitHub renders Markdown correctly.
- After creating or editing a substantial PR, issue, or comment, verify the rendered GitHub Markdown before considering the operation complete.
- Temporary Markdown body files are working files only and must not be committed.

## Issue -> Project -> delivery

GitHub Issue is the canonical work item and the GitHub Project **YACS — MVP**
is the canonical planning view.

The Project keeps the Status layout copied from 4VELO exactly. The current
template has `Backlog`, `Ready`, `In progress`, `In review`, `Blocked`,
`Done`. Automation owns `Backlog`, `In progress`, `In review` and
`Done`; `Ready` and `Blocked` remain planning/manual states.

- Every repository-changing task uses one primary Issue unless the user already
  identified the correct existing Issue.
- New/reopened Issues are added automatically as `Backlog`.
- Move an Issue to the copied manual planning column only after scope,
  non-scope, acceptance criteria and required proof are clear.
- Start implementation from the Issue on a dedicated branch.
- A Draft PR must reference the Issue with `Closes #<issue>`; automation moves
  the PR and linked Issue to `In progress`.
- Ready-for-review/non-draft PRs move to `In review`.
- Merge/Issue close moves completed items to `Done`.
- A closed-unmerged PR must not be represented as completed work.
- Project status is planning metadata only and never replaces required Unreal
  validation, CI, review, LFS or proof.
- Project automation setup and security are documented in
  `docs/ci/PROJECT_WORKFLOW.md`.

## Office and home workflow

This project is developed on two machines: the office PC, which is suitable for documentation, Git operations, lightweight code, and Python tests, and the home PC, which builds Unreal Engine and runs the full validation cycle.

The following rules apply to every task and do not weaken any earlier rule in this document:

- At most two unmerged implementation branches may exist simultaneously.
- Parallel implementation is allowed only within the current roadmap stage.
- Tasks developed in parallel must be independent.
- A parallel branch must not consume APIs, source files, assets, or behavior introduced only by another unmerged branch.
- Every task still follows the existing one issue, one branch, review, commit, push, and pull request workflow.
- Office work may receive a reviewed checkpoint commit and push when Unreal Engine is unavailable on the office PC.
- Such work must be explicitly marked `Unreal validation pending`.
- A **Draft** implementation pull request may be opened before home-PC Unreal validation when it is useful for review, CI orchestration or checkpointing. It must remain draft and explicitly state which Unreal/build/asset proofs are still pending.
- An implementation pull request that contains Unreal C++ code, Unreal assets, or Unreal integration changes must not be marked ready for review or merged until the relevant Unreal project build, required Unreal Automation Tests and any stage-specific asset/runtime proof pass on the home/reference PC or trusted UE runner.
- Documentation-only pull requests and other changes that cannot affect the Unreal build do not require Unreal validation.
- The product owner granted standing merge authorization on 2026-09-23: a pull request may be merged automatically without a separate per-PR `scal` command when its scope is approved, all required validation is complete, all required CI/status gates are green, no unresolved review finding or known blocker remains, and the pull request is mergeable and not draft.
- Standing merge authorization never waives required validation. Do not auto-merge when Unreal/home-PC validation is required but missing, any required gate is pending or failed, a review/blocker is unresolved, the pull request is draft/non-mergeable, or the product owner explicitly asks to hold the merge.
- Test requirements must not be weakened after a failure; the cause must be diagnosed first.
- Work from a future roadmap stage must not begin before the current stage completion criteria are met.
- Unreal compilation, editor integration, asset validation, and performance validation remain home-PC responsibilities when the office PC lacks Unreal Engine.

Documentation-only branches do not count toward the limit of two implementation branches.

## External tooling architecture policy

YACS uses an **Embark-first tooling review** because proven production tooling
patterns are preferable to inventing another local framework.

For a new editor, DCC, asset-pipeline, indexing, world-authoring or agent tool,
use this decision order:

1. inspect the closest public Embark Studios tool or documented pattern first;
2. use an Epic-native Unreal capability when it solves the same problem cleanly;
3. evaluate a proven open-source tool when neither of the above is sufficient;
4. build custom YACS tooling only for a concrete remaining gap.

"Embark-first" means **adopt or adapt proven patterns before inventing**, not
that every Embark repository becomes a dependency. Public Embark repositories
are evidence of public tooling approaches, not proof of the complete internal
ARC Raiders production stack.

### Explicit Embark-mode directive

When the product owner explicitly says **"Embarkuj"**, **"embark this"** or an
equivalent unambiguous instruction for a subsystem, treat that as explicit
architecture/scope approval to follow the strongest relevant **publicly
documented, production-proven Embark pattern end-to-end** for the current task.

- Do not silently down-scope the pattern to a cheaper, smaller or custom
  approximation merely to save implementation effort, CI time or tool cost.
- Do not replace a documented Embark stage with a guessed YACS shortcut while
  the documented stage is available and applicable.
- Embark mode copies the strongest **public production pattern and boundary**, not
  a vendor brand by itself. If the exact DCC/tool used by the reference pattern is
  unavailable, commercially unsuitable, or unjustified for YACS, use the strongest
  license-clean Unreal-native or open-source implementation that preserves the same
  producer -> derived-data -> consumer contract and required proof. Record the
  substitution explicitly and never claim Embark uses the substitute unless public
  evidence says so.
- Distinguish evidence from inference. If Embark's internal implementation is
  proprietary or unpublished, do **not** invent its node graph, algorithm or
  parameters. Reproduce only the public stage/contract with documented tools
  and YACS-owned inputs, or fail closed and report the missing recipe, license,
  asset or evidence.
- Once a lower-tier YACS/native baseline has failed its required visual or
  technical proof and the evidence ladder justifies escalation, do not keep
  retrying variations of that failed tier unless new evidence identifies a
  specific owning defect.
- Preserve YACS-owned truths: route/physics authority, source provenance,
  deterministic inputs, exact-SHA proof, performance budgets and human visual
  acceptance remain mandatory even in Embark mode.
- A tool or paid license required by the proven pattern is a real dependency
  decision. Record provenance/license evidence and surface acquisition cost or
  runner prerequisites explicitly instead of pretending the dependency does
  not exist.

Before copying, vendoring or adapting third-party source, follow
`docs/legal/DEPENDENCY_PROVENANCE.md`. A reference implementation may be
studied without entering the dependency graph.

Prefer small, high-level YACS domain operations such as route/world generation,
clearance validation and proof capture over exposing a large surface of
low-level Unreal calls to an agent. Repeated multi-step manual authoring should
be treated as pipeline friction worth automating once it is stable and
repeatable.

External tooling never bypasses Gumball policy, generated-content boundaries,
exact-SHA proof, rollback, CI or human visual acceptance. Do not introduce
Rust, AngelScript or another language merely because Embark uses it elsewhere;
language/runtime changes still require a concrete YACS need.

## AI safety rules

- Do not execute broad autonomous changes.
- Do not delete files without explicit approval.
- Do not replace working code only to change style.
- Do not invent APIs, SDK capabilities or device behavior.
- Verify external API and Unreal Engine claims against official documentation.
- Mark generated code that still requires validation.
- Follow `docs/legal/AI_ASSISTED_DEVELOPMENT.md` for AI-assisted work.
- Treat recognizable external implementations in generated output as
  third-party material requiring provenance review.
- When uncertain, stop and ask one focused question.
