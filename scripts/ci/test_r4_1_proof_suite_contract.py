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
            "stage3g_ride_through_sp638_local_corridor.py",
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
        self.assertIn("road_first_landscape_conform", wrapper)
        self.assertIn("official_sp638_gis", wrapper)
        self.assertIn('"terrain_owned_by_landscape": True', capture)
        self.assertIn('"custom_earthwork_mesh": False', capture)
        self.assertIn('"custom_meso_ground_mesh": False', capture)
        self.assertIn('LANDSCAPE_BASE_EDIT_LAYER = "MASE_Base"', capture)
        self.assertIn('LANDSCAPE_ROAD_EDIT_LAYER = "SP638_Road"', capture)
        self.assertIn("LANDSCAPE_CONFORM_SAMPLE_STEP_CM = 100.0", capture)
        self.assertIn("LANDSCAPE_MAX_ABS_CORRECTION_CM = 300.0", capture)
        self.assertIn("unreal.SplinePointType.LINEAR", capture)
        self.assertIn("edit_layer_delta_relative_to_landscape_origin", capture)
        self.assertIn("edit_layer_name=unreal.Name(LANDSCAPE_ROAD_EDIT_LAYER)", capture)
        self.assertIn("_replace_with_slice(spline, landscape_slice)", capture)
        self.assertIn("landscape_cut_fill.delta_proxy", wrapper)
        self.assertIn("apply_superelevation_to_profiles(", capture)
        self.assertIn("regularize_measured_superelevation_angles(", capture)
        self.assertIn("_sample_mase_lidar_bank_angles(", capture)
        self.assertIn("fit_road_crossfall_from_transect(", capture)
        self.assertIn('"mode": "mase_lidar_seeded_crossfall"', capture)
        self.assertIn(
            '"measurement_kind": "LiDAR_DTM_adaptive_road_transect_fit"',
            capture,
        )
        self.assertIn('"method": "adaptive_transect_linear_road_fit"', capture)
        self.assertIn("superelevation.peak_abs_bank_deg", wrapper)
        self.assertIn("superelevation.maximum_adjacent_delta_deg", wrapper)
        self.assertNotIn("proof_viewmode -ne 'lit'", wrapper)

    def test_transient_dynamic_mesh_normals_are_initialized_explicitly(self) -> None:
        capture = read("scripts/ue/stage3g_capture_sp638_local_corridor.py")
        spawn = capture.split("def _spawn_dynamic_mesh(", 1)[1].split(
            "\ndef main()", 1
        )[0]
        self.assertIn("dynamic_mesh.set_per_vertex_normals()", spawn)
        self.assertNotIn("dynamic_mesh.recompute_normals(", spawn)

    def test_transient_dynamic_mesh_tangent_mode_is_recorded_not_changed(
        self,
    ) -> None:
        # Diagnostic only: B.4.6 geometry fix must remain the single render
        # change under test, so the tangent mode is reported, never overridden.
        capture = read("scripts/ue/stage3g_capture_sp638_local_corridor.py")
        spawn = capture.split("def _spawn_dynamic_mesh(", 1)[1].split(
            "\ndef main()", 1
        )[0]
        self.assertIn("str(component.get_tangents_type())", spawn)
        self.assertIn('"tangents_type": tangents_type', spawn)
        self.assertNotIn("set_tangents_type(", spawn)

    def test_local_corridor_capture_waits_for_png_flush_and_uses_neutral_light(
        self,
    ) -> None:
        capture = read("scripts/ue/stage3g_capture_sp638_local_corridor.py")
        tick = capture.split("def _tick(", 1)[1].split("\ndef _dot(", 1)[0]
        self.assertIn("def _capture_png_is_ready(", capture)
        self.assertIn("CAPTURE_TIMEOUT_SECONDS = 90.0", capture)
        self.assertIn("MIN_CAPTURE_BYTES = 100_000", capture)
        self.assertIn("if not _capture_png_is_ready(_output_path):", tick)
        self.assertIn("if not _capture_png_is_ready(_actor_id_output_path):", tick)
        self.assertIn("_actor_id_output_path.unlink(missing_ok=True)", capture)
        self.assertIn("Rotator(pitch=-90.0, yaw=0.0, roll=0.0)", capture)
        self.assertGreaterEqual(
            capture.count("set_mobility(unreal.ComponentMobility.MOVABLE)"),
            2,
        )
        self.assertIn('"directional_mobility": "movable"', capture)
        self.assertIn('"skylight_mobility": "movable"', capture)
        self.assertIn('"purpose": "neutral_overhead_geometry_diagnostic"', capture)
        self.assertNotIn(
            "    level_editor.editor_set_viewport_realtime(True, viewport_config_key)",
            capture,
        )

    def test_transient_corridor_actor_handoff_survives_runpy_stage_boundary(
        self,
    ) -> None:
        capture = read("scripts/ue/stage3g_capture_sp638_local_corridor.py")
        dispatcher = read("scripts/ue/r4_1_editor_session.py")
        self.assertIn("_retained_transient_actors", capture)
        self.assertIn("_retained_transient_actors.append(actor)", capture)
        self.assertIn("_stage_runtime_globals", dispatcher)
        self.assertIn(
            '_stage_runtime_globals[str(stage["name"])] = stage_globals',
            dispatcher,
        )

    def test_local_corridor_ride_through_is_bounded_and_presentation_only(
        self,
    ) -> None:
        ride = read("scripts/ue/stage3g_ride_through_sp638_local_corridor.py")
        dispatcher = read("scripts/ue/r4_1_editor_session.py")
        self.assertIn("POWER_W = 100.0", ride)
        self.assertIn("START_BEFORE_HAIRPIN_M = 100.0", ride)
        self.assertIn("END_AFTER_HAIRPIN_M = 20.0", ride)
        self.assertIn("CAPTURE_RES_X = 1920", ride)
        self.assertIn("CAPTURE_RES_Y = 1080", ride)
        self.assertIn('"authoritative_sp638_physics": False', ride)
        self.assertIn(
            '"pace_source": "python_reference_physics_plus_local_visual_spline_grade"',
            ride,
        )
        self.assertIn("stage3g_ride_through_sp638_local_corridor.py", dispatcher)
        self.assertIn('"local_corridor_ride_through"', dispatcher)
        self.assertIn('"SP638_LocalCorridor_Asphalt"', ride)
        self.assertNotIn('"SP638_LocalCorridor_Earthwork"', ride)
        self.assertNotIn('"SP638_LocalMesoGround"', ride)

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
