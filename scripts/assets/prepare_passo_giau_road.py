#!/usr/bin/env python3
"""Prepare the official SP638 centerline for the Passo Giau terrain spike.

This produces a deterministic road centerline, samples presentation elevation
from the same Veneto 5 m DTM used by the Landscape, converts points to the
isolated map's local Unreal coordinates, and renders a GIS alignment proof.

The output is presentation-only. It does not replace YACS route/physics truth.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from shapely.geometry import LineString, MultiLineString, Point, box, shape
from shapely.ops import linemerge

TARGET_CRS = "EPSG:32632"
TARGET_BOUNDS = (730406.587, 5148246.775, 738406.587, 5156246.775)
ROAD_ROUTE_ID = "000000027157"
ROAD_NAME = "SP 638 DEL PASSO GIAU (BL)"
SAMPLE_SPACING_M = 10.0
ROAD_SURFACE_OFFSET_CM = 15.0
Z_SMOOTH_WINDOW = 5
MAX_JOIN_GAP_M = 1.0\nSPLINE_SIMPLIFY_TOLERANCE_M = 3.0


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def source_root() -> Path:
    return repository_root() / "ExternalAssets" / "Terrain" / "PassoGiau"


def road_root() -> Path:
    return source_root() / "RoadNetwork"


def terrain_root() -> Path:
    return source_root() / "PreparedVenetoLidar5m"


def output_root() -> Path:
    return source_root() / "PreparedRoad"


def feature_line(feature: dict[str, Any]) -> LineString:
    geom = shape(feature["geometry"])
    if isinstance(geom, LineString):
        return geom
    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        if isinstance(merged, LineString):
            return merged
        parts = sorted(merged.geoms, key=lambda part: part.length, reverse=True)
        if not parts:
            raise RuntimeError(f"empty road geometry: {feature.get('id')}")
        if sum(part.length for part in parts[1:]) > 0.5:
            raise RuntimeError(
                f"road feature has disconnected multipart geometry: {feature.get('id')}"
            )
        return parts[0]
    raise RuntimeError(f"unexpected road geometry: {geom.geom_type}")


def order_features(features: list[dict[str, Any]]) -> list[tuple[dict[str, Any], bool]]:
    adjacency: dict[str, list[int]] = {}
    edges: list[tuple[str, str]] = []
    for index, feature in enumerate(features):
        props = feature.get("properties") or {}
        start = str(props.get("nodo_ini") or "").strip()
        end = str(props.get("nodo_fin") or "").strip()
        if not start or not end or start == end:
            raise RuntimeError(f"invalid topology nodes: {feature.get('id')}")
        edges.append((start, end))
        adjacency.setdefault(start, []).append(index)
        adjacency.setdefault(end, []).append(index)

    components: list[set[int]] = []
    remaining = set(range(len(features)))
    while remaining:
        seed = next(iter(remaining))
        stack = [seed]
        component: set[int] = set()
        while stack:
            edge_index = stack.pop()
            if edge_index in component:
                continue
            component.add(edge_index)
            remaining.discard(edge_index)
            u, v = edges[edge_index]
            for node in (u, v):
                for neighbor in adjacency[node]:
                    if neighbor not in component:
                        stack.append(neighbor)
        components.append(component)

    components.sort(
        key=lambda comp: sum(
            float((features[index].get("properties") or {}).get("lunghez") or 0.0)
            for index in comp
        ),
        reverse=True,
    )
    chosen = components[0]
    chosen_length = sum(
        float((features[index].get("properties") or {}).get("lunghez") or 0.0)
        for index in chosen
    )
    total_length = sum(
        float((feature.get("properties") or {}).get("lunghez") or 0.0)
        for feature in features
    )
    if chosen_length < total_length * 0.99:
        raise RuntimeError(
            f"SP638 source is unexpectedly disconnected: "
            f"largest={chosen_length:.1f} m total={total_length:.1f} m"
        )

    degree: dict[str, int] = {}
    for index in chosen:
        u, v = edges[index]
        degree[u] = degree.get(u, 0) + 1
        degree[v] = degree.get(v, 0) + 1
    endpoints = sorted(node for node, value in degree.items() if value == 1)
    branch_nodes = sorted(node for node, value in degree.items() if value > 2)
    if branch_nodes:
        raise RuntimeError(f"SP638 topology branches inside AOI: {branch_nodes}")
    if len(endpoints) != 2:
        raise RuntimeError(f"SP638 expected two AOI endpoints, got {endpoints}")

    current = endpoints[0]
    visited: set[int] = set()
    ordered: list[tuple[dict[str, Any], bool]] = []
    while len(visited) < len(chosen):
        candidates = [
            index
            for index in adjacency[current]
            if index in chosen and index not in visited
        ]
        if len(candidates) != 1:
            raise RuntimeError(
                f"SP638 traversal ambiguity at node {current}: {candidates}"
            )
        index = candidates[0]
        visited.add(index)
        u, v = edges[index]
        forward = current == u
        ordered.append((features[index], forward))
        current = v if forward else u

    if current != endpoints[1]:
        raise RuntimeError("SP638 topology traversal did not reach the opposite endpoint")
    return ordered


def concatenate_centerline(
    ordered: list[tuple[dict[str, Any], bool]],
) -> LineString:
    coordinates: list[tuple[float, float]] = []
    for feature, forward in ordered:
        line = feature_line(feature)
        segment = list(line.coords)
        if not forward:
            segment.reverse()
        if coordinates:
            gap = math.dist(coordinates[-1][:2], segment[0][:2])
            if gap > MAX_JOIN_GAP_M:
                # Some datasets encode line orientation independently from node
                # orientation. Try the spatially continuous orientation before
                # treating this as a source defect.
                reverse_gap = math.dist(coordinates[-1][:2], segment[-1][:2])
                if reverse_gap < gap:
                    segment.reverse()
                    gap = reverse_gap
            if gap > MAX_JOIN_GAP_M:
                raise RuntimeError(
                    f"SP638 source segments do not join: gap={gap:.3f} m"
                )
            if gap < 1e-6:
                segment = segment[1:]
        coordinates.extend((float(x), float(y)) for x, y, *_rest in segment)

    if len(coordinates) < 2:
        raise RuntimeError("SP638 centerline contains too few coordinates")

    line = LineString(coordinates)
    clipped = line.intersection(box(*TARGET_BOUNDS))
    if isinstance(clipped, MultiLineString):
        parts = sorted(clipped.geoms, key=lambda part: part.length, reverse=True)
        secondary = sum(part.length for part in parts[1:])
        if secondary > 5.0:
            raise RuntimeError(
                f"SP638 enters AOI in multiple significant parts; secondary={secondary:.1f} m"
            )
        clipped = parts[0]
    if not isinstance(clipped, LineString) or clipped.length < 100.0:
        raise RuntimeError("clipped SP638 centerline is not a usable LineString")
    return clipped


def moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1:
        return values.astype(np.float64, copy=True)
    if window % 2 == 0:
        raise ValueError("smoothing window must be odd")
    radius = window // 2
    padded = np.pad(values.astype(np.float64), (radius, radius), mode="edge")
    kernel = np.ones(window, dtype=np.float64) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def main() -> int:
    try:
        source_path = road_root() / "passo_giau_sp638_source.geojson"
        terrain_path = terrain_root() / "passo_giau_veneto_lidar_5m_8km_epsg32632.tif"
        hillshade_path = terrain_root() / "passo_giau_veneto_lidar_5m_hillshade.png"
        download_report_path = road_root() / "road-download-report.json"
        for path in (source_path, terrain_path, hillshade_path, download_report_path):
            if not path.is_file():
                raise RuntimeError(f"missing required input: {path}")

        source = json.loads(source_path.read_text(encoding="utf-8"))
        features = source.get("features") or []
        if not isinstance(features, list) or not features:
            raise RuntimeError("SP638 source GeoJSON has no features")
        for feature in features:
            props = feature.get("properties") or {}
            if str(props.get("id_perc") or "").strip() != ROAD_ROUTE_ID:
                raise RuntimeError("SP638 source contains another route id")
            if str(props.get("percorsoam") or "").strip().upper() != ROAD_NAME:
                raise RuntimeError("SP638 source contains another road name")

        ordered = order_features(features)
        centerline = concatenate_centerline(ordered)
        length_m = float(centerline.length)

        distances = np.arange(0.0, length_m, SAMPLE_SPACING_M, dtype=np.float64)
        if distances.size == 0 or distances[-1] < length_m:
            distances = np.append(distances, length_m)
        xy = np.array(
            [[centerline.interpolate(float(distance)).x,
              centerline.interpolate(float(distance)).y]
             for distance in distances],
            dtype=np.float64,
        )

        with rasterio.open(terrain_path) as dataset:
            if str(dataset.crs) != TARGET_CRS:
                raise RuntimeError(
                    f"terrain CRS mismatch: actual={dataset.crs} expected={TARGET_CRS}"
                )
            raw_z = np.array(
                [float(sample[0]) for sample in dataset.sample(xy.tolist())],
                dtype=np.float64,
            )
        if not np.all(np.isfinite(raw_z)):
            raise RuntimeError("DTM sampling returned non-finite road elevations")

        smooth_z = moving_average(raw_z, Z_SMOOTH_WINDOW)
        if smooth_z.size != distances.size:
            raise RuntimeError("road elevation smoothing changed point count")

        spline_line = centerline.simplify(
            SPLINE_SIMPLIFY_TOLERANCE_M,
            preserve_topology=False,
        )
        if not isinstance(spline_line, LineString) or len(spline_line.coords) < 2:
            raise RuntimeError("SP638 spline simplification produced invalid geometry")
        spline_points: list[dict[str, float]] = []
        for index, (x_value, y_value) in enumerate(spline_line.coords):
            x = float(x_value)
            y = float(y_value)
            s = float(centerline.project(Point(x, y)))
            z = float(np.interp(s, distances, smooth_z))
            spline_points.append(
                {
                    "index": index,
                    "s_m": round(s, 3),
                    "x_epsg32632_m": round(x, 3),
                    "y_epsg32632_m": round(y, 3),
                    "ue_x_cm": round((x - TARGET_BOUNDS[0]) * 100.0, 3),
                    "ue_y_cm": round((TARGET_BOUNDS[3] - y) * 100.0, 3),
                    "ue_z_cm": round(
                        z * 100.0 + ROAD_SURFACE_OFFSET_CM,
                        3,
                    ),
                }
            )

        segment_ds = np.diff(distances)
        segment_dz = np.diff(smooth_z)
        grade_pct = np.divide(
            segment_dz * 100.0,
            segment_ds,
            out=np.zeros_like(segment_dz),
            where=segment_ds > 0.0,
        )

        left, bottom, right, top = TARGET_BOUNDS
        points: list[dict[str, float]] = []
        for index, (distance, coord, raw, smooth) in enumerate(
            zip(distances, xy, raw_z, smooth_z, strict=True)
        ):
            x, y = float(coord[0]), float(coord[1])
            points.append(
                {
                    "index": index,
                    "s_m": round(float(distance), 3),
                    "x_epsg32632_m": round(x, 3),
                    "y_epsg32632_m": round(y, 3),
                    "z_dtm_raw_m": round(float(raw), 3),
                    "z_presentation_m": round(float(smooth), 3),
                    "ue_x_cm": round((x - left) * 100.0, 3),
                    # Raster row 0 / Landscape Y=0 corresponds to north/top.
                    "ue_y_cm": round((top - y) * 100.0, 3),
                    "ue_z_cm": round(
                        float(smooth) * 100.0 + ROAD_SURFACE_OFFSET_CM,
                        3,
                    ),
                }
            )

        out = output_root()
        out.mkdir(parents=True, exist_ok=True)
        centerline_geojson_path = out / "passo_giau_sp638_centerline.geojson"
        road_json_path = out / "passo_giau_sp638_ue_centerline.json"
        overlay_path = out / "passo_giau_sp638_hillshade_overlay.png"
        report_path = out / "road-preparation-report.json"

        centerline_geojson = {
            "type": "FeatureCollection",
            "name": "SP 638 DEL PASSO GIAU (BL) — YACS AOI centerline",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "name": ROAD_NAME,
                        "route_id": ROAD_ROUTE_ID,
                        "length_m": round(length_m, 3),
                        "presentation_only": True,
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [round(float(x), 3), round(float(y), 3)]
                            for x, y in centerline.coords
                        ],
                    },
                }
            ],
        }
        centerline_geojson_path.write_text(
            json.dumps(centerline_geojson, ensure_ascii=False, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )

        download_report = json.loads(
            download_report_path.read_text(encoding="utf-8")
        )
        road_payload = {
            "schema_version": 1,
            "name": ROAD_NAME,
            "route_id": ROAD_ROUTE_ID,
            "source_provider": "Regione del Veneto",
            "source_layer": download_report["layer"],
            "source_license": download_report["license"],
            "required_attribution": download_report["required_attribution"],
            "source_positional_accuracy_m": download_report[
                "reported_positional_accuracy_m"
            ],
            "target_crs": TARGET_CRS,
            "target_bounds_epsg32632": [left, bottom, right, top],
            "ue_local_mapping": {
                "x_cm": "(easting - left) * 100",
                "y_cm": "(top - northing) * 100",
                "z_cm": "smoothed_DTM_m * 100 + road_surface_offset_cm",
                "road_surface_offset_cm": ROAD_SURFACE_OFFSET_CM,
            },
            "sample_spacing_m": SAMPLE_SPACING_M,
            "z_smoothing_window_points": Z_SMOOTH_WINDOW,
            "spline_simplify_tolerance_m": SPLINE_SIMPLIFY_TOLERANCE_M,
            "length_m": round(length_m, 3),
            "point_count": len(points),
            "points": points,
            "spline_control_point_count": len(spline_points),
            "spline_points": spline_points,
            "yacs_policy": {
                "presentation_only": True,
                "authoritative_route_geometry": False,
                "authoritative_physics": False,
            },
        }
        road_json_path.write_text(
            json.dumps(road_payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )

        image = Image.open(hillshade_path).convert("RGB")
        width, height = image.size
        draw = ImageDraw.Draw(image)
        pixels = [
            (
                int(round((float(x) - left) / (right - left) * (width - 1))),
                int(round((top - float(y)) / (top - bottom) * (height - 1))),
            )
            for x, y in centerline.coords
        ]
        draw.line(pixels, fill=(0, 0, 0), width=9, joint="curve")
        draw.line(pixels, fill=(255, 64, 32), width=5, joint="curve")
        for point in (pixels[0], pixels[-1]):
            x, y = point
            draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(255, 255, 255))
            draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=(255, 64, 32))
        image.save(overlay_path)

        report = {
            "schema_version": 1,
            "road": ROAD_NAME,
            "route_id": ROAD_ROUTE_ID,
            "source_feature_count": len(features),
            "ordered_feature_count": len(ordered),
            "centerline_length_m": round(length_m, 3),
            "sample_spacing_m": SAMPLE_SPACING_M,
            "sample_count": len(points),
            "spline_simplify_tolerance_m": SPLINE_SIMPLIFY_TOLERANCE_M,
            "spline_control_point_count": len(spline_points),
            "dtm_elevation_m": {
                "raw_min": round(float(raw_z.min()), 3),
                "raw_max": round(float(raw_z.max()), 3),
                "presentation_min": round(float(smooth_z.min()), 3),
                "presentation_max": round(float(smooth_z.max()), 3),
            },
            "presentation_grade_pct": {
                "p50_abs": round(float(np.percentile(np.abs(grade_pct), 50)), 3),
                "p95_abs": round(float(np.percentile(np.abs(grade_pct), 95)), 3),
                "max_abs": round(float(np.max(np.abs(grade_pct))), 3),
            },
            "outputs": {
                "centerline_geojson": centerline_geojson_path.name,
                "ue_centerline_json": road_json_path.name,
                "hillshade_overlay": overlay_path.name,
            },
            "visual_acceptance": "PENDING_HUMAN_REVIEW",
            "yacs_policy": {
                "presentation_only": True,
                "authoritative_route_geometry": False,
                "authoritative_physics": False,
            },
        }
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        print("Passo Giau SP638 preparation")
        print(f"  source features: {len(features)}")
        print(f"  ordered features: {len(ordered)}")
        print(f"  centerline: {length_m:.1f} m")
        print(f"  sampled points: {len(points)} @ {SAMPLE_SPACING_M:.1f} m")
        print(
            f"  spline controls: {len(spline_points)} "
            f"@ <= {SPLINE_SIMPLIFY_TOLERANCE_M:.1f} m 2D deviation"
        )
        print(
            "  elevation: "
            f"{smooth_z.min():.1f} .. {smooth_z.max():.1f} m"
        )
        print(
            "  grade |p95| / max: "
            f"{np.percentile(np.abs(grade_pct), 95):.1f}% / "
            f"{np.max(np.abs(grade_pct)):.1f}%"
        )
        print(f"[ok] {overlay_path}")
        print(f"[ok] {road_json_path}")
        return 0
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
