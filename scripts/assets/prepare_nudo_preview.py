"""Bounded owner-requested Nus de sa Corbata presentation reconstruction."""

import math

import numpy as np
from shapely.geometry import LineString

from scripts.geometry.network_pavement import shoulder_sections
from scripts.geometry.network_visual_preview import preview_fingerprint
from scripts.geometry.reviewed_network import validate_slab
from scripts.geometry.road_review_policy import review_surface, width_review


def design(network):
    """Connect the unchanged approach sections through the official source loop.

    Heights are a provisional continuous design between existing endpoints,
    never IGN source Z or a claim of surveyed bridge dimensions.
    """
    from scripts.assets.prepare_current_landscape_roads import smooth_axis, turns

    windows = network["approved"] + network["owner_reviewed"]
    markers = network["full_preview"]["source_markers"]
    paths = [
        next(m["xy_local_m"] for m in markers if ident in m["id"])
        for ident in ("01178", "01289", "01288")
    ]
    upper = min(
        (w for w in windows if "01287" in w["id"]),
        key=lambda w: math.dist(w["sections"][-1][12][:2], paths[0][0]),
    )["sections"]
    lower = min(
        (w for w in windows if "01272" in w["id"]),
        key=lambda w: math.dist(w["sections"][0][12][:2], paths[-1][-1]),
    )["sections"]
    points = [upper[-1][12][:2]]
    for path in paths:
        for p in path:
            if math.dist(points[-1], p) > 1e-5:
                points.append(p)
    points.append(lower[0][12][:2])
    _, xy = smooth_axis(LineString(points), spacing=3.0)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    # Match endpoint direction over bounded 8 m approach domains.
    for reverse, anchor in ((False, upper), (True, lower)):
        view = xy[::-1] if reverse else xy
        distance = s[-1] - s[::-1] if reverse else s
        base = np.asarray(anchor[0 if reverse else -1][12][:2])
        neighbor = np.asarray(anchor[1 if reverse else -2][12][:2])
        direction = base - neighbor
        direction /= np.linalg.norm(direction)
        index = int(np.searchsorted(distance, 8.0))
        length = distance[index]
        end = view[index].copy()
        tangent = view[index + 1] - view[index - 1]
        tangent /= np.linalg.norm(tangent)
        for i in range(index):
            t = distance[i] / length
            view[i] = (
                (2 * t**3 - 3 * t * t + 1) * base
                + (t**3 - 2 * t * t + t) * length * direction
                + (-2 * t**3 + 3 * t * t) * end
                + (t**3 - t * t) * length * tangent
            )
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))]
    z0, z1 = upper[-1][12][2], lower[0][12][2]
    z = z0 + (z1 - z0) * s / s[-1]
    tangent = np.gradient(xy, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    normal = np.c_[-tangent[:, 1], tangent[:, 0]]
    rows = np.empty((len(xy), 25, 3))
    rows[:, :, :2] = (
        xy[:, None, :] + normal[:, None, :] * np.linspace(-2.5, 2.5, 25)[None, :, None]
    )
    rows[:, :, 2] = z[:, None]
    # Exact endpoint crossfall blends to the level provisional bridge profile.
    for reverse, anchor in ((False, upper[-1]), (True, lower[0])):
        view = rows[::-1] if reverse else rows
        distance = s[-1] - s[::-1] if reverse else s
        delta = np.asarray(anchor) - view[0]
        for i in range(int(np.searchsorted(distance, 8.0))):
            t = distance[i] / 8.0
            view[i] += delta * (1 - 3 * t * t + 2 * t**3)
        view[0] = anchor
    # Endpoint-normal blending must not interpolate a shorter chord width.
    # Solve width together with alignment, as on the accepted hairpin joins.
    widths = np.linalg.norm(rows[:, -1, :2] - rows[:, 0, :2], axis=1)
    rows[:, :, :2] = (
        rows[:, 12:13, :2]
        + (rows[:, :, :2] - rows[:, 12:13, :2]) * (5.0 / widths)[:, None, None]
    )
    rows[0], rows[-1] = upper[-1], lower[0]
    widths = np.linalg.norm(rows[:, -1, :2] - rows[:, 0, :2], axis=1)
    rows = rows.tolist()
    review_reasons = []
    if width_review(rows)["status"] != "PASS":
        review_reasons.append("Nudo width exceeds the owner 5% envelope")
    try:
        validate_slab(rows)
    except ValueError as exc:
        review_reasons.append(str(exc))
    loop_start = int(np.argmin(np.linalg.norm(xy - paths[1][0], axis=1)))
    loop_end = int(np.argmin(np.linalg.norm(xy - paths[1][-1], axis=1)))
    bend_turns = [
        turns(np.asarray(rows)[loop_start : loop_end + 1, k, :2]) for k in (0, 12, 24)
    ]
    if any(t.min() < -1e-6 or not math.pi < t.sum() < 2 * math.pi for t in bend_turns):
        review_reasons.append("Nudo main bend reverses on an edge or axis")
    inspection = review_surface(rows)
    if inspection["status"] != "PASS":
        review_reasons.append(
            "Nudo surface design needs visual review: " + str(inspection)
        )
    upper_line = LineString([r[12][:2] for r in rows[: len(rows) // 2]])
    lower_line = LineString(paths[-1])
    crossing = upper_line.intersection(lower_line)
    if crossing.geom_type != "Point":
        raise ValueError("Nudo must have exactly one grade-separated crossing")
    center = [crossing.x, crossing.y]
    lower_direction = np.asarray(paths[-1][-1]) - np.asarray(paths[-1][0])
    lower_direction /= np.linalg.norm(lower_direction)
    lower_s = LineString([r[12][:2] for r in rows]).length - math.dist(
        center, rows[-1][12][:2]
    )
    lower_z = float(np.interp(lower_s, s, np.asarray(rows)[:, 12, 2]))
    near_lower = [
        r[12][2]
        for i, r in enumerate(rows)
        if s[i] > s[-1] - 35 and math.dist(r[12][:2], center) < 8
    ]
    return rows, {
        "center_xy_m": center,
        "lower_direction_xy": lower_direction.tolist(),
        "lower_height_m": lower_z,
        "opening_half_width_m": 3.5,
        "lower_profile_variation_m": max(abs(z - lower_z) for z in near_lower),
        "spring_height_m": 2.7,
        "arch_rise_m": 3.5,
        "upper_domain_station_m": 80.0,
        "dimension_evidence": "INFERRED_VISUAL_DESIGN_NOT_SURVEYED",
        "width_m": 5.0,
        "shoulder_m": 0.5,
        "support_cap_m": 9.0,
        "source_ids": [
            "VIAL_TR70190001178",
            "VIAL_TR70190001289",
            "VIAL_TR70190001288",
        ],
        "street_view_url": "https://www.google.com/maps/@39.8324306,2.8161705,3a,60y,196.97h,91.84t/",
        "imagery_date": "2026-07",
        "owner_request_date": "2026-10-04",
        "source_z_used": False,
        "main_bend_heading_deg": [float(np.degrees(t.sum())) for t in bend_turns],
        "collision_admitted": False,
        "human_visual_status": "PENDING",
        "visual_review_reasons": review_reasons,
    }


def prepare_nudo(network, terrain, manifest, output):
    from scripts.assets.prepare_current_landscape_roads import (
        digest,
        prepare_patch,
        technical_patch_tiles,
    )

    rows, structure = design(network)
    s = np.r_[
        0, np.cumsum([math.dist(a[12][:2], b[12][:2]) for a, b in zip(rows, rows[1:])])
    ]
    windows = []
    for i, (start, end) in enumerate(technical_patch_tiles(0, len(rows) - 1, s)):
        part = rows[start : end + 1]
        path = output / f"nudo-{i}.json"
        patch = prepare_patch(
            np.asarray(shoulder_sections(part)),
            terrain,
            manifest,
            path,
            reviewed_geometry=True,
        )
        windows.append(
            {
                "id": f"nudo-{i}",
                "sections": part,
                "length_m": float(s[end] - s[start]),
                "station_start_m": float(s[start]),
                "technical_patch_tile": True,
                "decision_interval_id": "owner-nudo-2026-10-04",
                "cut_manifest": path.name,
                "cut_sha256": digest(path),
                "max_cut_m": patch["max_cut_m"],
                "owner_reviewed_geometry": True,
                "surface_inspection": review_surface(part),
                "visual_review_reasons": structure["visual_review_reasons"],
                "nudo_structure": True,
            }
        )
    network["nudo"] = {
        "structure": structure,
        "windows": windows,
        "replaced_window_ids": [
            w["id"]
            for w in network["approved"] + network["owner_reviewed"]
            if "01178" in w["id"]
        ],
        "construction_sha256": preview_fingerprint(windows),
        "structure_sha256": preview_fingerprint([structure]),
        "endpoint_residual_m": 0.0,
    }
