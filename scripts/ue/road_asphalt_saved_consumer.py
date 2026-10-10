"""Author a new road/shoulder material map and verify a separate UE process.

Action prepare is the sole mutation authority: a new derived map, retained
Material Forge asphalt and source-owned gravel across the current network. Reload is
read-only and never repairs or re-saves any binding. The accepted #363 map,
Landscape, source road geometry, route and road physics are immutable.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.manage_local_workspace import load_workspace  # noqa: E402
from scripts.ci import official_mcp_bob_session as session  # noqa: E402
from scripts.assets import road_material_contract as asphalt_contract  # noqa: E402
from scripts.ue import road_asphalt_source_preflight as asphalt_source  # noqa: E402
from scripts.ue import road_asphalt_slot_canary as canary  # noqa: E402
from scripts.ue import read_road_material_baseline as baseline  # noqa: E402
from scripts.ue import sa_calobra_whole_map_prep as prep  # noqa: E402
from scripts.ue import road_shoulder_network as shoulder  # noqa: E402
from scripts.ue import road_shoulder_sources as shoulder_sources  # noqa: E402
from scripts.ue import road_shoulder_material as shoulder_material  # noqa: E402

MAP = "/Game/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview"
PREFIX = "Content/Generated/YACS/RoadAsphaltConsumer/"
PACKAGE = "/Game/Generated/YACS/RoadAsphaltConsumer"
MAP_FILE = "Content/" + MAP.removeprefix("/Game/") + ".umap"
OUTPUT_BASE = "Saved/RuntimeProof/RoadMaterialBaseline/"
RETAINED_BASE = "road-materials/saved-consumers"
MANIFEST = "road-asphalt-saved-manifest.json"
PREPARED = "road-asphalt-saved-prepared.json"
RELOADED = "road-asphalt-saved-reloaded.json"
PROFILE_DIAGNOSTIC = "road-network-profile-diagnostic.json"
# 186 source owners with up to 74,028 selected IDs need about 1.99 MiB before
# material/API/package metadata. Keep one copy of each source witness and a
# bounded 4 MiB manifest; the native baseline remains a separately hashed file.
JSON_LIMIT = 4 * 1024 * 1024
MAX_ASSET_BYTES = 512 * 1024 * 1024
MAX_ASSET_COUNT = 64
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
SIDECARS = (".umap", ".uasset", ".uexp", ".ubulk", ".uptnl", ".m.ubulk")
TEXTURES = {
    "BaseColorTex": "BaseColor",
    "NormalTex": "Normal_DX",
    "ORMTex": "ORM",
    "DetailMasksTex": "DetailMasks",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def normalized(value, map_package):
    """Only normalize the owning map identity, never actor geometry or materials."""
    if isinstance(value, str):
        basename = map_package.rsplit("/", 1)[-1]
        return value.replace(map_package + "." + basename, "<scene>.<world>").replace(
            map_package, "<scene>"
        )
    if isinstance(value, list):
        return [normalized(item, map_package) for item in value]
    if isinstance(value, tuple):
        return [normalized(item, map_package) for item in value]
    if isinstance(value, dict):
        return {
            normalized(k, map_package): normalized(v, map_package)
            for k, v in value.items()
        }
    return value


def inventory_digest(snapshot):
    """Hash native scene semantics in the exact JSON type domain of prior receipts.

    Unreal Python inventory has a sorted list of actor *tuples*; the authentic
    retained baseline decodes those same entries as JSON *lists*. Never require
    a Python container-type equality across process/JSON boundaries. Serialize
    every field under the identical canonical schema and compare all bytes.
    """
    raw = json.dumps(
        snapshot, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def expected_saved_inventory(original, saved, material_path, *, observed_map_package,
                             shoulder_receipt=None):
    """Audit every field using the actual owning map in this Editor phase.

    Before SaveMap both snapshots belong to the frozen source map. Only after
    SaveMap (and in fresh reload) may the observed actor paths belong to the
    new derived map. Never alias arbitrary map packages or ignore actor paths.
    """
    source_map = session.operation.MAP_PACKAGE
    require(original.get("map_package") == source_map,
            "Native baseline belongs to another source map")
    require(
        observed_map_package in (source_map, MAP)
        and saved.get("map_package") == observed_map_package,
        "Observed actor map identity differs from the approved save phase",
    )
    old = normalized(original, source_map)
    actual = normalized(saved, observed_map_package)
    road = canary.verify_accepted_surface(old)
    if shoulder_receipt is not None:
        owners = shoulder_receipt.get("owners", [])
        require(shoulder_receipt.get("schema_version") == 2
                and shoulder_receipt.get("support_count") == shoulder_sources.OWNER_COUNT
                and shoulder_receipt.get("material_target_count") == shoulder_sources.OWNER_COUNT - 1
                and isinstance(owners, list) and len(owners) == shoulder_sources.OWNER_COUNT
                and [row.get("support_label") for row in owners]
                == [f"YACS_PERSIST_SUPPORT_{i:03d}" for i in range(shoulder_sources.OWNER_COUNT)]
                and sum(row.get("material_target") is True for row in owners)
                == shoulder_sources.OWNER_COUNT - 1
                and sum(row.get("material_target") is False and row.get("kind") == "parapet"
                        for row in owners) == 1,
                "Shoulder source coverage is incomplete or duplicated")
        assets = shoulder_receipt["material"]["assets"]
        require(assets == shoulder_material.asset_paths(shoulder_material.DESTINATION_ROOT),
                "Shoulder material escaped its bounded package")
        for owner in owners:
            label = owner["support_label"]
            original_material = owner["source"]["original_material_path"]
            matches = [row for row in old["road_supports"] if row["label"] == label]
            require(len(matches) == 1 and len(matches[0]["slots"]) == 1
                    and matches[0]["slots"][0]["path"] == original_material,
                    "Shoulder source slot ownership differs: " + label)
            bindings = [row for row in old["mesh_material_collision_snapshot"]
                        if row["component"] == matches[0]["component"]]
            require(len(bindings) == 1 and bindings[0]["materials"] == [original_material],
                    "Shoulder material component is missing or ambiguous: " + label)
            if owner["material_target"]:
                matches[0]["slots"].append({"path": assets["instance"],
                    "parent": assets["master"], "class": "MaterialInstanceConstant",
                    "effective_color": None})
                bindings[0]["materials"].append(assets["instance"])
    canary._expected_live_snapshot(old, actual, road["component"], material_path)
    return inventory_digest(actual)


def verified_staging(exact_sha, staging_hash):
    staging_path, staging_id, staging, map_row = baseline.authenticated_preparation(
        session, exact_sha, staging_hash
    )
    require(staging.get("source_sha256") == session._sources(exact_sha),
            "Original consumer staging script bytes changed")
    rows = staging["consumer_assets"] + staging["source_dependencies"]
    session._verify_rows(ROOT, rows)
    session._assert_package_members(ROOT, rows)
    return staging_path, staging_id, staging, map_row, rows


def verified_predecessors(proof_root, exact_sha, staging_hash):
    for name, status in (
        ("road-material-baseline.json", "ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE"),
        ("road-asphalt-canary.json", "ROAD_ASPHALT_TRANSIENT_CANARY_ROLLED_BACK"),
    ):
        value = session._read_json(
            session._safe_path(proof_root, name), limit=JSON_LIMIT
        )
        require(value.get("status") == status and value.get("exact_sha") == exact_sha,
                "Prior exact-HEAD native baseline/asphalt canary is missing: " + name)
    prior = session._read_json(
        session._safe_path(proof_root, "road-material-baseline.json"), limit=JSON_LIMIT
    )
    trial = session._read_json(
        session._safe_path(proof_root, "road-asphalt-canary.json"), limit=JSON_LIMIT
    )
    require(
        prior["staging_receipt"]["sha256"] == staging_hash
        and prior["saved_asset_bytes_unchanged"] is True
        and prior["pre_post_inventory_equal"] is True
        and trial["staging_sha256"] == staging_hash
        and trial["native_material_bind_and_rollback_verified"] is True
        and trial["all_source_assets_unchanged"] is True
        and trial["map_saved"] is False,
        "Original native read and rolled-back canary were not both verified",
    )
    return prior, trial


def proof_paths():
    exact_sha = os.environ.get("YACS_ROAD_MATERIAL_EXPECTED_HEAD", "")
    staged_sha = os.environ.get("YACS_ROAD_MATERIAL_PREPARATION_SHA256", "")
    token = os.environ.get("YACS_ROAD_SAVED_RUN_TOKEN", "")
    require(re.fullmatch(r"[0-9a-f]{40}", exact_sha), "Exact head is required")
    require(re.fullmatch(r"[0-9a-f]{64}", staged_sha), "Original stage hash is required")
    require(re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,5}", token),
            "Run/attempt token is required")
    proof = session._safe_path(ROOT, OUTPUT_BASE + token)
    require(proof.is_dir(), "Missing original native proof directory")
    work = Path(load_workspace()["work"])
    require(work.is_dir(), "Missing canonical YACS work directory")
    retained = session._safe_path(work, RETAINED_BASE + "/" + exact_sha + "/" + token)
    return exact_sha, staged_sha, token, proof, retained


def write_once(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    require(0 < len(raw) <= JSON_LIMIT, "Saved asphalt receipt exceeds byte cap")
    session._safe_path(path.parent, path.name)
    with path.open("xb") as handle:
        handle.write(raw)
    return session._identity(path, JSON_LIMIT)


def verified_manifest_identity(proof, retained):
    """The downloadable evidence is byte-identical to the retained manifest."""
    identity = session._identity(session._safe_path(retained, MANIFEST), JSON_LIMIT)
    require(session._identity(session._safe_path(proof, MANIFEST), JSON_LIMIT) == identity,
            "Downloadable material manifest differs from retained native evidence")
    return identity


def write_profile_diagnostic(proof, retained, source_plan):
    """Retain source-only profiles after the caller authenticates every owner."""
    report = shoulder_sources.network_profile_report(source_plan)
    raw = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    limit = shoulder_sources.PROFILE_REPORT_MAX_BYTES
    require(0 < len(raw) <= limit, "Frozen network profile exceeds its separate byte cap")
    expected = {"file": PROFILE_DIAGNOSTIC, "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw)}
    for folder in (retained, proof):
        path = session._safe_path(folder, PROFILE_DIAGNOSTIC)
        with path.open("xb") as stream:
            stream.write(raw)
    return verified_profile_identity(proof, retained, expected)


def verified_profile_identity(proof, retained, expected):
    """Hash both fixed-name copies; reopening never regenerates the evidence."""
    limit = shoulder_sources.PROFILE_REPORT_MAX_BYTES
    require(isinstance(expected, dict)
            and set(expected) == {"file", "sha256", "size_bytes"}
            and expected.get("file") == PROFILE_DIAGNOSTIC
            and isinstance(expected.get("sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", expected["sha256"])
            and type(expected.get("size_bytes")) is int
            and 0 < expected["size_bytes"] <= limit,
            "Frozen network profile identity is outside its fixed file/byte contract")
    for folder in (retained, proof):
        observed = session._identity(session._safe_path(folder, PROFILE_DIAGNOSTIC), limit)
        require({"file": PROFILE_DIAGNOSTIC, **observed} == expected,
                "Frozen network profile diagnostic bytes changed")
    return expected


def native_world(api, package):
    require(api.EditorLoadingAndSavingUtils.load_map(package) is not None,
            "Expected Sa Calobra map did not load: " + package)
    baseline.dirty_packages(api)


def active_map_after_save(api):
    """Observe the live Editor world; SaveMap need not change its package name.

    This is a read-only identity check. The separately launched fresh reload
    must later verify the durable derived map bytes and every saved binding.
    """
    world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
    require(world is not None, "Saved road Editor world disappeared")
    owner = world.get_path_name().split(".")[0]
    require(
        owner in (session.operation.MAP_PACKAGE, MAP),
        "SaveMap left an unapproved map loaded",
    )
    return owner


def verify_material_instance(api, instance_path, master_path, paths, *, expected_response=None):
    inst = api.load_asset(instance_path)
    require(inst is not None and isinstance(inst, api.MaterialInstanceConstant),
            "Saved asphalt instance is missing")
    parent = inst.get_editor_property("parent")
    require(parent is not None and parent.get_path_name() == master_path,
            "Saved asphalt master hierarchy changed")
    library = api.MaterialEditingLibrary
    association = api.MaterialParameterAssociation.GLOBAL_PARAMETER
    tile = library.get_material_instance_scalar_parameter_value(
        inst, "TileSizeCm", association
    )
    require(abs(float(tile) - 400.0) <= 0.001,
            "Saved asphalt metric projection is not 400 cm")
    for parameter, channel in TEXTURES.items():
        texture = library.get_material_instance_texture_parameter_value(
            inst, parameter, association
        )
        require(
            texture is not None and texture.get_path_name() == paths[channel],
            "Saved asphalt texture binding differs: " + parameter,
        )
        if channel == "Normal_DX":
            require(
                texture.get_editor_property("srgb") is False
                and texture.get_editor_property("flip_green_channel") is False
                and texture.get_editor_property("compression_settings")
                == api.TextureCompressionSettings.TC_NORMALMAP,
                "Saved native DirectX normal is incorrectly imported",
            )
    from scripts.ue import import_material_forge_variant as forge

    response = forge.verify_dry_asphalt_response(inst, {
        "instance": instance_path, "master": master_path, "textures": paths,
    })
    require(expected_response is None or response == expected_response,
            "Saved dry asphalt material response changed")
    return inst


def verify_road_mesh(api, expected):
    """Read every road position/index/corner attribute/ID after save or GPU."""
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    road = baseline.road_support_actors(actors)[0]
    current = shoulder.inspect_mesh(api, road.get_dynamic_mesh_component())["summary"]
    require(current == expected, "Saved road full native buffers changed")
    return current


def produced_files():
    folder = session._safe_path(ROOT, PREFIX.removesuffix("/"))
    require(folder.is_dir(), "New derived material asset package root is missing")
    rows, total = [], 0
    for path in sorted(folder.rglob("*")):
        relative = path.relative_to(ROOT).as_posix()
        checked = session._safe_path(ROOT, relative)
        # The saved material family has nested directories. Audit every
        # directory for reparse aliases, but inventory/hash only actual package
        # files. Never skip an unexpected regular file or link.
        if checked.is_dir():
            require(not checked.is_symlink(), "Generated package directory is an alias")
            continue
        require(
            checked.is_file() and not checked.is_symlink(),
            "Unexpected package family member",
        )
        require(
            any(checked.name.endswith(suffix) for suffix in SIDECARS),
            "Unapproved generated road-material file type",
        )
        identity = session._identity(checked, MAX_ASSET_BYTES)
        total += identity["size_bytes"]
        require(total <= MAX_TOTAL_BYTES and len(rows) < MAX_ASSET_COUNT,
                "Generated material package count or byte budget exceeded")
        rows.append({"path": relative, **identity})
    require(
        any(row["path"] == MAP_FILE for row in rows)
        and sum(row["path"].endswith(".uasset") for row in rows) >= 6,
        "Missing road map or six material packages",
    )
    return rows


def retain_files(retained, rows):
    require(not retained.exists(), "Cannot overwrite an existing saved-consumer proof")
    session._safe_path(retained.parent, retained.name)
    retained.mkdir(parents=True, exist_ok=False)
    results = []
    for row in rows:
        relative = "packages/" + row["path"]
        destination = session._safe_path(retained, relative)
        require(not destination.exists(), "Persistent road asset collision")
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = session._safe_path(ROOT, row["path"])
        require(
            session._identity(source, MAX_ASSET_BYTES)
            == {k: row[k] for k in ("sha256", "size_bytes")},
            "Generated source changed before durable retention",
        )
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer, 4 * 1024 * 1024)
        require(
            session._identity(destination, MAX_ASSET_BYTES)
            == {k: row[k] for k in ("sha256", "size_bytes")},
            "Durable saved-consumer copy differs",
        )
        results.append({**row, "storage": relative})
    return results


def verify_retained_files(retained, rows):
    require(isinstance(rows, list) and 7 <= len(rows) <= MAX_ASSET_COUNT,
            "Invalid derived package count")
    names, total = set(), 0
    for row in rows:
        require(
            isinstance(row, dict)
            and set(row) == {"path", "sha256", "size_bytes", "storage"}
            and row["path"].startswith(PREFIX)
            and row["storage"] == "packages/" + row["path"]
            and row["path"] not in names,
            "Invalid or duplicate retained package path",
        )
        names.add(row["path"])
        total += row["size_bytes"]
        require(total <= MAX_TOTAL_BYTES, "Retained package byte budget exceeded")
        expected = {key: row[key] for key in ("sha256", "size_bytes")}
        for base, name in ((ROOT, row["path"]), (retained, row["storage"])):
            actual = session._identity(
                session._safe_path(base, name), MAX_ASSET_BYTES
            )
            require(actual == expected, "Saved road material package differs: " + name)


def prepare(api, proof, retained, exact_sha, staging_sha, original, rows, *, source_dependencies):
    require(not (ROOT / MAP_FILE).exists(), "Existing road-only saved map cannot be overwritten")
    require(not (ROOT / PREFIX).exists(), "Existing asphalt consumer package tree")
    before = original["native_inventory"]
    native_world(api, session.operation.MAP_PACKAGE)
    inventory_before = baseline.native_inventory(
        api, prep, session.operation.MAP_PACKAGE
    )
    require(
        inventory_digest(inventory_before) == inventory_digest(before),
        "Accepted full scene JSON differs from authenticated native baseline",
    )
    canary.verify_accepted_surface(inventory_before)
    baseline.native_projection(api)
    source_before = asphalt_source.verify_retained_replay()
    from scripts.ue import import_material_forge_variant as forge

    instance, receipt = forge.import_variant(
        asphalt_source.source_root() / "run-a" / asphalt_contract.FAMILY / asphalt_contract.VARIANT,
        destination_root=PACKAGE,
        save_assets=True,
    )
    require(
        receipt.get("status") == "IMPORTED_UE_REVIEW_PENDING"
        and receipt.get("family") == asphalt_contract.FAMILY
        and receipt.get("variant") == asphalt_contract.VARIANT
        and receipt.get("saved") is True
        and receipt.get("graph_sha256") == asphalt_source.GRAPH_SHA256
        and receipt.get("tile_metres") == 4
        and receipt.get("normal_convention") == "DirectX"
        and receipt.get("landscape_mutated") is False
        and receipt.get("geometry_changed") is False,
        "Saved Material Forge provenance and metric contract differ",
    )
    instance_path = receipt["assets"]["instance"]
    require(instance_path.startswith(PACKAGE + "/"), "Road instance escaped its package")
    verify_material_instance(
        api, instance_path, receipt["assets"]["master"],
        receipt["assets"]["textures"], expected_response=receipt["dry_asphalt_response"],
    )
    actors = list(api.get_editor_subsystem(api.EditorActorSubsystem).get_all_level_actors())
    road = baseline.road_support_actors(actors)[0]
    require(road.get_actor_label() == canary.ROAD_LABEL, "Expected one accepted road")
    component = road.get_dynamic_mesh_component()
    old_material = component.get_material(0)
    require(old_material is not None, "Frozen road material is missing")
    old_binding = canary.verify_accepted_surface(
        normalized(inventory_before, session.operation.MAP_PACKAGE)
    )
    require(component.get_path_name() == old_binding["component"].replace(
        "<scene>", session.operation.MAP_PACKAGE
    ) or component.get_path_name() == inventory_before["road_supports"][0]["component"],
            "Road component ownership differs")
    road_mesh_before = shoulder.inspect_mesh(api, component)["summary"]
    source_plan = shoulder_sources.load_sources()
    gravel, gravel_receipt = shoulder_material.create_material(
        api, shoulder_material.DESTINATION_ROOT, source_dependencies)
    shoulder_material.verify_material(api, gravel_receipt, source_dependencies)
    for path in gravel_receipt["assets"].values():
        asset = api.load_asset(path)
        require(asset is not None and api.EditorAssetLibrary.save_loaded_asset(
            asset, only_if_is_dirty=False), "Derived shoulder material save failed")
    rollback_state = None
    saved = False
    try:
        component.set_material(0, instance)
        require(
            component.get_material(0).get_path_name() == instance_path,
            "Saved road material assignment readback differs",
        )
        shoulder_receipt, rollback_state = shoulder.prepare(
            api, actors, source_plan, gravel, gravel_receipt
        )
        require(shoulder.inspect_mesh(api, component)["summary"] == road_mesh_before,
                "Road geometry, corner attributes or triangle IDs changed during material assignment")
        live = baseline.native_inventory(api, prep, session.operation.MAP_PACKAGE)
        expected_saved_inventory(
            inventory_before, live, instance_path,
            observed_map_package=session.operation.MAP_PACKAGE,
            shoulder_receipt=shoulder_receipt,
        )
        world = api.get_editor_subsystem(api.UnrealEditorSubsystem).get_editor_world()
        require(api.EditorLoadingAndSavingUtils.save_map(world, MAP),
                "New material-only derived map save failed")
        saved = True
        require((ROOT / MAP_FILE).is_file(), "New derived map file was not saved")
        observed_map = active_map_after_save(api)
        require(shoulder.inspect_mesh(api, component)["summary"] == road_mesh_before,
                "Road full buffers changed during derived map save")
        after = baseline.native_inventory(api, prep, observed_map)
        inventory_hash = expected_saved_inventory(
            inventory_before, after, instance_path,
            observed_map_package=observed_map,
            shoulder_receipt=shoulder_receipt,
        )
    except Exception:
        if not saved:
            component.set_material(0, old_material)
            if rollback_state is not None:
                shoulder.rollback(api, rollback_state)
            require(shoulder.inspect_mesh(api, component)["summary"] == road_mesh_before,
                    "Original road buffers changed during rollback")
        raise
    session._verify_rows(ROOT, rows)
    session._assert_package_members(ROOT, rows)
    require(asphalt_source.verify_retained_replay() == source_before,
            "Original asphalt source changed while saving consumer")
    assets = produced_files()
    delivered = retain_files(retained, assets)
    verify_retained_files(retained, delivered)
    profile_identity = write_profile_diagnostic(proof, retained, source_plan)
    manifest = {
        "schema_version": 1,
        "issue": 364,
        "status": "SAVED_ROAD_ASPHALT_CONSUMER_PREPARED",
        "exact_sha": exact_sha,
        "staging_sha256": staging_sha,
        "map_package": MAP,
        "map_file": MAP_FILE,
        "canonical_source_map": session.operation.MAP_PACKAGE,
        "map_saved": True,
        "canonical_saved": False,
        "source_scene_mutated": False,
        "material_instance": instance_path,
        "material_master": receipt["assets"]["master"],
        "texture_objects": receipt["assets"]["textures"],
        "source_proof": source_before,
        "source_receipt_sha256": asphalt_source.SOURCE_RECEIPT_SHA256,
        "graph_sha256": asphalt_source.GRAPH_SHA256,
        "metric_tile_cm": 400,
        "normal_convention": "DirectX",
        "expected_normalized_inventory_sha256": inventory_hash,
        "original_native_map_inventory_sha256": inventory_digest(before),
        "assets": delivered,
        "road_slot_zero_only": False,
        "support_186_unchanged": False,
        "shoulder_network": shoulder_receipt,
        "native_mesh_hash_format": shoulder.HASH_FORMAT,
        "road_mesh": road_mesh_before,
        "dry_asphalt_response": receipt["dry_asphalt_response"],
        "road_profile_diagnostic": profile_identity,
        "material_changes": "road_slot_zero_and_network_outer_shoulder_ids",
        "landscape_1024_unchanged": True,
        "road_geometry_unchanged": True,
        "physics_profile_unchanged": True,
        "fresh_reload_verified": False,
        "gpu_shader_verified": False,
        "visual_status": "PENDING_FINAL_M3",
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }
    manifest_id = write_once(retained / MANIFEST, manifest)
    require(write_once(session._safe_path(proof, MANIFEST), manifest) == manifest_id,
            "Downloadable material manifest differs from retained native evidence")
    require(verified_manifest_identity(proof, retained) == manifest_id,
            "Native material manifest copy changed after writing")
    receipt_path = session._safe_path(proof, PREPARED)
    receipt_id = write_once(receipt_path, {
        "status": "ROAD_ASPHALT_SAVED_PREPARED",
        "exact_sha": exact_sha,
        "manifest": manifest_id,
        "evidence_manifest": {"file": MANIFEST, **manifest_id},
        "retained_root": str(retained),
        "derived_map_sha256": next(x["sha256"] for x in assets if x["path"] == MAP_FILE),
        "material_saved": True,
        "new_world_only": True,
        "fresh_reload_verified": False,
        "performance_pass": False,
    })
    api.log("YACS_ROAD_ASPHALT_SAVED_PREPARED " + json.dumps({
        "map": MAP, "packages": len(delivered), "receipt_sha256": receipt_id["sha256"]
    }))


def reload(api, proof, retained, exact_sha, staging_sha, original, rows, *, source_dependencies):
    prepare_row = session._read_json(session._safe_path(proof, PREPARED), limit=JSON_LIMIT)
    require(
        prepare_row.get("status") == "ROAD_ASPHALT_SAVED_PREPARED"
        and prepare_row.get("exact_sha") == exact_sha
        and prepare_row.get("material_saved") is True
        and prepare_row.get("fresh_reload_verified") is False
        and prepare_row.get("retained_root") == str(retained),
        "No authentic native saved-consumer preparation",
    )
    original_manifest_id = verified_manifest_identity(proof, retained)
    require(
        prepare_row.get("manifest") == original_manifest_id
        and prepare_row.get("evidence_manifest") == {"file": MANIFEST, **original_manifest_id},
        "Persistent manifest differs from first native save",
    )
    manifest = session._read_json(retained / MANIFEST, limit=JSON_LIMIT)
    require(
        manifest.get("schema_version") == 1
        and manifest.get("issue") == 364
        and manifest.get("status") == "SAVED_ROAD_ASPHALT_CONSUMER_PREPARED"
        and manifest.get("exact_sha") == exact_sha
        and manifest.get("staging_sha256") == staging_sha
        and manifest.get("map_package") == MAP
        and manifest.get("map_file") == MAP_FILE
        and manifest.get("map_saved") is True
        and manifest.get("canonical_saved") is False
        and manifest.get("road_slot_zero_only") is False
        and manifest.get("support_186_unchanged") is False
        and manifest.get("material_changes") == "road_slot_zero_and_network_outer_shoulder_ids"
        and manifest.get("shoulder_network", {}).get("rollback_verified") is True
        and manifest.get("shoulder_network", {}).get("support_count") == 186
        and manifest.get("shoulder_network", {}).get("material_target_count") == 185
        and manifest.get("native_mesh_hash_format") == shoulder.HASH_FORMAT
        and manifest.get("source_scene_mutated") is False
        and manifest.get("source_receipt_sha256") == asphalt_source.SOURCE_RECEIPT_SHA256
        and manifest.get("graph_sha256") == asphalt_source.GRAPH_SHA256
        and manifest.get("metric_tile_cm") == 400
        and manifest.get("normal_convention") == "DirectX"
        and manifest.get("fresh_reload_verified") is False
        and manifest.get("performance_pass") is False,
        "Manifest claims unsupported native result",
    )
    verify_retained_files(retained, manifest["assets"])
    profile_identity = verified_profile_identity(proof, retained, manifest.get("road_profile_diagnostic"))
    session._verify_rows(ROOT, rows)
    session._assert_package_members(ROOT, rows)
    original_source = asphalt_source.verify_retained_replay()
    require(original_source == manifest["source_proof"], "Source replay changed after save")
    native_world(api, MAP)
    instance = verify_material_instance(
        api, manifest["material_instance"], manifest["material_master"],
        manifest["texture_objects"], expected_response=manifest["dry_asphalt_response"],
    )
    shoulder_material.verify_material(api, manifest["shoulder_network"]["material"], source_dependencies)
    shoulder.verify_loaded(api, manifest["shoulder_network"])
    verify_road_mesh(api, manifest["road_mesh"])
    require(
        instance.get_path_name() == manifest["material_instance"],
        "Fresh loaded material object differs",
    )
    after = baseline.native_inventory(api, prep, MAP)
    inventory_hash = expected_saved_inventory(
        original["native_inventory"], after, manifest["material_instance"],
        observed_map_package=MAP,
        shoulder_receipt=manifest["shoulder_network"],
    )
    require(
        inventory_hash == manifest["expected_normalized_inventory_sha256"],
        "Fresh loaded road/support/Landscape inventory differs from saved world",
    )
    baseline.dirty_packages(api)
    session._verify_rows(ROOT, rows)
    verify_retained_files(retained, manifest["assets"])
    require(verified_manifest_identity(proof, retained) == original_manifest_id,
            "Saved consumer manifest changed during fresh reload")
    verified_profile_identity(proof, retained, profile_identity)
    write_once(session._safe_path(proof, RELOADED), {
        "schema_version": 1,
        "issue": 364,
        "status": "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS",
        "exact_sha": exact_sha,
        "map_package": MAP,
        "saved_manifest_sha256": original_manifest_id["sha256"],
        "evidence_manifest_sha256": original_manifest_id["sha256"],
        "map_sha256": next(x["sha256"] for x in manifest["assets"] if x["path"] == MAP_FILE),
        "material_instance": instance.get_path_name(),
        "fresh_process": True,
        "road_material_reapplied": False,
        "shoulder_material_reapplied": False,
        "shoulder_network_fresh_reload_verified": True,
        "shoulder_positions_indices_normals_uv_unchanged": True,
        "shoulder_wall_materials_unchanged": True,
        "shoulder_support_count": manifest["shoulder_network"]["support_count"],
        "shoulder_material_target_count": manifest["shoulder_network"]["material_target_count"],
        "shoulder_selected_triangle_count": manifest["shoulder_network"]["selected_triangle_count"],
        "road_full_buffers_unchanged": True,
        "dry_asphalt_response_verified": True,
        "road_profile_diagnostic_sha256": profile_identity["sha256"],
        "source_scene_mutated": False,
        "new_saved_asset_bytes_unchanged": True,
        "supports_landscape_geometry_unchanged": True,
        "gpu_shader_verified": False,
        "owner_visual_status": "PENDING_FINAL_M3",
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    })
    api.log("YACS_ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS")


def main():
    action = os.environ.get("YACS_ROAD_SAVED_ACTION", "")
    require(action in ("prepare", "reload"), "Explicit saved consumer action required")
    session._assert_isolated_root()
    require(ROOT == session.ROOT == prep.ROOT, "Saved consumer modules belong to another checkout")
    exact_sha, staging_sha, token, proof, retained = proof_paths()
    staging_path, stage_identity, stage, _map_row, rows = verified_staging(
        exact_sha, staging_sha
    )
    original, trial = verified_predecessors(proof, exact_sha, staging_sha)
    require(
        trial["result"]["graph_sha256"] == asphalt_source.GRAPH_SHA256
        and trial["result"]["source_receipt_sha256"] == asphalt_source.SOURCE_RECEIPT_SHA256,
        "Prior native transient canary used another asphalt source",
    )
    import unreal

    native_project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve()
    require(native_project == ROOT, "Native saved consumer invoked for wrong Unreal checkout")
    require(
        str(unreal.SystemLibrary.get_engine_version()).startswith("5.8.2-56702186"),
        "Unverified Unreal executable version",
    )
    baseline.dirty_packages(unreal)
    prep.assert_isolated_bootstrap(unreal)
    if action == "prepare":
        prepare(unreal, proof, retained, exact_sha, staging_sha, original, rows,
                source_dependencies=stage["source_dependencies"])
    else:
        reload(unreal, proof, retained, exact_sha, staging_sha, original, rows,
               source_dependencies=stage["source_dependencies"])
    session._verify_rows(ROOT, rows)
    require(
        session._identity(staging_path, JSON_LIMIT) == stage_identity,
        "Original accepted source staging receipt changed",
    )
    unreal.SystemLibrary.quit_editor()


if __name__ == "__main__":
    main()
