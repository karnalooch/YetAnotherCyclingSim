"""Offline paint graph/readback behaviour; these fixtures are not native proof."""

from copy import deepcopy
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.ue import road_edge_marking_material as paint


class Texture:
    def __init__(self, path, channel):
        self.path = path
        self.properties = {"srgb": channel == "BaseColor", "flip_green_channel": False,
                           "compression_settings": "color" if channel == "BaseColor" else "normal" if channel == "Normal_DX" else "masks",
                           "address_x": "wrap", "address_y": "wrap"}

    def get_path_name(self):
        return self.path

    def get_editor_property(self, name):
        return self.properties[name]


class Material:
    def __init__(self, path):
        self.path, self.nodes, self.properties = path, [], {}

    def get_path_name(self):
        return self.path

    def get_editor_property(self, name):
        return self.properties[name]

    def set_editor_property(self, name, value):
        self.properties[name] = value


class Instance:
    def __init__(self, path, parent=None):
        self.path, self.parent = path, parent
        self.overrides = {"texture": {}, "scalar": {}, "vector": {}}

    def get_path_name(self):
        return self.path

    def get_editor_property(self, name):
        if name != "parent":
            raise AssertionError("Unknown fixture instance property")
        return self.parent

    def parameters(self, category):
        kind, property_name = {
            "texture": ("MaterialExpressionTextureObjectParameter", "texture"),
            "scalar": ("MaterialExpressionScalarParameter", "default_value"),
            "vector": ("MaterialExpressionVectorParameter", "default_value"),
        }[category]
        defaults = {n.properties["parameter_name"]: n.properties[property_name]
                    for n in self.parent.nodes if n.kind == kind}
        return {**defaults, **self.overrides[category]}


class Expression:
    def __init__(self, kind):
        self.kind, self.properties, self.inputs = kind, {}, {}

    def set_editor_property(self, name, value):
        self.properties[name] = value

    def set_material_function(self, value):
        self.properties["function"] = value
        return True


class Engine:
    def __init__(self):
        self.assets, self.events, self.outputs = {}, [], {}
        self.fail_connection = self.fail_compile = False
        self.asphalt_assets = paint.road_material.asphalt_asset_paths()
        self.textures = {channel: Texture(path, channel) for channel, path in self.asphalt_assets["textures"].items()}
        self.asphalt = Instance(self.asphalt_assets["instance"], Material(self.asphalt_assets["master"]))
        self.asphalt.overrides["scalar"] = {"TileSizeCm": 400.0, "DrySpecular": 0.2, "DryMetallic": 0.0}
        self.asphalt.overrides["texture"] = {"BaseColorTex": self.textures["BaseColor"],
                                                "NormalTex": self.textures["Normal_DX"], "ORMTex": self.textures["ORM"]}
        self.assets[self.asphalt.path] = self.asphalt
        self.assets.update({texture.path: texture for texture in self.textures.values()})
        self.api = SimpleNamespace(
            Material=Material, MaterialInstanceConstant=Instance, Texture2D=Texture,
            Paths=SimpleNamespace(project_dir=lambda: str(paint.ROOT), convert_relative_path_to_full=lambda p: p),
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: paint.ENGINE_VERSION),
            TextureCompressionSettings=SimpleNamespace(TC_DEFAULT="color", TC_NORMALMAP="normal", TC_MASKS="masks"),
            TextureAddress=SimpleNamespace(TA_WRAP="wrap"),
            MaterialParameterAssociation=SimpleNamespace(GLOBAL_PARAMETER="global"),
            MaterialDomain=SimpleNamespace(MD_SURFACE="surface"), MaterialShadingModel=SimpleNamespace(MSM_DEFAULT_LIT="lit"),
            BlendMode=SimpleNamespace(BLEND_MASKED="masked"),
            MaterialSamplerType=SimpleNamespace(SAMPLERTYPE_NORMAL="normal", SAMPLERTYPE_COLOR="color"),
            MaterialProperty=SimpleNamespace(**{"MP_" + name: name for name in (
                "BASE_COLOR", "NORMAL", "ROUGHNESS", "SPECULAR", "METALLIC", "EMISSIVE_COLOR", "AMBIENT_OCCLUSION", "OPACITY_MASK")}),
            LinearColor=lambda r, g, b, a: SimpleNamespace(r=r, g=g, b=b, a=a),
            MaterialFactoryNew=lambda: None, MaterialInstanceConstantFactoryNew=lambda: None,
            AssetToolsHelpers=SimpleNamespace(get_asset_tools=lambda: SimpleNamespace(create_asset=self.create_asset)),
            EditorAssetLibrary=SimpleNamespace(does_asset_exist=lambda path: path in self.assets),
            load_asset=self.load_asset,
        )
        self.api.MaterialEditingLibrary = SimpleNamespace(
            create_material_expression=self.node, connect_material_expressions=self.link,
            connect_material_property=self.output, recompile_material=lambda _: self.fail_compile,
            set_material_instance_parent=lambda instance, parent: setattr(instance, "parent", parent),
            update_material_instance=lambda _: None,
            **{"get_" + category + "_parameter_names": lambda instance, c=category: list(instance.parameters(c))
               for category in ("texture", "scalar", "vector")},
            **{"get_material_instance_" + category + "_parameter_value":
               lambda instance, name, association, c=category: instance.parameters(c).get(name)
               for category in ("texture", "scalar", "vector")},
        )
        for name in (*paint.road_material.EDGE_NODE_TYPES, *paint.EXTRA_NODE_TYPES,
                     "MaterialExpressionTextureObjectParameter", "MaterialExpressionScalarParameter",
                     "MaterialExpressionMaterialFunctionCall", "MaterialExpressionStaticBool",
                     "MaterialExpressionNormalize", "MaterialExpressionComponentMask", "MaterialExpressionConstant"):
            setattr(self.api, name, name)

    def load_asset(self, path):
        if path.startswith(paint.road_material.PROJECTION_ROOT):
            return path
        return self.assets.get(path)

    def create_asset(self, name, root, cls, factory):
        path = root + "/" + name + "." + name
        self.events.append(("create", path))
        value = cls(path)
        self.assets[path] = value
        return value

    def node(self, material, kind):
        self.events.append(("node", kind))
        result = Expression(kind)
        material.nodes.append(result)
        return result

    def link(self, source, output, target, pin):
        self.events.append(("link", target.kind, pin))
        target.inputs[pin] = (source, output)
        return not self.fail_connection

    def output(self, source, pin, prop):
        self.events.append(("output", prop))
        self.outputs[prop] = source
        return not self.fail_connection

    def create(self, *, uv=None, root=paint.DESTINATION_ROOT):
        with patch.object(paint, "_api_evidence", return_value={"fixture_only": True}):
            return paint.create_material(self.api, root, self.asphalt_assets, paint.UV_CONTRACT if uv is None else uv)

    def evaluate(self, prop, u, v=0.0, red=0.07):
        samples = {self.textures["BaseColor"].path: (red, 0.06, 0.055),
                   self.textures["Normal_DX"].path: (0.2, 0.0, math.sqrt(0.96))}

        def operation(a, b, function):
            if not isinstance(a, tuple) and not isinstance(b, tuple):
                return function(a, b)
            a = a if isinstance(a, tuple) else (a,) * len(b)
            b = b if isinstance(b, tuple) else (b,) * len(a)
            return tuple(function(x, y) for x, y in zip(a, b, strict=True))

        def visit(node):
            kind, data = node.kind, node.properties

            def get(pin=""):
                return visit(node.inputs[pin][0])

            if kind == "MaterialExpressionMaterialFunctionCall":
                return samples[node.inputs["TextureObject"][0].properties["texture"].path]
            if kind == "MaterialExpressionTextureCoordinate":
                return (u, v)
            if kind == "MaterialExpressionConstant":
                return data["r"]
            if kind == "MaterialExpressionScalarParameter":
                return data["default_value"]
            if kind in ("MaterialExpressionVectorParameter", "MaterialExpressionConstant3Vector"):
                color = data["default_value" if kind.endswith("Parameter") else "constant"]
                return tuple(getattr(color, key) for key in "rgb")
            if kind == "MaterialExpressionComponentMask":
                return get()[0]
            if kind == "MaterialExpressionSaturate":
                return max(0.0, min(1.0, get()))
            if kind == "MaterialExpressionOneMinus":
                return 1.0 - get()
            if kind == "MaterialExpressionNormalize":
                vector = get()
                length = math.sqrt(sum(x * x for x in vector))
                return tuple(x / length for x in vector)
            if kind == "MaterialExpressionLinearInterpolate":
                alpha = get("Alpha")
                return operation(get("A"), get("B"), lambda a, b: a * (1 - alpha) + b * alpha)
            functions = {"MaterialExpressionMultiply": lambda a, b: a * b,
                         "MaterialExpressionDivide": lambda a, b: a / b,
                         "MaterialExpressionSubtract": lambda a, b: a - b,
                         "MaterialExpressionAdd": lambda a, b: a + b,
                         "MaterialExpressionMin": min}
            return operation(get("A"), get("B"), functions[kind])
        return visit(self.outputs[prop])


class PaintTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_exact_two_assets_reuse_current_asphalt_no_world_save_or_texture_setters(self):
        instance, receipt = self.engine.create()
        self.assertEqual([event[1] for event in self.engine.events if event[0] == "create"], list(paint.asset_paths().values()))
        self.assertEqual(receipt["texture_objects"], {c: self.engine.textures[c].path for c in paint.TEXTURES.values()})
        self.assertEqual(instance.get_path_name(), paint.asset_paths()["instance"])
        self.assertTrue(all(receipt[key] is False for key in paint.FALSE_FLAGS))
        self.assertTrue(receipt["caller_saved_asset_bytes_required"])

    def test_foreign_destination_width_or_uv_convention_fail_before_asset_creation(self):
        for kind in ("root", "width", "channel", "axis"):
            engine = Engine()
            uv = deepcopy(paint.UV_CONTRACT)
            root = paint.DESTINATION_ROOT
            if kind == "root":
                root += "/../Elsewhere"
            elif kind == "width":
                uv["line_width_cm"] = 20
            elif kind == "channel":
                uv["channel"] = 1
            else:
                uv["u"] = "station_metres"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                engine.create(uv=uv, root=root)
            self.assertEqual(engine.events, [])

    def test_existing_material_assets_are_never_overwritten(self):
        self.engine.create()
        self.engine.events.clear()
        with self.assertRaisesRegex(ValueError, "refuse overwrite"):
            self.engine.create()
        self.assertEqual(self.engine.events, [])

    def test_fresh_readback_has_no_writes_and_rejects_dither_translucency_and_wrong_parent(self):
        instance, receipt = self.engine.create()
        self.engine.events.clear()
        self.assertIs(paint.verify_material(self.engine.api, deepcopy(receipt), self.engine.asphalt_assets, paint.UV_CONTRACT), instance)
        self.assertEqual(self.engine.events, [])
        for name, value in (("blend_mode", "translucent"), ("dither_opacity_mask", True),
                            ("dithered_lod_transition", True), ("tangent_space_normal", False),
                            ("opacity_mask_clip_value", 0.01), ("material_domain", "decal")):
            old = instance.parent.properties[name]
            instance.parent.properties[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                paint.verify_material(self.engine.api, receipt, self.engine.asphalt_assets, paint.UV_CONTRACT)
            instance.parent.properties[name] = old
        instance.parent.path = "/Game/Other.Master"
        with self.assertRaises(ValueError):
            paint.verify_material(self.engine.api, receipt, self.engine.asphalt_assets, paint.UV_CONTRACT)

    def test_effective_color_scalars_and_unexpected_parameters_are_read_back(self):
        instance, receipt = self.engine.create()
        for category, name, value in (
            ("scalar", "LineWidthCm", 20.0), ("scalar", "PaintRoughness", 0.1),
            ("scalar", "NormalStrength", float("nan")), ("scalar", "Displacement", 1.0),
            ("vector", "PaintColor", SimpleNamespace(r=1.0, g=0.0, b=0.0, a=1.0)),
            ("texture", "NoiseTex", self.engine.textures["BaseColor"]),
        ):
            instance.overrides[category][name] = value
            with self.subTest(category=category, name=name), self.assertRaises(ValueError):
                paint.verify_material(self.engine.api, receipt, self.engine.asphalt_assets, paint.UV_CONTRACT)
            instance.overrides[category].clear()

    def test_texture_color_space_normal_convention_and_source_graph_are_pinned(self):
        _, receipt = self.engine.create()
        for channel, name, value in (("BaseColor", "srgb", False), ("Normal_DX", "srgb", True),
                                     ("Normal_DX", "flip_green_channel", True), ("BaseColor", "address_x", "clamp")):
            texture = self.engine.textures[channel]
            old = texture.properties[name]
            texture.properties[name] = value
            with self.subTest(channel=channel, name=name), self.assertRaises(ValueError):
                paint.verify_material(self.engine.api, receipt, self.engine.asphalt_assets, paint.UV_CONTRACT)
            texture.properties[name] = old
        foreign = deepcopy(self.engine.asphalt_assets)
        foreign["textures"]["BaseColor"] = "/Game/Other.Texture"
        with self.assertRaises(ValueError):
            paint.verify_material(self.engine.api, receipt, foreign, paint.UV_CONTRACT)

    def test_created_graph_preserves_full_core_for_every_grain_and_varies_only_worn_margins(self):
        self.engine.create()
        for red in (-1.0, 0.0, 0.05, 0.065, 0.10, 0.12, 1.0):
            for u in (0.1, 0.2, 0.5, 0.8, 0.9):
                self.assertEqual(self.engine.evaluate("OPACITY_MASK", u, red=red), 1.0)
            for u in (0.0, 0.001, 0.999, 1.0):
                self.assertEqual(self.engine.evaluate("OPACITY_MASK", u, red=red), 0.0)
            for u in (0.03, 0.05, 0.07, 0.09):
                a = self.engine.evaluate("OPACITY_MASK", u, v=0, red=red)
                self.assertAlmostEqual(a, self.engine.evaluate("OPACITY_MASK", 1-u, v=1000, red=red))
        self.assertEqual(self.engine.evaluate("OPACITY_MASK", 0.05, red=0.05), 1.0)
        self.assertEqual(self.engine.evaluate("OPACITY_MASK", 0.05, red=0.12), 0.0)

    def test_created_graph_stays_matte_warm_and_nonemissive_without_wpo_or_depth_offset(self):
        instance, _ = self.engine.create()
        self.assertEqual(set(self.engine.outputs), {"BASE_COLOR", "NORMAL", "ROUGHNESS", "SPECULAR", "METALLIC",
                                                    "EMISSIVE_COLOR", "AMBIENT_OCCLUSION", "OPACITY_MASK"})
        for red in (0.0, 0.05, 0.065, 0.12, 1.0):
            rgb = self.engine.evaluate("BASE_COLOR", 0.5, red=red)
            for actual, base in zip(rgb, paint.COLOR[:3], strict=True):
                self.assertTrue(base * 0.96 - 1e-9 <= actual <= base + 1e-9)
            self.assertGreater(rgb[0], rgb[2])
            self.assertTrue(0.9 <= self.engine.evaluate("ROUGHNESS", 0.5, red=red) <= 0.95 + 1e-9)
            self.assertAlmostEqual(self.engine.evaluate("SPECULAR", 0.5, red=red), 0.2)
            self.assertEqual(self.engine.evaluate("METALLIC", 0.5, red=red), 0)
            self.assertEqual(self.engine.evaluate("EMISSIVE_COLOR", 0.5, red=red), 0)
            normal = self.engine.evaluate("NORMAL", 0.5, red=red)
            self.assertAlmostEqual(sum(x*x for x in normal), 1.0)
            self.assertLess(abs(normal[0]), 0.1)
        projections = [n for n in instance.parent.nodes if n.kind == "MaterialExpressionMaterialFunctionCall"]
        self.assertEqual(len(projections), 2)
        self.assertTrue(all(n.inputs["TextureSize"][0].properties["default_value"] == 400 for n in projections))

    def test_native_connection_or_compile_failure_never_produces_success_receipt(self):
        for flag in ("fail_connection", "fail_compile"):
            engine = Engine()
            setattr(engine, flag, True)
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                engine.create()
            self.assertNotIn(paint.asset_paths()["instance"], engine.assets)


if __name__ == "__main__":
    unittest.main()
