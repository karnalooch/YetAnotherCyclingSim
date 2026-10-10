"""YACS Material Forge: deterministic Material Maker graph authoring and QA.

Ownership boundary:
- PCG/PCGEx owns world semantics, classification, placement and authoritative masks.
- Material Forge owns surface appearance and material-local masks.
- BOB owns road/terrain geometry and earthworks.

This module never derives authoritative world classification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "worldgen/materials/material_forge/families.json"
DEFAULT_UPSTREAMS = ROOT / "worldgen/materials/material_forge/upstreams.json"

PNG_CHANNELS = ("BaseColor", "Normal_DX", "ORM", "DetailMasks")
ALL_CHANNELS = PNG_CHANNELS + ("Height",)
EXPORT_PREFIX = "YACS_Material"
EXPECTED_NORMAL_CONVENTION = "DirectX"
SEMANTIC_OWNER = "PCG/PCGEx"
GENERATOR_ID = "yacs-material-forge"
GENERATOR_VERSION = 5
DRY_ASPHALT_VARIANT = "dry_varied"

ASPHALT_FUNCTION = r"""
float yacs_rect_patch(vec2 uv, float cells, float salt) {
    vec2 p = uv*cells;
    vec2 cell = floor(p);
    vec2 local = fract(p);
    vec2 wrapped = mod(cell,cells);
    float cell_gate = smoothstep(0.78,0.94,yacs_hash(wrapped,salt));
    vec2 center = vec2(
        0.5+0.20*(yacs_hash(wrapped,salt+3.0)-0.5),
        0.5+0.20*(yacs_hash(wrapped,salt+5.0)-0.5)
    );
    vec2 half_size = vec2(
        mix(0.18,0.36,yacs_hash(wrapped,salt+7.0)),
        mix(0.10,0.25,yacs_hash(wrapped,salt+11.0))
    );
    vec2 delta = abs(local-center)-half_size;
    float signed_box = max(delta.x,delta.y);
    return cell_gate*(1.0-smoothstep(-0.015,0.045,signed_box));
}
float yacs_contour_crack(vec2 uv, float cells, float salt, float level, float width) {
    float field = yacs_noise(uv,cells,salt);
    return 1.0-smoothstep(width,width*2.6,abs(field-level));
}
vec4 yacs_limestone(vec2 uv, float seed, float fractures, float pores) {
    vec2 warp = vec2(yacs_noise(uv,13.0,seed),yacs_noise(uv,13.0,seed+3.0))-0.5;
    vec2 q = uv+0.012*warp;
    float fatigue_gate = smoothstep(
        0.60-0.08*clamp(fractures,0.0,1.5),
        0.76-0.06*clamp(fractures,0.0,1.5),
        yacs_noise(q,11.0,seed+17.0)
    );
    float primary_crack = yacs_contour_crack(q,23.0,seed+19.0,0.50,0.011);
    float secondary_crack = yacs_contour_crack(q,41.0,seed+23.0,0.46,0.008);
    float crack = clamp(
        primary_crack*fatigue_gate+
        0.42*secondary_crack*smoothstep(0.58,0.74,yacs_noise(q,19.0,seed+29.0)),
        0.0,1.0
    );
    float repair_a = yacs_rect_patch(q,9.0,seed+31.0);
    float repair_b = yacs_rect_patch(q+vec2(0.173,0.319),13.0,seed+37.0);
    float patch_mask = clamp(
        (repair_a+0.55*repair_b)*clamp(0.22+0.72*pores,0.0,1.0),
        0.0,1.0
    );
    float aggregate = 0.58*yacs_noise(q,257.0,seed+43.0)
                    + 0.42*yacs_noise(q,521.0,seed+47.0);
    float binder = yacs_noise(q,47.0,seed+53.0);
    float micro = yacs_noise(q,733.0,seed+59.0);
    float height = 0.50+0.017*(aggregate-0.5)+0.006*(micro-0.5);
    height += 0.008*(binder-0.5)+0.009*patch_mask;
    height -= clamp(fractures,0.0,1.6)*0.046*crack;
    float variation = clamp(0.46*binder+0.34*aggregate+0.20*micro,0.0,1.0);
    return vec4(clamp(height,0.0,1.0),crack,patch_mask,variation);
}
"""

# The historical asphalt field above stays unchanged. This separate source
# recipe adds variation within the same 4 m tile and five exported maps: no
# extra Unreal samples, world masks, wetness or geometry displacement.
DRY_ASPHALT_FUNCTION = r"""
vec4 yacs_limestone(vec2 uv, float seed, float fractures, float pores) {
    vec2 warp = vec2(yacs_noise(uv,9.0,seed),yacs_noise(uv,13.0,seed+3.0))-0.5;
    vec2 detail_warp = vec2(yacs_noise(uv,37.0,seed+5.0),yacs_noise(uv,37.0,seed+7.0))-0.5;
    vec2 q = uv+0.028*warp+0.003*detail_warp;

    float coarse = 0.62*yacs_noise(q,3.0,seed+11.0)
                 + 0.38*yacs_noise(q,7.0,seed+13.0);
    float middle = 0.60*yacs_noise(q,29.0,seed+17.0)
                 + 0.40*yacs_noise(q,61.0,seed+19.0);
    float aggregate = 0.60*yacs_noise(q,257.0,seed+23.0)
                    + 0.40*yacs_noise(q,521.0,seed+29.0);
    float micro = yacs_noise(q,733.0,seed+31.0);
    float wear = smoothstep(0.30,0.70,0.66*coarse+0.34*middle);

    float repair_field = 0.56*yacs_noise(q,5.0,seed+37.0)
                       + 0.31*yacs_noise(q,11.0,seed+41.0)
                       + 0.13*yacs_noise(q,47.0,seed+43.0);
    float patch_mask = clamp(
        smoothstep(0.57,0.64,repair_field)*clamp(pores,0.0,1.2),0.0,1.0
    );
    float primary_crack = 1.0-smoothstep(
        0.009,0.026,abs(yacs_noise(q,13.0,seed+47.0)-0.49)
    );
    primary_crack *= smoothstep(0.58,0.74,yacs_noise(q,7.0,seed+53.0));
    float secondary_crack = 1.0-smoothstep(
        0.007,0.021,abs(yacs_noise(q,23.0,seed+59.0)-0.51)
    );
    secondary_crack *= smoothstep(0.64,0.79,yacs_noise(q,17.0,seed+61.0));
    float crack = clamp(primary_crack+0.30*secondary_crack,0.0,1.0);
    crack *= 1.0-0.70*patch_mask;

    float height = 0.50+0.018*(aggregate-0.5)+0.006*(micro-0.5);
    height += 0.004*(middle-0.5)+0.003*patch_mask;
    height -= clamp(fractures,0.0,1.6)*0.022*crack;
    float variation = clamp(
        0.5+1.65*(0.58*(wear-0.5)+0.22*(middle-0.5)
        +0.14*(aggregate-0.5)+0.06*(micro-0.5)),0.0,1.0
    );
    return vec4(clamp(height,0.0,1.0),crack,patch_mask,variation);
}
"""

LIMESTONE_FUNCTION = r"""
vec4 yacs_limestone(vec2 uv, float seed, float fractures, float pores) {
    vec2 warp = vec2(yacs_noise(uv,11.0,seed),yacs_noise(uv,11.0,seed+3.0))-0.5;
    vec2 detail_warp = vec2(yacs_noise(uv,31.0,seed+5.0),yacs_noise(uv,31.0,seed+9.0))-0.5;
    vec2 q = uv+0.020*warp+0.004*detail_warp;
    vec3 major = yacs_cells(q,13.0,seed+11.0);
    float macro = yacs_noise(q,9.0,seed+31.0);
    float middle = yacs_noise(q,43.0,seed+41.0);
    float fine = yacs_noise(q,149.0,seed+47.0);
    float grain = yacs_noise(q,431.0,seed+51.0);

    float fracture_width = mix(0.010,0.036,yacs_noise(q,29.0,seed+13.0));
    float fracture = 1.0-smoothstep(0.0,fracture_width,major.y);
    fracture *= smoothstep(0.46,0.64,yacs_noise(q,17.0,seed+17.0));

    vec3 secondary = yacs_cells(q,37.0,seed+83.0);
    float fissure = (1.0-smoothstep(0.0,0.040,secondary.y));
    fissure *= smoothstep(0.54,0.72,yacs_noise(q,23.0,seed+85.0));

    vec3 cavities = yacs_cells(q,71.0,seed+61.0);
    float pit = (1.0-smoothstep(0.018,0.24,cavities.x));
    pit *= smoothstep(0.62,0.82,cavities.z);

    float karst_channel = 1.0-smoothstep(
        0.020,0.070,abs(yacs_noise(q,27.0,seed+67.0)-0.48)
    );
    karst_channel *= smoothstep(0.58,0.75,yacs_noise(q,13.0,seed+71.0));
    float pore_mask = clamp(max(pit,0.55*karst_channel),0.0,1.0);

    float height = 0.55+0.072*(macro-0.5)+0.047*(middle-0.5);
    height += 0.024*(fine-0.5)+0.009*(grain-0.5);
    height -= clamp(fractures,0.0,1.7)*(0.070*fracture+0.024*fissure);
    height -= clamp(pores,0.0,1.6)*(0.042*pit+0.022*karst_channel);

    float fracture_mask = clamp(max(fracture,0.48*fissure),0.0,1.0);
    float variation = clamp(0.40*macro+0.34*middle+0.26*fine,0.0,1.0);
    return vec4(clamp(height,0.0,1.0),fracture_mask,pore_mask,variation);
}
"""

SOIL_FUNCTION = r"""
vec4 yacs_limestone(vec2 uv, float seed, float fractures, float pores) {
    vec2 warp = vec2(yacs_noise(uv,13.0,seed),yacs_noise(uv,13.0,seed+3.0))-0.5;
    vec2 q = uv+0.010*warp;

    vec3 coarse_cells = yacs_cells(q,43.0,seed+11.0);
    float coarse_pebble = 1.0-smoothstep(0.030,0.30,coarse_cells.x);
    coarse_pebble *= smoothstep(0.55,0.80,coarse_cells.z);

    vec3 small_cells = yacs_cells(q,97.0,seed+17.0);
    float small_pebble = 1.0-smoothstep(0.020,0.22,small_cells.x);
    small_pebble *= smoothstep(0.68,0.86,small_cells.z);

    float pebble = clamp(
        clamp(fractures,0.0,1.5)*(coarse_pebble+0.48*small_pebble),
        0.0,1.0
    );

    vec3 crust_cells = yacs_cells(q,29.0,seed+23.0);
    float crust_crack = 1.0-smoothstep(0.0,0.032,crust_cells.y);
    crust_crack *= smoothstep(0.48,0.68,yacs_noise(q,17.0,seed+27.0));
    float crust_plate = smoothstep(0.58,0.76,yacs_noise(q,23.0,seed+29.0));
    float crust = clamp(
        clamp(pores,0.0,1.5)*(crust_crack+0.28*crust_plate),
        0.0,1.0
    );

    float fines = yacs_noise(q,173.0,seed+31.0);
    float grain = yacs_noise(q,487.0,seed+37.0);
    float mineral = yacs_noise(q,17.0,seed+41.0);
    float height = 0.47+0.055*coarse_pebble*clamp(fractures,0.0,1.5);
    height += 0.024*small_pebble*clamp(fractures,0.0,1.5);
    height += 0.014*(fines-0.5)+0.006*(grain-0.5);
    height -= 0.040*crust_crack*clamp(pores,0.0,1.5);
    height -= 0.006*crust_plate*clamp(pores,0.0,1.5);
    float variation = clamp(0.42*mineral+0.34*fines+0.24*grain,0.0,1.0);
    return vec4(clamp(height,0.0,1.0),pebble,crust,variation);
}
"""

def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def source_fingerprint(
    catalog_path: Path = DEFAULT_CATALOG,
    upstreams_path: Path = DEFAULT_UPSTREAMS,
) -> str:
    payload = {
        "generator": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "forge_sha256": sha256_path(Path(__file__)),
        "base_builder_sha256": sha256_path(
            ROOT / "scripts/assets/build_material_maker_limestone.py"
        ),
        "catalog_sha256": sha256_path(catalog_path),
        "upstreams_sha256": sha256_path(upstreams_path),
    }
    return canonical_hash(payload)


def _load_base_builder():
    path = ROOT / "scripts/assets/build_material_maker_limestone.py"
    spec = importlib.util.spec_from_file_location("yacs_mm_base_builder", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load existing Material Maker graph builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_catalog(path: Path = DEFAULT_CATALOG) -> dict[str, Any]:
    data = _json(path)
    families = data.get("families", [])
    if data.get("schema_version") != 1 or len(families) != 3:
        raise ValueError("Material Forge catalog must contain exactly three phase-A families")
    ids = {item["id"] for item in families}
    if ids != {"aged_mountain_asphalt", "regional_limestone", "mediterranean_soil"}:
        raise ValueError("Unexpected Material Forge family set")
    for family in families:
        variants = family.get("variants", [])
        if len(variants) < 3:
            raise ValueError(f"{family['id']} needs at least three variants")
        if len({v["id"] for v in variants}) != len(variants):
            raise ValueError(f"Duplicate variant id in {family['id']}")
        if family.get("semantic_owner") != SEMANTIC_OWNER:
            raise ValueError(f"{family['id']} must preserve PCG/PCGEx semantic ownership")
        for variant in variants:
            profile = _refinement_profile(variant)
            for key in (
                "variation_scale",
                "crack_color_scale",
                "pore_color_scale",
                "roughness_variation_scale",
                "roughness_crack_scale",
                "roughness_pore_scale",
                "ao_crack_scale",
                "ao_pore_scale",
            ):
                _profile_scale(profile, key)
            _profile_color_gain(profile)
            landscape = _landscape_profile(variant)
            if landscape:
                _profile_number(
                    landscape, "macro_tile_metres", 16.0, 8.0, 30.0
                )
                _profile_number(
                    landscape, "macro_strength", 0.0, 0.0, 0.30
                )
    return data


def load_upstreams(path: Path = DEFAULT_UPSTREAMS) -> dict[str, Any]:
    data = _json(path)
    if data.get("material_maker", {}).get("license") != "MIT":
        raise ValueError("Material Maker pin must remain MIT")
    if data.get("godot", {}).get("license") != "MIT":
        raise ValueError("Godot pin must remain MIT")
    return data


def _is_dry_asphalt(family_id: str, variant: dict[str, Any] | None) -> bool:
    return family_id == "aged_mountain_asphalt" and bool(
        variant and variant.get("id") == DRY_ASPHALT_VARIANT
    )


def _replace_surface_function(
    base_module, family_id: str, variant: dict[str, Any] | None = None
) -> str:
    helpers = base_module.FIELD.split("vec4 yacs_limestone(", 1)[0]
    if family_id == "aged_mountain_asphalt":
        return helpers + (
            DRY_ASPHALT_FUNCTION
            if _is_dry_asphalt(family_id, variant)
            else ASPHALT_FUNCTION
        )
    if family_id == "mediterranean_soil":
        return helpers + SOIL_FUNCTION
    if family_id == "regional_limestone":
        return helpers + LIMESTONE_FUNCTION
    raise ValueError(f"Unknown family: {family_id}")


def _detail_expression(family_id: str) -> str:
    if family_id == "aged_mountain_asphalt":
        return (
            "vec3(clamp($crack($uv),0.0,1.0),"
            "clamp($pore($uv),0.0,1.0),"
            "clamp(abs(2.0*$variation($uv)-1.0),0.0,1.0))"
        )
    if family_id in {"regional_limestone", "mediterranean_soil"}:
        return (
            "vec3(clamp($crack($uv),0.0,1.0),"
            "clamp($pore($uv),0.0,1.0),"
            "clamp($variation($uv),0.0,1.0))"
        )
    raise ValueError(family_id)


def _refinement_profile(variant: dict[str, Any] | None) -> dict[str, Any]:
    if not variant:
        return {}
    raw = variant.get("refinement", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Material Forge refinement profile must be an object")
    return raw


def _landscape_profile(variant: dict[str, Any] | None) -> dict[str, Any]:
    if not variant:
        return {}
    raw = variant.get("landscape", {})
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Material Forge landscape profile must be an object")
    return raw


def _profile_number(
    profile: dict[str, Any],
    key: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    value = float(profile.get(key, default))
    if not minimum <= value <= maximum:
        raise ValueError(
            f"Material Forge profile value out of range: {key}={value}"
        )
    return value


def _profile_scale(
    profile: dict[str, Any],
    key: str,
    default: float = 1.0,
) -> float:
    value = float(profile.get(key, default))
    if not 0.0 <= value <= 3.0:
        raise ValueError(f"Material Forge refinement scale out of range: {key}")
    return value


def _profile_color_gain(profile: dict[str, Any]) -> tuple[float, float, float]:
    raw = profile.get("color_gain", [1.0, 1.0, 1.0])
    if not isinstance(raw, list) or len(raw) != 3:
        raise ValueError("Material Forge color_gain must contain three values")
    gains = tuple(float(value) for value in raw)
    if any(value < 0.5 or value > 1.5 for value in gains):
        raise ValueError("Material Forge color_gain values must be in 0.5..1.5")
    return gains


def _signed_term(coefficient: float, expression: str) -> str:
    return f"{coefficient:+.6f}*{expression}"


def _color_output(
    family_id: str,
    variant: dict[str, Any] | None = None,
) -> str:
    profile = _refinement_profile(variant)
    gains = _profile_color_gain(profile)
    if family_id == "aged_mountain_asphalt":
        channels = (
            "$(name_uv)_tone*0.97",
            "$(name_uv)_tone*0.985",
            "$(name_uv)_tone",
        )
    elif family_id == "regional_limestone":
        channels = (
            "$(name_uv)_tone*1.020+0.025*$variation($uv)",
            "$(name_uv)_tone*0.990+0.008*$variation($uv)",
            "$(name_uv)_tone*0.920",
        )
    elif family_id == "mediterranean_soil":
        channels = (
            "$(name_uv)_tone*1.08",
            "$(name_uv)_tone*0.98",
            "$(name_uv)_tone*0.86",
        )
    else:
        raise ValueError(family_id)
    return "vec3(" + ",".join(
        f"({channel})*{gain:.6f}"
        for channel, gain in zip(channels, gains)
    ) + ")"


def _color_code(
    family_id: str,
    variant: dict[str, Any] | None = None,
) -> str:
    profile = _refinement_profile(variant)
    variation_scale = _profile_scale(profile, "variation_scale")
    crack_scale = _profile_scale(profile, "crack_color_scale")
    pore_scale = _profile_scale(profile, "pore_color_scale")
    if family_id == "aged_mountain_asphalt":
        if _is_dry_asphalt(family_id, variant):
            variation, crack, pore = 0.200, -0.045, -0.050
        else:
            variation, crack, pore = 0.085, -0.060, -0.030
    elif family_id == "regional_limestone":
        variation, crack, pore = 0.105, -0.052, -0.030
    elif family_id == "mediterranean_soil":
        variation, crack, pore = 0.130, 0.055, -0.045
    else:
        raise ValueError(family_id)
    return (
        "float $(name_uv)_tone = clamp($brightness"
        + _signed_term(variation * variation_scale, "($variation($uv)-0.5)")
        + _signed_term(crack * crack_scale, "$crack($uv)")
        + _signed_term(pore * pore_scale, "$pore($uv)")
        + ",0.0,1.0);"
    )


def _response_expressions(
    family_id: str,
    roughness: float,
    variant: dict[str, Any] | None = None,
) -> tuple[str, str]:
    profile = _refinement_profile(variant)
    rv = _profile_scale(profile, "roughness_variation_scale")
    rc = _profile_scale(profile, "roughness_crack_scale")
    rp = _profile_scale(profile, "roughness_pore_scale")
    ac = _profile_scale(profile, "ao_crack_scale")
    ap = _profile_scale(profile, "ao_pore_scale")
    r = f"{roughness:.6f}"
    if _is_dry_asphalt(family_id, variant):
        # Repair islands retain the same high dry roughness floor while colour
        # and roughness vary together across the surface.
        return (
            f"clamp({r}+0.055000*($variation($uv)-0.5)"
            "+0.018000*$crack($uv)-0.012000*$pore($uv),0.90,0.99)",
            "clamp(1.0-0.090000*$crack($uv)-0.025000*$pore($uv),0.0,1.0)",
        )
    if family_id == "aged_mountain_asphalt":
        variation, crack, pore, ao_crack, ao_pore = 0.070, 0.030, -0.060, 0.130, 0.040
    elif family_id == "regional_limestone":
        variation, crack, pore, ao_crack, ao_pore = 0.080, 0.000, 0.040, 0.160, 0.120
    elif family_id == "mediterranean_soil":
        variation, crack, pore, ao_crack, ao_pore = 0.050, 0.000, 0.030, 0.080, 0.070
    else:
        raise ValueError(family_id)
    rough = (
        f"clamp({r}"
        + _signed_term(variation * rv, "$variation($uv)")
        + _signed_term(crack * rc, "$crack($uv)")
        + _signed_term(pore * rp, "$pore($uv)")
        + ",0.0,1.0)"
    )
    ao = (
        "clamp(1.0"
        + _signed_term(-ao_crack * ac, "$crack($uv)")
        + _signed_term(-ao_pore * ap, "$pore($uv)")
        + ",0.0,1.0)"
    )
    return rough, ao

def author_variant(
    material_maker_source: Path,
    destination: Path,
    family: dict[str, Any],
    variant: dict[str, Any],
    upstreams: dict[str, Any],
) -> dict[str, Any]:
    """Create one editable .ptex variant without rendering it."""

    if destination.exists():
        raise FileExistsError(f"Refusing existing variant directory: {destination}")
    base = _load_base_builder()
    base.build(material_maker_source, destination)

    old_graph = destination / "SaCalobra_PaleLimestone.ptex"
    graph_path = destination / "Material.ptex"
    old_graph.rename(graph_path)
    graph = _json(graph_path)

    family_id = family["id"]
    graph["name"] = f"YACS {family['label']} / {variant['label']}"
    graph["seed_int"] = int(variant["seed"])
    nodes = {node["name"]: node for node in graph["nodes"]}
    shape = nodes["Limestone_Form"]
    color = nodes["Limestone_Color"]
    response = nodes["Limestone_Response"]
    normal = nodes["Height_Normal"]
    material = nodes["PBR_Output"]

    shape["parameters"].update(
        seed=int(variant["seed"]),
        fractures=float(variant["surface_a"]),
        pores=float(variant["surface_b"]),
    )
    shape["shader_model"]["name"] = f"{family['label']} surface field"
    shape["shader_model"]["global"] = _replace_surface_function(
        base, family_id, variant
    )

    color["parameters"]["brightness"] = float(variant["brightness"])
    color["shader_model"]["name"] = f"{family['label']} albedo"
    color["shader_model"]["code"] = _color_code(family_id, variant)
    color["shader_model"]["outputs"][0]["rgb"] = _color_output(family_id, variant)

    roughness_expr, ao_expr = _response_expressions(
        family_id,
        float(variant["roughness"]),
        variant,
    )
    response["shader_model"]["name"] = f"{family['label']} surface response"
    response["shader_model"]["outputs"][0]["f"] = roughness_expr
    response["shader_model"]["outputs"][1]["f"] = ao_expr
    normal["parameters"]["strength"] = float(variant["normal_strength"])

    detail = base.shader(
        "Material_Local_Masks",
        f"{family['label']} local masks",
        710,
        520,
        [
            base.source("crack"),
            base.source("pore"),
            base.source("variation"),
            base.source("height"),
        ],
        [base.output("Detail Masks", _detail_expression(family_id), "rgb")],
    )
    graph["nodes"].insert(-1, detail)

    def connect(a: str, ai: int, b: str, bi: int) -> None:
        graph["connections"].append(
            {"from": a, "from_port": ai, "to": b, "to_port": bi}
        )

    for source_port, target_port in ((1, 0), (2, 1), (3, 2), (0, 3)):
        connect("Limestone_Form", source_port, "Material_Local_Masks", target_port)

    ports = {
        p["name"]: i for i, p in enumerate(material["shader_model"]["inputs"])
    }
    connect("Material_Local_Masks", 0, "PBR_Output", ports["emission_tex"])
    material["parameters"]["emission_energy"] = 0

    exports = material["shader_model"]["exports"]["YACS/Textures"]["files"]
    exports.append(
        {
            "type": "texture",
            "file_name": "$(path_prefix)_DetailMasks.png",
            "output": 2,
        }
    )

    _write_json(graph_path, graph)

    provenance_path = destination / "provenance.json"
    provenance = _json(provenance_path)
    provenance.update(
        generator=GENERATOR_ID,
        generator_version=GENERATOR_VERSION,
        status="GRAPH_READY_RENDER_PENDING",
        family=family_id,
        family_label=family["label"],
        variant=variant["id"],
        variant_label=variant["label"],
        graph="Material.ptex",
        graph_sha256=sha256_path(graph_path),
        seed=int(variant["seed"]),
        tile_metres=float(family["tile_metres"]),
        normal_convention=EXPECTED_NORMAL_CONVENTION,
        local_mask_channels=family["local_masks"],
        semantic_owner=SEMANTIC_OWNER,
        world_semantics_generated=False,
        parameters={
            "brightness": float(variant["brightness"]),
            "surface_a": float(variant["surface_a"]),
            "surface_b": float(variant["surface_b"]),
            "roughness": float(variant["roughness"]),
            "normal_strength": float(variant["normal_strength"]),
            "refinement": _refinement_profile(variant),
            "landscape": _landscape_profile(variant),
        },
        upstreams=upstreams,
        expected_maps=[
            "BaseColor.png",
            "Normal_DX.png",
            "ORM.png",
            "Height.exr",
            "DetailMasks.png",
        ],
        recipe="scripts/assets/material_forge.py",
    )
    _write_json(provenance_path, provenance)

    fingerprint_payload = {
        "family": family_id,
        "variant": variant,
        "tile_metres": family["tile_metres"],
        "local_masks": family["local_masks"],
        "upstreams": upstreams,
        "graph_sha256": provenance["graph_sha256"],
    }
    return {
        "family": family_id,
        "variant": variant["id"],
        "directory": str(destination),
        "graph": str(graph_path),
        "graph_sha256": provenance["graph_sha256"],
        "fingerprint": canonical_hash(fingerprint_payload),
        "seed": int(variant["seed"]),
    }


def author_all(
    material_maker_source: Path,
    output: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    upstreams_path: Path = DEFAULT_UPSTREAMS,
) -> dict[str, Any]:
    catalog = load_catalog(catalog_path)
    upstreams = load_upstreams(upstreams_path)
    if output.exists():
        raise FileExistsError(f"Refusing existing run directory: {output}")
    output.mkdir(parents=True)

    variants: list[dict[str, Any]] = []
    for family in catalog["families"]:
        for variant in family["variants"]:
            destination = output / family["id"] / variant["id"]
            entry = author_variant(
                material_maker_source, destination, family, variant, upstreams
            )
            entry["directory"] = str(destination.relative_to(output)).replace("\\", "/")
            entry["graph"] = str((destination / "Material.ptex").relative_to(output)).replace(
                "\\", "/"
            )
            variants.append(entry)

    manifest = {
        "schema_version": 1,
        "generator": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "source_fingerprint": source_fingerprint(catalog_path, upstreams_path),
        "status": "GRAPHS_READY_RENDER_PENDING",
        "semantic_owner": SEMANTIC_OWNER,
        "world_semantics_generated": False,
        "catalog_sha256": sha256_path(catalog_path),
        "upstreams_sha256": sha256_path(upstreams_path),
        "upstreams": upstreams,
        "variants": variants,
    }
    manifest["run_fingerprint"] = canonical_hash(
        {
            "catalog_sha256": manifest["catalog_sha256"],
            "upstreams_sha256": manifest["upstreams_sha256"],
            "variants": [
                {
                    "family": x["family"],
                    "variant": x["variant"],
                    "fingerprint": x["fingerprint"],
                }
                for x in variants
            ],
        }
    )
    _write_json(output / "run-manifest.json", manifest)
    return manifest


def _wrap_stats(array: np.ndarray) -> dict[str, float]:
    dx = float(np.abs(array[:, 1:] - array[:, :-1]).mean())
    dy = float(np.abs(array[1:] - array[:-1]).mean())
    sx = float(np.abs(array[:, 0] - array[:, -1]).mean())
    sy = float(np.abs(array[0] - array[-1]).mean())
    return {
        "wrap_step_x": sx,
        "wrap_step_y": sy,
        "interior_step_x": dx,
        "interior_step_y": dy,
    }


def _assert_wrap(channel: str, stats: dict[str, float]) -> None:
    if stats["wrap_step_x"] > max(0.02, 4 * stats["interior_step_x"]):
        raise ValueError(f"Discontinuous wrap boundary: {channel} x")
    if stats["wrap_step_y"] > max(0.02, 4 * stats["interior_step_y"]):
        raise ValueError(f"Discontinuous wrap boundary: {channel} y")


def _dry_asphalt_statistics(
    color: np.ndarray, normal: np.ndarray, orm: np.ndarray, detail: np.ndarray
) -> dict[str, float]:
    """Measure the rendered dry recipe, not its intended scalar settings.

    Sixteen blocks per 4 m tile measure 25 cm appearance changes after micro
    detail has averaged away. This is source QA, not an Unreal appearance gate.
    """
    roughness = orm[..., 1]
    luma = color @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    height, width = luma.shape
    if height % 16 or width % 16:
        raise ValueError("Dry asphalt statistics need a 16-block source grid")
    coarse = luma.reshape(16, height // 16, 16, width // 16).mean(axis=(1, 3))
    stats = {
        "roughness_min": float(roughness.min()),
        "roughness_max": float(roughness.max()),
        "roughness_mean": float(roughness.mean()),
        "roughness_std": float(roughness.std()),
        "basecolor_luma_std": float(luma.std()),
        "basecolor_25cm_luma_std": float(coarse.std()),
        "patch_coverage_fraction": float(np.mean(detail[..., 1] > 0.25)),
        "normal_xy_rms": float(np.sqrt(np.mean((normal[..., :2] * 2 - 1) ** 2))),
    }
    # One UNORM8 step accommodates source export quantization, not a lower
    # roughness recipe. Actual min/max/mean are retained for the UE comparison.
    if not (
        0.90 - 1 / 255 <= stats["roughness_min"]
        <= stats["roughness_max"] <= 0.99 + 1 / 255
    ):
        raise ValueError("Dry asphalt roughness is outside 0.90..0.99")
    if stats["roughness_std"] < 0.003:
        raise ValueError("Dry asphalt roughness variation is missing")
    if (
        stats["basecolor_luma_std"] < 0.012
        or stats["basecolor_25cm_luma_std"] < 0.008
    ):
        raise ValueError("Dry asphalt coarse colour variation is missing")
    if not 0.02 <= stats["patch_coverage_fraction"] <= 0.40:
        raise ValueError("Dry asphalt irregular repair coverage is outside bounds")
    return stats


def check_variant(directory: Path, expected_resolution: int = 2048) -> dict[str, Any]:
    provenance = _json(directory / "provenance.json")
    if provenance.get("semantic_owner") != SEMANTIC_OWNER:
        raise ValueError("Material Forge cannot own world semantics")
    if provenance.get("world_semantics_generated") is not False:
        raise ValueError("Material Forge must not generate authoritative world semantics")
    if provenance.get("normal_convention") != EXPECTED_NORMAL_CONVENTION:
        raise ValueError("Only DirectX normal output is admitted for UE")

    export = directory / "export"
    arrays: dict[str, np.ndarray] = {}
    maps: dict[str, Any] = {}
    for channel in PNG_CHANNELS:
        path = export / f"{EXPORT_PREFIX}_{channel}.png"
        with Image.open(path) as image:
            if image.size != (expected_resolution, expected_resolution):
                raise ValueError(f"Unexpected resolution: {channel}")
            array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        arrays[channel] = array
        stats = _wrap_stats(array)
        _assert_wrap(channel, stats)
        maps[channel] = {
            "path": str(path.relative_to(directory)).replace("\\", "/"),
            "sha256": sha256_path(path),
            "size": [expected_resolution, expected_resolution],
            **stats,
        }

    color = arrays["BaseColor"]
    normal = arrays["Normal_DX"]
    orm = arrays["ORM"]
    detail = arrays["DetailMasks"]

    if float(color.std()) < 0.002:
        raise ValueError("Missing BaseColor surface variation")
    if float(normal[..., :2].std()) < 0.008:
        raise ValueError("Missing normal detail")
    if float(detail.std()) < 0.004:
        raise ValueError("Material-local detail masks are blank")
    if float(np.max(orm[..., 2])) > 1 / 255:
        raise ValueError("Phase-A material families must be non-metallic")

    vectors = normal * 2.0 - 1.0
    length = np.linalg.norm(vectors, axis=2)
    normal_error = float(np.quantile(np.abs(length - 1.0), 0.99))
    if normal_error > 0.03 or float(vectors[..., 2].min()) < -0.01:
        raise ValueError("Invalid DirectX normal vectors")

    exr = export / f"{EXPORT_PREFIX}_Height.exr"
    if exr.read_bytes()[:4] != b"\x76\x2f\x31\x01":
        raise ValueError("Missing EXR height")
    maps["Height"] = {
        "path": str(exr.relative_to(directory)).replace("\\", "/"),
        "sha256": sha256_path(exr),
    }

    native = export / f"{EXPORT_PREFIX}_native-check.json"
    if not native.is_file():
        raise ValueError("Missing Godot native decode receipt")
    native_check = _json(native)
    if native_check.get("valid") is not True:
        raise ValueError("Godot native image decoding failed")
    for suffix in (
        "BaseColor.png",
        "Normal_DX.png",
        "ORM.png",
        "Height.exr",
        "DetailMasks.png",
    ):
        image = native_check.get("images", {}).get(suffix)
        if image is None:
            raise ValueError(f"Native decode missing: {suffix}")
        if [image["width"], image["height"]] != [
            expected_resolution,
            expected_resolution,
        ]:
            raise ValueError(f"Native resolution mismatch: {suffix}")
        output_path = export / f"{EXPORT_PREFIX}_{suffix}"
        if image.get("sha256") != sha256_path(output_path):
            raise ValueError(f"Native decode hash mismatch: {suffix}")

    result = {
        "status": "MAP_CHECKS_PASS_UE_REVIEW_PENDING",
        "family": provenance["family"],
        "variant": provenance["variant"],
        "normal_convention": EXPECTED_NORMAL_CONVENTION,
        "normal_length_error_p99": normal_error,
        "maps": maps,
        "local_mask_channels": provenance["local_mask_channels"],
        "semantic_owner": SEMANTIC_OWNER,
        "world_semantics_generated": False,
        "geometry_changed": False,
        "visual_accepted": False,
        "performance_accepted": False,
    }
    if _is_dry_asphalt(provenance["family"], {"id": provenance["variant"]}):
        result["dry_asphalt_statistics"] = _dry_asphalt_statistics(
            color, normal, orm, detail
        )
    _write_json(directory / "validation.json", result)
    return result


def validate_run(root: Path) -> dict[str, Any]:
    manifest_path = root / "run-manifest.json"
    manifest = _json(manifest_path)
    validations: list[dict[str, Any]] = []
    for entry in manifest["variants"]:
        directory = root / entry["directory"]
        validation = check_variant(directory)
        validations.append(
            {
                "family": entry["family"],
                "variant": entry["variant"],
                "validation_sha256": sha256_path(directory / "validation.json"),
                "maps": {
                    name: data["sha256"] for name, data in validation["maps"].items()
                },
            }
        )
    manifest["status"] = "MAP_CHECKS_PASS_UE_REVIEW_PENDING"
    manifest["validations"] = validations
    _write_json(manifest_path, manifest)
    return manifest


def pack_world_masks(spec_path: Path, output: Path, manifest_path: Path) -> dict[str, Any]:
    """Pack authoritative world masks without deriving or reclassifying them."""

    spec = _json(spec_path)
    if spec.get("semantic_owner") != SEMANTIC_OWNER:
        raise ValueError("Packed world masks must remain owned by PCG/PCGEx")
    if spec.get("operation") != "pack_only":
        raise ValueError("Material Forge may only pack authoritative world masks")

    channels = spec.get("channels", {})
    arrays: list[np.ndarray] = []
    source_receipts: dict[str, Any] = {}
    size: tuple[int, int] | None = None
    for channel_name in ("R", "G", "B", "A"):
        entry = channels.get(channel_name)
        if not entry:
            if size is None:
                raise ValueError("First packed channel cannot be empty")
            arrays.append(np.zeros((size[1], size[0]), dtype=np.uint8))
            source_receipts[channel_name] = {"name": "UNUSED", "fill": 0}
            continue
        path = Path(entry["path"])
        with Image.open(path) as image:
            grey = np.asarray(image.convert("L"), dtype=np.uint8)
            current_size = image.size
        if size is None:
            size = current_size
        elif current_size != size:
            raise ValueError("World mask dimensions must match before packing")
        arrays.append(grey)
        source_receipts[channel_name] = {
            "name": entry["name"],
            "path": str(path),
            "sha256": sha256_path(path),
            "semantic_owner": SEMANTIC_OWNER,
        }

    rgba = np.stack(arrays, axis=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(output)

    result = {
        "schema_version": 1,
        "operation": "pack_only",
        "semantic_owner": SEMANTIC_OWNER,
        "classification_changed": False,
        "output": str(output),
        "output_sha256": sha256_path(output),
        "size": list(size) if size else None,
        "channels": source_receipts,
    }
    _write_json(manifest_path, result)
    return result


def plan_rebuild(
    root: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    upstreams_path: Path = DEFAULT_UPSTREAMS,
) -> dict[str, Any]:
    """Return whether a clean Material Forge rebuild is required."""

    manifest_path = root / "run-manifest.json"
    current = source_fingerprint(catalog_path, upstreams_path)
    if not manifest_path.exists():
        return {
            "rebuild_required": True,
            "reason": "run_manifest_missing",
            "current_source_fingerprint": current,
            "recorded_source_fingerprint": None,
        }
    recorded = _json(manifest_path).get("source_fingerprint")
    return {
        "rebuild_required": recorded != current,
        "reason": "source_fingerprint_changed" if recorded != current else "unchanged",
        "current_source_fingerprint": current,
        "recorded_source_fingerprint": recorded,
    }


def derive_material_mask(
    spec_path: Path,
    output: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Gate material-local detail by an authoritative PCG/PCGEx world mask.

    This is a presentation/detail transform only. It never thresholds, expands,
    erodes or otherwise reclassifies the authoritative world mask.
    """

    spec = _json(spec_path)
    if spec.get("semantic_owner") != SEMANTIC_OWNER:
        raise ValueError("World mask must remain owned by PCG/PCGEx")
    if spec.get("operation") != "modulate_detail_only":
        raise ValueError("Unsupported derived-mask operation")
    world = Path(spec["world_mask"]["path"])
    detail = Path(spec["detail_mask"]["path"])
    with Image.open(world) as image:
        world_array = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
        size = image.size
    with Image.open(detail) as image:
        if image.size != size:
            raise ValueError("World/detail mask dimensions must match")
        detail_array = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    derived = np.clip(detail_array * world_array[..., None], 0.0, 1.0)
    output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.uint8(derived * 255.0), mode="RGB").save(output)
    result = {
        "schema_version": 1,
        "operation": "modulate_detail_only",
        "semantic_owner": SEMANTIC_OWNER,
        "classification_changed": False,
        "world_mask": {
            "name": spec["world_mask"]["name"],
            "path": str(world),
            "sha256": sha256_path(world),
        },
        "detail_mask": {
            "path": str(detail),
            "sha256": sha256_path(detail),
        },
        "output": str(output),
        "output_sha256": sha256_path(output),
        "size": list(size),
    }
    _write_json(manifest_path, result)
    return result


def compare_run_manifests(left: Path, right: Path) -> dict[str, Any]:
    a = _json(left)
    b = _json(right)

    def signature(manifest: dict[str, Any]) -> dict[tuple[str, str], Any]:
        output = {}
        validation_map = {
            (x["family"], x["variant"]): x for x in manifest.get("validations", [])
        }
        for entry in manifest["variants"]:
            key = (entry["family"], entry["variant"])
            output[key] = {
                "graph_sha256": entry["graph_sha256"],
                "fingerprint": entry["fingerprint"],
                "maps": validation_map.get(key, {}).get("maps"),
            }
        return output

    left_sig = signature(a)
    right_sig = signature(b)
    keys = sorted(set(left_sig) | set(right_sig))
    mismatches = [
        {
            "family": key[0],
            "variant": key[1],
            "left": left_sig.get(key),
            "right": right_sig.get(key),
        }
        for key in keys
        if left_sig.get(key) != right_sig.get(key)
    ]
    return {
        "deterministic": not mismatches,
        "left_run_fingerprint": a.get("run_fingerprint"),
        "right_run_fingerprint": b.get("run_fingerprint"),
        "mismatches": mismatches,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    author = sub.add_parser("author", help="Create all 3x3 editable Material Maker graphs")
    author.add_argument(
        "--material-maker",
        "--material-maker-source",
        dest="material_maker",
        type=Path,
        required=True,
        help="Material Maker 1.7 install directory containing nodes/material.mmg and material_maker.exe",
    )
    author.add_argument("--output", type=Path, required=True)
    author.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    author.add_argument("--upstreams", type=Path, default=DEFAULT_UPSTREAMS)
    author.set_defaults(
        func=lambda args: print(
            json.dumps(
                author_all(
                    args.material_maker,
                    args.output,
                    args.catalog,
                    args.upstreams,
                ),
                indent=2,
            )
        )
    )

    validate = sub.add_parser("validate", help="Validate one rendered variant")
    validate.add_argument("variant", type=Path)
    validate.add_argument("--resolution", type=int, default=2048)
    validate.set_defaults(
        func=lambda args: print(
            json.dumps(check_variant(args.variant, args.resolution), indent=2)
        )
    )

    validate_run_parser = sub.add_parser(
        "validate-run", help="Validate all rendered variants in a run"
    )
    validate_run_parser.add_argument("root", type=Path)
    validate_run_parser.set_defaults(
        func=lambda args: print(json.dumps(validate_run(args.root), indent=2))
    )

    pack = sub.add_parser(
        "pack-world-masks",
        help="Pack already-authoritative PCG/PCGEx masks into RGBA without reclassification",
    )
    pack.add_argument("--spec", type=Path, required=True)
    pack.add_argument("--output", type=Path, required=True)
    pack.add_argument("--manifest", type=Path, required=True)
    pack.set_defaults(
        func=lambda args: print(
            json.dumps(pack_world_masks(args.spec, args.output, args.manifest), indent=2)
        )
    )

    plan = sub.add_parser(
        "plan-rebuild",
        help="Report whether generator/catalog/upstream fingerprints require a rebuild",
    )
    plan.add_argument("root", type=Path)
    plan.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    plan.add_argument("--upstreams", type=Path, default=DEFAULT_UPSTREAMS)
    plan.set_defaults(
        func=lambda args: print(
            json.dumps(plan_rebuild(args.root, args.catalog, args.upstreams), indent=2)
        )
    )

    derive = sub.add_parser(
        "derive-material-mask",
        help="Gate material-local detail with an authoritative world mask",
    )
    derive.add_argument("--spec", type=Path, required=True)
    derive.add_argument("--output", type=Path, required=True)
    derive.add_argument("--manifest", type=Path, required=True)
    derive.set_defaults(
        func=lambda args: print(
            json.dumps(
                derive_material_mask(args.spec, args.output, args.manifest), indent=2
            )
        )
    )

    compare = sub.add_parser(
        "compare", help="Compare graph/output hashes from two complete runs"
    )
    compare.add_argument("--left", type=Path, required=True)
    compare.add_argument("--right", type=Path, required=True)

    def run_compare(args: argparse.Namespace) -> None:
        result = compare_run_manifests(args.left, args.right)
        print(json.dumps(result, indent=2))
        if not result["deterministic"]:
            raise SystemExit(2)

    compare.set_defaults(func=run_compare)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
