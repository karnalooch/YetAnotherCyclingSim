"""Fail-closed tests for source-bound geometry collision diagnosis."""

from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.ue import sa_calobra_geometry_collision_witness as geometry


def vector(*p):
    return SimpleNamespace(x=p[0], y=p[1], z=p[2])


class GeometryCollisionWitnessTests(unittest.TestCase):
    def setUp(self):
        self.landscape = SimpleNamespace(get_path_name=lambda: "/World/Landscape")
        self.rock = SimpleNamespace(get_path_name=lambda: "/World/Cliff")
        self.views = [
            {"frame_id": name, "target": [30000.0, 50000.0, 10000.0]}
            for name in geometry.GEOMETRY_IDS
        ]
        self.captures = [
            {
                "frame_id": row["frame_id"],
                "mode": "prepared",
                "target_cm": row["target"],
            }
            for row in self.views
        ]
        self.rock_height = 0.0
        self.calls = []

        def hit(actor, start, z):
            return SimpleNamespace(
                get_editor_property=lambda field: {
                    "impact_point": vector(start.x, start.y, z),
                    "impact_normal": vector(0.0, 0.0, 1.0),
                    "hit_actor": actor,
                    "hit_component": SimpleNamespace(
                        get_path_name=lambda: "/Component/RockOrLandscape",
                        get_editor_property=lambda key: key == "cast_shadow",
                    ),
                    "face_index": 12,
                }[field]
            )

        def trace(
            world, start, end, channel, complex_trace, ignored, debug, ignore_self
        ):
            self.calls.append(tuple(actor.get_path_name() for actor in ignored))
            if self.rock in ignored:
                return hit(self.landscape, start, 10000.0)
            return hit(self.rock, start, 10000.0 + self.rock_height)

        self.api = SimpleNamespace(
            Vector=vector,
            EditorActorSubsystem=object(),
            get_editor_subsystem=lambda _: SimpleNamespace(
                get_all_level_actors=lambda: [self.landscape, self.rock]
            ),
            TraceTypeQuery=SimpleNamespace(ECC_VISIBILITY=0),
            DrawDebugTrace=SimpleNamespace(NONE=0),
            SystemLibrary=SimpleNamespace(line_trace_single=Mock(side_effect=trace)),
        )

    def observe(self):
        return geometry.capture_geometry_collision(
            self.api, object(), self.landscape, self.views
        )

    def test_exact_36_rays_and_72_nonmutating_traces(self):
        self.rock_height = 120
        report = self.observe()
        self.assertEqual(len(self.calls), 72)
        self.assertEqual(report["sample_count"], 36)
        self.assertTrue(
            all(
                row["category"] == "NON_LANDSCAPE_SURFACE_ABOVE"
                for row in report["samples"]
            )
        )
        self.assertTrue(all(row["height_delta_cm"] == 120 for row in report["samples"]))
        self.assertFalse(report["mutation_performed"])
        self.assertFalse(report["geometry_defect_confirmed"])
        verified = geometry.validate_geometry_collision(report, self.captures)
        self.assertEqual(verified["sample_count"], 36)
        self.assertFalse(verified["shadow_caster_identity_verified"])

    def test_zero_height_hit_is_not_a_proven_defect(self):
        report = self.observe()
        self.assertTrue(
            all(
                row["category"] == "NON_LANDSCAPE_HIT_REVIEW"
                for row in report["samples"]
            )
        )

    def test_missing_or_duplicate_target_fails_closed(self):
        for views in (self.views[:-1], self.views + self.views[-1:]):
            with self.assertRaisesRegex(ValueError, "inventory"):
                geometry.trace_plan(views)

    def test_unreal_58_hit_tuple_fallback_does_not_invent_geometry(self):
        def missing_property(_):
            raise Exception("HitResult: Failed to find property 'impact_point'")

        hit = SimpleNamespace(
            get_editor_property=missing_property,
            to_tuple=lambda: (
                vector(30000, 50000, 150000),
                vector(30000, 50000, -150000),
                vector(0, 0, 1),
                vector(30000, 50000, 10000),
                vector(30000, 50000, 10000),
            ),
        )
        result = geometry._hit_result(
            hit, [30000, 50000, 150000], [30000, 50000, -150000]
        )
        self.assertEqual(result["impact_cm"], [30000.0, 50000.0, 10000.0])
        self.assertIsNone(result["actor_path"])
        self.assertIsNone(result["component_cast_shadow"])

    def test_forged_impact_or_actor_inventory_rejected(self):
        report = self.observe()
        forged = copy.deepcopy(report)
        forged["samples"][0]["world_hit"]["impact_cm"][0] += 300
        with self.assertRaisesRegex(ValueError, "trace bounds"):
            geometry.validate_geometry_collision(forged, self.captures)
        forged = copy.deepcopy(report)
        forged["actor_paths"].remove("/World/Cliff")
        with self.assertRaisesRegex(ValueError, "actor inventory"):
            geometry.validate_geometry_collision(forged, self.captures)

    def test_fabricated_geometry_repair_proof_cannot_pass(self):
        report = self.observe()
        report["geometry_defect_confirmed"] = True
        with self.assertRaisesRegex(ValueError, "cannot assert repairs"):
            geometry.validate_geometry_collision(report, self.captures)

    def test_classification_does_not_infer_shadow_casting(self):
        owner = {"impact_cm": [0.0, 0.0, 100.0], "actor_path": "/World/Landscape"}
        rock = {"impact_cm": [0.0, 0.0, 105.0], "actor_path": "/World/Cliff"}
        self.assertEqual(
            geometry.classify_surface(rock, owner, "/World/Landscape"),
            "NON_LANDSCAPE_SURFACE_ABOVE",
        )
        self.assertEqual(
            geometry.classify_surface(rock, None, "/World/Landscape"),
            "LANDSCAPE_COLLISION_MISSING",
        )


if __name__ == "__main__":
    unittest.main()
