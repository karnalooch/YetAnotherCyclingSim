"""Bake the 4 unified landscape tiles into Unreal Engine using Houdini Engine Public API.

Target Level: /Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07
Each tile is 8129 x 8129 vertices (1024 components, 127 quads/section, 2 sections/component).
All 4 tiles share exact 0.5 m native lattice across the full [-4064, +4064] m domain.
"""
import json
import hashlib
import os
import shutil
from pathlib import Path
import time
import traceback
import unreal

_manifest_env = os.environ.get("YACS_LESSON07_REPAIR_MANIFEST")
if not _manifest_env:
    raise RuntimeError("Set YACS_LESSON07_REPAIR_MANIFEST to a verified fresh transfer manifest")
MANIFEST_PATH = Path(_manifest_env).resolve()
if Path("D:/yacs/work") not in MANIFEST_PATH.parents or "ue_transfer" == MANIFEST_PATH.parent.name:
    raise RuntimeError("Refusing legacy or non-versioned manifest")
REPORT_PATH = Path("D:/yacs/work/lesson07-unified-20261019/ue_landscape_bake_report.json")
LOG_PATH = Path("D:/yacs/work/lesson07-unified-20261019/ue_bake_log.txt")

MAP_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
BAKE_FOLDER = "/Game/Generated/YACS/Lesson07_Unified/Baked"
HDA_PATH = "/Game/Worlds/SaCalobra_Houdini_20261016/Houdini/SaCalobra_Terrain_Transfer_v2.SaCalobra_Terrain_Transfer_v2"

log_file = open(str(LOG_PATH), "w", encoding="utf-8")

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [BAKE] {msg}"
    log_file.write(line + "\n")
    log_file.flush()
    unreal.log(line)

state = {
    "status": "INITIALIZING",
    "tile_index": 0,
    "baked_tiles": [],
    "errors": [],
    "start_time": time.time(),
    "ticks": 0,
    "current_wrapper": None,
    "pending_action": None,
    "done": False,
    "timeout_ticks": 7200, # ~2 minutes per tile max
}

manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
tiles = manifest["tiles"]

def preflight_tiles():
    if manifest.get("status") != "NATIVE_TRANSFER_READY_UE_VALIDATION_PENDING":
        raise RuntimeError("Unverified L07 transfer: status must be native-ready pending")
    if manifest.get("accepted_l06_sha256") != "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24":
        raise RuntimeError("Transfer was not authenticated to the frozen L06 source")
    if not manifest.get("seam_verification", {}).get("seams_perfect"):
        raise RuntimeError("Native world-coordinate seams have not passed")
    if len(tiles) != 4:
        raise RuntimeError("Expected four L07 tiles")
    material_path = manifest.get("requested_hole_material")
    if not isinstance(material_path, str) or not material_path.startswith("/Game/"):
        raise RuntimeError("Production bake requires a validated masked hole material")
    material = unreal.load_asset(material_path)
    if not material or not isinstance(material, unreal.Material):
        raise RuntimeError(f"Masked landscape hole Material does not exist: {material_path}")
    if material.get_editor_property("blend_mode") != unreal.BlendMode.BLEND_MASKED:
        raise RuntimeError("Hole material must have BLEND_MASKED blend mode")
    linked = unreal.MaterialEditingLibrary.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_OPACITY_MASK
    )
    if linked is None or linked.get_class().get_name() != "MaterialExpressionLandscapeVisibilityMask":
        raise RuntimeError("Opacity Mask is not directly connected to LandscapeVisibilityMask")
    for tile in tiles:
        # Houdini records the per-tile hole material inside visibility metadata.
        validity = tile.get("visibility")
        if (not isinstance(validity, dict)
                or validity.get("layer") != "visibility"
                or validity.get("outside_source_zero") is not True
                or validity.get("requested_hole_material") != material_path):
            raise RuntimeError(f"{tile.get('name')}: no validity/visibility proof")
        path = MANIFEST_PATH.parent / tile["file"]
        if not path.is_file():
            raise RuntimeError(f"Missing tile {path}")
        with path.open("rb") as f:
            actual = hashlib.file_digest(f, "sha256").hexdigest()
        if actual != tile.get("sha256"):
            raise RuntimeError(f"Stale tile {path}; refusing destructive bake")

world = None
actor_subsystem = None
api = None
hda_asset = None
tick_handle = None

def fail(err_msg):
    log(f"ERROR: {err_msg}")
    state["errors"].append(err_msg)
    state["status"] = "FAILED"
    finish()

def setup_level_and_environment():
    global world, actor_subsystem
    log("Setting up level and environment...")
    project_path = Path(unreal.Paths.get_project_file_path()).resolve()
    # This mutating importer must run ONLY in an isolated work project. The
    # canonical author's active world is never an allowed target.
    if Path("D:/yacs/work").resolve() not in project_path.parents:
        raise RuntimeError("Destructive L07 baking in D:/yacs/project is prohibited")
    if os.environ.get("YACS_LESSON07_ALLOW_REBAKE") != "YES":
        raise RuntimeError("Explicit YACS_LESSON07_ALLOW_REBAKE=YES required")
    
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    
    if unreal.EditorAssetLibrary.does_asset_exist(MAP_PATH):
        log(f"Loading existing map {MAP_PATH}...")
        world = unreal.EditorLoadingAndSavingUtils.load_map(MAP_PATH)
    else:
        raise RuntimeError(f"Refusing to create a new L07 level without a prior isolated copy: {MAP_PATH}")
        
    if not world:
        raise RuntimeError("Failed to obtain editor world")
        
    if any(isinstance(a, unreal.LandscapeProxy)
           for a in actor_subsystem.get_all_level_actors()):
        if os.environ.get("YACS_LESSON07_ALLOW_REBAKE") != "YES":
            raise RuntimeError(
                "Existing landscapes are protected; deliberate "
                "YACS_LESSON07_ALLOW_REBAKE=YES required"
            )
    # Create a verified on-D: backup before approved destructive rebake.
    if os.environ.get("YACS_LESSON07_ALLOW_REBAKE") == "YES":
        saved_file = project_path.parent / "Content/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07.umap"
        if saved_file.is_file():
            backup_dir = project_path.parent / "Saved/L07_PreRebake_Backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            with saved_file.open("rb") as fd:
                old_sha = hashlib.file_digest(fd, "sha256").hexdigest()
            backup = backup_dir / f"{old_sha}.umap"
            if not backup.exists():
                shutil.copy2(saved_file, backup)
            with backup.open("rb") as fd:
                check_sha = hashlib.file_digest(fd, "sha256").hexdigest()
            if check_sha != old_sha:
                raise RuntimeError("Pre-rebake map backup checksum mismatch; refusing mutation")
            log(f"Verified old map backup at {backup} ({old_sha})")
    # Delete any pre-existing landscape actors to ensure clean transfer
    existing_actors = actor_subsystem.get_all_level_actors()
    removed_count = 0
    for a in existing_actors:
        if isinstance(a, unreal.LandscapeProxy):
            actor_subsystem.destroy_actor(a)
            removed_count += 1
    if removed_count > 0:
        log(f"Removed {removed_count} pre-existing landscape actors for clean bake")
        
    # Ensure lighting and atmosphere actors exist
    existing_actors = actor_subsystem.get_all_level_actors()
    has_sun = any(isinstance(a, unreal.DirectionalLight) for a in existing_actors)
    has_sky = any(isinstance(a, unreal.SkyLight) for a in existing_actors)
    has_atmosphere = any(isinstance(a, unreal.SkyAtmosphere) for a in existing_actors)
    has_postprocess = any(isinstance(a, unreal.PostProcessVolume) for a in existing_actors)
    
    if not has_sun:
        sun = actor_subsystem.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 200000), unreal.Rotator(-38, -35, 0))
        sun.set_actor_label("Review Sun")
        sc = sun.get_component_by_class(unreal.DirectionalLightComponent)
        sc.set_mobility(unreal.ComponentMobility.MOVABLE)
        sc.set_intensity(6.0)
        sc.set_editor_property("atmosphere_sun_light", True)
        log("Spawned Review Sun")
        
    if not has_atmosphere:
        atm = actor_subsystem.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
        atm.set_actor_label("Review Sky Atmosphere")
        log("Spawned Review Sky Atmosphere")
        
    if not has_sky:
        sky = actor_subsystem.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500000))
        sky.set_actor_label("Review Sky Light")
        skc = sky.get_component_by_class(unreal.SkyLightComponent)
        skc.set_mobility(unreal.ComponentMobility.MOVABLE)
        skc.set_editor_property("real_time_capture", True)
        log("Spawned Review Sky Light")
        
    if not has_postprocess:
        pp = actor_subsystem.spawn_actor_from_class(unreal.PostProcessVolume, unreal.Vector(0, 0, 0))
        pp.set_actor_label("Review Exposure")
        pp.set_editor_property("unbound", True)
        s = pp.get_editor_property("settings")
        s.set_editor_property("override_auto_exposure_min_brightness", True)
        s.set_editor_property("override_auto_exposure_max_brightness", True)
        s.set_editor_property("auto_exposure_min_brightness", 1.0)
        s.set_editor_property("auto_exposure_max_brightness", 1.0)
        pp.set_editor_property("settings", s)
        log("Spawned Review PostProcessVolume")
        
    # Never save a partly rebuilt existing level before successful bake.
    log("Level and environment prepared in memory; no early map save.")

def init_houdini_api():
    global api, hda_asset
    log("Initializing Houdini Public API...")
    api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
    api.create_session()
    if not api.is_session_valid():
        raise RuntimeError("Houdini Engine session could not be established")
    log("Houdini Engine session established successfully.")
    
    hda_asset = unreal.load_asset(HDA_PATH)
    if not hda_asset:
        raise RuntimeError(f"Failed to load HDA asset: {HDA_PATH}")
    log(f"Loaded HDA asset: {hda_asset.get_path_name()}")

def start_tile_bake():
    idx = state["tile_index"]
    if idx >= len(tiles):
        log("All tiles completed! Finalizing level...")
        state["pending_action"] = finish
        return
        
    tile = tiles[idx]
    tile_name = tile["name"]
    tile_file = str(MANIFEST_PATH.parent / tile["file"]).replace("\\", "/")
    
    log(f"\n>>> STARTING BAKE FOR TILE {idx + 1}/{len(tiles)}: {tile_name} <<<")
    log(f"    Cache: {tile_file}")
    
    settings = unreal.HoudiniPublicAPISettings()
    settings.enable_auto_cook = False
    settings.enable_auto_bake = False
    settings.bake_directory_path = BAKE_FOLDER
    
    wrapper = api.instantiate(hda_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)
    if not wrapper:
        raise RuntimeError(f"Instantiation failed: {api.get_last_error_message()}")
        
    state["current_wrapper"] = wrapper
    
    if not wrapper.set_string_parameter_value("terrain_cache", tile_file):
        raise RuntimeError(f"Failed to set terrain_cache parameter on {tile_name}")
        
    wrapper.on_post_cook_delegate.add_callable(on_post_cook)
    wrapper.on_post_processing_delegate.add_callable(on_post_processing)
    wrapper.on_post_bake_delegate.add_callable(on_post_bake)
    
    recook_res = wrapper.recook()
    log(f"    wrapper.recook() returned: {recook_res}")
    if not recook_res:
        raise RuntimeError(f"Failed to queue recook for {tile_name}: {wrapper.get_last_error_message()}")
    state["status"] = f"COOKING_{tile_name}"

def on_post_cook(w, success):
    log(f"    on_post_cook: success={success}, err={w.get_last_error_message()}")
    if not success:
        fail(f"Cook failed on tile {state['tile_index']}: {w.get_last_error_message()}")

def on_post_processing(w):
    log(f"    on_post_processing: num_outputs={w.get_num_outputs()}")
    if w.get_num_outputs() < 1:
        fail(f"Houdini Engine produced 0 outputs for tile {state['tile_index']}")
        return
        
    log("    Calling bake_all_outputs_with_settings...")
    bake_res = w.bake_all_outputs_with_settings(
        unreal.HoudiniEngineBakeOption.TO_ACTOR,
        replace_previous_bake=False,
        remove_temp_outputs_on_success=True
    )
    log(f"    bake_all_outputs_with_settings returned: {bake_res}")
    if not bake_res:
        fail(f"Bake call failed on tile {state['tile_index']}: {w.get_last_error_message()}")
    else:
        state["status"] = f"BAKING_{tiles[state['tile_index']]['name']}"

def on_post_bake(w, success):
    idx = state["tile_index"]
    tile_name = tiles[idx]["name"]
    log(f"    on_post_bake: success={success}, tile={tile_name}")
    if not success:
        fail(f"Bake failed on tile {tile_name}: {w.get_last_error_message()}")
        return
        
    state["baked_tiles"].append(tile_name)
    log(f"    Successfully baked {tile_name}!")
    
    # Clean up instantiated HDA component
    deleted = w.delete_instantiated_asset()
    log(f"    delete_instantiated_asset returned: {deleted}")
    state["current_wrapper"] = None
    
    # Advance to next tile
    state["tile_index"] += 1
    state["status"] = "NEXT_TILE"
    state["pending_action"] = start_tile_bake

def inventory_landscapes():
    actors = actor_subsystem.get_all_level_actors()
    landscapes = [a for a in actors if isinstance(a, unreal.LandscapeProxy)]
    
    results = []
    for la in landscapes:
        label = la.get_actor_label()
        loc = la.get_actor_location()
        scale = la.get_actor_scale3d()
        origin, extent = la.get_actor_bounds(False)
        comps = la.get_components_by_class(unreal.LandscapeComponent)
        mat = la.get_editor_property("landscape_material")
        
        entry = {
            "name": la.get_name(),
            "label": label,
            "class": la.get_class().get_name(),
            "location_cm": [loc.x, loc.y, loc.z],
            "scale": [scale.x, scale.y, scale.z],
            "bounds_origin_cm": [origin.x, origin.y, origin.z],
            "bounds_extent_cm": [extent.x, extent.y, extent.z],
            "component_count": len(comps),
            "material": mat.get_path_name() if mat else None,
        }
        results.append(entry)
        log(f"Landscape Actor: {label} | Components: {len(comps)} | Scale: {entry['scale']} | Bounds Origin: {entry['bounds_origin_cm']}")
    return results

def finish():
    if state["done"]:
        return
    state["done"] = True
    log("\n=== EXECUTING FINAL VERIFICATION & SAVE PASS ===")
    
    landscape_inventory = inventory_landscapes() if actor_subsystem is not None else []
    
    # Save the map and baked assets
    saved_map = (unreal.EditorLoadingAndSavingUtils.save_map(world, MAP_PATH)
                 if world is not None and not state["errors"] else False)
    log(f"save_map returned: {saved_map}")
    
    saved_dir = (unreal.EditorAssetLibrary.save_directory(
        BAKE_FOLDER, only_if_is_dirty=False, recursive=True)
        if world is not None and not state["errors"] else False)
    log(f"save_directory({BAKE_FOLDER}) returned: {saved_dir}")
    
    # Verification checks
    total_components = sum(la["component_count"] for la in landscape_inventory)
    bake_pass = (
        not state["errors"] and bool(saved_map) and bool(saved_dir)
        and len(landscape_inventory) == 4 and total_components == 4096
        and set(state["baked_tiles"]) == {tile["name"] for tile in tiles}
    )
    # A visibility volume is not proof of holes without LandscapeVisibilityMask.
    passed = False
    
    # 16-bit height quantization calculation
    # Range -5.0m to 1500.0m = 1505.0m = 150500 cm.
    # 16-bit uint16 = 65535 levels.
    # Quantization step = 150500 / 65535 = 2.2965 cm/step = 0.022965 m/step.
    quantization_cm = 150500.0 / 65535.0
    quantization_m = quantization_cm / 100.0
    
    final_report = {
        "status": "PENDING_VISIBILITY_MATERIAL_PROOF" if bake_pass else "FAILED",
        "bake_operations_pass": bool(bake_pass),
        "visibility_material_verified": False,
        "saved_map": bool(saved_map),
        "saved_assets": bool(saved_dir),
        "duration_seconds": time.time() - state["start_time"],
        "map_path": MAP_PATH,
        "baked_folder": BAKE_FOLDER,
        "baked_tiles": state["baked_tiles"],
        "landscape_actor_count": len(landscape_inventory),
        "total_component_count": total_components,
        "expected_component_count": 4096, # 4 * 1024
        "height_quantization": {
            "layer_min_m": -5.0,
            "layer_max_m": 1500.0,
            "layer_span_m": 1505.0,
            "uint16_levels": 65535,
            "quantization_step_cm": quantization_cm,
            "quantization_step_m": quantization_m,
        },
        "landscapes": landscape_inventory,
        "errors": state["errors"],
    }
    
    REPORT_PATH.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    log(f"Report written to {REPORT_PATH}")
    log(f"FINAL STATUS: {final_report['status']}")
    
    log_file.close()
    
    if tick_handle is not None:
        unreal.unregister_slate_post_tick_callback(tick_handle)
    unreal.EditorPythonScripting.set_keep_python_script_alive(False)
    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

def tick(delta_seconds):
    state["ticks"] += 1
    
    if state["pending_action"]:
        action = state["pending_action"]
        state["pending_action"] = None
        action()
        
    if state["ticks"] > state["timeout_ticks"] and not state["done"]:
        log("TIMEOUT WAITING FOR BAKE PROCESS!")
        fail("Execution timed out waiting for bake")

def main():
    global tick_handle
    try:
        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        preflight_tiles()
        setup_level_and_environment()
        init_houdini_api()
        tick_handle = unreal.register_slate_post_tick_callback(tick)
        state["pending_action"] = start_tile_bake
        log("Tick loop registered and active.")
    except Exception as e:
        log(f"Exception during startup: {traceback.format_exc()}")
        fail(str(e))

if __name__ == "__main__":
    main()
