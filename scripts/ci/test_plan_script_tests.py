"""Contract tests for fast Draft PR selection; unknown cases must run FULL."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.ci import plan_script_tests as p


ALL = sorted(
    (
        "scripts/assets/test_a.py",
        "scripts/blender/test_b.py",
        "scripts/ci/test_agent_contracts.py",
        "scripts/ci/test_ci_aggregate_contract.py",
        "scripts/ci/test_final_architecture_contract.py",
        "scripts/ci/test_script_test_discovery.py",
        "scripts/ci/test_unreal_ci.py",
        "scripts/geometry/test_g.py",
        "scripts/live_host/test_h.py",
        "scripts/runner/test_r.py",
        "scripts/ue/test_ue.py",
        "scripts/worldgen/test_pcg.py",
    )
)


class ScopeChoiceTests(unittest.TestCase):
    def test_pcg_edit_includes_native_consumer_and_guards(self):
        mode, reason, paths = p.decide_scope(
            ["scripts/worldgen/pcg365_mcp_adapter.py"], ALL
        )
        self.assertEqual(mode, "DRAFT_SCOPED")
        self.assertIn("scripts/worldgen/test_pcg.py", paths)
        self.assertIn("scripts/ue/test_ue.py", paths)
        self.assertIn("scripts/ci/test_ci_aggregate_contract.py", paths)
        self.assertNotIn("scripts/assets/test_a.py", paths)
        self.assertTrue(reason)

    def test_ue_editor_edit_includes_worldgen_and_guards(self):
        mode, _, paths = p.decide_scope(
            ["scripts/ue/pcg365_native_reduction_witness.py"], ALL
        )
        self.assertEqual(mode, "DRAFT_SCOPED")
        self.assertIn("scripts/worldgen/test_pcg.py", paths)
        self.assertIn("scripts/ue/test_ue.py", paths)

    def test_multiple_compatible_domains_deduplicate(self):
        mode, _, paths = p.decide_scope(
            ["scripts/worldgen/pcg.py", "scripts/ue/native.py"], ALL
        )
        self.assertEqual(mode, "DRAFT_SCOPED")
        self.assertEqual(len(paths), len(set(paths)))

    def test_draft_docs_only_keeps_policy_and_discovery_guards(self):
        mode, _, paths = p.decide_scope(["docs/README.md"], ALL)
        self.assertEqual(mode, "DRAFT_SCOPED")
        self.assertEqual(paths, list(p.SCOPED_GUARDS))

    def test_critical_or_unknown_changes_force_full(self):
        for changed in (
            [".github/workflows/ci.yml"],
            ["scripts/ci/run_script_tests.py"],
            ["scripts/ci/test_plan_script_tests.py"],
            ["scripts/ops/proof_broker.py"],
            ["Source/YetAnotherCyclingSim/Private/X.cpp"],
            ["Config/DefaultEngine.ini"],
            ["worldgen/sa_calobra/cliffs.json"],
            ["scripts/worldgen/fixture.json"],
            ["AGENTS.md"],
            ["scripts/new_domain/tool.py"],
            [],
            ["scripts/worldgen/a.py"] * 33,
        ):
            with self.subTest(changed=changed):
                mode, _, paths = p.decide_scope(changed, ALL)
                self.assertEqual(mode, "FULL")
                self.assertEqual(paths, ALL)

    def test_missing_guard_and_whole_domain_force_full(self):
        missing_guard = [x for x in ALL if x != p.SCOPED_GUARDS[0]]
        mode, _, selected = p.decide_scope(["scripts/worldgen/a.py"], missing_guard)
        self.assertEqual(mode, "FULL")
        self.assertEqual(selected, missing_guard)

    def test_mixed_docs_plus_domain_remains_scoped(self):
        mode, _, selected = p.decide_scope(
            ["docs/tooling/README.md", "scripts/worldgen/graph.py"], ALL
        )
        self.assertEqual(mode, "DRAFT_SCOPED")
        self.assertIn("scripts/worldgen/test_pcg.py", selected)


class GitHistoryTests(unittest.TestCase):
    @staticmethod
    def _fixture(root: Path) -> tuple[str, str]:
        (root / "scripts/ci").mkdir(parents=True)
        (root / "scripts/ue").mkdir(parents=True)
        (root / "scripts/worldgen").mkdir(parents=True)
        for index in range(p.MIN_MODULES):
            path = root / f"scripts/ci/test_fixture_{index:03}.py"
            path.write_text("import unittest\n", encoding="utf-8")
        for name in p.SCOPED_GUARDS:
            (root / name).write_text("import unittest\n", encoding="utf-8")
        (root / "scripts/worldgen/test_pcg.py").write_text(
            "import unittest\n", encoding="utf-8"
        )
        (root / "scripts/ue/test_ue.py").write_text(
            "import unittest\n", encoding="utf-8"
        )
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=root,
            check=True,
        )
        subprocess.run(["git", "config", "user.name", "CI Test"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=root, check=True)
        before = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        (root / "scripts/worldgen/example.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "change"], cwd=root, check=True)
        after = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        return before, after

    def test_single_commit_draft_is_scoped_but_ready_is_full(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before, after = self._fixture(root)
            draft = p.build_plan(root, draft_incremental=True, previous_sha=before)
            self.assertEqual(draft["head"], after)
            self.assertEqual(draft["mode"], "DRAFT_SCOPED")
            self.assertLess(len(draft["modules"]), draft["full_module_count"])
            ready = p.build_plan(root, draft_incremental=False, previous_sha=before)
            self.assertEqual(ready["mode"], "FULL")
            self.assertEqual(len(ready["modules"]), ready["full_module_count"])

    def test_missing_stale_or_malformed_before_runs_full(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before, after = self._fixture(root)
            for prev in ("", "wrong", after, "a" * 40):
                with self.subTest(prev=prev):
                    result = p.build_plan(
                        root, draft_incremental=True, previous_sha=prev
                    )
                    self.assertEqual(result["mode"], "FULL")
            self.assertNotEqual(before, after)

    def test_multiple_commits_rebase_or_non_ancestor_runs_full(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            before, _ = self._fixture(root)
            (root / "scripts/worldgen/example.py").write_text(
                "VALUE = 2\n", encoding="utf-8"
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "second"], cwd=root, check=True)
            result = p.build_plan(root, draft_incremental=True, previous_sha=before)
            self.assertEqual(result["mode"], "FULL")


if __name__ == "__main__":
    unittest.main()
