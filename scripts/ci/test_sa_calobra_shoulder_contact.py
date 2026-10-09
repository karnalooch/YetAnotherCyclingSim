"""Failure and conservation tests for the bounded Issue459 diagnostic."""

import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from scripts.ci.test_sa_calobra_tpp_survey_capture import write_png
from scripts.proof import sa_calobra_shoulder_contact as contract
from scripts.ue.capture_sa_calobra_shoulder_contact import ContactCapture, Owner


class Component:
    def __init__(self, path):
        self.path = path
        self.state = {"visible": True, "cast_hidden_shadow": True}
        self.fail = False

    def get_editor_property(self, key):
        return self.state[key]

    def set_editor_property(self, key, value):
        self.state[key] = value

    def set_visibility(self, value, _propagate):
        if self.fail:
            raise RuntimeError("deliberate visibility failure")
        self.state["visible"] = value

    def get_path_name(self):
        return self.path


class ShoulderContactTests(unittest.TestCase):
    def test_native_shutdown_is_guaranteed_when_final_readback_raises(self):
        owner = Owner.__new__(Owner)
        quit_editor = Mock()
        owner.api = SimpleNamespace(
            SystemLibrary=SimpleNamespace(quit_editor=quit_editor)
        )
        with patch.object(
            owner, "_finish", side_effect=RuntimeError("final native mesh lost")
        ):
            with self.assertRaisesRegex(RuntimeError, "native mesh lost"):
                owner.finish()
        quit_editor.assert_called_once()

    def test_support_identity_uses_source_interior_coordinates_and_native_face_order(
        self,
    ):
        sections = [
            [[float(i), float(j), 10.0 + j / 100] for j in range(25)]
            for i in range(110)
        ]
        triangles = list(contract.interior_top_triangles(sections))
        self.assertEqual(len(triangles), 5232)
        tid, points = triangles[0]
        self.assertEqual(tid, 2)
        self.assertEqual(points[0], (0.0, 0.0, 992.0))
        self.assertEqual(points[2], (100.0, 0.0, 992.0))
        moved = (points[0], points[1], (100.0, 0.0, 992.1))
        self.assertGreater(contract.triangle_delta(moved, points), 0.0001)
        with self.assertRaises(ValueError):
            contract.triangle_delta(
                (points[0], points[1], (100.0, 0.0, float("nan"))), points
            )
        with self.assertRaises(ValueError):
            list(contract.interior_top_triangles(sections[:-1]))

    def test_only_source_cut_intersecting_components_are_selected(self):
        self.assertTrue(contract.overlaps((55000, 50000, 58150, 53150)))
        self.assertFalse(contract.overlaps((0, 0, 3150, 3150)))
        with self.assertRaises(ValueError):
            contract.overlaps((55000, 50000, 55000, 53150))

    def test_plan_rejects_camera_drift_and_preserves_four_original_internal_poses(self):
        path = Path(__file__).resolve().parents[2] / contract.SURVEY_FILE
        original = {
            r["frame_id"]: r for r in csv.DictReader(io.StringIO(path.read_text()))
        }
        frames = []
        for frame_id in contract.FRAME_IDS:
            old = original[frame_id]
            row = {
                k: json.loads(old[k])
                for k in (
                    "road_position_cm",
                    "camera_location_cm",
                    "target_cm",
                    "ball_location_cm",
                )
            }
            row.update(
                frame_id=frame_id,
                window_id=old["window_id"],
                station_m=float(old["station_m"]),
                fov_deg=float(old["fov_deg"]),
            )
            frames.append(row)
        source = {"windows": [], "source_identity": {}}
        with patch.object(
            contract, "build_survey_plan", return_value={"frames": frames}
        ):
            plan = contract.diagnostic_plan(source, "a" * 40, path)
            self.assertEqual(plan["frame_count"], 12)
            self.assertEqual(
                {r["diagnostic_mode"] for r in plan["frames"]}, set(contract.MODES)
            )
            frames[0]["camera_location_cm"][0] += 0.01
            with self.assertRaisesRegex(ValueError, "camera pose differs"):
                contract.diagnostic_plan(source, "a" * 40, path)

    def test_each_mode_is_local_and_restores_visibility_and_hidden_shadow(self):
        capture = ContactCapture.__new__(ContactCapture)
        capture.support = Component("support")
        capture.components = [Component("landscape-a"), Component("landscape-b")]
        capture.surface_state = [
            (c, (True, True)) for c in (capture.support, *capture.components)
        ]
        capture.index = 0
        capture.pending = {}
        for mode in contract.MODES:
            capture.report = {"planned_frames": [{"diagnostic_mode": mode}]}
            with patch(
                "scripts.ue.sa_calobra_tpp_survey_capture.SurveyCapture._submit"
            ):
                capture._submit()
            self.assertEqual(capture.support.state["visible"], mode != "support-hidden")
            self.assertTrue(
                all(
                    c.state["visible"] == (mode != "local-landscape-hidden")
                    for c in capture.components
                )
            )
            for c, _ in capture.surface_state:
                if not c.state["visible"]:
                    self.assertFalse(c.state["cast_hidden_shadow"])
        capture.restore_visibility()
        self.assertTrue(
            all(
                c.state == {"visible": True, "cast_hidden_shadow": True}
                for c, _ in capture.surface_state
            )
        )
        # Cleanup attempts every component even when one native readback fails.
        capture.support.fail = True
        capture.components[0].state["visible"] = False
        with self.assertRaises(RuntimeError):
            capture.restore_visibility()
        self.assertTrue(capture.components[0].state["visible"])

    def evidence(self, root):
        capture = root / "capture"
        (capture / "frames").mkdir(parents=True)
        frames = []
        for frame in contract.FRAME_IDS:
            for mode in contract.MODES:
                frame_id = f"{frame}-{mode}"
                path = f"frames/{frame_id}.png"
                write_png(capture / path)
                row = {
                    "frame_id": frame_id,
                    "source_frame_id": frame,
                    "diagnostic_mode": mode,
                    "window_id": contract.WINDOW,
                    "road_position_cm": [0, 0, 0],
                    "camera_location_cm": [0, 0, 1],
                    "target_cm": [1, 0, 0],
                    "ball_location_cm": [0, 0, 0.4],
                    "station_m": 17.766589862,
                    "fov_deg": 76.0,
                    "file": path,
                    "size_bytes": (capture / path).stat().st_size,
                    "sha256": contract.digest(capture / path),
                    "native_readiness": {"status": "NATIVE_LOADING_AND_MIPS_READY"},
                    "surface_visibility": {
                        "support_visible": mode != "support-hidden",
                        "landscape_visible": mode != "local-landscape-hidden",
                    },
                }
                frames.append(row)
        report = {
            "status": "SHOULDER_CONTACT_CAPTURED",
            "exact_sha": "a" * 40,
            "source_road_sha": contract.FROZEN_SHA,
            "window_id": contract.WINDOW,
            "geometry_mutated": False,
            "saved_to_map": False,
            "rendered_owner": "PENDING_PAIRED_VISUAL_REVIEW",
            "support": {
                "interior_top_triangles_compared": 5232,
                "max_coordinate_delta_cm": 0.0,
                "triangle_sha256": "a" * 64,
            },
            "landscape": {"components": [{"bounds_cm": [55000, 50000, 58150, 53150]}]},
            "cut_manifest_sha256": contract.CUT_SHA256,
            "restoration": {
                "status": "RESTORED",
                "map_sha256": contract.MAP_SHA256,
                "support_triangle_sha256": "a" * 64,
            },
            "plan": {"frames": frames},
        }
        (root / "shoulder-contact.json").write_text(json.dumps(report))
        (capture / "survey.json").write_text(
            json.dumps({"status": "CAPTURED", "frames": frames})
        )
        return report, frames

    def test_verifier_rejects_incomplete_restoration_and_false_surface_owner_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, frames = self.evidence(root)
            self.assertEqual(contract.verify(root, "a" * 40)["frame_count"], 12)
            report["restoration"]["support_triangle_sha256"] = "b" * 64
            (root / "shoulder-contact.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "conservation failed"):
                contract.verify(root, "a" * 40)
            report["restoration"]["support_triangle_sha256"] = "a" * 64
            report["rendered_owner"] = "ROAD_FIXED_PASS"
            (root / "shoulder-contact.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "contract failed"):
                contract.verify(root, "a" * 40)
            report["rendered_owner"] = "PENDING_PAIRED_VISUAL_REVIEW"
            (root / "shoulder-contact.json").write_text(json.dumps(report))
            (root / "capture/survey.json").write_text(
                json.dumps({"status": "CAPTURED", "frames": frames[:-1]})
            )
            with self.assertRaisesRegex(ValueError, "inventory"):
                contract.verify(root, "a" * 40)


if __name__ == "__main__":
    unittest.main()
