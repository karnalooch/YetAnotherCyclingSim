"""Session-only whole-Landscape material preview, with exact binding rollback.

Run main('prepare'), then main('apply') after compilation settles.
main('restore') restores only this preview's material bindings. Never saves maps.
"""

import hashlib
import json
import os
import runpy
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
LIB = unreal.MaterialEditingLibrary
STATE = "_yacs_masked_material_preview"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError("Keep the accepted map open")
    actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(actors) != 1:
        raise RuntimeError("Expected one Landscape")
    components = actors[0].get_components_by_class(unreal.LandscapeComponent)
    if len(components) != 1024:
        raise RuntimeError("Unexpected frozen Landscape topology")
    return world, actors[0], components


def report(state, status, **extra):
    state["status"] = status
    out = ROOT / "Saved/RuntimeProof/MaskedMaterials"
    out.mkdir(parents=True, exist_ok=True)
    data = dict(
        status=status,
        material=state["material"].get_path_name(),
        weights_manifest_sha256=state["mask_hash"],
        map_saved=False,
        geometry_mutation=False,
        whole_landscape_components=1024,
        visual_acceptance="pending",
        performance="not measured",
        **extra,
    )
    (out / (str(os.getpid()) + ".json")).write_text(json.dumps(data, indent=2))
    unreal.log("YACS_MASKED_MATERIALS " + json.dumps(data))


def prepare():
    if getattr(unreal, STATE, None):
        raise RuntimeError("Preview already prepared; apply or restore it")
    world, landscape, components = context()
    memory = runpy.run_path(str(ROOT / "scripts/ue/sa_calobra_material_waves.py"))[
        "available_memory"
    ]()
    if memory["free_physical"] < 8 * 1024**3 or memory["free_commit"] < 12 * 1024**3:
        raise RuntimeError("Insufficient memory for preview preparation")
    mask_root = ROOT / "worldgen/materials/visual_fill"
    manifest = mask_root / "material-input-manifest.json"
    data = json.loads(manifest.read_text())
    payload = {k: v for k, v in data.items() if k != "fingerprint"}
    if (
        hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        != data["fingerprint"]
    ):
        raise RuntimeError("Mask fingerprint mismatch")
    if (
        data["status"] != "PRESENTATION_VISUAL_FILL_CANDIDATE"
        or data["grid"]["width"] != 4033
        or data["world_mapping"]["footprint_world_bounds_cm"]
        != [-25, -25, 201625, 201625]
    ):
        raise RuntimeError("Unsupported visual mask registration")
    for item in data["outputs"]:
        if (
            Path(item["path"]).name != item["path"]
            or digest(mask_root / item["path"]) != item["sha256"]
        ):
            raise RuntimeError("Mask bytes changed")
    receipt = ROOT / "Saved/RuntimeProof/VisualFill" / (str(os.getpid()) + ".json")
    imported = json.loads(receipt.read_text())
    if imported["manifest_sha256"] != digest(manifest):
        raise RuntimeError("Import receipt does not match mask")
    weights = unreal.load_asset(imported["asset"])
    if (
        not weights
        or weights.get_editor_property("srgb")
        or weights.get_editor_property("filter") != unreal.TextureFilter.TF_BILINEAR
    ):
        raise RuntimeError("Missing linear bilinear weight texture")
    foundation = runpy.run_path(
        str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
    )
    map_file = ROOT / "Content" / (MAP.removeprefix("/Game/") + ".umap")
    before = foundation["scene_snapshot"](world, landscape, map_file)
    package = "/Game/Generated/YACS/MaskedMaterials/" + uuid.uuid4().hex
    surface_root = ROOT / "worldgen/materials/material_maker/surface_set"
    surfaces = json.loads((surface_root / "manifest.json").read_text())
    textures = {}
    scales = {}
    # Validate every new file before importing any of them.
    paths = {}
    for item in surfaces["items"]:
        role = item["role"]
        folder = surface_root / item["directory"]
        validation = json.loads((folder / "validation.json").read_text())
        if validation["status"] != "MAP_CHECKS_PASS_UE_REVIEW_PENDING":
            raise RuntimeError("Surface validation missing")
        paths[role] = {}
        for channel in ("BaseColor", "Normal_DX", "ORM"):
            entry = validation["maps"][channel]
            file = (folder / entry["path"]).resolve()
            if (
                not file.is_relative_to(folder.resolve())
                or digest(file) != item["maps_sha256"][channel]
            ):
                raise RuntimeError("Surface identity mismatch")
            paths[role][channel] = file
        scales[role] = item["tile_metres"] * 100
    for role, channels in paths.items():
        textures[role] = {}
        for channel, file in channels.items():
            task = unreal.AssetImportTask()
            for prop, value in dict(
                filename=str(file),
                destination_path=package,
                destination_name="T_" + role + "_" + channel,
                automated=True,
                replace_existing=False,
                save=False,
            ).items():
                task.set_editor_property(prop, value)
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            imported_paths = task.get_editor_property("imported_object_paths")
            if len(imported_paths) != 1:
                raise RuntimeError("Import failed")
            tex = unreal.load_asset(imported_paths[0])
            tex.set_editor_property("srgb", channel == "BaseColor")
            tex.set_editor_property(
                "compression_settings",
                unreal.TextureCompressionSettings.TC_DEFAULT
                if channel == "BaseColor"
                else unreal.TextureCompressionSettings.TC_NORMALMAP
                if channel == "Normal_DX"
                else unreal.TextureCompressionSettings.TC_MASKS,
            )
            tex.set_editor_property("address_x", unreal.TextureAddress.TA_WRAP)
            tex.set_editor_property("address_y", unreal.TextureAddress.TA_WRAP)
            if channel == "Normal_DX":
                tex.set_editor_property("flip_green_channel", False)
            textures[role][channel] = tex
    legacy_receipt = json.loads(
        (
            ROOT / "worldgen/materials/sa_calobra_texture_library_result_20261005.json"
        ).read_text()
    )
    legacy = json.loads(Path(legacy_receipt["generation_receipt"]).read_text())
    for item in legacy["items"]:
        role = item["role"]
        if role in ("DryGrass", "ForestLitter"):
            textures[role] = {
                channel: foundation["load_required"](item["outputs"][channel]["asset"])
                for channel in ("BaseColor", "Normal", "Roughness")
            }
            scales[role] = item["recipe"]["worldSizeMeters"]["x"] * 100
    if set(textures) != {
        "ExposedRock",
        "DryMineral",
        "Scree",
        "DryGrass",
        "ForestLitter",
    }:
        raise RuntimeError("Incomplete surface set")
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_SaCalobraMaskedSurfaces",
        package,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if not material:
        raise RuntimeError("Material creation failed")
    nodes = []

    def node(cls, **props):
        n = LIB.create_material_expression(
            material, cls, -300 * (1 + len(nodes) % 10), 160 * (len(nodes) // 10)
        )
        if n is None:
            raise RuntimeError("Node creation failed")
        for k, v in props.items():
            n.set_editor_property(k, v)
        nodes.append(n)
        return n

    def link(a, pin, b, socket):
        if not LIB.connect_material_expressions(a, pin, b, socket):
            raise RuntimeError("Connection failed: " + socket)

    def binary(cls, a, b=None, **props):
        n = node(cls, **props)
        link(a, "", n, "A")
        if b is not None:
            link(b, "", n, "B")
        return n

    def unary(cls, a):
        n = node(cls)
        link(a, "", n, "")
        return n

    pos = node(unreal.MaterialExpressionWorldPosition)
    xy = node(unreal.MaterialExpressionComponentMask, r=True, g=True, b=False, a=False)
    link(pos, "", xy, "")
    add = binary(
        unreal.MaterialExpressionAdd,
        xy,
        node(unreal.MaterialExpressionConstant2Vector, r=25, g=25),
    )
    uv = binary(unreal.MaterialExpressionDivide, add, const_b=201650)
    sample = node(
        unreal.MaterialExpressionTextureSample,
        texture=weights,
        sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
    )
    link(uv, "", sample, "")
    channels = {}
    for role, pin in [
        ("DryGrass", "R"),
        ("ForestLitter", "G"),
        ("ExposedRock", "B"),
        ("Scree", "A"),
    ]:
        n = node(
            unreal.MaterialExpressionComponentMask,
            r=pin == "R",
            g=pin == "G",
            b=pin == "B",
            a=pin == "A",
        )
        link(sample, "RGBA", n, "")
        channels[role] = n
    # Preserve a mineral floor below decorative dry fibres.
    channels["DryGrass"] = binary(
        unreal.MaterialExpressionMultiply, channels["DryGrass"], const_b=0.55
    )
    total = binary(
        unreal.MaterialExpressionAdd, channels["DryGrass"], channels["ForestLitter"]
    )
    total = binary(unreal.MaterialExpressionAdd, total, channels["ExposedRock"])
    channels["DryMineral"] = unary(
        unreal.MaterialExpressionSaturate,
        unary(unreal.MaterialExpressionOneMinus, total),
    )
    underneath = unary(unreal.MaterialExpressionOneMinus, channels["Scree"])
    for role in list(channels):
        if role != "Scree":
            channels[role] = binary(
                unreal.MaterialExpressionMultiply, channels[role], underneath
            )
    tangent = node(unreal.MaterialExpressionStaticBool, value=False)
    outputs = {}
    for role, weight in channels.items():
        size = node(
            unreal.MaterialExpressionConstant3Vector,
            constant=unreal.LinearColor(scales[role], scales[role], scales[role], 1),
        )
        for channel, tex in textures[role].items():
            normal = channel in ("Normal", "Normal_DX")
            sampler = (
                unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
                if normal
                else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR
                if channel == "BaseColor"
                else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
            )
            obj = node(
                unreal.MaterialExpressionTextureObject,
                texture=tex,
                sampler_type=sampler,
            )
            fn = node(unreal.MaterialExpressionMaterialFunctionCall)
            name = "WorldAlignedNormal" if normal else "WorldAlignedTexture"
            if not fn.set_material_function(
                foundation["load_required"](
                    "/Engine/Functions/Engine_MaterialFunctions01/Texturing/" + name
                )
            ):
                raise RuntimeError("Projection unavailable")
            link(obj, "", fn, "TextureObject")
            link(size, "", fn, "TextureSize")
            if normal:
                link(tangent, "", fn, "WorldSpace")
            val = fn
            pin = "XYZ Texture"
            out = "Normal" if normal else channel
            if channel in ("ORM", "Roughness"):
                out = "Roughness"
                val = node(
                    unreal.MaterialExpressionComponentMask,
                    r=channel == "Roughness",
                    g=channel == "ORM",
                    b=False,
                    a=False,
                )
                link(fn, pin, val, "")
                pin = ""
            product = node(unreal.MaterialExpressionMultiply)
            link(val, pin, product, "A")
            link(weight, "", product, "B")
            outputs[out] = (
                binary(unreal.MaterialExpressionAdd, outputs[out], product)
                if out in outputs
                else product
            )
    outputs["Normal"] = unary(unreal.MaterialExpressionNormalize, outputs["Normal"])
    for key, prop in [
        ("BaseColor", unreal.MaterialProperty.MP_BASE_COLOR),
        ("Normal", unreal.MaterialProperty.MP_NORMAL),
        ("Roughness", unreal.MaterialProperty.MP_ROUGHNESS),
    ]:
        if not LIB.connect_material_property(outputs[key], "", prop):
            raise RuntimeError("Output failed")
    # No height/displacement, WPO or baked AO: frozen geometry remains authority.
    if LIB.recompile_material(material):
        raise RuntimeError("Material compile call failed")
    state = dict(
        world=world,
        landscape=landscape,
        components=components,
        material=material,
        original=landscape.get_editor_property("landscape_material"),
        overrides={
            c.get_path_name(): c.get_editor_property("override_material")
            for c in components
        },
        before=before,
        foundation=foundation,
        map_file=map_file,
        mask_hash=digest(manifest),
    )
    if before != foundation["scene_snapshot"](world, landscape, map_file):
        raise RuntimeError("Scene changed during preparation")
    setattr(unreal, STATE, state)
    report(state, "PREPARED_NOT_APPLIED", nodes=len(nodes), texture_count=16)


def restore_bindings(s):
    s["landscape"].set_editor_property("landscape_material", s["original"])
    for c in s["components"]:
        c.set_editor_property("override_material", s["overrides"][c.get_path_name()])


def main(action="prepare"):
    if action == "prepare":
        return prepare()
    if action not in ("apply", "restore"):
        raise ValueError("Unknown action")
    s = getattr(unreal, STATE, None)
    if not s:
        raise RuntimeError("No prepared session preview")
    world, landscape, components = context()
    if world != s["world"] or landscape != s["landscape"]:
        raise RuntimeError("World changed")
    if action == "restore":
        if (
            s["status"] != "APPLIED_SESSION_ONLY"
            or landscape.get_editor_property("landscape_material") != s["material"]
            or any(c.get_editor_property("override_material") for c in components)
        ):
            raise RuntimeError("Bindings changed externally; preserve them")
        restore_bindings(s)
        report(s, "RESTORED")
        return
    if s["status"] not in ("PREPARED_NOT_APPLIED", "FAILED_ROLLED_BACK"):
        raise RuntimeError("Already applied")
    if landscape.get_editor_property("landscape_material") != s["original"] or any(
        c.get_editor_property("override_material") != s["overrides"][c.get_path_name()]
        for c in components
    ):
        raise RuntimeError("Bindings changed externally")
    before = s["foundation"]["scene_snapshot"](world, landscape, s["map_file"])
    try:
        landscape.set_editor_property("landscape_material", s["material"])
        for c in components:
            if c.get_editor_property("override_material"):
                c.set_editor_property("override_material", None)
        if landscape.get_editor_property("landscape_material") != s["material"]:
            raise RuntimeError("Assignment failed")
        if before != s["foundation"]["scene_snapshot"](world, landscape, s["map_file"]):
            raise RuntimeError("Frozen scene changed")
        audit = getattr(
            unreal.YacsTextureAuditLibrary,
            "describe_landscape_material_instances",
            None,
        )
        checked = 0
        for c in components:
            if (
                c.get_editor_property("override_material") is not None
                or c.get_material(0) != s["material"]
            ):
                raise RuntimeError("Component material mismatch: " + c.get_name())
            if audit:
                row = json.loads(audit(c, s["material"]))
                if not row.get("all_instances_match"):
                    raise RuntimeError("Render material mismatch: " + c.get_name())
                checked += row["render_instance_count"]
        report(
            s,
            "APPLIED_SESSION_ONLY",
            geometry_snapshot_equal=True,
            render_instances_verified=checked
            if audit
            else "PENDING_NATIVE_AUDIT_UNAVAILABLE",
            component_bindings_verified=len(components),
        )
    except Exception:
        restore_bindings(s)
        report(s, "FAILED_ROLLED_BACK")
        raise


if __name__ == "__main__":
    main()
