"""Whole working-map preparation evidence inside the accepted v8 scene owner.

Twenty-one distributed, close, broad and seam views plus matched diagnostics. The
existing owning harness restores the map scene; this consumer restores all
Landscape materials, native v8 attributes, parameters and capture settings.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import time
import traceback
from pathlib import Path

from scripts.ue.prepare_landscape_capture import prepare_capture
from scripts.ue.sa_calobra_geometry_collision_witness import capture_geometry_collision
from scripts.ue.sa_calobra_whole_map_witness import (
    WITNESS_MODES,
    witness_parameters,
    witness_steps,
)
from scripts.ue.sa_calobra_whole_map_prep import console_value
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
NEAR_VIEWS = ("near-landscape-1", "near-landscape-2", "near-landscape-3")
FAR_VIEWS = ("window-0181-forward-00004", "window-0077-reverse-00000")
SURVEY_FILE = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
SURVEY_SHA256 = "15e0a2350c613bf52bfb1354192043ca0c6cd785493c59e7721305b67de099a3"
NEAR_INPUTS = {
    "material-weights.png": "af16fc7c43ec8a3a3b2e000fe716232a3229fe0ac6b4e9708baae5842ef99f6c",
    "sample-availability.png": "9c9906268977a8f49ba20c194cecb101e8bb8c25c44b51ee30f66e7e88a7522a",
    "inference-kind.png": "cc3bc3490878c5a96c20586cd28b0cd3cc812c5506ae97a7110c59e6ed3a3176",
    "exclusion-reasons.png": "f1adb0c0e8fc3fecba53cfaf033f9d33c0784ab4c7f0ecb0d661629d3b35494e",
    "exclusion-reasons.tif": "c74bde6ae8589304fe3d52f4e1e20801b0fe5647de6ffbc268c9b2ca65eaa941",
}
NEAR_TARGETS = (
    (
        1961,
        96,
        (244, 0, 4, 0),
        "low_vegetation_appearance",
        "7f43e4a3d3152ab7114223b7b171c939c7d63d680a85b1f357d61b020a664869",
    ),
    (
        2048,
        121,
        (71, 162, 8, 0),
        "forest_litter_appearance",
        "23f3f4b09b7a73e1a25903fcacf83ce58aae637bf3b5f8daf951b30e822e23dc",
    ),
    (
        2048,
        1408,
        (19, 0, 94, 0),
        "mineral_rock_mixture",
        "f5acdf97f56515ff8d38d1e8991feeaf9238dbd7ddb24aee9d5d873262db0e28",
    ),
)


def near_source_probes(inputs):
    """Bind the three CPU-audited 17x17 windows to immutable raster bytes.

    The host verifier independently decodes these windows. Embedded Unreal only
    needs the already verified file identities and fresh collision/camera proof.
    Appearance examples do not classify geography or physical demand bands.
    """
    if any(inputs["hashes"].get(name) != sha for name, sha in NEAR_INPUTS.items()):
        raise ValueError(
            "Near Landscape probes require the exact audited raster inputs"
        )
    return [
        {
            "row": row,
            "column": column,
            "pixel_window": [column - 8, row - 8, 17, 17],
            "xy_cm": [column * 50, row * 50],
            "center_rgba": list(rgba),
            "purpose_role": role,
            "physical_demand_band": "UNASSIGNED",
            "input_sha256": dict(NEAR_INPUTS),
            "halo_data_sha256": {
                "material_weights_rgba8": halo_sha,
                "availability_l8": "0682379a2bc138776a8dba4e8ca8a1933ec18b0b7ff9946b180d106c2e9c8f78",
                "inference_l8": "6559f403524ea6ef9bf2e1d0bb66d1af8152920fb002ec2c4ced993083124a88",
                "exclusion_reasons_l8": "6559f403524ea6ef9bf2e1d0bb66d1af8152920fb002ec2c4ced993083124a88",
            },
            "support": {
                "cells": 289,
                "availability255_cells": 289,
                "inference0_cells": 289,
                "exclusion0_cells": 289,
                "basis": "Pinned raster identity and independently decoded CPU windows",
            },
        }
        for row, column, rgba, role, halo_sha in NEAR_TARGETS
    ]


def original_survey_views(path=None):
    path = Path(path) if path is not None else ROOT / SURVEY_FILE
    data = checked_bytes(path, 4 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != SURVEY_SHA256:
        raise ValueError("Original B/C survey CSV byte identity changed")
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    selected = []
    for frame_id, index, card, band in (
        (FAR_VIEWS[0], 661, "SC-P04", "B"),
        (FAR_VIEWS[1], 1088, "SC-P06", "C"),
    ):
        matches = [row for row in rows if row["frame_id"] == frame_id]
        if len(matches) != 1 or int(matches[0]["index"]) != index:
            raise ValueError("Original survey observation identity differs")
        row = matches[0]
        camera, target = (
            json.loads(row["camera_location_cm"]),
            json.loads(row["target_cm"]),
        )
        fov = float(row["fov_deg"])
        resolution = [int(row["width_px"]), int(row["height_px"])]
        if (
            any(
                len(point) != 3 or not all(math.isfinite(value) for value in point)
                for point in (camera, target)
            )
            or fov != 76.0
            or resolution != [1280, 720]
            or resolution[0] * RESOLUTION[1] != resolution[1] * RESOLUTION[0]
        ):
            raise ValueError("Original survey camera/FOV/aspect contract differs")
        selected.append(
            {
                "frame_id": frame_id,
                "kind": "pinned_original_survey",
                "camera": camera,
                "target": target,
                "fov": fov,
                "coverage": "Original proposed "
                + band
                + " observation; no whole-view physical band assignment or mountain-distance measurement",
                "survey_source": {
                    "file": SURVEY_FILE,
                    "sha256": SURVEY_SHA256,
                    "frame_id": frame_id,
                    "index": index,
                    "original_png_sha256": row["sha256"],
                    "original_resolution": resolution,
                    "review_card": card,
                    "proposal_band": band,
                    "physical_surface_registered": False,
                },
            }
        )
    return selected


def trace_point(hit, start, end):
    """Extract a real interior line hit, excluding UE's trace endpoint vectors."""
    direction = [b - a for a, b in zip(start, end)]
    squared = sum(value * value for value in direction)
    if not math.isfinite(squared) or squared <= 0:
        raise ValueError("Invalid Landscape trace segment")
    candidates = []
    for value in () if hit is None else hit.to_tuple():
        if not all(hasattr(value, axis) for axis in ("x", "y", "z")):
            continue
        point = [float(getattr(value, axis)) for axis in ("x", "y", "z")]
        if not all(math.isfinite(number) for number in point):
            continue
        parameter = (
            sum((p - a) * d for p, a, d in zip(point, start, direction)) / squared
        )
        residual = sum(
            (p - a - parameter * d) ** 2 for p, a, d in zip(point, start, direction)
        )
        if 1e-6 < parameter < 1 - 1e-6 and residual <= 1.0:
            candidates.append((parameter, point))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def build_view_plan(
    ground,
    pilot_frames,
    bounds,
    component_bounds,
    seam_point,
    *,
    near_views=(),
    far_views=(),
):
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
    if (
        tuple(view["frame_id"] for view in near_views) != NEAR_VIEWS
        or tuple(view["frame_id"] for view in far_views) != FAR_VIEWS
    ):
        raise ValueError(
            "Whole-map near Landscape and original B/C coverage is incomplete"
        )
    views.extend(near_views)
    views.extend(far_views)
    if len(views) != 21 or len({view["frame_id"] for view in views}) != 21:
        raise ValueError("Whole-map view identity is not unique")
    return views


def build_steps(views):
    lookup = {view["frame_id"]: view for view in views}
    if len(lookup) != 21 or not set(TARGETED_VIEWS + NEAR_VIEWS + FAR_VIEWS) <= set(
        lookup
    ):
        raise ValueError("Whole-map camera coverage is incomplete")
    steps = [
        (lookup[name], "baseline") for name in TARGETED_VIEWS + NEAR_VIEWS + FAR_VIEWS
    ]
    steps += [(view, "prepared") for view in views]
    steps += [(lookup[name], "domains") for name in TARGETED_VIEWS]
    steps += [(lookup[name], "checker") for name in TARGETED_VIEWS + NEAR_VIEWS]
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
        self.native_root = Path(native_root)
        self.native_inputs = load_native_inputs(native_root)
        self.master_receipt = Path(master_receipt)
        self.master_data = json.loads(
            checked_bytes(self.master_receipt, 2 * 1024 * 1024)
        )
        self.exact_sha = exact_sha
        self.task = self.handle = self.pending = None
        self.capture_phase = "primary"
        self.witness_steps = []
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
            "source_scene": dict(
                source_scene, landscape_actor_path=landscape.get_path_name()
            ),
            "rendering_recipe": rendering_recipe(),
            "capture_plan": [],
            "captures": [],
            "diagnostic_captures": [],
            "geometry_collision_witness": {"status": "PENDING"},
            "diagnostic_capture_plan": [],
            "diagnostic_complete": False,
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
            "coverage_claim": "All 1024 components bound plus 21 sampled views; no every-pixel or whole-map visibility PASS",
            "error": None,
            "priming_captures_per_phase": PRIMES_PER_CAPTURE,
            "memory_checkpoints": [],
        }
        if self.root.exists():
            raise ValueError("Whole-map evidence directory must not already exist")
        for name in ("frames", "priming", "readiness", "diagnostics"):
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
        self.report["fresh_process_texture_compile_drain"] = actual[
            "texture_compile_drain"
        ]
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

    def _landscape_only_trace(self, start, end, actors):
        ignored = [actor for actor in actors if actor != self.landscape]

        def query(excluded):
            hit = self.api.SystemLibrary.line_trace_single(
                self.world,
                self.api.Vector(*start),
                self.api.Vector(*end),
                self.api.TraceTypeQuery.ECC_VISIBILITY,
                True,
                excluded,
                self.api.DrawDebugTrace.NONE,
                True,
            )
            return trace_point(hit, start, end)

        point = query(ignored)
        if point is None:
            raise RuntimeError(
                "Near Landscape trace missed: "
                + json.dumps({"start_cm": start, "end_cm": end})
            )
        control = query(actors)
        if control is not None:
            raise RuntimeError(
                "Near trace remains blocked with Landscape excluded: "
                + json.dumps(control)
            )
        return {
            "start_cm": list(start),
            "end_cm": list(end),
            "hit_cm": point,
            "owner_excluded_control_hit_cm": None,
        }

    def _build_near_views(self):
        actors = list(
            self.api.get_editor_subsystem(
                self.api.EditorActorSubsystem
            ).get_all_level_actors()
        )
        if self.landscape not in actors:
            raise RuntimeError(
                "Owning Landscape is missing from the native actor inventory"
            )
        paths = sorted(actor.get_path_name() for actor in actors)
        if len(paths) != len(set(paths)):
            raise RuntimeError("Native near-probe actor inventory is ambiguous")
        self.report["near_landscape_probes"] = []
        views = []
        for frame_id, source in zip(NEAR_VIEWS, near_source_probes(self.inputs)):
            x, y = source["xy_cm"]
            evidence = {
                "owner_path": self.landscape.get_path_name(),
                "world_actor_paths": paths,
                "ignored_actor_paths": sorted(
                    actor.get_path_name() for actor in actors if actor != self.landscape
                ),
                "nominal_camera_offset_cm": [100, 0, 250],
                "rendered_pixel_depth_verified": False,
                "scope": "Landscape-only collision ownership and same-camera checker review; no rendered pixel-depth or A-band registration",
            }
            self.report["near_landscape_probes"].append(
                {
                    "frame_id": frame_id,
                    "source_probe": source,
                    "landscape_probe": evidence,
                }
            )
            evidence["target_trace"] = self._landscape_only_trace(
                [x, y, 150000], [x, y, -150000], actors
            )
            target = evidence["target_trace"]["hit_cm"]
            evidence["eye_ground_trace"] = self._landscape_only_trace(
                [x + 100, y, 150000], [x + 100, y, -150000], actors
            )
            eye_ground = evidence["eye_ground_trace"]["hit_cm"]
            camera = [x + 100, y, max(target[2] + 250, eye_ground[2] + 150)]
            distance = math.dist(camera, target)
            evidence["camera_clearance_cm"] = camera[2] - eye_ground[2]
            evidence["target_distance_cm"] = distance
            if not 100 <= distance <= 500:
                raise RuntimeError(
                    f"Near Landscape {frame_id} target range {distance:.3f} cm is outside 100..500 cm; refusing a higher/farther camera"
                )
            end = [
                value + 25 * (value - eye) / distance
                for value, eye in zip(target, camera)
            ]
            evidence["aim_trace"] = self._landscape_only_trace(camera, end, actors)
            aim = evidence["aim_trace"]["hit_cm"]
            hit_distance = math.dist(camera, aim)
            evidence["hit_distance_cm"] = hit_distance
            if not 100 <= hit_distance <= 500 or any(
                abs(aim[index] - value) > 400 for index, value in enumerate((x, y))
            ):
                raise RuntimeError(
                    f"Near Landscape {frame_id} actual hit leaves the 1..5 m range or audited 17x17 support"
                )
            views.append(
                {
                    "frame_id": frame_id,
                    "kind": "source_grid_landscape_near",
                    "camera": camera,
                    "target": target,
                    "fov": 60.0,
                    "coverage": "Audited source-grid material example with a 1..5 m Landscape collision hit; visual/checker review remains separate",
                    "source_probe": source,
                    "landscape_probe": evidence,
                }
            )
        return views

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
            near_views=self._build_near_views(),
            far_views=original_survey_views(self.native_root / "frames.csv"),
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
            self.report["geometry_collision_witness"] = capture_geometry_collision(
                self.api, self.world, self.landscape, self.views
            )
            self.steps = build_steps(self.views)
            self.witness_steps = witness_steps(self.views)
            self.report["diagnostic_capture_plan"] = [
                dict(view, mode=mode, resolution=list(RESOLUTION))
                for view, mode in self.witness_steps
            ]
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
        changed = {}
        for name, value in values.items():
            actual = float(
                lib.get_material_instance_scalar_parameter_value(
                    self.instance, name, association
                )
            )
            if not math.isfinite(actual) or not math.isfinite(float(value)):
                raise RuntimeError("Non-finite whole-map scalar: " + name)
            if abs(actual - value) > 1e-5:
                changed[name] = value
        if not changed:
            return False
        for name, value in changed.items():
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
            if not math.isfinite(actual) or abs(actual - expected) > 1e-5:
                raise RuntimeError("Whole-map scalar readback differs: " + name)
        return True

    def _begin_step(self):
        frame, mode = (
            self.steps[self.index]
            if self.capture_phase == "primary"
            else self.witness_steps[self.index]
        )
        self.environment.assert_adaptive()
        self.binding.assert_other_materials()
        if mode == "baseline" and self.binding.applied:
            raise RuntimeError("All baseline captures must precede preparation binding")
        if mode != "baseline":
            desired = (
                witness_parameters(mode, mode_parameters("prepared"))
                if mode in WITNESS_MODES
                else mode_parameters(mode)
            )
            parameters_changed = self._set_parameters(desired)
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
            elif parameters_changed:
                # Moving a camera with unchanged parameters does not require
                # another material update or full GC. Native screenshot loading
                # and height-mip readiness still run for every view below.
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
        use_shadows = mode != "no-shadows"
        self.api.SystemLibrary.execute_console_command(self.world, "viewmode lit")
        self.api.SystemLibrary.execute_console_command(
            self.world, "showflag.DynamicShadows " + ("1" if use_shadows else "0")
        )
        if int(float(console_value(self.api, "showflag.DynamicShadows"))) != int(
            use_shadows
        ):
            raise RuntimeError("Visual witness shadow toggle readback failed")
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
            "dynamic_shadows": use_shadows,
            "material_parameters": (
                witness_parameters(mode, mode_parameters("prepared"))
                if mode in WITNESS_MODES
                else mode_parameters(mode)
            ),
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
        for name in ("source_probe", "landscape_probe", "survey_source"):
            if name in frame:
                self.pending[name] = frame[name]
        self.prime = 0
        self._submit()

    def _submit(self):
        prime = self.prime < PRIMES_PER_CAPTURE
        path = (
            self.root
            / (
                "priming"
                if prime
                else "frames"
                if self.capture_phase == "primary"
                else "diagnostics"
            )
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
            destination = (
                self.report["captures"]
                if self.capture_phase == "primary"
                else self.report["diagnostic_captures"]
            )
            destination.append(
                dict(
                    self.pending,
                    file=self.pending_path.relative_to(self.root).as_posix(),
                    sha256=hashlib.sha256(data).hexdigest(),
                    size_bytes=len(data),
                )
            )
            self.index += 1
            self._write()
            if self.capture_phase == "primary" and self.index == len(self.steps):
                self.capture_phase = "witness"
                self.index = 0
                self._begin_step()
            elif self.capture_phase == "witness" and self.index == len(
                self.witness_steps
            ):
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
        self.report["capture_complete"] = (
            len(self.report["captures"]) == len(self.steps) == 43
        )
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
        self.report["diagnostic_complete"] = (
            len(self.report["diagnostic_captures"]) == len(self.witness_steps) == 8
        )
        if not self.report["diagnostic_complete"]:
            errors.append("Bounded material/light witness capture is incomplete")
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
        # The owning callback also propagates a prior capture error. A failed
        # renderer does not imply that its separately verified LOD/camera/CVar
        # rollback failed. Preserve both results without admitting the capture.
        restored = self.environment.report.get("restored") is True
        environment_result = {
            "status": "RESTORED" if restored else "FAILED",
            "restore_errors": list(
                self.environment.report.get("restore_errors") or []
            ),
        }
        if error or not restored:
            self.report["status"] = "FAILED"
            self.report["error"] = (
                error or "Whole-map capture environment did not restore"
            )
            self.report["cleanup"] = {
                "status": "FAILED",
                "error": self.report["error"],
                "capture_environment": environment_result,
            }
        elif self.report["status"] == "CAPTURED_PENDING_SCENE_CLEANUP":
            self.report["status"] = "WHOLE_MAP_PREPARATION_PASS"
            self.report["cleanup"] = {
                "status": "RESTORED",
                "source_map_hash_unchanged": True,
                "source_scene_snapshot_unchanged": True,
                "landscape_materials_restored": True,
                "capture_environment_restored": True,
                "capture_environment": environment_result,
            }
        else:
            # Teardown success cannot turn a partial/inconsistent capture green.
            self.report["status"] = "FAILED"
            self.report["error"] = (
                self.report.get("error") or "Whole-map capture did not complete"
            )
            self.report["cleanup"] = {
                "status": "FAILED",
                "error": self.report["error"],
                "capture_environment": environment_result,
            }
        self._write()
