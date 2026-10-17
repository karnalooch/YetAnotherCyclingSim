"""Inspect two hash-pinned larger scans; optionally export one reviewed mesh each.

Request schema1: assets [{id,path,sha256,bytes}], exactly Namaqualand02/06.
First pass inventories every object. Second pass requires an inspection-hash-bound
selection JSON; no inferred LOD, combined meshes, geometry edits or admission.
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


def boundary_diagnostics(bm, matrix):
    edges = [e for e in bm.edges if e.is_boundary]
    neighbors = {}
    for edge in edges:
        a, b = edge.verts
        neighbors.setdefault(a, set()).add(b)
        neighbors.setdefault(b, set()).add(a)
    degree_two = all(len(adjacent) == 2 for adjacent in neighbors.values())
    remaining = set(neighbors)
    components = 0
    while remaining:
        components += 1
        pending = [remaining.pop()]
        while pending:
            for neighbor in neighbors[pending.pop()]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
    return {
        "boundary_world_bounds_m": bounds([list(matrix @ v.co) for v in neighbors])
        if neighbors
        else None,
        "boundary_loopcount": components if degree_two else None,
        "boundary_degree2_cycles": degree_two,
        "boundary_connected_components": components,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-directory", dest="lod0_output_directory", type=Path)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--expected-request-sha256", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    require(
        bpy.app.background and bpy.app.version == (4, 5, 9),
        "Pinned background Blender required",
    )
    request_hash = sha(args.request)
    require(request_hash == args.expected_request_sha256, "Request SHA256 mismatch")
    request = json.loads(args.request.read_text(encoding="utf-8-sig"))
    require(
        set(request) == {"schema_version", "assets"} and request["schema_version"] == 1,
        "Unexpected request schema",
    )
    require(
        len(request["assets"]) == 2
        and {a["id"] for a in request["assets"]}
        == {"namaqualand_boulder_02", "namaqualand_boulder_06"},
        "Exactly the two approved source IDs required",
    )
    output = args.output.resolve()
    require(
        not output.exists()
        and output.parent.is_dir()
        and output.is_relative_to(Path("D:/yacs/work/pcg365").resolve()),
        "New output in existing directory required",
    )
    selection = None
    prior = None
    require(
        bool(args.selection) == bool(args.lod0_output_directory),
        "Selection and export directory must be paired",
    )
    if args.selection:
        selection = json.loads(args.selection.read_text(encoding="utf-8-sig"))
        require(
            set(selection)
            == {"schema_version", "inspection_path", "inspection_sha256", "selections"}
            and selection["schema_version"] == 1,
            "Unexpected selection schema",
        )
        inspection_path = Path(selection["inspection_path"]).resolve(strict=True)
        require(
            sha(inspection_path) == selection["inspection_sha256"],
            "Inspection SHA mismatch",
        )
        prior = json.loads(inspection_path.read_text(encoding="utf-8"))
        require(
            prior["request_sha256"] == request_hash
            and prior["script_sha256"] == sha(Path(__file__)),
            "Inspection request/code mismatch",
        )
        require(
            len(selection["selections"]) == 2
            and {r["id"] for r in selection["selections"]}
            == {"namaqualand_boulder_02", "namaqualand_boulder_06"},
            "Exactly two explicit selections required",
        )
        require(
            all(set(r) == {"id", "object_name"} for r in selection["selections"]),
            "Unexpected selection fields",
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
    source_root = Path("D:/yacs/data/assets/pcg365-large-rocks01").resolve(strict=True)
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
        require(
            set(asset) == {"id", "path", "sha256", "bytes"}, "Unexpected asset fields"
        )
        path = Path(asset["path"]).resolve(strict=True)
        require(
            path.is_relative_to(source_root) and path.suffix.lower() == ".fbx",
            "Source outside approved cache",
        )
        before = sha(path)
        require(
            before == asset["sha256"] and path.stat().st_size == asset["bytes"],
            "Source SHA256/size mismatch",
        )
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
                bm.verts.index_update()
                remaining = set(bm.verts)
                components = 0
                while remaining:
                    components += 1
                    pending = [remaining.pop()]
                    while pending:
                        vertex = pending.pop()
                        for edge in vertex.link_edges:
                            other = edge.other_vert(vertex)
                            if other in remaining:
                                remaining.remove(other)
                                pending.append(other)
                topology = {
                    **boundary_diagnostics(bm, obj.matrix_world),
                    "connected_components": components,
                    "inconsistent_winding_edges": sum(
                        e.is_manifold and not e.is_contiguous for e in bm.edges
                    ),
                    "signed_volume_local_m3": bm.calc_volume(signed=True),
                    "degenerate_faces": sum(f.calc_area() <= 0 for f in bm.faces),
                    "boundary_edges": sum(e.is_boundary for e in bm.edges),
                    "nonmanifold_edges": sum(not e.is_manifold for e in bm.edges),
                    "wire_edges": sum(e.is_wire for e in bm.edges),
                }
            finally:
                bm.free()
            mesh_records.append(
                {
                    "object": obj.name,
                    "geometry_sha256": hashlib.sha256(
                        json.dumps(
                            {
                                "world_vertices": world,
                                "triangles": [
                                    list(t.vertices) for t in mesh.loop_triangles
                                ],
                            },
                            separators=(",", ":"),
                            allow_nan=False,
                        ).encode()
                    ).hexdigest(),
                    "modifiers": [m.type for m in obj.modifiers],
                    "has_animation": obj.animation_data is not None,
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
            selected_name = next(
                r["object_name"]
                for r in selection["selections"]
                if r["id"] == asset["id"]
            )
            selected = [o for o in meshes if o.name == selected_name]
            require(
                len(selected) == 1, "Expected exactly one explicitly named source LOD0"
            )
            lod0 = selected[0]
            measured = next(r for r in mesh_records if r["object"] == lod0.name)
            previous = next(a for a in prior["assets"] if a["id"] == asset["id"])
            prior_mesh = next(m for m in previous["meshes"] if m["object"] == lod0.name)
            require(
                measured == prior_mesh,
                "Selected geometry/transform/topology drift since inspection",
            )
            require(
                not measured["modifiers"] and not measured["has_animation"],
                "Modified/animated source requires separate review",
            )
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
                "selection_policy": "explicit inspection-bound object name; only selected MESH; original local geometry/object transform unchanged",
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
                "all_imported_objects": [
                    {
                        "name": o.name,
                        "type": o.type,
                        "parent": o.parent.name if o.parent else None,
                    }
                    for o in sorted(imported, key=lambda o: o.name)
                ],
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
        "request_sha256": request_hash,
        "script_sha256": sha(Path(__file__)),
        "selection_sha256": sha(args.selection) if args.selection else None,
        "import_settings": settings,
        "parser_sha256": sha(Path(parse_fbx.__file__)),
        "assets": records,
        "units": "Blender scene metres after standard FBX declared-unit/axis conversion",
        "comparison_policy": "Compare UE cm to Blender metres*100 only after documenting UE import axis mapping; world/local bounds and object origins are distinct",
        "limitations": "Topology/winding/volume diagnostics do not establish non-self-intersection, continuous support, underside suitability or visual acceptance. Explicit selection is not automatic LOD identification. No underside preparation performed.",
        "source_modified": False,
        "assets_saved": False,
        "derived_source_files_exported": derived_directory is not None,
        "placement": False,
        "qualified_assets": [],
        "native_unreal_execution": "NOT_RUN",
    }
    require(sha(args.request) == request_hash, "Request changed during inspection")
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
