"""Synthetic readiness/lifecycle regressions; not native visual acceptance."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts.ue import road_asphalt_gpu_review as gpu


class RoadCaptureReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = {
            key: "/Game/Derived/T_" + key + ".T_" + key
            for key in ("BaseColor", "Normal_DX", "ORM", "DetailMasks")
        }
        self.gravel_paths = {
            key: "/Game/Derived/Shoulder/T_" + key + ".T_" + key
            for key in ("BaseColor", "Normal_DX", "Roughness")
        }
        self.textures = {
            path: SimpleNamespace(
                get_path_name=Mock(return_value=path),
                set_force_mip_levels_to_be_resident=Mock(),
            )
            for path in (*self.paths.values(), *self.gravel_paths.values())
        }
        self.height = SimpleNamespace(
            get_path_name=Mock(return_value="/Game/Derived/L_Map.Height"),
            set_force_mip_levels_to_be_resident=Mock(),
        )
        self.events = []
        self.api = SimpleNamespace(
            load_asset=Mock(side_effect=self.textures.get),
            YacsTextureAuditLibrary=SimpleNamespace(
                describe_texture=Mock(return_value=json.dumps({
                    "is_default_texture": False,
                    "is_compiling": False,
                    "mips": 12,
                    "resident_mips": 12,
                }))
            ),
        )
        self.row = {
            "frame_id": "window-0112-forward-00001",
            "camera_location_cm": [1.0, 2.0, 3.0],
            "target_cm": [20.0, 2.0, 3.0],
            "fov_deg": 76.0,
        }
        context = {
            "proof": self.root,
            "manifest": {
                "texture_objects": self.paths,
                "outer_terrain_enabled": False,
                "shoulder_network": {"schema_version": 3, "material": {"texture_objects": self.gravel_paths}},
            },
            "frames": [self.row],
        }
        self.safe = self.enterContext(patch.object(
            gpu.session, "_safe_path", side_effect=lambda root, name: root / name
        ))
        self.identity = self.enterContext(patch.object(
            gpu.session, "_identity", side_effect=self.file_identity
        ))
        self.writer = self.enterContext(patch.object(
            gpu.saved, "write_once", side_effect=self.write_json
        ))
        self.height_objects = self.enterContext(patch.object(
            gpu, "_height_texture_objects", return_value=[self.height]
        ))
        self.prepare = self.enterContext(patch.object(
            gpu, "prepare_capture", side_effect=self.prepare_capture
        ))
        self.job = gpu.RoadLitCapture(self.api, context, object(), object())

    def file_identity(self, path, limit=None):
        raw = Path(path).read_bytes()
        return {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}

    def write_json(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as output:
            json.dump(value, output)
        return self.file_identity(path)

    def prepare_capture(self, api, landscape, eye, rotation, output,
                        *, request_height_mips):
        self.assertIs(api, self.api)
        self.assertTrue(request_height_mips)
        self.events.append("ready")
        value = {
            "status": "NATIVE_LOADING_AND_MIPS_READY",
            "height_mip_lease_requested": True,
            "viewport_primed_at_rider_camera": True,
            "native_loading_barrier_completed": True,
        }
        self.write_json(output / "capture-readiness.json", value)
        return value

    def configure_camera(self):
        self.api.SystemLibrary = SimpleNamespace(
            get_engine_version=lambda: gpu.visual_controls.ENGINE_VERSION,
            get_console_variable_string_value=Mock(return_value="0"),
            get_frame_count=Mock(return_value=100),
        )
        self.api.Vector = lambda x, y, z: SimpleNamespace(x=x, y=y, z=z)
        self.api.CameraComponent = object()
        self.api.MathLibrary = SimpleNamespace(find_look_at_rotation=Mock())
        self.api.ViewModeIndex = SimpleNamespace(VMI_LIT=object())
        self.api.ComparisonTolerance = SimpleNamespace(LOW=object())
        self.api.AutomationLibrary = SimpleNamespace(
            set_editor_viewport_view_mode=Mock(),
            get_editor_active_viewport_view_mode=Mock(return_value=self.api.ViewModeIndex.VMI_LIT),
            finish_loading_before_screenshot=Mock(),
            take_high_res_screenshot=Mock(side_effect=self.screenshot),
        )
        component = SimpleNamespace(
            set_editor_property=Mock(), get_editor_property=Mock(return_value=76.0)
        )
        self.job.camera = SimpleNamespace(
            set_actor_location=Mock(), set_actor_rotation=Mock(return_value=True),
            get_component_by_class=Mock(return_value=component),
            get_actor_location=Mock(return_value=self.api.Vector(1, 2, 3)),
            get_actor_forward_vector=Mock(return_value=self.api.Vector(1, 0, 0)),
        )
        self.job.stop = Mock()
        self.enterContext(patch.object(gpu, "decode_png", return_value=(1, 1, 3, b"rgb")))
        self.enterContext(patch.object(gpu, "frame_statistics", return_value={
            "width": 1280, "height": 720,
        }))

    def screenshot(self, **arguments):
        self.events.append("shot")
        Path(arguments["filename"]).write_bytes(b"SYNTHETIC PNG")
        return SimpleNamespace(is_valid_task=lambda: True, is_task_done=lambda: True)

    def configure_outer_terrain(self):
        from scripts.ue.test_road_asphalt_gpu_review import outer_terrain_fixture, outer_gpu_statistics_fixture

        manifest = outer_terrain_fixture()[3]
        manifest["shoulder_network"]["material"]["texture_objects"] = self.gravel_paths
        self.job.context["manifest"].update(manifest)
        self.job.context["outer_terrain_enabled"] = True
        for path in gpu.saved.outer_terrain_texture_paths(manifest):
            self.textures[path] = SimpleNamespace(get_path_name=Mock(return_value=path),
                set_force_mip_levels_to_be_resident=Mock())
        stats = outer_gpu_statistics_fixture(manifest)
        instance = SimpleNamespace(get_path_name=lambda: stats["instance"])
        self.api.load_asset.side_effect = lambda path: instance if path == stats["instance"] else self.textures.get(path)

        def observe(api, material):
            self.assertIs(api, self.api)
            self.assertIs(material, instance)
            self.assertEqual(self.job.pose_readiness["status"], "NATIVE_LOADING_AND_MIPS_READY")
            self.events.append("outer GPU statistics")
            return stats

        return self.enterContext(patch.object(gpu.saved.shoulder_material, "verify_gpu_material_statistics", side_effect=observe))

    def configure_cracks(self):
        from scripts.ue import road_crack_sources as source

        values = {"pins_sha256": "a" * 64, "selected_motifs": list(source.CANARY_MOTIFS)}
        assets = source.asset_paths(values)
        self.job.context["manifest"].update(crack_canary_enabled=True, crack_canary={
            "imports": {"sources": values, "assets": assets, "texture_count": 8}})
        for channels in assets["textures"].values():
            for path in channels.values():
                self.textures[path] = SimpleNamespace(get_path_name=Mock(return_value=path),
                    set_force_mip_levels_to_be_resident=Mock())

    def test_original_height_capture_helper_runs_before_first_screenshot(self):
        self.configure_camera()
        self.job.submit_pose()
        self.assertEqual(self.events, ["ready", "shot"])
        self.prepare.assert_called_once()
        self.assertEqual(self.job.pose_readiness["material_texture_count"], 7)
        self.assertEqual(len(self.job.residency_leases), 8)
        for texture in self.textures.values():
            texture.set_force_mip_levels_to_be_resident.assert_called_with(
                gpu.HEIGHT_MIP_LEASE_SECONDS, 0
            )

    def test_three_unique_warmups_precede_each_final_evidence_frame(self):
        self.configure_camera()
        self.job.submit_pose()
        for completed in range(3):
            self.job.tick(0.05)
            self.assertEqual(self.job.frames, [])
            self.assertEqual(self.job.completed_priming_frames, completed + 1)
        self.job.tick(0.05)
        self.assertEqual(len(self.job.frames), 1)
        self.assertEqual(len(self.job.frames[0]["priming_frames"]), 3)
        self.assertEqual(self.job.frames[0]["capture_readiness"]["status"],
                         "NATIVE_LOADING_AND_MIPS_READY")
        self.assertEqual(len(list((self.job.root / "priming").glob("*.png"))), 3)
        self.assertEqual(len(list((self.job.root / "frames").glob("*.png"))), 1)
        self.prepare.assert_called_once()
        self.job.stop.assert_not_called()
        self.assertIsNotNone(self.job.finish_requested_at)

    def test_crack_canary_requests_and_releases_all_eight_additional_maps(self):
        self.configure_cracks()
        self.job.prepare_pose(self.row, object(), object())
        self.assertEqual(self.job.pose_readiness["material_texture_count"], 15)
        self.assertEqual(len(self.job.residency_leases), 16)
        self.assertEqual(self.job.release_residency(), [])
        for texture in self.textures.values():
            self.assertEqual(texture.set_force_mip_levels_to_be_resident.call_args_list,
                             [unittest.mock.call(gpu.HEIGHT_MIP_LEASE_SECONDS, 0), unittest.mock.call(0.0, 0)])

    def test_outer_eighteen_textures_drain_before_stats_and_first_png(self):
        observer = self.configure_outer_terrain()
        self.configure_camera()
        self.job.submit_pose()
        self.assertEqual(self.events, ["ready", "outer GPU statistics", "shot"])
        self.assertEqual(self.job.pose_readiness["material_texture_count"], 18)
        self.assertEqual(len(self.job.residency_leases), 19)
        observer.assert_called_once()
        self.assertEqual(self.job.release_residency(), [])
        for texture in self.textures.values():
            texture.set_force_mip_levels_to_be_resident.assert_called_with(0.0, 0)

    def test_outer_with_cracks_tracks_all_twenty_six_maps_and_does_not_repeat_stats_each_pose(self):
        observer = self.configure_outer_terrain()
        self.configure_cracks()
        self.job.prepare_pose(self.row, object(), object())
        self.assertEqual(self.job.pose_readiness["material_texture_count"], 26)
        self.assertEqual(len(self.job.residency_leases), 27)
        self.job.phase = "controls"
        self.job.prepare_pose({**self.row, "frame_id": "synthetic-control"}, object(), object())
        observer.assert_called_once()
        self.assertEqual(self.job.pose_readiness["material_texture_count"], 26)
        self.assertEqual(self.job.release_residency(), [])
        for texture in self.textures.values():
            texture.set_force_mip_levels_to_be_resident.assert_called_with(0.0, 0)

    def test_outer_missing_terrain_texture_or_missing_gpu_statistics_stops_before_png(self):
        observer = self.configure_outer_terrain()
        self.configure_camera()
        observer.side_effect = ValueError("synthetic missing compiled GPU statistics")
        with self.assertRaisesRegex(ValueError, "compiled GPU"):
            self.job.submit_pose()
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()
        self.assertIsNone(self.job.outer_gpu_statistics_before)
        self.assertEqual(self.job.release_residency(), [])
        path = gpu.saved.outer_terrain_texture_paths(self.job.context["manifest"])[-1]
        del self.textures[path]
        with self.assertRaisesRegex(ValueError, "Pinned road texture missing"):
            self.job.prepare_pose({**self.row, "frame_id": "missing-outer"}, object(), object())
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()

    def test_crack_maps_cannot_hide_in_disabled_lane_or_replace_a_native_source_map(self):
        from scripts.ue import road_crack_sources as source

        with self.assertRaisesRegex(ValueError, "Disabled crack lane"):
            gpu.crack_texture_paths({"crack_canary_enabled": False, "crack_canary": {}})
        values = {"pins_sha256": "a" * 64, "selected_motifs": list(source.CANARY_MOTIFS)}
        assets = source.asset_paths(values)
        assets["textures"][source.CANARY_MOTIFS[0]]["ORM"] = self.paths["ORM"]
        with self.assertRaisesRegex(ValueError, "exact saved source selection"):
            gpu.crack_texture_paths({"crack_canary_enabled": True, "crack_canary": {
                "imports": {"sources": values, "assets": assets, "texture_count": 8}}})

    def test_control_pose_reuses_height_and_texture_readiness_in_separate_directory(self):
        self.job.phase = "controls"
        row = {**self.row, "frame_id": self.row["frame_id"] + "--current-worldnormal"}
        self.job.prepare_pose(row, object(), object())
        output = self.job.control_root / "readiness" / row["frame_id"]
        self.assertTrue((output / "capture-readiness.json").is_file())
        self.assertTrue((output / "road-texture-readiness.json").is_file())
        self.assertFalse((self.job.root / "readiness").exists())
        self.assertEqual(self.job.pose_readiness["material_texture_count"], 7)
        self.assertEqual(len(self.job.residency_leases), 8)
        self.prepare.assert_called_once()

    def test_low_material_mip_or_pending_compile_cannot_be_visual_evidence(self):
        for bad in (
            {"resident_mips": 1}, {"is_compiling": True},
            {"is_default_texture": True}, {"mips": 0},
        ):
            with self.subTest(bad=bad):
                metadata = {
                    "is_default_texture": False, "is_compiling": False,
                    "mips": 12, "resident_mips": 12, **bad,
                }
                self.api.YacsTextureAuditLibrary.describe_texture.return_value = json.dumps(metadata)
                self.prepare.side_effect = None
                self.prepare.return_value = {
                    "status": "NATIVE_LOADING_AND_MIPS_READY",
                    "height_mip_lease_requested": True,
                    "viewport_primed_at_rider_camera": True,
                    "native_loading_barrier_completed": True,
                }
                with self.assertRaisesRegex(ValueError, "not fully resident"):
                    self.job.prepare_pose(self.row, object(), object())
                self.assertIsNone(self.job.pose_readiness)

    def test_readiness_failure_never_submits_screenshot(self):
        self.configure_camera()
        self.prepare.side_effect = RuntimeError("height mip timeout")
        with self.assertRaisesRegex(RuntimeError, "height mip timeout"):
            self.job.submit_pose()
        self.api.AutomationLibrary.take_high_res_screenshot.assert_not_called()
        self.assertEqual(self.job.release_residency(), [])
        self.assertTrue(self.job.residency_released)
        self.height.set_force_mip_levels_to_be_resident.assert_called_with(0.0, 0)

    def test_cleanup_attempts_every_lease_even_if_one_release_fails(self):
        self.job.prepare_pose(self.row, object(), object())
        first = next(iter(self.textures.values()))
        first.set_force_mip_levels_to_be_resident.side_effect = RuntimeError("release failed")
        errors = self.job.release_residency()
        self.assertEqual(len(errors), 1)
        self.assertIn("release failed", errors[0])
        self.assertFalse(self.job.residency_released)
        for texture in (*self.textures.values(), self.height):
            texture.set_force_mip_levels_to_be_resident.assert_called_with(0.0, 0)

    def test_missing_texture_does_not_get_a_fabricated_readiness_receipt(self):
        self.api.load_asset.return_value = None
        self.api.load_asset.side_effect = None
        with self.assertRaisesRegex(ValueError, "texture missing"):
            self.job.prepare_pose(self.row, object(), object())
        self.prepare.assert_not_called()
        self.writer.assert_not_called()

    def test_missing_shoulder_texture_stops_before_capture_barrier(self):
        del self.textures[self.gravel_paths["Normal_DX"]]
        with self.assertRaisesRegex(ValueError, "texture missing"):
            self.job.prepare_pose(self.row, object(), object())
        self.prepare.assert_not_called()
        self.writer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
