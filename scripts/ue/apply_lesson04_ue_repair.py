"""Apply versioned Houdini transfer files only to the isolated Lesson04 map.

Run inside UE using YACS_LESSON04_TRANSFER and YACS_LESSON04_PROOF.
Requires the original Houdini Engine cached-heightfield HDA already in YACS.
No global saves, source map changes, editor restarts, or stream reconfiguration.
"""

import json
import hashlib
import os
from pathlib import Path
import time
import traceback
import unreal

MAP = "/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test"
ROOT = "/Game/Generated/YACS/Lesson04Repair_20261018"
HDA = "/Game/Worlds/SaCalobra_Houdini_20261016/Houdini/SaCalobra_Terrain_Transfer_v2"
transfer = Path(os.environ["YACS_LESSON04_TRANSFER"])
proof = Path(os.environ["YACS_LESSON04_PROOF"])
proof.mkdir(parents=True, exist_ok=True)
manifest = json.loads((transfer / "manifest.json").read_text())
assert unreal.SystemLibrary.get_engine_version().startswith("5.8.2-"), (
    "Revalidate the adapter for this Unreal version"
)
plugin = json.loads(
    (
        Path(unreal.Paths.project_dir())
        / "Plugins/Runtime/HoudiniEngine/HoudiniEngine.uplugin"
    ).read_text()
)
assert plugin["Version"] == 22000466 and manifest["houdini_version"] == "22.0.466", (
    "Revalidate the height codecs for this Houdini Engine version"
)

assert manifest["target_map"] == MAP and manifest["output_mode"] == 1
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
state = {
    "status": "STARTING",
    "map": MAP,
    "completed": [],
    "native_reopen": "NOT_RUN",
    "visual_acceptance": False,
    "performance_pass": False,
}
wrapper = None
pending = []
wait_ticks = 0
tick_handle = None
phase = "next"
current = None
processed = False
baked = None
deadline = time.monotonic() + 1800
busy = False
settle_until = 0


def record(status, **fields):
    state.update(status=status, **fields)
    (proof / "apply.json").write_text(json.dumps(state, indent=2, default=str))
    unreal.log(
        "LESSON04_REPAIR " + json.dumps({"status": status, **fields}, default=str)
    )


def require_isolated():
    world = editor.get_editor_world()
    assert world and world.get_path_name().split(".")[0] == MAP, (
        "Refusing mutation outside the isolated map"
    )


def fix_materials():
    require_isolated()
    old = "/Game/Generated/YACS/Review/Materials"
    mat_name = "M_SaCalobra_Lesson04_Review"
    master_path = ROOT + "/Materials/" + mat_name
    if not unreal.EditorAssetLibrary.does_asset_exist(master_path):
        assert unreal.EditorAssetLibrary.duplicate_asset(
            old + "/" + mat_name, master_path
        )
    master = unreal.load_asset(master_path)
    for tile in manifest["tiles"]:
        name = "MI_Lesson04_" + tile["name"]
        path = ROOT + "/Materials/" + name
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            assert unreal.EditorAssetLibrary.duplicate_asset(old + "/" + name, path)
        mi = unreal.load_asset(path)
        unreal.MaterialEditingLibrary.set_material_instance_parent(mi, master)
        for param, key in [
            ("OriginCm", "uv_origin_cm"),
            ("InvSizeCm", "uv_inverse_cm"),
        ]:
            value = unreal.LinearColor(*tile[key], 0)
            unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
                mi, param, value
            )
            # Some editor setters compare vector values with a tolerance larger
            # than the entire inverse-extent parameter. Write the reflected
            # override exactly, then independently read it back.
            overrides = mi.get_editor_property("vector_parameter_values")
            match = [v for v in overrides if str(v.parameter_info.name) == param]
            assert len(match) == 1, "Missing or ambiguous vector override"
            match[0].parameter_value = value
            mi.set_editor_property("vector_parameter_values", overrides)
            actual = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(
                mi, param
            )
            assert all(
                abs(a - b) <= max(1e-11, abs(b) * 1e-6)
                for a, b in zip((actual.r, actual.g, actual.b), tile[key])
            ), "Material parameter readback mismatch"
        unreal.MaterialEditingLibrary.update_material_instance(mi)
        assert unreal.EditorAssetLibrary.save_loaded_asset(mi)
        a = targets[tile["name"]]
        a.set_editor_property("landscape_material", mi)
        a.set_editor_property("landscape_hole_material", mi)
    assert unreal.EditorAssetLibrary.save_loaded_asset(master)


def finish():
    global phase, settle_until
    require_isolated()
    fix_materials()
    for a in targets.values():
        assert unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(a)
    phase = "settle"
    settle_until = time.monotonic() + 20


def save_candidate():
    require_isolated()
    assert levels.save_current_level()
    record(
        "SAVED_CANDIDATE",
        layers={
            n: [str(edit_layer.get_name_bp()) for edit_layer in a.get_edit_layers_bp()]
            for n, a in targets.items()
        },
        scales={
            n: [
                a.get_actor_scale3d().x,
                a.get_actor_scale3d().y,
                a.get_actor_scale3d().z,
            ]
            for n, a in targets.items()
        },
    )
    unreal.unregister_slate_post_tick_callback(tick_handle)
    # The caller owns the editor and any live stream. Never quit here.


def on_processed(in_wrapper):
    global processed
    processed = True


def on_baked(in_wrapper, success):
    global baked
    baked = bool(success)


def run_import(tile, layer):
    global wrapper, wait_ticks, phase, current, processed, baked
    require_isolated()
    record("IMPORTING", tile=tile["name"], layer=layer)
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    settings.bake_directory_path = ROOT + "/Baked"
    wrapper = api.instantiate(
        asset,
        unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT,
        settings,
    )
    assert wrapper, "HDA instantiation failed"
    wrapper.process_component_synchronous()
    assert wrapper.set_string_parameter_value(
        "terrain_cache", (transfer / tile["files"][layer]).as_posix()
    )
    processed = False
    baked = None
    current = (tile, layer)
    wrapper.on_post_processing_delegate.add_callable(on_processed)
    wrapper.on_post_bake_delegate.add_callable(on_baked)
    assert wrapper.recook(), wrapper.get_last_error_message()
    phase = "cook"


def tick(delta):
    global wait_ticks, phase, wrapper, busy
    if busy:
        return
    if wait_ticks:
        wait_ticks -= 1
        return
    busy = True
    try:
        assert time.monotonic() < deadline, "Native import timed out"
        if phase == "next":
            if pending:
                tile, layer = pending.pop(0)
                run_import(tile, layer)
            else:
                finish()
        elif phase == "cook" and processed:
            assert wrapper.get_num_outputs() > 0, "No native output"
            phase = "bake"
            assert wrapper.bake_all_outputs_with_settings(
                unreal.HoudiniEngineBakeOption.TO_ACTOR,
                replace_previous_bake=False,
                remove_temp_outputs_on_success=True,
            ), wrapper.get_last_error_message()
        elif phase == "bake" and baked is not None:
            assert baked, "Native bake failed"
            tile, layer = current
            assert layer in [
                str(edit_layer.get_name_bp())
                for edit_layer in targets[tile["name"]].get_edit_layers_bp()
            ], "Baked target layer missing"
            assert wrapper.delete_instantiated_asset(), wrapper.get_last_error_message()
            wrapper = None
            state["completed"].append({"tile": tile["name"], "layer": layer})
            record("BAKED")
            phase = "next"
            wait_ticks = 30
        elif phase == "settle" and time.monotonic() >= settle_until:
            save_candidate()
    except Exception:
        record("ERROR", error=traceback.format_exc())
        unreal.unregister_slate_post_tick_callback(tick_handle)
    finally:
        busy = False


try:
    require_isolated()
    targets = {
        a.get_actor_label(): a
        for a in actors.get_all_level_actors()
        if isinstance(a, unreal.LandscapeProxy)
    }
    assert set(targets) == {t["name"] for t in manifest["tiles"]}, (
        "Unexpected Landscape set"
    )
    asset = unreal.load_asset(HDA)
    assert asset, "Existing native transfer HDA missing"
    api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
    api.create_session()
    assert api.is_session_valid(), api.get_last_error_message()
    for tile in manifest["tiles"]:
        for layer, filename in tile["files"].items():
            with (transfer / filename).open("rb") as f:
                assert (
                    hashlib.file_digest(f, "sha256").hexdigest()
                    == tile["file_sha256"][layer]
                ), "Transfer changed after validation"
    for tile in manifest["tiles"]:
        a = targets[tile["name"]]
        assert abs(a.get_actor_location().z) < 0.001, (
            "Nonzero Z origin requires a separately calibrated transfer"
        )
        # Replace every height layer under the test map. Retained visibility data
        # is independent; this helper clears heights only using native UE APIs.
        for layer in a.get_edit_layers_bp():
            assert unreal.CyclingLandscapeEarthworksLibrary.clear_manual_layer(
                a, layer.get_name_bp()
            )
        s = a.get_actor_scale3d()
        s.z = manifest["scale_z"]
        a.set_actor_scale3d(s)
        pending.extend(
            (tile, layer) for layer in (manifest["base_layer"], manifest["delta_layer"])
        )
    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    tick_handle = unreal.register_slate_post_tick_callback(tick)
    record("READY_FOR_NATIVE_IMPORT")
except Exception:
    record("ERROR", error=traceback.format_exc())
