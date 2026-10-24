"""Repair L07 black global-colour modulation in the currently open editor.

Issue #365 / M3. Uses existing Pegasus Global Brightness endpoint (detail Value),
not a replacement shader. Saves only the existing material instance; its other
live settings are preserved. Never loads/saves a level or changes terrain.
Native fixed-camera A/B must precede use. Original disk MI is backed up locally.
"""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = "/Game/Generated/YACS/Lesson07_Unified"
INSTANCE = ROOT + "/Materials/MI_Landscape_Instance_YACS"
PARAMETER = "Global Brightness"


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
    proof = project / "Saved/RuntimeProof/Lesson07BlackPatches-20261020-1"
    proof.mkdir(parents=True, exist_ok=True)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if not world.get_path_name() == ROOT + "/L_SaCalobra_Lesson07.L_SaCalobra_Lesson07":
        raise RuntimeError("Unreal material preflight/readback failed")
    material = unreal.load_asset(INSTANCE)
    if (
        not material.get_editor_property("parent").get_path_name()
        == ROOT + "/Materials/M_Landscape_YACS.M_Landscape_YACS"
    ):
        raise RuntimeError("Unreal material preflight/readback failed")
    lib = unreal.MaterialEditingLibrary

    def parameters():
        result = {}
        for kind in ("scalar", "vector", "texture", "static_switch"):
            values = {}
            for name in getattr(lib, "get_" + kind + "_parameter_names")(material):
                value = getattr(
                    lib, "get_material_instance_" + kind + "_parameter_value"
                )(material, name)
                if isinstance(value, unreal.LinearColor):
                    value = [value.r, value.g, value.b, value.a]
                elif isinstance(value, unreal.Object):
                    value = value.get_path_name()
                values[str(name)] = value
            result[kind] = values
        return result

    def actors():
        result = {}
        for actor in unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors():
            if isinstance(actor, unreal.LandscapeProxy):
                transform = actor.get_actor_transform()
                result[actor.get_name()] = {
                    "location": list(transform.translation.to_tuple()),
                    "rotation": list(transform.rotation.to_tuple()),
                    "scale": list(transform.scale3d.to_tuple()),
                    "material": actor.get_editor_property(
                        "landscape_material"
                    ).get_path_name(),
                }
        return result

    before = parameters()
    if before["scalar"][PARAMETER] not in (0.0, 0.5):
        raise RuntimeError("Unreal material preflight/readback failed")
    before_actors = actors()
    if not set(before_actors) == {
        "SaCalobra_Unified_0_0",
        "SaCalobra_Unified_1_0",
        "SaCalobra_Unified_0_1",
        "SaCalobra_Unified_1_1",
    }:
        raise RuntimeError("Unreal material preflight/readback failed")
    if not all(
        (
            v["material"] == INSTANCE + ".MI_Landscape_Instance_YACS"
            for v in before_actors.values()
        )
    ):
        raise RuntimeError("Unreal material preflight/readback failed")
    asset = (
        project
        / "Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset"
    )
    backup = proof / "MI_Landscape_Instance_YACS.before.uasset"
    if not not backup.exists():
        raise RuntimeError("Inspect existing repair receipt before repeating")
    shutil.copy2(asset, backup)
    if not digest(asset) == digest(backup):
        raise RuntimeError("Unreal material preflight/readback failed")
    (proof / "live-parameters-before-save.json").write_text(
        json.dumps(before, indent=2), encoding="utf-8"
    )
    lib.set_material_instance_scalar_parameter_value(material, PARAMETER, 0.0)
    after = parameters()
    expected = json.loads(json.dumps(before))
    expected["scalar"][PARAMETER] = 0.0
    if not after == expected:
        raise RuntimeError("Unexpected other material parameter change")
    if not actors() == before_actors:
        raise RuntimeError("Landscape state changed")
    if not unreal.EditorAssetLibrary.save_loaded_asset(
        material, only_if_is_dirty=False
    ):
        raise RuntimeError("Unreal material preflight/readback failed")
    if not parameters() == expected:
        raise RuntimeError("Unreal material preflight/readback failed")
    receipt = {
        "status": "GLOBAL_BRIGHTNESS_REPAIRED_SAVED_NATIVE_READBACK",
        "world": world.get_path_name(),
        "parameter": PARAMETER,
        "original_observed_value": before["scalar"][PARAMETER],
        "final_value": 0.0,
        "other_live_parameters_preserved": True,
        "landscapes_unchanged": True,
        "saved_asset": INSTANCE,
        "backup_sha256": digest(backup),
        "saved_asset_sha256": digest(asset),
        "map_saved": False,
        "terrain_rebuilt": False,
        "computer_use": False,
        "editor_closed": False,
        "fresh_reopen_verified": False,
    }
    (proof / "repair.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("YACS_L07_GLOBAL_COLOUR_REPAIR_SAVED", receipt["saved_asset_sha256"])


if __name__ == "__main__":
    main()
