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

    def test_suite_boots_unreal_once_for_all_bounded_proofs(self) -> None:
        suite = read("scripts/ue/Invoke-YacsR4_1ProofSuite.ps1")
        self.assertIn("run_r4_1_proof_session.py", suite)
        self.assertEqual(suite.count("Start-Process -FilePath $UEditor"), 1)
        self.assertIn("editor_boot_count = 1", suite)
        self.assertIn("r4_1_session_id", suite)
        self.assertIn("editor_pid", suite)
        self.assertNotIn("Invoke-R4_1ChildProof", suite)

        session = read("scripts/ue/run_r4_1_proof_session.py")
        for token in (
            "probe_geometry_script_api.py",
            "probe_sp638_local_corridor_topology.py",
            "stage3g_capture_passo_giau_hairpin_corridor.py",
            "stage3g_capture_sp638_local_corridor.py",
            "r4_1_session_id",
            "editor_pid",
            "editor_boot_count",
        ):
            self.assertIn(token, session)

    def test_capture_scripts_support_guarded_parent_session(self) -> None:
        for path in (
            "scripts/ue/stage3g_capture_passo_giau_hairpin_corridor.py",
            "scripts/ue/stage3g_capture_sp638_local_corridor.py",
        ):
            capture = read(path)
            self.assertIn('YACS_R4_1_SESSION_MODE', capture)
            self.assertIn("get_session_result", capture)
            self.assertIn("_session_result", capture)

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
