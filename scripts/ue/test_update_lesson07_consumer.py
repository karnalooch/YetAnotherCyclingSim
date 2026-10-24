"""Lightweight admission and transaction tests; never imports Unreal."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.ue import update_lesson07_consumer as update


def fixture(mode="visibility-only"):
    transforms = {name: {"location_cm": [0, 0, 0],
                         "rotation_deg_pitch_yaw_roll": [0, -90, 0],
                         "scale": [50, 50, 100 + index]}
                  for index, name in enumerate(sorted(update.ACTORS))}
    selected = sorted(update.ACTORS) if mode == "height-and-visibility" else [sorted(update.ACTORS)[0]]
    return {
        "schema_version": 1, "status": "DERIVED_TRANSPORT_READY_NATIVE_UPDATE_NOT_RUN",
        "mode": mode, "selected_actors": selected, "source_map": update.MAP,
        "source_head": "a" * 40, "source_map_identity": {"sha256": "b" * 64},
        "hda_asset": update.HDA, "hda_parameter": "terrain_cache", "target_edit_layer": update.LAYER,
        "required_native_update_contract": dict(update.CONTRACT),
        "native_actor_transforms_before": transforms,
        "required_common_scale_z": 103 if mode == "height-and-visibility" else None,
    }


def ready_state(ready=True):
    return {"success": True, "world_package": update.MAP, "all_up_to_date": ready,
            "actors": [{"actor": name, "edit_layer_guid": "guid-" + name, "landscape_guid": "landscape-" + name,
                        "edit_layer_locked": False, "edit_layer_visible": True, "up_to_date": ready}
                       for name in sorted(update.ACTORS)]}


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = fixture()
        receipt = self.root / "receipt.json"
        receipt.write_text("{}", encoding="utf-8")
        self.manifest["source_manifest"] = self.manifest["native_before"] = {
            "path": str(receipt), "sha256": update.sha256(receipt)}
        original = self.root / "source.bgeo.sc"
        original.write_bytes(b"retained source")
        target = self.root / "target.bgeo.sc"
        target.write_bytes(b"verified derived transport")
        self.manifest["tiles"] = [{
            "name": self.manifest["selected_actors"][0], "file": target.name,
            "bytes": target.stat().st_size, "sha256": update.sha256(target),
            "source_file": str(original), "source_sha256": update.sha256(original),
            "source_unchanged": True, "saved_reopen_verified": True, "height_output": None,
            "visibility_polarity": "UE hole=1-source validity; visible=0, hole=1",
            "visibility_output": {"resolution": [8129, 8129, 1]},
            "update_attributes": {
                "unreal_output_name": self.manifest["selected_actors"][0],
                "unreal_landscape_output_mode": 1, "unreal_landscape_editlayer_name": update.LAYER,
                "unreal_landscape_editlayer_clear": 0, "unreal_landscape_section_size": 127,
                "unreal_landscape_sections_per_component": 2, "unreal_landscape_layer_normalize": 0,
            },
        }]

    def test_authenticated_mask_transport_is_admitted(self):
        update.validate_manifest(self.manifest, self.root)

    def test_mutating_or_mismatched_transport_is_refused(self):
        for field, value in (("unreal_landscape_output_mode", 0),
                             ("unreal_landscape_editlayer_clear", 1),
                             ("unreal_output_name", "OtherActor")):
            changed = copy.deepcopy(self.manifest)
            changed["tiles"][0]["update_attributes"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "attributes"):
                update.validate_manifest(changed, self.root)

    def test_changed_source_or_transport_refuses_operation(self):
        for field in ("source_sha256", "sha256"):
            changed = copy.deepcopy(self.manifest)
            changed["tiles"][0][field] = "0" * 64
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                update.validate_manifest(changed, self.root)

    def test_mask_transport_cannot_include_height(self):
        self.manifest["tiles"][0]["height_output"] = {"resolution": [8129, 8129, 1]}
        with self.assertRaisesRegex(RuntimeError, "contains height"):
            update.validate_manifest(self.manifest, self.root)

    def test_height_mode_requires_four_actors_and_measured_common_scale(self):
        self.manifest["mode"] = "height-and-visibility"
        self.manifest["required_common_scale_z"] = 103
        with self.assertRaisesRegex(RuntimeError, "all four"):
            update.validate_manifest(self.manifest, self.root)

    def test_parent_path_escape_is_refused_before_reading_transport(self):
        self.manifest["tiles"][0]["file"] = "../target.bgeo.sc"
        with self.assertRaisesRegex(RuntimeError, "direct BGEO"):
            update.validate_manifest(self.manifest, self.root)


class NativeHapiObservationTests(unittest.TestCase):
    def test_cookable_requires_observed_safe_flags_and_same_instance(self):
        cookable = SimpleNamespace(get_path_name=lambda: "Cookable")
        good = {"success": True, "world_package": update.MAP, "cookable_path": "Cookable",
                "is_landscape_modification": True, "landscape_use_temp_layers": False}
        for field, value in ((None, None), ("success", False), ("landscape_use_temp_layers", True),
                             ("is_landscape_modification", False), ("cookable_path", "Other"),
                             ("landscape_use_temp_layers", None)):
            state = dict(good)
            if field is not None:
                state[field] = value
            api = SimpleNamespace(YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                read_lesson07_cookable_state=lambda _: json.dumps(state)))
            with self.subTest(field=field):
                if field is None:
                    self.assertEqual(update.validate_cookable(api, cookable), good)
                else:
                    with self.assertRaisesRegex(RuntimeError, "configuration"):
                        update.validate_cookable(api, cookable)

    def test_actual_output_contract_refuses_changed_target_extents_flags_or_layers(self):
        actor = SimpleNamespace(get_name=lambda: sorted(update.ACTORS)[0],
                                get_path_name=lambda: "Landscape")
        output = SimpleNamespace(
            get_path_name=lambda: "Output",
            get_class=lambda: SimpleNamespace(get_name=lambda: "HoudiniLandscapeTargetLayerOutput"))
        record = SimpleNamespace(get_editor_property=lambda name: output if name == "output_object" else None)
        wrapper = SimpleNamespace(get_output_objects=lambda _: [record])
        good = {
            "success": True, "world_package": update.MAP, "output_path": "Output",
            "actor": actor.get_name(), "landscape_path": "Landscape", "landscape_proxy_path": "Landscape",
            "created_landscape": False, "layer_was_created": False, "clear_layer": False,
            "cooked_layer_requires_baking": False, "baked_edit_layer": update.LAYER,
            "cooked_edit_layer": update.LAYER, "extents": [0, 0, 8128, 8128], "target_layer": "visibility",
        }
        changes = [(None, None), ("success", False), ("world_package", "/Game/Other"),
                   ("output_path", "OtherOutput"), ("landscape_path", "OtherActor"),
                   ("landscape_proxy_path", "OtherActor"), ("target_layer", "height"),
                   ("baked_edit_layer", "Other"), ("cooked_edit_layer", "Temporary"),
                   ("extents", [0, 0, 8127, 8128])]
        changes += [(key, value) for key in ("created_landscape", "layer_was_created", "clear_layer",
                                            "cooked_layer_requires_baking") for value in (True, None)]
        for field, value in changes:
            state = dict(good)
            if field is not None:
                state[field] = value
            api = SimpleNamespace(YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                read_lesson07_output_state=lambda _: json.dumps(state)))
            with self.subTest(field=field, value=value):
                if field is None:
                    self.assertEqual(update.validate_outputs(api, wrapper, actor, "visibility-only")[0]["extents"],
                                     [0, 0, 8128, 8128])
                else:
                    with self.assertRaises(RuntimeError):
                        update.validate_outputs(api, wrapper, actor, "visibility-only")

    def test_unsafe_configuration_never_reaches_recook(self):
        wrapper = Mock()
        wrapper.is_auto_cooking_enabled.return_value = False
        wrapper.is_auto_bake_enabled.return_value = False
        api = SimpleNamespace(
            HoudiniPublicAPISettings=SimpleNamespace,
            HoudiniPublicAPIInstantiationType=SimpleNamespace(HOUDINI_ASSET_COMPONENT=1))
        public = SimpleNamespace(instantiate=lambda *_: wrapper)
        with patch.object(update, "validate_cookable", side_effect=RuntimeError("Unsafe configuration")):
            with self.assertRaisesRegex(RuntimeError, "Unsafe"):
                update.update_tile(api, public, object(), object(), object(),
                                   {"name": sorted(update.ACTORS)[0]}, Path("."), "visibility-only")
        wrapper.recook.assert_not_called()
        wrapper.set_string_parameter_value.assert_not_called()

    def test_recook_with_none_error_preserves_success_and_failure_paths(self):
        for cooked in (True, False):
            with self.subTest(cooked=cooked):
                wrapper = Mock()
                wrapper.is_auto_cooking_enabled.return_value = False
                wrapper.is_auto_bake_enabled.return_value = False
                wrapper.recook.return_value = cooked
                wrapper.get_last_error_message.return_value = None
                wrapper.set_string_parameter_value.return_value = True
                wrapper.delete_instantiated_asset.return_value = True
                api = SimpleNamespace(
                    HoudiniPublicAPISettings=SimpleNamespace,
                    HoudiniPublicAPIInstantiationType=SimpleNamespace(HOUDINI_ASSET_COMPONENT=1),
                    HoudiniPublicAPICookMode=SimpleNamespace(BLOCKING=2))
                public = SimpleNamespace(instantiate=lambda *_: wrapper)
                tile = {"name": sorted(update.ACTORS)[0], "file": "tile.bgeo.sc"}
                rows = [{"target_layer": "visibility"}]
                with patch.object(update, "validate_cookable") as configuration, \
                        patch.object(update, "validate_outputs", return_value=rows) as outputs:
                    if cooked:
                        self.assertEqual(update.update_tile(
                            api, public, object(), object(), object(), tile, Path("."), "visibility-only"), rows)
                        self.assertEqual(configuration.call_count, 2)
                        outputs.assert_called_once()
                        wrapper.delete_instantiated_asset.assert_called_once()
                        wrapper.get_last_error_message.assert_not_called()
                    else:
                        with self.assertRaisesRegex(RuntimeError, "^Native update failed: $"):
                            update.update_tile(
                                api, public, object(), object(), object(), tile, Path("."), "visibility-only")
                        outputs.assert_not_called()
                        wrapper.delete_instantiated_asset.assert_not_called()


class CompositionTests(unittest.TestCase):
    def test_pending_native_composition_yields_real_ticks(self):
        native = Mock(side_effect=[json.dumps(ready_state(False)), json.dumps(ready_state(True))])
        api = SimpleNamespace(YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
            read_lesson07_layer_update_state=native))
        result = {}
        operation = update.wait_for_layers(api, result, "composition")
        self.assertIsNone(next(operation))
        with self.assertRaises(StopIteration):
            next(operation)
        self.assertEqual(native.call_count, 2)
        self.assertTrue(result["composition"]["all_up_to_date"])

    def test_missing_native_observation_is_not_completion(self):
        api = SimpleNamespace(YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
            read_lesson07_layer_update_state=lambda: '{"success":false}'))
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            next(update.wait_for_layers(api, {}, "composition"))

    def test_hidden_or_locked_layer_is_refused(self):
        value = ready_state()
        value["actors"][0]["edit_layer_visible"] = False
        api = SimpleNamespace(YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
            read_lesson07_layer_update_state=lambda: json.dumps(value)))
        with self.assertRaisesRegex(RuntimeError, "hidden"):
            next(update.wait_for_layers(api, {}, "composition"))

    def test_common_scale_is_the_only_actor_change_admitted(self):
        manifest = fixture("height-and-visibility")
        before = copy.deepcopy(manifest["native_actor_transforms_before"])
        for name, row in before.items():
            row.update(edit_layer_guid="layer-" + name, landscape_guid="actor-" + name)
        after = copy.deepcopy(before)
        for row in after.values():
            row["scale"][2] = 103
        update.validate_actor_preservation(before, after, manifest)
        after[sorted(update.ACTORS)[0]]["edit_layer_guid"] = "replacement"
        with self.assertRaisesRegex(RuntimeError, "identity"):
            update.validate_actor_preservation(before, after, manifest)

    def test_mask_height_change_fails_after_composition(self):
        manifest = fixture()
        manifest["tiles"] = [{"name": manifest["selected_actors"][0]}]
        before = manifest["native_actor_transforms_before"]
        actors = {name: Mock() for name in update.ACTORS}
        public = SimpleNamespace(is_session_valid=lambda: True)
        asset = SimpleNamespace(get_path_name=lambda: update.HDA)
        api = SimpleNamespace(
            HoudiniPublicAPIBlueprintLib=SimpleNamespace(get_api=lambda: public),
            load_asset=lambda _: asset, EditorActorSubsystem=object, HoudiniAssetActor=type("HDA", (), {}),
            get_editor_subsystem=lambda _: SimpleNamespace(get_all_level_actors=lambda: []))

        def wait(_api, result, key):
            result[key] = ready_state()
            return
            yield  # This helper models an already completed native observation.

        with patch.object(update, "actor_snapshot", return_value=(before, actors)), \
                patch.object(update, "wait_for_layers", side_effect=wait), \
                patch.object(update, "update_tile", return_value=[]), \
                patch.object(update, "height_snapshot", side_effect=[{"digest": "before"}, {"digest": "changed"}]):
            operation = update.perform_update(api, manifest, Path("."), object(), {})
            next(operation)
            with self.assertRaisesRegex(RuntimeError, "Mask-only update changed"):
                next(operation)


class SaveBoundaryTests(unittest.TestCase):
    def test_owned_session_closes_after_operation_and_before_quit(self):
        for remains_valid in (False, True):
            with self.subTest(remains_valid=remains_valid), tempfile.TemporaryDirectory() as temp:
                events, callbacks = [], []
                public = SimpleNamespace(
                    is_session_valid=Mock(side_effect=[True, remains_valid]),
                    stop_session=lambda: events.append("stop_session"))
                api = SimpleNamespace(
                    Paths=SimpleNamespace(get_project_file_path=lambda:
                                          "D:/yacs/work/lesson07-cleanup-test/YetAnotherCyclingSim.uproject"),
                    HoudiniPublicAPIBlueprintLib=SimpleNamespace(get_api=lambda: public),
                    EditorPythonScripting=SimpleNamespace(set_keep_python_script_alive=lambda _: None),
                    register_slate_post_tick_callback=lambda callback: callbacks.append(callback) or 1,
                    unregister_slate_post_tick_callback=lambda _: events.append("unregister"),
                    SystemLibrary=SimpleNamespace(execute_console_command=lambda *args: events.append(args[-1])),
                    log=lambda _: None, log_error=lambda _: None)
                output = Path(temp) / "report.json"

                def operation(_api, _project, _output, result):
                    result["houdini_session"] = {"session_valid": True}
                    events.extend(["outputs_verified", "height_hashes_verified", "save_boundary_complete"])
                    result["status"] = "CANARY_COMPLETED_UNSAVED"
                    return
                    yield

                with patch.dict("sys.modules", {"unreal": api}), patch.dict(update.os.environ, {
                        "YACS_L07_UPDATE_PROJECT": "D:/yacs/work/lesson07-cleanup-test",
                        "YACS_L07_UPDATE_REPORT": str(output)}), \
                        patch.object(update, "execute", side_effect=operation):
                    update.main()
                    callbacks[0](0)
                self.assertEqual(events, ["outputs_verified", "height_hashes_verified", "save_boundary_complete",
                                          "stop_session", "unregister", "QUIT_EDITOR"])
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(report["houdini_session_close"]["valid_after"], remains_valid)
                self.assertEqual(report["status"],
                                 "FAILED_SESSION_CLOSE" if remains_valid else "CANARY_COMPLETED_UNSAVED")

    def test_failure_or_unsaved_canary_never_calls_save(self):
        for should_fail, save in ((True, "1"), (False, "0"), (False, "1")):
            with self.subTest(should_fail=should_fail, save=save), tempfile.TemporaryDirectory() as temp:
                project = Path(temp)
                manifest = fixture()
                manifest_path = project / "manifest.json"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                map_path = update.package_file(project, update.MAP, ".umap")
                map_path.parent.mkdir(parents=True)
                map_path.write_bytes(b"original map")
                hda_path = update.package_file(project, update.HDA)
                hda_path.parent.mkdir(parents=True)
                hda_path.write_bytes(b"existing HDA")
                save_map = Mock(return_value=True)
                api = SimpleNamespace(
                    SystemLibrary=SimpleNamespace(get_command_line=lambda: "-RenderOffscreen",
                                                  get_engine_version=lambda: "5.8.2-56702186"),
                    EditorLoadingAndSavingUtils=SimpleNamespace(
                        get_dirty_map_packages=lambda: [], get_dirty_content_packages=lambda: [],
                        load_map=lambda _: SimpleNamespace(get_path_name=lambda: update.MAP + ".Map"),
                        save_map=save_map))

                def perform(*_args):
                    yield
                    if should_fail:
                        raise RuntimeError("second tile failed")

                environment = {
                    "YACS_L07_UPDATE_MANIFEST": str(manifest_path),
                    "YACS_L07_UPDATE_MANIFEST_SHA256": update.sha256(manifest_path),
                    "YACS_L07_UPDATE_MAP_SHA256": update.sha256(map_path), "YACS_L07_UPDATE_SAVE": save,
                }
                result = {"map_saved": False}
                with patch.dict(update.os.environ, environment), \
                        patch.object(update, "HDA_SHA256", update.sha256(hda_path)), \
                        patch.object(update, "validate_manifest"), \
                        patch.object(update.shutil, "disk_usage", return_value=SimpleNamespace(free=100 * 1024**3)), \
                        patch.object(update, "perform_update", side_effect=perform):
                    operation = update.execute(api, project, project / "report.json", result)
                    next(operation)
                    save_map.assert_not_called()
                    if should_fail:
                        with self.assertRaisesRegex(RuntimeError, "second tile"):
                            next(operation)
                    else:
                        with self.assertRaises(StopIteration):
                            next(operation)
                self.assertEqual(save_map.call_count, int(not should_fail and save == "1"))
                self.assertEqual(map_path.read_bytes(), b"original map")


if __name__ == "__main__":
    unittest.main()
