"""Hosted non-execution contract for isolated Unreal L07 hole material."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import traceback
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
AUTHOR = ROOT / "scripts/ue/l07_visibility_material_author.py"
BAKE = ROOT / "scripts/ue/bake_lesson07_landscape.py"
TRANSFER = ROOT / "scripts/houdini/prepare_lesson07_ue_transfer.py"


def producer_value(name, values):
    """Evaluate one producer assignment, without importing hou or running main."""
    tree = ast.parse(TRANSFER.read_text(encoding="utf-8"))
    assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name
                for target in node.targets)
    )
    return eval(compile(ast.Expression(assignment.value), str(TRANSFER), "eval"),
                {}, values)


class L07BakeManifestPreflight(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.material_path = (
            "/Game/Generated/YACS/Lesson07_Unified/Materials/M_L07_Visibility_Holes"
        )
        # Use the actual producer dictionaries, with small synthetic files and
        # scalar sample summaries. This is schema proof, not native terrain proof.
        tiles = []
        for cfg in producer_value("tile_configs", {}):
            payload = cfg["name"].encode("utf-8")
            filename = f"{cfg['name']}.bgeo.sc"
            (self.directory / filename).write_bytes(payload)
            first = (cfg["tx"] - 2032.0, 0.0, cfg["tz"] - 2032.0)
            last = (cfg["tx"] + 2032.0, 0.0, cfg["tz"] + 2032.0)
            tiles.append(producer_value("tile_info", {
                **cfg, "out_filename": filename, "res": (8129, 8129, 1),
                "pos0": first, "pos_max": last,
                "bbox": SimpleNamespace(minvec=lambda: first, maxvec=lambda: last),
                "arr": SimpleNamespace(min=lambda: 0.0, max=lambda: 1000.0),
                "file_sha256": hashlib.sha256(payload).hexdigest(),
                "valid_count": 64000000, "invalid_count": 2080641,
                "padded_count": 2080641, "raw_alpha_min": 0.0,
                "raw_alpha_max": 255.0, "HOLE_MATERIAL": self.material_path,
            }))
        produced = producer_value("manifest", {
            "accepted_sha": producer_value("PINNED_L06_SHA256", {}),
            "HOLE_MATERIAL": self.material_path,
            "time": SimpleNamespace(time=lambda: 1.0), "start_time": 0.0,
            "SOURCE_CACHE": producer_value("SOURCE_CACHE", {"Path": Path}),
            "tiles_manifest": tiles, "height_seams": {}, "mask_seams": {},
            "max_seam_error": 0.0, "origin_reference_m": 473.5,
            "landmark_results": [],
        })
        self.manifest = json.loads(json.dumps(produced))

    def startup_namespace(self, manifest):
        material_type = type("Material", (), {})
        material = material_type()
        material.get_editor_property = Mock(return_value="masked")
        opacity_node = Mock()
        opacity_node.get_class.return_value.get_name.return_value = (
            "MaterialExpressionLandscapeVisibilityMask"
        )
        unreal = SimpleNamespace(
            Material=material_type,
            load_asset=Mock(return_value=material),
            BlendMode=SimpleNamespace(BLEND_MASKED="masked"),
            MaterialProperty=SimpleNamespace(MP_OPACITY_MASK="opacity_mask"),
            MaterialEditingLibrary=SimpleNamespace(
                get_material_property_input_node=Mock(return_value=opacity_node)),
            EditorPythonScripting=SimpleNamespace(
                set_keep_python_script_alive=Mock()),
            register_slate_post_tick_callback=Mock(),
        )
        namespace = {
            "manifest": manifest, "tiles": manifest["tiles"],
            "MANIFEST_PATH": self.directory / "manifest.json",
            "hashlib": hashlib, "unreal": unreal, "traceback": traceback,
            "state": {},
        }
        for name in ("setup_level_and_environment", "init_houdini_api", "tick",
                     "start_tile_bake", "log", "fail"):
            namespace[name] = Mock()
        tree = ast.parse(BAKE.read_text(encoding="utf-8"))
        # Only these definitions execute with fake UE APIs. No module imports,
        # native startup, map mutation, Houdini cook or bake function is executed.
        definitions = [node for node in tree.body
                       if isinstance(node, ast.FunctionDef)
                       and node.name in {"preflight_tiles", "main"}]
        self.assertEqual(len(definitions), 2)
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(BAKE), "exec"),
             namespace)
        return namespace

    def assert_startup_rejected(self, manifest, message):
        namespace = self.startup_namespace(manifest)
        namespace["main"]()
        namespace["fail"].assert_called_once()
        self.assertIn(message, namespace["fail"].call_args.args[0])
        namespace["setup_level_and_environment"].assert_not_called()
        namespace["init_houdini_api"].assert_not_called()
        namespace["unreal"].register_slate_post_tick_callback.assert_not_called()
        namespace["start_tile_bake"].assert_not_called()

    def test_real_producer_shape_passes_preflight(self):
        for tile in self.manifest["tiles"]:
            self.assertNotIn("requested_hole_material", tile)
            self.assertEqual(tile["visibility"]["requested_hole_material"],
                             self.material_path)
        namespace = self.startup_namespace(self.manifest)
        namespace["main"]()
        namespace["fail"].assert_not_called()
        namespace["setup_level_and_environment"].assert_called_once()
        namespace["unreal"].load_asset.assert_called_once_with(self.material_path)
        namespace["start_tile_bake"].assert_not_called()

    def test_absent_global_hole_material_rejects_before_mutation(self):
        for value in (None, "", "/Engine/InvalidMaterial"):
            with self.subTest(value=value):
                manifest = copy.deepcopy(self.manifest)
                manifest["requested_hole_material"] = value
                self.assert_startup_rejected(manifest, "requires a validated masked")
        del self.manifest["requested_hole_material"]
        self.assert_startup_rejected(self.manifest, "requires a validated masked")

    def test_each_tile_requires_nested_matching_material_before_mutation(self):
        for tile_index in range(4):
            for bad_value in (None, "", "/Game/OtherMaterial"):
                with self.subTest(tile=tile_index, value=bad_value):
                    manifest = copy.deepcopy(self.manifest)
                    manifest["tiles"][tile_index]["visibility"][
                        "requested_hole_material"] = bad_value
                    self.assert_startup_rejected(manifest, "no validity/visibility proof")

    def test_flat_tile_request_cannot_replace_missing_nested_request(self):
        tile = self.manifest["tiles"][-1]
        del tile["visibility"]["requested_hole_material"]
        tile["requested_hole_material"] = self.material_path
        self.assert_startup_rejected(self.manifest, "no validity/visibility proof")

    def test_malformed_visibility_proof_rejects_before_mutation(self):
        for value in (None, [], "visibility"):
            with self.subTest(visibility=value):
                manifest = copy.deepcopy(self.manifest)
                manifest["tiles"][0]["visibility"] = value
                self.assert_startup_rejected(manifest, "no validity/visibility proof")
        for value in (False, "true", 1):
            with self.subTest(outside_source_zero=value):
                manifest = copy.deepcopy(self.manifest)
                manifest["tiles"][0]["visibility"]["outside_source_zero"] = value
                self.assert_startup_rejected(manifest, "no validity/visibility proof")

    def test_tile_hash_still_rejects_before_mutation(self):
        path = self.directory / self.manifest["tiles"][-1]["file"]
        path.write_bytes(b"changed after transfer manifest")
        self.assert_startup_rejected(self.manifest, "Stale tile")


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
