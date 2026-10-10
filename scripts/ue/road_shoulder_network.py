"""Material-only #364 assignment with source ownership for all 186 supports.

One read-only C++ call hashes complete native buffers; only the first ownership
pass returns triangle witnesses. Every later pass compares those exact hashes.
The existing Geometry Script setter changes only source-proved outer top IDs.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import read_road_material_baseline as baseline
from scripts.ue import road_shoulder_sources as sources
from scripts.ue import road_shoulder_window as legacy

ROOT = Path(__file__).resolve().parents[2]
HASH_FORMAT = "blake3-256-le-i32-f64-corners-v1"
MAX_JSON_CHARS = 48 * 1024 * 1024
MAX_SUPPORT_VERTICES = 85000
MAX_SUPPORT_TRIANGLES = 150000
MAX_TOTAL_VERTICES = 700000
MAX_TOTAL_TRIANGLES = 1100000
ROAD_COUNTS = (856250, 1711760)
MAPS = (
    "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview",
    "/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview",
)
MATERIAL_ROOT = "/Game/Generated/YACS/RoadAsphaltConsumer/"
PRESERVED_FIELDS = (
    "vertex_count", "triangle_count", "uv_set_count",
    "positions_indices_blake3", "triangle_corner_normals_uv_blake3",
)
OWNER_SUMMARY_FIELDS = ("support_label", "window_id", "kind", "material_target", "selected_triangle_count")
INSPECTION_FILES = (
    "Source/YetAnotherCyclingSimEditor/Public/Diagnostics/YacsRoadMaterialInspectionLibrary.h",
    "Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsRoadMaterialInspectionLibrary.cpp",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def integer(value, minimum=0, maximum=MAX_SUPPORT_TRIANGLES):
    require(type(value) is int and minimum <= value <= maximum,
            "Native inspection integer is missing or outside its budget")
    return value


def inspect_mesh(api, component, witness_triangle_count=0):
    """Validate a native read-only support or exact accepted-road snapshot."""
    integer(witness_triangle_count)
    raw = api.YacsRoadMaterialInspectionLibrary.inspect_mesh(component, witness_triangle_count)
    require(isinstance(raw, str) and 0 < len(raw) <= MAX_JSON_CHARS,
            "Native road-material inspection exceeded the serialization budget")
    value = json.loads(raw)
    require(isinstance(value, dict), "Native road-material inspection is not an object")
    require(type(value.get("schema_version")) is int and value.get("schema_version") == 2
            and value.get("status") == "ROAD_MATERIAL_MESH_INSPECTED"
            and value.get("hash_format") == HASH_FORMAT
            and value.get("geometry_mutated") is False
            and value.get("component_path") == component.get_path_name()
            and value.get("mesh_path") == component.get_dynamic_mesh().get_path_name()
            and value.get("actor_label") == component.get_owner().get_actor_label()
            and value.get("map_package") in MAPS,
            "Native road-material inspection failed: " + str(value.get("error")))
    label = value.get("actor_label")
    road = label == "YACS_PERSIST_ROAD"
    require(road or (isinstance(label, str)
            and re.fullmatch(r"YACS_PERSIST_SUPPORT_[0-9]{3}", label)
            and int(label[-3:]) < sources.OWNER_COUNT), "Unknown native material owner")
    summary = value.get("summary", {})
    require(isinstance(summary, dict)
            and set(summary) == {*PRESERVED_FIELDS, "material_ids_blake3"},
            "Native mesh summary schema differs")
    vertices = integer(summary["vertex_count"], 1, ROAD_COUNTS[0] if road else MAX_SUPPORT_VERTICES)
    triangles = integer(summary["triangle_count"], 1, ROAD_COUNTS[1] if road else MAX_SUPPORT_TRIANGLES)
    integer(summary["uv_set_count"], 0, 4)
    require(not road or ((vertices, triangles) == ROAD_COUNTS and witness_triangle_count == 0),
            "Road buffer read is outside the exact frozen inventory")
    for key in ("positions_indices_blake3", "triangle_corner_normals_uv_blake3", "material_ids_blake3"):
        require(isinstance(summary[key], str) and re.fullmatch(r"[0-9a-f]{64}", summary[key]),
                "Missing complete native BLAKE3-256 digest")
    ids = value.get("material_ids")
    require(value.get("material_ids_included") is (not road) and isinstance(ids, list)
            and len(ids) == (0 if road else triangles), "Native material-ID inventory differs")
    for material_id in ids:
        integer(material_id, 0, 31)
    witnesses = value.get("witness_triangles")
    require(type(value.get("witness_triangle_count")) is int
            and value.get("witness_triangle_count") == witness_triangle_count
            and isinstance(witnesses, list) and len(witnesses) == witness_triangle_count
            and witness_triangle_count <= triangles, "Native source witness count differs")
    for tid, row in enumerate(witnesses):
        require(isinstance(row, list) and len(row) == 13 and row[0] == tid,
                "Native source witnesses are incomplete or reordered")
        for index in row[:4]:
            integer(index, 0, max(vertices, triangles) - 1)
        require(len(set(row[1:4])) == 3 and all(v < vertices for v in row[1:4])
                and all(type(v) in (int, float) and math.isfinite(v) for v in row[4:]),
                "Native source witness contains invalid indices or positions")
    return value


def native_api_evidence(api, component):
    evidence = legacy.native_api_evidence(api, component)
    method = api.YacsRoadMaterialInspectionLibrary.inspect_mesh
    doc = str(getattr(method, "__doc__", "") or "")
    require(callable(method) and all(p in doc for p in ("component", "witness_triangle_count")),
            "Installed native inspection signature differs")
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    header = session._safe_path(engine, "Source/Runtime/Core/Public/Hash/Blake3.h")
    text = header.read_text(encoding="utf-8-sig")
    require(all(symbol in text for symbol in ("FBlake3", "Update", "Finalize", "GetBytes")),
            "Pinned engine BLAKE3 API source is incomplete")
    evidence.update(
        bulk_hash_format=HASH_FORMAT,
        inspection_signature={"signature": doc[:2048], "sha256": hashlib.sha256(doc.encode()).hexdigest()},
        blake3_header=session._identity(header, 1024 * 1024),
        inspection_sources={path: session._identity(session._safe_path(ROOT, path), 1024 * 1024)
                            for path in INSPECTION_FILES},
        geometry_authoring_api_added=False,
    )
    return evidence


def owner_components(api, actors, source_plan):
    owners = source_plan.get("owners", [])
    require(isinstance(owners, list) and len(owners) == sources.OWNER_COUNT
            and [o["support_label"] for o in owners]
            == [f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(sources.OWNER_COUNT)]
            and sum(o["material_target"] is True for o in owners) == sources.OWNER_COUNT - 1
            and sum(o["kind"] == "parapet" and o["material_target"] is False for o in owners) == 1,
            "Authenticated support source plan is incomplete or reordered")
    native = {actor.get_actor_label(): actor for actor in baseline.road_support_actors(actors)[1:]}
    require(set(native) == {o["support_label"] for o in owners}, "Native source owner inventory differs")
    result = []
    for owner in owners:
        actor = native[owner["support_label"]]
        state = legacy.actor_snapshot(actor)
        require(state["location_cm"] == (0.0, 0.0, 0.0)
                and state["rotation_deg"] == (0.0, 0.0, 0.0)
                and state["scale"] == (1.0, 1.0, 1.0), "Transformed frozen support is not admitted")
        result.append((owner, actor.get_dynamic_mesh_component()))
    return result


def verify_ownership(snapshot, owner, identity):
    """Authenticate every oriented source top triangle, including outer strips."""
    require(snapshot["actor_label"] == owner["support_label"], "Native owner label changed")
    witnesses = snapshot["witness_triangles"]
    require(len(witnesses) == identity["expected_witness_triangle_count"],
            "Source ownership lacks complete native witnesses")
    worst = 0.0
    for (tid, expected), row in zip(sources.iter_expected_triangles(owner), witnesses, strict=True):
        require(row[0] == tid, "Source/native triangle IDs differ")
        if owner["kind"] == "parapet":
            face = owner["parapet_faces"][tid]
        else:
            strip, side = divmod(tid, 2)
            section, column = divmod(strip, 26)
            a = section * 27 + column
            face = (a, a + 1, a + 27) if side == 0 else (a + 1, a + 28, a + 27)
        require(tuple(row[1:4]) == tuple(face), "Source top connectivity changed")
        actual = (row[4:7], row[7:10], row[10:13])
        worst = max(worst, *(abs(float(a) - float(b)) for p, q in zip(actual, expected, strict=True)
                             for a, b in zip(p, q, strict=True)))
    require(worst <= 0.0001, "Native support no longer matches immutable source coordinates")
    if owner["kind"] == "parapet":
        require(snapshot["summary"]["triangle_count"] == owner["expected_triangle_count"],
                "Excluded parapet source inventory differs")
    return {"oriented_triangles_compared": len(witnesses),
            "max_source_coordinate_delta_cm": worst,
            "count_only_or_label_only_ownership": False}


def verify_slots(component, owner, instance=None):
    expected = 2 if instance is not None and owner["material_target"] else 1
    require(component.get_num_materials() == expected, "Original or derived material slot count differs")
    old = component.get_material(0)
    require(old is not None and old.get_path_name() == owner["original_material_path"],
            "Literal original support/wall material changed")
    if expected == 2:
        material = component.get_material(1)
        require(material is not None and material.get_path_name() == instance,
                "Shoulder gravel slot differs")
    return old


def verify_delta(before, after, owner, *, assigned):
    require(all(before[field] == after["summary"][field] for field in PRESERVED_FIELDS),
            "Material assignment changed full positions, indices, normals or UV buffers")
    selected = set(owner["selected_triangle_ids"]) if assigned and owner["material_target"] else set()
    require(len(selected) <= after["summary"]["triangle_count"]
            and all(type(tid) is int and 0 <= tid < min(owner["top_triangle_count"],
                        after["summary"]["triangle_count"]) for tid in selected),
            "Material selection escaped the source top domain")
    require(all(value == (1 if tid in selected else 0)
                for tid, value in enumerate(after["material_ids"])),
            "Unselected wall/interior/parapet material ID changed")
    if not selected:
        require(after["summary"] == before, "Complete original mesh did not survive rollback/exclusion")


def set_owner_ids(api, item, material_id):
    owner, component = item["owner"], item["component"]
    require(owner["material_target"] is True and material_id in (0, 1)
            and sources.owner_identity(owner) == item["source"], "Unapproved material selection changed")
    mesh = component.get_dynamic_mesh()
    for tid in owner["selected_triangle_ids"]:
        result = api.GeometryScript_Materials.set_triangle_material_id(
            mesh, tid, material_id, defer_change_notifications=True)
        require(len(result) == 2 and result[0] == mesh and result[1] is True,
                "Native source-owned material setter rejected triangle " + str(tid))
    component.notify_mesh_modified()


def verify_states(api, state, *, assigned):
    summaries = []
    for item in state["items"]:
        snapshot = inspect_mesh(api, item["component"])
        require(snapshot["actor_label"] == item["owner"]["support_label"], "Material owner changed during proof")
        verify_slots(item["component"], item["owner"], state["instance_path"] if assigned else None)
        verify_delta(item["before_mesh"], snapshot, item["owner"], assigned=assigned)
        summaries.append(snapshot["summary"])
    return summaries


def rollback(api, state):
    """Restore every attempted owner, then prove all 186 full original buffers."""
    errors = []
    for item in reversed(state["attempted"]):
        try:
            set_owner_ids(api, item, 0)
        except Exception as exc:
            errors.append(item["owner"]["support_label"] + " IDs: " + str(exc))
        try:
            item["component"].configure_material_set([item["old_material"]], delete_extra_slots=True)
        except Exception as exc:
            errors.append(item["owner"]["support_label"] + " slots: " + str(exc))
    try:
        summaries = verify_states(api, state, assigned=False)
    except Exception as exc:
        errors.append("rollback readback: " + str(exc))
    require(not errors, "Full-network rollback failed: " + "; ".join(errors))
    state["attempted"].clear()
    return {"status": "SHOULDER_NETWORK_ROLLBACK_VERIFIED", "support_count": len(summaries),
            "aggregate_meshes_sha256": digest(summaries)}


def apply_all(api, state, instance):
    for item in state["items"]:
        if item["owner"]["material_target"]:
            state["attempted"].append(item)
            item["component"].configure_material_set([item["old_material"], instance], delete_extra_slots=True)
            set_owner_ids(api, item, 1)


def prepare(api, actors, source_plan, instance, material_receipt):
    """Authenticate the whole network, prove rollback, then apply one shared MI.

    Return (serializable receipt, rollback state). The caller saves the map and
    calls rollback on a later pre-save failure. This helper never saves assets.
    """
    instance_path = material_receipt["assets"]["instance"]
    require(instance.get_path_name() == instance_path and instance_path.startswith(MATERIAL_ROOT),
            "Shared gravel material escaped the derived consumer")
    pairs = owner_components(api, actors, source_plan)
    api_receipt = native_api_evidence(api, pairs[0][1])
    state = {"items": [], "attempted": [], "instance_path": instance_path}
    total_vertices = total_triangles = 0
    for owner, component in pairs:
        old = verify_slots(component, owner)
        source = sources.owner_identity(owner)
        snapshot = inspect_mesh(api, component, source["expected_witness_triangle_count"])
        ownership = verify_ownership(snapshot, owner, source)
        verify_delta(snapshot["summary"], snapshot, owner, assigned=False)
        total_vertices += snapshot["summary"]["vertex_count"]
        total_triangles += snapshot["summary"]["triangle_count"]
        require(total_vertices <= MAX_TOTAL_VERTICES and total_triangles <= MAX_TOTAL_TRIANGLES,
                "Whole-support readback exceeds the admitted aggregate budget")
        state["items"].append({"owner": owner, "component": component, "old_material": old,
                               "source": source, "ownership": ownership, "before_mesh": snapshot["summary"]})
    # No assignment occurs until every source owner, including the parapet, has
    # completed its full geometry witness and original material check.
    try:
        apply_all(api, state, instance)
        verify_states(api, state, assigned=True)
    finally:
        rollback_proof = rollback(api, state)
    try:
        apply_all(api, state, instance)
        after = verify_states(api, state, assigned=True)
    except Exception:
        rollback(api, state)
        raise
    owners = [
        {**{key: item["source"][key] for key in OWNER_SUMMARY_FIELDS},
         "source": item["source"], "ownership": item["ownership"],
         "before_mesh": item["before_mesh"], "after_mesh": summary}
        for item, summary in zip(state["items"], after, strict=True)
    ]
    receipt = {
        "schema_version": 2, "status": "SHOULDER_NETWORK_PREPARED",
        "source_identity": source_plan["source_identity"], "material": material_receipt,
        "material_api": api_receipt, "hash_format": HASH_FORMAT, "owners": owners,
        "support_count": len(owners), "material_target_count": sum(o["material_target"] for o in owners),
        "excluded_parapet_count": sum(not o["material_target"] for o in owners),
        "selected_triangle_count": sum(o["selected_triangle_count"] for o in owners),
        "total_vertex_count": total_vertices, "total_triangle_count": total_triangles,
        "aggregate_after_sha256": digest(after), "rollback_verified": True,
        "rollback_proof": rollback_proof, "source_vertices_topology_normals_uv_preserved": True,
        "original_wall_material_preserved": True, "excluded_parapet_unchanged": True,
        "whole_area_admitted": False, "performance_pass": False,
    }
    return receipt, state


def verify_loaded(api, receipt, source_plan=None):
    """Read-only fresh load/GPU proof, inheriting source ownership by exact hashes."""
    source_plan = sources.load_sources() if source_plan is None else source_plan
    require(receipt.get("schema_version") == 2 and receipt.get("status") == "SHOULDER_NETWORK_PREPARED"
            and receipt.get("hash_format") == HASH_FORMAT and receipt.get("rollback_verified") is True
            and receipt.get("source_identity") == source_plan["source_identity"]
            and receipt.get("support_count") == sources.OWNER_COUNT
            and receipt.get("material_target_count") == sources.OWNER_COUNT - 1
            and receipt.get("excluded_parapet_count") == 1
            and receipt.get("source_vertices_topology_normals_uv_preserved") is True
            and receipt.get("original_wall_material_preserved") is True
            and receipt.get("excluded_parapet_unchanged") is True
            and receipt.get("whole_area_admitted") is False and receipt.get("performance_pass") is False,
            "Saved network material/source receipt differs")
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    pairs = owner_components(api, actors, source_plan)
    records = receipt.get("owners", [])
    require(isinstance(records, list) and len(records) == len(pairs), "Saved source-owner coverage differs")
    instance_path = receipt["material"]["assets"]["instance"]
    require(isinstance(instance_path, str) and instance_path.startswith(MATERIAL_ROOT),
            "Saved gravel material escaped the derived consumer")
    summaries = []
    for (owner, component), recorded in zip(pairs, records, strict=True):
        identity = sources.owner_identity(owner)
        require(identity == recorded["source"]
                and all(recorded.get(key) == identity[key] for key in OWNER_SUMMARY_FIELDS),
                "Fresh source ownership changed")
        proof = recorded.get("ownership", {})
        delta = proof.get("max_source_coordinate_delta_cm")
        require(proof.get("oriented_triangles_compared") == identity["expected_witness_triangle_count"]
                and proof.get("count_only_or_label_only_ownership") is False
                and type(delta) in (int, float) and math.isfinite(delta) and 0 <= delta <= 0.0001,
                "Saved oriented source/native ownership proof is incomplete")
        verify_slots(component, owner, instance_path)
        current = inspect_mesh(api, component)
        require(current["actor_label"] == owner["support_label"]
                and current["summary"] == recorded["after_mesh"],
                "Fresh full native mesh, corner attributes or material IDs changed")
        verify_delta(recorded["before_mesh"], current, owner, assigned=True)
        summaries.append(current["summary"])
    require(receipt.get("selected_triangle_count") == sum(r["selected_triangle_count"] for r in records)
            and receipt.get("total_vertex_count") == sum(s["vertex_count"] for s in summaries)
            and receipt.get("total_triangle_count") == sum(s["triangle_count"] for s in summaries)
            and receipt["total_vertex_count"] <= MAX_TOTAL_VERTICES
            and receipt["total_triangle_count"] <= MAX_TOTAL_TRIANGLES,
            "Fresh aggregate support inventory differs")
    require(receipt.get("rollback_proof") == {
        "status": "SHOULDER_NETWORK_ROLLBACK_VERIFIED", "support_count": sources.OWNER_COUNT,
        "aggregate_meshes_sha256": digest([r["before_mesh"] for r in records])},
        "Saved full-network rollback proof differs")
    require(digest(summaries) == receipt["aggregate_after_sha256"], "Fresh aggregate mesh digest changed")
    return receipt["aggregate_after_sha256"]
