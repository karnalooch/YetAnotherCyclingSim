import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
AUDIT = ROOT / "scripts" / "ue" / "stage3g_source_asset_audit.py"
HARNESS = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GSourceAssetAudit.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "stage3g-source-asset-audit.yml"
BOULDER_AUTHOR_HARNESS = (
    ROOT / "scripts" / "ue" / "Invoke-YacsStage3GBoulderLodAuthor.ps1"
)
STAGE3G_AUTHORING_HARNESS = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GAuthoring.ps1"


class Stage3GSourceAssetAuditContract(unittest.TestCase):
    def test_audit_pins_curated_source_families(self):
        text = AUDIT.read_text(encoding="utf-8")
        for source_id in (
            "sparse_grass",
            "forrest_ground_03",
            "rocky_terrain",
            "boulder_01",
        ):
            self.assertIn(f'"{source_id}"', text)

    def test_texture_policy_is_fail_closed(self):
        text = AUDIT.read_text(encoding="utf-8")
        self.assertIn("MAX_TEXTURE_DIMENSION = 2048", text)
        self.assertIn("never_stream_enabled", text)
        self.assertIn("mip_generation_disabled", text)
        self.assertIn("non_power_of_two_source", text)
        self.assertIn("normal_map_compression_missing", text)
        self.assertIn("get_material_used_textures", text)
        self.assertIn("AssetRegistryHelpers.get_asset_registry", text)
        self.assertIn("get_dependencies", text)
        self.assertIn("on_disk_package_dependencies", text)

    def test_boulder_requires_lod_or_nanite_and_pcg_usage(self):
        text = AUDIT.read_text(encoding="utf-8")
        self.assertIn("get_num_lods()", text)
        self.assertIn("nanite_settings", text)
        self.assertIn("requires_multiple_lods_or_nanite", text)
        self.assertIn("PCG_Valley", text)
        self.assertIn("PCG_HighAlpine", text)
        self.assertIn("PCGStaticMeshSpawnerSettings", text)
        self.assertIn("missing_pcg_static_mesh_spawner_usage", text)

        importer = (
            ROOT / "scripts" / "ue" / "stage3g_import_source_assets.py"
        ).read_text(encoding="utf-8")
        self.assertIn("BOULDER_LOD_POLICY", importer)
        self.assertIn("StaticMeshEditorSubsystem", importer)
        self.assertIn("set_lods", importer)

    def test_boulder_lod_authoring_uses_editor_context(self):
        author = BOULDER_AUTHOR_HARNESS.read_text(encoding="utf-8")
        self.assertIn("-ExecutePythonScript", author)
        self.assertNotIn("-run=PythonScript", author)

        stage3g = STAGE3G_AUTHORING_HARNESS.read_text(encoding="utf-8")
        import_block = stage3g.split("[2/5] Importing canonical Stage 3G R1 assets", 1)[
            1
        ].split("[3/5] Authoring Stage 3G texture-backed materials", 1)[0]
        self.assertIn("$ImportScript", import_block)
        self.assertIn("-ExecutePythonScript", import_block)
        self.assertNotIn("-run=PythonScript", import_block)

    def test_harness_is_exact_sha_full_lfs_and_non_mutating(self):
        text = HARNESS.read_text(encoding="utf-8")
        self.assertIn("ExpectedHead", text)
        self.assertIn("git -C $RepoRoot lfs fsck", text)
        self.assertIn("Build.bat", text)
        self.assertIn("YetAnotherCyclingSimEditor", text)
        self.assertIn("-run=PythonScript", text)
        self.assertIn("-NullRHI", text)
        self.assertIn("audit-only / no asset mutation", text)
        self.assertIn("exit 1", text)

    def test_workflow_uses_trusted_runner_and_retains_failure_evidence(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", text)
        self.assertIn("lfs: true", text)
        self.assertIn("ref: $" + "{{ github.sha }}", text)
        self.assertIn("cancel-in-progress: true", text)
        self.assertIn("Invoke-YacsStage3GSourceAssetAudit.ps1", text)
        self.assertIn("SM_Stage3G_Boulder.uasset", text)
        self.assertIn("Invoke-YacsStage3GEnvironmentPerformance.ps1", text)
        self.assertIn("-SkipBuild", text)
        self.assertIn("if: $" + "{{ always() }}", text)
        self.assertIn("stage3g-source-asset-audit-", text)
        self.assertIn("retention-days: 14", text)


if __name__ == "__main__":
    unittest.main()
