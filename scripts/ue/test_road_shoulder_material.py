"""Offline source/readback regressions, not native shoulder material admission."""

from __future__ import annotations

import ast
import copy
from contextlib import ExitStack
import hashlib
import json
import math
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from scripts.ue import road_shoulder_material as material
from scripts.ue import test_road_edge_marking_material as paint_fixture


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


def shared_builder_fixture(api):
    """Execute the real graph definitions, excluding the executable host entry."""
    path = material.ROOT / "scripts/ue/build_sa_calobra_whole_map_master.py"
    wanted = {"Graph", "load_required", "build_surface_terms", "build_graph"}
    definitions = [node for node in ast.parse(path.read_text()).body
                   if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted]
    module = ModuleType("scripts.ue.build_sa_calobra_whole_map_master")
    module.__dict__.update(unreal=api, LIB=api.MaterialEditingLibrary,
                           SCALARS=material.terrain_prep.SCALARS, ROLES=material.terrain_prep.ROLES,
                           DOMAIN_COLORS=material.terrain_prep.DOMAIN_COLORS)
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), "exec"), module.__dict__)
    return module


class SurfaceInstance(paint_fixture.Instance):
    def parameters(self, category):
        if category != "texture":
            return super().parameters(category)
        kinds = ("MaterialExpressionTextureObjectParameter", "MaterialExpressionTextureSampleParameter2D")
        values = {node.properties["parameter_name"]: node.properties["texture"] for node in self.parent.nodes
                  if node.kind in kinds}
        return {**values, **self.overrides[category]}


class SurfaceExpression(paint_fixture.Expression):
    def get_editor_property(self, name):
        return self.properties[name]


class SurfaceEngine(paint_fixture.Engine):
    """Small shared node evaluator; samples are fixtures, never native pixels."""
    def __init__(self):
        super().__init__()
        self.api.MaterialInstanceConstant = SurfaceInstance
        self.api.MaterialSamplerType.SAMPLERTYPE_MASKS = "masks"
        self.api.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR = "linear"
        self.api.TextureAddress.TA_CLAMP = "clamp"
        self.api.TextureFilter = SimpleNamespace(TF_BILINEAR="bilinear")
        self.api.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP = "vector_data"
        for name in material.TERRAIN_NODE_TYPES:
            setattr(self.api, name, name)
        self.gravel = {channel: paint_fixture.Texture(material._object_path(row["path"]), channel)
                       for channel, row in material.SOURCE_PINS.items()}
        bindings = {}
        for parameter, row in material.TERRAIN_PINS.items():
            if parameter in ("master", "instance"):
                continue
            texture = paint_fixture.Texture(material._object_path(row["path"]),
                                           "Normal_DX" if parameter.endswith("NormalTex") else "BaseColor")
            if parameter == "WeightTex":
                texture.properties.update(srgb=False, filter="bilinear", address_x="clamp", address_y="clamp",
                                          compression_settings="vector_data", never_stream=False)
            bindings[parameter] = texture
        recipe = material.terrain_prep.rendering_recipe()
        scalars = {**material.terrain_prep.SCALARS}
        for role, settings in recipe["roles"].items():
            scalars.update({role + "TileSizeCm": settings["tile_cm"], role + "Roughness": settings["roughness"]})
        self.terrain = {"weight": bindings["WeightTex"], "textures": {
            role: {channel: bindings[role + channel + "Tex"] for channel in ("BaseColor", "Normal")}
            for role in material.terrain_prep.ROLES},
            "contract": {"fixture_only": True, "scalar_values": scalars, "rendering_recipe": recipe,
                         "texture_objects": {name: value.path for name, value in bindings.items()}},
            "observation": {"fixture_only": True}}
        self.landscape = object()
        self.statistics = {"num_samplers": 6, "num_pixel_shader_instructions": 350, "num_pixel_texture_samples": 49,
                           "num_vertex_shader_instructions": 10, "num_vertex_texture_samples": 0,
                           "num_virtual_texture_samples": 0, "num_uv_scalars": 4, "num_interpolator_scalars": 0}
        self.api.MaterialEditingLibrary.get_statistics = lambda _: SimpleNamespace(
            get_editor_property=lambda name: self.statistics[name])
        self.api.MaterialEditingLibrary.recompile_material = lambda _: ["synthetic compile error"] if self.fail_compile else []
        self.builder = shared_builder_fixture(self.api)

    def create_asset(self, name, root, cls, factory):
        value = super().create_asset(name, root, cls, factory)
        if isinstance(value, paint_fixture.Material):
            value.properties["tangent_space_normal"] = True
        return value

    def node(self, parent, kind):
        value = SurfaceExpression(kind)
        parent.nodes.append(value)
        self.events.append(("node", kind))
        return value

    def scope(self):
        stack = ExitStack()
        stack.enter_context(patch.object(material, "_authenticate_sources", return_value=(self.gravel, material.SOURCE_PINS)))
        stack.enter_context(patch.object(material, "_authenticate_asphalt", return_value={
            channel: self.textures[channel] for channel in material.ASPHALT_TEXTURES.values()}))
        stack.enter_context(patch.object(material, "_authenticate_terrain", return_value=self.terrain))
        stack.enter_context(patch.object(material, "_api_evidence", return_value={"fixture_only": True}))
        stack.enter_context(patch.dict(sys.modules, {self.builder.__name__: self.builder}))
        stack.enter_context(patch.object(sys.modules["scripts.ue"], "build_sa_calobra_whole_map_master",
                                         self.builder, create=True))
        return stack

    def create(self, *, outer=True):
        with self.scope():
            return material.create_material(
                self.api, material.DESTINATION_ROOT, list(material.SOURCE_PINS.values()), self.asphalt_assets,
                **({"terrain_consumer_assets": list(material.TERRAIN_PINS.values()), "landscape": self.landscape} if outer else {}))

    def samples(self, *, gravel_red=0.125):
        values = {self.textures["BaseColor"].path: (0.08, 0.09, 0.1),
                  self.textures["Normal_DX"].path: (0.0, 0.0, 1.0), self.textures["ORM"].path: (0.8, 0.9, 0.0),
                  self.gravel["BaseColor"].path: (gravel_red, 0.3, 0.4),
                  self.gravel["Normal_DX"].path: (0.6, 0.0, 0.8), self.gravel["Roughness"].path: (0.6, 0.6, 0.6)}
        for i, role in enumerate(material.terrain_prep.ROLES):
            values[self.terrain["textures"][role]["BaseColor"].path] = (0.08 + i * 0.03, 0.1 + i * 0.04, 0.06 + i * 0.02)
            values[self.terrain["textures"][role]["Normal"].path] = (0.0, 0.6, 0.8)
        return values

    def evaluate(self, node, *, inner=50.0, outer=0.0, gravel_red=0.125, world=(12345.0, 54321.0, 300.0),
                 camera_distance=1000.0, weight_sample=None):
        samples = self.samples(gravel_red=gravel_red)

        def op(a, b, fn):
            if not isinstance(a, tuple) and not isinstance(b, tuple):
                return fn(a, b)
            a = a if isinstance(a, tuple) else (a,) * len(b)
            b = b if isinstance(b, tuple) else (b,) * len(a)
            return tuple(fn(x, y) for x, y in zip(a, b, strict=True))

        def visit(n):
            kind, data = n.kind, n.properties

            def get(pin=""):
                return visit(n.inputs[pin][0]) if pin in n.inputs else data["const_" + pin.lower()]

            if kind == "MaterialExpressionMaterialFunctionCall":
                return samples[n.inputs["TextureObject"][0].properties["texture"].path]
            if kind == "MaterialExpressionTextureSampleParameter2D":
                uv = get()
                return weight_sample(uv) if weight_sample else (0.15, 0.25, 0.10, 0.2)
            if kind == "MaterialExpressionTextureCoordinate":
                return (inner, 20.0) if data["coordinate_index"] == 0 else (outer, 37.0)
            if kind == "MaterialExpressionWorldPosition":
                return world
            if kind == "MaterialExpressionCameraPositionWS":
                return (world[0], world[1], world[2] + camera_distance)
            if kind == "MaterialExpressionScalarParameter":
                return data["default_value"]
            if kind == "MaterialExpressionConstant":
                return data["r"]
            if kind == "MaterialExpressionConstant2Vector":
                return (data["r"], data["g"])
            if kind == "MaterialExpressionConstant3Vector":
                return tuple(getattr(data["constant"], name) for name in "rgb")
            if kind == "MaterialExpressionComponentMask":
                selected = tuple(get()[i] for i, name in enumerate("rgba") if data[name])
                return selected[0] if len(selected) == 1 else selected
            if kind in ("MaterialExpressionSaturate", "MaterialExpressionOneMinus", "MaterialExpressionFloor", "MaterialExpressionFrac"):
                function = {"MaterialExpressionSaturate": lambda x: min(1.0, max(0.0, x)),
                            "MaterialExpressionOneMinus": lambda x: 1.0 - x, "MaterialExpressionFloor": math.floor,
                            "MaterialExpressionFrac": lambda x: x - math.floor(x)}[kind]
                return op(get(), 0.0, lambda x, _: function(x))
            if kind == "MaterialExpressionNormalize":
                value = get()
                length = math.sqrt(sum(x * x for x in value))
                return tuple(x / length for x in value)
            if kind == "MaterialExpressionDistance":
                return math.sqrt(sum((x - y) ** 2 for x, y in zip(get("A"), get("B"), strict=True)))
            if kind == "MaterialExpressionLinearInterpolate":
                alpha = get("Alpha")
                return op(get("A"), get("B"), lambda a, b: a * (1.0 - alpha) + b * alpha)
            return op(get("A"), get("B"), {"MaterialExpressionMultiply": lambda a, b: a * b,
                "MaterialExpressionDivide": lambda a, b: a / b, "MaterialExpressionAdd": lambda a, b: a + b,
                "MaterialExpressionSubtract": lambda a, b: a - b, "MaterialExpressionMax": max}[kind])
        return visit(node)


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


class OuterTerrainMaterialTests(unittest.TestCase):
    def assertSurfaceEqual(self, actual, expected):
        if isinstance(actual, tuple):
            self.assertEqual(len(actual), len(expected))
            for a, b in zip(actual, expected, strict=True):
                self.assertAlmostEqual(a, b, places=12)
        else:
            self.assertAlmostEqual(actual, expected, places=12)

    def test_original_146_node_producer_graph_is_semantically_unchanged(self):
        """Trace from producer source 1434dc5027b5 before extraction; no asset build."""
        engine = SurfaceEngine()
        engine.api.MaterialSamplerType = SimpleNamespace(**{
            key: key for key in ("SAMPLERTYPE_NORMAL", "SAMPLERTYPE_COLOR", "SAMPLERTYPE_LINEAR_COLOR")})
        engine.api.LinearColor = lambda r, g, b, a: [r, g, b, a]
        parent = paint_fixture.Material("fixture")
        textures = {role: {channel: role + "/" + channel for channel in ("BaseColor", "Normal")}
                    for role in material.terrain_prep.ROLES}
        count = engine.builder.build_graph(parent, "weights", textures, material.terrain_prep.rendering_recipe())
        indices = {id(node): i for i, node in enumerate(parent.nodes)}
        trace = {
            "nodes": [{"kind": node.kind, "properties": node.properties,
                       "links": {pin: [indices[id(source)], output] for pin, (source, output) in node.inputs.items()}}
                      for node in parent.nodes],
            "outputs": {"MP_" + name: [indices[id(node)], ""] for name, node in engine.outputs.items()},
        }
        self.assertEqual(count, 146)
        self.assertEqual(hashlib.sha256(json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                         "23910e318d28b5bfa2d655527c5d2245bd8a8e354f5cb565bd89322db94e33d9")

    def test_outer_graph_samples_the_actual_surface_terms_at_the_same_world_position(self):
        engine = SurfaceEngine()
        instance, receipt = engine.create()
        self.assertEqual(receipt["schema_version"], 3)
        self.assertIs(receipt["edge_transition"]["outer_terrain_transition"], True)
        self.assertEqual(receipt["unique_texture_objects"], 17)
        self.assertEqual(receipt["native_statistics"]["num_samplers"], 6)  # Fixture observation, not texture count.
        self.assertIs(receipt["gpu_compile_verified"], False)
        self.assertEqual(len(instance.parameters("texture")), 17)
        self.assertEqual(len(instance.parameters("scalar")), 20)
        self.assertEqual(set(engine.outputs), {"BASE_COLOR", "NORMAL", "ROUGHNESS", "EMISSIVE_COLOR",
                                               "AMBIENT_OCCLUSION", "SPECULAR", "METALLIC"})
        reference = engine.builder.build_surface_terms(
            engine.builder.Graph(paint_fixture.Material("reference")), engine.terrain["weight"],
            engine.terrain["textures"], engine.terrain["contract"]["rendering_recipe"])
        seen_uv = []

        def weights(uv):
            seen_uv.append(uv)
            return (0.15, 0.25, 0.10, 0.20)

        for world in ((12345.0, 54321.0, 300.0), (-25.0, 201625.0, 900.0)):
            for outer in (0.0, 0.5, 1.0):
                for camera_distance in (1000.0, 13000.0, 25000.0):
                    settings = dict(inner=50.0, outer=outer, world=world, camera_distance=camera_distance, weight_sample=weights)
                    for prop, term in (("BASE_COLOR", "BaseColor"), ("NORMAL", "Normal"), ("ROUGHNESS", "Roughness")):
                        self.assertSurfaceEqual(engine.evaluate(engine.outputs[prop], **settings),
                                                engine.evaluate(reference[term], **settings))
                    self.assertEqual(engine.evaluate(engine.outputs["EMISSIVE_COLOR"], **settings), (0.0, 0.0, 0.0))
                    self.assertTrue(all(uv == ((world[0] + 25.0) / 201650.0, (world[1] + 25.0) / 201650.0)
                                        for uv in seen_uv))
                    seen_uv.clear()
        far_normal = engine.evaluate(engine.outputs["NORMAL"], camera_distance=25000.0)
        self.assertEqual(far_normal, (0.0, 0.0, 1.0))
        projections = [node for node in instance.parent.nodes if node.kind == "MaterialExpressionMaterialFunctionCall"]
        self.assertEqual(len(projections), 16)
        role_sizes = engine.terrain["contract"]["scalar_values"]
        for node in projections:
            parameter = node.inputs["TextureObject"][0].properties["parameter_name"]
            if parameter in engine.terrain["contract"]["texture_objects"]:
                role = next(role for role in material.terrain_prep.ROLES if parameter.startswith(role))
                self.assertEqual(node.inputs["TextureSize"][0].properties["default_value"], role_sizes[role + "TileSizeCm"])
            if "WorldSpace" in node.inputs:
                self.assertIs(node.inputs["WorldSpace"][0].properties["value"], False)
        self.assertIs(receipt["outer_transition"]["normal_response_visual_verified"], False)

    def test_inner_transition_is_preserved_on_narrow_tapers_and_outer_grain_is_bounded(self):
        engine, legacy = SurfaceEngine(), SurfaceEngine()
        engine.create()
        legacy.create(outer=False)
        for red in (-0.1, 0.0, 0.125, 0.5, 1.2):
            for inner in (0.0, 3.0, 5.0, 8.0):
                for outer in (0.0, 5.0, 10.0):
                    settings = dict(inner=inner, outer=outer, gravel_red=red)
                    for prop in legacy.outputs:
                        self.assertSurfaceEqual(engine.evaluate(engine.outputs[prop], **settings),
                                                legacy.evaluate(legacy.outputs[prop], **settings))
            for outer in (10.0, 50.0):
                for prop in legacy.outputs:
                    settings = dict(inner=50.0, outer=outer, gravel_red=red)
                    self.assertSurfaceEqual(engine.evaluate(engine.outputs[prop], **settings),
                                            legacy.evaluate(legacy.outputs[prop], **settings))
        # Dark interstices reach farther into the shoulder with real terrain;
        # brighter scanned fragments keep gravel closer to the outer boundary.
        dark = engine.evaluate(engine.outputs["BASE_COLOR"], inner=50.0, outer=5.0, gravel_red=0.0)
        bright = engine.evaluate(engine.outputs["BASE_COLOR"], inner=50.0, outer=5.0, gravel_red=0.5)
        self.assertNotEqual(dark, engine.samples(gravel_red=0.0)[engine.gravel["BaseColor"].path])
        self.assertEqual(bright, engine.samples(gravel_red=0.5)[engine.gravel["BaseColor"].path])
        for outer in (1.0, 4.0, 8.0, 10.0):
            normal = engine.evaluate(engine.outputs["NORMAL"], outer=outer)
            self.assertAlmostEqual(sum(value * value for value in normal), 1.0, places=12)

    def test_all_frozen_generated_and_role_bytes_are_required_without_normalization(self):
        consumer = list(copy.deepcopy(material.TERRAIN_PINS).values())
        dependencies = [copy.deepcopy(row) for name, row in material.TERRAIN_PINS.items()
                        if name not in ("master", "instance", "WeightTex")]
        self.assertEqual(material.terrain_rows(consumer, dependencies), material.TERRAIN_PINS)
        for inventory, change in (("consumer", "missing"), ("consumer", "sha256"), ("consumer", "size_bytes"),
                                  ("dependencies", "missing"), ("dependencies", "sha256"),
                                  ("consumer", "duplicate"), ("consumer", "boolean_size")):
            rows = {"consumer": copy.deepcopy(consumer), "dependencies": copy.deepcopy(dependencies)}
            target = rows[inventory]
            if change == "missing":
                target.pop(0)
            elif change == "duplicate":
                target.append(copy.deepcopy(target[0]))
            else:
                target[0]["size_bytes" if change == "boolean_size" else change] = (
                    True if change == "boolean_size" else "0" * 64 if change == "sha256" else target[0][change] + 1)
            with self.subTest(inventory=inventory, change=change), self.assertRaises(ValueError):
                material.terrain_rows(rows["consumer"], rows["dependencies"])

    def test_fresh_readback_requires_effective_terrain_parameters_and_registered_weight_settings(self):
        engine = SurfaceEngine()
        # Preserve the effective native float values, including ordinary float
        # quantization, instead of reconstructing ideal recipe decimals.
        engine.terrain["contract"]["scalar_values"]["DryGrassRoughness"] = 0.8799999952316284
        engine.terrain["contract"]["scalar_values"]["MicroNormalStrength"] = 0.7500000596046448
        instance, receipt = engine.create()
        self.assertEqual(instance.parameters("scalar"), {**material.SCALARS, **engine.terrain["contract"]["scalar_values"]})
        engine.events.clear()

        def verify(value=receipt):
            with engine.scope():
                return material.verify_material(engine.api, value, list(material.SOURCE_PINS.values()),
                                                terrain_consumer_assets=list(material.TERRAIN_PINS.values()),
                                                landscape=engine.landscape)

        self.assertIs(verify(), instance)
        self.assertEqual(engine.events, [])  # No setters, recompilation, imports or saves during readback.
        for category, name, value in (("scalar", "DryGrassTileSizeCm", 400.0),
                                      ("scalar", "ScreeRoughness", 0.8601),
                                      ("scalar", "DomainMix", 1.0),
                                      ("texture", "DryGrassBaseColorTex", engine.gravel["BaseColor"])):
            instance.overrides[category][name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                verify()
            instance.overrides[category].clear()
        for name, value in (("srgb", True), ("address_x", "wrap"), ("filter", "nearest"), ("never_stream", True)):
            old = engine.terrain["weight"].properties[name]
            engine.terrain["weight"].properties[name] = value
            with self.subTest(weight_setting=name), self.assertRaises(ValueError):
                verify()
            engine.terrain["weight"].properties[name] = old
        normal = engine.terrain["textures"]["Scree"]["Normal"]
        normal.properties["flip_green_channel"] = True
        with self.assertRaises(ValueError):
            verify()
        normal.properties["flip_green_channel"] = False
        changed = copy.deepcopy(receipt)
        changed["terrain_source"]["scalar_values"]["MicroNormalStrength"] = 1.0
        with self.assertRaises(ValueError):
            verify(changed)
        changed = copy.deepcopy(receipt)
        changed["native_statistics"]["num_samplers"] = 17
        self.assertIs(verify(changed), instance)  # Observations may differ across NullRHI and GPU phases.
        for name, value in (("num_samplers", True), ("num_virtual_texture_samples", False)):
            changed = copy.deepcopy(receipt)
            changed["native_statistics"][name] = value
            with self.subTest(retained_statistic=name), self.assertRaises(ValueError):
                verify(changed)

    def test_native_authoring_errors_and_invalid_observations_cannot_be_declared_ready(self):
        engine = SurfaceEngine()
        engine.fail_compile = True
        with self.assertRaisesRegex(ValueError, "synthetic compile error"):
            engine.create()
        self.assertEqual(len([event for event in engine.events if event[0] == "create"]), 1)
        for name, value in (("num_samplers", -1), ("num_samplers", True),
                            ("num_pixel_shader_instructions", 1000001), ("num_virtual_texture_samples", 1)):
            engine = SurfaceEngine()
            engine.statistics[name] = value
            with self.subTest(statistic=name, value=value), self.assertRaises(ValueError):
                engine.create()

    def test_nullrhi_zero_observations_are_not_gpu_statistics_and_fresh_values_are_not_pins(self):
        engine = SurfaceEngine()
        engine.statistics = dict.fromkeys(material.STATISTICS_FIELDS, 0)
        instance, receipt = engine.create()
        self.assertEqual(receipt["native_statistics"], engine.statistics)
        self.assertFalse(receipt["gpu_compile_verified"])
        for name in ("num_samplers", "num_pixel_shader_instructions", "num_pixel_texture_samples"):
            original = dict(engine.statistics)
            engine.statistics.update(num_samplers=6, num_pixel_shader_instructions=350, num_pixel_texture_samples=49)
            engine.statistics[name] = 0
            with self.subTest(missing_gpu_statistic=name), self.assertRaises(ValueError):
                material.verify_gpu_material_statistics(engine.api, instance)
            engine.statistics = original
        engine.statistics.update(num_samplers=6, num_pixel_shader_instructions=350, num_pixel_texture_samples=49)
        with engine.scope():
            self.assertIs(material.verify_material(engine.api, receipt, list(material.SOURCE_PINS.values()),
                terrain_consumer_assets=list(material.TERRAIN_PINS.values()), landscape=engine.landscape), instance)
        engine.events.clear()
        gpu = material.verify_gpu_material_statistics(engine.api, instance)
        self.assertEqual(gpu["native_statistics"], engine.statistics)
        self.assertEqual(gpu["status"], "SHOULDER_TERRAIN_GPU_STATISTICS_VERIFIED")
        self.assertTrue(gpu["host_shader_log_check_required"])
        self.assertFalse(gpu["compile_error_text_observed"])
        self.assertFalse(gpu["gpu_compile_verified"])
        self.assertNotIn("native_compile_errors", gpu)
        self.assertEqual(engine.events, [])  # No native recompile, setters, or saves in this readback.
        instance.path = material.asset_paths(material.DESTINATION_ROOT)["instance"]
        with self.assertRaisesRegex(ValueError, "exact saved outer"):
            material.verify_gpu_material_statistics(engine.api, instance)


if __name__ == "__main__":
    unittest.main()
