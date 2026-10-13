"""PCG365 input audit and native PCGEx authoring, including in-place whole-area updates."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[2]
DOCS = Path("docs/experiments/sa-calobra-spatial-treatment-plan-20261013")
VISIBILITY_SHA = "16c8e872d31cfc38b920b28e1d68ae408d71920c39d2ae98df9db14ac7c4266c"
GRID = (4033, 4033)
AFFINE = [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5]
STAGE = Path("D:/yacs/work/pcg365/remote-rock-preview")
LIVE = Path("D:/yacs/live-host")
TERMINAL = {
    "CONTACT_JOB_COMPLETED_SAMPLED_ONLY",
    "CONTACT_JOB_CANCELLED_ROLLED_BACK",
    "FAILED_NATIVE_GUARD_NO_PLACEMENT",
    "FAILED_ROLLBACK_INCOMPLETE",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked(path, expected):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"Missing/aliased input: {path}")
    require(sha(path) == expected, f"Input SHA256 changed: {path}")
    return path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def raster(path, expected, logical=None):
    checked(path, expected)
    with rasterio.open(path) as source:
        require(
            source.shape == GRID and source.count == 1
            and str(source.crs) == "EPSG:25831"
            and list(source.transform)[:6] == AFFINE,
            f"Source grid/CRS differs: {path}",
        )
        result = source.read(1)
    if logical:
        require(
            hashlib.sha256(np.ascontiguousarray(result).tobytes()).hexdigest() == logical,
            f"Logical raster digest differs: {path}",
        )
    return result


def classify_cells(cliff, scree, reasons, slope, treatment, maximum_slope):
    """Count exact cells, never fill a 4m planning bin or use its display overlay.

    All technical exclusion bits win. Unknown/nonfinite slope is not eligible.
    Source support is only a necessary condition, not native contact proof.
    """
    require(cliff.shape == scree.shape == reasons.shape == slope.shape, "Grid mismatch")
    require(set(np.unique(cliff)) <= {0, 1, 255}, "Unknown cliff selector")
    require(set(np.unique(scree)) <= {0, 1, 255}, "Unknown scree selector")
    require(set(np.unique(treatment)) <= set(range(7)), "Unknown treatment class")
    rows, cols = cliff.shape
    require(treatment.shape == ((rows + 7) // 8, (cols + 7) // 8), "Planning grid mismatch")
    fine_treatment = np.repeat(np.repeat(treatment, 8, axis=0), 8, axis=1)[:rows, :cols]
    excluded = reasons != 0
    unknown = (cliff == 255) | (scree == 255) | ~np.isfinite(slope) | (slope < 0) | (slope > 90)
    require(not np.any((cliff == 1) & (scree == 1)), "Conflicting source selectors")
    eligible = ~excluded & ~unknown
    rock = eligible & (scree == 1) & (fine_treatment == 3)
    within_policy = rock & (slope <= maximum_slope)
    return {
        "source_cells": int(cliff.size),
        "technical_excluded_cells": int(excluded.sum()),
        "unknown_unexcluded_cells": int((unknown & ~excluded).sum()),
        "visible_cliff_source_cells": int((eligible & (cliff == 1) & (fine_treatment == 2)).sum()),
        "visible_scree_source_cells": int(rock.sum()),
        "scree_cells_within_existing_slope_policy": int(within_policy.sum()),
        "scree_cells_rejected_by_existing_slope_policy": int((rock & ~within_policy).sum()),
        "material_first_source_cells": int((eligible & (fine_treatment == 1)).sum()),
        "deferred_simplified_source_cells": int((eligible & (fine_treatment == 0)).sum()),
        "cell_area_m2": 0.25,
        "counts_are_overlapping_diagnostics_not_placement_counts": True,
    }


def pcgex_records(cliff, scree, reasons, slope, treatment, clearance_m, *, kind="scree", stride=1, protected_bits=255):
    """Translate exact source cells to PCG records; native nodes decide placement."""
    classify_cells(cliff, scree, reasons, slope, treatment, 42.0)
    require(clearance_m.shape == slope.shape, "Clearance grid mismatch")
    height, width = slope.shape
    fine = np.repeat(np.repeat(treatment, 8, axis=0), 8, axis=1)[:height, :width]
    require(kind in ("scree", "cliff") and type(stride) is int and 1 <= stride <= 16,
            "Unknown input layer or resolution")
    require(protected_bits == 255 or (kind == "cliff" and protected_bits == 63),
            "Unsupported consumer exclusion contract")
    selected, other, treatment_class = (scree, cliff, 3) if kind == "scree" else (cliff, scree, 2)
    excluded = reasons != 0 if protected_bits == 255 else (((reasons & 63) != 0) | (reasons > 255) | (reasons < 0))
    mask = ((selected == 1) & (other != 255) & ~excluded & (fine == treatment_class)
            & np.isfinite(slope) & (slope >= 0) & (slope <= 90))
    # Resolution adaptation only: native nodes still own slope, fitting and spacing.
    lattice = np.zeros_like(mask)
    lattice[::stride, ::stride] = True
    mask &= lattice
    rows, cols = np.nonzero(mask)
    records = []
    for row, col in zip(rows.tolist(), cols.tolist()):
        clearance = float(clearance_m[row, col]) * 100.0
        require(math.isfinite(clearance) and clearance >= 0, "Invalid source clearance")
        # A half-cell border surrounds the last centre. Bound arbitrary rock tilt
        # with a pivot-centred sphere; no placement/overlap solver lives here.
        edge = min((row + .5) * 50, (col + .5) * 50,
                   (height - row - .5) * 50, (width - col - .5) * 50)
        records.append([row, col, float(slope[row, col]), min(clearance, edge)])
    return records


def cliff_clearance(cliff, scree, reasons, slope, protected_bits):
    """Adapt the existing DTM cliff contract, not the LiDAR vegetation contract."""
    from scripts.assets.prepare_sa_calobra_road_masks import distance_lower_bound
    require(protected_bits == 63, "Authenticated cliff exclusion contract changed")
    require(cliff.shape == scree.shape == reasons.shape == slope.shape, "Grid mismatch")
    unknown = ((cliff == 255) | (scree == 255) | ~np.isfinite(slope)
               | (slope < 0) | (slope > 90))
    excluded = ((reasons & protected_bits) != 0) | unknown
    return distance_lower_bound(excluded, 0.5)


def rock_radius(assets):
    """Input bounds enclosing every supplied mesh under any rotation at scale 1."""
    require(bool(assets), "No rock assets")
    radii = []
    for asset in assets:
        bounds = asset["bounds_cm"]
        origin, extent = bounds["origin"], bounds["extent"]
        require(len(origin) == len(extent) == 3 and
                all(math.isfinite(v) for v in [*origin, *extent]) and
                all(v > 0 for v in extent), "Invalid mesh bounds")
        radii.append(math.sqrt(sum((abs(o) + e) ** 2 for o, e in zip(origin, extent))))
    return max(radii)


def audit(root, stage, prepare_pcgex=False, whole_area=False):
    """Reuse the existing source and regional validator; all reads, no UE."""
    sys.path.insert(0, str(root))
    regional = importlib.import_module("scripts.assets.prepare_pcg365_regional_manifest")
    contact = importlib.import_module("scripts.live_host.recipes.rock_contact_scatter")
    policy_module = importlib.import_module("scripts.assets.pcg_rock_contact_policy")
    require(Path(regional.__file__).resolve().is_relative_to(root), "Wrong validator checkout")
    require(Path(contact.__file__).resolve().is_relative_to(root), "Wrong recipe checkout")
    manifest, screen = regional.build(stage, root)
    require(
        regional.canonical(manifest) == (stage / "regional-manifest.json").read_bytes()
        == (root / "worldgen/live_host/window0067-regional-manifest.json").read_bytes(),
        "Regional manifest differs from reproducible inputs",
    )
    require(
        regional.canonical(screen) == (stage / "evidence/window0067-source-screen.json").read_bytes()
        == (root / DOCS / "window0067-source-screen.json").read_bytes(),
        "Regional screen differs from reproducible inputs",
    )
    visibility = read_json(checked(root / DOCS / "visibility-plan.json", VISIBILITY_SHA))
    archive = checked(root / DOCS / "visibility-arrays.npz", visibility["array_file_sha256"])
    with np.load(archive, allow_pickle=False) as saved:
        require(set(saved.files) == set(visibility["array_logical_sha256"]), "Array set differs")
        for name, expected in visibility["array_logical_sha256"].items():
            data = saved[name]
            require(data.shape == (505, 505), "Visibility shape differs")
            require(hashlib.sha256(np.ascontiguousarray(data).tobytes()).hexdigest() == expected,
                    "Visibility array changed: " + name)
        treatment = saved["treatment"].copy()
    # Authenticate the complete direct source closure of both planning manifests.
    for item in visibility["sources"]:
        checked(root / item["path"], item["sha256"])
    plan_path = root / DOCS / "spatial-plan.json"
    plan = read_json(plan_path)
    for item in plan["sources"]:
        checked(root / item["path"], item["sha256"])
    require(plan["grid"]["crs"] == "EPSG:25831"
            and plan["grid"]["transform"] == AFFINE
            and plan["grid"]["width"] == plan["grid"]["height"] == 4033,
            "Spatial plan grid differs")
    selector = next(p for p in plan["sources"] if Path(p["path"]).name == "cliff-erosion-manifest.json")
    selector_root = Path(selector["path"]).parent
    products = {p["path"]: p for p in plan["selector_products"]}
    masks = {}
    for name in ("cliff-candidate.tif", "scree-candidate.tif"):
        item = products[name]
        masks[name] = raster(selector_root / name, item["sha256"], item["logical_sha256"])
    reason_source = next(p for p in plan["sources"] if Path(p["path"]).name == "exclusion-reasons.tif")
    reasons = raster(Path(reason_source["path"]), reason_source["sha256"])
    slope_source = next(p for p in visibility["sources"] if Path(p["path"]).name == "slope.tif")
    slope = raster(Path(slope_source["path"]), slope_source["sha256"])
    policy = policy_module.refined_trial_policy()
    counts = classify_cells(masks["cliff-candidate.tif"], masks["scree-candidate.tif"],
                            reasons, slope, treatment, policy["max_local_slope_deg"])
    # No state or helper path is replaced in the already-published recipe.
    require(stage.resolve() == contact.STAGE.resolve(), "Different native stage is not admitted")
    native_input = contact.read_manifest(contact.REGIONAL_MANIFEST_SHA256, require_plant=True)
    require(native_input == manifest, "Native recipe manifest differs")
    contact.verify_footprints(native_input)
    prepared = None
    if prepare_pcgex:
        from scripts.worldgen import pcg365_pcgex_graph as graph
        source = next(item for item in manifest["exclusion_sources"]
                      if item["path"].endswith("exclusion-distance-lower-bound.bin"))
        clearance_path = checked(stage / source["path"], source["sha256"])
        clearance = np.fromfile(clearance_path, dtype="<f4").reshape(GRID)
        prepared = {
            "schema_version": 1, "policy": graph.POLICY, "map_package": manifest["map_package"],
            "assets": manifest["assets"], "radius_cm": rock_radius(manifest["assets"]),
            "visibility_manifest_sha256": VISIBILITY_SHA,
            "clearance_sha256": source["sha256"],
            "points": pcgex_records(masks["cliff-candidate.tif"], masks["scree-candidate.tif"],
                                    reasons, slope, treatment, clearance),
        }
        graph.verify_input(prepared)
        if whole_area:
            selector_manifest = read_json(selector["path"])
            protected_bits = selector_manifest["protected_reason_bits"]["mask"]
            cliff_distance = cliff_clearance(masks["cliff-candidate.tif"], masks["scree-candidate.tif"],
                                            reasons, slope, protected_bits)
            prepared["cliff_input_contract"] = {
                "selector_manifest_sha256": selector["sha256"],
                "protected_reason_bits": protected_bits,
                "unknown_terrain_excluded": True,
                "vegetation_only_reason_bits": [64, 128],
                "clearance_logical_sha256": hashlib.sha256(cliff_distance.tobytes()).hexdigest(),
                "clearance_producer": "scripts/assets/prepare_sa_calobra_road_masks.py:distance_lower_bound",
                "clearance_producer_sha256": sha(root / "scripts/assets/prepare_sa_calobra_road_masks.py"),
                "source_rasters_modified": False,
            }
            prepared["whole_area_layers"] = {
                "scree": prepared["points"],
                "cliffs": pcgex_records(masks["cliff-candidate.tif"], masks["scree-candidate.tif"],
                    reasons, slope, treatment, cliff_distance, kind="cliff", stride=4, protected_bits=protected_bits),
            }
    dependencies = [Path(regional.__file__), Path(contact.__file__), Path(policy_module.__file__)]
    blockers = [
        "Cliff treatment requires its own admitted mesh/surface consumer; map colours are proposals.",
        "The current native recipe registers only window0067-landscape-v1, not the full AOI.",
        "The existing saved material baseline is retained; no whole-area material replacement is admitted.",
        "Simplified/raised-form regions retain their unresolved review state.",
    ]
    if whole_area:
        blockers = ["Owner visual review and performance acceptance remain outstanding.",
                    "Grey simplified/raised-form areas retain the existing Landscape."]
    return {
        "schema_version": 1, "issue": 365, "milestone": "M3",
        "status": "WHOLE_AREA_NATIVE_INPUT_READY" if whole_area else "WHOLE_AREA_BUILD_BLOCKED_REGIONAL_PREVIEW_AVAILABLE",
        "source_head": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "entrypoint_sha256": sha(__file__),
        "dependencies": [{"path": p.relative_to(root).as_posix(), "sha256": sha(p)} for p in dependencies],
        "area_bounds_cm": [-25, -25, 201625, 201625], "area_size_m": [2016.5, 2016.5],
        "visibility_manifest_sha256": VISIBILITY_SHA,
        "visibility_archive_sha256": visibility["array_file_sha256"],
        "treatment_bin_counts": {str(k): v for k, v in sorted(Counter(treatment.ravel().tolist()).items())},
        "exact_source_cell_counts": counts,
        "native_policy": policy,
        "pcgex_input": prepared,
        "assets": manifest["assets"],
        "regional_manifest_sha256": contact.REGIONAL_MANIFEST_SHA256,
        "regional_scope": manifest["scope"], "regional_placements": manifest["placements"],
        "map_package": manifest["map_package"],
        "material_behavior": "REUSE_HASH_BOUND_FORGE_LIMESTONE_ON_IMPORTED_ROCKS",
        "source_material_packages": manifest["protected_packages"],
        "blockers": blockers, "native_execution": "NOT_RUN",
        "placement": False, "qualified_assets": [], "map_saved": False,
        "owner_visual": "PENDING_FINAL_M3", "performance": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }


def run_powershell(root, name, arguments):
    script = root / "scripts/live_host" / name
    require(script.is_file(), "Existing Live Host command missing")
    completed = subprocess.run(["pwsh", "-NoProfile", "-File", str(script), *arguments],
                               cwd=root, text=True, capture_output=True, timeout=60, check=False)
    require(completed.returncode == 0, completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


def receipt_readback(receipt, started, command, revision):
    """Bind to the exact submitted command; generic APPLIED is never completion."""
    require(started.get("status") == "STARTED_NO_RETRY", "Missing native start record")
    require(started.get("request") == command, "Native command differs from processed request")
    require(started.get("input") == receipt.get("input"), "Native input identity changed")
    for key in ("request_id", "sequence"):
        require(receipt.get(key) == command[key], "Native receipt identity differs: " + key)
    readback = receipt.get("readback", {})
    require(readback.get("recipe_revision") == revision, "Native recipe revision differs")
    require(readback.get("recipe") == "rock_contact_scatter", "Native recipe differs")
    require(receipt.get("status") == "COMPLETED_VISUAL_ONLY", "Native command rejected: " + str(receipt.get("status")))
    return readback["native_readback"]


def submit(root, session, revision, operation, manifest_sha, output, timeout):
    before = set((LIVE / "runtime/sessions" / session / "commands").glob("*.json"))
    text = run_powershell(root, "Send-YacsLiveHostCommand.ps1", [
        "-Action", "run_recipe", "-Recipe", "rock_contact_scatter",
        "-RecipeRevision", revision, "-Intent", "preview", "-ParametersJson",
        json.dumps({"operation": operation, "manifest_sha256": manifest_sha}),
    ])
    match = re.search(r"session=(\S+) sequence=(\d+)", text)
    require(match is not None and match[1] == session, "Live session changed during submission; do not retry")
    sequence = int(match[2])
    directory = LIVE / "runtime/sessions" / session / "commands"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        results = list(directory.glob(f"{sequence:06d}-*.result.json"))
        if results:
            require(len(results) == 1 and results[0] not in before, "Ambiguous native receipt")
            receipt = read_json(results[0])
            request_id = results[0].name.split("-", 1)[1].split(".")[0]
            processed = directory.parent / "processed" / f"{sequence:06d}-{request_id}.json"
            if not processed.exists():
                time.sleep(1)
                continue
            command = read_json(processed)
            started = read_json(directory / f"{sequence:06d}-{request_id}.started.json")
            require(command.get("session") == session and command.get("sequence") == sequence
                    and command.get("request_id") == request_id, "Processed command identity differs")
            require(receipt["input"] == {"bytes": processed.stat().st_size, "sha256": sha(processed)},
                    "Processed command bytes differ")
            require(command.get("parameters") == {
                "operation": operation, "manifest_sha256": manifest_sha,
            }, "Native parameters differ")
            native = receipt_readback(receipt, started, command, revision)
            write_new(output / results[0].name, receipt)
            write_new(output / f"{sequence:06d}-{request_id}.started.json", started)
            return native
        time.sleep(2)
    raise TimeoutError("Command receipt timeout; outcome unknown. Do not resubmit plant.")


def run_preview(root, audit_result, revision, output, timeout):
    require(re.fullmatch(r"[a-f0-9]{40}", revision or ""), "Exact published recipe revision required")
    status = json.loads(run_powershell(root, "Get-YacsLiveHostStatus.ps1", ["-RequireLive"]))
    require(status["status"] == "LIVE_VIDEO_VERIFIED"
            and status["map_package"] == audit_result["map_package"], "Current live world differs")
    session = status["session"]
    require(re.fullmatch(r"\d{8}T\d{6}Z-[a-f0-9]{12}", session), "Invalid session identity")
    manifest_sha = audit_result["regional_manifest_sha256"]
    state = submit(root, session, revision, "status", manifest_sha, output, 60)
    if state.get("operation_status") in {"CONTACT_JOB_RUNNING", "CONTACT_JOB_COMPLETED_SAMPLED_ONLY"}:
        require(state.get("manifest_sha256") == manifest_sha, "Another contact job owns the Editor")
        # Attach only to this exact producer, never relabel an older job's proof.
        job_id = state.get("request_id")
        require(re.fullmatch(r"[a-f0-9]{20}", job_id or ""), "Missing job origin")
        origin = list((LIVE / "runtime/sessions" / session / "commands").glob(f"*-{job_id}.started.json"))
        require(len(origin) == 1, "Ambiguous contact job origin")
        request = read_json(origin[0])["request"]
        require(request.get("recipe_revision") == revision and request.get("parameters") == {
            "operation": "plant", "manifest_sha256": manifest_sha,
        }, "Running job was created by another recipe/input")
        write_new(output / "attached-job-started.json", read_json(origin[0]))
    else:
        require(state.get("preview_placed", 0) == 0, "Existing previews are preserved; clear them explicitly first")
        state = submit(root, session, revision, "plant", manifest_sha, output, 60)
    deadline = time.monotonic() + timeout
    while state.get("operation_status") == "CONTACT_JOB_RUNNING":
        print(json.dumps({k: state.get(k) for k in ("phase", "sampled_positions", "preview_placed")}), flush=True)
        if time.monotonic() >= deadline:
            raise TimeoutError("Contact remains running in Unreal. No automatic restart/cancel/retry. Use the existing status/clear recipe.")
        time.sleep(15)
        state = submit(root, session, revision, "status", manifest_sha, output, 60)
        require(state.get("manifest_sha256") == manifest_sha, "Contact job replaced while waiting")
    require(state.get("operation_status") in TERMINAL, "Unrecognized terminal contact state")
    write_new(output / "native-result.json", {"session": session, "revision": revision, **state})
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--stage", type=Path, default=STAGE)
    parser.add_argument("--output", type=Path, required=True, help="New output directory; never overwrites previous work")
    parser.add_argument("--mode", choices=("audit", "prepare-pcgex", "build-pcgex", "regional-preview", "whole-area"), default="audit")
    parser.add_argument("--whole-area-assets", type=Path, default=ROOT / "worldgen/sa_calobra/pcg365_whole_area_assets_v4.json", help="Hash-bound local catalog for the whole-area native inputs")
    parser.add_argument("--recipe-revision", help="Existing CI-admitted recipe SHA; this command never publishes code")
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--save-preview-map", action="store_true", help="Save a new map copy; the source map is never saved")
    args = parser.parse_args()
    require(60 <= args.timeout_seconds <= 7200, "Timeout must be 60..7200 seconds")
    root = args.root.resolve()
    require(not args.output.exists(), "Output already exists; preserve earlier results")
    report = audit(root, args.stage.resolve(), prepare_pcgex=args.mode in ("prepare-pcgex", "build-pcgex", "whole-area"), whole_area=args.mode == "whole-area")
    prepared = report.pop("pcgex_input")
    args.output.mkdir(parents=True, exist_ok=False)
    if prepared is not None:
        from scripts.worldgen import pcg365_pcgex_graph as graph
        input_path = args.output / "pcgex-input.json"
        write_new(input_path, prepared)
        if args.mode == "whole-area":
            from scripts.worldgen.pcg365_whole_area import POLICIES, REVISION
            node_plan = {"recipe_revision": REVISION, "policies": POLICIES,
                         "input_contract": prepared["cliff_input_contract"],
                         "graph_state": "See each lane graph-state.json for the authored native graph",
                         "fragment_footprint": "Derived from the authenticated cliff mesh bounds"}
        else:
            node_plan = graph.recipe("/Game/Generated/YACS/PCG365Ex/R" + sha(input_path)[:16] + "_s2/DA_Rocks", prepared["radius_cm"])
        write_new(args.output / "pcgex-node-plan.json", node_plan)
        report["pcgex_preparation"] = {
            "status": "INPUT_READY_NATIVE_NOT_RUN", "policy": graph.POLICY,
            "input_sha256": sha(input_path), "radius_cm": prepared["radius_cm"],
            "input_points": len(prepared["points"]),
            "source_slope_at_most_42": sum(p[2] <= 42 for p in prepared["points"]),
            "source_slope_and_clearance_pass": sum(p[2] <= 42 and p[3] >=
                prepared["radius_cm"] + graph.POLICY["source_clearance_cm"] for p in prepared["points"]),
        }
    write_new(args.output / "world-input-audit.json", report)
    print(json.dumps({"status": report["status"], **report["exact_source_cell_counts"]}), flush=True)
    if args.mode == "build-pcgex":
        native = graph.build_preview(input_path, sha(input_path), args.output, args.stage, args.save_preview_map)
        print(json.dumps(native), flush=True)
        return 0
    if args.mode == "whole-area":
        require(args.whole_area_assets is not None, "Whole-area asset catalog is required")
        require(not args.save_preview_map, "Whole-area updates the current map in place; no copy")
        from scripts.worldgen.pcg365_whole_area import update_world
        native = update_world(input_path, sha(input_path), args.output, args.whole_area_assets)
        print(json.dumps(native), flush=True)
        return 0
    if args.mode == "regional-preview":
        native = run_preview(root, report, args.recipe_revision, args.output, args.timeout_seconds)
        return 0 if (native["operation_status"] == "CONTACT_JOB_COMPLETED_SAMPLED_ONLY"
                     and native.get("preview_placed") == len(report["regional_placements"])) else 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, TimeoutError, subprocess.SubprocessError) as exc:
        print(f"PCG365_STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
