"""Synthetic native adapters test control safety; no UE/render proof is claimed."""

from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts.ue import road_asphalt_visual_controls as controls

REAL_ROOT = controls.ROOT
NETWORK = controls.views.current_view_plan(REAL_ROOT)
TOKEN = "12345678-1"
HEAD = "b" * 40
MATERIAL_PATH = controls.saved.PACKAGE + "/Fixture.MI_Fixture"


class Object:
    def __init__(self, path, **properties):
        self.path = path
        self.properties = properties

    def get_path_name(self):
        return self.path

    def get_editor_property(self, name):
        return self.properties[name]

    def set_editor_property(self, name, value):
        self.properties[name] = value


class Material(Object):
    pass


class Road(Object):
    def __init__(self, material):
        super().__init__(controls.saved.MAP + ".PersistentLevel.FixtureRoad.Mesh")
        self.material = material
        self.assignments = []
        self.fail_restore = False

    def get_num_materials(self):
        return 1

    def get_material(self, index):
        assert index == 0
        return self.material

    def set_material(self, index, material):
        assert index == 0
        self.assignments.append(material.get_path_name())
        if self.fail_restore and material.get_path_name() == MATERIAL_PATH:
            raise RuntimeError("synthetic restoration failure")
        self.material = material


class Automation:
    def __init__(self):
        self.mode = "unlit"
        self.calls = []
        self.ignore_buffer = False
        self.fail_buffer_after_change = False
        self.fail_lit = False

    def set_editor_viewport_view_mode(self, mode):
        """Synthetic set_editor_viewport_view_mode(index)."""
        self.calls.append(("viewmode", mode))
        if self.fail_lit:
            raise RuntimeError("synthetic Lit restoration failure")
        self.mode = mode

    def set_editor_viewport_visualize_buffer(self, buffer_name):
        """Synthetic set_editor_viewport_visualize_buffer(buffer_name)."""
        self.calls.append(("buffer", buffer_name))
        if not self.ignore_buffer:
            self.mode = "visualize"
        if self.fail_buffer_after_change:
            raise RuntimeError("synthetic partial buffer setter failure")

    def get_editor_active_viewport_view_mode(self):
        """Synthetic get_editor_active_viewport_view_mode()."""
        return self.mode


class Editing:
    def __init__(self):
        self.nodes = []
        self.outputs = {}
        self.fail_connect = False
        self.compile_errors = []

    def create_material_expression(self, material, kind):
        """Synthetic create_material_expression(material, kind)."""
        node = Object("/Engine/Transient.Expression", kind=kind)
        self.nodes.append(node)
        return node

    def connect_material_property(self, expression, output, prop):
        """Synthetic connect_material_property(expression, output, property)."""
        self.outputs[prop] = expression
        return not self.fail_connect

    def recompile_material(self, material):
        """Synthetic recompile_material(material)."""
        return self.compile_errors


class Allocator:
    def __init__(self):
        self.allocations = []

    def create_component230_detail_material(self):
        """Synthetic create_component230_detail_material()."""
        material = Material("/Engine/Transient.Material_Fixture")
        self.allocations.append(material)
        return material


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "isolated-project"
        self.engine = Path(self.temp.name) / "engine"
        self.retained = Path(self.temp.name) / "retained"
        self.root.mkdir()
        for root, name, raw in (
            (self.root, controls.views.SURVEY, (REAL_ROOT / controls.views.SURVEY).read_bytes()),
            (self.root, controls.ALLOCATOR_CPP, b"""
UMaterial* UYacsLandscapeMeshDiagnosticLibrary::CreateComponent230DetailMaterial()
{ return NewObject<UMaterial>(GetTransientPackage(), NAME_None, RF_Transient); }
"""),
            (self.engine, controls.AUTOMATION_CPP, b"""
void UAutomationBlueprintFunctionLibrary::SetEditorViewportVisualizeBuffer(FName BufferName)
{ for (auto Viewport : LevelEditor->GetViewports()) {
    Viewport.SetViewMode(VMI_VisualizeBuffer);
    Viewport.ChangeBufferVisualizationMode(BufferName);
} }
"""),
            (self.engine, controls.AUTOMATION_HEADER, b"""
void SetEditorViewportVisualizeBuffer(FName BufferName);
void SetEditorViewportViewMode(EViewModeIndex Index);
EViewModeIndex GetEditorActiveViewportViewMode();
"""),
            (self.engine, "Config/BaseEngine.ini", b"""
[Engine.BufferVisualizationMaterials]
BaseColor=(Material="/Engine/BufferVisualization/BaseColor.BaseColor")
WorldNormal=(Material="/Engine/BufferVisualization/WorldNormal.WorldNormal")
[Unrelated]
"""),
        ):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        rows = []
        for index in range(7):
            name = controls.saved.MAP_FILE if index == 0 else controls.saved.PREFIX + str(index) + ".uasset"
            raw = ("synthetic-package-" + str(index)).encode()
            for base, relative in ((self.root, name), (self.retained, "packages/" + name)):
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            rows.append({"path": name, "storage": "packages/" + name,
                         "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)})
        self.context = {"run_token": TOKEN, "exact_sha": HEAD, "view_plan": deepcopy(NETWORK),
                        "retained": self.retained, "rows": [], "source_dependencies": [],
                        "manifest": {"map_package": controls.saved.MAP, "assets": rows,
                                     "material_instance": MATERIAL_PATH}}
        self.original = Material(MATERIAL_PATH)
        self.road = Road(self.original)
        self.auto, self.edit, self.allocator = Automation(), Editing(), Allocator()
        self.world = Object(controls.saved.MAP + ".L_SaCalobraRoadAsphaltReview")
        actors = [SimpleNamespace(get_actor_label=lambda: "YACS_PERSIST_ROAD",
                                  get_dynamic_mesh_component=lambda: self.road)]
        for index in range(186):
            actors.append(SimpleNamespace(get_actor_label=lambda i=index: f"YACS_PERSIST_SUPPORT_{i:03d}"))
        self.api = SimpleNamespace(
            Paths=SimpleNamespace(convert_relative_path_to_full=lambda p: p,
                                  project_dir=lambda: str(self.root), engine_dir=lambda: str(self.engine)),
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: controls.ENGINE_VERSION),
            UnrealEditorSubsystem="editor", EditorActorSubsystem="actors",
            get_editor_subsystem=lambda kind: SimpleNamespace(get_editor_world=lambda: self.world)
                if kind == "editor" else SimpleNamespace(get_all_level_actors=lambda: actors),
            AutomationLibrary=self.auto, MaterialEditingLibrary=self.edit,
            YacsLandscapeMeshDiagnosticLibrary=self.allocator, Material=Material,
            ViewModeIndex=SimpleNamespace(VMI_LIT="lit", VMI_VISUALIZE_BUFFER="visualize"),
            MaterialDomain=SimpleNamespace(MD_SURFACE="surface"),
            MaterialShadingModel=SimpleNamespace(MSM_DEFAULT_LIT="lit"),
            BlendMode=SimpleNamespace(BLEND_OPAQUE="opaque"),
            MaterialExpressionConstant3Vector="vector", MaterialExpressionConstant="scalar",
            LinearColor=lambda r, g, b, a: SimpleNamespace(r=r, g=g, b=b, a=a),
            MaterialProperty=SimpleNamespace(**{name: name for name in (
                "MP_BASE_COLOR", "MP_NORMAL", "MP_ROUGHNESS", "MP_SPECULAR", "MP_METALLIC",
                "MP_EMISSIVE_COLOR", "MP_AMBIENT_OCCLUSION")}),
        )
        for module in (controls, controls.saved, controls.session):
            patcher = patch.object(module, "ROOT", self.root)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(controls.session, "_assert_isolated_root")
        self.isolated = patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.dict(controls.os.environ, {
            controls.OWNED_ENV: TOKEN, "YACS_ROAD_SAVED_RUN_TOKEN": TOKEN,
            "YACS_ROAD_MATERIAL_EXPECTED_HEAD": HEAD})
        patcher.start()
        self.addCleanup(patcher.stop)

    def controller(self):
        return controls.VisualControls(self.api, self.context)

    def apply_through(self, controller, control):
        for job in controller.plan["jobs"]:
            controller.apply(job["job_id"])
            if job["control"] == control:
                return
        self.fail("Requested fixture control is absent")

    def test_exact_plan_preserves_real_cameras_and_has_eight_distinct_jobs(self):
        plan = controls.control_plan()
        self.assertEqual(plan["frame_count"], 8)
        self.assertEqual(len({job["job_id"] for job in plan["jobs"]}), 8)
        by_id = {row["frame_id"]: row for row in NETWORK["frames"]}
        for job in plan["jobs"]:
            self.assertEqual(job["camera"], by_id[job["camera"]["frame_id"]])
        self.assertEqual({job["camera"]["frame_id"] for job in plan["jobs"]}, set(controls.FRAME_IDS))
        self.assertEqual(plan, controls.control_plan())
        self.assertFalse(plan["owner_visual_pass"])

    def test_no_marker_refuses_before_view_or_material_mutations(self):
        controls.os.environ.pop(controls.OWNED_ENV)
        with self.assertRaisesRegex(ValueError, "marked owned"):
            self.controller().begin()
        self.assertEqual(self.auto.calls, [])
        self.assertEqual(self.allocator.allocations, [])
        self.assertEqual(self.road.assignments, [])

    def test_wrong_host_token_or_head_refuses_without_native_mutations(self):
        for key in ("YACS_ROAD_SAVED_RUN_TOKEN", "YACS_ROAD_MATERIAL_EXPECTED_HEAD"):
            with self.subTest(key=key), patch.dict(controls.os.environ, {key: "wrong"}):
                with self.assertRaises(ValueError):
                    self.controller().begin()
        self.assertEqual(self.auto.calls, [])
        self.assertEqual(self.road.assignments, [])

    def test_wrong_engine_project_map_or_plan_refuses_before_mutation(self):
        mutations = (
            lambda: setattr(self.api.SystemLibrary, "get_engine_version", lambda: "5.9"),
            lambda: setattr(self.api.Paths, "project_dir", lambda: str(self.root / "other")),
            lambda: setattr(self.world, "path", "/Game/Other.Other"),
            lambda: self.context["view_plan"]["frames"][0]["camera_location_cm"].__setitem__(0, -1),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                old_engine, old_project = self.api.SystemLibrary.get_engine_version, self.api.Paths.project_dir
                old_world, old_plan = self.world.path, deepcopy(self.context["view_plan"])
                mutate()
                with self.assertRaises(ValueError):
                    self.controller().begin()
                self.api.SystemLibrary.get_engine_version, self.api.Paths.project_dir = old_engine, old_project
                self.world.path, self.context["view_plan"] = old_world, old_plan
        self.assertEqual(self.auto.calls, [])

    def test_live_project_guard_is_called_before_native_mutation(self):
        self.isolated.side_effect = ValueError("refuses the live project")
        with self.assertRaisesRegex(ValueError, "live project"):
            self.controller().begin()
        self.assertEqual(self.auto.calls, [])

    def test_missing_buffer_config_rejects_before_mutation(self):
        path = self.engine / "Config/BaseEngine.ini"
        path.write_text(path.read_text().replace("WorldNormal=", "Missing="))
        with self.assertRaisesRegex(ValueError, "missing or remapped"):
            self.controller().begin()
        self.assertEqual(self.auto.calls, [])
        self.assertEqual(self.allocator.allocations, [])

    def test_comment_does_not_fake_installed_setter_implementation(self):
        path = self.engine / controls.AUTOMATION_CPP
        path.write_text(path.read_text().replace("Viewport.ChangeBufferVisualizationMode(BufferName);",
                                                "// Viewport.ChangeBufferVisualizationMode(BufferName);"))
        with self.assertRaisesRegex(ValueError, "viewport/argument path"):
            self.controller().begin()
        self.assertEqual(self.auto.calls, [])

    def test_transient_uniform_graph_preserves_geometry_normal_and_matte_response(self):
        controller = self.controller()
        controller.begin()
        self.apply_through(controller, "uniform-lit")
        material = self.road.material
        self.assertEqual(material.get_editor_property("shading_model"), "lit")
        self.assertTrue(material.get_editor_property("tangent_space_normal"))
        self.assertEqual(len(self.edit.nodes), 6)
        normal = self.edit.outputs["MP_NORMAL"].get_editor_property("constant")
        self.assertEqual((normal.r, normal.g, normal.b), (0, 0, 1))
        self.assertEqual(self.edit.outputs["MP_ROUGHNESS"].get_editor_property("r"), 0.933)
        self.assertEqual(self.edit.outputs["MP_METALLIC"].get_editor_property("r"), 0)
        self.assertEqual(self.edit.outputs["MP_EMISSIVE_COLOR"].get_editor_property("r"), 0)
        result = controller.restore()
        self.assertIs(self.road.material, self.original)
        self.assertEqual(self.auto.mode, "lit")
        self.assertEqual(result["status"], "RESTORED")
        self.assertTrue(result["saved_and_staged_package_bytes_unchanged"])
        self.assertFalse(result["capture_count_verified"])

    def test_eight_modes_record_exact_requests_without_claiming_buffer_getter(self):
        controller = self.controller()
        controller.begin()
        for job in controller.plan["jobs"]:
            observation = controller.apply(job["job_id"])
            self.assertEqual(controller.observe(), observation)
            self.assertFalse(observation["buffer_name_readback_verified"])
        result = controller.restore()
        self.assertEqual(len(result["applied_jobs"]), 8)
        self.assertEqual([call for call in self.auto.calls if call[0] == "buffer"],
                         [("buffer", "BaseColor"), ("buffer", "WorldNormal")] * 2)
        self.assertFalse(result["owner_visual_pass"])
        self.assertIs(self.road.material, self.original)

    def test_skipped_job_is_failure_and_restores_current_material_and_lit(self):
        controller = self.controller()
        controller.begin()
        with self.assertRaisesRegex(ValueError, "fixed eight-image"):
            controller.apply(controller.plan["jobs"][2]["job_id"])
        self.assertEqual(controller.report["status"], "FAILED")
        self.assertTrue(controller.restored)
        self.assertIs(self.road.material, self.original)

    def test_partial_buffer_setter_failure_restores_even_after_mode_changed(self):
        controller = self.controller()
        controller.begin()
        controller.apply(controller.plan["jobs"][0]["job_id"])
        self.auto.fail_buffer_after_change = True
        with self.assertRaisesRegex(RuntimeError, "partial buffer"):
            controller.apply(controller.plan["jobs"][1]["job_id"])
        self.assertTrue(controller.restored)
        self.assertEqual(self.auto.mode, "lit")
        self.assertIs(self.road.material, self.original)

    def test_silent_viewmode_failure_is_detected_and_rolled_back(self):
        controller = self.controller()
        controller.begin()
        controller.apply(controller.plan["jobs"][0]["job_id"])
        self.auto.ignore_buffer = True
        with self.assertRaisesRegex(ValueError, "viewmode readback"):
            controller.apply(controller.plan["jobs"][1]["job_id"])
        self.assertTrue(controller.restored)

    def test_material_drift_after_apply_is_detected_before_capture(self):
        controller = self.controller()
        controller.begin()
        self.apply_through(controller, "uniform-lit")
        self.road.material = Material("/Engine/Transient.Foreign")
        with self.assertRaisesRegex(ValueError, "material readback"):
            controller.observe()
        self.assertTrue(controller.restored)
        self.assertIs(self.road.material, self.original)

    def test_shader_error_restores_and_never_assigns_failed_control(self):
        self.edit.compile_errors = ["synthetic shader error"]
        controller = self.controller()
        with self.assertRaisesRegex(ValueError, "compilation reported errors"):
            controller.begin()
        self.assertEqual(self.road.assignments, [MATERIAL_PATH])
        self.assertEqual(self.auto.mode, "lit")
        self.assertEqual(controller.report["status"], "FAILED")

    def test_restore_attempts_lit_even_if_original_material_assignment_fails(self):
        controller = self.controller()
        controller.begin()
        self.apply_through(controller, "uniform-lit")
        self.road.fail_restore = True
        self.auto.mode = "visualize"
        with self.assertRaisesRegex(RuntimeError, "road material"):
            controller.restore()
        self.assertEqual(self.auto.mode, "lit")
        self.assertFalse(controller.restored)
        self.road.fail_restore = False
        controller.restore()
        self.assertIs(self.road.material, self.original)
        self.assertEqual(controller.report["status"], "FAILED")

    def test_saved_map_tamper_fails_cleanup_without_rewriting_it(self):
        controller = self.controller()
        controller.begin()
        self.apply_through(controller, "uniform-lit")
        path = self.root / controls.saved.MAP_FILE
        path.write_bytes(b"synthetic external map mutation")
        with self.assertRaisesRegex(RuntimeError, "immutable bytes"):
            controller.restore()
        self.assertEqual(path.read_bytes(), b"synthetic external map mutation")
        self.assertIs(self.road.material, self.original)
        self.assertEqual(self.auto.mode, "lit")
        self.assertEqual(controller.report["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
