"""Fixed, no-save mask review on an existing Landscape; never authors geometry."""

from __future__ import annotations
import hashlib
import json
import os
import time
import traceback
from pathlib import Path
import unreal

ROOT = Path(os.environ["YACS_MASK_REVIEW_ROOT"])
MANIFEST = json.loads((ROOT / "review-manifest.json").read_text(encoding="utf-8"))
SHA = os.environ["YACS_MASK_REVIEW_SHA"]
KEEP_OPEN = os.environ.get("YACS_MASK_REVIEW_KEEP_OPEN") == "1"
state = {"index": 0, "task": None, "handle": None, "captures": [], "busy": False}
kept = []


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def record(status, error=""):
    proof = {
        "schema_version": 1,
        "status": status,
        "error": error,
        "script_commit": SHA,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "review_manifest_sha256": digest(ROOT / "review-manifest.json"),
        "geometry_modified": False,
        "heightmap_imported": False,
        "earthworks_generated": False,
        "map_saved": False,
        "assets_saved": False,
        "frozen_map_sha256_before": state.get("map_hash"),
        "frozen_map_sha256_after": digest(state["map_file"])
        if "map_file" in state
        else None,
        "registration_samples": state.get("registration", []),
        "landscape_before": state.get("before"),
        "landscape_after": snapshot() if "landscape" in state else None,
        "captures": state["captures"],
        "review_environment": state.get("review_environment", "unchanged"),
        "legend": MANIFEST["legend"],
        "blocked_layers": MANIFEST["blocked_layers"],
        "whole_2a": "INCOMPLETE",
        "human_visual_acceptance": "PENDING",
        "compiled_project_commit": os.environ.get("YACS_MASK_COMPILED_PROJECT_SHA"),
        "implementation": "Python-only consumer; existing compiled Editor modules reused; no code compilation claimed",
    }
    (ROOT / "unreal-review-proof.json").write_text(
        json.dumps(proof, indent=2) + "\n", encoding="utf-8"
    )


def snapshot():
    landscape = state["landscape"]
    return {
        "transform": str(landscape.get_actor_transform()),
        "components": len(landscape.get_components_by_class(unreal.LandscapeComponent)),
        "layers": [
            str(layer.get_name_bp()) for layer in landscape.get_edit_layers_bp()
        ],
        "actors": sorted(
            (a.get_path_name(), str(a.get_actor_transform()))
            for a in state["original_actors"]
        ),
    }


def measure_registration():
    rows = []
    for sample in MANIFEST["registration_samples"]:
        x, y = sample["world_cm"]
        z = sample["native_elevation_m"] * 100
        hit = unreal.SystemLibrary.line_trace_single(
            state["world"],
            unreal.Vector(x, y, 150000),
            unreal.Vector(x, y, 0),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        values = () if hit is None else hit.to_tuple()
        candidates = [
            float(v.z)
            for v in values
            if all(hasattr(v, k) for k in ("x", "y", "z"))
            and abs(float(v.x) - x) < 0.1
            and abs(float(v.y) - y) < 0.1
            and float(v.z) > 10000
        ]
        if not candidates:
            raise RuntimeError("Frozen Landscape registration trace missed")
        actual = candidates[0]
        rows.append(
            {
                **sample,
                "measured_z_m": actual / 100,
                "native_residual_m": actual / 100 - z / 100,
            }
        )
    return rows


def texture_material(filename, index):
    package = "/Game/Generated/YACS/MaskReview"
    name = "T_MaskReview_" + str(index)
    if unreal.EditorAssetLibrary.does_asset_exist(package + "/" + name):
        raise RuntimeError("Existing review asset collision; no overwrite permitted")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(ROOT / filename))
    task.set_editor_property("destination_path", package)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", False)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = task.get_editor_property("imported_object_paths")
    if len(paths) != 1:
        raise RuntimeError("Texture import did not return one object")
    texture = unreal.load_asset(paths[0])
    texture.set_editor_property("srgb", True)
    texture.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
    texture.set_editor_property("address_x", unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property("address_y", unreal.TextureAddress.TA_CLAMP)
    texture.set_editor_property(
        "mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS
    )
    texture.set_editor_property(
        "compression_settings",
        unreal.TextureCompressionSettings.TC_VECTOR_DISPLACEMENTMAP,
    )
    texture.set_editor_property("never_stream", True)
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        "M_MaskReview_" + str(index),
        package,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)

    def expression(cls):
        return unreal.MaterialEditingLibrary.create_material_expression(mat, cls)

    def link(a, b, pin=""):
        if not unreal.MaterialEditingLibrary.connect_material_expressions(
            a, "", b, pin
        ):
            raise RuntimeError("Material graph connection failed: " + pin)

    position = expression(unreal.MaterialExpressionWorldPosition)
    xy = expression(unreal.MaterialExpressionComponentMask)
    for key, value in [("r", True), ("g", True), ("b", False), ("a", False)]:
        xy.set_editor_property(key, value)
    link(position, xy)
    offset = expression(unreal.MaterialExpressionConstant2Vector)
    offset.set_editor_property("r", 25.0)
    offset.set_editor_property("g", 25.0)
    add = expression(unreal.MaterialExpressionAdd)
    link(xy, add, "A")
    link(offset, add, "B")
    divide = expression(unreal.MaterialExpressionDivide)
    divide.set_editor_property("const_b", MANIFEST["world_mapping"]["texture_span_cm"])
    link(add, divide, "A")
    sample = expression(unreal.MaterialExpressionTextureSample)
    sample.set_editor_property("texture", texture)
    link(divide, sample)
    if not unreal.MaterialEditingLibrary.connect_material_property(
        sample, "RGB", unreal.MaterialProperty.MP_EMISSIVE_COLOR
    ):
        raise RuntimeError("Emissive diagnostic connection failed")
    errors = unreal.MaterialEditingLibrary.recompile_material(mat)
    if errors:
        raise RuntimeError("Material compile errors: " + str(errors))
    kept.extend([texture, mat, task])
    return mat


def schedule():
    state["busy"] = True
    view = state["views"][state["index"]]
    state["landscape"].set_editor_property(
        "landscape_material", state["materials"][view["material"]]
    )
    location = unreal.Vector(*view["location"])
    target = unreal.Vector(*view["target"])
    state["camera"].set_actor_location(location, False, False)
    state["camera"].set_actor_rotation(
        unreal.MathLibrary.find_look_at_rotation(location, target), False
    )
    viewport = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    viewport.set_level_viewport_camera_info(
        location, unreal.MathLibrary.find_look_at_rotation(location, target)
    )
    task = unreal.AutomationLibrary.take_high_res_screenshot(
        res_x=1920,
        res_y=1080,
        filename=str(ROOT / (view["name"] + ".png")),
        camera=state["camera"],
        delay=5.0,
        force_game_view=True,
    )
    if not task or not task.is_valid_task():
        raise RuntimeError("Invalid screenshot task")
    state["task"] = task
    state["started"] = time.monotonic()
    state["busy"] = False


def tick(delta):
    if state["busy"] or state["task"] is None:
        return
    try:
        if time.monotonic() - state["started"] > 120:
            raise RuntimeError("Screenshot timed out after 120 seconds")
        view = state["views"][state["index"]]
        path = ROOT / (view["name"] + ".png")
        if (
            state["task"].is_task_done()
            and path.is_file()
            and path.stat().st_size > 100000
        ):
            state["busy"] = True
            state["captures"].append(
                {
                    "view": view,
                    "path": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
            )
            state["index"] += 1
            if state["index"] < len(state["views"]):
                schedule()
            else:
                if snapshot() != state["before"]:
                    raise RuntimeError("Frozen Landscape snapshot changed")
                if digest(state["map_file"]) != state["map_hash"]:
                    raise RuntimeError("Frozen map bytes changed")
                state["landscape"].set_editor_property(
                    "landscape_material", state["materials"][1]
                )
                after_samples = measure_registration()
                if after_samples != state["registration"]:
                    raise RuntimeError("Frozen Landscape collision samples changed")
                state["performance_settings"].set_editor_property(
                    "bThrottleCPUWhenNotForeground",
                    state["original_background_throttle"],
                )
                record("PASS_DIAGNOSTIC_CONSUMER_ONLY")
                unreal.unregister_slate_post_tick_callback(state["handle"])
                unreal.log(
                    "[MaskReview] PASS; frozen geometry preserved; human review pending"
                )
                if not KEEP_OPEN:
                    unreal.SystemLibrary.quit_editor()
    except Exception:
        state["landscape"].set_editor_property(
            "landscape_material", state["original_material"]
        )
        record("FAIL", traceback.format_exc())
        unreal.unregister_slate_post_tick_callback(state["handle"])
        unreal.log_error(traceback.format_exc())


def main():
    if len(SHA) != 40 or any(c not in "0123456789abcdef" for c in SHA):
        raise RuntimeError("Exact script commit required")
    if MANIFEST["geometry_mutation"] is not False:
        raise RuntimeError("Geometry authoring forbidden")
    for row in MANIFEST["outputs"]:
        p = ROOT / row["path"]
        if (
            p.parent != ROOT
            or p.stat().st_size != row["size_bytes"]
            or digest(p) != row["sha256"]
        ):
            raise RuntimeError("Review output identity mismatch")
    if (ROOT / "unreal-review-proof.json").exists():
        raise RuntimeError("Preserve existing Unreal proof")
    performance = unreal.get_default_object(
        unreal.load_class(None, "/Script/UnrealEd.EditorPerformanceSettings")
    )
    state["performance_settings"] = performance
    state["original_background_throttle"] = performance.get_editor_property(
        "bThrottleCPUWhenNotForeground"
    )
    performance.set_editor_property("bThrottleCPUWhenNotForeground", False)
    # Volatile settings only, never SaveConfig. Prevent review assets/material
    # from being autosaved into the frozen project during this review session.
    loading = unreal.get_default_object(
        unreal.load_class(None, "/Script/UnrealEd.EditorLoadingSavingSettings")
    )
    loading.set_editor_property("bAutoSaveEnable", False)
    expected = MANIFEST["expected_landscape"]
    package = expected["map"]
    state["map_file"] = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ) / ("Content/" + package.removeprefix("/Game/") + ".umap")
    state["map_hash"] = digest(state["map_file"])
    world = unreal.EditorLoadingAndSavingUtils.load_map(package)
    state["world"] = world
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("Expected one existing Landscape")
    landscape = landscapes[0]
    state["landscape"] = landscape
    rotation = landscape.get_actor_rotation()
    if any(abs(v) > 0.000001 for v in (rotation.pitch, rotation.yaw, rotation.roll)):
        raise RuntimeError(
            "Rotated Landscape cannot use the admitted world-XY mask mapping"
        )
    scale = landscape.get_actor_scale3d()
    location = landscape.get_actor_location()
    if any(
        abs(v - e) > 0.001
        for v, e in [
            (scale.x, 50),
            (scale.y, 50),
            (scale.z, expected["scale_z"]),
            (location.x, 0),
            (location.y, 0),
            (location.z, expected["location_z_cm"]),
        ]
    ):
        raise RuntimeError(
            "Frozen Landscape transform differs from mask registration contract"
        )
    state["original_actors"] = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
    )
    state["before"] = snapshot()
    if state["before"]["components"] != 1024 or state["before"]["layers"] != [
        "Base_DTM",
        "Road_Earthworks",
    ]:
        raise RuntimeError("Frozen Landscape topology/layer ownership differs")
    state["original_material"] = landscape.get_editor_property("landscape_material")
    state["registration"] = measure_registration()
    if max(abs(row["native_residual_m"]) for row in state["registration"]) > 0.05:
        raise RuntimeError(
            "Landscape/native height disagreement exceeds 0.05 m; review required, no geometry repair"
        )
    state["materials"] = [
        texture_material(name, i)
        for i, name in enumerate(
            ["orthophoto.png", "review-overlay.png", "historical-context.png"]
        )
    ]
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if MANIFEST.get("review_atmosphere") is True:
        sky = actors.spawn_actor_from_class(
            unreal.SkyAtmosphere, unreal.Vector(), unreal.Rotator(), transient=True
        )
        sun = actors.spawn_actor_from_class(
            unreal.DirectionalLight,
            unreal.Vector(0, 0, 120000),
            unreal.Rotator(-35, -35, 0),
            transient=True,
        )
        if sky is None or sun is None:
            raise RuntimeError("Native review atmosphere/sun spawn failed")
        sky.set_actor_label("YACS_MASK_REVIEW_SKY_NO_SAVE")
        sun.set_actor_label("YACS_MASK_REVIEW_SUN_NO_SAVE")
        light = sun.get_component_by_class(unreal.DirectionalLightComponent)
        light.set_atmosphere_sun_light(True)
        light.set_atmosphere_sun_light_index(0)
        light.set_intensity(10.0)
        kept.extend([sky, sun])
        state["review_environment"] = {
            "type": "native SkyAtmosphere plus DirectionalLight; session only",
            "sun_rotation_deg": [-35, -35, 0],
            "sun_intensity": 10.0,
            "atmosphere_sun_index": 0,
            "map_saved": False,
        }
    camera = actors.spawn_actor_from_class(
        unreal.CameraActor, unreal.Vector(), unreal.Rotator(), transient=True
    )
    state["camera"] = camera
    camera.set_actor_label("YACS_MCP_MASK_REVIEW_NO_SAVE")
    camera.get_component_by_class(unreal.CameraComponent).set_editor_property(
        "field_of_view", 74.0
    )
    peak = MANIFEST["registration_samples"][-1]
    x, y = peak["world_cm"]
    z = peak["native_elevation_m"] * 100
    top = [100800, 100800, 356062]
    target = [100800, 100800, 68348]
    state["views"] = [
        {"name": name, "material": index, "location": top, "target": target}
        for name, index in [
            ("mask-ortho-plan", 0),
            ("mask-review-plan", 1),
            ("mask-history-plan", 2),
        ]
    ]
    state["views"].append(
        {
            "name": "mask-relief-review",
            "material": 1,
            "location": [x - 12000, y + 16000, z + 24000],
            "target": [x, y, z],
        }
    )
    if MANIFEST.get("review_atmosphere") is True:
        state["views"].append(
            {
                "name": "mask-landscape-sky",
                "material": 1,
                "location": [100800, 20000, 125000],
                "target": [100800, 155000, 75000],
            }
        )
    # The overlay uses the existing surface. No heights, road actors, collision or edit layers are authored.
    schedule()
    state["handle"] = unreal.register_slate_post_tick_callback(tick)


try:
    main()
except Exception:
    record("FAIL", traceback.format_exc())
    unreal.log_error(traceback.format_exc())
    raise
