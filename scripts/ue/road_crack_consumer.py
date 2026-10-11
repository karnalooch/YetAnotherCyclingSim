"""Bounded, unsaved local crack overlays with immutable source/paint witnesses.

``prepare`` only reads authenticated pavement bytes/data and clips two named
source windows. The one retained slab resolver supplies native addresses.
``create`` first verifies the existing white paint and every addressed road
face, then imports new pinned crack maps, creates new M/MI and two separate
render-only actors. Its transaction owns only those new objects. Road/support
and existing white-paint buffers, bindings and transforms are never changed.
``verify_loaded`` reads all those states again and performs no repair or save.

Native APIs are deliberately shared with road_edge_marking_consumer: the same
version-pinned source reader, actual transient append probe, complete buffer
reader and render flags. Shared hash domains are named explicitly in receipts;
the crack source mesh has its own hash, and the shared normal-payload hash also
includes the unique crack actor label and that source hash. Shader normal-space
admission still requires the separate neutral WorldNormal render canary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import struct
import time

from scripts.ue import road_crack_geometry as geometry
from scripts.ue import road_crack_material as material
from scripts.ue import road_crack_sources as source_maps
from scripts.ue import road_edge_marking_consumer as edge
from scripts.ue import road_pavement_source_bindings as bindings

ROOT = Path(__file__).resolve().parents[2]
ACTOR_PREFIX = "YACS_ROAD_CRACK_CANARY_"
NORMAL_CONTRACT = edge.NORMAL_CONTRACT
FALSE_FLAGS = ("source_geometry_changed", "source_materials_changed", "existing_paint_changed",
               "collision_enabled", "cast_shadow", "affects_navigation", "physics_authored", "map_saved",
               "normal_space_verified", "owner_visual_pass", "performance_pass")
BUFFER_READER_CONTRACT = "road_edge_marking_consumer_v1_full_position_index_split_normal_uv0_material_readback"


@dataclass(frozen=True)
class PreparedCracks:
    geometry_manifest_json: str
    geometry_contracts_json: str
    meshes: tuple[geometry.CrackMesh, ...]
    source_triangles: tuple[edge.SourceTriangle, ...]
    producer_sha256: str
    producer_size_bytes: int
    plan_sha256: str


def require(value, message):
    if not value:
        raise ValueError(message)


def _label(mesh):
    return ACTOR_PREFIX + mesh.event_id


def _expected_geometry_contract(extent_m, uv_rotation_degrees=0.0):
    return {"channel": 0, "u": "across_road_station", "v": "along_positive_road_station",
            "uv_range": [0.0, 1.0], "extent_cm": extent_m * 100.0, "empty_border_cm": 6.0,
            "surface_offset_cm": 0.1, "surface_offset_axis": "world_positive_z", "actor_scale": [1.0, 1.0, 1.0],
            "normal_contract": NORMAL_CONTRACT, "tangents": "AUTO_CALCULATED", "opacity_mask_clip_value": 0.1,
            "world_normal_canary_required": True, "uv_rotation_degrees": float(uv_rotation_degrees)}


def _contracts(meshes, values):
    require(isinstance(values, dict) and set(values) == {mesh.motif_id for mesh in meshes},
            "Every clipped crack motif needs exactly its authenticated material geometry contract")
    for mesh in meshes:
        contract = values[mesh.motif_id]
        require(isinstance(contract, dict) and contract == _expected_geometry_contract(mesh.extent_m, mesh.uv_rotation_degrees)
                and type(contract.get("channel")) is int
                and contract.get("world_normal_canary_required") is True
                and all(type(v) in (int, float) and math.isfinite(v) for v in (
                    contract["extent_cm"], contract["empty_border_cm"], contract["surface_offset_cm"],
                    contract["opacity_mask_clip_value"], contract["uv_rotation_degrees"],
                    *contract["uv_range"], *contract["actor_scale"])),
                "Crack material extent, UV frame, offset, normals or canary requirement differs from its clipped geometry")
    return json.loads(edge._json(values))


def _plan_hash(manifest_json, contracts_json, meshes, requests, producer_sha, producer_size):
    return edge._digest({"geometry_manifest_json": manifest_json, "geometry_contracts_json": contracts_json,
        "mesh_sha256": [geometry.mesh_sha256(mesh) for mesh in meshes],
        "source_triangles": [[*row.key, row.triangle_id, *row.vertex_ids, row.positions_cm] for row in requests],
        "producer_sha256": producer_sha, "producer_size_bytes": producer_size})


def prepare(source_plan, *, producer_bytes, geometry_contracts, events=geometry.CANARY_EVENTS):
    """Pure source preparation; no native API, proximity lookup or producer execution."""
    pin = bindings.PRODUCER_IDENTITY
    require(type(producer_bytes) is bytes and len(producer_bytes) == pin["size_bytes"]
            and hashlib.sha256(producer_bytes).hexdigest() == pin["sha256"],
            "Crack preparation needs the exact retained pavement producer bytes")
    build = geometry.build_cracks(source_plan, quad_triangles=bindings.QUAD_TRIANGLES, events=events)
    contracts = _contracts(build.meshes, geometry_contracts)
    needed = geometry.needed_faces(build)
    resolved = bindings.prepare_bindings(source_plan, producer_bytes=producer_bytes, needed_faces=needed)
    require(resolved["quad_triangles"] == bindings.QUAD_TRIANGLES
            and isinstance(resolved["triangle_bindings"], tuple) and len(resolved["triangle_bindings"]) == len(needed),
            "Crack native source binding inventory differs from its clipped source faces")
    owners = {owner["support_label"]: owner for owner in source_plan["owners"] if owner["material_target"]}
    requests, seen, seen_tids, vertex_owners = [], set(), set(), {}
    for row in resolved["triangle_bindings"]:
        require(isinstance(row, tuple) and len(row) == 8 and isinstance(row[0], str)
                and all(type(value) is int and value >= 0 for value in row[1:]),
                "Crack resolver returned an invalid explicit source/native address")
        key, tid, vids = tuple(row[:4]), row[4], tuple(row[5:])
        require(key in needed and key not in seen and tid not in seen_tids
                and tid < edge.network.ROAD_COUNTS[1] and len(set(vids)) == 3
                and all(vid < edge.network.ROAD_COUNTS[0] for vid in vids),
                "Crack source addresses are duplicated, outside its faces or outside the accepted road")
        label, section, cell, slot = key
        points = []
        for vid, index in zip(vids, bindings.QUAD_TRIANGLES[slot], strict=True):
            point_key = (label, section + geometry.CORNER_OFFSETS[index][0], cell + geometry.CORNER_OFFSETS[index][1])
            require(vid not in vertex_owners or vertex_owners[vid] == point_key,
                    "Different crack source vertices claim one native road vertex")
            vertex_owners[vid] = point_key
            points.append(tuple(float(value) * 100.0
                                for value in owners[label]["pavement_sections_m"][point_key[1]][point_key[2]]))
        requests.append(edge.SourceTriangle(key, tid, vids, tuple(points)))
        seen.add(key)
        seen_tids.add(tid)
    require(seen == set(needed), "Every clipped crack source face needs one exact native address")
    requests = tuple(sorted(requests, key=lambda request: request.key))
    manifest_json, contracts_json = edge._json(build.manifest), edge._json(contracts)
    digest = _plan_hash(manifest_json, contracts_json, build.meshes, requests, pin["sha256"], pin["size_bytes"])
    return PreparedCracks(manifest_json, contracts_json, build.meshes, requests, pin["sha256"], pin["size_bytes"], digest)


def _check_plan(plan, *, native=False):
    pin = bindings.PRODUCER_IDENTITY
    require(isinstance(plan, PreparedCracks) and plan.producer_sha256 == pin["sha256"]
            and plan.producer_size_bytes == pin["size_bytes"]
            and plan.plan_sha256 == _plan_hash(plan.geometry_manifest_json, plan.geometry_contracts_json, plan.meshes,
                plan.source_triangles, plan.producer_sha256, plan.producer_size_bytes),
            "Crack preparation changed or lacks its authenticated pavement producer")
    manifest, contracts = json.loads(plan.geometry_manifest_json), json.loads(plan.geometry_contracts_json)
    _contracts(plan.meshes, contracts)
    if native:
        counts = manifest["counts"]
        require(counts["source_owner_count"] == edge.sources.OWNER_COUNT
                and counts["pavement_owner_count"] == edge.sources.NETWORK_COUNT + 1
                and counts["excluded_parapet_count"] == 1
                and counts["source_section_count"] == edge.sources.PROFILE_PAVEMENT_ROW_COUNT
                and counts["mesh_count"] == 2
                and [value["event"] for value in manifest["events"]]
                == json.loads(edge._json([asdict(event) for event in geometry.CANARY_EVENTS])),
                "Native crack placement requires only the two named canaries on the complete authenticated pavement")
    return manifest, contracts


def _source_correspondence(api, plan, road_component):
    mesh = road_component.get_dynamic_mesh()
    require(isinstance(mesh, api.DynamicMesh)
            and (mesh.get_vertex_count(), mesh.get_triangle_count()) == edge.network.ROAD_COUNTS,
            "Crack source is not the exact native road mesh")
    witnesses, digest = {}, hashlib.sha256(b"YACS_LOCAL_ROAD_CRACK_SOURCE_WITNESS_V1\0")
    worst, cross_signs, normal_signs = 0.0, {"negative": 0, "positive": 0}, {"negative": 0, "positive": 0}
    for request in plan.source_triangles:
        try:
            witness = edge.read_source_triangle(api, mesh, request.triangle_id, request.vertex_ids, request.positions_cm)
        except ValueError as error:
            raise ValueError(f"Crack source {request.key}, native tid {request.triangle_id}: {error}") from error
        witnesses[request.key] = witness
        cross_signs["positive" if witness["ordered_face_cross_z_sign"] > 0 else "negative"] += 1
        normal_signs["positive" if witness["native_corner_normal_cross_alignment_sign"] > 0 else "negative"] += 1
        digest.update((request.key[0] + "\0").encode())
        digest.update(struct.pack("<7I", *request.key[1:], request.triangle_id, *request.vertex_ids))
        for actual, expected in zip(witness["positions_cm"], request.positions_cm, strict=True):
            worst = max(worst, *(abs(a - b) for a, b in zip(actual, expected, strict=True)))
            digest.update(struct.pack("<3d", *actual))
        for normal in witness["corner_normals"]:
            digest.update(struct.pack("<3d", *normal))
    payloads = []
    for source_mesh in plan.meshes:
        normals = [None] * len(source_mesh.positions_m)
        for fragment in source_mesh.fragments:
            actual = witnesses[(source_mesh.owner_label, *fragment.source_triangle)]["corner_normals"]
            for vid in range(fragment.first_vertex, fragment.first_vertex + fragment.vertex_count):
                weights = source_mesh.barycentric_weights[vid]
                normals[vid] = edge._unit(tuple(math.fsum(weights[corner] * actual[corner][axis] for corner in range(3))
                                                for axis in range(3)))
        require(all(normal is not None for normal in normals), "Crack vertex has no authenticated native corner normal")
        payloads.append(edge.RenderPayload(_label(source_mesh), geometry.mesh_sha256(source_mesh),
            tuple(tuple(value * 100.0 for value in point) for point in source_mesh.positions_m),
            source_mesh.triangles, tuple(normals), source_mesh.uv0))
    return tuple(payloads), {"source_triangle_count": len(witnesses), "native_source_witness_sha256": digest.hexdigest(),
        "max_source_coordinate_delta_cm": worst, "normal_contract": NORMAL_CONTRACT,
        "normal_orientation_contract": edge.NORMAL_ORIENTATION_CONTRACT, "ordered_source_cross_z_counts": cross_signs,
        "native_corner_normal_cross_alignment_counts": normal_signs, "native_addresses": "authenticated_retained_slab_resolver",
        "proximity_search_used": False, "source_normal_sign_converted": False}


def _white_readback(api, white_plan, white_receipt, asphalt_assets, actors, package, road):
    """Replay the existing white buffer reader inside the explicit aggregate.

    The C++ road/support inspector deliberately rejects paint components. Use
    the white lane's native reader for every paint vertex/face/corner instead;
    do not widen that inspector's source-owner allowlist.
    """
    manifest = edge._check_plan(white_plan, native=True)
    require(isinstance(white_receipt, dict) and len(edge._json(white_receipt).encode()) <= edge.saved.JSON_LIMIT
            and white_receipt.get("schema_version") == 1
            and white_receipt.get("status") == "EDGE_MARKINGS_CREATED_REVIEW_PENDING"
            and white_receipt.get("engine_version") == edge.material.ENGINE_VERSION
            and white_receipt.get("plan_sha256") == white_plan.plan_sha256
            and white_receipt.get("geometry") == manifest
            and white_receipt.get("normal_contract") == edge.NORMAL_CONTRACT
            and white_receipt.get("source_files_authenticated_by") == "outer_saved_consumer"
            and all(white_receipt.get(key) is True for key in (
                "render_flags_verified_before_append", "caller_saved_package_bytes_required",
                "full_source_buffers_preserved", "native_surface_correspondence_verified", "all_marking_buffers_verified"))
            and all(white_receipt.get(flag) is False for flag in edge.FALSE_FLAGS),
            "Aggregate white receipt or source preparation differs")
    instance = edge.material.verify_material(api, white_receipt["material"], asphalt_assets, manifest["material_uv_contract"])
    payloads, correspondence = edge._source_correspondence(api, white_plan, road)
    require(correspondence == white_receipt.get("source_correspondence"),
            "Aggregate white source faces/corner normals differ")
    by_label = edge._paint_actors(actors, [payload.label for payload in payloads])
    rows = [edge._paint_row(api, by_label[payload.label], payload, instance, package) for payload in payloads]
    require(rows == white_receipt.get("actors"), "Aggregate white native buffers, bindings or flags differ")
    readback = {"schema_version": 1, "status": "EDGE_MARKINGS_FRESH_READBACK_VERIFIED",
        "plan_sha256": white_plan.plan_sha256, "actor_count": len(rows), "normal_contract": edge.NORMAL_CONTRACT,
        "native_source_witness_sha256": correspondence["native_source_witness_sha256"],
        "all_marking_buffers_verified": True, "full_source_buffers_preserved": True,
        "read_only": True, "caller_fresh_process_and_saved_bytes_required": True,
        "aggregate_owner": "local_crack_canary", "owner_visual_pass": False, "performance_pass": False}
    return rows, correspondence, readback


def _original_actor_inventory(actors):
    return sorted((actor.get_path_name(), actor.get_actor_label(), edge.baseline.numeric_tuple(actor.get_actor_transform()))
                  for actor in actors if not actor.get_actor_label().startswith(ACTOR_PREFIX))


def _original_state(api, actors, package, *, white_plan, white_receipt, asphalt_assets):
    originals = [actor for actor in actors if not actor.get_actor_label().startswith(ACTOR_PREFIX)]
    state, road = edge._source_state(api, originals, package)
    owners = [actor for actor in originals if actor.get_actor_label() == "YACS_PERSIST_ROAD"]
    require(len(owners) == 1 and owners[0].get_editor_property("root_component") == road,
            "Crack source road is not the explicitly owned root component")
    transform = edge.existing.actor_snapshot(owners[0])
    require(transform["location_cm"] == (0., 0., 0.) and transform["rotation_deg"] == (0., 0., 0.)
            and transform["scale"] == (1., 1., 1.),
            "Crack source local positions require the accepted identity road transform")
    require(state == white_receipt.get("original_source_state"), "Aggregate original road/support/source scene differs")
    paint_rows, correspondence, readback = _white_readback(
        api, white_plan, white_receipt, asphalt_assets, actors, package, road)
    actor_inventory = edge.saved.normalized(_original_actor_inventory(actors), package)
    # Hash every field of the actual full reads. Those large exact source and
    # paint rows already live in the separately byte-pinned white receipt; a
    # duplicate would consume the saved manifest's 4 MiB bound needlessly.
    snapshot = {"schema_version": 1, "original_source_state_sha256": edge._digest(state),
        "white_actor_rows_sha256": edge._digest(paint_rows), "white_actor_count": len(paint_rows),
        "white_source_correspondence_sha256": edge._digest(correspondence),
        "all_original_actor_inventory_sha256": edge._digest(actor_inventory), "all_original_actor_count": len(actor_inventory),
        "complete_native_reads_verified": True, "white_receipt_sha256": edge._digest(white_receipt)}
    return snapshot, road, readback


def _verify_white_contract(plan, white_plan, white_receipt):
    manifest, _ = _check_plan(plan)
    white = edge._check_plan(white_plan, native=True)
    appearance = white["appearance"]
    require(white["source_identity_sha256"] == manifest["source_identity_sha256"]
            and appearance["setback_m"] == geometry.PAINT_SETBACK_M
            and appearance["width_m"] == geometry.PAINT_WIDTH_M
            and appearance["surface_offset_m"] == geometry.SURFACE_OFFSET_M
            and appearance["surface_offset_axis"] == "world_positive_z"
            and white_receipt.get("plan_sha256") == white_plan.plan_sha256,
            "Crack exclusion band differs from the actual saved white-paint/source contract")


def _crack_actors(actors, labels):
    rows = [actor for actor in actors if actor.get_actor_label().startswith(ACTOR_PREFIX)]
    actual = [actor.get_actor_label() for actor in rows]
    require(len(actual) == len(set(actual)) and set(actual) == set(labels),
            "Crack actor inventory is missing, duplicated or contains a foreign canary")
    return {actor.get_actor_label(): actor for actor in rows}


def _owned_asset_paths(source):
    textures = source_maps.asset_paths(source)
    materials = material.asset_paths(source)
    require(set(textures["textures"]) == set(materials) == set(source["selected_motifs"]),
            "Crack source/material asset inventory differs")
    masters = {materials[motif]["master"] for motif in source["selected_motifs"]}
    require(len(masters) == 1, "Crack canaries require the one shared bounded master")
    # Texture imports first, then the shared master and its instances. Reverse
    # cleanup releases every material reference before deleting new textures.
    paths = tuple(path for motif in source["selected_motifs"]
                  for path in textures["textures"][motif].values()) + tuple(masters) + tuple(
                      materials[motif]["instance"] for motif in source["selected_motifs"])
    require(len(paths) == len(set(paths)) == 5 * len(source["selected_motifs"]) + 1
            and all(isinstance(path, str) and path.startswith(source_maps.DESTINATION_ROOT + "/") for path in paths),
            "Crack transaction asset paths escape their bounded new namespace")
    return paths


def _rollback(api, actors, asset_paths, before, package, *, white_plan, white_receipt, asphalt_assets):
    failures, subsystem = [], api.get_editor_subsystem(api.EditorActorSubsystem)
    for actor in reversed(actors):
        if not subsystem.destroy_actor(actor):
            failures.append("actor " + actor.get_path_name())
    for path in reversed(asset_paths):
        if api.EditorAssetLibrary.does_asset_exist(path):
            if not api.EditorAssetLibrary.delete_asset(path) or api.EditorAssetLibrary.does_asset_exist(path):
                failures.append("new asset " + path)
    current = edge._actors(api)
    if any(actor.get_actor_label().startswith(ACTOR_PREFIX) for actor in current):
        failures.append("new crack actor remains")
    state, _, _ = _original_state(api, current, package, white_plan=white_plan,
                                  white_receipt=white_receipt, asphalt_assets=asphalt_assets)
    if state != before:
        failures.append("original road/support/white paint differs; no source repair attempted")
    require(not failures, "Crack owned-object cleanup was incomplete: " + "; ".join(failures))


def create(api, plan, source_root, pins, asphalt_assets, *, white_plan, white_receipt, source_repo_root=ROOT):
    """Create only the new canary assets/actors; caller owns saving a new derived map."""
    manifest, contracts = _check_plan(plan, native=True)
    _verify_white_contract(plan, white_plan, white_receipt)
    package, actors = edge._world(api), edge._actors(api)
    _crack_actors(actors, [])
    before, road, _ = _original_state(api, actors, package, white_plan=white_plan,
                                      white_receipt=white_receipt, asphalt_assets=asphalt_assets)
    source = source_maps.load_sources(source_root, pins, source_maps.CANARY_MOTIFS, source_repo_root=source_repo_root)
    require(set(source["selected_motifs"]) == set(contracts)
            and {motif: material.geometry_contract(source["motifs"][motif],
                    uv_rotation_degrees=contracts[motif]["uv_rotation_degrees"])
                 for motif in source["selected_motifs"]} == contracts,
            "Pinned Forge motifs do not match the source-clipped crack geometry")
    paths = _owned_asset_paths(source)
    require(all(not api.EditorAssetLibrary.does_asset_exist(path) for path in paths),
            "Existing crack assets cannot be replaced or reused as unverified candidates")
    evidence = edge.native_api_evidence(api)
    evidence["buffer_probe"] = edge._buffer_probe(api)
    payloads, correspondence = _source_correspondence(api, plan, road)
    observed = edge._actors(api)
    current, _ = edge._source_state(api, observed, package)
    require(edge._digest(current) == before["original_source_state_sha256"]
            and edge._digest(edge.saved.normalized(_original_actor_inventory(observed), package))
            == before["all_original_actor_inventory_sha256"], "Source scene changed during crack preflight")
    created, started = [], time.monotonic()
    try:
        _, import_receipt = source_maps.import_textures(api, source_root, pins, source_maps.CANARY_MOTIFS,
                                                        source_repo_root=source_repo_root)
        instances, material_receipt = material.create_materials(api, source_root, pins, import_receipt,
            asphalt_assets, contracts, source_repo_root=source_repo_root)
        require(set(instances) == set(contracts) and material_receipt.get("normal_space_verified") is False
                and material_receipt.get("world_normal_canary_required") is True,
                "Crack material omitted the mandatory native normal-space canary")
        rows, subsystem = [], api.get_editor_subsystem(api.EditorActorSubsystem)
        for source_mesh, payload in zip(plan.meshes, payloads, strict=True):
            actor = subsystem.spawn_actor_from_class(api.DynamicMeshActor, api.Vector(), api.Rotator(), transient=False)
            if actor is not None:
                created.append(actor)
            require(actor is not None and isinstance(actor, api.DynamicMeshActor), "Native crack actor creation failed")
            actor.set_actor_label(payload.label)
            actor.set_editor_property("hidden", False)
            component = actor.get_dynamic_mesh_component()
            require(isinstance(component, api.DynamicMeshComponent), "New crack component class differs")
            component.set_collision_enabled(api.CollisionEnabled.NO_COLLISION)
            component.set_cast_shadow(False)
            for name, value in edge.RENDER_PROPERTIES.items():
                component.set_editor_property(name, value)
            component.set_tangents_type(api.DynamicMeshComponentTangentsMode.AUTO_CALCULATED)
            edge._render_flags(api, component)
            edge._append_payload(api, component.get_dynamic_mesh(), payload)
            instance = instances[source_mesh.motif_id]
            component.set_material(0, instance)
            component.notify_mesh_modified()
            rows.append({"motif_id": source_mesh.motif_id, **edge._paint_row(api, actor, payload, instance, package)})
        current = edge._actors(api)
        _crack_actors(current, [payload.label for payload in payloads])
        after, _, _ = _original_state(api, current, package, white_plan=white_plan,
                                      white_receipt=white_receipt, asphalt_assets=asphalt_assets)
        require(after == before, "Crack creation changed original road/support/white-paint buffers or bindings")
        receipt = {"schema_version": 1, "status": "LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING",
            "engine_version": edge.material.ENGINE_VERSION, "plan_sha256": plan.plan_sha256,
            "geometry": manifest, "geometry_contracts": contracts, "normal_contract": NORMAL_CONTRACT,
            "source_correspondence": correspondence, "original_scene_state": before,
            "white_plan_sha256": white_plan.plan_sha256, "white_receipt_sha256": edge._digest(white_receipt),
            "imports": import_receipt, "material": material_receipt, "actors": rows, "owned_asset_paths": list(paths),
            "native_api": evidence, "shared_buffer_reader_contract": BUFFER_READER_CONTRACT,
            "shared_buffer_hash_domain": "YACS_EDGE_MARKING_NATIVE_BUFFER_V1",
            "shared_render_normal_payload_hash_domain": "YACS_EDGE_MARKING_NATIVE_NORMAL_PAYLOAD_V1",
            "full_source_and_existing_paint_buffers_preserved": True, "all_crack_buffers_verified": True,
            "native_surface_correspondence_verified": True, "render_flags_verified_before_append": True,
            "world_normal_canary_required": True, "caller_saved_package_bytes_required": True,
            "source_files_authenticated_by": "outer_saved_consumer_and_pinned_crack_source_loader",
            "create_seconds": time.monotonic() - started, **dict.fromkeys(FALSE_FLAGS, False)}
        require(len(edge._json(receipt).encode()) <= edge.saved.JSON_LIMIT, "Crack receipt exceeds its saved consumer byte bound")
        return tuple(created), receipt
    except Exception:
        _rollback(api, created, paths, before, package, white_plan=white_plan,
                  white_receipt=white_receipt, asphalt_assets=asphalt_assets)
        raise


def verify_loaded(api, plan, receipt, source_root, pins, asphalt_assets, *, white_plan, white_receipt, source_repo_root=ROOT):
    """Read-only saved native readback; process/file/WorldNormal proof remains external."""
    manifest, contracts = _check_plan(plan, native=True)
    _verify_white_contract(plan, white_plan, white_receipt)
    require(isinstance(receipt, dict) and len(edge._json(receipt).encode()) <= edge.saved.JSON_LIMIT
            and receipt.get("schema_version") == 1 and receipt.get("status") == "LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING"
            and receipt.get("engine_version") == edge.material.ENGINE_VERSION
            and receipt.get("plan_sha256") == plan.plan_sha256 and receipt.get("geometry") == manifest
            and receipt.get("geometry_contracts") == contracts and receipt.get("normal_contract") == NORMAL_CONTRACT
            and receipt.get("white_plan_sha256") == white_plan.plan_sha256
            and receipt.get("white_receipt_sha256") == edge._digest(white_receipt)
            and receipt.get("shared_buffer_reader_contract") == BUFFER_READER_CONTRACT
            and receipt.get("shared_buffer_hash_domain") == "YACS_EDGE_MARKING_NATIVE_BUFFER_V1"
            and receipt.get("shared_render_normal_payload_hash_domain") == "YACS_EDGE_MARKING_NATIVE_NORMAL_PAYLOAD_V1"
            and receipt.get("source_files_authenticated_by") == "outer_saved_consumer_and_pinned_crack_source_loader"
            and all(receipt.get(key) is True for key in (
                "full_source_and_existing_paint_buffers_preserved", "all_crack_buffers_verified",
                "native_surface_correspondence_verified", "render_flags_verified_before_append",
                "world_normal_canary_required", "caller_saved_package_bytes_required"))
            and all(receipt.get(key) is False for key in FALSE_FLAGS), "Fresh crack receipt or admission contract differs")
    package, actors = edge._world(api), edge._actors(api)
    originals, road, white_readback = _original_state(api, actors, package, white_plan=white_plan,
        white_receipt=white_receipt, asphalt_assets=asphalt_assets)
    require(originals == receipt.get("original_scene_state"), "Fresh original road/support/white-paint scene differs")
    # Material verification includes the complete source/import verification;
    # do not decode/hash the same selected maps a redundant second time here.
    instances = material.verify_materials(api, source_root, pins, receipt["imports"], receipt["material"],
                                          asphalt_assets, contracts, source_repo_root=source_repo_root)
    require(receipt.get("owned_asset_paths") == list(_owned_asset_paths(receipt["imports"]["sources"])),
            "Fresh crack asset ownership inventory differs")
    payloads, correspondence = _source_correspondence(api, plan, road)
    require(correspondence == receipt.get("source_correspondence"), "Fresh crack source positions/indices/corner normals differ")
    by_label = _crack_actors(actors, [payload.label for payload in payloads])
    rows = [{"motif_id": source_mesh.motif_id,
             **edge._paint_row(api, by_label[payload.label], payload, instances[source_mesh.motif_id], package)}
            for source_mesh, payload in zip(plan.meshes, payloads, strict=True)]
    require(rows == receipt.get("actors"), "Fresh crack native buffers, flags or bindings differ")
    return {"schema_version": 1, "status": "LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING",
            "plan_sha256": plan.plan_sha256, "actor_count": len(rows), "normal_contract": NORMAL_CONTRACT,
            "native_source_witness_sha256": correspondence["native_source_witness_sha256"],
            "full_source_and_existing_paint_buffers_preserved": True, "all_crack_buffers_verified": True,
            "read_only": True, "caller_fresh_process_and_saved_bytes_required": True,
            "edge_markings": white_readback,
            "world_normal_canary_required": True, "normal_space_verified": False,
            "owner_visual_pass": False, "performance_pass": False}
