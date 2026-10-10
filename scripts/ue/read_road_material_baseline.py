"""Read the exact staged #363 consumer for #364; never author, save or start MCP.

The trusted host supplies YACS_ROAD_MATERIAL_EXPECTED_HEAD,
YACS_ROAD_MATERIAL_PREPARATION_SHA256 and YACS_ROAD_MATERIAL_PROOF_ROOT.
Only a fresh isolated /Engine/Maps/Entry session is accepted. Native query docs
are observations, not permission to invoke an unproved geometry API.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "scripts/ue/read_road_material_baseline.py"
OUTPUT_BASE = "Saved/RuntimeProof/RoadMaterialBaseline"
OUTPUT_NAME = "road-material-baseline.json"
JSON_LIMIT = 2 * 1024 * 1024
ACTOR_LIMIT = 10000
QUERY_LIMIT = 96
DOC_LIMIT = 4096
PROJECTION_ROOT = "/Engine/Functions/Engine_MaterialFunctions01/Texturing/"
READER_SOURCES = (
    SOURCE,
    "scripts/ue/sa_calobra_whole_map_prep.py",
    "scripts/ue/inspect_sa_calobra_material_foundation.py",
    "scripts/ue/probe_geometry_script_api.py",
    "scripts/ue/verify_accepted_scene_checkpoint.py",
    "scripts/ue/create_accepted_scene_checkpoint.py",
    "scripts/ue/preview_sa_calobra_repair_patch.py",
    "scripts/ue/capture_material_forge_landscape.py",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def output_path(root, supplied, safe_path):
    """Admit one ignored run directory and one fixed exclusive evidence leaf."""
    requested = Path(supplied)
    require(requested.is_absolute(), "proof root must be absolute")
    try:
        relative = requested.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("proof root belongs to another project") from exc
    prefix = OUTPUT_BASE + "/"
    require(relative.startswith(prefix), "proof root is outside the fixed Saved root")
    token = relative.removeprefix(prefix)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", token) is not None,
            "proof root requires one bounded run token")
    target = safe_path(root, relative + "/" + OUTPUT_NAME)
    require(not target.exists(), "baseline evidence exists; refuse overwrite")
    return target


def validate_preparation(value, exact_sha, session):
    """The caller authenticates raw receipt bytes before this semantic check."""
    require(
        value.get("schema_version") == 1
        and value.get("status") == "ACCEPTED_CONSUMER_BYTES_STAGED"
        and value.get("exact_sha") == exact_sha
        and value.get("consumer_source_sha") == session.SOURCE_SHA
        and value.get("consumer_source_run") == session.SOURCE_RUN
        and value.get("consumer_source_attempt") == session.SOURCE_ATTEMPT
        and value.get("profile_sha256") == session.operation.PROFILE_SHA256
        and value.get("metadata_anchors") == {
            name: {"sha256": pin[0], "size_bytes": pin[1]}
            for name, pin in session.PINNED_METADATA.items()
        },
        "staging receipt differs from the frozen accepted consumer",
    )
    for flag in ("native_runtime_verified", "official_mcp_admitted",
                 "persistent_world_mutation", "performance_pass", "context_written"):
        require(value.get(flag) is False, "staging receipt has incompatible admission")
    require(value.get("performance_status") == "DEFERRED_AFTER_M3",
            "staging receipt changed the M3 performance contract")
    assets = value.get("consumer_assets")
    require(isinstance(assets, list) and len(assets) == 14,
            "accepted consumer asset inventory differs")
    paths = set()
    for row in assets:
        require(isinstance(row, dict) and isinstance(row.get("path"), str)
                and row["path"] not in paths
                and re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256"))) is not None
                and type(row.get("size_bytes")) is int
                and 0 < row["size_bytes"] <= session.FILE_LIMIT,
                "accepted asset identity is invalid or duplicated")
        paths.add(row["path"])
    maps = [row for row in assets if row["path"] == session.operation.MAP_FILE]
    require(len(maps) == 1, "staging receipt lacks the exact derived map")
    return maps[0]


def authenticated_preparation(session, exact_sha, expected_hash):
    path = session._safe_path(ROOT, session.SESSION_DIR + "/session-preparation.json")
    identity = session._identity(path, JSON_LIMIT)
    require(identity["sha256"] == expected_hash, "untrusted staging receipt bytes")
    value = session._read_json(path, (expected_hash, identity["size_bytes"]))
    map_row = validate_preparation(value, exact_sha, session)
    return path, identity, value, map_row


def numeric_tuple(value):
    if hasattr(value, "to_tuple"):
        return [numeric_tuple(item) for item in value.to_tuple()]
    result = float(value)
    require(math.isfinite(result), "native numeric snapshot is non-finite")
    return result


def road_support_actors(actors):
    road, supports = [], []
    labels = set()
    for actor in actors:
        label = actor.get_actor_label()
        if label.startswith("YACS_PERSIST_ROAD"):
            require(label == "YACS_PERSIST_ROAD", "ambiguous road label")
            road.append(actor)
        elif label.startswith("YACS_PERSIST_SUPPORT_"):
            require(re.fullmatch(r"YACS_PERSIST_SUPPORT_[0-9]{3}", label) is not None,
                    "invalid support label")
            supports.append(actor)
        else:
            continue
        require(label not in labels, "duplicate road/support label")
        labels.add(label)
    require(len(road) == 1 and len(supports) == 186,
            "expected one road and 186 saved supports")
    return sorted(road + supports, key=lambda actor: actor.get_actor_label())


def material_snapshot(api, material):
    if material is None:
        return None
    row = {"path": material.get_path_name(), "class": material.get_class().get_name(),
           "parent": None, "effective_color": None}
    if isinstance(material, api.MaterialInstanceConstant):
        parent = material.get_editor_property("parent")
        row["parent"] = None if parent is None else parent.get_path_name()
        names = api.MaterialEditingLibrary.get_vector_parameter_names(material)
        require(len(names) <= 256, "material parameter inventory exceeds its bound")
        if "Color" in (str(name) for name in names):
            color = api.MaterialEditingLibrary.get_material_instance_vector_parameter_value(
                material, "Color")
            row["effective_color"] = [numeric_tuple(getattr(color, channel))
                                      for channel in ("r", "g", "b", "a")]
    return row


def native_inventory(api, prep, map_package):
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    require(world is not None and world.get_path_name().split(".")[0] == map_package,
            "wrong loaded consumer map")
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    require(len(actors) <= ACTOR_LIMIT, "actor inventory exceeds its bound")
    landscapes = list(api.GameplayStatics.get_all_actors_of_class(world, api.Landscape))
    require(len(landscapes) == 1, "expected one saved Landscape")
    components = list(landscapes[0].get_components_by_class(api.LandscapeComponent))
    require(len(components) == 1024, "expected all 1024 saved Landscape components")
    rows = []
    for actor in road_support_actors(actors):
        component = actor.get_dynamic_mesh_component()
        mesh = component.get_dynamic_mesh()
        require(mesh is not None, "saved dynamic mesh is missing")
        slot_count = component.get_num_materials()
        require(0 < slot_count <= 32, "road/support material slot inventory is invalid")
        rows.append({
            "label": actor.get_actor_label(), "actor": actor.get_path_name(),
            "transform": numeric_tuple(actor.get_actor_transform()),
            "component": component.get_path_name(), "mesh": mesh.get_path_name(),
            "vertices": mesh.get_vertex_count(), "triangles": mesh.get_triangle_count(),
            "collision": str(component.get_collision_enabled()),
            "slots": [material_snapshot(api, component.get_material(index))
                      for index in range(slot_count)],
        })
    bindings = prep.mesh_material_snapshot(api)
    require(len(bindings) <= ACTOR_LIMIT, "mesh binding inventory exceeds its bound")
    require(len({row["component"] for row in bindings}) == len(bindings),
            "duplicate mesh component path")
    return {
        "world": world.get_path_name(), "map_package": map_package,
        "road_count": 1, "support_count": len(rows) - 1,
        "road_supports": rows,
        "actors": sorted((actor.get_path_name(), numeric_tuple(actor.get_actor_transform()))
                         for actor in actors),
        "mesh_material_collision_snapshot": bindings,
        "landscape": {"path": landscapes[0].get_path_name(), "component_count": len(components),
                      "components": sorted(component.get_path_name() for component in components)},
    }


def native_projection(api):
    result = {}
    for name in ("WorldAlignedTexture", "WorldAlignedNormal"):
        path = PROJECTION_ROOT + name
        asset = api.load_asset(path)
        require(asset is not None, "required native projection function is missing")
        expressions = list(api.MaterialEditingLibrary.get_material_function_expressions(asset))
        require(len(expressions) <= 1024, "native function expression inventory exceeds its bound")
        inputs, outputs = [], []
        for expression in expressions:
            if isinstance(expression, api.MaterialExpressionFunctionInput):
                inputs.append(str(expression.get_editor_property("input_name")))
            elif isinstance(expression, api.MaterialExpressionFunctionOutput):
                outputs.append(str(expression.get_editor_property("output_name")))
        result[name] = {"path": asset.get_path_name(), "input_names": inputs,
                        "output_names": outputs, "expression_count": len(expressions)}
    return result


def query_reflection(api, mesh):
    """Inspect actual read/query names and docs; never invoke discovered methods."""
    symbols = sorted(name for name in dir(api) if "geometryscript" in name.casefold()
                     and any(token in name.casefold() for token in ("mesh", "quer", "normal", "uv")))
    require(len(symbols) <= 128, "Geometry Script symbol inventory exceeds its bound")
    owners = [("DynamicMesh", mesh)] + [(name, getattr(api, name)) for name in symbols]
    methods, observed = {}, []
    for name, owner in owners:
        members = sorted(member for member in dir(owner)
                         if member.startswith(("get_", "is_", "has_"))
                         and any(token in member for token in
                                 ("vertex", "vertices", "triangle", "normal", "uv", "attribute", "material_id")))
        for member in members:
            qualified = name + "." + member
            observed.append(qualified)
            if len(methods) >= QUERY_LIMIT:
                continue
            method = getattr(owner, member)
            doc = str(getattr(method, "__doc__", "") or "")
            methods[qualified] = {"callable": callable(method), "doc": doc[:DOC_LIMIT],
                                  "doc_available": bool(doc), "doc_truncated": len(doc) > DOC_LIMIT,
                                  "invoked_by_reflection": False}
    require(len(observed) <= 1024, "query-name inventory exceeds its bound")
    material_methods = {}
    for name in ("get_material_function_expressions", "get_material_expression_input_names",
                 "get_material_expression_output_names", "get_vector_parameter_names",
                 "get_material_instance_vector_parameter_value"):
        method = getattr(api.MaterialEditingLibrary, name, None)
        doc = str(getattr(method, "__doc__", "") or "")
        material_methods[name] = {"callable": callable(method), "doc": doc[:DOC_LIMIT],
                                  "doc_available": bool(doc), "doc_truncated": len(doc) > DOC_LIMIT}
    return {"actual_geometry_script_symbols": symbols, "observed_query_names": observed,
            "query_docs": methods, "query_docs_truncated": len(observed) > len(methods),
            "material_read_docs": material_methods,
            "new_geometry_query_behavior_verified": False}


def dirty_packages(api):
    for name in ("get_dirty_map_packages", "get_dirty_content_packages"):
        reader = getattr(api.EditorLoadingAndSavingUtils, name, None)
        require(callable(reader) and not reader(), "native map/content is dirty")


def main():
    # These imports are inert host validators; no session, context or server is started.
    sys.path.insert(0, str(ROOT))
    from scripts import committed_git_blobs as committed_git
    from scripts.ci import official_mcp_bob_session as session
    from scripts.ue import sa_calobra_whole_map_prep as prep

    exact_sha = os.environ.get("YACS_ROAD_MATERIAL_EXPECTED_HEAD", "")
    preparation_sha = os.environ.get("YACS_ROAD_MATERIAL_PREPARATION_SHA256", "")
    require(re.fullmatch(r"[0-9a-f]{40}", exact_sha) is not None, "exact source SHA is required")
    require(re.fullmatch(r"[0-9a-f]{64}", preparation_sha) is not None,
            "trusted preparation receipt SHA256 is required")
    session._assert_isolated_root()
    require(session.ROOT.resolve() == ROOT and prep.ROOT.resolve() == ROOT,
            "executing baseline helpers belong to another checkout")
    target = output_path(ROOT, os.environ.get("YACS_ROAD_MATERIAL_PROOF_ROOT", ""), session._safe_path)
    session._git("check-ignore", "--no-index", "--quiet", "--", target.relative_to(ROOT).as_posix())
    sources = session._sources(exact_sha, include_utilities=True)
    blobs = committed_git._read_exact_blobs(
        ROOT, exact_sha, READER_SOURCES, blob_limit=JSON_LIMIT, total_limit=JSON_LIMIT,
        timeout_seconds=30, path_validator=session._safe_path)
    for relative, raw in blobs.items():
        identity = session._identity(session._safe_path(ROOT, relative), JSON_LIMIT)
        require(identity["sha256"] == hashlib.sha256(raw).hexdigest(),
                "baseline reader source differs from committed HEAD")
        sources[relative] = identity["sha256"]
    receipt_path, receipt_identity, receipt, map_row = authenticated_preparation(
        session, exact_sha, preparation_sha)
    require(receipt.get("source_sha256") == session._sources(exact_sha),
            "staging source identity differs")
    require(receipt.get("source_dependencies") == session._source_dependency_inventory(exact_sha),
            "staging dependency inventory differs")
    all_rows = receipt["consumer_assets"] + receipt["source_dependencies"]
    session._verify_rows(ROOT, all_rows)
    session._assert_package_members(ROOT, all_rows)

    import unreal

    actual_project = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve()
    require(actual_project == ROOT, "wrong native project")
    engine = str(unreal.SystemLibrary.get_engine_version())
    require(engine.startswith("5.8.2-56702186"), "native baseline requires pinned Unreal 5.8.2 CL56702186")
    dirty_packages(unreal)
    prep.assert_isolated_bootstrap(unreal)
    require(unreal.EditorLoadingAndSavingUtils.load_map(session.operation.MAP_PACKAGE) is not None,
            "exact saved consumer did not load")
    before = native_inventory(unreal, prep, session.operation.MAP_PACKAGE)
    road = road_support_actors(list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                                   .get_all_level_actors()))[0]
    reflection = query_reflection(unreal, road.get_dynamic_mesh_component().get_dynamic_mesh())
    projection = native_projection(unreal)
    require(native_inventory(unreal, prep, session.operation.MAP_PACKAGE) == before,
            "native baseline inventory changed during readback")
    dirty_packages(unreal)
    session._verify_rows(ROOT, all_rows)
    session._assert_package_members(ROOT, all_rows)
    require(session._identity(receipt_path, JSON_LIMIT) == receipt_identity,
            "staging receipt changed during native readback")
    current_sources = session._sources(exact_sha, include_utilities=True)
    for relative in READER_SOURCES:
        current_sources[relative] = session._identity(session._safe_path(ROOT, relative), JSON_LIMIT)["sha256"]
    require(current_sources == sources, "tracked baseline source changed during native readback")
    payload = {
        "schema_version": 1, "issue": 364, "status": "ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE",
        "exact_sha": exact_sha, "reader_source_sha256": sources,
        "engine_version": engine, "project": str(actual_project),
        "staging_receipt": {"path": receipt_path.relative_to(ROOT).as_posix(), **receipt_identity},
        "consumer_source_sha": receipt["consumer_source_sha"],
        "consumer_source_run": receipt["consumer_source_run"],
        "consumer_source_attempt": receipt["consumer_source_attempt"],
        "metadata_anchors": receipt["metadata_anchors"], "derived_map_identity": map_row,
        "consumer_assets": receipt["consumer_assets"],
        "source_dependencies": receipt["source_dependencies"],
        "native_inventory": before, "native_projection_functions": projection,
        "native_query_reflection": reflection, "read_only": True,
        "pre_post_inventory_equal": True, "saved_asset_bytes_unchanged": True,
        "full_mesh_geometry_hash_verified": False, "geometry_normal_uv_hash": None,
        "material_authoring_verified": False, "persistent_world_mutation": False,
        "official_mcp_admitted": False, "performance_pass": False,
        "performance_status": "DEFERRED_AFTER_M3", "owner_visual_pass": False,
    }
    raw = (json.dumps(payload, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")
    require(len(raw) <= JSON_LIMIT, "baseline evidence exceeds its fixed JSON bound")
    target = output_path(ROOT, str(target.parent), session._safe_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    session._safe_path(ROOT, target.relative_to(ROOT).as_posix())
    with target.open("xb") as stream:
        stream.write(raw)
    unreal.log("YACS_ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE road=1 supports=186 landscape_components=1024")


if __name__ == "__main__":
    main()
