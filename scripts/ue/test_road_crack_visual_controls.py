"""Synthetic transient-MID/control fixtures; no native images or admission."""

from copy import deepcopy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.ue import road_crack_visual_controls as controls
from scripts.ue import test_road_asphalt_visual_controls as fixture


class MIC(fixture.Object):
    def __init__(self, path):
        super().__init__(path, probe=0.0)


class MID(fixture.Object):
    def __init__(self, path, parent):
        super().__init__(path, parent=parent, probe=parent.properties["probe"])
        self.setters = []
        self.ignore_set = False

    def get_scalar_parameter_value(self, name):
        """Synthetic MID getter fixture."""
        assert name == "NeutralProbe"
        return self.properties["probe"]

    def set_scalar_parameter_value(self, name, value):
        """Synthetic MID setter fixture; no MIC/package modification."""
        assert name == "NeutralProbe"
        self.setters.append((name, value))
        if not self.ignore_set:
            self.properties["probe"] = value


class Component(fixture.Object):
    def __init__(self, path, original):
        super().__init__(path, cast_shadow=False, **controls.consumer.edge.RENDER_PROPERTIES)
        self.original = self.material = original
        self.mesh = fixture.Object(path + ".DynamicMesh")
        self.assignments, self.visibility = [], []
        self.fail_restore = False
        self.ignore_visibility = False

    def get_num_materials(self):
        """Synthetic component slot-count fixture."""
        return 1

    def get_material(self, index):
        """Synthetic component slot getter fixture."""
        assert index == 0
        return self.material

    def set_material(self, index, material):
        """Synthetic component slot setter fixture."""
        assert index == 0
        self.assignments.append(material.get_path_name())
        if self.fail_restore and material == self.original:
            raise RuntimeError("synthetic original MIC restoration failure")
        self.material = material

    def set_visibility(self, visible, propagate_to_children):
        """Synthetic component visibility fixture."""
        assert propagate_to_children is False
        self.visibility.append(visible)
        if not self.ignore_visibility:
            self.properties["visible"] = visible

    def get_dynamic_mesh(self):
        return self.mesh

    def get_collision_enabled(self):
        return "none"

    def get_tangents_type(self):
        return "auto"


class Actor(fixture.Object):
    def __init__(self, path, label, component):
        super().__init__(path, hidden=False, root_component=component)
        self.label, self.component = label, component

    def get_actor_label(self):
        return self.label

    def get_dynamic_mesh_component(self):
        return self.component

    def get_actor_location(self):
        return SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def get_actor_rotation(self):
        return SimpleNamespace(pitch=0.0, yaw=0.0, roll=0.0)

    def get_actor_scale3d(self):
        return SimpleNamespace(x=1.0, y=1.0, z=1.0)


class Allocator:
    def __init__(self):
        self.allocations = []
        self.fail_second = self.ignore_set = False

    def create_dynamic_material_instance(self, world, parent, *, creation_flags):
        """Synthetic create_dynamic_material_instance with explicit flags."""
        assert creation_flags == "TRANSIENT"
        if self.fail_second and self.allocations:
            raise RuntimeError("synthetic second transient MID allocation failure")
        mid = MID(world.get_path_name() + ":TransientMID_" + str(len(self.allocations)), parent)
        mid.ignore_set = self.ignore_set
        self.allocations.append(mid)
        return mid


class CrackControlTests(unittest.TestCase):
    def setUp(self):
        # Reuse the existing bounded viewport/files fixture, not a second
        # capture framework. The tests below exercise only the crack provider.
        fixture.ControlTests.setUp(self)
        patcher = patch.object(controls, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch.dict(os.environ, {controls.OWNED_ENV: fixture.TOKEN})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(controls.viewport.OWNED_ENV, None)
        ini = self.engine / "Config/BaseEngine.ini"
        ini.write_text(ini.read_text().replace("[Unrelated]", 'Roughness=(Material="/Engine/BufferVisualization/Roughness.Roughness")\n[Unrelated]'))
        for name, raw in (
            (controls.KISMET_CPP, """
UMaterialInstanceDynamic* UKismetMaterialLibrary::CreateDynamicMaterialInstance(UObject* WorldContextObject,
    UMaterialInterface* Parent, FName Name, EMIDCreationFlags CreationFlags)
{
    auto* Mid = UMaterialInstanceDynamic::Create(Parent, WorldContextObject, Name);
    if (EnumHasAnyFlags(CreationFlags, EMIDCreationFlags::Transient)) { Mid->SetFlags(RF_Transient); }
    return Mid;
}
"""),
            ("Source/Runtime/Engine/Public/Kismet/KismetMaterialLibrary.h", "EMIDCreationFlags Transient CreateDynamicMaterialInstance"),
            ("Source/Runtime/Engine/Public/Materials/MaterialInstanceDynamic.h", "K2_GetScalarParameterValue SetScalarParameterValue"),
            (controls.MID_CPP, """
float UMaterialInstanceDynamic::K2_GetScalarParameterValue(FName ParameterName)
{ float Value = 0.0f; GetScalarParameterValue(ParameterName, Value); return Value; }
"""),
        ):
            path = self.engine / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(raw)
        self.source = {"pins": deepcopy(controls.sources.VERIFIED_PINS), "pins_sha256": controls.digest(controls.sources.VERIFIED_PINS),
                       "selected_motifs": list(controls.sources.CANARY_MOTIFS), "motifs": {
                           motif: {"extent_cm": extent, "empty_border_cm": 6.0, "resolution": 2048}
                           for motif, extent in zip(controls.sources.CANARY_MOTIFS, (180.0, 140.0), strict=True)}}
        paths = controls.material.asset_paths(self.source)
        contracts = {motif: controls.material.geometry_contract(self.source["motifs"][motif], uv_rotation_degrees=rotation)
                     for motif, rotation in zip(controls.sources.CANARY_MOTIFS, (0.0, 90.0), strict=True)}
        self.actors = self.api.get_editor_subsystem(self.api.EditorActorSubsystem).get_all_level_actors()
        self.cracks, self.mics, rows = {}, {}, []
        for motif, label in zip(controls.sources.CANARY_MOTIFS, ("ordinary_0112", "nudo_0082"), strict=True):
            mic = MIC(paths[motif]["instance"])
            self.mics[motif] = mic
            path = self.world.get_path_name() + ".PersistentLevel." + label
            component = Component(path + ".Mesh", mic)
            actor = Actor(path, controls.consumer.ACTOR_PREFIX + label, component)
            self.actors.append(actor)
            self.cracks[motif] = component
            rows.append({"motif_id": motif, "label": actor.label,
                         "actor": controls.saved.normalized(controls.consumer.edge.existing.actor_snapshot(actor), controls.saved.MAP),
                         "component": controls.saved.normalized(component.path, controls.saved.MAP),
                         "mesh": controls.saved.normalized(component.mesh.path, controls.saved.MAP), "material": mic.path})
        self.context["manifest"].update(crack_canary_enabled=True, crack_canary={
            "status": "LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING", "normal_space_verified": False, "world_normal_canary_required": True,
            "imports": {"sources": self.source}, "geometry_contracts": contracts, "actors": rows,
            "material": {"assets": paths, "neutral_probe": controls.material.PROBE_CONTRACT,
                         "normal_space_verified": False, "geometry_contracts": contracts}})
        self.mid_allocator = Allocator()
        self.dirty = []

        def get_dirty():
            """Synthetic dirty-package query; no flags are cleared."""
            return list(self.dirty)

        def get_scalar(instance, parameter, association):
            """Synthetic saved-MIC readback; setters are intentionally absent."""
            assert parameter == "NeutralProbe" and association == "global"
            return instance.properties["probe"]

        self.api.MaterialLibrary = self.mid_allocator
        self.api.MaterialInstanceDynamic = MID
        self.api.MaterialInstanceConstant = MIC
        self.api.MIDCreationFlags = SimpleNamespace(TRANSIENT="TRANSIENT")
        self.api.DynamicMeshActor = Actor
        self.api.DynamicMeshComponent = Component
        self.api.CollisionEnabled = SimpleNamespace(NO_COLLISION="none")
        self.api.DynamicMeshComponentTangentsMode = SimpleNamespace(AUTO_CALCULATED="auto")
        self.api.MaterialParameterAssociation = SimpleNamespace(GLOBAL_PARAMETER="global")
        self.api.MaterialEditingLibrary.get_material_instance_scalar_parameter_value = get_scalar
        self.api.EditorLoadingAndSavingUtils = SimpleNamespace(get_dirty_content_packages=get_dirty)

    def controller(self):
        return controls.VisualControls(self.api, self.context)

    def assertOriginals(self):
        for motif, component in self.cracks.items():
            self.assertIs(component.material, self.mics[motif])
            self.assertIs(component.properties["visible"], True)
            self.assertEqual(self.mics[motif].properties["probe"], 0.0)
        self.assertEqual(self.road.assignments, [])
        self.assertEqual(self.allocator.allocations, [])

    def test_exact_sixteen_plan_reuses_ordinary_and_nudo_cameras_with_three_primes(self):
        plan = controls.control_plan()
        self.assertEqual(plan["frame_count"], 16)
        self.assertEqual(len({row["job_id"] for row in plan["jobs"]}), 16)
        self.assertEqual(plan["priming_captures_per_condition"], 3)
        for frame in controls.FRAME_IDS:
            jobs = [job for job in plan["jobs"] if job["camera"]["frame_id"] == frame]
            self.assertEqual([job["control"] for job in jobs], list(controls.CONTROLS))
            original = next(row for row in fixture.NETWORK["frames"] if row["frame_id"] == frame)
            self.assertTrue(all(job["camera"] == original for job in jobs))
        self.assertEqual(plan, controls.control_plan())
        self.assertEqual(controls.FAMILY, "road-crack")

    def test_preflight_is_read_only_and_begin_uses_two_transient_mids_without_mic_edits(self):
        before = controls.preflight(self.api, self.context)
        self.assertEqual(self.mid_allocator.allocations, [])
        self.assertEqual(self.auto.calls, [])
        controller = self.controller()
        begin = controller.begin()
        self.assertEqual(begin["status"], "READY")
        self.assertEqual({name: begin[name] for name in ("ownership", "native_api")}, before)
        self.assertEqual(len(self.mid_allocator.allocations), 2)
        self.assertTrue(all(row["creation_flags"] == "TRANSIENT" for row in begin["transient_mids"].values()))
        self.assertFalse(begin["saved_material_parameters_changed"])
        self.assertFalse(begin["native_api"]["native_object_flags_readback_verified"])
        self.assertOriginals()
        controller.restore()

    def test_all_sixteen_observations_match_exact_material_visibility_buffer_and_probe_state(self):
        controller = self.controller()
        controller.begin()
        for job in controller.plan["jobs"]:
            observation = controller.apply(job["job_id"])
            self.assertEqual(observation, controller.observe())
            neutral = job["control"].startswith("neutral-")
            visible = not job["control"].startswith("base-")
            self.assertEqual(len(observation["crack_actors"]), 2)
            self.assertEqual(observation["requested_buffer"], controls.BUFFERS.get(job["control"]))
            self.assertEqual(observation["dirty_content_count"], 0)
            for row in observation["crack_actors"]:
                self.assertEqual(row["visible_readback"], visible)
                self.assertEqual(row["neutral_probe_readback"], 1.0 if neutral else 0.0)
                self.assertEqual(row["original_mic_probe_readback"], 0.0)
                self.assertEqual(row["material_kind"], "transient_mid" if neutral else "original_mic")
            self.assertEqual([row["uv_rotation_degrees"] for row in observation["crack_actors"]], [0.0, 90.0])
        restored = controller.restore()
        self.assertEqual(restored["status"], "RESTORED")
        self.assertEqual(restored["cleanup_errors"], [])
        for key in ("original_material_restored", "original_visibility_restored", "original_mic_probe_values_zero",
                    "transient_mids_detached", "transient_mid_refs_released", "owned_viewports_returned_to_lit",
                    "saved_and_staged_package_bytes_unchanged"):
            self.assertIs(restored[key], True)
        self.assertEqual(controller.transients, {})
        self.assertEqual(self.auto.mode, "lit")
        self.assertEqual(len(restored["applied_jobs"]), 16)
        self.assertFalse(restored["normal_space_verified"])
        self.assertFalse(restored["capture_count_verified"])
        self.assertOriginals()

    def test_missing_or_ambiguous_ownership_foreign_frame_and_canary_off_fail_before_mutation(self):
        for name, value in ((controls.OWNED_ENV, "wrong"), (controls.viewport.OWNED_ENV, fixture.TOKEN),
                            ("YACS_ROAD_MATERIAL_EXPECTED_HEAD", "c" * 40)):
            with self.subTest(name=name), patch.dict(os.environ, {name: value}), self.assertRaises(ValueError):
                self.controller().begin()
        self.context["manifest"]["crack_canary_enabled"] = False
        with self.assertRaises(ValueError):
            self.controller().begin()
        self.context["manifest"]["crack_canary_enabled"] = True
        self.context["view_plan"]["frames"][0]["camera_location_cm"][0] += 1
        with self.assertRaises(ValueError):
            self.controller().begin()
        self.assertEqual(self.mid_allocator.allocations, [])
        self.assertEqual(self.auto.calls, [])

    def test_foreign_actor_material_rotation_or_nonzero_saved_probe_are_not_repaired(self):
        for kind in ("material", "rotation", "probe", "visible"):
            original = deepcopy(self.context["manifest"])
            mic = self.mics["short_oblique"]
            old_path = mic.path
            if kind == "material":
                mic.path = "/Game/Other.Foreign"
            elif kind == "rotation":
                self.context["manifest"]["crack_canary"]["geometry_contracts"]["short_oblique"]["uv_rotation_degrees"] = 0.0
            elif kind == "probe":
                mic.properties["probe"] = 1.0
            else:
                self.cracks["short_oblique"].properties["visible"] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.controller().begin()
            self.context["manifest"] = original
            mic.path, mic.properties["probe"] = old_path, 0.0
            self.cracks["short_oblique"].properties["visible"] = True
        self.assertEqual(self.mid_allocator.allocations, [])

    def test_partial_mid_creation_or_setter_failure_restores_without_dirty_content(self):
        for name in ("fail_second", "ignore_set"):
            self.mid_allocator.allocations.clear()
            setattr(self.mid_allocator, name, True)
            controller = self.controller()
            with self.subTest(name=name), self.assertRaises((ValueError, RuntimeError)):
                controller.begin()
            self.assertEqual(controller.report["status"], "FAILED")
            self.assertEqual(controller.report["cleanup_errors"], [])
            self.assertTrue(controller.report["transient_mids_detached"])
            self.assertOriginals()
            setattr(self.mid_allocator, name, False)

    def test_partial_buffer_change_observed_visibility_or_mid_drift_restores_every_component(self):
        for mode in ("buffer", "visibility", "mid"):
            controller = self.controller()
            controller.begin()
            if mode == "buffer":
                self.auto.fail_buffer_after_change = True
                operation = lambda: controller.apply(controller.plan["jobs"][0]["job_id"])
            else:
                controller.apply(controller.plan["jobs"][0]["job_id"])
                if mode == "visibility":
                    self.cracks["short_oblique"].properties["visible"] = True
                else:
                    controller.transients["short_oblique"].properties["probe"] = 0.0
                operation = controller.observe
            with self.subTest(mode=mode), self.assertRaises((ValueError, RuntimeError)):
                operation()
            self.auto.fail_buffer_after_change = False
            self.assertEqual(controller.report["status"], "FAILED")
            self.assertOriginals()
            self.assertEqual(self.auto.mode, "lit")

    def test_dirty_content_fails_and_is_never_cleared_even_during_cleanup(self):
        self.dirty.append(fixture.Object("/Game/ChangedAsset"))
        with self.assertRaisesRegex(ValueError, "dirty content"):
            self.controller().begin()
        self.assertEqual(self.mid_allocator.allocations, [])
        self.dirty.clear()
        controller = self.controller()
        controller.begin()
        controller.apply(controller.plan["jobs"][0]["job_id"])
        self.dirty.append(fixture.Object("/Game/ChangedAsset"))
        with self.assertRaisesRegex(RuntimeError, "restoration failed"):
            controller.observe()
        self.assertEqual(len(self.dirty), 1)
        self.assertEqual(controller.report["status"], "FAILED")
        self.assertTrue(controller.report["cleanup_errors"])
        self.assertOriginals()

    def test_restoration_attempts_both_components_visibility_and_lit_after_one_slot_failure(self):
        controller = self.controller()
        controller.begin()
        for job in controller.plan["jobs"][:2]:
            controller.apply(job["job_id"])
        self.cracks["drifting_interrupted"].fail_restore = True
        with self.assertRaisesRegex(RuntimeError, "restoration failure"):
            controller.restore()
        self.assertIs(self.cracks["short_oblique"].material, self.mics["short_oblique"])
        self.assertTrue(all(component.properties["visible"] for component in self.cracks.values()))
        self.assertEqual(self.auto.mode, "lit")
        self.assertFalse(controller.report["original_material_restored"])
        self.assertTrue(controller.report["original_visibility_restored"])
        self.assertEqual(controller.report["status"], "FAILED")

    def test_installed_allocator_getter_and_roughness_contracts_cannot_be_satisfied_by_comments(self):
        for relative, old, new in (
            (controls.KISMET_CPP, "Mid->SetFlags(RF_Transient);", "/* Mid->SetFlags(RF_Transient); */"),
            (controls.MID_CPP, "GetScalarParameterValue(ParameterName, Value);", "/* GetScalarParameterValue(ParameterName, Value); */"),
            ("Config/BaseEngine.ini", "/Engine/BufferVisualization/Roughness", "/Game/ForeignRoughness"),
        ):
            path = self.engine / relative
            original = path.read_text()
            path.write_text(original.replace(old, new))
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                self.controller().begin()
            path.write_text(original)
        self.assertEqual(self.mid_allocator.allocations, [])
        self.assertEqual(self.auto.calls, [])

    def test_order_is_enforced_and_changed_saved_file_fails_restoration(self):
        controller = self.controller()
        controller.begin()
        with self.assertRaisesRegex(ValueError, "fixed sixteen"):
            controller.apply(controller.plan["jobs"][1]["job_id"])
        self.assertOriginals()
        controller = self.controller()
        controller.begin()
        controller.apply(controller.plan["jobs"][0]["job_id"])
        row = self.context["manifest"]["assets"][0]
        path = self.root / row["path"]
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaises(RuntimeError):
            controller.restore()
        self.assertEqual(controller.report["status"], "FAILED")
        self.assertOriginals()


if __name__ == "__main__":
    unittest.main()
