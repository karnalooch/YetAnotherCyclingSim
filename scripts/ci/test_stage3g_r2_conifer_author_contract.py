from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
AUTHOR = ROOT / "scripts" / "ue" / "stage3g_author_conifer.py"
WRAPPER = ROOT / "scripts" / "ue" / "Invoke-YacsStage3GR2ConiferAuthor.ps1"


class Stage3GR2ConiferAuthorContractTests(unittest.TestCase):
    def test_mass_forest_source_and_profile_are_locked(self):
        source = AUTHOR.read_text(encoding="utf-8")
        self.assertIn('ASSET_ID = "fir_sapling_medium"', source)
        self.assertIn('SOURCE_MESH_NAME = "fir_sapling_medium_b_LOD0"', source)
        self.assertIn('PROFILE_NAME = "aggressive"', source)
        self.assertIn("(0.18, 0.50)", source)
        self.assertIn("(0.05, 0.22)", source)
        self.assertIn("(0.0125, 0.08)", source)

    def test_production_mesh_has_real_foliage_material_inputs(self):
        source = AUTHOR.read_text(encoding="utf-8")
        self.assertIn('("branches", "diffuse")', source)
        self.assertIn('("twigs", "alpha")', source)
        self.assertIn("MSM_TWO_SIDED_FOLIAGE", source)
        self.assertIn("BLEND_MASKED", source)
        self.assertIn("MP_OPACITY_MASK", source)

    def test_full_editor_mode_is_required_for_mesh_reduction(self):
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("Invoke-YacsUnrealCi.ps1", wrapper)
        self.assertIn("CyclingStage3World", wrapper)
        self.assertIn("pre-authoring build/Automation canary failed", wrapper)
        self.assertIn("-ExecutePythonScript=", wrapper)
        self.assertNotIn("-run=PythonScript", wrapper)
        self.assertIn("-ddc=noshared", wrapper)
        self.assertIn("-ZenDataPath=", wrapper)

    def test_wrapper_guards_expected_lod_triangle_chain(self):
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("420822, 75748, 21042, 5260", wrapper)
        self.assertIn("Content/Prototype/Environment/Stage3G/", wrapper)


if __name__ == "__main__":
    unittest.main()
