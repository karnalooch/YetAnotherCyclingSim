from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class PassoGiauLandscapeAuthorContractTest(unittest.TestCase):
    def test_cpp_import_contract_is_isolated_and_exact(self) -> None:
        cpp = read(
            "Source/YetAnotherCyclingSim/Private/Editor/"
            "CyclingPassoGiauLandscapeSpikeCommandlet.cpp"
        )
        self.assertIn(
            "/Game/Prototype/Maps/L_PassoGiauTerrainSpike",
            cpp,
        )
        self.assertNotIn("/Game/Prototype/Maps/L_CyclingTest", cpp)
        self.assertIn("LandscapeVertices = 4033", cpp)
        self.assertIn("NumSubsections = 2", cpp)
        self.assertIn("SubsectionSizeQuads = 63", cpp)
        self.assertIn(
            "ExpectedComponentCount = ExpectedComponentGrid * ExpectedComponentGrid",
            cpp,
        )
        self.assertIn("ExpectedComponentGrid = 32", cpp)
        self.assertIn("XYScaleCmPerVertex = 198.412698", cpp)
        self.assertIn("ZScale = 301.26543", cpp)
        self.assertIn("LocationZCm = 194259.253", cpp)
        self.assertIn('TEXT("ScaleZ=")', cpp)
        self.assertIn('TEXT("LocationZCm=")', cpp)
        self.assertIn("RuntimeZScale", cpp)
        self.assertIn("RuntimeLocationZCm", cpp)
        self.assertEqual(cpp.count("const double SampledElevationMinM ="), 1)
        self.assertEqual(cpp.count("const double SampledElevationMaxM ="), 1)
        self.assertIn("(static_cast<double>(EncodedMin) - 32768.0) / 128.0", cpp)
        self.assertIn("(static_cast<double>(EncodedMax) - 32768.0) / 128.0", cpp)
        self.assertIn(
            "encoded height-domain proof",
            read("scripts/ue/Invoke-YacsPassoGiauLandscapeSpike.ps1"),
        )

    def test_map_prep_creates_blank_isolated_spike_without_canonical_load(self) -> None:
        script = read("scripts/ue/stage3g_prepare_passo_giau_landscape_map.py")
        self.assertIn(
            'SPIKE_MAP = "/Game/Prototype/Maps/L_PassoGiauTerrainSpike"',
            script,
        )
        self.assertIn(
            "level_subsystem.new_level(SPIKE_MAP, is_partitioned_world=False)",
            script,
        )
        self.assertNotIn("duplicate_asset", script)
        self.assertNotIn("/Game/Prototype/Maps/L_CyclingTest", script)
        self.assertIn('"canonical_map_loaded": False', script)
        self.assertIn('"canonical_map_mutated": False', script)

    def test_wrapper_fails_closed_on_canonical_map_and_mutations(self) -> None:
        wrapper = read("scripts/ue/Invoke-YacsPassoGiauLandscapeSpike.ps1")
        self.assertIn("$CanonicalHashBefore", wrapper)
        self.assertIn("$CanonicalHashAfter", wrapper)
        self.assertIn("$SpikeMapPath = Join-Path $RepoRoot $SpikeMapRelative", wrapper)
        self.assertIn("Remove-Item -LiteralPath $SpikeMapPath -Force", wrapper)
        self.assertIn(
            "Failed to remove the existing isolated Passo Giau spike map", wrapper
        )
        self.assertIn(
            "L_CyclingTest changed during isolated Passo Giau authoring",
            wrapper,
        )
        self.assertIn(
            "$Unexpected = @($TrackedChanges | Where-Object { $_ -ne $SpikeMapRelative })",
            wrapper,
        )
        self.assertIn("visual_acceptance = 'PENDING_HUMAN_REVIEW'", wrapper)
        self.assertIn("authoritative_route_geometry = $false", wrapper)
        self.assertIn("authoritative_physics = $false", wrapper)
        self.assertNotIn("git lfs fsck", wrapper)
        self.assertNotIn("git lfs checkout", wrapper)
        self.assertIn("$ImportExitCode -notin @(0, 1)", wrapper)
        self.assertIn("CyclingPassoGiauLandscapeSpikeCommandlet: done", wrapper)
        self.assertIn("$CaptureExitCode -notin @(0, 1)", wrapper)
        self.assertIn(r"\[PassoGiauCapture\] PASS:", wrapper)
        self.assertIn(
            "$CaptureStdout = Join-Path $ArtifactRoot 'capture.stdout.log'", wrapper
        )
        self.assertIn("-RedirectStandardOutput $CaptureStdout", wrapper)
        self.assertIn("capture proof LOD stabilization is invalid", wrapper)
        self.assertIn("geometry proof sun unexpectedly casts shadows", wrapper)
        self.assertIn("diagnostic proof view mode is invalid", wrapper)
        self.assertIn("capture proof PNG byte count", wrapper)
        self.assertIn("Fatal error|Unhandled Exception|Critical error", wrapper)
        self.assertIn("code_only_lfs_asset_registry_exit_tolerance_used", wrapper)
        self.assertIn("download_passo_giau_veneto_lidar.py", wrapper)
        self.assertIn("prepare_passo_giau_veneto_lidar.py", wrapper)
        self.assertIn("PreparedVenetoLidar5m", wrapper)
        self.assertIn("('-ScaleZ=' + $ScaleZ.ToString", wrapper)
        self.assertIn("('-LocationZCm=' + $LocationZCm.ToString", wrapper)
        self.assertIn("native_cell_m", wrapper)
        self.assertIn("IODL 2.0", wrapper)

    def test_capture_requires_real_png_and_human_review(self) -> None:
        capture = read("scripts/ue/stage3g_capture_passo_giau_landscape.py")
        self.assertIn("take_high_res_screenshot", capture)
        self.assertIn("CAPTURE_RES_X = 3840", capture)
        self.assertIn("CAPTURE_RES_Y = 2160", capture)
        self.assertIn("res_x=CAPTURE_RES_X", capture)
        self.assertIn("res_y=CAPTURE_RES_Y", capture)
        self.assertIn('"r.AntiAliasingMethod 1"', capture)
        self.assertIn("r.PostProcessAAQuality", capture)
        self.assertIn('"proof_aa_method": PROOF_AA_METHOD', capture)
        self.assertIn('"post_process_aa_quality": PROOF_AA_QUALITY', capture)
        self.assertIn("is_task_done()", capture)
        self.assertIn("set_keep_python_script_alive(True)", capture)
        self.assertIn("set_keep_python_script_alive(False)", capture)
        self.assertNotIn("SystemLibrary.quit_editor", capture)
        self.assertIn("get_component_by_class(unreal.CameraComponent)", capture)
        self.assertIn("get_components_by_class(unreal.LandscapeComponent)", capture)
        self.assertIn("component.set_forced_lod(0)", capture)
        self.assertIn("component.set_lod_bias(0)", capture)
        self.assertIn("r.RayTracing.Geometry.Landscape.LODBias -1", capture)
        self.assertIn('"forced_landscape_lod": 0', capture)
        self.assertIn('"ray_tracing_landscape_lod_bias": -1', capture)
        self.assertIn("sun_component.set_cast_shadows(False)", capture)
        self.assertIn('"proof_sun_cast_shadows": False', capture)
        self.assertNotIn("/Game/Prototype/Environment/", capture)
        self.assertNotIn("component.set_material(", capture)
        self.assertNotIn("landscape_material", capture)
        self.assertIn('"viewmode lightingonly"', capture)
        self.assertIn('"proof_viewmode": "lightingonly"', capture)
        self.assertNotIn("get_camera_component()", capture)
        self.assertIn('"visual_acceptance": "PENDING_HUMAN_REVIEW"', capture)

    def test_workflow_runs_only_on_ue58_and_commits_only_spike_map(self) -> None:
        workflow = read(".github/workflows/passo-giau-r4-1-landscape-author.yml")
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", workflow)
        self.assertIn("lfs: false", workflow)
        self.assertIn("'scripts/assets/prepare_passo_giau_heightmap.py'", workflow)
        self.assertIn("'scripts/assets/download_passo_giau_veneto_lidar.py'", workflow)
        self.assertIn("'scripts/assets/prepare_passo_giau_veneto_lidar.py'", workflow)
        self.assertIn("PreparedVenetoLidar5m/terrain-report.json", workflow)
        self.assertNotIn("git lfs checkout", workflow)
        self.assertIn("path: _passo-giau-worktree", workflow)
        self.assertIn("working-directory: _passo-giau-worktree", workflow)
        self.assertIn("./scripts/ci/Test-YacsCodeOnlyCheckout.ps1", workflow)
        self.assertIn("$staleSpike = Join-Path $env:GITHUB_WORKSPACE", workflow)
        self.assertIn("Remove-Item -LiteralPath $staleSpike -Force", workflow)
        self.assertNotIn('git cat-file blob "HEAD:$spikeAsset"', workflow)
        self.assertNotIn("[System.IO.File]::WriteAllText(", workflow)
        self.assertNotIn("git lfs fsck", workflow)
        self.assertIn("permissions:\n  contents: write", workflow)
        self.assertIn(
            "$asset = 'Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap'",
            workflow,
        )
        self.assertIn("git diff --cached --name-only", workflow)
        self.assertNotIn("git add -A", workflow)
    def test_preparation_reports_numeric_and_seam_diagnostics(self) -> None:
        prepare = read("scripts/assets/prepare_passo_giau_heightmap.py")
        self.assertIn("def terrain_diagnostics(", prepare)
        self.assertIn('"vertical_quantization_step_m"', prepare)
        self.assertIn('"r16_roundtrip_error_m"', prepare)
        self.assertIn('"subsection_63_quads": seam_stats(63)', prepare)
        self.assertIn('"component_126_quads": seam_stats(126)', prepare)
        self.assertIn('"diagnostics": terrain_diagnostics(', prepare)
        self.assertIn("DEFAULT_LANDSCAPE_SIZE = 4033", prepare)
        self.assertIn("resampling=Resampling.cubic", prepare)
        self.assertIn('"landscape_resampling": "cubic"', prepare)


    def test_editor_build_links_landscape_module(self) -> None:
        build = read("Source/YetAnotherCyclingSim/YetAnotherCyclingSim.Build.cs")
        self.assertIn('"Landscape"', build)


if __name__ == "__main__":
    unittest.main()
