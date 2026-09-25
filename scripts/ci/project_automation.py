#!/usr/bin/env python3
"""Manage the YACS GitHub Project board and synchronize lifecycle statuses."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GRAPHQL_URL = "https://api.github.com/graphql"
REQUIRED_AUTOMATED_STATUSES = (
    "Backlog",
    "In progress",
    "In review",
    "Done",
)
SUPPORTED_PR_ACTIONS = {
    "opened",
    "reopened",
    "converted_to_draft",
    "ready_for_review",
    "closed",
}
SUPPORTED_ISSUE_ACTIONS = {"opened", "reopened", "closed"}


class AutomationError(RuntimeError):
    """Raised when project automation cannot complete safely."""


class GraphQLClient:
    def __init__(
        self,
        token: str,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        if not token:
            raise AutomationError("GH_TOKEN is required")
        self._token = token
        self._opener = opener or urlopen

    def execute(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = Request(
            GRAPHQL_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "yacs-project-automation",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise AutomationError(
                f"GitHub GraphQL HTTP {exc.code}: {exc.reason}"
            ) from exc
        except URLError as exc:
            raise AutomationError(
                f"GitHub GraphQL transport error: {exc.reason}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise AutomationError("GitHub GraphQL returned invalid JSON") from exc

        errors = result.get("errors")
        if errors:
            messages = "; ".join(
                str(error.get("message", "unknown error")) for error in errors
            )
            raise AutomationError(f"GitHub GraphQL error: {messages}")

        data = result.get("data")
        if not isinstance(data, dict):
            raise AutomationError("GitHub GraphQL response is missing data")
        return data


OWNER_PROJECTS_QUERY = """
query($login: String!) {
  user(login: $login) {
    id
    projectsV2(first: 100) {
      pageInfo { hasNextPage }
      nodes { id number title url }
    }
  }
}
"""

PROJECT_DETAILS_QUERY = """
query($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      id
      number
      title
      url
      fields(first: 100) {
        pageInfo { hasNextPage }
        nodes {
          __typename
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name color description }
          }
        }
      }
      repositories(first: 100) {
        pageInfo { hasNextPage }
        nodes { id nameWithOwner }
      }
      views(first: 100) {
        pageInfo { hasNextPage }
        nodes { id name layout }
      }
      workflows(first: 100) {
        pageInfo { hasNextPage }
        nodes { id number name enabled }
      }
    }
  }
}
"""

REPOSITORY_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id
    nameWithOwner
  }
}
"""

PULL_REQUEST_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      id
      number
      isDraft
      closingIssuesReferences(first: 20) {
        pageInfo { hasNextPage }
        nodes {
          id
          number
          repository { nameWithOwner }
        }
      }
    }
  }
}
"""

OPEN_ISSUES_QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, first: 100, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { id number }
    }
  }
}
"""

COPY_PROJECT_MUTATION = """
mutation(
  $projectId: ID!,
  $ownerId: ID!,
  $title: String!
) {
  copyProjectV2(
    input: {
      projectId: $projectId,
      ownerId: $ownerId,
      title: $title,
      includeDraftIssues: false
    }
  ) {
    projectV2 { id number title url }
  }
}
"""

LINK_REPOSITORY_MUTATION = """
mutation($projectId: ID!, $repositoryId: ID!) {
  linkProjectV2ToRepository(
    input: {projectId: $projectId, repositoryId: $repositoryId}
  ) {
    repository { id nameWithOwner }
  }
}
"""

ADD_ITEM_MUTATION = """
mutation($projectId: ID!, $contentId: ID!) {
  addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
    item { id }
  }
}
"""

UPDATE_STATUS_MUTATION = """
mutation(
  $projectId: ID!,
  $itemId: ID!,
  $fieldId: ID!,
  $optionId: String!
) {
  updateProjectV2ItemFieldValue(
    input: {
      projectId: $projectId,
      itemId: $itemId,
      fieldId: $fieldId,
      value: {singleSelectOptionId: $optionId}
    }
  ) {
    projectV2Item { id }
  }
}
"""


def load_event(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutomationError(f"cannot read GitHub event payload: {exc}") from exc


def split_repository(repository: str) -> tuple[str, str]:
    if "/" not in repository:
        raise AutomationError("GITHUB_REPOSITORY must be owner/name")
    owner, name = repository.split("/", 1)
    if not owner or not name:
        raise AutomationError("GITHUB_REPOSITORY must be owner/name")
    return owner, name


def choose_project(
    owner_data: dict[str, Any],
    title: str,
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    owner = owner_data.get("user")
    if not owner:
        raise AutomationError("project owner user could not be resolved")

    projects = owner.get("projectsV2", {})
    if projects.get("pageInfo", {}).get("hasNextPage"):
        raise AutomationError(
            "project owner has more than 100 projects; refusing partial discovery"
        )

    matches = [
        project
        for project in projects.get("nodes", [])
        if project.get("title") == title
    ]
    if not matches:
        if required:
            raise AutomationError(f"project not found: {title}")
        return None
    if len(matches) > 1:
        numbers = ", ".join(str(project.get("number")) for project in matches)
        raise AutomationError(f"multiple projects named {title!r}; numbers: {numbers}")
    return matches[0]


def project_node(details_data: dict[str, Any]) -> dict[str, Any]:
    project = details_data.get("node")
    if not project:
        raise AutomationError("project node is unavailable")
    for connection_name in ("fields", "repositories", "views", "workflows"):
        connection = project.get(connection_name, {})
        if connection.get("pageInfo", {}).get("hasNextPage"):
            raise AutomationError(
                f"project has more than 100 {connection_name}; refusing partial setup"
            )
    return project


def status_field(project: dict[str, Any]) -> dict[str, Any]:
    fields = project.get("fields", {}).get("nodes", [])
    matches = [
        field
        for field in fields
        if field.get("__typename") == "ProjectV2SingleSelectField"
        and field.get("name") == "Status"
    ]
    if len(matches) != 1:
        raise AutomationError(
            f"expected one Status single-select field, found {len(matches)}"
        )
    return matches[0]


def status_option_id(project: dict[str, Any], desired_status: str) -> tuple[str, str]:
    field = status_field(project)
    options = [
        option
        for option in field.get("options", [])
        if option.get("name") == desired_status
    ]
    if len(options) != 1:
        raise AutomationError(
            f"expected one Status option named {desired_status!r}, found {len(options)}"
        )
    return str(field["id"]), str(options[0]["id"])


def status_names(project: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(option.get("name", ""))
        for option in status_field(project).get("options", [])
    )


def verify_status_contract(
    project: dict[str, Any],
    *,
    expected_statuses: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    names = status_names(project)
    missing = [status for status in REQUIRED_AUTOMATED_STATUSES if status not in names]
    if missing:
        raise AutomationError(
            "Project is missing automated Status options: " + ", ".join(missing)
        )
    if expected_statuses is not None and names != expected_statuses:
        raise AutomationError(
            "copied Project Status options differ from source template: "
            f"source={expected_statuses!r}; target={names!r}"
        )
    return names


def pr_target_status(action: str, is_draft: bool, merged: bool = False) -> str | None:
    if action not in SUPPORTED_PR_ACTIONS:
        raise AutomationError(f"unsupported pull_request action: {action}")
    if action == "closed":
        return "Done" if merged else None
    if action == "ready_for_review":
        return "In review"
    if action == "converted_to_draft":
        return "In progress"
    return "In progress" if is_draft else "In review"


def issue_target_status(action: str) -> str:
    if action not in SUPPORTED_ISSUE_ACTIONS:
        raise AutomationError(f"unsupported issues action: {action}")
    return "Done" if action == "closed" else "Backlog"


def same_repo_closing_issues(
    pull_request_data: dict[str, Any],
    repository: str,
) -> list[dict[str, Any]]:
    repository_node = pull_request_data.get("repository")
    if not repository_node or not repository_node.get("pullRequest"):
        raise AutomationError("pull request could not be resolved")

    pull_request = repository_node["pullRequest"]
    closing = pull_request.get("closingIssuesReferences", {})
    if closing.get("pageInfo", {}).get("hasNextPage"):
        raise AutomationError(
            "pull request closes more than 20 issues; refusing partial status update"
        )

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for issue in closing.get("nodes", []):
        if issue.get("repository", {}).get("nameWithOwner") != repository:
            continue
        issue_id = str(issue["id"])
        if issue_id in seen:
            continue
        seen.add(issue_id)
        result.append(issue)
    return result


def set_content_status(
    client: GraphQLClient,
    *,
    project_id: str,
    content_id: str,
    field_id: str,
    option_id: str,
) -> str:
    add_data = client.execute(
        ADD_ITEM_MUTATION,
        {"projectId": project_id, "contentId": content_id},
    )
    item = add_data.get("addProjectV2ItemById", {}).get("item")
    if not item or not item.get("id"):
        raise AutomationError(f"project item unavailable for content {content_id}")

    item_id = str(item["id"])
    client.execute(
        UPDATE_STATUS_MUTATION,
        {
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "optionId": option_id,
        },
    )
    return item_id


def resolve_project(
    client: GraphQLClient,
    *,
    owner: str,
    title: str,
) -> dict[str, Any]:
    owner_data = client.execute(OWNER_PROJECTS_QUERY, {"login": owner})
    project = choose_project(owner_data, title)
    assert project is not None
    details = client.execute(PROJECT_DETAILS_QUERY, {"projectId": str(project["id"])})
    return project_node(details)


def list_open_issues(
    client: GraphQLClient,
    *,
    repository: str,
) -> list[dict[str, Any]]:
    owner, name = split_repository(repository)
    after: str | None = None
    result: list[dict[str, Any]] = []

    while True:
        data = client.execute(
            OPEN_ISSUES_QUERY,
            {"owner": owner, "name": name, "after": after},
        )
        repository_node = data.get("repository")
        if not repository_node:
            raise AutomationError(f"repository not found: {repository}")
        issues = repository_node.get("issues", {})
        result.extend(issues.get("nodes", []))
        page_info = issues.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            raise AutomationError("open-issue pagination cursor is missing")

    return result


def bootstrap_project(
    client: GraphQLClient,
    *,
    project_owner: str,
    source_title: str,
    target_title: str,
    repository: str,
) -> dict[str, Any]:
    repo_owner, repo_name = split_repository(repository)
    owner_data = client.execute(OWNER_PROJECTS_QUERY, {"login": project_owner})
    owner = owner_data.get("user")
    if not owner or not owner.get("id"):
        raise AutomationError("project owner user could not be resolved")

    source = choose_project(owner_data, source_title)
    assert source is not None
    source_details = client.execute(
        PROJECT_DETAILS_QUERY,
        {"projectId": str(source["id"])},
    )
    source_project = project_node(source_details)
    source_statuses = verify_status_contract(source_project)
    target = choose_project(owner_data, target_title, required=False)

    if target is None:
        copied = client.execute(
            COPY_PROJECT_MUTATION,
            {
                "projectId": str(source["id"]),
                "ownerId": str(owner["id"]),
                "title": target_title,
            },
        )
        target = copied.get("copyProjectV2", {}).get("projectV2")
        if not target or not target.get("id"):
            raise AutomationError("copied project was not returned by GitHub")
        print(
            f"project-bootstrap: copied {source_title!r} -> {target_title!r} "
            f"(#{target.get('number')})"
        )
    else:
        print(
            f"project-bootstrap: reusing existing {target_title!r} "
            f"(#{target.get('number')})"
        )

    repo_data = client.execute(
        REPOSITORY_QUERY,
        {"owner": repo_owner, "name": repo_name},
    )
    repository_node = repo_data.get("repository")
    if not repository_node or not repository_node.get("id"):
        raise AutomationError(f"repository not found: {repository}")

    details = client.execute(PROJECT_DETAILS_QUERY, {"projectId": str(target["id"])})
    project = project_node(details)
    linked_names = {
        str(node.get("nameWithOwner"))
        for node in project.get("repositories", {}).get("nodes", [])
    }
    if repository not in linked_names:
        client.execute(
            LINK_REPOSITORY_MUTATION,
            {
                "projectId": str(target["id"]),
                "repositoryId": str(repository_node["id"]),
            },
        )
        print(f"project-bootstrap: linked repository {repository}")
    else:
        print(f"project-bootstrap: repository already linked: {repository}")

    copied_statuses = verify_status_contract(
        project,
        expected_statuses=source_statuses,
    )
    print("project-bootstrap: copied Status columns -> " + " -> ".join(copied_statuses))

    field_id, backlog_option_id = status_option_id(project, "Backlog")
    open_issues = list_open_issues(client, repository=repository)
    for issue in open_issues:
        set_content_status(
            client,
            project_id=str(project["id"]),
            content_id=str(issue["id"]),
            field_id=field_id,
            option_id=backlog_option_id,
        )
    print(f"project-bootstrap: backfilled {len(open_issues)} open issue(s) -> Backlog")
    print(f"project-bootstrap: ready: {project.get('url')}")
    return project


def sync_event(
    client: GraphQLClient,
    *,
    event: dict[str, Any],
    event_name: str,
    repository: str,
    project_owner: str,
    project_title: str,
) -> None:
    project = resolve_project(client, owner=project_owner, title=project_title)
    project_id = str(project["id"])

    if event_name == "issues":
        issue = event.get("issue")
        if not isinstance(issue, dict):
            raise AutomationError("workflow event does not contain issue")
        action = str(event.get("action", ""))
        desired_status = issue_target_status(action)
        field_id, option_id = status_option_id(project, desired_status)
        content_id = str(issue.get("node_id", ""))
        if not content_id:
            raise AutomationError("issue event is missing node_id")
        number = int(issue["number"])
        set_content_status(
            client,
            project_id=project_id,
            content_id=content_id,
            field_id=field_id,
            option_id=option_id,
        )
        print(f"project-status: issue #{number} -> {desired_status}")
        return

    if event_name != "pull_request":
        raise AutomationError(f"unsupported GitHub event: {event_name}")

    pull_request_event = event.get("pull_request")
    if not isinstance(pull_request_event, dict):
        raise AutomationError("workflow event does not contain pull_request")

    action = str(event.get("action", ""))
    desired_status = pr_target_status(
        action,
        bool(pull_request_event.get("draft")),
        bool(pull_request_event.get("merged")),
    )
    pr_number = int(pull_request_event["number"])
    if desired_status is None:
        print(
            f"project-status: action={action} merged=false; "
            f"PR #{pr_number} status unchanged"
        )
        return

    repo_owner, repo_name = split_repository(repository)
    pr_data = client.execute(
        PULL_REQUEST_QUERY,
        {"owner": repo_owner, "name": repo_name, "number": pr_number},
    )
    repository_node = pr_data.get("repository")
    pull_request = repository_node.get("pullRequest") if repository_node else None
    if not pull_request:
        raise AutomationError("pull request could not be resolved")

    closing_issues = same_repo_closing_issues(pr_data, repository)
    field_id, option_id = status_option_id(project, desired_status)
    targets = [
        ("pull request", pr_number, str(pull_request["id"])),
        *[
            ("issue", int(issue["number"]), str(issue["id"]))
            for issue in closing_issues
        ],
    ]

    print(
        f"project-status: action={action} target={desired_status!r} "
        f"project={project_title!r} targets={len(targets)}"
    )
    for kind, number, content_id in targets:
        set_content_status(
            client,
            project_id=project_id,
            content_id=content_id,
            field_id=field_id,
            option_id=option_id,
        )
        print(f"project-status: {kind} #{number} -> {desired_status}")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise AutomationError(f"{name} is required")
    return value


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if len(args) != 1 or args[0] not in {"bootstrap", "sync-event"}:
            raise AutomationError("usage: project_automation.py {bootstrap|sync-event}")

        token = require_env("GH_TOKEN")
        repository = require_env("GITHUB_REPOSITORY")
        project_owner = require_env("PROJECT_OWNER")
        project_title = require_env("PROJECT_TITLE")
        client = GraphQLClient(token)

        if args[0] == "bootstrap":
            source_title = require_env("SOURCE_PROJECT_TITLE")
            bootstrap_project(
                client,
                project_owner=project_owner,
                source_title=source_title,
                target_title=project_title,
                repository=repository,
            )
            return 0

        event_name = require_env("GITHUB_EVENT_NAME")
        event_path = Path(require_env("GITHUB_EVENT_PATH"))
        event = load_event(event_path)
        sync_event(
            client,
            event=event,
            event_name=event_name,
            repository=repository,
            project_owner=project_owner,
            project_title=project_title,
        )
        return 0
    except (AutomationError, KeyError, TypeError, ValueError) as exc:
        print(f"project-automation: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
