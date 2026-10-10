# Git, Project and branching

> Scoped policy migrated from original root AGENTS.md (blob `c4c75a9e92088195a7aad1c72c849ac9482d1462`). Read only for applicable work. Current domain SSOT and owner decisions take precedence over superseded chronology.

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

Owner dependency policy, 2026-10-04: the 13-step M3 world-finishing sequence
uses existing #335, then #363 through #374. Each successor is natively blocked
by its immediate predecessor. Before starting implementation, opening its
implementation PR or moving it to Ready/In progress, verify the predecessor is
completed with required proof and merged implementation where applicable.
Closing as not planned, a draft PR or green CI alone does not satisfy the gate.
Native GitHub dependencies record the relationship but do not prevent PR
creation; agents must enforce this execution rule. Removing dependencies or
changing order requires explicit owner authorization. Project Blocked is
planning metadata and does not replace proof or this dependency check.

Owner-authorized exception, 2026-10-09: the final execution order is
#372 visual/technical acceptance → #374 full-route assembly/implementation
closeout → #373 measured performance, retaining #372 as an additional
prerequisite of #373. Preserve the existing 13 step IDs. Native dependency
reconciliation is pending (currently #373 still blocks #374); resolve that
graph before starting #374 and do not claim documentation changed it.
Intermediate handoffs retain `DEFERRED_AFTER_M3`, `performance_pass: false`;
budgets and later measured admission remain unchanged.

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

