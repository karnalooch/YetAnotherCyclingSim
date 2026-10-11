"""Offline source/readback regressions, not native shoulder material admission."""

from __future__ import annotations

import copy
import json
import math
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.ue import road_shoulder_material as material


class Texture:
    def __init__(self, path, channel):
        self.path = path
        self.properties = {
            "srgb": channel == "BaseColor",
            "compression_settings": {"BaseColor": "color", "Normal_DX": "normal",
                                     "Roughness": "masks", "ORM": "masks"}[channel],
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
        self.asphalt_tile = 400.0

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
        self.asphalt_paths = {channel: material.asphalt_asset_paths()["textures"][channel]
                              for channel in material.ASPHALT_TEXTURES.values()}
        self.asphalt_textures = {channel: Texture(path, channel) for channel, path in self.asphalt_paths.items()}
        self.master = Master(material.asset_paths(material.DESTINATION_ROOT)["master"])
        parameters = {name: self.textures[channel] for name, channel in material.TEXTURES.items()}
        parameters.update({name: self.asphalt_textures[channel] for name, channel in material.ASPHALT_TEXTURES.items()})
        self.instance = Instance(self.master, parameters)
        self.api = SimpleNamespace(
            Material=Master, MaterialInstanceConstant=Instance,
            TextureCompressionSettings=SimpleNamespace(TC_DEFAULT="color", TC_NORMALMAP="normal", TC_MASKS="masks"),
            TextureAddress=SimpleNamespace(TA_WRAP="wrap"),
            MaterialParameterAssociation=SimpleNamespace(GLOBAL_PARAMETER="global"),
            MaterialEditingLibrary=SimpleNamespace(
                get_texture_parameter_names=lambda inst: list(inst.textures),
                get_scalar_parameter_names=lambda inst: list(material.SCALARS),
                get_material_instance_scalar_parameter_value=lambda inst, name, association: (
                    inst.tile if name == "TileSizeCm" else inst.asphalt_tile),
                get_material_instance_texture_parameter_value=lambda inst, name, association: inst.textures[name],
            ),
        )
        self.ledger = json.loads((material.ROOT / material.LEDGER).read_text(encoding="utf-8-sig"))

    def verify(self):
        return material._verify_instance(self.api, self.instance,
                                         material.asset_paths(material.DESTINATION_ROOT)["master"],
                                         self.paths, self.asphalt_paths)

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

    def test_edge_asphalt_uses_current_graph_package_and_its_own_400cm_scale(self):
        paths = material.asphalt_asset_paths()
        self.assertEqual(set(paths["textures"]), {"BaseColor", "Normal_DX", "ORM", "DetailMasks"})
        for path in (paths["master"], paths["instance"], *paths["textures"].values()):
            self.assertIn("/" + material.asphalt_source.GRAPH_SHA256[:12] + "/", path)
        for wrong in (150.0, 400.01, float("nan")):
            self.instance.asphalt_tile = wrong
            with self.subTest(value=wrong), self.assertRaises(ValueError):
                self.verify()

    def test_edge_asphalt_orm_normal_or_foreign_texture_cannot_be_silently_repaired(self):
        for channel, name, wrong in (("ORM", "srgb", True), ("ORM", "compression_settings", "color"),
                                     ("Normal_DX", "flip_green_channel", True)):
            texture = self.asphalt_textures[channel]
            original = texture.properties[name]
            texture.properties[name] = wrong
            with self.subTest(channel=channel, name=name), self.assertRaises(ValueError):
                self.verify()
            texture.properties[name] = original
        self.asphalt_textures["BaseColor"].path = self.paths["BaseColor"]
        with self.assertRaises(ValueError):
            self.verify()

    def test_created_graph_keeps_metric_projection_and_bounded_granular_pbr_transition(self):
        """Evaluate the authored graph at physical edge distances, not a replica formula.

        This checks connection semantics with fixture texels. Native class/pin
        compatibility and actual scanned appearance still require the UE run.
        """
        class Expression:
            def __init__(self, kind):
                self.kind, self.properties, self.inputs = kind, {}, {}

            def set_editor_property(self, name, value):
                self.properties[name] = value

            def get_editor_property(self, name):
                return self.properties[name]

            def set_material_function(self, value):
                self.properties["function"] = value
                return True

        expressions, outputs = [], {}

        def node(master, kind):
            result = Expression(kind)
            expressions.append(result)
            return result

        def connect(source, output, target, pin):
            target.inputs[pin] = (source, output)
            return True

        def output(source, pin, prop):
            outputs[prop] = (source, pin)
            return True

        properties = ("BASE_COLOR", "NORMAL", "ROUGHNESS", "AMBIENT_OCCLUSION", "SPECULAR", "METALLIC")
        api = SimpleNamespace(**vars(self.api))
        api.MaterialEditingLibrary = SimpleNamespace(
            create_material_expression=node, connect_material_expressions=connect,
            connect_material_property=output, recompile_material=lambda _: False,
            set_material_instance_parent=lambda *_: None, update_material_instance=lambda _: None)
        api.MaterialProperty = SimpleNamespace(**{"MP_" + name: name for name in properties})
        api.MaterialSamplerType = SimpleNamespace(SAMPLERTYPE_NORMAL="normal", SAMPLERTYPE_COLOR="color", SAMPLERTYPE_MASKS="masks")
        api.EditorAssetLibrary = SimpleNamespace(does_asset_exist=lambda _: False)
        api.AssetToolsHelpers = SimpleNamespace(get_asset_tools=lambda: SimpleNamespace(
            create_asset=lambda name, *_: self.master if name == "M_ShoulderNetwork" else self.instance))
        api.MaterialFactoryNew = api.MaterialInstanceConstantFactoryNew = lambda: None
        self.instance.get_path_name = lambda: material.asset_paths(material.DESTINATION_ROOT)["instance"]
        api.load_asset = lambda path: path
        for name in (*material.EDGE_NODE_TYPES, "MaterialExpressionTextureObjectParameter",
                     "MaterialExpressionScalarParameter", "MaterialExpressionMaterialFunctionCall",
                     "MaterialExpressionStaticBool", "MaterialExpressionNormalize", "MaterialExpressionComponentMask",
                     "MaterialExpressionConstant"):
            setattr(api, name, name)
        with patch.object(material, "_authenticate_sources", return_value=(self.textures, material.SOURCE_PINS)), \
             patch.object(material, "_authenticate_asphalt", return_value=self.asphalt_textures), \
             patch.object(material, "_api_evidence", return_value={}), \
             patch.object(material, "_verify_instance", return_value=self.instance):
            _, receipt = material.create_material(api, material.DESTINATION_ROOT, self.sources,
                                                  material.asphalt_asset_paths())
        self.assertEqual(set(outputs), set(properties))  # No opacity, WPO or displacement output.
        self.assertEqual(receipt["schema_version"], 2)
        self.assertFalse(receipt["textures_imported"])
        projections = [n for n in expressions if n.kind == "MaterialExpressionMaterialFunctionCall"]
        self.assertEqual(len(projections), 6)
        for projection in projections:
            texture = projection.inputs["TextureObject"][0].properties["texture"]
            scale = projection.inputs["TextureSize"][0].properties["default_value"]
            self.assertEqual(scale, 400.0 if texture in self.asphalt_textures.values() else 150.0)

        samples = {
            self.asphalt_paths["BaseColor"]: (0.08, 0.09, 0.10),
            self.asphalt_paths["Normal_DX"]: (0.0, 0.0, 1.0), self.asphalt_paths["ORM"]: (0.8, 0.9, 0.0),
            self.paths["BaseColor"]: (0.2, 0.3, 0.4),
            self.paths["Normal_DX"]: (0.6, 0.0, 0.8), self.paths["Roughness"]: (0.6, 0.6, 0.6),
        }

        def vector_op(a, b, function):
            if not isinstance(a, tuple) and not isinstance(b, tuple):
                return function(a, b)
            a = a if isinstance(a, tuple) else (a,) * len(b)
            b = b if isinstance(b, tuple) else (b,) * len(a)
            return tuple(function(x, y) for x, y in zip(a, b, strict=True))

        def evaluate(expression, distance):
            kind, data = expression.kind, expression.properties

            def get(pin):
                return evaluate(expression.inputs[pin][0], distance)

            if kind == "MaterialExpressionMaterialFunctionCall":
                return samples[expression.inputs["TextureObject"][0].properties["texture"].path]
            if kind == "MaterialExpressionTextureCoordinate":
                return (distance, 50.0)
            if kind == "MaterialExpressionConstant":
                return data["r"]
            if kind == "MaterialExpressionComponentMask":
                return get("")[1 if data["g"] else 0]
            if kind == "MaterialExpressionSaturate":
                return max(0.0, min(1.0, get("")))
            if kind == "MaterialExpressionNormalize":
                value = get("")
                length = math.sqrt(sum(x * x for x in value))
                return tuple(x / length for x in value)
            if kind == "MaterialExpressionLinearInterpolate":
                alpha = get("Alpha")
                return vector_op(get("A"), get("B"), lambda a, b: a * (1 - alpha) + b * alpha)
            functions = {"MaterialExpressionMultiply": lambda a, b: a * b,
                         "MaterialExpressionAdd": lambda a, b: a + b,
                         "MaterialExpressionSubtract": lambda a, b: a - b}
            return vector_op(get("A"), get("B"), functions[kind])

        def rendered(distance, prop):
            return evaluate(outputs[prop][0], distance)

        for red in (-0.1, 0.0, 0.125, 0.5, 1.2):
            samples[self.paths["BaseColor"]] = (red, 0.3, 0.4)
            for distance in (0.0, 2.5, 3.0):
                self.assertEqual(rendered(distance, "BASE_COLOR"), samples[self.asphalt_paths["BaseColor"]])
                self.assertAlmostEqual(rendered(distance, "ROUGHNESS"), 0.9)
                self.assertAlmostEqual(rendered(distance, "SPECULAR"), 0.2)
            for distance in (8.0, 20.0, 50.0):
                self.assertEqual(rendered(distance, "BASE_COLOR"), samples[self.paths["BaseColor"]])
                self.assertAlmostEqual(rendered(distance, "ROUGHNESS"), 0.6)
                self.assertAlmostEqual(rendered(distance, "SPECULAR"), 0.5)
        samples[self.paths["BaseColor"]] = (0.125, 0.3, 0.4)
        self.assertAlmostEqual(rendered(5.5, "ROUGHNESS"), 0.75)
        self.assertAlmostEqual(rendered(5.5, "AMBIENT_OCCLUSION"), 0.9)
        self.assertAlmostEqual(sum(x * x for x in rendered(5.5, "NORMAL")), 1.0)
        samples[self.paths["BaseColor"]] = (0.0, 0.3, 0.4)
        self.assertAlmostEqual(rendered(5.5, "ROUGHNESS"), 0.9)
        samples[self.paths["BaseColor"]] = (0.5, 0.3, 0.4)
        self.assertAlmostEqual(rendered(5.5, "ROUGHNESS"), 0.6)


if __name__ == "__main__":
    unittest.main()
