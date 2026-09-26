# Branch hygiene

YACS automatically removes stale remote branch refs after work reaches
`main`.

The cleanup is intentionally conservative. A branch is eligible only when:

- it is not the default branch;
- it has no open same-repository pull request;
- it is not the base of an open pull request;
- and one of these proofs holds:
  - the current branch tip exactly matches a merged PR head (covers squash merges);
  - the current branch tip is already contained in `main` and the branch has a
    merged PR history;
  - a closed-unmerged same-repository PR contains the exact marker
    `<!-- yacs-branch-hygiene:delete-head-safe -->` and the current branch tip
    still exactly matches that PR head SHA.

The explicit marker is intended for superseded/abandoned PRs. If the branch was
reused and its tip changed after the PR closed, it is preserved.

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
