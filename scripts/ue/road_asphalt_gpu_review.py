"""Issue #364: four pinned, road-facing lit screenshots from a freshly saved consumer.

This is a bounded technical GPU rendering canary, not owner approval or a
whole-map visual audit. The camera identities/poses come from an immutable
previously captured bidirectional road survey, never guessed free cameras.
Only a transient camera and viewport state may change; nothing is saved.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci import official_mcp_bob_session as session  # noqa: E402
from scripts.proof.sa_calobra_shoulder_contact import (  # noqa: E402
    FRAME_IDS,
    SURVEY_SHA256,
)
from scripts.ue import read_road_material_baseline as baseline  # noqa: E402
from scripts.ue import road_asphalt_saved_consumer as saved  # noqa: E402
from scripts.ue import sa_calobra_whole_map_prep as prep  # noqa: E402
from scripts.ue.sa_calobra_detail_capture import decode_png  # noqa: E402
from scripts.ue.prepare_landscape_capture import (  # noqa: E402
    HEIGHT_MIP_LEASE_SECONDS,
    _height_texture_objects,
    prepare_capture,
)

SURVEY = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
RECEIPT = "road-asphalt-lit-review.json"
RESOLUTION = (1280, 720)
MAX_CSV_BYTES = 1024 * 1024
MAX_FRAME_BYTES = 16 * 1024 * 1024
TOTAL_DEADLINE_SECONDS = 380
FRAME_DEADLINE_SECONDS = 90
PRIMING_FRAMES = 3


def require(value, message):
    if not value:
        raise ValueError(message)


def validated_road_views(raw, required_sha256):
    """Accept exactly four prior road-camera poses at window 0112, both directions."""
    require(
        isinstance(raw, bytes)
        and 0 < len(raw) <= MAX_CSV_BYTES
        and hashlib.sha256(raw).hexdigest() == required_sha256,
        "Frozen road survey camera source is missing or changed",
    )
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        rows = {}
        names = set()
        for n, row in enumerate(reader):
            require(n < 4096, "Camera CSV exceeds row limit")
            frame = row.get("frame_id")
            require(frame not in names, "Camera CSV contains duplicate frame IDs")
            names.add(frame)
            if frame not in FRAME_IDS:
                continue
            require(
                row.get("direction") in ("forward", "reverse")
                and row.get("window_id")
                == "reviewed-VIAL_TR70190001272-1-interval-24-0"
                and row.get("native_readiness_status") == "NATIVE_LOADING_AND_MIPS_READY"
                and row.get("visual_review_status") == "UNREVIEWED",
                "Chosen survey row differs from the retained road proof",
            )
            vectors = {}
            for field in ("camera_location_cm", "target_cm", "road_position_cm"):
                numbers = json.loads(row[field])
                require(
                    isinstance(numbers, list)
                    and len(numbers) == 3
                    and all(
                        type(v) in (int, float) and math.isfinite(v) for v in numbers
                    ),
                    "Invalid source road camera vector",
                )
                vectors[field] = [float(v) for v in numbers]
            require(
                math.dist(vectors["camera_location_cm"], vectors["target_cm"]) > 100.0
                and math.dist(vectors["road_position_cm"], vectors["camera_location_cm"])
                < 2500.0
                and float(row["fov_deg"]) == 76.0
                and int(row["width_px"]) == RESOLUTION[0]
                and int(row["height_px"]) == RESOLUTION[1],
                "Road camera pose/FOV/resolution is outside its original contract",
            )
            rows[frame] = {
                "frame_id": frame,
                "direction": row["direction"],
                "station_m": float(row["station_m"]),
                "fov_deg": 76.0,
                **vectors,
            }
        require(set(rows) == set(FRAME_IDS), "Missing accepted forward/reverse road poses")
        return [rows[frame] for frame in FRAME_IDS]
    except (KeyError, TypeError, OverflowError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid authenticated road camera CSV") from exc


def frame_statistics(png_path):
    """Technical only: valid nonuniform lit pixels, not road visibility or aesthetics."""
    width, height, channels, pixels = decode_png(png_path, RESOLUTION)
    pixel_total = width * height
    step = max(1, pixel_total // 2048)
    samples = {
        tuple(pixels[i * channels : i * channels + 3])
        for i in range(0, pixel_total, step)
    }
    require(
        len(samples) >= 12,
        "Native lit screenshot is uniform/blank or its sample diversity is too low",
    )
    return {
        "width": width,
        "height": height,
        "channels": channels,
        "unique_sampled_rgb": len(samples),
        "visual_quality_reviewed": False,
        "road_pixels_isolated": False,
    }


def authenticate_render_context():
    session._assert_isolated_root()
    require(saved.ROOT == ROOT == session.ROOT == prep.ROOT,
            "GPU review is not inside the exact isolated repository")
    exact_sha, staged_sha, token, proof, retained = saved.proof_paths()
    stage_path, stage_identity, stage, _map, rows = saved.verified_staging(
        exact_sha, staged_sha
    )
    original, _trial = saved.verified_predecessors(proof, exact_sha, staged_sha)
    host = session._read_json(session._safe_path(proof, "saved-road-host-receipt.json"))
    prepare_receipt = session._read_json(session._safe_path(proof, saved.PREPARED))
    fresh_receipt = session._read_json(session._safe_path(proof, saved.RELOADED))
    manifest_path = session._safe_path(retained, saved.MANIFEST)
    manifest_id = session._identity(manifest_path, saved.JSON_LIMIT)
    manifest = session._read_json(manifest_path)
    require(
        host.get("schema_version") == 1
        and host.get("status") == "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS"
        and host.get("exact_sha") == exact_sha
        and host.get("saved_derived_consumer") is True
        and host.get("fresh_reload_verified") is True
        and host.get("original_map_saved") is False
        and host.get("original_landscape_mutated") is False
        and host.get("gpu_shader_verified") is False
        and host.get("performance_pass") is False
        and host.get("proof_files", {}).get("saved_prepared", {}).get("sha256")
        == session._identity(session._safe_path(proof, saved.PREPARED))["sha256"]
        and host.get("proof_files", {}).get("fresh_reload", {}).get("sha256")
        == session._identity(session._safe_path(proof, saved.RELOADED))["sha256"]
        and prepare_receipt.get("manifest") == manifest_id
        and fresh_receipt.get("saved_manifest_sha256") == manifest_id["sha256"]
        and fresh_receipt.get("status")
        == "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS"
        and fresh_receipt.get("fresh_process") is True
        and fresh_receipt.get("road_material_reapplied") is False
        and manifest.get("status") == "SAVED_ROAD_ASPHALT_CONSUMER_PREPARED"
        and manifest.get("exact_sha") == exact_sha
        and manifest.get("staging_sha256") == staged_sha
        and manifest.get("map_package") == saved.MAP
        and manifest.get("road_slot_zero_only") is True
        and manifest.get("support_186_unchanged") is True
        and manifest.get("landscape_1024_unchanged") is True
        and manifest.get("metric_tile_cm") == 400
        and manifest.get("performance_pass") is False,
        "Cannot render without the same exact-SHA native save and fresh-reload proof",
    )
    saved.verify_retained_files(retained, manifest["assets"])
    source = session._safe_path(ROOT, SURVEY)
    survey_identity = session._identity(source, MAX_CSV_BYTES)
    require(survey_identity["sha256"] == SURVEY_SHA256, "Road camera CSV pin differs")
    frames = validated_road_views(source.read_bytes(), SURVEY_SHA256)
    return {
        "exact_sha": exact_sha,
        "staging_sha256": staged_sha,
        "run_token": token,
        "proof": proof,
        "retained": retained,
        "manifest": manifest,
        "manifest_id": manifest_id,
        "original": original,
        "rows": rows,
        "stage_path": stage_path,
        "stage_identity": stage_identity,
        "frames": frames,
        "survey_identity": survey_identity,
        "host_receipt_identity": session._identity(
            session._safe_path(proof, "saved-road-host-receipt.json")
        ),
    }


def audit_transient_capture_dirty_packages(api):
    """Admit only camera/viewport dirt in the unsaved *derived* world.

    Unreal marks its current map dirty when an otherwise transient CameraActor
    is spawned and destroyed. That package dirt is not a saved map mutation:
    whole-world normalized inventory and immutable on-disk SHA checks remain
    separate mandatory gates. Every content-package dirt or foreign map dirt
    remains a hard failure.
    """
    loading = api.EditorLoadingAndSavingUtils
    maps = list(loading.get_dirty_map_packages())
    content = list(loading.get_dirty_content_packages())
    require(
        len(maps) <= 8 and len(content) <= 8,
        "GPU camera produced unbounded dirty package inventory",
    )

    def name(pkg):
        if hasattr(pkg, "get_path_name"):
            return pkg.get_path_name()
        require(isinstance(pkg, str), "Unidentified Unreal dirty package object")
        return pkg

    map_paths = sorted(name(pkg) for pkg in maps)
    content_paths = sorted(name(pkg) for pkg in content)
    require(
        not content_paths and all(path == saved.MAP for path in map_paths),
        "GPU camera changed non-derived map/content package: "
        + repr({"maps": map_paths, "content": content_paths}),
    )
    return {
        "derived_map_dirty_in_memory": bool(map_paths),
        "dirty_map_paths": map_paths,
        "dirty_content_count": len(content_paths),
        "no_original_or_content_package_dirty": True,
        "dirty_derived_package_saved": False,
        "geometry_or_material_changes_admitted": False,
    }


class RoadLitCapture:
    def __init__(self, api, context, world, landscape):
        self.api = api
        self.context = context
        self.world, self.landscape = world, landscape
        self.proof = context["proof"]
        self.root = session._safe_path(self.proof, "road-asphalt-lit-review")
        require(not self.root.exists(), "GPU review output already exists; no overwrite")
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "frames").mkdir()
        (self.root / "priming").mkdir()
        self.camera = None
        self.viewport_before = None
        self.handle = None
        self.task = None
        self.index = 0
        self.frames = []
        self.started = time.monotonic()
        self.submitted = None
        self.prime_index = 0
        self.prime_evidence = []
        self.completed_priming_frames = 0
        self.pending_path = None
        self.pose_readiness = None
        self.residency_leases = {}
        self.residency_released = False
        self.stopped = False
        self.busy = False
        self.finish_requested_at = None
        self.transient_dirty_audit = None

    def start(self):
        self.busy = True
        try:
            self.api.EditorPythonScripting.set_keep_python_script_alive(True)
            viewport = self.api.get_editor_subsystem(self.api.UnrealEditorSubsystem)
            self.viewport_before = viewport.get_level_viewport_camera_info()
            require(self.viewport_before is not None,
                    "GPU road review needs an owned Editor viewport")
            self.camera = self.api.get_editor_subsystem(
                self.api.EditorActorSubsystem
            ).spawn_actor_from_class(
                self.api.CameraActor, self.api.Vector(), self.api.Rotator(),
                transient=True,
            )
            require(self.camera is not None, "Transient road camera could not spawn")
            self.handle = self.api.register_slate_post_tick_callback(self.tick)
            self.submit_pose()
        except Exception:
            self.stop(traceback.format_exc())
        finally:
            self.busy = False

    def prepare_pose(self, row, eye, rotation):
        """Reuse the accepted terrain capture path, not a screenshot-only barrier.

        The original source survey primed the active viewport and checked full
        map-owned height mip residency. Merely aiming a CameraActor omits that
        streaming input. Keep source geometry/LOD/materials fixed and retain
        before/after residency telemetry instead of assuming a terrain defect.
        """
        material_paths = self.context["manifest"]["texture_objects"]
        require(
            set(material_paths) == {"BaseColor", "Normal_DX", "ORM", "DetailMasks"}
            and len(set(material_paths.values())) == 4,
            "Expected four distinct authenticated road textures",
        )
        road_textures = []
        for channel, path in sorted(material_paths.items()):
            texture = self.api.load_asset(path)
            require(
                texture is not None and texture.get_path_name() == path,
                "Pinned road texture missing before residency request: " + channel,
            )
            self.residency_leases[path] = texture
            texture.set_force_mip_levels_to_be_resident(HEIGHT_MIP_LEASE_SECONDS, 0)
            road_textures.append((channel, texture))
        # Register before the helper call so partial setup also cleans up.
        for texture in _height_texture_objects(self.api, self.landscape):
            self.residency_leases[texture.get_path_name()] = texture
        output = session._safe_path(self.root, "readiness/" + row["frame_id"])
        report = prepare_capture(
            self.api, self.landscape, eye, rotation, output,
            request_height_mips=True,
        )
        require(
            report.get("status") == "NATIVE_LOADING_AND_MIPS_READY"
            and report.get("viewport_primed_at_rider_camera") is True
            and report.get("height_mip_lease_requested") is True
            and report.get("native_loading_barrier_completed") is True,
            "Accepted native terrain capture preparation did not complete",
        )
        materials = []
        for channel, texture in road_textures:
            raw = self.api.YacsTextureAuditLibrary.describe_texture(texture)
            require(isinstance(raw, str) and len(raw) <= 16384,
                    "Unbounded native road texture telemetry")
            metadata = json.loads(raw)
            require(
                isinstance(metadata, dict)
                and "error" not in metadata
                and metadata.get("is_default_texture") is False
                and metadata.get("is_compiling") is False
                and type(metadata.get("mips")) is int
                and metadata["mips"] > 0
                and metadata.get("resident_mips") == metadata["mips"],
                "Road texture is not fully resident: " + channel,
            )
            materials.append({"channel": channel, "asset": texture.get_path_name(),
                              "native_readback": metadata})
        material_id = saved.write_once(output / "road-texture-readiness.json", {
            "schema_version": 1, "status": "ROAD_TEXTURE_MIPS_READY",
            "textures": materials, "lease_seconds": HEIGHT_MIP_LEASE_SECONDS,
            "material_parameters_changed": False, "saved_to_map": False,
        })
        self.pose_readiness = {
            "status": report["status"],
            "height_receipt": session._identity(output / "capture-readiness.json", 8 * 1024 * 1024),
            "material_receipt": material_id,
            "height_mip_lease_requested": True,
            "viewport_primed_at_rider_camera": True,
            "material_texture_count": len(materials),
        }

    def release_residency(self):
        """End only this isolated capture's expiring requests, including failures."""
        errors = []
        for name, texture in self.residency_leases.items():
            try:
                texture.set_force_mip_levels_to_be_resident(0.0, 0)
            except Exception as exc:
                errors.append("mip lease: " + name + ": " + str(exc))
        self.residency_released = not errors
        return errors

    def submit_pose(self):
        row = self.context["frames"][self.index]
        eye = self.api.Vector(*row["camera_location_cm"])
        target = self.api.Vector(*row["target_cm"])
        rotation = self.api.MathLibrary.find_look_at_rotation(eye, target)
        self.camera.set_actor_location(eye, False, False)
        self.camera.set_actor_rotation(rotation, False)
        component = self.camera.get_component_by_class(self.api.CameraComponent)
        component.set_editor_property("field_of_view", row["fov_deg"])
        actual = self.camera.get_actor_location()
        require(
            all(
                abs(float(getattr(actual, axis)) - number) <= 0.1
                for axis, number in zip(
                    ("x", "y", "z"), row["camera_location_cm"], strict=True
                )
            ),
            "Fixed road camera location did not read back",
        )
        require(
            abs(float(component.get_editor_property("field_of_view")) - 76.0) <= 0.001,
            "Fixed road camera FOV differs",
        )
        self.api.AutomationLibrary.set_editor_viewport_view_mode(
            self.api.ViewModeIndex.VMI_LIT
        )
        if self.prime_index == 0:
            self.prepare_pose(row, eye, rotation)
        self.api.AutomationLibrary.finish_loading_before_screenshot()
        filename = (
            self.root / "priming" / f"{row['frame_id']}-{self.prime_index:02d}.png"
            if self.prime_index < PRIMING_FRAMES
            else self.root / "frames" / (row["frame_id"] + ".png")
        )
        self.pending_path = filename
        require(not filename.exists(), "Road review PNG already exists")
        self.task = self.api.AutomationLibrary.take_high_res_screenshot(
            res_x=RESOLUTION[0],
            res_y=RESOLUTION[1],
            filename=str(filename),
            camera=self.camera,
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=self.api.ComparisonTolerance.LOW,
            comparison_notes=(
                "YACS accepted window0112 road asphalt; technical capture, "
                "final owner visual pending"
            ),
            delay=0.0,
            force_game_view=True,
        )
        require(self.task is not None and self.task.is_valid_task(),
                "Unreal refused the native lit road screenshot task")
        self.submitted = time.monotonic()

    def tick(self, _delta):
        if self.stopped or self.busy:
            return
        if self.finish_requested_at is not None:
            # Let completed screenshot tasks, GPU/RHI and DDC work drain before
            # releasing the Python callback and requesting Editor shutdown.
            # No new camera pose/asset/save operation is submitted during this.
            if time.monotonic() - self.finish_requested_at >= 10.0:
                self.stop()
            return
        if self.task is None:
            return
        self.busy = True
        try:
            now = time.monotonic()
            require(
                now - self.started <= TOTAL_DEADLINE_SECONDS,
                "Road GPU capture exceeded its bounded total deadline",
            )
            require(
                now - self.submitted <= FRAME_DEADLINE_SECONDS,
                "Road GPU screenshot deadline exceeded",
            )
            if not self.task.is_task_done():
                return
            row = self.context["frames"][self.index]
            path = self.pending_path
            require(path is not None and path.exists(),
                    "Unreal screenshot task completed without PNG")
            if self.prime_index < PRIMING_FRAMES:
                decode_png(path, RESOLUTION)
                self.prime_evidence.append({
                    "file": path.relative_to(self.proof).as_posix(),
                    **session._identity(path, MAX_FRAME_BYTES),
                })
                self.completed_priming_frames += 1
                self.prime_index += 1
                self.task = None
                self.submit_pose()
                return
            require(len(self.prime_evidence) == PRIMING_FRAMES,
                    "Road pose did not complete all priming frames")
            info = frame_statistics(path)
            identity = session._identity(path, MAX_FRAME_BYTES)
            self.frames.append(
                {**row, "file": path.relative_to(self.proof).as_posix(),
                 **identity, **info, "render_mode": "lit",
                 "capture_readiness": self.pose_readiness,
                 "priming_frames": list(self.prime_evidence)}
            )
            self.prime_index = 0
            self.prime_evidence = []
            self.index += 1
            self.task = None
            if self.index == len(self.context["frames"]):
                self.finish_requested_at = time.monotonic()
            else:
                self.submit_pose()
        except Exception:
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
            except Exception as exc:
                errors.append("callback: " + str(exc))
        if self.camera is not None:
            try:
                actors = self.api.get_editor_subsystem(self.api.EditorActorSubsystem)
                require(actors.destroy_actor(self.camera) is not False,
                        "Cannot destroy transient road review camera")
            except Exception as exc:
                errors.append("camera: " + str(exc))
        if self.viewport_before is not None:
            try:
                viewport = self.api.get_editor_subsystem(self.api.UnrealEditorSubsystem)
                viewport.set_level_viewport_camera_info(*self.viewport_before)
                actual = viewport.get_level_viewport_camera_info()
                require(
                    all(
                        abs(float(getattr(actual[0], axis))
                            - float(getattr(self.viewport_before[0], axis))) <= 0.001
                        for axis in ("x", "y", "z")
                    ),
                    "Road review viewport restoration differs",
                )
            except Exception as exc:
                errors.append("viewport: " + str(exc))
        errors.extend(self.release_residency())
        context = self.context
        try:
            self.transient_dirty_audit = audit_transient_capture_dirty_packages(
                self.api
            )
        except Exception as exc:
            errors.append("dirty package ownership: " + str(exc))
        for label, action in (
            ("native scene", lambda: saved.expected_saved_inventory(
                context["original"]["native_inventory"],
                baseline.native_inventory(self.api, prep, saved.MAP),
                context["manifest"]["material_instance"],
                observed_map_package=saved.MAP,
            )),
            ("saved package hashes", lambda: saved.verify_retained_files(
                context["retained"], context["manifest"]["assets"]
            )),
            ("source assets", lambda: session._verify_rows(ROOT, context["rows"])),
            ("stage identity", lambda: require(
                session._identity(context["stage_path"], saved.JSON_LIMIT)
                == context["stage_identity"], "Accepted stage receipt changed"
            )),
            ("manifest", lambda: require(
                session._identity(
                    context["retained"] / saved.MANIFEST, saved.JSON_LIMIT
                ) == context["manifest_id"], "Retained saved manifest changed"
            )),
            ("prior proof", lambda: require(
                session._identity(
                    session._safe_path(self.proof, "saved-road-host-receipt.json")
                ) == context["host_receipt_identity"],
                "Original fresh reload host receipt changed"
            )),
        ):
            try:
                result = action()
                if label == "native scene":
                    require(
                        result == context["manifest"]["expected_normalized_inventory_sha256"],
                        "Road/support/Landscape snapshot differs after render",
                    )
            except Exception as exc:
                errors.append(label + ": " + str(exc))
        if len(self.frames) != len(context["frames"]):
            errors.append("Incomplete road-facing bidirectional render frames")
        if self.completed_priming_frames != len(context["frames"]) * PRIMING_FRAMES:
            errors.append("Incomplete per-pose priming sequence")
        receipt = {
            "schema_version": 1,
            "issue": 364,
            "status": (
                "ROAD_ASPHALT_LIT_REVIEW_FRAMES_RETAINED"
                if not errors else "ROAD_ASPHALT_LIT_REVIEW_FAILED"
            ),
            "exact_sha": context["exact_sha"],
            "run_token": context["run_token"],
            "map_package": saved.MAP,
            "saved_manifest_sha256": context["manifest_id"]["sha256"],
            "camera_csv_sha256": SURVEY_SHA256,
            "window": "0112",
            "view_authority": "accepted_bidirectional_tpp_source_camera",
            "frame_count": len(self.frames),
            "expected_frame_count": len(FRAME_IDS),
            "frames": self.frames,
            "errors": errors,
            "transient_camera_destroyed": not any(
                entry.startswith("camera:") for entry in errors
            ),
            "sources_and_saved_assets_unchanged": not errors,
            "transient_dirty_package_audit": self.transient_dirty_audit,
            "gpu_shutdown_quiescence_seconds": 10.0,
            "priming_frames_per_pose": PRIMING_FRAMES,
            "completed_priming_frames": self.completed_priming_frames,
            "residency_requests_released": self.residency_released,
            "capture_readiness_verified": not errors,
            "terrain_geometry_repaired": False,
            "native_lit_frames_retained": not errors,
            "gpu_shader_compilation_admitted": False,
            "road_pixel_visibility_admitted": False,
            "whole_area_visual_admitted": False,
            "shoulder_wall_materials_admitted": False,
            "owner_visual_status": "PENDING_FINAL_M3",
            "performance_status": "DEFERRED_AFTER_M3",
            "performance_pass": False,
        }
        try:
            saved.write_once(session._safe_path(self.proof, RECEIPT), receipt)
        finally:
            try:
                self.api.EditorPythonScripting.set_keep_python_script_alive(False)
            finally:
                self.api.SystemLibrary.quit_editor()


def main():
    import unreal

    context = authenticate_render_context()
    require(
        Path(unreal.Paths.convert_relative_path_to_full(
            unreal.Paths.project_dir()
        )).resolve() == ROOT
        and str(unreal.SystemLibrary.get_engine_version()).startswith("5.8.2-56702186"),
        "GPU render belongs to wrong Unreal source or engine",
    )
    baseline.dirty_packages(unreal)
    prep.assert_isolated_bootstrap(unreal)
    world = unreal.EditorLoadingAndSavingUtils.load_map(saved.MAP)
    require(world is not None, "Saved asphalt consumer did not load for lit render")
    inventories = baseline.native_inventory(unreal, prep, saved.MAP)
    digest = saved.expected_saved_inventory(
        context["original"]["native_inventory"],
        inventories,
        context["manifest"]["material_instance"],
        observed_map_package=saved.MAP,
    )
    require(
        digest == context["manifest"]["expected_normalized_inventory_sha256"],
        "GPU review loaded a different saved road material world",
    )
    saved.verify_material_instance(
        unreal,
        context["manifest"]["material_instance"],
        context["manifest"]["material_master"],
        context["manifest"]["texture_objects"],
    )
    landscape = list(unreal.GameplayStatics.get_all_actors_of_class(
        world, unreal.Landscape
    ))
    require(len(landscape) == 1, "GPU review requires exactly one saved Landscape")
    global ROAD_GPU_JOB
    ROAD_GPU_JOB = RoadLitCapture(unreal, context, world, landscape[0])
    ROAD_GPU_JOB.start()


if __name__ == "__main__":
    main()
