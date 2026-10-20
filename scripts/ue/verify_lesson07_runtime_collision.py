"""Read the 15 authenticated L07 interior collision probes in a real SIE world.

Epic UE 5.8 LevelEditorSubsystem::EditorPlaySimulate/EditorRequestEndPlay and
UnrealEditorSubsystem::GetGameWorld provide the lifecycle; no terrain rebuild,
Houdini cook, content modification or asset save is performed here.
The parent owns the isolated process and its external deadline/exit-code check.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

MAP = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
WORLD_PATH = MAP + "." + MAP.rsplit("/", 1)[1]
MAP_SHA256 = "d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75"
ACTORS = {f"SaCalobra_Unified_{x}_{y}" for x in range(2) for y in range(2)}
SOURCE_HEAD = "5d4475af5fe04eade56ce87b2d62f257cd7095ef"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(path):
    path = Path(path).resolve()
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": digest}


def authenticated_json(path, digest, max_bytes=16 * 1024**2):
    require(0 < Path(path).stat().st_size <= max_bytes, "Evidence size is outside its bound")
    observed = identity(path)
    require(observed["sha256"] == digest.lower(), "Evidence SHA256 mismatch: " + str(path))
    return json.loads(Path(path).read_text(encoding="utf-8-sig")), observed


def normalize_pie_path(path):
    return re.sub(r"(?<=[/.])UEDPIE_\d+_", "", path)


def validate_runtime_world(world, editor_world, in_play):
    require(in_play and world is not None and world != editor_world, "A separate active runtime world is required")
    path = world.get_path_name()
    package = path.split(".", 1)[0]
    directory, name = MAP.rsplit("/", 1)
    require(re.fullmatch(re.escape(directory) + r"/UEDPIE_\d+_" + re.escape(name), package)
            and normalize_pie_path(path) == WORLD_PATH, "Runtime world is not the exact PIE copy of L07")
    return path


def read_inputs(project):
    native, native_identity = authenticated_json(
        os.environ["YACS_L07_RUNTIME_NATIVE_REPORT"], os.environ["YACS_L07_RUNTIME_NATIVE_SHA256"])
    plan, plan_identity = authenticated_json(
        os.environ["YACS_L07_RUNTIME_PLAN"], os.environ["YACS_L07_RUNTIME_PLAN_SHA256"], 1024**2)
    map_file = project / "Content" / (MAP[6:] + ".umap")
    saved_map = identity(map_file)
    require(saved_map["sha256"] == MAP_SHA256 and native.get("map_after") == saved_map
            and native.get("map_before") == saved_map and native.get("candidate_map_unchanged") is True,
            "Saved map differs from the authenticated final native readback")
    require(Path(native["project_root"]).resolve() == project and native.get("level") == MAP
            and native.get("source_head") == plan.get("source_head") == SOURCE_HEAD
            and native.get("structural_readback_complete") is True
            and native.get("repair_receipts_authenticated") is True,
            "Native readback does not authenticate this repaired candidate")
    preparation, preparation_identity = authenticated_json(
        native["preparation_identity"]["path"], native["preparation_identity"]["sha256"], 1024**2)
    require(preparation_identity == native["preparation_identity"], "Native preparation identity changed")
    interior = native.get("native_interiors", {})
    value = interior.get("value", {})
    expected_plan = {"path": plan_identity["path"], "sha256": plan_identity["sha256"]}
    require(interior.get("observed") is True and value.get("samples_complete") is True
            and value.get("plan_identity") == expected_plan and preparation.get("interior_plan") == expected_plan,
            "Native interior probes reference another source plan")
    require(plan.get("schema_version") == 1
            and plan.get("status") == "SOURCE_SELECTED_INTERIOR_NATIVE_READ_PENDING"
            and plan.get("level") == MAP and plan.get("original_source_center_bounds_m") == [-3999.75, 3999.75]
            and plan.get("buffer_vertices") == 3, "Unexpected source-selected interior plan")
    authenticated_json(plan["manifest"]["path"], plan["manifest"]["sha256"], 1024**2)
    probes = bind_queries(plan, value)
    actors = {row["name"]: row for row in native["landscapes"]}
    require(set(actors) == ACTORS, "Native actor set changed")
    return native, probes, actors, {
        "native_report": native_identity, "source_plan": plan_identity,
        "preparation": preparation_identity, "map_before": saved_map,
    }


def bind_queries(plan, interior):
    planned, measured = plan.get("probes", []), interior.get("probes", [])
    require(len(planned) == len(measured) == 15, "Exactly the 15 authenticated probes are required")
    native = {p["id"]: p for p in measured}
    require(len(native) == 15 and set(native) == {p["id"] for p in planned}, "Interior probe identity mismatch")
    queries = []
    for probe in planned:
        row = native[probe["id"]]
        require(probe["actor"] in ACTORS and row.get("actor") == probe["actor"]
                and row.get("component_path") == probe["component_path"] and row.get("observed") is True
                and probe["component_path"].startswith(WORLD_PATH + ":PersistentLevel." + probe["actor"] + "."),
                "Interior actor/component identity mismatch")
        validity = probe.get("source_validity")
        require(type(validity) is int and validity in (0, 1) and probe.get("uniform_source_patch_samples") == 64,
                "Source classification must come from the verified uniform patch")
        corners = row.get("native_corners", {}).get("samples", [])
        visibility_status = row.get("native_corners", {}).get("visibility_status")
        require(len(corners) == 4 and all(len(c) == 5 for c in corners)
                and row["native_corners"].get("vertex_indices") == probe.get("local_vertex_indices"),
                "Native visibility/corner identity differs from the source class")
        weights = [c[4] for c in corners]
        require((visibility_status == "ALLOCATED_READ" and weights == [255*(1-validity)]*4)
                or (validity == 1 and visibility_status == "NOT_ALLOCATED" and weights == [None]*4),
                "Native visibility observation conflicts with the source class")
        xy = [math.fsum(c[i] for c in corners) / 4.0 for i in (1, 2)]
        require(all(math.isfinite(v) for v in xy) and row["center_collision"].get("query_xy_cm") == xy,
                "Native collision query no longer identifies the original quad center")
        queries.append({"id": probe["id"], "actor": probe["actor"], "component_path": probe["component_path"],
                        "source_validity": validity, "query_xy_cm": xy,
                        "native_visibility_status": visibility_status, "native_visibility_weights": weights,
                        "editor_trace_hit": row["center_collision"]["hit"]})
    require(sum(q["source_validity"] == 0 for q in queries) == 3, "Expected three holes and twelve valid controls")
    return queries


def runtime_targets(api, world, expected):
    actors = list(api.GameplayStatics.get_all_actors_of_class(world, api.LandscapeProxy))
    require(len(actors) == 4 and {a.get_name() for a in actors} == ACTORS, "Runtime actor set differs")
    targets = {}
    for actor in actors:
        name = actor.get_name()
        require(normalize_pie_path(actor.get_path_name()) == WORLD_PATH + ":PersistentLevel." + name,
                "Runtime actor belongs to another level")
        location, rotation, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
        transform = {"location_cm": [location.x, location.y, location.z],
                     "rotation_deg_pitch_yaw_roll": [rotation.pitch, rotation.yaw, rotation.roll],
                     "scale": [scale.x, scale.y, scale.z]}
        require(all(transform[key] == expected[name][key] for key in transform), "Runtime Landscape transform changed")
        components = list(actor.get_components_by_class(api.LandscapeComponent))
        collision = list(actor.get_components_by_class(api.LandscapeHeightfieldCollisionComponent))
        require(len(components) == len(collision) == 1024, "Runtime Landscape component set is incomplete")
        targets[name] = (actor, {normalize_pie_path(c.get_path_name()): c for c in components},
                         {normalize_pie_path(c.get_render_component().get_path_name()): c for c in collision})
    return targets


def runtime_trace(api, world, targets, probe):
    actor, renders, collisions = targets[probe["actor"]]
    render = renders.get(probe["component_path"])
    collision = collisions.get(probe["component_path"])
    require(render is not None and collision is not None and collision.is_query_collision_enabled(),
            "The original target component has no runtime query collision")
    xy = probe["query_xy_cm"]
    ignored = [target[0] for name, target in targets.items() if name != probe["actor"]]
    raw = api.SystemLibrary.line_trace_single(
        world, api.Vector(xy[0], xy[1], 200000.0), api.Vector(xy[0], xy[1], -50000.0),
        api.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, api.DrawDebugTrace.NONE, True)
    hit = raw.to_dict() if raw is not None else {"blocking_hit": False}
    require(isinstance(hit, dict) and type(hit.get("blocking_hit")) is bool, "Runtime trace result is unknown")
    result = {**probe, "runtime_world": True, "observed": True, "hit": hit["blocking_hit"],
              "runtime_collision_component": collision.get_path_name(),
              "runtime_render_component": render.get_path_name()}
    if hit["blocking_hit"]:
        actual = hit.get("hit_component") or hit.get("component")
        require(hit.get("hit_actor") == actor and actual == collision and actual.get_owner() == actor
                and actual.get_render_component() == render, "Runtime hit is from another actor/component")
        point = hit["impact_point"]
        result["impact_point_cm"] = [float(point.x), float(point.y), float(point.z)]
        require(all(math.isfinite(v) for v in result["impact_point_cm"]), "Nonfinite runtime collision point")
    result["matches_source_class"] = result["hit"] == bool(probe["source_validity"])
    return result


def run(api, project, result, deadline):
    level = api.get_editor_subsystem(api.LevelEditorSubsystem)
    editor = api.get_editor_subsystem(api.UnrealEditorSubsystem)
    require(not level.is_in_play_in_editor() and editor.get_game_world() is None,
            "An existing play session must be preserved")
    require(not api.EditorLoadingAndSavingUtils.get_dirty_map_packages()
            and not api.EditorLoadingAndSavingUtils.get_dirty_content_packages(), "Existing unsaved work must be preserved")
    native, probes, expected, identities = read_inputs(project)
    result.update(identities)
    result["source_head"] = native["source_head"]
    api.log("[L07 runtime] authenticated saved map and 15 source-selected probes; loading map")
    editor_world = api.EditorLoadingAndSavingUtils.load_map(MAP)
    require(editor_world is not None and editor_world.get_path_name() == WORLD_PATH, "Exact L07 editor world did not load")
    started = False
    try:
        started = True
        api.log("[L07 runtime] requesting Simulate In Editor")
        level.editor_play_simulate()
        yield
        while editor.get_game_world() is None or not level.is_in_play_in_editor():
            require(time.monotonic() < deadline, "Runtime world start timed out")
            yield
        world = editor.get_game_world()
        result["runtime_world_path"] = validate_runtime_world(world, editor_world, level.is_in_play_in_editor())
        while api.GameplayStatics.get_time_seconds(world) <= 0:
            require(time.monotonic() < deadline, "Runtime world did not tick")
            yield
        result["runtime_world"] = True
        result["runtime_time_seconds"] = api.GameplayStatics.get_time_seconds(world)
        targets = runtime_targets(api, world, expected)
        api.log("[L07 runtime] authenticated actual SIE world, four actors and collision components")
        result["probes"] = []
        for probe in probes:
            result["probes"].append(runtime_trace(api, world, targets, probe))
        result["sampled_collision_matches_source"] = all(p["matches_source_class"] for p in result["probes"])
        result["status"] = ("RUNTIME_SAMPLES_MATCH_SOURCE" if result["sampled_collision_matches_source"]
                            else "RUNTIME_SAMPLES_DIFFER_FROM_SOURCE")
    finally:
        if started:
            api.log("[L07 runtime] requesting orderly end of owned simulation")
            level.editor_request_end_play()
            stop_deadline = time.monotonic() + 90
            yield
            while editor.get_game_world() is not None or level.is_in_play_in_editor():
                require(time.monotonic() < stop_deadline, "Owned simulation did not stop")
                yield
            result["simulation_stopped"] = True


def main():
    import unreal
    project = Path(unreal.Paths.get_project_file_path()).resolve().parent
    require(project == Path(os.environ["YACS_L07_RUNTIME_PROJECT"]).resolve()
            and Path("D:/yacs/work").resolve() in project.parents, "Owned isolated candidate required")
    require(unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"), "Unexpected engine version")
    output = Path(os.environ["YACS_L07_RUNTIME_REPORT"]).resolve()
    require(not output.exists() and output.suffix == ".json", "New owned JSON report required")
    result = {"schema_version": 1, "status": "STARTED", "project_root": str(project),
              "runtime_world": False, "simulation_stopped": False, "geometry_accepted": False,
              "whole_landscape_collision_proved": False, "map_saved": False,
              "scope": "15 authenticated interior quad centers: three holes and twelve valid controls",
              "trace": {"channel": "Visibility", "trace_type_query": 1, "complex": True}}
    operation = run(unreal, project, result, time.monotonic() + 900)
    state = {"busy": False, "done": False, "handle": None}

    def finish(error=None):
        state["done"] = True
        try:
            if error is not None:
                result["status"], result["error"] = "FAILED_RUNTIME_VERIFICATION", str(error)
                unreal.log_error(str(error))
            if "map_before" in result:
                result["map_after"] = identity(result["map_before"]["path"])
                result["candidate_map_unchanged"] = result["map_before"] == result["map_after"]
                if not result["candidate_map_unchanged"]:
                    result["status"] = "FAILED_SAVED_MAP_CHANGED"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        finally:
            unreal.unregister_slate_post_tick_callback(state["handle"])
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)
            unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

    def tick(_delta):
        if state["busy"] or state["done"]:
            return
        state["busy"] = True
        try:
            next(operation)
        except StopIteration:
            finish()
        except Exception as error:
            finish(error)
        finally:
            state["busy"] = False

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    state["handle"] = unreal.register_slate_post_tick_callback(tick)


if __name__ == "__main__":
    main()
