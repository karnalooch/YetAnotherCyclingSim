"""Synthetic native-object fault tests; no Unreal, server, build or real image."""

import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.ue import level_editor_material_bridge as bridge


class NativeObject:
    def __init__(self, name):
        self.name = name

    def get_path_name(self):
        return self.name


class NativeSettings:
    """Generic UObject wrapper with UPROPERTY names and no generated aliases."""

    def __init__(self, properties):
        self.properties = properties
        self.reads = []

    def get_editor_property(self, name):
        self.reads.append(name)
        if name not in self.properties:
            raise ValueError("Native settings property is unavailable: " + name)
        return self.properties[name]


class Material(NativeObject):
    def __init__(self, name, parent=None):
        super().__init__(name)
        self.parent = parent
        self.scalar = 0.90
        self.color = [0.64, 0.63, 0.59, 1.0]

    def get_editor_property(self, name):
        assert name == "parent"
        return self.parent


class Mid(Material):
    fail_vector = False

    def get_scalar_parameter_value(self, name):
        assert name == "PaintRoughness"
        return self.scalar

    def get_vector_parameter_value(self, name):
        assert name == "PaintColor"
        return SimpleNamespace(
            **dict(zip(("r", "g", "b", "a"), self.color, strict=True))
        )

    def set_scalar_parameter_value(self, name, value):
        assert name == "PaintRoughness"
        self.scalar = value

    def set_vector_parameter_value(self, name, value):
        assert name == "PaintColor"
        if self.fail_vector:
            raise RuntimeError("synthetic vector setter failed after scalar")
        self.color = [value.r, value.g, value.b, value.a]


class Component(NativeObject):
    def __init__(self, name, material):
        super().__init__(name)
        self.material = material
        self.fail_once = False
        self.on_failure = lambda: None

    def get_material(self, slot):
        assert slot == 0
        return self.material

    def get_num_materials(self):
        return 1

    def set_material(self, slot, material):
        assert slot == 0
        self.material = material
        if self.fail_once:
            self.fail_once = False
            self.on_failure()
            raise RuntimeError("synthetic slot setter failed after assignment")


class Actor(NativeObject):
    def __init__(self, name, component):
        super().__init__(name)
        self.component = component

    def get_dynamic_mesh_component(self):
        return self.component


class Fixture:
    def __init__(self, root):
        self.root = root
        self.manager = object.__new__(bridge.MaterialPreview)
        manager = self.manager
        self.world = NativeObject(bridge.MAP_PACKAGE + ".L_SaCalobraRoadAsphaltReview")
        self.current_world = self.world
        self.master = Material(bridge.PAINT_MASTER)
        self.original = Material(bridge.PAINT_MATERIAL, self.master)
        self.components = [
            Component("component" + str(index), self.original) for index in range(4)
        ]
        self.actors = [
            Actor("actor" + str(index), component)
            for index, component in enumerate(self.components)
        ]
        self.mids, self.captures, self.callbacks = [], [], []
        self.dirty = [NativeObject("/Game/OwnerUnsavedMaterial")]
        self.camera = (
            SimpleNamespace(x=1.0, y=2.0, z=3.0),
            SimpleNamespace(pitch=4.0, yaw=5.0, roll=6.0),
        )
        self.api = SimpleNamespace(
            MaterialInstanceDynamic=Mid,
            MaterialLibrary=SimpleNamespace(
                create_dynamic_material_instance=self.create_mid
            ),
            MIDCreationFlags=SimpleNamespace(TRANSIENT="TRANSIENT"),
            LinearColor=lambda *values: SimpleNamespace(
                **dict(zip(("r", "g", "b", "a"), values, strict=True))
            ),
            MaterialEditingLibrary=SimpleNamespace(
                get_material_instance_scalar_parameter_value=lambda material, _name: (
                    material.scalar
                ),
                get_material_instance_vector_parameter_value=lambda material, _name: (
                    SimpleNamespace(
                        **dict(zip(("r", "g", "b", "a"), material.color, strict=True))
                    )
                ),
            ),
            Paths=SimpleNamespace(project_dir=lambda: str(root)),
            EditorLoadingAndSavingUtils=SimpleNamespace(
                get_dirty_map_packages=list,
                get_dirty_content_packages=lambda: self.dirty,
            ),
            AutomationLibrary=SimpleNamespace(
                get_editor_active_viewport_view_mode=lambda: "LIT",
                finish_loading_before_screenshot=lambda: None,
                take_high_res_screenshot=self.capture,
            ),
            ViewModeIndex=SimpleNamespace(VMI_LIT="LIT"),
            ComparisonTolerance=SimpleNamespace(LOW="LOW"),
            register_slate_post_tick_callback=self.register,
            unregister_slate_post_tick_callback=lambda handle: self.callbacks.remove(
                handle
            ),
        )
        manager.api, manager.root = self.api, root
        manager.world = self.world
        manager.editor = SimpleNamespace(
            get_editor_world=lambda: self.current_world,
            get_level_viewport_camera_info=lambda: self.camera,
        )
        manager.identity = {
            "session_id": "synthetic",
            "editor_pid": bridge.os.getpid(),
            "editor_start_filetime_utc": "12345",
            "project_root": str(root),
            "map_package": bridge.MAP_PACKAGE,
            "runtime_source_sha": bridge.RUNTIME_SHA,
            "launcher_sha": "a" * 40,
        }
        manager.sequence, manager.used, manager.pending, manager.tick_handle = (
            0,
            set(),
            None,
            None,
        )
        manager.in_tick = False
        manager.native_guard = lambda: None
        manager.saved_digest, manager.last_source_digest = "b" * 64, "c" * 64
        manager.verify_saved_inputs = lambda: manager.saved_digest
        manager.original, manager.mid = self.original, None
        manager.targets = [
            (actor, component, self.original)
            for actor, component in zip(self.actors, self.components, strict=True)
        ]
        manager.initial_values = {
            "paint_roughness": self.original.scalar,
            "paint_color": list(self.original.color),
        }
        manager.expected_values = copy.deepcopy(manager.initial_values)
        manager.original_bindings = manager.observe()

    def create_mid(self, world, original, creation_flags):
        assert (
            world == self.world
            and original == self.original
            and creation_flags == "TRANSIENT"
        )
        mid = Mid("/SyntheticTransient.MID_" + str(len(self.mids)), original)
        self.mids.append(mid)
        return mid

    def register(self, callback):
        self.callbacks.append(callback)
        return callback

    def capture(self, **kwargs):
        self.captures.append(kwargs)
        # Synthetic header-shaped bytes exercise completion checks only.
        raw = (
            b"\x89PNG\r\n\x1a\n"
            + struct.pack(">I", 13)
            + b"IHDR"
            + struct.pack(">II", 1280, 720)
            + bytes(5000)
        )
        Path(kwargs["filename"]).write_bytes(raw)
        return SimpleNamespace(is_valid_task=lambda: True, is_task_done=lambda: True)

    def complete(self):
        for _ in range(4):
            self.manager.tick(0.1)
        assert self.manager.pending is None

    def request(self, name, *, action="set", sequence=None, **values):
        request = {
            "schema_version": 1,
            "session_id": "synthetic",
            "request_id": name,
            "action": action,
            "expected_sequence": self.manager.sequence
            if sequence is None
            else sequence,
        }
        if action == "set":
            request.update(paint_roughness=0.35, paint_color=[0.2, 0.4, 0.6, 1.0])
        request.update(values)
        return bridge.canonical(request)

    def receipt(self, name):
        return json.loads(
            (self.root / bridge.REQUEST_ROOT / name / "receipt.json").read_text()
        )


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Fixture(Path(self.temporary.name))
        self.manager = self.fixture.manager

    def test_two_requests_reuse_bound_mid_and_restore_exact_prior_state(self):
        before = self.manager.observe()
        initial_dirty = bridge.dirty_state(self.fixture.api)
        response = json.loads(self.manager.handle_json(self.fixture.request("first")))
        self.assertEqual(response["status"], "ACCEPTED")
        self.assertIsNotNone(self.manager.pending)
        with self.assertRaisesRegex(ValueError, "still pending"):
            self.manager.handle_json(self.fixture.request("overlap", action="inspect"))
        self.fixture.complete()
        first = self.fixture.receipt("first")
        self.manager.handle_json(
            self.fixture.request(
                "second", paint_roughness=0.75, paint_color=[0.6, 0.3, 0.2, 1.0]
            )
        )
        self.fixture.complete()
        second = self.fixture.receipt("second")
        self.assertEqual(second["before"], first["after"])
        self.assertEqual(len(self.fixture.mids), 1)
        self.assertIs(self.fixture.components[0].get_material(0), self.fixture.mids[0])
        self.assertEqual(second["after"]["paint_roughness"], 0.75)
        self.assertEqual(second["editor_pid"], first["editor_pid"])
        self.assertEqual(
            second["editor_start_filetime_utc"], first["editor_start_filetime_utc"]
        )
        self.assertEqual(second["camera"], first["camera"])
        result = json.loads(
            self.manager.handle_json(self.fixture.request("restore", action="restore"))
        )
        self.assertEqual(result["sequence"], 3)
        self.assertEqual(result["after"], before)
        self.assertEqual(bridge.dirty_state(self.fixture.api), initial_dirty)
        self.assertTrue(
            all(
                component.material is self.fixture.original
                for component in self.fixture.components
            )
        )
        self.assertEqual(len(self.fixture.captures), 8)
        for record in (first, second):
            self.assertEqual(record["status"], "COMPLETED")
            self.assertEqual(len(record["captures"]), 4)
            self.assertEqual(
                [row["priming"] for row in record["captures"]],
                [True, True, True, False],
            )
            self.assertEqual(record["dirty_after"], initial_dirty)
            self.assertFalse(record["source_world_saved"])

    def test_partial_slot_assignment_rolls_back_only_owned_mid(self):
        self.fixture.components[2].fail_once = True
        with self.assertRaisesRegex(RuntimeError, "slot setter failed"):
            self.manager.handle_json(self.fixture.request("partial"))
        self.assertTrue(
            all(
                component.material is self.fixture.original
                for component in self.fixture.components
            )
        )
        self.assertIsNone(self.manager.mid)
        self.assertEqual(self.fixture.receipt("partial")["status"], "BLOCKED")
        self.assertEqual(self.manager.sequence, 0)

    def test_vector_failure_after_scalar_restores_original_bindings(self):
        self.fixture.api.MaterialLibrary.create_dynamic_material_instance = (
            self.failing_mid
        )
        with self.assertRaisesRegex(RuntimeError, "vector setter failed"):
            self.manager.handle_json(self.fixture.request("partial-parameters"))
        self.assertEqual(self.fixture.mids[0].scalar, 0.35)
        self.assertEqual(self.fixture.original.scalar, 0.90)
        self.assertTrue(
            all(
                component.material is self.fixture.original
                for component in self.fixture.components
            )
        )
        self.assertEqual(self.manager.observe(), self.manager.original_bindings)

    def test_explicit_restore_finishes_cleanup_after_partial_slot_failure(self):
        self.manager.handle_json(self.fixture.request("first"))
        self.fixture.complete()
        self.fixture.components[2].fail_once = True
        with self.assertRaisesRegex(RuntimeError, "slot setter failed"):
            self.manager.handle_json(
                self.fixture.request("restore-failure", action="restore")
            )
        self.assertTrue(
            all(
                component.material is self.fixture.original
                for component in self.fixture.components
            )
        )
        self.assertEqual(self.manager.observe(), self.manager.original_bindings)
        self.assertEqual(self.fixture.receipt("restore-failure")["status"], "BLOCKED")

    def failing_mid(self, *args, **kwargs):
        mid = self.fixture.create_mid(*args, **kwargs)
        mid.fail_vector = True
        return mid

    def test_partial_failure_preserves_foreign_owner_binding(self):
        foreign = Material("/Game/OwnerChangedMaterial")
        self.fixture.components[2].fail_once = True
        self.fixture.components[2].on_failure = lambda: setattr(
            self.fixture.components[3], "material", foreign
        )
        with self.assertRaisesRegex(ValueError, "Concurrent owner binding preserved"):
            self.manager.handle_json(self.fixture.request("foreign"))
        self.assertIs(self.fixture.components[3].material, foreign)
        self.assertTrue(
            all(
                component.material is self.fixture.original
                for component in self.fixture.components[:3]
            )
        )
        self.assertIn("restore_error", self.fixture.receipt("foreign"))

    def test_live_getter_change_is_rejected_without_overwriting_owner(self):
        self.manager.handle_json(self.fixture.request("first"))
        self.fixture.complete()
        self.fixture.mids[0].scalar = 0.12
        with self.assertRaisesRegex(ValueError, "outside the preview"):
            self.manager.handle_json(self.fixture.request("second"))
        self.assertEqual(self.fixture.mids[0].scalar, 0.12)
        self.assertEqual(self.manager.sequence, 1)

    def test_changed_world_is_rejected_before_material_mutation(self):
        self.fixture.current_world = NativeObject(self.fixture.world.name)
        with self.assertRaisesRegex(ValueError, "world changed"):
            self.manager.handle_json(self.fixture.request("wrong-world"))
        self.assertEqual(self.fixture.mids, [])

    def test_invalid_inputs_are_rejected_before_native_writes(self):
        valid = json.loads(self.fixture.request("invalid"))
        invalid = [
            {**valid, "session_id": "another"},
            {**valid, "expected_sequence": 2},
            {**valid, "expected_sequence": False},
            {**valid, "paint_roughness": -0.1},
            {**valid, "paint_roughness": True},
            {**valid, "paint_color": [0, 0, 0, 0]},
            {**valid, "target": "/Game/Other"},
            {**valid, "parameter": "LineWidthCm"},
            {**valid, "request_id": "../escape"},
            {**valid, "action": "save"},
        ]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.manager.handle_json(bridge.canonical(request))
        for raw in (
            '{"schema_version":1,"schema_version":1}',
            self.fixture.request("nan").replace("0.35", "NaN"),
        ):
            with self.assertRaises(ValueError):
                self.manager.handle_json(raw)
        self.assertEqual(self.fixture.mids, [])
        self.assertEqual(self.manager.sequence, 0)

    def test_duplicate_request_is_never_applied_twice(self):
        self.manager.handle_json(self.fixture.request("first"))
        self.fixture.complete()
        with self.assertRaisesRegex(ValueError, "already used"):
            self.manager.handle_json(self.fixture.request("first"))
        self.assertEqual(len(self.fixture.mids), 1)
        self.assertEqual(self.manager.sequence, 1)

    def test_missing_png_blocks_and_restores_owned_preview(self):
        self.manager.handle_json(self.fixture.request("capture-failure"))
        self.manager.pending["path"].unlink()
        self.manager.tick(0.1)
        self.assertIsNone(self.manager.pending)
        self.assertEqual(self.manager.observe(), self.manager.original_bindings)
        self.assertEqual(self.fixture.receipt("capture-failure")["status"], "BLOCKED")

    def test_loading_barrier_cannot_reenter_the_capture_state_machine(self):
        def nested_slate_tick():
            for callback in tuple(self.fixture.callbacks):
                callback(0.1)

        self.fixture.api.AutomationLibrary.finish_loading_before_screenshot = (
            nested_slate_tick
        )
        self.manager.handle_json(self.fixture.request("reentrant-barrier"))
        self.fixture.complete()
        self.assertEqual(len(self.fixture.captures), 4)
        self.assertEqual(
            self.fixture.receipt("reentrant-barrier")["status"], "COMPLETED"
        )


class RegistrationBoundaryTests(unittest.TestCase):
    def native_settings(self):
        # Exact UPROPERTY identifiers from UE 5.8.2 ModelContextProtocolSettings.h
        # (589492fd...) and ToolsetRegistrySubsystem.h (30d55774...).
        return (
            NativeSettings(
                {
                    "bAutoStartServer": False,
                    "bEnableToolSearch": False,
                    "ServerUrlPath": "/mcp",
                }
            ),
            NativeSettings(
                {"AllowedNames": list(bridge.ALLOWED_NAMES), "BlockedNames": []}
            ),
        )

    def test_private_class_wrapper_reads_literal_native_mcp_and_registry_names(self):
        settings, registry = self.native_settings()
        bridge.require_official_settings(settings, registry)
        self.assertEqual(
            settings.reads, ["bAutoStartServer", "bEnableToolSearch", "ServerUrlPath"]
        )
        self.assertEqual(registry.reads, ["AllowedNames", "BlockedNames"])

    def test_every_mcp_setting_is_read_again_and_rejected_if_changed(self):
        for name, changed in (
            ("bAutoStartServer", True),
            ("bAutoStartServer", 0),
            ("bEnableToolSearch", True),
            ("bEnableToolSearch", "False"),
            ("ServerUrlPath", "/other"),
            ("AllowedNames", []),
            ("AllowedNames", ["YacsRoadMaterialPreview"]),
            ("BlockedNames", ["YacsRoadMaterialPreview"]),
        ):
            with self.subTest(name=name, changed=changed):
                settings, registry = self.native_settings()
                bridge.require_official_settings(settings, registry)
                owner = settings if name in settings.properties else registry
                owner.properties[name] = changed
                with self.assertRaises(ValueError):
                    bridge.require_official_settings(settings, registry)
                self.assertEqual(owner.reads.count(name), 2)

    def test_missing_native_setting_is_not_replaced_by_an_alias_or_default(self):
        for name, alias in (
            ("bAutoStartServer", "auto_start_server"),
            ("bEnableToolSearch", "enable_tool_search"),
            ("ServerUrlPath", "server_url_path"),
            ("AllowedNames", "allowed_names"),
            ("BlockedNames", "blocked_names"),
        ):
            with self.subTest(name=name):
                settings, registry = self.native_settings()
                owner = settings if name in settings.properties else registry
                owner.properties[alias] = owner.properties.pop(name)
                with self.assertRaisesRegex(
                    ValueError, "Native settings property is unavailable"
                ):
                    bridge.require_official_settings(settings, registry)
                self.assertNotIn(alias, owner.reads)

    def test_settings_refusal_reports_only_bounded_values_actually_read(self):
        settings, registry = self.native_settings()
        settings.properties.update(
            {"bAutoStartServer": True, "ServerUrlPath": "/unexpected"}
        )
        with self.assertRaises(ValueError) as refused:
            bridge.require_official_settings(settings, registry)
        observed = json.loads(str(refused.exception).split("; observed=", 1)[1])
        self.assertEqual(
            observed,
            {
                "bAutoStartServer": True,
                "bEnableToolSearch": False,
                "ServerUrlPath": "/unexpected",
            },
        )
        settings.properties.update({"bAutoStartServer": False, "ServerUrlPath": "/mcp"})
        registry.properties["AllowedNames"] = ["unexpected" * 100] * 10
        with self.assertRaises(ValueError) as refused:
            bridge.require_official_settings(settings, registry)
        observed = json.loads(str(refused.exception).split("; observed=", 1)[1])
        self.assertEqual(observed["AllowedNames"]["count"], 10)
        self.assertEqual(len(observed["AllowedNames"]["first_names"]), 4)
        self.assertEqual(
            [len(v) for v in observed["AllowedNames"]["first_names"]], [64] * 4
        )
        self.assertEqual(observed["BlockedNames"], {"count": 0, "first_names": []})

    def test_python_remote_execution_requires_live_native_false_without_fallback(self):
        settings = NativeSettings({"bRemoteExecution": False})
        bridge.require_python_remote_disabled(settings)
        for value in (True, None, 0, "False"):
            with self.subTest(value=value):
                settings.properties["bRemoteExecution"] = value
                with self.assertRaisesRegex(ValueError, "must be disabled"):
                    bridge.require_python_remote_disabled(settings)
        self.assertEqual(settings.reads, ["bRemoteExecution"] * 5)
        unreadable = NativeSettings({"remote_execution": False})
        with self.assertRaisesRegex(
            ValueError, "Native settings property is unavailable"
        ):
            bridge.require_python_remote_disabled(unreadable)
        self.assertEqual(unreadable.reads, ["bRemoteExecution"])

    def preview_schema(self):
        return {
            "tools": [
                {
                    "name": "YacsRoadMaterialPreview.Preview",
                    "description": "Bounded preview",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"RequestJson": {"type": "string"}},
                        "required": ["RequestJson"],
                    },
                }
            ],
        }

    def test_live_registry_inventory_is_checked_again_after_registration(self):
        own_schema = self.preview_schema()
        catalog = [copy.deepcopy(own_schema)]
        calls = []

        def live_schemas():
            calls.append(True)
            return bridge.canonical(catalog)

        registry = SimpleNamespace(get_all_toolset_json_schemas=live_schemas)
        result = bridge.require_registry_catalog(registry, own_schema)
        self.assertEqual(
            result,
            {
                "toolset_count": 1,
                "tool_count": 1,
                "schema_sha256": bridge.digest(catalog),
            },
        )
        catalog.append({"tools": [{"name": "Foreign.Tool"}]})
        with self.assertRaisesRegex(ValueError, "Live official registry differs"):
            bridge.require_registry_catalog(registry, own_schema)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(catalog), 2)  # Never remove another owner's tools.

    def test_registry_catalog_rejects_missing_extra_or_changed_native_schema(self):
        own_schema = self.preview_schema()
        changed = copy.deepcopy(own_schema)
        changed["tools"][0]["inputSchema"]["properties"]["Other"] = {"type": "string"}
        for catalog in ([], [own_schema, own_schema], [changed], [None], own_schema):
            with self.subTest(catalog=catalog):
                registry = SimpleNamespace(
                    get_all_toolset_json_schemas=lambda catalog=catalog: (
                        bridge.canonical(catalog)
                    )
                )
                with self.assertRaises(ValueError):
                    bridge.require_registry_catalog(registry, own_schema)

    def test_registry_catalog_parser_is_bounded_and_requests_still_require_objects(
        self,
    ):
        own_schema = self.preview_schema()
        for raw in (
            '[{"tools":[],"tools":[]}]',
            '[{"tools":NaN}]',
            " " * (64 * 1024) + bridge.canonical([own_schema]),
        ):
            with self.subTest(raw=raw[:80]):
                registry = SimpleNamespace(
                    get_all_toolset_json_schemas=lambda raw=raw: raw
                )
                with self.assertRaises(ValueError):
                    bridge.require_registry_catalog(registry, own_schema)
        with self.assertRaisesRegex(ValueError, "JSON must be one object"):
            bridge.validate_request("[]", "synthetic", 0, set())

    def test_catalog_refusal_reports_counts_and_only_short_actual_names(self):
        catalog = [
            {
                "name": "ForeignToolset" * 20,
                "tools": [{"name": "Foreign.Tool" * 20}] * 7,
            }
        ] * 10
        registry = SimpleNamespace(
            get_all_toolset_json_schemas=lambda: bridge.canonical(catalog)
        )
        with self.assertRaisesRegex(
            ValueError, "Live official registry differs"
        ) as refused:
            bridge.require_registry_catalog(registry, self.preview_schema())
        observed = json.loads(str(refused.exception).split("; observed=", 1)[1])
        self.assertEqual(observed["toolset_count"], 10)
        self.assertEqual(len(observed["first_toolsets"]), 4)
        for row in observed["first_toolsets"]:
            self.assertEqual(row["tool_count"], 7)
            self.assertEqual(len(row["name"]), 64)
            self.assertEqual([len(v) for v in row["first_tool_names"]], [64, 64])
        self.assertLess(len(str(refused.exception).encode()), 2048)

    def test_allowlisted_legacy_declaration_must_actually_be_abstract(self):
        source = 'UCLASS(Abstract, MinimalAPI, Meta=(DeprecationMessage="legacy")) class UExample : public UObject {}'
        bridge.require_abstract_base(source, "UExample")
        for changed in (
            source.replace("Abstract, ", ""),
            source.replace("Abstract, ", "/* Abstract */ "),
            source.replace("Abstract, ", "").replace('"legacy"', '"Abstract"'),
        ):
            with self.assertRaisesRegex(ValueError, "not declared Abstract"):
                bridge.require_abstract_base(changed, "UExample")

    def test_concrete_legacy_library_is_refused(self):
        names = list(bridge.ABSTRACT_LEGACY_CLASSES)
        api = SimpleNamespace(
            ClassIterator=lambda _: names,
            ModelContextProtocolToolLibrary=object,
            get_default_object=lambda name: SimpleNamespace(
                get_class=lambda: NativeObject(name)
            ),
        )
        self.assertEqual(bridge.legacy_census(api), sorted(names))
        names.append("/Script/ForeignPlugin.UnboundedTools")
        with self.assertRaisesRegex(ValueError, "concrete legacy"):
            bridge.legacy_census(api)

    def test_only_one_required_string_preview_tool_is_admitted(self):
        tool = {
            "name": "YacsRoadMaterialPreview.Preview",
            "description": "Bounded preview",
            "inputSchema": {
                "type": "object",
                "properties": {"RequestJson": {"type": "string"}},
                "required": ["RequestJson"],
            },
        }
        self.assertEqual(
            bridge.reflected_tool({"tools": [tool]}), (tool, "RequestJson")
        )
        for changed in (
            {"tools": [tool, tool]},
            {"tools": [{**tool, "name": "MaterialInstanceTools.SetParent"}]},
            {"tools": [{**tool, "inputSchema": {"type": "object", "properties": {}}}]},
        ):
            with self.assertRaises(ValueError):
                bridge.reflected_tool(changed)


if __name__ == "__main__":
    unittest.main()
