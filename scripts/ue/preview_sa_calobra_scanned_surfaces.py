"""Reversible scan-based surface candidate for the existing masked preview.

Uses CC0 payloads pinned in scanned_refinement/manifest.json. No saving,
height/displacement, geometry, lighting, placement or source-mask changes.
"""

import hashlib
import json
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary
ROLES = {"DryGrass", "ForestLitter", "ExposedRock", "Scree", "DryMineral"}


def main():
    base = runpy.run_path(
        str(ROOT / "scripts/ue/preview_sa_calobra_masked_materials.py")
    )
    world, landscape, components = base["context"]()
    state = getattr(unreal, base["STATE"], None)
    if not state or state["status"] != "APPLIED_SESSION_ONLY":
        raise RuntimeError("Apply the existing masked preview first")
    current = state["material"]
    if landscape.get_editor_property("landscape_material") != current or any(
        c.get_material(0) != current or c.get_editor_property("override_material")
        for c in components
    ):
        raise RuntimeError("Bindings changed externally")
    before = state["foundation"]["scene_snapshot"](world, landscape, state["map_file"])
    memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ]()
    if memory["free_physical"] < 6 * 1024**3 or memory["free_commit"] < 8 * 1024**3:
        raise RuntimeError("Insufficient memory for scan import")
    manifest_path = ROOT / "worldgen/materials/scanned_refinement/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for item in manifest["items"]:
        if item["license"] != "CC0-1.0":
            raise RuntimeError("Unexpected license")
        for entry in item["maps"].values():
            if (
                hashlib.sha256(Path(entry["file"]).read_bytes()).hexdigest()
                != entry["sha256"]
            ):
                raise RuntimeError("Scan source changed")
    package = "/Game/Generated/YACS/ScannedSurfaces/" + uuid.uuid4().hex
    textures = state.get("scan_textures")
    if textures is None:
        textures = {}
        for item in manifest["items"]:
            textures[item["asset"]] = {}
            for channel, entry in item["maps"].items():
                task = unreal.AssetImportTask()
                for key, value in dict(
                    filename=entry["file"],
                    destination_path=package,
                    destination_name="T_" + item["asset"] + "_" + channel,
                    automated=True,
                    replace_existing=False,
                    save=False,
                ).items():
                    task.set_editor_property(key, value)
                unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
                paths = task.get_editor_property("imported_object_paths")
                if len(paths) != 1:
                    raise RuntimeError("Scan import failed")
                tex = unreal.load_asset(paths[0])
                tex.set_editor_property("srgb", channel == "diff")
                tex.set_editor_property(
                    "compression_settings",
                    {
                        "diff": unreal.TextureCompressionSettings.TC_DEFAULT,
                        "nor_dx": unreal.TextureCompressionSettings.TC_NORMALMAP,
                        "arm": unreal.TextureCompressionSettings.TC_MASKS,
                    }[channel],
                )
                tex.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
                tex.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
                if channel == "nor_dx":
                    tex.set_editor_property("flip_green_channel", False)
                textures[item["asset"]][channel] = tex
        state["scan_textures"] = textures
    original = state.get("tuning_original")
    if original is None:
        raise RuntimeError("Original masked baseline not retained")
    material = unreal.EditorAssetLibrary.duplicate_asset(
        original.get_path_name(), package + "/M_ScannedLimestoneGround"
    )
    if not material:
        raise RuntimeError("Clone failed")
    expressions = list(LIB.get_material_expressions(material))

    def node(cls, **properties):
        result = LIB.create_material_expression(material, cls)
        if not result:
            raise RuntimeError("Expression creation failed")
        for key, value in properties.items():
            result.set_editor_property(key, value)
        return result

    def link(source, pin, target, socket):
        if not LIB.connect_material_expressions(source, pin, target, socket):
            raise RuntimeError("Connection failed: " + socket)

    def binary(cls, a, b=None, **props):
        result = node(cls, **props)
        link(a, "", result, "A")
        if b is not None:
            link(b, "", result, "B")
        return result

    def unary(cls, a):
        result = node(cls)
        link(a, "", result, "")
        return result

    legacy_pointer = json.loads(
        (
            ROOT / "worldgen/materials/sa_calobra_texture_library_result_20261005.json"
        ).read_text()
    )
    legacy = json.loads(Path(legacy_pointer["generation_receipt"]).read_text())
    lookup = {
        v["asset"]: row["role"]
        for row in legacy["items"]
        for v in row["outputs"].values()
    }
    products = []
    weights = {}
    limiters = [
        n
        for n in expressions
        if isinstance(n, unreal.MaterialExpressionMultiply)
        and abs(n.get_editor_property("const_b") - 0.55) < 0.00001
    ]
    if len(limiters) != 1:
        raise RuntimeError("Unexpected baseline grass limiter")
    limiters[0].set_editor_property("const_b", 1.0)
    for product in expressions:
        if not isinstance(product, unreal.MaterialExpressionMultiply):
            continue
        inputs = LIB.get_inputs_for_material_expression(material, product)
        if len(inputs) != 2:
            continue
        source, weight = inputs
        projection = source
        if isinstance(source, unreal.MaterialExpressionComponentMask):
            parents = LIB.get_inputs_for_material_expression(material, source)
            projection = parents[0] if parents else None
        if not isinstance(projection, unreal.MaterialExpressionMaterialFunctionCall):
            continue
        parents = LIB.get_inputs_for_material_expression(material, projection)
        objects = [
            p for p in parents if isinstance(p, unreal.MaterialExpressionTextureObject)
        ]
        if len(objects) != 1:
            continue
        obj = objects[0]
        tex = obj.get_editor_property("texture")
        role = lookup.get(tex.get_path_name())
        for candidate in ("ExposedRock", "Scree", "DryMineral"):
            if tex.get_name().startswith("T_" + candidate + "_"):
                role = candidate
        if role not in ROLES:
            continue
        products.append((product, projection, source, obj, role))
        weights[role] = weight
    if set(weights) != ROLES or any(
        sum(p[4] == r for p in products) != 3 for r in ROLES
    ):
        raise RuntimeError("Expected five roles, three channels each")

    # Sharpen mixed domains without inventing coverage where a source is zero.
    powered = {
        r: binary(unreal.MaterialExpressionMultiply, w, w) for r, w in weights.items()
    }
    total = None
    for value in powered.values():
        total = (
            value
            if total is None
            else binary(unreal.MaterialExpressionAdd, total, value)
        )
    normalized = {
        r: binary(unreal.MaterialExpressionDivide, w, total) for r, w in powered.items()
    }
    vn = node(unreal.MaterialExpressionVertexNormalWS)
    # Projection must follow the rendered surface, not only interpolated
    # Landscape vertex normals. Screen derivatives do not alter geometry.
    position = node(unreal.MaterialExpressionWorldPosition)
    dx = unary(unreal.MaterialExpressionDDX, position)
    dy = unary(unreal.MaterialExpressionDDY, position)
    geometric = unary(
        unreal.MaterialExpressionNormalize,
        binary(unreal.MaterialExpressionCrossProduct, dy, dx),
    )
    orientation = unary(
        unreal.MaterialExpressionSign,
        binary(unreal.MaterialExpressionDotProduct, geometric, vn),
    )
    geometric = binary(unreal.MaterialExpressionMultiply, geometric, orientation)
    nz = node(unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False)
    link(geometric, "", nz, "")
    nz = unary(unreal.MaterialExpressionAbs, nz)
    slope = binary(
        unreal.MaterialExpressionSubtract,
        node(unreal.MaterialExpressionConstant, r=0.75),
        nz,
    )
    slope = unary(
        unreal.MaterialExpressionSaturate,
        binary(unreal.MaterialExpressionDivide, slope, const_b=0.35),
    )
    gentle = unary(unreal.MaterialExpressionOneMinus, slope)
    final_weights = {
        r: binary(unreal.MaterialExpressionMultiply, w, gentle)
        for r, w in normalized.items()
    }
    final_weights["ExposedRock"] = binary(
        unreal.MaterialExpressionAdd, final_weights["ExposedRock"], slope
    )
    for product, projection, source, obj, role in products:
        link(final_weights[role], "", product, "B")
        sampler = obj.get_editor_property("sampler_type")
        color = sampler == unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
        normal = sampler == unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
        link(geometric, "", projection, "Normal" if normal else "World Space Normal")
        if normal:
            link(
                node(unreal.MaterialExpressionStaticBool, value=True),
                "",
                projection,
                "Use High Quality Normals",
            )
        if role in ("ExposedRock", "DryGrass", "ForestLitter"):
            asset = "aerial_rocks_02" if role == "ExposedRock" else "aerial_grass_rock"
            channel = "diff" if color else "nor_dx" if normal else "arm"
            obj.set_editor_property("texture", textures[asset][channel])
            size_cm = 5000 if role == "ExposedRock" else 1500
            size = node(
                unreal.MaterialExpressionConstant3Vector,
                constant=unreal.LinearColor(size_cm, size_cm, size_cm, 1),
            )
            link(size, "", projection, "TextureSize")
            if not color and not normal:
                source.set_editor_property("g", True)
                source.set_editor_property("r", False)
            if color:
                if role == "ExposedRock":
                    gray = node(unreal.MaterialExpressionDesaturation)
                    link(projection, "XYZ Texture", gray, "")
                    link(
                        node(unreal.MaterialExpressionConstant, r=1),
                        "",
                        gray,
                        "Fraction",
                    )
                    value = binary(unreal.MaterialExpressionMultiply, gray, const_b=0.9)
                    value = binary(unreal.MaterialExpressionAdd, value, const_b=0.12)
                    value = unary(unreal.MaterialExpressionSaturate, value)
                else:
                    gray = node(unreal.MaterialExpressionDesaturation)
                    link(projection, "XYZ Texture", gray, "")
                    link(
                        node(unreal.MaterialExpressionConstant, r=0.65),
                        "",
                        gray,
                        "Fraction",
                    )
                    tint = (
                        (0.48, 0.65, 0.32) if role == "DryGrass" else (0.24, 0.32, 0.15)
                    )
                    value = binary(
                        unreal.MaterialExpressionMultiply,
                        gray,
                        node(
                            unreal.MaterialExpressionConstant3Vector,
                            constant=unreal.LinearColor(*tint, 1),
                        ),
                    )
                link(value, "", product, "A")
        elif role == "DryMineral" and color:
            value = node(unreal.MaterialExpressionMultiply, const_b=0.45)
            link(projection, "XYZ Texture", value, "A")
            link(value, "", product, "A")
    normal_source = LIB.get_material_property_input_node(
        material, unreal.MaterialProperty.MP_NORMAL
    )
    softened = node(unreal.MaterialExpressionLinearInterpolate, const_alpha=0.4)
    link(
        node(
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(0, 0, 1, 1),
        ),
        "",
        softened,
        "A",
    )
    link(normal_source, "", softened, "B")
    softened = unary(unreal.MaterialExpressionNormalize, softened)
    if not LIB.connect_material_property(
        softened, "", unreal.MaterialProperty.MP_NORMAL
    ):
        raise RuntimeError("Normal output connection failed")
    if LIB.recompile_material(material):
        raise RuntimeError("Material compile failed")
    try:
        landscape.set_editor_property("landscape_material", material)
        if any(c.get_material(0) != material for c in components):
            raise RuntimeError("Component binding mismatch")
        if before != state["foundation"]["scene_snapshot"](
            world, landscape, state["map_file"]
        ):
            raise RuntimeError("Frozen scene changed")
    except Exception:
        landscape.set_editor_property("landscape_material", current)
        raise
    state["material"] = material
    result = dict(
        material=material.get_path_name(),
        component_bindings_verified=len(components),
        geometry_snapshot_equal=True,
        map_saved=False,
        visual_acceptance="pending",
        performance="not measured",
        source_manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    )
    (ROOT / "Saved/RuntimeProof/MaskedMaterials/scanned.json").write_text(
        json.dumps(result, indent=2)
    )
    unreal.log("YACS_SCANNED_SURFACES " + json.dumps(result))


if __name__ == "__main__":
    main()
