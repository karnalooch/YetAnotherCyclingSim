#!/usr/bin/env python3
"""Extract a deterministic native-metric DTM patch for Gate C.3 rider proof.

The patch is cut directly from the prepared 1 m hybrid MASE/Veneto GeoTIFF.
It never samples Unreal Landscape collision and never changes route/physics truth.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import Window

TARGET_CRS = "EPSG:32632"
TARGET_BOUNDS = (730406.587, 5148246.775, 738406.587, 5156246.775)
PATCH_EXTENT_M = 512.0
PATCH_VERTEX_COUNT = 513
CURVATURE_SAMPLE_STEP_M = 25.0
CURVATURE_HALF_WINDOW_M = 25.0
END_MARGIN_M = 100.0


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def source_heightfield_path() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "PreparedMasePstLidar1x1"
        / "passo_giau_mase_pst_hybrid_1m_8km_epsg32632.tif"
    )


def source_road_path() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "PreparedRoad"
        / "passo_giau_sp638_ue_centerline.json"
    )


def output_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "PreparedNearField"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _points(payload: dict[str, Any]) -> list[dict[str, float]]:
    points = payload.get("points")
    if not isinstance(points, list) or len(points) < 8:
        raise ValueError("prepared SP638 input contains too few sampled points")
    result: list[dict[str, float]] = []
    previous_s = -1.0
    for item in points:
        if not isinstance(item, dict):
            raise ValueError("prepared SP638 point is not an object")
        point = {
            "s_m": float(item["s_m"]),
            "x": float(item["x_epsg32632_m"]),
            "y": float(item["y_epsg32632_m"]),
        }
        if point["s_m"] <= previous_s:
            raise ValueError("prepared SP638 station distances are not strictly increasing")
        previous_s = point["s_m"]
        result.append(point)
    return result


def _segment_index(points: list[dict[str, float]], distance_m: float) -> int:
    if distance_m <= points[0]["s_m"]:
        return 0
    for index in range(len(points) - 1):
        if points[index]["s_m"] <= distance_m <= points[index + 1]["s_m"]:
            return index
    return len(points) - 2


def _sample_xy(points: list[dict[str, float]], distance_m: float) -> tuple[float, float]:
    index = _segment_index(points, distance_m)
    left = points[index]
    right = points[index + 1]
    span = right["s_m"] - left["s_m"]
    if span <= 0.0:
        raise ValueError("prepared SP638 segment has non-positive station span")
    alpha = max(0.0, min(1.0, (distance_m - left["s_m"]) / span))
    return (
        left["x"] + (right["x"] - left["x"]) * alpha,
        left["y"] + (right["y"] - left["y"]) * alpha,
    )


def _direction_at(points: list[dict[str, float]], distance_m: float) -> tuple[float, float]:
    index = _segment_index(points, distance_m)
    left = points[index]
    right = points[index + 1]
    dx = right["x"] - left["x"]
    dy = right["y"] - left["y"]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        raise ValueError("prepared SP638 contains a zero-length segment")
    return dx / length, dy / length


def choose_hairpin(points: list[dict[str, float]]) -> tuple[float, float, float, float]:
    length_m = points[-1]["s_m"]
    if length_m <= 2.0 * END_MARGIN_M:
        raise ValueError(f"prepared SP638 is unexpectedly short: {length_m:.1f} m")

    best_distance = END_MARGIN_M
    best_score = -1.0
    distance = END_MARGIN_M
    while distance <= length_m - END_MARGIN_M + 1e-9:
        before = _direction_at(
            points,
            max(0.0, distance - CURVATURE_HALF_WINDOW_M),
        )
        after = _direction_at(
            points,
            min(length_m, distance + CURVATURE_HALF_WINDOW_M),
        )
        dot = max(-1.0, min(1.0, before[0] * after[0] + before[1] * after[1]))
        score = 1.0 - dot
        if score > best_score:
            best_score = score
            best_distance = distance
        distance += CURVATURE_SAMPLE_STEP_M

    x, y = _sample_xy(points, best_distance)
    return best_distance, best_score, x, y


def main() -> int:
    source = source_heightfield_path()
    road = source_road_path()
    if not source.is_file():
        raise FileNotFoundError(f"native metric DTM is missing: {source}")
    if not road.is_file():
        raise FileNotFoundError(f"prepared SP638 input is missing: {road}")

    road_payload = json.loads(road.read_text(encoding="utf-8"))
    points = _points(road_payload)
    focus_s_m, curvature_score, focus_x, focus_y = choose_hairpin(points)

    with rasterio.open(source) as dataset:
        if dataset.count != 1:
            raise ValueError(f"expected one DTM band, got {dataset.count}")
        if dataset.crs is None or dataset.crs.to_epsg() != 32632:
            raise ValueError(f"expected {TARGET_CRS}, got {dataset.crs}")
        cell_x = abs(float(dataset.transform.a))
        cell_y = abs(float(dataset.transform.e))
        if abs(cell_x - 1.0) > 1e-6 or abs(cell_y - 1.0) > 1e-6:
            raise ValueError(
                f"native DTM spacing drifted from 1 m: x={cell_x} y={cell_y}"
            )

        center_row, center_col = dataset.index(focus_x, focus_y)
        half = PATCH_VERTEX_COUNT // 2
        row_off = center_row - half
        col_off = center_col - half
        if (
            row_off < 0
            or col_off < 0
            or row_off + PATCH_VERTEX_COUNT > dataset.height
            or col_off + PATCH_VERTEX_COUNT > dataset.width
        ):
            raise ValueError(
                "selected C.3 hairpin patch falls outside native DTM bounds: "
                f"row={center_row} col={center_col}"
            )

        window = Window(
            col_off=col_off,
            row_off=row_off,
            width=PATCH_VERTEX_COUNT,
            height=PATCH_VERTEX_COUNT,
        )
        masked = dataset.read(1, window=window, masked=True).astype(np.float32)
        if np.ma.count_masked(masked):
            raise ValueError(
                f"native C.3 patch contains {int(np.ma.count_masked(masked))} masked samples"
            )
        heights = np.asarray(masked, dtype=np.float32)
        if heights.shape != (PATCH_VERTEX_COUNT, PATCH_VERTEX_COUNT):
            raise ValueError(f"native C.3 patch shape drifted: {heights.shape}")
        if not np.all(np.isfinite(heights)):
            raise ValueError("native C.3 patch contains non-finite heights")

        window_transform = dataset.window_transform(window)
        north_x, north_y = rasterio.transform.xy(
            window_transform,
            0,
            0,
            offset="center",
        )
        south_x, south_y = rasterio.transform.xy(
            window_transform,
            PATCH_VERTEX_COUNT - 1,
            0,
            offset="center",
        )
        east_x, _ = rasterio.transform.xy(
            window_transform,
            0,
            PATCH_VERTEX_COUNT - 1,
            offset="center",
        )

    # Raster rows run north -> south, while build_terrain_skin_mesh expects UE Y
    # to descend across rows. UE Y increases southward, so reverse the rows.
    ue_rows = np.flipud(heights).astype("<f4", copy=False)
    first_ue_x_m = (float(north_x) - TARGET_BOUNDS[0])
    first_ue_y_m = (TARGET_BOUNDS[3] - float(south_y))
    last_ue_x_m = (float(east_x) - TARGET_BOUNDS[0])
    last_ue_y_m = (TARGET_BOUNDS[3] - float(north_y))

    out = output_root()
    out.mkdir(parents=True, exist_ok=True)
    binary_path = out / "passo_giau_native_dtm_patch_f32le.bin"
    metadata_path = out / "passo_giau_native_dtm_patch.json"
    binary_path.write_bytes(ue_rows.tobytes(order="C"))

    metadata = {
        "schema_version": 1,
        "proof_gate": "C.3",
        "source": {
            "kind": "prepared native metric DTM",
            "path": str(source.relative_to(repository_root())).replace("\\", "/"),
            "sha256": sha256_file(source),
            "crs": TARGET_CRS,
            "grid_step_m": 1.0,
            "landscape_collision_sampled": False,
        },
        "hairpin_selection": {
            "source": "prepared official SP638 presentation centerline",
            "focus_s_m": round(focus_s_m, 3),
            "curvature_score": round(curvature_score, 9),
            "focus_epsg32632_m": [round(focus_x, 3), round(focus_y, 3)],
            "canonical_route_authority_preserved": True,
        },
        "grid": {
            "extent_m": PATCH_EXTENT_M,
            "rows": PATCH_VERTEX_COUNT,
            "columns": PATCH_VERTEX_COUNT,
            "sample_count": PATCH_VERTEX_COUNT * PATCH_VERTEX_COUNT,
            "step_x_m": 1.0,
            "step_y_m": 1.0,
            "x_order": "ue_x_ascending",
            "row_order": "ue_y_descending",
            "first_ue_x_m": round(first_ue_x_m, 6),
            "first_ue_y_m": round(first_ue_y_m, 6),
            "last_ue_x_m": round(last_ue_x_m, 6),
            "last_ue_y_m": round(last_ue_y_m, 6),
            "elevation_min_m": round(float(np.min(ue_rows)), 6),
            "elevation_max_m": round(float(np.max(ue_rows)), 6),
        },
        "binary": {
            "file": binary_path.name,
            "dtype": "float32-le",
            "layout": "row-major",
            "byte_count": binary_path.stat().st_size,
            "sha256": sha256_file(binary_path),
        },
        "yacs_policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "native_dtm_direct": True,
            "smoothing_applied": False,
            "road_constraints_applied": False,
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "Gate C.3 native DTM patch: "
        f"{PATCH_VERTEX_COUNT}x{PATCH_VERTEX_COUNT} @ 1 m, "
        f"focus_s={focus_s_m:.1f} m, curvature={curvature_score:.6f}"
    )
    print(f"[ok] {metadata_path}")
    print(f"[ok] {binary_path}: {binary_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
