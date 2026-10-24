import unreal

log_file = open("D:/yacs/project/worldgen/houdini/sa_calobra/debug_load_log.txt", "w")
def log(msg):
    log_file.write(str(msg) + "\n")
    log_file.flush()
    unreal.log(str(msg))

log("=== DEBUG PE_LOAD_LANDSCAPE IN UNREAL ===")
asset_root = "/Game/Worlds/SaCalobra_Houdini_20261016"
map_path = f"{asset_root}/L_SaCalobra_LandscapeOnly"

level_subsystem = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
level_subsystem.load_level(map_path)

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
landscapes = [a for a in actor_subsystem.get_all_level_actors() if isinstance(a, unreal.LandscapeProxy)]
target = [l for l in landscapes if "Detail_0_0" in l.get_actor_label()][0]

log(f"Target landscape: {target.get_actor_label()} ({target.get_name()})")

api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
api.create_session()

load_asset = unreal.load_asset(f"{asset_root}/Houdini/sop_PE_Load_Landscape_2.sop_PE_Load_Landscape_2")
settings = unreal.HoudiniPublicAPISettings()
settings.enable_auto_cook = False
settings.enable_auto_bake = False

wrapper = api.instantiate(load_asset, unreal.HoudiniPublicAPIInstantiationType.HOUDINI_ASSET_COMPONENT, settings)

project_dir = "D:/yacs/project/worldgen/houdini/sa_calobra"
log(f"Setting dir = {project_dir}")
wrapper.set_string_parameter_value("dir", project_dir)

log("Setting environment = 0 (Unreal)")
wrapper.set_int_parameter_value("environment", 0)

log("Setting mode = 1 (Update Existing)")
wrapper.set_int_parameter_value("mode", 1)

log("Setting input7 = 1 (Layer1_Manual)")
wrapper.set_int_parameter_value("input7", 1)

target_label = target.get_actor_label()
log(f"Setting output_name = {target_label}")
wrapper.set_string_parameter_value("output_name", target_label)

# Verify parameter values as read back from wrapper
log("Readback values:")
try:
    log(f"  dir: {wrapper.get_string_parameter_value('dir')}")
    log(f"  environment: {wrapper.get_int_parameter_value('environment')}")
    log(f"  mode: {wrapper.get_int_parameter_value('mode')}")
    log(f"  input7: {wrapper.get_int_parameter_value('input7')}")
    log(f"  output_name: {wrapper.get_string_parameter_value('output_name')}")
except Exception as e:
    log(f"  Error reading back: {e}")

log("\nCalling recook()...")
wrapper.recook()

log("Calling process_component_synchronous()...")
res = wrapper.process_component_synchronous()
log(f"process_component_synchronous returned: {res}")
log(f"last_error: '{wrapper.get_last_error_message()}'")
log(f"num_outputs: {wrapper.get_num_outputs()}")

for i in range(wrapper.get_num_outputs()):
    log(f"  Output {i}: type={wrapper.get_output_type_at(i)}")

log("Calling bake_all_outputs()...")
bake_res = wrapper.bake_all_outputs()
log(f"bake_all_outputs returned: {bake_res}")

wrapper.process_component_synchronous()
log(f"Post-bake last_error: '{wrapper.get_last_error_message()}'")

# Check target landscape edit layers
log(f"\nTarget edit layers count: {len(target.get_edit_layers_bp())}")
for l in target.get_edit_layers_bp():
    log(f"  layer: {l.get_name()} (bp: {l.get_name_bp()})")

wrapper.delete_instantiated_asset()
log("Done!")
log_file.close()

unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
