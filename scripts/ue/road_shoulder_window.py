"""Source-owned window 0112 shoulder material IDs; no geometry authoring.

The frozen producer uses 27 points per cross-section. Only its two outer
strips receive slot 1; interior top faces, vertical walls and every other mesh
retain their original material IDs. Native positions, indices and every
triangle-corner normal/UV are hashed before assignment and after fresh load.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import struct

from scripts.ci import official_mcp_bob_session as session
from scripts.manage_local_workspace import load_workspace
from scripts.proof.sa_calobra_shoulder_contact import (
    WINDOW,
    interior_top_triangles,
    triangle_delta,
)
from scripts.proof.sa_calobra_tpp_survey import load_frozen_windows
from scripts.ue import read_road_material_baseline as baseline
from scripts.ue.capture_sa_calobra_shoulder_contact import (
    actor_snapshot,
    mesh_triangle,
    native_triangles,
)

SECTION_COUNT = 110
SECTION_WIDTH = 27
TOP_TRIANGLES = (SECTION_COUNT - 1) * 52
MAX_TRIANGLES = 12000
MAX_VERTICES = 20000
OLD_MATERIAL = "/Game/Worlds/SaCalobra/CheckpointMaterials/MI_Accepted_1.MI_Accepted_1"
SHOULDER_IDS = tuple(
    i * 52 + j * 2 + side
    for i in range(SECTION_COUNT - 1)
    for j in (0, 25)
    for side in (0, 1)
)
API_FILES = {
    "Plugins/Runtime/GeometryScripting/Source/GeometryScriptingCore/Public/GeometryScript/MeshMaterialFunctions.h": "SetTriangleMaterialID",
    "Plugins/Runtime/GeometryScripting/Source/GeometryScriptingCore/Private/MeshMaterialFunctions.cpp": "SetTriangleMaterialID",
    "Source/Runtime/GeometryFramework/Public/Components/DynamicMeshComponent.h": "ConfigureMaterialSet",
    "Source/Runtime/GeometryFramework/Private/Components/DynamicMeshComponent.cpp": "ConfigureMaterialSet",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def xyz(value):
    result = tuple(float(getattr(value, key)) for key in ("x", "y", "z"))
    require(all(math.isfinite(v) for v in result), "Nonfinite native mesh vector")
    return result


def native_api_evidence(api, component):
    """Read installed source and reflection before invoking material-ID setters."""
    require(str(api.SystemLibrary.get_engine_version()).startswith("5.8.2-56702186"),
            "Shoulder material API requires the pinned UE 5.8.2 build")
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    sources = {}
    for relative, symbol in API_FILES.items():
        file = session._safe_path(engine, relative)
        identity = session._identity(file, 4 * 1024 * 1024)
        text = file.read_text(encoding="utf-8-sig")
        require(symbol in text, "Installed material API source lacks " + symbol)
        sources[relative] = {**identity, "verified_symbol": symbol}
    docs = {}
    for name, method, parameters in (
        ("GeometryScript_Materials.set_triangle_material_id",
         api.GeometryScript_Materials.set_triangle_material_id,
         ("target_mesh", "triangle_id", "material_id", "defer_change_notifications")),
        ("DynamicMeshComponent.configure_material_set", component.configure_material_set,
         ("new_material_set", "delete_extra_slots")),
    ):
        doc = str(getattr(method, "__doc__", "") or "")
        require(callable(method) and all(p in doc for p in parameters),
                "Installed material-ID Python signature differs: " + name)
        docs[name] = {"signature": doc[:2048], "sha256": hashlib.sha256(doc.encode()).hexdigest()}
    return {"engine_version": str(api.SystemLibrary.get_engine_version()),
            "installed_sources": sources, "native_signatures": docs,
            "engine_source_redistributed": False}


def frozen_window():
    config = load_workspace()
    data = Path(config["data"])
    relative = str(Path(session.PROFILE_RELATIVE).parent).replace("\\", "/")
    root = session._safe_path(data, relative)
    recipe = session._read_json(
        session._safe_path(session.ROOT,
            "worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json")
    )
    for row in recipe["inputs"]:
        session._safe_path(root, row["path"])
    source = load_frozen_windows(root)
    matches = [row for row in source["windows"] if row["id"] == WINDOW]
    require(len(matches) == 1 and not matches[0].get("nudo_structure"),
            "Frozen ordinary shoulder window is missing or ambiguous")
    return matches[0]["sections"], source["source_identity"]


def find_owner(api, actors, sections):
    """Verify the actual mesh against all 5,232 immutable interior top faces."""
    target = list(interior_top_triangles(sections))
    matches = []
    for actor in baseline.road_support_actors(actors)[1:]:
        state = actor_snapshot(actor)
        require(state["location_cm"] == (0.0, 0.0, 0.0)
                and state["rotation_deg"] == (0.0, 0.0, 0.0)
                and state["scale"] == (1.0, 1.0, 1.0),
                "Unexpected transformed support in frozen consumer")
        component = actor.get_dynamic_mesh_component()
        mesh = component.get_dynamic_mesh()
        tid, expected = target[0]
        probe = native_triangles(api, mesh, [tid], allow_missing=True)
        if probe is None or triangle_delta(mesh_triangle(probe, tid), expected) > 0.0001:
            continue
        actual = native_triangles(api, mesh)
        worst = max(triangle_delta(mesh_triangle(actual, i), points) for i, points in target)
        if worst <= 0.0001:
            matches.append((actor, component, mesh, worst))
    require(len(matches) == 1, "Source-owned window0112 support is missing or duplicated")
    return matches[0]


def read_mesh(api, mesh):
    """Dense native readback, preserving IDs and all rendered normal/UV corners."""
    queries = api.GeometryScript_MeshQueries
    vertices, triangles = int(mesh.get_vertex_count()), int(mesh.get_triangle_count())
    require(0 < vertices <= MAX_VERTICES and TOP_TRIANGLES <= triangles <= MAX_TRIANGLES,
            "Window0112 mesh exceeds the bounded native inventory")
    require(queries.get_num_vertex_i_ds(mesh) == vertices
            and queries.get_num_triangle_i_ds(mesh) == triangles,
            "Window0112 native mesh has unadmitted vertex/triangle gaps")
    uv_sets = int(mesh.get_num_uv_sets())
    require(0 <= uv_sets <= 4, "Unexpected native support UV layer count")
    geometry, attributes, materials = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    geometry.update(struct.pack("<3i", 1, vertices, triangles))
    attributes.update(struct.pack("<2i", 1, uv_sets))
    points, faces, ids = [], [], []
    for vid in range(vertices):
        point, valid = queries.get_vertex_position(mesh, vid)
        require(valid is True, "Native vertex read failed")
        point = xyz(point)
        points.append(point)
        geometry.update(struct.pack("<i3d", vid, *point))
    for tid in range(triangles):
        face, valid = queries.get_triangle_indices(mesh, tid)
        indices = tuple(int(getattr(face, k)) for k in ("x", "y", "z"))
        require(valid is True and len(set(indices)) == 3
                and all(0 <= i < vertices for i in indices), "Native triangle read failed")
        faces.append(indices)
        geometry.update(struct.pack("<4i", tid, *indices))
        result = queries.get_triangle_normals(mesh, tid)
        require(len(result) == 5 and result[-1] is True,
                "Native triangle has no verified split normals")
        attributes.update(struct.pack("<i", tid))
        for vector in result[1:4]:
            attributes.update(struct.pack("<3d", *xyz(vector)))
        for layer in range(uv_sets):
            result = queries.get_triangle_u_vs(mesh, layer, tid)
            require(len(result) == 4 and type(result[-1]) is bool,
                    "Native UV read signature differs")
            attributes.update(struct.pack("<i?", layer, result[-1]))
            for vector in result[:3]:
                uv = (float(vector.x), float(vector.y))
                require(all(math.isfinite(v) for v in uv), "Nonfinite native UV")
                attributes.update(struct.pack("<2d", *uv))
        material_id, valid = mesh.get_triangle_material_id(tid)
        require(valid is True and type(material_id) is int and material_id >= 0,
                "Native triangle material ID is unavailable")
        ids.append(material_id)
        materials.update(struct.pack("<2i", tid, material_id))
    return {
        "points": points, "faces": faces, "material_ids": ids,
        "summary": {"vertex_count": vertices, "triangle_count": triangles,
                    "uv_set_count": uv_sets, "positions_indices_sha256": geometry.hexdigest(),
                    "triangle_corner_normals_uv_sha256": attributes.hexdigest(),
                    "material_ids_sha256": materials.hexdigest()},
    }


def verify_selection(snapshot, sections):
    """Validate ordered source top strips and reject side-wall or under-road IDs."""
    points, faces = snapshot["points"], snapshot["faces"]
    require(len(sections) == SECTION_COUNT and all(len(s) == 25 for s in sections),
            "Window0112 source cross sections differ")
    require(TOP_TRIANGLES <= len(faces) <= MAX_TRIANGLES
            and SECTION_COUNT * SECTION_WIDTH <= len(points) <= MAX_VERTICES,
            "Window0112 native top inventory is incomplete")
    worst, extents = 0.0, []
    for i, section in enumerate(sections):
        for j, source in enumerate(section, 1):
            expected = (source[0] * 100, source[1] * 100, (source[2] - 0.08) * 100)
            actual = points[i * 27 + j]
            worst = max(worst, *(abs(a - b) for a, b in zip(actual, expected, strict=True)))
        for outer, inner in ((0, 1), (26, 25)):
            width = math.dist(points[i * 27 + outer][:2], points[i * 27 + inner][:2]) / 100
            require(0 < width <= 1.0, "Frozen shoulder extent is not bounded")
            extents.append(width)
    require(worst <= 0.0001, "Native support no longer matches frozen road source")
    for i in range(SECTION_COUNT - 1):
        for j in range(26):
            a, b, c, d = i * 27 + j, i * 27 + j + 1, (i + 1) * 27 + j, (i + 1) * 27 + j + 1
            require(tuple(faces[i * 52 + j * 2]) == (a, b, c)
                    and tuple(faces[i * 52 + j * 2 + 1]) == (b, d, c),
                    "Frozen support top triangle topology differs")
    for face in faces[TOP_TRIANGLES:]:
        require(all(v >= SECTION_COUNT * 27 for v in face),
                "Wall material domain shares a top-strip vertex")
        a, b, c = (points[v] for v in face)
        u, v = [b[k] - a[k] for k in range(3)], [c[k] - a[k] for k in range(3)]
        normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        length = math.sqrt(sum(n * n for n in normal))
        require(length > 0 and abs(normal[2]) / length <= 1e-6,
                "Unrecognized nonvertical wall/structure in shoulder owner")
    return {"window_id": WINDOW, "source_interior_triangles_compared": 5232,
            "max_source_coordinate_delta_cm": worst, "selected_triangle_count": len(SHOULDER_IDS),
            "selected_triangle_ids": list(SHOULDER_IDS), "top_triangle_count": TOP_TRIANGLES,
            "min_shoulder_width_m": min(extents), "max_shoulder_width_m": max(extents),
            "selection": "frozen_27_column_top_outer_strips_j0_j25",
            "walls_and_under_road_top_selected": False}


def verify_mesh_delta(before, after, selected=SHOULDER_IDS):
    require(before["summary"]["positions_indices_sha256"] == after["summary"]["positions_indices_sha256"]
            and before["summary"]["triangle_corner_normals_uv_sha256"] == after["summary"]["triangle_corner_normals_uv_sha256"],
            "Shoulder assignment changed positions, topology, normals or UVs")
    require(tuple(selected) == SHOULDER_IDS, "Shoulder selection widened beyond frozen outer strips")
    require(all(value == 0 for value in before["material_ids"]),
            "Original support contains unadmitted material IDs")
    selected_set = set(selected)
    require(len(after["material_ids"]) == len(before["material_ids"])
            and all(value == (1 if tid in selected_set else 0)
                    for tid, value in enumerate(after["material_ids"])),
            "Unexpected wall/interior/shoulder triangle material assignment")


def set_ids(api, component, selected, material_id):
    require(tuple(selected) == SHOULDER_IDS and material_id in (0, 1),
            "Unapproved shoulder material mutation")
    mesh = component.get_dynamic_mesh()
    for tid in selected:
        result = api.GeometryScript_Materials.set_triangle_material_id(
            mesh, tid, material_id, defer_change_notifications=True)
        require(len(result) == 2 and result[0] == mesh and result[1] is True,
                "Native shoulder material ID setter rejected triangle " + str(tid))
    component.notify_mesh_modified()


def apply_with_rollback_proof(api, component, instance, before):
    """Prove reversible material-only assignment, then bind the same candidate."""
    require(component.get_num_materials() == 1, "Original shoulder slot count differs")
    old = component.get_material(0)
    require(old is not None and old.get_path_name() == OLD_MATERIAL,
            "Original shoulder/wall material differs")
    try:
        component.configure_material_set([old, instance], delete_extra_slots=True)
        set_ids(api, component, SHOULDER_IDS, 1)
        during = read_mesh(api, component.get_dynamic_mesh())
        verify_mesh_delta(before, during)
    finally:
        set_ids(api, component, SHOULDER_IDS, 0)
        component.configure_material_set([old], delete_extra_slots=True)
        require(component.get_num_materials() == 1 and component.get_material(0) == old,
                "Shoulder material slots failed to roll back")
        restored = read_mesh(api, component.get_dynamic_mesh())
        require(restored["summary"] == before["summary"], "Shoulder mesh rollback differs")
    component.configure_material_set([old, instance], delete_extra_slots=True)
    set_ids(api, component, SHOULDER_IDS, 1)
    after = read_mesh(api, component.get_dynamic_mesh())
    verify_mesh_delta(before, after)
    return after


def verify_loaded(api, receipt):
    """Fresh-load readback: no material assignment, geometry change or saving."""
    sections, identity = frozen_window()
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    actor, component, mesh, _worst = find_owner(api, actors, sections)
    require(actor.get_actor_label() == receipt["support_label"]
            and identity == receipt["source_identity"], "Fresh shoulder source owner differs")
    current = read_mesh(api, mesh)
    require(verify_selection(current, sections) == receipt["selection"],
            "Fresh shoulder triangle/footprint selection differs")
    require(current["summary"] == receipt["after_mesh"],
            "Fresh shoulder positions, indices, normals, UV or material IDs differ")
    require(component.get_num_materials() == 2
            and component.get_material(0).get_path_name() == OLD_MATERIAL
            and component.get_material(1).get_path_name() == receipt["material"]["assets"]["instance"],
            "Fresh shoulder/wall material slots differ")
    return current["summary"]
