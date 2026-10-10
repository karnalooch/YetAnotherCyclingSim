"""Bounded, reversible #364 asphalt material canary for the accepted road only.

Library entry point for a separately authorized native session; this module
does not launch Unreal, save packages, edit Landscape, or alter road geometry.
Source authentication and actual Unreal execution remain independent proof gates.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

ROAD_LABEL = "YACS_PERSIST_ROAD"
ROAD_VERTICES = 856250
ROAD_TRIANGLES = 1711760
SUPPORT_COUNT = 186
LANDSCAPE_COMPONENT_COUNT = 1024
ASPHALT_DESTINATION = "/Game/Generated/YACS/RoadAsphaltCanary"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_accepted_surface(snapshot):
    """Require the fixed saved checkpoint, not an arbitrary road-like actor."""
    require(snapshot.get("road_count") == 1
            and snapshot.get("support_count") == SUPPORT_COUNT,
            "road/support checkpoint counts differ")
    landscape = snapshot.get("landscape")
    require(isinstance(landscape, dict)
            and landscape.get("component_count") == LANDSCAPE_COMPONENT_COUNT,
            "frozen Landscape component count differs")
    rows = snapshot.get("road_supports")
    require(isinstance(rows, list) and len(rows) == SUPPORT_COUNT + 1,
            "road/support snapshot is incomplete")
    road = [row for row in rows if row.get("label") == ROAD_LABEL]
    require(len(road) == 1, "road material owner is not unique")
    road = road[0]
    require(road.get("vertices") == ROAD_VERTICES
            and road.get("triangles") == ROAD_TRIANGLES,
            "accepted road topology/counts differ")
    slots = road.get("slots")
    require(isinstance(slots, list) and len(slots) == 1
            and isinstance(slots[0], dict)
            and isinstance(slots[0].get("path"), str),
            "accepted road requires exactly one owned material slot")
    require(str(slots[0].get("parent", "")).startswith(
        "/Engine/BasicShapes/BasicShapeMaterial"
    ), "accepted road parent material changed")
    supports = [row.get("label") for row in rows if row.get("label") != ROAD_LABEL]
    expected = {f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(1, SUPPORT_COUNT + 1)}
    require(len(supports) == SUPPORT_COUNT and set(supports) == expected,
            "accepted support actors are missing or ambiguous")
    component = road.get("component")
    bindings = snapshot.get("mesh_material_collision_snapshot")
    require(isinstance(component, str) and isinstance(bindings, list),
            "native binding snapshot is missing")
    matches = [row for row in bindings if row.get("component") == component]
    require(len(matches) == 1 and matches[0].get("materials") == [slots[0]["path"]],
            "road slot and mesh binding disagree")
    return {"component": component, "previous_material": slots[0]["path"]}


def verify_import_receipt(receipt, expected_graph_sha256):
    """Source/scale provenance is mandatory before touching the road slot."""
    require(isinstance(receipt, dict), "material import receipt is missing")
    require(receipt.get("status") == "IMPORTED_UE_REVIEW_PENDING"
            and receipt.get("family") == "aged_mountain_asphalt"
            and receipt.get("variant") == "base"
            and receipt.get("graph_sha256") == expected_graph_sha256
            and receipt.get("tile_metres") == 4
            and receipt.get("normal_convention") == "DirectX"
            and receipt.get("saved") is False
            and receipt.get("geometry_changed") is False
            and receipt.get("landscape_mutated") is False
            and receipt.get("world_semantics_generated") is False,
            "transient asphalt importer contract differs")
    assets = receipt.get("assets")
    require(isinstance(assets, dict)
            and isinstance(assets.get("instance"), str)
            and assets["instance"].startswith(ASPHALT_DESTINATION + "/"),
            "asphalt canary instance is outside its scoped package")


def authenticate_asphalt_replay(
    proof_root: Path,
    expected_receipt_sha256: str,
    expected_source_head: str,
    expected_source_fingerprint: str,
):
    """Recheck both original renders and their pinned receipt before UE import."""
    from scripts.assets.road_material_contract import check_asphalt_replay

    proof_root = Path(proof_root)
    replay = check_asphalt_replay(
        proof_root, expected_receipt_sha256,
        expected_source_head, expected_source_fingerprint,
    )
    require(replay.get("status") == "ROAD_ASPHALT_REPLAY_RECEIPT_VERIFIED"
            and replay.get("retained_two_run_graph_and_map_bytes_equal") is True
            and replay.get("producer_attestation_authenticated") is True
            and replay.get("unreal_verified") is False
            and replay.get("world_mutation") is False,
            "asphalt replay is not an authenticated producer input")
    runs = replay.get("runs")
    require(isinstance(runs, list) and len(runs) == 2
            and runs[0].get("run") == "run-a"
            and runs[1].get("run") == "run-b"
            and runs[0].get("graph_sha256") == runs[1].get("graph_sha256"),
            "asphalt graph identities differ")
    variant = proof_root / "run-a/aged_mountain_asphalt/base"
    return variant, replay


def _expected_live_snapshot(before, during, component_path, material_path):
    """The only permitted consumer mutation is road material slot zero."""
    expected = deepcopy(before)
    for row in expected["road_supports"]:
        if row["label"] == ROAD_LABEL:
            actual = [item for item in during.get("road_supports", [])
                      if item.get("label") == ROAD_LABEL]
            require(len(actual) == 1 and len(actual[0].get("slots", [])) == 1
                    and actual[0]["slots"][0] is not None
                    and actual[0]["slots"][0].get("path") == material_path,
                    "asphalt road slot readback failed")
            expected_slot = actual[0]["slots"][0]
            expected["road_supports"] = [
                {**item, "slots": [expected_slot]} if item["label"] == ROAD_LABEL else item
                for item in expected["road_supports"]
            ]
            break
    else:
        raise ValueError("saved road owner disappeared")
    found = 0
    for row in expected["mesh_material_collision_snapshot"]:
        if row["component"] == component_path:
            require(len(row["materials"]) == 1,
                    "road mesh binding slot count changed")
            row["materials"] = [material_path]
            found += 1
    require(found == 1, "road mesh component binding is ambiguous")
    require(during == expected,
            "material canary changed geometry, supports, Landscape or other bindings")


def try_road_only_material(snapshot, actors, asphalt_instance, import_receipt):
    """Temporarily bind one road slot and prove full snapshot rollback.

    snapshot: native read-only inventory callable from #364 baseline reader.
    actors: exact saved scene actors. No save, no Landscape edit, no support edits.
    """
    before = snapshot()
    binding = verify_accepted_surface(before)
    require(asphalt_instance is not None, "native asphalt instance is missing")
    path = asphalt_instance.get_path_name()
    require(path == import_receipt["assets"]["instance"],
            "material instance differs from its importer receipt")
    roads = [actor for actor in actors if actor.get_actor_label() == ROAD_LABEL]
    require(len(roads) == 1, "road Actor lookup is ambiguous")
    comp = roads[0].get_dynamic_mesh_component()
    require(comp.get_path_name() == binding["component"]
            and comp.get_num_materials() == 1,
            "live road component differs from frozen inventory")
    original = comp.get_material(0)
    require(original is not None
            and original.get_path_name() == binding["previous_material"],
            "live road material differs before canary")
    try:
        comp.set_material(0, asphalt_instance)
        require(comp.get_material(0).get_path_name() == path,
                "transient asphalt assignment readback failed")
        during = snapshot()
        _expected_live_snapshot(before, during, binding["component"], path)
    finally:
        # Fail closed even if assignment/readback/snapshot fails halfway through.
        comp.set_material(0, original)
        require(comp.get_material(0) is not None
                and comp.get_material(0).get_path_name() == binding["previous_material"],
                "cannot restore original road material")
        require(snapshot() == before, "road canary rollback snapshot differs")
    return {
        "status": "ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK",
        "road_label": ROAD_LABEL,
        "road_component": binding["component"],
        "previous_material": binding["previous_material"],
        "canary_material": path,
        "road_slot_readback": True,
        "all_186_supports_unchanged": True,
        "landscape_1024_components_unchanged": True,
        "consumer_snapshot_restored": True,
        "full_geometry_hash_verified": False,
        "saved_consumer_verified": False,
        "material_authoring_admitted": False,
        "owner_visual_status": "PENDING_FINAL_M3",
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }


def candidate_on_loaded_accepted_map(
    api, proof_root, receipt_sha256, source_head, source_fingerprint
):
    """Native-session entry point after the independently authenticated baseline.

    The caller owns editor isolation, source SHA, stage/asset checks and evidence
    persistence. Do not invoke from an open interactive editor or arbitrary map.
    """
    from scripts.ue import import_material_forge_variant as forge
    from scripts.ue import read_road_material_baseline as baseline
    from scripts.ue import sa_calobra_whole_map_prep as prep
    from scripts.ci import official_mcp_bob_session as session

    session._assert_isolated_root()
    variant, replay = authenticate_asphalt_replay(
        proof_root, receipt_sha256, source_head, source_fingerprint
    )
    def snapshot():
        return baseline.native_inventory(api, prep, session.operation.MAP_PACKAGE)

    before = snapshot()
    verify_accepted_surface(before)
    instance, imported = forge.import_variant(
        variant, destination_root=ASPHALT_DESTINATION, save_assets=False
    )
    verify_import_receipt(imported, replay["runs"][0]["graph_sha256"])
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    result = try_road_only_material(snapshot, actors, instance, imported)
    result["source_head"] = replay["source_head"]
    result["source_fingerprint"] = replay["source_fingerprint"]
    result["source_receipt_sha256"] = replay["authenticated_source_receipt"]["sha256"]
    result["graph_sha256"] = replay["runs"][0]["graph_sha256"]
    result["import_receipt"] = imported
    return result
