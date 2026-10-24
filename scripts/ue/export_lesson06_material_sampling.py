"""Read back only the four currently bound material color textures."""
import json
import os
from pathlib import Path
import unreal

assert os.getpid() == 11820
out = Path(unreal.Paths.project_dir()).resolve() / 'Saved/RuntimeProof/Lesson06MaterialSampling'
applied = json.loads((out / 'applied.json').read_text())
actors = {a.get_actor_label(): a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()}
rows = []
for name in applied['actors']:
    material = actors[name].get_editor_property('landscape_material')
    texture = unreal.MaterialEditingLibrary.get_material_instance_texture_parameter_value(material, 'AlbedoTexture')
    assert texture.get_path_name().startswith('/Game/Generated/YACS/Lesson06MaterialSampling_20261018/')
    file = out / (name + '_native.png')
    assert not file.exists()
    task = unreal.AssetExportTask()
    task.object = texture
    task.filename = str(file)
    task.automated = True
    task.prompt = False
    task.replace_identical = False
    task.exporter = unreal.TextureExporterPNG()
    assert unreal.Exporter.run_asset_export_task(task)
    rows.append({'name': name, 'texture': texture.get_path_name(), 'export': str(file)})
(out / 'texture_exports.json').write_text(json.dumps(rows, indent=2) + '\n')
