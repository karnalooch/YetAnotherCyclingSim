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

    def test_suite_boots_one_editor_and_validates_all_bounded_proofs(self) -> None:
        suite = read("scripts/ue/Invoke-YacsR4_1ProofSuite.ps1")
        self.assertIn("scripts/ue/r4_1_editor_session.py", suite)
        self.assertEqual(suite.count("Start-Process -FilePath $UEditor"), 1)
        self.assertIn("editor_process_count = 1", suite)
        self.assertIn("editor_boot_count = 1", suite)
        self.assertIn("'-ValidateOnly'", suite)
        for script in (
            "Invoke-YacsGeometryScriptProbe.ps1",
            "Invoke-YacsSp638CorridorTopologyProbe.ps1",
            "Invoke-YacsPassoGiauHairpinCorridorProof.ps1",
            "Invoke-YacsSp638LocalCorridorVisualProof.ps1",
        ):
            self.assertIn(script, suite)
        self.assertIn("'-PreparedWorkspaceStamp', $StampPath", suite)
        self.assertNotIn("Invoke-R4_1ChildProof", suite)

    def test_editor_dispatcher_is_fixed_scope_and_single_process(self) -> None:
        dispatcher = read("scripts/ue/r4_1_editor_session.py")
        for script in (
            "probe_geometry_script_api.py",
            "probe_sp638_local_corridor_topology.py",
            "stage3g_capture_passo_giau_hairpin_corridor.py",
            "stage3g_capture_sp638_local_corridor.py",
        ):
            self.assertIn(script, dispatcher)
        self.assertIn('"editor_process_count": 1', dispatcher)
        self.assertIn('"single_editor_process": True', dispatcher)
        self.assertIn("YACS_R4_1_SESSION_EXPECTED_HEAD", dispatcher)
        self.assertNotIn("input(", dispatcher)

    def test_visual_proofs_support_session_managed_lifetime(self) -> None:
        for path in (
            "scripts/ue/stage3g_capture_passo_giau_hairpin_corridor.py",
            "scripts/ue/stage3g_capture_sp638_local_corridor.py",
        ):
            script = read(path)
            self.assertIn("YACS_R4_1_EDITOR_SESSION_MANAGED", script)
            self.assertIn("def _release_python_script()", script)
            self.assertIn(
                "unreal.EditorPythonScripting.set_keep_python_script_alive(False)",
                script,
            )
            self.assertNotIn(
                'if os.environ.get(SESSION_MANAGED_ENV, "").strip() != "1":\n'
                "        _release_python_script()",
                script,
            )

    def test_rider_close_geometry_proof_is_material_independent(self) -> None:
        capture = read("scripts/ue/stage3g_capture_sp638_local_corridor.py")
        wrapper = read("scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1")
        self.assertNotIn('"viewmode lightingonly"', capture)
        self.assertIn("unreal.ViewModeIndex.VMI_LIGHTING_ONLY", capture)
        self.assertIn(
            "unreal.AutomationLibrary.set_editor_active_viewport_view_mode(",
            capture,
        )
        self.assertIn(
            "unreal.AutomationLibrary.get_editor_active_viewport_view_mode()",
            capture,
        )
        self.assertIn('"proof_viewmode": "lightingonly"', capture)
        self.assertIn('"material_independent_geometry_proof": True', capture)
        self.assertIn("unreal.LevelEditorSubsystem", capture)
        self.assertIn("get_active_viewport_config_key()", capture)
        self.assertIn("set_level_viewport_camera_info(", capture)
        self.assertIn("set_level_viewport_fov(76.0", capture)
        self.assertIn("editor_set_game_view(True", capture)
        self.assertIn('"capture_source": "primary_level_editor_viewport"', capture)
        self.assertIn('"offscreen_camera_capture": False', capture)
        self.assertIn('"viewport_viewmode_verified": True', capture)
        self.assertIn(
            '"AutomationLibrary.set_editor_active_viewport_view_mode"',
            capture,
        )
        self.assertIn("camera=None", capture)
        self.assertIn("force_game_view=False", capture)
        self.assertNotIn("unreal.CameraActor", capture)
        self.assertIn("proof_viewmode -ne 'lightingonly'", wrapper)
        self.assertIn("material_independent_geometry_proof", wrapper)
        self.assertIn("primary_level_editor_viewport", wrapper)
        self.assertIn("offscreen_camera_capture", wrapper)
        self.assertIn("viewport_viewmode_verified", wrapper)
        self.assertIn(
            "AutomationLibrary.set_editor_active_viewport_view_mode",
            wrapper,
        )
        self.assertIn("adaptive_asymmetric_earthwork_envelope", wrapper)
        self.assertIn("minimum_protected_clearance_m", wrapper)
        self.assertNotIn("proof_viewmode -ne 'lit'", wrapper)

    def test_child_wrappers_fail_closed_before_reuse(self) -> None:
        for path in (
            "scripts/ue/Invoke-YacsGeometryScriptProbe.ps1",
            "scripts/ue/Invoke-YacsSp638CorridorTopologyProbe.ps1",
            "scripts/ue/Invoke-YacsPassoGiauHairpinCorridorProof.ps1",
            "scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1",
        ):
            wrapper = read(path)
            self.assertIn("[string] $PreparedWorkspaceStamp", wrapper)
            self.assertIn("[switch] $ValidateOnly", wrapper)
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
