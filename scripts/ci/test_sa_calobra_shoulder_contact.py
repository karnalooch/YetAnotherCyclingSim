"""Failure and conservation tests for the bounded Issue459 diagnostic."""

import csv
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import struct
import unittest
from unittest.mock import patch
from unittest.mock import Mock
from types import SimpleNamespace

from scripts.ci.test_sa_calobra_tpp_survey_capture import write_png
from scripts.proof import sa_calobra_shoulder_contact as contract
from scripts.ue.capture_sa_calobra_shoulder_contact import (
    ContactCapture,
    Owner,
    native_triangles,
    native_support_snapshot,
    native_component_layout,
    mesh_digest,
    mesh_triangle,
    read_hairpin_wall_contact,
    read_support022,
)


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
    def support022_native_fixture(self):
        from scripts.ue import road_shoulder_sources as sources

        window = {
            "id": contract.SUPPORT022_WINDOW,
            "sections": [
                [[float(i), j / 5.0, 10.0 + j / 100.0] for j in range(25)]
                for i in range(153)
            ],
        }
        owner = sources._owner(
            window, 22, sources._support_top_witnesses(window["sections"]), "ordinary"
        )
        top = dict(sources.iter_expected_triangles(owner))
        positions = {**top, **dict.fromkeys(range(7904, 8616), ((1.0, 2.0, 3.0),) * 3)}
        path = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.L_SaCalobraAccepted_20261004:PersistentLevel.DynamicMeshActor_23"
        component = Component(path + ".DynamicMeshComponent")
        mesh = SimpleNamespace(get_path_name=lambda: component.path + ".DynamicMesh")
        component.get_dynamic_mesh = lambda: mesh
        actor = SimpleNamespace(
            get_actor_label=lambda: contract.SUPPORT022_LABEL,
            get_path_name=lambda: path,
            get_actor_location=lambda: SimpleNamespace(x=0.0, y=0.0, z=0.0),
            get_actor_rotation=lambda: SimpleNamespace(pitch=0.0, yaw=0.0, roll=0.0),
            get_actor_scale3d=lambda: SimpleNamespace(x=1.0, y=1.0, z=1.0),
            get_dynamic_mesh_component=lambda: component,
        )
        foreign = SimpleNamespace(
            get_actor_label=lambda: "YACS_PERSIST_SUPPORT_099",
            get_dynamic_mesh_component=Mock(
                side_effect=AssertionError("unowned query")
            ),
        )
        counts = {"vertex_count": 5555, "triangle_count": 8616}

        def read(actual_mesh, ids):
            self.assertIs(actual_mesh, mesh)
            self.assertEqual(ids, [])
            return json.dumps(
                dict(
                    status="NATIVE_WINDOW0112_SUPPORT_TRIANGLES",
                    geometry_mutated=False,
                    mesh_path=mesh.get_path_name(),
                    **counts,
                    returned_triangle_count=len(positions),
                    triangles=[
                        [tid, *(v for point in tri for v in point)]
                        for tid, tri in positions.items()
                    ],
                )
            )

        getter = Mock(side_effect=read)
        api = SimpleNamespace(
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                read_window0112_support_triangles=getter
            )
        )
        source = {"windows": [window], "source_identity": {"recipe_sha256": "c" * 64}}
        return (
            api,
            source,
            [foreign, actor],
            positions,
            counts,
            getter,
            mesh_digest({"positions": top}),
        )

    def test_support022_requires_nominated_source_and_every_ordered_native_top(self):
        api, source, actors, positions, counts, getter, source_hash = (
            self.support022_native_fixture()
        )
        with patch(
            "scripts.ue.capture_sa_calobra_shoulder_contact.SUPPORT022_TOP_SHA256",
            source_hash,
        ):
            component, mesh, evidence = read_support022(api, actors, source)
            getter.assert_called_once_with(mesh, [])
            actors[0].get_dynamic_mesh_component.assert_not_called()
            self.assertEqual(evidence["source_top_triangles_compared"], 7904)
            self.assertEqual(
                evidence["triangle_sha256"], mesh_digest({"positions": positions})
            )
            self.assertFalse(evidence["native_vertex_ids_observed"])
            self.assertEqual(evidence["original_visibility"], [True, True])
            before_calls = getter.call_count
            with self.assertRaisesRegex(RuntimeError, "missing/ambiguous"):
                read_support022(api, actors + [actors[1]], source)
            with self.assertRaisesRegex(RuntimeError, "window/section"):
                read_support022(api, actors, dict(source, windows=[]))
            self.assertEqual(getter.call_count, before_calls)
            original = positions[0]
            positions[0] = ((*original[0][:2], original[0][2] + 0.001), *original[1:])
            with self.assertRaisesRegex(RuntimeError, "ordered coordinates"):
                read_support022(api, actors, source)
            positions[0] = original
            counts["vertex_count"] += 1
            with self.assertRaisesRegex(RuntimeError, "buffer inventory"):
                read_support022(api, actors, source)
            counts["vertex_count"] -= 1
            # Correct cardinality with one substituted TID is not a dense read.
            positions[9000] = positions.pop(8615)
            with self.assertRaisesRegex(RuntimeError, "buffer inventory"):
                read_support022(api, actors, source)
            positions[8615] = positions.pop(9000)
            with patch.object(
                actors[1],
                "get_actor_scale3d",
                return_value=SimpleNamespace(x=2.0, y=1.0, z=1.0),
            ):
                with self.assertRaisesRegex(RuntimeError, "transform/map"):
                    read_support022(api, actors, source)
            self.assertEqual(
                component.state, {"visible": True, "cast_hidden_shadow": True}
            )

    def test_cleanup_rechecks_support022_perimeter_even_after_primary_failure(self):
        api, source, actors, positions, _, _, source_hash = (
            self.support022_native_fixture()
        )
        with patch(
            "scripts.ue.capture_sa_calobra_shoulder_contact.SUPPORT022_TOP_SHA256",
            source_hash,
        ):
            component, mesh, evidence = read_support022(api, actors, source)
        owner = Owner.__new__(Owner)
        owner.api, owner.target = api, "window0112"
        owner.support022, owner.support022_mesh = component, mesh
        owner.mesh, owner.before, owner.viewport, owner.transient = (
            object(),
            None,
            None,
            [],
        )
        owner.report = {"support022": evidence}
        owner.capture = SimpleNamespace(
            stopped=False,
            handle=None,
            restore_visibility=Mock(),
            mark_cleanup=Mock(),
            report={"status": "CAPTURED"},
        )
        # The only change is a non-top corner outside the 7904 source witnesses.
        positions[8615] = ((1.0, 2.0, 3.001), (1.0, 2.0, 3.0), (1.0, 2.0, 3.0))
        with (
            patch.object(owner, "write"),
            patch(
                "scripts.ue.capture_sa_calobra_shoulder_contact.digest",
                return_value=contract.MAP_SHA256,
            ),
            patch(
                "scripts.ue.capture_sa_calobra_shoulder_contact.native_support_snapshot",
                side_effect=RuntimeError("primary native read failed"),
            ),
        ):
            owner._finish()
        self.assertEqual(owner.report["status"], "FAILED")
        self.assertIn("primary native read failed", owner.report["error"])
        self.assertIn(
            "Support022 complete ordered triangle coordinates changed",
            owner.report["error"],
        )
        self.assertEqual(
            owner.report["restoration"]["support022_triangle_sha256"],
            mesh_digest({"positions": positions}),
        )
        self.assertEqual(
            owner.report["restoration"]["support022_visibility"], [True, True]
        )
        owner.capture.restore_visibility.assert_called_once()

    def test_native_component_bounds_replace_hidden_size_property_and_check_source_grid(
        self,
    ):
        component = Component("source.landscape.component")
        component.state.update(section_base_x=1008, section_base_y=882)
        transform = {
            "rotation_deg": (0.0, 0.0, 0.0),
            "scale": (50.0, 50.0, 100.0),
            "location_cm": (125.0, -250.0, 300.0),
        }
        origin = SimpleNamespace(x=53675.0, y=47000.0, z=60000.0)
        extent = SimpleNamespace(x=3150.0, y=3150.0, z=1200.0)
        getter = Mock(return_value=(origin, extent, 4700.0))
        api = SimpleNamespace(
            SystemLibrary=SimpleNamespace(get_component_bounds=getter)
        )
        layout = native_component_layout(api, component, transform)
        self.assertEqual(layout["component_size_quads"], 126)
        self.assertEqual(layout["bounds_cm"], (50525.0, 43850.0, 56825.0, 50150.0))
        self.assertEqual(layout["section_base"], (1008, 882))
        self.assertEqual(
            layout["native_bounds_query"], "SystemLibrary.GetComponentBounds"
        )
        getter.assert_called_once_with(component)
        # The fixture deliberately has no component_size_quads property.
        self.assertNotIn("component_size_quads", component.state)
        for change in (
            lambda: setattr(origin, "x", 53676.0),
            lambda: setattr(extent, "x", 3150.25),
            lambda: setattr(extent, "y", 1575.0),
            lambda: setattr(extent, "z", float("nan")),
            lambda: component.state.update(section_base_x=True),
            lambda: transform.update(rotation_deg=(0.0, 90.0, 0.0)),
            lambda: transform.update(scale=(100.0, 50.0, 100.0)),
        ):
            origin.x, extent.x, extent.y, extent.z = 53675.0, 3150.0, 3150.0, 1200.0
            component.state["section_base_x"] = 1008
            transform.update(rotation_deg=(0.0, 0.0, 0.0), scale=(50.0, 50.0, 100.0))
            change()
            with self.assertRaises(RuntimeError):
                native_component_layout(api, component, transform)

    def test_hairpin_snapshot_reads_every_dense_native_id_in_bounded_chunks(self):
        mesh = SimpleNamespace(get_path_name=lambda: "source.hairpin.mesh")
        calls = []

        def read(_mesh, ids):
            calls.append(tuple(ids))
            self.assertTrue(ids)
            self.assertLessEqual(len(ids), 12000)
            return json.dumps(
                {
                    "status": "NATIVE_WINDOW0112_SUPPORT_TRIANGLES",
                    "geometry_mutated": False,
                    "mesh_path": mesh.get_path_name(),
                    "vertex_count": 79785,
                    "triangle_count": 132218,
                    "returned_triangle_count": len(ids),
                    "triangles": [
                        [tid, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
                        for tid in ids
                    ],
                }
            )

        api = SimpleNamespace(
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                read_window0112_support_triangles=read
            )
        )
        snapshot = native_support_snapshot(api, mesh, target="hairpin0081")
        self.assertEqual(len(calls), 12)
        self.assertEqual(
            tuple(tid for group in calls for tid in group), tuple(range(132218))
        )
        self.assertEqual(len(calls[-1]), 218)
        self.assertEqual(len(snapshot["positions"]), 132218)
        before = mesh_digest(snapshot)
        snapshot["positions"][132217] = (
            (0.0, 0.0, 0.001),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        )
        self.assertNotEqual(
            mesh_digest(snapshot), before
        )  # Perimeter is conserved too.
        bad = {
            "status": "NATIVE_WINDOW0112_SUPPORT_TRIANGLES",
            "geometry_mutated": False,
            "mesh_path": mesh.get_path_name(),
            "vertex_count": 79785,
            "triangle_count": 132218,
            "returned_triangle_count": 0,
            "triangles": [],
        }
        api.YacsLandscapeMeshDiagnosticLibrary.read_window0112_support_triangles = Mock(
            return_value=json.dumps(bad)
        )
        with self.assertRaisesRegex(RuntimeError, "exact requested IDs"):
            native_support_snapshot(api, mesh, target="hairpin0081")

    def test_hairpin_source_interior_uses_all_2401_rows_with_same_support_lowering(
        self,
    ):
        sections = [
            [[float(i), float(j), 10.04] for j in range(25)] for i in range(2401)
        ]
        triangles = list(
            contract.interior_top_triangles(sections, target="hairpin0081")
        )
        self.assertEqual(len(triangles), 115200)
        self.assertEqual(triangles[0][0], 2)
        self.assertEqual(triangles[-1][0], 124797)
        self.assertAlmostEqual(triangles[0][1][0][2], 996.0)
        with self.assertRaisesRegex(ValueError, "2401x25"):
            list(contract.interior_top_triangles(sections[:110], target="hairpin0081"))

    def test_native_triangle_adapter_preserves_sparse_ids_and_rejects_incomplete_or_nonfinite_reads(
        self,
    ):
        mesh = SimpleNamespace(get_path_name=lambda: "saved.target.mesh")
        result = {
            "status": "NATIVE_WINDOW0112_SUPPORT_TRIANGLES",
            "geometry_mutated": False,
            "mesh_path": "saved.target.mesh",
            "vertex_count": 3,
            "triangle_count": 1,
            "returned_triangle_count": 1,
            "triangles": [[2, 1.25, 2.5, 3.75, 4, 5, 6, 7, 8, 9]],
        }
        read = Mock(side_effect=lambda *_args: json.dumps(result))
        api = SimpleNamespace(
            YacsLandscapeMeshDiagnosticLibrary=SimpleNamespace(
                read_window0112_support_triangles=read
            )
        )
        full = native_triangles(api, mesh)
        self.assertEqual(mesh_triangle(full, 2)[0], (1.25, 2.5, 3.75))
        self.assertEqual(
            mesh_digest(full), mesh_digest(native_triangles(api, mesh, [2]))
        )
        read.assert_called_with(mesh, [2])
        for field in ("vertex_count", "triangle_count", "returned_triangle_count"):
            result[field] = float(result[field])
        result["triangles"][0][0] = 2.0
        self.assertEqual(mesh_digest(full), mesh_digest(native_triangles(api, mesh)))
        result["triangles"][0][0] = True
        with self.assertRaisesRegex(RuntimeError, "integer ID/count"):
            native_triangles(api, mesh)
        result["triangles"][0][0] = 2.5
        with self.assertRaisesRegex(RuntimeError, "integer ID/count"):
            native_triangles(api, mesh)
        result["triangles"][0][0] = 2
        with self.assertRaisesRegex(RuntimeError, "exact requested IDs"):
            native_triangles(api, mesh, [0])
        result["triangles"][0][-1] = float("nan")
        with self.assertRaisesRegex(RuntimeError, "invalid ID or coordinates"):
            native_triangles(api, mesh)
        result["triangles"] = []
        result["returned_triangle_count"] = 0
        with self.assertRaisesRegex(RuntimeError, "inventory differs"):
            native_triangles(api, mesh)
        result.clear()
        result["error"] = "missing or duplicate native support triangle ID"
        self.assertIsNone(native_triangles(api, mesh, [2], allow_missing=True))
        with self.assertRaisesRegex(RuntimeError, "query failed"):
            native_triangles(api, mesh, [2])

    def test_native_shutdown_is_guaranteed_when_final_readback_raises(self):
        owner = Owner.__new__(Owner)
        quit_editor = Mock()
        keepalive = Mock()
        owner.api = SimpleNamespace(
            SystemLibrary=SimpleNamespace(quit_editor=quit_editor),
            EditorPythonScripting=SimpleNamespace(
                set_keep_python_script_alive=keepalive
            ),
        )
        with patch.object(
            owner, "_finish", side_effect=RuntimeError("final native mesh lost")
        ):
            with self.assertRaisesRegex(RuntimeError, "native mesh lost"):
                owner.finish()
        keepalive.assert_called_once_with(False)
        quit_editor.assert_called_once()

    def test_commandline_keepalive_wraps_async_capture_and_cleanup(self):
        owner = Owner.__new__(Owner)
        events = []
        owner.api = SimpleNamespace(
            EditorPythonScripting=SimpleNamespace(
                set_keep_python_script_alive=lambda value: events.append(value)
            ),
            SystemLibrary=SimpleNamespace(quit_editor=lambda: events.append("quit")),
        )
        owner.capture = SimpleNamespace(start=lambda: events.append("callback"))
        owner._start_capture()
        self.assertEqual(events, [True, "callback"])
        with patch.object(
            owner, "_finish", side_effect=lambda _error: events.append("restore")
        ):
            owner.finish()
        self.assertEqual(events, [True, "callback", "restore", False, "quit"])

    def test_native_quit_still_runs_when_keepalive_release_fails(self):
        owner = Owner.__new__(Owner)
        owner.capture = None
        owner.report = {"status": "SHOULDER_CONTACT_CAPTURED"}
        quit_editor = Mock()
        owner.api = SimpleNamespace(
            EditorPythonScripting=SimpleNamespace(
                set_keep_python_script_alive=Mock(
                    side_effect=RuntimeError("release lost")
                )
            ),
            SystemLibrary=SimpleNamespace(quit_editor=quit_editor),
        )
        with (
            patch.object(owner, "_finish") as cleanup,
            patch.object(owner, "write") as write,
        ):
            with self.assertRaisesRegex(RuntimeError, "release lost"):
                owner.finish("capture failed")
        cleanup.assert_called_once_with("capture failed")
        write.assert_called_once_with()
        self.assertEqual(owner.report["status"], "FAILED")
        self.assertIn("release lost", owner.report["error"])
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
            self.assertEqual(plan["frame_count"], 16)
            self.assertEqual(plan["diagnostic_schema_version"], 2)
            self.assertEqual(
                {r["diagnostic_mode"] for r in plan["frames"]},
                set(contract.WINDOW_MODES),
            )
            for first, original_row in zip(range(0, 16, 4), frames, strict=True):
                for control in plan["frames"][first : first + 4]:
                    for key, value in original_row.items():
                        if key != "frame_id":
                            self.assertEqual(control[key], value)
            frames[0]["camera_location_cm"][0] += 0.01
            with self.assertRaisesRegex(ValueError, "camera pose differs"):
                contract.diagnostic_plan(source, "a" * 40, path)

    def test_hairpin_plan_reuses_two_exact_gpu_poses_without_altering_0112_selection(
        self,
    ):
        path = Path(__file__).resolve().parents[2] / contract.SURVEY_FILE
        original = {
            r["frame_id"]: r for r in csv.DictReader(io.StringIO(path.read_text()))
        }
        frames = []
        for frame_id in contract.HAIRPIN_FRAME_IDS:
            old = original[frame_id]
            row = {
                key: json.loads(old[key])
                for key in (
                    "road_position_cm",
                    "camera_location_cm",
                    "target_cm",
                    "ball_location_cm",
                )
            }
            row.update(
                frame_id=frame_id,
                window_id=old["window_id"],
                direction=old["direction"],
                station_m=float(old["station_m"]),
                fov_deg=float(old["fov_deg"]),
            )
            frames.append(row)
        material = {
            "frame_count": 68,
            "survey_sha256": contract.SURVEY_SHA256,
            "frames": [
                {key: value for key, value in row.items() if key != "ball_location_cm"}
                for row in frames
            ]
            + [{"frame_id": f"fixture-{i}"} for i in range(66)],
        }
        raw = json.dumps(material).encode()
        with tempfile.TemporaryDirectory() as directory:
            view_path = Path(directory) / "fixed-material-views.json"
            view_path.write_bytes(raw)
            with (
                patch.object(
                    contract,
                    "MATERIAL_VIEW_PLAN_SHA256",
                    hashlib.sha256(raw).hexdigest(),
                ),
                patch.object(contract, "MATERIAL_VIEW_PLAN_SIZE", len(raw)),
                patch.object(
                    contract, "build_survey_plan", return_value={"frames": frames}
                ),
            ):
                source = {"windows": [], "source_identity": {}}
                plan = contract.diagnostic_plan(
                    source,
                    "a" * 40,
                    path,
                    target="hairpin0081",
                    view_plan_path=view_path,
                )
                self.assertEqual(plan["frame_count"], 6)
                self.assertEqual(
                    plan["source_poses"],
                    ["window-0081-forward-00008", "window-0081-reverse-00004"],
                )
                self.assertEqual(plan["frames"][0]["station_m"], 153.86538846592342)
                self.assertEqual(plan["frames"][3]["station_m"], 230.79808269888514)
                self.assertEqual(
                    plan["frames"][0]["camera_location_cm"],
                    material["frames"][0]["camera_location_cm"],
                )
                self.assertEqual(
                    plan["frames"][3]["camera_location_cm"],
                    material["frames"][1]["camera_location_cm"],
                )
                self.assertEqual(
                    contract.FRAME_IDS,
                    (
                        "window-0112-forward-00001",
                        "window-0112-forward-00002",
                        "window-0112-reverse-00001",
                        "window-0112-reverse-00002",
                    ),
                )
                with self.assertRaisesRegex(ValueError, "authenticated 68-frame"):
                    contract.diagnostic_plan(
                        source, "a" * 40, path, target="hairpin0081"
                    )
                view_path.write_bytes(raw + b"\n")
                with self.assertRaisesRegex(ValueError, "plan bytes differ"):
                    contract.diagnostic_plan(
                        source,
                        "a" * 40,
                        path,
                        target="hairpin0081",
                        view_plan_path=view_path,
                    )

    def test_failed_initialization_reports_original_error_before_missing_survey_and_cannot_restore_pass(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps(
                {
                    "status": "FAILED",
                    "error": "LandscapeComponent has no component_size_quads",
                    "restoration": {"status": "FAILED"},
                }
            ).encode()
            (root / "shoulder-contact.json").write_bytes(raw)
            with self.assertRaisesRegex(
                ValueError, "LandscapeComponent has no component_size_quads"
            ):
                contract.verify(root, "a" * 40)
            self.assertEqual((root / "shoulder-contact.json").read_bytes(), raw)
            self.assertFalse((root / "capture/survey.json").exists())
        owner = Owner.__new__(Owner)
        owner.capture = owner.before = owner.mesh = owner.viewport = None
        owner.transient, owner.report = [], {}
        with (
            patch.object(owner, "write"),
            patch(
                "scripts.ue.capture_sa_calobra_shoulder_contact.digest",
                return_value=contract.MAP_SHA256,
            ),
        ):
            owner._finish()
        self.assertEqual(owner.report["status"], "FAILED")
        self.assertEqual(owner.report["restoration"]["status"], "FAILED")
        self.assertEqual(owner.report["error"], "Diagnostic capture was not started")
        with (
            patch.object(owner, "write"),
            patch.object(
                owner,
                "release_height_mips",
                side_effect=RuntimeError("mip release failed"),
            ),
            patch(
                "scripts.ue.capture_sa_calobra_shoulder_contact.digest",
                return_value=contract.MAP_SHA256,
            ),
        ):
            owner._finish("capture initialization failed")
        self.assertFalse(owner.report["restoration"]["height_mip_leases_released"])
        self.assertIn("mip release failed", owner.report["error"])

    def test_each_mode_is_local_and_restores_visibility_and_hidden_shadow(self):
        capture = ContactCapture.__new__(ContactCapture)
        capture.support = Component("support")
        capture.support022 = Component("support022")
        capture.components = [Component("landscape-a"), Component("landscape-b")]
        capture.surface_state = [
            (c, (True, True))
            for c in (capture.support, *capture.components, capture.support022)
        ]
        capture.index = 0
        capture.pending = {}
        for mode in contract.WINDOW_MODES:
            capture.report = {"planned_frames": [{"diagnostic_mode": mode}]}
            with patch(
                "scripts.ue.sa_calobra_tpp_survey_capture.SurveyCapture._submit"
            ):
                capture._submit()
            self.assertEqual(capture.support.state["visible"], mode != "support-hidden")
            self.assertEqual(
                capture.support022.state["visible"], mode != "support022-hidden"
            )
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
        capture.support022.state.update(visible=False, cast_hidden_shadow=False)
        with self.assertRaises(RuntimeError):
            capture.restore_visibility()
        self.assertTrue(capture.components[0].state["visible"])
        self.assertEqual(
            capture.support022.state, {"visible": True, "cast_hidden_shadow": True}
        )
        capture.support022 = None
        capture.report = {"planned_frames": [{"diagnostic_mode": "support022-hidden"}]}
        with self.assertRaisesRegex(RuntimeError, "authenticated owner"):
            capture._submit()

    def evidence(
        self, root, *, target="window0112", cut_raw=None, include_support022=False
    ):
        if include_support022 and target != "window0112":
            raise ValueError("Support022 fixture belongs only to window0112")
        spec = contract.target_spec(target)
        capture = root / "capture"
        (capture / "frames").mkdir(parents=True)
        frames = []
        for frame in spec["frame_ids"]:
            for mode in contract.WINDOW_MODES if include_support022 else contract.MODES:
                frame_id = f"{frame}-{mode}"
                path = f"frames/{frame_id}.png"
                write_png(capture / path)
                row = {
                    "frame_id": frame_id,
                    "source_frame_id": frame,
                    "diagnostic_mode": mode,
                    "window_id": spec["window_id"],
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
            "window_id": spec["window_id"],
            "geometry_mutated": False,
            "saved_to_map": False,
            "rendered_owner": "PENDING_PAIRED_VISUAL_REVIEW",
            "support": {
                "interior_top_triangles_compared": (spec["section_count"] - 1) * 48,
                "vertices": spec["mesh_counts"][0],
                "triangles": spec["mesh_counts"][1],
                "max_coordinate_delta_cm": 0.0,
                "triangle_sha256": "a" * 64,
            },
            "landscape": {"components": [{"bounds_cm": [55000, 50000, 58150, 53150]}]},
            "cut_manifest_sha256": spec["cut_sha256"],
            "restoration": {
                "status": "RESTORED",
                "map_sha256": contract.MAP_SHA256,
                "support_triangle_sha256": "a" * 64,
            },
            "plan": {"frames": frames},
        }
        if include_support022:
            prefix = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004.L_SaCalobraAccepted_20261004:PersistentLevel."
            primary, neighbour = (
                prefix + "DynamicMeshActor_113",
                prefix + "DynamicMeshActor_23",
            )
            component = neighbour + ".DynamicMeshComponent"
            report["support"].update(
                label="YACS_PERSIST_SUPPORT_112",
                path=primary,
                component=primary + ".DynamicMeshComponent",
            )
            report["landscape"]["components"][0]["path"] = (
                prefix + "Landscape.Component"
            )
            report["source_identity"] = {"recipe_sha256": "c" * 64}
            report["support022"] = dict(
                label=contract.SUPPORT022_LABEL,
                path=neighbour,
                component=component,
                mesh_path=component + ".DynamicMesh",
                location_cm=[0.0] * 3,
                rotation_deg=[0.0] * 3,
                scale=[1.0] * 3,
                source_window_id=contract.SUPPORT022_WINDOW,
                source_section_count=153,
                source_top_triangles_compared=7904,
                source_top_triangle_sha256=contract.SUPPORT022_TOP_SHA256,
                source_recipe_sha256="c" * 64,
                vertices=5555,
                triangles=8616,
                max_coordinate_delta_cm=0.0,
                native_query="YacsLandscapeMeshDiagnosticLibrary.ReadWindow0112SupportTriangles",
                native_triangle_ids_dense=True,
                native_triangle_ids_in_digest=True,
                native_vertex_ids_observed=False,
                triangle_sha256="b" * 64,
                original_visibility=[True, True],
            )
            report["restoration"].update(
                support022_triangle_sha256="b" * 64, support022_visibility=[True, True]
            )
            report["plan"].update(
                diagnostic_schema_version=2,
                frame_count=16,
                source_poses=list(contract.FRAME_IDS),
                original_survey_csv_sha256=contract.SURVEY_SHA256,
            )
            for row in frames:
                row["surface_visibility"].update(
                    support022_visible=row["diagnostic_mode"] != "support022-hidden",
                    support022_component=component,
                    support_component=report["support"]["component"],
                    landscape_components=[
                        c["path"] for c in report["landscape"]["components"]
                    ],
                    hidden_shadow_disabled_on_hidden_surfaces=True,
                )
        if target == "hairpin0081":
            bounds = contract.cut_bounds(cut_raw, target=target)
            (root / "source-cut-manifest.json").write_bytes(cut_raw)
            report["cut_footprint_cm"] = bounds
            report["landscape"]["components"] = [{"bounds_cm": bounds}]
            report["plan"].update(
                diagnostic_target=target,
                material_view_plan_sha256=contract.MATERIAL_VIEW_PLAN_SHA256,
            )
        (root / "shoulder-contact.json").write_text(json.dumps(report))
        (capture / "survey.json").write_text(
            json.dumps({"status": "CAPTURED", "frames": frames})
        )
        return report, frames

    def test_current_verifier_requires_16_frames_and_support022_identity_restore_visibility(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, frames = self.evidence(root, include_support022=True)
            self.assertEqual(contract.verify(root, "a" * 40)["frame_count"], 16)
            self.assertLess(
                (root / "shoulder-contact.json").stat().st_size, 4 * 1024 * 1024
            )
            changes = (
                lambda r: r.pop("support022"),
                lambda r: r["plan"].pop("diagnostic_schema_version"),
                lambda r: r["plan"].update(diagnostic_schema_version=True),
                lambda r: r["support022"].update(source_top_triangle_sha256="a" * 64),
                lambda r: r["support022"].update(vertices=5554),
                lambda r: r["support022"].update(native_vertex_ids_observed=True),
                lambda r: r["support022"].update(component=r["support"]["component"]),
                lambda r: r["restoration"].update(support022_triangle_sha256="a" * 64),
                lambda r: r["restoration"].update(support022_visibility=[True, False]),
                lambda r: r["plan"]["frames"][3].update(camera_location_cm=[0, 0, 2]),
            )
            for change in changes:
                with self.subTest(change=change):
                    value = copy.deepcopy(report)
                    change(value)
                    (root / "shoulder-contact.json").write_text(json.dumps(value))
                    with self.assertRaises(ValueError):
                        contract.verify(root, "a" * 40)
            (root / "shoulder-contact.json").write_text(json.dumps(report))
            for field, value in (
                ("support022_visible", True),
                ("support022_component", report["support"]["component"]),
                ("hidden_shadow_disabled_on_hidden_surfaces", False),
            ):
                rows = copy.deepcopy(frames)
                rows[3]["surface_visibility"][field] = value
                (root / "capture/survey.json").write_text(
                    json.dumps({"status": "CAPTURED", "frames": rows})
                )
                with self.assertRaisesRegex(ValueError, "visibility/owner"):
                    contract.verify(root, "a" * 40)
            rows = [r for r in frames if r["diagnostic_mode"] != "support022-hidden"]
            (root / "capture/survey.json").write_text(
                json.dumps({"status": "CAPTURED", "frames": rows})
            )
            with self.assertRaisesRegex(ValueError, "inventory"):
                contract.verify(root, "a" * 40)

    def test_hairpin_verifier_requires_source_cut_bytes_and_six_separate_modes(self):
        raw = json.dumps(
            {
                "operation": "CUT_ONLY",
                "grid_step_m": 0.5,
                "rect": {
                    "min_x": 2080,
                    "min_y": 990,
                    "max_x": 2300,
                    "max_y": 1310,
                    "width": 221,
                    "height": 321,
                },
            }
        ).encode()
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(
                contract, "HAIRPIN_CUT_SHA256", hashlib.sha256(raw).hexdigest()
            ),
            patch.object(contract, "HAIRPIN_CUT_SIZE", len(raw)),
        ):
            root = Path(directory)
            report, frames = self.evidence(root, target="hairpin0081", cut_raw=raw)
            self.assertEqual(
                contract.verify(root, "a" * 40, target="hairpin0081")["frame_count"], 6
            )
            self.assertEqual(
                report["cut_footprint_cm"], (104000.0, 49500.0, 115000.0, 65500.0)
            )
            self.assertFalse(
                contract.overlaps(contract.CUT_BOUNDS_CM, report["cut_footprint_cm"])
            )
            with self.assertRaisesRegex(ValueError, "contract failed"):
                contract.verify(root, "a" * 40)
            (root / "source-cut-manifest.json").write_bytes(raw + b"\n")
            with self.assertRaisesRegex(ValueError, "CUT footprint source differs"):
                contract.verify(root, "a" * 40, target="hairpin0081")
            (root / "source-cut-manifest.json").write_bytes(raw)
            (root / "capture/survey.json").write_text(
                json.dumps({"status": "CAPTURED", "frames": frames[:-1]})
            )
            with self.assertRaisesRegex(ValueError, "inventory"):
                contract.verify(root, "a" * 40, target="hairpin0081")

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


class HairpinWallContactTests(unittest.TestCase):
    def setUp(self):
        # Fixed native inventory, small source AOI. These are synthetic unit
        # fixtures only; no value stands in for an observed native elevation.
        change = patch.object(contract, "HAIRPIN_WALL_ROWS", (1, 4))
        change.start()
        self.addCleanup(change.stop)
        self.raw = b"".join(
            struct.pack("<f", 900.0 + gy * 10 + gx)
            for gy in range(11)
            for gx in range(11)
        )
        cut = {
            "operation": "CUT_ONLY",
            "grid_step_m": 0.5,
            "rect": {
                "min_x": 0,
                "min_y": 0,
                "max_x": 10,
                "max_y": 10,
                "width": 11,
                "height": 11,
            },
            "layer_encoding": "LANDSCAPE_TEXTURE_PATCH_WORLD_UNITS_F32_MIN",
            "blend_mode": "Min",
            "height_encoding": "WorldUnits",
            "world_space_unit": "centimeter",
            "zero_height_meaning": "WorldZero",
            "patch_file": "ma2141-cut-patch.f32",
            "patch_byte_count": len(self.raw),
            "patch_sha256": hashlib.sha256(self.raw).hexdigest(),
            "profile_sha256": "b" * 64,
        }
        self.cut_raw = json.dumps(cut).encode()
        for name, value in (
            ("HAIRPIN_CUT_SHA256", hashlib.sha256(self.cut_raw).hexdigest()),
            ("HAIRPIN_CUT_SIZE", len(self.cut_raw)),
        ):
            change = patch.object(contract, name, value)
            change.start()
            self.addCleanup(change.stop)
        self.identity = dict(
            path="D:/fixture/ma2141-cut-patch.f32",
            size_bytes=len(self.raw),
            sha256_before=cut["patch_sha256"],
            sha256_after=cut["patch_sha256"],
        )
        self.source_identity = dict(
            recipe_sha256="a" * 64, hairpin_pavement_lift_m=0.04
        )
        self.support = dict(
            label="YACS_PERSIST_SUPPORT_185",
            path="/source.actor",
            component="/source.actor.mesh",
            triangle_sha256="a" * 64,
        )
        self.sections = [[(0.0, 0.0, 0.0)] * 25 for _ in range(2401)]
        dummy = ((1000000.0, 1000000.0, 0.0),) * 3
        self.positions = dict.fromkeys(range(132218), dummy)
        self.outer = {i: (i * 12.5, 25.0, 1000.0 + i) for i in range(1, 5)}
        for i in range(1, 5):
            self.sections[i][0] = (i * 0.125, 0.75, (1008.0 + i) / 100.0)
        for i in range(1, 4):
            a, b = self.outer[i], self.outer[i + 1]
            p, q = (tuple(v * 100 for v in self.sections[k][0]) for k in (i, i + 1))
            p, q = (*p[:2], p[2] - 8.0), (*q[:2], q[2] - 8.0)
            self.positions[i * 52], self.positions[i * 52 + 1] = (a, p, b), (p, q, b)
        a, b = self.outer[1], self.outer[2]
        ga, gb = (*a[:2], a[2] - 80.0), (*b[:2], b[2] - 120.0)
        # Actual IDs are intentionally nonconsecutive. A guessed wall offset
        # or two-triangles-per-source-row formula cannot satisfy this fixture.
        self.positions[130005], self.positions[131999] = (a, b, gb), (a, gb, ga)
        a, b = self.outer[2], self.outer[3]
        crossing = tuple(x + 0.4 * (y - x) for x, y in zip(a, b, strict=True))
        self.positions[129901] = (crossing, b, (*b[:2], b[2] - 50.0))

    def build(self):
        return contract.hairpin_wall_contact(
            self.positions,
            self.sections,
            self.support,
            self.source_identity,
            self.cut_raw,
            self.raw,
            self.identity,
        )

    def verify(self, value):
        contract.verify_wall_contact(
            value,
            dict(support=self.support, source_identity=self.source_identity),
            self.cut_raw,
        )

    def resign(self, value):
        value["payload_sha256"] = contract._wall_hash(
            {k: v for k, v in value.items() if k != "payload_sha256"}
        )

    def test_actual_wall_corners_bind_source_rows_and_partial_crossing_without_guessing_ids(
        self,
    ):
        before = dict(self.positions)
        value = self.build()
        self.verify(value)
        self.assertEqual(
            [(r[0], r[1]) for r in value["wall_triangles"]],
            [(1, 130005), (1, 131999), (2, 129901)],
        )
        self.assertEqual(value["segments_without_matched_wall"], [3])
        self.assertEqual(
            value["wall_triangles"][-1][2:5], list(self.positions[129901][0])
        )
        self.assertEqual(self.positions, before)
        self.assertEqual(value["non_top_triangles_scanned"], 7418)
        self.assertFalse(value["geometry_mutated"])
        self.assertFalse(value["native_vertex_ids_available"])

    def test_foreign_side_and_top_are_not_wall_candidates_and_ambiguous_owner_fails(
        self,
    ):
        self.positions[124900] = tuple(
            (p[0], p[1] + 500.0, p[2]) for p in self.positions[130005]
        )
        value = self.build()
        self.assertNotIn(124900, [r[1] for r in value["wall_triangles"]])
        self.assertTrue(all(r[1] >= 124800 for r in value["wall_triangles"]))
        with self.assertRaisesRegex(ValueError, "ambiguous source-segment"):
            contract._select_wall_faces(
                self.positions,
                {1: (self.outer[1], self.outer[2]), 2: (self.outer[1], self.outer[2])},
            )

    def test_disconnected_floating_or_degenerate_owner_never_gets_an_observation_pass(
        self,
    ):
        original = dict(self.positions)
        for tid in (130005, 131999):
            self.positions[tid] = tuple(
                (*p[:2], p[2] - 5.0) for p in self.positions[tid]
            )
        with self.assertRaisesRegex(ValueError, "does not meet its actual outer top"):
            self.build()
        self.positions = dict(original)
        a, gb, ga = self.positions[131999]
        self.positions[131999] = (a, (*gb[:2], gb[2] - 1.0), ga)
        with self.assertRaisesRegex(ValueError, "wall pair is disconnected"):
            self.build()
        self.positions = original
        a, p, b = self.positions[52]
        self.positions[52] = (b, p, b)
        with self.assertRaisesRegex(ValueError, "no XY span"):
            self.build()

    def test_source_cut_keeps_exact_row_major_raw_nodes_and_no_interpolated_native_height(
        self,
    ):
        value = self.build()
        cut = value["cut_source"]
        self.assertFalse(cut["height_interpolation_performed"])
        self.assertFalse(cut["final_native_landscape_height_observed"])
        self.assertEqual(cut["corners_outside_source_patch"], [])
        shifted = copy.deepcopy(value["wall_triangles"])
        for row in shifted:
            for column in (2, 5, 8):
                row[column] += 100000.0
        keys, outside = contract._wall_cut_keys(shifted, json.loads(self.cut_raw))
        self.assertEqual(keys, [])
        self.assertEqual(len(outside), 3 * len(shifted))
        self.assertEqual(
            [node[:2] for node in cut["nodes"]], [[0, 0], [1, 0], [0, 1], [1, 1]]
        )
        for gx, gy, offset, raw, x, y, z in cut["nodes"]:
            self.assertEqual(offset, (gy * 11 + gx) * 4)
            self.assertEqual(bytes.fromhex(raw), self.raw[offset : offset + 4])
            self.assertEqual((x, y, z), (gx * 50.0, gy * 50.0, 900.0 + gy * 10 + gx))
        bad = copy.deepcopy(value)
        bad["cut_source"]["nodes"][0][3] = struct.pack(
            ">f", bad["cut_source"]["nodes"][0][-1]
        ).hex()
        self.resign(bad)
        with self.assertRaisesRegex(ValueError, "raw4/position/height"):
            self.verify(bad)

    def test_hash_source_correspondence_and_retained_payload_bounds_are_enforced(self):
        value = self.build()
        value["wall_triangles"][0][4] += 1.0
        with self.assertRaisesRegex(ValueError, "payload hash"):
            self.verify(value)
        value = self.build()
        value["pavement_edge_rows_cm"][0][3] += 1.0
        self.resign(value)
        with self.assertRaisesRegex(ValueError, "not bound to consecutive source"):
            self.verify(value)
        with patch.object(contract, "WALL_EVIDENCE_LIMIT", 512):
            with self.assertRaisesRegex(ValueError, "exceeds 1MiB"):
                self.build()
        self.raw = self.raw[:-1] + bytes([self.raw[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "patch bytes differ"):
            self.build()

    def test_file_read_authenticates_whole_patch_before_after_without_native_or_source_writes(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "ma2141-cut-patch.f32"
            path.write_bytes(self.raw)
            value = read_hairpin_wall_contact(
                dict(positions=self.positions),
                self.sections,
                self.support,
                self.source_identity,
                root,
                self.cut_raw,
            )
            self.verify(value)
            self.assertEqual(value["source_patch_identity"]["path"], str(path))
            self.assertEqual(path.read_bytes(), self.raw)
            with patch(
                "scripts.ue.capture_sa_calobra_shoulder_contact.digest",
                side_effect=[self.identity["sha256_before"], "f" * 64],
            ):
                with self.assertRaisesRegex(ValueError, "changed during the read"):
                    read_hairpin_wall_contact(
                        dict(positions=self.positions),
                        self.sections,
                        self.support,
                        self.source_identity,
                        root,
                        self.cut_raw,
                    )

    def test_optional_failed_field_cannot_fall_back_to_historical_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, _ = ShoulderContactTests().evidence(
                root, target="hairpin0081", cut_raw=self.cut_raw
            )
            self.assertEqual(
                contract.verify(root, "a" * 40, target="hairpin0081")["frame_count"], 6
            )
            report["support_wall_contact"] = dict(
                schema_version=1, status="FAILED", error="ambiguous wall"
            )
            (root / "shoulder-contact.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, "ambiguous wall"):
                contract.verify(root, "a" * 40, target="hairpin0081")
            report["support_wall_contact"] = self.build()
            report["support"].update(self.support)
            report["source_identity"] = self.source_identity
            (root / "shoulder-contact.json").write_text(json.dumps(report))
            self.assertEqual(
                contract.verify(root, "a" * 40, target="hairpin0081")["frame_count"], 6
            )
            self.assertLess(
                (root / "shoulder-contact.json").stat().st_size, 2 * 1024 * 1024
            )

    def test_full_321_row_observation_stays_inside_existing_receipt_budget(self):
        first, last = 1560, 1880
        self.raw = b"".join(
            struct.pack("<f", 900.0 + gy * 10 + gx)
            for gy in range(11)
            for gx in range(380, 481)
        )
        cut = json.loads(self.cut_raw)
        cut.update(
            rect={
                "min_x": 380,
                "min_y": 0,
                "max_x": 480,
                "max_y": 10,
                "width": 101,
                "height": 11,
            },
            patch_sha256=hashlib.sha256(self.raw).hexdigest(),
            patch_byte_count=len(self.raw),
        )
        self.cut_raw = json.dumps(cut).encode()
        self.identity.update(
            size_bytes=len(self.raw),
            sha256_before=cut["patch_sha256"],
            sha256_after=cut["patch_sha256"],
        )
        self.positions = dict.fromkeys(
            range(132218), ((1000000.0, 1000000.0, 0.0),) * 3
        )
        for i in range(first, last + 1):
            self.sections[i][0] = (i * 0.125, 0.75, 10.08)
        for i in range(first, last):
            a, b = (i * 12.5, 25.0, 1000.0), ((i + 1) * 12.5, 25.0, 1000.0)
            p, q = (a[0], 75.0, 1000.0), (b[0], 75.0, 1000.0)
            self.positions[i * 52], self.positions[i * 52 + 1] = (a, p, b), (p, q, b)
            ga, gb = (*a[:2], 900.0), (*b[:2], 900.0)
            tid = 124800 + (i - first) * 2
            self.positions[tid], self.positions[tid + 1] = (a, b, gb), (a, gb, ga)
        with (
            patch.object(contract, "HAIRPIN_WALL_ROWS", (first, last)),
            patch.object(
                contract, "HAIRPIN_CUT_SHA256", hashlib.sha256(self.cut_raw).hexdigest()
            ),
            patch.object(contract, "HAIRPIN_CUT_SIZE", len(self.cut_raw)),
        ):
            value = self.build()
            self.verify(value)
            self.assertEqual(len(value["wall_triangles"]), 640)
            self.assertEqual(len(value["native_top_triangles"]), 640)
            self.assertEqual(len(value["pavement_edge_rows_cm"]), 321)
            self.assertLess(
                len(json.dumps(value, indent=4).encode()), contract.WALL_EVIDENCE_LIMIT
            )


if __name__ == "__main__":
    unittest.main()
