"""Synthetic native-object fault tests; no Unreal, server, build or real image."""

import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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


class NativeClass(NativeObject):
    """Native UClass object, deliberately distinct from a Python type/CDO."""

    def __init__(self, name, parent=None):
        super().__init__(name)
        self.parent = parent
        self.metaclass = None

    def get_class(self):
        return self.metaclass or NativeObject("/Script/CoreUObject.Class")


class NativeClassInventory:
    def __init__(self):
        self.object = NativeClass("/Script/CoreUObject.Object")
        self.meta = NativeClass("/Script/CoreUObject.Class", self.object)
        self.base = NativeClass(bridge.LEGACY_BASE_CLASS, self.object)
        self.editor = NativeClass(
            next(iter(bridge.ABSTRACT_LEGACY_CLASSES - {bridge.LEGACY_BASE_CLASS})),
            self.base,
        )
        self.classes = [self.meta, self.base, self.editor]
        self.lookup = {cls.get_path_name(): cls for cls in self.classes}
        self.lookup[self.object.name] = self.object
        self.loads, self.iterated, self.inheritance = [], [], []
        self.type_yields, self.type_iterated = None, []
        self.cdo = NativeClass("/Script/CoreUObject.Default__Class")
        self.cdo_reads = []
        for cls in [*self.classes, self.object, self.cdo]:
            cls.metaclass = self.meta

        class PythonObject:
            @staticmethod
            def static_class():
                return self.object

        # The unexported native MCP base classes still have no Python aliases.
        self.api = SimpleNamespace(
            Object=PythonObject,
            load_class=self.load_class,
            ObjectIterator=self.objects,
            ClassIterator=self.class_types,
            get_default_object=self.default_object,
            MathLibrary=SimpleNamespace(class_is_child_of=self.is_child),
        )

    def load_class(self, outer, path):
        assert outer is None
        self.loads.append(path)
        return self.lookup.get(path)

    def objects(self, native_class):
        assert native_class is self.meta
        self.iterated.append(native_class)
        return iter(self.classes)

    def is_child(self, candidate, parent):
        assert isinstance(candidate, NativeClass)
        assert isinstance(parent, NativeClass)
        self.inheritance.append((candidate, parent))
        while candidate is not None:
            if candidate is parent:
                return True
            candidate = candidate.parent
        return False

    def class_types(self, root_type):
        assert root_type is self.api.Object
        self.type_iterated.append(root_type)
        return iter(self.classes if self.type_yields is None else self.type_yields)

    def default_object(self, cls):
        self.cdo_reads.append(cls)
        assert cls is self.meta, "Never materialize a represented library CDO"
        return self.cdo


class PreflightFixture(NativeClassInventory):
    """Synthetic disputed candidate; does not establish real UE conversion rules."""

    def __init__(self):
        super().__init__()
        self.settings = NativeSettings({"bRemoteExecution": False})
        self.settings_class = NativeClass(
            "/Script/PythonScriptPlugin.PythonScriptPluginSettings", self.object
        )
        self.lookup.update(
            {
                self.object.name: self.object,
                self.settings_class.name: self.settings_class,
            }
        )
        self.classes.insert(0, self.object)
        self.type_yields = list(self.classes)
        self.native_material = {"observed_material_api": True}

        class PythonObject:
            @staticmethod
            def static_class():
                return self.object

        self.api.Object = PythonObject
        self.api.ClassIterator = self.class_types
        self.api.get_default_object = self.default_object

    def class_types(self, root_type):
        assert root_type is self.api.Object
        return iter(self.type_yields)

    def default_object(self, cls):
        self.cdo_reads.append(cls)
        if cls is self.settings_class:
            return self.settings
        if cls is self.meta:
            return self.cdo
        raise AssertionError("Unexpected CDO materialization")

    def is_child(self, candidate, parent):
        """class_is_child_of(test_class, parent_class) -> bool"""
        candidate = (
            candidate.static_class() if isinstance(candidate, type) else candidate
        )
        parent = parent.static_class() if isinstance(parent, type) else parent
        for value in (candidate, parent):
            current = value
            while current is not None and current is not self.object:
                current = current.parent
            if current is None:
                raise TypeError(
                    "NativizeProperty TestClass ClassProperty: allowed Class type Object"
                )
        self.inheritance.append((candidate, parent))
        while candidate is not None:
            if candidate is parent:
                return True
            candidate = candidate.parent
        return False


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

    def test_legacy_census_uses_native_classes_without_python_alias_or_cdo(self):
        inventory = NativeClassInventory()
        inventory.classes.append(NativeClass("/Script/Unrelated.OtherClass"))
        self.assertEqual(
            bridge.legacy_census(inventory.api), sorted(bridge.ABSTRACT_LEGACY_CLASSES)
        )
        self.assertEqual(
            inventory.loads,
            ["/Script/CoreUObject.Class", *sorted(bridge.ABSTRACT_LEGACY_CLASSES)],
        )
        self.assertEqual(inventory.iterated, [inventory.meta])
        self.assertEqual(inventory.type_iterated, [inventory.api.Object])
        self.assertEqual(inventory.cdo_reads, [])
        self.assertEqual(
            inventory.inheritance, [(cls, inventory.base) for cls in inventory.classes]
        )

    def test_census_refuses_every_missing_or_redirected_native_class_before_iteration(
        self,
    ):
        for path in (
            "/Script/CoreUObject.Class",
            *sorted(bridge.ABSTRACT_LEGACY_CLASSES),
        ):
            for replacement in (None, NativeClass("/Script/Foreign.WrongClass")):
                with self.subTest(path=path, replacement=replacement):
                    inventory = NativeClassInventory()
                    inventory.lookup[path] = replacement
                    with self.assertRaisesRegex(ValueError, "unavailable or differs"):
                        bridge.legacy_census(inventory.api)
                    self.assertEqual(inventory.iterated, [])

    def test_census_refuses_empty_missing_base_or_duplicate_native_inventory(self):
        for selection in ([], [0], [0, 1], [0, 2], [0, 1, 2, 2]):
            with self.subTest(selection=selection):
                inventory = NativeClassInventory()
                inventory.classes = [inventory.classes[index] for index in selection]
                expected = (
                    "Duplicate native"
                    if selection == [0, 1, 2, 2]
                    else "exactly the two pinned"
                )
                with self.assertRaisesRegex(ValueError, expected):
                    bridge.legacy_census(inventory.api)

    def test_concrete_legacy_library_from_either_base_is_refused_on_next_census(self):
        for base in ("base", "editor"):
            with self.subTest(base=base):
                inventory = NativeClassInventory()
                bridge.legacy_census(inventory.api)
                inventory.classes.append(
                    NativeClass(
                        "/Script/ForeignPlugin.UnboundedTools", getattr(inventory, base)
                    )
                )
                with self.assertRaisesRegex(ValueError, "concrete legacy") as refused:
                    bridge.legacy_census(inventory.api)
                self.assertIn(
                    "/Script/ForeignPlugin.UnboundedTools", str(refused.exception)
                )

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


class NativeCoverageTests(unittest.TestCase):
    def test_only_exact_default_instances_of_actual_metaclasses_explain_the_difference(
        self,
    ):
        fixture = NativeClassInventory()
        custom_meta = NativeClass("/Script/Synthetic.CustomMeta", fixture.meta)
        custom_meta.metaclass = fixture.meta
        custom_cdo = NativeClass("/Transient/ArbitraryTemplateName")
        custom_cdo.metaclass = custom_meta
        fixture.classes.append(custom_meta)
        fixture.type_yields = list(fixture.classes)
        fixture.classes.extend([fixture.cdo, custom_cdo])

        def default_object(meta):
            fixture.cdo_reads.append(meta)
            if meta is fixture.meta:
                return fixture.cdo
            self.assertIs(meta, custom_meta)
            return custom_cdo

        fixture.api.get_default_object = default_object
        proof = {}
        self.assertEqual(
            bridge.legacy_census(fixture.api, evidence=proof),
            sorted(bridge.ABSTRACT_LEGACY_CLASSES),
        )
        self.assertEqual(fixture.cdo_reads, [fixture.meta, custom_meta])
        self.assertEqual(
            (proof["class_count"], proof["object_count"], proof["meta_cdo_count"]),
            (4, 6, 2),
        )
        self.assertTrue(proof["class_iteration_complete"])
        self.assertTrue(proof["object_iteration_complete"])
        self.assertTrue(proof["native_coverage_verified"])
        self.assertEqual(
            proof["first_meta_cdos"][1],
            {
                "candidate_path": custom_cdo.name,
                "metaclass_path": custom_meta.name,
                "cdo_path": custom_cdo.name,
            },
        )

    def test_non_cdo_native_class_omitted_by_class_iterator_always_blocks(self):
        for is_legacy in (False, True):
            with self.subTest(is_legacy=is_legacy):
                fixture = NativeClassInventory()
                omitted = NativeClass(
                    "/Script/Synthetic.Omitted",
                    fixture.base if is_legacy else fixture.object,
                )
                omitted.metaclass = fixture.meta
                fixture.type_yields = list(fixture.classes)
                fixture.classes.append(omitted)
                with self.assertRaisesRegex(
                    bridge.NativeCensusError, "non-CDO class omitted"
                ) as caught:
                    bridge.legacy_census(fixture.api)
                self.assertEqual(
                    caught.exception.context["candidate"]["path"], omitted.name
                )
                self.assertEqual(caught.exception.context["stage"], "metaclass_cdo")
                self.assertEqual(fixture.cdo_reads, [fixture.meta])
                self.assertNotIn(omitted, fixture.cdo_reads)

    def test_same_path_in_two_iterators_requires_same_native_object(self):
        fixture = NativeClassInventory()
        fixture.type_yields = list(fixture.classes)
        replacement = NativeClass(fixture.base.name, fixture.object)
        replacement.metaclass = fixture.meta
        fixture.classes[1] = replacement
        with self.assertRaisesRegex(
            bridge.NativeCensusError, "native object identity"
        ) as caught:
            bridge.legacy_census(fixture.api)
        self.assertEqual(
            caught.exception.context["candidate"]["path"], fixture.base.name
        )
        self.assertEqual(caught.exception.context["stage"], "coverage_identity")
        self.assertEqual(fixture.cdo_reads, [])

    def test_every_class_iterator_object_must_also_exist_in_object_iterator(self):
        fixture = NativeClassInventory()
        fixture.type_yields = list(fixture.classes)
        fixture.classes.remove(fixture.base)
        with self.assertRaisesRegex(
            bridge.NativeCensusError, "absent from ObjectIterator"
        ) as caught:
            bridge.legacy_census(fixture.api)
        self.assertEqual(
            caught.exception.context["candidate"]["path"], fixture.base.name
        )
        self.assertEqual(caught.exception.context["stage"], "coverage")

    def test_incomplete_or_duplicate_inventory_is_never_admitted(self):
        for failure in (
            "class_exception",
            "object_exception",
            "object_duplicate",
            "class_cap",
            "object_cap",
        ):
            with self.subTest(failure=failure):
                fixture = NativeClassInventory()
                fixture.type_yields = list(fixture.classes)
                bound = 32768
                if failure.endswith("exception"):

                    def failed_iterator(_root, fixture=fixture):
                        yield fixture.meta
                        raise RuntimeError("native iterator failed before completion")

                    setattr(
                        fixture.api,
                        "ClassIterator"
                        if failure == "class_exception"
                        else "ObjectIterator",
                        failed_iterator,
                    )
                elif failure == "object_duplicate":
                    fixture.classes.append(fixture.base)
                elif failure == "class_cap":
                    bound = 3
                else:
                    bound = 4
                    fixture.classes.append(fixture.cdo)
                proof = {}
                with (
                    patch.object(bridge, "NATIVE_CENSUS_LIMIT", bound),
                    self.assertRaises(bridge.NativeCensusError) as caught,
                ):
                    bridge.legacy_census(fixture.api, evidence=proof)
                self.assertEqual(proof, {})
                if failure.endswith("cap"):
                    self.assertEqual(caught.exception.context["stage"], "completion")
                if failure.endswith("exception"):
                    self.assertEqual(caught.exception.context["index"], 1)
                    self.assertIsInstance(caught.exception.native_error, RuntimeError)

    def test_neither_iterator_can_substitute_a_python_type_for_a_native_class(self):
        for iterator in ("ClassIterator", "ObjectIterator"):
            with self.subTest(iterator=iterator):
                fixture = NativeClassInventory()
                fixture.type_yields = list(fixture.classes)

                class UnexportedWrapper:
                    static_class = Mock(
                        side_effect=AssertionError("must not substitute wrapper")
                    )

                if iterator == "ClassIterator":
                    fixture.type_yields.append(UnexportedWrapper)
                else:
                    fixture.classes.append(UnexportedWrapper)
                with self.assertRaisesRegex(bridge.NativeCensusError, "Python type"):
                    bridge.legacy_census(fixture.api)
                UnexportedWrapper.static_class.assert_not_called()
                self.assertEqual(fixture.cdo_reads, [])

    def test_difference_requires_uclass_metaclass_and_exact_cdo_owner_and_identity(
        self,
    ):
        for failure in (
            "non_class_meta",
            "missing_cdo",
            "wrong_cdo_owner",
            "wrong_cdo_identity",
            "python_cdo",
        ):
            with self.subTest(failure=failure):
                fixture = NativeClassInventory()
                candidate = NativeClass(fixture.cdo.name)
                candidate.metaclass = fixture.meta
                fixture.type_yields = list(fixture.classes)
                fixture.classes.append(candidate)
                returned = fixture.cdo
                if failure == "non_class_meta":
                    candidate.metaclass = NativeClass(
                        "/Script/Synthetic.NotAClassMeta", fixture.object
                    )
                    candidate.metaclass.metaclass = fixture.meta
                elif failure == "missing_cdo":
                    returned = None
                elif failure == "wrong_cdo_owner":
                    returned.metaclass = fixture.base
                elif failure == "python_cdo":
                    returned = type("PythonCDO", (), {})
                cdo_read = Mock(return_value=returned)
                fixture.api.get_default_object = cdo_read
                with self.assertRaises(bridge.NativeCensusError) as caught:
                    bridge.legacy_census(fixture.api)
                if failure == "non_class_meta":
                    cdo_read.assert_not_called()
                    self.assertEqual(
                        caught.exception.context["candidate"]["path"],
                        candidate.metaclass.name,
                    )
                    self.assertEqual(
                        caught.exception.context["coverage_candidate"]["path"],
                        candidate.name,
                    )
                else:
                    cdo_read.assert_called_once_with(fixture.meta)
                    self.assertEqual(
                        caught.exception.context["candidate"]["path"], candidate.name
                    )

    def test_repeated_guard_allows_new_nonlegacy_class_but_rejects_a_legacy_descendant(
        self,
    ):
        fixture = NativeClassInventory()
        original_proof, current_proof = {}, {}
        original = bridge.legacy_census(fixture.api, evidence=original_proof)
        own_toolset = NativeClass(
            "/Script/Python.YacsRoadMaterialPreview", fixture.object
        )
        own_toolset.metaclass = fixture.meta
        fixture.classes.append(own_toolset)
        self.assertEqual(
            bridge.legacy_census(fixture.api, evidence=current_proof), original
        )
        self.assertEqual(original_proof["class_count"], 3)
        self.assertEqual(current_proof["class_count"], 4)
        foreign = NativeClass("/Script/Foreign.UnboundedTools", fixture.base)
        foreign.metaclass = fixture.meta
        fixture.classes.append(foreign)
        with self.assertRaisesRegex(
            bridge.NativeCensusError, "concrete legacy library"
        ) as caught:
            bridge.legacy_census(fixture.api)
        self.assertEqual(caught.exception.context["candidate"]["path"], foreign.name)


class RegistrationPreflightTests(unittest.TestCase):
    def refused(self, fixture):
        with self.assertRaisesRegex(
            ValueError, "registration preflight BLOCKED"
        ) as caught:
            bridge.registration_preflight(fixture.api, Path("synthetic-engine"))
        raw = str(caught.exception).split("; observed=", 1)[1]
        self.assertLessEqual(len(raw.encode("utf-8")), bridge.PREFLIGHT_LIMIT)
        result = json.loads(raw)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(result["diagnostic_only"])
        self.assertFalse(result["qualified"])
        return result

    def test_all_three_gates_return_actual_values_without_diagnostics(self):
        fixture = PreflightFixture()
        with (
            patch.object(
                bridge, "material_api_evidence", return_value=fixture.native_material
            ) as material,
            patch.object(bridge, "legacy_census_diagnostics") as diagnostics,
        ):
            libraries, settings, native_material = bridge.registration_preflight(
                fixture.api, Path("synthetic-engine")
            )
        self.assertEqual(libraries, sorted(bridge.ABSTRACT_LEGACY_CLASSES))
        self.assertIs(settings, fixture.settings)
        self.assertIs(native_material, fixture.native_material)
        self.assertEqual(fixture.settings.reads, ["bRemoteExecution"])
        self.assertEqual(fixture.cdo_reads, [fixture.settings_class])
        material.assert_called_once_with(fixture.api, Path("synthetic-engine"))
        diagnostics.assert_not_called()

    def test_census_failure_keeps_candidate_and_both_independent_readbacks(self):
        fixture = PreflightFixture()
        fixture.classes.insert(0, fixture.cdo)
        fixture.type_yields.insert(0, fixture.cdo)
        with patch.object(
            bridge, "material_api_evidence", return_value=fixture.native_material
        ) as material:
            result = self.refused(fixture)
        self.assertEqual(result["checks"]["legacy_census"]["status"], "BLOCKED")
        self.assertEqual(
            result["checks"]["legacy_census"]["error"]["type"], "TypeError"
        )
        self.assertEqual(
            result["checks"]["python_remote_execution"],
            {"status": "PASSED", "bRemoteExecution": False},
        )
        self.assertEqual(result["checks"]["material_api_evidence"]["status"], "PASSED")
        self.assertEqual(fixture.settings.reads, ["bRemoteExecution"])
        material.assert_called_once()
        details = result["legacy_class_diagnostics"]
        self.assertEqual(
            details["class_is_child_of_signature"],
            "class_is_child_of(test_class, parent_class) -> bool",
        )
        self.assertEqual(len(details["control_pairs"]), 4)
        self.assertTrue(
            all(
                row["status"] == "READ" and row["value"]
                for row in details["control_pairs"]
            )
        )
        first = details["candidate_scan"]["first_failures"][0]
        self.assertEqual(first["index"], 0)
        self.assertEqual(first["stage"], "call")
        self.assertEqual(first["identity"]["path"], fixture.cdo.name)
        self.assertEqual(first["identity"]["python_type"], "NativeClass")
        self.assertTrue(first["is_metaclass_cdo"])
        self.assertEqual(details["metaclass_cdo"]["path"], fixture.cdo.name)
        comparison = details["class_iterator_comparison"]
        self.assertTrue(comparison["iteration_complete"])
        self.assertTrue(all(comparison["base_memberships"].values()))
        self.assertFalse(comparison["native_coverage_verified"])
        self.assertEqual(comparison["error_count"], 1)
        production = result["checks"]["legacy_census"]["error"]["census_context"]
        self.assertEqual(production["candidate"]["path"], fixture.cdo.name)
        self.assertEqual(production["iterator"], "ClassIterator(Object)")
        self.assertEqual(production["stage"], "inheritance")

    def test_actual_production_failure_beyond_diagnostic_cap_keeps_its_own_identity(
        self,
    ):
        for failure in ("inheritance", "coverage"):
            with self.subTest(failure=failure):
                fixture = PreflightFixture()
                ordinary = [
                    NativeClass(f"/Script/Synthetic.Ordinary{index}", fixture.object)
                    for index in range(300)
                ]
                for cls in ordinary:
                    cls.metaclass = fixture.meta
                fixture.classes = [*ordinary, *fixture.classes]
                fixture.type_yields = list(fixture.classes)
                actual_bad = NativeClass("/Script/Synthetic.ActualLateFailure")
                actual_bad.metaclass = fixture.meta
                fixture.classes.append(actual_bad)
                if failure == "inheritance":
                    fixture.type_yields.append(actual_bad)
                with patch.object(
                    bridge,
                    "material_api_evidence",
                    return_value=fixture.native_material,
                ):
                    result = self.refused(fixture)
                primary = result["checks"]["legacy_census"]["error"]
                context = primary["census_context"]
                self.assertEqual(context["candidate"]["path"], actual_bad.name)
                self.assertEqual(
                    context["candidate"]["object_class"], fixture.meta.name
                )
                self.assertEqual(context["index"], 304)
                self.assertEqual(
                    context["stage"],
                    "inheritance" if failure == "inheritance" else "metaclass_cdo",
                )
                self.assertEqual(
                    primary["type"],
                    "TypeError" if failure == "inheritance" else "ValueError",
                )
                capped = result["legacy_class_diagnostics"]["candidate_scan"]
                self.assertEqual(capped["checked_count"], 256)
                self.assertEqual(capped["first_failures"], [])
                self.assertTrue(capped["truncated"])
                self.assertEqual(
                    result["checks"]["python_remote_execution"]["status"], "PASSED"
                )
                self.assertEqual(
                    result["checks"]["material_api_evidence"]["status"], "PASSED"
                )

    def test_remote_or_material_failure_alone_still_refuses_without_census_diagnostics(
        self,
    ):
        for failure in ("remote_true", "remote_unreadable", "material"):
            with self.subTest(failure=failure):
                fixture = PreflightFixture()
                if failure == "remote_true":
                    fixture.settings.properties["bRemoteExecution"] = True
                if failure == "remote_unreadable":
                    fixture.settings.properties = {"remote_execution": False}
                material_error = (
                    RuntimeError("MaterialLibrary.create_dynamic_material_instance")
                    if failure == "material"
                    else None
                )
                with (
                    patch.object(
                        bridge,
                        "material_api_evidence",
                        return_value=fixture.native_material,
                        side_effect=material_error,
                    ) as material,
                    patch.object(bridge, "legacy_census_diagnostics") as diagnostics,
                ):
                    result = self.refused(fixture)
                self.assertEqual(result["checks"]["legacy_census"]["status"], "PASSED")
                self.assertEqual(fixture.settings.reads, ["bRemoteExecution"])
                failed = (
                    "material_api_evidence"
                    if failure == "material"
                    else "python_remote_execution"
                )
                other = (
                    "python_remote_execution"
                    if failure == "material"
                    else "material_api_evidence"
                )
                self.assertEqual(result["checks"][failed]["status"], "BLOCKED")
                self.assertEqual(result["checks"][other]["status"], "PASSED")
                self.assertNotIn("legacy_class_diagnostics", result)
                diagnostics.assert_not_called()
                material.assert_called_once()

    def test_failed_diagnostic_cannot_hide_three_independent_gate_failures(self):
        fixture = PreflightFixture()
        fixture.classes = []
        fixture.type_yields = []
        fixture.settings.properties = {"remote_execution": False}
        with (
            patch.object(
                bridge,
                "material_api_evidence",
                side_effect=RuntimeError("allocator-source-unreadable"),
            ) as material,
            patch.object(
                bridge,
                "legacy_census_diagnostics",
                side_effect=RuntimeError("diagnostic-readback-failed"),
            ) as diagnostics,
        ):
            result = self.refused(fixture)
        self.assertEqual(
            [row["status"] for row in result["checks"].values()], ["BLOCKED"] * 3
        )
        self.assertIn(
            "exactly the two pinned",
            result["checks"]["legacy_census"]["error"]["message"],
        )
        self.assertIn(
            "bRemoteExecution",
            result["checks"]["python_remote_execution"]["error"]["message"],
        )
        self.assertEqual(
            result["checks"]["material_api_evidence"]["error"]["message"],
            "allocator-source-unreadable",
        )
        self.assertEqual(
            result["legacy_class_diagnostics"]["error"]["message"],
            "diagnostic-readback-failed",
        )
        self.assertEqual(fixture.settings.reads, ["bRemoteExecution"])
        material.assert_called_once()
        diagnostics.assert_called_once()

    def test_object_iterator_limit_counts_failures_and_preserves_first_identities(self):
        fixture = PreflightFixture()
        consumed = []

        def candidates(_metaclass):
            for index in range(300):
                consumed.append(index)
                yield fixture.cdo

        fixture.api.ObjectIterator = candidates
        scan = bridge.legacy_census_diagnostics(fixture.api)["candidate_scan"]
        self.assertEqual(len(consumed), 256)
        self.assertEqual(scan["checked_count"], 256)
        self.assertEqual(scan["error_count"], 256)
        self.assertEqual(len(scan["first_failures"]), 4)
        self.assertTrue(scan["truncated"])
        self.assertFalse(scan["iteration_complete"])
        self.assertTrue(
            all(
                row["identity"]["path"] == fixture.cdo.name
                for row in scan["first_failures"]
            )
        )

    def test_type_iterator_records_native_types_duplicates_and_unexpected_yields(self):
        fixture = PreflightFixture()

        class PythonLegacy:
            @staticmethod
            def static_class():
                return fixture.base

        fixture.type_yields = [
            fixture.base,
            PythonLegacy,
            fixture.editor,
            "not-a-class",
        ]
        scan = bridge.class_iterator_diagnostics(fixture.api)
        self.assertEqual(scan["checked_count"], 4)
        self.assertEqual(scan["duplicate_path_count"], 1)
        self.assertEqual(scan["true_count"], 3)
        self.assertEqual(scan["error_count"], 1)
        self.assertEqual(
            scan["first_yields"][0]["identity"]["representation"], "native_class_object"
        )
        self.assertEqual(
            scan["first_yields"][1]["identity"]["representation"], "python_type"
        )
        self.assertEqual(scan["first_yields"][3]["python_type"], "str")
        self.assertIsNone(scan["first_yields"][3]["identity"])
        self.assertEqual(scan["first_failures"][0]["index"], 3)
        self.assertEqual(scan["first_failures"][0]["stage"], "identity")
        self.assertTrue(all(scan["base_memberships"].values()))
        self.assertTrue(scan["iteration_complete"])
        self.assertFalse(scan["truncated"])
        self.assertFalse(scan["native_coverage_verified"])
        self.assertEqual(scan["status"], "ERROR")

    def test_type_iterator_cap_counts_each_duplicate_without_claiming_completeness(
        self,
    ):
        fixture = PreflightFixture()
        consumed = []

        def candidates(_root_type):
            for index in range(32770):
                consumed.append(index)
                yield fixture.base

        fixture.api.ClassIterator = candidates
        scan = bridge.class_iterator_diagnostics(fixture.api)
        self.assertEqual(len(consumed), 32768)
        self.assertEqual(scan["checked_count"], 32768)
        self.assertEqual(scan["duplicate_path_count"], 32767)
        self.assertEqual(scan["true_count"], 32768)
        self.assertTrue(scan["truncated"])
        self.assertFalse(scan["iteration_complete"])
        self.assertFalse(scan["native_coverage_verified"])

    def test_iteration_exception_is_explicitly_incomplete_for_both_iterators(self):
        for iterator, key in (
            ("ObjectIterator", "candidate_scan"),
            ("ClassIterator", "class_iterator_comparison"),
        ):
            with self.subTest(iterator=iterator):
                fixture = PreflightFixture()

                def candidates(_root, fixture=fixture):
                    yield fixture.base
                    raise RuntimeError("iterator-stopped-with-error")

                setattr(fixture.api, iterator, candidates)
                scan = bridge.legacy_census_diagnostics(fixture.api)[key]
                self.assertEqual(scan["checked_count"], 1)
                self.assertFalse(scan["iteration_complete"])
                self.assertTrue(scan["truncated"])
                self.assertEqual(scan["status"], "ERROR")
                self.assertEqual(
                    scan["iteration_error"]["message"], "iterator-stopped-with-error"
                )

    def test_non_bmp_compaction_keeps_control_outcomes_and_disputed_identities(self):
        fixture = PreflightFixture()
        fixture.classes.insert(0, fixture.cdo)
        fixture.type_yields.insert(0, fixture.cdo)
        details = bridge.legacy_census_diagnostics(fixture.api)
        huge = "\U0001f642" * 4096
        long_error = {"type": "TypeError", "message": huge, "message_truncated": False}
        details["class_is_child_of_signature"] = huge
        for row in details["control_pairs"]:
            row.update({"status": "ERROR", "error": long_error})
            row.pop("value", None)
            for side in ("test", "parent"):
                row[side]["path"] = huge
        for name in ("candidate_scan", "class_iterator_comparison"):
            scan = details[name]
            first = scan["first_failures"][0]
            first["error"] = long_error
            first["identity"]["path"] = "disputed-candidate:" + huge
            first["identity"]["python_type"] = huge
            scan["first_failures"] = [copy.deepcopy(first) for _ in range(4)]
            scan["iteration_error"] = long_error
            scan["error_count"] = 300
        details["metaclass_cdo"]["path"] = "metaclass-cdo:" + huge
        fixture.settings.get_editor_property = Mock(side_effect=ValueError(huge))
        actual_failure = bridge.NativeCensusError(
            {
                "iterator": "ObjectIterator(Class)",
                "stage": "metaclass_inheritance",
                "index": 301,
                "candidate": {
                    "path": "actual-production-class:" + huge,
                    "object_class": huge,
                    "python_type": huge,
                },
                "coverage_candidate": {
                    "path": "actual-coverage-object:" + huge,
                    "object_class": huge,
                    "python_type": huge,
                },
                "parent_class": huge,
                "cdo_path": huge,
            },
            TypeError(huge),
        )
        with (
            patch.object(bridge, "legacy_census", side_effect=actual_failure),
            patch.object(
                bridge, "material_api_evidence", side_effect=RuntimeError(huge)
            ),
            patch.object(bridge, "legacy_census_diagnostics", return_value=details),
        ):
            result = self.refused(fixture)
        self.assertTrue(
            all(row["status"] == "BLOCKED" for row in result["checks"].values())
        )
        self.assertTrue(
            all(row["error"]["message_truncated"] for row in result["checks"].values())
        )
        primary = result["checks"]["legacy_census"]["error"]
        self.assertEqual(primary["type"], "TypeError")
        self.assertEqual(primary["census_context"], actual_failure.context)
        self.assertEqual(primary["census_context"]["index"], 301)
        self.assertTrue(
            primary["census_context"]["candidate"]["path"].startswith(
                "actual-production-class:"
            )
        )
        self.assertTrue(
            primary["census_context"]["coverage_candidate"]["path"].startswith(
                "actual-coverage-object:"
            )
        )
        compact = result["legacy_class_diagnostics"]
        self.assertTrue(compact["details_truncated"])
        self.assertEqual(len(compact["control_pairs"]), 4)
        self.assertTrue(
            all(
                row["status"] == "ERROR" and row["error"]["message"]
                for row in compact["control_pairs"]
            )
        )
        self.assertTrue(compact["metaclass_cdo"]["path"].startswith("metaclass-cdo:"))
        for name in ("candidate_scan", "class_iterator_comparison"):
            scan = compact[name]
            self.assertEqual(scan["error_count"], 300)
            self.assertEqual(
                scan["iteration_complete"], details[name]["iteration_complete"]
            )
            self.assertEqual(scan["truncated"], details[name]["truncated"])
            self.assertEqual(len(scan["first_failures"]), 1)
            first = scan["first_failures"][0]
            self.assertTrue(first["identity"]["path"].startswith("disputed-candidate:"))
            self.assertTrue(first["error"]["message"])
            self.assertTrue(first["error"]["message_truncated"])
        self.assertEqual(
            compact["class_iterator_comparison"]["base_memberships"],
            details["class_iterator_comparison"]["base_memberships"],
        )

    def test_real_installer_refusal_precedes_tool_registration_and_own_start_commands(
        self,
    ):
        fixture = PreflightFixture()
        fixture.classes.insert(0, fixture.cdo)
        fixture.type_yields.insert(0, fixture.cdo)
        official = NativeSettings(
            {
                "bAutoStartServer": False,
                "bEnableToolSearch": False,
                "ServerUrlPath": "/mcp",
            }
        )
        registry = NativeSettings(
            {"AllowedNames": list(bridge.ALLOWED_NAMES), "BlockedNames": []}
        )
        fixed_cdos = {}
        for path, settings in (
            (
                "/Script/ModelContextProtocolEngine.ModelContextProtocolSettings",
                official,
            ),
            ("/Script/ToolsetRegistry.ToolsetRegistrySettings", registry),
        ):
            native = NativeClass(path, fixture.object)
            fixture.lookup[path] = native
            fixed_cdos[native] = settings

        def default_object(native):
            if native in fixed_cdos:
                return fixed_cdos[native]
            return fixture.default_object(native)

        fixture.api.get_default_object = default_object
        console, register, define_class = Mock(), Mock(), Mock()
        fixture.api.SystemLibrary = SimpleNamespace(
            get_engine_version=lambda: bridge.ENGINE_VERSION,
            execute_console_command=console,
        )
        fixture.api.ToolsetRegistry = SimpleNamespace(register_toolset_class=register)
        fixture.api.uclass = define_class
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pins = {}
            for module, name in (
                ("ModelContextProtocolEngine", "ModelContextProtocolToolLibrary"),
                ("ModelContextProtocolEditor", "ModelContextProtocolEditorToolLibrary"),
            ):
                relative = f"Plugins/Experimental/ModelContextProtocol/Source/{module}/Public/{name}.h"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    f"UCLASS(Abstract) class U{name} : public UObject {{}}",
                    encoding="utf-8",
                )
                pins[relative] = bridge.file_identity(path)["sha256"]
            fixture.api.Paths = SimpleNamespace(
                engine_dir=lambda: str(root), convert_relative_path_to_full=str
            )
            with (
                patch.object(bridge, "BRIDGE", None),
                patch.object(bridge, "ENGINE_PINS", pins),
                patch.object(
                    bridge,
                    "material_api_evidence",
                    return_value=fixture.native_material,
                ) as material,
                patch.object(bridge, "MaterialPreview") as preview,
                self.assertRaisesRegex(ValueError, "registration preflight BLOCKED"),
            ):
                bridge.install(fixture.api, root, {}, "synthetic-session", "a" * 40)
        self.assertEqual(fixture.settings.reads, ["bRemoteExecution"])
        material.assert_called_once()
        preview.assert_not_called()
        define_class.assert_not_called()
        register.assert_not_called()
        console.assert_not_called()


if __name__ == "__main__":
    unittest.main()
