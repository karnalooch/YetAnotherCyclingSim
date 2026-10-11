"""Issue #364: pinned whole-network road views from a freshly saved consumer.

This is representative technical GPU review across the current area.
Final owner visual approval and exhaustive road-pixel visibility remain separate. The camera identities/poses come from an immutable
previously captured bidirectional road survey, never guessed free cameras.
An optional owned-process diagnostic then captures eight controls in the same
loop, temporarily swapping one road slot and restoring it before all audits.
No map or asset is saved.
"""

from __future__ import annotations

from copy import deepcopy
import csv
import hashlib
import io
import json
import math
import os
import re
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
from scripts.ue import road_asphalt_visual_controls as visual_controls  # noqa: E402
from scripts.ue import road_material_views as material_views  # noqa: E402
from scripts.ue import sa_calobra_whole_map_prep as prep  # noqa: E402
from scripts.ue.sa_calobra_detail_capture import decode_png  # noqa: E402
from scripts.ue.prepare_landscape_capture import (  # noqa: E402
    HEIGHT_MIP_LEASE_SECONDS,
    _height_texture_objects,
    prepare_capture,
)

SURVEY = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
RECEIPT = "road-asphalt-lit-review.json"
CONTROL_RECEIPT = "road-asphalt-visual-controls.json"
RESOLUTION = (1280, 720)
MAX_CSV_BYTES = 1024 * 1024
MAX_FRAME_BYTES = 16 * 1024 * 1024
# The authenticated plan expands four comparison views to 68 area views.
# Per-pose loading and three priming captures stay intact.
TOTAL_DEADLINE_SECONDS = 1080
# Native run 38090395135 completed one screenshot with a 98.964 s trace-to-save
# delay. Give the per-shot watchdog bounded recovery room within the unchanged
# total deadline; this is not the deferred owner performance acceptance gate.
FRAME_DEADLINE_SECONDS = 180
PRIMING_FRAMES = 3
EXPECTED_VIEW_PLAN = "road-asphalt-expected-view-plan.json"
CAMERA_FORWARD_TOLERANCE = 0.00001
CAPTURE_CONSOLE_NAMES = (
    "r.AntiAliasingMethod", "r.ScreenPercentage",
    "r.Editor.Viewport.ScreenPercentage",
    "r.Editor.Viewport.ScreenPercentageMode.RealTime",
    "r.Editor.Viewport.ScreenPercentageMode.NonRealTime",
    "r.DynamicRes.OperationMode", "r.TSR.ThinGeometryDetection",
    "r.TSR.History.ScreenPercentage", "r.HighResScreenshotDelay",
    "r.Test.FreezeTemporalSequences", "r.Test.FreezeTemporalHistories",
    "r.Test.CameraCut",
)


def capture_state_api_evidence(api):
    """Version-matched read-only getters, not a renderer/view-history probe.

    UE 5.8: SystemLibrary.get_frame_count returns GFrameCounter. Kismet's
    console string getter is also used by prep.console_value in this repo.
    https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SystemLibrary
    https://dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/Development/GetConsoleVariableStringValue
    """
    require(api.SystemLibrary.get_engine_version() == visual_controls.ENGINE_VERSION,
            "Capture state readback requires the pinned UE 5.8.2 build")
    methods = {}
    for name in ("get_console_variable_string_value", "get_frame_count"):
        method = getattr(api.SystemLibrary, name, None)
        doc = str(getattr(method, "__doc__", "") or "")
        require(callable(method) and 0 < len(doc) <= 32768,
                "Native capture state getter has no callable signature: " + name)
        methods["SystemLibrary." + name] = {
            "signature": doc.splitlines()[0], "doc_sha256": hashlib.sha256(doc.encode()).hexdigest()}
    return {"engine_version": visual_controls.ENGINE_VERSION, "reflected_methods": methods,
            "console_names": list(CAPTURE_CONSOLE_NAMES), "read_only": True,
            "effective_view_state_readback_available": False}


def native_capture_state(api):
    """Observe actual CVars and GFrameCounter without interpreting missing as zero."""
    values = {}
    for name in CAPTURE_CONSOLE_NAMES:
        raw = api.SystemLibrary.get_console_variable_string_value(name)
        require(isinstance(raw, str) and len(raw) <= 128,
                "Native capture console readback is not a bounded string: " + name)
        if not raw.strip():
            values[name] = {"status": "UNKNOWN", "raw": raw, "value": None}
        else:
            value = float(raw)
            require(math.isfinite(value), "Nonfinite capture console readback: " + name)
            values[name] = {"status": "OBSERVED", "raw": raw, "value": value}
    count = api.SystemLibrary.get_frame_count()
    require(type(count) is int and count >= 0, "Native frame counter is invalid")
    # A CVar is a configuration value, not FSceneView::AntiAliasingMethod.
    # GFrameCounter is not the screenshot's TSR history/sample counter either.
    return {"schema_version": 1, "frame_count": count, "cvars": values,
            "read_only": True, "console_overrides_applied": False,
            "effective_view_aa": None, "effective_screen_percentage": None,
            "temporal_history_observed": False}


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


def authenticated_view_plan(proof):
    """Authenticate host-selected source poses before opening the saved world."""
    path = session._safe_path(proof, EXPECTED_VIEW_PLAN)
    expected_sha = os.environ.get("YACS_ROAD_MATERIAL_VIEW_PLAN_SHA256", "")
    require(re.fullmatch(r"[0-9a-f]{64}", expected_sha), "Missing host camera-plan hash")
    identity = session._identity(path, MAX_CSV_BYTES)
    require(identity["sha256"] == expected_sha, "Expected camera-plan bytes changed")
    plan = session._read_json(path, limit=MAX_CSV_BYTES)
    require(plan == material_views.current_view_plan(ROOT),
            "Expected camera plan differs from authenticated whole-network source poses")
    require(session._identity(path, MAX_CSV_BYTES) == identity,
            "Expected camera plan changed during authentication")
    return plan, identity


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
    manifest_id = saved.verified_manifest_identity(proof, retained)
    manifest = session._read_json(manifest_path, limit=saved.JSON_LIMIT)
    profile_identity = saved.verified_profile_identity(proof, retained, manifest.get("road_profile_diagnostic"))
    outer_terrain = saved.outer_terrain_enabled()
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
        and prepare_receipt.get("evidence_manifest") == {"file": saved.MANIFEST, **manifest_id}
        and fresh_receipt.get("saved_manifest_sha256") == manifest_id["sha256"]
        and fresh_receipt.get("evidence_manifest_sha256") == manifest_id["sha256"]
        and fresh_receipt.get("status")
        == "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS"
        and fresh_receipt.get("fresh_process") is True
        and fresh_receipt.get("road_material_reapplied") is False
        and fresh_receipt.get("shoulder_material_reapplied") is False
        and fresh_receipt.get("shoulder_network_fresh_reload_verified") is True
        and fresh_receipt.get("shoulder_positions_indices_normals_original_uv_prefix_unchanged") is True
        and fresh_receipt.get("shoulder_material_edge_uv_fresh_reload_verified") is True
        and fresh_receipt.get("shoulder_support_count") == 186
        and fresh_receipt.get("shoulder_material_target_count") == 185
        and fresh_receipt.get("shoulder_selected_triangle_count")
        == manifest.get("shoulder_network", {}).get("selected_triangle_count")
        and fresh_receipt.get("road_full_buffers_unchanged") is True
        and fresh_receipt.get("dry_asphalt_response_verified") is True
        and fresh_receipt.get("road_profile_diagnostic_sha256") == profile_identity["sha256"]
        and manifest.get("status") == "SAVED_ROAD_ASPHALT_CONSUMER_PREPARED"
        and manifest.get("exact_sha") == exact_sha
        and manifest.get("staging_sha256") == staged_sha
        and manifest.get("map_package") == saved.MAP
        and manifest.get("road_slot_zero_only") is False
        and manifest.get("support_186_unchanged") is False
        and manifest.get("shoulder_network", {}).get("rollback_verified") is True
        and manifest.get("shoulder_network", {}).get("schema_version")
        == (saved.shoulder.OUTER_SCHEMA_VERSION if outer_terrain else saved.shoulder.SCHEMA_VERSION)
        and manifest.get("shoulder_network", {}).get("source_vertices_topology_normals_uv_prefix_preserved") is True
        and manifest.get("shoulder_network", {}).get("material_edge_uv_appended") is True
        and manifest.get("shoulder_network", {}).get("support_count") == 186
        and manifest.get("shoulder_network", {}).get("material_target_count") == 185
        and manifest.get("native_mesh_hash_format") == saved.shoulder.HASH_FORMAT
        and manifest.get("material_changes") == "road_slot_zero_network_outer_shoulder_ids_and_edge_uv"
        and manifest.get("landscape_1024_unchanged") is True
        and manifest.get("metric_tile_cm") == 400
        and manifest.get("performance_pass") is False,
        "Cannot render without the same exact-SHA native save and fresh-reload proof",
    )
    surface_modes, fresh_surface_readback = authenticate_surface_detail_proofs(
        host, prepare_receipt, fresh_receipt, manifest,
        edge_markings=saved.edge_markings_enabled(),
        crack_canary=saved.crack_canary_enabled(),
    )
    fresh_outer_readback = authenticate_outer_terrain_proofs(
        host, prepare_receipt, fresh_receipt, manifest, outer_terrain=outer_terrain)
    saved.verify_retained_files(retained, manifest["assets"])
    source = session._safe_path(ROOT, SURVEY)
    survey_identity = session._identity(source, MAX_CSV_BYTES)
    require(survey_identity["sha256"] == SURVEY_SHA256, "Road camera CSV pin differs")
    view_plan, view_plan_identity = authenticated_view_plan(proof)
    frames = view_plan["frames"]
    return {
        "exact_sha": exact_sha,
        "staging_sha256": staged_sha,
        "run_token": token,
        "proof": proof,
        "retained": retained,
        "manifest": manifest,
        "manifest_id": manifest_id,
        "surface_modes": surface_modes,
        "fresh_surface_readback": fresh_surface_readback,
        "outer_terrain_enabled": outer_terrain,
        "fresh_outer_terrain_readback": fresh_outer_readback,
        "profile_identity": profile_identity,
        "original": original,
        "rows": rows,
        "source_dependencies": stage["source_dependencies"],
        "terrain_consumer_assets": stage["consumer_assets"],
        "stage_path": stage_path,
        "stage_identity": stage_identity,
        "frames": frames,
        "view_plan": view_plan,
        "view_plan_identity": view_plan_identity,
        "survey_identity": survey_identity,
        "host_receipt_identity": session._identity(
            session._safe_path(proof, "saved-road-host-receipt.json")
        ),
    }


def authenticate_surface_detail_proofs(host, prepared, fresh, manifest, *, edge_markings, crack_canary):
    """Bind each optional lane to the preceding actual save/fresh processes."""
    saved._surface_modes(edge_markings, crack_canary)
    modes = {"edge_markings": edge_markings, "crack_canary": crack_canary}
    readbacks = {}
    for name, enabled in modes.items():
        key = name + "_enabled"
        require(all(row.get(key) is enabled for row in (manifest, prepared, fresh))
                and host.get(name + "_requested") is enabled
                and host.get(name + "_fresh_reload_verified") is enabled
                and fresh.get(name + "_fresh_reload_verified") is enabled,
                "Surface detail save/fresh/host modes differ: " + name)
        singular = "edge_marking" if name == "edge_markings" else "crack"
        require(fresh.get(singular + "_material_reapplied") is False
                and fresh.get(singular + "_geometry_reapplied") is False,
                "Surface detail was reapplied instead of freshly read: " + name)
        readback = fresh.get(singular + "_readback")
        if not enabled:
            require(name not in manifest and readback is None,
                    "Disabled surface detail lane contains a saved or read-back addition: " + name)
        else:
            require(isinstance(manifest.get(name), dict) and isinstance(readback, dict)
                    and readback.get("read_only") is True
                    and readback.get("owner_visual_pass") is False
                    and readback.get("performance_pass") is False,
                    "Surface detail has no native read-only fresh witness: " + name)
        readbacks[name] = readback
    if edge_markings:
        require(readbacks["edge_markings"].get("status") == "EDGE_MARKINGS_FRESH_READBACK_VERIFIED"
                and readbacks["edge_markings"].get("all_marking_buffers_verified") is True
                and readbacks["edge_markings"].get("full_source_buffers_preserved") is True,
                "Fresh white edge-marking buffers were not verified")
    if crack_canary:
        creation, result = manifest["crack_canary"], readbacks["crack_canary"]
        saved.crack_canary_inventory(creation)
        require(result.get("status") == "LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING"
                and result.get("plan_sha256") == creation.get("plan_sha256")
                and result.get("native_source_witness_sha256")
                == creation.get("source_correspondence", {}).get("native_source_witness_sha256")
                and result.get("actor_count") == 2
                and all(result.get(flag) is True for flag in (
                    "all_crack_buffers_verified", "full_source_and_existing_paint_buffers_preserved",
                    "caller_fresh_process_and_saved_bytes_required", "world_normal_canary_required"))
                and result.get("normal_space_verified") is False
                and host.get("crack_normal_space_verified") is False
                and readbacks["edge_markings"].get("aggregate_owner") == "local_crack_canary",
                "Fresh crack canary lacks the full native surface/paint witness and pending normal review")
    return modes, readbacks


def outer_binding_summary(manifest, readback):
    """Validate actual observations; renderer-specific counters are not bindings.

    Save/fresh use NullRHI. Keep their observed native counters in the receipt,
    without requiring those counts to equal a later SM6 GPU material resource.
    The separate GPU verifier must observe a real compiled material after the
    existing loading barrier; this function never grants that admission.
    """
    outer = saved.outer_terrain_receipt(manifest)
    require(outer is not None and isinstance(readback, dict), "Outer terrain has no native readback")
    statistics = readback.get("outer_native_statistics")
    names = set(saved.shoulder_material.STATISTICS_FIELDS)
    require(isinstance(statistics, dict) and set(statistics) == names
            and all(type(value) is int and 0 <= value <= 1000000 for value in statistics.values())
            and statistics["num_virtual_texture_samples"] == 0,
            "Outer terrain native statistics are missing or unbounded")
    terrain = outer["material"]["terrain_source"]
    expected = {
        "status": "SHOULDER_MATERIALS_NATIVE_READBACK_VERIFIED", "read_only": True,
        "base_instance": manifest["shoulder_network"]["material"]["assets"]["instance"],
        "outer_terrain_enabled": True, "outer_instance": outer["material"]["assets"]["instance"],
        "outer_owner_labels": list(saved.OUTER_TERRAIN_OWNER_LABELS),
        "outer_texture_objects": terrain["texture_objects"], "outer_native_statistics": statistics,
        "outer_gpu_compile_verified": False, "landscape_instance": terrain["instance"],
        "landscape_component_count": 1024, "outer_material_reapplied": False,
        "outer_geometry_reapplied": False, "physical_contact_verified": False,
        "normal_response_visual_verified": False, "owner_visual_pass": False, "performance_pass": False,
    }
    require(readback == expected and all(readback.get(name) is value for name, value in expected.items()
                                        if type(value) is bool),
            "Outer terrain native binding/authority readback differs")
    return {key: value for key, value in readback.items() if key != "outer_native_statistics"}


def authenticate_outer_terrain_proofs(host, prepared, fresh, manifest, *, outer_terrain):
    require(type(outer_terrain) is bool, "Outer terrain render mode must be an explicit boolean")
    require(all(row.get("outer_terrain_enabled") is outer_terrain for row in (manifest, prepared, fresh))
            and host.get("outer_terrain_requested") is outer_terrain
            and host.get("outer_terrain_fresh_reload_verified") is outer_terrain
            and fresh.get("outer_terrain_fresh_reload_verified") is outer_terrain,
            "Outer terrain save/fresh/host mode differs")
    require(fresh.get("outer_material_reapplied") is False and fresh.get("outer_geometry_reapplied") is False
            and host.get("outer_terrain_physical_contact_verified") is False
            and host.get("outer_terrain_normal_response_verified") is False,
            "Outer terrain was reapplied or received unsupported contact/normal admission")
    outer = saved.outer_terrain_receipt(manifest)
    readback = fresh.get("outer_terrain_readback")
    if outer_terrain:
        outer_binding_summary(manifest, readback)
        require(host.get("outer_terrain_owner_labels") == list(saved.OUTER_TERRAIN_OWNER_LABELS),
                "Outer terrain host selected another owner set")
    else:
        require(outer is None and readback is None and host.get("outer_terrain_owner_labels") == [],
                "Disabled outer terrain lane contains a native or authored addition")
    return readback


def material_texture_paths(manifest):
    """The same exact 7/15/18/26 objects for initial finish and per-pose residency."""
    material_paths = dict(manifest["texture_objects"])
    require(set(material_paths) == {"BaseColor", "Normal_DX", "ORM", "DetailMasks"}
            and len(set(material_paths.values())) == 4, "Expected four distinct authenticated road textures")
    gravel_paths = manifest["shoulder_network"]["material"]["texture_objects"]
    require(set(gravel_paths) == {"BaseColor", "Normal_DX", "Roughness"}
            and len(set(gravel_paths.values())) == 3, "Expected three authenticated shoulder textures")
    material_paths.update({"Shoulder_" + channel: path for channel, path in gravel_paths.items()})
    material_paths.update(crack_texture_paths(manifest))
    outer_paths = saved.outer_terrain_texture_paths(manifest)
    if outer_paths:
        names = [name for name in saved.shoulder_material.TERRAIN_PINS if name not in ("master", "instance")]
        require(len(outer_paths) == len(names) == 11, "Expected eleven frozen outer terrain textures")
        material_paths.update({"OuterTerrain_" + name: path for name, path in zip(names, outer_paths, strict=True)})
    require(len(material_paths) == len(set(material_paths.values())),
            "Distinct road, shoulder, crack and outer terrain channels share an unexpected asset")
    return material_paths


def finish_loaded_material_texture_compilation(api, manifest):
    """Finalize selected async texture builds before reading their GPU dimensions.

    Existing YacsTextureAuditLibrary.cpp calls FinishCompilation(Pending), then
    rejects default/still-compiling textures. It changes no import settings or
    source art and performs no GC. All original size/settings guards run next.
    """
    paths = material_texture_paths(manifest)
    textures = []
    for channel, path in sorted(paths.items()):
        texture = api.load_asset(path)
        require(isinstance(texture, api.Texture2D) and texture.get_path_name() == path,
                "Pinned material texture missing before native compilation finish: " + channel)
        textures.append(texture)
    require(api.YacsTextureAuditLibrary.finish_texture_compilation(textures) is True,
            "Selected loaded material textures did not finish native compilation")
    return {"status": "SELECTED_TEXTURE_COMPILATION_FINISHED",
            "native_api": "YacsTextureAuditLibrary.finish_texture_compilation",
            "texture_count": len(textures), "texture_objects": paths,
            "native_finished": True, "settings_changed": False, "source_assets_saved": False}


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


def crack_texture_paths(manifest):
    """Extend residency only with the eight already authenticated canary maps."""
    enabled = manifest.get("crack_canary_enabled", False)
    require(type(enabled) is bool, "Crack residency requires an explicit saved lane")
    if not enabled:
        require("crack_canary" not in manifest, "Disabled crack lane contains unexpected assets")
        return {}
    from scripts.ue import road_crack_sources

    receipt = manifest.get("crack_canary", {}).get("imports", {})
    source = receipt.get("sources", {})
    require(receipt.get("texture_count") == 8
            and source.get("selected_motifs") == list(road_crack_sources.CANARY_MOTIFS)
            and receipt.get("assets") == road_crack_sources.asset_paths(source),
            "Crack residency maps differ from the exact saved source selection")
    paths = {"Crack_" + motif + "_" + channel: path
             for motif, channels in receipt["assets"]["textures"].items()
             for channel, path in channels.items()}
    require(len(paths) == len(set(paths.values())) == 8,
            "Crack residency requires eight distinct native maps")
    return paths


class RoadLitCapture:
    def __init__(self, api, context, world, landscape):
        self.api = api
        self.context = context
        self.world, self.landscape = world, landscape
        self.proof = context["proof"]
        marker = os.environ.get(visual_controls.OWNED_ENV)
        crack_marker = os.environ.get("YACS_ROAD_CRACK_CONTROLS_OWNED")
        require(marker is None or marker == context.get("run_token"),
                "Visual control marker differs from the authenticated owned run")
        require(crack_marker is None or crack_marker == context.get("run_token"),
                "Crack control marker differs from the authenticated owned run")
        require(marker is None or crack_marker is None,
                "One owned diagnostic sequence may follow the original Lit captures")
        coverage_marker = os.environ.get(visual_controls.COVERAGE_OWNED_ENV)
        require(coverage_marker is None or (
            coverage_marker == context.get("run_token") and marker is not None
            and crack_marker is None and context.get("manifest", {}).get("edge_markings_enabled") is True),
            "Paint coverage requires its owned legacy control lane and saved white markings")
        self.paint_coverage_enabled = coverage_marker is not None
        self.control_module = visual_controls
        self.control_family = "road-asphalt"
        if crack_marker is not None:
            require(context["manifest"].get("crack_canary_enabled") is True,
                    "Crack controls require the explicitly saved crack canary")
            from scripts.ue import road_crack_visual_controls

            self.control_module = road_crack_visual_controls
            self.control_family = "road-crack"
        self.controls_enabled = marker is not None or crack_marker is not None
        self.control_plan = (visual_controls.control_plan(paint_coverage=True)
                             if self.paint_coverage_enabled else
                             self.control_module.control_plan() if self.controls_enabled else None)
        self.control_receipt_name = self.control_family + "-visual-controls.json"
        self.control_root = session._safe_path(self.proof, self.control_family + "-visual-controls")
        require(not self.controls_enabled or not self.control_root.exists(),
                "Visual control output already exists; no overwrite")
        self.root = session._safe_path(self.proof, "road-asphalt-lit-review")
        require(not self.root.exists(), "GPU review output already exists; no overwrite")
        self.root.mkdir(parents=True, exist_ok=False)
        (self.root / "frames").mkdir()
        (self.root / "priming").mkdir()
        if self.controls_enabled:
            self.control_root.mkdir(parents=True, exist_ok=False)
            (self.control_root / "frames").mkdir()
            (self.control_root / "priming").mkdir()
        self.phase = "lit"
        self.controls = None
        self.control_preflight = None
        self.control_begin = self.control_restore = None
        self.control_frames = []
        self.control_completed_priming_frames = 0
        self.control_max_completed_screenshot_seconds = 0.0
        self.pending_control_observation = None
        self.camera = None
        self.viewport_before = None
        self.handle = None
        self.task = None
        self.index = 0
        self.frames = []
        self.started = time.monotonic()
        self.submitted = None
        self.max_completed_screenshot_seconds = 0.0
        self.prime_index = 0
        self.prime_evidence = []
        self.completed_priming_frames = 0
        self.pending_path = None
        self.pending_camera_observation = None
        self.pending_viewmode_before = None
        self.pending_capture_state_before = None
        self.capture_state_api = None
        self.pose_readiness = None
        self.residency_leases = {}
        self.residency_released = False
        self.stopped = False
        self.busy = False
        self.finish_requested_at = None
        self.transient_dirty_audit = None
        self.edge_marking_readback = None
        self.outer_terrain_readback = None
        self.outer_gpu_statistics_before = None
        self.outer_gpu_statistics_after = None
        self.crack_readback = None

    def capture_row(self):
        if self.phase == "lit":
            return self.context["frames"][self.index]
        job = self.control_plan["jobs"][self.index]
        return {**job["camera"], "source_frame_id": job["camera"]["frame_id"],
                "frame_id": job["job_id"], "control_mode": job["control"]}

    def capture_root(self):
        return self.root if self.phase == "lit" else self.control_root

    def begin_controls(self):
        require(self.controls_enabled and self.controls is None
                and len(self.frames) == len(self.context["frames"]),
                "Visual controls require the completed original ordered Lit sequence")
        self.phase = "controls"
        self.index = 0
        self.controls = self.control_module.VisualControls(self.api, self.context)
        require(self.controls.plan == self.control_plan, "Diagnostic control plan changed")
        self.control_begin = self.controls.begin()
        require(self.control_preflight is not None and all(
            self.control_begin.get(key) == self.control_preflight.get(key) for key in ("ownership", "native_api")),
            "Diagnostic native API/owned context changed after the Lit sequence")
        self.submit_pose()

    def start(self):
        self.busy = True
        try:
            self.api.EditorPythonScripting.set_keep_python_script_alive(True)
            self.capture_state_api = capture_state_api_evidence(self.api)
            if self.controls_enabled:
                self.control_preflight = self.control_module.preflight(
                    self.api, self.context, self.control_plan)
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
        material_paths = material_texture_paths(self.context["manifest"])
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
        output = session._safe_path(self.capture_root(), "readiness/" + row["frame_id"])
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
        if self.context.get("outer_terrain_enabled", False) and self.outer_gpu_statistics_before is None:
            # Save/fresh-reopen use NullRHI. Observe actual GPU statistics only
            # after the existing native loading and full-mip barrier above.
            self.outer_gpu_statistics_before = self.read_outer_gpu_statistics()

    def read_outer_gpu_statistics(self):
        if not self.context.get("outer_terrain_enabled", False):
            return None
        outer = saved.outer_terrain_receipt(self.context["manifest"])
        require(outer is not None, "GPU outer mode has no authenticated material receipt")
        instance = self.api.load_asset(outer["material"]["assets"]["instance"])
        return saved.shoulder_material.verify_gpu_material_statistics(self.api, instance)

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
        row = self.capture_row()
        self.pending_camera_observation = None
        self.pending_control_observation = None
        self.pending_viewmode_before = None
        self.pending_capture_state_before = None
        eye = self.api.Vector(*row["camera_location_cm"])
        target = self.api.Vector(*row["target_cm"])
        rotation = self.api.MathLibrary.find_look_at_rotation(eye, target)
        self.camera.set_actor_location(eye, False, False)
        # UE 5.8 AActor exposes K2_SetActorRotation as SetActorRotation with a
        # bool success result; GetActorForwardVector returns its world-space X
        # direction. Verify both the setter and its actual result before each
        # prime/final capture, including after the native loading barrier.
        # https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/AActor
        require(self.camera.set_actor_rotation(rotation, False) is True,
                "Fixed road camera rotation setter rejected the requested pose")
        component = self.camera.get_component_by_class(self.api.CameraComponent)
        component.set_editor_property("field_of_view", row["fov_deg"])
        if self.phase == "lit":
            self.api.AutomationLibrary.set_editor_viewport_view_mode(
                self.api.ViewModeIndex.VMI_LIT
            )
        elif self.prime_index == 0:
            self.controls.apply(row["frame_id"])
        if self.prime_index == 0:
            self.prepare_pose(row, eye, rotation)
        self.api.AutomationLibrary.finish_loading_before_screenshot()
        if self.phase == "controls":
            self.pending_control_observation = self.controls.observe()
        location = self.camera.get_actor_location()
        actual = [float(getattr(location, axis)) for axis in ("x", "y", "z")]
        require(
            all(
                math.isfinite(value) and abs(value - number) <= 0.1
                for value, number in zip(actual, row["camera_location_cm"], strict=True)
            ),
            "Fixed road camera location did not read back",
        )
        fov = float(component.get_editor_property("field_of_view"))
        require(
            math.isfinite(fov) and abs(fov - row["fov_deg"]) <= 0.001,
            "Fixed road camera FOV differs",
        )
        observed = self.camera.get_actor_forward_vector()
        forward = [float(getattr(observed, axis)) for axis in ("x", "y", "z")]
        length = math.hypot(*forward)
        require(all(math.isfinite(value) for value in forward)
                and math.isfinite(length) and length > 0.0,
                "Fixed road camera forward vector is invalid")
        unit = [value / length for value in forward]
        expected = [target - eye for target, eye in zip(
            row["target_cm"], row["camera_location_cm"], strict=True)]
        distance = math.hypot(*expected)
        require(math.isfinite(distance) and distance > 0.0,
                "Pinned road camera look direction is invalid")
        forward_error = math.dist(unit, [value / distance for value in expected])
        require(forward_error <= CAMERA_FORWARD_TOLERANCE,
                "Fixed road camera forward direction differs from the pinned target")
        self.pending_camera_observation = {
            "rotation_setter_accepted": True,
            "location_cm": actual,
            "forward_unit": unit,
            "fov_deg": fov,
            "forward_error": forward_error,
        }
        filename = (
            self.capture_root() / "priming" / f"{row['frame_id']}-{self.prime_index:02d}.png"
            if self.prime_index < PRIMING_FRAMES
            else self.capture_root() / "frames" / (row["frame_id"] + ".png")
        )
        self.pending_path = filename
        require(not filename.exists(), "Road review PNG already exists")
        self.pending_viewmode_before = self.observe_viewmode()
        if self.capture_state_api is None:
            self.capture_state_api = capture_state_api_evidence(self.api)
        self.pending_capture_state_before = native_capture_state(self.api)
        self.task = self.api.AutomationLibrary.take_high_res_screenshot(
            res_x=RESOLUTION[0],
            res_y=RESOLUTION[1],
            filename=str(filename),
            camera=self.camera,
            mask_enabled=False,
            capture_hdr=False,
            comparison_tolerance=self.api.ComparisonTolerance.LOW,
            comparison_notes=(
                "YACS current road network asphalt and gravel; technical capture, "
                "final owner visual pending"
                if self.phase == "lit" else
                "YACS road band diagnostic; " + row["control_mode"] + "; no visual acceptance"
            ),
            delay=0.0,
            force_game_view=True,
        )
        require(self.task is not None and self.task.is_valid_task(),
                "Unreal refused the native lit road screenshot task")
        self.submitted = time.monotonic()

    def observe_viewmode(self):
        name = (
            "VMI_VISUALIZE_BUFFER"
            if self.phase == "controls"
            and self.capture_row()["control_mode"] in self.control_module.BUFFERS
            else "VMI_LIT"
        )
        actual = self.api.AutomationLibrary.get_editor_active_viewport_view_mode()
        require(actual == getattr(self.api.ViewModeIndex, name),
                "Native viewport viewmode differs from the requested capture mode")
        return name

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
            elapsed = now - self.submitted
            require(
                elapsed <= FRAME_DEADLINE_SECONDS,
                "Road GPU screenshot deadline exceeded "
                f"({elapsed:.3f}s > {FRAME_DEADLINE_SECONDS}s)",
            )
            if not self.task.is_task_done():
                return
            # Monotonic submission-to-first-observed-completion latency, not a
            # GPU-only timing. The deadline must precede even a completed task.
            if self.phase == "lit":
                self.max_completed_screenshot_seconds = max(self.max_completed_screenshot_seconds, elapsed)
            else:
                self.control_max_completed_screenshot_seconds = max(
                    self.control_max_completed_screenshot_seconds, elapsed)
            row = self.capture_row()
            control_observations = {}
            if self.phase == "controls":
                control_observations = {
                    "native_control_observation_before": self.pending_control_observation,
                    "native_control_observation_after": self.controls.observe(),
                }
                require(control_observations["native_control_observation_before"]
                        == control_observations["native_control_observation_after"],
                        "Diagnostic material/viewmode changed during the native screenshot")
            viewmode_observations = {
                "native_viewmode_before": self.pending_viewmode_before,
                "native_viewmode_after": self.observe_viewmode(),
            }
            require(viewmode_observations["native_viewmode_before"]
                    == viewmode_observations["native_viewmode_after"],
                    "Native viewport viewmode changed during the screenshot")
            capture_state_after = native_capture_state(self.api)
            require(self.pending_capture_state_before is not None
                    and capture_state_after["frame_count"] >= self.pending_capture_state_before["frame_count"],
                    "Native frame counter regressed during the screenshot")
            capture_states = {
                "native_capture_state_before": self.pending_capture_state_before,
                "native_capture_state_after": capture_state_after,
                "capture_cvars_unchanged": (self.pending_capture_state_before["cvars"]
                                            == capture_state_after["cvars"]),
            }
            path = self.pending_path
            require(path is not None and path.exists(),
                    "Unreal screenshot task completed without PNG")
            if self.prime_index < PRIMING_FRAMES:
                decode_png(path, RESOLUTION)
                self.prime_evidence.append({
                    "file": path.relative_to(self.proof).as_posix(),
                    **session._identity(path, MAX_FRAME_BYTES),
                    "native_camera_observation": self.pending_camera_observation,
                    "screenshot_elapsed_seconds": elapsed,
                    **viewmode_observations,
                    **capture_states,
                    **control_observations,
                })
                if self.phase == "lit":
                    self.completed_priming_frames += 1
                else:
                    self.control_completed_priming_frames += 1
                self.prime_index += 1
                self.task = None
                self.submit_pose()
                return
            require(len(self.prime_evidence) == PRIMING_FRAMES,
                    "Road pose did not complete all priming frames")
            info = frame_statistics(path)
            identity = session._identity(path, MAX_FRAME_BYTES)
            completed_frames = self.frames if self.phase == "lit" else self.control_frames
            render_mode = "buffer_visualization" if row.get("control_mode") in self.control_module.BUFFERS else "lit"
            completed_frames.append(
                {**row, "file": path.relative_to(self.proof).as_posix(),
                 **identity, **info, "render_mode": render_mode,
                 "native_camera_observation": self.pending_camera_observation,
                 "screenshot_elapsed_seconds": elapsed,
                 "capture_readiness": self.pose_readiness,
                 "priming_frames": list(self.prime_evidence),
                 **viewmode_observations, **capture_states, **control_observations}
            )
            self.prime_index = 0
            self.prime_evidence = []
            self.index += 1
            self.task = None
            phase_count = len(self.context["frames"]) if self.phase == "lit" else self.control_plan["frame_count"]
            if self.index == phase_count:
                if self.phase == "lit" and self.controls_enabled:
                    self.begin_controls()
                else:
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
        # A failed debug channel does not rewrite a completed Lit sequence.
        # Shared restoration/conservation failures still fail both receipts.
        errors = [error] if error and self.phase == "lit" else []
        control_errors = [error] if error and self.phase == "controls" else []
        if self.handle is not None:
            try:
                self.api.unregister_slate_post_tick_callback(self.handle)
            except Exception as exc:
                errors.append("callback: " + str(exc))
        if self.controls is not None:
            try:
                self.control_restore = self.controls.restore()
            except Exception as exc:
                self.control_restore = deepcopy(self.controls.report)
                errors.append("visual control restoration: " + str(exc))
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
                shoulder_receipt=context["manifest"]["shoulder_network"],
                edge_marking_receipt=context["manifest"].get("edge_markings"),
                crack_canary_receipt=context["manifest"].get("crack_canary"),
            )),
            ("road surface details", lambda: saved.verify_surface_details(
                self.api, context["manifest"],
                context["manifest"].get("edge_markings_enabled", False),
                context["manifest"].get("crack_canary_enabled", False),
            )),
            ("shoulder native mesh", lambda: saved.shoulder.verify_loaded(
                self.api, context["manifest"]["shoulder_network"], context["source_plan"]
            )),
            ("shoulder material", lambda: saved.verify_shoulder_materials(
                self.api, context["manifest"], context["source_dependencies"], context["terrain_consumer_assets"]
            )),
            ("outer terrain GPU statistics", self.read_outer_gpu_statistics),
            ("road full buffers", lambda: saved.verify_road_mesh(
                self.api, context["manifest"]["road_mesh"]
            )),
            ("dry asphalt response", lambda: saved.verify_material_instance(
                self.api, context["manifest"]["material_instance"],
                context["manifest"]["material_master"], context["manifest"]["texture_objects"],
                expected_response=context["manifest"]["dry_asphalt_response"],
            )),
            ("camera plan", lambda: require(
                session._identity(session._safe_path(self.proof, EXPECTED_VIEW_PLAN), MAX_CSV_BYTES)
                == context["view_plan_identity"], "Expected whole-network camera plan changed"
            )),
            ("saved package hashes", lambda: saved.verify_retained_files(
                context["retained"], context["manifest"]["assets"]
            )),
            ("frozen profile diagnostic", lambda: saved.verified_profile_identity(
                self.proof, context["retained"], context["profile_identity"]
            )),
            ("source assets", lambda: session._verify_rows(ROOT, context["rows"])),
            ("stage identity", lambda: require(
                session._identity(context["stage_path"], saved.JSON_LIMIT)
                == context["stage_identity"], "Accepted stage receipt changed"
            )),
            ("manifest", lambda: require(
                saved.verified_manifest_identity(self.proof, context["retained"])
                == context["manifest_id"], "Retained/downloadable saved manifest changed"
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
                elif label == "road surface details":
                    require(result == {"edge_markings": context.get("edge_marking_readback"),
                                       "crack_canary": context.get("crack_readback")},
                            "Road white/crack readback changed during render")
                    self.edge_marking_readback = result["edge_markings"]
                    self.crack_readback = result["crack_canary"]
                elif label == "shoulder material":
                    if context.get("outer_terrain_enabled", False):
                        self.outer_terrain_readback = result
                        require(outer_binding_summary(context["manifest"], result)
                                == outer_binding_summary(context["manifest"], context["outer_terrain_readback"]),
                                "Outer terrain bindings changed during the GPU review")
                    else:
                        require(result == context["shoulder_material_readback"],
                                "Base shoulder material readback changed during the GPU review")
                elif label == "outer terrain GPU statistics":
                    self.outer_gpu_statistics_after = result
                    require(result == self.outer_gpu_statistics_before
                            and (not context.get("outer_terrain_enabled", False) or isinstance(result, dict)),
                            "Outer terrain GPU statistics changed or have no post-readiness observation")
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
            "road_profile_diagnostic_sha256": context["profile_identity"]["sha256"],
            "camera_csv_sha256": SURVEY_SHA256,
            "view_plan_sha256": context["view_plan_identity"]["sha256"],
            "material_view_sampling": {k: v for k, v in context["view_plan"].items() if k != "frames"},
            "view_authority": "accepted_bidirectional_tpp_source_camera",
            "frame_count": len(self.frames),
            "expected_frame_count": len(context["frames"]),
            "frames": self.frames,
            "errors": errors,
            "transient_camera_destroyed": not any(
                entry.startswith("camera:") for entry in errors
            ),
            "sources_and_saved_assets_unchanged": not errors,
            "transient_dirty_package_audit": self.transient_dirty_audit,
            "gpu_shutdown_quiescence_seconds": 10.0,
            "frame_deadline_seconds": FRAME_DEADLINE_SECONDS,
            "max_completed_screenshot_seconds": self.max_completed_screenshot_seconds,
            "priming_frames_per_pose": PRIMING_FRAMES,
            "completed_priming_frames": self.completed_priming_frames,
            "residency_requests_released": self.residency_released,
            "capture_readiness_verified": not errors,
            "capture_state_native_api": self.capture_state_api,
            "loaded_material_texture_compilation": context.get("loaded_material_texture_compilation"),
            "terrain_geometry_repaired": False,
            "native_lit_frames_retained": not errors,
            "gpu_shader_compilation_admitted": False,
            "road_pixel_visibility_admitted": False,
            "whole_area_visual_admitted": False,
            "shoulder_wall_materials_admitted": False,
            "shoulder_network_material_ids_verified": not errors,
            "shoulder_material_edge_uv_verified": not errors,
            "shoulder_support_count": context["manifest"]["shoulder_network"]["support_count"],
            "shoulder_material_target_count": context["manifest"]["shoulder_network"]["material_target_count"],
            "shoulder_selected_triangle_count": context["manifest"]["shoulder_network"]["selected_triangle_count"],
            "shoulder_wall_materials_unchanged": not errors,
            "road_full_buffers_unchanged": not errors,
            "dry_asphalt_response_verified": not errors,
            "edge_markings_enabled": context["manifest"].get("edge_markings_enabled", False),
            "edge_markings_before": context.get("edge_marking_readback"),
            "edge_markings_after": self.edge_marking_readback,
            "crack_canary_enabled": context["manifest"].get("crack_canary_enabled", False),
            "crack_before": context.get("crack_readback"),
            "crack_after": self.crack_readback,
            "crack_normal_space_verified": False,
            "outer_terrain_enabled": context.get("outer_terrain_enabled", False),
            "outer_terrain_before": context.get("outer_terrain_readback"),
            "outer_terrain_after": self.outer_terrain_readback,
            "outer_gpu_statistics_before": self.outer_gpu_statistics_before,
            "outer_gpu_statistics_after": self.outer_gpu_statistics_after,
            "outer_terrain_native_bindings_verified": not errors and context.get("outer_terrain_enabled", False),
            "outer_terrain_gpu_statistics_verified": not errors and context.get("outer_terrain_enabled", False),
            "outer_terrain_physical_contact_verified": False,
            "outer_terrain_normal_response_verified": False,
            "exhaustive_road_pixel_visibility": False,
            "whole_area_owner_accepted": False,
            "owner_visual_status": "PENDING_FINAL_M3",
            "performance_status": "DEFERRED_AFTER_M3",
            "performance_pass": False,
        }
        try:
            lit_identity = saved.write_once(session._safe_path(self.proof, RECEIPT), receipt)
            if self.controls_enabled:
                control_receipt = self.visual_control_receipt(errors + control_errors, lit_identity)
                saved.write_once(session._safe_path(self.proof, self.control_receipt_name), control_receipt)
        finally:
            # Release the -ExecutePythonScript lifecycle after proof and cleanup.
            # The host still requires an observed zero process exit.
            self.api.EditorPythonScripting.set_keep_python_script_alive(False)

    def visual_control_receipt(self, shared_errors, lit_identity):
        errors = list(shared_errors)
        if len(self.control_frames) != self.control_plan["frame_count"]:
            errors.append("Incomplete fixed road control sequence")
        if self.control_completed_priming_frames != self.control_plan["frame_count"] * PRIMING_FRAMES:
            errors.append("Incomplete control priming sequence")
        if [row.get("frame_id") for row in self.control_frames] != [
                row["job_id"] for row in self.control_plan["jobs"]]:
            errors.append("Control frames differ from the fixed ordered diagnostic plan")
        if self.control_begin is None or self.control_begin.get("status") != "READY":
            errors.append("Visual control native preflight/begin did not complete")
        restoration = self.control_restore or {}
        restoration_flags = (
            "original_material_restored", "owned_viewports_returned_to_lit",
            "saved_and_staged_package_bytes_unchanged")
        if self.control_family == "road-crack":
            restoration_flags += (
                "original_visibility_restored", "original_mic_probe_values_zero",
                "transient_mids_detached", "transient_mid_refs_released")
        if self.paint_coverage_enabled:
            restoration_flags += (
                "paint_bindings_restored", "paint_original_mic_parameters_unchanged",
                "paint_transient_mid_detached", "paint_transient_mid_ref_released")
        restored = (
            restoration.get("status") == "RESTORED"
            and restoration.get("cleanup_errors") == []
            and all(restoration.get(name) is True for name in restoration_flags)
            and (self.control_family != "road-crack" and not self.paint_coverage_enabled
                 or type(restoration.get("dirty_content_count")) is int
                 and restoration["dirty_content_count"] == 0)
        )
        if not restored:
            errors.append("Visual control restoration did not complete cleanly")
        context = self.context
        receipt = {
            "schema_version": 1, "issue": 364,
            "status": (self.control_family.upper().replace("-", "_")
                       + ("_VISUAL_CONTROLS_FRAMES_RETAINED" if not errors else "_VISUAL_CONTROLS_FAILED")),
            "exact_sha": context["exact_sha"], "run_token": context["run_token"],
            "map_package": saved.MAP, "saved_manifest_sha256": context["manifest_id"]["sha256"],
            "camera_csv_sha256": SURVEY_SHA256,
            "view_plan_sha256": context["view_plan_identity"]["sha256"],
            "lit_review_receipt": {"file": RECEIPT, **lit_identity},
            "control_plan": self.control_plan,
            "control_plan_sha256": self.control_module.digest(self.control_plan),
            "preflight": self.control_preflight, "begin": self.control_begin, "restore": self.control_restore,
            "frame_count": len(self.control_frames),
            "expected_frame_count": self.control_plan["frame_count"],
            "frames": self.control_frames, "errors": errors,
            "priming_frames_per_pose": PRIMING_FRAMES,
            "completed_priming_frames": self.control_completed_priming_frames,
            "frame_deadline_seconds": FRAME_DEADLINE_SECONDS,
            "total_deadline_seconds_shared_with_lit": TOTAL_DEADLINE_SECONDS,
            "max_completed_screenshot_seconds": self.control_max_completed_screenshot_seconds,
            "control_restoration_verified": restored,
            "capture_readiness_verified": not errors,
            "capture_state_native_api": self.capture_state_api,
            "native_control_observations_verified": not errors,
            "sources_and_saved_assets_unchanged": not errors,
            "native_channel_images_reviewed": False,
            "buffer_name_readback_verified": False,
            "geometry_or_source_texture_change": False, "map_saved": False,
            "source_assets_saved": False, "whole_area_visual_admitted": False,
            "owner_visual_status": "PENDING_FINAL_M3", "performance_status": "DEFERRED_AFTER_M3",
            "performance_pass": False,
        }
        if self.control_family == "road-crack":
            receipt["world_normal_canary_required"] = True
            receipt["normal_space_verified"] = False
        if self.paint_coverage_enabled:
            legacy = visual_controls.control_plan()
            receipt.update(
                paint_coverage_enabled=True, legacy_control_plan=legacy,
                legacy_control_plan_sha256=visual_controls.digest(legacy),
                paint_coverage_frame_count=sum(row.get("control_mode") in visual_controls.COVERAGE_CONTROLS
                                              for row in self.control_frames),
                paint_full_native_buffers_verified=(not errors and isinstance(self.edge_marking_readback, dict)
                    and self.edge_marking_readback.get("all_marking_buffers_verified") is True
                    and self.edge_marking_readback.get("full_source_buffers_preserved") is True
                    and self.edge_marking_readback.get("actor_count") == visual_controls.PAINT_COUNT
                    and self.edge_marking_readback == context.get("edge_marking_readback")),
                paint_pixel_aliasing_cause_verified=False,
            )
        return receipt


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
    context["loaded_material_texture_compilation"] = finish_loaded_material_texture_compilation(
        unreal, context["manifest"])
    details = saved.verify_surface_details(
        unreal, context["manifest"], **context["surface_modes"])
    require(details == context["fresh_surface_readback"],
            "GPU surface details differ from the authenticated fresh-process readback")
    context["edge_marking_readback"] = details["edge_markings"]
    context["crack_readback"] = details["crack_canary"]
    inventories = baseline.native_inventory(unreal, prep, saved.MAP)
    digest = saved.expected_saved_inventory(
        context["original"]["native_inventory"],
        inventories,
        context["manifest"]["material_instance"],
        observed_map_package=saved.MAP,
        shoulder_receipt=context["manifest"]["shoulder_network"],
        edge_marking_receipt=context["manifest"].get("edge_markings"),
        crack_canary_receipt=context["manifest"].get("crack_canary"),
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
        expected_response=context["manifest"]["dry_asphalt_response"],
    )
    shoulder_readback = saved.verify_shoulder_materials(
        unreal, context["manifest"], context["source_dependencies"], context["terrain_consumer_assets"])
    context["shoulder_material_readback"] = shoulder_readback
    context["outer_terrain_readback"] = shoulder_readback if context["outer_terrain_enabled"] else None
    if context["outer_terrain_enabled"]:
        require(outer_binding_summary(context["manifest"], shoulder_readback)
                == outer_binding_summary(context["manifest"], context["fresh_outer_terrain_readback"]),
                "GPU outer terrain bindings differ from the actual fresh-process readback")
    context["source_plan"] = saved.shoulder_sources.load_sources()
    saved.shoulder.verify_loaded(unreal, context["manifest"]["shoulder_network"], context["source_plan"])
    saved.verify_road_mesh(unreal, context["manifest"]["road_mesh"])
    landscape = list(unreal.GameplayStatics.get_all_actors_of_class(
        world, unreal.Landscape
    ))
    require(len(landscape) == 1, "GPU review requires exactly one saved Landscape")
    global ROAD_GPU_JOB
    ROAD_GPU_JOB = RoadLitCapture(unreal, context, world, landscape[0])
    ROAD_GPU_JOB.start()


if __name__ == "__main__":
    main()
