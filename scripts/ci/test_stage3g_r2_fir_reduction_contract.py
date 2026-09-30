from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ue" / "stage3g_profile_fir_reduction.py"


class Stage3GR2FirReductionContractTests(unittest.TestCase):
    def test_commandlet_has_explicit_lod_backend_fallback(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            "unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)",
            source,
        )
        self.assertIn('getattr(unreal, "EditorStaticMeshLibrary", None)', source)
        self.assertIn("library.set_lods(mesh, options)", source)
        self.assertIn('"reduction_backend": reduction_backend', source)

    def test_multi_variant_source_is_isolated_before_reduction(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('staging = "{}/Import".format(profile_root)', source)
        self.assertIn(
            "unreal.EditorAssetLibrary.duplicate_asset(",
            source,
        )
        self.assertIn(
            "unreal.EditorAssetLibrary.delete_directory(staging)",
            source,
        )
        self.assertIn("unreal.collect_garbage()", source)
        self.assertIn("isolated selected mesh", source)

    def test_reduction_target_is_parameterized(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("YACS_STAGE3G_REDUCTION_ASSET_ID", source)
        self.assertIn("YACS_STAGE3G_REDUCTION_SOURCE_MESH", source)
        self.assertIn("import_selected_variant", source)

    def test_reduction_uses_full_editor_python_mode_and_isolated_zen_ddc(self):
        wrapper = (
            ROOT / "scripts" / "ue" / "Invoke-YacsStage3GR2FirReductionProfile.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("-ExecutePythonScript=", wrapper)
        self.assertNotIn("-run=PythonScript", wrapper)
        self.assertIn("-ddc=noshared", wrapper)
        self.assertIn("-ZenDataPath=", wrapper)
        self.assertIn("$ZenDataPath", wrapper)

    def test_fallback_does_not_change_profile_definitions(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"conservative": [', source)
        self.assertIn('"balanced": [', source)
        self.assertIn('"aggressive": [', source)
        self.assertIn("validate_monotonic(profile_name, after)", source)


if __name__ == "__main__":
    unittest.main()
