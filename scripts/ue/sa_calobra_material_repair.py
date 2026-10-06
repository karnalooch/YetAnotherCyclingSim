"""Bounded native-material repair on the accepted Landscape, with binding rollback.

Run main('checker') for the metric projection diagnostic. No geometry or map save.
Installed UE 5.8.2 graph inspection defines Normal as tangent-space input and
WorldSpace=False as tangent-space output on WorldAlignedNormal.
"""

import hashlib
import json
import runpy
import time
import uuid
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
MAP = "/Game/Worlds/SaCalobra/L_SaCalobraAccepted_20261004"
STATE = "_yacs_material_repair"
LIB = unreal.MaterialEditingLibrary
OUT = ROOT / "Saved/RuntimeProof/MaterialRepair"


def snapshot(state):
    return state["foundation"]["scene_snapshot"](
        state["world"], state["landscape"], state["map_file"]
    )


def context():
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = editor.get_editor_world()
    if world.get_path_name().split(".")[0] != MAP:
        raise RuntimeError("Wrong map; refuse automatic map switching")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Projection functions require the inspected UE 5.8.2")
    state = getattr(unreal, STATE, None)
    if state:
        if state["world"] != world or snapshot(state) != state["before"]:
            raise RuntimeError("Frozen scene changed outside material repair")
        if (
            state["landscape"].get_editor_property("landscape_material")
            != state["current"]
        ):
            raise RuntimeError("Material changed outside this repair")
        return state
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected exactly one frozen Landscape")
    landscape = landscapes[0]
    components = list(landscape.get_components_by_class(unreal.LandscapeComponent))
    if len(components) != 1024 or any(
        c.get_editor_property("override_material") for c in components
    ):
        raise RuntimeError("Unexpected component topology or existing override")
    state = {
        "world": world,
        "landscape": landscape,
        "components": components,
        "map_file": ROOT / "Content" / (MAP.removeprefix("/Game/") + ".umap"),
        "foundation": runpy.run_path(
            str(ROOT / "scripts/ue/sa_calobra_material_foundation.py")
        ),
        "original": landscape.get_editor_property("landscape_material"),
        "camera": editor.get_level_viewport_camera_info(),
        "materials": {},
        "textures": {},
    }
    state["current"] = state["original"]
    state["before"] = snapshot(state)
    setattr(unreal, STATE, state)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "baseline.json").write_text(
        json.dumps(
            {
                "world": world.get_path_name(),
                "material": state["original"].get_path_name(),
                "scene_snapshot": state["before"],
                "camera_position": [
                    state["camera"][0].x,
                    state["camera"][0].y,
                    state["camera"][0].z,
                ],
                "camera_rotation": [
                    state["camera"][1].pitch,
                    state["camera"][1].yaw,
                    state["camera"][1].roll,
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return state


class RepairGraph:
    def __init__(self, name):
        package = "/Game/Generated/YACS/MaterialRepair/" + uuid.uuid4().hex
        self.material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            name, package, unreal.Material, unreal.MaterialFactoryNew()
        )
        if not self.material:
            raise RuntimeError("Material creation failed")
        self.material.set_editor_property("tangent_space_normal", True)

    def node(self, kind, **properties):
        node = LIB.create_material_expression(self.material, getattr(unreal, kind))
        if not node:
            raise RuntimeError("Expression creation failed: " + kind)
        for key, value in properties.items():
            node.set_editor_property(key, value)
        return node

    def link(self, source, target, socket, pin=""):
        if not LIB.connect_material_expressions(source, pin, target, socket):
            raise RuntimeError("Expression connection failed: " + socket)

    def constant(self, value):
        if isinstance(value, (int, float)):
            return self.node("MaterialExpressionConstant", r=value)
        return self.node(
            "MaterialExpressionConstant3Vector", constant=unreal.LinearColor(*value, 1)
        )

    def binary(self, kind, a, b):
        node = self.node("MaterialExpression" + kind)
        self.link(a, node, "Base" if kind == "Power" else "A")
        self.link(b, node, "Exp" if kind == "Power" else "B")
        return node

    def unary(self, kind, value):
        node = self.node("MaterialExpression" + kind)
        self.link(value, node, "")
        return node

    def direction(self, mode):
        vertex = self.node("MaterialExpressionVertexNormalWS")
        if mode == "native":
            return vertex
        position = self.node("MaterialExpressionWorldPosition")
        dx, dy = self.unary("DDX", position), self.unary("DDY", position)
        normal = self.unary("Normalize", self.binary("CrossProduct", dy, dx))
        sign = self.unary("Sign", self.binary("DotProduct", normal, vertex))
        normal = self.binary("Multiply", normal, sign)
        if mode == "geometric":
            return normal
        blend = self.node("MaterialExpressionLinearInterpolate", const_alpha=0.65)
        self.link(vertex, blend, "A")
        self.link(normal, blend, "B")
        return self.unary("Normalize", blend)

    def output(self, expression, prop, pin=""):
        if not LIB.connect_material_property(expression, pin, prop):
            raise RuntimeError("Material output failed: " + str(prop))

    def project(self, texture, size_cm, normal=False, masks=False, direction=None):
        obj = self.node(
            "MaterialExpressionTextureObject",
            texture=texture,
            sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
            if normal
            else unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
            if masks
            else unreal.MaterialSamplerType.SAMPLERTYPE_COLOR,
        )
        fn = self.node("MaterialExpressionMaterialFunctionCall")
        name = "WorldAlignedNormal" if normal else "WorldAlignedTexture"
        asset = unreal.load_asset(
            "/Engine/Functions/Engine_MaterialFunctions01/Texturing/" + name
        )
        if not asset or not fn.set_material_function(asset):
            raise RuntimeError("Native projection missing")
        self.link(obj, fn, "TextureObject")
        self.link(self.constant((size_cm, size_cm, size_cm)), fn, "TextureSize")
        # Leave native surface-direction defaults intact. Normal is tangent-space,
        # not a socket for the geometric world normal or its screen derivatives.
        if normal:
            self.link(
                self.node("MaterialExpressionStaticBool", value=False), fn, "WorldSpace"
            )
            self.link(
                self.node("MaterialExpressionStaticBool", value=True),
                fn,
                "Use High Quality Normals",
            )
        if direction is not None:
            if normal:
                tangent = self.node(
                    "MaterialExpressionTransform",
                    transform_source_type=unreal.MaterialVectorCoordTransformSource.TRANSFORMSOURCE_WORLD,
                    transform_type=unreal.MaterialVectorCoordTransform.TRANSFORM_TANGENT,
                )
                self.link(direction, tangent, "")
                self.link(tangent, fn, "Normal")
            else:
                self.link(direction, fn, "World Space Normal")
        return fn

    def compile(self):
        errors = LIB.recompile_material(self.material)
        if errors:
            raise RuntimeError("Material compile failed: " + str(errors))
        return self.material


def assign(state, material, label):
    before = snapshot(state)
    previous = state["current"]
    try:
        state["landscape"].set_editor_property("landscape_material", material)
        if any(c.get_material(0) != material for c in state["components"]):
            raise RuntimeError("Component assignment mismatch")
        if snapshot(state) != before:
            raise RuntimeError("Frozen scene changed during material assignment")
    except Exception:
        state["landscape"].set_editor_property("landscape_material", previous)
        raise
    state["current"] = material
    result = {
        "variant": label,
        "material": material.get_path_name(),
        "component_assignment_count": len(state["components"]),
        "geometry_snapshot_equal": True,
        "map_saved": False,
        "native_instance_audit": "PENDING",
        "owner_visual_acceptance": "PENDING",
        "performance": "NOT_MEASURED",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (OUT / (label + ".json")).write_text(json.dumps(result, indent=2), encoding="utf-8")
    unreal.log("YACS_MATERIAL_REPAIR " + json.dumps(result))
    return result


def checker(state, mode="native"):
    label = "checker_" + mode
    if label not in state["materials"]:
        graph = RepairGraph("M_ProjectionChecker_" + mode)
        texture = unreal.load_asset(
            "/Engine/OpenWorldTemplate/LandscapeMaterial/T_GridChecker_A"
        )
        if not texture:
            raise RuntimeError("Installed metric checker missing")
        fn = graph.project(texture, 300)
        if mode != "native":
            graph.link(graph.direction(mode), fn, "World Space Normal")
        graph.output(fn, unreal.MaterialProperty.MP_EMISSIVE_COLOR, "XYZ Texture")
        graph.material.set_editor_property(
            "shading_model", unreal.MaterialShadingModel.MSM_UNLIT
        )
        state["materials"][label] = graph.compile()
    return assign(state, state["materials"][label], label)


def projection_review(state, surface=False):
    if state.get("capture_active"):
        raise RuntimeError("Diagnostic capture already active")
    directory = OUT / (
        ("surface-" if surface else "projection-") + uuid.uuid4().hex[:8]
    )
    directory.mkdir()
    progress = {"index": 0, "task": None, "busy": False, "rows": []}
    modes = (
        ("weights", "neutral", "flat", "candidate")
        if surface
        else ("native", "geometric", "mixed")
    )
    state["capture_active"] = True

    def tick(_delta):
        if progress["busy"]:
            return
        progress["busy"] = True
        try:
            if progress["task"]:
                if time.monotonic() - progress["started"] > 120:
                    raise RuntimeError("Projection screenshot timed out")
                if not progress["task"].is_task_done():
                    return
                path = directory / (modes[progress["index"]] + ".png")
                if not path.is_file():
                    raise RuntimeError("Screenshot completed without output")
                progress["rows"].append(
                    {
                        "mode": modes[progress["index"]],
                        "file": str(path),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
                progress["index"] += 1
                progress["task"] = None
                # Retire generated Landscape instances before compiling another
                # full-area variant. Otherwise long batches retain tens of GB.
                unreal.collect_garbage()
            if progress["index"] == len(modes):
                unreal.unregister_slate_post_tick_callback(progress["handle"])
                state["capture_active"] = False
                (directory / "receipt.json").write_text(
                    json.dumps(progress["rows"], indent=2), encoding="utf-8"
                )
                unreal.log("YACS_PROJECTION_REVIEW_COMPLETE " + str(directory))
                return
            mode = modes[progress["index"]]
            if surface:
                main(mode)
            else:
                checker(state, mode)
            unreal.AutomationLibrary.finish_loading_before_screenshot()
            progress["started"] = time.monotonic()
            progress["task"] = unreal.AutomationLibrary.take_high_res_screenshot(
                res_x=1920,
                res_y=1080,
                filename=str(directory / (mode + ".png")),
                delay=2.0,
                force_game_view=True,
            )
            if not progress["task"] or not progress["task"].is_valid_task():
                raise RuntimeError("Invalid screenshot task")
        except Exception as exc:
            unreal.unregister_slate_post_tick_callback(progress["handle"])
            state["capture_active"] = False
            (directory / "error.json").write_text(
                json.dumps({"error": str(exc)}), encoding="utf-8"
            )
            unreal.log_error("YACS_PROJECTION_REVIEW_FAILED " + str(exc))
        finally:
            progress["busy"] = False

    progress["handle"] = unreal.register_slate_post_tick_callback(tick)
    return str(directory)


def main(action="checker"):
    if action in ("rebuild_candidate", "surface_review", "bounded_residency"):
        raise RuntimeError(
            "Disabled after the 2026-10-06 D3D12 out-of-video-memory crash. "
            "Prepare and validate one material in an isolated editor before "
            "applying it to the full Landscape; do not repeat live batch rebuilds "
            "or force texture residency in the owner editor."
        )
    state = context()
    if action == "rebuild_candidate":
        module = runpy.run_path(str(ROOT / "scripts/ue/build_sa_calobra_repaired_surface.py"))
        state["materials"]["repair_candidate"] = module["build"](state, "candidate")
        result = assign(state, state["materials"]["repair_candidate"], "repair_candidate")
        unreal.collect_garbage()
        return result
    if action == "close_view":
        point = state["before"]["traces"][4][0]
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        editor.set_level_viewport_camera_info(
            unreal.Vector(point[0], point[1], point[2] + 170),
            unreal.Rotator(pitch=-15, yaw=45, roll=0),
        )
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        state["detail_capture"] = unreal.AutomationLibrary.take_high_res_screenshot(
            res_x=1920,
            res_y=1080,
            filename=str(OUT / "close-view.png"),
            delay=5.0,
            force_game_view=True,
        )
        return
    if action == "bounded_residency":
        # The world-position projections were receiving only 256px resident
        # mips on this Landscape. Bound this small shared library to 2K with
        # its full mip chain resident; never raise the global streaming pool.
        selected = []
        for texture in LIB.get_used_textures(state["current"]):
            if texture.get_path_name().startswith(
                "/Game/Generated/YACS/MaterialRepair/Textures/"
            ):
                texture.set_editor_property("max_texture_size", 2048)
                texture.set_editor_property("never_stream", True)
                selected.append(texture)
        if not selected:
            raise RuntimeError("No repair textures selected")
        unreal.AutomationLibrary.finish_loading_before_screenshot()
        state["residency_capture"] = unreal.AutomationLibrary.take_high_res_screenshot(
            res_x=1920,
            res_y=1080,
            filename=str(OUT / "bounded-residency.png"),
            delay=8.0,
            force_game_view=True,
        )
        unreal.log("YACS_BOUNDED_RESIDENCY_TEXTURES " + str(len(selected)))
        return len(selected)
    if action == "save_candidate":
        if state.get("capture_active") or state["current"] != state["materials"].get(
            "repair_candidate"
        ):
            raise RuntimeError("Finish candidate review before scoped asset save")
        assets = [state["current"], state["repair_sources"]["weights"]]
        for role, channels in state["repair_sources"].items():
            if role != "weights":
                assets.extend(channels.values())
        rows = []
        for asset in assets:
            if not asset.get_path_name().startswith(
                (
                    "/Game/Generated/YACS/MaterialRepair/",
                    "/Game/Generated/YACS/VisualFill/",
                )
            ):
                raise RuntimeError("Asset save escaped the repair namespace")
            if not unreal.EditorAssetLibrary.save_loaded_asset(
                asset, only_if_is_dirty=False
            ):
                raise RuntimeError("Scoped asset save failed")
            file = (
                ROOT
                / "Content"
                / (
                    asset.get_path_name().split(".")[0].removeprefix("/Game/")
                    + ".uasset"
                )
            )
            rows.append(
                {
                    "path": file.relative_to(ROOT).as_posix(),
                    "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                    "size_bytes": file.stat().st_size,
                }
            )
        if snapshot(state) != state["before"]:
            raise RuntimeError("Frozen scene changed during scoped save")
        receipt = {
            "status": "ASSETS_SAVED_RELOAD_PENDING",
            "material": state["current"].get_path_name(),
            "assets": rows,
            "saved_map_sha256": state["before"]["saved_map_sha256"],
            "geometry_unchanged": True,
            "map_saved": False,
            "owner_visual_acceptance": "PENDING",
            "performance": "NOT_MEASURED",
            "sources": state["repair_source_receipt"],
        }
        path = ROOT / "worldgen/materials/sa_calobra_repair_asset.json"
        path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        unreal.log("YACS_REPAIR_ASSETS_SAVED " + str(path))
        return receipt
    if action == "checker":
        return checker(state)
    if action in ("checker_geometric", "checker_mixed"):
        return checker(state, action.removeprefix("checker_"))
    if action == "projection_review":
        return projection_review(state)
    if action == "surface_review":
        return projection_review(state, surface=True)
    if action in ("candidate", "weights", "flat", "neutral") or action.startswith(
        "weight_"
    ):
        return runpy.run_path(
            str(ROOT / "scripts/ue/build_sa_calobra_repaired_surface.py")
        )["main"](state, action)
    if action == "restore":
        return assign(state, state["original"], "restored")
    raise ValueError("Unknown repair action: " + action)


if __name__ == "__main__":
    main()
