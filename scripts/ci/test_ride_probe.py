"""Bounded scouting/focus contracts; no dependency on Unreal or external codecs."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import zlib

from scripts.proof.ride_probe import (
    ProbeConfig,
    sample_plan,
    terrain_event,
    select_focus,
    frame_plan,
    performance_hotspots,
)
from scripts.proof.package_ride_probe import validate
from scripts.ue.ride_probe_capture import (
    CaptureLoop,
    config_from_env,
    sample_native_camera,
)

SHA = "a" * 40
ROOT = Path(__file__).resolve().parents[2]


def samples(config):
    result = sample_plan(config, 15000, 16000)
    for row in result:
        x = row["station_m"] * 100
        row.update(
            road_position_cm=[x, 0, 0],
            camera_location_cm=[x, 0, 160],
            target_cm=[x + 100, 0, 160],
            road_forward_unit=[1, 0, 0],
            road_z_m=0.0,
        )
    return result


def png(path, width, height):
    def chunk(name, data):
        return (
            struct.pack(">I", len(data))
            + name
            + data
            + struct.pack(">I", zlib.crc32(name + data))
        )

    raw = (b"\0" + b"\x64" * (width * 3)) * height
    Path(path).write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.config = ProbeConfig(SHA)
        self.samples = samples(self.config)

    def test_light_frame_and_query_budget(self):
        self.assertEqual(len(self.samples), 161)
        plan = frame_plan(self.config, self.samples)
        self.assertEqual(len(plan), 25)
        self.assertEqual({r["size"][0] for r in plan}, {960})
        self.assertEqual(plan[-1]["time_s"] - plan[0]["time_s"], 12)

    def test_focus_is_two_seconds_on_both_sides(self):
        config = ProbeConfig(SHA, "focus")
        plan = frame_plan(config, samples(config))
        self.assertEqual(len(plan), 41)
        self.assertEqual(
            (plan[0]["station_m"], plan[20]["station_m"], plan[-1]["station_m"]),
            (15395, 15415, 15435),
        )
        self.assertEqual({r["fps"] for r in plan}, {10})

    def test_full_context_is_reserved_at_scout_edges(self):
        for tick in (0, 120):
            focus = {"tick": tick, "severity": 2}
            plan = frame_plan(self.config, self.samples, focus)[25:]
            self.assertEqual(plan[-1]["time_s"] - plan[0]["time_s"], 4)
            self.assertEqual(plan[0]["tick"], tick - 20)
            self.assertEqual(plan[-1]["tick"], tick + 20)

    def test_wide_is_secondary_and_keeps_pose(self):
        config = ProbeConfig(SHA, "focus", wide=True)
        plan = frame_plan(config, samples(config))
        self.assertEqual(len(plan), 82)
        for a, b in zip(plan[:41], plan[41:]):
            self.assertEqual(a["camera_location_cm"], b["camera_location_cm"])
            self.assertEqual(a["target_cm"], b["target_cm"])
            self.assertEqual((a["fov"], b["fov"]), (76, 105))

    def test_combined_budget_is_bounded(self):
        config = ProbeConfig(SHA, wide=True)
        self.assertEqual(len(frame_plan(config, samples(config), {"tick": 60})), 107)

    def test_replay_is_deterministic(self):
        self.assertEqual(
            frame_plan(self.config, self.samples),
            frame_plan(self.config, samples(self.config)),
        )

    def test_invalid_config_fails(self):
        for changes in (
            {"mode": "full"},
            {"exact_sha": "main"},
            {"center_m": True},
            {"center_m": "nan"},
            {"center_m": "inf"},
            {"center_m": -1},
            {"wide": "true"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ProbeConfig(**(dict(exact_sha=SHA) | changes))

    def test_context_does_not_silently_clamp_to_corridor(self):
        with self.assertRaisesRegex(ValueError, "exceeds prepared"):
            sample_plan(self.config, 15400, 15430)

    def test_missing_focus_pose_fails(self):
        with self.assertRaises(ValueError):
            frame_plan(self.config, self.samples[1:], {"tick": 0})

    def test_unknown_ground_does_not_prove_clean(self):
        event = terrain_event(self.samples[80], None)
        self.assertEqual(event["kind"], "unmeasured_ground")
        self.assertIsNone(select_focus([event]))

    def test_collision_signal_is_only_locator(self):
        event = terrain_event(self.samples[80], 3.0)
        self.assertFalse(event["render_defect_confirmed"])
        self.assertEqual(select_focus([event]), event)
        self.assertIsNone(terrain_event(self.samples[80], 0.20))

    def test_ranking_is_stable_and_scoped(self):
        events = [{"tick": t, "severity": 2} for t in [-10, 10, 60, 110, 130]]
        self.assertEqual(select_focus(events)["tick"], 60)
        self.assertEqual(select_focus(events[::-1])["tick"], 60)

    def test_perf_source_requires_matching_sha_and_route(self):
        for context in (
            {"exact_sha": SHA, "route_id": "AlpineJourney"},
            {"exact_sha": "b" * 40, "route_id": "SP638-presentation"},
        ):
            with self.assertRaises(ValueError):
                performance_hotspots([], context, self.config)

    def test_perf_uses_distance_not_sector_clock(self):
        events = performance_hotspots(
            [
                {"frame_ms": 45, "distance_m": 15402, "rel_s": 0.1},
                {"frame_ms": 12, "distance_m": 15403, "rel_s": 0.1},
            ],
            {
                "exact_sha": SHA,
                "route_id": "SP638-presentation",
                "frame_threshold_ms": 33.3,
            },
            self.config,
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["station_m"], 15402)
        self.assertNotIn("time_s", events[0])

    def test_environment_admission_defaults_off(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(config_from_env(15415))
        with patch.dict(
            "os.environ",
            {"YACS_RIDE_PROBE_MODE": "focus", "YACS_RIDE_PROBE_SHA": SHA},
            clear=True,
        ):
            self.assertEqual(config_from_env(15415).center_m, 15415)

    def test_invalid_environment_wide_fails(self):
        with patch.dict(
            "os.environ",
            {"YACS_RIDE_PROBE_MODE": "focus", "YACS_RIDE_PROBE_WIDE": "yes"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                config_from_env(15415)

    def test_native_sampling_does_not_mutate_spline(self):
        api = SimpleNamespace(SplineCoordinateSpace=SimpleNamespace(WORLD="world"))

        class Spline:
            def get_location_at_distance_along_spline(self, s, space):
                return SimpleNamespace(x=s, y=0, z=s * 0.05)

            def get_direction_at_distance_along_spline(self, s, space):
                return SimpleNamespace(x=1, y=0, z=0.05)

        output = sample_native_camera(api, Spline(), self.config, 15000, 16000)
        self.assertEqual(output[80]["camera_location_cm"][0], 1541500)
        self.assertEqual(
            output[80]["camera_location_cm"][2] - output[80]["road_position_cm"][2], 160
        )


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "RideProbe"
        self.now = [0.0]
        self.done = []
        self.removed = []
        self.task = SimpleNamespace(
            is_task_done=lambda: True, is_valid_task=lambda: True
        )
        self.vector = lambda *v: SimpleNamespace(x=v[0], y=v[1], z=v[2])
        self.camera = SimpleNamespace(
            get_component_by_class=lambda cls: SimpleNamespace(
                set_editor_property=lambda *args: None
            )
        )
        self.location = self.vector(0, 0, 160)
        self.rotation = SimpleNamespace(pitch=0.0, yaw=0.0, roll=0.0)

        def set_pose(loc, rot, *args):
            self.location = loc

        self.camera.set_actor_location_and_rotation = set_pose
        self.camera.get_actor_location = lambda: self.location

        def take(**args):
            png(args["filename"], args["res_x"], args["res_y"])
            return self.task

        self.api = SimpleNamespace(
            EditorPythonScripting=SimpleNamespace(
                set_keep_python_script_alive=lambda value: None
            ),
            register_slate_post_tick_callback=lambda cb: "handle",
            unregister_slate_post_tick_callback=self.removed.append,
            Vector=self.vector,
            MathLibrary=SimpleNamespace(
                find_look_at_rotation=lambda *args: self.rotation
            ),
            CameraComponent=object,
            AutomationLibrary=SimpleNamespace(take_high_res_screenshot=take),
            ComparisonTolerance=SimpleNamespace(LOW=0),
            log_error=lambda text: None,
        )
        self.ready = lambda *args, **kw: {
            "status": "NATIVE_LOADING_AND_MIPS_READY",
            "duration_seconds": 0.1,
            "height_mip_lease_requested": True,
        }
        self.config = ProbeConfig(SHA)
        self.proof = {
            "diagnostic_variant": "E",
            "corridor_mesh_sha256": "f" * 64,
            "local_terrain_skin": {},
            "render_centerline": {},
            "surface_visibility": {"macro_landscape": True},
        }

    def loop(self):
        return CaptureLoop(
            self.api,
            self.camera,
            object(),
            self.config,
            samples(self.config),
            [],
            self.proof,
            self.root,
            Path(self.tmp.name) / "anchor.png",
            self.location,
            self.rotation,
            lambda *args: self.done.append(args),
            self.ready,
            clock=lambda: self.now[0],
        )

    def complete(self):
        loop = self.loop()
        loop.start()
        for _ in range(200):
            loop.tick(0.016)
            if loop.finished:
                break
        self.assertEqual(self.done, [(True, "")])
        self.assertEqual(self.removed, ["handle"])
        return loop

    def test_one_session_completes_all_planned_frames(self):
        loop = self.complete()
        self.assertEqual(len(loop.report["frames"]), 25)
        report, groups = validate(self.root, SHA)
        self.assertEqual(report["performance_acceptance"], "NOT_MEASURED")
        self.assertEqual(set(groups), {"scout"})

    def test_stale_directory_refuses_reuse(self):
        self.root.mkdir()
        (self.root / "stale.txt").write_text("old")
        with self.assertRaises(RuntimeError):
            self.loop()

    def test_invalid_native_task_fails(self):
        self.task.is_valid_task = lambda: False
        loop = self.loop()
        loop.start()
        loop.tick(0.016)
        self.assertFalse(self.done[0][0])
        self.assertIn("invalid", self.done[0][1])

    def test_missing_frame_fails_even_if_task_done(self):
        self.api.AutomationLibrary.take_high_res_screenshot = lambda **args: self.task
        loop = self.loop()
        loop.start()
        loop.tick(0.016)
        loop.tick(0.016)
        self.assertFalse(self.done[0][0])

    def test_native_barrier_failure_is_not_swallowed(self):
        def failed(*args, **kw):
            raise RuntimeError("mips not ready")

        self.ready = failed
        loop = self.loop()
        loop.start()
        loop.tick(0.016)
        self.assertEqual(self.done, [(False, "mips not ready")])

    def test_task_timeout_fails_and_unregisters_callback(self):
        self.task.is_task_done = lambda: False
        loop = self.loop()
        loop.start()
        loop.tick(0.016)
        self.now[0] = 31
        loop.tick(0.016)
        self.assertFalse(self.done[0][0])
        self.assertIn("30s", self.done[0][1])
        self.assertEqual(self.removed, ["handle"])

    def test_invalid_camera_move_fails(self):
        self.camera.get_actor_location = lambda: self.vector(123, 123, 123)
        loop = self.loop()
        loop.start()
        loop.tick(0.016)
        self.assertFalse(self.done[0][0])
        self.assertIn("pose", self.done[0][1])

    def test_validation_rejects_missing_tampered_extra_and_wrong_sha(self):
        self.complete()
        with self.assertRaises(ValueError):
            validate(self.root, "b" * 40)
        p = self.root / "scout/frame_0000.png"
        original = p.read_bytes()
        p.write_bytes(original + b"junk")
        with self.assertRaises(ValueError):
            validate(self.root, SHA)
        p.write_bytes(original)
        extra = self.root / "scout/frame_0100.png"
        extra.write_bytes(original)
        with self.assertRaises(ValueError):
            validate(self.root, SHA)
        extra.unlink()
        p.unlink()
        with self.assertRaises((ValueError, FileNotFoundError)):
            validate(self.root, SHA)

    def test_validation_rejects_false_acceptance_and_camera_drift(self):
        loop = self.complete()
        original = copy.deepcopy(loop.report)
        for key, value in [
            ("status", "RUNNING"),
            ("performance_acceptance", "PASS"),
            ("visual_acceptance", "PASS"),
        ]:
            report = copy.deepcopy(original)
            report[key] = value
            (self.root / "ride-probe.json").write_text(json.dumps(report))
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(self.root, SHA)
        report = copy.deepcopy(original)
        report["frames"][0]["camera_location_cm"][2] += 100
        (self.root / "ride-probe.json").write_text(json.dumps(report))
        with self.assertRaises(ValueError):
            validate(self.root, SHA)


class WiringTests(unittest.TestCase):
    def test_script_samples_original_route_before_slice(self):
        text = (ROOT / "scripts/ue/stage3g_capture_sp638_local_corridor.py").read_text()
        self.assertLess(
            text.index("sample_native_camera(unreal"),
            text.index("_replace_with_slice(spline, landscape_slice)"),
        )
        self.assertIn("done=_finish, prepare=prepare_capture", text)

    def test_reduced_probe_cannot_mint_full_terrain_receipt(self):
        text = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text()
        self.assertIn(
            "success() && (inputs.ride_probe_mode == 'off' || inputs.ride_probe_mode == '')",
            text,
        )
        self.assertIn(
            "name: ride-probe-${{ github.run_id }}-${{ github.run_attempt }}", text
        )
        self.assertIn('else "m3-ride-diagnostic"', text)
        self.assertIn("$variants = @('A','B','C','D','E')", text)
        self.assertIn("-Variant C3", text)

    def test_request_values_are_environment_not_shell_interpolation(self):
        text = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text()
        self.assertIn(
            "YACS_RIDE_PROBE_CENTER_M: ${{ inputs.ride_probe_station_m }}", text
        )
        self.assertNotIn("-RideProbeCenterM '${{", text)
        self.assertIn("config_from_env(15415.0)", text)

    def test_compile_cache_and_world_guard_remain(self):
        text = (ROOT / ".github/workflows/passo-giau-embark-terrain.yml").read_text()
        self.assertIn("PCGEx compile cache HIT: kind=none", text)
        self.assertIn("group: yacs-pcgex-author-workspace-", text)
        text = (
            ROOT / "scripts/ue/Invoke-YacsSp638LocalCorridorVisualProof.ps1"
        ).read_text()
        self.assertIn("$env:YACS_RIDE_PROBE_SHA = $ExpectedHead", text)
        self.assertIn("render resource gate", text.lower())
        self.assertIn("mutated tracked files", text)

    def test_new_modules_are_render_not_compile_inputs(self):
        from scripts.ci.classify_changes import (
            EMBARK_TERRAIN_RENDER_EXACT,
            EMBARK_TERRAIN_RENDER_PREFIXES,
        )

        self.assertIn("scripts/proof/", EMBARK_TERRAIN_RENDER_PREFIXES)
        self.assertIn("scripts/ue/ride_probe_capture.py", EMBARK_TERRAIN_RENDER_EXACT)


if __name__ == "__main__":
    unittest.main()
