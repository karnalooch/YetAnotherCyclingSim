"""Inventory hash-pinned rock LOD objects and actual connected face components.

Read-only DCC analysis. No selection inference, mesh export, source mutation,
terrain work or asset qualification. Invoke only under the owned Blender lease.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def face_components(faces):
    """Stable vertex-connected components; shared coordinates are not welded."""
    adjacent = {}
    for index, face in enumerate(faces):
        for vertex in face:
            adjacent.setdefault(vertex, []).append(index)
    remaining = set(range(len(faces)))
    result = []
    while remaining:
        first = min(remaining)
        pending, group = [first], []
        remaining.remove(first)
        while pending:
            current = pending.pop()
            group.append(current)
            for vertex in faces[current]:
                for neighbor in adjacent[vertex]:
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        pending.append(neighbor)
        result.append(sorted(group))
    return result


def component_report(mesh, matrix, indices):
    from collections import Counter
    from mathutils import Vector

    triangles = [mesh.loop_triangles[i] for i in indices]
    vertices = sorted({v for t in triangles for v in t.vertices})
    positions = {i: matrix @ mesh.vertices[i].co for i in vertices}
    directed, edges = Counter(), Counter()
    area, volume = 0.0, 0.0
    for triangle in triangles:
        ids = list(triangle.vertices)
        a, b, c = (positions[i] for i in ids)
        area += (b - a).cross(c - a).length / 2
        volume += a.dot(b.cross(c)) / 6
        for i in range(3):
            edge = (ids[i], ids[(i + 1) % 3])
            directed[edge] += 1
            edges[tuple(sorted(edge))] += 1
    boundary = [edge for edge, count in edges.items() if count == 1]
    boundary_vertices = sorted({v for e in boundary for v in e})

    def bounds(ids):
        return (
            {
                key: [op(positions[v][axis] for v in ids) for axis in range(3)]
                for key, op in [("min", min), ("max", max)]
            }
            if ids
            else None
        )

    closed = all(count == 2 for count in edges.values())
    winding = (
        all(count == 1 and directed[(b, a)] == 1 for (a, b), count in directed.items())
        if closed
        else None
    )
    require(
        all(math.isfinite(x) for p in positions.values() for x in p),
        "Nonfinite source geometry",
    )
    centroid = sum(positions.values(), Vector()) / len(vertices)
    return {
        "triangle_count": len(indices),
        "vertex_count": len(vertices),
        "triangle_indices_sha256": hashlib.sha256(
            json.dumps(indices, separators=(",", ":")).encode()
        ).hexdigest(),
        "triangle_index_min": min(indices),
        "triangle_index_max": max(indices),
        "world_bounds_m": bounds(vertices),
        "vertex_mean_world_m": list(centroid),
        "surface_area_m2": area,
        "boundary_edges": len(boundary),
        "boundary_world_bounds_m": bounds(boundary_vertices),
        "nonmanifold_edge_count": sum(count != 2 for count in edges.values()),
        "closed": closed,
        "consistent_winding": winding,
        "signed_volume_m3": volume if closed and winding else None,
        "source_self_intersection": "UNKNOWN_NOT_TESTED",
    }


def main():
    import bpy

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--expected-request-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender4.5.9 required",
    )
    raw = args.request.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == args.expected_request_sha256,
        "Request identity differs",
    )
    request = json.loads(raw)
    require(
        request["schema_version"] == 1 and 1 <= len(request["assets"]) <= 8,
        "Bounded schema1 source list required",
    )
    require(
        len({a["id"] for a in request["assets"]}) == len(request["assets"]),
        "Duplicate source IDs",
    )
    output = args.output.resolve()
    root = Path("D:/yacs/work/pcg365").resolve(strict=True)
    require(
        output.is_relative_to(root) and not output.exists() and output.parent.is_dir(),
        "Fresh output file below existing owned stage required",
    )
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    records = []
    for asset in request["assets"]:
        source = Path(asset["path"]).resolve(strict=True)
        allowed = [Path("D:/yacs/data/assets").resolve(strict=True), root]
        require(
            any(source.is_relative_to(p) for p in allowed)
            and source.suffix.lower() == ".fbx",
            "Source outside bounded roots",
        )
        before = sha(source)
        require(
            before == asset["sha256"] and source.stat().st_size == asset["bytes"],
            "Source identity differs",
        )
        existing = set(bpy.data.objects)
        require(
            bpy.ops.import_scene.fbx(
                filepath=str(source),
                global_scale=1,
                use_manual_orientation=False,
                bake_space_transform=False,
                use_anim=False,
                use_image_search=False,
                use_custom_normals=True,
            )
            == {"FINISHED"},
            "FBX import failed",
        )
        imported = set(bpy.data.objects) - existing
        objects = []
        try:
            for obj in sorted(imported, key=lambda o: o.name):
                if obj.type != "MESH":
                    objects.append({"name": obj.name, "type": obj.type})
                    continue
                require(
                    not obj.modifiers
                    and obj.animation_data is None
                    and obj.data.shape_keys is None,
                    "Deformed source unsupported",
                )
                mesh = obj.data
                mesh.calc_loop_triangles()
                faces = [list(t.vertices) for t in mesh.loop_triangles]
                groups = face_components(faces)
                objects.append(
                    {
                        "name": obj.name,
                        "type": "MESH",
                        "mesh": mesh.name,
                        "matrix_world": [list(r) for r in obj.matrix_world],
                        "triangles": len(faces),
                        "vertices": len(mesh.vertices),
                        "uv_layers": [layer.name for layer in mesh.uv_layers],
                        "material_slots": [
                            mat.name if mat else None for mat in mesh.materials
                        ],
                        "components": [
                            {
                                "component_index": i,
                                **component_report(mesh, obj.matrix_world, g),
                            }
                            for i, g in enumerate(groups)
                        ],
                        "component_count": len(groups),
                        "selection": "NOT_SELECTED_NO_INFERRED_LOD",
                    }
                )
            require(
                sha(source) == before and source.stat().st_size == asset["bytes"],
                "Source changed during inspection",
            )
            records.append(
                {
                    "id": asset["id"],
                    "source": str(source),
                    "source_sha256_before": before,
                    "source_sha256_after": sha(source),
                    "source_bytes": asset["bytes"],
                    "license": asset.get("license", "UNKNOWN_NOT_ADMITTED"),
                    "objects": objects,
                }
            )
        finally:
            for obj in imported:
                bpy.data.objects.remove(obj, do_unlink=True)
    require(args.request.read_bytes() == raw, "Request changed")
    report = {
        "schema_version": 1,
        "issue": 365,
        "status": "ROCK_COMPONENT_SOURCE_INSPECTION_ONLY",
        "request_sha256": args.expected_request_sha256,
        "script_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "blender_version": bpy.app.version_string,
        "assets": records,
        "source_modified": False,
        "terrain_modified": False,
        "placement": False,
        "qualified_assets": [],
        "native_unreal_execution": "NOT_RUN",
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
