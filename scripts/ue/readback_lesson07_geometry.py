"""Inspect the pinned saved L07 in an owned, physically isolated Editor.

The PowerShell launcher authenticates/copies assets and ordinary CI binaries.
This reader never saves or repairs the world. Native LOD0 seam samples and
collision probes remain measurements pending comparison to the Houdini source.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct

LEVEL_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
MAP_FILE = "Content" + LEVEL_PATH.removeprefix("/Game") + ".umap"
ORIGINAL_MAP_SHA256 = "61aa69146ce6822b20d0d2ffe93e6840ce238b941fea3f5ae955c0e15a7814f7"
ORIGINAL_MAP_SIZE = 1842190204
MAP_SHA256 = "d14a132cdfbb59f340a4c5ed503296153bb00700fa2a790cd3d5f900ebc5ac75"
MAP_SIZE = 1838638056
CURRENT_MATERIAL_PINS = {
    "Content/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS.uasset":
        ("8c1dc875218a027a5ac83d88f8eedba49769fdd8494d287e7264807082eb11bf", 39740),
    "Content/Generated/YACS/Lesson07_Unified/Materials/M_Landscape_YACS.uasset":
        ("53a1d68a97a5205a25463dea5c6aaaec4a9bb1167a1ce9e131a84406327fad66", 208956),
}
REPAIRED_PREPARATION_STATUS = "L07_REPAIRED_BYTES_NATIVE_READ_PENDING"
REPAIR_RECEIPT_LIMIT = 32 * 1024**2
SOURCE_MANIFEST_SHA256 = "66847b4a614e748a0012dcefabbc6f2be9b0326f0a863714e690cb71c068a8f6"
SOURCE_CACHE_SHA256 = "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24"
EXPECTED_ACTORS = {f"SaCalobra_Unified_{x}_{y}" for x in range(2) for y in range(2)}
EXPECTED_MATERIAL = "/Game/Generated/YACS/Lesson07_Unified/Materials/MI_Landscape_Instance_YACS"
REQUIRED_PACKAGES = (
    LEVEL_PATH, EXPECTED_MATERIAL,
    # The assigned instance's actual parent is discovered by the native
    # dependency walk. An unreferenced retained original master is not a seed.
    "/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_IDMap",
    "/Game/Generated/YACS/Lesson07_Unified/Textures/T_PE_Terrain_Color",
    *(f"/Game/Generated/YACS/Lesson07_Unified/Materials/TA_{name}_Unified"
      for name in ("Colour", "Normal", "Masks")),
)
MAX_DEPENDENCIES = 2048
MAX_DEPENDENCY_EDGES = 16384
COMPONENT_FIELDS = ("component_size_quads", "subsection_size_quads",
                    "num_subsections", "section_base_x", "section_base_y")
COMPONENT_QUADS = 254
COMPONENT_VERTICES = COMPONENT_QUADS + 1
TILE_QUADS = COMPONENT_QUADS * 32
SEAM_SAMPLE_COLUMNS = ["height_u16", "world_x_cm", "world_y_cm", "world_z_cm", "visibility_u8"]
# HAPI carries binary32 metre scales. The installed translator multiplies by
# 100. Permit only the immediate binary32 neighbours of 0.5 m, not a geometric
# acceptance tolerance; preserve actual transforms and measure their world drift.
XY_SCALE_INTERVAL_CM = tuple(
    struct.unpack("<f", struct.pack("<I", bits))[0] * 100.0
    for bits in (0x3EFFFFFF, 0x3F000001)
)


def plain_path(value):
    """Do not follow a linked parent while authenticating evidence or copies."""
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("An absolute, non-traversing path is required")
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink() or (
            ancestor.exists()
            and getattr(ancestor.lstat(), "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("Refuse linked/reparse input or output")
    return path.resolve()


def file_identity(path, limit):
    path = plain_path(path)
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= limit:
        raise ValueError("Input is not a bounded, nonempty file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Input changed while hashing")
    return {"path": str(path), "size_bytes": after.st_size, "sha256": digest.hexdigest()}


def map_identity_pair(value):
    if (not isinstance(value, dict)
            or re.fullmatch(r"[0-9a-f]{64}", str(value.get("sha256"))) is None
            or type(value.get("size_bytes")) is not int
            or not 0 < value["size_bytes"] <= 3 * 1024**3):
        raise ValueError("Invalid bounded map identity")
    return value["sha256"], value["size_bytes"]


def repair_inventory(value):
    """Normalize Windows receipt paths without admitting aliases or traversal."""
    if not isinstance(value, dict) or not 0 < len(value) <= 2048:
        raise ValueError("Repair receipt requires a bounded asset inventory")
    result = {}
    for path, digest in value.items():
        relative = path.replace("\\", "/")
        if (relative in result or any(p in ("", ".", "..") for p in relative.split("/"))
                or not relative.startswith(("Content/Generated/YACS/Lesson07_Unified/",
                                            "Content/PegasusDemo/Materials/"))
                or not relative.endswith((".umap", ".uasset"))
                or re.fullmatch(r"[0-9a-f]{64}", str(digest)) is None):
            raise ValueError("Repair inventory contains an unsupported path/hash")
        result[relative] = digest
    if MAP_FILE not in result:
        raise ValueError("Repair inventory omits the exact L07 map")
    return result


def complete_height_snapshot(value):
    return (isinstance(value, dict) and value.get("schema_version") == 1
            and value.get("success") is True and value.get("errors") == []
            and value.get("world_package") == LEVEL_PATH
            and value.get("hash_algorithm") == "BLAKE3-256"
            and value.get("actor_count") == 4 and value.get("component_count") == 4096
            and isinstance(value.get("component_bindings"), list)
            and len(value["component_bindings"]) == 4096
            and isinstance(value.get("textures"), list) and bool(value["textures"]))


def read_repair_receipt(reference):
    if not isinstance(reference, dict):
        raise ValueError("Repair receipt reference must include its path and SHA256")
    identity = file_identity(reference["path"], REPAIR_RECEIPT_LIMIT)
    if identity["sha256"] != reference.get("sha256"):
        raise ValueError("Untrusted repair receipt bytes")
    raw = Path(identity["path"]).read_bytes()
    if (len(raw) != identity["size_bytes"]
            or hashlib.sha256(raw).hexdigest() != identity["sha256"]):
        raise ValueError("Repair receipt changed while reading")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Repair receipt is not an object")
    return value


def validate_consumer_repair(receipt, before_sha, after_sha, source_head):
    mode = receipt.get("mode")
    if (receipt.get("schema_version") != 1 or receipt.get("source_head") != source_head
            or mode not in ("visibility-only", "height-and-visibility")
            or receipt.get("map_saved") is not True
            or receipt.get("source_comparison_proved") is not False
            or receipt.get("visibility_source_proved") is not False
            or map_identity_pair(receipt.get("source_map_identity")) != (ORIGINAL_MAP_SHA256, ORIGINAL_MAP_SIZE)):
        raise ValueError("Consumer repair does not identify a saved scoped L07 update")
    for key, expected in (("map_before", before_sha), ("map_after", after_sha)):
        identity = receipt.get(key)
        if (map_identity_pair(identity)[0] != expected
                or plain_path(identity["path"]) != plain_path(receipt["project"]) / MAP_FILE):
            raise ValueError("Consumer repair map identities differ from its inventory")
    selected = receipt.get("selected_actors")
    if (not isinstance(selected, list) or not selected or len(set(selected)) != len(selected)
            or not set(selected) <= EXPECTED_ACTORS
            or sorted(receipt.get("completed_actors", [])) != sorted(selected)
            or (mode == "height-and-visibility" and set(selected) != EXPECTED_ACTORS)):
        raise ValueError("Consumer repair did not complete the selected existing actors")
    transport = read_repair_receipt(receipt.get("transport_manifest"))
    if (transport.get("schema_version") != 1
            or transport.get("status") != "DERIVED_TRANSPORT_READY_NATIVE_UPDATE_NOT_RUN"
            or transport.get("source_head") != source_head or transport.get("mode") != mode
            or sorted(transport.get("selected_actors", [])) != sorted(selected)
            or transport.get("source_map") != LEVEL_PATH
            or transport.get("geometry_accepted") is not False
            or map_identity_pair(transport.get("source_map_identity")) != (ORIGINAL_MAP_SHA256, ORIGINAL_MAP_SIZE)):
        raise ValueError("Consumer transport receipt differs from the scoped update")
    before, after = receipt.get("actors_before"), receipt.get("actors_after")
    if (not isinstance(before, dict) or set(before) != EXPECTED_ACTORS
            or not isinstance(after, dict) or set(after) != EXPECTED_ACTORS):
        raise ValueError("Consumer repair must preserve all four actor identities")
    required = {"path", "landscape_guid", "location_cm", "rotation_deg_pitch_yaw_roll", "scale",
                "edit_layer", "edit_layer_guid", "component_paths", "material", "hole_material"}
    for name, actor in before.items():
        if (not isinstance(actor, dict) or not required <= set(actor)
                or actor["edit_layer"] != "Houdini_Unified_Final"
                or not actor["landscape_guid"] or not actor["edit_layer_guid"]
                or not actor["path"].startswith(LEVEL_PATH + ".")
                or actor["material"] != EXPECTED_MATERIAL
                or not isinstance(actor["component_paths"], list)
                or len(actor["component_paths"]) != 1024
                or len(set(actor["component_paths"])) != 1024
                or any(not p.startswith(actor["path"] + ".") for p in actor["component_paths"])):
            raise ValueError("Consumer repair actor/layout/layer observation is incomplete")
        for field in ("location_cm", "rotation_deg_pitch_yaw_roll", "scale"):
            values = actor[field]
            if (not isinstance(values, list) or len(values) != 3
                    or any(type(n) not in (int, float) or not math.isfinite(n) for n in values)):
                raise ValueError("Consumer actor transform is not a finite native observation")
        if any(n <= 0 for n in actor["scale"]):
            raise ValueError("Consumer actor scale must be positive")
    # Compare complete observed records, so new observed fields are protected
    # too. Only the explicitly selected common Z quantization may differ.
    expected_after = json.loads(json.dumps(before))
    if mode == "height-and-visibility":
        common = max(actor["scale"][2] for actor in before.values())
        if (receipt.get("required_common_scale_z") != common
                or transport.get("required_common_scale_z") != common):
            raise ValueError("Common quantization scale is not the observed pre-update maximum")
        for actor in expected_after.values():
            actor["scale"][2] = common
    elif (receipt.get("whole_heightmaps_unchanged") is not True
          or receipt.get("heightmaps_before") != receipt.get("heightmaps_after")):
        raise ValueError("Visibility-only repair changed native heightmaps")
    if before.keys() != after.keys() or expected_after != after:
        raise ValueError("Consumer repair changed actor identity, layout or an unapproved transform")
    if any(not complete_height_snapshot(receipt.get(key))
           or receipt[key].get("height_source_scope") != "composite_and_existing_edit_layer_all_mips"
           for key in ("heightmaps_before", "heightmaps_after")):
        raise ValueError("Consumer repair requires complete native heightmap observations")
    outputs = receipt.get("native_outputs")
    expected_layers = {"visibility"} | ({"height"} if mode == "height-and-visibility" else set())
    expected_outputs = {(actor, layer) for actor in selected for layer in expected_layers}
    if (not isinstance(outputs, list) or len(outputs) != len(expected_outputs)
            or {(row.get("actor"), row.get("target_layer")) for row in outputs} != expected_outputs
            or any(row.get("extents") != [0, 0, 8128, 8128]
                   or row.get("cooked_edit_layer") != "Houdini_Unified_Final"
                   or any(row.get(flag) is not False for flag in
                          ("created_landscape", "layer_was_created", "clear_layer",
                           "cooked_layer_requires_baking")) for row in outputs)):
        raise ValueError("Native consumer outputs changed the existing target contract")


def authenticated_repaired_map(project, preparation, observed_map):
    """Admit a local diagnostic read, never promote a repair to accepted proof.

    The existing material refresher records map hashes in its full asset
    inventories, rather than map sizes. Its retained backup authenticates the
    original bytes/size. The final repaired size is independently measured and
    pinned by staging; each intervening map hash must form a continuous chain.
    """
    lineage = preparation["map"]
    if map_identity_pair(lineage.get("original_identity")) != (ORIGINAL_MAP_SHA256, ORIGINAL_MAP_SIZE):
        raise ValueError("Repair lineage does not start at the original pinned L07")
    references = lineage.get("repair_receipts")
    if not isinstance(references, list) or not 0 < len(references) <= 8:
        raise ValueError("Explicit bounded repair receipt chain is required")
    previous_files, repair_project, previous_sha = None, None, ORIGINAL_MAP_SHA256
    previous_size = ORIGINAL_MAP_SIZE
    seen = set()
    for reference in references:
        receipt = read_repair_receipt(reference)
        if reference["sha256"] in seen:
            raise ValueError("Duplicate repair receipt")
        seen.add(reference["sha256"])
        current_project = plain_path(receipt["project"])
        if repair_project is not None and current_project != repair_project:
            raise ValueError("Repair chain changed its source project")
        repair_project = current_project
        before = repair_inventory(receipt.get("files"))
        after = repair_inventory(receipt.get("files_after"))
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
        claimed = receipt.get("changed_files")
        if (not isinstance(claimed, list)
                or sorted(p.replace("\\", "/") for p in claimed) != changed
                or set(before) != set(after) or set(changed) - {MAP_FILE}
                or receipt.get("protected_files_unchanged") is not True
                or before[MAP_FILE] != previous_sha
                or (previous_files is not None and before != previous_files)
                or receipt.get("geometry_accepted") is not False
                or receipt.get("fresh_reopen_verified") is not False):
            raise ValueError("Repair receipt changed protected assets or broke map lineage")
        if (receipt.get("mode"), receipt.get("status")) == (
                "REFRESH_MAP", "MAP_CACHES_REFRESHED_REOPEN_PENDING"):
            if (receipt.get("map_saved_after_cache_refresh") is not True
                    or receipt.get("whole_heightmaps_unchanged") is not True
                    or not complete_height_snapshot(receipt.get("heightmaps_before"))
                    or receipt["heightmaps_before"] != receipt.get("heightmaps_after")):
                raise ValueError("Cache refresh did not preserve complete native heightmaps")
            refresh = receipt.get("grass_refresh", {})
            if (refresh.get("success") is not True or refresh.get("errors") != []
                    or refresh.get("world_package") != LEVEL_PATH
                    or refresh.get("actor_count") != 4 or refresh.get("component_count") != 4096
                    or refresh.get("updated_component_count") != 4096
                    or refresh.get("grass_type_reference_count_after") != 0):
                raise ValueError("Native grass cache refresh was incomplete")
            backup = file_identity(receipt["map_backup"], 3 * 1024**3)
            if backup["sha256"] != before[MAP_FILE] or (
                    previous_size is not None and backup["size_bytes"] != previous_size):
                raise ValueError("Retained map backup does not authenticate repair lineage")
            previous_size = None  # This existing receipt records hashes, not its saved size.
        elif receipt.get("status") == "UPDATED_EXISTING_MAP_REOPEN_PENDING":
            validate_consumer_repair(receipt, before[MAP_FILE], after[MAP_FILE], preparation["source_head"])
            if previous_size is not None and receipt["map_before"]["size_bytes"] != previous_size:
                raise ValueError("Consumer repair broke the preceding map size identity")
            previous_size = receipt["map_after"]["size_bytes"]
        else:
            raise ValueError("Repair receipt is not an allowlisted successful saved operation")
        previous_files, previous_sha = after, after[MAP_FILE]
    source = lineage["source_identity"]
    if (plain_path(source["path"]) != repair_project / MAP_FILE
            or source["sha256"] != previous_sha
            or (previous_size is not None and observed_map["size_bytes"] != previous_size)
            or map_identity_pair(source) != map_identity_pair(observed_map)):
        raise ValueError("Candidate map differs from authenticated repaired map lineage")
    # Bind the current copies to the final authenticated inventory, including
    # unchanged source textures/materials. A map-only receipt cannot bless other
    # edits that occurred later or a substituted staging inventory.
    staged = {}
    for row in preparation.get("assets", []):
        relative = row["relative"].replace("\\", "/")
        if relative in previous_files:
            if relative in staged:
                raise ValueError("Duplicate staged repaired asset")
            staged[relative] = row["copied_identity"]["sha256"]
    if staged != previous_files:
        raise ValueError("Staged assets differ from the authenticated repair inventory")
    for relative, digest in previous_files.items():
        measured = observed_map if relative == MAP_FILE else file_identity(project / relative, 3 * 1024**3)
        if measured["sha256"] != digest:
            raise ValueError("Candidate asset differs from the authenticated repair inventory")


def authenticated_current_map(project, preparation, observed_map):
    """Current canonical copies have exact map/material pins, not a repair claim."""
    lineage = preparation["map"]
    if (lineage.get("relative") != MAP_FILE or lineage.get("repair_receipts")
            or map_identity_pair(lineage.get("source_identity")) != (MAP_SHA256, MAP_SIZE)
            or map_identity_pair(lineage.get("original_identity")) != (ORIGINAL_MAP_SHA256, ORIGINAL_MAP_SIZE)):
        raise ValueError("Staging receipt differs from the pinned saved L07 or its original identity")
    if map_identity_pair(observed_map) != (MAP_SHA256, MAP_SIZE):
        raise ValueError("Candidate map differs from the pinned saved L07")
    for relative, pin in CURRENT_MATERIAL_PINS.items():
        rows = [row for row in preparation.get("assets", []) if row.get("relative") == relative]
        if (len(rows) != 1 or map_identity_pair(rows[0].get("source_identity")) != pin
                or map_identity_pair(rows[0].get("copied_identity")) != pin):
            raise ValueError("Staged current material differs from its exact pin: " + relative)
        if map_identity_pair(file_identity(project / relative, 3 * 1024**3)) != pin:
            raise ValueError("Candidate current material differs from its exact pin: " + relative)


def authenticated_preparation(project, env):
    project = plain_path(project)
    manifest_path = plain_path(env["YACS_L07_PREPARATION_FILE"])
    manifest_identity = file_identity(manifest_path, 8 * 1024**2)
    if manifest_identity["sha256"] != env["YACS_L07_PREPARATION_SHA256"]:
        raise ValueError("Untrusted L07 staging receipt bytes")
    value = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if (value.get("schema_version") != 1
            or value.get("status") not in ("L07_COPIED_BYTES_NATIVE_READ_PENDING",
                                           REPAIRED_PREPARATION_STATUS)
            or value.get("source_head") != env["YACS_L07_EXPECTED_HEAD"]
            or re.fullmatch(r"[0-9a-f]{40}", str(value.get("source_head"))) is None
            or plain_path(value["candidate_root"]) != project
            or value.get("level") != LEVEL_PATH
            or value.get("geometry_accepted") is not False
            or value.get("dependency_closure_complete") is not False):
        raise ValueError("Staging receipt does not identify this isolated L07 read")
    repaired = value["status"] == REPAIRED_PREPARATION_STATUS
    if (value["map"]["relative"] != MAP_FILE or (not repaired and (
            map_identity_pair(value["map"]["source_identity"]) != (MAP_SHA256, MAP_SIZE)
            or value["map"].get("repair_receipts")))):
        raise ValueError("Staging receipt differs from the pinned saved L07")
    reader_identity = file_identity(__file__, 256 * 1024)
    if reader_identity["sha256"] != value["reader_identity"]["sha256"]:
        raise ValueError("Executed reader bytes differ from staging provenance")
    observed_map = file_identity(project / MAP_FILE, 3 * 1024**3)
    if repaired:
        authenticated_repaired_map(project, value, observed_map)
    else:
        authenticated_current_map(project, value, observed_map)
    if "interior_plan" in value:
        authenticated_interior_plan(value)
    output = plain_path(env["YACS_LESSON07_READBACK_PATH"])
    if (output != plain_path(value["report_path"])
            or output.parent != manifest_path.parent or output.exists()):
        raise ValueError("Readback output is not its new, owned evidence file")
    return value, manifest_identity, observed_map, output


def authenticated_interior_plan(preparation):
    reference = preparation["interior_plan"]
    file_identity(reference["path"], 1024**2)
    plan = read_repair_receipt(reference)
    if (plan.get("schema_version") != 1
            or plan.get("status") != "SOURCE_SELECTED_INTERIOR_NATIVE_READ_PENDING"
            or plan.get("source_head") != preparation["source_head"] or plan.get("level") != LEVEL_PATH
            or plan.get("accepted_l06_sha256") != SOURCE_CACHE_SHA256
            or plan.get("manifest", {}).get("sha256") != SOURCE_MANIFEST_SHA256
            or plan.get("original_source_center_bounds_m") != [-3999.75, 3999.75]
            or plan.get("buffer_vertices") != 3
            or plan.get("geometry_accepted") is not False
            or plan.get("source_triangle_interpolation_proved") is not False
            or plan.get("visibility_layer_proved_in_ue") is not False
            or set(plan.get("actor_registration", {})) != EXPECTED_ACTORS):
        raise ValueError("Interior plan does not identify the pinned source/task")
    manifest = read_repair_receipt(plan["manifest"])
    if manifest.get("accepted_l06_sha256") != SOURCE_CACHE_SHA256:
        raise ValueError("Interior plan references another source cache")
    for actor in plan["actor_registration"].values():
        for key in ("location_cm", "rotation_deg_pitch_yaw_roll", "scale"):
            values = actor.get(key)
            if (not isinstance(values, list) or len(values) != 3
                    or any(type(n) not in (int, float) or not math.isfinite(n) for n in values)):
                raise ValueError("Interior plan has an invalid actor registration")
    probes = plan.get("probes")
    if not isinstance(probes, list) or len(probes) > 24:
        raise ValueError("Interior plan exceeds its bounded sample count")
    seen, counts = set(), {}
    for probe in probes:
        name, label = probe.get("actor"), probe.get("id")
        indices, validity = probe.get("local_vertex_indices"), probe.get("source_validity")
        if (name not in EXPECTED_ACTORS or not isinstance(label, str) or label in seen
                or type(validity) is not int or validity not in (0, 1)
                or not isinstance(indices, list) or len(indices) != 4
                or any(type(i) is not int or not 0 <= i < 255**2 for i in indices)
                or indices != [indices[0], indices[0]+1, indices[0]+255, indices[0]+256]
                or not 3 <= indices[0] % 255 <= 250 or not 3 <= indices[0] // 255 <= 250
                or not probe.get("component_path", "").startswith(LEVEL_PATH + ".")
                or f".{name}." not in probe["component_path"]
                or probe.get("uniform_source_patch_samples") != 64
                or len(probe.get("source_corners", [])) != 4):
            raise ValueError("Interior plan has an invalid actor/component/buffered quad")
        for corner in probe["source_corners"]:
            if corner.get("source_validity") != validity:
                raise ValueError("Interior source quad contains mixed validity")
            position, index = corner.get("source_voxel_center_houdini_m"), corner.get("source_voxel_index")
            if (not isinstance(position, list) or len(position) != 3
                    or any(type(n) not in (int, float) or not math.isfinite(n) for n in position)
                    or not all(-3999.75 <= position[i] <= 3999.75 for i in (0, 2))
                    or not isinstance(index, list) or len(index) != 3
                    or any(type(n) is not int or not 0 <= n <= 8128 for n in index)
                    or index[2] != 0
                    or type(corner.get("source_vertex_height_m")) not in (int, float)
                    or not math.isfinite(corner["source_vertex_height_m"])):
                raise ValueError("Interior source quad lies outside the original source grid")
        seen.add(label)
        counts[(name, validity)] = counts.get((name, validity), 0) + 1
        if counts[(name, validity)] > 3:
            raise ValueError("Interior plan exceeds its per-actor/class bound")
    return plan


def observe(call):
    try:
        return {"observed": True, "value": call(), "error": None}
    except Exception as exc:
        return {"observed": False, "value": None, "error": str(exc)[:1000]}


def dependency_inventory(seeds, query, package_exists, staged_packages):
    """Bounded on-disk package walk; None/exception never means no dependencies.

    This is an inventory of native package references, not a claim about dynamic
    string references, shader compilation or a complete rendered asset closure.
    """
    pending = list(sorted(set(seeds)))
    visited = set()
    rows = []
    problems = []
    edge_count = 0
    while pending:
        package = pending.pop()
        if package in visited:
            continue
        if len(visited) >= MAX_DEPENDENCIES:
            problems.append("Native dependency inventory exceeded its package bound")
            break
        visited.add(package)
        row = {"package": package, "present": None, "dependencies": None}
        rows.append(row)
        if re.fullmatch(r"/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*", package) is None:
            problems.append(f"Unsupported package name: {package[:300]}")
            continue
        if package.startswith("/Game/") and package not in staged_packages:
            row["present"] = False
            problems.append(f"Referenced game package was not staged: {package}")
            continue
        try:
            row["present"] = package_exists(package)
            if row["present"] is not True:
                problems.append(f"Package missing or availability UNKNOWN: {package}")
                continue
            if package.startswith("/Script/"):
                row["kind"] = "LOADED_SCRIPT_PACKAGE"
                row["dependencies"] = []
                continue
            dependencies = query(package)
            if dependencies is None:
                problems.append(f"Dependency query UNKNOWN: {package}")
                continue
            dependencies = sorted({str(item) for item in dependencies})
            edge_count += len(dependencies)
            if edge_count > MAX_DEPENDENCY_EDGES:
                problems.append("Native dependency inventory exceeded its edge bound")
                break
            row["dependencies"] = dependencies
            pending.extend(dep for dep in dependencies if dep not in visited)
        except Exception as exc:
            problems.append(f"Dependency query failed for {package}: {str(exc)[:500]}")
    return {
        "status": "ON_DISK_PACKAGE_QUERIES_COMPLETE" if rows and not problems else "INCOMPLETE",
        "queries_complete": bool(rows) and not problems,
        "dependency_closure_complete": False,
        "scope": "Native on-disk hard/soft game/editor package references; dynamic references and shaders are unproved",
        "packages": rows, "edge_count": edge_count, "problems": problems,
    }


def native_dependencies(api, preparation):
    registry = api.AssetRegistryHelpers.get_asset_registry()
    registry.search_all_assets(True)
    options = api.AssetRegistryDependencyOptions(
        include_soft_package_references=True, include_hard_package_references=True,
        include_game_package_references=True, include_editor_only_package_references=True,
        include_searchable_names=False, include_soft_management_references=False,
        include_hard_management_references=False,
    )
    staged = {"/Game/" + row["relative"][len("Content/"):].rsplit(".", 1)[0]
              for row in preparation["assets"]
              if row["relative"].endswith((".uasset", ".umap"))}

    def exists(package):
        if package.startswith("/Script/"):
            return api.find_object(None, package) is not None
        assets = registry.get_assets_by_package_name(api.Name(package), True)
        return None if assets is None else len(assets) > 0

    return dependency_inventory(
        REQUIRED_PACKAGES, lambda package: registry.get_dependencies(api.Name(package), options),
        exists, staged,
    )

def on_source_grid(x_m, z_m):
    ax = (x_m + 3999.75) / 0.5
    az = (3999.75 - z_m) / 0.5
    return abs(ax - round(ax)) < 1e-5 and abs(az - round(az)) < 1e-5


def xy_scale_representation(scale):
    valid = (len(scale) == 3 and all(type(x) in (int, float) and math.isfinite(x) for x in scale)
             and all(XY_SCALE_INTERVAL_CM[0] <= x <= XY_SCALE_INTERVAL_CM[1] for x in scale[:2]))
    return {
        "within_one_binary32_input_step": valid,
        "expected_step_cm": 50.0, "admitted_step_interval_cm": list(XY_SCALE_INTERVAL_CM),
        "actual_tile_span_delta_cm": [(x - 50.0) * TILE_QUADS for x in scale[:2]],
        "geometry_accepted": False,
    }


def exact_integer(value, low, high):
    return (type(value) in (int, float) and math.isfinite(value)
            and low <= value <= high and value == int(value))


def read_component_samples(api, component, indices):
    """Authenticate bounded native composite samples; never synthesize missing data."""
    if (not 0 < len(indices) <= 1024 or len(set(indices)) != len(indices)
            or any(type(i) is not int or not 0 <= i < COMPONENT_VERTICES**2 for i in indices)):
        raise ValueError("Invalid bounded native sample indices")
    path = component.get_path_name()
    raw = api.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_component_samples(component, indices)
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 512 * 1024:
        raise ValueError("Native samples are not bounded JSON")
    value = json.loads(raw)
    if (not isinstance(value, dict) or not exact_integer(value.get("schema_version"), 1, 1)
            or value.get("observed") is not True):
        raise ValueError("Native samples UNKNOWN: " + str(value)[:500])
    if (value.get("component_path") != path or value.get("world_package") != LEVEL_PATH
            or value.get("actor_name") not in EXPECTED_ACTORS):
        raise ValueError("Native sample identity differs from this L07 component")
    observed = value.get("visibility_observed")
    status = value.get("visibility_status")
    if (type(observed) is not bool or status not in ("ALLOCATED_READ", "NOT_ALLOCATED", "READ_FAILED")
            or observed != (status == "ALLOCATED_READ")):
        raise ValueError("Native visibility observation is UNKNOWN")
    actual_indices, samples = value.get("vertex_indices"), value.get("samples")
    if (not isinstance(actual_indices, list) or len(actual_indices) != len(indices)
            or any(not exact_integer(i, 0, COMPONENT_VERTICES**2 - 1) for i in actual_indices)
            or actual_indices != indices or not isinstance(samples, list) or len(samples) != len(indices)):
        raise ValueError("Native sample indices/count differ from the request")
    for row in samples:
        if (not isinstance(row, list) or len(row) != 5 or not exact_integer(row[0], 0, 65535)
                or any(type(n) not in (int, float) or not math.isfinite(n) for n in row[1:4])
                or (not exact_integer(row[4], 0, 255) if observed else row[4] is not None)):
            raise ValueError("Invalid native height, position or visibility sample")
        row[0] = int(row[0])
        if observed:
            row[4] = int(row[4])
    return value


def landscape_edge_plans(api, actor, components, layouts):
    """Use observed section indices and the native transform to identify edges."""
    if len(components) != 1024 or len(layouts) != 1024 or any(not r["observed"] for r in layouts):
        raise ValueError("Complete native component layout required for seam sampling")
    grid = {}
    for component, layout in zip(components, layouts):
        fields = layout["fields"]
        if (fields["component_size_quads"], fields["subsection_size_quads"], fields["num_subsections"]) != (254, 127, 2):
            raise ValueError("Unexpected native seam component dimensions")
        key = (fields["section_base_x"], fields["section_base_y"])
        if key in grid:
            raise ValueError("Duplicate native section coordinate")
        grid[key] = component
    xs, ys = (sorted({key[i] for key in grid}) for i in (0, 1))
    if (len(xs) != 32 or len(ys) != 32
            or any(b - a != COMPONENT_QUADS for seq in (xs, ys) for a, b in zip(seq, seq[1:]))
            or set(grid) != {(x, y) for x in xs for y in ys}):
        raise ValueError("Incomplete native tile grid")
    transform = actor.get_actor_transform()
    plans = []
    for edge in range(4):  # X min/max, Y min/max in the native Landscape lattice.
        axis, high = edge // 2, edge % 2
        axes = (xs, ys)
        fixed_section = axes[axis][-1 if high else 0]
        fixed_vertex = fixed_section + (COMPONENT_QUADS if high else 0)
        selected = [(fixed_section, t) if axis == 0 else (t, fixed_section) for t in axes[1-axis]]
        endpoints = []
        for t in (axes[1-axis][0], axes[1-axis][-1] + COMPONENT_QUADS):
            local = (fixed_vertex, t, 0) if axis == 0 else (t, fixed_vertex, 0)
            position = transform.transform_location(api.Vector(*local))
            point = [float(position.x), float(position.y), float(position.z)]
            if not all(math.isfinite(n) for n in point):
                raise ValueError("Nonfinite native edge transform")
            endpoints.append(point)
        plans.append({"edge": edge, "components": [grid[key] for key in selected], "endpoints": endpoints})
    return plans


def read_native_edge(api, actor, plan):
    edge = plan["edge"]
    axis, high = edge // 2, edge % 2
    fixed = COMPONENT_QUADS if high else 0
    indices = [t * COMPONENT_VERTICES + fixed if axis == 0 else fixed * COMPONENT_VERTICES + t
               for t in range(COMPONENT_VERTICES)]
    samples, components, joins = [], [], []
    for component in plan["components"]:
        value = read_component_samples(api, component, indices)
        if value["actor_name"] != actor.get_name():
            raise ValueError("Native seam sample belongs to another actor")
        rows = value["samples"]
        components.append({"component_path": value["component_path"],
                           "visibility_status": value["visibility_status"]})
        if samples:
            joins.append({"vertex_offset": len(samples) - 1, "next_component_sample": rows[0],
                          "delta_xyz_cm": [rows[0][i] - samples[-1][i] for i in (1, 2, 3)],
                          "height_code_delta": rows[0][0] - samples[-1][0],
                          "visibility_equal": (rows[0][4] == samples[-1][4]
                                               if rows[0][4] is not None and samples[-1][4] is not None else None)})
            samples.extend(rows[1:])
        else:
            samples.extend(rows)
    if len(samples) != TILE_QUADS + 1:
        raise ValueError("Native seam sample count is incomplete")
    return {"actor": actor.get_name(), "edge": edge, "samples": samples,
            "components": components, "component_joins": joins}


def seam_collision_trace(api, world, actors, target, xy, expected_render_component=None):
    result = {"observed": False, "hit": None, "query_xy_cm": list(xy), "error": None}
    try:
        ignored = [a for a in actors if a != target]
        raw = api.SystemLibrary.line_trace_single(
            world, api.Vector(xy[0], xy[1], 200000.0), api.Vector(xy[0], xy[1], -50000.0),
            api.TraceTypeQuery.TRACE_TYPE_QUERY1, True, ignored, api.DrawDebugTrace.NONE, True,
        )
        hit = raw.to_dict() if raw is not None else {"blocking_hit": False}
        if not isinstance(hit, dict) or type(hit.get("blocking_hit")) is not bool:
            raise ValueError("Native collision state UNKNOWN")
        result["hit"] = hit["blocking_hit"]
        if result["hit"]:
            actual_actor = hit.get("hit_actor")
            component = hit.get("hit_component") or hit.get("component")
            if actual_actor != target or component is None or component.get_owner() != target:
                raise ValueError("Trace did not authenticate the requested Landscape actor/component")
            path = component.get_path_name()
            if not path.startswith(LEVEL_PATH + "."):
                raise ValueError("Collision component belongs to another world")
            if expected_render_component is not None:
                render_component = component.get_render_component()
                if render_component != expected_render_component:
                    raise ValueError("Collision hit belongs to another Landscape render component")
                result["hit_render_component"] = render_component.get_path_name()
            impact = hit["impact_point"]
            xyz = [float(impact.x), float(impact.y), float(impact.z)]
            if not all(math.isfinite(n) for n in xyz):
                raise ValueError("Nonfinite collision position")
            result.update(impact_point_cm=xyz, hit_actor=actual_actor.get_name(), hit_component=path)
        result["observed"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:500]
    return result


def native_interior_readback(api, world, actors, native_tiles, preparation):
    plan = authenticated_interior_plan(preparation)
    result = {"schema_version": 1, "plan_identity": preparation["interior_plan"],
              "source_selection": plan["tiles"], "probes": [], "samples_complete": False,
              "geometry_accepted": False, "source_triangle_interpolation_proved": False,
              "visibility_layer_proved_in_ue": False}
    for probe in plan["probes"]:
        row = {"id": probe["id"], "actor": probe["actor"], "component_path": probe["component_path"],
               "observed": False, "error": None}
        result["probes"].append(row)
        try:
            actor, components, layouts = native_tiles[probe["actor"]]
            loc, rot, scale = actor.get_actor_location(), actor.get_actor_rotation(), actor.get_actor_scale3d()
            expected = plan["actor_registration"][probe["actor"]]
            if ([loc.x, loc.y, loc.z] != expected["location_cm"]
                    or [rot.pitch, rot.yaw, rot.roll] != expected["rotation_deg_pitch_yaw_roll"]
                    or [scale.x, scale.y] != expected["scale"][:2]):
                raise ValueError("Interior actor registration changed from the source plan")
            matches = [(c, layout) for c, layout in zip(components, layouts)
                       if c.get_path_name() == probe["component_path"]]
            if len(matches) != 1:
                raise ValueError("Interior component identity is not unique/present")
            component, layout = matches[0]
            if (not layout["observed"] or [layout["fields"][key] for key in
                    ("section_base_x", "section_base_y")] != probe["component_section_base"]):
                raise ValueError("Interior component grid registration changed")
            samples = read_component_samples(api, component, probe["local_vertex_indices"])
            if samples["actor_name"] != probe["actor"]:
                raise ValueError("Interior samples belong to another actor")
            row["native_corners"] = samples
            xy = [math.fsum(p[i] for p in samples["samples"])/4.0 for i in (1, 2)]
            row["center_collision"] = seam_collision_trace(
                api, world, actors, actor, xy, expected_render_component=component)
            row["observed"] = row["center_collision"]["observed"]
            row["error"] = row["center_collision"]["error"]
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    result["samples_complete"] = bool(result["probes"]) and all(r["observed"] for r in result["probes"])
    return result


def read_native_seam_pair(api, world, actors, native_tiles, plans, name_a, name_b, seam):
    """Fill an owned report progressively so a later failure preserves earlier reads."""
    choices = []
    for a in plans[name_a]:
        for b in plans[name_b]:
            for reverse in (False, True):
                endpoints_b = b["endpoints"][::-1] if reverse else b["endpoints"]
                gap = max(math.dist(x[:2], y[:2]) for x, y in zip(a["endpoints"], endpoints_b))
                choices.append((gap, a["edge"], b["edge"], reverse))
    gap, edge_a, edge_b, reverse = min(choices)
    # Half a grid cell only bounds adjacency discovery, never seam acceptance.
    if gap >= 25.0:
        raise ValueError(f"{name_a}/{name_b}: no neighbouring native edges within half a grid cell")
    a = seam["a"] = read_native_edge(api, native_tiles[name_a][0], plans[name_a][edge_a])
    b = seam["b"] = read_native_edge(api, native_tiles[name_b][0], plans[name_b][edge_b])
    if reverse:
        b["samples"].reverse()
        b["sample_order_reversed"] = True
        b["component_join_offsets_follow_native_order"] = True
    pairs = list(zip(a["samples"], b["samples"]))
    known_visibility = [(x[4], y[4]) for x, y in pairs if x[4] is not None and y[4] is not None]
    seam["peer_summary"] = {
        "sample_pairs": len(pairs),
        "max_xy_gap_cm": max(math.dist(x[1:3], y[1:3]) for x, y in pairs),
        "max_abs_height_delta_cm": max(abs(x[3] - y[3]) for x, y in pairs),
        "visibility_pairs_observed": len(known_visibility),
        "visibility_disagreements": sum(x != y for x, y in known_visibility),
        "geometry_accepted": False,
    }
    probes = seam["collision_probes"] = []
    for side_name, side in (("a", a), ("b", b)):
        target = native_tiles[side["actor"]][0]
        center = target.get_actor_bounds(False)[0]
        # Every half component, including both corners: 65 vertices per side.
        for offset in range(0, TILE_QUADS + 1, 127):
            row = side["samples"][offset]
            xy = row[1:3]
            delta = [float(center.x) - xy[0], float(center.y) - xy[1]]
            length = math.hypot(*delta)
            if not math.isfinite(length) or length == 0:
                raise ValueError("Cannot establish an inward collision probe direction")
            inside = [xy[i] + 25.0 * delta[i] / length for i in (0, 1)]
            probes.append({
                "side": side_name, "vertex_offset": offset,
                "at_vertex": seam_collision_trace(api, world, actors, target, xy),
                "inside": seam_collision_trace(api, world, actors, target, inside),
            })


def native_seam_readback(api, world, actors, native_tiles):
    """Read both complete native edges at four seams; collision is a separate sample."""
    if set(native_tiles) != EXPECTED_ACTORS:
        raise ValueError("Four exact L07 native actors required")
    plans = {name: observe(lambda entry=entry: landscape_edge_plans(api, *entry))
             for name, entry in native_tiles.items()}
    seams = []
    for axis in range(2):
        for other in range(2):
            ij_a = (0, other) if axis == 0 else (other, 0)
            ij_b = (1, other) if axis == 0 else (other, 1)
            name_a, name_b = (f"SaCalobra_Unified_{i}_{j}" for i, j in (ij_a, ij_b))
            seam = {"id": f"{'x' if axis == 0 else 'y'}_{other}", "observed": False, "error": None}
            seams.append(seam)
            try:
                for name in (name_a, name_b):
                    if not plans[name]["observed"]:
                        raise ValueError(name + ": " + plans[name]["error"])
                read_native_seam_pair(api, world, actors, native_tiles,
                                      {name: plans[name]["value"] for name in (name_a, name_b)},
                                      name_a, name_b, seam)
                seam["observed"] = True
            except Exception as exc:
                seam["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    complete = len(seams) == 4 and all(s["observed"] for s in seams)
    return {
        "schema_version": 1, "sample_columns": SEAM_SAMPLE_COLUMNS, "seams": seams,
        "height_samples_complete": complete,
        "visibility_samples_complete": complete and all(
            s["peer_summary"]["visibility_pairs_observed"] == TILE_QUADS + 1 for s in seams),
        "collision_queries_complete": complete and all(
            p[mode]["observed"] for s in seams for p in s["collision_probes"] for mode in ("at_vertex", "inside")),
        "collision_scope": "65 positions per side/seam, exact native vertex XY and 25cm inward; no-hit is retained, not accepted as valid NoData",
        "geometry_accepted": False, "source_height_interpolation_proved": False,
        "visibility_layer_proved_in_ue": False,
    }

def actor_height_step_cm(scale_z):
    if not math.isfinite(scale_z) or scale_z <= 0:
        raise ValueError("Invalid Landscape Scale.Z")
    return float(scale_z) / 128.0

def read_component_layout(api, component):
    """Read public C++ fields once, authenticating the native component result."""
    result = {"observed": False, "component_path": None, "world_package": None,
              "fields": None, "error": None}
    try:
        component_path = component.get_path_name()
        if not isinstance(component_path, str) or not component_path:
            raise ValueError("Native component identity is UNKNOWN")
        result["component_path"] = component_path
        raw = api.YacsLandscapeMeshDiagnosticLibrary.read_lesson07_component_layout(component)
        if not isinstance(raw, str) or not raw or len(raw.encode("utf-8")) > 4096:
            raise ValueError("Native component layout is not bounded JSON")
        value = json.loads(raw)
        if (not isinstance(value, dict) or type(value.get("schema_version")) not in (int, float)
                or value["schema_version"] != 1):
            raise ValueError("Unknown native component layout schema")
        if value.get("observed") is not True:
            raise ValueError("Native component layout UNKNOWN: " + str(value.get("error", "no observation")))
        if value.get("component_path") != component_path or value.get("world_package") != LEVEL_PATH:
            raise ValueError("Native component layout identity differs from this L07 component")
        raw_fields = value.get("fields")
        if not isinstance(raw_fields, dict) or set(raw_fields) != set(COMPONENT_FIELDS):
            raise ValueError("Native component layout fields are missing or unexpected")
        fields = {}
        for name in COMPONENT_FIELDS:
            number = raw_fields[name]
            # UE's JSON number writer may emit 254.0 for an actual int32.
            # Bounds and exact integrality reject NaN/Inf/fractions before conversion.
            if (type(number) not in (int, float) or not -(2**31) <= number < 2**31
                    or (type(number) is float and not number.is_integer())):
                raise ValueError(f"Native component layout {name} is not an exact int32")
            fields[name] = int(number)
        result.update(observed=True, world_package=value["world_package"], fields=fields)
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:1000]
    return result


def actual_component_settings(layouts):
    observed = {}
    for prop in COMPONENT_FIELDS:
        values = [layout["fields"][prop] if layout["observed"] else None for layout in layouts]
        observed[prop] = {
            "values": sorted({v for v in values if v is not None}),
            "read_count": len(values) - values.count(None),
            "total": len(values),
            "complete": bool(values) and None not in values,
        }
    return observed


def actual_landscape_layers(api, proxy):
    """Layer APIs belong to the owning Landscape, including for streaming proxies."""
    try:
        owner = proxy.get_landscape_actor()
        if owner is None or not isinstance(owner, api.Landscape):
            raise ValueError("Owning Landscape is UNKNOWN")
        owner_path = owner.get_path_name()
        if owner_path.split(".")[0] != LEVEL_PATH:
            raise ValueError("Owning Landscape is outside the pinned L07 world")
    except Exception as exc:
        return {key: {"observed": False, "value": None, "error": str(exc)[:1000]}
                for key in ("landscape_owner", "edit_layers", "target_layers")}

    def names(values):
        if values is None:
            raise ValueError("Native layer names are UNKNOWN")
        result = []
        for value in values:
            if value is None:
                raise ValueError("Native layer name is UNKNOWN")
            result.append(str(value))
        return result

    return {
        "landscape_owner": {"observed": True, "value": owner_path, "error": None},
        "edit_layers": observe(lambda: names(layer.get_name_bp() for layer in owner.get_edit_layers_bp())),
        "target_layers": observe(lambda: names(owner.get_target_layer_names(True))),
    }


def structure_problems(rows):
    problems = []
    names = [row["label"] for row in rows]
    if len(rows) != 4 or len(set(names)) != 4 or set(names) != EXPECTED_ACTORS:
        problems.append("Actual Landscape labels/count differ from the four pinned L07 actors")
    for row in rows:
        label = row["label"]
        if row["component_count"] != 1024:
            problems.append(f"{label}: expected 1024 actual components")
        for prop in COMPONENT_FIELDS:
            measured = row["actual_component_properties"][prop]
            if (measured["complete"] is not True or measured["read_count"] != 1024
                    or measured["total"] != 1024):
                problems.append(f"{label}: native component field UNKNOWN/incomplete: {prop}")
        for prop, expected in (("component_size_quads", 254),
                               ("subsection_size_quads", 127), ("num_subsections", 2)):
            if row["actual_component_properties"][prop]["values"] != [expected]:
                problems.append(f"{label}: actual {prop} differs from the L07 layout")
        pairs = row["component_section_bases"]
        if len(pairs) != 1024 or any(None in pair for pair in pairs):
            problems.append(f"{label}: component section positions are UNKNOWN/incomplete")
        else:
            xs, ys = (sorted({pair[i] for pair in pairs}) for i in (0, 1))
            if (len(set(map(tuple, pairs))) != 1024 or len(xs) != 32 or len(ys) != 32
                    or any(b - a != 254 for values in (xs, ys) for a, b in zip(values, values[1:]))):
                problems.append(f"{label}: actual component positions do not form the expected grid")
        for prop in ("location_cm", "rotation_deg_pitch_yaw_roll", "scale", "bounds_origin_cm", "bounds_extent_cm"):
            if len(row[prop]) != 3 or not all(math.isfinite(x) for x in row[prop]):
                problems.append(f"{label}: non-finite or incomplete {prop}")
        if not xy_scale_representation(row["scale"])["within_one_binary32_input_step"] or row["scale"][2] <= 0:
            problems.append(f"{label}: unexpected Landscape scale")
        if not row["assigned_material"] or row["assigned_material"].split(".")[0] != EXPECTED_MATERIAL:
            problems.append(f"{label}: expected Landscape material is missing or changed")
        for prop in ("hole_material", "edit_layers", "target_layers"):
            if row[prop]["observed"] is not True:
                problems.append(f"{label}: {prop} is UNKNOWN")
    return problems


def inspect_map(unreal, preparation):
    world = unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    if not world or world.get_path_name().split(".")[0] != LEVEL_PATH:
        raise RuntimeError(f"Actual loaded world is not the pinned map: {LEVEL_PATH}")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()

    landscapes = [a for a in actors if isinstance(a, unreal.LandscapeProxy)]
    print(f"Found {len(landscapes)} landscape actors in level.")

    landscape_data = []
    native_tiles = {}
    total_components = 0

    for la in sorted(landscapes, key=lambda x: x.get_name()):
        name = la.get_name()
        loc = la.get_actor_location()
        scale = la.get_actor_scale3d()
        rotation = la.get_actor_rotation()
        origin, extent = la.get_actor_bounds(False)
        comps = la.get_components_by_class(unreal.LandscapeComponent)
        num_comps = len(comps)
        total_components += num_comps
        layouts = [read_component_layout(unreal, comp) for comp in comps]
        if name in native_tiles:
            raise ValueError("Duplicate native Landscape name")
        native_tiles[name] = (la, comps, layouts)

        mat = la.get_editor_property("landscape_material")
        mat_name = mat.get_path_name() if mat else None

        info = {
            "name": name,
            "label": la.get_actor_label(),
            "class": la.get_class().get_name(),
            "location_cm": [loc.x, loc.y, loc.z],
            "rotation_deg_pitch_yaw_roll": [rotation.pitch, rotation.yaw, rotation.roll],
            "scale": [scale.x, scale.y, scale.z],
            "xy_scale_representation": xy_scale_representation([scale.x, scale.y, scale.z]),
            "bounds_origin_cm": [origin.x, origin.y, origin.z],
            "bounds_extent_cm": [extent.x, extent.y, extent.z],
            "component_count": num_comps,
            "actual_component_properties": actual_component_settings(layouts),
            "native_component_layouts": layouts,
            "component_section_bases": [
                [layout["fields"][prop] if layout["observed"] else None
                 for prop in ("section_base_x", "section_base_y")]
                for layout in layouts
            ],
            "expected_design_not_observed": {
                "component_grid": "32x32", "section_quads": 127,
                "num_subsections": 2, "component_quads": 254,
                "tile_quads": 8128, "tile_vertices": 8129,
            },
            "assigned_material": mat_name,
            "hole_material": observe(lambda: (
                la.get_editor_property("landscape_hole_material").get_path_name()
                if la.get_editor_property("landscape_hole_material") else None)),
            **actual_landscape_layers(unreal, la),
        }
        landscape_data.append(info)
        print(f"  Landscape: {name}, comps={num_comps}, mat={mat_name}")

    query_points = [
        {"name": "Puig Major Summit", "x_ue": -128375.0, "y_ue": 349525.0, "x_h": -1283.75, "z_h": 3495.25, "expected_h_m": 1437.16},
        {"name": "Sa Calobra Cove Beach", "x_ue": 47000.0, "y_ue": -106000.0, "x_h": 470.0, "z_h": -1060.0, "expected_h_m": 10.34},
        {"name": "Inland Center (0, 0)", "x_ue": 0.0, "y_ue": 0.0, "x_h": 0.0, "z_h": 0.0, "expected_h_m": 473.51},
        {"name": "Scree Cluster 1 Centroid", "x_ue": -250278.0, "y_ue": 184595.0, "x_h": -2502.78, "z_h": 1845.95, "expected_h_m": 460.95},
    ]

    scales = {a["name"]: float(a["scale"][2]) for a in landscape_data}
    sampled_points = []
    problems = structure_problems(landscape_data)
    rounded_reference_warnings = []
    for qp in query_points:
        sampled = {**qp, "observed": False, "hit": None, "error": None}
        try:
            start = unreal.Vector(qp["x_ue"], qp["y_ue"], 200000.0)
            end = unreal.Vector(qp["x_ue"], qp["y_ue"], -50000.0)
            hit = unreal.SystemLibrary.line_trace_single(
                world, start, end, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
                True, [], unreal.DrawDebugTrace.NONE, True,
            )
            d = hit.to_dict() if hit is not None else {"blocking_hit": False}
            if not isinstance(d, dict) or type(d.get("blocking_hit")) is not bool:
                raise ValueError("Native trace blocking-hit state is UNKNOWN")
            sampled["hit"] = d["blocking_hit"]
            if d["blocking_hit"]:
                impact = d["impact_point"]
                impact_cm = [float(impact.x), float(impact.y), float(impact.z)]
                if not all(math.isfinite(value) for value in impact_cm):
                    raise ValueError("Native trace impact point is non-finite")
                hit_z_cm = impact_cm[2]
                hit_z_m = hit_z_cm / 100.0
                actor_hit = d["hit_actor"].get_name() if d.get("hit_actor") else None
                sampled["impact_point_cm"] = impact_cm
                sampled["hit_z_cm"] = hit_z_cm
                sampled["hit_z_m"] = hit_z_m
                sampled["hit_actor"] = actor_hit
                component = d.get("hit_component") or d.get("component")
                sampled["hit_component"] = component.get_path_name() if component else None
                sampled["hit_component_observed"] = component is not None
                if component is None:
                    problems.append(f"{qp['name']}: hit component is UNKNOWN")
                if qp["expected_h_m"] is not None:
                    delta_m = hit_z_m - qp["expected_h_m"]
                    delta_cm = delta_m * 100.0
                    sampled["delta_m"] = delta_m
                    sampled["delta_cm"] = delta_cm
                    step_cm = (actor_height_step_cm(scales[actor_hit])
                               if actor_hit in scales and math.isfinite(scales[actor_hit])
                               and scales[actor_hit] > 0 else None)
                    sampled["actor_quantization_step_cm"] = step_cm
                    sampled["on_source_grid"] = on_source_grid(qp["x_h"], qp["z_h"])
                    sampled["quantization_steps"] = delta_cm / step_cm if step_cm else None
                    if step_cm is None:
                        problems.append(f"{qp['name']}: hit unexpected actor {actor_hit}")
                    elif sampled["on_source_grid"] and abs(delta_cm) > step_cm / 2.0 + 0.1:
                        rounded_reference_warnings.append(
                            f"{qp['name']}: {delta_cm:.2f}cm differs from a rounded historical "
                            f"reference, not an authoritative source voxel/interpolation."
                        )
                    print(f"  Hit {qp['name']}: {hit_z_m:.3f}m, rounded ref={qp['expected_h_m']}, delta={delta_cm:.2f}cm, actor={actor_hit}; exact native L06 witness still required")
                else:
                    print(f"  Hit {qp['name']}: Z = {hit_z_m:.3f} m, actor={actor_hit}")
            else:
                print(f"  Trace on {qp['name']} did not hit landscape via line trace")
                problems.append(f"{qp['name']}: collision trace did not hit Landscape")
            sampled["observed"] = True
        except Exception as exc:
            sampled["error"] = f"{type(exc).__name__}: {exc}"[:1000]
            problems.append(f"{qp['name']}: collision diagnostic UNKNOWN: {sampled['error']}")
        sampled_points.append(sampled)

    native_seams = observe(lambda: native_seam_readback(unreal, world, actors, native_tiles))
    if not native_seams["observed"]:
        problems.append("Native seam samples are UNKNOWN: " + native_seams["error"])
    elif not native_seams["value"]["height_samples_complete"]:
        problems.append("Native seam height samples are incomplete; retain individual seam errors")
    elif not native_seams["value"]["collision_queries_complete"]:
        problems.append("Some native seam collision queries are UNKNOWN; retain their individual errors")
    native_interiors = {"observed": False, "value": None, "error": "NOT_REQUESTED"}
    if "interior_plan" in preparation:
        native_interiors = observe(lambda: native_interior_readback(
            unreal, world, actors, native_tiles, preparation))
        if not native_interiors["observed"] or not native_interiors["value"]["samples_complete"]:
            problems.append("Requested interior source-selected native samples are incomplete")
    dependencies = observe(lambda: native_dependencies(unreal, preparation))
    if dependencies["observed"]:
        problems.extend(dependencies["value"]["problems"])
    else:
        problems.append("Native package queries are UNKNOWN: " + dependencies["error"])
    report = {
        "status": "STRUCTURE_READBACK_INCOMPLETE" if problems else "STRUCTURE_READBACK_COMPLETE_GEOMETRY_PENDING",
        "structural_readback_complete": not problems,
        "rounded_reference_warnings": rounded_reference_warnings,
        "geometry_accepted": False,
        "reasons": problems,
        "warning": "Collision raycasts are not raw Landscape height vertex readback.",
        "level": LEVEL_PATH,
        "total_landscape_actors": len(landscapes),
        "total_components": total_components,
        "expected_total_components": 4096,
        "components_pass": not structure_problems(landscape_data),
        "actor_quantization_step_cm": {
            name: actor_height_step_cm(z) if math.isfinite(z) and z > 0 else None
            for name, z in scales.items()
        },
        "native_component_properties_complete": bool(landscape_data) and all(
            all(row["actual_component_properties"][prop]["complete"]
                for prop in COMPONENT_FIELDS)
            for row in landscape_data
        ),
        "native_dependencies": dependencies,
        "native_seams": native_seams,
        "native_interiors": native_interiors,
        "dependency_closure_complete": False,
        "material_render_verified": False,
        "native_reopen_after_repair": "NOT_RUN",
        "source_height_interpolation_proved": False,
        "visibility_layer_proved_in_ue": False,
        "transport_envelope": {
            "source_domain": "8000x8000 m, 16000x16000 cells at 0.5m spacing",
            "transport_envelope": "8128x8128 m, 4 tiles of 8129x8129 vertices (16257x16257 total envelope)",
            "padding_handling": "UNVERIFIED IN EXISTING UE MAP; original bake predated visibility-preserving transfer.",
            "quantization_unit_cm": None,
            "note": "Quantization uses each observed actor Scale.Z. Rounded source landmarks are not a true interpolated-height reference."
        },
        "landscapes": landscape_data,
        "sampled_heights": sampled_points,
    }
    return report


def main():
    import unreal

    project = plain_path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    try:
        preparation, preparation_identity, map_before, output = authenticated_preparation(project, os.environ)
    except Exception:
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
        raise
    report = {
        "schema_version": 2, "status": "STRUCTURE_READBACK_INCOMPLETE",
        "structural_readback_complete": False, "geometry_accepted": False,
        "source_height_interpolation_proved": False, "visibility_layer_proved_in_ue": False,
        "material_render_verified": False, "dependency_closure_complete": False,
        "source_head": preparation["source_head"], "project_root": str(project),
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "preparation_identity": preparation_identity, "map_before": map_before,
        "map_after": None, "candidate_map_unchanged": None,
        "map_lineage": preparation["map"],
        "repair_receipts_authenticated": preparation["status"] == REPAIRED_PREPARATION_STATUS,
        "reasons": [],
    }
    try:
        if not report["engine_version"].startswith("5.8.2-56702186"):
            raise RuntimeError("Unexpected native engine version")
        report.update(inspect_map(unreal, preparation))
        if report["repair_receipts_authenticated"]:
            report["native_reopen_after_repair"] = (
                "READBACK_COMPLETE_ACCEPTANCE_PENDING" if report["structural_readback_complete"]
                else "READBACK_INCOMPLETE")
    except Exception as exc:
        report["reasons"].append(f"Native reader failed: {type(exc).__name__}: {exc}")
        report["status"] = "STRUCTURE_READBACK_INCOMPLETE"
        report["structural_readback_complete"] = False
    finally:
        try:
            report["map_after"] = file_identity(project / MAP_FILE, 3 * 1024**3)
            report["candidate_map_unchanged"] = report["map_after"] == map_before
            if not report["candidate_map_unchanged"]:
                report["reasons"].append("Candidate map bytes changed")
                report["status"] = "STRUCTURE_READBACK_INCOMPLETE"
                report["structural_readback_complete"] = False
        except Exception as exc:
            report["reasons"].append("Final candidate map identity is UNKNOWN: " + str(exc))
            report["status"] = "STRUCTURE_READBACK_INCOMPLETE"
            report["structural_readback_complete"] = False
        # Exclusive evidence output; no package save, bake, import or source write.
        # Full two-sided seam vertices fit the existing 8 MiB evidence bound
        # without whitespace expansion; never truncate observations to fit.
        payload = json.dumps(finite_json(report), separators=(",", ":"), allow_nan=False)
        if len(payload.encode("utf-8")) > 8 * 1024**2:
            raise RuntimeError("Native readback exceeded its evidence bound")
        with output.open("x", encoding="utf-8") as stream:
            stream.write(payload)
        print(f"L07 structural readback: {report['status']}; geometry_accepted=false")
        unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")


def finite_json(value):
    """Keep invalid native numbers explicit as null, with their recorded errors."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: finite_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_json(item) for item in value]
    return value

if __name__ == "__main__":
    main()
