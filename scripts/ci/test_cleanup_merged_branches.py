from __future__ import annotations

import unittest

import cleanup_merged_branches as cb


class BranchDecisionTests(unittest.TestCase):
    def test_default_branch_is_never_deleted(self):
        delete, reason = cb.should_delete(
            branch_name="main",
            branch_sha="MAIN",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names=set(),
            merged_head_shas={"MAIN"},
            tip_is_in_default=True,
        )
        self.assertFalse(delete)
        self.assertEqual(reason, "default branch")

    def test_open_pr_branch_is_preserved(self):
        delete, reason = cb.should_delete(
            branch_name="feat/live",
            branch_sha="NEW",
            default_branch="main",
            open_branch_names={"feat/live"},
            open_base_branch_names=set(),
            merged_head_shas={"OLD"},
            tip_is_in_default=False,
        )
        self.assertFalse(delete)
        self.assertEqual(reason, "open pull request")

    def test_branch_used_as_open_pr_base_is_preserved(self):
        delete, reason = cb.should_delete(
            branch_name="feat/parent",
            branch_sha="PRHEAD",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names={"feat/parent"},
            merged_head_shas={"PRHEAD"},
            tip_is_in_default=False,
        )
        self.assertFalse(delete)
        self.assertEqual(reason, "base of open pull request")

    def test_open_base_branches_collects_stack_bases(self):
        pulls = [
            {"base": {"ref": "main"}},
            {"base": {"ref": "feat/parent"}},
            {"base": {"ref": "feat/parent"}},
        ]
        self.assertEqual(
            cb.open_base_branches(pulls),
            {"main", "feat/parent"},
        )

    def test_branch_without_merged_pr_is_preserved(self):
        delete, reason = cb.should_delete(
            branch_name="feat/live",
            branch_sha="NEW",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names=set(),
            merged_head_shas=set(),
            tip_is_in_default=False,
        )
        self.assertFalse(delete)
        self.assertIn("no merged pull request", reason)

    def test_exact_squash_merged_head_is_deleted(self):
        delete, reason = cb.should_delete(
            branch_name="feat/done",
            branch_sha="PRHEAD",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names=set(),
            merged_head_shas={"PRHEAD"},
            tip_is_in_default=False,
        )
        self.assertTrue(delete)
        self.assertIn("matches a merged pull request", reason)

    def test_synced_stale_branch_contained_in_main_is_deleted(self):
        delete, reason = cb.should_delete(
            branch_name="docs/done",
            branch_sha="OLD_MAIN",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names=set(),
            merged_head_shas={"ORIGINAL_PR_HEAD"},
            tip_is_in_default=True,
        )
        self.assertTrue(delete)
        self.assertIn("contained in the default branch", reason)

    def test_reused_branch_with_new_work_is_preserved(self):
        delete, reason = cb.should_delete(
            branch_name="feat/reused",
            branch_sha="NEW_WORK",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names=set(),
            merged_head_shas={"OLD_PR_HEAD"},
            tip_is_in_default=False,
        )
        self.assertFalse(delete)
        self.assertIn("not proven merged", reason)

    def test_merged_heads_ignore_forks_and_unmerged_prs(self):
        pulls = [
            {
                "merged_at": "2026-09-25T00:00:00Z",
                "head": {
                    "ref": "feat/local",
                    "sha": "A",
                    "repo": {"full_name": "owner/repo"},
                },
            },
            {
                "merged_at": None,
                "head": {
                    "ref": "feat/open",
                    "sha": "B",
                    "repo": {"full_name": "owner/repo"},
                },
            },
            {
                "merged_at": "2026-09-25T00:00:00Z",
                "head": {
                    "ref": "feat/fork",
                    "sha": "C",
                    "repo": {"full_name": "someone/fork"},
                },
            },
        ]
        self.assertEqual(
            cb.merged_heads(pulls, "owner/repo"),
            {"feat/local": {"A"}},
        )

    def test_explicit_delete_marker_collects_closed_unmerged_heads(self):
        pulls = [
            {
                "merged_at": None,
                "body": cb.EXPLICIT_DELETE_MARKER,
                "head": {
                    "ref": "fix/superseded",
                    "sha": "OLD",
                    "repo": {"full_name": "owner/repo"},
                },
            },
            {
                "merged_at": "2026-09-25T00:00:00Z",
                "body": cb.EXPLICIT_DELETE_MARKER,
                "head": {
                    "ref": "fix/merged",
                    "sha": "MERGED",
                    "repo": {"full_name": "owner/repo"},
                },
            },
        ]
        self.assertEqual(
            cb.explicit_delete_heads(pulls, "owner/repo"),
            {"fix/superseded": {"OLD"}},
        )

    def test_explicit_marker_deletes_only_matching_current_tip(self):
        delete, reason = cb.should_delete(
            branch_name="fix/superseded",
            branch_sha="OLD",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names=set(),
            merged_head_shas=set(),
            tip_is_in_default=False,
            explicit_delete_head_shas={"OLD"},
        )
        self.assertTrue(delete)
        self.assertIn("explicitly marked safe", reason)

    def test_explicit_marker_does_not_delete_reused_branch(self):
        delete, reason = cb.should_delete(
            branch_name="fix/superseded",
            branch_sha="NEW_WORK",
            default_branch="main",
            open_branch_names=set(),
            open_base_branch_names=set(),
            merged_head_shas=set(),
            tip_is_in_default=False,
            explicit_delete_head_shas={"OLD"},
        )
        self.assertFalse(delete)
        self.assertIn("no merged pull request", reason)

    def test_open_heads_ignore_forks(self):
        pulls = [
            {
                "head": {
                    "ref": "feat/local",
                    "repo": {"full_name": "owner/repo"},
                }
            },
            {
                "head": {
                    "ref": "feat/fork",
                    "repo": {"full_name": "someone/fork"},
                }
            },
        ]
        self.assertEqual(cb.open_heads(pulls, "owner/repo"), {"feat/local"})


if __name__ == "__main__":
    unittest.main()
