"""Toggle one validated Material Forge instance on the Sa Calobra canary component.

The script never saves the level. Run it again to restore the original override.
World semantics and geometry remain unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import os
import runpy
from pathlib import Path

import unreal


ROOT = Path(__file__).resolve().parents[2]
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
MAP_HASH = "276d1621fa083850f6d603b6d115b01b74c9a92c182254d15302e786abfbf29c"
CANARY = "LandscapeComponent_230"


def _load_importer():
    path = ROOT / "scripts/ue/import_material_forge_variant.py"
    spec = importlib.util.spec_from_file_location("yacs_material_forge_importer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Material Forge importer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    raw = os.environ.get("YACS_MATERIAL_FORGE_VARIANT_DIR")
    if not raw:
        raise RuntimeError("Set YACS_MATERIAL_FORGE_VARIANT_DIR before canary preview")
    variant_dir = Path(raw)

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError("Open the accepted Sa Calobra map; no automatic map switch")

    foundation = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_foundation.py"))
    map_file = ROOT / "Content" / (MAP.removeprefix("/Game/") + ".umap")
    if foundation["digest"](map_file) != MAP_HASH:
        raise RuntimeError("Accepted map changed; refusing Material Forge canary")

    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected one frozen Landscape")
    landscape = landscapes[0]
    components = landscape.get_components_by_class(unreal.LandscapeComponent)
    matches = [component for component in components if component.get_name() == CANARY]
    if len(components) != 1024 or len(matches) != 1:
        raise RuntimeError("Unexpected Landscape topology or canary component")
    component = matches[0]

    before = foundation["scene_snapshot"](world, landscape, map_file)
    prior = getattr(unreal, "_yacs_material_forge_canary", None)
    current = component.get_editor_property("override_material")
    if prior:
        if (
            prior["world"] != world.get_path_name()
            or prior["component"] != component
            or current != prior["material"]
        ):
            raise RuntimeError("Material Forge canary changed externally")
        target = prior["original"]
        receipt = {"status": "RESTORED"}
    else:
        importer = _load_importer()
        target, import_receipt = importer.import_variant(
            variant_dir,
            destination_root="/Game/Generated/YACS/MaterialForgeCanary",
            save_assets=False,
        )
        receipt = {
            "status": "CANARY_ASSIGNED",
            "import": import_receipt,
        }

    original = current
    global_material = landscape.get_editor_property("landscape_material")
    other = {
        c.get_path_name(): c.get_editor_property("override_material")
        for c in components
        if c != component
    }
    try:
        component.set_editor_property("override_material", target)
        if component.get_editor_property("override_material") != target:
            raise RuntimeError("Material Forge canary assignment failed")
        if target is not None and component.get_material(0) != target:
            raise RuntimeError("Canary material consumer did not update")
        if global_material != landscape.get_editor_property("landscape_material"):
            raise RuntimeError("Global Landscape material changed")
        if any(
            c.get_editor_property("override_material") != other[c.get_path_name()]
            for c in components
            if c != component
        ):
            raise RuntimeError("Another Landscape component changed")
        if before != foundation["scene_snapshot"](world, landscape, map_file):
            raise RuntimeError("Frozen scene/geometry snapshot changed")
    except Exception:
        component.set_editor_property("override_material", original)
        raise

    receipt.update(
        component=component.get_path_name(),
        material=target.get_path_name() if target else None,
        map_saved=False,
        geometry_changed=False,
        world_semantics_changed=False,
        visual_acceptance="pending",
        performance_acceptance="pending",
    )
    proof = ROOT / "Saved/RuntimeProof/MaterialForgeCanary"
    proof.mkdir(parents=True, exist_ok=True)
    (proof / "latest.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )

    unreal._yacs_material_forge_canary = (
        None
        if prior
        else {
            "world": world.get_path_name(),
            "component": component,
            "original": original,
            "material": target,
        }
    )
    unreal.log("YACS_MATERIAL_FORGE_CANARY " + json.dumps(receipt))


if __name__ == "__main__":
    main()
