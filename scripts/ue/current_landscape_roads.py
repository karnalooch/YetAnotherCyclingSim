"""Import checked network candidates with the established transient UE paths."""

import hashlib
import json
import math
from pathlib import Path

import unreal

from scripts.geometry.bob_vertical_support import build_vertical_support
from scripts.geometry.network_pavement import pavement_slab, shoulder_sections
from scripts.ue.ma2141_road_preview import spawn_pavement_mesh


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trace(world, point):
    x, y, z = point
    hit = unreal.SystemLibrary.line_trace_single(
        world,
        unreal.Vector(x * 100, y * 100, (z + 100) * 100),
        unreal.Vector(x * 100, y * 100, (z - 100) * 100),
        unreal.TraceTypeQuery.ECC_VISIBILITY,
        True,
        [],
        unreal.DrawDebugTrace.NONE,
        True,
    )
    candidates = [
        p.z / 100
        for p in (() if hit is None else hit.to_tuple())
        if all(hasattr(p, k) for k in ("x", "y", "z"))
        and abs(p.x - x * 100) < 0.1
        and abs(p.y - y * 100) < 0.1
        and abs(p.z - z * 100) < 9999
    ]
    if not candidates:
        raise RuntimeError("Network Landscape trace missed")
    return candidates[0]


def start(world, root, exact_sha):
    directory = root / "Network"
    network = json.loads((directory / "network.json").read_text())
    if (
        network["exact_sha"] != exact_sha
        or network["width_m"] != 5.0
        or network["shoulder_m"] != 0.5
        or network["map_saved"]
        or network["base_dtm_modified"]
    ):
        raise RuntimeError("Network preview provenance mismatch")
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("Network needs the existing single Landscape")
    labels = [str(layer.get_name_bp()) for layer in landscapes[0].get_edit_layers_bp()]
    if labels.count("Base_DTM") != 1 or labels.count("Road_Earthworks") != 1:
        raise RuntimeError("Network Landscape layer ownership is ambiguous")
    for window in network["approved"]:
        path = directory / window["cut_manifest"]
        if path.name != window["cut_manifest"] or digest(path) != window["cut_sha256"]:
            raise RuntimeError("Network CUT manifest changed")
        patch = json.loads(path.read_text())
        if (
            patch["max_cut_m"] > 1.0
            or digest(directory / patch["patch_file"]) != patch["patch_sha256"]
        ):
            raise RuntimeError("Network CUT cap/hash mismatch")
        if not unreal.CyclingLandscapeEarthworksLibrary.apply_road_earthworks_patch(
            landscapes[0], str(path)
        ):
            raise RuntimeError("Network native CUT patch application failed")
    return network


def finish(world, root, exact_sha, network):
    kept = []
    reports = []
    for window in network["approved"]:
        sections = window["sections"]
        if len(sections) < 3 or any(len(row) != 25 for row in sections):
            raise RuntimeError("Network sections are incomplete")
        ground = []
        support = shoulder_sections(sections)
        missed_clearance = 0
        maximum_penetration = 0.0
        for row, extended in zip(sections, support, strict=True):
            if any(not math.isfinite(v) for p in row for v in p):
                raise RuntimeError("Network nonfinite vertex")
            width = math.dist(row[0][:2], row[-1][:2])
            if abs(width - 5.0) > 0.0001:
                raise RuntimeError("Native network width drift")
            for point in row:
                penetration = trace(world, point) - point[2]
                maximum_penetration = max(maximum_penetration, penetration)
                missed_clearance += penetration > 0.005
            endpoints = [trace(world, extended[0]), trace(world, extended[-1])]
            if any(
                g - p[2] > 0.005 for g, p in zip(endpoints, (extended[0], extended[-1]))
            ):
                raise RuntimeError("Native network shoulder buried")
            ground.append(endpoints)
        if missed_clearance:
            raise RuntimeError(
                f"Network asphalt penetration: {window['id']}: {missed_clearance} samples, {maximum_penetration:.4f} m"
            )
        vertices, triangles = pavement_slab(sections)
        sv, st, proof = build_vertical_support(support, ground)
        if (
            proof["min_shoulder_extent_m"] < 0.4999
            or proof["max_shoulder_extent_m"] > 0.51
            or proof["max_wall_height_m"] > 4.0
        ):
            raise RuntimeError("Network support/shoulder admission failed")
        kept.append(
            spawn_pavement_mesh(
                world, vertices, triangles, "BOB network asphalt " + window["id"]
            )
        )
        actor, material = spawn_pavement_mesh(
            world, sv, st, "BOB network support " + window["id"]
        )
        material.set_vector_parameter_value(
            "Color", unreal.LinearColor(0.34, 0.31, 0.25, 1)
        )
        kept.append((actor, material))
        reports.append(
            {
                "id": window["id"],
                "length_m": window["length_m"],
                "trace_count": len(sections) * 27,
                "asphalt_penetration_count": missed_clearance,
                "maximum_penetration_m": maximum_penetration,
                "support": proof,
            }
        )
    report = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "status": "PARTIAL_IMPORTED"
        if network["blocked"]
        else "IMPORTED_REVIEW_REQUIRED",
        "approved_length_m": network["approved_length_m"],
        "blocked_length_m": network["blocked_length_m"],
        "windows": reports,
        "blocked": network["blocked"],
        "map_saved": False,
        "base_dtm_modified": False,
        "collision_admitted": False,
        "human_visual_status": "PENDING",
        "performance_status": "PENDING",
    }
    (root / "network-native-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    return kept, report
