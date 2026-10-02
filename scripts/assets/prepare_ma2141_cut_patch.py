"""Prepare a bounded CUT-only Road_Earthworks height patch for Ma-2141.

The patch is deliberately asymmetric: it may only lower terrain that is above the
BOB-inspected smooth ribbon. It never fills unsupported road, moves route XY,
modifies Base_DTM, resolves structures, or grants road/learning admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.geometry.curved_road_plan import STATION_COUNT, profile_plan_valid
from scripts.geometry.road_cut_limits import (
    cut_limits,
    inspection_within_cut_limits,
    station_cut_limit,
)
from scripts.worldgen.bob_terrain_fit_inspector import inspect_terrain_fit

GRID_STEP_M = 0.5
SECTION_POINTS = 25
EXPECTED_STATIONS = 601
NEUTRAL_HEIGHT = 32768
CUT_CLEARANCE_M = 0.01
GUARD_CELLS = 1
_EPS = 1e-8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inside_triangle(px, py, triangle):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = triangle
    denom = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(denom) <= 1e-12:
        raise ValueError("Degenerate road-profile triangle")
    wa = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denom
    wb = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denom
    wc = 1.0 - wa - wb
    if min(wa, wb, wc) < -_EPS or max(wa, wb, wc) > 1.0 + _EPS:
        return None
    return wa * az + wb * bz + wc * cz


def rasterize_profile_grid(profile):
    rows = profile["stations"]
    expected_count = STATION_COUNT if "presentation_plan" in profile and profile_plan_valid(profile) else EXPECTED_STATIONS
    if len(rows) != expected_count:
        raise ValueError("CUT patch requires the complete recipe station domain")

    xy = np.asarray([row["xy_local_m"] for row in rows], dtype=float)
    target = np.asarray([row["candidate_ground_m"] for row in rows], dtype=float)
    if (
        xy.shape != (expected_count, SECTION_POINTS, 2)
        or target.shape != (expected_count, SECTION_POINTS)
        or not np.isfinite(xy).all()
        or not np.isfinite(target).all()
    ):
        raise ValueError("Invalid finite road-profile grid")

    samples: dict[tuple[int, int], float] = {}
    for station in range(expected_count - 1):
        for lateral in range(SECTION_POINTS - 1):
            p00 = (*xy[station, lateral], target[station, lateral])
            p01 = (*xy[station, lateral + 1], target[station, lateral + 1])
            p10 = (*xy[station + 1, lateral], target[station + 1, lateral])
            p11 = (*xy[station + 1, lateral + 1], target[station + 1, lateral + 1])
            for triangle in ((p00, p01, p10), (p01, p11, p10)):
                min_x = math.floor(min(point[0] for point in triangle) / GRID_STEP_M)
                max_x = math.ceil(max(point[0] for point in triangle) / GRID_STEP_M)
                min_y = math.floor(min(point[1] for point in triangle) / GRID_STEP_M)
                max_y = math.ceil(max(point[1] for point in triangle) / GRID_STEP_M)
                for grid_y in range(min_y, max_y + 1):
                    for grid_x in range(min_x, max_x + 1):
                        if not (0 <= grid_x <= 4032 and 0 <= grid_y <= 4032):
                            continue
                        z = _inside_triangle(
                            grid_x * GRID_STEP_M,
                            grid_y * GRID_STEP_M,
                            triangle,
                        )
                        if z is None:
                            continue
                        key = (grid_x, grid_y)
                        previous = samples.get(key)
                        if previous is not None and abs(previous - z) > 0.02:
                            raise ValueError(
                                "Road-profile branches conflict on one Landscape vertex"
                            )
                        samples[key] = z if previous is None else (previous + z) * 0.5

    if len(samples) < 1000:
        raise ValueError("Road-profile rasterization produced too few Landscape vertices")
    return samples


def _decode_height_m(encoded, manifest):
    return (
        (float(encoded) - NEUTRAL_HEIGHT) * float(manifest["scale_z"]) / 128.0
        + float(manifest["location_z_cm"])
    ) / 100.0


def _world_height_cm(encoded, manifest):
    return _decode_height_m(encoded, manifest) * 100.0



def _patch_bounds(requested):
    # Landscape Texture Patch excludes its outer coverage edge. Keep every
    # requested vertex one unchanged native texel inside that edge.
    min_x = max(0, min(key[0] for key in requested) - 1)
    max_x = min(4032, max(key[0] for key in requested) + 1)
    min_y = max(0, min(key[1] for key in requested) - 1)
    max_y = min(4032, max(key[1] for key in requested) + 1)
    if any(x in (min_x, max_x) or y in (min_y, max_y) for x,y in requested):
        raise ValueError("CUT requests need one neutral native texel around texture coverage")
    return min_x, max_x, min_y, max_y


def prepare(prepared, profile_path, output_manifest, output_r16, exact_sha):
    for path in (output_manifest, output_r16):
        if path.exists():
            raise FileExistsError("Preserve existing CUT patch evidence")
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact lowercase SHA40 required")

    terrain_manifest = json.loads(
        (prepared / "terrain-import.json").read_text(encoding="utf-8")
    )
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    inspection = profile.get("bob_inspection")
    if (
        terrain_manifest.get("region_id") != "sa_calobra"
        or terrain_manifest.get("vertices") != [4033, 4033]
        or profile.get("exact_sha") != exact_sha
        or profile.get("region_id") != "sa_calobra"
        or profile.get("status") != "REVIEW_REQUIRED"
        or profile.get("heightmap_sha256") != terrain_manifest.get("heightmap_sha256")
        or not profile_plan_valid(profile)
        or profile.get("terrain_modified") is not False
        or profile.get("road_earthworks_modified") is not False
        or not isinstance(inspection, dict)
        or inspection.get("inspection_complete") is not True
        or inspection.get("role") != "INSPECTOR_ONLY"
        or inspection.get("earthworks_authoring_permitted") is not False
    ):
        raise ValueError("Unadmitted profile/terrain input for CUT-only patch")

    terrain_path = prepared / "terrain.r16"
    if (
        terrain_path.stat().st_size != 4033 * 4033 * 2
        or sha256(terrain_path) != terrain_manifest["heightmap_sha256"]
    ):
        raise ValueError("Prepared native terrain changed before CUT patch")

    policy = json.loads(
        (ROOT / "worldgen/terrain/adaptive_terrain_policy.json").read_text(
            encoding="utf-8"
        )
    )
    limits = cut_limits(profile.get("presentation_plan", {}), policy)
    structure_threshold = float(policy["thresholds"]["retaining_cut_fill_m"])

    pre_samples = []
    for row in profile["stations"]:
        for lateral, xy, native, target in zip(
            row["lateral_m"],
            row["xy_local_m"],
            row["native_ground_m"],
            row["candidate_ground_m"],
            strict=True,
        ):
            pre_samples.append(
                {
                    "station_m": row["station_m"],
                    "lateral_m": lateral,
                    "local_xy_m": xy,
                    "road_surface_z_m": float(target) + 0.04,
                    "landscape_z_m": native,
                }
            )
    expected_pre_fit = inspect_terrain_fit(
        pre_samples,
        exact_sha=exact_sha,
        contact_band_max_m=0.08,
        structure_review_threshold_m=structure_threshold,
    )
    if (
        not expected_pre_fit["inspection_complete"]
        or expected_pre_fit["class_counts"]["CUT_REQUIRED"] <= 0
        or expected_pre_fit["class_counts"]["STRUCTURE_REVIEW"] != 0
        or not inspection_within_cut_limits(expected_pre_fit, limits)
    ):
        raise ValueError("CUT-only precondition is outside the bounded recipe")

    terrain = np.fromfile(terrain_path, dtype="<u2").reshape(4033, 4033)
    road_targets = rasterize_profile_grid(profile)

    # Lower one native grid ring beyond the ribbon wherever a cut is required.
    # This prevents edge traces from borrowing a still-high outside vertex. It is
    # intentionally only one 0.5 m cell and never introduces positive/fill deltas.
    requested: dict[tuple[int, int], float] = dict(road_targets)
    for (grid_x, grid_y), target_m in list(road_targets.items()):
        base_m = _decode_height_m(terrain[grid_y, grid_x], terrain_manifest)
        if base_m <= target_m - CUT_CLEARANCE_M:
            continue
        for dy in range(-GUARD_CELLS, GUARD_CELLS + 1):
            for dx in range(-GUARD_CELLS, GUARD_CELLS + 1):
                gx, gy = grid_x + dx, grid_y + dy
                if 0 <= gx <= 4032 and 0 <= gy <= 4032:
                    previous = requested.get((gx, gy))
                    requested[(gx, gy)] = (
                        target_m if previous is None else min(previous, target_m)
                    )

    # Cover all four native cell corners under every inspected road sample.
    # Rasterizing only grid vertices inside the road can miss thin edge wedges.
    # These extra boundary requests obey the existing guard depth cap.
    for row in profile["stations"]:
        for (x_m, y_m), target_m in zip(
            row["xy_local_m"], row["candidate_ground_m"], strict=True
        ):
            cell_x, cell_y = math.floor(x_m / GRID_STEP_M), math.floor(y_m / GRID_STEP_M)
            for gy in (cell_y, cell_y + 1):
                for gx in (cell_x, cell_x + 1):
                    if not (0 <= gx <= 4032 and 0 <= gy <= 4032):
                        raise ValueError("Road sample cell lies outside native terrain")
                    previous = requested.get((gx, gy))
                    requested[(gx, gy)] = target_m if previous is None else min(previous, target_m)

    # Only native cells touching the marked ribbon and its one-cell guard can
    # use the cliff cap. Everywhere else retains the ordinary 1 m recipe.
    cliff_keys = set()
    for row in profile["stations"]:
        if station_cut_limit(limits, row["station_m"]) <= limits["ordinary_m"]:
            continue
        for x_m, y_m in row["xy_local_m"]:
            ix, iy = math.floor(x_m / GRID_STEP_M), math.floor(y_m / GRID_STEP_M)
            for gy in range(iy - GUARD_CELLS, iy + 2 + GUARD_CELLS):
                for gx in range(ix - GUARD_CELLS, ix + 2 + GUARD_CELLS):
                    cliff_keys.add((gx, gy))

    def vertex_cap(x, y):
        return limits["cliff_m"] if (x, y) in cliff_keys else limits["ordinary_m"]

    min_x, max_x, min_y, max_y = _patch_bounds(requested)
    width = max_x - min_x + 1
    height = max_y - min_y + 1
    patch = np.empty((height, width), dtype="<f4")
    for patch_y in range(height):
        grid_y = min_y + patch_y
        for patch_x in range(width):
            grid_x = min_x + patch_x
            patch[patch_y, patch_x] = _world_height_cm(
                terrain[grid_y, grid_x],
                terrain_manifest,
            )

    modified = 0
    clamped_guard_at_cap = 0
    cut_values = []
    road_keys = set(road_targets)
    for (grid_x, grid_y), target_m in requested.items():
        base_m = _decode_height_m(terrain[grid_y, grid_x], terrain_manifest)
        delta_m = min(0.0, target_m - CUT_CLEARANCE_M - base_m)
        if delta_m < -vertex_cap(grid_x, grid_y) - 1e-6:
            if (grid_x, grid_y) in road_keys:
                raise ValueError("Road CUT target exceeded the spatial CUT safety cap")
            clamped_guard_at_cap += 1
            delta_m = -vertex_cap(grid_x, grid_y)
        if delta_m < -1e-6:
            modified += 1
            cut_values.append(-delta_m)
            patch[grid_y - min_y, grid_x - min_x] = (
                base_m + delta_m
            ) * 100.0

    # A capped steep outside corner can still lift the interpolated facet into
    # asphalt. Lower the other corners of that same facet, sharing only the
    # measured excess, while retaining the spatial per-vertex cap. Lowering is
    # monotonic, so previously cleared samples cannot become penetrations.
    for row in profile["stations"]:
        for (x_m, y_m), target_m in zip(row["xy_local_m"], row["candidate_ground_m"], strict=True):
            gx, gy = x_m / GRID_STEP_M, y_m / GRID_STEP_M
            ix, iy = math.floor(gx), math.floor(gy)
            fx, fy = gx - ix, gy - iy
            corners = (
                ((ix, iy, 1-fx), (ix+1, iy, fx-fy), (ix+1, iy+1, fy))
                if fx >= fy else
                ((ix, iy, 1-fy), (ix, iy+1, fy-fx), (ix+1, iy+1, fx))
            )
            for _ in range(4):
                current = sum(float(patch[y-min_y, x-min_x])/100*w for x,y,w in corners)
                excess = current - (target_m - CUT_CLEARANCE_M)
                if excess <= 1e-4:
                    break
                available = [(x,y,w) for x,y,w in corners if w > 1e-9 and
                             float(patch[y-min_y, x-min_x])/100 >
                             _decode_height_m(terrain[y,x], terrain_manifest)-vertex_cap(x, y)+1e-4]
                total_weight = sum(w for _,_,w in available)
                if total_weight <= 1e-9:
                    raise ValueError("Cannot clear road facet within the spatial CUT cap")
                for x,y,w in available:
                    floor = _decode_height_m(terrain[y,x], terrain_manifest)-vertex_cap(x, y)
                    patch[y-min_y, x-min_x] = max(floor, float(patch[y-min_y, x-min_x])/100-excess/total_weight-1e-4)*100
            else:
                raise ValueError("Road facet clearance did not converge within its three corners")

    # Recompute metrics after facet correction, rather than reporting only the
    # initial raster/guard pass.
    cut_values = []
    for py in range(height):
        for px in range(width):
            base_m = _decode_height_m(terrain[min_y+py,min_x+px], terrain_manifest)
            floor_cm = (base_m - vertex_cap(min_x + px, min_y + py))*100
            if float(patch[py,px]) < floor_cm:
                patch[py,px] = np.nextafter(np.float32(floor_cm), np.float32(np.inf))
            depth = base_m - float(patch[py,px])/100
            if depth > 1e-4:
                cut_values.append(depth)
    modified = len(cut_values)

    if modified == 0:
        raise ValueError("CUT-only patch contains no terrain changes")
    output_r16.parent.mkdir(parents=True, exist_ok=True)
    patch.tofile(output_r16)

    result = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "architect": "BOB",
        "region_id": "sa_calobra",
        "operation": "CUT_ONLY",
        "status": "BOUNDED_TRANSIENT_RECIPE",
        "layer": "Road_Earthworks",
        "layer_encoding": "LANDSCAPE_TEXTURE_PATCH_WORLD_UNITS_F32_MIN",
        "blend_mode": "Min",
        "height_encoding": "WorldUnits",
        "zero_height_meaning": "WorldZero",
        "world_space_unit": "centimeter",
        "base_layer": "Base_DTM",
        "base_dtm_modified": False,
        "route_xy_modified": False,
        "fill_authoring_permitted": False,
        "structure_authoring_permitted": False,
        "save_map": False,
        "grid_step_m": GRID_STEP_M,
        "cut_clearance_m": CUT_CLEARANCE_M,
        "guard_cells": GUARD_CELLS,
        "max_cut_limit_m": limits["cliff_m"],
        "cut_limits": limits,
        "cliff_cap_vertex_count": len(cliff_keys.intersection(requested)),
        "modified_vertex_count": modified,
        "clamped_guard_at_cap_count": clamped_guard_at_cap,
        "max_cut_m": max(cut_values),
        "mean_cut_m": float(np.mean(cut_values)),
        "rect": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "width": width,
            "height": height,
        },
        "patch_file": output_r16.name,
        "patch_sha256": sha256(output_r16),
        "patch_byte_count": output_r16.stat().st_size,
        "texture_resolution": [width, height],
        "unscaled_coverage_cm": [
            (width - 1) * GRID_STEP_M * 100.0,
            (height - 1) * GRID_STEP_M * 100.0,
        ],
        "texture_center_world_cm": [
            (min_x + max_x) * 0.5 * GRID_STEP_M * 100.0,
            (min_y + max_y) * 0.5 * GRID_STEP_M * 100.0,
            0.0,
        ],
        "profile_sha256": sha256(profile_path),
        "heightmap_sha256": terrain_manifest["heightmap_sha256"],
        "expected_pre_fit": {
            "sample_count": expected_pre_fit["sample_count"],
            "class_counts": expected_pre_fit["class_counts"],
            "max_cut_required_m": expected_pre_fit["max_cut_required_m"],
            "max_fill_required_m": expected_pre_fit["max_fill_required_m"],
        },
        "admission": {
            "road_admitted": False,
            "eligible_for_learning": False,
            "continuous_support": "NOT_PROVEN",
            "structures": "NOT_AUTHORED",
            "fill": "NOT_AUTHORED",
        },
    }
    output_manifest.write_text(
        json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--output-f32", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    result = prepare(
        args.prepared_terrain,
        args.profile,
        args.output_manifest,
        args.output_f32,
        args.exact_sha,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "modified_vertex_count": result["modified_vertex_count"],
                "max_cut_m": result["max_cut_m"],
                "expected_pre_fit": result["expected_pre_fit"],
            }
        )
    )
