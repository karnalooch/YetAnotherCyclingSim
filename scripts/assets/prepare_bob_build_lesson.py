"""Prepare one owner's authorized transient native builder lesson."""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.worldgen.bob_build_lesson import plan_lesson
from scripts.geometry.native_heightfield_pavement import build_surface, solidify


def prepare(profile_path, output):
    if output.exists():
        raise FileExistsError("Preserve existing lesson evidence")
    candidate = json.loads(profile_path.read_text())
    plan = plan_lesson(candidate)
    rows = plan["points"]
    outline = [r["xy_m"][0] for r in rows] + [r["xy_m"][-1] for r in reversed(rows)]
    vertices, faces, proof = build_surface(outline, lambda x, y: 0.0, diagonal="a_d")
    solid, triangles = solidify(vertices, faces, thickness=0.08, burial=0.04)
    plan.update(
        vertices_local_m=solid,
        triangles=triangles,
        top_vertex_count=len(vertices),
        top_triangle_count=len(faces),
        native_mesh=proof,
    )
    output.write_text(json.dumps(plan, separators=(",", ":"), allow_nan=False) + "\n")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(args.profile, args.output)
    print(
        json.dumps(
            {
                "recipe_id": plan["recipe_id"],
                "station_range_m": plan["station_range_m"],
                "top_vertex_count": plan["top_vertex_count"],
            }
        )
    )
