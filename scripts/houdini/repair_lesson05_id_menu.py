"""Guard the retained Pegasus ID menu when optional ID metadata is absent.

HIP-local embedded UI adaptation using SideFX hou.Geometry.findGlobalAttrib.
Run with hython; --verify checks the saved HIP without changing it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import hou

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--hip', type=Path, required=True)
ap.add_argument('--receipt', type=Path, required=True)
ap.add_argument('--verify', action='store_true')
a = ap.parse_args()
hou.setUpdateMode(hou.updateMode.Manual)
hou.hipFile.load(str(a.hip), suppress_save_prompt=True, ignore_load_warnings=True)

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

rows = []
source_hda = Path('D:/yacs/project/worldgen/houdini/sa_calobra/otls/sop_PE_Heightfield_Layers_to_ID.2.0.hda')
source_hash = digest(source_hda)
if not a.verify:
    target = hou.node('/obj/PEGASUS_PIPELINE_OVERVIEW/Houdini_Load_Landscape/PE_Heightfield_Layers_to_ID')
    definition = target.type().definition()
    assert len(target.type().instances()) == 2
    definition.copyToHDAFile('Embedded')
    embedded = next(d for d in hou.hda.definitionsInFile('Embedded') if d.nodeTypeName() == target.type().name())
    group = embedded.parmTemplateGroup()
    template = group.find('id_layer')
    script = template.itemGeneratorScript()
    assert 'if geo.dictAttribValue("id"):' in script
    template.setItemGeneratorScript(script.replace('if geo.dictAttribValue("id"):', 'if geo.findGlobalAttrib("id") is not None and geo.dictAttribValue("id"):'))
    group.replace('id_layer', template)
    embedded.setParmTemplateGroup(group)
    embedded.setIsPreferred(True)
for name in ('Houdini_Load_Landscape', 'Unreal_Load_Landscape'):
    parent = hou.node('/obj/PEGASUS_PIPELINE_OVERVIEW/' + name)
    node = parent.node('PE_Heightfield_Layers_to_ID')
    template = node.parm('id_layer').parmTemplate()
    original = template.itemGeneratorScript()
    old = 'if geo.dictAttribValue("id"):'
    new = 'if geo.findGlobalAttrib("id") is not None and geo.dictAttribValue("id"):'
    assert new in original
    menu_geo = node.node('IN_MENU').geometry()
    # Execute the real menu script against real HOM geometry fixtures as well as
    # the existing scene: absent, empty and valid dictionary cases.
    script = node.parm('id_layer').parmTemplate().itemGeneratorScript()
    namespace = {'hou': hou}
    exec('def menu():\n' + '\n'.join('    ' + line for line in script.splitlines()), namespace)
    previous = hou.pwd()
    hou.setPwd(node)
    try:
        actual = namespace['menu']()
    finally:
        hou.setPwd(previous)
    fixture_script = script.replace("hou.node('IN_MENU')", 'fixture_node')
    cases = []
    for metadata in (None, {}, {'0': {'name': 'Background'}, '1': {'name': 'Scree'}}):
        geo = hou.Geometry()
        if metadata is not None:
            geo.addAttrib(hou.attribType.Global, 'id', {})
            geo.setGlobalAttribValue('id', metadata)
        fixture = type('Fixture', (), {'geometry': lambda self: geo})()
        scope = {'hou': hou, 'fixture_node': fixture}
        exec('def menu():\n' + '\n'.join('    ' + line for line in fixture_script.splitlines()), scope)
        result = scope['menu']()
        expected = ['0', 'Background', '1', 'Scree'] if metadata else []
        assert result == expected, (result, expected)
        cases.append(result)
    rows.append({'node': node.path(), 'menu': actual,
                 'input_detail_attributes': [v.name() for v in menu_geo.globalAttribs()],
                 'input_connections': [v.path() for v in node.node('IN_MENU').inputs()],
                 'fixture_results': cases,
                 'hda': node.type().definition().libraryFilePath(),
                 'external_hda_sha256': digest(source_hda)})

if not a.verify:
    backup = a.hip.with_name(a.hip.stem + '_BeforeIdMenuRepair' + a.hip.suffix)
    assert not backup.exists(), 'Refuse backup overwrite'
    shutil.copy2(a.hip, backup)
    before = digest(backup)
    hou.hipFile.save(str(a.hip))
    receipt = {'before_sha256': before, 'backup': str(backup), 'hip': str(a.hip),
               'after_sha256': digest(a.hip), 'nodes': rows,
               'scope': 'Embedded definition menu guard, used by two overview nodes; external HDA unchanged',
               'fresh_reopen': 'pending'}
else:
    receipt = json.loads(a.receipt.read_text())
    assert digest(a.hip) == receipt['after_sha256']
    assert rows == receipt['nodes']
    receipt['fresh_reopen'] = 'PASS: both menus and three metadata fixtures per menu'
assert digest(source_hda) == source_hash
a.receipt.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
