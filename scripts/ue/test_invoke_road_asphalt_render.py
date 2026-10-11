"""Road asphalt GPU host policy regression; independent native capture is required."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "scripts/ue/Invoke-YacsRoadAsphaltRender.ps1"
WORKFLOW = ROOT / ".github/workflows/road-material-native-proof.yml"
ATTRIBUTES = ROOT / ".gitattributes"


def add_capture_state_fixture(receipt):
    """Production snapshot shape over synthetic getters, never renderer evidence."""
    from scripts.ue import road_asphalt_gpu_review as gpu
    from scripts.ue.test_road_asphalt_gpu_review import CaptureReadback

    native = CaptureReadback()
    native.values["r.TSR.ThinGeometryDetection"] = ""  # Missing is explicitly unknown.
    api = SimpleNamespace(SystemLibrary=native)
    receipt["capture_state_native_api"] = gpu.capture_state_api_evidence(api)
    for frame in receipt["frames"]:
        for capture in [*frame["priming_frames"], frame]:
            capture.update(native_capture_state_before=gpu.native_capture_state(api),
                           native_capture_state_after=gpu.native_capture_state(api),
                           capture_cvars_unchanged=True)


class RoadAsphaltGpuHostContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = HOST.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_gpu_review_follows_saved_and_fresh_reopened_native_consumer(self):
        order = (
            "Stage verified consumer and read native baseline",
            "Run isolated reversible road asphalt canary",
            "Save and fresh-reopen the isolated road asphalt consumer",
            "Capture native road-facing lit GPU review",
            "Retain native inventory and owned-process evidence",
        )
        positions = [self.workflow.index(stage) for stage in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Invoke-YacsRoadAsphaltRender.ps1", self.workflow)

    def test_bounded_pinned_windows_host_and_gui_rhi(self):
        for key in (
            "Require-ExactSource",
            "'scripts/ue/sa_calobra_material_waves.py'",
            "Require-IdleHost",
            "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS",
            "Get-YacsUnrealHostState.ps1",
            "UnrealEditor-Cmd.exe",
            "UnrealEditor.exe",
            "-RenderOffscreen",
            "-norhithread",
            "-ScriptErrorsAreFatal",
            "Unreal GPU review process",
            "WaitForExit(200)",
            "1200",
            "readHost.value.proof_files",
            "road-asphalt-lit-review.json",
            "road-asphalt-gpu-host-receipt.json",
            "ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS",
            "File-Identity",
            "Write-ExclusiveReceipt",
            "Get-FileHash",
            "saved_derived_consumer",
        ):
            with self.subTest(key=key):
                self.assertIn(key, self.host)
        self.assertNotIn("'-NullRHI'", self.host)
        self.assertNotIn("save_map(", self.host)
        self.assertNotIn("Start-Job", self.host)

    def test_flags_never_admit_owner_visual_performance_or_shader_benchmark(self):
        for key in (
            "PENDING_FINAL_M3",
            "DEFERRED_AFTER_M3",
            "gpu_shader_compilation_admitted = $false",
            "road_pixel_visibility_admitted = $false",
            "native_lit_frames_retained",
            "transient_dirty_package_audit",
            "gpu_shutdown_quiescence_seconds",
            "verified_frame_count",
            "owner_visual_status",
            "performance_pass = $false",
            "shoulder_network_material_ids_verified",
            "shoulder_wall_materials_unchanged",
            "exhaustive_road_pixel_visibility",
            "whole_area_owner_accepted",
        ):
            self.assertIn(key, self.host)

    def test_gpu_wrapper_bytes_and_workflow_triggers_are_explicit(self):
        attributes = ATTRIBUTES.read_text(encoding="utf-8")
        self.assertIn(
            "scripts/ue/Invoke-YacsRoadAsphaltRender.ps1 text eol=lf",
            attributes,
        )
        self.assertNotIn(b"\r", HOST.read_bytes())
        trigger = self.workflow.split("permissions:", 1)[0]
        for name in (
            "scripts/ue/Invoke-YacsRoadAsphaltRender.ps1",
            "scripts/ue/road_asphalt_gpu_review.py",
            "scripts/ue/test_road_asphalt_gpu_review.py",
            "scripts/ue/road_shoulder_sources.py",
            "scripts/ue/road_shoulder_network.py",
            "scripts/ue/road_material_views.py",
            "Source/YetAnotherCyclingSimEditor/Public/Diagnostics/YacsRoadMaterialInspectionLibrary.h",
            "Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsRoadMaterialInspectionLibrary.cpp",
        ):
            self.assertIn("- '" + name + "'", trigger)

    def test_expected_ordered_plan_is_pinned_before_editor_and_rechecked_afterwards(self):
        for name in (
            "road-asphalt-expected-view-plan.json", "current_view_plan",
            "YACS_ROAD_MATERIAL_VIEW_PLAN_SHA256", "Assert-GpuReviewContract",
            "Assert-JsonEqual $expected $actualPose", "verified_frame_ids",
            "Assert-Identity $expectedPlan.identity 2MB",
            "$frame.priming_frames[$prime]", "capture-readiness.json",
            "road-texture-readiness.json", "resident_mips -ne $native.mips",
        ):
            self.assertIn(name, self.host)
        self.assertLess(self.host.index("Write-ExclusiveReceipt $planPath $plan"),
                        self.host.index("$renderProcess = Start-Process"))
        self.assertIn("$planPython.path -I -B -c $planCode $root", self.host)
        self.assertNotIn("$data.frame_count -ne 4", self.host)
        self.assertNotIn("window0112_selected_triangle_count", self.host)
        self.assertIn("$network.selected_triangle_count", self.host)
        self.assertIn("timeout-minutes: 38", self.workflow)

    def test_only_full_network_manifest_gets_measured_four_mib_bound(self):
        # 186 owners plus up to 74,028 selected IDs need ~1.99 MB before
        # material/API/assets. GPU rows instead reference separate mip files:
        # the prior 4-row receipt was 10,335 bytes, ~200 KB conservatively for 68.
        self.assertIn("param([string] $Path, [long] $Limit = 2MB)", self.host)
        self.assertIn("'road-asphalt-saved-manifest.json') 4MB", self.host)
        self.assertIn("Assert-Identity $savedManifest.identity 4MB", self.host)
        self.assertIn("Read-PinnedJson (Join-Path $proof 'road-asphalt-lit-review.json')", self.host)
        self.assertIn("$raw.Length -gt 2MB", self.host)

    def test_profile_copies_are_rehashed_and_bound_to_fresh_and_gpu_receipts(self):
        for value in (
            "$PROFILE_DIAGNOSTIC = 'road-network-profile-diagnostic.json'",
            "$Pin.size_bytes -gt 8MB", "$Pin.Count -ne 3",
            "File-Identity (Join-Path $ProofRoot $PROFILE_DIAGNOSTIC) 8MB",
            "File-Identity (Join-Path $RetainedRoot $PROFILE_DIAGNOSTIC) 8MB",
            "Resolve-ProfileRetainedRoot $workspace.value $WorkspaceConfig",
            "$readHost.value.proof_files.workspace_config.sha256",
            "$savedReceipt.value.retained_root", "$savedManifest.value.road_profile_diagnostic",
            "$reopenReceipt.value.road_profile_diagnostic_sha256 -cne $profileCopies.proof.sha256",
            "$Data.road_profile_diagnostic_sha256 -cne $ProfileSha",
            "Assert-Identity $profileCopies.proof 8MB",
            "Assert-Identity $profileCopies.retained 8MB",
            "Assert-Identity $workspace.identity 2MB",
        ):
            self.assertIn(value, self.host)
        self.assertLess(self.host.index("$profileCopies = Get-ProfileCopies"),
                        self.host.index("$renderProcess = Start-Process"))
        self.assertGreater(self.host.index("Assert-Identity $profileCopies.retained 8MB"),
                           self.host.index("$renderProcess.ExitCode -ne 0"))

    def test_native_pose_is_observed_and_recomputed_for_final_and_priming_frames(self):
        for value in (
            "Assert-NativeCameraObservation $expected $frame.native_camera_observation",
            "Assert-NativeCameraObservation $expected $frame.priming_frames[$prime].native_camera_observation",
            "$Observed.rotation_setter_accepted -isnot [bool]",
            "$Pose.target_cm[$axis] - $Pose.camera_location_cm[$axis]",
            "$error -gt 0.00001", "$Observed.forward_error -lt 0",
            "-gt 0.1", "-gt 0.001", "[double]::IsFinite([double]$number)",
        ):
            self.assertIn(value, self.host)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_profile_sidecar_rejects_changed_bytes_bounds_and_retained_path(self):
        from scripts.ue.test_invoke_road_saved_consumer import run_profile_sidecar_contract_cases

        run_profile_sidecar_contract_cases(self, HOST, "File-Identity")

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_powershell_contract_rejects_same_count_different_plan_and_failed_readiness(self):
        from scripts.ue.road_material_views import current_view_plan

        plan = current_view_plan()
        frames = []
        for pose in plan["frames"]:
            name = pose["frame_id"]
            delta = [target - eye for target, eye in zip(pose["target_cm"], pose["camera_location_cm"], strict=True)]
            length = math.sqrt(sum(value * value for value in delta))
            frames.append({**deepcopy(pose), "file": f"road-asphalt-lit-review/frames/{name}.png",
                "native_viewmode_before": "VMI_LIT", "native_viewmode_after": "VMI_LIT",
                "native_camera_observation": {"rotation_setter_accepted": True,
                    "location_cm": list(pose["camera_location_cm"]),
                    "forward_unit": [value / length for value in delta],
                    "fov_deg": pose["fov_deg"], "forward_error": 0.0},
                "width": 1280, "height": 720, "unique_sampled_rgb": 100,
                "visual_quality_reviewed": False, "render_mode": "lit",
                "capture_readiness": {"status": "NATIVE_LOADING_AND_MIPS_READY",
                    "height_mip_lease_requested": True, "viewport_primed_at_rider_camera": True,
                    "material_texture_count": 7},
                "priming_frames": [{"file": f"road-asphalt-lit-review/priming/{name}-{i:02d}.png",
                    "native_viewmode_before": "VMI_LIT", "native_viewmode_after": "VMI_LIT",
                    "native_camera_observation": {"rotation_setter_accepted": True,
                        "location_cm": list(pose["camera_location_cm"]),
                        "forward_unit": [value / length for value in delta],
                        "fov_deg": pose["fov_deg"], "forward_error": 0.0}}
                                   for i in range(3)]})
        # Only a pure wrapper-contract fixture; no files, pixels, engine or
        # native material proof are represented by these synthetic flags.
        good = {"status": "ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED", "schema_version": 1,
            "issue": 364, "exact_sha": "a" * 40, "run_token": "123-1",
            "saved_manifest_sha256": "b" * 64, "view_plan_sha256": "c" * 64,
            "road_profile_diagnostic_sha256": "e" * 64,
            "camera_csv_sha256": plan["survey_sha256"],
            "frame_count": len(frames), "expected_frame_count": len(frames), "frames": frames,
            "shoulder_support_count": 186, "shoulder_material_target_count": 185,
            "shoulder_selected_triangle_count": 1234, "priming_frames_per_pose": 3,
            "completed_priming_frames": len(frames) * 3, "gpu_shutdown_quiescence_seconds": 10.0,
            "owner_visual_status": "PENDING_FINAL_M3", "performance_status": "DEFERRED_AFTER_M3",
            "errors": [], "native_lit_frames_retained": True,
            "shoulder_network_material_ids_verified": True, "shoulder_wall_materials_unchanged": True,
            "shoulder_material_edge_uv_verified": True,
            "road_full_buffers_unchanged": True, "dry_asphalt_response_verified": True,
            "sources_and_saved_assets_unchanged": True, "capture_readiness_verified": True,
            "residency_requests_released": True, "transient_camera_destroyed": True,
            "gpu_shader_compilation_admitted": False, "road_pixel_visibility_admitted": False,
            "whole_area_visual_admitted": False, "shoulder_wall_materials_admitted": False,
            "exhaustive_road_pixel_visibility": False, "whole_area_owner_accepted": False,
            "terrain_geometry_repaired": False, "performance_pass": False,
            "transient_dirty_package_audit": {"no_original_or_content_package_dirty": True,
                "dirty_derived_package_saved": False, "dirty_content_count": 0},
            "material_view_sampling": {key: value for key, value in plan.items() if key != "frames"}}
        add_capture_state_fixture(good)
        self.assertLess(len(json.dumps(good, sort_keys=True, indent=2).encode()), 2 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "input.json"
            fixture.write_text(json.dumps({"plan": plan, "good": good}, allow_nan=False), encoding="utf-8")
            runner = root / "contracts.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
foreach ($name in @('Assert-JsonEqual', 'Assert-ViewPlan', 'Assert-NativeCameraObservation',
                    'Assert-CaptureStateApi', 'Assert-CaptureStatePair', 'Assert-GpuReviewContract')) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw 'Missing unique production validation function.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$fixture = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
$plan = $fixture.plan
function Check($data) {
    Assert-GpuReviewContract $data $plan ('c' * 64) ('b' * 64) 1234 ('a' * 40) '123-1' ('e' * 64)
}
Check $fixture.good
$drift = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
$drift.frames[-1].native_capture_state_after.cvars['r.ScreenPercentage'].raw = '99'
$drift.frames[-1].native_capture_state_after.cvars['r.ScreenPercentage'].value = 99.0
$drift.frames[-1].capture_cvars_unchanged = $false
Check $drift # Observe real drift; never silently override it or claim an effective view state.
$crackLit = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
foreach ($frame in $crackLit.frames) { $frame.capture_readiness.material_texture_count = 15 }
Assert-GpuReviewContract $crackLit $plan ('c' * 64) ('b' * 64) 1234 ('a' * 40) '123-1' ('e' * 64) 15
$rejectedDefault = $false
try { Check $crackLit } catch { $rejectedDefault = $true }
if (-not $rejectedDefault) { throw 'Legacy seven-texture default admitted the fifteen-texture lane.' }
$crackLit.frames[-1].capture_readiness.material_texture_count = 7
$rejectedPartial = $false
try { Assert-GpuReviewContract $crackLit $plan ('c' * 64) ('b' * 64) 1234 ('a' * 40) '123-1' ('e' * 64) 15 }
catch { $rejectedPartial = $true }
if (-not $rejectedPartial) { throw 'Crack Lit lane omitted the last pose crack texture residency.' }
foreach ($failure in @('order', 'pose', 'station', 'plan_hash', 'profile', 'priming', 'priming_total',
                       'mips', 'supports', 'selected_ids', 'walls', 'road_buffers', 'asphalt',
                       'admission', 'edge_uv', 'sampling', 'shader', 'native_location', 'native_rotation',
                       'native_direction', 'native_fov', 'native_error', 'native_nonfinite', 'native_missing',
                       'prime_direction', 'prime_missing', 'prime_viewmode', 'final_viewmode',
                       'snapshot_raw', 'snapshot_nonfinite', 'snapshot_cvar_missing', 'snapshot_getter_missing',
                       'snapshot_effective', 'snapshot_counter_bool', 'snapshot_stability', 'prime_snapshot')) {
    $data = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'order' { $swap = $data.frames[0]; $data.frames[0] = $data.frames[1]; $data.frames[1] = $swap }
        'pose' { $data.frames[0].camera_location_cm[2] += 0.001 }
        'station' { $data.frames[0].station_m += 0.1 }
        'plan_hash' { $data.view_plan_sha256 = 'd' * 64 }
        'profile' { $data.road_profile_diagnostic_sha256 = 'f' * 64 }
        'priming' { $data.frames[0].priming_frames = $data.frames[0].priming_frames[0..1] }
        'priming_total' { $data.completed_priming_frames -= 1 }
        'mips' { $data.frames[0].capture_readiness.status = 'UNKNOWN' }
        'supports' { $data.shoulder_support_count = 185 }
        'selected_ids' { $data.shoulder_selected_triangle_count += 1 }
        'walls' { $data.shoulder_wall_materials_unchanged = $false }
        'road_buffers' { $data.road_full_buffers_unchanged = $false }
        'asphalt' { $data.dry_asphalt_response_verified = $false }
        'edge_uv' { $data.shoulder_material_edge_uv_verified = $false }
        'admission' { $data.whole_area_owner_accepted = $true }
        'sampling' { $data.material_view_sampling.occupied_road_cells[0][0] += 1 }
        'shader' { $data.gpu_shader_compilation_admitted = $true }
        'native_location' { $data.frames[0].native_camera_observation.location_cm[0] += 0.2 }
        'native_rotation' { $data.frames[0].native_camera_observation.rotation_setter_accepted = $false }
        'native_direction' { $data.frames[0].native_camera_observation.forward_unit[0] *= -1 }
        'native_fov' { $data.frames[0].native_camera_observation.fov_deg += 0.01 }
        'native_error' { $data.frames[0].native_camera_observation.forward_error = 0.000005 }
        'native_nonfinite' { $data.frames[0].native_camera_observation.forward_unit[0] = [double]::NaN }
        'native_missing' { $data.frames[0].Remove('native_camera_observation') | Out-Null }
        'prime_direction' { $data.frames[0].priming_frames[1].native_camera_observation.forward_unit[0] *= -1 }
        'prime_missing' { $data.frames[0].priming_frames[2].Remove('native_camera_observation') | Out-Null }
        'prime_viewmode' { $data.frames[0].priming_frames[2].native_viewmode_after = 'VMI_VISUALIZE_BUFFER' }
        'final_viewmode' { $data.frames[0].native_viewmode_before = 'VMI_UNLIT' }
        'snapshot_raw' { $data.frames[0].native_capture_state_after.cvars['r.ScreenPercentage'].raw = '99' }
        'snapshot_nonfinite' { $data.frames[0].native_capture_state_before.cvars['r.ScreenPercentage'].raw = 'NaN' }
        'snapshot_cvar_missing' { $data.frames[0].native_capture_state_after.cvars.Remove('r.AntiAliasingMethod') | Out-Null }
        'snapshot_getter_missing' { $data.capture_state_native_api.reflected_methods.Remove('SystemLibrary.get_frame_count') | Out-Null }
        'snapshot_effective' { $data.frames[0].native_capture_state_after.effective_view_aa = 'TSR' }
        'snapshot_counter_bool' { $data.frames[0].native_capture_state_after.frame_count = $true }
        'snapshot_stability' { $data.frames[0].capture_cvars_unchanged = $false }
        'prime_snapshot' { $data.frames[-1].priming_frames[2].Remove('native_capture_state_before') | Out-Null }
    }
    $rejected = $false
    try { Check $data } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production GPU gate admitted ' + $failure) }
}
'POWERSHELL_GPU_CONTRACT_CASES_PASS'
''', encoding="utf-8")
            result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(HOST), str(fixture)],
                capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("POWERSHELL_GPU_CONTRACT_CASES_PASS", result.stdout)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_control_gate_rejects_changed_images_modes_and_restoration(self):
        from scripts.ue import road_asphalt_visual_controls as controls
        from scripts.ue.road_asphalt_saved_consumer import MAP

        plan = controls.control_plan()
        original = "/Game/Generated/YACS/RoadAsphaltConsumer/MI_Test.MI_Test"
        transient = "/Engine/Transient.ControlFixture"
        frames, applied = [], []
        for job in plan["jobs"]:
            pose, mode = job["camera"], job["control"]
            delta = [target - eye for target, eye in zip(pose["target_cm"], pose["camera_location_cm"], strict=True)]
            length = math.sqrt(sum(value * value for value in delta))
            camera = {"rotation_setter_accepted": True, "location_cm": list(pose["camera_location_cm"]),
                "forward_unit": [value / length for value in delta], "fov_deg": pose["fov_deg"], "forward_error": 0.0}
            observation = {"control": mode,
                "active_viewmode_readback": "VMI_VISUALIZE_BUFFER" if mode in controls.BUFFERS else "VMI_LIT",
                "road_material_readback": transient if mode == "uniform-lit" else original,
                "requested_buffer": controls.BUFFERS.get(mode), "buffer_name_readback_verified": False}
            capture = {"native_camera_observation": camera,
                "native_viewmode_before": observation["active_viewmode_readback"],
                "native_viewmode_after": observation["active_viewmode_readback"],
                "native_control_observation_before": observation, "native_control_observation_after": observation}
            frames.append({**deepcopy(pose), **deepcopy(capture), "frame_id": job["job_id"], "source_frame_id": pose["frame_id"],
                "control_mode": mode, "file": "road-asphalt-visual-controls/frames/" + job["job_id"] + ".png",
                "width": 1280, "height": 720, "unique_sampled_rgb": 100,
                "render_mode": "buffer_visualization" if mode in controls.BUFFERS else "lit",
                "visual_quality_reviewed": False,
                "capture_readiness": {"status": "NATIVE_LOADING_AND_MIPS_READY",
                    "height_mip_lease_requested": True, "viewport_primed_at_rider_camera": True,
                    "material_texture_count": 7},
                "priming_frames": [{**deepcopy(capture),
                    "file": f"road-asphalt-visual-controls/priming/{job['job_id']}-{index:02d}.png"}
                    for index in range(3)]})
            applied.append({"job_id": job["job_id"], **observation})
        ownership = {"run_token": "123-1", "consumer_exact_sha": "a" * 40,
            "owned_process_marker_verified": True, "pid": 1234}
        native_api = {"engine_version": controls.ENGINE_VERSION, "synthetic_fixture": True}
        good = {"schema_version": 1, "issue": 364,
            "status": "ROAD_ASPHALT_VISUAL_CONTROLS_FRAMES_RETAINED",
            "exact_sha": "a" * 40, "run_token": "123-1", "map_package": MAP,
            "saved_manifest_sha256": "b" * 64, "view_plan_sha256": "c" * 64,
            "camera_csv_sha256": plan["survey_sha256"],
            "lit_review_receipt": {"file": "road-asphalt-lit-review.json", "sha256": "d" * 64, "size_bytes": 100},
            "control_plan": plan, "control_plan_sha256": controls.digest(plan),
            "frame_count": 8, "expected_frame_count": 8, "frames": frames,
            "priming_frames_per_pose": 3, "completed_priming_frames": 24,
            "total_deadline_seconds_shared_with_lit": 1080, "frame_deadline_seconds": 180,
            "owner_visual_status": "PENDING_FINAL_M3", "performance_status": "DEFERRED_AFTER_M3", "errors": [],
            "preflight": {"ownership": ownership, "native_api": native_api},
            "begin": {"status": "READY", "plan_sha256": controls.digest(plan),
                "original_material": original, "transient_material": transient,
                "ownership": ownership, "native_api": native_api,
                "uniform_node_count": 6, "uniform_material": controls.UNIFORM,
                "view_state_contract": "owned_editor_establish_Lit_and_restore_Lit",
                "buffer_name_getter_available": False, "geometry_vertex_normals_preserved": True},
            "restore": {"status": "RESTORED", "plan_sha256": controls.digest(plan),
                "applied_jobs": applied, "cleanup_errors": [],
                "original_material_restored": True, "owned_viewports_returned_to_lit": True,
                "saved_and_staged_package_bytes_unchanged": True},
            **{key: True for key in ("control_restoration_verified", "capture_readiness_verified",
                "native_control_observations_verified", "sources_and_saved_assets_unchanged")},
            **{key: False for key in ("native_channel_images_reviewed", "buffer_name_readback_verified",
                "geometry_or_source_texture_change", "map_saved", "source_assets_saved",
                "whole_area_visual_admitted", "performance_pass")}}
        # This runs only receipt policy against disposable synthetic data. It
        # does not assert that a native image or restored UE scene exists.
        add_capture_state_fixture(good)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "input.json"
            fixture.write_text(json.dumps({"expected": {"control_plan": plan, "sha256": controls.digest(plan)},
                "original": original, "lit": {"sha256": "d" * 64, "size_bytes": 100}, "good": good},
                allow_nan=False), encoding="utf-8")
            runner = root / "control-contracts.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
foreach ($name in @('Assert-JsonEqual', 'Assert-NativeCameraObservation',
                    'Assert-CaptureStateApi', 'Assert-CaptureStatePair',
                    'Assert-VisualControlObservation', 'Assert-VisualControlContract')) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw 'Missing unique production visual control function.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$fixture = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
function Check($data) {
    Assert-VisualControlContract $data $fixture.expected ('c' * 64) ('b' * 64) `
        $fixture.lit $fixture.original ('a' * 40) '123-1'
}
Check $fixture.good
$withCracks = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
foreach ($frame in $withCracks.frames) { $frame.capture_readiness.material_texture_count = 15 }
Assert-VisualControlContract $withCracks $fixture.expected ('c' * 64) ('b' * 64) `
    $fixture.lit $fixture.original ('a' * 40) '123-1' $false 15
$rejectedSevenOnly = $false
try { Check $withCracks } catch { $rejectedSevenOnly = $true }
if (-not $rejectedSevenOnly) { throw 'Legacy control default admitted the wrong texture lane.' }
foreach ($failure in @('order', 'camera', 'source_pose', 'mode', 'file', 'count', 'plan', 'plan_hash',
                       'lit_receipt', 'manifest', 'prime_count', 'prime_name', 'prime_mode', 'prime_camera',
                       'material', 'buffer', 'buffer_claim', 'mips', 'restoration', 'view_restore',
                       'saved_bytes', 'owner', 'performance', 'deadline', 'token', 'transient',
                       'preflight', 'uniform', 'normals', 'api_claim', 'station', 'render_mode', 'visual_claim', 'prime_viewmode', 'prime_snapshot')) {
    $data = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'order' { $swap = $data.frames[0]; $data.frames[0] = $data.frames[1]; $data.frames[1] = $swap }
        'camera' { $data.frames[0].native_camera_observation.location_cm[0] += 1 }
        'source_pose' { $data.frames[0].source_frame_id = 'window-0112-forward-00002' }
        'mode' { $data.frames[1].native_control_observation_after.active_viewmode_readback = 'VMI_LIT' }
        'file' { $data.frames[0].file = 'road-asphalt-lit-review/frames/reused.png' }
        'count' { $data.frames = $data.frames[0..6] }
        'plan' { $data.control_plan.jobs[0].camera.station_m += 1 }
        'plan_hash' { $data.control_plan_sha256 = 'e' * 64 }
        'lit_receipt' { $data.lit_review_receipt.sha256 = 'e' * 64 }
        'manifest' { $data.saved_manifest_sha256 = 'e' * 64 }
        'prime_count' { $data.completed_priming_frames = 23 }
        'prime_name' { $data.frames[0].priming_frames[1].file = $data.frames[0].priming_frames[0].file }
        'prime_mode' { $data.frames[2].priming_frames[1].native_control_observation_before.active_viewmode_readback = 'VMI_LIT' }
        'prime_camera' { $data.frames[0].priming_frames[2].native_camera_observation.fov_deg += 1 }
        'material' { $data.frames[3].native_control_observation_after.road_material_readback = $fixture.original }
        'buffer' { $data.frames[1].native_control_observation_before.requested_buffer = 'WorldNormal' }
        'buffer_claim' { $data.frames[1].native_control_observation_after.buffer_name_readback_verified = $true }
        'mips' { $data.frames[0].capture_readiness.material_texture_count = 6 }
        'restoration' { $data.restore.status = 'FAILED' }
        'view_restore' { $data.restore.owned_viewports_returned_to_lit = $false }
        'saved_bytes' { $data.restore.saved_and_staged_package_bytes_unchanged = $false }
        'owner' { $data.whole_area_visual_admitted = $true }
        'performance' { $data.performance_pass = $true }
        'deadline' { $data.total_deadline_seconds_shared_with_lit = 2160 }
        'token' { $data.begin.ownership.run_token = '456-1' }
        'transient' { $data.begin.transient_material = '/Game/Materials/Changed.Changed' }
        'preflight' { $data.preflight.native_api.engine_version = 'different build' }
        'uniform' { $data.begin.uniform_material.roughness = 0.2 }
        'normals' { $data.begin.geometry_vertex_normals_preserved = $false }
        'api_claim' { $data.begin.buffer_name_getter_available = $true }
        'station' { $data.frames[0].station_m += 1 }
        'render_mode' { $data.frames[1].render_mode = 'lit' }
        'visual_claim' { $data.frames[0].visual_quality_reviewed = $true }
        'prime_viewmode' { $data.frames[2].priming_frames[1].native_viewmode_after = 'VMI_LIT' }
        'prime_snapshot' { $data.frames[7].priming_frames[2].Remove('native_capture_state_after') | Out-Null }
    }
    $rejected = $false
    try { Check $data } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production visual control gate admitted ' + $failure) }
}
'POWERSHELL_VISUAL_CONTROL_CASES_PASS'
''', encoding="utf-8")
            result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(HOST), str(fixture)],
                capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("POWERSHELL_VISUAL_CONTROL_CASES_PASS", result.stdout)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_real_powershell_parser_accepts_native_gpu_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "check.ps1"
            path.write_text(
                """param([string] $Script)
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $Script, [ref] $tokens, [ref] $errors
) | Out-Null
if ($errors.Count) { throw ($errors.Message -join "; ") }
""",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(path), str(HOST)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

    def _crack_host_fixture(self, directory, *, outer_terrain=False):
        """Real provider reports over disposable fake UE; never native image evidence."""
        from scripts.ue import road_crack_visual_controls as controls
        from scripts.ue.test_road_crack_visual_controls import CrackControlTests

        native = CrackControlTests()
        native.setUp()
        self.addCleanup(native.doCleanups)
        manifest = native.context["manifest"]
        manifest["edge_markings_enabled"] = True
        # The saved native inventory uses the UE object-path colon. Keep the
        # disposable objects and their pinned rows identical to that convention.
        actors = native.api.get_editor_subsystem(native.api.EditorActorSubsystem).get_all_level_actors()
        for row in manifest["crack_canary"]["actors"]:
            actor = next(actor for actor in actors if actor.get_actor_label() == row["label"])
            component = actor.get_dynamic_mesh_component()
            for obj in (actor, component, component.mesh):
                obj.path = obj.path.replace(".PersistentLevel.", ":PersistentLevel.")
            row["actor"]["path"] = row["actor"]["path"].replace(".PersistentLevel.", ":PersistentLevel.")
            row["component"] = row["component"].replace(".PersistentLevel.", ":PersistentLevel.")
            row["mesh"] = row["mesh"].replace(".PersistentLevel.", ":PersistentLevel.")
        channels = ("BaseColor", "Normal_DX", "ORM", "DetailMasks")
        manifest["texture_objects"] = {channel: f"/Game/Fixture/Base_{channel}.Base_{channel}" for channel in channels}
        manifest["shoulder_network"] = {"material": {"texture_objects": {
            channel: f"/Game/Fixture/Shoulder_{channel}.Shoulder_{channel}" for channel in ("BaseColor", "Normal_DX", "Roughness")}}}
        manifest["crack_canary"]["imports"].update(texture_count=8, assets=controls.sources.asset_paths(native.source))
        if outer_terrain:
            from scripts.ue.test_road_asphalt_gpu_review import outer_terrain_fixture
            outer = outer_terrain_fixture()[3]
            outer["shoulder_network"]["material"]["texture_objects"] = manifest["shoulder_network"]["material"]["texture_objects"]
            manifest.update(outer)
        paths = {**manifest["texture_objects"], **{
            "Shoulder_" + channel: path for channel, path in manifest["shoulder_network"]["material"]["texture_objects"].items()}, **{
            "Crack_" + motif + "_" + channel: path
            for motif, channels in manifest["crack_canary"]["imports"]["assets"]["textures"].items()
            for channel, path in channels.items()}}
        if outer_terrain:
            paths.update({"OuterTerrain_" + name: path for name, path in
                manifest["shoulder_network"]["outer_terrain"]["material"]["terrain_source"]["texture_objects"].items()})
        material_ready = {"schema_version": 1, "status": "ROAD_TEXTURE_MIPS_READY", "lease_seconds": 1200,
            "material_parameters_changed": False, "saved_to_map": False,
            "textures": [{"channel": channel, "asset": path, "native_readback": {
                "is_default_texture": False, "is_compiling": False, "mips": 12, "resident_mips": 12}}
                for channel, path in sorted(paths.items())]}
        proof = directory / "proof"

        def write(relative, raw):
            path = proof / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}

        plan = controls.control_plan()
        preflight = controls.preflight(native.api, native.context, plan)
        controller = native.controller()
        begin = controller.begin()
        frames = []
        for job in plan["jobs"]:
            controller.apply(job["job_id"])
            pose = job["camera"]
            delta = [target - eye for target, eye in zip(pose["target_cm"], pose["camera_location_cm"], strict=True)]
            length = math.sqrt(sum(value * value for value in delta))
            camera = {"rotation_setter_accepted": True, "location_cm": list(pose["camera_location_cm"]),
                "forward_unit": [value / length for value in delta], "fov_deg": pose["fov_deg"], "forward_error": 0.0}

            def capture(relative):
                # Deliberately labelled byte fixtures: the host authenticates
                # retained bytes; the separate UE decoder owns PNG validity.
                identity = write(relative, b"synthetic host byte fixture, not a native PNG: " + relative.encode())
                return {"file": relative, **identity, "screenshot_elapsed_seconds": 1.0,
                    "native_viewmode_before": "VMI_VISUALIZE_BUFFER" if job["control"] in controls.BUFFERS else "VMI_LIT",
                    "native_viewmode_after": "VMI_VISUALIZE_BUFFER" if job["control"] in controls.BUFFERS else "VMI_LIT",
                    "native_camera_observation": deepcopy(camera),
                    "native_control_observation_before": controller.observe(),
                    "native_control_observation_after": controller.observe()}

            priming = [capture(f"road-crack-visual-controls/priming/{job['job_id']}-{index:02d}.png") for index in range(3)]
            final = capture("road-crack-visual-controls/frames/" + job["job_id"] + ".png")
            readiness = "road-crack-visual-controls/readiness/" + job["job_id"] + "/"
            height = write(readiness + "capture-readiness.json", b'{"synthetic_height_fixture":true}')
            texture = write(readiness + "road-texture-readiness.json", json.dumps(material_ready, allow_nan=False).encode())
            frames.append({**deepcopy(pose), **final, "frame_id": job["job_id"], "source_frame_id": pose["frame_id"],
                "control_mode": job["control"], "width": 1280, "height": 720, "unique_sampled_rgb": 100,
                "visual_quality_reviewed": False,
                "render_mode": "buffer_visualization" if job["control"] in controls.BUFFERS else "lit",
                "priming_frames": priming, "capture_readiness": {"status": "NATIVE_LOADING_AND_MIPS_READY",
                    "height_receipt": height, "material_receipt": texture, "height_mip_lease_requested": True,
                    "viewport_primed_at_rider_camera": True, "material_texture_count": len(paths)}})
        restored = controller.restore()
        good = {"schema_version": 1, "issue": 364, "status": "ROAD_CRACK_VISUAL_CONTROLS_FRAMES_RETAINED",
            "exact_sha": native.context["exact_sha"], "run_token": native.context["run_token"], "map_package": controls.saved.MAP,
            "saved_manifest_sha256": "b" * 64, "view_plan_sha256": "c" * 64, "camera_csv_sha256": plan["survey_sha256"],
            "lit_review_receipt": {"file": "road-asphalt-lit-review.json", "sha256": "d" * 64, "size_bytes": 100},
            "control_plan": plan, "control_plan_sha256": controls.digest(plan),
            "frame_count": 16, "expected_frame_count": 16, "frames": frames,
            "priming_frames_per_pose": 3, "completed_priming_frames": 48, "max_completed_screenshot_seconds": 1.0,
            "total_deadline_seconds_shared_with_lit": 1080, "frame_deadline_seconds": 180,
            "owner_visual_status": "PENDING_FINAL_M3", "performance_status": "DEFERRED_AFTER_M3", "errors": [],
            "preflight": preflight, "begin": begin, "restore": restored,
            **{key: True for key in ("control_restoration_verified", "capture_readiness_verified",
                "native_control_observations_verified", "sources_and_saved_assets_unchanged", "world_normal_canary_required")},
            **{key: False for key in ("native_channel_images_reviewed", "buffer_name_readback_verified",
                "geometry_or_source_texture_change", "map_saved", "source_assets_saved", "whole_area_visual_admitted",
                "performance_pass", "normal_space_verified")}}
        add_capture_state_fixture(good)
        return {"good": good, "expected": {"control_plan": plan, "sha256": controls.digest(plan)},
            "network": native.context["view_plan"], "manifest": manifest,
            "lit": {"sha256": "d" * 64, "size_bytes": 100}, "pid": begin["ownership"]["pid"],
            "project": str(native.root), "engine": str(native.engine), "proof": str(proof), "ready": material_ready}

    def _paint_host_fixture(self, *, outer_terrain=False):
        """Real controller/receipt over 370 fake objects, with no native image claim."""
        from scripts.ue import road_asphalt_gpu_review as gpu
        from scripts.ue import road_asphalt_visual_controls as controls
        from scripts.ue.test_road_asphalt_visual_controls import PaintCoverageTests
        import struct

        native = PaintCoverageTests()
        native.setUp()
        self.addCleanup(native.doCleanups)
        # Effective UE scalars are float32; exact decimal equality is invalid.
        native.paint_mic.scalars = {name: struct.unpack('f', struct.pack('f', value))[0]
                                   for name, value in native.paint_mic.scalars.items()}
        native.context["manifest"]["crack_canary_enabled"] = True
        native.context["manifest"]["outer_terrain_enabled"] = outer_terrain
        plan = controls.control_plan(paint_coverage=True)
        preflight = controls.preflight(native.api, native.context, plan)
        controller = controls.VisualControls(native.api, native.context)
        begin = controller.begin()
        self.assertTrue(all(component.assignments == [] for component in native.paint_components))
        frames = []
        for job in plan["jobs"]:
            controller.apply(job["job_id"])
            pose, mode = job["camera"], job["control"]
            delta = [target - eye for target, eye in zip(pose["target_cm"], pose["camera_location_cm"], strict=True)]
            length = math.sqrt(sum(value * value for value in delta))
            camera = {"rotation_setter_accepted": True, "location_cm": list(pose["camera_location_cm"]),
                "forward_unit": [value / length for value in delta], "fov_deg": pose["fov_deg"], "forward_error": 0.0}
            viewmode = "VMI_VISUALIZE_BUFFER" if mode in controls.BUFFERS else "VMI_LIT"
            def capture(relative):
                return {"file": relative, "sha256": "e" * 64, "size_bytes": 100, "screenshot_elapsed_seconds": 1.0,
                    "native_viewmode_before": viewmode, "native_viewmode_after": viewmode,
                    "native_camera_observation": deepcopy(camera),
                    "native_control_observation_before": controller.observe(),
                    "native_control_observation_after": controller.observe()}
            frame = {**deepcopy(pose), **capture(f"road-asphalt-visual-controls/frames/{job['job_id']}.png"),
                "frame_id": job["job_id"], "source_frame_id": pose["frame_id"], "control_mode": mode,
                "width": 1280, "height": 720, "unique_sampled_rgb": 100, "visual_quality_reviewed": False,
                "render_mode": "buffer_visualization" if mode in controls.BUFFERS else "lit",
                "priming_frames": [capture(f"road-asphalt-visual-controls/priming/{job['job_id']}-{index:02d}.png")
                                   for index in range(3)],
                "capture_readiness": {"status": "NATIVE_LOADING_AND_MIPS_READY", "height_mip_lease_requested": True,
                    "viewport_primed_at_rider_camera": True, "material_texture_count": 26 if outer_terrain else 15,
                    "height_receipt": {"sha256": "e" * 64, "size_bytes": 100},
                    "material_receipt": {"sha256": "e" * 64, "size_bytes": 100}}}
            frames.append(frame)
        job = gpu.RoadLitCapture.__new__(gpu.RoadLitCapture)
        job.control_plan, job.control_module, job.control_family = plan, controls, "road-asphalt"
        job.paint_coverage_enabled = True
        job.control_preflight, job.control_begin, job.control_restore = preflight, begin, controller.restore()
        job.control_frames, job.control_completed_priming_frames = frames, 30
        job.control_max_completed_screenshot_seconds = 1.0
        job.capture_state_api = None
        job.edge_marking_readback = {"all_marking_buffers_verified": True, "full_source_buffers_preserved": True, "actor_count": 370}
        job.context = {**native.context, "manifest_id": {"sha256": "b" * 64},
                       "view_plan_identity": {"sha256": "c" * 64}, "edge_marking_readback": job.edge_marking_readback}
        good = job.visual_control_receipt([], {"sha256": "d" * 64, "size_bytes": 100})
        add_capture_state_fixture(good)
        legacy = controls.control_plan()
        return {"good": good, "expected": {"control_plan": plan, "sha256": controls.digest(plan),
                "legacy_control_plan": legacy, "legacy_control_plan_sha256": controls.digest(legacy)},
            "manifest": native.context["manifest"], "original": native.context["manifest"]["material_instance"],
            "lit": {"sha256": "d" * 64, "size_bytes": 100}}

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_paint_pair_gate_keeps_full_bindings_native_scalars_and_two_mib_limit(self):
        fixture = self._paint_host_fixture()
        raw = (json.dumps(fixture["good"], sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        self.assertLess(len(raw), 2 * 1024 * 1024)
        self.assertEqual(len(fixture["good"]["begin"]["paint_binding_templates"]["original_mic"]["bindings"]), 370)
        self.assertNotIn("paint_binding_templates", fixture["good"]["restore"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            retained = root / "paint-controls.json"
            retained.write_bytes(raw)
            fixture["receipt_path"] = str(retained)
            path = root / "input.json"
            path.write_text(json.dumps(fixture, allow_nan=False), encoding="utf-8")
            runner = root / "paint.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
foreach ($name in @('Assert-PlainPath', 'File-Identity', 'Assert-Identity', 'Read-PinnedJson', 'Assert-JsonEqual',
    'Assert-NativeCameraObservation', 'Assert-CaptureStateApi', 'Assert-CaptureStatePair',
    'Assert-VisualControlObservation', 'Assert-PaintScalars', 'Assert-PaintObservation',
    'Assert-PaintCoverageContract', 'Assert-VisualControlContract')) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw ('Missing unique paint validation: ' + $name) }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$fixture = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
function Check($data, [int] $textures = 15) {
    Assert-VisualControlContract $data $fixture.expected ('c' * 64) ('b' * 64) $fixture.lit $fixture.original `
        $fixture.good.exact_sha $fixture.good.run_token $true $textures $fixture.manifest
}
$retained = Read-PinnedJson $fixture.receipt_path
Assert-JsonEqual $fixture.good $retained.value 'complete paint control receipt within unchanged 2 MiB bound'
Check $retained.value
$withOuter = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
foreach ($frame in $withOuter.frames) { $frame.capture_readiness.material_texture_count = 26 }
Check $withOuter 26
foreach ($failure in @('missing_template', 'last_original_target', 'last_mid_target', 'template_hash', 'duplicate_template',
    'before_hash', 'prime_hash', 'count', 'matches', 'restore_hash', 'mid_parent', 'mid_flags',
    'mic_scalar', 'full_scalar', 'width', 'setter_material', 'fourth_setter', 'assignment', 'last_restore',
    'detach', 'refs', 'dirty', 'buffers', 'pixel_claim', 'legacy_hash', 'legacy_camera', 'pair_camera', 'mips',
    'snapshot_missing', 'snapshot_zero', 'snapshot_history', 'snapshot_api', 'snapshot_regression')) {
    $data = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'missing_template' { $data.begin.paint_binding_templates.Remove('original_mic') | Out-Null }
        'last_original_target' { $data.begin.paint_binding_templates.original_mic.bindings[-1].component += '_foreign' }
        'last_mid_target' { $data.begin.paint_binding_templates.transient_mid.bindings[-1].label = 'YACS_FOREIGN' }
        'template_hash' { $data.begin.paint_binding_templates.original_mic.bindings_sha256 = 'f' * 64 }
        'duplicate_template' { $data.restore.paint_binding_templates = $data.begin.paint_binding_templates }
        'before_hash' { $data.frames[8].native_control_observation_before.paint_coverage.bindings_sha256 = 'f' * 64 }
        'prime_hash' { $data.frames[9].priming_frames[2].native_control_observation_after.paint_coverage.bindings_sha256 = 'f' * 64 }
        'count' { $data.frames[9].native_control_observation_after.paint_coverage.binding_count = 369 }
        'matches' { $data.frames[9].native_control_observation_after.paint_coverage.bindings_match_template = $false }
        'restore_hash' { $data.restore.paint_restored_observation.bindings_sha256 = 'f' * 64 }
        'mid_parent' { $data.begin.paint_transient_mid.parent = '/Game/Foreign.Foreign' }
        'mid_flags' { $data.begin.paint_transient_mid.creation_flags = 'NONE' }
        'mic_scalar' { $data.frames[9].native_control_observation_after.paint_coverage.original_mic_scalar_parameters.EdgeWearMinCm = -0.05 }
        'full_scalar' { $data.frames[9].native_control_observation_before.paint_coverage.scalar_parameters.EdgeWearSpanCm = 0.72 }
        'width' { $data.begin.paint_original_scalar_parameters.LineWidthCm = 11.0 }
        'setter_material' { @($data.restore.calls | Where-Object { $_.function -ceq 'MaterialInstanceDynamic.set_scalar_parameter_value' })[0].material = $data.begin.paint_original_material }
        'fourth_setter' { $data.restore.calls += @($data.restore.calls | Where-Object { $_.function -ceq 'MaterialInstanceDynamic.set_scalar_parameter_value' })[0] }
        'assignment' { @($data.restore.calls | Where-Object { $_.function -ceq 'paint_component.set_material' })[0].material = $data.begin.paint_original_material }
        'last_restore' { @($data.restore.calls | Where-Object { $_.function -ceq 'paint_component.set_material' })[-1].material = $data.begin.paint_transient_mid.path }
        'detach' { $data.restore.paint_transient_mid_detached = $false }
        'refs' { $data.restore.paint_transient_mid_ref_released = $false }
        'dirty' { $data.restore.dirty_content_count = 1 }
        'buffers' { $data.paint_full_native_buffers_verified = $false }
        'pixel_claim' { $data.paint_pixel_aliasing_cause_verified = $true }
        'legacy_hash' { $data.legacy_control_plan_sha256 = 'f' * 64 }
        'legacy_camera' { $data.legacy_control_plan.jobs[0].camera.station_m += 1 }
        'pair_camera' { $data.control_plan.jobs[9].camera.station_m += 1 }
        'mips' { $data.frames[9].capture_readiness.material_texture_count = 7 }
        'snapshot_missing' { $data.frames[9].priming_frames[2].Remove('native_capture_state_after') | Out-Null }
        'snapshot_zero' { $data.frames[9].native_capture_state_after.cvars['r.TSR.ThinGeometryDetection'].value = 0 }
        'snapshot_history' { $data.frames[9].native_capture_state_before.temporal_history_observed = $true }
        'snapshot_api' { $data.capture_state_native_api.engine_version = 'different' }
        'snapshot_regression' { $data.frames[9].native_capture_state_after.frame_count = 0 }
    }
    $rejected = $false
    try { Check $data } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production paint gate admitted ' + $failure) }
}
'POWERSHELL_PAINT_PAIR_CASES_PASS'
''', encoding="utf-8")
            result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(HOST), str(path)],
                                    capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("POWERSHELL_PAINT_PAIR_CASES_PASS", result.stdout)

    def _run_crack_host_cases(self, directory, fixture, cases):
        fixture_path = directory / "input.json"
        fixture_path.write_text(json.dumps(fixture, allow_nan=False), encoding="utf-8")
        runner = directory / "crack-contracts.ps1"
        runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
foreach ($name in @('Assert-PlainPath', 'File-Identity', 'Assert-Identity', 'Read-PinnedJson', 'Assert-JsonEqual',
                    'Assert-CaptureStateApi', 'Assert-CaptureStatePair',
                    'Assert-NativeCameraObservation', 'Assert-SurfaceDetailLanes', 'Assert-SurfaceDetailGpuReadback',
                    'Assert-CrackControlPlan', 'Get-CrackControlTargets', 'Assert-CrackVisualControlObservation',
                    'Assert-CrackControlApi', 'Assert-CrackVisualControlContract', 'Assert-MaterialTextureReadiness',
                    'Get-CrackVisualControlArtifacts', 'Assert-OuterNativeStatistics', 'Get-OuterTerrainTextureBindings',
                    'Get-OuterTerrainBindingSummary', 'Assert-OuterTerrainLanes', 'Assert-OuterTerrainGpuReadback',
                    'Log-Identity', 'Get-OuterTerrainShaderLogObservation', 'Assert-OuterTerrainShaderLog')) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw ('Missing unique production crack function: ' + $name) }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$fixture = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
function Check($data) {
    Assert-CrackVisualControlContract $data $fixture.expected ('c' * 64) ('b' * 64) $fixture.lit `
        $fixture.manifest $fixture.pid $fixture.project $fixture.good.exact_sha $fixture.good.run_token $fixture.network `
        $fixture.ready.textures.Count
}
function FreshData { return ($fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40) }
function Reject($action, $label) {
    $rejected = $false
    try { & $action | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production crack gate admitted ' + $label) }
}
Check $fixture.good
''' + cases + "\n'POWERSHELL_CRACK_CASES_PASS'\n", encoding="utf-8")
        result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(HOST), str(fixture_path)],
            capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("POWERSHELL_CRACK_CASES_PASS", result.stdout)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_crack_gate_checks_both_native_actors_and_all_sixteen_conditions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._crack_host_fixture(root)
            self._run_crack_host_cases(root, fixture, r'''
foreach ($failure in @('order', 'count', 'source_pose', 'camera', 'station', 'plan', 'hash', 'network',
    'mode', 'render_mode', 'prime_count', 'prime_name', 'prime_mode', 'prime_camera', 'final_file', 'png_hash',
    'png_size', 'elapsed', 'elapsed_type', 'max_elapsed', 'deadline', 'mip_count', 'viewport_priming',
    'missing_actor', 'actor_order', 'actor_path', 'component', 'visibility', 'probe', 'mic_probe', 'material_kind',
    'mid_parent', 'uv_rotation', 'dirty_observation', 'buffer_claim', 'buffer_argument', 'ownership_pid',
    'project', 'token', 'head', 'restore', 'restore_visibility', 'detach', 'refs', 'saved_bytes', 'mic_zero',
    'cleanup', 'dirty_begin', 'dirty_restore', 'duplicate_mid', 'mid_flags', 'begin_calls', 'restore_calls',
    'mic_setter', 'native_api_flags', 'native_api_hash', 'native_api_header', 'normal_claim', 'owner_claim',
    'performance', 'visual_review', 'source_save', 'geometry_change', 'preflight', 'restore_api', 'lit_receipt', 'prime_viewmode', 'prime_snapshot')) {
    $data = FreshData
    switch ($failure) {
        'order' { $swap = $data.frames[0]; $data.frames[0] = $data.frames[1]; $data.frames[1] = $swap }
        'count' { $data.frames = $data.frames[0..14] }
        'source_pose' { $data.frames[0].source_frame_id = 'window-0082-forward-00002' }
        'camera' { $data.frames[0].native_camera_observation.location_cm[2] += 1 }
        'station' { $data.frames[0].station_m += 1 }
        'plan' { $data.control_plan.jobs[0].camera.station_m += 1 }
        'hash' { $data.control_plan_sha256 = 'e' * 64 }
        'network' { $data.view_plan_sha256 = 'e' * 64 }
        'mode' { $data.frames[1].native_control_observation_after.active_viewmode_readback = 'VMI_LIT' }
        'render_mode' { $data.frames[1].render_mode = 'lit' }
        'prime_count' { $data.completed_priming_frames = 47 }
        'prime_name' { $data.frames[15].priming_frames[2].file = $data.frames[15].priming_frames[1].file }
        'prime_mode' { $data.frames[1].priming_frames[2].native_control_observation_after.requested_buffer = 'WorldNormal' }
        'prime_camera' { $data.frames[15].priming_frames[2].native_camera_observation.fov_deg += 1 }
        'final_file' { $data.frames[0].file = 'road-asphalt-lit-review/frames/reused.png' }
        'png_hash' { $data.frames[0].sha256 = 'not-a-hash' }
        'png_size' { $data.frames[15].priming_frames[2].size_bytes = 0 }
        'elapsed' { $data.frames[15].priming_frames[2].screenshot_elapsed_seconds = 181 }
        'elapsed_type' { $data.frames[0].screenshot_elapsed_seconds = '1' }
        'max_elapsed' { $data.max_completed_screenshot_seconds = 0.0 }
        'deadline' { $data.total_deadline_seconds_shared_with_lit = 2160 }
        'mip_count' { $data.frames[0].capture_readiness.material_texture_count = 7 }
        'viewport_priming' { $data.frames[0].capture_readiness.viewport_primed_at_rider_camera = $false }
        'missing_actor' { $data.frames[1].native_control_observation_before.crack_actors = @($data.frames[1].native_control_observation_before.crack_actors[0]) }
        'actor_order' { [Array]::Reverse($data.frames[1].native_control_observation_before.crack_actors) }
        'actor_path' { $data.frames[1].native_control_observation_before.crack_actors[1].actor += '_foreign' }
        'component' { $data.frames[1].native_control_observation_before.crack_actors[1].component += '_foreign' }
        'visibility' { $data.frames[1].native_control_observation_before.crack_actors[1].visible_readback = $false }
        'probe' { $data.frames[1].native_control_observation_before.crack_actors[1].neutral_probe_readback = 0.0 }
        'mic_probe' { $data.frames[1].native_control_observation_before.crack_actors[1].original_mic_probe_readback = 1.0 }
        'material_kind' { $data.frames[1].native_control_observation_before.crack_actors[1].material_kind = 'original_mic' }
        'mid_parent' { $data.frames[1].native_control_observation_before.crack_actors[1].transient_mid_parent_readback += '_foreign' }
        'uv_rotation' { $data.frames[1].native_control_observation_before.crack_actors[1].uv_rotation_degrees = 0.0 }
        'dirty_observation' { $data.frames[0].priming_frames[0].native_control_observation_after.dirty_content_count = 1 }
        'buffer_claim' { $data.frames[1].native_control_observation_before.buffer_name_readback_verified = $true }
        'buffer_argument' { $data.frames[2].native_control_observation_after.requested_buffer = 'BaseColor' }
        'ownership_pid' { $data.begin.ownership.pid += 1 }
        'project' { $data.begin.ownership.project += '/foreign' }
        'token' { $data.begin.ownership.run_token = '456-1' }
        'head' { $data.exact_sha = 'e' * 40 }
        'restore' { $data.restore.status = 'FAILED' }
        'restore_visibility' { $data.restore.original_visibility_restored = $false }
        'detach' { $data.restore.transient_mids_detached = $false }
        'refs' { $data.restore.transient_mid_refs_released = $false }
        'saved_bytes' { $data.restore.saved_and_staged_package_bytes_unchanged = $false }
        'mic_zero' { $data.restore.original_mic_probe_values_zero = $false }
        'cleanup' { $data.restore.cleanup_errors += 'unrestored component' }
        'dirty_begin' { $data.begin.dirty_content_count = 1 }
        'dirty_restore' { $data.restore.dirty_content_count = 1 }
        'duplicate_mid' { $data.begin.transient_mids.short_oblique.path = $data.begin.transient_mids.drifting_interrupted.path }
        'mid_flags' { $data.begin.transient_mids.short_oblique.creation_flags = 'NONE' }
        'begin_calls' { $data.begin.calls[2].value = 0.0 }
        'restore_calls' { $data.restore.calls[-1].argument = 'VMI_UNLIT' }
        'mic_setter' { $data.restore.calls[2].material = $data.begin.original_materials.drifting_interrupted }
        'native_api_flags' { foreach ($part in @('preflight', 'begin', 'restore')) { $data[$part].native_api.rf_transient_set_by_installed_allocator = $false } }
        'native_api_hash' { foreach ($part in @('preflight', 'begin', 'restore')) { $data[$part].native_api.mid_scalar_getter_body_sha256 = 'invalid' } }
        'native_api_header' { foreach ($part in @('preflight', 'begin', 'restore')) {
            $keys = @($data[$part].native_api.crack_sources.Keys)
            $key = @($keys | Where-Object { $_ -like '*/MaterialInstanceDynamic.h' })[0]
            $value = $data[$part].native_api.crack_sources[$key]
            $data[$part].native_api.crack_sources.Remove($key)
            $data[$part].native_api.crack_sources['../foreign.h'] = $value
        } }
        'normal_claim' { $data.normal_space_verified = $true }
        'owner_claim' { $data.whole_area_visual_admitted = $true }
        'performance' { $data.performance_pass = $true }
        'visual_review' { $data.frames[0].visual_quality_reviewed = $true }
        'source_save' { $data.restore.source_assets_saved = $true }
        'geometry_change' { $data.restore.geometry_buffers_modified = $true }
        'preflight' { $data.preflight.ownership.pid += 1 }
        'restore_api' { $data.restore.native_api.engine_version = 'different' }
        'lit_receipt' { $data.lit_review_receipt.sha256 = 'e' * 64 }
        'prime_viewmode' { $data.frames[15].priming_frames[2].native_viewmode_before = 'VMI_LIT' }
        'prime_snapshot' { $data.frames[15].priming_frames[2].Remove('native_capture_state_after') | Out-Null }
    }
    Reject { Check $data } $failure
}
''')

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_crack_byte_and_residency_gate_rechecks_all_images_sources_and_maps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._crack_host_fixture(root)
            self._run_crack_host_cases(root, fixture, r'''
function Files($data) {
    return Get-CrackVisualControlArtifacts $data $fixture.proof $fixture.manifest $fixture.engine $fixture.project
}
$all = Files $fixture.good
if ($all.Count -ne 104) { throw 'Expected 64 PNG identities, 32 readiness sidecars and eight API/config sources.' }
foreach ($kind in @('final', 'last_prime', 'height', 'mid_cpp', 'allocator')) {
    $path = switch ($kind) {
        'final' { Join-Path $fixture.proof $fixture.good.frames[0].file }
        'last_prime' { Join-Path $fixture.proof $fixture.good.frames[15].priming_frames[2].file }
        'height' { Join-Path $fixture.proof ('road-crack-visual-controls/readiness/' + $fixture.good.frames[0].frame_id + '/capture-readiness.json') }
        'mid_cpp' { Join-Path $fixture.engine 'Source/Runtime/Engine/Private/Materials/MaterialInstanceDynamic.cpp' }
        'allocator' { Join-Path $fixture.project 'Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsComponent230Detail.cpp' }
    }
    $bytes = [IO.File]::ReadAllBytes($path)
    try {
        [IO.File]::WriteAllBytes($path, @($bytes) + @(1))
        Reject { Files $fixture.good } ('changed bytes: ' + $kind)
        [IO.File]::Delete($path)
        Reject { Files $fixture.good } ('missing file: ' + $kind)
    }
    finally { [IO.File]::WriteAllBytes($path, $bytes) }
}
$materialPath = Join-Path $fixture.proof ('road-crack-visual-controls/readiness/' + $fixture.good.frames[0].frame_id + '/road-texture-readiness.json')
$originalBytes = [IO.File]::ReadAllBytes($materialPath)
foreach ($failure in @('replacement', 'duplicate', 'reorder', 'seven_only', 'mips', 'compiling', 'default', 'save', 'parameters')) {
    $data = FreshData
    $ready = $fixture.ready | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'replacement' { $ready.textures[1].asset = '/Game/Unrelated.Asset' }
        'duplicate' { $ready.textures[1].asset = $ready.textures[2].asset }
        'reorder' { $swap = $ready.textures[1]; $ready.textures[1] = $ready.textures[2]; $ready.textures[2] = $swap }
        'seven_only' { $ready.textures = $ready.textures[0..6] }
        'mips' { $ready.textures[1].native_readback.resident_mips = 11 }
        'compiling' { $ready.textures[1].native_readback.is_compiling = $true }
        'default' { $ready.textures[1].native_readback.is_default_texture = $true }
        'save' { $ready.saved_to_map = $true }
        'parameters' { $ready.material_parameters_changed = $true }
    }
    try {
        [IO.File]::WriteAllText($materialPath, ($ready | ConvertTo-Json -Depth 40))
        $pin = File-Identity $materialPath 2MB
        $data.frames[0].capture_readiness.material_receipt.sha256 = $pin.sha256
        $data.frames[0].capture_readiness.material_receipt.size_bytes = $pin.size_bytes
        Reject { Files $data } ('repinned incorrect texture readback: ' + $failure)
    }
    finally { [IO.File]::WriteAllBytes($materialPath, $originalBytes) }
}
Files $fixture.good | Out-Null
''')

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_outer_lanes_keep_nullrhi_distinct_and_verify_all_twenty_six_textures(self):
        from scripts.ue.test_road_asphalt_gpu_review import outer_terrain_fixture, outer_gpu_statistics_fixture

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._crack_host_fixture(root, outer_terrain=True)
            host, prepared, fresh, manifest = outer_terrain_fixture()
            manifest["shoulder_network"]["outer_terrain"]["material"].update(
                status="SHOULDER_MATERIAL_CREATED_REVIEW_PENDING", native_compile_errors=[], unique_texture_objects=17)
            stats = outer_gpu_statistics_fixture(manifest)
            before, after = deepcopy(fresh["outer_terrain_readback"]), deepcopy(fresh["outer_terrain_readback"])
            before["outer_native_statistics"] = deepcopy(stats["native_statistics"])
            after["outer_native_statistics"] = deepcopy(stats["native_statistics"])
            fixture["outer_lanes"] = {"host_row": host, "prepared": prepared, "fresh": fresh, "manifest": manifest,
                "gpu": {"outer_terrain_enabled": True, "outer_terrain_native_bindings_verified": True,
                    "outer_terrain_gpu_statistics_verified": True, "outer_terrain_physical_contact_verified": False,
                    "outer_terrain_normal_response_verified": False, "outer_terrain_before": before, "outer_terrain_after": after,
                    "outer_gpu_statistics_before": stats, "outer_gpu_statistics_after": deepcopy(stats)}}
            disabled = outer_terrain_fixture(enabled=False)
            fixture["outer_disabled"] = dict(zip(("host_row", "prepared", "fresh", "manifest"), disabled, strict=True))
            self._run_crack_host_cases(root, fixture, r'''
function Outer($rows) {
    Assert-OuterTerrainLanes $rows.host_row $rows.prepared $rows.fresh $rows.manifest $true
    Assert-OuterTerrainGpuReadback $rows.gpu $rows.fresh $rows.manifest $true
}
Outer $fixture.outer_lanes
$disabled = $fixture.outer_disabled
Assert-OuterTerrainLanes $disabled.host_row $disabled.prepared $disabled.fresh $disabled.manifest $false
$offGpu = @{ outer_terrain_enabled = $false; outer_terrain_native_bindings_verified = $false
    outer_terrain_gpu_statistics_verified = $false; outer_terrain_physical_contact_verified = $false
    outer_terrain_normal_response_verified = $false; outer_terrain_before = $null; outer_terrain_after = $null
    outer_gpu_statistics_before = $null; outer_gpu_statistics_after = $null }
Assert-OuterTerrainGpuReadback $offGpu $disabled.fresh $disabled.manifest $false
$offGpu.outer_gpu_statistics_before = $fixture.outer_lanes.gpu.outer_gpu_statistics_before
Reject { Assert-OuterTerrainGpuReadback $offGpu $disabled.fresh $disabled.manifest $false } 'disabled outer GPU payload'
if ($fixture.outer_lanes.fresh.outer_terrain_readback.outer_native_statistics.num_samplers -ne 0 -or
    $fixture.outer_lanes.gpu.outer_gpu_statistics_before.native_statistics.num_samplers -le 0) {
    throw 'Fixture must distinguish NullRHI zero from the later positive GPU observation.'
}
foreach ($failure in @('host_mode', 'prepared_mode', 'fresh_mode', 'fresh_reapply', 'saved_gpu_claim', 'saved_errors',
                      'fresh_gpu_claim', 'source_channels', 'source_binding', 'owner_nudo', 'owner_parapet', 'uv0',
                      'shader_scope', 'before_binding', 'after_binding', 'zero_gpu', 'negative_gpu', 'boolean_gpu',
                      'changed_gpu', 'extra_gpu_field', 'normal_claim', 'contact_claim', 'host_log_omitted')) {
    $rows = $fixture.outer_lanes | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'host_mode' { $rows.host_row.outer_terrain_requested = $false }
        'prepared_mode' { $rows.prepared.outer_terrain_enabled = 1 }
        'fresh_mode' { $rows.fresh.outer_terrain_enabled = $false }
        'fresh_reapply' { $rows.fresh.outer_material_reapplied = $true }
        'saved_gpu_claim' { $rows.manifest.shoulder_network.outer_terrain.material.gpu_compile_verified = $true }
        'saved_errors' { $rows.manifest.shoulder_network.outer_terrain.material.native_compile_errors = @('synthetic') }
        'fresh_gpu_claim' { $rows.fresh.outer_terrain_readback.outer_gpu_compile_verified = $true }
        'source_channels' { $rows.manifest.shoulder_network.outer_terrain.material.terrain_source.texture_objects.Remove('ScreeNormalTex') }
        'source_binding' { $rows.manifest.shoulder_network.outer_terrain.material.terrain_source.texture_objects.ScreeNormalTex = '/Game/Foreign.Texture' }
        'owner_nudo' { $rows.manifest.shoulder_network.outer_terrain.owner_labels[4] = 'YACS_PERSIST_SUPPORT_082' }
        'owner_parapet' { $rows.gpu.outer_terrain_after.outer_owner_labels[4] = 'YACS_PERSIST_SUPPORT_181' }
        'uv0' { $rows.manifest.shoulder_network.outer_terrain.uv0_stage_witness_required = $false }
        'shader_scope' { $rows.gpu.outer_gpu_statistics_before.master = '/Game/Foreign.Master' }
        'before_binding' { $rows.gpu.outer_terrain_before.outer_texture_objects.ScreeNormalTex = '/Game/Foreign.Texture' }
        'after_binding' { $rows.gpu.outer_terrain_after.landscape_component_count = 1023 }
        'zero_gpu' { $rows.gpu.outer_gpu_statistics_before.native_statistics.num_samplers = 0 }
        'negative_gpu' { $rows.gpu.outer_gpu_statistics_before.native_statistics.num_uv_scalars = -1 }
        'boolean_gpu' { $rows.gpu.outer_gpu_statistics_before.native_statistics.num_samplers = $true }
        'changed_gpu' { $rows.gpu.outer_gpu_statistics_after.native_statistics.num_samplers += 1 }
        'extra_gpu_field' { $rows.gpu.outer_gpu_statistics_before.native_statistics.invented = 0 }
        'normal_claim' { $rows.gpu.outer_terrain_normal_response_verified = $true }
        'contact_claim' { $rows.gpu.outer_terrain_after.physical_contact_verified = $true }
        'host_log_omitted' { $rows.gpu.outer_gpu_statistics_before.host_shader_log_check_required = $false }
    }
    Reject { Outer $rows } $failure
}
# The same sixteen controls retain all 26 source identities, not just a count.
Get-CrackVisualControlArtifacts $fixture.good $fixture.proof $fixture.manifest $fixture.engine $fixture.project | Out-Null
foreach ($failure in @('missing_outer', 'last_outer_default', 'outer_not_resident', 'outer_replacement')) {
    $ready = $fixture.ready | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    $outer = @($ready.textures | Where-Object { $_.channel -clike 'OuterTerrain_*' })
    switch ($failure) {
        'missing_outer' { $ready.textures = @($ready.textures | Where-Object { $_.channel -cne 'OuterTerrain_ScreeNormalTex' }) }
        'last_outer_default' { $outer[-1].native_readback.is_default_texture = $true }
        'outer_not_resident' { $outer[-1].native_readback.resident_mips -= 1 }
        'outer_replacement' { $outer[-1].asset = '/Game/Foreign.Texture' }
    }
    Reject { Assert-MaterialTextureReadiness $ready $fixture.manifest } $failure
}
$withoutCracks = $fixture.manifest | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
$withoutCracks.crack_canary_enabled = $false; $withoutCracks.Remove('crack_canary')
$eighteen = $fixture.ready | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
$eighteen.textures = @($eighteen.textures | Where-Object { $_.channel -cnotlike 'Crack_*' })
if ($eighteen.textures.Count -ne 18) { throw 'Expected eighteen base/shoulder/outer texture readbacks.' }
Assert-MaterialTextureReadiness $eighteen $withoutCracks
Reject { Assert-MaterialTextureReadiness $fixture.ready $withoutCracks } 'extra disabled crack textures'
$wrongCount = FreshData
$wrongCount.frames[-1].capture_readiness.material_texture_count = 15
Reject { Check $wrongCount } 'stale fifteen-texture count with outer canary'
''')

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_targeted_shader_log_catches_owned_failure_and_ignores_unrelated_startup_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._crack_host_fixture(root)
            self._run_crack_host_cases(root, fixture, r'''
$path = Join-Path $fixture.proof 'synthetic-shader-log.log'
$prefix = '/Game/Generated/YACS/RoadAsphaltConsumer/ShoulderNetwork/TerrainBlend/'
$master = $prefix + 'M_ShoulderNetworkTerrain.M_ShoulderNetworkTerrain'
# Firsthand Epic forum log formatter, with this fixture's material substituted;
# these strings are not a native rendering or a UE5.8 compiler success witness.
$unrelated = @(
    'LogShaderCompilers: Warning: Failed to compile Material /Engine/Unrelated.Unrelated for platform PCD3D_SM6, Default Material will be used in game.',
    'LogStreaming: Error: Could not find file /Engine/EditorResources/MissingAsset',
    'LogMaterial: Warning: Missing cached shader map for M_ShoulderNetworkTerrain, compiling.',
    'LogShaderCompilers: Display: Completed shader compilation for M_ShoulderNetworkTerrain.',
    'LogMaterial: Error: /Game/Other/M_ShoulderNetworkTerrain_Debug failed to compile material.'
)
[IO.File]::WriteAllText($path, ($unrelated -join "`r`n"), [Text.UTF8Encoding]::new($true))
$before = File-Identity $path
$observed = Get-OuterTerrainShaderLogObservation $path
Assert-OuterTerrainShaderLog $observed
Assert-JsonEqual 0 $observed.matched_line_count 'no targeted failures in unrelated/normal fixture'
Assert-JsonEqual $false $observed.all_shader_errors_verified 'targeted scan is not universal shader proof'
Assert-JsonEqual $false $observed.gpu_compilation_admitted 'log observation is not GPU admission'
Assert-Identity $before
$failures = @(
    ('LogShaderCompilers: Warning: Failed to compile Material ' + $master + ' for platform PCD3D_SM6, Default Material will be used in game.'),
    ('LogMaterial: Error: Failed to compile Material ' + $master),
    ('LogMaterial: Warning: ' + $prefix + 'MI_ShoulderNetworkTerrain.MI_ShoulderNetworkTerrain: Default Material will be used in game.'),
    'LogShaderCompilers: Error: M_ShoulderNetworkTerrain [SM6] error X3000: synthetic compile error'
)
foreach ($failure in $failures) {
    [IO.File]::WriteAllText($path, (($unrelated + @($failure)) -join "`r`n"))
    $observed = Get-OuterTerrainShaderLogObservation $path
    Assert-JsonEqual 1 $observed.matched_line_count 'one targeted native-format error'
    Assert-JsonEqual $failure $observed.matched_lines[0].text 'retained exact failure line'
    Assert-JsonEqual 6 $observed.matched_lines[0].line_number 'retained source line number'
    Reject { Assert-OuterTerrainShaderLog $observed } 'targeted shader failure'
}
[IO.File]::WriteAllText($path, ((1..65 | ForEach-Object { $failures[0] }) -join "`n"))
$observed = Get-OuterTerrainShaderLogObservation $path
Assert-JsonEqual 65 $observed.matched_line_count 'all matches counted'
Assert-JsonEqual 64 $observed.matched_lines.Count 'bounded retained failure lines'
Assert-JsonEqual $true $observed.matches_truncated 'bounded observation explicitly marked'
Reject { Assert-OuterTerrainShaderLog $observed } 'truncated error set still fails'
''')

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_surface_lane_gates_bind_saved_fresh_and_gpu_without_readback_reapplication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = self._crack_host_fixture(root)
            self._run_crack_host_cases(root, fixture, r'''
# Evaluate only the production lane guard/settings/environment expressions;
# no Editor or Windows host operation is invoked by these local policy tests.
$guards = @($ast.EndBlock.Statements | Where-Object {
    $_ -is [System.Management.Automation.Language.IfStatementAst] -and
    ($_.Extent.Text.StartsWith('if ($CrackCanary -and -not $EdgeMarkings') -or
     $_.Extent.Text.StartsWith('if ($PaintCoverage -and (-not $VisualControls'))
})
$processes = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.CommandAst] -and $node.GetCommandName() -ceq 'Start-Process'
}, $true))
if ($guards.Count -ne 2 -or $processes.Count -ne 1) { throw 'Production lane guards or owned process differ.' }
$environmentExpression = $null
for ($index = 0; $index -lt $processes[0].CommandElements.Count; $index++) {
    $item = $processes[0].CommandElements[$index]
    if ($item -is [System.Management.Automation.Language.CommandParameterAst] -and $item.ParameterName -ceq 'Environment') {
        $environmentExpression = $processes[0].CommandElements[$index + 1].Extent.Text
    }
}
if (-not $environmentExpression) { throw 'Owned GPU process lacks an explicit environment.' }
$RunToken = $fixture.good.run_token; $ExpectedHead = $fixture.good.exact_sha
$WorkspaceConfig = 'D:\yacs\workspace.json'
$readHost = @{ value = @{ proof_files = @{ session_preparation = @{ sha256 = 'f' * 64 } } } }
$expectedPlan = @{ identity = @{ sha256 = 'c' * 64 } }
foreach ($OuterTerrainCanary in @($false, $true)) {
foreach ($mode in @(@($false, $false, $false, $false), @($false, $true, $false, $false),
                    @($true, $true, $false, $false), @($true, $false, $true, $false),
                    @($true, $true, $true, $false), @($true, $true, $false, $true), @($true, $true, $true, $true))) {
    $EdgeMarkings, $VisualControls, $CrackCanary, $PaintCoverage = $mode
    foreach ($guard in $guards) { . ([scriptblock]::Create($guard.Extent.Text)) }
    foreach ($name in @('edgeMarkingSetting', 'visualControlToken', 'crackCanarySetting', 'crackControlToken',
                       'paintCoverageToken', 'expectedVisualControlCount', 'expectedMaterialTextureCount', 'outerTerrainSetting')) {
        $setting = @($ast.EndBlock.Statements | Where-Object {
            $_ -is [System.Management.Automation.Language.AssignmentStatementAst] -and $_.Left.Extent.Text -ceq ('$' + $name)
        })
        if ($setting.Count -ne 1) { throw 'Production GPU lane setting is missing or ambiguous.' }
        . ([scriptblock]::Create($setting[0].Extent.Text))
    }
    $environment = & ([scriptblock]::Create($environmentExpression))
    Assert-JsonEqual $(if ($EdgeMarkings) { '1' } else { '0' }) $environment.YACS_ROAD_EDGE_MARKINGS 'edge environment'
    Assert-JsonEqual $(if ($CrackCanary) { '1' } else { '0' }) $environment.YACS_ROAD_CRACK_CANARY 'crack environment'
    Assert-JsonEqual $(if ($OuterTerrainCanary) { '1' } else { '0' }) $environment.YACS_ROAD_OUTER_TERRAIN_CANARY 'outer environment'
    Assert-JsonEqual $(if ($VisualControls) { $RunToken } else { $null }) $environment.YACS_ROAD_VISUAL_CONTROLS_OWNED 'inactive asphalt marker cleared'
    Assert-JsonEqual $(if ($CrackCanary -and -not $VisualControls) { $RunToken } else { $null }) `
        $environment.YACS_ROAD_CRACK_CONTROLS_OWNED 'scene presence does not select the crack controller'
    Assert-JsonEqual $(if ($PaintCoverage) { $RunToken } else { $null }) $environment.YACS_ROAD_PAINT_COVERAGE_OWNED 'inactive paint marker cleared'
    Assert-JsonEqual $(if ($PaintCoverage) { 10 } else { 8 }) $expectedVisualControlCount 'exact selected asphalt control count'
    Assert-JsonEqual ($(if ($CrackCanary) { 15 } else { 7 }) + $(if ($OuterTerrainCanary) { 11 } else { 0 })) `
        $expectedMaterialTextureCount 'native material texture lane'
}
}
foreach ($mode in @(@($false, $false, $true, $false), @($false, $true, $true, $false),
                    @($true, $false, $false, $true), @($false, $true, $false, $true), @($true, $false, $true, $true))) {
    $EdgeMarkings, $VisualControls, $CrackCanary, $PaintCoverage = $mode
    Reject { foreach ($guard in $guards) { . ([scriptblock]::Create($guard.Extent.Text)) } } 'incompatible diagnostic switches'
}
foreach ($mode in @(@($false, $false), @($true, $false), @($true, $true))) {
    $markings, $cracks = $mode
    $savedHost = @{ edge_markings_requested = $markings; edge_markings_fresh_reload_verified = $markings
        crack_canary_requested = $cracks; crack_canary_fresh_reload_verified = $cracks; crack_normal_space_verified = $false }
    $prepared = @{ edge_markings_enabled = $markings; crack_canary_enabled = $cracks }
    $manifest = @{ edge_markings_enabled = $markings; crack_canary_enabled = $cracks }
    $fresh = @{ edge_markings_enabled = $markings; crack_canary_enabled = $cracks
        edge_markings_fresh_reload_verified = $markings; crack_canary_fresh_reload_verified = $cracks
        edge_marking_material_reapplied = $false; edge_marking_geometry_reapplied = $false
        crack_material_reapplied = $false; crack_geometry_reapplied = $false; edge_marking_readback = $null; crack_readback = $null }
    if ($markings) {
        $manifest.edge_markings = @{ saved = $true }
        $fresh.edge_marking_readback = @{ status = 'EDGE_MARKINGS_FRESH_READBACK_VERIFIED'; read_only = $true
            owner_visual_pass = $false; performance_pass = $false; all_marking_buffers_verified = $true; full_source_buffers_preserved = $true }
    }
    if ($cracks) {
        $manifest.crack_canary = @{ status = 'LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING'; plan_sha256 = 'a' * 64
            normal_space_verified = $false; source_correspondence = @{ native_source_witness_sha256 = 'b' * 64 } }
        $fresh.crack_readback = @{ status = 'LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING'
            plan_sha256 = 'a' * 64; actor_count = 2; native_source_witness_sha256 = 'b' * 64
            all_crack_buffers_verified = $true; full_source_and_existing_paint_buffers_preserved = $true
            caller_fresh_process_and_saved_bytes_required = $true; world_normal_canary_required = $true
            normal_space_verified = $false; read_only = $true; owner_visual_pass = $false; performance_pass = $false }
        $fresh.edge_marking_readback.aggregate_owner = 'local_crack_canary'
    }
    Assert-SurfaceDetailLanes $savedHost $prepared $fresh $manifest $markings $cracks
    foreach ($part in @('host_requested', 'host_fresh', 'prepared', 'fresh_mode', 'fresh_verified', 'manifest', 'reapplied')) {
        $rows = @{ host_row = $savedHost; prepared = $prepared; fresh = $fresh; manifest = $manifest } |
            ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
        switch ($part) {
            'host_requested' { $rows.host_row.crack_canary_requested = -not $cracks }
            'host_fresh' { $rows.host_row.crack_canary_fresh_reload_verified = -not $cracks }
            'prepared' { $rows.prepared.crack_canary_enabled = -not $cracks }
            'fresh_mode' { $rows.fresh.crack_canary_enabled = -not $cracks }
            'fresh_verified' { $rows.fresh.crack_canary_fresh_reload_verified = -not $cracks }
            'manifest' { $rows.manifest.crack_canary_enabled = -not $cracks }
            'reapplied' { $rows.fresh.crack_geometry_reapplied = $true }
        }
        Reject { Assert-SurfaceDetailLanes $rows.host_row $rows.prepared $rows.fresh $rows.manifest $markings $cracks } $part
    }
    $gpu = @{ edge_markings_enabled = $markings; crack_canary_enabled = $cracks; crack_normal_space_verified = $false
        edge_markings_before = $fresh.edge_marking_readback; edge_markings_after = $fresh.edge_marking_readback
        crack_before = $fresh.crack_readback; crack_after = $fresh.crack_readback }
    Assert-SurfaceDetailGpuReadback $gpu $fresh $markings $cracks
    foreach ($key in @('edge_markings_before', 'edge_markings_after', 'crack_before', 'crack_after')) {
        $copy = $gpu | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
        $copy[$key] = @{ invented = $true }
        Reject { Assert-SurfaceDetailGpuReadback $copy $fresh $markings $cracks } $key
    }
    $gpu.crack_normal_space_verified = $true
    Reject { Assert-SurfaceDetailGpuReadback $gpu $fresh $markings $cracks } 'normal admission'
}
Reject { Assert-SurfaceDetailLanes @{} @{} @{} @{} $false $true } 'cracks without white markings'
''')


if __name__ == "__main__":
    unittest.main()
