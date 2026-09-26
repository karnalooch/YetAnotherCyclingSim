# GitHub Project workflow

Status: **SETUP PENDING**  
Issue: #88  
Target Project: **YACS — MVP**

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

The copied fifth column is intentionally a human planning state. Automation
never promotes a Backlog item into that planning column by itself.

## One-time setup

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
