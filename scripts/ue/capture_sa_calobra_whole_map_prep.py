"""Whole working-map preparation evidence inside the accepted v8 scene owner.

Sixteen distributed, close, broad and seam views plus matched diagnostics. The
existing owning harness restores the map scene; this consumer restores all
Landscape materials, native v8 attributes, parameters and capture settings.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
import traceback
from pathlib import Path

from scripts.ue.prepare_landscape_capture import prepare_capture
from scripts.ue.sa_calobra_detail_capture import decode_png
from scripts.ue.sa_calobra_detail_capture import load_inputs as load_native_inputs
from scripts.ue.sa_calobra_whole_map_prep import (
    INSTANCE_PATH,
    MASTER_PATH,
    RESOLUTION,
    ROOT,
    SCALARS,
    LandscapeBinding,
    asset_file,
    canonical,
    checked_bytes,
    digest,
    drain_compilation,
    load_inputs,
    memory_checkpoint,
    near_detail_factor,
    package_files,
    rendering_recipe,
    source_assets,
    verify_instance,
    write_json,
)

PRIMES_PER_CAPTURE = 3
TARGETED_VIEWS = (
    "ground-0-0",
    "ground-1-1",
    "window-0023-forward-00000",
    "overview-north",
)


def build_view_plan(ground, pilot_frames, bounds, component_bounds, seam_point):
    """Camera fixtures are review coverage, never world-space demand masks."""
    if len(ground) != 9 or len(pilot_frames) != 2:
        raise ValueError(
            "Whole-map review requires nine distributed and two pinned pilot views"
        )
    views = []
    for index, (target, camera) in enumerate(ground):
        views.append(
            {
                "frame_id": f"ground-{index // 3}-{index % 3}",
                "kind": "distributed_ground",
                "camera": list(camera),
                "target": list(target),
                "fov": 60.0,
                "coverage": "One of nine 3x3 distributed ground targets; not every-pixel acceptance",
            }
        )
    for frame in pilot_frames:
        views.append(
            {
                "frame_id": frame["frame_id"],
                "kind": "pinned_road_close",
                "camera": list(frame["camera"]),
                "target": list(frame["target"]),
                "fov": frame["fov"],
                "coverage": "Exact previously annotated pose; accepted v8 limestone remains unchanged",
            }
        )
    origin, extent = component_bounds["origin_cm"], component_bounds["extent_cm"]
    target = [origin[0], origin[1], origin[2] + 0.35 * extent[2]]
    views.append(
        {
            "frame_id": "dominant-wall",
            "kind": "dominant_face_review",
            "camera": [origin[0] - 18000.0, origin[1] - 15000.0, target[2] + 11000.0],
            "target": target,
            "fov": 60.0,
            "coverage": "Broader Component230 wall and adjacent slopes; no new B-band assignment",
        }
    )
    min_x, max_x, min_y, max_y, min_z, max_z = bounds
    span = max(max_x - min_x, max_y - min_y)
    center = [(min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2]
    for name, sign in (("overview-north", -1), ("overview-south", 1)):
        views.append(
            {
                "frame_id": name,
                "kind": "whole_map_overview",
                "camera": [
                    center[0] + sign * 0.55 * span,
                    center[1] + sign * span,
                    max_z + 0.8 * span,
                ],
                "target": center,
                "fov": 58.0,
                "coverage": "Opposing whole-map overview of the fixed working extent",
            }
        )
    for name, scale in (("seam-close", 1.0), ("seam-distant", 8.0)):
        views.append(
            {
                "frame_id": name,
                "kind": "same_source_boundary_probe",
                "camera": [
                    value + scale * offset
                    for value, offset in zip(seam_point, (1800.0, 1200.0, 1400.0))
                ],
                "target": list(seam_point),
                "fov": 60.0,
                "coverage": "Same exact retained v8 east-boundary vertex at two distances; local seam review pending",
            }
        )
    if len(views) != 16 or len({view["frame_id"] for view in views}) != 16:
        raise ValueError("Whole-map view identity is not unique")
    return views


def build_steps(views):
    lookup = {view["frame_id"]: view for view in views}
    if len(lookup) != 16 or not set(TARGETED_VIEWS) <= set(lookup):
        raise ValueError("Whole-map camera coverage is incomplete")
    steps = [(lookup[name], "baseline") for name in TARGETED_VIEWS]
    steps += [(view, "prepared") for view in views]
    steps += [
        (lookup[name], mode)
        for mode in ("domains", "checker")
        for name in TARGETED_VIEWS
    ]
    steps += [(lookup["ground-1-1"], mode) for mode in ("normal-near", "normal-far")]
    return steps


def mode_parameters(mode):
    if mode not in (
        "baseline",
        "prepared",
        "domains",
        "checker",
        "normal-near",
        "normal-far",
    ):
        raise ValueError("Unknown whole-map material mode")
    result = {
        name: SCALARS[name]
        for name in ("DomainMix", "CheckerMix", "ForceDetailMix", "ForcedDetailFactor")
    }
    if mode in ("domains", "checker"):
        result["DomainMix" if mode == "domains" else "CheckerMix"] = 1.0
    if mode.startswith("normal-"):
        result["ForceDetailMix"] = 1.0
        result["ForcedDetailFactor"] = 1.0 if mode == "normal-near" else 0.0
    return result


def paired_normal_response(near, far):
    """Sample a fixed image grid; this is a shading response, not a cost test."""
    if near[:2] != far[:2]:
        raise ValueError("Near/far material comparison dimensions differ")
    count, changed, total_delta, maximum = 0, 0, 0, 0
    for pixel in range(0, near[0] * near[1], 16):
        a = near[3][pixel * near[2] : pixel * near[2] + 3]
        b = far[3][pixel * far[2] : pixel * far[2] + 3]
        delta = [abs(int(x) - int(y)) for x, y in zip(a, b)]
        count += 1
        changed += max(delta) >= 2
        total_delta += sum(delta)
        maximum = max(maximum, max(delta))
    return {
        "status": "RENDERED_SHADING_RESPONSE"
        if changed >= 8
        else "NO_CLEAR_SHADING_RESPONSE",
        "sample_stride_pixels": 16,
        "sampled_pixels": count,
        "changed_pixels_at_least_2_levels": changed,
        "mean_absolute_rgb_delta_0_255": total_delta / (3 * count),
        "maximum_channel_delta_0_255": maximum,
        "scope": "Same camera with forced micro-normal factor1/0; no geometry/LOD/GPU-cost inference",
    }


class WholeMapCapture:
    def __init__(
        self,
        api,
        world,
        landscape,
        camera,
        component,
        root,
        input_root,
        native_root,
        master_receipt,
        exact_sha,
        source_scene,
        environment,
        done,
        *,
        clock=time.monotonic,
    ):
        self.api, self.world, self.landscape = api, world, landscape
        self.camera, self.component, self.environment = camera, component, environment
        self.root, self.done, self.clock = Path(root), done, clock
        self.inputs = load_inputs(input_root)
        self.native_inputs = load_native_inputs(native_root)
        self.master_receipt = Path(master_receipt)
        self.master_data = json.loads(
            checked_bytes(self.master_receipt, 2 * 1024 * 1024)
        )
        self.exact_sha = exact_sha
        self.task = self.handle = self.pending = None
        self.binding = self.master = self.instance = None
        self.native_started = self.stopped = False
        self.busy = False
        self.index = 0
        self.started = clock()
        self.parameter_originals = {}
        self.report = {
            "schema_version": 1,
            "status": "RUNNING",
            "exact_sha": exact_sha,
            "prep_manifest_sha256": self.inputs["manifest_sha256"],
            "inputs_sha256": self.inputs["hashes"],
            "master_receipt_sha256": digest(self.master_receipt),
            "native_inputs_sha256": self.native_inputs["hashes"],
            "source_scene": source_scene,
            "rendering_recipe": rendering_recipe(),
            "capture_plan": [],
            "captures": [],
            "native_source": None,
            "native_modes": [],
            "native_restore": None,
            "bindings": {"status": "PENDING", "expected_component_count": 1024},
            "cleanup": {"status": "PENDING"},
            "capture_environment": environment.report,
            "native_trial_applied": False,
            "geometry_changed_by_preparation": False,
            "saved_to_map": False,
            "visual_acceptance": "PENDING_OWNER",
            "performance_acceptance": "NOT_MEASURED",
            "shader_cost_reduction_claimed": False,
            "coverage_claim": "Full1024 component binding plus16 sampled views; no every-pixel or whole-map visibility PASS",
            "error": None,
            "priming_captures_per_phase": PRIMES_PER_CAPTURE,
            "memory_checkpoints": [],
        }
        if self.root.exists():
            raise ValueError("Whole-map evidence directory must not already exist")
        for name in ("frames", "priming", "readiness"):
            (self.root / name).mkdir(parents=True)
        self._write()

    def _write(self):
        write_json(self.root / "whole-map-prep-receipt.json", self.report)

    def _native(self, text, status):
        result = json.loads(text)
        if result.get("status") != status:
            raise RuntimeError(
                "Whole-map native v8 guard failed: " + json.dumps(result)
            )
        return result

    def _verify_master(self):
        data = self.master_data
        if (
            data.get("status") != "WHOLE_MAP_FIXED_MASTER_SAVED"
            or data.get("exact_sha") != self.exact_sha
            or data.get("master") != MASTER_PATH
            or data.get("instance") != INSTANCE_PATH
            or data.get("prep_manifest_sha256") != self.inputs["manifest_sha256"]
            or data.get("source_assets") != source_assets()
            or data.get("rendering_recipe") != self.report["rendering_recipe"]
            or data.get("rendering_recipe_sha256")
            != hashlib.sha256(canonical(data["rendering_recipe"])).hexdigest()
        ):
            raise RuntimeError(
                "Fixed whole-map master does not match current source/recipe"
            )
        assets = data.get("generated_assets", [])
        if len(assets) != 3 or {row.get("asset") for row in assets} != {
            MASTER_PATH,
            INSTANCE_PATH,
            MASTER_PATH.rsplit("/", 1)[0] + "/T_WholeMapWeights",
        }:
            raise RuntimeError("Incomplete saved preparation packages")
        for row in assets:
            path = asset_file(row["asset"])
            if (
                path.relative_to(ROOT).as_posix() != row.get("file")
                or digest(path) != row.get("sha256")
                or path.stat().st_size != row.get("size_bytes")
                or package_files(row["asset"]) != row.get("package_files")
            ):
                raise RuntimeError("Saved whole-map preparation package changed")
        self.master, self.instance = (
            self.api.load_asset(MASTER_PATH),
            self.api.load_asset(INSTANCE_PATH),
        )
        if self.master is None or self.instance is None:
            raise RuntimeError(
                "Fresh process cannot load saved preparation master/instance"
            )
        actual = verify_instance(self.api, self.master, self.instance, data)
        self.parameter_originals = {name: actual["scalars"][name] for name in SCALARS}
        self.report["fresh_process_texture_readbacks"] = actual["texture_readbacks"]
        self.report["fresh_process_master_verified"] = True

    def _ground_height(self, x, y):
        # The admitted source permits below-sea-level terrain. Keep both trace
        # endpoints outside the working elevation range and exclude them from
        # hit candidates; a missing hit must never become an invented height.
        trace_bottom, trace_top = -150000, 150000
        hit = self.api.SystemLibrary.line_trace_single(
            self.world,
            self.api.Vector(x, y, trace_top),
            self.api.Vector(x, y, trace_bottom),
            self.api.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [],
            self.api.DrawDebugTrace.NONE,
            True,
        )
        heights = [
            float(point.z)
            for point in (() if hit is None else hit.to_tuple())
            if all(hasattr(point, axis) for axis in ("x", "y", "z"))
            and abs(point.x - x) < 0.1
            and abs(point.y - y) < 0.1
            and math.isfinite(float(point.z))
            and trace_bottom < point.z < trace_top
        ]
        if not heights:
            raise RuntimeError("Distributed ground camera trace missed")
        return max(heights)

    def _build_views(self):
        ground = []
        for x in (25000, 100000, 175000):
            for y in (25000, 100000, 175000):
                height = self._ground_height(x, y)
                eye_x, eye_y = x - 3000, y - 4000
                eye_z = max(height + 2000, self._ground_height(eye_x, eye_y) + 2000)
                ground.append(([x, y, height], [eye_x, eye_y, eye_z]))
        bounds = [
            float("inf"),
            float("-inf"),
            float("inf"),
            float("-inf"),
            float("inf"),
            float("-inf"),
        ]
        for component in self.binding.components:
            origin, extent, _radius = self.api.SystemLibrary.get_component_bounds(
                component
            )
            for index, axis in enumerate(("x", "y", "z")):
                bounds[2 * index] = min(
                    bounds[2 * index],
                    float(getattr(origin, axis) - getattr(extent, axis)),
                )
                bounds[2 * index + 1] = max(
                    bounds[2 * index + 1],
                    float(getattr(origin, axis) + getattr(extent, axis)),
                )
        vertices = self.native_inputs["data"]["source"]["vertices_cm"]
        east_edge = [row for row in vertices if abs(row[4] - 44100.0) < 1e-6]
        if not east_edge:
            raise RuntimeError("Retained v8 east boundary is missing")
        seam = min(east_edge, key=lambda row: (abs(row[5] - 47250.0), row[0]))
        if list(seam[1:4]) != list(seam[4:7]):
            raise RuntimeError("Seam probe is not a fixed source boundary vertex")
        self.report["source_scene"]["seam_probe"] = {
            "source_vertex_id": seam[0],
            "target_cm": seam[4:7],
            "boundary_xy_cm": [37800, 44100, 44100, 50400],
            "original_source_delta_cm": 0.0,
            "defect_admitted": False,
            "scope": "One shared east boundary point; broader seam acceptance remains owner review",
        }
        views = build_view_plan(
            ground,
            self.native_inputs["data"]["pilot"]["frames"],
            bounds,
            self.report["source_scene"]["component_bounds"],
            seam[4:7],
        )
        for view in views:
            if view["frame_id"] in ("dominant-wall", "seam-close", "seam-distant"):
                x, y, z = view["camera"]
                view["camera"][2] = max(z, self._ground_height(x, y) + 2000)
        return views

    def start(self):
        self.busy = True
        try:
            self.report["memory_checkpoints"].append(
                memory_checkpoint("before_preparation", 8, 12)
            )
            self._verify_master()
            self.environment.assert_adaptive()
            self.binding = LandscapeBinding(
                self.api, self.landscape, self.master, self.instance
            )
            texts = self.native_inputs["texts"]
            native = self._native(
                self.api.YacsLandscapeMeshDiagnosticLibrary.begin_component230_detail(
                    self.component,
                    texts["source"],
                    texts["mask"],
                    texts["trial"],
                    texts["manifest"],
                ),
                "DETAIL_NATIVE_SOURCE_VERIFIED",
            )
            self.native_started = True
            mapping = native.pop("source_row_to_native_triangle_id")
            if (
                len(mapping) != 58216
                or len(set(mapping)) != 58216
                or native.get("native_attributes_retained") is not True
            ):
                raise RuntimeError(
                    "Whole-map native source mapping or attributes differ"
                )
            path = self.root / "source-row-native-triangle-map.json"
            write_json(path, mapping)
            native.update(
                source_row_map_file=path.name,
                source_row_map_sha256=digest(path),
                candidate_validated_but_not_applied=True,
            )
            self.report["native_source"] = native
            self.report["separate_mesh_materials_before"] = self.binding.other_materials
            self.views = self._build_views()
            self.steps = build_steps(self.views)
            self.report["capture_plan"] = [
                dict(view, mode=mode, resolution=list(RESOLUTION))
                for view, mode in self.steps
            ]
            self.report["capture_plan_sha256"] = hashlib.sha256(
                canonical(self.report["capture_plan"])
            ).hexdigest()
            self.handle = self.api.register_slate_post_tick_callback(self.tick)
            self._begin_step()
        except Exception:  # noqa: BLE001 - asynchronous native failures must enter complete rollback
            self.stop(traceback.format_exc())
        finally:
            self.busy = False

    def _set_parameters(self, values):
        lib = self.api.MaterialEditingLibrary
        association = self.api.MaterialParameterAssociation.GLOBAL_PARAMETER
        for name, value in values.items():
            lib.set_material_instance_parameter_override(
                self.instance, name, True, association
            )
            lib.set_material_instance_scalar_parameter_value(
                self.instance, name, float(value), association
            )
        lib.update_material_instance(self.instance)
        for name, expected in values.items():
            actual = float(
                lib.get_material_instance_scalar_parameter_value(
                    self.instance, name, association
                )
            )
            if abs(actual - expected) > 1e-5:
                raise RuntimeError("Whole-map scalar readback differs: " + name)

    def _begin_step(self):
        frame, mode = self.steps[self.index]
        self.environment.assert_adaptive()
        self.binding.assert_other_materials()
        if mode != "baseline":
            self._set_parameters(mode_parameters(mode))
            if not self.binding.applied:
                self.report["memory_checkpoints"].append(
                    memory_checkpoint("before_all1024_binding", 6, 8)
                )
                rows = self.binding.apply()
                write_json(self.root / "landscape-material-bindings.json", rows)
                self.report["bindings"] = {
                    "status": "ALL_NATIVE_ROOTS_MATCH",
                    "component_count": len(rows),
                    "expected_component_count": 1024,
                    "expected_root_material": self.master.get_path_name(),
                    "assigned_instance": self.instance.get_path_name(),
                    "file": "landscape-material-bindings.json",
                    "sha256": digest(self.root / "landscape-material-bindings.json"),
                    "includes_hidden_component230": True,
                }
            else:
                drain_compilation(self.api)
        # This known baseline guard retains all v8 attributes and never selects
        # the old trial. The only changing material is on the Landscape.
        native = self._native(
            self.api.YacsLandscapeMeshDiagnosticLibrary.set_component230_detail_mode(
                self.component, "baseline"
            ),
            "DETAIL_NATIVE_MODE_APPLIED",
        )
        if (
            native.get("changed_vertices") != 0
            or native.get("recomputed_normal_elements") != 0
            or native.get("native_uvs_unchanged") is not True
            or native.get("topology_unchanged") is not True
        ):
            raise RuntimeError(
                "Whole-map preparation changed accepted v8 geometry or attributes"
            )
        self.report["native_modes"].append(
            dict(native, frame_id=frame["frame_id"], landscape_mode=mode)
        )
        self.component.notify_mesh_modified()
        self.binding.assert_other_materials()
        eye, target = (
            self.api.Vector(*frame["camera"]),
            self.api.Vector(*frame["target"]),
        )
        rotation = self.api.MathLibrary.find_look_at_rotation(eye, target)
        self.camera.set_actor_location(eye, False, False)
        self.camera.set_actor_rotation(rotation, False)
        camera_component = self.camera.get_component_by_class(self.api.CameraComponent)
        camera_component.set_editor_property("field_of_view", frame["fov"])
        actual = self.camera.get_actor_location()
        if any(
            abs(float(getattr(actual, axis)) - value) > 0.001
            for axis, value in zip(("x", "y", "z"), frame["camera"])
        ):
            raise RuntimeError("Whole-map camera readback differs")
        actual_rotation = self.camera.get_actor_rotation()
        if (
            any(
                abs(
                    (
                        float(getattr(actual_rotation, axis))
                        - float(getattr(rotation, axis))
                        + 180
                    )
                    % 360
                    - 180
                )
                > 0.01
                for axis in ("pitch", "yaw", "roll")
            )
            or abs(
                float(camera_component.get_editor_property("field_of_view"))
                - frame["fov"]
            )
            > 0.001
        ):
            raise RuntimeError("Whole-map camera rotation or FOV differs")
        self.api.SystemLibrary.execute_console_command(self.world, "viewmode lit")
        self.api.SystemLibrary.execute_console_command(
            self.world, "showflag.DynamicShadows 1"
        )
        self.api.AutomationLibrary.set_editor_viewport_view_mode(
            self.api.ViewModeIndex.VMI_LIT
        )
        readiness_root = self.root / "readiness" / (frame["frame_id"] + "-" + mode)
        readiness = prepare_capture(
            self.api,
            self.landscape,
            eye,
            rotation,
            readiness_root,
            request_height_mips=True,
        )
        distance = (
            sum((a - b) ** 2 for a, b in zip(frame["camera"], frame["target"])) ** 0.5
        )
        self.pending = {
            "frame_id": frame["frame_id"],
            "mode": mode,
            "kind": frame["kind"],
            "camera_location_cm": frame["camera"],
            "target_cm": frame["target"],
            "camera_rotation_deg": [
                float(getattr(actual_rotation, axis))
                for axis in ("pitch", "yaw", "roll")
            ],
            "fov_deg": frame["fov"],
            "resolution": list(RESOLUTION),
            "viewmode": "lit",
            "dynamic_shadows": True,
            "material_parameters": mode_parameters(mode),
            "target_distance_cm": distance,
            "automatic_target_detail_factor": near_detail_factor(distance),
            "readiness": {
                "status": readiness["status"],
                "file": (readiness_root / "capture-readiness.json")
                .relative_to(self.root)
                .as_posix(),
                "sha256": digest(readiness_root / "capture-readiness.json"),
            },
        }
        self.prime = 0
        self._submit()

    def _submit(self):
        prime = self.prime < PRIMES_PER_CAPTURE
        path = (
            self.root
            / ("priming" if prime else "frames")
            / (self.pending["frame_id"] + "-" + self.pending["mode"] + ".png")
        )
        if path.exists() and not prime:
            raise RuntimeError("Whole-map proof refuses an existing admitted frame")
        self.api.AutomationLibrary.finish_loading_before_screenshot()
        self.task = self.api.AutomationLibrary.take_high_res_screenshot(
            res_x=RESOLUTION[0],
            res_y=RESOLUTION[1],
            filename=str(path),
            camera=self.camera,
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=self.api.ComparisonTolerance.LOW,
            comparison_notes="Whole working-map material preparation; sampled visual review, not final area/performance admission",
            delay=0.0,
            force_game_view=True,
        )
        if not self.task or not self.task.is_valid_task():
            raise RuntimeError("Whole-map native screenshot task is invalid")
        self.pending_path, self.task_started = path, self.clock()

    def tick(self, _delta):
        if self.stopped or self.busy:
            return
        self.busy = True
        try:
            if self.clock() - self.task_started > 90:
                raise RuntimeError("Whole-map native screenshot exceeded 90 seconds")
            if not self.task.is_task_done():
                return
            data = checked_bytes(self.pending_path, 24 * 1024 * 1024)
            if (
                len(data) < 10000
                or data[:8] != b"\x89PNG\r\n\x1a\n"
                or tuple(int.from_bytes(data[p : p + 4], "big") for p in (16, 20))
                != RESOLUTION
            ):
                raise RuntimeError(
                    "Whole-map screenshot is invalid or has wrong dimensions"
                )
            if self.prime < PRIMES_PER_CAPTURE:
                self.prime += 1
                self._submit()
                return
            self.environment.assert_adaptive()
            self.binding.assert_other_materials()
            self.report["captures"].append(
                dict(
                    self.pending,
                    file=self.pending_path.relative_to(self.root).as_posix(),
                    sha256=hashlib.sha256(data).hexdigest(),
                    size_bytes=len(data),
                )
            )
            self.index += 1
            self._write()
            if self.index == len(self.steps):
                self.stop()
            else:
                self._begin_step()
        except Exception:  # noqa: BLE001 - asynchronous native failures must enter complete rollback
            self.stop(traceback.format_exc())
        finally:
            self.busy = False

    def stop(self, error=None):
        if self.stopped:
            return
        self.stopped = True
        errors = [error] if error else []
        if self.handle is not None:
            try:
                self.api.unregister_slate_post_tick_callback(self.handle)
            except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
                errors.append("callback cleanup: " + str(exc))
            self.handle = None
        try:
            if self.binding is not None and self.binding.applied:
                final_rows = self.binding.audit()
                self.report["bindings"]["verified_again_after_captures"] = (
                    len(final_rows) == 1024
                )
        except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
            errors.append("final native material audit: " + str(exc))
        if self.native_started:
            try:
                self.report["native_restore"] = self._native(
                    self.api.YacsLandscapeMeshDiagnosticLibrary.end_component230_detail(
                        self.component
                    ),
                    "DETAIL_NATIVE_RESTORED",
                )
                self.component.notify_mesh_modified()
            except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
                errors.append("native v8 restoration: " + str(exc))
        if self.binding is not None:
            try:
                errors.extend(self.binding.restore())
                self.binding.assert_other_materials()
                self.report["separate_mesh_materials_preserved"] = True
            except Exception as exc:  # noqa: BLE001 - owning scene cleanup must still run
                errors.append("Landscape material restoration: " + str(exc))
                self.report["separate_mesh_materials_preserved"] = False
        try:
            if self.instance is not None and self.parameter_originals:
                self._set_parameters(self.parameter_originals)
                # Defaults were inherited in the saved instance. Restore that
                # override state, not just visually equivalent scalar values.
                association = self.api.MaterialParameterAssociation.GLOBAL_PARAMETER
                for name in self.parameter_originals:
                    self.api.MaterialEditingLibrary.set_material_instance_parameter_override(
                        self.instance, name, False, association
                    )
                self.api.MaterialEditingLibrary.update_material_instance(self.instance)
        except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
            errors.append("parameter restoration: " + str(exc))
        try:
            if (
                load_inputs(self.inputs["root"])["manifest_sha256"]
                != self.inputs["manifest_sha256"]
            ):
                raise RuntimeError("Preparation inputs changed during capture")
            for row in self.master_data.get("generated_assets", []):
                if digest(asset_file(row["asset"])) != row["sha256"] or package_files(
                    row["asset"]
                ) != row.get("package_files"):
                    raise RuntimeError(
                        "Saved preparation package changed during capture"
                    )
        except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
            errors.append("immutable evidence: " + str(exc))
        self.report["duration_seconds"] = round(self.clock() - self.started, 3)
        self.report["capture_complete"] = len(self.report["captures"]) == 30
        if self.report["capture_complete"]:
            try:
                pair = [
                    next(row for row in self.report["captures"] if row["mode"] == mode)
                    for mode in ("normal-near", "normal-far")
                ]
                response = paired_normal_response(
                    *(decode_png(self.root / row["file"], RESOLUTION) for row in pair)
                )
                response["files"] = [
                    {"file": row["file"], "sha256": row["sha256"]} for row in pair
                ]
                self.report["near_far_material_response"] = response
            except Exception as exc:  # noqa: BLE001 - continue every native rollback after wrapper errors
                errors.append("near/far image evidence: " + str(exc))
        if not self.report["capture_complete"] and not errors:
            errors.append("Whole-map capture coverage is incomplete")
        self.report["status"] = "FAILED" if errors else "CAPTURED_PENDING_SCENE_CLEANUP"
        self.report["error"] = "\n".join(errors) if errors else None
        try:
            self._write()
        except Exception as exc:  # noqa: BLE001 - evidence failure must not skip scene cleanup
            errors.append("final evidence write: " + str(exc))
            self.report["status"] = "FAILED"
            self.report["error"] = "\n".join(errors)
        finally:
            # The owning harness restores original camera, console/LOD state,
            # Landscape visibility/material, and destroys transient actors even
            # when a diagnostic or evidence write has failed.
            self.done(self.report["error"])

    def mark_cleanup(self, error):
        if error or not self.environment.report.get("restored"):
            self.report["status"] = "FAILED"
            self.report["error"] = (
                error or "Whole-map capture environment did not restore"
            )
            self.report["cleanup"] = {"status": "FAILED", "error": self.report["error"]}
        elif self.report["status"] == "CAPTURED_PENDING_SCENE_CLEANUP":
            self.report["status"] = "WHOLE_MAP_PREPARATION_PASS"
            self.report["cleanup"] = {
                "status": "RESTORED",
                "source_map_hash_unchanged": True,
                "source_scene_snapshot_unchanged": True,
                "landscape_materials_restored": True,
                "capture_environment_restored": True,
            }
        self._write()
