"""Sequential, bounded editor capture on the existing prepared terrain scene.

No new scene builder, physics driver, process-per-frame, or runtime FPS claim.
The original native spline is sampled before the diagnostic consumer slices it.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import time
import traceback

from scripts.proof.ride_probe import (
    ProbeConfig,
    frame_plan,
    sample_plan,
    select_focus,
    terrain_event,
)
from scripts.ue.road_capture_camera import rider_capture_frame

_ACTIVE = None


def config_from_env(anchor_m):
    mode = os.environ.get("YACS_RIDE_PROBE_MODE", "off")
    if mode == "off":
        return None
    wide = os.environ.get("YACS_RIDE_PROBE_WIDE", "false")
    if wide not in {"true", "false"}:
        raise ValueError("YACS_RIDE_PROBE_WIDE must be true or false")
    return ProbeConfig(
        exact_sha=os.environ.get("YACS_RIDE_PROBE_SHA", ""),
        mode=mode,
        center_m=os.environ.get("YACS_RIDE_PROBE_CENTER_M", "").strip() or anchor_m,
        wide=wide == "true",
    )


def sample_native_camera(api, spline, config, slice_start_m, slice_end_m):
    rows = sample_plan(config, slice_start_m, slice_end_m)
    for row in rows:
        distance = row["station_m"] * 100.0
        location = spline.get_location_at_distance_along_spline(
            distance, api.SplineCoordinateSpace.WORLD
        )
        direction = spline.get_direction_at_distance_along_spline(
            distance, api.SplineCoordinateSpace.WORLD
        )
        xyz = (float(location.x), float(location.y), float(location.z))
        forward = (float(direction.x), float(direction.y), float(direction.z))
        frame = rider_capture_frame(
            xyz, forward, tuple(xyz[i] + 100 * forward[i] for i in range(3)), 160.0
        )
        row.update(frame)
        row["road_z_m"] = xyz[2] / 100.0
    return rows


def scan_ground(api, world, road_actor, rows, height_reader):
    """Run before transient meshes spawn: query Landscape collision only.

    The visual heightfield can differ from collision. Each finding is explicitly
    a locator for image review, never evidence of a confirmed render defect.
    """
    events = []
    for row in rows:
        x, y, z = row["road_position_cm"]
        hit = api.SystemLibrary.line_trace_single(
            world,
            api.Vector(x, y, z + 250000.0),
            api.Vector(x, y, z - 250000.0),
            api.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [road_actor],
            api.DrawDebugTrace.NONE,
            True,
        )
        height = None
        if hit is not None:
            try:
                height = (
                    height_reader(
                        hit,
                        expected_x_cm=x,
                        expected_y_cm=y,
                        trace_bottom_z_cm=z - 250000.0,
                        trace_top_z_cm=z + 250000.0,
                    )
                    / 100.0
                )
            except RuntimeError as exc:
                row["query_error"] = str(exc)
        row["landscape_collision_height_m"] = height
        event = terrain_event(row, height)
        if event is not None:
            events.append(event)
    return events


def png_info(path):
    data = Path(path).read_bytes()
    if len(data) < 45 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError(f"invalid PNG: {path}")
    width, height = struct.unpack(">II", data[16:24])
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": [width, height],
        "bytes": len(data),
    }


class CaptureLoop:
    """Advance only after native task completion; fail on missing/stale frames."""

    def __init__(
        self,
        api,
        camera,
        landscape,
        config,
        samples,
        events,
        proof_data,
        root,
        baseline_png,
        baseline_location,
        baseline_rotation,
        done,
        prepare,
        clock=time.monotonic,
    ):
        self.api, self.camera, self.landscape = api, camera, landscape
        self.config, self.root, self.done = config, Path(root), done
        self.prepare, self.clock = prepare, clock
        self.handle = None
        self.task = None
        self.index = 0
        self.started = clock()
        self.finished = False
        focus = select_focus(events) if config.mode == "light" else None
        plan = frame_plan(config, samples, focus)
        self.report = {
            "schema_version": 1,
            "status": "RUNNING",
            "config": config.to_dict(),
            "exact_sha": config.exact_sha,
            "diagnostic_variant": proof_data["diagnostic_variant"],
            "presentation_only": True,
            "saved_to_map": False,
            "visual_acceptance": "PENDING_HUMAN_REVIEW",
            "performance_acceptance": "NOT_MEASURED",
            "clock": "deterministic_camera_distance_at_10_mps_not_wall_time_or_simulation",
            "frame_timing_is_benchmark": False,
            "scope": "bounded_prepared_corridor_not_full_route",
            "locator": "Landscape_collision_not_render_height; no_claim_of_complete_defect_detection",
            "geometry": {
                key: proof_data[key]
                for key in (
                    "corridor_mesh_sha256",
                    "local_terrain_skin",
                    "render_centerline",
                    "surface_visibility",
                )
            },
            "events": events,
            "focus": focus,
            "samples": samples,
            "frames": [],
            "planned_frames": plan,
            "no_finding_means": "NO_AUTOMATIC_LOCATOR; inspect scout images, not visual PASS",
        }
        if self.root.exists() and any(self.root.iterdir()):
            raise RuntimeError(
                "ride-probe output is not empty; refusing stale evidence reuse"
            )
        self.root.mkdir(parents=True, exist_ok=True)
        self.queue = [
            {
                "file": str(baseline_png),
                "group": "anchor",
                "size": [3840, 2160],
                "location": baseline_location,
                "rotation": baseline_rotation,
                "fov": 76.0,
            }
        ] + plan

    def _write(self):
        (self.root / "ride-probe.json").write_text(
            json.dumps(self.report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )

    def start(self):
        self.api.EditorPythonScripting.set_keep_python_script_alive(True)
        self._write()
        self.handle = self.api.register_slate_post_tick_callback(self.tick)

    def stop(self, success, error=""):
        if self.finished:
            return
        self.finished = True
        if self.handle is not None:
            self.api.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        self.report["status"] = "CAPTURED" if success else "FAILED"
        self.report["error"] = error
        self.report["capture_wall_seconds"] = self.clock() - self.started
        self._write()
        self.done(success, error)

    def tick(self, _delta_time):
        if self.finished:
            return
        try:
            if self.clock() - self.started > 600:
                raise RuntimeError("ride-probe total capture deadline exceeded (600s)")
            if self.task is not None:
                if not self.task.is_task_done():
                    if self.clock() - self.submitted > 30:
                        raise RuntimeError(
                            "ride-probe screenshot task deadline exceeded (30s)"
                        )
                    return
                info = png_info(self.path)
                if info["size"] != self.row["size"]:
                    raise RuntimeError(
                        "ride-probe screenshot dimensions do not match the request"
                    )
                if self.row["group"] != "anchor":
                    self.report["frames"].append(
                        {
                            **self.row,
                            **info,
                            "readiness": self.readiness,
                            "capture_wall_s": self.clock() - self.submitted,
                            "frame_timing_is_benchmark": False,
                        }
                    )
                self.index += 1
                self.task = None
                self._write()
                if self.index == len(self.queue):
                    self.stop(True)
                    return
                # Schedule the next camera pose on a fresh editor tick.
                return
            self.row = self.queue[self.index]
            self.path = (
                Path(self.row["file"])
                if self.row["group"] == "anchor"
                else self.root / self.row["file"]
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                raise RuntimeError(f"refusing pre-existing frame: {self.path}")
            if self.row["group"] == "anchor":
                location, rotation = self.row["location"], self.row["rotation"]
            else:
                location = self.api.Vector(*self.row["camera_location_cm"])
                rotation = self.api.MathLibrary.find_look_at_rotation(
                    location, self.api.Vector(*self.row["target_cm"])
                )
            self.camera.set_actor_location_and_rotation(location, rotation, False, True)
            self.camera.get_component_by_class(
                self.api.CameraComponent
            ).set_editor_property("field_of_view", self.row["fov"])
            actual = self.camera.get_actor_location()
            if (
                max(
                    abs(getattr(actual, axis) - getattr(location, axis))
                    for axis in ("x", "y", "z")
                )
                > 0.1
            ):
                raise RuntimeError(
                    "camera did not reach its requested route-local pose"
                )
            ready = self.prepare(
                self.api,
                self.landscape,
                location,
                rotation,
                self.root,
                request_height_mips=bool(
                    self.report["geometry"]["surface_visibility"]["macro_landscape"]
                ),
            )
            self.readiness = {
                "status": ready["status"],
                "duration_seconds": ready["duration_seconds"],
                "full_height_mips_requested": ready["height_mip_lease_requested"],
            }
            if self.row["group"] != "anchor":
                self.row["camera_rotation_deg"] = [
                    float(rotation.pitch),
                    float(rotation.yaw),
                    float(rotation.roll),
                ]
            self.task = self.api.AutomationLibrary.take_high_res_screenshot(
                res_x=self.row["size"][0],
                res_y=self.row["size"][1],
                filename=str(self.path),
                camera=self.camera,
                mask_enabled=False,
                capture_hdr=False,
                comparison_tolerance=self.api.ComparisonTolerance.LOW,
                comparison_notes="YACS bounded ride probe; not performance evidence",
                delay=0.2,
                force_game_view=True,
            )
            if not self.task or not self.task.is_valid_task():
                raise RuntimeError("native ride-probe screenshot task is invalid")
            self.submitted = self.clock()
        except Exception as exc:
            self.api.log_error(traceback.format_exc())
            self.stop(False, str(exc))


def start_capture(**kwargs):
    global _ACTIVE
    _ACTIVE = CaptureLoop(**kwargs)
    _ACTIVE.start()
