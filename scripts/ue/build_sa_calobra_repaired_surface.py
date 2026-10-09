"""Native five-domain surface graph; immutable source masks and frozen geometry.

Invoked by sa_calobra_material_repair.py. Imported textures are initially unsaved.
All Normal inputs are transformed into the space required by installed UE 5.8.2.
"""

import hashlib
import json
import os
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
ROLES = ("DryGrass", "ForestLitter", "ExposedRock", "DryMineral", "Scree")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_sources(state):
    if state.get("repair_sources"):
        return state["repair_sources"]
    memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ]()
    if memory["free_physical"] < 6 * 1024**3 or memory["free_commit"] < 8 * 1024**3:
        raise RuntimeError("Insufficient memory for bounded material import")
    sources = []
    scans = ROOT / "worldgen/materials/scanned_refinement/manifest.json"
    for item in json.loads(scans.read_text())["items"]:
        if item["license"] != "CC0-1.0":
            raise RuntimeError("Source is not admitted CC0 preview material")
        for channel, entry in item["maps"].items():
            sources.append(
                (item["asset"], channel, Path(entry["file"]), entry["sha256"])
            )
    surface_root = ROOT / "worldgen/materials/material_maker/surface_set"
    for item in json.loads((surface_root / "manifest.json").read_text())["items"]:
        folder = surface_root / item["directory"]
        validation = json.loads((folder / "validation.json").read_text())
        for channel, kind in (
            ("BaseColor", "diff"),
            ("Normal_DX", "nor_dx"),
            ("ORM", "arm"),
        ):
            path = (folder / validation["maps"][channel]["path"]).resolve()
            if not path.is_relative_to(folder.resolve()):
                raise RuntimeError("Surface path escapes its manifest")
            sources.append((item["role"], kind, path, item["maps_sha256"][channel]))
    for _, _, path, sha in sources:
        if digest(path) != sha:
            raise RuntimeError("Source texture identity mismatch: " + str(path))
    package = "/Game/Generated/YACS/MaterialRepair/Textures/" + uuid.uuid4().hex
    textures = {}
    rows = []
    for role, channel, path, sha in sources:
        task = unreal.AssetImportTask()
        for key, value in dict(
            filename=str(path),
            destination_path=package,
            destination_name="T_" + role + "_" + channel,
            automated=True,
            replace_existing=False,
            save=False,
        ).items():
            task.set_editor_property(key, value)
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        paths = task.get_editor_property("imported_object_paths")
        if len(paths) != 1:
            raise RuntimeError("Texture import did not produce exactly one asset")
        texture = unreal.load_asset(paths[0])
        settings = dict(
            srgb=channel == "diff",
            address_x=unreal.TextureAddress.TA_WRAP,
            address_y=unreal.TextureAddress.TA_WRAP,
            compression_settings={
                "diff": unreal.TextureCompressionSettings.TC_DEFAULT,
                "nor_dx": unreal.TextureCompressionSettings.TC_NORMALMAP,
                "arm": unreal.TextureCompressionSettings.TC_MASKS,
            }[channel],
        )
        if channel == "nor_dx":
            settings["flip_green_channel"] = False
        for key, value in settings.items():
            texture.set_editor_property(key, value)
            if texture.get_editor_property(key) != value:
                raise RuntimeError("Texture setting readback failed: " + key)
        textures.setdefault(role, {})[channel] = texture
        rows.append(dict(source=str(path), source_sha256=sha, asset=paths[0]))
    # Reuse the registered importer, including its producer/hash/grid checks.
    runpy.run_path(str(ROOT / "scripts/ue/prepare_sa_calobra_visual_fill.py"))["main"]()
    receipt = json.loads(
        (
            ROOT / "Saved/RuntimeProof/VisualFill" / (str(os.getpid()) + ".json")
        ).read_text()
    )
    textures["weights"] = unreal.load_asset(receipt["asset"])
    if not textures["weights"]:
        raise RuntimeError("Registered weight texture missing")
    state["repair_sources"] = textures
    state["repair_source_receipt"] = rows
    return textures


def build(state, mode):
    repair = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_repair.py"))
    sources = import_sources(state)
    g = repair["RepairGraph"]("M_SaCalobraRepair_" + mode)
    c, b, u = g.constant, g.binary, g.unary
    parameters = {}
    scalar_nodes = {}

    def scalar(name, value, low, high):
        if name in scalar_nodes:
            if parameters[name] != dict(default=value, minimum=low, maximum=high):
                raise RuntimeError("Conflicting scalar parameter: " + name)
            return scalar_nodes[name]
        n = g.node(
            "MaterialExpressionScalarParameter",
            parameter_name=name,
            default_value=value,
            slider_min=low,
            slider_max=high,
        )
        n = b("Min", b("Max", n, c(low)), c(high))
        parameters[name] = dict(default=value, minimum=low, maximum=high)
        scalar_nodes[name] = n
        return n

    def tint(name, value):
        return g.node(
            "MaterialExpressionVectorParameter",
            parameter_name=name,
            default_value=unreal.LinearColor(*value, 1),
        )

    def lerp(a, value, alpha):
        n = g.node("MaterialExpressionLinearInterpolate")
        for src, pin in ((a, "A"), (value, "B"), (alpha, "Alpha")):
            g.link(src, n, pin)
        return n

    def channel(source, pin, output=""):
        n = g.node(
            "MaterialExpressionComponentMask",
            r=pin == "R",
            g=pin == "G",
            b=pin == "B",
            a=pin == "A",
        )
        g.link(source, n, "", output)
        return n

    def add_all(values):
        result = values[0]
        for value in values[1:]:
            result = b("Add", result, value)
        return result

    # Pixel-centred, linear, bilinear sampling of the existing 4033-square mask.
    pos = g.node("MaterialExpressionWorldPosition")
    xy = g.node("MaterialExpressionComponentMask", r=True, g=True, b=False, a=False)
    g.link(pos, xy, "")
    uv = b(
        "Divide",
        b("Add", xy, g.node("MaterialExpressionConstant2Vector", r=25, g=25)),
        c(201650),
    )
    sample = g.node(
        "MaterialExpressionTextureSample",
        texture=sources["weights"],
        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )
    g.link(uv, sample, "")
    raw = {role: channel(sample, pin, "RGBA") for role, pin in zip(ROLES[:3], "RGB")}
    raw["DryMineral"] = u("Saturate", u("OneMinus", add_all(list(raw.values()))))
    overlay = channel(sample, "A", "RGBA")
    exponent = scalar("WeightExponent", 1.0, 1.0, 2.0)
    powered = {role: b("Power", weight, exponent) for role, weight in raw.items()}
    total = b("Max", add_all(list(powered.values())), c(0.000001))
    weights = {role: b("Divide", weight, total) for role, weight in powered.items()}
    direction = g.direction("mixed")
    # Optional limited artistic modifier. Default zero preserves minority masks.
    nz = u("Abs", channel(direction, "B"))
    t = u("Saturate", b("Divide", b("Subtract", c(0.4226182617), nz), c(0.3354625190)))
    smooth = b(
        "Multiply", b("Multiply", t, t), b("Subtract", c(3), b("Multiply", c(2), t))
    )
    slope = b("Multiply", smooth, scalar("SlopeRockStrength", 0, 0, 0.35))
    for role in weights:
        weights[role] = b("Multiply", weights[role], u("OneMinus", slope))
    weights["ExposedRock"] = b("Add", weights["ExposedRock"], slope)
    for role in weights:
        weights[role] = b("Multiply", weights[role], u("OneMinus", overlay))
    weights["Scree"] = overlay
    if mode == "weights" or mode.startswith("weight_"):
        if mode == "weights":
            palette = (
                (0.15, 0.8, 0.1),
                (0.0, 0.2, 0.6),
                (0.9, 0.9, 0.9),
                (0.65, 0.25, 0.05),
                (0.8, 0.1, 0.65),
            )
            output = add_all(
                [
                    b("Multiply", weights[r], c(color))
                    for r, color in zip(ROLES, palette)
                ]
            )
        else:
            output = weights[mode.removeprefix("weight_")]
        g.output(output, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        g.material.set_editor_property(
            "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
        )
    else:

        def project(role, kind, metres):
            fn = g.project(
                sources[role][kind],
                metres * 100,
                normal=kind == "nor_dx",
                masks=kind == "arm",
                direction=direction,
            )
            scale_name = (
                "RockMacroMetres"
                if role == "aerial_rocks_02" and metres == 50
                else "RockMesoMetres"
                if role == "aerial_rocks_02"
                else "GroundMetres"
                if role == "aerial_grass_rock"
                else "MicroMetres"
            )
            low, high = (
                (30, 100)
                if metres == 50
                else (4, 30)
                if metres == 12
                else (3, 30)
                if metres == 15
                else (0.5, 4)
            )
            size = b(
                "Multiply", scalar(scale_name, metres, low, high), c((100, 100, 100))
            )
            g.link(size, fn, "TextureSize")
            # Explicit named output avoids relying on a function's output order.
            n = g.node("MaterialExpressionMultiply", const_b=1.0)
            g.link(fn, n, "A", "XYZ Texture")
            return n

        def desaturate(value, amount):
            n = g.node("MaterialExpressionDesaturation")
            g.link(value, n, "")
            g.link(c(amount), n, "Fraction")
            return n

        # Three scales: 50m low-amplitude colour, 12m structure, 2m microdetail.
        macro = desaturate(project("aerial_rocks_02", "diff", 50), 1)
        rock = desaturate(project("aerial_rocks_02", "diff", 12), 0.9)
        rock = b(
            "Add",
            b("Multiply", rock, tint("RockTint", (0.80, 0.78, 0.71))),
            tint("RockLift", (0.12, 0.12, 0.115)),
        )
        macro_strength = scalar("MacroVariation", 0.18, 0, 0.3)
        modulation = b(
            "Add", c(1), b("Multiply", b("Subtract", macro, c(0.25)), macro_strength)
        )
        rock = b("Multiply", rock, modulation)
        grass = desaturate(project("aerial_grass_rock", "diff", 15), 0.4)
        colors = {
            "ExposedRock": rock,
            "DryGrass": b("Multiply", grass, tint("GrassTint", (0.72, 0.90, 0.48))),
            "ForestLitter": b(
                "Multiply", grass, tint("ForestTint", (0.35, 0.47, 0.22))
            ),
            "DryMineral": b(
                "Multiply",
                project("DryMineral", "diff", 2),
                tint("MineralTint", (0.65, 0.59, 0.49)),
            ),
            "Scree": b(
                "Multiply",
                project("Scree", "diff", 2),
                tint("ScreeTint", (0.9, 0.88, 0.81)),
            ),
        }
        rough_rock = channel(project("aerial_rocks_02", "arm", 12), "G")
        rough_ground = channel(project("aerial_grass_rock", "arm", 15), "G")
        roughness = {
            "ExposedRock": rough_rock,
            "DryGrass": rough_ground,
            "ForestLitter": rough_ground,
            "DryMineral": c(0.88),
            "Scree": c(0.85),
        }
        color = add_all([b("Multiply", colors[r], weights[r]) for r in ROLES])
        color = lerp(color, colors["ExposedRock"], scalar("DebugRockOnly", 0, 0, 1))
        rough = add_all([b("Multiply", roughness[r], weights[r]) for r in ROLES])
        rough = b("Min", b("Max", rough, c(0.65)), c(0.98))
        flat = c((0, 0, 1))
        if mode == "flat" or mode == "neutral":
            normal = flat
        else:
            meso = project("aerial_rocks_02", "nor_dx", 12)
            micro = project("ExposedRock", "nor_dx", 2)
            # A normalised interpolation in one tangent space; no raw WS normals.
            rock_normal = u(
                "Normalize", lerp(meso, micro, scalar("MicroNormalMix", 0.25, 0, 0.5))
            )
            ground_normal = project("aerial_grass_rock", "nor_dx", 15)
            normals = {
                "ExposedRock": rock_normal,
                "DryGrass": ground_normal,
                "ForestLitter": ground_normal,
                "DryMineral": flat,
                "Scree": project("Scree", "nor_dx", 2),
            }
            normal = u(
                "Normalize",
                add_all([b("Multiply", normals[r], weights[r]) for r in ROLES]),
            )
            normal = u(
                "Normalize", lerp(flat, normal, scalar("NormalStrength", 0.35, 0, 0.65))
            )
        g.output(
            c((0.35, 0.35, 0.35)) if mode == "neutral" else color,
            unreal.MaterialProperty.MP_BASE_COLOR,
        )
        g.output(rough, unreal.MaterialProperty.MP_ROUGHNESS)
        g.output(normal, unreal.MaterialProperty.MP_NORMAL)
        g.output(c(0), unreal.MaterialProperty.MP_METALLIC)
        g.output(c(0.25), unreal.MaterialProperty.MP_SPECULAR)
    material = g.compile()
    state.setdefault("repair_parameters", {})[mode] = parameters
    return material


def main(state, mode="candidate"):
    key = "repair_" + mode
    if key not in state["materials"]:
        state["materials"][key] = build(state, mode)
    repair = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_repair.py"))
    result = repair["assign"](state, state["materials"][key], key)
    result["parameters"] = state["repair_parameters"][mode]
    result["sources"] = state["repair_source_receipt"]
    result["mask_semantics"] = (
        "RGB base mixture; residual mineral; A independent artistic scree overlay"
    )
    (repair["OUT"] / (key + ".json")).write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
