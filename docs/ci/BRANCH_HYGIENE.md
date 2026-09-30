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


## 2026-09-30 architecture-reset purge

After the world/CI architecture reset, YACS performs one exact-name purge of
pre-reset remote branches. This is intentionally **not** a new aggressive
default policy: the names are enumerated in
`ARCHITECTURE_RESET_DELETE_BRANCHES`, so the override becomes inert after
those refs are gone.

The normal safety precedence still wins:

1. `main` is never deleted;
2. an open same-repository PR head is never deleted;
3. a branch used as the base of an open PR is never deleted;
4. only then may an exact reset-list match bypass the historical merged-PR
   proof requirement.

Landscape/road work deliberately preserved through this reset:

- `feat/255-sp638-road-earthworks` — active PR #256;
- `feat/247-r4-1b4-meso-ground` — last bounded rider-close meso-ground line;
- `feat/238-r4-1b3-1-corridor-occlusion` — last corridor/road visual line.

The reset removes stale CI experiments, old Stage 3/4 implementation branches,
proof branches, DEM probes and temporary preservation refs that belong to the
pre-reset architecture.

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
