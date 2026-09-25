from __future__ import annotations

import json
import unittest

import project_automation as pa


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RecordingClient:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def execute(self, query, variables):
        self.calls.append((query, variables))
        if not self.responses:
            return {}
        response = self.responses.pop(0)
        if callable(response):
            return response(query, variables)
        return response


class ProjectAutomationTests(unittest.TestCase):
    def test_pr_lifecycle_maps_to_expected_status(self):
        self.assertEqual(pa.pr_target_status("opened", True), "In progress")
        self.assertEqual(pa.pr_target_status("opened", False), "In review")
        self.assertEqual(pa.pr_target_status("reopened", True), "In progress")
        self.assertEqual(pa.pr_target_status("reopened", False), "In review")
        self.assertEqual(
            pa.pr_target_status("converted_to_draft", False), "In progress"
        )
        self.assertEqual(pa.pr_target_status("ready_for_review", True), "In review")
        self.assertEqual(pa.pr_target_status("closed", False, merged=True), "Done")
        self.assertIsNone(pa.pr_target_status("closed", False, merged=False))

    def test_issue_lifecycle_maps_to_expected_status(self):
        self.assertEqual(pa.issue_target_status("opened"), "Backlog")
        self.assertEqual(pa.issue_target_status("reopened"), "Backlog")
        self.assertEqual(pa.issue_target_status("closed"), "Done")

    def test_unsupported_actions_fail_closed(self):
        with self.assertRaisesRegex(pa.AutomationError, "unsupported"):
            pa.pr_target_status("synchronize", False)
        with self.assertRaisesRegex(pa.AutomationError, "unsupported"):
            pa.issue_target_status("edited")

    def test_choose_project_requires_exact_unique_title(self):
        data = {
            "user": {
                "projectsV2": {
                    "pageInfo": {"hasNextPage": False},
                    "nodes": [
                        {"id": "P1", "number": 1, "title": "Other"},
                        {
                            "id": "P2",
                            "number": 2,
                            "title": "4VELO — Product & Takeover",
                        },
                    ],
                }
            }
        }
        project = pa.choose_project(data, "4VELO — Product & Takeover")
        self.assertEqual(project["id"], "P2")
        self.assertIsNone(pa.choose_project(data, "Missing", required=False))
        with self.assertRaisesRegex(pa.AutomationError, "not found"):
            pa.choose_project(data, "Missing")

    def test_project_discovery_fails_on_unhandled_pagination(self):
        data = {
            "user": {
                "projectsV2": {
                    "pageInfo": {"hasNextPage": True},
                    "nodes": [],
                }
            }
        }
        with self.assertRaisesRegex(pa.AutomationError, "more than 100"):
            pa.choose_project(data, "Any")

    def test_status_contract_preserves_five_column_template(self):
        expected = (
            "Backlog",
            "Ready",
            "In progress",
            "In review",
            "Done",
        )
        project = {
            "fields": {
                "nodes": [
                    {
                        "__typename": "ProjectV2SingleSelectField",
                        "id": "STATUS",
                        "name": "Status",
                        "options": [
                            {"id": str(index), "name": name}
                            for index, name in enumerate(expected)
                        ],
                    }
                ]
            }
        }
        self.assertEqual(pa.verify_status_contract(project), expected)

    def test_status_contract_rejects_missing_automated_status(self):
        project = {
            "fields": {
                "nodes": [
                    {
                        "__typename": "ProjectV2SingleSelectField",
                        "id": "STATUS",
                        "name": "Status",
                        "options": [
                            {"id": "1", "name": "Backlog"},
                            {"id": "2", "name": "Ready"},
                            {"id": "3", "name": "In progress"},
                            {"id": "4", "name": "Done"},
                            {"id": "5", "name": "Other"},
                        ],
                    }
                ]
            }
        }
        with self.assertRaisesRegex(pa.AutomationError, "missing automated"):
            pa.verify_status_contract(project)

    def test_status_option_resolution_is_by_name(self):
        project = {
            "fields": {
                "nodes": [
                    {
                        "__typename": "ProjectV2SingleSelectField",
                        "id": "STATUS",
                        "name": "Status",
                        "options": [
                            {"id": "BACKLOG", "name": "Backlog"},
                            {"id": "READY", "name": "Ready"},
                            {"id": "PROGRESS", "name": "In progress"},
                            {"id": "REVIEW", "name": "In review"},
                            {"id": "DONE", "name": "Done"},
                        ],
                    }
                ]
            }
        }
        self.assertEqual(
            pa.status_option_id(project, "In review"), ("STATUS", "REVIEW")
        )
        self.assertEqual(pa.status_option_id(project, "Done"), ("STATUS", "DONE"))

    def test_same_repo_closing_issues_are_filtered_and_deduplicated(self):
        data = {
            "repository": {
                "pullRequest": {
                    "closingIssuesReferences": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {
                                "id": "I1",
                                "number": 10,
                                "repository": {
                                    "nameWithOwner": "karnalooch/YetAnotherCyclingSim"
                                },
                            },
                            {
                                "id": "I1",
                                "number": 10,
                                "repository": {
                                    "nameWithOwner": "karnalooch/YetAnotherCyclingSim"
                                },
                            },
                            {
                                "id": "I2",
                                "number": 20,
                                "repository": {"nameWithOwner": "elsewhere/repo"},
                            },
                        ],
                    }
                }
            }
        }
        issues = pa.same_repo_closing_issues(
            data, "karnalooch/YetAnotherCyclingSim"
        )
        self.assertEqual([issue["number"] for issue in issues], [10])

    def test_closing_issue_pagination_fails_instead_of_partial_update(self):
        data = {
            "repository": {
                "pullRequest": {
                    "closingIssuesReferences": {
                        "pageInfo": {"hasNextPage": True},
                        "nodes": [],
                    }
                }
            }
        }
        with self.assertRaisesRegex(pa.AutomationError, "more than 20"):
            pa.same_repo_closing_issues(data, "karnalooch/YetAnotherCyclingSim")

    def test_add_existing_item_result_is_valid_for_status_update(self):
        client = RecordingClient(
            [
                {"addProjectV2ItemById": {"item": {"id": "ITEM"}}},
                {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "ITEM"}}},
            ]
        )
        item_id = pa.set_content_status(
            client,
            project_id="PROJECT",
            content_id="CONTENT",
            field_id="STATUS",
            option_id="READY",
        )
        self.assertEqual(item_id, "ITEM")
        self.assertEqual(client.calls[1][1]["itemId"], "ITEM")

    def test_open_issue_listing_paginates(self):
        client = RecordingClient(
            [
                {
                    "repository": {
                        "issues": {
                            "pageInfo": {
                                "hasNextPage": True,
                                "endCursor": "CURSOR",
                            },
                            "nodes": [{"id": "I1", "number": 1}],
                        }
                    }
                },
                {
                    "repository": {
                        "issues": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "endCursor": None,
                            },
                            "nodes": [{"id": "I2", "number": 2}],
                        }
                    }
                },
            ]
        )
        issues = pa.list_open_issues(
            client, repository="karnalooch/YetAnotherCyclingSim"
        )
        self.assertEqual([issue["number"] for issue in issues], [1, 2])
        self.assertIsNone(client.calls[0][1]["after"])
        self.assertEqual(client.calls[1][1]["after"], "CURSOR")

    def test_graphql_errors_are_reported_without_token_leak(self):
        def opener(_request, timeout):
            self.assertEqual(timeout, 30)
            return FakeResponse({"errors": [{"message": "permission denied"}]})

        client = pa.GraphQLClient("secret-token-value", opener=opener)
        with self.assertRaisesRegex(pa.AutomationError, "permission denied") as context:
            client.execute("query { viewer { login } }", {})
        self.assertNotIn("secret-token-value", str(context.exception))

    def test_graphql_success_returns_data(self):
        def opener(_request, timeout):
            self.assertEqual(timeout, 30)
            return FakeResponse({"data": {"viewer": {"login": "karnalooch"}}})

        client = pa.GraphQLClient("token", opener=opener)
        self.assertEqual(
            client.execute("query { viewer { login } }", {}),
            {"viewer": {"login": "karnalooch"}},
        )


if __name__ == "__main__":
    unittest.main()
