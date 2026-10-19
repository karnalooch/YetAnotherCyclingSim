import unreal

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]

for ls in landscapes:
    origin, extent = ls.get_actor_bounds(False)
    loc = ls.get_actor_location()
    scale = ls.get_actor_scale3d()
    print(f"\nLandscape: {ls.get_actor_label()}")
    print(f"  Location (cm): x={loc.x}, y={loc.y}, z={loc.z}")
    print(f"  Bounds Origin (cm): x={origin.x}, y={origin.y}, z={origin.z}")
    print(f"  Bounds Extent (cm): x={extent.x}, y={extent.y}, z={extent.z}")
    print(f"  Scale: x={scale.x}, y={scale.y}, z={scale.z}")
    print(f"  Bounds in meters: [{origin.x - extent.x:.1f}, {origin.y - extent.y:.1f}] -> [{origin.x + extent.x:.1f}, {origin.y + extent.y:.1f}] cm")
    print(f"  Bounds in m: [{(origin.x - extent.x)/100:.2f}, {(origin.y - extent.y)/100:.2f}] -> [{(origin.x + extent.x)/100:.2f}, {(origin.y + extent.y)/100:.2f}] m")
