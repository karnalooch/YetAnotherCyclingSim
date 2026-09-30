#!/usr/bin/env python3
"""Measure PCGEx SP638 presentation output against the prepared official road."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from shapely import distance, line_locate_point, points
from shapely.geometry import LineString


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--execution-output", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def percentile(values: np.ndarray, q: float) -> float:
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("metric input is empty or non-finite")
    return float(np.percentile(values, q))


def stats(values: np.ndarray) -> dict[str, float]:
    return {
        "p50_m": round(percentile(values, 50), 6),
        "p95_m": round(percentile(values, 95), 6),
        "max_m": round(float(values.max()), 6),
    }


def as_xyz(dataset: dict) -> np.ndarray:
    raw = dataset.get("points") or []
    if len(raw) < 2:
        raise ValueError("PCGEx dataset has fewer than two points")
    array = np.asarray(
        [[float(p["x_cm"]), float(p["y_cm"]), float(p["z_cm"])] for p in raw],
        dtype=np.float64,
    )
    if (
        array.ndim != 2
        or array.shape[1] != 3
        or not np.all(np.isfinite(array))
    ):
        raise ValueError("PCGEx dataset contains invalid coordinates")
    return array / 100.0


def main() -> int:
    args = parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    output = json.loads(args.execution_output.read_text(encoding="utf-8"))

    policy = source.get("yacs_policy") or {}
    if policy.get("presentation_only") is not True:
        raise SystemExit("source is not presentation-only")
    if policy.get("authoritative_route_geometry") is not False:
        raise SystemExit("source unexpectedly claims route authority")
    if policy.get("authoritative_physics") is not False:
        raise SystemExit("source unexpectedly claims physics authority")
    if output.get("status") != "PASS":
        raise SystemExit("PCGEx execution output did not report PASS")

    source_points = source.get("points") or []
    if len(source_points) < 2:
        raise SystemExit("source contains fewer than two points")

    source_xyz = (
        np.asarray(
            [
                [
                    float(point["ue_x_cm"]),
                    float(point["ue_y_cm"]),
                    float(point["ue_z_cm"]),
                ]
                for point in source_points
            ],
            dtype=np.float64,
        )
        / 100.0
    )
    if not np.all(np.isfinite(source_xyz)):
        raise SystemExit("source contains non-finite coordinates")

    datasets_raw = output.get("datasets") or []
    if len(datasets_raw) < 3:
        raise SystemExit("expected at least three PCGEx point datasets")
    datasets = [as_xyz(item) for item in datasets_raw]

    source_line = LineString(source_xyz[:, :2])
    if source_line.length <= 0:
        raise SystemExit("source polyline has zero length")

    source_sampled_s = np.concatenate(
        (
            [0.0],
            np.cumsum(
                np.linalg.norm(np.diff(source_xyz[:, :2], axis=0), axis=1)
            ),
        )
    )
    source_z = source_xyz[:, 2]

    distance_sets: list[np.ndarray] = []
    medians: list[float] = []
    for dataset in datasets:
        geometry_points = points(dataset[:, 0], dataset[:, 1])
        values = np.asarray(
            distance(geometry_points, source_line),
            dtype=np.float64,
        )
        distance_sets.append(values)
        medians.append(float(np.median(values)))

    center_index = int(np.argmin(medians))
    center = datasets[center_index]
    center_horizontal = distance_sets[center_index]

    center_geometry_points = points(center[:, 0], center[:, 1])
    projected_s = np.asarray(
        line_locate_point(source_line, center_geometry_points),
        dtype=np.float64,
    )
    reference_z = np.interp(projected_s, source_sampled_s, source_z)
    center_vertical = np.abs(center[:, 2] - reference_z)
    center_3d = np.hypot(center_horizontal, center_vertical)

    edge_indices = [index for index in range(len(datasets)) if index != center_index]
    edge_indices.sort(key=lambda index: medians[index])
    if len(edge_indices) < 2:
        raise SystemExit("PCGEx output is missing two corridor edge paths")
    edge_indices = edge_indices[:2]

    center_line = LineString(center[:, :2])
    edge_to_center: dict[str, dict[str, object]] = {}
    for label, index in zip(("edge_a", "edge_b"), edge_indices, strict=True):
        dataset = datasets[index]
        values = np.asarray(
            distance(points(dataset[:, 0], dataset[:, 1]), center_line),
            dtype=np.float64,
        )
        edge_to_center[label] = {
            "source_collection_index": int(
                datasets_raw[index].get("source_collection_index", index)
            ),
            **stats(values),
        }

    edge_a = datasets[edge_indices[0]]
    edge_b = datasets[edge_indices[1]]
    if edge_a.shape[0] == edge_b.shape[0]:
        full_width = np.linalg.norm(edge_a[:, :2] - edge_b[:, :2], axis=1)
        width_stats: dict[str, object] = stats(full_width)
    else:
        width_stats = {"status": "UNAVAILABLE_POINT_COUNT_MISMATCH"}

    report = {
        "schema_version": 1,
        "status": "PASS",
        "source_point_count": len(source_points),
        "pcgex_dataset_count": len(datasets),
        "centerline": {
            "source_collection_index": int(
                datasets_raw[center_index].get(
                    "source_collection_index",
                    center_index,
                )
            ),
            "point_count": int(center.shape[0]),
            "horizontal_deviation": stats(center_horizontal),
            "vertical_deviation": stats(center_vertical),
            "three_dimensional_deviation": stats(center_3d),
        },
        "corridor": {
            "expected_half_width_m": 3.0,
            "edge_to_center": edge_to_center,
            "edge_to_edge_width": width_stats,
        },
        "authority": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
        },
        "acceptance": {
            "numeric_thresholds": "REPORT_ONLY",
            "human_visual_review": "PENDING",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
