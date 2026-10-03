"""Spawn the owner's simple retaining support after native CUT has settled."""

import hashlib
import json

import unreal

from scripts.geometry.bob_vertical_support import (
    SHOULDER_M,
    build_vertical_support,
    support_sections,
)
from scripts.ue.ma2141_road_preview import spawn_pavement_mesh


def spawn_support(world, root, exact_sha, context):
    sections = support_sections(context["profile"])
    ground = []
    for section in sections:
        heights = []
        for x, y, z in (section[0], section[-1]):
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
            values = () if hit is None else hit.to_tuple()
            candidates = [
                float(p.z) / 100
                for p in values
                if all(hasattr(p, k) for k in ("x", "y", "z"))
                and abs(p.x - x * 100) < 0.1
                and abs(p.y - y * 100) < 0.1
                and abs(p.z - z * 100) < 9999
            ]
            if not candidates:
                raise RuntimeError("Vertical support Landscape trace missed")
            heights.append(candidates[0])
        ground.append(heights)
    vertices, triangles, report = build_vertical_support(sections, ground)
    actor, material = spawn_pavement_mesh(
        world,
        vertices,
        triangles,
        "BOB vertical support and 0.5 m shoulders - transient",
    )
    material.set_vector_parameter_value(
        "Color", unreal.LinearColor(0.34, 0.31, 0.25, 1)
    )
    report.update(
        {
            "exact_sha": exact_sha,
            "shoulder_m": SHOULDER_M,
            "shoulder_height": "slab underside; 0.08 m below asphalt",
            "base_dtm_modified": False,
            "map_saved": False,
            "material": "neutral geometry review; stone dressing pending",
            "mesh_sha256": hashlib.sha256(
                json.dumps([vertices, triangles], separators=(",", ":")).encode()
            ).hexdigest(),
        }
    )
    (root / "bob-vertical-support-proof.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return actor, material, report
