"""Read-only material and texture sampling inventory for the live L06 scene."""
import json, os
from pathlib import Path
import unreal
P=Path(unreal.Paths.project_dir()).resolve();O=P/'Saved/RuntimeProof/Lesson06MaterialSampling'
O.mkdir(exist_ok=True)
assert os.getpid()==11820
rows=[]
for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if not isinstance(a,unreal.LandscapeProxy):continue
    if a.get_actor_label() not in ['SaCalobra_Detail_0_0','SaCalobra_Context_Valid','SaCalobra_DTM_Context_21']:continue
    m=a.get_editor_property('landscape_material')
    t=unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m,'AlbedoTexture')
    r={'actor':a.get_actor_label(),'material':m.get_path_name(),'texture':t.get_path_name(),'parent':m.get_editor_property('parent').get_path_name()}
    for prop in ['filter','mip_gen_settings','lod_bias','max_texture_size','never_stream','srgb','compression_settings','lod_group','address_x','address_y']:
        r[prop]=str(t.get_editor_property(prop))
    r['size']=[t.blueprint_get_size_x(),t.blueprint_get_size_y()]
    rows.append(r)
(O/'sampling_before.json').write_text(json.dumps(rows,indent=2))
