import unreal

log_file = open("D:/yacs/project/worldgen/houdini/sa_calobra/landscape_actors_info.txt", "w")
def log(msg):
    log_file.write(str(msg) + "\n")
    log_file.flush()

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]

log(f"Found {len(landscapes)} landscape actors:\n")
for l in landscapes:
    loc = l.get_actor_location()
    rot = l.get_actor_rotation()
    scale = l.get_actor_scale3d()
    bounds = l.get_actor_bounds(False)
    layers = [lyr.get_name_bp() for lyr in l.get_edit_layers_bp()]
    
    log(f"--- {l.get_actor_label()} ---")
    log(f"  Class: {l.get_class().get_name()}")
    log(f"  Location: (X={loc.x:.2f}, Y={loc.y:.2f}, Z={loc.z:.2f})")
    log(f"  Rotation: (P={rot.pitch:.2f}, Y={rot.yaw:.2f}, R={rot.roll:.2f})")
    log(f"  Scale: (X={scale.x:.4f}, Y={scale.y:.4f}, Z={scale.z:.4f})")
    log(f"  Bounds origin: {bounds[0]}, box_extent: {bounds[1]}")
    log(f"  Edit layers count: {len(layers)}")
    for lname in layers:
        log(f"    - {lname}")
    
    log("")

log_file.close()
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
