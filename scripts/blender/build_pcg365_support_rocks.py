"""Author two original flat-support decorative rock forms, without admission."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from io_scene_fbx import export_fbx_bin, parse_fbx
from mathutils import Matrix


RECIPES = (
    {
        "id": "support_rock_a",
        "sides": 8,
        "width_m": 0.50,
        "depth_m": 0.46,
        "height_m": 0.42,
        "radii": [1.0, 0.96, 1.02, 0.98, 1.0, 1.03, 0.97, 1.01],
        "middle_scale": 0.77,
        "upper_scale": 0.31,
        "upper_height_fraction": [0.89, 0.92, 0.87, 0.91, 0.90, 0.88, 0.93, 0.89],
        "apex_xy_fraction": [0.018, -0.013],
    },
    {
        "id": "support_rock_b",
        "sides": 6,
        "width_m": 0.54,
        "depth_m": 0.49,
        "height_m": 0.445,
        "radii": [0.98, 1.02, 0.97, 1.01, 0.99, 1.03],
        "middle_scale": 0.71,
        "upper_scale": 0.27,
        "upper_height_fraction": [0.92, 0.86, 0.90, 0.94, 0.88, 0.91],
        "apex_xy_fraction": [-0.014, 0.021],
    },
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cross2(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def inside(poly, point):
    return all(
        cross2(poly[i], poly[(i + 1) % len(poly)], point) > 0 for i in range(len(poly))
    )


def geometry(recipe):
    """Nested convex XY rings ensure every vertical footprint has a flat base."""
    n = recipe["sides"]
    raw = [
        (r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
        for i, r in enumerate(recipe["radii"])
    ]
    sx = recipe["width_m"] / (max(p[0] for p in raw) - min(p[0] for p in raw))
    sy = recipe["depth_m"] / (max(p[1] for p in raw) - min(p[1] for p in raw))
    base = [(p[0] * sx, p[1] * sy) for p in raw]
    require(
        all(cross2(base[i], base[(i + 1) % n], base[(i + 2) % n]) > 0 for i in range(n))
        and inside(base, (0, 0)),
        "Base must be strictly convex around origin",
    )
    h = recipe["height_m"]
    middle = [(x * recipe["middle_scale"], y * recipe["middle_scale"]) for x, y in base]
    upper = [(x * recipe["upper_scale"], y * recipe["upper_scale"]) for x, y in base]
    apex_xy = (
        recipe["apex_xy_fraction"][0] * recipe["width_m"],
        recipe["apex_xy_fraction"][1] * recipe["depth_m"],
    )
    require(
        all(inside(base, p) for p in middle)
        and all(inside(middle, p) for p in upper)
        and inside(upper, apex_xy),
        "XY ring nesting failed",
    )
    vertices = [(x, y, 0.0) for x, y in base]
    vertices += [(x, y, h * 0.58) for x, y in middle]
    vertices += [
        (x, y, h * recipe["upper_height_fraction"][i]) for i, (x, y) in enumerate(upper)
    ]
    apex = len(vertices)
    vertices.append((*apex_xy, h))
    cap = len(vertices)
    vertices.append((0.0, 0.0, 0.0))
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((cap, j, i))
        for tier in range(2):
            a, b, c, d = (
                tier * n + i,
                tier * n + j,
                (tier + 1) * n + j,
                (tier + 1) * n + i,
            )
            faces += [(a, b, c), (a, c, d)]
        faces.append((2 * n + i, 2 * n + j, apex))
    return vertices, faces


def declared_units(path):
    tree, version = parse_fbx.parse(str(path))
    values = {}
    for node in tree.elems:
        if node.id != b"GlobalSettings":
            continue
        for props in node.elems:
            if props.id != b"Properties70":
                continue
            for entry in props.elems:
                if entry.id == b"P" and entry.props:
                    name = entry.props[0].decode("utf-8")
                    if name in {
                        "UnitScaleFactor",
                        "OriginalUnitScaleFactor",
                        "UpAxis",
                        "UpAxisSign",
                        "FrontAxis",
                        "FrontAxisSign",
                        "CoordAxis",
                        "CoordAxisSign",
                    }:
                        require(name not in values, "Duplicate FBX global setting")
                        values[name] = list(entry.props[4:])
    require("UnitScaleFactor" in values, "Exported FBX lacks unit declaration")
    return {"fbx_version": version, "global_settings": values}


def build(recipe, output, export_options):
    vertices, faces = geometry(recipe)
    mesh = bpy.data.meshes.new(recipe["id"] + "_Geometry")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    require(
        not mesh.validate(verbose=False), "Authored mesh required corrective validation"
    )
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.normal_update()
        topology = {
            "boundary_edges": sum(e.is_boundary for e in bm.edges),
            "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
            "wire_edges": sum(e.is_wire for e in bm.edges),
            "vertices": len(bm.verts),
            "edges": len(bm.edges),
            "faces": len(bm.faces),
            "signed_volume_m3": bm.calc_volume(signed=True),
        }
        require(
            topology["boundary_edges"]
            == topology["nonmanifold_edges"]
            == topology["wire_edges"]
            == 0
            and topology["signed_volume_m3"] > 0,
            "Authored mesh is not outward closed manifold",
        )
        require(
            all(len(f.verts) == 3 and f.calc_area() > 0 for f in bm.faces),
            "Degenerate/nontriangular authored face",
        )
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()
    mesh.calc_loop_triangles()
    obj = bpy.data.objects.new(recipe["id"], mesh)
    bpy.context.collection.objects.link(obj)
    require(
        obj.matrix_world == Matrix.Identity(4)
        and not obj.modifiers
        and obj.animation_data is None
        and mesh.shape_keys is None,
        "Authored mesh has unexpected transform/deformation",
    )
    for polygon in mesh.polygons:
        polygon.use_smooth = False
    # A material slot is required for the later single shared Forge MI binding.
    placeholder = bpy.data.materials.new(recipe["id"] + "_SlotOnly")
    mesh.materials.append(placeholder)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = output / (recipe["id"] + ".fbx")
    require(
        bpy.ops.export_scene.fbx(filepath=str(path), **export_options) == {"FINISHED"},
        "Official FBX export failed",
    )
    actual_vertices = [list(v.co) for v in mesh.vertices]
    actual_faces = [list(p.vertices) for p in mesh.polygons]
    minimum = [min(v[i] for v in actual_vertices) for i in range(3)]
    maximum = [max(v[i] for v in actual_vertices) for i in range(3)]
    require(
        minimum[2] == 0.0 and all(v[2] >= 0 for v in actual_vertices),
        "Flat support base is not Z0",
    )
    base_polygons = [
        p for p in mesh.polygons if all(mesh.vertices[i].co.z == 0 for i in p.vertices)
    ]
    require(
        len(base_polygons) == recipe["sides"]
        and all(p.normal.z < 0 for p in base_polygons),
        "Flat base cap inventory/winding differs",
    )
    geometry_hash = hashlib.sha256(
        json.dumps(
            {"vertices_m": actual_vertices, "faces": actual_faces},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    record = {
        "id": recipe["id"],
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "recipe": recipe,
        "vertices_m": actual_vertices,
        "triangle_faces": actual_faces,
        "geometry_sha256": geometry_hash,
        "bounds_m": {"min": minimum, "max": maximum},
        "triangles": len(mesh.loop_triangles),
        "topology": topology,
        "object_matrix_world": [list(row) for row in obj.matrix_world],
        "support_anchor_local_m": [0.0, 0.0, 0.0],
        "flat_base": True,
        "horizontal_overhang": False,
        "nested_convex_xy_rings_verified": True,
        "uv_layers": [],
        "materials": "one placeholder slot; Forge MI applied only in isolated UE consumer",
        "exported_fbx_declarations": declared_units(path),
    }
    bpy.data.objects.remove(obj, do_unlink=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender4.5.9 required",
    )
    output = args.output_directory.resolve()
    allowed = Path("D:/yacs/work/pcg365").resolve(strict=True)
    require(
        output.is_relative_to(allowed) and output != allowed and not output.exists(),
        "New owned PCG365 output directory required",
    )
    output.mkdir(parents=True, exist_ok=False)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    export_options = {
        "use_selection": True,
        "object_types": {"MESH"},
        "global_scale": 1.0,
        "apply_unit_scale": True,
        "axis_forward": "-Y",
        "axis_up": "Z",
        "add_leaf_bones": False,
        "bake_anim": False,
        "mesh_smooth_type": "FACE",
        "use_mesh_modifiers": False,
        "use_custom_props": False,
    }
    records = [build(recipe, output, export_options) for recipe in RECIPES]
    report = {
        "schema_version": 1,
        "issue": 365,
        "status": "AUTHORED_SUPPORT_ROCK_SOURCES_ONLY",
        "source_provenance": "YACS_AUTHORED_PROCEDURAL_NOT_SCAN",
        "third_party_geometry": False,
        "blender_version": bpy.app.version_string,
        "background": True,
        "units": "metres",
        "script_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "exporter_sha256": sha(Path(export_fbx_bin.__file__)),
        "export_options": {
            **export_options,
            "object_types": sorted(export_options["object_types"]),
        },
        "assets": records,
        "placement": False,
        "qualified_assets": [],
        "native_unreal_execution": "NOT_RUN",
        "continuous_terrain_support": "UNVERIFIED",
        "limitations": "Original decorative support geometry, not regional geology, scanned stone or accepted placement; native unit/axis import, support policy and GPU review remain required. FBX file metadata may vary between exports; geometry recipes and hashes are recorded separately.",
    }
    with (output / "authored-support-rocks.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
