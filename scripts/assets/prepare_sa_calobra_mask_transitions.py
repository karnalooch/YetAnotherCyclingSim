"""Soften mask presentation, audit stream topology and preview bounded point reads."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.features import rasterize
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import nearest_points

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_sa_calobra_pcg_masks import verified_manifest
from prepare_sa_calobra_road_masks import distance_lower_bound
from read_sa_calobra_pcg_masks import evaluate
from verify_sa_calobra_lidar_masks import digest, verify as verify_lidar


def smoothstep(values):
    values = np.clip(values, 0, 1)
    return values * values * (3 - 2 * values)


def window_sum(values, radius):
    padded = np.pad(values.astype(np.float64), radius)
    summed = np.pad(padded.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    width = 2 * radius + 1
    return (
        summed[width:, width:]
        - summed[:-width, width:]
        - summed[width:, :-width]
        + summed[:-width, :-width]
    )


def density_weights(counts, selectors, distances):
    total = window_sum(counts.sum(0, dtype=np.uint64), 5)
    weights = np.zeros(selectors.shape, dtype=np.float32)
    for band, fade_m in enumerate([3, 6, 10]):
        share = np.divide(
            window_sum(counts[band + 1], 5),
            total,
            out=np.zeros_like(total),
            where=total > 0,
        )
        weights[band] = share * smoothstep(distances / fade_m)
        weights[band, selectors[band] != 1] = 0
        weights[band, selectors[band] == 255] = -32767
    return weights


def audit_network(records, bounds):
    lines = []
    for row in records:
        if row.get("source") != "regional-provisional-hydrography":
            continue
        g = shape(row["geometry"])
        for part in [g] if g.geom_type == "LineString" else g.geoms:
            lines.append((row["object_id"], part))
    if len(lines) < 2:
        raise ValueError("Insufficient regional stream topology")
    boundary = box(*bounds).boundary
    endpoints, repairs, candidates = [], [], []
    seen = set()
    for i, (source_id, line) in enumerate(lines):
        for end in [0, -1]:
            p = Point(line.coords[end])
            near = sorted(
                (p.distance(other), j) for j, (_, other) in enumerate(lines) if j != i
            )
            distance, target = near[0]
            q = nearest_points(p, lines[target][1])[1]
            ambiguous = len(near) > 1 and abs(near[1][0] - distance) < 0.01
            state = (
                "boundary_exit"
                if p.distance(boundary) < 0.01
                else "source_junction"
                if distance < 1e-5
                else "source_terminal_unverified"
            )
            row = {
                "object_id": source_id,
                "end": end,
                "xy_m": list(p.coords[0]),
                "nearest_object_id": lines[target][0],
                "gap_m": distance,
                "ambiguous_nearest": ambiguous,
                "status": state,
            }
            endpoints.append(row)
            if state != "source_terminal_unverified" or ambiguous or distance > 20:
                continue
            key = tuple(
                sorted(
                    (tuple(np.round(p.coords[0], 6)), tuple(np.round(q.coords[0], 6)))
                )
            )
            if key in seen:
                continue
            seen.add(key)
            connector = {
                **row,
                "geometry": mapping(LineString([p.coords[0], q.coords[0]])),
            }
            if distance <= 0.5:
                repairs.append(
                    {
                        **connector,
                        "status": "DERIVED_SUBPIXEL_TOPOLOGY_JOIN",
                        "authority": "One native cell maximum; display only, no source rewrite or flow/culvert/wetness inference",
                    }
                )
            else:
                candidates.append(
                    {
                        **connector,
                        "status": "UNVERIFIED_GAP_CANDIDATE",
                        "authority": "Nearest segment alone is insufficient evidence; never joined in admitted network",
                    }
                )
    return {
        "primary_source": "GOIB provisional hydrography; BTN remains independent context",
        "line_parts": len(lines),
        "endpoints": endpoints,
        "subpixel_joins": repairs,
        "unverified_gap_candidates": candidates,
        "flow_direction": "unknown",
        "wetness": "unknown",
        "culverts": "unverified; road overlays may hide an otherwise continuous stream",
        "all_terminals_are_errors": False,
    }


def prepare(pcg_path, context_path, lidar_path, road_path, baseline_path, output):
    if output.exists():
        raise FileExistsError("Preserve previous transition candidate")
    pcg, context, road = [
        verified_manifest(p) for p in [pcg_path, context_path, road_path]
    ]
    verify_lidar(lidar_path)
    lidar = json.loads(lidar_path.read_text(encoding="utf8"))
    baseline = json.loads(baseline_path.read_text(encoding="utf8"))
    if not (
        pcg["grid"]
        == context["grid"]
        == road["grid"]
        == lidar["grid"]
        == baseline["grid"]
    ):
        raise ValueError("Transition inputs disagree on frozen grid")
    for p in [context_path, lidar_path, road_path]:
        if not any(r["sha256"] == digest(p) for r in pcg["source_manifests"]):
            raise ValueError("Transition parent does not match admitted PCG package")
    for row in baseline["outputs"]:
        p = baseline_path.parent / row["path"]
        if (
            p.parent != baseline_path.parent
            or digest(p) != row["sha256"]
            or p.stat().st_size != row["size_bytes"]
        ):
            raise ValueError("Stale baseline review")

    def read(path):
        with rasterio.open(path) as ds:
            return ds.read(), ds.profile

    selectors, profile = read(pcg_path.parent / "vegetation-selectors.tif")
    reasons = read(pcg_path.parent / "exclusion-reasons.tif")[0][0]
    distances = read(pcg_path.parent / "exclusion-distance-lower-bound.tif")[0][0]
    counts = read(lidar_path.parent / "class-counts.tif")[0]
    weights = density_weights(counts, selectors, distances)
    bob = (reasons & 4) != 0
    feather = (1 - smoothstep(distance_lower_bound(bob, 0.5) / 6)).astype(np.float32)
    feather[bob] = 1
    # Retain every original hard exclusion. The feather attenuates only outside it.
    for band in range(3):
        selected = selectors[band] == 1
        weights[band, selected] *= 1 - feather[selected]
    records = json.loads(
        (context_path.parent / "context-exclusions.json").read_text(encoding="utf8")
    )["features"]
    audit = audit_network(records, [483000, 4407500, 485016.5, 4409516.5])
    grid_shape = reasons.shape

    def burn(rows):
        return (
            rasterize(
                rows,
                out_shape=grid_shape,
                transform=profile["transform"],
                dtype="uint8",
                all_touched=True,
            )
            if rows
            else np.zeros(grid_shape, dtype=np.uint8)
        )

    water_shapes = [
        (
            r["geometry"],
            2 if shape(r["geometry"]).geom_type in ("Polygon", "MultiPolygon") else 1,
        )
        for r in records
        if r["group"] == "water"
    ]
    water = burn(water_shapes)
    joined = burn([(r["geometry"], 3) for r in audit["subpixel_joins"]])
    if np.any((joined != 0) & ((reasons & 16) == 0)):
        raise ValueError("Subpixel join escapes original conservative water holdback")
    water[joined != 0] = 3
    gaps = burn([(r["geometry"], 1) for r in audit["unverified_gap_candidates"]])
    # No eligible domain grows, and original selectors/exclusions stay read-only.
    assert np.all(weights[selectors == 0] == 0)
    assert np.all(weights[selectors == 255] == -32767)
    image = np.array(Image.open(baseline_path.parent / "orthophoto.png").convert("RGB"))
    for band, color in enumerate([[170, 220, 90], [65, 175, 75], [15, 95, 45]]):
        alpha = np.maximum(0, weights[band]) * 0.7
        image = np.rint(
            image * (1 - alpha[:, :, None]) + np.array(color) * alpha[:, :, None]
        ).astype(np.uint8)
    image = np.rint(
        image * (1 - 0.48 * feather[:, :, None])
        + np.array([175, 105, 205]) * 0.48 * feather[:, :, None]
    ).astype(np.uint8)
    # Blue denotes the holdback only; ochre mapped centreline is not a wetness claim.
    held = (reasons & 16) != 0
    image[held] = np.rint(0.8 * image[held] + 0.2 * np.array([35, 115, 245])).astype(
        np.uint8
    )
    image[water != 0] = [155, 115, 55]
    image[gaps != 0] = [255, 110, 25]
    for bit, color in [
        (32, [255, 166, 0]),
        (8, [0, 230, 255]),
        (2, [245, 210, 130]),
        (1, [245, 245, 245]),
    ]:
        image[(reasons & bit) != 0] = color

    # Bounded spacing/weight trial with explicit example circles, not real UE assets.
    rng = np.random.default_rng(335)
    points = []
    roi = [850, 850, 1050, 1050]
    for band, (spacing, radius) in enumerate([(4, 0.35), (8, 1), (15, 2.5)]):
        for y in np.arange(roi[1] + spacing / 2, roi[3], spacing):
            for x in np.arange(roi[0] + spacing / 2, roi[2], spacing):
                x, yq = (
                    x + rng.uniform(-0.2, 0.2) * spacing,
                    y + rng.uniform(-0.2, 0.2) * spacing,
                )
                col, row = int(np.floor(x * 2 + 0.5)), int(np.floor(yq * 2 + 0.5))
                if rng.random() > max(0, float(weights[band, row, col])):
                    continue
                decision = evaluate(
                    selectors, distances, x * 100, yq * 100, band, radius, 0.5
                )
                if not decision["selected"]:
                    continue
                if any(
                    np.hypot(x - p["world_xy_m"][0], yq - p["world_xy_m"][1])
                    < radius + p["example_radius_m"]
                    for p in points
                ):
                    continue
                points.append(
                    {
                        "band": band,
                        "world_xy_m": [float(x), float(yq)],
                        "example_radius_m": radius,
                        "additional_clearance_m": 0.5,
                        "decision": decision,
                    }
                )
    sample = {
        "status": "POINT_DISTRIBUTION_REVIEW_ONLY",
        "seed": 335,
        "roi_world_xy_m": roi,
        "points": points,
        "real_assets_admitted": False,
        "pcgex_graph_executed": False,
        "limits": "Example circles and authored spacing; no species, actual mesh bounds, performance or planting admission",
    }
    output.mkdir(parents=True)
    products = []
    for name, array, nodata, meaning in [
        (
            "vegetation-density-weight.tif",
            weights,
            -32767,
            "Relative source-class return share over 11 cells/5.5m times authored exclusion fades; not physical plant density/confidence",
        ),
        (
            "bob-transition-weight.tif",
            feather[None],
            -32767,
            "Original BOB holdback weight1; outward 6m smooth fade only; hard exclusions unchanged",
        ),
        (
            "water-centreline-review.tif",
            water[None],
            255,
            "1 mapped line/point;2 mapped surface;3 derived <=0.5m display-only join; no water depth/wetness",
        ),
        (
            "water-gap-review.tif",
            gaps[None],
            255,
            "Unverified nearest-feature gap candidates; review only, not network repairs",
        ),
    ]:
        p = output / name
        with rasterio.open(
            p,
            "w",
            **{
                **profile,
                "dtype": str(array.dtype),
                "count": len(array),
                "nodata": nodata,
                "compress": "DEFLATE",
            },
        ) as ds:
            ds.write(array)
        products.append(
            {
                "path": name,
                "size_bytes": p.stat().st_size,
                "sha256": digest(p),
                "logical_sha256": hashlib.sha256(array.tobytes()).hexdigest(),
                "semantics": meaning,
            }
        )
    for name, data in [
        ("hydrology-topology-review.json", audit),
        ("placement-point-review.json", sample),
    ]:
        (output / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf8")
    Image.fromarray(image).save(output / "review-overlay.png")
    crop = (
        Image.fromarray(image)
        .crop((1700, 1700, 2100, 2100))
        .resize((1200, 1200), Image.Resampling.NEAREST)
    )
    draw = ImageDraw.Draw(crop)
    for point in points:
        x, y = point["world_xy_m"]
        r = point["example_radius_m"] * 6
        # Nearest 3x enlargement maps source pixel centre 0 to display centre 1.
        cx, cy = (x - 850) * 6 + 1, (y - 850) * 6 + 1
        draw.ellipse(
            (cx - r, cy - r, cx + r, cy + r),
            outline=[(170, 220, 90), (65, 175, 75), (15, 95, 45)][point["band"]],
            width=2,
        )
    crop.save(output / "placement-point-review.png")
    for p in sorted(output.iterdir()):
        if not any(r["path"] == p.name for r in products):
            products.append(
                {"path": p.name, "size_bytes": p.stat().st_size, "sha256": digest(p)}
            )
    report = {
        "schema_version": 1,
        "status": "TRANSITION_AND_TOPOLOGY_REVIEW_CANDIDATE",
        "geometry_mutation": False,
        "hard_exclusions_modified": False,
        "grid": pcg["grid"],
        "source_manifests": [
            {"path": p.parent.name + "/" + p.name, "sha256": digest(p)}
            for p in [pcg_path, context_path, lidar_path, road_path, baseline_path]
        ],
        "counts": {
            "subpixel_joins": len(audit["subpixel_joins"]),
            "unverified_gap_candidates": len(audit["unverified_gap_candidates"]),
            "example_points_by_band": [
                sum(p["band"] == b for p in points) for b in range(3)
            ],
        },
        "outputs": products,
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "admission": "Mask dressing and topology review only; existing hard exclusions remain binding; larger gaps/culverts/wetness unverified; no PCGEx graph, mesh placement or terrain changes",
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "transition-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in [
        "pcg-manifest",
        "context-manifest",
        "lidar-manifest",
        "road-manifest",
        "baseline-review",
        "output",
    ]:
        parser.add_argument("--" + name, required=True, type=Path)
    a = parser.parse_args()
    print(
        json.dumps(
            prepare(
                a.pcg_manifest,
                a.context_manifest,
                a.lidar_manifest,
                a.road_manifest,
                a.baseline_review,
                a.output,
            )["counts"]
        )
    )
