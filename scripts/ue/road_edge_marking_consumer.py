"""Bounded render-only edge paint; source addresses are explicit, never searched.

``prepare`` is pure. Its caller supplies authenticated ``load_sources()`` data,
the exact retained pavement producer bytes, its ordered quad topology, and
explicit native triangle/vertex addresses. A binding is an eight-field row:
``[support_label, section, cell, slot, road_tid, road_vid0, road_vid1, road_vid2]``.
Only the source triangles actually clipped by the paint builder may be bound.
This module never executes the old producer or infers its global offsets.

``create`` checks every addressed native road face before creating a new M/MI
and separate DynamicMesh actors. Original road/support buffers, bindings and
transforms are compared in full. The caller owns exact-SHA staging, saving a
new derived map, package-byte identities and the separate fresh editor run.
``verify_loaded`` only reads; it never reapplies bindings or repairs geometry.

The builder's flat normals and hash remain intact. A separately hashed render
payload interpolates the REAL road's split corner normals with its barycentric
weights. Positions, triangles and UV0 remain those of the clipped builder.
Native buffer authoring is gated by an actual transient two-triangle probe.

Primary UE 5.8 contracts, supplemented by installed source and native readback:
https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/GeometryScriptSimpleMeshBuffers
https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/GeometryFramework/UDynamicMeshComponent
Existing native call conventions: road_shoulder_window.py and
capture_sa_calobra_component230_cliff.py. No alternate guessed API is tried.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import time

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import read_road_material_baseline as baseline
from scripts.ue import road_asphalt_saved_consumer as saved
from scripts.ue import road_edge_marking_geometry as geometry
from scripts.ue import road_edge_marking_material as material
from scripts.ue import road_shoulder_network as network
from scripts.ue import road_shoulder_sources as sources
from scripts.ue import road_shoulder_window as existing

ROOT = Path(__file__).resolve().parents[2]
ACTOR_PREFIX = "YACS_ROAD_EDGE_MARKING_"
PRODUCER_IDENTITY = dict(sources.PRODUCERS["network_pavement.py"])
PRODUCER_PATH = "support-consumers/network_pavement.py"
MAX_BINDINGS = 250000
MAX_BINDING_BYTES = 32 * 1024 * 1024
POSITION_TOLERANCE_CM = 0.0001
ATTRIBUTE_TOLERANCE = 0.000001
NORMAL_CONTRACT = "normalized_barycentric_native_road_split_corner_normals"
NORMAL_ORIENTATION_CONTRACT = "preserve_recorded_native_normals_and_source_winding_without_sign_conversion"
CORNER_OFFSETS = ((0, 0), (0, 1), (1, 0), (1, 1))
FALSE_FLAGS = ("source_geometry_changed", "source_materials_changed", "collision_enabled",
               "cast_shadow", "affects_navigation", "physics_authored", "map_saved",
               "owner_visual_pass", "performance_pass")


@dataclass(frozen=True)
class SourceTriangle:
    key: tuple[str, int, int, int]
    triangle_id: int
    vertex_ids: tuple[int, int, int]
    positions_cm: tuple[tuple[float, float, float], ...]


@dataclass(frozen=True)
class PreparedMarkings:
    geometry_manifest_json: str
    meshes: tuple[geometry.MarkingMesh, ...]
    source_triangles: tuple[SourceTriangle, ...]
    producer_sha256: str
    producer_size_bytes: int
    plan_sha256: str


@dataclass(frozen=True)
class RenderPayload:
    label: str
    source_mesh_sha256: str
    positions_cm: tuple[tuple[float, float, float], ...]
    triangles: tuple[tuple[int, int, int], ...]
    normals: tuple[tuple[float, float, float], ...]
    uv0: tuple[tuple[float, float], ...]


def require(value, message):
    if not value:
        raise ValueError(message)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _label(mesh):
    require(re.fullmatch(r"YACS_PERSIST_SUPPORT_[0-9]{3}", mesh.owner_label) is not None
            and int(mesh.owner_label[-3:]) < sources.OWNER_COUNT,
            "Edge marking owner has no bounded saved support identity")
    return ACTOR_PREFIX + mesh.owner_label[-3:] + "_" + mesh.edge


def _plan_hash(manifest_json, meshes, triangles, producer_sha256, producer_size_bytes):
    return _digest({"geometry_manifest_json": manifest_json,
                    "mesh_sha256": [geometry.mesh_sha256(mesh) for mesh in meshes],
                    "source_triangles": [[*row.key, row.triangle_id, *row.vertex_ids, row.positions_cm]
                                         for row in triangles],
                    "producer_sha256": producer_sha256, "producer_size_bytes": producer_size_bytes})


def prepare(source_plan, *, producer_bytes, quad_triangles, triangle_bindings):
    """Pure preparation with exact source bytes and explicit native addresses.

    No default diagonal, global offset calculation, nearby-face lookup, native
    import, file write or source-producer execution is allowed in this step.
    """
    require(type(producer_bytes) is bytes and len(producer_bytes) == PRODUCER_IDENTITY["size_bytes"]
            and hashlib.sha256(producer_bytes).hexdigest() == PRODUCER_IDENTITY["sha256"],
            "Edge markings need the exact retained pavement producer bytes")
    require(isinstance(source_plan, dict)
            and source_plan.get("source_identity", {}).get("producer_files", {}).get(PRODUCER_PATH)
            == PRODUCER_IDENTITY, "Pavement producer differs from the authenticated source plan")
    build = geometry.build_markings(source_plan, quad_triangles=quad_triangles)
    require(build.manifest["material_uv_contract"] == material.UV_CONTRACT,
            "Paint geometry width/UV contract differs from its material")
    require(isinstance(triangle_bindings, (tuple, list)) and 0 < len(triangle_bindings) <= MAX_BINDINGS,
            "Explicit pavement triangle bindings are missing or unbounded")
    require(len(_json(triangle_bindings).encode()) <= MAX_BINDING_BYTES,
            "Explicit pavement addresses exceed their byte bound")
    needed = {(mesh.owner_label, *fragment.source_triangle)
              for mesh in build.meshes for fragment in mesh.fragments}
    owners = {owner["support_label"]: owner for owner in source_plan["owners"] if owner["material_target"]}
    topology = build.manifest["source_triangle_layout"]["quad_triangles"]
    requests, seen_keys, seen_tids, vertex_owners = [], set(), set(), {}
    for row in triangle_bindings:
        require(isinstance(row, (tuple, list)) and len(row) == 8
                and isinstance(row[0], str) and all(type(v) is int and v >= 0 for v in row[1:]),
                "Pavement binding needs one owner plus seven explicit nonnegative integer addresses")
        key, tid, vids = tuple(row[:4]), row[4], tuple(row[5:8])
        require(key in needed and key not in seen_keys and tid not in seen_tids,
                "Pavement binding is missing, duplicated or outside the clipped source triangles")
        require(tid < network.ROAD_COUNTS[1] and len(set(vids)) == 3
                and all(vid < network.ROAD_COUNTS[0] for vid in vids),
                "Pavement binding is outside the accepted native road")
        label, section, cell, slot = key
        source_keys = tuple((label, section + CORNER_OFFSETS[index][0], cell + CORNER_OFFSETS[index][1])
                            for index in topology[slot])
        points = []
        for vid, point_key in zip(vids, source_keys, strict=True):
            require(vid not in vertex_owners or vertex_owners[vid] == point_key,
                    "Native pavement vertex is claimed by different source vertices")
            vertex_owners[vid] = point_key
            points.append(tuple(float(value) * 100.0
                                for value in owners[label]["pavement_sections_m"][point_key[1]][point_key[2]]))
        requests.append(SourceTriangle(key, tid, vids, tuple(points)))
        seen_keys.add(key)
        seen_tids.add(tid)
    require(seen_keys == needed, "Every clipped source triangle needs its explicit native binding")
    require(len({_label(mesh) for mesh in build.meshes}) == len(build.meshes), "Duplicate paint actor identity")
    requests = tuple(sorted(requests, key=lambda row: row.key))
    manifest_json = _json(build.manifest)
    digest = _plan_hash(manifest_json, build.meshes, requests, **{
        "producer_sha256": PRODUCER_IDENTITY["sha256"], "producer_size_bytes": PRODUCER_IDENTITY["size_bytes"]})
    return PreparedMarkings(manifest_json, build.meshes, requests, PRODUCER_IDENTITY["sha256"],
                            PRODUCER_IDENTITY["size_bytes"], digest)


def _check_plan(plan, *, native=False):
    require(isinstance(plan, PreparedMarkings)
            and plan.producer_sha256 == PRODUCER_IDENTITY["sha256"]
            and plan.producer_size_bytes == PRODUCER_IDENTITY["size_bytes"]
            and plan.plan_sha256 == _plan_hash(plan.geometry_manifest_json, plan.meshes, plan.source_triangles,
                                             plan.producer_sha256, plan.producer_size_bytes),
            "Edge marking preparation changed or lacks the pinned producer")
    manifest = json.loads(plan.geometry_manifest_json)
    if native:
        counts = manifest["counts"]
        require(counts["source_owner_count"] == sources.OWNER_COUNT
                and counts["pavement_owner_count"] == sources.NETWORK_COUNT + 1
                and counts["excluded_parapet_count"] == 1
                and counts["source_section_count"] == sources.PROFILE_PAVEMENT_ROW_COUNT
                and counts["mesh_count"] == 2 * (sources.NETWORK_COUNT + 1),
                "Native edge paint requires the complete authenticated 185-owner pavement")
    return manifest


def _vector(value, fields="xyz"):
    result = tuple(getattr(value, axis) for axis in fields)
    require(all(type(v) in (int, float) and math.isfinite(v) for v in result),
            "Native paint/source attribute contains a nonfinite coordinate")
    return tuple(float(v) for v in result)


def _unit(vector):
    magnitude = math.hypot(*vector)
    require(math.isfinite(magnitude) and magnitude > 1e-12, "Degenerate source or interpolated paint normal")
    return tuple(v / magnitude for v in vector)


def _close(actual, expected, tolerance):
    return len(actual) == len(expected) and max(abs(a - b) for a, b in zip(actual, expected, strict=True)) <= tolerance


def read_source_triangle(api, road_mesh, triangle_id, expected_vertex_ids, expected_positions_cm):
    """Read one explicitly addressed road face; never resolve by proximity.

    Existing GeometryScript query tuple shapes are checked exactly. Returned
    normals are the actual split corner values, not recomputed face normals.
    The caller first authenticates the road component and complete mesh hash.
    """
    require(type(triangle_id) is int and 0 <= triangle_id < network.ROAD_COUNTS[1]
            and len(expected_vertex_ids) == len(expected_positions_cm) == 3
            and len(set(expected_vertex_ids)) == 3
            and all(type(vid) is int and 0 <= vid < network.ROAD_COUNTS[0] for vid in expected_vertex_ids)
            and all(len(point) == 3 and all(type(v) in (int, float) and math.isfinite(v) for v in point)
                    for point in expected_positions_cm),
            "Invalid explicit native road triangle request")
    query = api.GeometryScript_MeshQueries
    result = query.get_triangle_indices(road_mesh, triangle_id)
    require(isinstance(result, tuple) and len(result) == 2 and result[1] is True,
            "Native road triangle index read failed")
    indices = tuple(getattr(result[0], axis) for axis in "xyz")
    require(all(type(v) is int for v in indices) and indices == tuple(expected_vertex_ids),
            "Native road triangle topology/winding differs from the pinned producer")
    points = []
    for vid, expected in zip(indices, expected_positions_cm, strict=True):
        result = query.get_vertex_position(road_mesh, vid)
        require(isinstance(result, tuple) and len(result) == 2 and result[1] is True,
                "Native road vertex read failed")
        point = _vector(result[0])
        require(_close(point, expected, POSITION_TOLERANCE_CM),
                "Native road triangle no longer corresponds to its immutable source surface")
        points.append(point)
    result = query.get_triangle_normals(road_mesh, triangle_id)
    require(isinstance(result, tuple) and len(result) == 5 and result[0] == road_mesh and result[4] is True,
            "Native road split corner normal read failed")
    normals = tuple(_vector(vector) for vector in result[1:4])
    face_normal = _unit(geometry._cross(*points))
    # The authenticated pavement producer has clockwise top faces in source
    # XY (negative mathematical cross Z). That sign does not authorize a
    # guessed conversion of Unreal's stored split normals. Keep both ordered
    # indices and every native normal as read; all corners must be unit and
    # lie in one coherent open hemisphere of this source face. This also makes
    # every convex barycentric normal interpolation nonzero. Full source
    # buffer/asset identities, rather than an invented up-axis, own the values.
    dots = [sum(a * b for a, b in zip(normal, face_normal, strict=True)) for normal in normals]
    alignment = 1 if dots[0] > 0 else -1
    require(abs(face_normal[2]) > 0.000001
            and all(abs(math.hypot(*normal) - 1.0) <= 0.00001 for normal in normals)
            and all(alignment * dot > 0.000001 for dot in dots),
            "Native road top winding or split normal orientation is invalid")
    return {"triangle_id": triangle_id, "vertex_ids": indices,
            "positions_cm": tuple(points), "corner_normals": normals,
            "ordered_face_cross_z_sign": 1 if face_normal[2] > 0 else -1,
            "native_corner_normal_cross_alignment_sign": alignment}


def _render_payloads(plan, witnesses):
    outputs = []
    for mesh in plan.meshes:
        normals = [None] * len(mesh.positions_m)
        for fragment in mesh.fragments:
            witness = witnesses[(mesh.owner_label, *fragment.source_triangle)]
            for index in range(fragment.first_vertex, fragment.first_vertex + fragment.vertex_count):
                weights = mesh.barycentric_weights[index]
                normal = tuple(sum(weights[corner] * witness["corner_normals"][corner][axis]
                                   for corner in range(3)) for axis in range(3))
                normals[index] = _unit(normal)
        require(all(normal is not None for normal in normals), "A paint vertex has no native source normal")
        outputs.append(RenderPayload(_label(mesh), geometry.mesh_sha256(mesh),
                                     tuple(tuple(value * 100.0 for value in point) for point in mesh.positions_m),
                                     mesh.triangles, tuple(normals), mesh.uv0))
    return tuple(outputs)


def render_payload_sha256(payload):
    digest = hashlib.sha256(b"YACS_EDGE_MARKING_NATIVE_NORMAL_PAYLOAD_V1\0")
    digest.update((payload.label + "\0" + payload.source_mesh_sha256 + "\0" + NORMAL_CONTRACT).encode())
    for rows, fmt in ((payload.positions_cm, "<3d"), (payload.triangles, "<3I"),
                      (payload.normals, "<3d"), (payload.uv0, "<2d")):
        digest.update(struct.pack("<I", len(rows)))
        for row in rows:
            digest.update(struct.pack(fmt, *row))
    return digest.hexdigest()


def _read_payload(api, mesh, payload):
    """Read every new native position/index/corner normal/UV/material ID."""
    query = api.GeometryScript_MeshQueries
    vertices, triangles = len(payload.positions_cm), len(payload.triangles)
    require(mesh.get_vertex_count() == query.get_num_vertex_i_ds(mesh) == vertices
            and mesh.get_triangle_count() == query.get_num_triangle_i_ds(mesh) == triangles
            and mesh.get_num_uv_sets() == 1, "Native paint mesh has gaps, extra data or missing UV0")
    digest = hashlib.sha256(b"YACS_EDGE_MARKING_NATIVE_BUFFER_V1\0")
    digest.update(struct.pack("<3I", vertices, triangles, 1))
    for vid, expected in enumerate(payload.positions_cm):
        result = query.get_vertex_position(mesh, vid)
        require(isinstance(result, tuple) and len(result) == 2 and result[1] is True,
                "Native paint vertex read failed")
        point = _vector(result[0])
        require(_close(point, expected, POSITION_TOLERANCE_CM), "Native paint position differs from clipped source")
        digest.update(struct.pack("<I3d", vid, *point))
    for tid, expected in enumerate(payload.triangles):
        face = query.get_triangle_indices(mesh, tid)
        require(isinstance(face, tuple) and len(face) == 2 and face[1] is True,
                "Native paint triangle read failed")
        indices = tuple(getattr(face[0], axis) for axis in "xyz")
        require(indices == expected and all(type(v) is int for v in indices),
                "Native paint source triangulation changed")
        normals = query.get_triangle_normals(mesh, tid)
        uvs = query.get_triangle_u_vs(mesh, 0, tid)
        material_id = mesh.get_triangle_material_id(tid)
        require(isinstance(normals, tuple) and len(normals) == 5 and normals[0] == mesh and normals[4] is True
                and isinstance(uvs, tuple) and len(uvs) == 4 and uvs[3] is True
                and isinstance(material_id, tuple) and len(material_id) == 2
                and type(material_id[0]) is int and material_id[0] == 0 and material_id[1] is True,
                "Native paint normals, UV0 or material IDs are unavailable")
        digest.update(struct.pack("<5I", tid, *indices, 0))
        for corner, vid in enumerate(indices):
            normal, uv = _vector(normals[corner + 1]), _vector(uvs[corner], "xy")
            quantized_normal = tuple(struct.unpack("<f", struct.pack("<f", v))[0] for v in payload.normals[vid])
            quantized_uv = tuple(struct.unpack("<f", struct.pack("<f", v))[0] for v in payload.uv0[vid])
            require(_close(normal, quantized_normal, ATTRIBUTE_TOLERANCE),
                    "Native paint split normal differs from the interpolated road normal")
            require(_close(uv, quantized_uv, ATTRIBUTE_TOLERANCE), "Native paint UV0 differs from its source clipping")
            digest.update(struct.pack("<5d", *normal, *uv))
    return {"vertex_count": vertices, "triangle_count": triangles, "uv_set_count": 1,
            "native_buffers_sha256": digest.hexdigest(), "render_payload_sha256": render_payload_sha256(payload)}


def _append_payload(api, mesh, payload):
    require(mesh.get_vertex_count() == mesh.get_triangle_count() == 0, "Refuse to append paint to an existing mesh")
    buffers = api.GeometryScriptSimpleMeshBuffers()
    buffers.set_editor_property("vertices", [api.Vector(*point) for point in payload.positions_cm])
    buffers.set_editor_property("triangles", [api.IntVector(*face) for face in payload.triangles])
    buffers.set_editor_property("normals", [api.Vector(*normal) for normal in payload.normals])
    buffers.set_editor_property("uv0", [api.Vector2D(*uv) for uv in payload.uv0])
    # The stock return object is not substituted for actual complete readback.
    mesh.append_buffers_to_mesh(buffers, material_id=0, defer_change_notifications=True)


def _buffer_probe(api):
    """Real transient native behavior, including UVs and deliberately split normals."""
    first, second = _unit((0.12, 0.0, 1.0)), _unit((0.0, -0.18, 1.0))
    payload = RenderPayload("transient-buffer-probe", "0" * 64,
                            ((0., 0., 0.), (10., 0., 0.), (0., 10., 0.),
                             (10., 0., 0.), (10., 10., 1.), (0., 10., 0.)),
                            ((0, 1, 2), (3, 4, 5)), (first, first, first, second, second, second),
                            ((0., 0.), (1., 0.), (0., 1.), (1., 0.), (1., 1.), (0., 1.)))
    mesh = api.DynamicMesh()
    require(mesh is not None and isinstance(mesh, api.DynamicMesh), "Native transient DynamicMesh is unavailable")
    _append_payload(api, mesh, payload)
    summary = _read_payload(api, mesh, payload)
    return {"status": "NATIVE_BUFFER_APPEND_READBACK_VERIFIED", **summary,
            "normals_supplied_not_recomputed": True, "world_actor_created": False}


def native_api_evidence(api):
    """Installed source + exact generated signatures; behavior is probed separately."""
    material._context(api)
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    files = {}
    geometry_root = "Plugins/Runtime/GeometryScripting/Source/GeometryScriptingCore/"
    contracts = [
        ([geometry_root + "Public/GeometryScript/MeshBasicEditFunctions.h"],
         ("FGeometryScriptSimpleMeshBuffers", "AppendBuffersToMesh", "Normals", "UV0")),
        ([geometry_root + "Private/MeshBasicEditFunctions.cpp"], ("AppendBuffersToMesh",)),
        ([geometry_root + "Public/GeometryScript/MeshQueryFunctions.h"],
         ("GetTriangleIndices", "GetTriangleNormals", "GetTriangleUVs", "GetVertexPosition")),
        (["Source/Runtime/GeometryFramework/Public/Components/DynamicMeshComponent.h"],
         ("GetTangentsType", "SetTangentsType", "bEnableComplexCollision")),
    ]
    for name, folder, symbols in (
        ("ActorComponent", "Components", ("bCanEverAffectNavigation",)),
        ("PrimitiveComponent", "Components", ("SetCastShadow", "SetCollisionEnabled", "bGenerateOverlapEvents")),
        ("Actor", "GameFramework", ("RootComponent", "bHidden")),
    ):
        contracts.append(([f"Source/Runtime/Engine/{location}/{folder}/{name}.h"
                           for location in ("Public", "Classes")], symbols))
    for candidates, symbols in contracts:
        matches = [relative for relative in candidates if session._safe_path(engine, relative).is_file()]
        require(matches, "Installed paint consumer source is missing: " + candidates[0])
        relative = matches[0]
        path = session._safe_path(engine, relative)
        identity = session._identity(path, 4 * 1024 * 1024)
        source = path.read_text(encoding="utf-8-sig")
        require(all(symbol in source for symbol in symbols),
                "Installed native paint consumer source contract differs: " + relative)
        files[relative] = {**identity, "verified_symbols": list(symbols)}
    signatures = {}
    for owner_name, names in (
        ("DynamicMesh", ("append_buffers_to_mesh", "get_triangle_material_id")),
        ("GeometryScript_MeshQueries", ("get_triangle_indices", "get_vertex_position", "get_triangle_normals",
                                         "get_triangle_u_vs", "get_num_vertex_i_ds", "get_num_triangle_i_ds")),
        ("DynamicMeshComponent", ("set_collision_enabled", "get_collision_enabled", "set_cast_shadow",
                                    "set_tangents_type", "get_tangents_type", "notify_mesh_modified")),
        ("EditorActorSubsystem", ("spawn_actor_from_class", "destroy_actor")),
        ("EditorAssetLibrary", ("delete_asset", "does_asset_exist")),
    ):
        owner = getattr(api, owner_name, None)
        require(owner is not None, "Required native paint API owner is unavailable: " + owner_name)
        for name in names:
            method = getattr(owner, name, None)
            doc = str(getattr(method, "__doc__", "") or "")
            require(callable(method) and 0 < len(doc) <= 32768,
                    "Required native paint API has no callable signature: " + owner_name + "." + name)
            signatures[owner_name + "." + name] = {
                "signature": doc.splitlines()[0], "sha256": hashlib.sha256(doc.encode()).hexdigest()}
    return {"engine_version": material.ENGINE_VERSION, "installed_sources": files,
            "native_signatures": signatures, "engine_source_redistributed": False}


def _world(api):
    material._context(api)
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    require(world is not None and world.get_path_name().split(".")[0] in network.MAPS,
            "Paint consumer requires the bounded road material review world")
    return world.get_path_name().split(".")[0]


def _actors(api):
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    require(len(actors) <= baseline.ACTOR_LIMIT, "Paint actor inventory exceeds its explicit bound")
    return actors


def _source_state(api, actors, package):
    """Complete native road/support buffers and bindings, plus other actor identity."""
    rows, road_component = [], None
    for actor in baseline.road_support_actors(actors):
        require(isinstance(actor, api.DynamicMeshActor), "Road/source owner is not its native DynamicMeshActor")
        component = actor.get_dynamic_mesh_component()
        require(isinstance(component, api.DynamicMeshComponent), "Road/source component type changed")
        value = network.inspect_mesh(api, component)
        if actor.get_actor_label() == "YACS_PERSIST_ROAD":
            road_component = component
        count = component.get_num_materials()
        require(type(count) is int and 0 < count <= 32, "Source material slot count is invalid")
        slots = []
        for index in range(count):
            asset = component.get_material(index)
            require(asset is not None, "Source owner lost a material binding")
            slots.append(asset.get_path_name())
        rows.append({"actor": existing.actor_snapshot(actor), "component": component.get_path_name(),
                     "mesh": component.get_dynamic_mesh().get_path_name(), "summary": value["summary"],
                     "materials": slots, "collision": str(component.get_collision_enabled()),
                     "cast_shadow": component.get_editor_property("cast_shadow"),
                     "affects_navigation": component.get_editor_property("can_ever_affect_navigation")})
    require(road_component is not None, "Missing exact saved road component")
    others = sorted((actor.get_path_name(), baseline.numeric_tuple(actor.get_actor_transform()))
                    for actor in actors if not actor.get_actor_label().startswith(ACTOR_PREFIX))
    return saved.normalized({"road_supports": rows, "original_actors": others}, package), road_component


def _source_correspondence(api, plan, road_component):
    mesh = road_component.get_dynamic_mesh()
    require(isinstance(mesh, api.DynamicMesh)
            and (mesh.get_vertex_count(), mesh.get_triangle_count()) == network.ROAD_COUNTS,
            "Edge paint source is outside the exact native road inventory")
    witnesses, digest, worst = {}, hashlib.sha256(b"YACS_EDGE_MARKING_ROAD_WITNESS_V1\0"), 0.0
    cross_signs, normal_signs = {"negative": 0, "positive": 0}, {"negative": 0, "positive": 0}
    for request in plan.source_triangles:
        try:
            value = read_source_triangle(api, mesh, request.triangle_id, request.vertex_ids, request.positions_cm)
        except ValueError as error:
            raise ValueError(f"Edge paint source {request.key}, native tid {request.triangle_id}: {error}") from error
        witnesses[request.key] = value
        cross_signs["positive" if value["ordered_face_cross_z_sign"] > 0 else "negative"] += 1
        normal_signs["positive" if value["native_corner_normal_cross_alignment_sign"] > 0 else "negative"] += 1
        digest.update((request.key[0] + "\0").encode())
        digest.update(struct.pack("<7I", *request.key[1:], request.triangle_id, *request.vertex_ids))
        for actual, expected in zip(value["positions_cm"], request.positions_cm, strict=True):
            worst = max(worst, *(abs(a - b) for a, b in zip(actual, expected, strict=True)))
            digest.update(struct.pack("<3d", *actual))
        for normal in value["corner_normals"]:
            digest.update(struct.pack("<3d", *normal))
    return _render_payloads(plan, witnesses), {
        "source_triangle_count": len(witnesses), "native_source_witness_sha256": digest.hexdigest(),
        "max_source_coordinate_delta_cm": worst, "normal_contract": NORMAL_CONTRACT,
        "normal_orientation_contract": NORMAL_ORIENTATION_CONTRACT,
        "ordered_source_cross_z_counts": cross_signs,
        "native_corner_normal_cross_alignment_counts": normal_signs,
        "source_triangle_ids_inferred": False, "proximity_search_used": False}


RENDER_PROPERTIES = {"can_ever_affect_navigation": False, "generate_overlap_events": False,
                     "enable_complex_collision": False, "visible": True, "hidden_in_game": False}


def _render_flags(api, component):
    require(component.get_collision_enabled() == api.CollisionEnabled.NO_COLLISION
            and component.get_editor_property("cast_shadow") is False
            and component.get_tangents_type() == api.DynamicMeshComponentTangentsMode.AUTO_CALCULATED
            and all(component.get_editor_property(name) is expected for name, expected in RENDER_PROPERTIES.items()),
            "Paint is not visible render-only geometry with collision/shadow/navigation disabled")


def _paint_row(api, actor, payload, instance, package):
    require(isinstance(actor, api.DynamicMeshActor) and actor.get_actor_label() == payload.label,
            "Paint actor identity or native class differs")
    component = actor.get_dynamic_mesh_component()
    require(isinstance(component, api.DynamicMeshComponent)
            and actor.get_editor_property("root_component") == component
            and actor.get_editor_property("hidden") is False, "Paint root component or actor visibility differs")
    state = existing.actor_snapshot(actor)
    require(state["location_cm"] == (0., 0., 0.) and state["rotation_deg"] == (0., 0., 0.)
            and state["scale"] == (1., 1., 1.), "Paint actor moved away from its source surface")
    _render_flags(api, component)
    require(component.get_num_materials() == 1 and component.get_material(0) == instance,
            "Paint does not own exactly its approved material slot")
    mesh = component.get_dynamic_mesh()
    require(isinstance(mesh, api.DynamicMesh)
            and mesh.get_path_name().startswith(component.get_path_name() + "."),
            "Paint component does not own its new native mesh")
    summary = _read_payload(api, mesh, payload)
    return saved.normalized({"label": payload.label, "actor": state, "component": component.get_path_name(),
                             "mesh": mesh.get_path_name(), "source_mesh_sha256": payload.source_mesh_sha256,
                             "material": instance.get_path_name(), **summary}, package)


def _paint_actors(actors, expected_labels):
    rows = [actor for actor in actors if actor.get_actor_label().startswith(ACTOR_PREFIX)]
    labels = [actor.get_actor_label() for actor in rows]
    require(len(labels) == len(set(labels)) and set(labels) == set(expected_labels),
            "Paint actor inventory is missing, duplicated or contains a foreign marking")
    return {actor.get_actor_label(): actor for actor in rows}


def _rollback_created(api, created, before, package):
    """Remove only objects newly owned by this call; never restore source meshes."""
    actors = api.get_editor_subsystem(api.EditorActorSubsystem)
    failures = []
    for actor in reversed(created):
        if not actors.destroy_actor(actor):
            failures.append("actor " + actor.get_path_name())
    for path in reversed(tuple(material.asset_paths().values())):
        if api.EditorAssetLibrary.does_asset_exist(path):
            if not api.EditorAssetLibrary.delete_asset(path) or api.EditorAssetLibrary.does_asset_exist(path):
                failures.append("new material " + path)
    remaining = _actors(api)
    if any(actor.get_actor_label().startswith(ACTOR_PREFIX) for actor in remaining):
        failures.append("new paint actor remains")
    current, _ = _source_state(api, remaining, package)
    if current != before:
        failures.append("original source state differs; no source repair was attempted")
    require(not failures, "Paint creation failed and owned-object cleanup was incomplete: " + "; ".join(failures))


def create(api, plan, asphalt_assets):
    """Create unsaved new M/MI and persistent paint actors after full preflight.

    Call only in the existing exclusive candidate editor session. The outer
    saved consumer must authenticate source files and save a NEW derived map.
    Any failure removes this call's new actors/materials and raises; it never
    modifies the frozen road/supports to make a candidate fit.
    """
    manifest = _check_plan(plan, native=True)
    package, actors = _world(api), _actors(api)
    _paint_actors(actors, [])
    require(all(not api.EditorAssetLibrary.does_asset_exist(path) for path in material.asset_paths().values()),
            "Existing edge marking material assets cannot be replaced")
    before, road_component = _source_state(api, actors, package)
    evidence = native_api_evidence(api)
    evidence["buffer_probe"] = _buffer_probe(api)
    started = time.monotonic()
    payloads, correspondence = _source_correspondence(api, plan, road_component)
    current, _ = _source_state(api, _actors(api), package)
    require(current == before, "Source scene changed during edge marking preflight")
    created = []
    try:
        instance, material_receipt = material.create_material(
            api, material.DESTINATION_ROOT, asphalt_assets, manifest["material_uv_contract"])
        subsystem = api.get_editor_subsystem(api.EditorActorSubsystem)
        rows = []
        for payload in payloads:
            actor = subsystem.spawn_actor_from_class(api.DynamicMeshActor, api.Vector(), api.Rotator(), transient=False)
            if actor is not None:
                created.append(actor)
            require(actor is not None and isinstance(actor, api.DynamicMeshActor), "Native paint actor creation failed")
            actor.set_actor_label(payload.label)
            actor.set_editor_property("hidden", False)
            component = actor.get_dynamic_mesh_component()
            require(isinstance(component, api.DynamicMeshComponent), "New paint component class differs")
            component.set_collision_enabled(api.CollisionEnabled.NO_COLLISION)
            component.set_cast_shadow(False)
            for name, value in RENDER_PROPERTIES.items():
                component.set_editor_property(name, value)
            component.set_tangents_type(api.DynamicMeshComponentTangentsMode.AUTO_CALCULATED)
            _render_flags(api, component)  # No geometry exists until these native flags read back correctly.
            _append_payload(api, component.get_dynamic_mesh(), payload)
            component.set_material(0, instance)
            component.notify_mesh_modified()
            rows.append(_paint_row(api, actor, payload, instance, package))
        observed = _actors(api)
        _paint_actors(observed, [payload.label for payload in payloads])
        after, _ = _source_state(api, observed, package)
        require(after == before, "Paint creation changed original road/support buffers, bindings or actors")
        receipt = {
            "schema_version": 1, "status": "EDGE_MARKINGS_CREATED_REVIEW_PENDING",
            "engine_version": material.ENGINE_VERSION, "plan_sha256": plan.plan_sha256,
            "geometry": manifest, "normal_contract": NORMAL_CONTRACT, "source_correspondence": correspondence,
            "original_source_state": before, "material": material_receipt, "actors": rows,
            "native_api": evidence, "render_flags_verified_before_append": True,
            "caller_saved_package_bytes_required": True, "full_source_buffers_preserved": True,
            "native_surface_correspondence_verified": True, "all_marking_buffers_verified": True,
            "source_files_authenticated_by": "outer_saved_consumer",
            "preflight_and_create_seconds": time.monotonic() - started,
            **dict.fromkeys(FALSE_FLAGS, False),
        }
        require(len(_json(receipt).encode()) <= saved.JSON_LIMIT, "Paint receipt exceeds the saved consumer byte bound")
        return tuple(created), receipt
    except Exception:
        _rollback_created(api, created, before, package)
        raise


def verify_loaded(api, plan, receipt, asphalt_assets):
    """Read-only fresh native verification; never set, spawn, save or repair.

    The caller separately proves a fresh editor process and authenticates the
    saved map/M/MI/source package bytes. This reads every marking buffer and
    checks source correspondence again, including actual source split normals.
    """
    manifest = _check_plan(plan, native=True)
    require(isinstance(receipt, dict) and len(_json(receipt).encode()) <= saved.JSON_LIMIT
            and receipt.get("schema_version") == 1
            and receipt.get("status") == "EDGE_MARKINGS_CREATED_REVIEW_PENDING"
            and receipt.get("engine_version") == material.ENGINE_VERSION
            and receipt.get("plan_sha256") == plan.plan_sha256 and receipt.get("geometry") == manifest
            and receipt.get("normal_contract") == NORMAL_CONTRACT
            and receipt.get("render_flags_verified_before_append") is True
            and receipt.get("caller_saved_package_bytes_required") is True
            and receipt.get("full_source_buffers_preserved") is True
            and receipt.get("native_surface_correspondence_verified") is True
            and receipt.get("all_marking_buffers_verified") is True
            and receipt.get("source_files_authenticated_by") == "outer_saved_consumer"
            and all(receipt.get(flag) is False for flag in FALSE_FLAGS),
            "Fresh paint receipt or source preparation differs")
    package, actors = _world(api), _actors(api)
    originals, road_component = _source_state(api, actors, package)
    require(originals == receipt.get("original_source_state"), "Fresh road/support/source scene differs")
    instance = material.verify_material(api, receipt["material"], asphalt_assets, manifest["material_uv_contract"])
    payloads, correspondence = _source_correspondence(api, plan, road_component)
    require(correspondence == receipt.get("source_correspondence"), "Fresh native road source/corner normals differ")
    by_label = _paint_actors(actors, [payload.label for payload in payloads])
    rows = [_paint_row(api, by_label[payload.label], payload, instance, package) for payload in payloads]
    require(rows == receipt.get("actors"), "Fresh native paint buffers, attributes or bindings differ")
    return {"schema_version": 1, "status": "EDGE_MARKINGS_FRESH_READBACK_VERIFIED",
            "plan_sha256": plan.plan_sha256, "actor_count": len(rows), "normal_contract": NORMAL_CONTRACT,
            "native_source_witness_sha256": correspondence["native_source_witness_sha256"],
            "all_marking_buffers_verified": True, "full_source_buffers_preserved": True,
            "read_only": True, "caller_fresh_process_and_saved_bytes_required": True,
            "owner_visual_pass": False, "performance_pass": False}
