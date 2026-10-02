"""Execute and verify one bounded transient CUT-only Road_Earthworks patch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import unreal

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.worldgen.bob_terrain_fit_inspector import inspect_terrain_fit

CUT_PROOF = "bob-road-earthworks-cut-proof.json"
PATCH_MANIFEST = "ma2141-cut-patch.json"
MAX_CUT_M = 1.0


def measure_smooth_terrain_fit(
    world,
    profile,
    smooth_vertices,
    smooth_meta,
    *,
    exact_sha,
    contact_band_max_m,
    geometry_inspection_view,
):
    policy = json.loads(
        (ROOT / "worldgen/terrain/adaptive_terrain_policy.json").read_text(
            encoding="utf-8"
        )
    )
    structure_threshold_m = float(
        policy["thresholds"]["retaining_cut_fill_m"]
    )
    top_count = int(smooth_meta["top_vertex_count"])
    section_points = int(smooth_meta["cross_section_point_count"])
    rows = profile["stations"]
    if top_count != len(rows) * section_points:
        raise RuntimeError("Smooth ribbon/profile sample count mismatch")

    samples = []
    for sample_index, point in enumerate(smooth_vertices[:top_count]):
        x_m, y_m, road_z_m = [float(value) for value in point]
        x_cm = x_m * 100.0
        y_cm = y_m * 100.0
        road_z_cm = road_z_m * 100.0
        hit = unreal.SystemLibrary.line_trace_single(
            world,
            unreal.Vector(x_cm, y_cm, road_z_cm + 10000.0),
            unreal.Vector(x_cm, y_cm, road_z_cm - 10000.0),
            unreal.TraceTypeQuery.ECC_VISIBILITY,
            True,
            [],
            unreal.DrawDebugTrace.NONE,
            True,
        )
        values = () if hit is None else hit.to_tuple()
        candidates = [
            float(value.z) / 100.0
            for value in values
            if all(hasattr(value, key) for key in ("x", "y", "z"))
            and abs(float(value.x) - x_cm) < 0.1
            and abs(float(value.y) - y_cm) < 0.1
            and abs(float(value.z) - road_z_cm) < 9999.0
        ]
        station_index = sample_index // section_points
        lateral_index = sample_index % section_points
        row = rows[station_index]
        samples.append(
            {
                "station_m": float(row["station_m"]),
                "lateral_m": float(row["lateral_m"][lateral_index]),
                "local_xy_m": [x_m, y_m],
                "road_surface_z_m": road_z_m,
                "landscape_z_m": candidates[0] if candidates else None,
            }
        )

    return inspect_terrain_fit(
        samples,
        exact_sha=exact_sha,
        contact_band_max_m=float(contact_band_max_m),
        structure_review_threshold_m=structure_threshold_m,
        geometry_inspection_view=geometry_inspection_view,
    )


def apply_cut_patch(world, root, exact_sha, pre_fit):
    manifest_path = root / PATCH_MANIFEST
    patch = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = pre_fit["class_counts"]
    if (
        patch.get("exact_sha") != exact_sha
        or patch.get("region_id") != "sa_calobra"
        or patch.get("operation") != "CUT_ONLY"
        or patch.get("layer") != "Road_Earthworks"
        or patch.get("base_dtm_modified") is not False
        or patch.get("fill_authoring_permitted") is not False
        or patch.get("structure_authoring_permitted") is not False
        or patch.get("save_map") is not False
        or pre_fit.get("inspection_complete") is not True
        or pre_fit.get("trace_miss_count") != 0
        or int(counts.get("CUT_REQUIRED", 0)) <= 0
        or int(counts.get("STRUCTURE_REVIEW", 0)) != 0
        or float(pre_fit.get("max_cut_required_m", 999.0)) > MAX_CUT_M
    ):
        raise RuntimeError("BOB CUT patch precondition failed closed")

    landscapes = list(
        unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    )
    if len(landscapes) != 1:
        raise RuntimeError("BOB CUT patch expects exactly one Landscape")
    landscape = landscapes[0]
    layer_names = [
        str(layer.get_name_bp()) for layer in landscape.get_edit_layers_bp()
    ]
    if layer_names.count("Base_DTM") != 1 or layer_names.count("Road_Earthworks") != 1:
        raise RuntimeError("BOB CUT patch has ambiguous semantic Landscape layers")

    library = getattr(unreal, "CyclingLandscapeEarthworksLibrary", None)
    if library is None:
        raise RuntimeError("CyclingLandscapeEarthworksLibrary is unavailable")
    if not library.apply_road_earthworks_patch(landscape, str(manifest_path)):
        raise RuntimeError("Native Road_Earthworks CUT patch application failed")
    return patch


def finalize_cut_proof(root, exact_sha, patch, pre_fit, post_fit, *, reject_on_failure=True):
    before = pre_fit["class_counts"]
    after = post_fit["class_counts"]
    new_fill_required = max(
        0,
        int(after.get("FILL_REQUIRED", 0))
        - int(before.get("FILL_REQUIRED", 0)),
    )
    passed = (
        post_fit.get("inspection_complete") is True
        and post_fit.get("trace_miss_count") == 0
        and int(before.get("CUT_REQUIRED", 0)) > 0
        and int(before.get("STRUCTURE_REVIEW", 0)) == 0
        and int(after.get("CUT_REQUIRED", 0)) == 0
        and int(after.get("STRUCTURE_REVIEW", 0)) == 0
        and new_fill_required == 0
        and float(post_fit.get("max_cut_required_m", 999.0)) <= 1e-6
    )
    report = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "architect": "BOB",
        "recipe_id": "bob-direct-road-earthworks-cut-v1",
        "status": "TECHNICAL_CUT_PASS" if passed else "REJECT_CUT",
        "operation": "CUT_ONLY",
        "selected_layer": "Road_Earthworks",
        "base_layer": "Base_DTM",
        "execution_scope": "transient editor session; map not saved",
        "geometry_repair_executed": True,
        "transient_road_earthworks_modified": True,
        "base_dtm_modified": False,
        "map_saved": False,
        "fill_authored": False,
        "structures_authored": False,
        "new_fill_required_sample_count": new_fill_required,
        "patch_modified_vertex_count": patch["modified_vertex_count"],
        "patch_max_cut_m": patch["max_cut_m"],
        "before": {
            "sample_count": pre_fit["sample_count"],
            "trace_miss_count": pre_fit["trace_miss_count"],
            "class_counts": before,
            "max_cut_required_m": pre_fit["max_cut_required_m"],
            "max_fill_required_m": pre_fit["max_fill_required_m"],
        },
        "after": {
            "sample_count": post_fit["sample_count"],
            "trace_miss_count": post_fit["trace_miss_count"],
            "class_counts": after,
            "max_cut_required_m": post_fit["max_cut_required_m"],
            "max_fill_required_m": post_fit["max_fill_required_m"],
        },
        "road_admitted": False,
        "eligible_for_learning": False,
        "continuous_contact": "NOT_PROVEN",
        "road_collision": "NOT_PROVEN",
        "human_visual": "PENDING",
        "performance": "PENDING",
    }
    (root / CUT_PROOF).write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    if not passed and reject_on_failure:
        raise RuntimeError("BOB CUT patch did not eliminate every CUT_REQUIRED sample")
    return report
