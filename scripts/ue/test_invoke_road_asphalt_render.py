"""Road asphalt GPU host policy regression; independent native capture is required."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / "scripts/ue/Invoke-YacsRoadAsphaltRender.ps1"
WORKFLOW = ROOT / ".github/workflows/road-material-native-proof.yml"
ATTRIBUTES = ROOT / ".gitattributes"


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
foreach ($name in @('Assert-JsonEqual', 'Assert-ViewPlan', 'Assert-NativeCameraObservation', 'Assert-GpuReviewContract')) {
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
foreach ($failure in @('order', 'pose', 'station', 'plan_hash', 'profile', 'priming', 'priming_total',
                       'mips', 'supports', 'selected_ids', 'walls', 'road_buffers', 'asphalt',
                       'admission', 'sampling', 'shader', 'native_location', 'native_rotation',
                       'native_direction', 'native_fov', 'native_error', 'native_nonfinite', 'native_missing',
                       'prime_direction', 'prime_missing')) {
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


if __name__ == "__main__":
    unittest.main()
