"""Exercise material admission before native access, cache reuse or writes."""
from contextlib import ExitStack
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch


class NativeAccessTrap:
    def __init__(self, access):
        self.access = access

    def __getattr__(self, name):
        return self.access(name)


class MaterialAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name("lesson06_unified_pipeline.py")
        spec = importlib.util.spec_from_file_location("material_admission_recipe", path)
        cls.recipe = importlib.util.module_from_spec(spec)
        # Import only the Python recipe. Houdini/OIIO are never loaded, and its
        # historical import-time environment assignments do not escape the test.
        modules = {name: ModuleType(name) for name in ("hou", "numpy", "OpenImageIO")}
        with patch.dict(sys.modules, modules), patch.dict(os.environ):
            spec.loader.exec_module(cls.recipe)

    def setUp(self):
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.access = Mock(side_effect=AssertionError("Access before material admission"))
        self.addCleanup(self.access.assert_not_called)
        for name in ("hou", "np", "oi"):
            self.patches.enter_context(patch.object(self.recipe, name, NativeAccessTrap(self.access)))
        for name in ("install_hdas", "digest", "vol_layer"):
            self.patches.enter_context(patch.object(self.recipe, name, self.access))
        for name in ("exists", "stat", "open", "mkdir", "read_bytes", "write_bytes", "write_text"):
            self.patches.enter_context(patch.object(Path, name, self.access))

    def test_direct_material_stages_reject_before_cache_or_native_access(self):
        for name in ("stage3_scree", "stage4a_grass", "stage4b_sand", "stage4c_cliff",
                     "stage4d_scree", "stage4_materials_and_tints", "stage5_idmap"):
            for force in (False, True):
                with self.subTest(entrypoint=name, force=force), self.assertRaisesRegex(
                        RuntimeError, "PEGASUS_MATERIAL_SOURCES_INCOMPLETE"):
                    getattr(self.recipe, name)(force=force)

    def test_main_rejects_every_dependent_request_before_base_or_masks(self):
        with patch.object(self.recipe, "stage1_base") as base, \
                patch.object(self.recipe, "stage2_masks") as masks:
            for stage in (None, "all", "4a", "4b", "4c", "scree", "4d", "materials", "idmap"):
                for force in (False, True):
                    argv = ["lesson06_unified_pipeline.py"]
                    if stage is not None:
                        argv += ["--stage", stage]
                    if force:
                        argv.append("--force")
                    with self.subTest(stage=stage, force=force), patch.object(sys, "argv", argv):
                        with self.assertRaisesRegex(RuntimeError, "PEGASUS_MATERIAL_SOURCES_INCOMPLETE"):
                            self.recipe.main()
            base.assert_not_called()
            masks.assert_not_called()


if __name__ == "__main__":
    unittest.main()
