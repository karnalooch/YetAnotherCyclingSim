"""Synthetic contracts only; native UE 5.8 and saved-consumer evidence remain pending."""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.ue import road_asphalt_slot_canary as canary


class Material:
    def __init__(self, name):
        self.name = name

    def get_path_name(self):
        return self.name


class Component:
    def __init__(self, material):
        self.original = material
        self.material = material
        self.calls = []

    def get_path_name(self):
        return "/Map.RoadComponent"

    def get_num_materials(self):
        return 1

    def get_material(self, index):
        assert index == 0
        return self.material

    def set_material(self, index, value):
        assert index == 0
        self.calls.append(value.get_path_name())
        self.material = value


class Actor:
    def __init__(self, component):
        self.component = component

    def get_actor_label(self):
        return canary.ROAD_LABEL

    def get_dynamic_mesh_component(self):
        return self.component


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.old = Material("/Game/Worlds/SaCalobra/CheckpointMaterials/MI_Accepted_0")
        self.new = Material(canary.ASPHALT_DESTINATION
                            + f"/{canary.FAMILY}/{canary.VARIANT}/abcdef/M_F.MI_MaterialForge")
        self.comp = Component(self.old)
        self.actor = Actor(self.comp)
        self.receipt = {
            "status": "IMPORTED_UE_REVIEW_PENDING",
            "family": canary.FAMILY,
            "variant": canary.VARIANT,
            "graph_sha256": "a" * 64,
            "tile_metres": 4,
            "normal_convention": "DirectX",
            "saved": False,
            "geometry_changed": False,
            "landscape_mutated": False,
            "world_semantics_generated": False,
            "assets": {
                "instance": self.new.get_path_name(),
                "textures": {"ORM": "/Synthetic/T_ORM.T_ORM"},
            },
            "dry_asphalt_response": {
                "status": "DRY_ASPHALT_RESPONSE_READBACK_VERIFIED",
                "scalar_parameter_values": {
                    "TileSizeCm": 400.0, "DrySpecular": 0.2, "DryMetallic": 0.0,
                },
                "scalar_parameter_names": ["DryMetallic", "DrySpecular", "TileSizeCm"],
                "orm_texture": "/Synthetic/T_ORM.T_ORM",
                "orm_srgb": False,
                "orm_compression": "TC_MASKS",
                "shader_gpu_compilation_verified": False,
                "visual_accepted": False,
            },
            "dry_surface_connections": {
                "scope": "NATIVE_CREATION_CONNECTION_RETURNS",
                "connections": {
                    "orm_projection_to_green_mask": True,
                    "green_mask_to_roughness": True,
                    "DrySpecular": True, "DryMetallic": True,
                },
                "roughness_source": "WorldAlignedTexture(ORMTex).G",
                "roughness_multiplier_used": False,
            },
        }
        self.base = {
            "road_count": 1,
            "support_count": 186,
            "landscape": {"component_count": 1024, "components": ["unchanged"]},
            "road_supports": [{
                "label": canary.ROAD_LABEL, "vertices": 856250,
                "triangles": 1711760,
                "component": self.comp.get_path_name(),
                "slots": [{"path": self.old.get_path_name(),
                           "parent": "/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"}],
            }] + [
                {"label": f"YACS_PERSIST_SUPPORT_{i:03d}",
                 "component": f"support-{i}", "vertices": i,
                 "triangles": i + 1,
                 "slots": [{"path": f"support-mat-{i}"}]}
                for i in range(186)
            ],
            "mesh_material_collision_snapshot": [{
                "component": self.comp.get_path_name(),
                "materials": [self.old.get_path_name()], "collision": "NO_COLLISION",
            }] + [
                {"component": f"support-{i}", "materials": [f"support-mat-{i}"],
                 "collision": "NO_COLLISION"}
                for i in range(186)
            ],
        }
        self.sabotage = False

    def snapshot(self):
        value = deepcopy(self.base)
        current = self.comp.get_material(0).get_path_name()
        if current != self.old.get_path_name():
            value["road_supports"][0]["slots"] = [
                {"path": current, "parent": self.new.get_path_name()}
            ]
            value["mesh_material_collision_snapshot"][0]["materials"] = [current]
            if self.sabotage:
                value["road_supports"][1]["vertices"] = -999
        return value

    def test_owned_asphalt_canary_restores_every_saved_binding(self):
        canary.verify_import_receipt(self.receipt, "a" * 64)
        result = canary.try_road_only_material(
            self.snapshot, [self.actor], self.new, self.receipt
        )
        self.assertEqual(result["status"],
                         "ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK")
        self.assertEqual(self.comp.calls,
                         [self.new.get_path_name(), self.old.get_path_name()])
        self.assertEqual(self.comp.get_material(0).get_path_name(),
                         self.old.get_path_name())
        self.assertFalse(result["full_geometry_hash_verified"])
        self.assertFalse(result["material_authoring_admitted"])
        self.assertFalse(result["performance_pass"])

    def test_diagnostic_reports_only_mismatched_paths_and_keeps_strict_equality(self):
        expected = {
            "road_supports": [{"label": "ROAD", "vertices": 42}],
            "landscape": {"component_count": 1024},
        }
        actual = deepcopy(expected)
        actual["road_supports"][0]["vertices"] = 43
        paths = canary._snapshot_difference_paths(expected, actual)
        self.assertEqual(paths, ["$.road_supports[0].vertices"])
        self.assertNotIn("42", repr(paths))
        self.assertNotIn("43", repr(paths))
        self.assertEqual(canary._snapshot_difference_paths(expected, expected), [])
        self.assertEqual(
            canary._snapshot_difference_paths(
                {"key": [1, 2]}, {"key": [1, 2, 3]}
            ),
            ["$.key: length"],
        )

    def test_modified_support_snapshot_is_rejected_and_road_restored(self):
        self.sabotage = True
        with self.assertRaisesRegex(ValueError, "supports"):
            canary.try_road_only_material(
                self.snapshot, [self.actor], self.new, self.receipt
            )
        self.assertEqual(self.comp.material, self.old)
        self.assertEqual(self.comp.calls[-1], self.old.get_path_name())

    def test_rejects_unapproved_road_geometry_or_support_count(self):
        for edit in (
            ("road_supports", 0, "vertices", 100),
            ("road_supports", 0, "triangles", 100),
            ("landscape", "component_count", 1023),
            ("support_count", 185),
        ):
            candidate = deepcopy(self.base)
            if len(edit) == 4:
                candidate[edit[0]][edit[1]][edit[2]] = edit[3]
            elif len(edit) == 3:
                candidate[edit[0]][edit[1]] = edit[2]
            else:
                candidate[edit[0]] = edit[1]
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                canary.verify_accepted_surface(candidate)

    def test_frozen_native_support_labels_are_exact_zero_based_000_to_185(self):
        support_labels = [
            row["label"] for row in self.base["road_supports"]
            if row["label"].startswith("YACS_PERSIST_SUPPORT_")
        ]
        self.assertEqual(len(support_labels), 186)
        self.assertEqual(support_labels[0], "YACS_PERSIST_SUPPORT_000")
        self.assertEqual(support_labels[-1], "YACS_PERSIST_SUPPORT_185")
        canary.verify_accepted_surface(self.base)
        broken = deepcopy(self.base)
        broken["road_supports"][-1]["label"] = "YACS_PERSIST_SUPPORT_186"
        with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
            canary.verify_accepted_surface(broken)

    def test_shared_support_slot_cannot_be_used_as_road_owner(self):
        broken = deepcopy(self.base)
        broken["road_supports"][0]["component"] = "support-1"
        with self.assertRaisesRegex(ValueError, "binding"):
            canary.verify_accepted_surface(broken)

    def test_wrong_source_or_saved_assets_are_rejected_before_material_swap(self):
        for key, value in (
            ("variant", "base"),
            ("tile_metres", 2),
            ("normal_convention", "OpenGL"),
            ("saved", True),
            ("geometry_changed", True),
            ("landscape_mutated", True),
            ("graph_sha256", "b" * 64),
        ):
            with self.subTest(key=key):
                bad = {**self.receipt, key: value}
                with self.assertRaisesRegex(ValueError, "contract"):
                    canary.verify_import_receipt(bad, "a" * 64)
        self.assertEqual(self.comp.calls, [])

    def test_dry_response_and_real_connection_receipt_fail_closed_before_swap(self):
        failures = (
            ("scalar_parameter_values", {"TileSizeCm": 400, "DrySpecular": 0.5, "DryMetallic": 0}),
            ("scalar_parameter_values", {"TileSizeCm": 400, "DrySpecular": float("nan"), "DryMetallic": 0}),
            ("scalar_parameter_values", {"TileSizeCm": 400, "DrySpecular": 0.2, "DryMetallic": False}),
            ("scalar_parameter_names", ["TileSizeCm"]),
            ("orm_srgb", True),
            ("orm_texture", "/Synthetic/Wrong_ORM"),
            ("shader_gpu_compilation_verified", True),
        )
        for key, value in failures:
            bad = deepcopy(self.receipt)
            bad["dry_asphalt_response"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                canary.verify_import_receipt(bad, "a" * 64)
        for key in self.receipt["dry_surface_connections"]["connections"]:
            bad = deepcopy(self.receipt)
            bad["dry_surface_connections"]["connections"][key] = False
            with self.subTest(connection=key), self.assertRaisesRegex(ValueError, "connection"):
                canary.verify_import_receipt(bad, "a" * 64)
        bad = deepcopy(self.receipt)
        bad["dry_surface_connections"]["roughness_multiplier_used"] = True
        with self.assertRaisesRegex(ValueError, "roughness"):
            canary.verify_import_receipt(bad, "a" * 64)
        self.assertEqual(self.comp.calls, [])

    def test_replay_selects_exported_recipe_after_two_run_authentication(self):
        replay = {
            "status": "ROAD_ASPHALT_REPLAY_RECEIPT_VERIFIED",
            "retained_two_run_graph_and_map_bytes_equal": True,
            "producer_attestation_authenticated": True,
            "unreal_verified": False, "world_mutation": False,
            "runs": [{"run": run, "graph_sha256": "a" * 64} for run in ("run-a", "run-b")],
        }
        root = Path("/synthetic-source-proof")
        with patch("scripts.assets.road_material_contract.check_asphalt_replay", return_value=replay) as verify:
            selected, receipt = canary.authenticate_asphalt_replay(root, "b" * 64, "c" * 40, "d" * 64)
        verify.assert_called_once_with(root, "b" * 64, "c" * 40, "d" * 64)
        self.assertEqual(selected, root / "run-a" / canary.FAMILY / canary.VARIANT)
        self.assertIs(receipt, replay)

    def test_road_actor_confusion_rejects_without_changes(self):
        other = Mock()
        other.get_actor_label.return_value = "YACS_PERSIST_ROAD_COPY"
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            canary.try_road_only_material(
                self.snapshot, [self.actor, other], self.new, self.receipt
            )
        self.assertEqual(self.comp.calls, [])

    def test_failed_assignment_readback_rolls_back(self):
        def wrong_on_second_read():
            return self.old

        actual = self.comp.get_material
        reads = [0]

        def read(index):
            reads[0] += 1
            if reads[0] == 3:
                return wrong_on_second_read()
            return actual(index)

        self.comp.get_material = read
        with self.assertRaisesRegex(ValueError, "readback"):
            canary.try_road_only_material(
                self.snapshot, [self.actor], self.new, self.receipt
            )
        self.assertEqual(self.comp.calls[-1], self.old.get_path_name())

    def test_pure_library_has_no_run_on_import_or_unreal_import(self):
        # The imported library must remain inert outside the native entry point.
        self.assertFalse(hasattr(canary, "main"))
        self.assertNotIn("unreal", canary.__dict__)


class _UnrealObject:
    """In-memory API fixture; no native compilation, assets or proof claims."""

    def __init__(self, path="/Synthetic/Object"):
        self.path = path
        self.props = {}
        self.nodes = []

    def get_path_name(self):
        return self.path

    def set_editor_property(self, name, value):
        self.props[name] = value

    def get_editor_property(self, name):
        return self.props[name]

    def set_material_function(self, function):
        self.props["material_function"] = function
        return True


class DryImporterBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.created, self.property_links, self.expression_links = [], [], []
        self.failed_property = None
        api = SimpleNamespace()
        for name in ("Material", "MaterialInstanceConstant", "Texture2D"):
            setattr(api, name, type(name, (_UnrealObject,), {}))
        for name in (
            "TextureObjectParameter", "ScalarParameter", "MaterialFunctionCall",
            "StaticBool", "Normalize", "ComponentMask", "Constant", "Multiply",
        ):
            setattr(api, "MaterialExpression" + name, type(name, (_UnrealObject,), {}))

        def create_expression(material, cls):
            """Synthetic create_material_expression(material, expression_class)."""
            node = cls()
            material.nodes.append(node)
            return node

        def connect_expressions(a, output, b, socket):
            """Synthetic connect_material_expressions returns bool."""
            self.expression_links.append((a, output, b, socket))
            return True

        def connect_property(node, output, prop):
            """Synthetic connect_material_property returns bool."""
            self.property_links.append((node, output, prop))
            return prop != self.failed_property

        def parameter_nodes(instance, field):
            return [node for node in instance.props["parent"].nodes if field in node.props]

        def scalar_names(instance):
            """Synthetic get_scalar_parameter_names includes inherited values."""
            return [node.props["parameter_name"] for node in parameter_nodes(instance, "default_value")]

        def scalar_value(instance, name, association):
            """Synthetic effective scalar getter returns a native-like float32."""
            value = next(node.props["default_value"] for node in parameter_nodes(instance, "default_value")
                         if node.props["parameter_name"] == name)
            return struct.unpack("f", struct.pack("f", value))[0]

        def texture_value(instance, name, association):
            """Synthetic effective texture getter includes inherited values."""
            return next(node.props["texture"] for node in parameter_nodes(instance, "texture")
                        if node.props["parameter_name"] == name)

        def create_asset(name, package, cls, factory):
            asset = cls(package + "/" + name + "." + name)
            self.created.append(asset)
            return asset

        api.MaterialEditingLibrary = SimpleNamespace(
            create_material_expression=create_expression,
            connect_material_expressions=connect_expressions,
            connect_material_property=connect_property,
            get_scalar_parameter_names=scalar_names,
            get_material_instance_scalar_parameter_value=scalar_value,
            get_material_instance_texture_parameter_value=texture_value,
            get_texture_parameter_names=lambda instance: [
                node.props["parameter_name"] for node in parameter_nodes(instance, "texture")
            ],
            set_material_instance_parent=lambda instance, master: instance.set_editor_property("parent", master),
            update_material_instance=lambda instance: None,
            recompile_material=lambda master: None,
            layout_material_expressions=lambda master: None,
        )
        api.AssetToolsHelpers = SimpleNamespace(get_asset_tools=lambda: SimpleNamespace(create_asset=create_asset))
        api.MaterialFactoryNew = api.MaterialInstanceConstantFactoryNew = lambda: None
        api.MaterialParameterAssociation = SimpleNamespace(GLOBAL_PARAMETER="global")
        api.MaterialSamplerType = SimpleNamespace(
            SAMPLERTYPE_NORMAL="normal", SAMPLERTYPE_MASKS="masks", SAMPLERTYPE_COLOR="color",
        )
        api.TextureCompressionSettings = SimpleNamespace(TC_MASKS="masks")
        api.TextureAddress = SimpleNamespace(TA_WRAP="wrap")
        api.MaterialProperty = SimpleNamespace(**{name: name for name in (
            "MP_BASE_COLOR", "MP_NORMAL", "MP_AMBIENT_OCCLUSION", "MP_ROUGHNESS",
            "MP_SPECULAR", "MP_METALLIC", "MP_EMISSIVE_COLOR",
        )})
        api.load_asset = lambda path: _UnrealObject(path)
        api.log = lambda value: None
        path = Path(__file__).with_name("import_material_forge_variant.py")
        spec = importlib.util.spec_from_file_location("synthetic_forge_importer", path)
        self.forge = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"unreal": api}):
            spec.loader.exec_module(self.forge)
        self.forge.ROOT = Path(self.temp.name)
        self.api = api

    def import_fixture(self, variant=canary.VARIANT):
        provenance = {
            "family": canary.FAMILY, "variant": variant, "tile_metres": 4,
            "graph_sha256": "a" * 64, "local_mask_channels": {},
        }

        def texture(package, name, path, channel):
            value = self.api.Texture2D(package + "/" + name + "." + name)
            value.props.update(srgb=channel == "BaseColor", compression_settings="masks",
                               address_x="wrap", address_y="wrap")
            return value

        with (
            patch.object(self.forge, "_require_variant", return_value=({}, provenance)),
            patch.object(self.forge, "_verified_map", return_value=Path("synthetic-map")),
            patch.object(self.forge, "_import_texture", side_effect=texture),
        ):
            return self.forge.import_variant(Path("synthetic-variant"), canary.ASPHALT_DESTINATION)

    def test_dry_import_connects_explicit_scalars_and_direct_orm_green_without_ui(self):
        instance, receipt = self.import_fixture()
        canary.verify_import_receipt(receipt, "a" * 64)
        response = self.forge.verify_dry_asphalt_response(instance, receipt["assets"])
        self.assertEqual(response, receipt["dry_asphalt_response"])
        self.assertAlmostEqual(response["scalar_parameter_values"]["DrySpecular"], 0.2)
        self.assertEqual(response["scalar_parameter_values"]["DryMetallic"], 0)
        props = {prop: node for node, output, prop in self.property_links}
        self.assertEqual(props["MP_SPECULAR"].props["parameter_name"], "DrySpecular")
        self.assertEqual(props["MP_METALLIC"].props["parameter_name"], "DryMetallic")
        roughness = props["MP_ROUGHNESS"]
        self.assertIsInstance(roughness, self.api.MaterialExpressionComponentMask)
        self.assertEqual({key: roughness.props[key] for key in "rgba"},
                         {"r": False, "g": True, "b": False, "a": False})
        incoming = [(node, pin) for node, pin, target, socket in self.expression_links if target is roughness]
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming[0][1], "XYZ Texture")
        self.assertIsInstance(incoming[0][0], self.api.MaterialExpressionMaterialFunctionCall)
        self.assertFalse(response["shader_gpu_compilation_verified"])
        self.assertFalse(hasattr(self.api.MaterialEditingLibrary, "get_material_property_input_node"))

    def test_historical_asphalt_variants_keep_their_existing_response(self):
        for variant in ("base", "worn", "repaired"):
            self.property_links.clear()
            instance, receipt = self.import_fixture(variant)
            self.assertNotIn("dry_asphalt_response", receipt)
            self.assertNotIn("dry_surface_connections", receipt)
            self.assertEqual(self.forge.LIB.get_scalar_parameter_names(instance), ["TileSizeCm"])
            self.assertNotIn("MP_SPECULAR", [prop for node, pin, prop in self.property_links])
            self.assertNotIn("MP_METALLIC", [prop for node, pin, prop in self.property_links])

    def test_failed_dry_connection_stops_before_instance_creation(self):
        self.failed_property = "MP_SPECULAR"
        with self.assertRaisesRegex(RuntimeError, "output connection failed"):
            self.import_fixture()
        self.assertFalse(any(isinstance(asset, self.api.MaterialInstanceConstant) for asset in self.created))

    def test_missing_native_readback_api_stops_before_import(self):
        self.forge.LIB.get_material_instance_scalar_parameter_value = None
        with self.assertRaisesRegex(RuntimeError, "native dry asphalt API"):
            self.import_fixture()
        self.assertEqual(self.created, [])

    def test_fresh_scalar_and_orm_readback_rejects_changed_material_response(self):
        instance, receipt = self.import_fixture()
        parent = instance.props["parent"]
        specular = next(node for node in parent.nodes if node.props.get("parameter_name") == "DrySpecular")
        specular.props["default_value"] = 0.5
        with self.assertRaisesRegex(RuntimeError, "DrySpecular"):
            self.forge.verify_dry_asphalt_response(instance, receipt["assets"])
        specular.props["default_value"] = 0.2
        orm = next(node.props["texture"] for node in parent.nodes if node.props.get("parameter_name") == "ORMTex")
        for name, changed in (("srgb", True), ("compression_settings", "color"), ("address_x", "clamp")):
            original = orm.props[name]
            orm.props[name] = changed
            with self.subTest(property=name), self.assertRaisesRegex(RuntimeError, "ORM data texture"):
                self.forge.verify_dry_asphalt_response(instance, receipt["assets"])
            orm.props[name] = original
        extra = self.api.MaterialExpressionScalarParameter()
        extra.props.update(parameter_name="UnexpectedRoughnessMultiplier", default_value=1.0)
        parent.nodes.append(extra)
        with self.assertRaisesRegex(RuntimeError, "inventory"):
            self.forge.verify_dry_asphalt_response(instance, receipt["assets"])


if __name__ == "__main__":
    unittest.main()
