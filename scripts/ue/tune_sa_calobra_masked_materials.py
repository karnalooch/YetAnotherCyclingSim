"""Reversible shading-only A/B and slope-aware palette correction."""

import json
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
LIB = unreal.MaterialEditingLibrary


def main(action="correct"):
    base = runpy.run_path(
        str(ROOT / "scripts/ue/preview_sa_calobra_masked_materials.py")
    )
    world, landscape, components = base["context"]()
    state = getattr(unreal, base["STATE"], None)
    if not state or state["status"] != "APPLIED_SESSION_ONLY":
        raise RuntimeError("Expected active masked preview")
    if landscape.get_editor_property("landscape_material") != state["material"]:
        raise RuntimeError("Material changed externally")
    before = state["foundation"]["scene_snapshot"](world, landscape, state["map_file"])
    current = state["material"]
    if action == "flat":
        package = "/Game/Generated/YACS/MaskedMaterials/" + uuid.uuid4().hex
        target = unreal.EditorAssetLibrary.duplicate_asset(
            current.get_path_name(), package + "/M_FlatNormalCheck"
        )
        if not target:
            raise RuntimeError("Clone failed")
        flat = LIB.create_material_expression(
            target, unreal.MaterialExpressionConstant3Vector
        )
        flat.set_editor_property("constant", unreal.LinearColor(0, 0, 1, 1))
        if not LIB.connect_material_property(
            flat, "", unreal.MaterialProperty.MP_NORMAL
        ):
            raise RuntimeError("Flat normal connection failed")
        state["tuning_original"] = current
    elif action == "correct":
        original = state.setdefault("tuning_original", current)
        package = "/Game/Generated/YACS/MaskedMaterials/" + uuid.uuid4().hex
        target = unreal.EditorAssetLibrary.duplicate_asset(
            original.get_path_name(), package + "/M_SlopeAwareLimestone"
        )
        if not target:
            raise RuntimeError("Clone failed")
        expressions = list(LIB.get_material_expressions(target))
        grass_limits = [
            n
            for n in expressions
            if isinstance(n, unreal.MaterialExpressionMultiply)
            and abs(n.get_editor_property("const_b") - 0.55) < 0.00001
        ]
        if len(grass_limits) != 1:
            raise RuntimeError("Expected exactly one dry-fibre contribution limiter")
        grass_limits[0].set_editor_property("const_b", 1.0)

        def node(cls, **props):
            n = LIB.create_material_expression(target, cls)
            if n is None:
                raise RuntimeError("Node failed")
            for k, v in props.items():
                n.set_editor_property(k, v)
            return n

        def link(a, pin, b, socket):
            if not LIB.connect_material_expressions(a, pin, b, socket):
                raise RuntimeError("Connection failed " + socket)

        def unary(cls, a):
            n = node(cls)
            link(a, "", n, "")
            return n

        def binary(cls, a, b=None, **props):
            n = node(cls, **props)
            link(a, "", n, "A")
            if b is not None:
                link(b, "", n, "B")
            return n

        # Shading only: all geographic/placement rasters remain unchanged.
        vn = node(unreal.MaterialExpressionVertexNormalWS)
        nz = node(
            unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False
        )
        link(vn, "", nz, "")
        nz = unary(unreal.MaterialExpressionAbs, nz)
        # Smoothly replace ground cover by rock from about 41 to 66 degrees.
        steep = binary(
            unreal.MaterialExpressionSubtract,
            node(unreal.MaterialExpressionConstant, r=0.75),
            nz,
        )
        steep = unary(
            unreal.MaterialExpressionSaturate,
            binary(unreal.MaterialExpressionDivide, steep, const_b=0.35),
        )
        gentle = unary(unreal.MaterialExpressionOneMinus, steep)
        legacy = json.loads(
            (
                ROOT
                / "Saved/RuntimeProof/TextureLibraries/3fb8a9508ac141a396189f4a0c3438f9/result.json"
            ).read_text()
        )
        role_by_texture = {
            v["asset"]: row["role"]
            for row in legacy["items"]
            for v in row["outputs"].values()
        }
        changed = []
        for product in expressions:
            if not isinstance(product, unreal.MaterialExpressionMultiply):
                continue
            inputs = LIB.get_inputs_for_material_expression(target, product)
            if len(inputs) != 2:
                continue
            source, weight = inputs
            projection = source
            if isinstance(source, unreal.MaterialExpressionComponentMask):
                parents = LIB.get_inputs_for_material_expression(target, source)
                if not parents:
                    continue
                projection = parents[0]
            if not isinstance(
                projection, unreal.MaterialExpressionMaterialFunctionCall
            ):
                continue
            parents = LIB.get_inputs_for_material_expression(target, projection)
            objects = [
                p
                for p in parents
                if isinstance(p, unreal.MaterialExpressionTextureObject)
            ]
            if len(objects) != 1:
                continue
            texture = objects[0].get_editor_property("texture")
            path = texture.get_path_name()
            role = role_by_texture.get(path)
            for candidate in ("ExposedRock", "Scree", "DryMineral"):
                if texture.get_name().startswith("T_" + candidate + "_"):
                    role = candidate
            if role not in (
                "DryGrass",
                "ForestLitter",
                "ExposedRock",
                "Scree",
                "DryMineral",
            ):
                continue
            new_weight = binary(unreal.MaterialExpressionMultiply, weight, gentle)
            if role == "ExposedRock":
                new_weight = binary(unreal.MaterialExpressionAdd, new_weight, steep)
            link(new_weight, "", product, "B")
            if (
                objects[0].get_editor_property("sampler_type")
                == unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
            ):
                if role in ("DryGrass", "ForestLitter"):
                    desat = node(unreal.MaterialExpressionDesaturation)
                    link(projection, "XYZ Texture", desat, "")
                    link(
                        node(unreal.MaterialExpressionConstant, r=1),
                        "",
                        desat,
                        "Fraction",
                    )
                    # Linear albedo multipliers: muted Mediterranean olive ground.
                    tint = (
                        (0.32, 0.48, 0.14) if role == "DryGrass" else (0.34, 0.40, 0.19)
                    )
                    color = binary(
                        unreal.MaterialExpressionMultiply,
                        desat,
                        node(
                            unreal.MaterialExpressionConstant3Vector,
                            constant=unreal.LinearColor(*tint, 1),
                        ),
                    )
                    link(color, "", product, "A")
                elif role == "DryMineral":
                    color = node(unreal.MaterialExpressionMultiply, const_b=0.55)
                    link(projection, "XYZ Texture", color, "A")
                    link(color, "", product, "A")
                elif role == "ExposedRock":
                    macro = node(unreal.MaterialExpressionMaterialFunctionCall)
                    if not macro.set_material_function(
                        projection.get_editor_property("material_function")
                    ):
                        raise RuntimeError("Macro projection failed")
                    link(objects[0], "", macro, "TextureObject")
                    size = node(
                        unreal.MaterialExpressionConstant3Vector,
                        constant=unreal.LinearColor(800, 800, 800, 1),
                    )
                    link(size, "", macro, "TextureSize")
                    red = node(
                        unreal.MaterialExpressionComponentMask,
                        r=True,
                        g=False,
                        b=False,
                        a=False,
                    )
                    link(macro, "XYZ Texture", red, "")
                    ramp = binary(unreal.MaterialExpressionSubtract, red, const_b=0.40)
                    ramp = unary(
                        unreal.MaterialExpressionSaturate,
                        binary(unreal.MaterialExpressionMultiply, ramp, const_b=5),
                    )
                    factor = binary(
                        unreal.MaterialExpressionAdd,
                        binary(unreal.MaterialExpressionMultiply, ramp, const_b=0.4),
                        const_b=0.65,
                    )
                    varied = node(unreal.MaterialExpressionMultiply)
                    link(projection, "XYZ Texture", varied, "A")
                    link(factor, "", varied, "B")
                    link(varied, "", product, "A")
            changed.append(role)
        expected_roles = {"DryGrass", "ForestLitter", "ExposedRock", "Scree", "DryMineral"}
        if set(changed) != expected_roles or any(
            changed.count(role) != 3 for role in expected_roles
        ):
            raise RuntimeError(
                "Expected three channels for five roles, got " + str(changed)
            )
        # Soften micro normals only; no change to terrain normals or geometry.
        original_normal = LIB.get_material_property_input_node(
            target, unreal.MaterialProperty.MP_NORMAL
        )
        flat = node(
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(0, 0, 1, 1),
        )
        normal = node(unreal.MaterialExpressionLinearInterpolate, const_alpha=0.85)
        link(flat, "", normal, "A")
        link(original_normal, "", normal, "B")
        normal = unary(unreal.MaterialExpressionNormalize, normal)
        if not LIB.connect_material_property(
            normal, "", unreal.MaterialProperty.MP_NORMAL
        ):
            raise RuntimeError("Normal failed")
    elif action == "restore":
        target = state["tuning_original"]
    else:
        raise ValueError(action)
    if action != "restore" and LIB.recompile_material(target):
        raise RuntimeError("Compile failed")
    try:
        landscape.set_editor_property("landscape_material", target)
        if any(c.get_material(0) != target for c in components):
            raise RuntimeError("Binding mismatch")
        if before != state["foundation"]["scene_snapshot"](
            world, landscape, state["map_file"]
        ):
            raise RuntimeError("Frozen scene changed")
    except Exception:
        landscape.set_editor_property("landscape_material", current)
        raise
    state["material"] = target
    report = dict(
        action=action,
        material=target.get_path_name(),
        component_bindings_verified=1024,
        geometry_snapshot_equal=True,
        map_saved=False,
        visual_acceptance="pending",
        performance="not measured",
    )
    out = ROOT / "Saved/RuntimeProof/MaskedMaterials"
    (out / ("tuning-" + action + ".json")).write_text(json.dumps(report, indent=2))
    unreal.log("YACS_MATERIAL_TUNING " + json.dumps(report))


if __name__ == "__main__":
    main()
