"""Load the pinned saved material onto an already loaded frozen map, without saving."""

import builtins
import json
import runpy
from pathlib import Path

import unreal

REPO = Path(__file__).resolve().parents[2]


def consume(report_path, *, restore=False, require_fresh=False, baseline=False):
    if restore and baseline:
        raise ValueError("Choose baseline or restore")
    foundation = runpy.run_path(
        str(REPO / "scripts/ue/sa_calobra_material_foundation.py")
    )
    digest = foundation["digest"]
    recipe_path = REPO / "worldgen/materials/sa_calobra_foundation.json"
    receipt_path = REPO / "worldgen/materials/sa_calobra_foundation_asset.json"
    recipe = json.loads(recipe_path.read_text(encoding="utf8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf8"))
    if (
        digest(recipe_path) != receipt["recipe_sha256"]
        or digest(REPO / "scripts/ue/sa_calobra_material_foundation.py")
        != receipt["producer_sha256"]
    ):
        raise RuntimeError("Saved candidate recipe/producer identity differs")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Unverified engine version")
    if (
        Path(
            unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
        ).resolve()
        != REPO
    ):
        raise RuntimeError("Wrong project checkout")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != recipe["map"]:
        raise RuntimeError("Wrong map; consumer will not load another map")
    map_file = REPO / "Content" / (recipe["map"].removeprefix("/Game/") + ".umap")
    if digest(map_file) != receipt["saved_map_sha256"]:
        raise RuntimeError("Frozen map bytes differ")
    for row in receipt["assets"]:
        path = (REPO / row["path"]).resolve()
        if not path.is_relative_to(
            REPO / "Content/Generated/YACS/SaCalobra/MaterialFoundation"
        ):
            raise RuntimeError("Saved candidate path escapes its package")
        if path.stat().st_size != row["size_bytes"] or digest(path) != row["sha256"]:
            raise RuntimeError("Saved candidate asset bytes differ: " + row["path"])
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected one frozen Landscape")
    landscape = landscapes[0]
    before = foundation["scene_snapshot"](world, landscape, map_file)
    if require_fresh and any(
        asset.get_path_name().split(".")[0] == receipt["material"]
        for asset in unreal.ObjectIterator(unreal.Material)
    ):
        raise RuntimeError(
            "Candidate already resident; fresh-load proof requires a fresh process"
        )
    previous = getattr(builtins, "_yacs_2b_saved_consumer", None)
    if previous is not None and previous["world"] != world.get_path_name():
        raise RuntimeError("Saved consumer cache belongs to another world")
    if restore:
        if previous is None:
            raise RuntimeError("No saved-consumer material to restore")
        material = previous["original"]
    else:
        material = unreal.load_asset(receipt["material"])
        if material is None:
            raise RuntimeError("Saved material could not be loaded")
        if previous is None:
            previous = {
                "world": world.get_path_name(),
                "original": landscape.get_editor_property("landscape_material"),
            }
            builtins._yacs_2b_saved_consumer = previous
        if baseline:
            authoring = getattr(builtins, "_yacs_2b_material", None)
            if authoring is None or authoring["world"] != world.get_path_name():
                raise RuntimeError("No matching original authoring material retained")
            material = authoring["original"]
    try:
        landscape.set_editor_property("landscape_material", material)
        if foundation["scene_snapshot"](world, landscape, map_file) != before:
            raise RuntimeError("Frozen scene changed during saved consumption")
        components = landscape.get_components_by_class(unreal.LandscapeComponent)
        if len(components) != 1024:
            raise RuntimeError("Frozen Landscape topology differs")
        if landscape.get_editor_property("landscape_material") != material:
            raise RuntimeError("Landscape material property did not update")
        for component in components:
            root = component.get_material(0)
            seen = set()
            while isinstance(root, unreal.MaterialInstance):
                if root.get_path_name() in seen:
                    raise RuntimeError("Cyclic material parent")
                seen.add(root.get_path_name())
                root = root.get_editor_property("parent")
            if root != material:
                raise RuntimeError("Landscape component did not consume the material")
    except Exception:
        landscape.set_editor_property("landscape_material", previous["original"])
        raise
    report = {
        "status": "BASELINE_MATERIAL_APPLIED_GEOMETRY_UNCHANGED"
        if baseline
        else "SAVED_MATERIAL_CONSUMED_GEOMETRY_UNCHANGED",
        "fresh_material_load": bool(require_fresh),
        "material": material.get_path_name() if material else None,
        "component_count": len(components),
        "component_roots_verified": len(components),
        "scene_snapshot_equal": True,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "receipt_sha256": digest(receipt_path),
        "map_sha256": digest(map_file),
        "consumer_sha256": digest(__file__),
        "restore": restore,
        "baseline": baseline,
        "map_saved": False,
        "assets_saved": False,
        "visual_acceptance": "PENDING",
        "performance": "NOT_MEASURED",
    }
    Path(report_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    if restore:
        del builtins._yacs_2b_saved_consumer
    return report
