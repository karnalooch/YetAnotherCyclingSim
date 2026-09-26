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

    def test_fallback_does_not_change_profile_definitions(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"conservative": [', source)
        self.assertIn('"balanced": [', source)
        self.assertIn('"aggressive": [', source)
        self.assertIn("validate_monotonic(profile_name, after)", source)


if __name__ == "__main__":
    unittest.main()
