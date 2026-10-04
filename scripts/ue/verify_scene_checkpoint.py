"""Read the saved checkpoint in a fresh editor and verify persistent content."""

import builtins
import ast
import json
import math
import sys
import time
import traceback
from pathlib import Path
import unreal

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.workspace import load_workspace, digest  # noqa: E402 - UE bootstrap
from scripts.geometry.bob_vertical_support import build_vertical_support  # noqa: E402

config = load_workspace()
out = Path(config["checkpoints"]) / config["checkpoint"]
expected = json.loads((out / "recovery-progress.json").read_text())
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name().split(".")[0] != config["map"]:
    raise RuntimeError("Wrong map in reopen verification")
landscapes = list(
    unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
)
if len(landscapes) != 1:
    raise RuntimeError("Landscape missing after reopen")
landscape = landscapes[0]
if not unreal.CyclingLandscapeEarthworksLibrary.finish_road_earthworks_batch(landscape):
    raise RuntimeError("Persisted CUT layer could not merge")
state = {"after": time.monotonic() + 20}
builtins._yacs_reopen_verify = state


def verify_arch_serialization(meshes, mismatches):
    """Prove unused-vertex removal against every original oriented triangle."""
    root = (
        Path(config["data"])
        / "world-data/sa-calobra-working-v1/frozen-road-c5573b3-2026-10-04"
    )
    recipe = json.loads((root / "source-recipe.json").read_text())
    for item in recipe["inputs"]:
        if digest(root / item["path"]) != item["sha256"]:
            raise RuntimeError("Frozen input hash differs")
    ns = {"math": math, "build_vertical_support": build_vertical_support}
    for name, sha, names in (
        (
            "network_pavement.py",
            "9f43ab7a3f2ca3e23e6eb6321bf42a6a84616b8faa9d84dbff9b04d2c7bbb451",
            {"pavement_slab", "shoulder_sections"},
        ),
        (
            "nudo_structure.py",
            "a8031e7725d57bdab3de717064dc18fca0e509142d88bf8d5cf624d336768ed9",
            {"arch_height", "build_nudo_support", "bridge_parapets"},
        ),
    ):
        path = root / "support-consumers" / name
        if digest(path) != sha:
            raise RuntimeError("Support consumer hash differs")
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        body = [
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names
        ]
        exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), ns)
    network = json.loads(
        (root / "Network/network.json").read_text(encoding="utf-8-sig")
    )
    native = json.loads(
        (root / "network-native-proof.json").read_text(encoding="utf-8-sig")
    )
    ids = {w["id"] for w in native["windows"]}
    windows = [
        w
        for w in network["approved"]
        + network["owner_reviewed"]
        + network["nudo"]["windows"]
        if w["id"] in ids
    ]
    index = 0
    candidates = {}
    for window in windows:
        if window.get("nudo_structure"):
            sections = ns["shoulder_sections"](window["sections"])
            pv, _ = ns["bridge_parapets"](
                sections, window["station_start_m"], network["nudo"]["structure"]
            )
            index += bool(pv)
            candidates[f"YACS_PERSIST_SUPPORT_{index:03}"] = (window, sections)
        index += 1
    proofs = []
    for mismatch in mismatches:
        label = mismatch["expected"]["label"]
        if label not in candidates:
            raise RuntimeError("Unexplained mesh inventory difference: " + label)
        window, sections = candidates[label]
        ground = [[trace_height(row[0]), trace_height(row[-1])] for row in sections]
        vertices, triangles, _ = ns["build_nudo_support"](
            sections, ground, window["station_start_m"], network["nudo"]["structure"]
        )
        used = {i for face in triangles for i in face}
        if (len(vertices), len(triangles)) != (
            mismatch["expected"]["vertices"],
            mismatch["expected"]["triangles"],
        ):
            raise RuntimeError("Arch source reconstruction differs")
        if (len(used), len(triangles)) != (
            mismatch["actual"]["vertices"],
            mismatch["actual"]["triangles"],
        ):
            raise RuntimeError("Difference is not precisely unused vertices")
        mesh = meshes[label].get_dynamic_mesh_component().get_dynamic_mesh()
        worst = 0.0
        for tid, face in enumerate(triangles):
            valid, a, b, c = mesh.get_triangle_positions(tid)
            if not valid:
                raise RuntimeError("Missing archived triangle")
            for actual, vid in zip((a, b, c), face, strict=True):
                worst = max(
                    worst,
                    *(
                        abs(value - wanted * 100)
                        for value, wanted in zip(
                            (actual.x, actual.y, actual.z), vertices[vid], strict=True
                        )
                    ),
                )
        if worst > 0.0001:
            raise RuntimeError("Arch triangle coordinates changed: " + str(worst))
        proofs.append(
            {
                "label": label,
                "discarded_unused_vertices": len(vertices) - len(used),
                "triangles_compared": len(triangles),
                "max_coordinate_delta_cm": worst,
            }
        )
    return proofs


def trace_height(point):
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
    heights = [
        float(p.z) / 100
        for p in (() if hit is None else hit.to_tuple())
        if all(hasattr(p, k) for k in ("x", "y", "z"))
        and abs(p.x - x * 100) < 0.1
        and abs(p.y - y * 100) < 0.1
        and abs(p.z - z * 100) < 9999
    ]
    if not heights:
        raise RuntimeError("Landscape trace missed")
    return heights[0]


def tick(delta):
    if time.monotonic() < state["after"]:
        return
    try:
        actors = unreal.get_editor_subsystem(
            unreal.EditorActorSubsystem
        ).get_all_level_actors()
        meshes = {
            a.get_actor_label(): a
            for a in actors
            if a.get_actor_label().startswith(
                ("YACS_PERSIST_ROAD", "YACS_PERSIST_SUPPORT_")
            )
        }
        if len(meshes) != 187:
            raise RuntimeError("Saved road/support actor count differs")
        mismatches = []
        actual_meshes = []
        for item in expected["mesh_reports"]:
            actor = meshes[item["label"]]
            comp = actor.get_dynamic_mesh_component()
            mesh = comp.get_dynamic_mesh()
            actual_meshes.append(
                {
                    "label": item["label"],
                    "vertices": mesh.get_vertex_count(),
                    "triangles": mesh.get_triangle_count(),
                }
            )
            if (mesh.get_vertex_count(), mesh.get_triangle_count()) != (
                item["vertices"],
                item["triangles"],
            ):
                mismatches.append({"expected": item, "actual": actual_meshes[-1]})
            if comp.get_material(0).get_path_name() != item["material"]:
                raise RuntimeError("Saved material differs")
        patches = [
            a for a in actors if a.get_actor_label().startswith("YACS_PERSIST_CUT")
        ]
        if len(patches) != 185:
            raise RuntimeError("Saved CUT patch actor count differs")
        worst = 0
        for sample in expected["ground_samples"]:
            x, y, z = sample["point"]
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
                raise RuntimeError("Saved Landscape trace missed")
            worst = max(worst, abs(heights[0] - sample["ground_z_m"]))
        if worst > 0.001:
            raise RuntimeError("Saved ground differs after reload: " + str(worst))
        map_file = (
            Path(config["project"])
            / "Content"
            / (config["map"].removeprefix("/Game/") + ".umap")
        )
        if digest(map_file) != expected["map_sha256"]:
            raise RuntimeError("Map file differs from checkpoint")
        arch_proofs = (
            verify_arch_serialization(meshes, mismatches) if mismatches else []
        )
        result = {
            "status": "PASS",
            "serialization_inventory_changes": mismatches,
            "arch_triangle_proofs": arch_proofs,
            "actual_meshes": actual_meshes,
            "map_package": config["map"],
            "map_sha256": expected["map_sha256"],
            "pavement_actors": 1,
            "support_actors": 186,
            "cut_patch_actors": 185,
            "ground_samples": len(expected["ground_samples"]),
            "max_ground_delta_m": worst,
            "road_replayed": False,
            "full_layer_remerge_verified": True,
            "performance_admission": False,
            "engine_version": unreal.SystemLibrary.get_engine_version(),
        }
    except Exception:
        result = {
            "status": "FAIL",
            "map_package": config["map"],
            "error": traceback.format_exc(),
        }
        unreal.log_error(result["error"])
    (out / "reopen-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    unreal.unregister_slate_post_tick_callback(state["handle"])
    unreal.SystemLibrary.quit_editor()


state["handle"] = unreal.register_slate_post_tick_callback(tick)
