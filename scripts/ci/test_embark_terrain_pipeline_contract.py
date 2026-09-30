from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
        self.assertEqual(
            examples["commit"], "78e5842c116ae0500408e22e8f7d002e12d45831"
        )
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
            "OffsetLeft->Offset.Constant = 300.0",
            "OffsetRight->Offset.Constant = 300.0",
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
            "pcgex_graph_proof.json",
            "graph_authoring_and_api_integration_only",
            "shipping_runtime_dependency",
            "Get-FileHash",
        ):
            self.assertIn(token, wrapper)
        self.assertIn(
            "It does not claim the graph has already executed against prepared SP638 data.",
            wrapper,
        )

    def test_active_workflow_tracks_pcgex_inputs_and_does_not_require_dcc(self) -> None:
        workflow = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text(
            encoding="utf-8"
        )
        for token in (
            "Prepare real SP638 authoring input",
            "passo_giau_sp638_ue_centerline.json",
            "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
            "PCGEx corridor graph authoring",
            "Invoke-YacsPassoGiauPcgExGraph.ps1",
            "YacsPassoGiauPcgExGraphCommandlet.cpp",
            "YacsPassoGiauSp638PathSettings.cpp",
            "YetAnotherCyclingSimEditor.Build.cs",
            "YetAnotherCyclingSim.uproject",
            "Plugins/PCGExtendedToolkit",
        ):
            self.assertIn(token, workflow)
        for forbidden in (
            "embark_terrain_pipeline.py preflight",
            "Materialize only DCC recipe binaries",
            "Execute full Embark terrain pipeline",
        ):
            self.assertNotIn(forbidden, workflow)


if __name__ == "__main__":
    unittest.main()
