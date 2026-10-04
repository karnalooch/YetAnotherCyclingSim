"""Construct the exact visually accepted network and join its hairpin boundaries."""

import json
import math

import numpy as np

from scripts.geometry.network_pavement import shoulder_sections, surface_inspection
from scripts.geometry.network_visual_preview import preview_fingerprint
from scripts.geometry.reviewed_network import (
    REVIEWED_COMMIT,
    REVIEWED_FINGERPRINT,
    validate_reviewed_geometry,
    validate_slab,
)
from scripts.geometry.smooth_road_ribbon import build_smooth_road_ribbon


def join_sections(network_rows, hairpin_rows):
    """Hermite join with identical end sections and matched endpoint directions."""
    a, before = np.asarray(network_rows[-1]), np.asarray(network_rows[-2])
    b, after = np.asarray(hairpin_rows[0]), np.asarray(hairpin_rows[1])
    length = float(np.linalg.norm(b[12, :2] - a[12, :2]))
    if not 0.1 < length < 12:
        raise ValueError("Hairpin connection is outside the admitted 8 m boundary gap")
    da = (a - before) / np.linalg.norm(a[12, :2] - before[12, :2]) * length
    db = (after - b) / np.linalg.norm(after[12, :2] - b[12, :2]) * length
    rows = []
    for t in np.linspace(0, 1, max(3, math.ceil(length / 0.25) + 1)):
        row = (
            (2 * t**3 - 3 * t**2 + 1) * a
            + (t**3 - 2 * t**2 + t) * da
            + (-2 * t**3 + 3 * t**2) * b
            + (t**3 - t**2) * db
        )
        # Interpolating opposing edge tangents can pinch a short join. Solve
        # width with the alignment: smoothstep returns exactly to both bases.
        blend = 3 * t * t - 2 * t**3
        width = (1 - blend) * np.linalg.norm(
            a[-1, :2] - a[0, :2]
        ) + blend * np.linalg.norm(b[-1, :2] - b[0, :2])
        row[:, :2] = row[12, :2] + (row[:, :2] - row[12, :2]) * width / np.linalg.norm(
            row[-1, :2] - row[0, :2]
        )
        rows.append(row.tolist())
    rows[0], rows[-1] = a.tolist(), b.tolist()
    validate_slab(rows)
    widths = [math.dist(row[0][:2], row[-1][:2]) for row in rows]
    if min(widths) < 4.99 or max(widths) > 5.51:
        raise ValueError("Hairpin connector width is outside the endpoint envelope")
    return rows


def hairpin_connections(network, profile):
    vertices, _, _ = build_smooth_road_ribbon(profile)
    rows = [vertices[i * 25 : (i + 1) * 25] for i in range(len(profile["stations"]))]
    windows = network["approved"] + network["full_preview"]["rejected_surfaces"]
    connections = []
    for label, target in (
        ("entry", rows),
        ("exit", [list(reversed(r)) for r in reversed(rows)]),
    ):
        candidates = []
        for item in windows:
            source = item["sections"]
            for directed in (source, [list(reversed(r)) for r in reversed(source)]):
                distance = math.dist(directed[-1][12][:2], target[0][12][:2])
                candidates.append((distance, item["id"], directed))
        distance, ident, source = min(candidates, key=lambda x: x[0])
        if distance > 12:
            raise ValueError("Missing network endpoint next to the accepted hairpin")
        sections = join_sections(source, target)
        connections.append(
            {
                "id": "hairpin-" + label,
                "sections": sections,
                "connected_window_id": ident,
                "endpoint_residual_m": max(
                    math.dist(p, q)
                    for actual, expected in (
                        (sections[0], source[-1]),
                        (sections[-1], target[0]),
                    )
                    for p, q in zip(actual, expected, strict=True)
                ),
                "length_m": sum(
                    math.dist(a[12], b[12]) for a, b in zip(sections, sections[1:])
                ),
                "connection": True,
            }
        )
    return connections


def prepare_reviewed(network, terrain, manifest, output):
    # Import at call time: the existing producer owns raster preparation.
    from scripts.assets.prepare_current_landscape_roads import (
        digest,
        prepare_patch,
        technical_patch_tiles,
    )

    validate_reviewed_geometry(network)
    profile = json.loads((output.parent / "ma2141-profile-candidate.json").read_text())
    if (
        profile["exact_sha"] != network["exact_sha"]
        or profile["heightmap_sha256"] != network["heightmap_sha256"]
    ):
        raise ValueError("Hairpin connection provenance mismatch")
    connections = hairpin_connections(network, profile)
    reviewed = []
    for item in network["full_preview"]["rejected_surfaces"] + connections:
        sections = item["sections"]
        validate_slab(sections)
        stations = np.r_[
            0,
            np.cumsum(
                [
                    math.dist(a[12][:2], b[12][:2])
                    for a, b in zip(sections, sections[1:])
                ]
            ),
        ]
        for index, (start, end) in enumerate(
            technical_patch_tiles(0, len(sections) - 1, stations)
        ):
            part = sections[start : end + 1]
            ident = "reviewed-" + item["id"] + "-" + str(index)
            path = output / (ident + ".json")
            patch = prepare_patch(
                np.asarray(shoulder_sections(part)),
                terrain,
                manifest,
                path,
                reviewed_geometry=True,
            )
            reviewed.append(
                {
                    "id": ident,
                    "sections": part,
                    "length_m": float(stations[end] - stations[start]),
                    "technical_patch_tile": True,
                    "decision_interval_id": item["id"],
                    "cut_manifest": path.name,
                    "cut_sha256": digest(path),
                    "max_cut_m": patch["max_cut_m"],
                    "surface_inspection": surface_inspection(part),
                    "owner_reviewed_geometry": True,
                    "connection": item.get("connection", False),
                }
            )
    network["owner_reviewed"] = reviewed
    network["owner_construction_decision"] = {
        "date": "2026-10-04",
        "reviewed_commit": REVIEWED_COMMIT,
        "reviewed_fingerprint": REVIEWED_FINGERPRINT,
        "reviewed_surface_count": len(network["full_preview"]["rejected_surfaces"]),
        "cut_above_reviewed_pavement": True,
        "material": "ASPHALT",
        "geometry_unchanged_except_connections": True,
        "connections": [
            {k: v for k, v in item.items() if k != "sections"} for item in connections
        ],
        "engineering_admitted": False,
        "collision_admitted": False,
        "construction_sha256": preview_fingerprint(reviewed),
    }
