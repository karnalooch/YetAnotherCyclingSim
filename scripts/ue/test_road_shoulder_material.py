"""Offline source/readback regressions, not native shoulder material admission."""

from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace

from scripts.ue import road_shoulder_material as material


class Texture:
    def __init__(self, path, channel):
        self.path = path
        self.properties = {
            "srgb": channel == "BaseColor",
            "compression_settings": {"BaseColor": "color", "Normal_DX": "normal",
                                     "Roughness": "masks"}[channel],
            "address_x": "wrap", "address_y": "wrap", "flip_green_channel": False,
        }

    def get_editor_property(self, name):
        return self.properties[name]

    def get_path_name(self):
        return self.path


class Master:
    def __init__(self, path):
        self.path = path
        self.tangent = True

    def get_path_name(self):
        return self.path

    def get_editor_property(self, name):
        if name != "tangent_space_normal":
            raise AssertionError("Unexpected native property")
        return self.tangent


class Instance:
    def __init__(self, parent, textures):
        self.parent, self.textures = parent, textures
        self.tile = 150.0

    def get_editor_property(self, name):
        if name != "parent":
            raise AssertionError("Unexpected native property")
        return self.parent


class ShoulderMaterialTests(unittest.TestCase):
    def setUp(self):
        self.sources = list(copy.deepcopy(material.SOURCE_PINS).values())
        self.paths = {channel: material._object_path(row["path"])
                      for channel, row in material.SOURCE_PINS.items()}
        self.textures = {channel: Texture(path, channel) for channel, path in self.paths.items()}
        self.master = Master(material.asset_paths(material.DESTINATION_ROOT)["master"])
        self.instance = Instance(self.master, self.textures)
        self.api = SimpleNamespace(
            Material=Master, MaterialInstanceConstant=Instance,
            TextureCompressionSettings=SimpleNamespace(TC_DEFAULT="color", TC_NORMALMAP="normal", TC_MASKS="masks"),
            TextureAddress=SimpleNamespace(TA_WRAP="wrap"),
            MaterialParameterAssociation=SimpleNamespace(GLOBAL_PARAMETER="global"),
            MaterialEditingLibrary=SimpleNamespace(
                get_texture_parameter_names=lambda inst: list(material.TEXTURES),
                get_scalar_parameter_names=lambda inst: ["TileSizeCm"],
                get_material_instance_scalar_parameter_value=lambda inst, name, association: inst.tile,
                get_material_instance_texture_parameter_value=lambda inst, name, association: inst.textures[material.TEXTURES[name]],
            ),
        )
        self.ledger = json.loads((material.ROOT / material.LEDGER).read_text(encoding="utf-8-sig"))

    def verify(self):
        return material._verify_instance(self.api, self.instance,
                                         material.asset_paths(material.DESTINATION_ROOT)["master"], self.paths)

    def test_native_source_rows_are_required_with_exact_hash_size_and_unique_path(self):
        self.assertEqual(material.source_rows(self.sources), material.SOURCE_PINS)
        for alteration in ("sha256", "size_bytes", "missing", "duplicate", "boolean_size"):
            rows = copy.deepcopy(self.sources)
            if alteration == "sha256":
                rows[0]["sha256"] = "0" * 64
            elif alteration == "size_bytes":
                rows[0]["size_bytes"] += 1
            elif alteration == "missing":
                rows.pop()
            elif alteration == "boolean_size":
                rows[0]["size_bytes"] = True
            else:
                rows.append(rows[0].copy())
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                material.source_rows(rows)

    def test_source_ledger_license_scale_and_pbr_identity_cannot_be_relabelled(self):
        material._validate_ledger(self.ledger)
        changes = (("license", "unknown"), ("world_size_m", [4, 4]),
                   ("source_id", "gravel_ground_01"), ("source_sha256", "0" * 64))
        for field, changed in changes:
            ledger = copy.deepcopy(self.ledger)
            row = next(row for row in ledger["items"] if row["role"] == "FillGravel")
            row[field] = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                material._validate_ledger(ledger)
        row = next(row for row in self.ledger["items"] if row["role"] == "FillGravel")
        row["pbr_maps"]["Normal"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            material._validate_ledger(self.ledger)

    def test_only_two_new_assets_in_the_fixed_namespace_are_admitted(self):
        self.assertEqual(set(material.asset_paths(material.DESTINATION_ROOT)), {"master", "instance"})
        for root in ("/Game/Other", material.DESTINATION_ROOT + "/../Other", material.DESTINATION_ROOT + "/"):
            with self.subTest(root=root), self.assertRaises(ValueError):
                material.asset_paths(root)

    def test_fresh_readback_accepts_original_150cm_data_without_texture_mutators(self):
        # The stubs deliberately have no setters/importers: verification cannot
        # repair source texture flags or silently reapply a material parameter.
        self.assertIs(self.verify(), self.instance)

    def test_changed_normal_color_space_green_channel_and_roughness_reject(self):
        changes = (("Normal_DX", "srgb", True), ("Normal_DX", "flip_green_channel", True),
                   ("Normal_DX", "compression_settings", "color"),
                   ("Roughness", "srgb", True), ("Roughness", "compression_settings", "color"),
                   ("BaseColor", "srgb", False), ("BaseColor", "address_x", "clamp"))
        for channel, field, value in changes:
            texture = self.textures[channel]
            old = texture.properties[field]
            texture.properties[field] = value
            with self.subTest(channel=channel, field=field), self.assertRaises(ValueError):
                self.verify()
            texture.properties[field] = old

    def test_missing_foreign_texture_and_parent_reject(self):
        for channel in self.textures:
            texture = self.textures[channel]
            original = texture.path
            texture.path = "/Game/Unverified.Texture"
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                self.verify()
            texture.path = original
        self.master.path = "/Game/Other.Master"
        with self.assertRaises(ValueError):
            self.verify()

    def test_four_metre_reuse_nonfinite_and_missing_scale_reject(self):
        for value in (0, 400, float("nan"), float("inf"), 150.01):
            self.instance.tile = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.verify()

    def test_projection_normal_space_and_unexpected_parameters_reject(self):
        self.master.tangent = False
        with self.assertRaises(ValueError):
            self.verify()
        self.master.tangent = True
        self.api.MaterialEditingLibrary.get_scalar_parameter_names = lambda inst: ["TileSizeCm", "Displacement"]
        with self.assertRaises(ValueError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
