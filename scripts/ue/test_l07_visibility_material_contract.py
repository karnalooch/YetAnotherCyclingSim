"""Hosted non-execution contract for isolated Unreal L07 hole material."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
AUTHOR = ROOT / "scripts/ue/l07_visibility_material_author.py"
BAKE = ROOT / "scripts/ue/bake_lesson07_landscape.py"
TRANSFER = ROOT / "scripts/houdini/prepare_lesson07_ue_transfer.py"


class L07VisibilityMaterialContract(unittest.TestCase):
    def test_native_author_script_compiles_without_importing_unreal(self):
        ast.parse(AUTHOR.read_text(encoding="utf-8"))

    def test_audit_is_default_and_apply_stays_out_of_canonical_project(self):
        content = AUTHOR.read_text(encoding="utf-8")
        for required in (
            'MODE = os.environ.get("YACS_L07_VISIBILITY_MATERIAL_MODE", "AUDIT")',
            'MODE == "APPLY"',
            'D:/yacs/work',
            "unreal.BlendMode.BLEND_MASKED",
            "MaterialExpressionLandscapeVisibilityMask",
            "MP_OPACITY_MASK",
            "saved_world_before_sha256",
        ):
            self.assertIn(required, content)

    def test_bake_requires_actual_masked_material_and_isolated_project(self):
        code = BAKE.read_text(encoding="utf-8")
        self.assertIn("unreal.BlendMode.BLEND_MASKED", code)
        self.assertIn("MaterialExpressionLandscapeVisibilityMask", code)
        self.assertIn("YACS_LESSON07_REPAIR_MANIFEST", code)
        self.assertIn("D:/yacs/work", code)

    def test_houdini_uses_sidefx_22_hole_attribute_and_keeps_pending(self):
        code = TRANSFER.read_text(encoding="utf-8")
        self.assertIn('attrs["unreal_material_hole"]', code)
        self.assertIn('"masked_material_ue_verified": False', code)
        self.assertIn('"performance_1080p60_verified": False', code)


if __name__ == "__main__":
    unittest.main()
