"""CPU boundary tests for passive observation; these are not native UE proof."""

import builtins
import importlib.util
import json
from pathlib import Path
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.ue import lesson07_observe_editor as reader


class Object:
    def __init__(self, path, kind="Object", properties=None):
        self.path = path
        self.kind = kind
        self.properties = properties or {}

    def get_path_name(self):
        return self.path

    def get_name(self):
        return self.path.rsplit(".", 1)[-1]

    def get_class(self):
        return SimpleNamespace(get_name=lambda: self.kind)

    def get_editor_property(self, name):
        if name not in self.properties:
            raise AttributeError("Synthetic unavailable property: " + name)
        return self.properties[name]


class Landscape(Object):
    def __init__(self, name, instance, index):
        super().__init__(
            reader.WORLD + ":PersistentLevel." + name,
            properties={
                "landscape_material": instance,
                "landscape_hole_material": None,
            },
        )
        self.position = SimpleNamespace(x=index + 0.25, y=-index - 0.5, z=71.0)
        self.components = 1024

    def get_actor_location(self):
        return self.position

    def get_actor_rotation(self):
        return SimpleNamespace(pitch=0.0, yaw=-90.0, roll=0.000002)

    def get_actor_scale3d(self):
        return SimpleNamespace(x=50.0, y=50.0, z=561.389892578125)

    def get_components_by_class(self, _cls):
        return [None] * self.components


class ArrayTexture(Object):
    pass


class Fixture:
    def __init__(self):
        self.forbidden = Mock(side_effect=AssertionError("Mutating API was invoked"))
        self.master = Object(
            reader.MASTER,
            "Material",
            {
                "blend_mode": "BLEND_MASKED",
                "use_material_attributes": True,
                "tangent_space_normal": True,
                "enable_tessellation": False,
            },
        )
        self.instance = Object(
            reader.INSTANCE, "MaterialInstanceConstant", {"parent": self.master}
        )
        self.function = Object("/Game/Test/Function.Function", "MaterialFunction")
        self.constant = Object(
            self.function.path + ":Constant", "MaterialExpressionConstant", {"r": 0.5}
        )
        self.call = Object(
            self.master.path + ":Call",
            "MaterialExpressionMaterialFunctionCall",
            {"material_function": self.function},
        )
        self.master_nodes = [self.call]
        self.function_nodes = [self.constant]
        self.scalars = dict(reader.EXPECTED_SCALARS)
        self.map_dirty = [Object(reader.ROOT + "/OwnerDirtyMap")]
        self.content_dirty = [Object(reader.ROOT + "/OwnerDirtyMaterial")]
        self.actors = [
            Landscape(name, self.instance, index)
            for index, name in enumerate(sorted(reader.EXPECTED_ACTORS))
        ]
        self.editor = SimpleNamespace(
            get_editor_world=Mock(return_value=Object(reader.WORLD)),
            get_level_viewport_camera_info=lambda: (
                SimpleNamespace(x=1.0, y=2.0, z=3.0),
                SimpleNamespace(pitch=-10.0, yaw=40.0, roll=0.0),
            ),
            get_level_viewport_size=lambda: SimpleNamespace(x=1920, y=1080),
            set_level_viewport_camera_info=self.forbidden,
        )
        self.actor_api = SimpleNamespace(
            get_all_level_actors=Mock(return_value=self.actors),
            spawn_actor_from_class=self.forbidden,
        )
        self.lib = SimpleNamespace(
            get_material_expressions=Mock(side_effect=lambda _: self.master_nodes),
            get_material_function_expressions=Mock(
                side_effect=lambda _: self.function_nodes
            ),
            get_material_expression_input_names=lambda _: ["A", "B"],
            get_material_expression_input_types=lambda _: [1, 1],
            get_material_expression_output_names=lambda _: ["First", "Second"],
            get_inputs_for_material_expression=Mock(
                return_value=[self.constant, self.constant]
            ),
            get_inputs_for_material_function_expression=Mock(return_value=[None, None]),
            get_scalar_parameter_names=lambda _: list(self.scalars),
            get_material_instance_scalar_parameter_value=Mock(
                side_effect=lambda _, name: self.scalars[name]
            ),
            get_texture_parameter_names=lambda _: [],
            recompile_material=self.forbidden,
            update_material_instance=self.forbidden,
            refresh_material_editor=self.forbidden,
            set_material_instance_scalar_parameter_value=self.forbidden,
        )
        self.api = SimpleNamespace(
            Paths=SimpleNamespace(
                project_dir=lambda: "D:/yacs/project/",
                get_project_file_path=lambda: reader.PROJECT_FILE,
                convert_relative_path_to_full=str,
            ),
            UnrealEditorSubsystem="editor",
            EditorActorSubsystem="actors",
            LandscapeProxy=Landscape,
            LandscapeComponent=object,
            Texture2DArray=ArrayTexture,
            SystemLibrary=SimpleNamespace(
                get_engine_version=lambda: "5.8.2-test",
                execute_console_command=self.forbidden,
            ),
            EditorLoadingAndSavingUtils=SimpleNamespace(
                get_dirty_map_packages=Mock(side_effect=lambda: list(self.map_dirty)),
                get_dirty_content_packages=Mock(
                    side_effect=lambda: list(self.content_dirty)
                ),
                save_dirty_packages=self.forbidden,
                load_map=self.forbidden,
            ),
            AutomationLibrary=SimpleNamespace(
                get_editor_active_viewport_view_mode=lambda: "VMI_LIT",
                set_editor_viewport_view_mode=self.forbidden,
                take_high_res_screenshot=self.forbidden,
            ),
            EditorAssetLibrary=SimpleNamespace(
                load_asset=self.forbidden, save_loaded_asset=self.forbidden
            ),
            MaterialEditingLibrary=self.lib,
            load_asset=self.forbidden,
            load_object=self.forbidden,
            collect_garbage=self.forbidden,
            get_editor_subsystem=Mock(
                side_effect=lambda kind: {
                    "editor": self.editor,
                    "actors": self.actor_api,
                }[kind]
            ),
            find_object=Mock(
                side_effect=lambda _, name, **kwargs: {
                    reader.INSTANCE: self.instance,
                    reader.MASTER: self.master,
                }.get(name)
            ),
        )

    def collect(self):
        result = reader.collect(self.api)
        self.forbidden.assert_not_called()
        return result


class PassiveObservationTests(unittest.TestCase):
    def test_import_and_main_are_inert_without_unreal(self):
        path = Path(reader.__file__)
        original = builtins.__import__

        def reject_unreal(name, *args, **kwargs):
            if name == "unreal":
                raise AssertionError("Unreal import occurred before collect")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_unreal):
            spec = importlib.util.spec_from_file_location("passive_import_check", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            runpy.run_path(str(path), run_name="__main__")
        self.assertTrue(callable(module.collect))

    def test_wrong_directory_or_project_file_rejects_before_editor_or_assets(self):
        for field, value in (
            ("project_dir", "D:/another/project"),
            ("get_project_file_path", "D:/yacs/project/Other.uproject"),
        ):
            with self.subTest(field=field):
                fixture = Fixture()
                setattr(fixture.api.Paths, field, lambda: value)
                with self.assertRaisesRegex(RuntimeError, "Wrong active project"):
                    fixture.collect()
                fixture.api.get_editor_subsystem.assert_not_called()
                fixture.api.find_object.assert_not_called()
                fixture.forbidden.assert_not_called()

    def test_wrong_or_missing_world_rejects_before_asset_or_actor_handling(self):
        for world in (None, Object("/Game/Other.Other")):
            with self.subTest(world=world):
                fixture = Fixture()
                fixture.editor.get_editor_world.return_value = world
                with self.assertRaisesRegex(RuntimeError, "Wrong active EditorWorld"):
                    fixture.collect()
                fixture.api.find_object.assert_not_called()
                fixture.actor_api.get_all_level_actors.assert_not_called()

    def test_native_identity_api_error_propagates_before_asset_handling(self):
        fixture = Fixture()
        fixture.editor.get_editor_world.side_effect = RuntimeError(
            "world getter unavailable"
        )
        with self.assertRaisesRegex(RuntimeError, "world getter unavailable"):
            fixture.collect()
        fixture.api.find_object.assert_not_called()

    def test_collects_dirty_state_transforms_and_bindings_without_mutation(self):
        fixture = Fixture()
        result = fixture.collect()
        self.assertEqual(result["actors"]["value"]["component_count"], 4096)
        self.assertEqual(
            result["actors"]["value"]["actors"][0]["location_cm"], [0.25, -0.5, 71.0]
        )
        self.assertEqual(
            result["dirty_before"]["maps"]["value"], [reader.ROOT + "/OwnerDirtyMap"]
        )
        self.assertTrue(result["dirty_sets_equal"])
        checks = result["validation"]["baseline_checks"]
        self.assertEqual(checks["scalar.Global Normal Flatten"]["status"], "MATCH")
        self.assertEqual(checks["instance_parent"]["status"], "MATCH")
        self.assertFalse(result["limitations"]["new_captures"])
        self.assertFalse(result["validation"]["visual_or_native_graph_acceptance"])
        self.assertFalse(result["camera"]["fov"]["observed"])
        self.assertIsNone(
            result["camera"]["primary_and_active_viewport_identity_match"]
        )
        for call in fixture.api.find_object.call_args_list:
            self.assertIs(call.kwargs["follow_redirectors"], False)
        json.dumps(result, allow_nan=False)

    def test_baseline_deviations_and_rejected_references_are_explicit(self):
        fixture = Fixture()
        fixture.scalars["Global Normal Flatten"] = 0.2
        fixture.scalars.pop("UV Distort")
        fixture.actors[0].components = 1000
        fixture.instance.properties["parent"] = Object("/Game/Wrong.Wrong")
        fixture.function.path = "/Engine/Functions/Engine_MaterialFunctions03/Texturing/TextureVariation.TextureVariation"
        result = fixture.collect()
        checks = result["validation"]["baseline_checks"]
        self.assertEqual(checks["scalar.Global Normal Flatten"]["status"], "MISMATCH")
        self.assertEqual(checks["scalar.UV Distort"]["status"], "UNAVAILABLE")
        self.assertEqual(checks["component_count"]["status"], "MISMATCH")
        self.assertEqual(checks["instance_parent"]["status"], "MISMATCH")
        self.assertEqual(
            len(
                result["validation"][
                    "rejected_variation_references_in_enumerated_nodes"
                ]
            ),
            1,
        )
        self.assertFalse(result["validation"]["variation_absence_proved"])

    def test_dirty_delta_is_not_silently_accepted(self):
        fixture = Fixture()
        fixture.api.EditorLoadingAndSavingUtils.get_dirty_map_packages.side_effect = [
            [],
            fixture.map_dirty,
        ]
        result = fixture.collect()
        self.assertFalse(result["dirty_sets_equal"])
        self.assertEqual(
            result["validation"]["baseline_checks"]["dirty_sets_equal"]["status"],
            "MISMATCH",
        )

    def test_missing_optional_apis_remain_unavailable(self):
        fixture = Fixture()
        del fixture.api.EditorLoadingAndSavingUtils.get_dirty_content_packages
        del fixture.lib.get_inputs_for_material_function_expression
        result = fixture.collect()
        self.assertIsNone(result["dirty_sets_equal"])
        self.assertEqual(
            result["validation"]["baseline_checks"]["dirty_sets_equal"]["status"],
            "UNAVAILABLE",
        )
        graph = result["graph"]["value"]
        node = graph["graphs"][fixture.function.path]["nodes"][0]
        self.assertFalse(node["producer_nodes_in_api_order"]["observed"])
        self.assertGreater(result["validation"]["unavailable_observation_count"], 0)

    def test_missing_loaded_lookup_does_not_fall_back_to_loading(self):
        fixture = Fixture()
        del fixture.api.find_object
        result = fixture.collect()
        self.assertFalse(result["loaded_assets"]["instance"]["observed"])
        self.assertFalse(result["graph"]["observed"])
        self.assertEqual(
            result["validation"]["baseline_checks"]["instance_parent"]["status"],
            "UNAVAILABLE",
        )

    def test_property_error_and_nonfinite_scalar_are_not_observed_values(self):
        fixture = Fixture()
        fixture.constant.properties = {}
        fixture.scalars["Global Normal Flatten"] = float("nan")
        result = fixture.collect()
        scalar = result["instance"]["value"]["scalars"]["Global Normal Flatten"]
        self.assertFalse(scalar["observed"])
        self.assertIn("Non-finite", scalar["error"])
        node = result["graph"]["value"]["graphs"][fixture.function.path]["nodes"][0]
        self.assertFalse(node["properties"]["r"]["observed"])
        self.assertIn("Synthetic unavailable", node["properties"]["r"]["error"])
        json.dumps(result, allow_nan=False)

    def test_function_ownership_and_raw_ambiguous_connections_are_preserved(self):
        fixture = Fixture()
        result = fixture.collect()
        fixture.lib.get_inputs_for_material_function_expression.assert_called_once_with(
            fixture.function, fixture.constant
        )
        fixture.lib.get_inputs_for_material_expression.assert_called_once_with(
            fixture.master, fixture.call
        )
        graph = result["graph"]["value"]
        nodes = graph["graphs"][fixture.master.path]["nodes"]
        self.assertEqual(
            nodes[0]["producer_nodes_in_api_order"]["value"],
            [fixture.constant.path] * 2,
        )
        self.assertFalse(graph["input_array_alignment_verified"])
        self.assertFalse(graph["selected_output_indices_observed"])
        self.assertFalse(graph["connection_component_masks_observed"])

    def test_node_and_graph_limits_are_reported_without_acceptance(self):
        for limit in ("MAX_NODES", "MAX_GRAPHS"):
            with self.subTest(limit=limit), patch.object(reader, limit, 1):
                result = Fixture().collect()
                graph = result["graph"]["value"]
                self.assertTrue(graph["limits_reached"])
                self.assertFalse(graph["graph_contract_pass"])
                self.assertEqual(
                    result["validation"]["graph_truncation"], graph["limits_reached"]
                )
                if limit == "MAX_NODES":
                    self.assertLessEqual(graph["observed_node_count"], 1)
                else:
                    self.assertLessEqual(len(graph["graphs"]), 1)

    def test_recursive_function_cycle_terminates_without_global_changes(self):
        fixture = Fixture()
        fixture.function_nodes = [
            Object(
                fixture.function.path + ":SelfCall",
                "MaterialExpressionMaterialFunctionCall",
                {"material_function": fixture.function},
            )
        ]
        before_scalars = dict(reader.EXPECTED_SCALARS)
        result = fixture.collect()
        self.assertEqual(len(result["graph"]["value"]["graphs"]), 2)
        self.assertEqual(result["graph"]["value"]["limits_reached"], [])
        self.assertEqual(reader.EXPECTED_SCALARS, before_scalars)


if __name__ == "__main__":
    unittest.main()
