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

        self.assertIn("ConvertNonEditLayerLandscape()", cpp)
        self.assertIn("if (EditLayers.Num() == 0)", cpp)
        self.assertIn('FName BaseLayerName(TEXT("Base_DTM"))', cpp)
        self.assertIn('FName RoadLayerName(TEXT("Road_Earthworks"))', cpp)
        self.assertIn("ULandscapeEditLayer::StaticClass()", cpp)
        self.assertIn("Landscape->EditorApplySpline(", cpp)
        self.assertIn("Spline->SetMobility(EComponentMobility::Static);", cpp)
        self.assertIn("RoadEarthworksHalfWidthCm = 450.0", cpp)
        self.assertIn("RoadEarthworksSideFalloffCm = 650.0", cpp)
        self.assertIn("RoadEarthworksSubdivisionsPerControlPoint = 4", cpp)
        self.assertIn("Landscape->ForceLayersFullUpdate()", cpp)
        self.assertIn(r'TEXT("  \"edit_layers_enabled\": true,\n")', cpp)
        self.assertIn(r'TEXT("  \"road_earthworks_applied\": %s,\n")', cpp)
        self.assertNotIn("SpawnHairpinRetainingHelper(", cpp)
        self.assertNotIn("RetainingHelper", cpp)
        wrapper = read("scripts/ue/Invoke-YacsPassoGiauLandscapeSpike.ps1")
        self.assertIn("edit_layers_enabled", wrapper)
        self.assertIn("edit_layer_count -ne 2", wrapper)
        self.assertIn("base_edit_layer -ne 'Base_DTM'", wrapper)
        self.assertIn("road_edit_layer -ne 'Road_Earthworks'", wrapper)
        self.assertIn("road_earthworks_applied", wrapper)
        self.assertIn("road_earthworks_raise_heights", wrapper)
        self.assertIn("road_earthworks_lower_heights", wrapper)
        self.assertIn("road_earthworks_side_falloff_cm - 650.0", wrapper)
        self.assertIn("redundant edit-layer conversion", wrapper)
        self.assertIn("Attempting to ConvertNonEditLayerLandscape", wrapper)
        self.assertIn("spline-mesh mobility attachment failures", wrapper)
        self.assertIn("AttachTo:.*SP638Spline.*is not static.*SP638Segment_", wrapper)
        self.assertNotIn("retaining_helper", wrapper)

        self.assertIn('#include "LandscapeImportHelper.h"', cpp)
        self.assertIn("VerifyUnrealImportReaderParity(", cpp)
        self.assertIn("GetHeightmapImportDescriptor(", cpp)
        self.assertIn("GetHeightmapImportData(", cpp)
        self.assertIn("Unreal native R16 reader parity mismatch", cpp)
        self.assertIn(
            r'TEXT("  \"unreal_native_import_reader_parity\": \"PASS\",\n")',
            cpp,
        )
        self.assertIn(
            "Unreal-native R16 import-reader parity proof is missing or failed",
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
        self.assertIn("RoadTerrainOnlyPng", wrapper)
        self.assertIn("same-camera-combined-vs-terrain-only", wrapper)
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
        self.assertIn("download_passo_giau_mase_pst.py", wrapper)
        self.assertIn("prepare_passo_giau_mase_pst.py", wrapper)
        self.assertIn("PreparedMasePstLidar1x1", wrapper)
        self.assertIn("('-ScaleZ=' + $ScaleZ.ToString", wrapper)
        self.assertIn("('-LocationZCm=' + $LocationZCm.ToString", wrapper)
        self.assertIn("native_cell_m", wrapper)
        self.assertIn("EPSG:4326", wrapper)
        self.assertIn("EPSG:32632", wrapper)
        self.assertIn("sampled_unique_elevation_count", wrapper)
        self.assertIn(
            "4215d1d37fb8540c44442aedd164b6cda3f1845f3552413a975a6b7b1461e93c",
            wrapper,
        )
        self.assertIn("CC BY 4.0", wrapper)

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
        self.assertIn("YACS_PASSO_GIAU_ROAD_TERRAIN_ONLY_PNG", capture)
        self.assertIn("same-camera-combined-vs-terrain-only", capture)
        self.assertIn("mesh.set_visibility(False, True)", capture)
        self.assertIn("mesh.set_visibility(True, True)", capture)

    def test_workflow_runs_only_on_ue58_and_commits_only_spike_map(self) -> None:
        workflow = read(".github/workflows/passo-giau-r4-1-landscape-author.yml")
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", workflow)
        self.assertIn("lfs: false", workflow)
        self.assertIn("'scripts/assets/prepare_passo_giau_heightmap.py'", workflow)
        self.assertIn("'scripts/assets/download_passo_giau_mase_pst.py'", workflow)
        self.assertIn("'scripts/assets/download_passo_giau_veneto_lidar.py'", workflow)
        self.assertIn("'scripts/assets/prepare_passo_giau_mase_pst.py'", workflow)
        self.assertIn("'scripts/assets/prepare_passo_giau_veneto_lidar.py'", workflow)
        self.assertIn("PreparedMasePstLidar1x1/terrain-report.json", workflow)
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

    def test_active_mase_pst_preparation_reports_numeric_and_seam_diagnostics(
        self,
    ) -> None:
        prepare = read("scripts/assets/prepare_passo_giau_mase_pst.py")
        shared = read("scripts/assets/prepare_passo_giau_veneto_lidar.py")

        self.assertIn(
            "from prepare_passo_giau_veneto_lidar import (",
            prepare,
        )
        for helper in (
            "adjacent_diagnostics",
            "encode_u16",
            "hillshade",
            "landscape_diagnostics",
            "scanline_diagnostics",
            "slope_diagnostics",
            "stats",
        ):
            self.assertIn(helper, prepare)

        # The MASE path deliberately reuses the already-proven numeric
        # diagnostics instead of forking their implementation.
        self.assertIn("def r16_roundtrip_diagnostics(", shared)
        self.assertIn("def seam_diagnostics(", shared)
        self.assertIn("def slope_diagnostics(", shared)
        self.assertIn("def scanline_diagnostics(", shared)
        self.assertIn("def landscape_diagnostics(", shared)
        self.assertIn('"vertical_quantization_step_m"', shared)
        self.assertIn('"r16_roundtrip_error_m"', shared)
        self.assertIn('"subsection_63_quads": seam_diagnostics(', shared)
        self.assertIn('"component_126_quads": seam_diagnostics(', shared)

        self.assertIn('"landscape_diagnostics": landscape_diagnostics(', prepare)
        self.assertIn('"slope_degrees": slope_diagnostics(', prepare)
        self.assertIn('"scanlines": scanline_diagnostics(', prepare)
        self.assertIn("LANDSCAPE_SIZE = 4033", prepare)
        self.assertIn('PRIMARY_SOURCE_CRS = "EPSG:4326"', prepare)
        self.assertIn('TARGET_CRS = "EPSG:32632"', prepare)
        self.assertIn("TARGET_NATIVE_RESOLUTION_M = 1.0", prepare)
        self.assertIn("TARGET_NATIVE_SIZE = 8000", prepare)
        self.assertIn("MIN_MASE_COVERAGE_SHARE = 0.50", prepare)
        self.assertIn("EXPECTED_MASE_PIXEL_DEGREES = (0.00001, 0.000005)", prepare)
        self.assertIn("expected one of {EXPECTED_MASE_PIXEL_DEGREES}", prepare)
        self.assertIn("non-square angular pixels", prepare)
        self.assertIn("PASSO_GIAU_WGS84", prepare)
        self.assertNotIn("expected 1000x1000", prepare)
        self.assertNotIn("src.width != 1000", prepare)
        self.assertNotIn("src.height != 1000", prepare)
        self.assertIn("expected Float32 raster data", prepare)
        self.assertIn("src.count != 1", prepare)
        self.assertIn("reproject_veneto_fallback(", prepare)
        self.assertIn("mase_missing_samples_filled_by_veneto", prepare)
        self.assertIn("nearest_mase_sample_distance_m", prepare)
        self.assertIn("terrain_truth_note", prepare)
        self.assertIn("sampled_unique_elevation_count", prepare)
        self.assertIn("resampling=Resampling.cubic", prepare)
        self.assertIn('"landscape_resampling": "cubic"', prepare)
        self.assertIn("landscape_resampling_guard", prepare)
        self.assertIn("np.clip(", prepare)
        self.assertIn("clipped_above_count", prepare)

        wrapper = read("scripts/ue/Invoke-YacsPassoGiauLandscapeSpike.ps1")
        self.assertIn("nearest_mase_sample_distance_m", wrapper)
        self.assertIn("$Diagnostics = $Terrain.landscape_diagnostics", wrapper)
        self.assertIn("$Diagnostics.r16_roundtrip_error_m", wrapper)
        self.assertIn("$Diagnostics.seams.subsection_63_quads", wrapper)
        self.assertIn("$Diagnostics.seams.component_126_quads", wrapper)
        self.assertIn("R16 round-trip error exceeds half-step", wrapper)
        self.assertIn("prepared slope diagnostics", wrapper)
        self.assertIn("deterministic center scanline diagnostics", wrapper)

    def test_road_preparer_samples_active_mase_hybrid_terrain(self) -> None:
        prepare = read("scripts/assets/prepare_passo_giau_road.py")
        self.assertIn('return source_root() / "PreparedMasePstLidar1x1"', prepare)
        self.assertIn('"passo_giau_mase_pst_hybrid_1m_8km_epsg32632.tif"', prepare)
        self.assertIn('"passo_giau_mase_pst_hybrid_2m_preview_hillshade.png"', prepare)
        self.assertNotIn("PreparedVenetoLidar5m", prepare)
        self.assertNotIn("passo_giau_veneto_lidar_5m_8km_epsg32632.tif", prepare)

    def test_sp638_reports_primary_vs_fallback_length_on_active_1m_mask(
        self,
    ) -> None:
        terrain = read("scripts/assets/prepare_passo_giau_mase_pst.py")
        road = read("scripts/assets/prepare_passo_giau_road.py")
        workflow = read(".github/workflows/passo-giau-road-alignment.yml")
        author = read(".github/workflows/passo-giau-r4-1-road-author.yml")

        self.assertIn("passo_giau_mase_pst_primary_coverage_1m.tif", terrain)
        self.assertIn('"primary_coverage_mask_geotiff"', terrain)
        self.assertIn("SOURCE_COVERAGE_SAMPLE_INTERVAL_M = 1.0", road)
        self.assertIn("passo_giau_mase_pst_primary_coverage_1m.tif", road)
        self.assertIn('"terrain_source_coverage"', road)
        self.assertIn('"mase_primary_length_m"', road)
        self.assertIn('"veneto_fallback_length_m"', road)
        self.assertIn("Prepare active MASE-primary hybrid terrain source", workflow)
        self.assertIn("download_passo_giau_mase_pst.py", workflow)
        self.assertIn("prepare_passo_giau_mase_pst.py", workflow)
        self.assertIn("'scripts/assets/prepare_passo_giau_mase_pst.py'", author)
        self.assertIn("permissions:\n  contents: read", author)
        self.assertIn("persist-credentials: false", author)
        self.assertNotIn("Commit only isolated spike map", author)
        self.assertNotIn("git push origin", author)

    def test_generic_preparer_keeps_reference_diagnostic_contract(self) -> None:
        prepare = read("scripts/assets/prepare_passo_giau_heightmap.py")
        self.assertIn("def terrain_diagnostics(", prepare)
        self.assertIn('"r16_roundtrip_error_m"', prepare)
        self.assertIn('"subsection_63_quads": seam_stats(63)', prepare)
        self.assertIn('"component_126_quads": seam_stats(126)', prepare)

    def test_mase_release_source_is_pinned_and_does_not_depend_on_live_mase(
        self,
    ) -> None:
        downloader = read("scripts/assets/download_passo_giau_mase_pst.py")
        self.assertIn(
            'RELEASE_TAG = "data-mase-pst-passo-giau-dtm-2026-09-28"',
            downloader,
        )
        self.assertIn("ARCHIVE_BYTES = 853_162_557", downloader)
        self.assertIn(
            'ARCHIVE_SHA256 = "4215d1d37fb8540c44442aedd164b6cda3f1845f3552413a975a6b7b1461e93c"',
            downloader,
        )
        self.assertIn("EXPECTED_TILE_COUNT = 204", downloader)
        self.assertIn("SOURCE_PACKAGE_ID = 1372858", downloader)
        self.assertIn("DOWNLOAD_ATTEMPTS = 6", downloader)
        self.assertIn("DOWNLOAD_TIMEOUT_SECONDS = 300", downloader)
        self.assertIn('headers["Range"] = f"bytes={written}-"', downloader)
        self.assertIn('"Content-Range"', downloader)
        self.assertIn("resuming at byte", downloader)
        self.assertIn(
            'ARCHIVE_NAME = "MASE_PST_8309f0171e3340c6aba45798c4812d54_1372858_DTM.zip"',
            downloader,
        )
        self.assertIn('EXPECTED_TILE_SUFFIX = "_DTM.tiff"', downloader)
        self.assertIn("EXPECTED_DSM_TILE_COUNT = 0", downloader)
        self.assertIn('SOURCE_CRS = "EPSG:4326"', downloader)
        self.assertIn("SOURCE_PIXEL_SIZES_DEG = (0.00001, 0.000005)", downloader)
        self.assertIn('"pixel_sizes_degrees"', downloader)
        self.assertNotIn('"tile_pixels": [1000, 1000]', downloader)
        self.assertIn(
            '"tile_dimensions": "source-defined; validated during terrain preparation"',
            downloader,
        )
        self.assertIn("immutable_source_checkpoint", downloader)
        self.assertIn("live_mase_dependency", downloader)
        self.assertNotIn("sim.mase.gov.it", downloader)

    def test_editor_build_links_landscape_import_modules(self) -> None:
        build = read("Source/YetAnotherCyclingSim/YetAnotherCyclingSim.Build.cs")
        self.assertIn('"Landscape"', build)
        self.assertIn('"LandscapeEditor"', build)


if __name__ == "__main__":
    unittest.main()
