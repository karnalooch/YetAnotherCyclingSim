"""Three owned UE process boundaries for natural20, no implied child exit proof.

The launcher owns process completion and exact-SHA admission. These phases only
write immutable diagnostic receipts, and never save/modify the accepted map.
"""
import hashlib
import json
from pathlib import Path

import unreal

from scripts.ue import sa_calobra_pcg_material_binding as material
from scripts.ue import sa_calobra_pcg_rock_collection as collection
from scripts.ue import sa_calobra_pcg_collection_contact as contact
from scripts.ue.sa_calobra_pcg_terrain_contact import require


ACTIONS = {
    "collection-contact-prepare",
    "collection-contact-measure",
    "collection-contact-review",
}


def identity(path):
    data = Path(path).read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_once(root, relative, value):
    root = Path(root).resolve()
    path = root / relative
    require(path.resolve().is_relative_to(root), "Unsafe phase output")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return {
        "path": relative,
        **identity(path),
    }


def binding_readback(root, head):
    source = root / "proof/material/binding.json"
    binding = json.loads(source.read_text(encoding="utf-8"))
    require(binding["code_sha"] == head, "Fresh session binding HEAD differs")
    material.verify_binding(binding)
    return binding


def prepare(root, output, head, inspect):
    checked = inspect()
    require(
        checked["status"] == "NATIVE_INSPECTION_COMPLETED",
        "Native inspection rejected",
    )
    checked["code_sha"] = head
    phase_inspect = write_once(root, "proof/inspect/inspect-receipt.json", checked)

    binding = material.prepare_binding(root / "forge-source", head)
    material.save_binding(binding)
    phase_binding = write_once(root, "proof/material/binding.json", binding)
    phase_material = write_once(
        root, "proof/material/material-receipt.json",
        {"code_sha": head, "status": "MATERIAL_BINDING_SAVED",
         "binding": binding, "placement": False},
    )

    built = collection.build(root, root / "proof/rock-collection", head, binding)
    require(
        built["status"] == "ROCK_COLLECTION_ASSETS_SAVED"
        and len(built["meshes"]) == 20
        and built["qualified_assets"] == []
        and built["placement"] is False,
        "Incomplete twenty-mesh preparation",
    )
    phase_inventory = {
        "path": "proof/rock-collection/rock-collection-inventory.json",
        **identity(root / "proof/rock-collection/rock-collection-inventory.json"),
    }
    phase_collection = write_once(
        root, "proof/rock-collection/rock-collection-receipt.json",
        {"action": "rock-collection", **built},
    )
    return {
        "code_sha": head,
        "action": "collection-contact-prepare",
        "status": "COLLECTION_CONTACT_PREPARED",
        "phases": {
            "inspect": phase_inspect,
            "binding": phase_binding,
            "material": phase_material,
            "inventory": phase_inventory,
            "collection": phase_collection,
        },
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "terrain_contact": "NOT_RUN",
        "map_saved": False,
    }


def measure(root, output, head):
    binding = binding_readback(root, head)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actor = actors.spawn_actor_from_class(
        unreal.StaticMeshActor, unreal.Vector(), transient=True
    )
    require(actor is not None, "Material readback actor missing")
    try:
        require(
            actor.static_mesh_component.set_static_mesh(
                unreal.load_asset(binding["derived_mesh"])
            ),
            "Missing saved Forge readback mesh",
        )
        bound = material.verify_binding(binding, actor.static_mesh_component)
    finally:
        require(actors.destroy_actor(actor), "Fresh material actor cleanup failed")
    phase_material = write_once(
        root, "proof/collection-contact-measure/material-fresh-phase.json",
        {"code_sha": head, "status": "MATERIAL_BINDING_FRESH_READBACK",
         "readback": bound},
    )

    saved = collection.reload(root, output, head, binding)
    require(
        saved["status"] == "ROCK_COLLECTION_ASSETS_FRESH_RELOAD_VERIFIED"
        and len(saved["meshes"]) == 20,
        "Fresh collection readback rejected",
    )
    phase_collection = write_once(
        root, "proof/collection-contact-measure/collection-fresh-phase.json",
        {"code_sha": head, **saved},
    )

    all_output = root / "proof/collection-contact-all"
    all_output.mkdir(exist_ok=False)
    measured = contact.run_all(root, all_output, head, binding)
    require(
        measured["status"] == "COLLECTION_CONTACT_ALL_MEASURED"
        and len(measured["batches"]) == 10
        and measured["placement"] is False,
        "Complete contact measurement rejected",
    )
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    all_receipt = write_once(
        root, "proof/collection-contact-all/collection-contact-all-receipt.json",
        {"action": "collection-contact-all", **measured,
         "asset_compilation_loading_barrier_completed": True},
    )
    return {
        "code_sha": head,
        "action": "collection-contact-measure",
        "status": "COLLECTION_CONTACT_ALL_MEASURED",
        "contact_execution_mode": "THREE_SESSION_MEASURE",
        "phases": {
            "material_readback": phase_material,
            "collection_readback": phase_collection,
            "contact": all_receipt,
        },
        "placement": False,
        "qualified_assets": [],
        "full_qualification": False,
        "map_saved": False,
        "terrain_modified": False,
        "terrain_contact": "MEASURED_SAMPLED_ONLY",
    }


def review(root, output, head, finish):
    binding = binding_readback(root, head)
    fresh = contact.reload(root, output, head, binding)
    require(
        fresh["status"] == "COLLECTION_CONTACT_FRESH_READBACK"
        and len(fresh["cases"]) == 100
        and len(fresh["meshes"]) == 20,
        "Fresh review aggregate rejected",
    )
    unreal.AutomationLibrary.finish_loading_before_screenshot()
    phase = write_once(
        root, "proof/collection-contact-review/contact-fresh-phase.json",
        {"action": "collection-contact-reload", **fresh,
         "asset_compilation_loading_barrier_completed": True},
    )

    def completed(report):
        report["action"] = "collection-contact-review"
        report["phases"] = {"contact_readback": phase}
        report["contact_execution_mode"] = "THREE_SESSION_MEASURE"
        finish(report)

    return contact.start(root, output, head, binding, completed, grouped_review=True)


def run(root, output, head, action, inspect, finish):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(action in ACTIONS, "Unknown contact session")
    require(output == root / "proof" / action, "Unexpected session output")
    if action == "collection-contact-review":
        return review(root, output, head, finish)
    if action == "collection-contact-prepare":
        report = prepare(root, output, head, inspect)
    else:
        report = measure(root, output, head)
    finish(report)
    return None
