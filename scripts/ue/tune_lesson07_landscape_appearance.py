"""Bounded M3/#365 appearance tuning of the already-open L07 consumer.

Reuses Pegasus parameters and UE texture build adjustments; no new shader,
classification, height, actors, level save, listener or editor lifecycle action.
The colour adjustment intentionally grades all five array slices. Their source
pixels/order remain intact; near-neutral limestone stays near-neutral. Settings
are an artistic YACS candidate, not prescribed SideFX or geographic values.
"""

import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT = "/Game/Generated/YACS/Lesson07_Unified"
SCALARS = {
    "Global Colour Strength": 0.0,
    "Global Saturation": 0.0,
    "Global Brightness": 0.0,
    "Detail Brightness": 1.0,
    "Macro Tiling": 0.25,
    "Global Normal Flatten": 0.2,
}
COLOUR_ADJUSTMENTS = {
    "adjust_hue": 25.0,
    "adjust_saturation": 0.7,
    "adjust_brightness": 1.1,
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    import unreal

    project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    )
    if project.resolve() != Path(__file__).resolve().parents[2]:
        raise RuntimeError(
            "Active Unreal project differs from this script checkout; no writes performed"
        )
    proof = project / "Saved/RuntimeProof/Lesson07Appearance-20261020-1"
    proof.mkdir(parents=True, exist_ok=True)
    backup_dir = proof / "before-assets"
    backup_dir.mkdir(exist_ok=True)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world.get_path_name() == ROOT + "/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07":
        raise RuntimeError("Unreal material preflight/readback failed")
    lib = unreal.MaterialEditingLibrary
    mi = unreal.load_asset(ROOT + "/Materials/MI_Landscape_Instance_YACS")
    if (
        not mi.get_editor_property("parent").get_path_name()
        == ROOT + "/Materials/M_Landscape_YACS.M_Landscape_YACS"
    ):
        raise RuntimeError("Unreal material preflight/readback failed")
    arrays = {
        k: unreal.load_asset(ROOT + "/Materials/TA_" + k + "_Unified")
        for k in ("Colour", "Normal", "Masks")
    }
    actors = [
        a
        for a in unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors()
        if isinstance(a, unreal.LandscapeProxy)
    ]
    if not {a.get_name() for a in actors} == {
        "SaCalobra_Unified_0_0",
        "SaCalobra_Unified_1_0",
        "SaCalobra_Unified_0_1",
        "SaCalobra_Unified_1_1",
    }:
        raise RuntimeError("Unreal material preflight/readback failed")

    def actor_state():
        return {
            a.get_name(): {
                "translation": list(a.get_actor_location().to_tuple()),
                "rotation": list(a.get_actor_rotation().to_tuple()),
                "scale": list(a.get_actor_scale3d().to_tuple()),
                "material": a.get_editor_property("landscape_material").get_path_name(),
                "nanite": bool(a.get_editor_property("enable_nanite")),
            }
            for a in actors
        }

    before_actors = actor_state()
    if not all(
        (
            v["material"] == mi.get_path_name() and (not v["nanite"])
            for v in before_actors.values()
        )
    ):
        raise RuntimeError("Unreal material preflight/readback failed")
    before_scalars = {
        str(n): lib.get_material_instance_scalar_parameter_value(mi, n)
        for n in lib.get_scalar_parameter_names(mi)
    }
    sources = {
        k: [t.get_path_name() for t in a.get_editor_property("source_textures")]
        for k, a in arrays.items()
    }
    for kind, paths in sources.items():
        if not len(paths) == 5:
            raise RuntimeError("Unreal material preflight/readback failed")
        for index, cls in enumerate(("Grass", "Grass2", "Sand", "Cliffs", "Scree")):
            if not paths[index].endswith(f"/T_{cls}_{kind}.T_{cls}_{kind}"):
                raise RuntimeError("Unreal material preflight/readback failed")
    assets = [mi, *arrays.values()]
    for asset in assets:
        path = (
            project / "Content" / (asset.get_path_name().split(".")[0][6:] + ".uasset")
        )
        backup = backup_dir / path.name
        if not backup.exists():
            shutil.copy2(path, backup)
        if not digest(path) == digest(backup):
            raise RuntimeError("Inspect previous tuning receipt before rerunning")
    for name, value in SCALARS.items():
        lib.set_material_instance_scalar_parameter_value(mi, name, value)
    for name, value in COLOUR_ADJUSTMENTS.items():
        arrays["Colour"].set_editor_property(name, value)
    for kind in ("Normal", "Masks"):
        arrays[kind].set_editor_property(
            "mip_gen_settings", unreal.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP
        )
    drains = []
    for _ in range(3):
        drain = json.loads(
            unreal.YacsTextureAuditLibrary.drain_asset_compilation_and_collect_garbage()
        )
        drains.append(drain)
        if drain.get("ok"):
            break
    if not drains[-1].get("ok"):
        raise RuntimeError("Compilation incomplete; no assets saved")
    after_scalars = {
        n: lib.get_material_instance_scalar_parameter_value(mi, n)
        for n in before_scalars
    }
    if not all(
        (
            abs(after_scalars[n] - SCALARS.get(n, v)) < 1e-06
            for n, v in before_scalars.items()
        )
    ):
        raise RuntimeError("Unreal material preflight/readback failed")
    if not actor_state() == before_actors:
        raise RuntimeError("Unreal material preflight/readback failed")
    if not sources == {
        k: [t.get_path_name() for t in a.get_editor_property("source_textures")]
        for k, a in arrays.items()
    }:
        raise RuntimeError("Unreal material preflight/readback failed")
    saved = {}
    for asset in assets:
        if not unreal.EditorAssetLibrary.save_loaded_asset(
            asset, only_if_is_dirty=False
        ):
            raise RuntimeError("Unreal material preflight/readback failed")
        path = (
            project / "Content" / (asset.get_path_name().split(".")[0][6:] + ".uasset")
        )
        saved[str(path.relative_to(project))] = digest(path)
    receipt = {
        "status": "APPEARANCE_SAVED_NATIVE_READBACK_COMPLETE",
        "pid": os.getpid(),
        "world": world.get_path_name(),
        "scalars": after_scalars,
        "colour_adjustments_all_slices": COLOUR_ADJUSTMENTS,
        "sources": sources,
        "actor_state": before_actors,
        "saved": saved,
        "compile_drains": drains,
        "other_scalar_parameters_preserved": True,
        "map_saved": False,
        "terrain_rebuilt": False,
        "computer_use": False,
        "fresh_reopen_verified": False,
        "owner_visual_accepted": False,
    }
    (proof / "saved.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("YACS_L07_APPEARANCE_SAVED", json.dumps(saved))


if __name__ == "__main__":
    main()
