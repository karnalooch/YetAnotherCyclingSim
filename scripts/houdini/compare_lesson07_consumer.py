"""Compare saved L07 BGEO tiles with the native UE seam receipt, without cooking.

Run with the installed Houdini Python interpreter under host ownership:
    hython -B compare_lesson07_consumer.py --ue-report receipt.json --output new.json

Only hou.Geometry.loadFromFile / Volume read APIs are used. No HIP, SOP, actor,
asset, input cache or receipt is modified. Output must be a new file.

References:
https://www.sidefx.com/docs/houdini/hom/hou/Volume.html
HoudiniLandscapeUtils.cpp: ConvertHeightFieldData, QuantizeNormalizedDataTo16Bit
HoudiniLandscapeTranslator.cpp: visibility -> uint8 -> TAlphamapAccessor
UE 5.8 LandscapeDataAccess.h: GetLocalHeight
"""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import struct


DEFAULT_MANIFEST = Path(
    "D:/yacs/work/lesson07-native-proof-39390349735-1/manifest.json"
)
MANIFEST_SHA256 = "66847b4a614e748a0012dcefabbc6f2be9b0326f0a863714e690cb71c068a8f6"
SOURCE_SHA256 = "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24"
ACTORS = {f"SaCalobra_Unified_{x}_{y}" for x in range(2) for y in range(2)}
LEVEL = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
COLUMNS = [
    "height_u16", "world_x_cm", "world_y_cm", "world_z_cm", "visibility_u8"
]
INTERIOR_SOURCE_BOUNDS_M = [-3999.75, 3999.75]
INTERIOR_BUFFER_VERTICES = 3
INTERIOR_PER_CLASS_PER_ACTOR = 3


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"Expected finite number, got {value!r}")
    return float(value)


def unsigned(value, maximum):
    result = finite(value)
    if not result.is_integer() or not 0 <= result <= maximum:
        raise ValueError(f"Expected unsigned integer <= {maximum}, got {value!r}")
    return int(result)


def float32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def quantization_model(height_m, scale_z, location_z_cm):
    """Diagnostic reproduction of the installed non-fused float32 conversion.

    Code equality is an observation, not an acceptance standard. A fused
    compiler operation can differ at a truncation boundary. The real-arithmetic
    interval exposes the 65535-versus-65536 and truncation biases; it excludes
    floating-point roundoff, registration error and extra edit-layer blending.
    """
    height_m, scale_z, location_z_cm = map(
        finite, (height_m, scale_z, location_z_cm)
    )
    if scale_z <= 0:
        raise ValueError("Scale.Z must be positive")
    step_cm = scale_z / 128.0
    half_range_cm = float32(float32(scale_z) * 256.0)
    factor = float32(float32(100.0 / half_range_cm) * 0.5)
    aligned = float32(float32(float32(height_m) * factor) + 0.5)
    clamped = min(1.0, max(0.0, aligned))
    code = int(float32(clamped * 65535.0))
    bias_cm = location_z_cm - height_m * 100.0 / 65536.0
    return {
        "height_step_cm": step_cm,
        "predicted_height_u16_non_fused_float32": code,
        "predicted_world_z_cm": location_z_cm + (code - 32768) * step_cm,
        "clipping_in_model": clamped != aligned,
        "unrotated_real_arithmetic_residual_interval_cm": [
            bias_cm - 1.5 * step_cm, bias_cm - 0.5 * step_cm
        ],
    }


def world_z_at_xy(code, actor, x_cm, y_cm):
    """Apply the observed UE Rotator, including the retained tiny roll.

    Basis rows follow UE Core/Math/RotationTranslationMatrix.h. Solve the two
    horizontal equations for local scaled XY; then evaluate world Z. This is
    a diagnostic transform, not a change to the native terrain or a tolerance.
    """
    pitch, yaw, roll = map(math.radians, actor["rotation_deg_pitch_yaw_roll"])
    sp, cp, sy, cy, sr, cr = (
        math.sin(pitch), math.cos(pitch), math.sin(yaw), math.cos(yaw),
        math.sin(roll), math.cos(roll),
    )
    bx = (cp * cy, cp * sy, sp)
    by = (sr * sp * cy - cr * sy, sr * sp * sy + cr * cy, -sr * cp)
    bz = (-(cr * sp * cy + sr * sy), cy * sr - cr * sp * sy, cr * cp)
    local_z = (code - 32768) * actor["scale"][2] / 128.0
    dx = x_cm - actor["location_cm"][0] - bz[0] * local_z
    dy = y_cm - actor["location_cm"][1] - bz[1] * local_z
    determinant = bx[0] * by[1] - bx[1] * by[0]
    if determinant == 0:
        raise ValueError("Landscape rotation has a singular XY projection")
    local_x = (dx * by[1] - dy * by[0]) / determinant
    local_y = (bx[0] * dy - bx[1] * dx) / determinant
    return (
        actor["location_cm"][2] + bx[2] * local_x + by[2] * local_y + bz[2] * local_z
    )


def readback_validator():
    """Reuse the existing reader's admission rules without importing Unreal."""
    source = Path(__file__).resolve().parents[1] / "ue/readback_lesson07_geometry.py"
    spec = importlib.util.spec_from_file_location("lesson07_readback_admission", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_native_map(report, report_path):
    """Authenticate original bytes or the exact saved repair chain, never a flag."""
    reader = readback_validator()
    before, after = report.get("map_before"), report.get("map_after")
    if (report.get("candidate_map_unchanged") is not True or before != after
            or report.get("geometry_accepted") is not False
            or re.fullmatch(r"[0-9a-f]{40}", str(report.get("source_head"))) is None):
        raise ValueError("Native report does not preserve a measured, unaccepted map identity")
    identity = reader.map_identity_pair(before)
    project = reader.plain_path(report["project_root"])
    if reader.plain_path(before["path"]) != project / reader.MAP_FILE:
        raise ValueError("Native map belongs to another project/package")
    repaired = report.get("repair_receipts_authenticated") is True
    if identity == (reader.ORIGINAL_MAP_SHA256, reader.ORIGINAL_MAP_SIZE):
        if repaired or report.get("map_lineage", {}).get("repair_receipts"):
            raise ValueError("Original map cannot claim a repaired lineage")
        return
    if not repaired and identity != (reader.MAP_SHA256, reader.MAP_SIZE):
        raise ValueError("Changed map requires an authenticated repair lineage")
    reference = report.get("preparation_identity")
    if not isinstance(reference, dict):
        raise ValueError("Current/repaired report omits its authenticated staging receipt")
    reader.file_identity(reference["path"], 8 * 1024**2)
    preparation = reader.read_repair_receipt(reference)
    if (preparation.get("schema_version") != 1
            or preparation.get("status") != (reader.REPAIRED_PREPARATION_STATUS if repaired
                                             else "L07_COPIED_BYTES_NATIVE_READ_PENDING")
            or preparation.get("source_head") != report["source_head"]
            or preparation.get("level") != LEVEL
            or reader.plain_path(preparation["candidate_root"]) != project
            or reader.plain_path(preparation["report_path"]) != reader.plain_path(report_path)
            or preparation.get("map") != report.get("map_lineage")
            or preparation.get("geometry_accepted") is not False
            or preparation.get("dependency_closure_complete") is not False):
        raise ValueError("Current/repaired report differs from its staged task/map/lineage")
    actual_reader = reader.file_identity(reader.__file__, 256 * 1024)
    if actual_reader["sha256"] != preparation["reader_identity"]["sha256"]:
        raise ValueError("Repair admission reader bytes differ from staged provenance")
    current = reader.file_identity(project / reader.MAP_FILE, 3 * 1024**3)
    if current != before:
        raise ValueError("Repaired map changed since native readback")
    if repaired:
        reader.authenticated_repaired_map(project, preparation, current)
    else:
        reader.authenticated_current_map(project, preparation, current)


def projected_grid_xy(actor, grid_x, grid_y):
    """Observed UE Rotator basis at local Z=0, used only to select source voxels."""
    pitch, yaw, roll = map(math.radians, actor["rotation_deg_pitch_yaw_roll"])
    sp, cp, sy, cy, sr, cr = (
        math.sin(pitch), math.cos(pitch), math.sin(yaw), math.cos(yaw),
        math.sin(roll), math.cos(roll),
    )
    x, y = grid_x * actor["scale"][0], grid_y * actor["scale"][1]
    return [actor["location_cm"][0] + cp * cy * x + (sr * sp * cy - cr * sy) * y,
            actor["location_cm"][1] + cp * sy * x + (sr * sp * sy + cr * cy) * y]


def interior_candidate(height, validity, actor, layout):
    fields = layout["fields"]
    if (not layout.get("observed") or
            [fields[k] for k in ("component_size_quads", "subsection_size_quads", "num_subsections")]
            != [254, 127, 2]):
        raise ValueError("Interior selection requires the observed original component lattice")
    x0, y0 = fields["section_base_x"] + 127, fields["section_base_y"] + 127
    patch, corners = [], {}
    # A full 8x8 uniform patch surrounds the central quad by three source-grid
    # intervals. This is sample selection, never a geometry acceptance tolerance.
    for dy in range(-INTERIOR_BUFFER_VERTICES, 2 + INTERIOR_BUFFER_VERTICES):
        for dx in range(-INTERIOR_BUFFER_VERTICES, 2 + INTERIOR_BUFFER_VERTICES):
            xy = projected_grid_xy(actor, x0 + dx, y0 + dy)
            row = volume_observation(height, validity, *xy)
            px, _, pz = row["source_voxel_center_houdini_m"]
            lo, hi = INTERIOR_SOURCE_BOUNDS_M
            if not (lo <= px <= hi and lo <= pz <= hi):
                return None, "outside_original_source_rectangle"
            patch.append(row["source_validity"])
            if dx in (0, 1) and dy in (0, 1):
                corners[(dx, dy)] = row
    if len(set(patch)) != 1:
        return None, "mixed_source_validity_patch"
    return {
        "actor": actor["name"], "component_path": layout["component_path"],
        "component_section_base": [fields["section_base_x"], fields["section_base_y"]],
        "local_vertex_indices": [127 * 255 + 127, 127 * 255 + 128,
                                 128 * 255 + 127, 128 * 255 + 128],
        "source_validity": patch[0], "uniform_source_patch_samples": len(patch),
        "source_corners": [corners[key] for key in ((0, 0), (1, 0), (0, 1), (1, 1))],
    }, None


def spread_interior_candidates(candidates, limit=INTERIOR_PER_CLASS_PER_ACTOR):
    """Choose separated observed component centers; absence is an observation."""
    remaining = sorted(candidates, key=lambda row: tuple(row["component_section_base"]))
    chosen = []
    while remaining and len(chosen) < limit:
        if not chosen:
            selected = remaining[0]
        else:
            selected = max(remaining, key=lambda row: min(
                math.dist(row["component_section_base"], other["component_section_base"])
                for other in chosen))
        chosen.append(selected)
        remaining.remove(selected)
    return chosen


def prepare_interior_plan(manifest_path, report_path):
    manifest, report, actors = validate_inputs(manifest_path, report_path)
    result = {
        "schema_version": 1, "status": "SOURCE_SELECTED_INTERIOR_NATIVE_READ_PENDING",
        "source_head": report["source_head"], "level": LEVEL,
        "manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
        "native_before": {"path": str(report_path), "sha256": sha256(report_path)},
        "accepted_l06_sha256": SOURCE_SHA256,
        "original_source_center_bounds_m": INTERIOR_SOURCE_BOUNDS_M,
        "source_bounds_basis": "Pinned centered 16000x16000 source cells at 0.5 m; transport padding excluded",
        "buffer_vertices": INTERIOR_BUFFER_VERTICES,
        "selection": "Central quad per observed component, uniform 8x8 source-validity patch; up to three separated candidates per class per actor",
        "actor_registration": {name: {key: row[key] for key in
            ("location_cm", "rotation_deg_pitch_yaw_roll", "scale")} for name, row in actors.items()},
        "geometry_accepted": False, "source_triangle_interpolation_proved": False,
        "visibility_layer_proved_in_ue": False, "tiles": [], "probes": [],
    }
    import hou
    for tile in manifest["tiles"]:
        path = (manifest_path.parent / tile["file"]).resolve()
        if path.parent != manifest_path.parent.resolve() or sha256(path) != tile["sha256"]:
            raise ValueError("Interior selection requires unchanged pinned adjacent BGEO")
        geometry = hou.Geometry()
        geometry.loadFromFile(str(path))
        try:
            volumes = {p.attribValue("name"): p for p in geometry.prims() if isinstance(p, hou.Volume)}
            if set(volumes) != {"height", "visibility"} or len(geometry.prims()) != 2:
                raise ValueError("Pinned interior source layers changed")
            height, validity = volumes["height"], volumes["visibility"]
            if list(height.resolution()) != tile["resolution"] or height.resolution() != validity.resolution():
                raise ValueError("Pinned interior source resolution changed")
            candidates, skipped = {0: [], 1: []}, Counter()
            layouts = actors[tile["name"]]["native_component_layouts"]
            if len(layouts) != 1024:
                raise ValueError("Interior selection requires all original component layouts")
            for layout in layouts:
                row, reason = interior_candidate(height, validity, actors[tile["name"]], layout)
                if row is None:
                    skipped[reason] += 1
                else:
                    candidates[row["source_validity"]].append(row)
            selected = {key: spread_interior_candidates(rows) for key, rows in candidates.items()}
            result["tiles"].append({
                "actor": tile["name"], "source_file": str(path), "sha256": tile["sha256"],
                "examined_component_centers": len(layouts),
                "uniform_interior_candidates_by_validity": {str(k): len(v) for k, v in candidates.items()},
                "selected_by_validity": {str(k): len(v) for k, v in selected.items()},
                "skipped": dict(skipped),
            })
            for source_class, rows in selected.items():
                for index, row in enumerate(rows):
                    result["probes"].append({**row, "id": f"{tile['name']}-validity{source_class}-{index}"})
        finally:
            geometry.clear()
    return result


def validate_inputs(manifest_path, report_path):
    if sha256(manifest_path) != MANIFEST_SHA256:
        raise ValueError("Not the pinned 39390349735-1 transfer manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("accepted_l06_sha256") != SOURCE_SHA256:
        raise ValueError("Transfer references another L06 cache")
    tiles = manifest.get("tiles", [])
    if len(tiles) != 4 or {t["name"] for t in tiles} != ACTORS:
        raise ValueError("Transfer must contain exactly the four L07 tiles")
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    if report.get("level") != LEVEL:
        raise ValueError("Native report is not the canonical L07 map package")
    if not report.get("engine_version", "").startswith("5.8.2-56702186"):
        raise ValueError("Native report is not from the inspected UE 5.8.2 build")
    if report.get("candidate_map_unchanged") is not True:
        raise ValueError("Native readback did not prove map conservation")
    validate_native_map(report, report_path)
    observation = report.get("native_seams", {})
    if observation.get("observed") is not True:
        raise ValueError(f"Native seams not observed: {observation.get('error')}")
    native = observation["value"]
    if native.get("schema_version") != 1 or native.get("sample_columns") != COLUMNS:
        raise ValueError("Unsupported native seam schema")
    seams = native.get("seams", [])
    if len(seams) != 4 or len({s["id"] for s in seams}) != 4:
        raise ValueError("Expected four distinct native seams")
    actors = report.get("landscapes", [])
    if len(actors) != 4 or {a["name"] for a in actors} != ACTORS:
        raise ValueError("Native actor identity differs from pinned L07 actors")
    for actor in actors:
        if actor["label"] != actor["name"]:
            raise ValueError("Unexpected actor label/name mapping")
        if len(actor["scale"]) != 3 or len(actor["location_cm"]) != 3:
            raise ValueError("Incomplete native actor transform")
        if len(actor["rotation_deg_pitch_yaw_roll"]) != 3:
            raise ValueError("Incomplete native actor rotation")
        for value in (
            actor["scale"] + actor["location_cm"] + actor["rotation_deg_pitch_yaw_roll"]
        ):
            finite(value)
    for seam in seams:
        if seam.get("observed") is not True:
            continue
        if seam["a"]["actor"] == seam["b"]["actor"]:
            raise ValueError("Seam sides cannot belong to the same actor")
        for side in ("a", "b"):
            edge = seam[side]
            if edge["actor"] not in ACTORS or len(edge["samples"]) != 8129:
                raise ValueError("Missing actor or incomplete native edge")
            for row in edge["samples"]:
                if len(row) != 5:
                    raise ValueError("Malformed native sample")
                unsigned(row[0], 65535)
                for value in row[1:4]:
                    finite(value)
                if row[4] is not None:
                    unsigned(row[4], 255)
    return manifest, report, {a["name"]: a for a in actors}


def volume_observation(height, validity, x_cm, y_cm):
    position = (finite(x_cm) / 100.0, 0.0, finite(y_cm) / 100.0)
    index = tuple(height.posToIndex(position))
    if not height.isValidIndex(index) or not validity.isValidIndex(index):
        raise ValueError(f"Native XY outside source tile: {position}, index={index}")
    center = tuple(float(v) for v in height.indexToPos(index))
    mask_center = tuple(float(v) for v in validity.indexToPos(index))
    if center != mask_center:
        raise ValueError("Height and retained validity volume transforms differ")
    value = finite(height.voxel(index))
    mask = finite(validity.voxel(index))
    if mask not in (0.0, 1.0):
        raise ValueError(f"Pinned transfer validity is not binary: {mask}")
    return {
        "source_voxel_index": list(index),
        "source_voxel_center_houdini_m": list(center),
        "source_vertex_height_m": value,
        "source_hou_interpolated_height_m_diagnostic": finite(height.sample(position)),
        "source_validity": int(mask),
        "expected_ue_hole_weight_u8": 0 if mask == 1.0 else 255,
        "xy_to_source_vertex_cm": [
            x_cm - center[0] * 100.0, y_cm - center[2] * 100.0
        ],
    }


def compare_vertex(height, validity, sample, actor):
    code, x_cm, y_cm, z_cm, visibility = sample
    source = volume_observation(height, validity, x_cm, y_cm)
    model = quantization_model(
        source["source_vertex_height_m"], actor["scale"][2], actor["location_cm"][2]
    )
    unrotated_z = model["predicted_world_z_cm"]
    model["predicted_world_z_cm"] = world_z_at_xy(
        model["predicted_height_u16_non_fused_float32"], actor, x_cm, y_cm
    )
    model["rotation_contribution_to_predicted_z_cm"] = (
        model["predicted_world_z_cm"] - unrotated_z
    )
    return {
        **source, **model,
        "native_world_z_cm": z_cm,
        "native_height_u16": code,
        "native_visibility_u8": visibility,
        "height_residual_from_source_vertex_cm": (
            z_cm - source["source_vertex_height_m"] * 100.0
        ),
        "raw_height_code_difference": (
            code - model["predicted_height_u16_non_fused_float32"]
        ),
        "world_z_difference_from_model_cm": z_cm - model["predicted_world_z_cm"],
        "visibility_matches_source_validity": (
            None if visibility is None
            else visibility == source["expected_ue_hole_weight_u8"]
        ),
    }


def summarize(rows):
    residual = [r["height_residual_from_source_vertex_cm"] for r in rows]
    return {
        "sample_count": len(rows),
        "height_residual_cm_min_max": [min(residual), max(residual)],
        "max_abs_height_residual_cm": max(map(abs, residual)),
        "max_xy_registration_error_cm": max(
            math.hypot(*r["xy_to_source_vertex_cm"]) for r in rows
        ),
        "raw_code_difference_counts": dict(sorted(Counter(
            r["raw_height_code_difference"] for r in rows
        ).items())),
        "visibility_unknown_count": sum(
            r["visibility_matches_source_validity"] is None for r in rows
        ),
        "visibility_mismatch_count": sum(
            r["visibility_matches_source_validity"] is False for r in rows
        ),
        "source_validity_counts": dict(Counter(r["source_validity"] for r in rows)),
        "model_clipping_count": sum(r["clipping_in_model"] for r in rows),
    }


def collision_observation(height, validity, probe, edge):
    """Keep an interior hou.sample result explicitly separate from collision proof."""
    result = {"side": probe["side"], "vertex_offset": probe["vertex_offset"]}
    sample = edge["samples"][unsigned(probe["vertex_offset"], len(edge["samples"]) - 1)]
    for kind in ("at_vertex", "inside"):
        native = probe.get(kind, {})
        xy = native.get("query_xy_cm", sample[1:3] if kind == "at_vertex" else None)
        row = {"native": native, "source_triangle_interpolation_proved": False}
        if xy is None:
            row["error"] = "Native query XY is missing"
        else:
            row["source"] = volume_observation(height, validity, *xy)
            if native.get("observed") is True and native.get("hit") is True:
                hit = native.get("impact_point_cm")
                if hit is not None:
                    row["bilinear_diagnostic_residual_cm"] = (
                        finite(hit[2])
                        - row["source"]["source_hou_interpolated_height_m_diagnostic"] * 100
                    )
            row["note"] = (
                "hou.Volume.sample is a diagnostic reference. No collision PASS "
                "without the actual UE triangle and source heights at its vertices."
            )
        result[kind] = row
    return result


def compare_interior_probe(height, validity, probe, native, actor):
    result = {"id": probe["id"], "actor": probe["actor"], "native": native,
              "source_validity": probe["source_validity"],
              "source_triangle_interpolation_proved": False, "geometry_accepted": False}
    if native.get("observed") is not True:
        result["error"] = native.get("error", "Native interior observation incomplete")
        return result
    corners = native["native_corners"]
    if (native.get("actor") != probe["actor"] or native.get("component_path") != probe["component_path"]
            or corners.get("actor_name") != probe["actor"]
            or corners.get("component_path") != probe["component_path"]
            or corners.get("world_package") != LEVEL
            or corners.get("vertex_indices") != probe["local_vertex_indices"]
            or len(corners.get("samples", [])) != 4):
        raise ValueError("Interior native corner identity differs from source-selected quad")
    rows = []
    for planned, sample in zip(probe["source_corners"], corners["samples"]):
        if len(sample) != 5:
            raise ValueError("Malformed native interior corner")
        unsigned(sample[0], 65535)
        for number in sample[1:4]:
            finite(number)
        if sample[4] is not None:
            unsigned(sample[4], 255)
        row = compare_vertex(height, validity, sample, actor)
        if any(row[key] != planned[key] for key in (
                "source_voxel_index", "source_voxel_center_houdini_m",
                "source_vertex_height_m", "source_validity")):
            raise ValueError("Actual native XY maps to another source voxel than the interior plan")
        rows.append(row)
    collision = native["center_collision"]
    center_xy = [math.fsum(row[i] for row in corners["samples"])/4.0 for i in (1, 2)]
    if collision.get("query_xy_cm") != center_xy:
        raise ValueError("Interior collision query is not the native quad center")
    source_center = volume_observation(height, validity, *center_xy)
    if source_center["source_validity"] != probe["source_validity"]:
        raise ValueError("Actual quad center left the uniform source validity patch")
    if collision.get("observed") is not True or type(collision.get("hit")) is not bool:
        raise ValueError("Interior collision result is UNKNOWN")
    if collision["hit"] and (
            collision.get("hit_actor") != probe["actor"]
            or collision.get("hit_render_component") != probe["component_path"]):
        raise ValueError("Interior collision did not authenticate the selected actor/render component")
    matches = [row["visibility_matches_source_validity"] for row in rows]
    result.update(
        source_corners=rows, source_center=source_center,
        sampled_visibility_matches_source=(all(matches) if all(x is not None for x in matches) else None),
        expected_center_collision_hit=bool(probe["source_validity"]),
        sampled_collision_hit_matches_source_class=collision["hit"] == bool(probe["source_validity"]),
        note="Uniform buffered source class and exact four native vertex weights; sampled hit/miss only. No triangle-height, whole-area visibility or geometry acceptance.",
    )
    return result


def compare(manifest_path, report_path):
    manifest, report, actors = validate_inputs(manifest_path, report_path)
    native = report["native_seams"]["value"]
    complete = native.get("height_samples_complete") is True and all(
        s.get("observed") is True for s in native["seams"]
    )
    result = {
        "schema_version": 1,
        "status": (
            "DIAGNOSTIC_COMPLETE_ACCEPTANCE_PENDING" if complete
            else "PARTIAL_NATIVE_SEAM_DIAGNOSTIC"
        ),
        "manifest": {"path": str(manifest_path), "sha256": sha256(manifest_path)},
        "native_report": {"path": str(report_path), "sha256": sha256(report_path)},
        "native_provenance": {key: report.get(key) for key in (
            "source_head", "project_root", "engine_version", "preparation_identity",
            "map_before", "map_after", "candidate_map_unchanged",
            "map_lineage", "repair_receipts_authenticated",
        )},
        "source_cache_sha256_declared_by_pinned_manifest": SOURCE_SHA256,
        "source_cache_rehashed_by_this_comparison": False,
        "coordinate_mapping": "UE cm (X,Y,Z) = Houdini metres (X,Z,height)*100",
        "validity_semantics": (
            "Pinned BGEO visibility stores source validity, not a hole weight: "
            "valid=1 expects UE visibility byte 0; invalid=0 expects byte 255. "
            "Missing native allocation remains UNKNOWN."
        ),
        "quantization_model": (
            "Installed SideFX22.0.466 float32 truncation to 65535 values; "
            "UE5.8 GetLocalHeight=(u16-32768)/128. Model residuals are diagnostics, "
            "not project tolerances. No half-step or uniform Scale.Z assumption."
        ),
        "geometry_accepted": False,
        "source_height_interpolation_proved": False,
        "visibility_layer_proved_in_ue": False,
        "tiles": [],
        "seams": {s["id"]: {
            "native_observed": s.get("observed") is True,
            "native_error": s.get("error"),
            "native_peer_summary": s.get("peer_summary"),
            "sides": {}, "collision_probes": [],
        } for s in native["seams"]},
        "interior_samples": {"native_observed": False, "probes": [], "geometry_accepted": False},
    }
    interior_observation = report.get("native_interiors", {})
    interior_plan, interior_rows = None, {}
    if interior_observation.get("observed") is True:
        reader = readback_validator()
        preparation = reader.read_repair_receipt(report["preparation_identity"])
        interior_plan = reader.authenticated_interior_plan(preparation)
        value = interior_observation["value"]
        if value.get("plan_identity") != preparation["interior_plan"]:
            raise ValueError("Native interior report references another source plan")
        interior_rows = {row["id"]: row for row in value["probes"]}
        if (len(interior_rows) != len(value["probes"])
                or set(interior_rows) != {p["id"] for p in interior_plan["probes"]}):
            raise ValueError("Native interior observations omit/substitute selected probes")
        result["interior_samples"].update(
            native_observed=True, plan_identity=value["plan_identity"],
            source_selection=interior_plan["tiles"], samples_complete=value.get("samples_complete") is True)
    else:
        result["interior_samples"]["error"] = interior_observation.get("error", "NOT_REQUESTED")
    # Import only here: syntax/helper validation can use ordinary Python.
    import hou

    for tile in manifest["tiles"]:
        path = (manifest_path.parent / tile["file"]).resolve()
        if path.parent != manifest_path.parent.resolve():
            raise ValueError("Tile must be adjacent to the pinned manifest")
        actual_hash = sha256(path)
        if actual_hash != tile["sha256"]:
            raise ValueError(f"Tile bytes changed: {path}")
        applicable = [
            seam for seam in native["seams"]
            if seam.get("observed") is True and any(
                seam[side]["actor"] == tile["name"] for side in ("a", "b")
            )
        ]
        interior_probes = ([p for p in interior_plan["probes"] if p["actor"] == tile["name"]]
                           if interior_plan else [])
        if not applicable and not interior_probes:
            result["tiles"].append({
                "name": tile["name"], "path": str(path), "sha256": actual_hash,
                "volumes_read": False, "reason": "No successful native seam for this tile",
            })
            continue
        geometry = hou.Geometry()
        geometry.loadFromFile(str(path))
        try:
            volumes = {
                p.attribValue("name"): p for p in geometry.prims()
                if isinstance(p, hou.Volume)
            }
            if set(volumes) != {"height", "visibility"} or len(geometry.prims()) != 2:
                raise ValueError("Pinned native tile layers changed")
            height, validity = volumes["height"], volumes["visibility"]
            if list(height.resolution()) != tile["resolution"]:
                raise ValueError("Height resolution differs from manifest")
            if height.resolution() != validity.resolution():
                raise ValueError("Validity resolution differs from height")
            result["tiles"].append({
                "name": tile["name"], "path": str(path), "sha256": actual_hash,
                "volumes_read": True,
            })
            for probe in interior_probes:
                result["interior_samples"]["probes"].append(compare_interior_probe(
                    height, validity, probe, interior_rows[probe["id"]], actors[tile["name"]]))
            for seam in applicable:
                output = result["seams"][seam["id"]]
                for side in ("a", "b"):
                    edge = seam[side]
                    if edge["actor"] != tile["name"]:
                        continue
                    rows = [
                        compare_vertex(height, validity, sample, actors[tile["name"]])
                        for sample in edge["samples"]
                    ]
                    output["sides"][side] = {
                        "actor": tile["name"], "summary": summarize(rows), "samples": rows
                    }
                    for probe in seam.get("collision_probes", []):
                        if probe["side"] == side:
                            output["collision_probes"].append(
                                collision_observation(height, validity, probe, edge)
                            )
        finally:
            geometry.clear()
    for seam in result["seams"].values():
        if not seam["native_observed"]:
            continue
        a, b = seam["sides"]["a"]["samples"], seam["sides"]["b"]["samples"]
        seam["max_abs_source_vertex_height_difference_cm"] = max(
            abs(x["source_vertex_height_m"] - y["source_vertex_height_m"]) * 100
            for x, y in zip(a, b)
        )
        seam["max_abs_native_height_difference_cm"] = max(
            abs(x["native_world_z_cm"] - y["native_world_z_cm"])
            for x, y in zip(a, b)
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--ue-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-interior-plan", action="store_true",
                        help="Read pinned BGEO only and select buffered interior probes; no native UE/cook")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite a receipt")
    operation = prepare_interior_plan if args.prepare_interior_plan else compare
    result = operation(args.manifest.resolve(), args.ue_report.resolve())
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"Diagnostic written: {args.output}; native acceptance remains pending")


if __name__ == "__main__":
    main()
