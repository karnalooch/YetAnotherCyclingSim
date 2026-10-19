import json
from pathlib import Path
import time
import unreal

REPORT_PATH = Path("D:/yacs/work/lesson07-unified-20261019/ue_level_setup_report.json")
SOURCE_MAP = "/Game/Worlds/SaCalobra_Houdini_20261016/L_SaCalobra_LandscapeOnly"
TARGET_MAP = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
MI_PATH = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"

def log(msg):
    unreal.log(f"[LESSON07_LEVEL] {msg}")

def main():
    start_time = time.time()
    report = {
        "status": "STARTED",
        "timestamp": start_time,
        "source_map": SOURCE_MAP,
        "target_map": TARGET_MAP,
        "material_instance": MI_PATH,
    }

    # 1. Load Material Instance
    mi = unreal.EditorAssetLibrary.load_asset(MI_PATH)
    if not mi:
        raise RuntimeError(f"Failed to load material instance: {MI_PATH}")
    log(f"Loaded Material Instance: {mi.get_path_name()}")

    # 2. Duplicate or Load Source Map
    if not unreal.EditorAssetLibrary.does_asset_exist(TARGET_MAP):
        log(f"Target map {TARGET_MAP} does not exist. Duplicating from {SOURCE_MAP}...")
        dup_success = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_MAP, TARGET_MAP)
        if not dup_success:
            log(f"Duplicate asset failed, trying load and save...")
            src_world = unreal.EditorLoadingAndSavingUtils.load_map(SOURCE_MAP)
            if not src_world:
                raise RuntimeError(f"Failed to load source map {SOURCE_MAP}")
            save_success = unreal.EditorLoadingAndSavingUtils.save_map(src_world, TARGET_MAP)
            if not save_success:
                raise RuntimeError(f"Failed to save map as {TARGET_MAP}")
        log(f"Created target map {TARGET_MAP}")

    # 3. Load Target Map
    world = unreal.EditorLoadingAndSavingUtils.load_map(TARGET_MAP)
    if not world:
        raise RuntimeError(f"Failed to load target map {TARGET_MAP}")
    log(f"Loaded world: {world.get_path_name()}")

    # 4. Enumerate Actors and Assign Material
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = actor_subsystem.get_all_level_actors()
    log(f"Found {len(all_actors)} actors in level")

    landscape_actors = []
    lighting_actors = []

    for actor in all_actors:
        cls_name = actor.get_class().get_name()
        actor_name = actor.get_name()
        
        if isinstance(actor, unreal.LandscapeProxy):
            actor.set_editor_property("landscape_material", mi)
            origin, extent = actor.get_actor_bounds(False)
            landscape_actors.append({
                "name": actor_name,
                "class": cls_name,
                "assigned_material": actor.get_editor_property("landscape_material").get_path_name(),
                "origin": [origin.x, origin.y, origin.z],
                "extent": [extent.x, extent.y, extent.z],
            })
            log(f"Assigned MI to Landscape actor: {actor_name}")
            
        elif isinstance(actor, (unreal.DirectionalLight, unreal.SkyLight, unreal.SkyAtmosphere, unreal.ExponentialHeightFog)):
            lighting_actors.append({
                "name": actor_name,
                "class": cls_name,
            })
            log(f"Found lighting actor: {actor_name} ({cls_name})")

    report["landscape_actors"] = landscape_actors
    report["lighting_actors"] = lighting_actors

    # 5. Save Target Map
    saved = unreal.EditorLoadingAndSavingUtils.save_map(world, TARGET_MAP)
    if not saved:
        raise RuntimeError(f"Failed to save modified level {TARGET_MAP}")
    log(f"Saved modified level {TARGET_MAP}")

    # 6. Verification Pass: Re-open map cleanly
    log("Executing verification re-open pass...")
    reopen_world = unreal.EditorLoadingAndSavingUtils.load_map(TARGET_MAP)
    if not reopen_world:
        raise RuntimeError("Re-opening map failed!")
    
    reopen_actors = actor_subsystem.get_all_level_actors()
    reopen_landscapes = [a for a in reopen_actors if isinstance(a, unreal.LandscapeProxy)]
    for la in reopen_landscapes:
        assigned = la.get_editor_property("landscape_material")
        assert assigned and assigned.get_path_name().startswith(MI_PATH), f"Material mismatch on {la.get_name()}: {assigned}"

    report["verification_reopen"] = {
        "status": "SUCCESS",
        "actor_count": len(reopen_actors),
        "landscape_count": len(reopen_landscapes),
        "materials_verified": True,
    }
    report["status"] = "LEVEL_SETUP_SUCCESS"
    report["duration_seconds"] = time.time() - start_time

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log(f"Report written to {REPORT_PATH}")
    print("LEVEL_SETUP_COMPLETED_SUCCESSFULLY")

if __name__ == "__main__":
    main()
