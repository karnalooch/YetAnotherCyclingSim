"""Read-only native texture/streaming diagnostics for the current live repair."""
import unreal,json,os
from pathlib import Path
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06NorthMaterial';O.mkdir(exist_ok=True)
assert os.getpid()==json.loads((P/'Saved/RuntimeProof/Lesson06SeamRemote/ready.json').read_text())['pid']
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
cvars={n:unreal.SystemLibrary.get_console_variable_int_value(n) for n in ['r.Streaming.PoolSize','r.Streaming.UseFixedPoolSize','r.Streaming.LimitPoolSizeToVRAM','r.Streaming.UseNewBudget','r.TextureStreaming','r.Streaming.MipBias','r.Streaming.Boost','r.Streaming.MaxTempMemoryAllowed']}
rows=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
 if not isinstance(a,unreal.LandscapeProxy):continue
 m=a.get_editor_property('landscape_material');t=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m,'AlbedoTexture')
 r={'actor':a.get_actor_label(),'material':m.get_path_name(),'texture':t.get_path_name(),'hidden':a.is_temporarily_hidden_in_editor(),'size':[t.blueprint_get_size_x(),t.blueprint_get_size_y()]}
 for prop in ['filter','mip_gen_settings','lod_bias','max_texture_size','never_stream','srgb','compression_settings','lod_group','address_x','address_y']:r[prop]=str(t.get_editor_property(prop))
 rows.append(r)
(O/'streaming_before.json').write_text(json.dumps({'pid':os.getpid(),'cvars':cvars,'textures':rows},indent=2))
unreal.SystemLibrary.execute_console_command(world,'stat streaming')
unreal.SystemLibrary.execute_console_command(world,'r.Streaming.UseFixedPoolSize ?')
