"""Read current material bindings without modifying the open world."""

import json
import runpy
from pathlib import Path
import unreal

root = Path(__file__).resolve().parents[2]
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)


def path(value):
    return value.get_path_name() if value else None


report = {
    "world": path(world),
    "landscapes": [],
    "memory": runpy.run_path(str(root / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ](),
}
for actor in actors:
    components = actor.get_components_by_class(unreal.LandscapeComponent)
    report["landscapes"].append(
        {
            "actor": path(actor),
            "material": path(actor.get_editor_property("landscape_material")),
            "components": len(components),
            "overrides": {
                c.get_name(): path(c.get_editor_property("override_material"))
                for c in components
                if c.get_editor_property("override_material")
            },
        }
    )
(root / "Saved/live-material-inspection.json").write_text(json.dumps(report, indent=2))
unreal.log("YACS_LIVE_MATERIAL_INSPECTION " + json.dumps(report))
