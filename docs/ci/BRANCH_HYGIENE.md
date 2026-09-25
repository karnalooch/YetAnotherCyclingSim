# Branch hygiene

YACS automatically removes stale remote branch refs after work reaches
`main`.

The cleanup is intentionally conservative. A branch is eligible only when:

- it is not the default branch;
- it has no open same-repository pull request;
- GitHub history contains a merged same-repository pull request for that branch;
- and either:
  - the current branch tip exactly matches a merged PR head (covers squash
    merges), or
  - the current branch tip is already contained in `main`.

A branch that was reused and contains newer work is preserved.

The workflow runs after pushes to `main`, which includes normal PR merges, and
can also be run manually in dry-run mode.

Implementation:

- `.github/workflows/branch-hygiene.yml`
- `scripts/ci/cleanup_merged_branches.py`
- `scripts/ci/test_cleanup_merged_branches.py`

Security:

- no `pull_request_target`;
- no external token;
- only repository-scoped `GITHUB_TOKEN`;
- workflow requests `contents: write` only because deleting Git refs requires
  repository contents write permission;
- fork PR heads are ignored;
- every keep/delete decision is logged.

If repository Actions policy later removes write access from `GITHUB_TOKEN`,
the workflow fails instead of silently claiming cleanup.
