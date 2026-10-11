"""Authenticate the separate eight-motif Forge proof and import selected maps.

Explicit caller pins bind the original source-proof.json and both run manifests.
The exact recipe/upstream/code bytes are read from source_repo_root; this can be
an authenticated read-only mirror when the consumer uses another line ending.
No input normalization, generator execution, NumPy/Pillow, downloads or saves.
Only new selected texture assets can be created. World placement and native
normal-space/visual admission belong to the later isolated consumer canary.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import re
import struct

from scripts.assets import road_material_contract as source_io
from scripts.ci import official_mcp_bob_session as session
from scripts.manage_local_workspace import load_workspace
from scripts.ue import road_shoulder_material as road_material
from scripts.ue.sa_calobra_detail_capture import decode_png

ROOT = Path(__file__).resolve().parents[2]
DESTINATION_ROOT = "/Game/Generated/YACS/RoadAsphaltConsumer/CrackLayer"
CANARY_MOTIFS = ("drifting_interrupted", "short_oblique")
CHANNELS = ("BaseColor", "Normal_DX", "ORM", "DetailMasks")
SUFFIXES = {**{name: name + ".png" for name in CHANNELS}, "Height": "Height.exr"}
EXPORT_PREFIX = "YACS_Material"
GENERATOR = "yacs-material-forge-road-decals"
SOURCE_STATUS = "DECAL_MAP_CHECKS_PASS_UE_REVIEW_PENDING"
MASK_CHANNELS = {"R": "crack_core", "G": "angular_chips", "B": "faint_local_weathering"}
PENDING_FLAGS = ("world_semantics_generated", "geometry_changed", "placement_generated",
                 "ue_verified", "visual_accepted", "performance_accepted", "native_process_exit_verified")
SOURCE_FILES = {
    "adapter_sha256": "scripts/assets/material_forge_road_decals.py",
    "recipe_sha256": "worldgen/materials/material_forge/road_crack_decals.json",
    "forge_helpers_sha256": "scripts/assets/material_forge.py",
    "base_builder_sha256": "scripts/assets/build_material_maker_limestone.py",
    "render_gd_sha256": "scripts/assets/render_material_forge.gd",
    "upstreams_sha256": "worldgen/materials/material_forge/upstreams.json",
}
FALSE_FLAGS = ("saved", "world_assignment", "geometry_changed", "source_maps_modified",
               "source_texture_pixels_verified_in_ue", "normal_space_verified", "owner_visual_pass", "performance_pass")
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_MAP_BYTES = 32 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
# Root independently replayed the original immutable 16-export bundle. These
# are its actual native-host file paths and byte pins, not a new acceptance.
VERIFIED_PINS = {
    "schema_version": 1, "exact_sha": "07ebafad08bce8bc227089901cb46785079fefda", "run": "38102423216", "attempt": "1",
    "source_proof": {"file": "source-proof.json", "sha256": "bdfb2b889a8c8ed48960518909f497d822b5c34e7d4631a890368de984310afb", "size_bytes": 28571},
    "run_manifests": {repeat: {"file": repeat + "/run-manifest.json", "sha256": "4918510f4dfd656440baee73862ebb4c951a36b11ab1f446ad8953b4e8eebca6", "size_bytes": 5296}
                      for repeat in ("run-a", "run-b")},
}


def source_root():
    """Locate only the retained native source run; no search, fallback or replay."""
    relative = "material-forge/road-decals/" + VERIFIED_PINS["exact_sha"] + "/" + VERIFIED_PINS["run"] + "-" + VERIFIED_PINS["attempt"]
    root = session._safe_path(Path(load_workspace()["work"]), relative)
    source_io._safe_path(root, directory=True)
    return root


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(session._canonical(value)).hexdigest()


def _number(value, low, high, label):
    require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
            "Invalid crack source " + label)
    return float(value)


def _identity(value, label, *, with_file=False):
    keys = {"sha256", "size_bytes"} | ({"file"} if with_file else set())
    require(isinstance(value, dict) and set(value) == keys
            and isinstance(value["sha256"], str) and SHA256.fullmatch(value["sha256"])
            and type(value["size_bytes"]) is int and 0 < value["size_bytes"] <= MAX_JSON_BYTES,
            "Missing explicit immutable pin: " + label)
    if with_file:
        name = value["file"]
        require(isinstance(name, str) and name and "\\" not in name and ":" not in name
                and not name.startswith("/") and all(p not in ("", ".", "..") for p in name.split("/")),
                "Crack pin must name a plain relative file: " + label)
    return {key: value[key] for key in ("sha256", "size_bytes")}


def _pins(value):
    require(isinstance(value, dict) and set(value) == {
        "schema_version", "exact_sha", "run", "attempt", "source_proof", "run_manifests"}
        and type(value["schema_version"]) is int and value["schema_version"] == 1
        and isinstance(value["exact_sha"], str) and re.fullmatch(r"[0-9a-f]{40}", value["exact_sha"])
        and all(isinstance(value[key], str) and re.fullmatch(r"[1-9][0-9]{0,19}", value[key])
                for key in ("run", "attempt"))
        and isinstance(value["run_manifests"], dict) and set(value["run_manifests"]) == {"run-a", "run-b"},
        "Crack source needs explicit host, run and two-manifest pins")
    _identity(value["source_proof"], "source proof", with_file=True)
    require(Path(value["source_proof"]["file"]).name == "source-proof.json", "Wrong crack host receipt filename")
    for repeat, pin in value["run_manifests"].items():
        _identity(pin, repeat, with_file=True)
        require(Path(pin["file"]).name == "run-manifest.json", "Wrong crack run manifest filename")
    require(value["run_manifests"]["run-a"]["file"] != value["run_manifests"]["run-b"]["file"],
            "Crack repeats must be different input directories")
    return deepcopy(value)


def _false(value, fields, label):
    require(all(value.get(key) is False for key in fields), label + " overstates source or visual authority")


def _source_inputs(root, expected, budget):
    require(isinstance(expected, dict) and set(expected) == {"generator", "version", *SOURCE_FILES}
            and expected["generator"] == GENERATOR and type(expected["version"]) is int and expected["version"] == 1,
            "Wrong crack generator/source identity")
    inputs, data = {}, {}
    for key, relative in SOURCE_FILES.items():
        raw, identity, _ = source_io._read(session._safe_path(root, relative), MAX_JSON_BYTES, budget)
        require(identity["sha256"] == expected[key], "Crack source bytes differ: " + relative)
        inputs[relative] = identity
        data[key] = raw
    recipe = source_io._json(data["recipe_sha256"])
    require(recipe.get("schema_version") == 1 and recipe.get("id") == "road_crack_decals"
            and recipe.get("resolution") == 2048 and recipe.get("empty_border_metres") == 0.06
            and recipe.get("sampler_address") == "clamp" and recipe.get("tileable") is False
            and recipe.get("semantic_owner") == "PCG/PCGEx" and recipe.get("local_mask_channels") == MASK_CHANNELS,
            "Crack recipe physical/mask contract differs")
    motifs = recipe.get("motifs")
    require(isinstance(motifs, list) and len(motifs) == 8 and all(isinstance(m, dict) for m in motifs)
            and all(isinstance(m.get("id"), str) and re.fullmatch(r"[a-z][a-z0-9_]{2,48}", m["id"]) for m in motifs)
            and len({m["id"] for m in motifs}) == 8, "Crack recipe needs eight unique authored motifs")
    for motif in motifs:
        _number(motif.get("extent_metres"), 1.0, 2.0, "physical extent")
    return recipe, source_io._json(data["upstreams_sha256"]), inputs


def _statistics(stats, extent):
    require(isinstance(stats, dict), "Crack source lacks native-map statistics")
    bounds = {"core_coverage_fraction": (0.0004, 0.025), "total_footprint_fraction": (0.0005, 0.055),
              "normal_length_error_max": (0.0, 0.03), "normal_xy_peak": (0.015, 0.65),
              "weathering_max": (0.0, 0.18), "roughness_min": (0.84, 1.0), "border_mask_max": (0.0, 0.0)}
    for key, (low, high) in bounds.items():
        _number(stats.get(key), low, high, key)
    require(type(stats.get("border_pixels_checked")) is int
            and stats["border_pixels_checked"] == max(1, math.floor(0.06 / extent * 2048) - 2),
            "Crack source empty-border inspection differs")


def load_sources(source_root, pins, motif_ids=CANARY_MOTIFS, *, source_repo_root=ROOT):
    """Read-only full two-run authentication; no image generation or UE calls.

    The host must independently establish trust in the supplied immutable pins.
    This function checks their actual receipt content and all eighty map files.
    It never turns a caller-supplied claim into owner or shader-space acceptance.
    """
    pins = _pins(pins)
    root, repo = Path(source_root), Path(source_repo_root)
    source_io._safe_path(root, directory=True)
    source_io._safe_path(repo, directory=True)
    budget, files = [0], {}

    def read(relative, *, pin=None, sha=None, limit=MAX_JSON_BYTES, json_value=True):
        raw, identity, _ = source_io._read(session._safe_path(root, relative), limit, budget)
        if pin is not None:
            require(identity == _identity(pin, relative, with_file=True), "Pinned crack receipt bytes changed: " + relative)
        if sha is not None:
            require(isinstance(sha, str) and SHA256.fullmatch(sha) and identity["sha256"] == sha,
                    "Crack artifact bytes changed: " + relative)
        files[relative] = identity
        return source_io._json(raw) if json_value else raw

    host = read(pins["source_proof"]["file"], pin=pins["source_proof"])
    require(host.get("schema_version") == 1 and host.get("issue") == 364
            and host.get("status") == "ROAD_DECALS_SOURCE_DETERMINISM_PASS"
            and all(host.get(key) == pins[key] for key in ("exact_sha", "run", "attempt"))
            and host.get("tool_archive_hashes_verified") is True
            and host.get("native_process_exit_verified") is True
            and host.get("two_run_graph_and_map_bytes_equal") is True and host.get("error") is None
            and host.get("human_visual_status") == "PENDING_FINAL_M3"
            and host.get("performance_status") == "DEFERRED_AFTER_M3", "Crack host proof is incomplete or belongs to another run")
    _false(host, ("unreal_consumption_verified", "world_mutation", "performance_pass"), "Crack host")
    recipe, upstreams, source_files = _source_inputs(repo, host.get("source_identity"), budget)
    ids = tuple(m["id"] for m in recipe["motifs"])
    require(isinstance(motif_ids, (list, tuple)) and 1 <= len(motif_ids) <= 8
            and all(isinstance(m, str) and m in ids for m in motif_ids)
            and len(set(motif_ids)) == len(motif_ids), "Requested crack motifs are missing or duplicated")
    selected = tuple(m for m in ids if m in motif_ids)
    comparison = host.get("comparison", {})
    require(comparison.get("status") == "DECAL_TWO_RUN_MAP_BYTES_MATCH_HOST_RECEIPT_PENDING"
            and comparison.get("deterministic") is True and comparison.get("native_decode_verified") is True
            and comparison.get("requires_existing_host_pin_and_exit_verification") is True
            and comparison.get("motif_count") == 8 and comparison.get("maps_per_motif") == 5
            and comparison.get("mismatches") == [] and comparison.get("source_identity") == host["source_identity"],
            "Crack host lacks the linked two-run comparison")
    _false(comparison, PENDING_FLAGS, "Crack comparison")
    expected_runs = [{"repeat": repeat, "directory": repeat,
                      "manifest_sha256": pins["run_manifests"][repeat]["sha256"]} for repeat in ("run-a", "run-b")]
    require(host.get("runs") == expected_runs, "Crack host manifests differ from explicit pins")
    require(comparison.get("left_manifest_sha256") == expected_runs[0]["manifest_sha256"]
            and comparison.get("right_manifest_sha256") == expected_runs[1]["manifest_sha256"],
            "Crack comparison manifest identities differ")
    processes = host.get("processes")
    expected_order = [(repeat, motif) for repeat in ("run-a", "run-b") for motif in ids]
    require(isinstance(processes, list) and len(processes) == 16
            and [(p.get("repeat"), p.get("motif")) for p in processes] == expected_order,
            "Crack proof needs all sixteen ordered native exits")
    for process in processes:
        require(type(process.get("pid")) is int and process["pid"] > 0
                and process.get("exit_observed") is True and type(process.get("exit_code")) is int
                and process["exit_code"] == 0 and process.get("stopped_on_failure") is False,
                "Crack renderer did not complete as an observed owned process")
        _number(process.get("elapsed_seconds"), 0.0, 1200.0, "process duration")
        _number(process.get("deadline_seconds"), 1, 180, "process deadline")

    repeats = {}
    for repeat in ("run-a", "run-b"):
        pin = pins["run_manifests"][repeat]
        parent = Path(pin["file"]).parent
        manifest = read(pin["file"], pin=pin)
        require(manifest.get("schema_version") == 1 and manifest.get("generator") == GENERATOR
                and manifest.get("source_identity") == host["source_identity"] and manifest.get("status") == SOURCE_STATUS,
                "Crack run source/validation contract differs")
        _false(manifest, PENDING_FLAGS, "Crack run")
        entries, validations = manifest.get("variants"), manifest.get("validations")
        require(isinstance(entries, list) and [v.get("motif") for v in entries] == list(ids)
                and isinstance(validations, list) and [v.get("motif") for v in validations] == list(ids),
                "Crack run omitted or reordered a motif")
        motifs, outlines = {}, set()
        for authored, entry, validation_row in zip(recipe["motifs"], entries, validations, strict=True):
            motif = authored["id"]
            require(entry.get("directory") == motif, "Crack motif directory escaped its identity")
            directory = parent / motif

            def item(name, **kwargs):
                return read((directory / name).as_posix(), **kwargs)

            provenance = item("provenance.json", sha=entry.get("provenance_sha256"))
            required = {"motif": motif, "generator": GENERATOR, "generator_version": 1,
                        "source_identity": host["source_identity"], "graph_sha256": entry.get("graph_sha256"),
                        "draw_instructions_sha256": entry.get("draw_instructions_sha256"),
                        "physical_extent_metres": authored["extent_metres"], "resolution": 2048,
                        "empty_border_metres": 0.06, "sampler_address": "clamp", "tileable": False,
                        "semantic_owner": "PCG/PCGEx", "local_mask_channels": MASK_CHANNELS,
                        "normal_convention": "DirectX", "normal_strength": 0.16,
                        "height_is_authoring_only": True, "displacement_enabled": False,
                        "asset_kind": "local_surface_decal", "upstreams": upstreams, "node_count": 6}
            require(all(provenance.get(key) == value for key, value in required.items()), "Crack motif provenance differs")
            _false(provenance, PENDING_FLAGS, "Crack provenance")
            graph = item("Material.ptex", sha=entry.get("graph_sha256"))
            instructions = item("draw-instructions.json", sha=entry.get("draw_instructions_sha256"))
            require(isinstance(graph.get("nodes"), list) and len(graph["nodes"]) == 6
                    and instructions.get("extent_metres") == authored["extent_metres"], "Crack graph/metric drawing differs")
            forms = [n for n in graph["nodes"] if n.get("name") == "Road_Crack_Form"]
            require(len(forms) == 1 and isinstance(forms[0].get("shader_model", {}).get("global"), str)
                    and hashlib.sha256(forms[0]["shader_model"]["global"].encode()).hexdigest()
                    == provenance.get("surface_shader_sha256"), "Crack surface field differs from provenance")
            validation = item("validation.json", sha=validation_row.get("validation_sha256"))
            require(validation.get("status") == SOURCE_STATUS and validation.get("motif") == motif
                    and validation.get("graph_sha256") == entry["graph_sha256"]
                    and validation.get("normal_convention") == "DirectX" and validation.get("sampler_address") == "clamp"
                    and validation.get("native_decode_verified") is True, "Crack native-map validation is incomplete")
            _false(validation, PENDING_FLAGS, "Crack validation")
            _statistics(validation.get("mask_statistics"), authored["extent_metres"])
            outline = validation.get("decoded_core_outline_sha256")
            require(isinstance(outline, str) and SHA256.fullmatch(outline) and outline not in outlines,
                    "Crack native motifs are missing or repeat one decoded outline")
            outlines.add(outline)
            native = item("export/" + EXPORT_PREFIX + "_native-check.json", sha=validation.get("native_check_sha256"))
            require(native.get("valid") is True and native.get("engine", {}).get("hash") == upstreams["godot"]["commit"]
                    and set(native.get("images", {})) == set(SUFFIXES.values())
                    and set(validation.get("maps", {})) == set(SUFFIXES), "Crack source lacks all five Godot decodes")
            maps = {}
            for channel, suffix in SUFFIXES.items():
                row, decoded = validation["maps"][channel], native["images"][suffix]
                relative = "export/" + EXPORT_PREFIX + "_" + suffix
                require(row.get("path") == relative and row.get("size") == [2048, 2048]
                        and decoded.get("width") == decoded.get("height") == 2048
                        and decoded.get("sha256") == row.get("sha256"), "Crack native decode/map identity differs")
                raw = item(relative, sha=row.get("sha256"), limit=MAX_MAP_BYTES, json_value=False)
                if channel == "Height":
                    require(raw[:4] == b"\x76\x2f\x31\x01", "Crack authoring height is not an EXR")
                else:
                    require(len(raw) > 33 and raw[:8] == b"\x89PNG\r\n\x1a\n"
                            and struct.unpack_from(">IIBBBBB", raw, 16) in (
                                (2048, 2048, 8, 2, 0, 0, 0), (2048, 2048, 8, 6, 0, 0, 0)),
                            "Crack source is not an RGB(A) 2K PNG")
                path = (directory / relative).as_posix()
                maps[channel] = {"file": path, **files[path]}
            process = processes[expected_order.index((repeat, motif))]
            item("source-runner.log", sha=process.get("log_sha256"), limit=16 * 1024 * 1024, json_value=False)
            motifs[motif] = {"motif": motif, "extent_cm": float(authored["extent_metres"]) * 100.0,
                             "empty_border_cm": 6.0, "resolution": 2048, "graph_sha256": entry["graph_sha256"],
                             "draw_instructions_sha256": entry["draw_instructions_sha256"],
                             "decoded_core_outline_sha256": outline, "maps": maps,
                             "mask_statistics": validation["mask_statistics"]}
        repeats[repeat] = motifs
    for motif in ids:
        left, right = deepcopy(repeats["run-a"][motif]), deepcopy(repeats["run-b"][motif])
        for values in (left, right):
            values["maps"] = {c: {k: v for k, v in row.items() if k != "file"} for c, row in values["maps"].items()}
        require(left == right, "Crack repeated graph, map bytes or native statistics differ")
    return {"schema_version": 1, "status": "ROAD_CRACK_SOURCE_BYTES_AUTHENTICATED",
            "pins": pins, "pins_sha256": digest(pins), "source_identity": host["source_identity"],
            "selected_motifs": list(selected), "motifs": {m: repeats["run-a"][m] for m in selected},
            "source_inputs": source_files, "files": files, "verified_map_count": 80,
            "verified_process_count": 16, "read_only": True, "normal_space_verified": False,
            "owner_visual_pass": False, "performance_pass": False}


def neutral_border(decoded, extent_cm, border_cm):
    """Measure actual encoded neutral pixels; no invented half-gray constants.

    decoded maps come from the existing bounded stdlib PNG decoder. The native
    Forge receipt remains a separate proof, bound to these exact source bytes.
    """
    require(set(decoded) == set(CHANNELS), "Neutral crack border needs all four runtime maps")
    width, height = decoded["BaseColor"][:2]
    require(width == height and width >= 8, "Invalid neutral border dimensions")
    ring = max(1, math.floor(border_cm / extent_cm * width) - 2)
    require(0 < ring < width / 2, "Invalid neutral source border")
    values, max_deltas = {}, {}
    for channel, (w, h, channels, pixels) in decoded.items():
        require((w, h) == (width, height) and channels in (3, 4) and len(pixels) == w * h * channels,
                "Neutral border decode differs across channels")
        reference = tuple(pixels[:3])
        delta = 0
        for y in range(height):
            spans = ((0, width),) if y < ring or y >= height - ring else ((0, ring), (width - ring, width))
            for start, end in spans:
                for x in range(start, end):
                    index = (y * width + x) * channels
                    delta = max(delta, *(abs(pixels[index + c] - reference[c]) for c in range(3)))
                    require(channels == 3 or pixels[index + 3] == 255, "Crack source alpha changed in its empty border")
        require(delta <= (0 if channel == "DetailMasks" else 1), "Crack source border is not neutral: " + channel)
        values[channel], max_deltas[channel] = list(reference), delta
    require(values["DetailMasks"] == [0, 0, 0], "Crack masks leak into the empty border")
    require(all(v in (127, 128) for v in values["Normal_DX"][:2]) and values["Normal_DX"][2] >= 254,
            "Crack source border has a non-neutral DirectX normal")
    require(values["ORM"][0] >= 254 and values["ORM"][1] >= 214 and values["ORM"][2] <= 1,
            "Crack source border is not dry, non-metallic and unoccluded")
    require(all(2 <= v <= 250 for v in values["BaseColor"]), "Crack neutral color cannot form a stable linear ratio")

    def linear(value):
        s = value / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return {"border_pixels_checked": ring, "encoded_rgb8": values, "border_max_rgb8_delta": max_deltas,
            "base_color_linear": [linear(v) for v in values["BaseColor"]],
            "orm_linear": [v / 255.0 for v in values["ORM"]],
            "normal_xy_bias": [2.0 * v / 255.0 - 1.0 for v in values["Normal_DX"][:2]],
            "source_png_border_verified": True, "ue_normal_space_verified": False}


@lru_cache(maxsize=8)
def _decode_neutral_maps(root, extent_cm, border_cm, map_identities):
    # Cache only this small measurement, never decoded images or source trust.
    # Every public caller first reauthenticates the full eighty-map proof. The
    # cache key includes each exact map hash/size and the physical footprint.
    decoded = {channel: decode_png(session._safe_path(Path(root), relative), (2048, 2048))
               for channel, relative, sha, size in map_identities}
    result = neutral_border(decoded, extent_cm, border_cm)
    budget = [0]
    for channel, relative, sha, size in map_identities:
        _, identity, _ = source_io._read(session._safe_path(Path(root), relative), MAX_MAP_BYTES, budget)
        require(identity == {"sha256": sha, "size_bytes": size}, "Crack map bytes changed during neutral-border decoding")
    return result


def _neutral_sources(root, source):
    return {motif: deepcopy(_decode_neutral_maps(str(Path(root).resolve()), data["extent_cm"], data["empty_border_cm"],
            tuple((c, data["maps"][c]["file"], data["maps"][c]["sha256"], data["maps"][c]["size_bytes"]) for c in CHANNELS)))
            for motif, data in source["motifs"].items()}


def asset_paths(source):
    key = digest({"pins_sha256": source["pins_sha256"], "motifs": source["selected_motifs"]})[:12]
    root = DESTINATION_ROOT + "/" + key
    return {"root": root, "textures": {motif: {channel: root + "/" + motif + "/T_Crack_" + channel
            + ".T_Crack_" + channel for channel in CHANNELS} for motif in source["selected_motifs"]}}


def _context(api):
    require(api.SystemLibrary.get_engine_version() == road_material.ENGINE_VERSION,
            "Crack import requires the pinned UE build")
    require(Path(api.Paths.convert_relative_path_to_full(api.Paths.project_dir())).resolve() == ROOT.resolve()
            == session.ROOT.resolve(), "Crack import belongs to another project checkout")
    session._assert_isolated_root()


def _import_api(api):
    evidence = {}
    for cls, name in ((api.AssetToolsHelpers.get_asset_tools(), "import_asset_tasks"),
                      (api.Texture2D, "blueprint_get_size_x"), (api.Texture2D, "blueprint_get_size_y")):
        method = getattr(cls, name, None)
        doc = str(getattr(method, "__doc__", "") or "")
        require(callable(method) and 0 < len(doc) <= 32768, "Required native crack import API is unavailable: " + name)
        evidence[name] = {"signature": doc.splitlines()[0], "sha256": hashlib.sha256(doc.encode()).hexdigest()}
    require(callable(getattr(api, "AssetImportTask", None)) and hasattr(api.TextureAddress, "TA_CLAMP"),
            "Native clamped texture import API is unavailable")
    return evidence


def _settings(api, channel):
    return {"srgb": channel == "BaseColor", "compression_settings": {
        "BaseColor": api.TextureCompressionSettings.TC_DEFAULT, "Normal_DX": api.TextureCompressionSettings.TC_NORMALMAP,
        "ORM": api.TextureCompressionSettings.TC_MASKS, "DetailMasks": api.TextureCompressionSettings.TC_MASKS}[channel],
        "address_x": api.TextureAddress.TA_CLAMP, "address_y": api.TextureAddress.TA_CLAMP,
        **({"flip_green_channel": False} if channel == "Normal_DX" else {})}


def _verify_textures(api, paths):
    result = {}
    for motif, channels in paths["textures"].items():
        result[motif] = {}
        for channel, path in channels.items():
            texture = api.load_asset(path)
            require(texture is not None and isinstance(texture, api.Texture2D) and texture.get_path_name() == path,
                    "Crack texture object identity differs: " + channel)
            require(all(texture.get_editor_property(k) == v for k, v in _settings(api, channel).items())
                    and texture.blueprint_get_size_x() == texture.blueprint_get_size_y() == 2048,
                    "Crack native texture size, CLAMP or color/normal settings differ: " + channel)
            result[motif][channel] = texture
    return result


def import_textures(api, source_root, pins, motif_ids=CANARY_MOTIFS, *, source_repo_root=ROOT):
    """Return (native textures by motif, receipt). New unsaved assets only."""
    _context(api)
    source = load_sources(source_root, pins, motif_ids, source_repo_root=source_repo_root)
    neutral = _neutral_sources(source_root, source)
    paths, evidence = asset_paths(source), _import_api(api)
    require(all(not api.EditorAssetLibrary.does_asset_exist(path)
                for channels in paths["textures"].values() for path in channels.values()),
            "Crack texture destination exists; refuse overwrite")
    for motif, channels in paths["textures"].items():
        for channel, object_path in channels.items():
            package, name = object_path.split(".")[0].rsplit("/", 1)
            task = api.AssetImportTask()
            for prop, value in {"filename": str(session._safe_path(Path(source_root), source["motifs"][motif]["maps"][channel]["file"])),
                                "destination_path": package, "destination_name": name,
                                "automated": True, "replace_existing": False, "save": False}.items():
                task.set_editor_property(prop, value)
            api.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            require(list(task.get_editor_property("imported_object_paths")) == [object_path], "Native crack texture import failed")
            texture = api.load_asset(object_path)
            require(texture is not None and isinstance(texture, api.Texture2D), "Imported crack texture is missing")
            for key, value in _settings(api, channel).items():
                texture.set_editor_property(key, value)
    textures = _verify_textures(api, paths)
    require(load_sources(source_root, pins, motif_ids, source_repo_root=source_repo_root) == source,
            "Crack inputs changed during native texture import")
    return textures, {"schema_version": 1, "status": "ROAD_CRACK_TEXTURES_IMPORTED_REVIEW_PENDING",
                      "engine_version": road_material.ENGINE_VERSION, "sources": source, "assets": paths,
                      "neutral_sources": neutral, "native_api": evidence, "texture_count": len(textures) * 4,
                      "import_settings_readback_verified": True, "caller_saved_asset_bytes_required": True,
                      **{name: False for name in FALSE_FLAGS}}


def verify_import(api, source_root, pins, receipt, *, source_repo_root=ROOT):
    """Read-only fresh native settings/source checks; saved asset bytes are caller-owned."""
    _context(api)
    require(isinstance(receipt, dict) and receipt.get("schema_version") == 1
            and receipt.get("status") == "ROAD_CRACK_TEXTURES_IMPORTED_REVIEW_PENDING"
            and receipt.get("engine_version") == road_material.ENGINE_VERSION
            and receipt.get("caller_saved_asset_bytes_required") is True
            and receipt.get("import_settings_readback_verified") is True, "Wrong crack import receipt")
    _false(receipt, FALSE_FLAGS, "Crack import")
    source = load_sources(source_root, pins, receipt.get("sources", {}).get("selected_motifs"), source_repo_root=source_repo_root)
    require(receipt.get("sources") == source and receipt.get("assets") == asset_paths(source)
            and receipt.get("texture_count") == 4 * len(source["selected_motifs"])
            and receipt.get("neutral_sources") == _neutral_sources(source_root, source),
            "Crack import source, extent or neutral border differs")
    return _verify_textures(api, receipt["assets"])
