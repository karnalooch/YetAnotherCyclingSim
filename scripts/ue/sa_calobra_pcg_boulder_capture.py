"""Two real GPU views in an owned diagnostic world; never saves a map or quits UE."""

import hashlib
import json
import math
from pathlib import Path
import struct
import time
import traceback

import unreal


_ACTIVE = []
RESOLUTION = (1920, 1080)


def _xyz(value):
    return [float(getattr(value, axis)) for axis in ("x", "y", "z")]


class BoulderCapture:
    def __init__(
        self, world, target_center, output_dir, on_complete, framing_radius_cm
    ):
        self.world, self.done = world, on_complete
        self.center = _xyz(target_center)
        self.radius = float(framing_radius_cm)
        if (
            not all(math.isfinite(v) for v in self.center + [self.radius])
            or self.radius <= 0
        ):
            raise ValueError(
                "Finite target center and positive measured framing radius required"
            )
        project = Path(unreal.Paths.project_dir()).resolve()
        self.root = Path(output_dir).resolve()
        if not self.root.is_relative_to(project) or self.root == project:
            raise ValueError(
                "Capture output must be inside the owned diagnostic project"
            )
        if self.root.exists():
            raise ValueError("Capture output must be new")
        self.root.mkdir(parents=True)
        self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.owned, self.task, self.handle = [], None, None
        self.index, self.stopped = 0, False
        self.started = time.monotonic()
        self.report = {
            "schema_version": 1,
            "status": "RUNNING",
            "scope": "LOCAL_DIAGNOSTIC_ONLY",
            "target_center_cm": self.center,
            "framing_radius_cm": self.radius,
            "resolution_px": list(RESOLUTION),
            "frames": [],
            "lighting": [],
            "saved_map": False,
            "visual_acceptance": "PENDING_OWNER",
            "performance_acceptance": "NOT_MEASURED",
            "error": None,
        }

    def _write(self):
        path = self.root / "boulder-capture-receipt.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        temporary.replace(path)

    def _spawn(self, cls, location, rotation):
        actor = self.actors.spawn_actor_from_class(
            cls, location, rotation, transient=True
        )
        if actor is None:
            raise RuntimeError("Transient capture actor creation failed: " + str(cls))
        self.owned.append(actor)
        return actor

    def start(self):
        try:
            for cls, component_cls, intensity in (
                (unreal.DirectionalLight, unreal.DirectionalLightComponent, 6.0),
                (unreal.SkyLight, unreal.SkyLightComponent, 1.15),
            ):
                lights = list(
                    unreal.GameplayStatics.get_all_actors_of_class(self.world, cls)
                )
                created = not lights
                if created:
                    light = self._spawn(
                        cls,
                        unreal.Vector(*self.center),
                        unreal.Rotator(pitch=-36.0, yaw=-52.0, roll=0.0),
                    )
                    component = light.get_component_by_class(component_cls)
                    component.set_intensity(intensity)
                    if cls == unreal.SkyLight:
                        component.set_editor_property(
                            "lower_hemisphere_is_black", False
                        )
                        component.recapture_sky()
                    lights = [light]
                for light in lights:
                    component = light.get_component_by_class(component_cls)
                    rotation = light.get_actor_rotation()
                    self.report["lighting"].append(
                        {
                            "actor": light.get_path_name(),
                            "class": light.get_class().get_name(),
                            "created_transient": created,
                            "intensity": float(
                                component.get_editor_property("intensity")
                            ),
                            "rotation_deg": [
                                float(getattr(rotation, a))
                                for a in ("pitch", "yaw", "roll")
                            ],
                        }
                    )
            prefix = self.world.get_path_name().split(".", 1)[0] + "."
            leased = []
            for texture in unreal.ObjectIterator(unreal.Texture2D):
                if (
                    texture.get_path_name().startswith(prefix)
                    and texture.get_editor_property("lod_group")
                    == unreal.TextureGroup.TEXTUREGROUP_TERRAIN_HEIGHTMAP
                ):
                    texture.set_force_mip_levels_to_be_resident(120.0, 0)
                    leased.append(texture.get_path_name())
            if not leased:
                raise RuntimeError("No map-owned Landscape height textures to prime")
            self.report["height_mip_lease"] = {
                "seconds": 120.0,
                "textures": sorted(leased),
                "resident_mip_telemetry": "UNAVAILABLE_CONTENT_ONLY",
            }
            self.camera = self._spawn(
                unreal.CameraActor, unreal.Vector(*self.center), unreal.Rotator()
            )
            self.camera.get_component_by_class(
                unreal.CameraComponent
            ).set_editor_property("field_of_view", 50.0)
            unreal.AutomationLibrary.set_editor_viewport_view_mode(
                unreal.ViewModeIndex.VMI_LIT
            )
            self.handle = unreal.register_slate_post_tick_callback(self.tick)
            self._submit()
        except Exception:
            self.stop(traceback.format_exc())
        return self

    def _submit(self):
        offsets = ((-3.5, -4.0, 0.7), (4.0, -3.0, 0.55))
        eye = unreal.Vector(
            *(c + self.radius * o for c, o in zip(self.center, offsets[self.index]))
        )
        from scripts.ue.sa_calobra_pcg_terrain_contact import unpack

        all_actors = self.actors.get_all_level_actors()
        grounds = [a for a in all_actors if isinstance(a, unreal.LandscapeProxy)]
        if len(grounds) != 1:
            raise RuntimeError("Ambiguous capture ground")
        hit = unreal.SystemLibrary.line_trace_single(
            self.world,
            unreal.Vector(eye.x, eye.y, 150000),
            unreal.Vector(eye.x, eye.y, -150000),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [a for a in all_actors if a != grounds[0]],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        ground = unpack(hit, grounds[0])
        if ground is None:
            raise RuntimeError("Camera ground measurement missed")
        # A fixed 0.6 m near-ground diagnostic camera, identical before/after.
        # This prevents subterranean captures without altering asset/terrain.
        eye.z = ground["position_cm"][2] + 60.0
        rotation = unreal.MathLibrary.find_look_at_rotation(
            eye, unreal.Vector(*self.center)
        )
        self.camera.set_actor_location(eye, False, False)
        self.camera.set_actor_rotation(rotation, False)
        actual = _xyz(self.camera.get_actor_location())
        if any(abs(a - b) > 0.0001 for a, b in zip(actual, _xyz(eye))):
            raise RuntimeError("Capture camera position readback differs")
        actual_rotation = self.camera.get_actor_rotation()
        actual_fov = float(
            self.camera.get_component_by_class(
                unreal.CameraComponent
            ).get_editor_property("field_of_view")
        )
        if abs(actual_fov - 50.0) > 0.0001:
            raise RuntimeError("Capture camera FOV readback differs")
        if any(
            abs(
                (float(getattr(actual_rotation, a)) - float(getattr(rotation, a)) + 180)
                % 360
                - 180
            )
            > 0.01
            for a in ("pitch", "yaw", "roll")
        ):
            raise RuntimeError("Capture camera rotation readback differs")
        self.pending = {
            "file": "boulder-low-angle-%02d.png" % (self.index + 1),
            "camera_location_cm": actual,
            "camera_ground": ground,
            "camera_ground_clearance_cm": 60.0,
            "camera_fov_deg": actual_fov,
            "camera_rotation_deg": [
                float(getattr(actual_rotation, a)) for a in ("pitch", "yaw", "roll")
            ],
        }
        viewport = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        viewport.set_level_viewport_camera_info(eye, rotation)
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        self.pending["viewport_primed"] = True
        self.task = unreal.AutomationLibrary.take_high_res_screenshot(
            res_x=RESOLUTION[0],
            res_y=RESOLUTION[1],
            filename=str(self.root / self.pending["file"]),
            camera=self.camera,
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=unreal.ComparisonTolerance.LOW,
            comparison_notes="YACS #365 Boulder contact diagnostic; owner visual review pending",
            delay=1.0,
            force_game_view=True,
        )
        if not self.task or not self.task.is_valid_task():
            raise RuntimeError("Invalid native screenshot task")
        self.submitted = time.monotonic()
        self._write()

    def tick(self, _delta):
        if self.stopped or self.task is None:
            return
        try:
            if time.monotonic() - self.submitted > 120:
                raise RuntimeError("Native screenshot task timed out (120 seconds)")
            if not self.task.is_task_done():
                return
            self.task = (
                None  # Native loading can re-enter Slate during the next submit.
            )
            data = (self.root / self.pending["file"]).read_bytes()
            if (
                len(data) < 45
                or data[:8] != b"\x89PNG\r\n\x1a\n"
                or data[12:16] != b"IHDR"
            ):
                raise RuntimeError("Native screenshot is not a PNG with IHDR")
            width, height = struct.unpack(">II", data[16:24])
            if (width, height) != RESOLUTION:
                raise RuntimeError("Native screenshot dimensions differ")
            self.report["frames"].append(
                dict(
                    self.pending,
                    width_px=width,
                    height_px=height,
                    size_bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )
            self.index += 1
            if self.index == 2:
                self.stop()
            else:
                self._submit()
        except Exception:
            self.stop(traceback.format_exc())

    def stop(self, error=None):
        if self.stopped:
            return
        self.stopped = True
        cleanup_errors = []
        if self.handle is not None:
            try:
                unreal.unregister_slate_post_tick_callback(self.handle)
            except Exception:
                cleanup_errors.append(traceback.format_exc())
            self.handle = None
        for actor in reversed(self.owned):
            try:
                if not self.actors.destroy_actor(actor):
                    raise RuntimeError("Capture actor cleanup failed")
            except Exception:
                cleanup_errors.append(traceback.format_exc())
        self.report.update(
            status="FAILED" if error or cleanup_errors else "CAPTURE_COMPLETED",
            error=error or ("Capture cleanup failed" if cleanup_errors else None),
            cleanup_errors=cleanup_errors,
            wall_seconds=time.monotonic() - self.started,
        )
        self._write()
        if self in _ACTIVE:
            _ACTIVE.remove(self)
        self.done(self.report)


def start_capture(world, target_center, output_dir, on_complete, *, framing_radius_cm):
    """Return live capture state; callback receives receipt after two PNGs or failure.

    Caller supplies the actual placed mesh bounds radius in cm and keeps UE ticking.
    Caller must use a real rendering RHI and owns exit, visual review and proof admission.
    """
    capture = BoulderCapture(
        world, target_center, output_dir, on_complete, framing_radius_cm
    )
    _ACTIVE.append(capture)
    return capture.start()
