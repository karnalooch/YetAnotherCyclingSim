from __future__ import annotations

import unittest
from pathlib import Path

from unittest.mock import patch

import pr_orchestrator as po


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, object, object]] = []

    def rest(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        *,
        query: dict | None = None,
    ):
        self.calls.append((method, path, payload, query))
        if path.endswith("/update-branch"):
            return {"message": "Updating pull request branch."}
        if path.endswith("/merge"):
            return {"merged": True, "sha": "MERGED"}
        if "/pulls/" in path and method == "PATCH":
            return {"number": 1}
        raise AssertionError(f"unexpected REST call: {method} {path} {payload} {query}")

    def graphql(self, query: str, variables: dict):
        self.calls.append(("GRAPHQL", query, variables, None))
        return {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [],
                    }
                }
            }
        }


def pr_payload(
    *,
    number: int = 10,
    base: str = "main",
    head: str = "feat/test",
    sha: str = "HEAD",
    body: str = "Auto-merge: eligible",
    mergeable: bool = True,
    mergeable_state: str = "clean",
    draft: bool = False,
) -> dict:
    return {
        "number": number,
        "title": "Test PR",
        "body": body,
        "state": "open",
        "draft": draft,
        "mergeable": mergeable,
        "mergeable_state": mergeable_state,
        "user": {"login": "owner"},
        "base": {"ref": base},
        "head": {
            "ref": head,
            "sha": sha,
            "repo": {"full_name": "owner/repo"},
        },
    }


class MarkerTests(unittest.TestCase):
    def test_manual_marker_wins(self):
        self.assertEqual(
            po.auto_merge_mode(
                "Auto-merge: eligible\nAuto-merge: manual"
            ),
            "manual",
        )

    def test_eligible_marker_is_explicit_line(self):
        self.assertEqual(
            po.auto_merge_mode("x\nAuto-merge: eligible\ny"),
            "eligible",
        )
        self.assertIsNone(po.auto_merge_mode("please auto-merge: eligible later"))


class CheckTests(unittest.TestCase):
    def test_latest_check_run_wins(self):
        runs = [
            {"id": 1, "name": "Aggregate CI gate", "conclusion": "failure"},
            {"id": 2, "name": "Aggregate CI gate", "conclusion": "success"},
        ]
        self.assertEqual(po.missing_required_checks(runs), [])

    def test_missing_aggregate_blocks(self):
        runs = [{"id": 1, "name": "Repository policy", "conclusion": "success"}]
        self.assertEqual(
            po.missing_required_checks(runs),
            ["Aggregate CI gate"],
        )


class StackRelationTests(unittest.TestCase):
    def test_open_parent_map_uses_same_repo_heads_only(self):
        pulls = [
            pr_payload(number=1, head="parent"),
            {
                **pr_payload(number=2, head="forked"),
                "head": {
                    "ref": "forked",
                    "sha": "F",
                    "repo": {"full_name": "someone/fork"},
                },
            },
        ]
        mapping = po.open_parent_by_head(pulls, repository="owner/repo")
        self.assertEqual(set(mapping), {"parent"})
        self.assertEqual(mapping["parent"]["number"], 1)

    @patch.object(po, "get_pull_request")
    def test_child_waits_for_open_parent(self, get_pr):
        child = pr_payload(number=2, base="parent", head="child")
        parent = pr_payload(number=1, base="main", head="parent")
        get_pr.return_value = child
        api = FakeApi()

        result = po.evaluate_pull_request(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pr_summary=child,
            open_parents={"parent": parent},
        )

        self.assertEqual(result, "waiting-parent")
        self.assertEqual(api.calls, [])

    @patch.object(po, "merged_parent_for_branch")
    @patch.object(po, "get_pull_request")
    def test_child_retargets_after_parent_merged(
        self,
        get_pr,
        merged_parent,
    ):
        child = pr_payload(number=2, base="parent", head="child")
        get_pr.return_value = child
        merged_parent.return_value = {
            "number": 1,
            "merged_at": "2026-09-26T00:00:00Z",
        }
        api = FakeApi()

        result = po.evaluate_pull_request(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pr_summary=child,
            open_parents={},
        )

        self.assertEqual(result, "retargeted")
        self.assertIn(
            (
                "PATCH",
                "/repos/owner/repo/pulls/2",
                {"base": "main"},
                None,
            ),
            api.calls,
        )

    @patch.object(po, "get_pull_request")
    def test_child_behind_open_parent_is_updated_first(self, get_pr):
        child = pr_payload(
            number=2,
            base="parent",
            head="child",
            mergeable_state="behind",
        )
        parent = pr_payload(number=1, head="parent")
        get_pr.return_value = child
        api = FakeApi()

        result = po.evaluate_pull_request(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pr_summary=child,
            open_parents={"parent": parent},
        )

        self.assertEqual(result, "updated")
        self.assertTrue(
            any(path.endswith("/update-branch") for _m, path, _p, _q in api.calls)
        )


class RootLifecycleTests(unittest.TestCase):
    @patch.object(po, "get_pull_request")
    def test_root_behind_main_is_updated_before_checks(self, get_pr):
        root = pr_payload(mergeable_state="behind")
        get_pr.return_value = root
        api = FakeApi()

        result = po.evaluate_pull_request(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pr_summary=root,
            open_parents={},
        )

        self.assertEqual(result, "updated")
        self.assertTrue(
            any(path.endswith("/update-branch") for _m, path, _p, _q in api.calls)
        )

    @patch.object(po, "unresolved_review_threads", return_value=0)
    @patch.object(po, "list_reviews", return_value=[])
    @patch.object(
        po,
        "list_check_runs",
        return_value=[
            {
                "id": 10,
                "name": "Aggregate CI gate",
                "conclusion": "success",
            }
        ],
    )
    @patch.object(po, "get_pull_request")
    def test_clean_green_root_merges(
        self,
        get_pr,
        _checks,
        _reviews,
        _threads,
    ):
        root = pr_payload()
        get_pr.return_value = root
        api = FakeApi()

        result = po.evaluate_pull_request(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pr_summary=root,
            open_parents={},
        )

        self.assertEqual(result, "merged")
        self.assertTrue(
            any(path.endswith("/merge") for _m, path, _p, _q in api.calls)
        )

    @patch.object(po, "list_check_runs", return_value=[])
    @patch.object(po, "get_pull_request")
    def test_root_without_fresh_aggregate_does_not_merge(
        self,
        get_pr,
        _checks,
    ):
        root = pr_payload()
        get_pr.return_value = root
        api = FakeApi()

        result = po.evaluate_pull_request(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pr_summary=root,
            open_parents={},
        )

        self.assertEqual(result, "blocked")
        self.assertFalse(
            any(path.endswith("/merge") for _m, path, _p, _q in api.calls)
        )

    @patch.object(po, "get_pull_request")
    def test_manual_marker_never_enters_merge_flow(self, get_pr):
        root = pr_payload(
            body="Auto-merge: eligible\nAuto-merge: manual"
        )
        api = FakeApi()

        result = po.evaluate_pull_request(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pr_summary=root,
            open_parents={},
        )

        self.assertEqual(result, "not-eligible")
        get_pr.assert_not_called()


class OrderingTests(unittest.TestCase):
    @patch.object(po, "evaluate_pull_request", return_value="blocked")
    def test_roots_are_evaluated_before_children(self, evaluate):
        child = pr_payload(number=20, base="parent", head="child")
        root = pr_payload(number=30, base="main", head="root")
        parent = pr_payload(number=10, base="main", head="parent")
        api = FakeApi()

        exit_code = po.evaluate_eligible_pull_requests(
            api,
            repository="owner/repo",
            repository_owner="owner",
            default_branch="main",
            pull_requests=[child, root, parent],
        )

        self.assertEqual(exit_code, 0)
        numbers = [
            call.kwargs["pr_summary"]["number"]
            for call in evaluate.call_args_list
        ]
        self.assertEqual(numbers, [10, 30, 20])


class WorkflowContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        cls.workflow = (
            root / ".github" / "workflows" / "pr-orchestrator.yml"
        ).read_text(encoding="utf-8")
        cls.ci = (
            root / ".github" / "workflows" / "ci.yml"
        ).read_text(encoding="utf-8")

    def test_orchestrator_runs_only_trusted_default_branch_tooling(self):
        self.assertIn("pull_request_target:", self.workflow)
        self.assertIn('workflows: ["CyclingSim CI"]', self.workflow)
        self.assertIn(
            "ref: ${{ github.event.repository.default_branch }}",
            self.workflow,
        )
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertNotIn("secrets.", self.workflow)

    def test_orchestrator_has_minimal_required_write_permissions(self):
        self.assertIn("contents: write", self.workflow)
        self.assertIn("pull-requests: write", self.workflow)
        self.assertIn("checks: read", self.workflow)
        self.assertNotIn("issues: write", self.workflow)

    def test_stacked_prs_receive_normal_ci(self):
        self.assertIn("  pull_request:", self.ci)
        self.assertNotIn("pull_request:\n    branches: [main]", self.ci)
        self.assertIn("name: Aggregate CI gate", self.ci)


if __name__ == "__main__":
    unittest.main()
