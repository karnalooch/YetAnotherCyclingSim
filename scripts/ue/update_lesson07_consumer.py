"""Update the existing L07 consumer through its authenticated file-to-output HDA.

The owner launches this only in the isolated candidate. No landscape is created,
no bake is performed, and no intermediate state is saved. The transport comes
from prepare_lesson07_consumer_update.py, preserving the source BGEO files.

Authority: SideFX Houdini 22 Unreal landscape/basics.html and publicapi.html;
installed 22.0.466 HoudiniPublicAPIAssetWrapper, HoudiniCookable and landscape
translator/runtime cleanup. Recook(BLOCKING) waits for successful processing.
Direct mode-1 outputs must reference the original actor and existing edit layer.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time

MAP = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
MATERIAL = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"
LAYER = "Houdini_Unified_Final"
ACTORS = {f"SaCalobra_Unified_{x}_{y}" for x in range(2) for y in range(2)}
HDA = ("/Game/Worlds/SaCalobra_Houdini_20261016/Houdini/"
       "SaCalobra_Terrain_Transfer_v2.SaCalobra_Terrain_Transfer_v2")
HDA_SHA256 = "0a70090cc2b04f50987553b81cabd789298fbde3ffebf2da2a670a1ef92037b6"
CONTRACT = {
    "modify_existing_only": True, "landscape_use_temp_layers": False,
    "clear_edit_layer": False, "do_not_bake_all_outputs": True,
    "no_save_between_scale_change_and_all_height_updates": True,
    "material_assignment_unchanged": True,
    "preserve_actor_identity_layout_xy_and_source_caches": True,
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def progress(unreal, phase):
    getattr(unreal, "log", print)("[L07 update] " + phase)


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(path):
    path = Path(path).resolve()
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256(path)}


def package_file(project, package, suffix=".uasset"):
    require(package.startswith("/Game/"), "Expected an explicit Game package")
    return project / "Content" / (package.split(".", 1)[0][6:] + suffix)


def object_path(obj):
    return obj.get_path_name().split(".", 1)[0] if obj is not None else None


def inventory(project):
    paths = []
    for relative in ("Generated/YACS/Lesson07_Unified", "PegasusDemo/Materials"):
        root = project / "Content" / relative
        paths.extend(root.rglob("*.uasset"))
        paths.extend(root.rglob("*.umap"))
    return {str(path.relative_to(project)): sha256(path) for path in sorted(paths)}


def read_authenticated_json(path, digest):
    require(sha256(path) == digest.lower(), f"Receipt identity mismatch: {path}")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_manifest(manifest, directory):
    require(manifest.get("schema_version") == 1
            and manifest.get("status") == "DERIVED_TRANSPORT_READY_NATIVE_UPDATE_NOT_RUN",
            "Expected the verified transport manifest")
    require(manifest.get("source_map") == MAP and manifest.get("hda_asset") == HDA
            and manifest.get("hda_parameter") == "terrain_cache"
            and manifest.get("target_edit_layer") == LAYER, "Transport target mismatch")
    require(manifest.get("required_native_update_contract") == CONTRACT,
            "Transport update contract mismatch")
    mode = manifest.get("mode")
    require(mode in ("visibility-only", "height-and-visibility"), "Unsupported transport mode")
    selected = manifest.get("selected_actors", [])
    require(selected and len(selected) == len(set(selected)) and set(selected) <= ACTORS,
            "Invalid selected actors")
    transforms = manifest.get("native_actor_transforms_before", {})
    require(set(transforms) == ACTORS, "Complete original actor transforms required")
    for transform in transforms.values():
        for key in ("location_cm", "rotation_deg_pitch_yaw_roll", "scale"):
            values = transform.get(key, [])
            require(len(values) == 3 and all(type(v) in (int, float) and math.isfinite(v)
                                            for v in values), "Invalid original actor transform")
        require(transform["location_cm"][2] == 0 and min(transform["scale"]) > 0,
                "Nonzero Z origin or invalid scale requires separate calibration")
    if mode == "height-and-visibility":
        require(set(selected) == ACTORS, "Height updates require all four existing actors")
        require(manifest.get("required_common_scale_z") == max(
            row["scale"][2] for row in transforms.values()), "Common scale is not the measured maximum")
    else:
        require(manifest.get("required_common_scale_z") is None, "Mask-only update cannot rescale terrain")
    tiles = manifest.get("tiles", [])
    require(len(tiles) == len(selected) and {t["name"] for t in tiles} == set(selected),
            "Transport actor set mismatch")
    for tile in tiles:
        path = (directory / tile["file"]).resolve()
        require(path.parent == directory.resolve() and path.suffixes == [".bgeo", ".sc"],
                "Transport must be a direct BGEO child")
        require(path.stat().st_size == tile["bytes"] and sha256(path) == tile["sha256"],
                "Transport file changed")
        require(sha256(tile["source_file"]) == tile["source_sha256"]
                and tile.get("source_unchanged") is True and tile.get("saved_reopen_verified") is True,
                "Original BGEO or prepared reopen proof changed")
        attributes = {
            "unreal_output_name": tile["name"], "unreal_landscape_output_mode": 1,
            "unreal_landscape_editlayer_name": LAYER, "unreal_landscape_editlayer_clear": 0,
            "unreal_landscape_section_size": 127, "unreal_landscape_sections_per_component": 2,
            "unreal_landscape_layer_normalize": 0,
        }
        require(tile.get("update_attributes") == attributes, "Unsafe transport attributes")
        require(tile.get("visibility_polarity") == "UE hole=1-source validity; visible=0, hole=1",
                "Unknown visibility polarity")
        require(tile["visibility_output"]["resolution"] == [8129, 8129, 1],
                "Unexpected transport resolution")
        if mode == "visibility-only":
            require(tile["height_output"] is None, "Mask-only transport contains height")
        else:
            require(tile["height_output"] == tile["height_source"]
                    and tile.get("height_float32_and_transform_unchanged") is True,
                    "Prepared height values or registration changed")
    for key in ("source_manifest", "native_before"):
        receipt = manifest[key]
        read_authenticated_json(receipt["path"], receipt["sha256"])


def actor_snapshot(unreal, composition_state):
    actors = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
              if isinstance(a, unreal.LandscapeProxy)]
    require(len(actors) == 4 and {a.get_name() for a in actors} == ACTORS, "Existing actor set changed")
    native_layers = {row["actor"]: row for row in composition_state["actors"]}
    snapshots, targets = {}, {}
    for actor in actors:
        name = actor.get_name()
        location, rotation, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
        components = list(actor.get_components_by_class(unreal.LandscapeComponent))
        require(len(components) == 1024, "Existing component count changed")
        layers = list(actor.get_edit_layers_bp())
        require([str(layer.get_name_bp()) for layer in layers] == [LAYER],
                "The single existing target layer is required")
        require(native_layers[name]["edit_layer_locked"] is False, "Target edit layer is locked")
        require(object_path(actor.get_editor_property("landscape_material")) == MATERIAL,
                "Existing material binding changed")
        snapshots[name] = {
            "path": actor.get_path_name(), "landscape_guid": native_layers[name]["landscape_guid"],
            "location_cm": [location.x, location.y, location.z],
            "rotation_deg_pitch_yaw_roll": [rotation.pitch, rotation.yaw, rotation.roll],
            "scale": [scale.x, scale.y, scale.z], "edit_layer": LAYER,
            "edit_layer_guid": native_layers[name]["edit_layer_guid"],
            "component_paths": sorted(c.get_path_name() for c in components),
            "material": object_path(actor.get_editor_property("landscape_material")),
            "hole_material": object_path(actor.get_editor_property("landscape_hole_material")),
        }
        targets[name] = actor
    return snapshots, targets


def validate_transforms(before, manifest):
    for name, expected in manifest["native_actor_transforms_before"].items():
        require(all(before[name][key] == expected[key] for key in expected),
                f"Original actor transform changed: {name}")


def validate_actor_preservation(before, after, manifest):
    expected = copy.deepcopy(before)
    if manifest["mode"] == "height-and-visibility":
        for row in expected.values():
            row["scale"][2] = manifest["required_common_scale_z"]
    require(after == expected, "Actor identity, layout, XY, layers or material changed unexpectedly")


def height_snapshot(unreal):
    value = json.loads(unreal.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_heightmap_hashes())
    require(value.get("success") is True and value.get("world_package") == MAP
            and value.get("actor_count") == 4 and value.get("component_count") == 4096
            and value.get("height_source_scope") == "composite_and_existing_edit_layer_all_mips"
            and len(value.get("component_bindings", [])) == 4096 and value.get("textures"),
            "Complete native heightmap preservation report required")
    return value


def wait_for_layers(unreal, result, key):
    """Yield to real editor ticks until native composition/readback is complete."""
    progress(unreal, key + ": waiting for native layer composition")
    next_notice = time.monotonic() + 30
    while True:
        state = json.loads(unreal.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_layer_update_state())
        require(state.get("success") is True and state.get("world_package") == MAP
                and len(state.get("actors", [])) == 4
                and {a["actor"] for a in state["actors"]} == ACTORS,
                "Native layer completion observation unavailable")
        require(all(a.get("edit_layer_locked") is False and a.get("edit_layer_visible") is True
                    and a.get("edit_layer_guid") and a.get("landscape_guid") for a in state["actors"]),
                "Original layer is locked, hidden or lacks identity")
        result[key] = state
        if state.get("all_up_to_date") is True and all(a.get("up_to_date") is True for a in state["actors"]):
            progress(unreal, key + ": all four landscapes are up to date")
            return
        if time.monotonic() >= next_notice:
            progress(unreal, key + ": still waiting for native layer composition")
            next_notice = time.monotonic() + 30
        yield


def validate_cookable(unreal, cookable):
    require(cookable is not None, "Native HAPI cookable is unavailable")
    state = json.loads(unreal.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_cookable_state(cookable))
    require(state.get("success") is True and state.get("world_package") == MAP
            and state.get("cookable_path") == cookable.get_path_name()
            and state.get("is_landscape_modification") is True
            and state.get("landscape_use_temp_layers") is False,
            "Unsafe or unavailable native landscape configuration: " + json.dumps(state))
    return state


def validate_outputs(unreal, wrapper, actor, mode):
    records = wrapper.get_output_objects(None)
    require(records is not None, "Native output enumeration failed")
    expected_layers = {"visibility"} | ({"height"} if mode == "height-and-visibility" else set())
    rows = []
    for record in records:
        output = record.get_editor_property("output_object")
        require(output is not None and output.get_class().get_name() == "HoudiniLandscapeTargetLayerOutput",
                "Unexpected native output class")
        state = json.loads(unreal.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_output_state(output))
        require(state.get("success") is True and state.get("world_package") == MAP
                and state.get("output_path") == output.get_path_name(),
                "Native landscape output observation unavailable: " + json.dumps(state))
        get = state.get
        require(get("landscape_path") == actor.get_path_name()
                and get("landscape_proxy_path") == actor.get_path_name()
                and get("actor") == actor.get_name(),
                "Native output targeted a different actor")
        require(get("created_landscape") is False and get("layer_was_created") is False
                and get("clear_layer") is False and get("cooked_layer_requires_baking") is False,
                "Native output created or cleared a landscape/layer or requires baking")
        require(get("baked_edit_layer") == LAYER and get("cooked_edit_layer") == LAYER,
                "Temporary or unexpected edit layer")
        bounds = get("extents")
        require(bounds == [0, 0, 8128, 8128], "Native update did not cover the exact existing grid")
        rows.append({"actor": actor.get_name(), "target_layer": get("target_layer"),
                     "extents": bounds, "created_landscape": False,
                     "layer_was_created": False, "clear_layer": False,
                     "cooked_edit_layer": LAYER, "cooked_layer_requires_baking": False})
    require(len(rows) == len(expected_layers) and {r["target_layer"] for r in rows} == expected_layers,
            "Native update did not process every requested layer")
    return rows


def update_tile(unreal, api, asset, world, actor, tile, directory, mode):
    progress(unreal, tile["name"] + ": instantiate existing HDA with automatic cook/bake disabled")
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    settings.world_context_object = world
    wrapper = api.instantiate(asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
    require(wrapper is not None, "Existing HDA instantiation failed")
    require(not wrapper.is_auto_cooking_enabled() and not wrapper.is_auto_bake_enabled(),
            "Automatic cook/bake must be disabled")
    cookable = wrapper.get_houdini_cookable()
    validate_cookable(unreal, cookable)
    require(wrapper.set_string_parameter_value("terrain_cache", (directory / tile["file"]).as_posix()),
            "Could not bind the authenticated transport")
    progress(unreal, tile["name"] + ": blocking native cook started")
    if not wrapper.recook(unreal.HoudiniPublicAPICookMode.BLOCKING):
        raise RuntimeError("Native update failed: " + str(wrapper.get_last_error_message() or ""))
    progress(unreal, tile["name"] + ": cook completed; authenticate native output records")
    validate_cookable(unreal, cookable)
    rows = validate_outputs(unreal, wrapper, actor, mode)
    # Native cleanup deletes landscapes/layers only if created flags are true.
    # The checks above establish that removing this temporary HDA preserves the existing target.
    require(wrapper.delete_instantiated_asset(), "Temporary HDA cleanup failed")
    progress(unreal, tile["name"] + ": existing target verified and temporary HDA removed")
    return rows


def perform_update(unreal, manifest, directory, world, result):
    yield from wait_for_layers(unreal, result, "composition_before")
    before, actors = actor_snapshot(unreal, result["composition_before"])
    validate_transforms(before, manifest)
    result["actors_before"] = before
    progress(unreal, "hash all composite and existing-layer heightmap mips: before update")
    result["heightmaps_before"] = height_snapshot(unreal)
    progress(unreal, "before-update hashes complete; initialize Houdini Engine session")
    api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
    if not api.is_session_valid():
        api.create_session()
    require(api.is_session_valid(), "Houdini Engine session is unavailable")
    result["houdini_session"] = {
        "session_valid": True, "required_houdini_version": "22.0.466",
        "runtime_version_verified": False,
        "runtime_version_evidence": "Parent must authenticate built/running HAPI versions from this process log.",
    }
    asset = unreal.load_asset(HDA)
    require(asset is not None and asset.get_path_name() == HDA, "Authenticated existing HDA did not load")
    if manifest["mode"] == "height-and-visibility":
        progress(unreal, "apply common Scale.Z to all four actors; no save until all updates succeed")
        for name in sorted(ACTORS):
            scale = before[name]["scale"]
            actors[name].set_actor_scale3d(unreal.Vector(scale[0], scale[1], manifest["required_common_scale_z"]))
    result["completed_actors"], result["native_outputs"] = [], []
    for tile in manifest["tiles"]:
        result["native_outputs"].extend(update_tile(
            unreal, api, asset, world, actors[tile["name"]], tile, directory, manifest["mode"]))
        result["completed_actors"].append(tile["name"])
    require(set(result["completed_actors"]) == set(manifest["selected_actors"]),
            "No partial update may be saved")
    for name in manifest["selected_actors"]:
        actors[name].force_layers_full_update()
    progress(unreal, "native layer update requested; return control to engine ticks")
    yield  # Return to the engine after requesting the composition, even if the prior state was idle.
    yield from wait_for_layers(unreal, result, "composition_after")
    require({a["actor"]: a["edit_layer_guid"] for a in result["composition_before"]["actors"]}
            == {a["actor"]: a["edit_layer_guid"] for a in result["composition_after"]["actors"]},
            "Native edit-layer identity changed during composition")
    result["actors_after"], _ = actor_snapshot(unreal, result["composition_after"])
    validate_actor_preservation(before, result["actors_after"], manifest)
    progress(unreal, "hash all composite and existing-layer heightmap mips: after completed composition")
    result["heightmaps_after"] = height_snapshot(unreal)
    progress(unreal, "after-update hashes complete")
    result["whole_heightmaps_unchanged"] = result["heightmaps_before"] == result["heightmaps_after"]
    if manifest["mode"] == "visibility-only":
        require(result["whole_heightmaps_unchanged"], "Mask-only update changed height bytes or bindings; no save")
    # Verify cleanup removed all HDA actors before saving the map.
    require(not any(isinstance(a, unreal.HoudiniAssetActor) for a in
                    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()),
            "Temporary HDA actor remained; no save")


def execute(unreal, project, output, result):
    progress(unreal, "authenticate transport, saved map, HDA and existing package inventory")
    require(not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
            and not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
            "Existing unsaved packages must be preserved")
    require("-nullrhi" not in unreal.SystemLibrary.get_command_line().lower(),
            "Landscape composition requires the owned rendering process")
    result["engine_version"] = unreal.SystemLibrary.get_engine_version()
    require(result["engine_version"].startswith("5.8.2-56702186"), "Unexpected native engine version")
    transport = Path(os.environ["YACS_L07_UPDATE_MANIFEST"]).resolve()
    digest = os.environ["YACS_L07_UPDATE_MANIFEST_SHA256"].lower()
    manifest = read_authenticated_json(transport, digest)
    validate_manifest(manifest, transport.parent)
    result.update(mode=manifest["mode"], source_head=manifest["source_head"],
                  selected_actors=manifest["selected_actors"],
                  required_common_scale_z=manifest["required_common_scale_z"],
                  transport_manifest={"path": str(transport), "sha256": digest},
                  source_map_identity=manifest["source_map_identity"])
    map_file = package_file(project, MAP, ".umap")
    result["map_before"] = identity(map_file)
    result["files"] = inventory(project)
    require(result["map_before"]["sha256"] == os.environ["YACS_L07_UPDATE_MAP_SHA256"].lower(),
            "Current saved map differs from the explicit repair baseline")
    hda_file = package_file(project, HDA)
    require(sha256(hda_file) == HDA_SHA256, "Existing HDA asset bytes changed")
    result["hda_asset_sha256"] = HDA_SHA256
    require(shutil.disk_usage(project).free >= map_file.stat().st_size + 30 * 1024**3,
            "Authenticated map backup must preserve the 30 GiB reserve")
    backup = output.parent / (output.stem + "-backup")
    backup.mkdir(parents=True, exist_ok=False)
    backup_map = backup / map_file.name
    shutil.copy2(map_file, backup_map)
    require(sha256(backup_map) == result["map_before"]["sha256"], "Map backup identity mismatch")
    result["map_backup"] = str(backup_map)
    progress(unreal, "authenticated backup complete; load exact existing L07 map")
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    require(world is not None and object_path(world) == MAP, "Exact existing map did not load")
    progress(unreal, "existing L07 map loaded")
    yield from perform_update(unreal, manifest, transport.parent, world, result)
    validate_manifest(manifest, transport.parent)
    require(sha256(hda_file) == HDA_SHA256 and identity(map_file) == result["map_before"],
            "Protected HDA or saved map changed before the save boundary")
    require(not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages(),
            "Unexpected external dirty content; no save")
    if os.environ.get("YACS_L07_UPDATE_SAVE", "0") == "1":
        progress(unreal, "all update checks complete; save the existing map once")
        result["save_attempted"] = True
        require(unreal.EditorLoadingAndSavingUtils.save_map(world, MAP), "Existing map save failed; backup retained")
        result["map_saved"] = True
        result["status"] = "UPDATED_EXISTING_MAP_REOPEN_PENDING"
    else:
        result["status"] = "CANARY_COMPLETED_UNSAVED"
        progress(unreal, "canary complete; discard in-memory update without saving")


def close_owned_houdini_session(unreal, result):
    """Close this isolated process's HAPI session before UObject/module teardown."""
    if not result.get("houdini_session", {}).get("session_valid"):
        return
    progress(unreal, "close owned Houdini Engine session before editor shutdown")
    api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
    state = {"valid_before": bool(api.is_session_valid()), "stop_requested": False}
    result["houdini_session_close"] = state
    if state["valid_before"]:
        state["stop_requested"] = True
        api.stop_session()  # Public void API: verify actual state instead of its return value.
    state["valid_after"] = bool(api.is_session_valid())
    require(not state["valid_after"], "Owned Houdini Engine session remained valid after StopSession")
    state["status"] = "CLOSED"
    progress(unreal, "owned Houdini Engine session is closed; process exit remains externally verified")


def main():
    import unreal

    project = Path(unreal.Paths.get_project_file_path()).resolve().parent
    require(project == Path(os.environ["YACS_L07_UPDATE_PROJECT"]).resolve()
            and Path("D:/yacs/work").resolve() in project.parents, "Isolated candidate project required")
    output = Path(os.environ["YACS_L07_UPDATE_REPORT"]).resolve()
    result = {"schema_version": 1, "status": "STARTED", "project": str(project),
              "map_saved": False, "geometry_accepted": False, "source_comparison_proved": False,
              "visibility_source_proved": False, "fresh_reopen_verified": False}
    operation = execute(unreal, project, output, result)
    deadline = time.monotonic() + 1800
    state = {"busy": False, "handle": None}

    def finish(error=None):
        if error is not None:
            result["status"] = "FAILED_SAVE_ATTEMPT" if result.get("save_attempted") else "FAILED_NO_SAVE"
            result["error"] = str(error)
            unreal.log_error(str(error))
        try:
            try:
                close_owned_houdini_session(unreal, result)
            except Exception as close_error:
                result["status"] = "FAILED_SESSION_CLOSE"
                result["session_close_error"] = str(close_error)
                unreal.log_error(str(close_error))
            progress(unreal, "final saved-package inventory and receipt")
            if "files" in result:
                result["files_after"] = inventory(project)
                result["changed_files"] = sorted(p for p in set(result["files"]) | set(result["files_after"])
                                                if result["files"].get(p) != result["files_after"].get(p))
                allowed = {str(package_file(project, MAP, ".umap").relative_to(project))} if result["map_saved"] else set()
                result["protected_files_unchanged"] = not (set(result["changed_files"]) - allowed)
                if not result["protected_files_unchanged"]:
                    result["status"] = "FAILED_PROTECTED_ASSET_CHANGED"
                result["map_after"] = identity(package_file(project, MAP, ".umap"))
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        finally:
            unreal.unregister_slate_post_tick_callback(state["handle"])
            unreal.EditorPythonScripting.set_keep_python_script_alive(False)
            # Discard incomplete in-memory updates in this owned process; no generator replay.
            unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

    def tick(_delta):
        if state["busy"]:
            return
        state["busy"] = True
        try:
            require(time.monotonic() < deadline, "Native update/composition timed out; no save")
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
