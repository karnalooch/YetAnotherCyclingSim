"""Owned isolated #365 native diagnostics; never Sa Calobra placement admission.

The launcher stages an empty content-only project and authenticated dependencies.
Inspect reads the installed Epic graph skill and reflected APIs before authoring.
Native output remains local diagnostic evidence, not a Proof Broker receipt.
"""

import hashlib
import json
import os
from pathlib import Path
import traceback

import unreal


OUTPUT = Path(os.environ["YACS_PCG_PROBE_OUTPUT"])
ACTION = os.environ["YACS_PCG_PROBE_ACTION"]
HEAD = os.environ["YACS_PCG_PROBE_EXPECTED_HEAD"]


def write_new(name, value):
    path = OUTPUT / name
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2))


def vector(value):
    return [float(value.x), float(value.y), float(value.z)]


def inspect_mesh(path):
    mesh = unreal.load_asset(path)
    if not isinstance(mesh, unreal.StaticMesh):
        raise RuntimeError("Expected native StaticMesh: " + path)
    bounds = mesh.get_bounds()
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    import_data = mesh.get_editor_property("asset_import_data")
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    options = unreal.AssetRegistryDependencyOptions(
        include_soft_package_references=True,
        include_hard_package_references=True,
        include_searchable_names=False,
        include_soft_management_references=False,
        include_hard_management_references=False,
    )
    package = mesh.get_path_name().split(".")[0]
    dependencies = [str(item) for item in registry.get_dependencies(package, options)]
    return {
        "object_path": mesh.get_path_name(),
        "class": mesh.get_class().get_name(),
        "bounds_origin_cm": vector(bounds.origin),
        "bounds_extent_cm": vector(bounds.box_extent),
        "sphere_radius_cm": float(bounds.sphere_radius),
        "lod_count": mesh.get_num_lods(),
        "lod_vertices": [
            subsystem.get_number_verts(mesh, lod) for lod in range(mesh.get_num_lods())
        ],
        "lod_uv_channels": [
            subsystem.get_num_uv_channels(mesh, lod)
            for lod in range(mesh.get_num_lods())
        ],
        "collision_complexity": str(subsystem.get_collision_complexity(mesh)),
        "import_filenames": list(import_data.extract_filenames())
        if import_data
        else [],
        "package_dependencies": dependencies,
        "missing_game_dependencies": [
            item
            for item in dependencies
            if item.startswith("/Game/")
            and not unreal.EditorAssetLibrary.does_asset_exist(item)
        ],
        "material_slots": [
            str(slot.material_slot_name) for slot in mesh.static_materials
        ],
        "material_objects": [
            slot.material_interface.get_path_name() if slot.material_interface else None
            for slot in mesh.static_materials
        ],
        "qualification_status": "PENDING",
        "source_provenance": "NOT_ADMITTED",
    }


def inspect():
    # Read through Epic's reflected skill API; do not parse cooked/uasset bytes.
    skill_class = unreal.load_class(None, "/Script/ToolsetRegistry.AgentSkillToolset")
    if not skill_class:
        raise RuntimeError("Installed AgentSkillToolset class is unavailable")
    registry = unreal.ToolsetRegistry
    if not registry.is_toolset_class_registered(skill_class):
        registry.register_toolset_class(skill_class)
    schema = json.loads(registry.get_toolset_json_schema(skill_class))
    write_new("installed-skill-tool-schema.json", schema)

    def call_skill(name, arguments):
        # AICallable functions are not Python methods. Use the installed registry
        # wrapper; these two native skill readers are synchronous. A pending or
        # failed result is a hard diagnostic failure, never fabricated output.
        result = registry.execute_tool(schema["name"], name, json.dumps(arguments))
        if not result.get_editor_property("bIsComplete"):
            raise RuntimeError("Native skill reader did not complete synchronously")
        if result.error:
            raise RuntimeError(result.error)
        return json.loads(result.value)

    skills = call_skill("ListSkills", {})
    selected = [str(path) for path in skills if "Skill_PCGGraphGeneration" in str(path)]
    if len(selected) != 1:
        raise RuntimeError("Expected one installed PCG graph skill: " + repr(selected))
    details = call_skill("GetSkills", {"SkillPaths": selected})
    prompts = {}
    for path, detail in details.items():
        keys = [key for key in detail if key.casefold() == "instructions"]
        if len(keys) != 1 or not isinstance(detail[keys[0]], str):
            raise RuntimeError("Malformed installed skill details")
        prompts[str(path)] = detail[keys[0]]
    if len(prompts) != 1 or not all(prompts.values()):
        raise RuntimeError("PCG graph skill did not return instructions")
    write_new("installed-pcg-skill.json", prompts)
    types = (
        "PCGCreatePointsSettings",
        "PCGPoint",
        "PCGGraph",
        "PCGGraphFactory",
        "PCGComponent",
        "PCGVolume",
        "PCGPointData",
        "PCGDataCollection",
        "PCGStaticMeshSpawnerSettings",
        "PCGExSampleNearestSurfaceSettings",
        "AgentSkillToolset",
        "PCGToolset",
        "StaticMeshEditorSubsystem",
        "EditorActorSubsystem",
        "SystemLibrary",
    )
    inventory = {
        name: sorted(
            item for item in dir(getattr(unreal, name)) if not item.startswith("_")
        )
        if hasattr(unreal, name)
        else None
        for name in types
    }
    write_new("reflected-pcg-api.json", inventory)
    meshes = [inspect_mesh("/Engine/BasicShapes/Cube.Cube")]
    boulder = "/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder"
    if unreal.EditorAssetLibrary.does_asset_exist(boulder):
        meshes.append(inspect_mesh(boulder))
    write_new("native-mesh-inventory.json", meshes)
    return {
        "status": "NATIVE_INSPECTION_COMPLETED",
        "skill_paths": selected,
        "skill_sha256": hashlib.sha256(
            json.dumps(prompts, sort_keys=True).encode()
        ).hexdigest(),
        "mesh_count": len(meshes),
    }


def main():
    receipt = {
        "schema_version": 1,
        "issue": 365,
        "code_sha": HEAD,
        "action": ACTION,
        "placement": False,
        "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
        "native_build": "NOT_RUN_PREBUILT_DEPENDENCY",
        "terrain_contact": "NOT_RUN",
        "qualified_assets": [],
        "owner_visual_status": "PENDING_FINAL_M3",
        "performance_pass": False,
        "status": "FAILED",
    }
    try:
        if ACTION != "inspect":
            raise RuntimeError(
                "Graph authoring requires reviewed installed skill/API inspection"
            )
        receipt.update(inspect())
    except Exception:
        receipt["error"] = traceback.format_exc()
        unreal.log_error(receipt["error"])
    finally:
        write_new(ACTION + "-receipt.json", receipt)
        unreal.SystemLibrary.quit_editor()


main()
