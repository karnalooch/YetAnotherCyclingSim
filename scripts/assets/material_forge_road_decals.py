"""Author and check the bounded road-crack source addon, without UE placement.

Use the existing pinned Material Maker install to author two fresh runs; invoke
the commands printed by ``render-commands`` through the existing GPU host runner,
then ``validate`` each run and ``compare`` them. The unchanged Forge GDScript
exports and natively decodes all five maps. This adapter neither downloads tools
nor launches Godot. Native process exit and host identity remain the host proof's
responsibility; identical map bytes alone do not establish either of them.

The JSON paths are authored shapes, with millimetre-scale deterministic edge
irregularity. They are local, clamped surface events, not a tiled crack noise or
a world-placement generator. Their source proof is separate from the pinned
aged_mountain_asphalt/dry_varied base proof.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECIPE = ROOT / "worldgen/materials/material_forge/road_crack_decals.json"
GENERATOR = "yacs-material-forge-road-decals"
VERSION = 1
MAX_SEGMENTS = 64
MAX_CHIPS = 12
MAX_GRAPH_NODES = 6
MAX_KNOT_DEVIATION_METRES = 0.0032
MAX_EDGE_RADIUS_SCALE = 1.22
MAP_SUFFIXES = ("BaseColor.png", "Normal_DX.png", "ORM.png", "Height.exr", "DetailMasks.png")
MASK_CHANNELS = {"R": "crack_core", "G": "angular_chips", "B": "faint_local_weathering"}
PENDING_FLAGS = {
    "world_semantics_generated": False,
    "geometry_changed": False,
    "placement_generated": False,
    "ue_verified": False,
    "visual_accepted": False,
    "performance_accepted": False,
    "native_process_exit_verified": False,
}


def _load_forge():
    path = ROOT / "scripts/assets/material_forge.py"
    spec = importlib.util.spec_from_file_location("yacs_decal_forge_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load existing Material Forge helpers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


forge = _load_forge()


def _number(value: Any, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} outside [{low}, {high}]")
    return float(value)


def _keys(value: dict, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"Unexpected {label} fields")


def _unit(seed: int, token: str) -> float:
    """Version-independent random value, used only for bounded local edges."""
    digest = hashlib.sha256(f"{seed}:{token}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") / (2**64 - 1)


def outline_fingerprint(motif: dict) -> str:
    """Ignore seed, width, chips, translation, scale and quarter-turn/mirror disguises."""
    paths = [np.array(stroke["points"], dtype=np.float64)[:, :2] for stroke in motif["strokes"]]
    points = np.concatenate(paths)
    centre = (points.min(axis=0) + points.max(axis=0)) * 0.5
    scale = float(np.max(np.ptp(points, axis=0)))
    if scale <= 0:
        raise ValueError("Empty authored outline")
    variants = []
    for swap in (False, True):
        for sign_x, sign_y in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            transformed = []
            for path in paths:
                normalized = (path - centre) / scale
                if swap:
                    normalized = normalized[:, ::-1]
                normalized = np.round(normalized * [sign_x, sign_y], 6)
                normalized[np.abs(normalized) < 0.0000005] = 0.0
                forward = tuple(tuple(float(v) for v in point) for point in normalized)
                transformed.append(min(forward, forward[::-1]))
            variants.append(tuple(sorted(transformed)))
    return forge.canonical_hash(min(variants))


def drawing_instructions(motif: dict, resolution: int, border: float) -> dict:
    """Compile authored knots to a small, immutable list of metric primitives."""
    extent = float(motif["extent_metres"])
    seed = motif["seed"]
    segments = []
    for stroke_index, stroke in enumerate(motif["strokes"]):
        points = stroke["points"]
        for index, (left, right) in enumerate(zip(points, points[1:])):
            a = np.array(left[:2], dtype=np.float64) * extent
            b = np.array(right[:2], dtype=np.float64) * extent
            delta = b - a
            length = float(np.linalg.norm(delta))
            if length < 0.004:
                raise ValueError("Authored knots must be at least 4 mm apart")
            token = f"stroke-{stroke_index}-segment-{index}"
            perpendicular = np.array([-delta[1], delta[0]]) / length
            radius_a, radius_b = float(left[2]) * 0.0005, float(right[2]) * 0.0005
            knots = [(a, radius_a)]
            # Three unequally spaced internal knots keep the authored large
            # path, while removing long ruler-straight walls. Branch endpoints
            # stay fixed; local deviations are bounded to 3.2 mm.
            for knot in range(3):
                key = token + f"-knot-{knot}"
                t = (knot + 1) / 4 + 0.11 * (_unit(seed, key + "-position") - 0.5)
                offset = MAX_KNOT_DEVIATION_METRES * math.sin(math.pi * t)
                offset *= 2 * _unit(seed, key + "-offset") - 1
                middle = a + t * delta + offset * perpendicular
                radius_mid = ((1 - t) * radius_a + t * radius_b)
                radius_mid *= 0.60 + 0.72 * _unit(seed, key + "-width")
                knots.append((middle, radius_mid))
            knots.append((b, radius_b))
            for knot, ((start, ra), (end, rb)) in enumerate(zip(knots, knots[1:])):
                segments.append({
                    "start_m": [round(float(v), 9) for v in start],
                    "end_m": [round(float(v), 9) for v in end],
                    "radius_start_m": round(ra, 9),
                    "radius_end_m": round(rb, 9),
                    "strength": float(stroke["strength"]),
                    "stroke": stroke_index,
                    "edge_seed": round(3 + 97 * _unit(seed, token + f"-edge-{knot}"), 9),
                })
    chips = []
    for index, chip in enumerate(motif["chips"]):
        chips.append({
            "centre_m": [round(float(v) * extent, 9) for v in chip["centre"]],
            "half_size_m": [round(float(v) * 0.0005, 9) for v in chip["size_mm"]],
            "angle_radians": round(math.radians(chip["angle_degrees"]), 9),
            "corner_cuts": [round(1.20 + 0.55 * _unit(seed, f"chip-{index}-{n}"), 9)
                            for n in range(4)],
            "strength": float(chip["strength"]),
        })
    if not 1 <= len(segments) <= MAX_SEGMENTS or len(chips) > MAX_CHIPS:
        raise ValueError("Decal primitive budget exceeded")
    aa = 0.65 * extent / resolution
    clearance = extent
    for item in segments:
        # Includes the wider, faint weathering halo and its antialias edge.
        radius = 2 * MAX_EDGE_RADIUS_SCALE * max(item["radius_start_m"], item["radius_end_m"]) + 0.0015 + aa
        for point in (item["start_m"], item["end_m"]):
            clearance = min(clearance, *[min(v, extent - v) - radius for v in point])
    for item in chips:
        radius = math.hypot(*item["half_size_m"]) + aa
        clearance = min(clearance, *[min(v, extent - v) - radius for v in item["centre_m"]])
    if clearance < border + 2 * extent / resolution:
        raise ValueError("Decal primitives intrude into the empty border")
    return {
        "schema_version": 1,
        "coordinate_unit": "metre",
        "extent_metres": extent,
        "resolution": resolution,
        "empty_border_metres": border,
        "minimum_primitive_clearance_metres": round(clearance, 9),
        "antialias_metres": round(aa, 12),
        "segments": segments,
        "chips": chips,
    }


def load_recipe(path: Path = DEFAULT_RECIPE) -> dict:
    recipe = forge._json(path)
    _keys(recipe, {"schema_version", "id", "description", "resolution", "empty_border_metres",
                   "sampler_address", "tileable", "semantic_owner", "local_mask_channels", "motifs"}, "recipe")
    if recipe["schema_version"] != 1 or recipe["id"] != "road_crack_decals":
        raise ValueError("Unsupported road decal recipe")
    if type(recipe["resolution"]) is not int or recipe["resolution"] not in (1024, 2048):
        raise ValueError("Decal resolution must be 1024 or 2048")
    border = _number(recipe["empty_border_metres"], 0.05, 0.12, "empty border")
    if (recipe["sampler_address"] != "clamp" or recipe["tileable"] is not False
            or recipe["semantic_owner"] != forge.SEMANTIC_OWNER
            or recipe["local_mask_channels"] != MASK_CHANNELS):
        raise ValueError("Decals must be clamped local masks under PCG/PCGEx semantics")
    motifs = recipe["motifs"]
    if not isinstance(motifs, list) or len(motifs) != 8:
        raise ValueError("Exactly eight authored road-crack motifs are required")
    ids, outlines = set(), set()
    for motif in motifs:
        _keys(motif, {"id", "label", "extent_metres", "seed", "strokes", "chips"}, "motif")
        if not isinstance(motif["id"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,48}", motif["id"]):
            raise ValueError("Invalid motif id")
        if motif["id"] in ids:
            raise ValueError("Duplicate motif id")
        ids.add(motif["id"])
        _number(motif["extent_metres"], 1.0, 2.0, "physical extent")
        _number(motif["seed"], 1, 2**31 - 1, "seed")
        if type(motif["seed"]) is not int:
            raise ValueError("Seed must be an integer")
        if not isinstance(motif["strokes"], list) or not 1 <= len(motif["strokes"]) <= 8:
            raise ValueError("Each motif needs one to eight authored strokes")
        for stroke in motif["strokes"]:
            _keys(stroke, {"strength", "points"}, "stroke")
            _number(stroke["strength"], 0.25, 0.95, "stroke strength")
            points = stroke["points"]
            if not isinstance(points, list) or not 2 <= len(points) <= 12:
                raise ValueError("Each stroke needs two to twelve authored knots")
            for point in points:
                if not isinstance(point, list) or len(point) != 3:
                    raise ValueError("Knots require normalized u, v and full width in millimetres")
                _number(point[0], 0, 1, "knot u")
                _number(point[1], 0, 1, "knot v")
                _number(point[2], 0.2, 9.0, "full crack width mm")
        if not isinstance(motif["chips"], list) or len(motif["chips"]) > MAX_CHIPS:
            raise ValueError("Chip budget exceeded")
        for chip in motif["chips"]:
            _keys(chip, {"centre", "size_mm", "angle_degrees", "strength"}, "chip")
            if (not isinstance(chip["centre"], list) or not isinstance(chip["size_mm"], list)
                    or len(chip["centre"]) != 2 or len(chip["size_mm"]) != 2):
                raise ValueError("Chip centre and size must be two-dimensional")
            for value in chip["centre"]:
                _number(value, 0, 1, "chip position")
            for value in chip["size_mm"]:
                _number(value, 2, 18, "chip size mm")
            _number(chip["angle_degrees"], -180, 180, "chip angle")
            _number(chip["strength"], 0.25, 0.95, "chip strength")
        drawing_instructions(motif, recipe["resolution"], border)
        outline = outline_fingerprint(motif)
        if outline in outlines:
            raise ValueError("Authored outlines cannot be transformed copies of another motif")
        outlines.add(outline)
    return recipe


FIELD_HELPERS = r"""
float yacs_road_edge_noise(float p) {
    float cell = floor(p);
    float f = fract(p);
    f = f*f*(3.0-2.0*f);
    float a = fract(sin(cell*127.13+17.31)*43758.5453);
    float b = fract(sin((cell+1.0)*127.13+17.31)*43758.5453);
    return mix(a,b,f);
}
vec2 yacs_road_segment(vec2 p, vec2 a, vec2 b, float ra, float rb, float strength, float salt, float aa) {
    vec2 ab = b-a;
    float along = clamp(dot(p-a,ab)/dot(ab,ab),0.0,1.0);
    float distance_to_line = length(p-a-along*ab);
    float support = 2.0*1.22*max(ra,rb)+0.0015+aa;
    if (distance_to_line > support) { return vec2(0.0); }
    float radius = mix(ra,rb,along);
    float signed_side = dot(p-a,vec2(-ab.y,ab.x));
    float side_seed = signed_side < 0.0 ? salt : salt+41.3;
    float metric_along = along*length(ab);
    float coarse_edge = yacs_road_edge_noise(metric_along/0.0035+side_seed);
    float fine_edge = yacs_road_edge_noise(metric_along/0.0017-0.37*side_seed);
    radius *= 0.66+0.56*(0.64*coarse_edge+0.36*fine_edge);
    float core = 1.0-smoothstep(max(0.0,radius-aa),radius+aa,distance_to_line);
    float halo_radius = 2.0*radius+0.0015;
    float halo = 1.0-smoothstep(radius,halo_radius+aa,distance_to_line);
    return strength*vec2(core,0.16*halo);
}
float yacs_road_chip(vec2 p, vec2 centre, vec2 half_size, float angle, vec4 cuts, float strength, float aa) {
    vec2 delta = p-centre;
    vec2 q = vec2(cos(angle)*delta.x+sin(angle)*delta.y,-sin(angle)*delta.x+cos(angle)*delta.y);
    vec2 n = q/half_size;
    float scale = min(half_size.x,half_size.y)*0.70710678118;
    float diagonal = max(max(n.x+n.y-cuts.x,n.x-n.y-cuts.y),max(-n.x+n.y-cuts.z,-n.x-n.y-cuts.w));
    float distance_to_chip = max(max(abs(q.x)-half_size.x,abs(q.y)-half_size.y),diagonal*scale);
    return strength*(1.0-smoothstep(-aa,aa,distance_to_chip));
}
"""


def _float(value: float) -> str:
    return f"{float(value):.12f}"


def _vec(values: list[float]) -> str:
    return f"vec{len(values)}(" + ",".join(_float(v) for v in values) + ")"


def surface_shader(instructions: dict) -> str:
    extent = _float(instructions["extent_metres"])
    border = _float(instructions["empty_border_metres"])
    lines = [FIELD_HELPERS, "vec4 yacs_road_decal(vec2 uv) {",
             f"    vec2 p = uv*{extent};",
             f"    float edge_distance = min(min(p.x,p.y),min({extent}-p.x,{extent}-p.y));",
             f"    if (edge_distance <= {border}) {{ return vec4(0.5,0.0,0.0,0.0); }}",
             f"    float aa = {_float(instructions['antialias_metres'])};",
             "    vec2 strokes = vec2(0.0);", "    float chips = 0.0;"]
    for item in instructions["segments"]:
        args = [_vec(item["start_m"]), _vec(item["end_m"]),
                _float(item["radius_start_m"]), _float(item["radius_end_m"]),
                _float(item["strength"]), _float(item["edge_seed"])]
        lines.append("    strokes = max(strokes,yacs_road_segment(p," + ",".join(args) + ",aa));")
    for item in instructions["chips"]:
        args = [_vec(item["centre_m"]), _vec(item["half_size_m"]), _float(item["angle_radians"]),
                _vec(item["corner_cuts"]), _float(item["strength"])]
        lines.append("    chips = max(chips,yacs_road_chip(p," + ",".join(args) + ",aa));")
    lines += ["    float weathering = max(strokes.y,0.10*chips);",
              "    return vec4(0.5-0.055*strokes.x-0.018*chips,strokes.x,chips,weathering);", "}", ""]
    return "\n".join(lines)


def source_identity(recipe_path: Path = DEFAULT_RECIPE) -> dict:
    return {
        "generator": GENERATOR,
        "version": VERSION,
        "adapter_sha256": forge.sha256_path(Path(__file__)),
        "recipe_sha256": forge.sha256_path(recipe_path),
        "forge_helpers_sha256": forge.sha256_path(ROOT / "scripts/assets/material_forge.py"),
        "base_builder_sha256": forge.sha256_path(ROOT / "scripts/assets/build_material_maker_limestone.py"),
        "render_gd_sha256": forge.sha256_path(ROOT / "scripts/assets/render_material_forge.gd"),
        "upstreams_sha256": forge.sha256_path(forge.DEFAULT_UPSTREAMS),
    }


def author_variant(mm_install: Path, destination: Path, motif: dict, recipe: dict, identity: dict) -> dict:
    if destination.exists():
        raise FileExistsError(f"Refusing existing decal directory: {destination}")
    base = forge._load_base_builder()
    # The shared builder prints its temporary limestone filename. Keep this
    # adapter's CLI stdout as a single parseable JSON result for the host.
    with contextlib.redirect_stdout(io.StringIO()):
        base.build(mm_install, destination)
    old_graph = destination / "SaCalobra_PaleLimestone.ptex"
    material = next(node for node in forge._json(old_graph)["nodes"] if node["name"] == "PBR_Output")
    instructions = drawing_instructions(motif, recipe["resolution"], recipe["empty_border_metres"])
    field = surface_shader(instructions)
    shape = base.shader("Road_Crack_Form", "Authored local road fracture", 0, 0, [],
                        [base.output(label, "$(name_uv)_field." + swizzle)
                         for label, swizzle in (("Height", "r"), ("Crack", "g"), ("Chips", "b"), ("Weathering", "a"))],
                        code="vec4 $(name_uv)_field = yacs_road_decal($uv);", global_code=field)
    inputs = [base.source(name) for name in ("crack", "chips", "weathering")]
    color = base.shader("Road_Crack_Color", "Warm dry fracture and angular losses", 400, -180, inputs,
                        [base.output("Base Color", "$(name_uv)_color", "rgb")],
                        code="vec3 $(name_uv)_color = mix(vec3(0.27,0.26,0.24),vec3(0.105,0.100,0.092),$crack($uv));\n"
                             "$(name_uv)_color = mix($(name_uv)_color,vec3(0.16,0.152,0.139),0.65*$chips($uv));\n"
                             "$(name_uv)_color += vec3(0.07,0.060,0.045)*$weathering($uv);")
    response = base.shader("Road_Crack_Response", "Dry shallow surface response", 400, 140,
                           inputs + [base.source("height")],
                           [base.output("Roughness", "clamp(0.90+0.04*$crack($uv)+0.02*$chips($uv),0.0,1.0)"),
                            base.output("AO", "clamp(1.0-0.14*$crack($uv)-0.05*$chips($uv),0.0,1.0)"),
                            base.output("Depth", "1.0-$height($uv)")])
    normal = {"name": "Height_Normal", "type": "normal_map2", "node_position": {"x": 450, "y": 450},
              "parameters": {"size": int(math.log2(recipe["resolution"])), "strength": 0.16, "buffer": 1, "param2": 0}}
    masks = base.shader("Material_Local_Masks", "Clamped local decal masks", 710, 520, inputs,
                        [base.output("Detail Masks", "vec3($crack($uv),$chips($uv),$weathering($uv))", "rgb")])
    material["parameters"].update(size=int(math.log2(recipe["resolution"])), emission_energy=0)
    material["shader_model"]["exports"]["YACS/Textures"]["files"].append(
        {"type": "texture", "file_name": "$(path_prefix)_DetailMasks.png", "output": 2})
    connections = []

    def connect(left, port, right, target):
        connections.append({"from": left, "from_port": port, "to": right, "to_port": target})

    for target in ("Road_Crack_Color", "Road_Crack_Response", "Material_Local_Masks"):
        for i in range(3):
            connect("Road_Crack_Form", i + 1, target, i)
    connect("Road_Crack_Form", 0, "Road_Crack_Response", 3)
    connect("Road_Crack_Form", 0, "Height_Normal", 0)
    ports = {p["name"]: i for i, p in enumerate(material["shader_model"]["inputs"])}
    for node, port, target in (("Road_Crack_Color", 0, "albedo_tex"), ("Road_Crack_Response", 0, "roughness_tex"),
                               ("Road_Crack_Response", 1, "ao_tex"), ("Road_Crack_Response", 2, "depth_tex"),
                               ("Height_Normal", 0, "normal_tex"), ("Material_Local_Masks", 0, "emission_tex")):
        connect(node, port, "PBR_Output", ports[target])
    graph = {"type": "graph", "name": "YACS local road crack / " + motif["label"], "parameters": {},
             "seed_int": motif["seed"], "nodes": [shape, color, response, normal, masks, material], "connections": connections}
    graph_path = destination / "Material.ptex"
    forge._write_json(graph_path, graph)
    old_graph.unlink()
    forge._write_json(destination / "draw-instructions.json", instructions)
    provenance = forge._json(destination / "provenance.json")
    # This is a footprint, never a repeating tile or a physical displacement.
    provenance.pop("tile_metres", None)
    provenance.update({
        "generator": GENERATOR, "generator_version": VERSION, "status": "DECAL_GRAPH_READY_RENDER_PENDING",
        "asset_kind": "local_surface_decal", "motif": motif["id"], "source_identity": identity,
        "graph": "Material.ptex", "graph_sha256": forge.sha256_path(graph_path),
        "draw_instructions_sha256": forge.sha256_path(destination / "draw-instructions.json"),
        "authored_outline_sha256": outline_fingerprint(motif),
        "surface_shader_sha256": hashlib.sha256(field.encode()).hexdigest(),
        "physical_extent_metres": motif["extent_metres"], "resolution": recipe["resolution"],
        "empty_border_metres": recipe["empty_border_metres"], "sampler_address": "clamp", "tileable": False,
        "local_mask_channels": MASK_CHANNELS, "normal_convention": "DirectX", "normal_strength": 0.16,
        "height_is_authoring_only": True, "displacement_enabled": False,
        "semantic_owner": forge.SEMANTIC_OWNER, "upstreams": forge.load_upstreams(),
        "expected_maps": list(MAP_SUFFIXES), "node_count": len(graph["nodes"]),
        "segment_count": len(instructions["segments"]), "chip_count": len(instructions["chips"]),
        **PENDING_FLAGS,
    })
    forge._write_json(destination / "provenance.json", provenance)
    (destination / "export").mkdir()
    return {"motif": motif["id"], "directory": motif["id"],
            "graph_sha256": provenance["graph_sha256"],
            "draw_instructions_sha256": provenance["draw_instructions_sha256"],
            "provenance_sha256": forge.sha256_path(destination / "provenance.json")}


def author(mm_install: Path, output: Path, recipe_path: Path = DEFAULT_RECIPE) -> dict:
    recipe = load_recipe(recipe_path)
    if output.exists():
        raise FileExistsError("Author each repeat into a fresh directory")
    for relative in ("nodes/material.mmg", "material_maker.exe"):
        if not (mm_install / relative).is_file():
            raise FileNotFoundError(f"Pinned Material Maker install is missing {relative}")
    identity = source_identity(recipe_path)
    output.mkdir(parents=True)
    entries = [author_variant(mm_install, output / item["id"], item, recipe, identity) for item in recipe["motifs"]]
    manifest = {"schema_version": 1, "generator": GENERATOR, "status": "DECAL_GRAPHS_READY_RENDER_PENDING",
                "source_identity": identity, "variants": entries, **PENDING_FLAGS}
    forge._write_json(output / "run-manifest.json", manifest)
    return manifest


def _source_entries(run: Path, recipe_path: Path = DEFAULT_RECIPE) -> tuple[dict, list[tuple[dict, Path, dict]]]:
    recipe = load_recipe(recipe_path)
    manifest = forge._json(run / "run-manifest.json")
    if (manifest.get("schema_version") != 1 or manifest.get("generator") != GENERATOR
            or manifest.get("source_identity") != source_identity(recipe_path)):
        raise ValueError("Decal run source identity is stale or incompatible")
    entries = manifest.get("variants", [])
    expected = {item["id"]: item for item in recipe["motifs"]}
    if len(entries) != 8 or {e.get("motif") for e in entries} != set(expected):
        raise ValueError("Decal run must contain all eight unique motifs")
    checked = []
    for entry in entries:
        motif_id = entry["motif"]
        if entry.get("directory") != motif_id:
            raise ValueError("Decal directory must be the local motif id")
        directory = run / motif_id
        for key, relative in (("graph_sha256", "Material.ptex"), ("draw_instructions_sha256", "draw-instructions.json"),
                              ("provenance_sha256", "provenance.json")):
            if entry.get(key) != forge.sha256_path(directory / relative):
                raise ValueError(f"Decal source hash mismatch: {motif_id}/{relative}")
        provenance = forge._json(directory / "provenance.json")
        instructions = drawing_instructions(expected[motif_id], recipe["resolution"], recipe["empty_border_metres"])
        if forge._json(directory / "draw-instructions.json") != instructions:
            raise ValueError("Draw instructions do not match the authored recipe")
        required = {"motif": motif_id, "generator": GENERATOR, "generator_version": VERSION,
                    "source_identity": manifest["source_identity"], "graph_sha256": entry["graph_sha256"],
                    "draw_instructions_sha256": entry["draw_instructions_sha256"],
                    "authored_outline_sha256": outline_fingerprint(expected[motif_id]),
                    "physical_extent_metres": expected[motif_id]["extent_metres"], "resolution": recipe["resolution"],
                    "empty_border_metres": recipe["empty_border_metres"], "sampler_address": "clamp", "tileable": False,
                    "semantic_owner": forge.SEMANTIC_OWNER, "local_mask_channels": MASK_CHANNELS,
                    "normal_convention": "DirectX", "height_is_authoring_only": True, "displacement_enabled": False,
                    "upstreams": forge.load_upstreams(), "expected_maps": list(MAP_SUFFIXES), **PENDING_FLAGS}
        if any(provenance.get(key) != value for key, value in required.items()):
            raise ValueError("Decal provenance contract mismatch")
        graph = forge._json(directory / "Material.ptex")
        if len(graph["nodes"]) != MAX_GRAPH_NODES:
            raise ValueError("Decal graph exceeds the six-node budget")
        form = next(node for node in graph["nodes"] if node["name"] == "Road_Crack_Form")
        if form["shader_model"]["global"] != surface_shader(instructions):
            raise ValueError("Decal graph field differs from the authored instructions")
        checked.append((entry, directory, provenance))
    return manifest, checked


def render_commands(run: Path, godot: Path, source: Path, recipe_path: Path = DEFAULT_RECIPE) -> dict:
    """Return argv arrays; caller must enforce the existing tool/host/exit gates."""
    manifest, entries = _source_entries(run, recipe_path)
    for path in (godot, source / "project.godot", source / ".godot/global_script_class_cache.cfg"):
        if not path.is_file():
            raise FileNotFoundError(f"Pinned, primed runtime is missing {path}")
    if not (source / ".godot/imported").is_dir():
        raise FileNotFoundError("Material Maker import cache is not primed")
    commands = []
    for entry, directory, provenance in entries:
        if any((directory / "export").iterdir()):
            raise FileExistsError("Refusing render commands for an existing export")
        commands.append({
            "motif": entry["motif"],
            "argv": [str(godot.resolve()), "--path", str(source.resolve()), "--script",
                     str(ROOT / "scripts/assets/render_material_forge.gd"), "--",
                     str((directory / "Material.ptex").resolve()),
                     str((directory / "export" / forge.EXPORT_PREFIX).resolve()), str(provenance["resolution"])],
            "log_path": str((directory / "source-runner.log").resolve()), "required_process_exit": 0,
        })
    return {"source_identity": manifest["source_identity"], "required_upstream_pins": forge.load_upstreams(),
            "requires_existing_host_pin_and_exit_verification": True, "commands": commands, **PENDING_FLAGS}


def mask_statistics(detail: np.ndarray, normal: np.ndarray, orm: np.ndarray, extent: float, border: float) -> dict:
    """Check sparse clamped masks. Tiled-material variation gates do not apply."""
    resolution = detail.shape[0]
    ring = max(1, math.floor(border / extent * resolution) - 2)
    outside = np.zeros(detail.shape[:2], dtype=bool)
    outside[:ring] = outside[-ring:] = True
    outside[:, :ring] = outside[:, -ring:] = True
    if float(np.max(detail[outside])) != 0.0:
        raise ValueError("Clamped decal masks leak into the empty border")
    if (float(np.max(np.abs(normal[outside, :2] - 0.5))) > 1 / 255 + 1e-7
            or float(np.min(normal[outside, 2])) < 254 / 255):
        raise ValueError("Decal border normal is not neutral")
    core_fraction = float(np.mean(detail[..., 0] > 0.1))
    footprint = float(np.mean(np.max(detail, axis=2) > 1 / 255))
    if not 0.0004 <= core_fraction <= 0.025 or not 0.0005 <= footprint <= 0.055:
        raise ValueError("Decal must contain sparse readable cracks, with clean asphalt around them")
    if float(detail[..., 0].max()) < 0.25 or float(detail[..., 2].max()) > 0.18:
        raise ValueError("Crack core missing or local weathering dominates")
    if float(orm[..., 2].max()) > 1 / 255 or float(orm[..., 1].min()) < 0.84:
        raise ValueError("Road cracks must stay dry and non-metallic")
    vectors = normal * 2 - 1
    error = float(np.max(np.abs(np.linalg.norm(vectors, axis=2) - 1)))
    # Sparse errors must not disappear behind a whole-image p99 statistic.
    if error > 0.03 or float(vectors[..., 2].min()) < -0.01:
        raise ValueError("Invalid decal DirectX normal vectors")
    normal_peak = float(np.max(np.linalg.norm(vectors[..., :2], axis=2)))
    if not 0.015 <= normal_peak <= 0.65:
        raise ValueError("Decal relief is missing or excessively steep")
    return {"core_coverage_fraction": core_fraction, "total_footprint_fraction": footprint,
            "border_pixels_checked": ring, "border_mask_max": 0.0, "normal_length_error_max": error,
            "normal_xy_peak": normal_peak,
            "weathering_max": float(detail[..., 2].max()), "roughness_min": float(orm[..., 1].min())}


def check_variant(directory: Path, provenance: dict) -> dict:
    resolution = provenance["resolution"]
    export = directory / "export"
    native_path = export / (forge.EXPORT_PREFIX + "_native-check.json")
    native = forge._json(native_path)
    if native.get("valid") is not True or set(native.get("images", {})) != set(MAP_SUFFIXES):
        raise ValueError("Complete Godot native decode is required for all five maps")
    if native.get("engine", {}).get("hash") != provenance["upstreams"]["godot"]["commit"]:
        raise ValueError("Native decoder does not match the pinned Godot commit")
    maps, arrays = {}, {}
    for suffix in MAP_SUFFIXES:
        path = export / (forge.EXPORT_PREFIX + "_" + suffix)
        digest = forge.sha256_path(path)
        check = native["images"][suffix]
        if (check.get("sha256") != digest or check.get("width") != resolution
                or check.get("height") != resolution):
            raise ValueError(f"Native decode dimensions/hash mismatch: {suffix}")
        channel = suffix.split(".")[0]
        maps[channel] = {"path": "export/" + path.name, "sha256": digest, "size": [resolution, resolution]}
        if suffix.endswith(".png"):
            with Image.open(path) as image:
                if image.size != (resolution, resolution) or image.mode not in ("RGB", "RGBA"):
                    raise ValueError(f"Invalid RGB decal map: {suffix}")
                arrays[channel] = np.asarray(image.convert("RGB"), dtype=np.float32) / 255
        else:
            with path.open("rb") as stream:
                if stream.read(4) != b"\x76\x2f\x31\x01":
                    raise ValueError("Height is not an EXR; native decode remains mandatory")
    stats = mask_statistics(arrays["DetailMasks"], arrays["Normal_DX"], arrays["ORM"],
                            provenance["physical_extent_metres"], provenance["empty_border_metres"])
    # Constant black/white output under an otherwise valid opacity mask is a
    # broken albedo export. Warm, dark grey cracks stay inside these broad bounds.
    visible = arrays["DetailMasks"][..., 0] > 0.1
    luma = arrays["BaseColor"].mean(axis=2)[visible]
    if float(luma.min()) < 0.04 or float(luma.max()) > 0.45 or float(luma.std()) < 0.003:
        raise ValueError("Missing or invalid local crack albedo")
    return {"status": "DECAL_MAP_CHECKS_PASS_UE_REVIEW_PENDING", "motif": provenance["motif"],
            "graph_sha256": provenance["graph_sha256"], "maps": maps, "mask_statistics": stats,
            "decoded_core_outline_sha256": hashlib.sha256(np.packbits(visible).tobytes()).hexdigest(),
            "native_decode_verified": True, "native_check_sha256": forge.sha256_path(native_path),
            "normal_convention": "DirectX", "sampler_address": "clamp", **PENDING_FLAGS}


def validate(run: Path, recipe_path: Path = DEFAULT_RECIPE) -> dict:
    manifest, entries = _source_entries(run, recipe_path)
    validations, outlines = [], set()
    for entry, directory, provenance in entries:
        result = check_variant(directory, provenance)
        if result["decoded_core_outline_sha256"] in outlines:
            raise ValueError("Distinct source motifs rendered the same crack outline")
        outlines.add(result["decoded_core_outline_sha256"])
        forge._write_json(directory / "validation.json", result)
        validations.append({"motif": entry["motif"], "validation_sha256": forge.sha256_path(directory / "validation.json")})
    manifest.update(status="DECAL_MAP_CHECKS_PASS_UE_REVIEW_PENDING", validations=validations)
    forge._write_json(run / "run-manifest.json", manifest)
    return manifest


def _validated_signature(run: Path, recipe_path: Path) -> dict:
    manifest, entries = _source_entries(run, recipe_path)
    if manifest.get("status") != "DECAL_MAP_CHECKS_PASS_UE_REVIEW_PENDING":
        raise ValueError("Both native runs must be validated before comparison")
    validations = manifest.get("validations", [])
    if len(validations) != 8 or {v.get("motif") for v in validations} != {e[0]["motif"] for e in entries}:
        raise ValueError("Comparison requires eight complete validations")
    by_id = {v["motif"]: v for v in validations}
    signature = {}
    for entry, directory, provenance in entries:
        validation_path = directory / "validation.json"
        if by_id[entry["motif"]].get("validation_sha256") != forge.sha256_path(validation_path):
            raise ValueError("Stale decal validation hash")
        result = forge._json(validation_path)
        if (result.get("status") != "DECAL_MAP_CHECKS_PASS_UE_REVIEW_PENDING"
                or result.get("native_decode_verified") is not True
                or result.get("graph_sha256") != entry["graph_sha256"]):
            raise ValueError("Invalid decal native validation")
        if set(result.get("maps", {})) != {s.split(".")[0] for s in MAP_SUFFIXES}:
            raise ValueError("Comparison cannot omit a decal channel")
        for channel, data in result["maps"].items():
            suffix = next(s for s in MAP_SUFFIXES if s.startswith(channel + "."))
            path = directory / "export" / (forge.EXPORT_PREFIX + "_" + suffix)
            if data.get("sha256") != forge.sha256_path(path):
                raise ValueError("Decal output changed after validation")
        native = directory / "export" / (forge.EXPORT_PREFIX + "_native-check.json")
        if result.get("native_check_sha256") != forge.sha256_path(native):
            raise ValueError("Decal native decode receipt changed after validation")
        signature[entry["motif"]] = {
            "graph": entry["graph_sha256"], "instructions": entry["draw_instructions_sha256"],
            "source_node": provenance["adapted_source_sha256"], "tool_exe": provenance["tool_exe_sha256"],
            "maps": {channel: data["sha256"] for channel, data in result["maps"].items()},
        }
    return signature


def compare(left: Path, right: Path, recipe_path: Path = DEFAULT_RECIPE) -> dict:
    if left.resolve() == right.resolve():
        raise ValueError("Two distinct native run directories are required")
    a, b = _validated_signature(left, recipe_path), _validated_signature(right, recipe_path)
    mismatches = [motif for motif in sorted(a) if a[motif] != b[motif]]
    return {"status": "DECAL_TWO_RUN_MAP_BYTES_MATCH_HOST_RECEIPT_PENDING" if not mismatches else "DECAL_TWO_RUN_MISMATCH",
            "deterministic": not mismatches, "motif_count": 8, "maps_per_motif": 5,
            "source_identity": source_identity(recipe_path), "mismatches": mismatches,
            "native_decode_verified": True, "requires_existing_host_pin_and_exit_verification": True,
            "left_manifest_sha256": forge.sha256_path(left / "run-manifest.json"),
            "right_manifest_sha256": forge.sha256_path(right / "run-manifest.json"), **PENDING_FLAGS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE)
    sub = parser.add_subparsers(dest="operation", required=True)
    build = sub.add_parser("author")
    build.add_argument("--material-maker", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    commands = sub.add_parser("render-commands")
    commands.add_argument("--run", type=Path, required=True)
    commands.add_argument("--godot", type=Path, required=True)
    commands.add_argument("--source", type=Path, required=True)
    check = sub.add_parser("validate")
    check.add_argument("--run", type=Path, required=True)
    repeated = sub.add_parser("compare")
    repeated.add_argument("--left", type=Path, required=True)
    repeated.add_argument("--right", type=Path, required=True)
    args = parser.parse_args()
    if args.operation == "author":
        result = author(args.material_maker, args.output, args.recipe)
    elif args.operation == "render-commands":
        result = render_commands(args.run, args.godot, args.source, args.recipe)
    elif args.operation == "validate":
        result = validate(args.run, args.recipe)
    else:
        result = compare(args.left, args.right, args.recipe)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.operation == "compare" and not result["deterministic"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
