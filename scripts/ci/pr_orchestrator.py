#!/usr/bin/env python3
"""Fail-closed pull-request orchestrator for YACS.

Responsibilities are intentionally process-only:
- respect explicit Auto-merge markers;
- understand stacked PRs from base-branch -> parent head-branch relations;
- keep stacked children fresh against their current parent;
- after a parent merges, retarget the child to main and require fresh CI;
- require the current-head Aggregate CI gate to be green;
- refuse drafts, forks, foreign authors, unresolved review threads, and
  outstanding CHANGES_REQUESTED reviews;
- update branches that are behind their base before considering merge;
- squash-merge only when GitHub reports a clean merge state.

Risk classification stays in Governance + Security + Aggregate CI. This script
must not duplicate those policy lists.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_ROOT = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
ELIGIBLE_MARKER = "auto-merge: eligible"
MANUAL_MARKER = "auto-merge: manual"
REQUIRED_CHECKS = ("Aggregate CI gate",)


class OrchestratorError(RuntimeError):
    """Raised when the orchestrator cannot make a safe decision."""


class ApiError(OrchestratorError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API {status}: {message}")
        self.status = status


class GitHubApi:
    def __init__(self, token: str) -> None:
        if not token:
            raise OrchestratorError("GITHUB_TOKEN is required")
        self._token = token

    def _request(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "yacs-pr-orchestrator",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                message = parsed.get("message", exc.reason)
            except json.JSONDecodeError:
                message = exc.reason
            raise ApiError(exc.code, str(message)) from exc
        except URLError as exc:
            raise OrchestratorError(
                f"GitHub transport error: {exc.reason}"
            ) from exc

        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OrchestratorError("GitHub returned invalid JSON") from exc

    def rest(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
    ) -> Any:
        suffix = ""
        if query:
            suffix = "?" + urlencode(query)
        return self._request(method, f"{API_ROOT}{path}{suffix}", payload)

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        result = self._request(
            "POST",
            GRAPHQL_URL,
            {"query": query, "variables": variables},
        )
        if not isinstance(result, dict):
            raise OrchestratorError("GraphQL response is not an object")
        errors = result.get("errors")
        if errors:
            messages = "; ".join(
                str(error.get("message", "unknown GraphQL error"))
                for error in errors
            )
            raise OrchestratorError(f"GitHub GraphQL error: {messages}")
        data = result.get("data")
        if not isinstance(data, dict):
            raise OrchestratorError("GraphQL response is missing data")
        return data


REVIEW_THREADS_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        pageInfo { hasNextPage }
        nodes { isResolved }
      }
    }
  }
}
"""


def normalized_lines(body: str | None) -> set[str]:
    return {
        line.strip().lower()
        for line in (body or "").splitlines()
        if line.strip()
    }


def auto_merge_mode(body: str | None) -> str | None:
    lines = normalized_lines(body)
    if MANUAL_MARKER in lines:
        return "manual"
    if ELIGIBLE_MARKER in lines:
        return "eligible"
    return None


def latest_check_conclusions(
    check_runs: Iterable[dict[str, Any]],
) -> dict[str, str | None]:
    latest: dict[str, tuple[int, str | None]] = {}
    for run in check_runs:
        name = str(run.get("name", ""))
        raw_id = run.get("id")
        if raw_id is None:
            raise OrchestratorError(f"check run {name!r} is missing id")
        try:
            run_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise OrchestratorError(
                f"check run {name!r} has invalid id"
            ) from exc
        conclusion = run.get("conclusion")
        previous = latest.get(name)
        if previous is None or run_id > previous[0]:
            latest[name] = (
                run_id,
                None if conclusion is None else str(conclusion),
            )
    return {name: value[1] for name, value in latest.items()}


def missing_required_checks(
    check_runs: Iterable[dict[str, Any]],
) -> list[str]:
    conclusions = latest_check_conclusions(check_runs)
    return [
        name
        for name in REQUIRED_CHECKS
        if conclusions.get(name) != "success"
    ]


def has_changes_requested(reviews: Iterable[dict[str, Any]]) -> bool:
    latest: dict[str, tuple[int, str]] = {}
    for review in reviews:
        user = review.get("user") or {}
        login = str(user.get("login", ""))
        if not login:
            continue
        review_id = int(review.get("id", 0))
        state = str(review.get("state", "")).upper()
        previous = latest.get(login)
        if previous is None or review_id > previous[0]:
            latest[login] = (review_id, state)
    return any(
        state == "CHANGES_REQUESTED"
        for _review_id, state in latest.values()
    )


def list_open_pull_requests(
    api: GitHubApi,
    repository: str,
) -> list[dict[str, Any]]:
    pulls = api.rest(
        "GET",
        f"/repos/{repository}/pulls",
        query={"state": "open", "per_page": 100},
    )
    if not isinstance(pulls, list):
        raise OrchestratorError("open pull request response is not a list")
    if len(pulls) >= 100:
        raise OrchestratorError(
            "100 open pull requests returned; refusing incomplete scan"
        )
    return pulls


def get_pull_request(
    api: GitHubApi,
    repository: str,
    number: int,
) -> dict[str, Any]:
    pr = api.rest("GET", f"/repos/{repository}/pulls/{number}")
    if not isinstance(pr, dict):
        raise OrchestratorError(f"PR #{number} response is not an object")
    return pr


def list_reviews(
    api: GitHubApi,
    repository: str,
    number: int,
) -> list[dict[str, Any]]:
    reviews = api.rest(
        "GET",
        f"/repos/{repository}/pulls/{number}/reviews",
        query={"per_page": 100},
    )
    if not isinstance(reviews, list):
        raise OrchestratorError(f"PR #{number} reviews response is not a list")
    if len(reviews) >= 100:
        raise OrchestratorError(
            f"PR #{number} has 100+ reviews; manual handling required"
        )
    return reviews


def list_check_runs(
    api: GitHubApi,
    repository: str,
    sha: str,
) -> list[dict[str, Any]]:
    payload = api.rest(
        "GET",
        f"/repos/{repository}/commits/{sha}/check-runs",
        query={"per_page": 100},
    )
    if not isinstance(payload, dict):
        raise OrchestratorError("check-runs response is not an object")
    total = int(payload.get("total_count", 0))
    if total > 100:
        raise OrchestratorError(
            f"{total} check runs found; refusing incomplete scan"
        )
    runs = payload.get("check_runs", [])
    if not isinstance(runs, list):
        raise OrchestratorError("check_runs is not a list")
    return runs


def unresolved_review_threads(
    api: GitHubApi,
    *,
    repository: str,
    number: int,
) -> int:
    owner, name = repository.split("/", 1)
    data = api.graphql(
        REVIEW_THREADS_QUERY,
        {"owner": owner, "name": name, "number": number},
    )
    repository_node = data.get("repository")
    pull_request = (
        repository_node.get("pullRequest")
        if isinstance(repository_node, dict)
        else None
    )
    if not isinstance(pull_request, dict):
        raise OrchestratorError(f"PR #{number} could not be resolved")
    threads = pull_request.get("reviewThreads", {})
    if threads.get("pageInfo", {}).get("hasNextPage"):
        raise OrchestratorError(
            f"PR #{number} has more than 100 review threads"
        )
    return sum(
        1
        for node in threads.get("nodes", [])
        if not bool(node.get("isResolved"))
    )


def merged_parent_for_branch(
    api: GitHubApi,
    *,
    repository: str,
    repository_owner: str,
    branch: str,
) -> dict[str, Any] | None:
    pulls = api.rest(
        "GET",
        f"/repos/{repository}/pulls",
        query={
            "state": "closed",
            "head": f"{repository_owner}:{branch}",
            "per_page": 100,
        },
    )
    if not isinstance(pulls, list):
        raise OrchestratorError(
            f"closed PR lookup for branch {branch!r} is not a list"
        )
    merged = [
        pr
        for pr in pulls
        if pr.get("merged_at")
        and pr.get("head", {}).get("repo", {}).get("full_name") == repository
    ]
    if not merged:
        return None
    merged.sort(
        key=lambda pr: str(pr.get("merged_at", "")),
        reverse=True,
    )
    return merged[0]


def open_parent_by_head(
    open_pull_requests: Iterable[dict[str, Any]],
    *,
    repository: str,
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for pr in open_pull_requests:
        head = pr.get("head", {})
        if head.get("repo", {}).get("full_name") != repository:
            continue
        ref = str(head.get("ref", ""))
        if not ref:
            continue
        if ref in result:
            raise OrchestratorError(
                f"multiple open PRs use head branch {ref!r}"
            )
        result[ref] = pr
    return result


def print_block(number: int, reason: str) -> None:
    print(f"pr-orchestrator: PR #{number} BLOCKED: {reason}")


def update_branch(
    api: GitHubApi,
    *,
    repository: str,
    number: int,
    head_sha: str,
    label: str,
) -> str:
    try:
        api.rest(
            "PUT",
            f"/repos/{repository}/pulls/{number}/update-branch",
            {"expected_head_sha": head_sha},
        )
    except ApiError as exc:
        if exc.status == 422:
            print(
                f"pr-orchestrator: PR #{number} update-branch skipped: {exc}"
            )
            return "blocked"
        raise
    print(
        f"pr-orchestrator: PR #{number} UPDATED from {label}; "
        "waiting for fresh checks"
    )
    return "updated"


def evaluate_pull_request(
    api: GitHubApi,
    *,
    repository: str,
    repository_owner: str,
    default_branch: str,
    pr_summary: dict[str, Any],
    open_parents: dict[str, dict[str, Any]],
) -> str:
    number = int(pr_summary["number"])
    if auto_merge_mode(pr_summary.get("body")) != "eligible":
        return "not-eligible"

    pr = get_pull_request(api, repository, number)
    if auto_merge_mode(pr.get("body")) != "eligible":
        print_block(
            number,
            "eligible marker removed or Auto-merge: manual is present",
        )
        return "blocked"
    if pr.get("state") != "open":
        return "not-open"
    if bool(pr.get("draft")):
        print_block(number, "PR is still draft")
        return "blocked"
    if pr.get("head", {}).get("repo", {}).get("full_name") != repository:
        print_block(number, "head repository is not the protected repository")
        return "blocked"
    if pr.get("user", {}).get("login") != repository_owner:
        print_block(number, "PR author is not repository owner")
        return "blocked"

    head_sha = str(pr.get("head", {}).get("sha", ""))
    if not head_sha:
        raise OrchestratorError(f"PR #{number} has no head SHA")

    base_ref = str(pr.get("base", {}).get("ref", ""))
    if not base_ref:
        raise OrchestratorError(f"PR #{number} has no base branch")

    mergeable_state = str(pr.get("mergeable_state", "unknown"))
    if base_ref != default_branch:
        open_parent = open_parents.get(base_ref)
        if open_parent is not None:
            parent_number = int(open_parent["number"])
            if parent_number == number:
                raise OrchestratorError(
                    f"PR #{number} cannot use its own head as base"
                )
            if mergeable_state == "behind":
                return update_branch(
                    api,
                    repository=repository,
                    number=number,
                    head_sha=head_sha,
                    label=f"stack parent #{parent_number}",
                )
            print(
                f"pr-orchestrator: PR #{number} WAITING for stack parent "
                f"#{parent_number} ({base_ref})"
            )
            return "waiting-parent"

        merged_parent = merged_parent_for_branch(
            api,
            repository=repository,
            repository_owner=repository_owner,
            branch=base_ref,
        )
        if merged_parent is None:
            print_block(
                number,
                f"base {base_ref!r} is neither {default_branch!r} nor a "
                "managed open/merged stack parent",
            )
            return "blocked"

        parent_number = int(merged_parent["number"])
        api.rest(
            "PATCH",
            f"/repos/{repository}/pulls/{number}",
            {"base": default_branch},
        )
        print(
            f"pr-orchestrator: PR #{number} RETARGETED "
            f"{base_ref} -> {default_branch} after parent #{parent_number} merged; "
            "waiting for fresh CI"
        )
        return "retargeted"

    if mergeable_state == "behind":
        return update_branch(
            api,
            repository=repository,
            number=number,
            head_sha=head_sha,
            label=default_branch,
        )

    missing = missing_required_checks(
        list_check_runs(api, repository, head_sha)
    )
    if missing:
        print_block(
            number,
            "required checks not green on current head: " + ", ".join(missing),
        )
        return "blocked"

    reviews = list_reviews(api, repository, number)
    if has_changes_requested(reviews):
        print_block(number, "latest review contains CHANGES_REQUESTED")
        return "blocked"

    unresolved = unresolved_review_threads(
        api,
        repository=repository,
        number=number,
    )
    if unresolved:
        print_block(number, f"{unresolved} unresolved review thread(s)")
        return "blocked"

    if pr.get("mergeable") is not True:
        print_block(number, f"GitHub mergeable={pr.get('mergeable')!r}")
        return "blocked"
    if mergeable_state != "clean":
        print_block(
            number,
            f"mergeable_state={mergeable_state!r}, expected 'clean'",
        )
        return "blocked"

    result = api.rest(
        "PUT",
        f"/repos/{repository}/pulls/{number}/merge",
        {
            "sha": head_sha,
            "merge_method": "squash",
            "commit_title": f"{str(pr.get('title', '')).strip()} (#{number})",
        },
    )
    if not isinstance(result, dict) or not bool(result.get("merged")):
        message = (
            result.get("message", "merge rejected")
            if isinstance(result, dict)
            else "merge rejected"
        )
        raise OrchestratorError(
            f"PR #{number} merge was rejected: {message}"
        )

    print(f"pr-orchestrator: PR #{number} MERGED via squash")
    return "merged"


def evaluate_eligible_pull_requests(
    api: GitHubApi,
    *,
    repository: str,
    repository_owner: str,
    default_branch: str,
    pull_requests: Iterable[dict[str, Any]],
) -> int:
    pulls = list(pull_requests)
    open_parents = open_parent_by_head(pulls, repository=repository)
    had_errors = False

    # Parents before children: a PR based on main gets a chance to merge before
    # a child based on that PR's branch is evaluated in the same invocation.
    pulls.sort(
        key=lambda pr: (
            0 if pr.get("base", {}).get("ref") == default_branch else 1,
            int(pr.get("number", 0)),
        )
    )

    for pr in pulls:
        if auto_merge_mode(pr.get("body")) != "eligible":
            continue
        number = pr.get("number", "?")
        try:
            evaluate_pull_request(
                api,
                repository=repository,
                repository_owner=repository_owner,
                default_branch=default_branch,
                pr_summary=pr,
                open_parents=open_parents,
            )
        except (OrchestratorError, KeyError, TypeError, ValueError) as exc:
            print(
                f"pr-orchestrator: PR #{number} FAIL: {exc}",
                file=sys.stderr,
            )
            had_errors = True

    return 1 if had_errors else 0


def main() -> int:
    try:
        repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        repository_owner = os.environ.get("REPOSITORY_OWNER", "").strip()
        default_branch = os.environ.get("DEFAULT_BRANCH", "main").strip()
        token = os.environ.get("GITHUB_TOKEN", "").strip()

        if "/" not in repository:
            raise OrchestratorError("GITHUB_REPOSITORY must be owner/name")
        if not repository_owner:
            raise OrchestratorError("REPOSITORY_OWNER is required")
        if not default_branch:
            raise OrchestratorError("DEFAULT_BRANCH is required")

        api = GitHubApi(token)
        pulls = list_open_pull_requests(api, repository)
        eligible = [
            pr for pr in pulls
            if auto_merge_mode(pr.get("body")) == "eligible"
        ]
        print(
            f"pr-orchestrator: evaluating {len(eligible)} eligible "
            f"open PR(s) out of {len(pulls)}"
        )
        return evaluate_eligible_pull_requests(
            api,
            repository=repository,
            repository_owner=repository_owner,
            default_branch=default_branch,
            pull_requests=pulls,
        )
    except (OrchestratorError, KeyError, TypeError, ValueError) as exc:
        print(f"pr-orchestrator: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
