"""Inspect exactly two hash-pinned FBX sources with Blender's installed importer.

Request: {"schema_version":1,"assets":[{"id":"rock_07","path":"...fbx",
"sha256":"..."}, {"id":"rock_09","path":"...fbx","sha256":"..."}]}.
Optional derived FBX export isolates existing LOD0 without geometry editing.
No original source rewriting, rescaling, .blend save or placement admission.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bmesh
import bpy
from io_scene_fbx import parse_fbx


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def bounds(points):
    require(
        points and all(math.isfinite(v) for p in points for v in p),
        "Missing/nonfinite mesh vertices",
    )
    return {
        "min": [min(p[i] for p in points) for i in range(3)],
        "max": [max(p[i] for p in points) for i in range(3)],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lod0-output-directory", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender required",
    )
    request = json.loads(args.request.read_text(encoding="utf-8"))
    require(
        set(request) == {"schema_version", "assets"} and request["schema_version"] == 1,
        "Unexpected request schema",
    )
    require(
        len(request["assets"]) == 2
        and {a["id"] for a in request["assets"]} == {"rock_07", "rock_09"},
        "Exactly the two approved source IDs required",
    )
    output = args.output.resolve()
    require(
        not output.exists() and output.parent.is_dir(),
        "New output in existing directory required",
    )
    derived_directory = None
    export_settings = {
        "use_selection": True,
        "object_types": {"MESH"},
        "global_scale": 1.0,
        "apply_unit_scale": True,
        "apply_scale_options": "FBX_SCALE_NONE",
        "use_space_transform": True,
        "bake_space_transform": False,
        "use_mesh_modifiers": False,
        "bake_anim": False,
        "axis_forward": "-Y",
        "axis_up": "Z",
        "path_mode": "AUTO",
        "embed_textures": False,
    }
    if args.lod0_output_directory is not None:
        derived_directory = args.lod0_output_directory.resolve()
        require(
            derived_directory.is_relative_to(Path("D:/yacs/work/pcg365").resolve())
            and not derived_directory.exists()
            and derived_directory.parent.is_dir(),
            "Derived LOD0 directory must be fresh under existing pcg365 work parent",
        )
        derived_directory.mkdir()
    source_root = Path("D:/yacs/data/assets/pcg365-rock-qualification01").resolve(
        strict=True
    )
    settings = {
        "global_scale": 1.0,
        "use_manual_orientation": False,
        "bake_space_transform": False,
        "use_anim": False,
        "use_image_search": False,
        "use_custom_normals": True,
    }
    # Unit conversion is the stock importer path, not a corrective geometry scale.
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    records = []
    for asset in request["assets"]:
        require(set(asset) == {"id", "path", "sha256"}, "Unexpected asset fields")
        path = Path(asset["path"]).resolve(strict=True)
        require(
            path.is_relative_to(source_root) and path.suffix.lower() == ".fbx",
            "Source outside approved cache",
        )
        before = sha(path)
        require(before == asset["sha256"], "Source SHA256 mismatch")
        tree, version = parse_fbx.parse(str(path))
        globals_nodes = [e for e in tree.elems if e.id == b"GlobalSettings"]
        require(len(globals_nodes) == 1, "Missing/duplicate FBX GlobalSettings")
        props_nodes = [e for e in globals_nodes[0].elems if e.id == b"Properties70"]
        require(len(props_nodes) == 1, "Missing/duplicate FBX Properties70")
        wanted = {
            "UnitScaleFactor",
            "OriginalUnitScaleFactor",
            "UpAxis",
            "UpAxisSign",
            "FrontAxis",
            "FrontAxisSign",
            "CoordAxis",
            "CoordAxisSign",
        }
        declared = {}
        for element in props_nodes[0].elems:
            if element.id == b"P" and element.props:
                name = element.props[0].decode("utf-8")
                if name in wanted:
                    require(name not in declared, "Duplicate FBX global property")
                    declared[name] = list(element.props[4:])
        before_objects = set(bpy.data.objects)
        require(
            bpy.ops.import_scene.fbx(filepath=str(path), **settings) == {"FINISHED"},
            "FBX import failed",
        )
        imported = set(bpy.data.objects) - before_objects
        meshes = sorted((o for o in imported if o.type == "MESH"), key=lambda o: o.name)
        require(meshes, "No source meshes")
        mesh_records, all_points = [], []
        for obj in meshes:
            mesh = obj.data
            local = [list(v.co) for v in mesh.vertices]
            world = [list(obj.matrix_world @ v.co) for v in mesh.vertices]
            all_points.extend(world)
            mesh.calc_loop_triangles()
            bm = bmesh.new()
            try:
                bm.from_mesh(mesh)
                topology = {
                    "boundary_edges": sum(e.is_boundary for e in bm.edges),
                    "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
                    "wire_edges": sum(e.is_wire for e in bm.edges),
                }
            finally:
                bm.free()
            mesh_records.append(
                {
                    "object": obj.name,
                    "vertices": len(mesh.vertices),
                    "polygons": len(mesh.polygons),
                    "triangles": len(mesh.loop_triangles),
                    "local_bounds_m": bounds(local),
                    "world_bounds_m": bounds(world),
                    "object_matrix_world": [list(r) for r in obj.matrix_world],
                    "origin_world_m": list(obj.matrix_world.translation),
                    "uv_layers": [layer.name for layer in mesh.uv_layers],
                    "topology": topology,
                }
            )
        after = sha(path)
        require(before == after, "Source changed during inspection")
        derived = None
        if derived_directory is not None:
            selected = [o for o in meshes if o.name == asset["id"] + "_LOD0"]
            require(
                len(selected) == 1, "Expected exactly one explicitly named source LOD0"
            )
            lod0 = selected[0]
            for obj in bpy.context.view_layer.objects:
                obj.select_set(False)
            lod0.select_set(True)
            bpy.context.view_layer.objects.active = lod0
            derived_path = derived_directory / (asset["id"] + "_lod0.fbx")
            require(not derived_path.exists(), "Derived FBX overwrite forbidden")
            require(
                bpy.ops.export_scene.fbx(filepath=str(derived_path), **export_settings)
                == {"FINISHED"},
                "LOD0 FBX export failed",
            )
            require(sha(path) == before, "Original changed during derived export")
            derived = {
                "path": str(derived_path),
                "sha256": sha(derived_path),
                "bytes": derived_path.stat().st_size,
                "selected_object": lod0.name,
                "selection_policy": "exact asset ID + _LOD0; only selected MESH; original local geometry/object transform unchanged",
                "excluded_mesh_objects": sorted(o.name for o in meshes if o != lod0),
                "source_lod0_measurement": next(
                    r for r in mesh_records if r["object"] == lod0.name
                ),
                "export_options": {
                    k: sorted(v) if isinstance(v, set) else v
                    for k, v in export_settings.items()
                },
                "exporter_sha256": sha(
                    Path(parse_fbx.__file__).with_name("export_fbx_bin.py")
                ),
                "native_reimport_comparison": "NOT_RUN",
            }
        records.append(
            {
                "id": asset["id"],
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256_before": before,
                "sha256_after": after,
                "fbx_version": version,
                "declared_global_settings": declared,
                "missing_declared_settings": sorted(wanted - declared.keys()),
                "mesh_count": len(meshes),
                "meshes": mesh_records,
                "combined_world_bounds_m": bounds(all_points),
                "derived_lod0_fbx": derived,
            }
        )
        for obj in imported:
            bpy.data.objects.remove(obj, do_unlink=True)
    report = {
        "schema_version": 1,
        "issue": 365,
        "status": "SOURCE_DCC_INSPECTION_ONLY",
        "blender_version": bpy.app.version_string,
        "background": True,
        "request_sha256": sha(args.request),
        "import_settings": settings,
        "parser_sha256": sha(Path(parse_fbx.__file__)),
        "assets": records,
        "units": "Blender scene metres after standard FBX declared-unit/axis conversion",
        "comparison_policy": "Compare UE cm to Blender metres*100 only after documenting UE import axis mapping; world/local bounds and object origins are distinct",
        "limitations": "Topology edge counts are not continuous support, closed-solid or render proof; source origin is not a qualified support anchor; missing FBX settings remain missing",
        "source_modified": False,
        "assets_saved": False,
        "derived_source_files_exported": derived_directory is not None,
        "placement": False,
        "qualified_assets": [],
        "native_unreal_execution": "NOT_RUN",
    }
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
