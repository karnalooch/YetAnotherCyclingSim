"""CPU admission/rollback checks; these do not establish native UE execution."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from scripts.ue import apply_lesson07_surface_repair as repair


class FileTransportTests(unittest.TestCase):
    def test_importer_compiles_after_file_mode_transport_prologue(self):
        # The installed tool prepends ordinary statements before the file text.
        # Compile only: no UE import, filesystem staging or main() execution.
        source = Path(repair.__file__).read_text(encoding="utf-8")
        compile("import sys\n__file__ = 'tool-file.py'\n" + source, "<file-mode-prologue>", "exec")


class ImportInputStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name) / "package"
        self.package.mkdir()
        self.manifest = {"maps": {}}
        for name, (_, _, filename) in repair.MAPS.items():
            path = self.package / filename
            path.write_bytes(("CPU input-copy fixture: " + name).encode())
            self.manifest["maps"][name] = {"file": filename, "size_bytes": path.stat().st_size,
                                           "sha256": repair.sha(path)}

    def test_five_fixed_aliases_preserve_bytes_and_refuse_overwrite(self):
        original_manifest = json.dumps(self.manifest, sort_keys=True)
        originals = {path.name: path.read_bytes() for path in self.package.iterdir()}
        inputs = repair.stage_import_inputs(self.package, self.manifest)
        self.assertEqual({path.name for path in inputs.values()}, {
            "T_Grass_Normal.png", "T_Grass_Masks.png", "T_Cliffs_Colour.png",
            "T_Cliffs_Normal.png", "T_Cliffs_Masks.png"})
        self.assertEqual({path.name for path in (self.package.parent / "import-inputs").iterdir()},
                         {path.name for path in inputs.values()})
        for name, path in inputs.items():
            self.assertEqual(path.read_bytes(), originals[self.manifest["maps"][name]["file"]])
        self.assertEqual(json.dumps(self.manifest, sort_keys=True), original_manifest)
        self.assertEqual({path.name: path.read_bytes() for path in self.package.iterdir()}, originals)
        before = {name: path.read_bytes() for name, path in inputs.items()}
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            repair.stage_import_inputs(self.package, self.manifest)
        self.assertEqual({name: path.read_bytes() for name, path in inputs.items()}, before)

    def test_expansion_and_changed_source_fail_before_alias_writes(self):
        self.manifest["maps"]["Grass_Colour"] = self.manifest["maps"]["Cliffs_Colour"]
        with self.assertRaisesRegex(ValueError, "five"):
            repair.stage_import_inputs(self.package, self.manifest)
        del self.manifest["maps"]["Grass_Colour"]
        source = self.package / repair.MAPS["Cliffs_Colour"][2]
        source.write_bytes(source.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "hash, size or filename"):
            repair.stage_import_inputs(self.package, self.manifest)
        self.assertFalse((self.package.parent / "import-inputs").exists())


class PackageAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {
            "schema_version": 1, "package_id": repair.PACKAGE_ID, "size": [2048, 2048],
            "normal_convention": "DirectX", "masks_channels": {"R": "AO", "G": "Roughness", "B": "Height"},
            "classification_changed": False, "terrain_changed": False,
            "provenance": {"fixture": "CPU-only synthetic images"}, "maps": {},
        }
        for name, (_, _, filename) in repair.MAPS.items():
            path = self.root / filename
            Image.new("RGB", (2048, 2048), (128, 128, 255)).save(path)
            self.manifest["maps"][name] = {"file": filename, "size_bytes": path.stat().st_size,
                                           "sha256": repair.sha(path)}
        self.grass = {name: self.manifest["maps"][name]["sha256"] for name in repair.GRASS_HASHES}
        self.addCleanup(patch.stopall)
        patch.object(repair, "GRASS_HASHES", self.grass).start()
        self.pin = self.write_manifest()

    def write_manifest(self):
        path = self.root / "surface-repair-package.json"
        path.write_text(json.dumps(self.manifest), encoding="utf-8")
        return repair.sha(path)

    def test_valid_package_reads_only_and_preserves_file_bytes(self):
        before = {p.name: repair.sha(p) for p in self.root.iterdir()}
        self.assertEqual(repair.validate_package(self.root, self.pin), self.manifest)
        self.assertEqual(before, {p.name: repair.sha(p) for p in self.root.iterdir()})

    def test_manifest_pin_and_image_tamper_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "hash"):
            repair.validate_package(self.root, "UNSET")
        with self.assertRaisesRegex(ValueError, "hash"):
            repair.validate_package(self.root, "0" * 64)
        image = self.root / repair.MAPS["Cliffs_Colour"][2]
        image.write_bytes(image.read_bytes() + b"unreviewed change")
        with self.assertRaisesRegex(ValueError, "hash or byte"):
            repair.validate_package(self.root, self.pin)

    def test_target_expansion_and_path_escape_are_rejected(self):
        self.manifest["maps"]["Grass_Colour"] = self.manifest["maps"]["Cliffs_Colour"]
        with self.assertRaisesRegex(ValueError, "five"):
            repair.validate_package(self.root, self.write_manifest())
        del self.manifest["maps"]["Grass_Colour"]
        self.manifest["maps"]["Cliffs_Colour"]["file"] = "../outside.png"
        with self.assertRaisesRegex(ValueError, "filename"):
            repair.validate_package(self.root, self.write_manifest())

    def test_rehashed_bad_dimensions_and_channel_contract_are_rejected(self):
        image = self.root / repair.MAPS["Cliffs_Normal"][2]
        Image.new("RGB", (1024, 1024)).save(image)
        self.manifest["maps"]["Cliffs_Normal"].update(size_bytes=image.stat().st_size, sha256=repair.sha(image))
        with self.assertRaisesRegex(ValueError, "2K"):
            repair.validate_package(self.root, self.write_manifest())
        self.manifest["masks_channels"]["B"] = "Metallic"
        with self.assertRaisesRegex(ValueError, "contract"):
            repair.validate_package(self.root, self.write_manifest())

    def test_retained_grass_pin_cannot_be_replaced_by_manifest(self):
        patch.object(repair, "GRASS_HASHES", {**self.grass, "Grass_Normal": "0" * 64}).start()
        with self.assertRaisesRegex(ValueError, "Grass source"):
            repair.validate_package(self.root, self.pin)

    def test_linked_source_is_rejected_even_if_bytes_and_hash_match(self):
        path = self.root / repair.MAPS["Cliffs_Colour"][2]
        target = self.root / "same-bytes.png"
        path.rename(target)
        try:
            path.symlink_to(target)
        except OSError:
            self.skipTest("Symlink creation is not available on this host")
        with self.assertRaisesRegex(ValueError, "Redirected"):
            repair.validate_package(self.root, self.pin)

    def test_wrong_staging_fails_before_native_api_or_filesystem_writes(self):
        unreal = Mock()
        with patch.dict("sys.modules", {"unreal": unreal}), self.assertRaisesRegex(RuntimeError, "staging"):
            repair.main()
        self.assertEqual(unreal.mock_calls, [])

    def test_wrong_active_project_with_valid_staged_package_never_imports(self):
        canonical = self.root / "project"
        staging_root = canonical / "Saved/RuntimeProof/Lesson07SurfaceRepair-20261021"
        staging = staging_root / "39519585751-1"
        package = staging / "package"
        package.mkdir(parents=True)
        for source in list(self.root.iterdir()):
            if source.is_file():
                (package / source.name).write_bytes(source.read_bytes())
        script = staging / "apply_lesson07_surface_repair.py"
        script.write_text("# CPU test staged script", encoding="utf-8")
        unreal = Mock()
        unreal.Paths.project_dir.return_value = str(self.root / "other-project")
        unreal.Paths.convert_relative_path_to_full.side_effect = lambda path: path
        with patch.dict("sys.modules", {"unreal": unreal}), patch.multiple(
                repair, ROOT=canonical, STAGING_ROOT=staging_root,
                EXPECTED_MANIFEST_SHA256=self.pin, __file__=str(script)):
            with self.assertRaisesRegex(RuntimeError, "Canonical idle editor"):
                repair.main()
        unreal.AssetToolsHelpers.get_asset_tools.assert_not_called()
        unreal.EditorAssetLibrary.save_loaded_asset.assert_not_called()
        self.assertFalse((staging / "before-arrays").exists())
        self.assertFalse((staging / "live-import.json").exists())


class Array:
    def __init__(self, sources, *, fail=False):
        self.values = {"source_textures": sources, "srgb": True, "compression_settings": "Default"}
        self.fail = fail

    def get_editor_property(self, name):
        return self.values[name]

    def set_editor_property(self, name, value):
        if self.fail:
            raise RuntimeError("injected native setter failure")
        self.values[name] = value
        if name == "source_textures":
            self.values.update(srgb=True, compression_settings="Default")


class RollbackTests(unittest.TestCase):
    def test_rollback_restores_normal_sources_and_reset_settings(self):
        originals = [object() for _ in range(5)]
        array = Array([object() for _ in range(5)])
        settings = {"srgb": False, "compression_settings": "Normalmap"}
        save = Mock(return_value=True)
        unreal = SimpleNamespace(EditorAssetLibrary=SimpleNamespace(save_loaded_asset=save))
        errors = repair.rollback_arrays(unreal, {"Normal": array}, {"Normal": originals},
                                        {"Normal": settings}, ["Normal"])
        self.assertEqual(errors, [])
        self.assertEqual(array.values, {"source_textures": originals, **settings})
        save.assert_called_once_with(array, only_if_is_dirty=False)

    def test_one_rollback_failure_does_not_skip_other_touched_arrays(self):
        originals = [object() for _ in range(5)]
        arrays = {"Colour": Array([]), "Normal": Array([], fail=True)}
        settings = {"Colour": {"srgb": True}, "Normal": {"srgb": False}}
        save = Mock(return_value=True)
        unreal = SimpleNamespace(EditorAssetLibrary=SimpleNamespace(save_loaded_asset=save))
        errors = repair.rollback_arrays(unreal, arrays, {key: originals for key in arrays},
                                        settings, ["Colour", "Normal"])
        self.assertEqual([e["channel"] for e in errors], ["Normal"])
        self.assertEqual(arrays["Colour"].values["source_textures"], originals)
        save.assert_called_once_with(arrays["Colour"], only_if_is_dirty=False)


if __name__ == "__main__":
    unittest.main()
