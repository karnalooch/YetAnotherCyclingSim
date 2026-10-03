"""Bounded, source-grounded asphalt candidates on the existing Sa Calobra map.

The accepted 300 m recipe keeps ownership of its footprint. Other pavement is
provisional 5 m. Failed geometry/earthworks windows remain explicit coverage gaps.
No canonical source coordinates, physics data or saved Landscape are modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, Polygon, box, shape
from shapely.ops import substring, transform

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import itertools

from scripts.assets.prepare_ma2141_cut_patch import _decode_height_m, _inside_triangle
from scripts.assets.prepare_ma2141_diagnostic import select_alignment
from scripts.assets.prepare_ma2141_profile import local_linear_fit
from scripts.assets.prepare_ma2141_road_preview import triangle_candidates
from scripts.geometry.bob_vertical_support import build_vertical_support
from scripts.geometry.network_pavement import shoulder_sections

SOURCE = (
    ROOT
    / "worldgen/terrain/benchmarks/sa_calobra/current_landscape_igr_roads_2026-10-03.json"
)
SOURCE_SHA = "0b959ed9ae741d64721669531edd33fac7fe1f1969cd1be58b77785d6eb05ea5"
WIDTH = 5.0
SHOULDER = 0.5
STEP = 0.5
CUT_CAP = 1.0
SUPPORT_CAP = 4.0


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "LineString":
        return [geometry]
    return [g for g in geometry.geoms if g.geom_type == "LineString"]


def smooth_axis(line, spacing=4.0):
    """Uniform cubic B-spline control envelope, evaluated offline into buffers.

    Same convex cubic family as the accepted bend; no runtime curve authority.
    Independent checks of both offsets reject a pinched inner edge/short hook.
    """
    keys = np.linspace(0, line.length, max(4, math.ceil(line.length / spacing) + 1))
    raw = np.array([line.interpolate(s).coords[0][:2] for s in keys])
    controls = np.vstack([2 * raw[0] - raw[1], raw, 2 * raw[-1] - raw[-2]])
    count = math.ceil(line.length / STEP)
    stations = np.linspace(0, line.length, count + 1)
    key = stations / keys[1]
    integer = np.minimum(np.floor(key).astype(int), len(raw) - 2)
    u = key - integer
    weights = (
        np.array(
            [
                (1 - u) ** 3,
                3 * u**3 - 6 * u * u + 4,
                -3 * u**3 + 3 * u * u + 3 * u + 1,
                u**3,
            ]
        ).T
        / 6
    )
    xy = sum(weights[:, j, None] * controls[integer + j] for j in range(4))
    return stations, xy


def turns(points):
    a, b = np.diff(points, axis=0)[:-1], np.diff(points, axis=0)[1:]
    lengths = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
    if (lengths <= 1e-12).any():
        raise ValueError("Boundary stops or reverses")
    return np.arctan2(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0], np.sum(a * b, axis=1))


def inspect_sections(sections, source_line):
    xy = np.asarray(sections)[:, :, :2]
    left, right = xy[:, 0], xy[:, -1]
    axis = (left + right) / 2
    widths = np.linalg.norm(right - left, axis=1)
    if np.max(abs(widths - WIDTH)) > 0.0001:
        raise ValueError("Nonconstant asphalt width")
    ring = Polygon(np.vstack([left, right[::-1]]))
    if (
        not ring.is_valid
        or not LineString(left).is_simple
        or not LineString(right).is_simple
    ):
        raise ValueError("Pavement intersects/folds")
    center_turn = turns(axis)
    source_points = np.asarray(source_line.coords)[:, :2]
    source_turn = turns(source_points) if len(source_points) > 2 else np.array([])
    significant = source_turn[abs(source_turn) > 1e-4]
    single_sign = (
        int(np.sign(significant[0]))
        if len(significant) and np.all(np.sign(significant) == np.sign(significant[0]))
        else 0
    )
    if single_sign and np.sum(abs(significant)) > math.radians(30):
        for curve in (left, right, axis):
            lengths = np.linalg.norm(np.diff(curve, axis=0), axis=1)
            tolerance = 0.0004 * (1 / lengths[:-1] + 1 / lengths[1:])
            if (turns(curve) * single_sign < -tolerance).any():
                raise ValueError(
                    "Single source bend has a counter-turn in final boundary/axis"
                )
    # Every original segment is checked; a hook cannot disappear by averaging.
    for edge in (left, right):
        t = turns(edge)
        tolerance = 0.0008 / np.minimum(
            np.linalg.norm(np.diff(edge, axis=0), axis=1)[:-1],
            np.linalg.norm(np.diff(edge, axis=0), axis=1)[1:],
        )
        if ((t * np.sign(center_turn) < -tolerance) & (abs(center_turn) > 1e-5)).any():
            raise ValueError("Pavement counter-turns relative to bend")
        segments = np.linalg.norm(np.diff(edge, axis=0), axis=1)
        radius = (segments[:-1] + segments[1:]) / 2 / np.maximum(abs(t), 1e-12)
        if radius.min() < 1.5:
            raise ValueError("Inner radius below accepted minimum")
    displacement = source_line.hausdorff_distance(LineString(axis))
    if displacement > 1.0:
        raise ValueError(f"Source displacement exceeds 1 m ({displacement:.3f})")
    for a, b in itertools.pairwise(xy):
        for j in range(len(a) - 1):
            for p, q, r in ((a[j], a[j + 1], b[j]), (a[j + 1], b[j + 1], b[j])):
                if (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (
                    r[0] - p[0]
                ) >= -1e-9:
                    raise ValueError("Folded asphalt facet")
    return {
        "width_min_m": float(widths.min()),
        "width_max_m": float(widths.max()),
        "source_displacement_m": displacement,
        "both_edges_checked": True,
    }


def native_ground(heights, manifest, points):
    result = []
    for x, y in np.asarray(points).reshape(-1, 2):
        # Reuse the independently proved native triangle diagonal (not bilinear).
        candidates = triangle_candidates(
            heights,
            manifest,
            manifest["origin_epsg_m"][0] + x,
            manifest["origin_epsg_m"][1] - y,
        )
        result.append(candidates[0])
    return np.asarray(result).reshape(np.asarray(points).shape[:-1])


def prepare_patch(sections, terrain, manifest, path):
    samples = {}
    for a, b in itertools.pairwise(sections):
        for j in range(len(a) - 1):
            for tri in ((a[j], a[j + 1], b[j]), (a[j + 1], b[j + 1], b[j])):
                for gy in range(
                    math.floor(min(p[1] for p in tri) / STEP),
                    math.ceil(max(p[1] for p in tri) / STEP) + 1,
                ):
                    for gx in range(
                        math.floor(min(p[0] for p in tri) / STEP),
                        math.ceil(max(p[0] for p in tri) / STEP) + 1,
                    ):
                        z = _inside_triangle(gx * STEP, gy * STEP, tri)
                        if z is not None:
                            samples[gx, gy] = min(
                                samples.get((gx, gy), math.inf), z - 0.05
                            )
    # Include every interpolation-cell corner, then one neutral border.
    for row in sections:
        for x, y, z in row:
            gx, gy = math.floor(x / STEP), math.floor(y / STEP)
            for dx in (0, 1):
                for dy in (0, 1):
                    samples[gx + dx, gy + dy] = min(
                        samples.get((gx + dx, gy + dy), math.inf), z - 0.05
                    )
    for (gx, gy), z in list(samples.items()):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                samples[gx + dx, gy + dy] = min(
                    samples.get((gx + dx, gy + dy), math.inf), z
                )
    minx, miny = min(x for x, y in samples) - 1, min(y for x, y in samples) - 1
    maxx, maxy = max(x for x, y in samples) + 1, max(y for x, y in samples) + 1
    if minx < 0 or miny < 0 or maxx > 4032 or maxy > 4032:
        raise ValueError("CUT footprint outside existing Landscape")
    base = (
        _decode_height_m(0, manifest)
        + terrain[miny : maxy + 1, minx : maxx + 1].astype(float)
        * manifest["scale_z"]
        / 12800
    )
    patch = base.copy()
    for (x, y), target in samples.items():
        patch[y - miny, x - minx] = min(patch[y - miny, x - minx], target)
    depth = base - patch
    if depth.max() > CUT_CAP:
        raise ValueError(f"Ordinary 1 m CUT cap exceeded ({depth.max():.3f})")
    patch = (patch * 100).astype("<f4")
    patch.tofile(path.with_suffix(".f32"))
    payload = {
        "schema_version": 1,
        "region_id": "sa_calobra",
        "operation": "CUT_ONLY",
        "layer": "Road_Earthworks",
        "layer_encoding": "LANDSCAPE_TEXTURE_PATCH_WORLD_UNITS_F32_MIN",
        "blend_mode": "Min",
        "height_encoding": "WorldUnits",
        "zero_height_meaning": "WorldZero",
        "world_space_unit": "centimeter",
        "base_layer": "Base_DTM",
        "base_dtm_modified": False,
        "fill_authoring_permitted": False,
        "structure_authoring_permitted": False,
        "save_map": False,
        "patch_file": path.with_suffix(".f32").name,
        "patch_sha256": digest(path.with_suffix(".f32")),
        "max_cut_m": float(depth.max()),
        "rect": {
            "min_x": minx,
            "min_y": miny,
            "max_x": maxx,
            "max_y": maxy,
            "width": maxx - minx + 1,
            "height": maxy - miny + 1,
        },
    }
    path.write_text(json.dumps(payload) + "\n")
    return payload


def prepare(prepared, output, exact_sha):
    if output.exists():
        raise FileExistsError("Preserve previous network evidence")
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact SHA required")
    manifest = json.loads((prepared / "terrain-import.json").read_text())
    if (
        manifest["region_id"] != "sa_calobra"
        or manifest["vertices"] != [4033, 4033]
        or digest(prepared / "terrain.r16") != manifest["heightmap_sha256"]
    ):
        raise ValueError("Unadmitted terrain")
    terrain = np.fromfile(prepared / "terrain.r16", dtype="<u2").reshape(4033, 4033)
    if digest(SOURCE) != SOURCE_SHA:
        raise ValueError("Pinned IGN road source changed")
    source = json.loads(SOURCE.read_text())
    if source["numberReturned"] != len(source["features"]) or source[
        "numberMatched"
    ] != len(source["features"]):
        raise ValueError("Incomplete road source collection")
    output.mkdir(parents=True)
    origin = manifest["origin_epsg_m"]
    tf = Transformer.from_crs(4326, 25831, always_xy=True).transform
    area = box(origin[0] + 10, origin[1] - 2006, origin[0] + 2006, origin[1] - 10)
    _, accepted, _ = select_alignment()
    protected = accepted.buffer(8)
    for feature in source["features"]:
        if feature["id"] in ("VIAL_TR70190001288", "VIAL_TR70190001289"):
            protected = protected.union(
                transform(tf, shape(feature["geometry"])).buffer(12)
            )
    result = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "region_id": "sa_calobra",
        "source_sha256": digest(SOURCE),
        "heightmap_sha256": manifest["heightmap_sha256"],
        "width_m": WIDTH,
        "shoulder_m": SHOULDER,
        "width_evidence": "INFERRED_PREVIEW_ONLY",
        "base_dtm_modified": False,
        "map_saved": False,
        "canonical_source_modified": False,
        "road_physics_admitted": False,
        "approved": [],
        "blocked": [],
        "source_clipped_length_m": 0,
    }
    for feature in source["features"]:
        geometry = transform(tf, shape(feature["geometry"]))
        clipped = geometry.intersection(area)
        result["source_clipped_length_m"] += clipped.length
        if feature["properties"].get("surfacecategory") != "paved":
            result["blocked"].append(
                {
                    "id": feature["id"],
                    "reason": "Unverified paved surface",
                    "length_m": clipped.length,
                }
            )
            continue
        # Known Nudo loop requires a bridge/underpass recipe, not two terrain cuts.
        if feature["id"] in ("VIAL_TR70190001288", "VIAL_TR70190001289"):
            result["blocked"].append(
                {
                    "id": feature["id"],
                    "reason": "Grade-separated Nudo structure review",
                    "length_m": clipped.length,
                }
            )
            continue
        for part_index, line in enumerate(lines(clipped.difference(protected))):
            if line.length < 3:
                continue
            s, xy = smooth_axis(line)
            tangent = np.gradient(xy, s, axis=0)
            norm = np.linalg.norm(tangent, axis=1)
            normals = np.column_stack([-tangent[:, 1], tangent[:, 0]]) / norm[:, None]
            local = np.column_stack([xy[:, 0] - origin[0], origin[1] - xy[:, 1]])
            normals[:, 1] *= -1
            offsets = np.linspace(-WIDTH / 2, WIDTH / 2, 25)
            section_xy = (
                local[:, None, :] + normals[:, None, :] * offsets[None, :, None]
            )
            # UE reflected Y requires left-to-right sections with clockwise top faces.
            section_xy = section_xy[:, ::-1, :]
            heights = native_ground(terrain, manifest, section_xy)
            center = local_linear_fit(s, heights[:, 12], 7.5)
            bank = local_linear_fit(s, (heights[:, -1] - heights[:, 0]) / WIDTH, 20.0)
            # Preview design only: no survey banking or bus-width inference.
            bank *= min(
                1.0,
                0.04 / max(float(np.max(abs(bank))), 1e-12),
                0.0037 / max(float(np.max(abs(np.diff(bank) / np.diff(s)))), 1e-12),
            )
            ground = center[:, None] + bank[:, None] * offsets[None, :]
            sections = np.dstack([section_xy, ground + 0.04])
            for start in range(0, len(s) - 2, 200):
                end = min(start + 201, len(s))
                length = float(s[end - 1] - s[start])
                if end - start < 3:
                    continue
                ident = f"{feature['id']}-{part_index}-{start}"
                try:
                    source_window = substring(line, float(s[start]), float(s[end - 1]))
                    part = sections[start:end]
                    # Reflect section order back only for planar admission.
                    metrics = inspect_sections(
                        part,
                        transform(
                            lambda x, y, z=None: (x - origin[0], origin[1] - y),
                            source_window,
                        ),
                    )
                    if (
                        np.max(abs(np.diff(center[start:end]) / np.diff(s[start:end])))
                        > 0.31
                    ):
                        raise ValueError("Road grade exceeds reviewed preview limit")
                    if (
                        np.max(abs(np.diff(bank[start:end]) / np.diff(s[start:end])))
                        > 0.004
                    ):
                        raise ValueError("Banking transition exceeds reviewed rate")
                    delta = ground[start:end] - heights[start:end]
                    if delta.max() > SUPPORT_CAP:
                        raise ValueError("Support height needs structure review")
                    patch_path = output / (ident + "-cut.json")
                    support = shoulder_sections(part.tolist())
                    outer_ground = native_ground(
                        terrain, manifest, np.asarray(support)[:, [0, -1], :2]
                    )
                    _, _, support_proof = build_vertical_support(
                        support, outer_ground.tolist()
                    )
                    if support_proof["max_wall_height_m"] > SUPPORT_CAP:
                        raise ValueError("Shoulder support needs structure review")
                    patch = prepare_patch(
                        np.asarray(support), terrain, manifest, patch_path
                    )
                    result["approved"].append(
                        {
                            "id": ident,
                            "length_m": length,
                            "sections": part.tolist(),
                            "metrics": metrics,
                            "cut_manifest": patch_path.name,
                            "cut_sha256": digest(patch_path),
                            "max_cut_m": patch["max_cut_m"],
                        }
                    )
                except ValueError as exc:
                    result["blocked"].append(
                        {"id": ident, "length_m": length, "reason": str(exc)}
                    )
    result["approved_length_m"] = sum(x["length_m"] for x in result["approved"])
    result["blocked_length_m"] = sum(x["length_m"] for x in result["blocked"])
    result["protected_or_boundary_length_m"] = (
        result["source_clipped_length_m"]
        - result["approved_length_m"]
        - result["blocked_length_m"]
    )
    result["status"] = (
        "PARTIAL_PREVIEW_REQUIRES_REVIEW"
        if result["blocked"]
        else "PREVIEW_REQUIRES_NATIVE_PROOF"
    )
    (output / "network.json").write_text(
        json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n"
    )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared-terrain", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--exact-sha", required=True)
    a = p.parse_args()
    r = prepare(a.prepared_terrain, a.output_dir, a.exact_sha)
    print(
        json.dumps(
            {k: v for k, v in r.items() if k not in ("approved", "blocked")}, indent=2
        )
    )
    print("Approved windows:", len(r["approved"]), "Blocked:", len(r["blocked"]))
