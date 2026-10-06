"""Render deterministic ground-scale Material Forge references in pinned Blender."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import bpy
from mathutils import Vector

from scripts.blender.material_forge_reference_contract import (
    build_reference_plan,
    sha256_file,
)


def _tail_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rock", required=True, type=Path)
    parser.add_argument("--soil", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args(_tail_args())


def _require_below(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} must remain below {root}")
    return resolved


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_image(path: Path, *, srgb: bool) -> bpy.types.Image:
    image = bpy.data.images.load(str(path), check_existing=False)
    image.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    return image


def _material_from_variant(name: str, variant: dict) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (900, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (620, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-900, 0)

    base = nodes.new("ShaderNodeTexImage")
    base.location = (-650, 220)
    base.interpolation = "Linear"
    base.image = _load_image(Path(variant["maps"]["BaseColor"]["path"]), srgb=True)
    links.new(texcoord.outputs["UV"], base.inputs["Vector"])
    links.new(base.outputs["Color"], bsdf.inputs["Base Color"])

    orm = nodes.new("ShaderNodeTexImage")
    orm.location = (-650, -20)
    orm.interpolation = "Linear"
    orm.image = _load_image(Path(variant["maps"]["ORM"]["path"]), srgb=False)
    links.new(texcoord.outputs["UV"], orm.inputs["Vector"])
    orm_sep = nodes.new("ShaderNodeSeparateColor")
    orm_sep.mode = "RGB"
    orm_sep.location = (-370, -20)
    links.new(orm.outputs["Color"], orm_sep.inputs["Color"])
    links.new(orm_sep.outputs[1], bsdf.inputs["Roughness"])
    links.new(orm_sep.outputs[2], bsdf.inputs["Metallic"])

    normal = nodes.new("ShaderNodeTexImage")
    normal.location = (-650, -300)
    normal.interpolation = "Linear"
    normal.image = _load_image(
        Path(variant["maps"]["Normal_DX"]["path"]),
        srgb=False,
    )
    links.new(texcoord.outputs["UV"], normal.inputs["Vector"])

    split = nodes.new("ShaderNodeSeparateColor")
    split.mode = "RGB"
    split.location = (-380, -300)
    links.new(normal.outputs["Color"], split.inputs["Color"])

    flip_green = nodes.new("ShaderNodeMath")
    flip_green.operation = "SUBTRACT"
    flip_green.location = (-130, -340)
    flip_green.inputs[0].default_value = 1.0
    links.new(split.outputs[1], flip_green.inputs[1])

    combine = nodes.new("ShaderNodeCombineColor")
    combine.mode = "RGB"
    combine.location = (90, -260)
    links.new(split.outputs[0], combine.inputs[0])
    links.new(flip_green.outputs[0], combine.inputs[1])
    links.new(split.outputs[2], combine.inputs[2])

    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.space = "TANGENT"
    normal_map.location = (350, -240)
    normal_map.inputs["Strength"].default_value = 1.0
    links.new(combine.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
    return material


def _add_surface(
    name: str,
    x: float,
    tile: float,
    material: bpy.types.Material,
):
    bpy.ops.mesh.primitive_plane_add(size=tile, location=(x, 0.0, 0.0))
    obj = bpy.context.active_object
    obj.name = name
    obj.data.materials.append(material)
    return obj


def _simple_material(
    name: str,
    color: tuple[float, float, float, float],
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = 0.62
    return material


def _add_scale_marker() -> None:
    material = _simple_material(
        "YACS_ScaleMarker",
        (0.035, 0.035, 0.035, 1.0),
    )
    bpy.ops.mesh.primitive_cube_add(
        location=(0.0, 1.55, 0.9),
        scale=(0.03, 0.03, 0.9),
    )
    bpy.context.active_object.data.materials.append(material)
    bpy.ops.mesh.primitive_cube_add(
        location=(0.0, 1.55, 1.8),
        scale=(0.50, 0.025, 0.025),
    )
    bpy.context.active_object.data.materials.append(material)


def _configure_scene():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    world = bpy.data.worlds.new("YACS_ReferenceWorld")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.055, 0.065, 0.08, 1.0)
    background.inputs["Strength"].default_value = 0.42
    scene.world = world

    sun_data = bpy.data.lights.new("YACS_GrazingSun", type="SUN")
    sun_data.energy = 2.0
    sun_data.angle = math.radians(8.0)
    sun = bpy.data.objects.new("YACS_GrazingSun", sun_data)
    sun.rotation_euler = (
        math.radians(53.0),
        math.radians(-18.0),
        math.radians(-32.0),
    )
    scene.collection.objects.link(sun)

    area_data = bpy.data.lights.new("YACS_SoftFill", type="AREA")
    area_data.energy = 850.0
    area_data.shape = "DISK"
    area_data.size = 5.5
    area = bpy.data.objects.new("YACS_SoftFill", area_data)
    area.location = (-2.5, -3.5, 6.5)
    direction = Vector((0.0, 0.0, 0.0)) - area.location
    area.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(area)

    camera_data = bpy.data.cameras.new("YACS_ReferenceCamera")
    camera = bpy.data.objects.new("YACS_ReferenceCamera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    return scene, camera


def _set_camera(camera, view: dict) -> None:
    camera.location = tuple(view["location"])
    direction = Vector(tuple(view["target"])) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = float(view["lens_mm"])


def main() -> int:
    args = parse_args()
    expected = tuple(int(part) for part in args.expected_version.split("."))
    actual = tuple(int(value) for value in bpy.app.version[:3])
    if actual != expected:
        raise RuntimeError(
            f"bpy version mismatch: expected {expected}, got {actual}"
        )
    if not bpy.app.background:
        raise RuntimeError("Material Forge reference proof must run headlessly")

    config = Path(os.environ["YACS_WORKSPACE_CONFIG"]).resolve(strict=True)
    workspace_root = config.parent
    rock = _require_below(args.rock, workspace_root, "Rock variant")
    soil = _require_below(args.soil, workspace_root, "Soil variant")
    output = _require_below(
        args.output,
        workspace_root / "work" / "blender",
        "Reference output",
    )
    output.mkdir(parents=True, exist_ok=True)

    plan = build_reference_plan(rock, soil)
    tile = float(plan["tile_metres"])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene, camera = _configure_scene()

    gap = 0.15
    offset = tile / 2.0 + gap
    rock_material = _material_from_variant(
        "YACS_RegionalLimestone",
        plan["rock"],
    )
    soil_material = _material_from_variant(
        "YACS_MediterraneanSoil",
        plan["soil"],
    )
    _add_surface("YACS_RegionalLimestone", -offset, tile, rock_material)
    _add_surface("YACS_MediterraneanSoil", offset, tile, soil_material)
    _add_scale_marker()

    renders = []
    for view in plan["views"]:
        _set_camera(camera, view)
        path = output / f"{view['name']}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"Reference render missing: {path}")
        renders.append(
            {
                "name": view["name"],
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )

    receipt = {
        "schema_version": 1,
        "status": "BLENDER_REFERENCE_PASS_UE_REVIEW_PENDING",
        "blender_version": ".".join(str(value) for value in actual),
        "background": bool(bpy.app.background),
        "render_engine": scene.render.engine,
        "resolution": [
            scene.render.resolution_x,
            scene.render.resolution_y,
        ],
        "input_fingerprint": plan["input_fingerprint"],
        "tile_metres": tile,
        "left_surface": "regional_limestone/base",
        "right_surface": "mediterranean_soil/fine",
        "rock": plan["rock"],
        "soil": plan["soil"],
        "renders": renders,
        "directx_green_channel_flipped_for_blender": True,
        "ao_applied_to_albedo": False,
        "height_displacement_used": False,
        "world_semantics_changed": False,
        "geometry_authority_changed": False,
        "accepted_map_opened": False,
        "assets_saved_to_unreal": False,
        "visual_accepted": False,
        "performance_accepted": False,
    }
    canonical = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_sha256"
    }
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(
            canonical,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    _write_json(output / "reference-receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
