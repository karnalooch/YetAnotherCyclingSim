import argparse
import hou
from pathlib import Path

ap = argparse.ArgumentParser(
    description="Create a native SOP readback adapter, with no terrain output."
)
ap.add_argument("--output", type=Path, required=True)
args = ap.parse_args()
path = args.output.resolve()
assert hou.applicationVersionString() == "22.0.466"
path.parent.mkdir(parents=True, exist_ok=True)
assert not path.exists()
geo = hou.node("/obj").createNode("geo")
sub = geo.createNode("subnet", "Landscape_Readback")
incoming = sub.createNode("null", "UNREAL_INPUTS")
incoming.setInput(0, sub.indirectInputs()[0])
out = sub.createNode("output", "output0")
discard = sub.createNode("blast", "NO_LANDSCAPE_OUTPUT")
discard.setInput(0, incoming)
discard.parm("group").set("*")
out.setInput(0, discard)
out.setDisplayFlag(True)
group = sub.parmTemplateGroup()
group.append(hou.StringParmTemplate("file", "Readback File", 1))
button = hou.ButtonParmTemplate("capture", "Capture Native Input")
button.setScriptCallback(
    "hou.pwd().node('UNREAL_INPUTS').geometry().saveToFile(hou.pwd().evalParm('file'))"
)
button.setScriptCallbackLanguage(hou.scriptLanguage.Python)
group.append(button)
sub.setParmTemplateGroup(group)
hda = sub.createDigitalAsset(
    name="yacs::landscape_readback::1.2",
    hda_file_name=str(path),
    min_num_inputs=1,
    max_num_inputs=1,
    description="Native Landscape readback (no outputs)",
)
hda.type().definition().setParmTemplateGroup(group)
print(path)
