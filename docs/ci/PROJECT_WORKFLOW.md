# GitHub Project workflow

Status: **SETUP PENDING**  
Issue: #88  
Target Project: **YACS — MVP**

## Purpose

YACS copies the 4VELO board structure **1:1**, including its five Status
columns. Repository automation relies only on the four lifecycle statuses it
owns: `Backlog`, `In progress`, `In review` and `Done`. The fifth
planning column is preserved exactly as configured in the 4VELO template and
remains a human planning state.

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
verifies that the copied Project still has exactly five Status columns and all
four automated lifecycle statuses, verifies/creates the repository link and
backfills all currently open YACS Issues to `Backlog`.

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

## Verification

After bootstrap:

1. confirm the copied board has the same five Status columns as the 4VELO
   template and includes `Backlog`, `In progress`, `In review`, `Done`;
2. verify existing open YACS Issues appear in `Backlog`;
3. move one groomed Issue to the copied manual planning column;
4. open a Draft PR containing `Closes #<issue>` and confirm both items move to
   `In progress`;
5. mark the PR Ready for review and confirm both move to `In review`;
6. merge only after normal YACS validation and confirm both reach `Done`;
7. verify a closed-unmerged PR is not falsely marked Done.

Project automation is planning metadata only. It never replaces Unreal build,
Automation, LFS, visual proof, CI, review or merge requirements.
