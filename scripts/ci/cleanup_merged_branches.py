#!/usr/bin/env python3
"""Delete stale remote branches that are proven to belong to merged PRs.

The cleanup is deliberately conservative:
- default branch is never deleted;
- a branch with an open same-repository PR is never deleted;
- a branch is considered only if it has at least one merged same-repository PR;
- exact merged PR heads are safe to delete (covers squash merges);
- otherwise the current branch tip must already be contained in the default branch;
- reused branches with newer/unmerged work are preserved.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"


class CleanupError(RuntimeError):
    """Raised when branch cleanup cannot complete safely."""


class GitHubApi:
    def __init__(
        self,
        token: str,
        repository: str,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not token:
            raise CleanupError("GH_TOKEN is required")
        if "/" not in repository:
            raise CleanupError("GITHUB_REPOSITORY must be owner/name")
        self._token = token
        self.repository = repository
        self._opener = opener or urlopen

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
    ) -> Any:
        request = Request(
            API_ROOT + path,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "yacs-branch-hygiene",
            },
            method=method,
        )
        try:
            with self._opener(request, timeout=30) as response:
                raw = response.read()
        except HTTPError as exc:
            raise CleanupError(
                f"GitHub API HTTP {exc.code}: {exc.reason} ({path})"
            ) from exc
        except URLError as exc:
            raise CleanupError(f"GitHub API transport error: {exc.reason}") from exc

        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise CleanupError(f"GitHub API returned invalid JSON for {path}") from exc

    def list_paginated(self, path: str) -> list[dict[str, Any]]:
        separator = "&" if "?" in path else "?"
        page = 1
        result: list[dict[str, Any]] = []
        while True:
            batch = self.request(f"{path}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise CleanupError(f"expected list response for {path}")
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1
            if page > 100:
                raise CleanupError(f"pagination safety limit exceeded for {path}")

    def repository_info(self) -> dict[str, Any]:
        data = self.request(f"/repos/{self.repository}")
        if not isinstance(data, dict):
            raise CleanupError("repository metadata is unavailable")
        return data

    def branches(self) -> list[dict[str, Any]]:
        return self.list_paginated(f"/repos/{self.repository}/branches")

    def pulls(self, state: str) -> list[dict[str, Any]]:
        return self.list_paginated(
            f"/repos/{self.repository}/pulls?state={quote(state, safe='')}"
        )

    def compare(self, base: str, head: str) -> dict[str, Any]:
        base_ref = quote(base, safe="")
        head_ref = quote(head, safe="")
        data = self.request(f"/repos/{self.repository}/compare/{base_ref}...{head_ref}")
        if not isinstance(data, dict):
            raise CleanupError(f"compare result unavailable for {base}...{head}")
        return data

    def delete_branch(self, branch: str) -> None:
        ref = quote(f"heads/{branch}", safe="/")
        self.request(f"/repos/{self.repository}/git/refs/{ref}", method="DELETE")


def current_sha(branch: dict[str, Any]) -> str:
    commit = branch.get("commit")
    if not isinstance(commit, dict) or not commit.get("sha"):
        raise CleanupError(f"branch payload has no commit SHA: {branch!r}")
    return str(commit["sha"])


def same_repository_head(pr: dict[str, Any], repository: str) -> bool:
    head = pr.get("head")
    if not isinstance(head, dict):
        return False
    head_repo = head.get("repo")
    return (
        isinstance(head_repo, dict)
        and head_repo.get("full_name") == repository
        and bool(head.get("ref"))
    )


def merged_heads(
    pulls: list[dict[str, Any]],
    repository: str,
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for pr in pulls:
        if not pr.get("merged_at") or not same_repository_head(pr, repository):
            continue
        head = pr["head"]
        sha = head.get("sha")
        if sha:
            result[str(head["ref"])].add(str(sha))
    return dict(result)


def open_heads(
    pulls: list[dict[str, Any]],
    repository: str,
) -> set[str]:
    return {
        str(pr["head"]["ref"]) for pr in pulls if same_repository_head(pr, repository)
    }


def open_base_branches(pulls: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for pr in pulls:
        base = pr.get("base")
        if not isinstance(base, dict):
            continue
        ref = str(base.get("ref", ""))
        if ref:
            result.add(ref)
    return result


def should_delete(
    *,
    branch_name: str,
    branch_sha: str,
    default_branch: str,
    open_branch_names: set[str],
    open_base_branch_names: set[str],
    merged_head_shas: set[str],
    tip_is_in_default: bool,
) -> tuple[bool, str]:
    if branch_name == default_branch:
        return False, "default branch"
    if branch_name in open_branch_names:
        return False, "open pull request"
    if branch_name in open_base_branch_names:
        return False, "base of open pull request"
    if not merged_head_shas:
        return False, "no merged pull request proves this branch is stale"
    if branch_sha in merged_head_shas:
        return True, "current tip matches a merged pull request head"
    if tip_is_in_default:
        return True, "current tip is already contained in the default branch"
    return False, "branch tip contains work not proven merged"


def tip_contained_in_default(
    api: GitHubApi,
    *,
    branch_sha: str,
    default_sha: str,
) -> bool:
    if branch_sha == default_sha:
        return True
    compare = api.compare(branch_sha, default_sha)
    status = str(compare.get("status", ""))
    behind_by = int(compare.get("behind_by", -1))
    return status in {"ahead", "identical"} and behind_by == 0


def run_cleanup(
    api: GitHubApi,
    *,
    dry_run: bool = False,
) -> tuple[list[str], list[str]]:
    repo = api.repository_info()
    default_branch = str(repo.get("default_branch", ""))
    if not default_branch:
        raise CleanupError("repository default branch is unavailable")

    branches = api.branches()
    by_name = {str(branch.get("name")): branch for branch in branches}
    default = by_name.get(default_branch)
    if default is None:
        raise CleanupError(f"default branch {default_branch!r} is missing")
    default_sha = current_sha(default)

    open_prs = api.pulls("open")
    closed_prs = api.pulls("closed")
    open_branch_names = open_heads(open_prs, api.repository)
    open_base_branch_names = open_base_branches(open_prs)
    merged = merged_heads(closed_prs, api.repository)

    deleted: list[str] = []
    kept: list[str] = []

    for branch_name in sorted(by_name):
        branch = by_name[branch_name]
        sha = current_sha(branch)
        merged_shas = merged.get(branch_name, set())

        contained = False
        if (
            branch_name != default_branch
            and branch_name not in open_branch_names
            and merged_shas
            and sha not in merged_shas
        ):
            contained = tip_contained_in_default(
                api,
                branch_sha=sha,
                default_sha=default_sha,
            )

        delete, reason = should_delete(
            branch_name=branch_name,
            branch_sha=sha,
            default_branch=default_branch,
            open_branch_names=open_branch_names,
            open_base_branch_names=open_base_branch_names,
            merged_head_shas=merged_shas,
            tip_is_in_default=contained,
        )

        if not delete:
            kept.append(branch_name)
            print(f"KEEP   {branch_name}: {reason}")
            continue

        prefix = "DRYRUN" if dry_run else "DELETE"
        print(f"{prefix:<6} {branch_name}: {reason}")
        if not dry_run:
            api.delete_branch(branch_name)
        deleted.append(branch_name)

    print(
        f"branch-hygiene: deleted={len(deleted)} kept={len(kept)} "
        f"dry_run={str(dry_run).lower()}"
    )
    return deleted, kept


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    try:
        token = os.environ.get("GH_TOKEN", "").strip()
        repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        api = GitHubApi(token, repository)
        run_cleanup(api, dry_run=env_bool("DRY_RUN"))
        return 0
    except (CleanupError, KeyError, TypeError, ValueError) as exc:
        print(f"branch-hygiene: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
