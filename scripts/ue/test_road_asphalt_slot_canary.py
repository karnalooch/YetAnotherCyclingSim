"""Synthetic contracts only; native UE 5.8 and saved-consumer evidence remain pending."""

from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import Mock

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
                            + "/aged_mountain_asphalt/base/abcdef/M_F.MI_MaterialForge")
        self.comp = Component(self.old)
        self.actor = Actor(self.comp)
        self.receipt = {
            "status": "IMPORTED_UE_REVIEW_PENDING",
            "family": "aged_mountain_asphalt",
            "variant": "base",
            "graph_sha256": "a" * 64,
            "tile_metres": 4,
            "normal_convention": "DirectX",
            "saved": False,
            "geometry_changed": False,
            "landscape_mutated": False,
            "world_semantics_generated": False,
            "assets": {"instance": self.new.get_path_name()},
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
                for i in range(1, 187)
            ],
            "mesh_material_collision_snapshot": [{
                "component": self.comp.get_path_name(),
                "materials": [self.old.get_path_name()], "collision": "NO_COLLISION",
            }] + [
                {"component": f"support-{i}", "materials": [f"support-mat-{i}"],
                 "collision": "NO_COLLISION"}
                for i in range(1, 187)
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

    def test_shared_support_slot_cannot_be_used_as_road_owner(self):
        broken = deepcopy(self.base)
        broken["road_supports"][0]["component"] = "support-1"
        with self.assertRaisesRegex(ValueError, "binding"):
            canary.verify_accepted_surface(broken)

    def test_wrong_source_or_saved_assets_are_rejected_before_material_swap(self):
        for key, value in (
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
            if reads[0] == 2:
                return wrong_on_second_read()
            return actual(index)

        self.comp.get_material = read
        with self.assertRaisesRegex(ValueError, "readback"):
            canary.try_road_only_material(
                self.snapshot, [self.actor], self.new, self.receipt
            )
        self.assertEqual(self.comp.calls[-1], self.old.get_path_name())

    def test_pure_library_has_no_run_on_import_or_unreal_import(self):
        import sys
        self.assertFalse(hasattr(canary, "main"))
        self.assertNotIn("unreal", canary.__dict__)
        self.assertNotIn("unreal", sys.modules)


if __name__ == "__main__":
    unittest.main()
