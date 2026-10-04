"""Restore the accepted fixed scene into a durable checkpoint, one mesh copy only.

Run inside the configured UE editor on the baseline map. No new road design or
CUT targets are generated. Existing checkpoint destinations are never replaced.
"""

from __future__ import annotations
import ast
import builtins
import json
import math
import sys
import time
import traceback
from pathlib import Path
import unreal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.manage_local_workspace import digest, load_workspace  # noqa: E402 - UE does not add the repo root
from scripts.geometry.bob_vertical_support import (  # noqa: E402
    build_vertical_support,
    support_sections,
)

CONFIG = load_workspace()
ROOT = (
    Path(CONFIG["data"])
    / "world-data/sa-calobra-working-v1/frozen-road-c5573b3-2026-10-04"
)
OUT = Path(CONFIG["checkpoints"]) / CONFIG["checkpoint"]
SHA = "c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6"
PACKAGE = CONFIG["map"]
ASSETS = "/Game/Worlds/SaCalobra/CheckpointMaterials"
CUT_ASSETS = "/Game/Worlds/SaCalobra/CheckpointEarthworks"


def functions(path, names, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    selected = [
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names
    ]
    if {n.name for n in selected} != set(names):
        raise ValueError("Incomplete consumer functions")
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"),
        namespace,
    )


def begin():
    if Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve() != Path(CONFIG["project"]):
        raise RuntimeError("Refuse checkpoint in another project")
    if unreal.EditorAssetLibrary.does_asset_exist(PACKAGE):
        raise RuntimeError("Checkpoint already exists")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if (
        world.get_path_name().split(".")[0]
        != "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline"
    ):
        raise RuntimeError("Unexpected map")
    recipe = json.loads((ROOT / "source-recipe.json").read_text())
    if recipe["accepted_sha"] != SHA:
        raise RuntimeError("Source revision mismatch")
    for item in recipe["inputs"]:
        path = ROOT / item["path"]
        if path.stat().st_size != item["size_bytes"] or digest(path) != item["sha256"]:
            raise RuntimeError("Frozen input differs: " + str(path))
    network = json.loads(
        (ROOT / "Network/network.json").read_text(encoding="utf-8-sig")
    )
    native = json.loads(
        (ROOT / "network-native-proof.json").read_text(encoding="utf-8-sig")
    )
    profile = json.loads(
        (ROOT / "ma2141-profile-candidate.json").read_text(encoding="utf-8-sig")
    )
    ids = {w["id"] for w in native["windows"]}
    windows = [
        w
        for w in network["approved"]
        + network["owner_reviewed"]
        + network["nudo"]["windows"]
        if w["id"] in ids
    ]
    if len(windows) != 184:
        raise RuntimeError("Unexpected window count")
    rows = [
        [
            [xy[0], xy[1], z + 0.04]
            for xy, z in zip(row["xy_local_m"], row["candidate_ground_m"], strict=True)
        ]
        for row in profile["stations"]
    ]
    road_windows = windows + [{"id": "accepted-hairpin", "sections": rows}]
    ns = {"math": math, "build_vertical_support": build_vertical_support}
    expected_consumers = {
        "network_pavement.py": "9f43ab7a3f2ca3e23e6eb6321bf42a6a84616b8faa9d84dbff9b04d2c7bbb451",
        "nudo_structure.py": "a8031e7725d57bdab3de717064dc18fca0e509142d88bf8d5cf624d336768ed9",
    }
    for name, expected_hash in expected_consumers.items():
        if digest(ROOT / "support-consumers" / name) != expected_hash:
            raise RuntimeError("Frozen support consumer hash mismatch: " + name)
    functions(
        ROOT / "support-consumers/network_pavement.py",
        {"pavement_slab", "shoulder_sections"},
        ns,
    )
    functions(
        ROOT / "support-consumers/nudo_structure.py",
        {"arch_height", "build_nudo_support", "bridge_parapets"},
        ns,
    )
    paths = [ROOT / "Network" / w["cut_manifest"] for w in windows] + [
        ROOT / "ma2141-cut-patch.json"
    ]
    for path in paths:
        patch = json.loads(path.read_text(encoding="utf-8-sig"))
        if (
            patch["operation"] != "CUT_ONLY"
            or patch["base_dtm_modified"]
            or patch["fill_authoring_permitted"]
        ):
            raise RuntimeError("Invalid fixed CUT contract")
        if digest(path.parent / patch["patch_file"]) != patch["patch_sha256"]:
            raise RuntimeError("CUT hash mismatch")
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("Expected one Landscape")
    landscape = landscapes[0]
    state = {
        "stage": "CUT",
        "index": 0,
        "mesh_reports": [],
        "support_reports": [],
        "ground_samples": [],
        "objects": [],
        "materials": {},
    }
    builtins._yacs_checkpoint = state

    def write(error=None):
        report = {
            k: v
            for k, v in state.items()
            if k
            not in (
                "objects",
                "materials",
                "handle",
                "road_actor",
                "road_mesh",
                "wait_until",
            )
        }
        report.update(
            error=error,
            map_package=PACKAGE,
            source_sha=SHA,
            engine_version=unreal.SystemLibrary.get_engine_version(),
            performance_admission=False,
        )
        (OUT / "recovery-progress.json").write_text(json.dumps(report, indent=2) + "\n")

    def material(color):
        key = tuple(color)
        if key not in state["materials"]:
            mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                "MI_Accepted_" + str(len(state["materials"])),
                ASSETS,
                unreal.MaterialInstanceConstant,
                unreal.MaterialInstanceConstantFactoryNew(),
            )
            if mat is None:
                raise RuntimeError("Material asset collision")
            unreal.MaterialEditingLibrary.set_material_instance_parent(
                mat, unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
            )
            value = unreal.LinearColor(*color, 1)
            unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
                mat, "Color", value
            )
            actual = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(
                mat, "Color"
            )
            if (
                max(abs(a - b) for a, b in zip(color, (actual.r, actual.g, actual.b)))
                > 1e-6
            ):
                raise RuntimeError("Material readback differs")
            state["materials"][key] = mat
        return state["materials"][key]

    def append(mesh, vertices, triangles):
        buffers = unreal.GeometryScriptSimpleMeshBuffers()
        buffers.set_editor_property(
            "vertices", [unreal.Vector(*(v * 100 for v in point)) for point in vertices]
        )
        buffers.set_editor_property(
            "triangles", [unreal.IntVector(*t) for t in triangles]
        )
        mesh.append_buffers_to_mesh(
            buffers, material_id=0, defer_change_notifications=True
        )

    def new_mesh(label, color):
        actor = actors.spawn_actor_from_class(
            unreal.DynamicMeshActor, unreal.Vector(), unreal.Rotator(), transient=False
        )
        actor.set_actor_label(label)
        comp = actor.get_dynamic_mesh_component()
        comp.set_material(0, material(color))
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        state["objects"].append(actor)
        return actor, comp.get_dynamic_mesh()

    def record_mesh(actor, mesh):
        state["mesh_reports"].append(
            {
                "label": actor.get_actor_label(),
                "vertices": mesh.get_vertex_count(),
                "triangles": mesh.get_triangle_count(),
                "material": actor.get_dynamic_mesh_component()
                .get_material(0)
                .get_path_name(),
            }
        )

    def trace(point):
        x, y, z = point
        hit = unreal.SystemLibrary.line_trace_single(
            world,
            unreal.Vector(x * 100, y * 100, (z + 100) * 100),
            unreal.Vector(x * 100, y * 100, (z - 100) * 100),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        values = () if hit is None else hit.to_tuple()
        heights = [
            float(p.z) / 100
            for p in values
            if all(hasattr(p, k) for k in ("x", "y", "z"))
            and abs(p.x - x * 100) < 0.1
            and abs(p.y - y * 100) < 0.1
            and abs(p.z - z * 100) < 9999
        ]
        if not heights:
            raise RuntimeError("Landscape trace missed")
        return heights[0]

    def support(vertices, triangles, color):
        actor, mesh = new_mesh(
            "YACS_PERSIST_SUPPORT_" + str(len(state["objects"]) - 1).zfill(3), color
        )
        append(mesh, vertices, triangles)
        mesh.recompute_normals(
            unreal.GeometryScriptCalculateNormalsOptions(),
            defer_change_notifications=True,
        )
        actor.get_dynamic_mesh_component().notify_mesh_modified()
        record_mesh(actor, mesh)

    def tick(delta):
        if state.get("busy"):
            return
        state["busy"] = True
        try:
            if state["stage"] == "CUT":
                for i, path in enumerate(paths):
                    if not unreal.CyclingLandscapeEarthworksLibrary.apply_road_earthworks_patch(
                        landscape,
                        str(path),
                        True,
                        CUT_ASSETS + "/T_Cut_" + str(i).zfill(3),
                    ):
                        raise RuntimeError(
                            "Persistent fixed CUT replay failed: " + str(path)
                        )
                if not unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(
                    landscape
                ):
                    raise RuntimeError("CUT batch failed")
                state.update(
                    stage="WAIT",
                    wait_until=time.monotonic() + 20,
                    cut_patch_count=len(paths),
                )
                write()
                return
            if state["stage"] == "WAIT":
                if time.monotonic() < state["wait_until"]:
                    return
                actor, mesh = new_mesh("YACS_PERSIST_ROAD", (0.035, 0.035, 0.035))
                state.update(stage="ROAD", road_actor=actor, road_mesh=mesh, index=0)
            if state["stage"] == "ROAD":
                i = state["index"]
                if i < len(road_windows):
                    vertices, triangles = ns["pavement_slab"](
                        road_windows[i]["sections"]
                    )
                    append(state["road_mesh"], vertices, triangles)
                    state["index"] += 1
                    write()
                    return
                mesh = state["road_mesh"]
                if (mesh.get_vertex_count(), mesh.get_triangle_count()) != (
                    856250,
                    1711760,
                ):
                    raise RuntimeError("Road inventory differs from accepted merge")
                options = unreal.GeometryScriptSplitNormalsOptions()
                options.set_editor_property("opening_angle_deg", 60.0)
                mesh.compute_split_normals(
                    options, unreal.GeometryScriptCalculateNormalsOptions()
                )
                state["road_actor"].get_dynamic_mesh_component().notify_mesh_modified()
                record_mesh(state["road_actor"], mesh)
                state.update(stage="SUPPORT", index=0)
            if state["stage"] == "SUPPORT":
                i = state["index"]
                if i < len(windows):
                    item = windows[i]
                    sections = ns["shoulder_sections"](item["sections"])
                    ground = [[trace(row[0]), trace(row[-1])] for row in sections]
                    if item.get("nudo_structure"):
                        vertices, triangles, proof = ns["build_nudo_support"](
                            sections,
                            ground,
                            item["station_start_m"],
                            network["nudo"]["structure"],
                        )
                        pv, pt = ns["bridge_parapets"](
                            sections,
                            item["station_start_m"],
                            network["nudo"]["structure"],
                        )
                        if pv:
                            support(pv, pt, (0.4, 0.37, 0.3))
                    else:
                        vertices, triangles, proof = build_vertical_support(
                            sections, ground
                        )
                    support(vertices, triangles, (0.34, 0.31, 0.25))
                    proof["id"] = item["id"]
                    state["support_reports"].append(proof)
                    state["index"] += 1
                    write()
                    return
                if i == len(windows):
                    sections = support_sections(profile)
                    ground = [[trace(row[0]), trace(row[-1])] for row in sections]
                    vertices, triangles, proof = build_vertical_support(
                        sections, ground
                    )
                    support(vertices, triangles, (0.34, 0.31, 0.25))
                    proof["id"] = "accepted-hairpin"
                    state["support_reports"].append(proof)
                    state.update(stage="VERIFY", index=0)
            if state["stage"] == "VERIFY":
                for item in road_windows:
                    rows = item["sections"]
                    for i in sorted({0, len(rows) // 2, len(rows) - 1}):
                        for j in (0, 12, 24):
                            point = rows[i][j]
                            height = trace(point)
                            if point[2] - height < -0.007:
                                raise RuntimeError("Ground penetrates pavement")
                            state["ground_samples"].append(
                                {"point": point, "ground_z_m": height}
                            )
                old = {w["id"]: w["support"] for w in native["windows"]}
                delta = max(
                    abs(r["max_wall_height_m"] - old[r["id"]]["max_wall_height_m"])
                    for r in state["support_reports"]
                    if r["id"] in old
                )
                state["max_support_wall_height_delta_m"] = delta
                if delta > 0.001:
                    raise RuntimeError("Recovered supports differ from frozen proof")
                if len(state["mesh_reports"]) != 187:
                    raise RuntimeError("Support count differs")
                state["stage"] = "MATERIALS"
                write()
                return
            if state["stage"] == "MATERIALS":
                review = (
                    Path(CONFIG["data"])
                    / "world-data/sa-calobra-working-v1/mask-transition-review-v1a-2026-10-04"
                )
                material_ns = {
                    "unreal": unreal,
                    "ROOT": review,
                    "MANIFEST": json.loads(
                        (review / "review-manifest.json").read_text()
                    ),
                    "kept": [],
                }
                functions(
                    REPO / "scripts/ue/sa_calobra_mask_review.py",
                    {"texture_material"},
                    material_ns,
                )
                masks = [
                    material_ns["texture_material"](name, i)
                    for i, name in enumerate(
                        [
                            "orthophoto.png",
                            "review-overlay.png",
                            "historical-context.png",
                        ]
                    )
                ]
                landscape.set_editor_property("landscape_material", masks[1])
                sky = actors.spawn_actor_from_class(
                    unreal.SkyAtmosphere,
                    unreal.Vector(),
                    unreal.Rotator(),
                    transient=False,
                )
                sky.set_actor_label("YACS_PERSIST_REVIEW_SKY")
                sun = actors.spawn_actor_from_class(
                    unreal.DirectionalLight,
                    unreal.Vector(0, 0, 120000),
                    unreal.Rotator(-35, -35, 0),
                    transient=False,
                )
                sun.set_actor_label("YACS_PERSIST_REVIEW_SUN")
                light = sun.get_component_by_class(unreal.DirectionalLightComponent)
                light.set_atmosphere_sun_light(True)
                light.set_atmosphere_sun_light_index(0)
                light.set_intensity(10.0)
                state.update(stage="SAVE", wait_until=time.monotonic() + 15)
                write()
                return
            if state["stage"] == "SAVE":
                if time.monotonic() < state["wait_until"]:
                    return
                for folder in (ASSETS, CUT_ASSETS, "/Game/Generated/YACS/MaskReview"):
                    if not unreal.EditorAssetLibrary.save_directory(
                        folder, False, True
                    ):
                        raise RuntimeError("Asset save failed: " + folder)
                if not unreal.EditorLoadingAndSavingUtils.save_map(world, PACKAGE):
                    raise RuntimeError("Checkpoint save failed")
                path = (
                    Path(CONFIG["project"])
                    / "Content"
                    / (PACKAGE.removeprefix("/Game/") + ".umap")
                )
                state.update(
                    stage="SAVED_REOPEN_PENDING",
                    map_sha256=digest(path),
                    map_bytes=path.stat().st_size,
                )
                write()
                unreal.unregister_slate_post_tick_callback(state["handle"])
                unreal.SystemLibrary.quit_editor()
        except Exception:
            state["stage"] = "FAILED"
            write(traceback.format_exc())
            unreal.unregister_slate_post_tick_callback(state["handle"])
            unreal.log_error(traceback.format_exc())
            unreal.SystemLibrary.quit_editor()
        finally:
            state["busy"] = False

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    write()


begin()
