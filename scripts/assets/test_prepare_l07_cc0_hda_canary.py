import importlib.util
import tempfile
from pathlib import Path
import unittest

from test_build_l07_polyhaven_bindings import fixture, module as binding_module, SELECTION

PATH = Path(__file__).parents[1] / "houdini/prepare_l07_cc0_hda_canary.py"
spec = importlib.util.spec_from_file_location("l07hdacanary", PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CanaryPreflightTests(unittest.TestCase):
    def test_only_approved_rock_maps_are_bound(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            result = module.approved_paths(binding_module.prepare(root, SELECTION), root)
            self.assertEqual(set(result), {"filename1", "filename2", "filename3"})
            self.assertTrue(result["filename1"].endswith("dark_rock_diff_4k.png"))

    def test_reject_changed_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            binding = binding_module.prepare(root, SELECTION)
            Path(binding["houdini"][0]["files"]["rough"]["path"]).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "source changed"):
                module.approved_paths(binding, root)

    def test_wrong_material_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            binding = binding_module.prepare(root, SELECTION)
            binding["houdini"][0]["slug"] = "wrong"
            with self.assertRaisesRegex(ValueError, "Unexpected native"):
                module.approved_paths(binding, root)

    def test_volume_check_requires_rgb(self):
        before = {"height": {}, "mask": {}}
        with self.assertRaisesRegex(ValueError, "did not generate RGB"):
            module.verify_canary_volumes(before, before)

    def test_volume_check_refuses_height_change(self):
        before = {"height": {"resolution": [256, 256, 1], "voxel_sha256": "X"},
                  "mask": {"resolution": [256, 256, 1], "voxel_sha256": "M"}}
        after = {**before, "height": {"resolution": [256, 256, 1], "voxel_sha256": "Y"},
                 "r": {"resolution": [256, 256, 1], "voxel_sha256": "r"},
                 "g": {"resolution": [256, 256, 1], "voxel_sha256": "g"},
                 "b": {"resolution": [256, 256, 1], "voxel_sha256": "b"}}
        with self.assertRaisesRegex(ValueError, "protected height"):
            module.verify_canary_volumes(before, after)

    def test_volume_check_accepts_identical_height_and_mask(self):
        before = {"height": {"resolution": [256, 256, 1]},
                  "mask": {"resolution": [256, 256, 1]}}
        after = {**before, "r": {"resolution": [256, 256, 1], "voxel_sha256": "r"},
                 "g": {"resolution": [256, 256, 1], "voxel_sha256": "g"},
                 "b": {"resolution": [256, 256, 1], "voxel_sha256": "b"}}
        self.assertTrue(module.verify_canary_volumes(before, after)["source_volume_identity_unchanged"])


if __name__ == "__main__":
    unittest.main()
