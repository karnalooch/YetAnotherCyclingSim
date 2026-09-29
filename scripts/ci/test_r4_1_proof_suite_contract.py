from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class R41PreparedProofSuiteContractTests(unittest.TestCase):
    def test_suite_builds_and_materializes_once(self) -> None:
        suite = read("scripts/ue/Invoke-YacsR4_1ProofSuite.ps1")
        self.assertEqual(suite.count("git -C $RepoRoot lfs pull"), 1)
        self.assertEqual(suite.count("Engine/Build/BatchFiles/Build.bat"), 1)
        self.assertIn("editor_build_count = 1", suite)
        self.assertIn("lfs_map_materialization_count = 1", suite)
        self.assertIn("prepared_workspace.json", suite)

    def test_suite_runs_all_bounded_proofs_from_same_stamp(self) -> None:
        suite = read("scripts/ue/Invoke-YacsR4_1ProofSuite.ps1")
        for script in (
            "Invoke-YacsGeometryScriptProbe.ps1",
            "Invoke-YacsSp638CorridorTopologyProbe.ps1",
            "Invoke-YacsPassoGiauHairpinCorridorProof.ps1",
            "Invoke-YacsSp638LocalCorridorVisualProof.ps1",
        ):
            self.assertIn(script, suite)
        self.assertIn("'-PreparedWorkspaceStamp', $StampPath", suite)
        self.assertIn("& $Pwsh @ChildArgs", suite)

    def test_child_wrappers_fail_closed_before_reuse(self) -> None:
        for path in (
            "scripts/ue/Invoke-YacsGeometryScriptProbe.ps1",
            "scripts/ue/Invoke-YacsSp638CorridorTopologyProbe.ps1",
            "scripts/ue/Invoke-YacsPassoGiauHairpinCorridorProof.ps1",
            "scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1",
        ):
            wrapper = read(path)
            self.assertIn("[string] $PreparedWorkspaceStamp", wrapper)
            self.assertIn("Test-YacsR4_1PreparedWorkspace.ps1", wrapper)

    def test_stamp_is_bound_to_sha_worktree_map_and_build(self) -> None:
        validator = read("scripts/ue/Test-YacsR4_1PreparedWorkspace.ps1")
        for token in (
            "git -C $RepoRoot rev-parse HEAD",
            "Prepared R4.1 stamp HEAD mismatch",
            "stamp belongs to a different worktree",
            "map byte count changed",
            "YetAnotherCyclingSimEditor",
            "Win64",
            "Development",
        ):
            self.assertIn(token, validator)

    def test_manual_heavy_workflow_uses_canonical_suite(self) -> None:
        workflow = read(".github/workflows/passo-giau-r4-1b3-geometry-probe.yml")
        self.assertIn("if: github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("Invoke-YacsR4_1ProofSuite.ps1", workflow)
        self.assertNotIn("./scripts/ue/Invoke-YacsGeometryScriptProbe.ps1", workflow)
        self.assertIn("git -C $worktree clean -ffdx", workflow)

    def test_legacy_hairpin_heavy_workflow_is_dispatch_only(self) -> None:
        workflow = read(".github/workflows/passo-giau-r4-1-hairpin-corridor.yml")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:", workflow)


if __name__ == "__main__":
    unittest.main()
