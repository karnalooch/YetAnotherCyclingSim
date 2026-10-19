import unreal

asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

world = unreal.EditorLevelLibrary.get_editor_world()
rt = unreal.RenderingLibrary.create_render_target2d(world, 1280, 720)

loc = unreal.Vector(-95000.0, -53000.0, 35000.0)
rot = unreal.Rotator(-45.0, 0.0, 0.0)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
capture_actor = actor_subsystem.spawn_actor_from_class(unreal.SceneCapture2D, loc, rot)
cc = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
cc.texture_target = rt
cc.capture_scene()

folder = "D:/yacs/project/worldgen/houdini/sa_calobra/evidence"
filename = "test_scene_capture.png"
unreal.RenderingLibrary.export_render_target(world, rt, folder, filename)

capture_actor.destroy_actor()
print("Scene capture test successful!")

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
