from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RoadCaptureCameraTests(unittest.TestCase):
    def frame(
        self,
        road=(0.0, 0.0, 100.0),
        forward=(1.0, 0.0, 0.0),
        legacy=(-100.0, 20.0, 100.0),
    ):
        from scripts.ue.road_capture_camera import rider_capture_frame

        return rider_capture_frame(road, forward, legacy, 160.0)

    def test_hairpin_chord_cannot_reverse_rider_view(self):
        import math

        result = self.frame()
        self.assertGreater(result["legacy_chord_angle_deg"], 90.0)
        self.assertLess(result["legacy_chord_horizontal_alignment"], 0.0)
        self.assertEqual(result["road_forward_unit"], [1.0, 0.0, 0.0])
        self.assertEqual(result["camera_location_cm"], [0.0, 0.0, 260.0])
        self.assertTrue(all(math.isfinite(v) for v in result["target_cm"]))

    def test_position_and_height_never_change_to_avoid_geometry(self):
        result = self.frame(road=(12345.0, -222.0, 170000.0))
        self.assertEqual(result["camera_location_cm"], [12345.0, -222.0, 170160.0])
        self.assertFalse(result["position_adjusted_for_visibility"])
        self.assertFalse(result["route_or_terrain_modified"])

    def test_grade_and_direction_are_preserved(self):
        import math

        result = self.frame(forward=(0.0, -20.0, 2.0))
        forward = result["road_forward_unit"]
        self.assertAlmostEqual(math.hypot(*forward), 1.0)
        self.assertAlmostEqual(forward[2] / -forward[1], 0.1)
        self.assertEqual(forward[0], 0.0)

    def test_translation_and_tangent_scale_do_not_change_orientation(self):
        a = self.frame(forward=(3.0, 4.0, 1.0))
        b = self.frame(road=(200000.0, 300000.0, 400000.0), forward=(30.0, 40.0, 10.0))
        for first, second in zip(a["road_forward_unit"], b["road_forward_unit"]):
            self.assertAlmostEqual(first, second)

    def test_invalid_direction_fails_closed(self):
        import math

        for forward in (
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (math.nan, 1.0, 0.0),
            (True, 0.0, 0.0),
        ):
            with self.subTest(forward=forward), self.assertRaises(ValueError):
                self.frame(forward=forward)

    def test_invalid_eye_height_fails_closed(self):
        import math
        from scripts.ue.road_capture_camera import rider_capture_frame

        for height in (0.0, -1.0, math.inf, math.nan, True):
            with self.subTest(height=height), self.assertRaises(ValueError):
                rider_capture_frame((0, 0, 0), (1, 0, 0), (2, 0, 0), height)

    def test_degenerate_legacy_target_does_not_control_new_frame(self):
        result = self.frame(legacy=(0.0, 0.0, 100.0))
        self.assertIsNone(result["legacy_chord_angle_deg"])
        self.assertEqual(result["road_forward_unit"], [1.0, 0.0, 0.0])

    def test_capture_uses_the_original_camera_station_before_slice(self):
        capture = (
            ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py"
        ).read_text()
        self.assertIn(
            "road_forward = spline.get_direction_at_distance_along_spline(\n        camera_distance_cm,",
            capture,
        )
        self.assertLess(
            capture.index(
                "road_forward = spline.get_direction_at_distance_along_spline"
            ),
            capture.index("_replace_with_slice(spline, landscape_slice)"),
        )
        self.assertIn('"camera_frame": camera_frame', capture)
        self.assertIn("request_height_mips=macro_landscape_visible", capture)


class EmbarkTerrainPipelineContractTests(unittest.TestCase):
    def test_owner_embark_directive_allows_license_clean_pattern_substitution(
        self,
    ) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for token in (
            "### Explicit Embark-mode directive",
            "production-proven Embark pattern end-to-end",
            "Do not silently down-scope",
            "strongest **public production pattern and boundary**",
            "license-clean Unreal-native or open-source implementation",
            "do **not** invent its node graph",
        ):
            self.assertIn(token, agents)

    def test_world_bible_records_pcgex_first_bounded_substitution(self) -> None:
        bible = (ROOT / "docs/WORLD_BUILDING_BIBLE.md").read_text(encoding="utf-8")
        for token in (
            "Passo Giau Embark escalation — selected after native visual failure",
            "Current bounded substitution — PCGEx-first proof",
            "PCGEx is not claimed to be an Embark Studios dependency",
            "Base_DTM",
            "Road_Earthworks",
            "route or physics authority",
            "Houdini/Gaea",
            "rider-camera",
        ):
            self.assertIn(token, bible)

    def test_pcgex_manifest_pins_authoring_dependency_and_authority_boundaries(
        self,
    ) -> None:
        config = json.loads(
            (ROOT / "worldgen/embark/pcgex/passo_giau_corridor.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["pipeline_id"], "passo-giau-embark-pcgex-v2")
        self.assertTrue(config["architecture"]["authoring_only"])
        self.assertFalse(config["architecture"]["shipping_runtime_dependency"])
        self.assertEqual(
            config["pcgex"]["commit"],
            "39a8f1bdc65b2c4613a1e87b71d93b4576db0a66",
        )
        self.assertEqual(config["pcgex"]["version_name"], "0.79")
        self.assertEqual(config["pcgex"]["engine_version"], "5.8.0")
        self.assertEqual(config["pcgex"]["license"], "MIT")
        examples = config["reference_examples"]
        self.assertEqual(
            examples["repository"], "https://github.com/PCGEx/PCGExExampleProject"
        )
        self.assertEqual(examples["commit"], "78e5842c116ae0500408e22e8f7d002e12d45831")
        self.assertEqual(examples["engine_version"], "5.8")
        self.assertIn("reference_only", examples["use_policy"])
        self.assertEqual(
            examples["assets"]["road_corridor"],
            "Content/Examples/ConnectRoad/PCGEx_ConnectRoad.uasset",
        )
        self.assertEqual(
            examples["assets"]["landscape_tensors"],
            "Content/Categories/Tensors/LandscapeTensors/PCGEx_LandscapeTensors.uasset",
        )
        self.assertEqual(
            examples["assets"]["cliff"],
            "Content/Categories/Misc/Isolines/PCGEx_Cliff.uasset",
        )
        self.assertEqual(
            config["graph"]["asset"],
            "/Game/WorldGen/PCGEx/PCG_PassoGiau_SP638_Corridor",
        )
        self.assertEqual(
            config["graph"]["generator_commandlet"], "YacsPassoGiauPcgExGraph"
        )
        classes = [node["class"] for node in config["graph"]["nodes"]]
        self.assertEqual(
            classes,
            [
                "UYacsPassoGiauSp638PathSettings",
                "UPCGExResamplePathSettings",
                "UPCGExSmoothSettings",
                "UPCGExOffsetPathSettings",
                "UPCGExOffsetPathSettings",
            ],
        )
        invariants = config["invariants"]
        self.assertTrue(invariants["preserve_route_xy"])
        self.assertTrue(invariants["preserve_physics_authority"])
        self.assertTrue(invariants["preserve_source_provenance"])
        self.assertTrue(invariants["base_dtm_is_non_destructive"])
        self.assertTrue(invariants["road_earthworks_are_separate"])
        self.assertTrue(invariants["forbid_houdini_or_gaea_as_required_dependencies"])
        self.assertTrue(invariants["forbid_pcgex_as_route_or_physics_authority"])
        self.assertTrue(invariants["pcgex_spatial_features_are_non_authoritative"])
        self.assertTrue(invariants["verified_case_learning_is_yacs_owned"])
        self.assertTrue(invariants["forbid_unreviewed_proof_as_learning_case"])

        adaptive = config["graph"]["adaptive_terrain_feature_role"]
        self.assertEqual(
            adaptive["contract"],
            "worldgen/terrain/adaptive_terrain_feature_contract.json",
        )
        self.assertIn("filters", adaptive["permitted_pcgex_capabilities"])
        self.assertIn("sampling", adaptive["permitted_pcgex_capabilities"])
        self.assertIn("heuristics", adaptive["permitted_pcgex_capabilities"])
        self.assertIn("route_authority", adaptive["forbidden_responsibilities"])
        self.assertIn(
            "automatic_verified_case_promotion",
            adaptive["forbidden_responsibilities"],
        )

        feature_contract = json.loads(
            (
                ROOT / "worldgen/terrain/adaptive_terrain_feature_contract.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            feature_contract["preferred_spatial_producer"],
            "pcgex_spatial_analysis",
        )
        boundary = feature_contract["producer_boundary"]
        self.assertTrue(boundary["canonical_road_xy_preserved"])
        self.assertFalse(boundary["authoritative_route_geometry"])
        self.assertFalse(boundary["authoritative_physics"])
        self.assertIn(
            "nearest_branch_xy_m",
            feature_contract["required_features"],
        )
        self.assertIn(
            "curvature_radius_m",
            feature_contract["required_features"],
        )

    def test_dependency_ledger_makes_pcgex_current_and_dcc_optional(self) -> None:
        ledger = (ROOT / "docs/legal/DEPENDENCY_PROVENANCE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("PCGEx / PCG Extended Toolkit", ledger)
        self.assertIn("**approved pinned authoring dependency**", ledger)
        self.assertIn("39a8f1bdc65b2c4613a1e87b71d93b4576db0a66", ledger)
        self.assertIn("**reference / optional escalation**", ledger)
        self.assertIn("not required by #287/#288", ledger)

    def test_pcgex_bootstrap_is_exact_sha_clean_and_credential_free(self) -> None:
        bootstrap = (ROOT / "scripts/worldgen/Bootstrap-YacsPcgEx.ps1").read_text(
            encoding="utf-8"
        )
        for token in (
            "https://github.com/PCGEx/PCGExtendedToolkit.git",
            "39a8f1bdc65b2c4613a1e87b71d93b4576db0a66",
            "$ExpectedVersion = '0.79'",
            "$ExpectedEngineVersion = '5.8.0'",
            "$ExpectedLicenseFirstLine = 'MIT License'",
            "shipping_runtime_dependency = $false",
            "clean_checkout",
        ):
            self.assertIn(token, bootstrap)
        self.assertNotIn("password=", bootstrap.lower())
        self.assertNotIn("client_secret=", bootstrap.lower())

        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("Plugins/PCGExtendedToolkit/", gitignore)

    def test_unreal_project_and_editor_module_keep_pcgex_optional(self) -> None:
        uproject = json.loads(
            (ROOT / "YetAnotherCyclingSim.uproject").read_text(encoding="utf-8")
        )
        plugin = next(
            item for item in uproject["Plugins"] if item["Name"] == "PCGExtendedToolkit"
        )
        self.assertTrue(plugin["Enabled"])
        self.assertTrue(plugin["Optional"])
        self.assertEqual(plugin["TargetAllowList"], ["Editor"])

        build = (
            ROOT
            / "Source/YetAnotherCyclingSimEditor/YetAnotherCyclingSimEditor.Build.cs"
        ).read_text(encoding="utf-8")
        for token in (
            "Plugins",
            "PCGExtendedToolkit",
            "YACS_WITH_PCGEX=",
            "PCGExCore",
            "PCGExBlending",
            "PCGExFoundations",
            "PCGExElementsPaths",
            "PCGExElementsSampling",
            "PCGExElementsTopology",
        ):
            self.assertIn(token, build)

    def test_pcg_source_adapter_enforces_presentation_only_policy(self) -> None:
        source = (
            ROOT
            / "Source/YetAnotherCyclingSimEditor/Private/PCG/YacsPassoGiauSp638PathSettings.cpp"
        ).read_text(encoding="utf-8")
        for token in (
            "presentation_only",
            "authoritative_route_geometry",
            "authoritative_physics",
            'TEXT("ue_x_cm")',
            'TEXT("ue_y_cm")',
            'TEXT("ue_z_cm")',
            "YACS.SP638.PresentationOnly",
            "YACS.Source.RegioneDelVeneto",
        ):
            self.assertIn(token, source)

    def test_graph_commandlet_authors_bounded_deterministic_first_spike(self) -> None:
        source = (
            ROOT
            / "Source/YetAnotherCyclingSimEditor/Private/PCG/YacsPassoGiauPcgExGraphCommandlet.cpp"
        ).read_text(encoding="utf-8")
        for token in (
            "#if YACS_WITH_PCGEX",
            "UPCGExResamplePathSettings",
            "UPCGExSmoothSettings",
            "UPCGExOffsetPathSettings",
            "Resample->SampleLength.Constant = 100.0",
            "Smooth->bPreserveStart = true",
            "Smooth->bPreserveEnd = true",
            "Smooth->BlendingInterface = EPCGExBlendingInterface::Monolithic",
            "FPCGExBlendingDetails(EPCGExBlendingType::Average)",
            "OffsetLeft->Offset.Constant = 300.0",
            "OffsetRight->Offset.Constant = 300.0",
            "Graph->AddLabeledEdge(SmoothNode, PathPin, OutputNode, GraphOutputPin)",
            "UEditorLoadingAndSavingUtils::NewBlankMap(false)",
            "UBoxComponent",
            "YacsPcgExSchedulerBounds",
            "Component->SetGraphLocal(Graph)",
            "Component->GenerateLocal(true)",
            "FWorldPartitionHelpers::FakeEngineTick(World)",
            "Component->GetGeneratedGraphOutput()",
            "YACS PCGEx corridor graph executed:",
            "YACS PCGEx corridor graph authored:",
            "SP638 presentation -> resample 1m -> bounded smooth -> +/-3m offsets.",
        ):
            self.assertIn(token, source)

    def test_exact_sha_graph_wrapper_proves_api_integration_without_overclaiming(
        self,
    ) -> None:
        wrapper = (ROOT / "scripts/ue/Invoke-YacsPassoGiauPcgExGraph.ps1").read_text(
            encoding="utf-8"
        )
        for token in (
            "Bootstrap-YacsPcgEx.ps1",
            "YetAnotherCyclingSimEditor",
            "-run=YacsPassoGiauPcgExGraph",
            "-Execute",
            "pcgex_graph_output.json",
            "pcgex_graph_proof.json",
            "graph_execution_against_prepared_sp638",
            "point_dataset_count",
            "total_point_count",
            "shipping_runtime_dependency",
            "Get-FileHash",
        ):
            self.assertIn(token, wrapper)

    def test_gate_c_surface_ownership_matrix_is_fail_closed(self) -> None:
        capture = (
            ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py"
        ).read_text(encoding="utf-8")
        wrapper = (
            ROOT / "scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1"
        ).read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text(
            encoding="utf-8"
        )
        extractor = (
            ROOT / "scripts/assets/extract_passo_giau_native_dtm_patch.py"
        ).read_text(encoding="utf-8")
        manifest_path = ROOT / "worldgen/embark/passo_giau_terrain_pipeline.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertIn(
            'DIAGNOSTIC_VARIANT_ENV = "YACS_SP638_LOCAL_CORRIDOR_VARIANT"', capture
        )
        for variant in (
            '"A": {',
            '"B": {',
            '"C": {',
            '"D": {',
            '"E": {',
            '"C3": {',
            '"H": {',
        ):
            self.assertIn(variant, capture)
        self.assertIn('"Base_DTM" not in edit_layer_names', capture)
        self.assertIn('name == "Road_Earthworks"', capture)
        self.assertIn("get_edit_layers_bp()", capture)
        self.assertNotIn("landscape.get_edit_layers()", capture)
        self.assertIn('"selected_earthworks_layer": edit_layer_name', capture)
        self.assertNotIn("edit_layer_names[0]", capture)
        self.assertIn("set_visibility(macro_landscape_visible, True)", capture)

        self.assertIn("[ValidateSet('A','B','C','D','E','C3','F','G','H')]", wrapper)
        self.assertIn("if ($Variant -in @('C3','H'))", wrapper)
        self.assertIn("$ExpectedMacro = $Variant -in @('A','B','E','F','G')", wrapper)
        self.assertIn("$ExpectedLocal = $Variant -in @('C','D','E')", wrapper)
        self.assertIn("$ExpectedCorridor = $Variant -in @('B','D','E','G')", wrapper)
        self.assertIn("$Variant -eq 'H'", wrapper)
        self.assertIn("selected_earthworks_layer -ne 'Road_Earthworks'", wrapper)
        for token in (
            "Release-YacsUnrealWorkspaceLocks.ps1",
            "$CleanupWorkspace = $RepoRoot",
            "$env:GITHUB_WORKSPACE",
            "& $WorkspaceCleanup -Workspace $CleanupWorkspace",
            "$MinFreeVirtualGb = 8.0",
            "$ResourceHeadroomWaitSec = 15",
            "render_resource_headroom.txt",
            "SP638 render resource gate",
            "Refusing to launch UnrealEditor",
        ):
            self.assertIn(token, wrapper)

        self.assertIn("$variants = @('A','B','C','D','E')", workflow)
        self.assertIn("foreach ($variant in $variants)", workflow)
        self.assertIn("-Variant $variant", workflow)
        self.assertIn("extract_passo_giau_native_dtm_patch.py", workflow)
        self.assertIn("-Variant C3", workflow)
        self.assertIn("-Variant H", workflow)
        self.assertIn("apply_corridor_constraints_to_height_grid", capture)
        self.assertIn("make_road_clearance_profiles", capture)
        self.assertIn(
            '"single_local_ground_owner": constraint_metrics is not None', capture
        )
        self.assertIn('"shoulders_capped_to_road_edge_height": True', capture)
        self.assertIn('"asphalt_vertical_clearance_m"', capture)
        self.assertIn("asphalt-edge clearance apron", wrapper)
        self.assertIn("YACS_NATIVE_DTM_PATCH_METADATA", capture)
        self.assertIn("prepared native metric DTM bounded patch", capture)
        self.assertIn("landscape_collision_sampled", capture)
        self.assertIn("Native-DTM proof did not use the native metric DTM.", wrapper)
        self.assertIn("proof_hairpin_focus", extractor)
        self.assertIn("focus_epsg32632_m", extractor)
        self.assertNotIn("source_station_m", extractor)
        self.assertNotIn("choose_hairpin", extractor)
        self.assertIn("_validate_pcgex_proof_focus", capture)
        self.assertIn("Gate C PCGEx proof focus drifted", capture)
        proof_location = manifest["proof_locations"]["gate_c_hairpin"]
        self.assertEqual(proof_location["focus_ue_m"], [5605.084, 1821.661])
        self.assertEqual(
            proof_location["focus_epsg32632_m"],
            [736011.671, 5154425.114],
        )
        self.assertEqual(
            proof_location["reference_pcgex_focus_distance_m"],
            15450.0,
        )
        self.assertEqual(proof_location["reference_workflow_run_id"], 36764749645)
        self.assertLessEqual(
            proof_location["max_render_focus_xy_drift_m"],
            2.0,
        )

    def test_active_workflow_tracks_pcgex_inputs_and_does_not_require_dcc(self) -> None:
        workflow = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text(
            encoding="utf-8"
        )
        for token in (
            "Prepare real SP638 authoring input",
            "passo_giau_sp638_ue_centerline.json",
            "passo_giau_native_dtm_patch.json",
            "extract_passo_giau_native_dtm_patch.py",
            "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
            "Remove-Item -LiteralPath $spikePath -Force",
            "version https://git-lfs.github.com/spec/v1",
            "Passo Giau map remained materialized before code-only checkout guard.",
            "PCGEx corridor graph authoring",
            "Invoke-YacsPassoGiauPcgExGraph.ps1",
            "Render PCGEx rider-close corridor proof",
            "Invoke-YacsSp638LocalCorridorVisualProof.ps1",
            "PcgExExecutionOutput",
            "YacsPassoGiauPcgExGraphCommandlet.cpp",
            "YacsPassoGiauSp638PathSettings.cpp",
            "YetAnotherCyclingSimEditor.Build.cs",
            "YetAnotherCyclingSim.uproject",
            "Plugins/PCGExtendedToolkit",
            "PCGEx corridor deviation report",
            "validate_pcgex_corridor_output.py",
            "pcgex_corridor_deviation.json",
        ):
            self.assertIn(token, workflow)
        rider_wrapper = (
            ROOT / "scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1"
        ).read_text(encoding="utf-8")
        for token in (
            "AdditionalAllowedDirtyPaths",
            "Content/WorldGen/",
            "PcgExExecutionOutput",
        ):
            self.assertIn(token, rider_wrapper)

        pcgex_wrapper = (
            ROOT / "scripts/ue/Invoke-YacsPassoGiauPcgExGraph.ps1"
        ).read_text(encoding="utf-8")
        for token in (
            "PCGEx conservative UBT profile",
            "<bAllowUBAExecutor>false</bAllowUBAExecutor>",
            "<bAllowUBALocalExecutor>false</bAllowUBALocalExecutor>",
            "<MaxParallelActions>$MaxParallelActions</MaxParallelActions>",
            "$Context.Machine.FreeVirtualGb",
        ):
            self.assertIn(token, pcgex_wrapper)

        for forbidden in (
            "embark_terrain_pipeline.py preflight",
            "Materialize only DCC recipe binaries",
            "Execute full Embark terrain pipeline",
            "AdditionalAllowedDirtyPaths",
        ):
            self.assertNotIn(forbidden, workflow)

    def test_surface_isolation_is_an_explicit_complete_two_by_two(self) -> None:
        import ast

        capture = (
            ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(capture)
        variants = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "DIAGNOSTIC_VARIANTS"
                for target in node.targets
            )
        )
        for name, cut_fill, corridor in (
            ("A", False, False),
            ("F", True, False),
            ("G", False, True),
            ("B", True, True),
        ):
            with self.subTest(variant=name):
                self.assertEqual(
                    variants[name],
                    {
                        "macro_landscape_visible": True,
                        "local_terrain_visible": False,
                        "corridor_visible": corridor,
                        "apply_landscape_cut_fill": cut_fill,
                    },
                )
        wrapper = (
            ROOT / "scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1"
        ).read_text()
        self.assertIn("$ExpectedCorridor = $Variant -in @('B','D','E','G')", wrapper)
        self.assertIn("$ExpectedCutFill = $Variant -in @('B','C','D','E','F')", wrapper)
        self.assertIn('"persisted_map_layers_preserved": True', capture)

    def test_surface_isolation_is_opt_in_and_does_not_replace_baseline(self) -> None:
        workflow = (
            ROOT / ".github/workflows/passo-giau-embark-terrain.yml"
        ).read_text()
        self.assertIn("include_surface_isolation:", workflow)
        option = workflow.split("      include_surface_isolation:", 1)[1].split(
            "permissions:", 1
        )[0]
        self.assertIn("default: false", option)
        self.assertIn("type: boolean", option)
        self.assertIn("$variants = @('A','B','C','D','E')", workflow)
        self.assertIn(
            "if ($env:YACS_SURFACE_ISOLATION -eq 'true') {\n            $variants += @('F','G')",
            workflow,
        )
        self.assertIn("-Variant C3", workflow)
        self.assertIn("-Variant H", workflow)
        self.assertIn(
            '"surface_isolation_requested": os.environ["YACS_SURFACE_ISOLATION"] == "true"',
            workflow,
        )

    def test_active_workflow_is_not_bound_to_merged_feature_branch(self) -> None:
        workflow = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("feat/287-embark-terrain-pipeline", workflow)
        for token in (
            "branches-ignore:",
            "- main",
            "- 'dependabot/**'",
            "github.repository == 'karnalooch/YetAnotherCyclingSim'",
            "github.event_name == 'push'",
            "github.event_name == 'workflow_dispatch'",
        ):
            self.assertIn(token, workflow)

    def test_embark_proof_uses_fingerprinted_build_reuse_fail_closed(self) -> None:
        workflow = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text(
            encoding="utf-8"
        )
        classifier = (ROOT / "scripts/ci/classify_changes.py").read_text(
            encoding="utf-8"
        )
        wrapper = (ROOT / "scripts/ue/Invoke-YacsPassoGiauPcgExGraph.ps1").read_text(
            encoding="utf-8"
        )

        for token in (
            "Classify Embark proof cost",
            "--embark-terrain-proof",
            "compile_fingerprint",
            "proof_mode",
            "Resolve compile-fingerprint cache",
            "PCGEx compile cache HIT",
            "PCGEx compile required",
            "compile_kind",
            "environment_identity",
            "legacy-cache-schema-migration",
            "compile-fingerprint-mismatch",
            "environment-identity-mismatch",
            "pcgex-pin-mismatch",
            "skip_build",
            "clean: false",
            "Saved/BuildCache/PCGEx/compile-state.json",
        ):
            self.assertIn(token, workflow)

        for token in (
            "classify_embark_terrain_proof",
            "embark_terrain_compile_fingerprint",
            '"heavy"',
            '"render"',
            '"cheap"',
            "YetAnotherCyclingSim.uproject",
            "pcgex_commit",
            "engine_version",
        ):
            self.assertIn(token, classifier)

        for token in (
            "[switch] $SkipBuild",
            "validated compile fingerprint cache hit",
            "Compile-fingerprint cache is missing YetAnotherCyclingSimEditor binaries.",
            "Compile-fingerprint cache is missing PCGEx plugin binaries.",
        ):
            self.assertIn(token, wrapper)

        self.assertIn(
            '$UbtConfig = @"\n<?xml version="1.0" encoding="utf-8" ?>',
            wrapper,
        )

        self.assertIn(
            "passo-giau-m3-pcgex-input-${{ github.run_id }}",
            workflow,
        )
        self.assertNotIn(
            "passo-giau-m3-pcgex-input-${{ github.run_id }}-${{ github.run_attempt }}",
            workflow,
        )

        self.assertIn(
            "Resolve-YacsUnrealBuildEnvironment.ps1",
            workflow,
        )
        self.assertIn(
            "schema_version = 2",
            workflow,
        )
        self.assertIn(
            "$purgeProjectBuild = $false",
            workflow,
        )
        self.assertNotIn(
            "if ($mode -ne 'heavy'",
            workflow,
        )

        self.assertNotIn(
            "Remove-Item -LiteralPath $pcgex -Recurse -Force",
            workflow,
        )


class LandscapeCaptureReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock

        self.events = []
        self.landscape = SimpleNamespace(
            get_path_name=lambda: "/Game/Map.Map:Landscape"
        )
        self.texture = SimpleNamespace(
            get_path_name=lambda: "/Game/Map.Map:Landscape.Heightmap_0",
            get_editor_property=lambda name: "heightmap",
        )
        self.state = {
            "texture": self.texture.get_path_name(),
            "is_default_texture": False,
            "is_compiling": False,
            "mips": 10,
            "resident_mips": 7,
        }
        self.viewport = SimpleNamespace(
            get_level_viewport_camera_info=lambda: ("old-position", "old-rotation"),
            set_level_viewport_camera_info=lambda *args: self.events.append(
                ("view", args)
            ),
        )
        self.api = SimpleNamespace(
            Texture2D=object,
            UnrealEditorSubsystem=object,
            TextureGroup=SimpleNamespace(TEXTUREGROUP_TERRAIN_HEIGHTMAP="heightmap"),
            ObjectIterator=lambda _: [self.texture],
            get_editor_subsystem=lambda _: self.viewport,
            YacsTextureAuditLibrary=SimpleNamespace(
                describe_texture=lambda _: json.dumps(self.state)
            ),
            AutomationLibrary=SimpleNamespace(
                finish_loading_before_screenshot=Mock(
                    side_effect=lambda: self.events.append(("barrier", ()))
                )
            ),
        )

    def capture(self, output, **kwargs):
        from scripts.ue.prepare_landscape_capture import prepare_capture

        return prepare_capture(
            self.api,
            self.landscape,
            "rider-position",
            "rider-rotation",
            output,
            **kwargs,
        )

    def test_actual_view_is_set_before_native_barrier_and_recorded(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            report = self.capture(Path(directory))
            self.assertEqual(
                self.events,
                [("view", ("rider-position", "rider-rotation")), ("barrier", ())],
            )
            self.assertEqual(report["status"], "NATIVE_LOADING_COMPLETED")
            self.assertFalse(report["terrain_quality_accepted"])
            self.assertFalse(report["height_edits_applied"])
            self.assertFalse(report["saved_to_map"])
            self.assertEqual(report["textures_after"][0]["resident_mips"], 7)
            self.assertEqual(
                json.loads((Path(directory) / "capture-readiness.json").read_text()),
                report,
            )

    def test_missing_viewport_fails_before_barrier(self):
        import tempfile

        self.api.get_editor_subsystem = lambda _: None
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "active level viewport"):
                self.capture(Path(directory))
            self.api.AutomationLibrary.finish_loading_before_screenshot.assert_not_called()
            self.assertEqual(
                json.loads((Path(directory) / "capture-readiness.json").read_text())[
                    "status"
                ],
                "FAILED",
            )

    def test_unrelated_package_textures_are_excluded(self):
        import tempfile
        from types import SimpleNamespace

        foreign = SimpleNamespace(get_path_name=lambda: "/Game/MapOther.MapOther:T")
        self.api.ObjectIterator = lambda _: [foreign, self.texture]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(len(self.capture(Path(directory))["textures_after"]), 1)

    def test_no_height_textures_fails_closed(self):
        import tempfile

        self.api.ObjectIterator = lambda _: []
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "No map-owned"):
                self.capture(Path(directory))
            self.api.AutomationLibrary.finish_loading_before_screenshot.assert_not_called()

    def test_native_barrier_error_is_not_swallowed(self):
        import tempfile

        self.api.AutomationLibrary.finish_loading_before_screenshot.side_effect = (
            RuntimeError("loading failed")
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "loading failed"):
                self.capture(Path(directory))
            self.assertNotIn(
                "native_loading_barrier_completed",
                json.loads((Path(directory) / "capture-readiness.json").read_text()),
            )

    def test_readback_error_is_not_a_success(self):
        import tempfile

        self.state = {"error": "missing derived data"}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "missing derived data"):
                self.capture(Path(directory))

    def test_unready_texture_rejects_capture(self):
        import tempfile

        self.state["is_default_texture"] = True
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "not ready"):
                self.capture(Path(directory))

    def test_native_mip_request_waits_and_records_full_residency(self):
        import tempfile
        from unittest.mock import Mock

        self.texture.set_force_mip_levels_to_be_resident = Mock(
            side_effect=lambda *args: self.events.append(("mip-request", args))
        )

        def complete_requested_streaming():
            self.events.append(("barrier", ()))
            if self.texture.set_force_mip_levels_to_be_resident.called:
                self.state["resident_mips"] = 10

        self.api.AutomationLibrary.finish_loading_before_screenshot.side_effect = (
            complete_requested_streaming
        )
        with tempfile.TemporaryDirectory() as directory:
            report = self.capture(Path(directory), request_height_mips=True)
            self.assertEqual(report["status"], "NATIVE_LOADING_AND_MIPS_READY")
            self.assertEqual(
                report["textures_before_mip_request"][0]["resident_mips"], 7
            )
            self.assertEqual(report["textures_after"][0]["resident_mips"], 10)
            self.assertEqual(report["mip_residency_request_count"], 1)
            self.texture.set_force_mip_levels_to_be_resident.assert_called_once_with(
                120.0, 0
            )
            self.assertEqual(
                [event[0] for event in self.events],
                ["view", "barrier", "mip-request", "barrier"],
            )
            self.assertFalse(report["terrain_quality_accepted"])

    def test_partial_residency_fails_and_releases_transient_request(self):
        import tempfile
        from unittest.mock import Mock, call

        self.texture.set_force_mip_levels_to_be_resident = Mock()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, "not fully resident"):
                self.capture(Path(directory), request_height_mips=True)
            self.assertEqual(
                self.texture.set_force_mip_levels_to_be_resident.call_args_list,
                [call(120.0, 0), call(0.0, 0)],
            )
            report = json.loads(
                (Path(directory) / "capture-readiness.json").read_text()
            )
            self.assertEqual(report["status"], "FAILED")
            self.assertEqual(report["textures_after"][0]["resident_mips"], 7)

    def test_controls_do_not_request_residency(self):
        import tempfile
        from unittest.mock import Mock

        self.texture.set_force_mip_levels_to_be_resident = Mock()
        with tempfile.TemporaryDirectory() as directory:
            report = self.capture(Path(directory))
            self.texture.set_force_mip_levels_to_be_resident.assert_not_called()
            self.assertFalse(report["height_mip_lease_requested"])
            self.assertEqual(report["height_mip_lease_seconds"], 0.0)
        capture = (
            ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py"
        ).read_text()
        self.assertIn("request_height_mips=macro_landscape_visible", capture)

    def test_only_visible_macro_variants_request_height_mips(self):
        import ast

        capture = (
            ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py"
        ).read_text()
        tree = ast.parse(capture)
        variants = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "DIAGNOSTIC_VARIANTS"
                for target in node.targets
            )
        )
        self.assertEqual(
            {
                name
                for name, policy in variants.items()
                if policy["macro_landscape_visible"]
            },
            {"A", "B", "E", "F", "G"},
        )
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        calls = [
            node
            for node in ast.walk(main)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "prepare_capture"
        ]
        self.assertEqual(len(calls), 1)
        option = next(
            keyword.value
            for keyword in calls[0].keywords
            if keyword.arg == "request_height_mips"
        )
        self.assertIsInstance(option, ast.Name)
        self.assertEqual(option.id, "macro_landscape_visible")
        self.assertIn(
            'macro_landscape_visible = bool(variant["macro_landscape_visible"])',
            capture,
        )

    def test_capture_hook_is_after_camera_and_before_screenshot_for_every_variant(self):
        capture = (
            ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py"
        ).read_text()
        start = capture.index(
            '    _proof_data["capture_preparation"] = prepare_capture('
        )
        self.assertLess(
            capture.index(
                'camera_component.set_editor_property("field_of_view", 76.0)'
            ),
            start,
        )
        self.assertLess(
            start,
            capture.index(
                "    _task = unreal.AutomationLibrary.take_high_res_screenshot(", start
            ),
        )
        block = capture[
            start : capture.index(
                "    _task = unreal.AutomationLibrary.take_high_res_screenshot(", start
            )
        ]
        self.assertNotIn("if variant_name", block)
        self.assertIn("camera_location, camera_rotation, _proof_path.parent", block)

    def test_base_layer_comparison_prepares_before_second_capture(self):
        import ast

        capture = (
            ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py"
        ).read_text()
        tree = ast.parse(capture)
        helper = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_advance_layer_comparison"
        )
        calls = [node for node in ast.walk(helper) if isinstance(node, ast.Call)]
        prepare = next(
            node
            for node in calls
            if isinstance(node.func, ast.Name) and node.func.id == "prepare_capture"
        )
        shot = next(
            node
            for node in calls
            if isinstance(node.func, ast.Attribute)
            and node.func.attr == "take_high_res_screenshot"
        )
        self.assertLess(prepare.lineno, shot.lineno)
        option = next(
            k.value for k in prepare.keywords if k.arg == "request_height_mips"
        )
        self.assertIs(option.value, True)


if __name__ == "__main__":
    unittest.main()
