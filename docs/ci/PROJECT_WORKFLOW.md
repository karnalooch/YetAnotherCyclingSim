# GitHub Project workflow

Status: **ACTIVE — verified 2026-10-03**

Setup issue: #88; freshness correction: #353

Target Project: [**YACS — MVP**](https://github.com/users/karnalooch/projects/5)

## Purpose

YACS copies the 4VELO board structure **1:1**, including the complete Status
field. The current 4VELO template exposes six Status options:
`Backlog`, `Ready`, `In progress`, `In review`, `Blocked`, `Done`.
Repository automation relies only on `Backlog`, `In progress`,
`In review` and `Done`; `Ready` and `Blocked` remain planning/manual
states unless a later workflow explicitly owns them.

The bootstrap workflow copies the existing personal GitHub Project
`4VELO — Product & Takeover` as the structural template. GitHub Project copy
preserves views, custom fields and configured workflows, but does not copy
repository links, original items or auto-add workflows. The YACS bootstrap
therefore links the repository and the repository workflow owns auto-add/status
movement.

## Lifecycle

| Event | Issue | Pull Request |
| --- | --- | --- |
| Issue opened/reopened | `Backlog` | — |
| Groomed and selected | move to the copied planning column manually | — |
| Draft PR with `Closes #...` | `In progress` | `In progress` |
| PR ready/non-draft | `In review` | `In review` |
| PR merged | `Done` | `Done` |
| Issue closed | `Done` | — |
| PR closed without merge | unchanged | unchanged |

The copied `Ready` and `Blocked` columns are manual planning states. Automation
never promotes a Backlog item into either planning column by itself.

For the 13-step M3 world-finishing sequence, existing #335 is step 1 and #363
through #374 are steps 2–13. Each successor has a native GitHub `blocked_by`
relationship to the preceding issue and stays in the manual `Blocked` state
while that prerequisite is open. Before implementation/PR creation or promotion
to Ready/In progress, verify completion with required proof and merged
implementation where applicable; closed-as-not-planned is not completion.
GitHub dependencies do not themselves disable branch/PR creation, so the agent
execution rule in AGENTS.md remains binding. Only explicit owner authorization
can change the order or remove a dependency.

After initial issue-open auto-add/status runs complete, set and read back the
manual Blocked values; an asynchronous initial Backlog update can otherwise
overwrite an earlier manual edit. This is a sequencing check, not a new status
automation or a replacement for native dependencies.

## Verified deployment

On 2026-10-03 the GitHub API confirmed Project `PVT_kwHOABLWOs4BkqmU`,
number 5, and the six Status options in the documented order. Trusted
`project-status.yml` synchronization runs are active; run
[37146784063](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/37146784063)
completed successfully. Issue/PR status readback was checked during repository
closeout. Setup is complete; the instructions below are retained for recovery
or a future replacement board, not a current owner action.

Superseded duplicate Issues and closed-unmerged experimental PRs may be archived
from the planning view after review. Archive is not completion and does not
delete GitHub history or grant missing validation. Blocked world/source work
remains open with its missing proofs explicit.

## One-time setup / recovery

The Project is owned by the personal GitHub account. GitHub's built-in
`GITHUB_TOKEN` cannot perform the required user-owned Project V2 mutations.

1. Create or reuse a **classic PAT** for the Project owner with the `project`
   scope.
2. In the YACS repository open **Settings -> Secrets and variables -> Actions**.
3. Add the token as repository secret `PROJECTS_TOKEN`.
4. Open **Actions -> Bootstrap YACS Project board -> Run workflow**.
5. Verify the run reports the URL of `YACS — MVP`.

The bootstrap is idempotent: if `YACS — MVP` already exists it reuses it,
reads the Status options from both the source 4VELO Project and the copied YACS
Project, requires an exact match, verifies the four automated lifecycle statuses,
verifies/creates the repository link and backfills all currently open YACS
Issues to `Backlog`.

Never commit, print or paste the token into Issues, PRs, logs or documentation.

## Repository automation

`.github/workflows/project-status.yml` listens to Issue and Pull Request
lifecycle events and calls `scripts/ci/project_automation.py`.

Security boundaries:

- never uses `pull_request_target`;
- fork PRs cannot execute the privileged sync job;
- built-in workflow permissions stay at `contents: read`;
- only the separate `PROJECTS_TOKEN` can mutate the user-owned Project;
- linked Issue propagation uses GitHub's `closingIssuesReferences` relation and
  ignores Issues from other repositories;
- more than 20 linked closing Issues fails closed rather than partially updating;
- Project/field discovery fails closed on unhandled pagination or ambiguous names.

Before `PROJECTS_TOKEN` is configured the event workflow exits successfully
with a warning so the setup PR can be merged without a secret. The manual
bootstrap workflow itself fails if the secret is missing.


## Pull request orchestration

YACS uses a separate fail-closed PR orchestrator for merge process control.
Risk and code correctness remain owned by Governance, Security and the
`Aggregate CI gate`; the orchestrator does not duplicate those policy lists.

For a low-risk PR that may be merged automatically, add this exact line to the
PR body:

`Auto-merge: eligible`

For a high-risk or intentionally human-controlled PR, use:

`Auto-merge: manual`

`manual` always wins if both markers are present.

Stacked PRs are inferred from GitHub branch relations rather than extra
metadata. If PR B targets the head branch of open PR A, B is treated as A's
child. The orchestrator keeps B current with A but will not merge B while A is
open. After A merges, B is retargeted to `main`, must receive fresh CI on its
current head, and is considered for merge only after the new
`Aggregate CI gate` is green.

The orchestrator also refuses automatic merge when a PR is a draft, comes from
a fork or non-owner author, has unresolved review threads, has a current
`CHANGES_REQUESTED` review, is behind its base, lacks a green Aggregate gate,
or GitHub does not report a clean merge state. A behind branch is updated first
and then waits for fresh checks.

Branch cleanup is stack-aware: a merged parent branch is preserved while any
open PR still uses it as a base, preventing cleanup from racing the restack
operation.

The orchestrator is event-driven and also reconciles every 15 minutes. This
periodic pass is deliberate: transient GitHub mergeability states, delayed
check propagation, or a missed event must not leave an otherwise healthy stack
stuck forever. Cyclic stacks fail closed instead of waiting indefinitely.

## Verification

After bootstrap:

1. confirm the copied board has exactly the same Status options as the 4VELO
   template; currently:
   `Backlog`, `Ready`, `In progress`, `In review`, `Blocked`, `Done`;
2. verify existing open YACS Issues appear in `Backlog`;
3. move one groomed Issue to the copied manual planning column;
4. open a Draft PR containing `Closes #<issue>` and confirm both items move to
   `In progress`;
5. mark the PR Ready for review and confirm both move to `In review`;
6. merge only after normal YACS validation and confirm both reach `Done`;
7. verify a closed-unmerged PR is not falsely marked Done.

Project automation is planning metadata only. It never replaces Unreal build,
Automation, LFS, visual proof, CI, review or merge requirements.
