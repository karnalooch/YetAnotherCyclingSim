"""Offline graph and native-call fixtures, explicitly not shader-space proof."""

from contextlib import ExitStack
from copy import deepcopy
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.ue import road_crack_material as material
from scripts.ue import road_crack_sources as sources
from scripts.ue import test_road_edge_marking_material as paint_fixture
from scripts.ue.test_road_crack_sources import neutral_fixture


class Expression(paint_fixture.Expression):
    def get_editor_property(self, name):
        return self.properties[name]


class Instance(paint_fixture.Instance):
    def parameters(self, category):
        if category != "texture":
            return super().parameters(category)
        defaults = {node.properties["parameter_name"]: node.properties["texture"] for node in self.parent.nodes
                    if node.kind in ("MaterialExpressionTextureObjectParameter", "MaterialExpressionTextureSampleParameter2D")}
        return {**defaults, **self.overrides[category]}


class Function:
    def __init__(self, path):
        self.path = path

    def get_path_name(self):
        return self.path + "." + self.path.rsplit("/", 1)[1]


class Engine(paint_fixture.Engine):
    def __init__(self):
        super().__init__()
        self.asphalt.__class__ = Instance
        self.api.MaterialInstanceConstant = Instance
        self.api.SamplerSourceMode = SimpleNamespace(SSM_FROM_TEXTURE_ASSET="texture_asset")
        self.api.MaterialVectorCoordTransformSource = SimpleNamespace(TRANSFORMSOURCE_TANGENT="tangent")
        self.api.MaterialVectorCoordTransform = SimpleNamespace(TRANSFORM_WORLD="world")
        self.api.MaterialSamplerType.SAMPLERTYPE_MASKS = "masks"
        self.api.TextureAddress.TA_CLAMP = "clamp"
        for name in material.EXTRA_NODE_TYPES:
            setattr(self.api, name, name)
        self.fail_override = None
        for category in ("texture", "scalar", "vector"):
            setattr(self.api.MaterialEditingLibrary, "set_material_instance_" + category + "_parameter_value",
                    lambda instance, name, value, c=category: self.override(instance, c, name, value))
        self.source = {"pins_sha256": "a" * 64, "selected_motifs": list(sources.CANARY_MOTIFS), "motifs": {
            motif: {"extent_cm": extent, "empty_border_cm": 6.0, "resolution": 2048}
            for motif, extent in zip(sources.CANARY_MOTIFS, (180.0, 140.0), strict=True)}}
        self.local = {}
        texture_paths = sources.asset_paths(self.source)
        for motif, channels in texture_paths["textures"].items():
            self.local[motif] = {}
            for channel, path in channels.items():
                texture = paint_fixture.Texture(path, channel)
                texture.properties.update(address_x="clamp", address_y="clamp")
                self.local[motif][channel] = texture
                self.assets[path] = texture
        self.import_receipt = {"fixture_only": True, "sources": self.source, "assets": texture_paths,
                               "neutral_sources": {motif: neutral_fixture() for motif in sources.CANARY_MOTIFS}}
        self.contracts = {motif: material.geometry_contract(self.source["motifs"][motif], uv_rotation_degrees=rotation)
                          for motif, rotation in zip(sources.CANARY_MOTIFS, (0, 90), strict=True)}

    def load_asset(self, path):
        if path.startswith(material.road_material.PROJECTION_ROOT):
            return Function(path)
        return self.assets.get(path)

    def node(self, parent, kind):
        self.events.append(("node", kind))
        result = Expression(kind)
        parent.nodes.append(result)
        return result

    def override(self, instance, category, name, value):
        self.events.append(("override", instance.path, category, name, value))
        if self.fail_override is not None and self.fail_override(instance, category, name, value):
            return False
        instance.overrides[category][name] = value
        return True

    def scope(self):
        stack = ExitStack()
        stack.enter_context(patch.object(sources, "_context"))
        stack.enter_context(patch.object(sources, "verify_import", return_value=self.local))
        stack.enter_context(patch.object(material, "_api_evidence", return_value={"fixture_only": True, "normal_space_verified": False}))
        return stack

    def create(self):
        with self.scope():
            return material.create_materials(self.api, "unused-fixture-root", {}, self.import_receipt, self.asphalt_assets, self.contracts)

    def verify(self, receipt):
        with self.scope():
            return material.verify_materials(self.api, "unused-fixture-root", {}, self.import_receipt, receipt, self.asphalt_assets, self.contracts)

    def evaluate(self, prop, instance, *, uv=(0.5, 0.5), local=None, base=None, rotation=0.0,
                 world_position=(120.0, 300.0, 40.1)):
        neutral = self.import_receipt["neutral_sources"]["drifting_interrupted"]
        local_values = {"BaseColor": tuple(neutral["base_color_linear"]), "ORM": tuple(neutral["orm_linear"]),
                        "Normal_DX": (*neutral["normal_xy_bias"], 1.0), "DetailMasks": (0.0, 0.0, 0.0), **(local or {})}
        base_values = {"BaseColor": (0.065, 0.06, 0.055), "Normal_DX": (0.15, -0.2, math.sqrt(0.9375)),
                       "ORM": (0.98, 0.88, 0.0), **(base or {})}
        projected_channels = {parameter: channel for parameter, channel in material.BASE_TEXTURES.items()}
        local_channels = {parameter: channel for parameter, channel in material.LOCAL_TEXTURES.items()}
        parameters = {c: instance.parameters(c) for c in ("scalar", "vector", "texture")}

        def operation(a, b, fn):
            if not isinstance(a, tuple) and not isinstance(b, tuple):
                return fn(a, b)
            a = a if isinstance(a, tuple) else (a,) * len(b)
            b = b if isinstance(b, tuple) else (b,) * len(a)
            return tuple(fn(x, y) for x, y in zip(a, b, strict=True))

        def visit(node):
            kind, data = node.kind, node.properties

            def get(pin=""):
                return visit(node.inputs[pin][0])

            if kind == "MaterialExpressionMaterialFunctionCall":
                parameter = node.inputs["TextureObject"][0].properties["parameter_name"]
                value = base_values[projected_channels[parameter]]
                return value(get("WorldPosition")) if callable(value) else value
            if kind == "MaterialExpressionTextureSampleParameter2D":
                self.assert_uv_identity(node, get())
                return local_values[local_channels[data["parameter_name"]]]
            if kind == "MaterialExpressionTextureCoordinate":
                return uv
            if kind == "MaterialExpressionWorldPosition":
                return world_position
            if kind == "MaterialExpressionScalarParameter":
                return parameters["scalar"][data["parameter_name"]]
            if kind in ("MaterialExpressionVectorParameter", "MaterialExpressionConstant3Vector"):
                value = parameters["vector"][data["parameter_name"]] if kind.endswith("Parameter") else data["constant"]
                return tuple(getattr(value, channel) for channel in "rgb")
            if kind == "MaterialExpressionConstant":
                return data["r"]
            if kind == "MaterialExpressionComponentMask":
                values = tuple(get()[index] for index, name in enumerate("rgba") if data[name])
                return values[0] if len(values) == 1 else values
            if kind == "MaterialExpressionSaturate":
                return operation(get(), 0.0, lambda a, _: max(0.0, min(1.0, a)))
            if kind == "MaterialExpressionOneMinus":
                return operation(get(), 0.0, lambda a, _: 1.0 - a)
            if kind == "MaterialExpressionNormalize":
                value = get()
                length = math.sqrt(sum(v * v for v in value))
                return tuple(v / length for v in value)
            if kind == "MaterialExpressionTransform":
                # Independent orthonormal fixture frame: tilted road plus a UV
                # turn. It does not assert actual UE's tangent-space behaviour.
                x, y, z = get()
                angle = math.radians(rotation)
                x, y = math.cos(angle) * x - math.sin(angle) * y, math.sin(angle) * x + math.cos(angle) * y
                return (0.8 * x + 0.6 * z, y, -0.6 * x + 0.8 * z)
            if kind == "MaterialExpressionLinearInterpolate":
                alpha = get("Alpha")
                return operation(get("A"), get("B"), lambda a, b: a * (1.0 - alpha) + b * alpha)
            return operation(get("A"), get("B"), {
                "MaterialExpressionMultiply": lambda a, b: a * b, "MaterialExpressionDivide": lambda a, b: a / b,
                "MaterialExpressionSubtract": lambda a, b: a - b, "MaterialExpressionAdd": lambda a, b: a + b,
                "MaterialExpressionMin": min, "MaterialExpressionMax": max}[kind])
        return visit(self.outputs[prop])

    @staticmethod
    def assert_uv_identity(node, value):
        if node.inputs[""][0].kind != "MaterialExpressionTextureCoordinate" or len(value) != 2:
            raise AssertionError("Crack source UV was transformed inside the material")


class MaterialTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def assertVectorAlmostEqual(self, actual, expected):
        for a, b in zip(actual, expected, strict=True):
            self.assertAlmostEqual(a, b, places=7)

    def test_exact_additive_paths_one_master_two_instances_and_pending_native_gate(self):
        values, receipt = self.engine.create()
        paths = material.asset_paths(self.engine.source)
        self.assertEqual(set(values), set(sources.CANARY_MOTIFS))
        self.assertEqual(set(e[1] for e in self.engine.events if e[0] == "create"), {v for row in paths.values() for v in row.values()})
        self.assertEqual(len([e for e in self.engine.events if e[0] == "create"]), 3)
        self.assertLessEqual(receipt["graph_creation"]["node_count"], material.MAX_GRAPH_NODES)
        self.assertTrue(receipt["world_normal_canary_required"])
        self.assertTrue(all(receipt[name] is False for name in material.FALSE_FLAGS))
        self.assertEqual(receipt["geometry_contracts"]["short_oblique"]["uv_rotation_degrees"], 90.0)
        self.assertTrue(receipt["caller_saved_asset_bytes_required"])
        self.engine.events.clear()
        self.assertEqual(values, self.engine.verify(receipt))
        self.assertEqual(self.engine.events, [])

    def test_neutral_source_preserves_base_grain_roughness_ao_and_normal_across_tilted_rotated_frames(self):
        values, _ = self.engine.create()
        instance = values["drifting_interrupted"]
        for rotation in (0.0, 90.0, 37.0, -125.0):
            for base_color in ((0.025, 0.023, 0.02), (0.12, 0.1, 0.09)):
                self.assertVectorAlmostEqual(self.engine.evaluate("BASE_COLOR", instance, rotation=rotation, base={"BaseColor": base_color}), base_color)
                self.assertAlmostEqual(self.engine.evaluate("ROUGHNESS", instance, rotation=rotation), 0.88)
                self.assertAlmostEqual(self.engine.evaluate("AMBIENT_OCCLUSION", instance, rotation=rotation), 0.98)
                self.assertVectorAlmostEqual(self.engine.evaluate("NORMAL", instance, rotation=rotation), (0.15, -0.2, math.sqrt(0.9375)))
        for u in (0.0, 0.03, 0.5, 0.97, 1.0):
            self.assertEqual(self.engine.evaluate("OPACITY_MASK", instance, uv=(u, 0.5)), 0.0)

    def test_source_crack_is_relative_to_base_grain_matte_and_physically_local(self):
        values, _ = self.engine.create()
        instance = values["drifting_interrupted"]
        neutral = self.engine.import_receipt["neutral_sources"]["drifting_interrupted"]
        detail = {"BaseColor": tuple(v * 0.4 for v in neutral["base_color_linear"]),
                  "ORM": (0.86, neutral["orm_linear"][1] + 0.035, 0.0), "DetailMasks": (0.8, 0.6, 0.1)}
        self.assertVectorAlmostEqual(self.engine.evaluate("BASE_COLOR", instance, local=detail), (0.026, 0.024, 0.022))
        self.assertAlmostEqual(self.engine.evaluate("ROUGHNESS", instance, local=detail), 0.915)
        self.assertAlmostEqual(self.engine.evaluate("AMBIENT_OCCLUSION", instance, local=detail), 0.98 * 0.86)
        self.assertAlmostEqual(self.engine.evaluate("OPACITY_MASK", instance, local=detail), 0.8)
        for uv in ((0.0, 0.5), (0.5, 0.0), (1.0, 0.5), (0.5, 1.0), (6 / 180, 0.5), (0.5, 1 - 6 / 180)):
            self.assertAlmostEqual(self.engine.evaluate("OPACITY_MASK", instance, uv=uv, local=detail), 0.0)
        for prop, expected in (("METALLIC", 0.0), ("SPECULAR", 0.2), ("EMISSIVE_COLOR", 0.0)):
            self.assertEqual(self.engine.evaluate(prop, instance, local=detail), expected)

    def test_local_normal_turns_with_actual_uv_frame_while_base_does_not(self):
        instances, _ = self.engine.create()
        instance = instances["short_oblique"]
        bias = self.engine.import_receipt["neutral_sources"]["short_oblique"]["normal_xy_bias"]
        local = {"Normal_DX": (bias[0] + 0.25, bias[1], math.sqrt(0.9375))}
        zero = self.engine.evaluate("NORMAL", instance, local=local, rotation=0)
        turned = self.engine.evaluate("NORMAL", instance, local=local, rotation=90)
        self.assertNotEqual(zero, turned)
        for value in (zero, turned):
            self.assertAlmostEqual(sum(v * v for v in value), 1.0)
        instance.overrides["scalar"]["NeutralProbe"] = 1.0
        for rotation in (0, 90):
            self.assertVectorAlmostEqual(self.engine.evaluate("NORMAL", instance, local=local, rotation=rotation),
                                         (0.15, -0.2, math.sqrt(0.9375)))
            self.assertEqual(self.engine.evaluate("OPACITY_MASK", instance, uv=(0, 0), local=local), 1.0)
            self.assertVectorAlmostEqual(self.engine.evaluate("BASE_COLOR", instance, local={"BaseColor": (0.0, 0.0, 0.0)}),
                                         (0.065, 0.06, 0.055))

    def test_world_projection_uses_original_source_position_and_all_local_samples_retain_clamp_uv0(self):
        instances, _ = self.engine.create()
        instance = instances["drifting_interrupted"]
        points = []

        def sample(position):
            points.append(position)
            return (0.065, 0.06, 0.055)

        self.engine.evaluate("BASE_COLOR", instance, base={"BaseColor": sample})
        self.assertTrue(points)
        for position in points:
            self.assertVectorAlmostEqual(position, (120, 300, 40))
        local = [n for n in instance.parent.nodes if n.kind == "MaterialExpressionTextureSampleParameter2D"]
        self.assertEqual(len(local), 4)
        self.assertTrue(all(n.properties["sampler_source"] == "texture_asset" and n.properties["const_coordinate"] == 0 for n in local))
        functions = [n for n in instance.parent.nodes if n.kind == "MaterialExpressionMaterialFunctionCall"]
        self.assertEqual(len(functions), 3)
        self.assertTrue(all(n.inputs["TextureSize"][0].properties["default_value"] == 400 for n in functions))
        normal = next(n for n in functions if "WorldAlignedNormal" in n.properties["function"].get_path_name())
        self.assertIs(normal.inputs["WorldSpace"][0].properties["value"], True)
        self.assertEqual(set(self.engine.outputs), {"BASE_COLOR", "ROUGHNESS", "NORMAL", "OPACITY_MASK", "METALLIC",
                                                   "SPECULAR", "EMISSIVE_COLOR", "AMBIENT_OCCLUSION"})

    def test_foreign_geometry_existing_assets_or_failed_native_graph_prevent_receipt(self):
        for key, value in (("surface_offset_cm", 0.2), ("channel", 1), ("actor_scale", [2, 1, 1]), ("uv_rotation_degrees", 45)):
            engine = Engine()
            engine.contracts["short_oblique"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                engine.create()
            self.assertFalse(engine.events)
        for flag in ("fail_connection", "fail_compile"):
            engine = Engine()
            setattr(engine, flag, True)
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                engine.create()
            self.assertFalse(any(e[0] == "create" and "/MI_" in e[1] for e in engine.events))
        self.engine.create()
        self.engine.events.clear()
        with self.assertRaisesRegex(ValueError, "refuse overwrite"):
            self.engine.create()
        self.assertEqual(self.engine.events, [])

    def test_fresh_readback_rejects_wrong_space_clipping_texture_extent_or_unrestored_probe(self):
        instances, receipt = self.engine.create()
        instance = instances["short_oblique"]
        for key, value in (("tangent_space_normal", True), ("blend_mode", "decal"), ("opacity_mask_clip_value", 0.5),
                           ("dithered_lod_transition", True)):
            old = instance.parent.properties[key]
            instance.parent.properties[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.engine.verify(receipt)
            instance.parent.properties[key] = old
        for kind, key, value in (("scalar", "NeutralProbe", 1.0), ("scalar", "ExtentCm", 180),
                                  ("texture", "CrackNormalTex", self.engine.textures["Normal_DX"]),
                                  ("vector", "NeutralNormalXY", SimpleNamespace(r=0, g=0, b=0, a=1))):
            old = instance.overrides[kind][key]
            instance.overrides[kind][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.engine.verify(receipt)
            instance.overrides[kind][key] = old
        for key in ("normal_space_verified", "owner_visual_pass"):
            changed = deepcopy(receipt)
            changed[key] = True
            with self.assertRaises(ValueError):
                self.engine.verify(changed)

    def test_native_preflight_requires_installed_sources_and_records_function_bytes(self):
        api = self.engine.api
        with tempfile.TemporaryDirectory() as directory:
            engine_root = Path(directory)
            api.Paths.engine_dir = lambda: str(engine_root)
            for name in (*material.EXTRA_NODE_TYPES, "Material"):
                path = engine_root / "Source/Runtime/Engine/Public/Materials" / (name + ".h")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("U" + name + " OpacityMaskClipValue DitherOpacityMask DitheredLODTransition TangentSpaceNormal")
                if name != "Material":
                    setattr(api, name, lambda: None)
            for name in ("WorldAlignedTexture", "WorldAlignedNormal"):
                path = engine_root / "Content/Functions/Engine_MaterialFunctions01/Texturing" / (name + ".uasset")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("disposable function fixture " + name).encode())
            for name in ("get_vector_parameter_names", "get_material_instance_vector_parameter_value",
                         "set_material_instance_texture_parameter_value", "set_material_instance_scalar_parameter_value",
                         "set_material_instance_vector_parameter_value"):
                getattr(api.MaterialEditingLibrary, name).__doc__ = "Disposable fixture reflection signature."
            with patch.object(material.road_material, "_api_evidence", return_value={"fixture_only": True}):
                before = material._api_evidence(api)
                self.assertEqual(len(before["projection_function_packages"]), 2)
                self.assertFalse(before["normal_space_verified"])
                path.write_bytes(b"changed fixture function")
                self.assertNotEqual(material._api_evidence(api), before)
                (engine_root / "Source/Runtime/Engine/Public/Materials/MaterialExpressionTransform.h").unlink()
                with self.assertRaisesRegex(ValueError, "header is missing"):
                    material._api_evidence(api)


if __name__ == "__main__":
    unittest.main()
