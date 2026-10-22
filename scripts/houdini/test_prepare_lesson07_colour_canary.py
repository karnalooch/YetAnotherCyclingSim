"""Boundary and conservation checks; these do not claim a native Houdini cook."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from scripts.houdini import prepare_lesson07_colour_canary as canary


class CanaryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_missing_default_crop_does_not_fallback_cook_or_create_output(self):
        alternate = self.root / "SCREE_FULLRES_PREVIEW.bgeo.sc"
        alternate.write_bytes(b"present alternate does not authorize fallback")
        output_root = self.root / "outputs"
        with patch.object(canary, "PREVIEW_ROOT", self.root), \
                patch.object(canary, "OUTPUT_ROOT", output_root), \
                patch.object(canary, "cook_canary") as cook:
            with self.assertRaises(FileNotFoundError):
                canary.preflight("SCREE_SITE_GLOBAL_COLOR")
            cook.assert_not_called()
            self.assertFalse(output_root.exists())

    def test_main_rejects_substitute_canary_before_preflight_or_output(self):
        with patch.object(canary, "output_directory") as output, \
                patch.object(canary, "preflight") as preflight, \
                patch.object(canary, "require_native_environment") as environment, \
                patch.object(canary, "cook_canary") as cook:
            for crop in canary.CROP_PINS:
                with self.subTest(crop=crop), self.assertRaisesRegex(
                        RuntimeError, "PEGASUS_SUBSTITUTE_CANARY_DISABLED"):
                    canary.main(["--run-token", "disabled", "--source-crop", crop])
            for blocked in (output, preflight, environment, cook):
                blocked.assert_not_called()

    def test_direct_cook_rejects_before_environment_import_or_io(self):
        with patch.object(canary, "require_native_environment") as environment, \
                patch("builtins.__import__", side_effect=AssertionError("Unexpected native import")), \
                patch.object(Path, "open") as file_open, \
                patch.object(Path, "mkdir") as mkdir, \
                patch.object(Path, "write_text") as write:
            with self.assertRaisesRegex(RuntimeError, "PEGASUS_SUBSTITUTE_CANARY_DISABLED"):
                canary.cook_canary({}, self.root / "disabled", {})
            for blocked in (environment, file_open, mkdir, write):
                blocked.assert_not_called()

    def test_changed_or_oversized_source_is_rejected_before_native_work(self):
        crop = self.root / "SCREE_SITE_GLOBAL_COLOR.bgeo.sc"
        crop.write_bytes(b"changed source")
        with patch.object(canary, "PREVIEW_ROOT", self.root), \
                patch.object(canary, "cook_canary") as cook:
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                canary.preflight("SCREE_SITE_GLOBAL_COLOR")
            cook.assert_not_called()
        with self.assertRaisesRegex(ValueError, "bounded input"):
            canary.identity(crop, maximum=2)
        with self.assertRaisesRegex(ValueError, "pinned size"):
            canary.identity(crop, size=1)

    def test_source_and_output_links_are_rejected(self):
        original = self.root / "source.bgeo.sc"
        original.write_bytes(b"native fixture")
        link = self.root / "linked.bgeo.sc"
        try:
            link.symlink_to(original)
        except OSError as exc:
            self.skipTest(f"Test environment cannot create symlinks: {exc}")
        with self.assertRaisesRegex(ValueError, "Linked path"):
            canary.identity(link)
        linked_root = self.root / "linked-directory"
        linked_root.symlink_to(self.root, target_is_directory=True)
        with patch.object(canary, "OUTPUT_ROOT", linked_root):
            with self.assertRaisesRegex(ValueError, "Linked path"):
                canary.output_directory("run")

    def test_output_run_cannot_escape_or_overwrite(self):
        with patch.object(canary, "OUTPUT_ROOT", self.root):
            for token in ("../escape", "absolute/path", "..", "", "a" * 65):
                with self.subTest(token=token), self.assertRaises(ValueError):
                    canary.output_directory(token)
            (self.root / "existing").mkdir()
            with self.assertRaisesRegex(ValueError, "overwrite"):
                canary.output_directory("existing")
            self.assertEqual(canary.output_directory("colour-a_1"), self.root / "colour-a_1")

    def test_cpu_environment_must_be_selected_before_hython_start(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "before launching hython"):
                canary.require_native_environment()
        with patch.dict(os.environ, {"HOUDINI_OCL_DEVICETYPE": "GPU", "HOUDINI_COP_MAXRES": "32768"}):
            with self.assertRaises(ValueError):
                canary.require_native_environment()
        with patch.dict(os.environ, {"HOUDINI_OCL_DEVICETYPE": "CPU", "HOUDINI_COP_MAXRES": "32768"}):
            canary.require_native_environment()

    def test_two_explicit_crop_pins_match_existing_native_receipt(self):
        repo = Path(__file__).resolve().parents[2]
        receipt = json.loads((repo / canary.SOURCE_RECEIPT.split("#")[0]).read_text())
        repair = receipt["houdini_preview_verification"]["repair"]
        self.assertEqual(tuple(repair["scree_crop_resolution"]), canary.RESOLUTION)
        self.assertEqual(repair["scree_crop_class_pixels"], 34)
        self.assertEqual(set(canary.CROP_PINS), {"SCREE_SITE_GLOBAL_COLOR", "SCREE_FULLRES_PREVIEW"})
        for name, digest in canary.CROP_PINS.items():
            self.assertEqual(repair["render_caches"][name]["sha256"], digest)
            recorded = repair["render_caches"][name]["path"].replace("\\", "/")
            self.assertEqual(recorded, str(canary.PREVIEW_ROOT / f"{name}.bgeo.sc"))

    def test_canary_parameters_equal_fingerprinted_stage4a_recipe(self):
        path = Path(canary.__file__).with_name("lesson06_unified_pipeline.py")
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), canary.RECIPE_SHA256)
        tree = ast.parse(path.read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "stage4a_grass")
        assignments = [n for n in ast.walk(function) if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute) and n.func.attr == "setParms"
                       and isinstance(n.func.value, ast.Name) and n.func.value.id == "mat_grass"]
        self.assertEqual(len(assignments), 1)
        values = {ast.literal_eval(k): v for k, v in zip(assignments[0].args[0].keys, assignments[0].args[0].values)}
        scalar_keys = set(values) - {"filename1", "filename2", "filename3"}
        self.assertEqual({key: ast.literal_eval(values[key]) for key in scalar_keys},
                         {**canary.MATERIAL_PARMS, "use_mask": 1})
        for key in ("filename1", "filename2", "filename3"):
            filename = ast.literal_eval(values[key].args[0].right)
            self.assertEqual(Path(canary.ASSET_PINS[key][0]).name, filename)


class ConservationAndCoverageTests(unittest.TestCase):
    def setUp(self):
        self.before = {
            name: {"resolution": [257, 257, 1], "transform": [1, 0, 0],
                   "position": [0, 0, 0], "voxels_sha256": f"fixture-{name}"}
            for name in canary.REQUIRED | {"mask", "roughness"}
        }

    def test_rgb_only_changes_pass_but_every_non_rgb_layer_is_protected(self):
        candidate = deepcopy(self.before)
        for name in canary.RGB:
            candidate[name]["voxels_sha256"] = "native-hda-rgb"
        canary.require_equal_layers(self.before, candidate)
        for name in self.before.keys() - canary.RGB:
            modified = deepcopy(candidate)
            modified[name]["voxels_sha256"] = "changed"
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Protected volume"):
                canary.require_equal_layers(self.before, modified)

    def test_lattice_drift_and_removed_or_added_volume_fail(self):
        for name in ("height", "r", "g", "b"):
            for key, changed in (("position", [1, 0, 0]), ("transform", [2, 0, 0]),
                                 ("resolution", [256, 257, 1])):
                modified = deepcopy(self.before)
                modified[name][key] = changed
                with self.subTest(name=name, key=key), self.assertRaises(ValueError):
                    canary.require_equal_layers(self.before, modified)
        for modified in ({k: v for k, v in self.before.items() if k != "Alpha"},
                         {**self.before, "invented_mask": {}}):
            with self.assertRaisesRegex(ValueError, "layer names"):
                canary.require_equal_layers(self.before, modified)

    def test_coverage_excludes_invalid_voxels_and_reports_regressions(self):
        alpha = np.array([1, 1, 0, 1], dtype=np.float32)
        masked = np.array([[0, 0, 0], [1, 1, 1], [0, 0, 0], [1, 1, 1]], dtype=np.float32)
        unmasked = np.array([[0.1, 0.2, 0.3], [1, 1, 1], [1, 1, 1], [0, 0, 0]], dtype=np.float32)
        counts = canary.coverage_counts(alpha, masked, unmasked, np)
        self.assertEqual(counts["valid_voxels"], 3)
        self.assertEqual(counts["black_valid_voxels_filled"], 1)
        self.assertEqual(counts["new_black_valid_voxels"], 1)
        self.assertEqual(counts["different_valid_rgb_voxels"], 2)
        unmasked[0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            canary.coverage_counts(alpha, masked, unmasked, np)


if __name__ == "__main__":
    unittest.main()
