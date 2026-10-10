"""Execute and verify one bounded transient CUT-only Road_Earthworks patch."""

from __future__ import annotations

from copy import deepcopy
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
from scripts.geometry.curved_road_plan import profile_plan_valid
from scripts.geometry.road_cut_limits import cut_limits, inspection_within_cut_limits
from scripts.ue.sa_calobra_geometry_collision_witness import _hit_result, _property

HEIGHTFIELD_CLASS_PATH = "/Script/Landscape.LandscapeHeightfieldCollisionComponent"


def _preflight_landscape_identity(landscape):
    library = getattr(unreal, "YacsBobLandscapeHitLibrary", None)
    if library is None:
        return
    reader = getattr(library, "inspect_accepted_checkpoint_identity", None)
    if (not callable(reader)
            or not callable(getattr(library, "inspect_accepted_landscape_hit", None))):
        raise RuntimeError("BOB native Landscape checkpoint interface is unavailable")
    identity = reader()
    impact = _property(identity, "impact_point")
    try:
        zero_impact = impact is not None and all(
            type(getattr(impact, axis)) in (int, float) and getattr(impact, axis) == 0.0
            for axis in ("x", "y", "z")
        )
    except (AttributeError, TypeError):
        zero_impact = False
    if (_property(identity, "accepted") is not True
            or _property(identity, "status") != "CHECKPOINT_IDENTITY"
            or _property(identity, "error") != ""
            or _property(identity, "map_package") != landscape.get_path_name().split(".")[0]
            or _property(identity, "hit_actor") != landscape
            or _property(identity, "actor_path") != landscape.get_path_name()
            or _property(identity, "actor_class_path") != landscape.get_class().get_path_name()
            or _property(identity, "blocking_hit") is not False or not zero_impact
            or _property(identity, "hit_component") is not None
            or _property(identity, "component_path") != ""
            or _property(identity, "component_class_path") != ""):
        raise RuntimeError("BOB native Landscape checkpoint identity is rejected or inconsistent")


def _landscape_measurement_scope(world, landscape):
    _preflight_landscape_identity(landscape)
    landscapes = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape))
    if len(landscapes) != 1 or landscapes[0] != landscape:
        raise RuntimeError("BOB inspection expects the single supplied Landscape in this world")
    actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
    paths = [actor.get_path_name() for actor in actors]
    if (landscape not in actors or any(not isinstance(path, str) or not path for path in paths)
            or len(set(paths)) != len(paths)):
        raise RuntimeError("BOB Landscape inspection actor inventory is missing or ambiguous")
    # Owned mesh/render primitives are not necessarily terrain. Admit only the
    # native heightfield collision class; unsupported classes stay unmeasured.
    primitives = list(landscape.get_components_by_class(unreal.PrimitiveComponent))
    try:
        components = [component for component in primitives
                      if component.get_class().get_path_name()
                      == HEIGHTFIELD_CLASS_PATH]
    except Exception as exc:  # noqa: BLE001 - reflected class may be unavailable
        raise RuntimeError("BOB Landscape collision component type is unavailable") from exc
    component_paths = [component.get_path_name() for component in components]
    if (not components or any(not isinstance(path, str) or not path for path in component_paths)
            or len(set(component_paths)) != len(component_paths)):
        raise RuntimeError("BOB Landscape heightfield collision inventory is missing or ambiguous")
    return [actor for actor in actors if actor != landscape], components


def _landscape_hit_height(hit, start, end, landscape, components):
    if hit is None:
        return None
    library = getattr(unreal, "YacsBobLandscapeHitLibrary", None)
    if library is not None:
        reader = getattr(library, "inspect_accepted_landscape_hit", None)
        if not callable(reader):
            raise RuntimeError("BOB native Landscape hit bridge interface is unavailable")
        hit = reader(hit)
        accepted, status = _property(hit, "accepted"), _property(hit, "status")
        blocking = _property(hit, "blocking_hit")
        if (accepted is not True
                or _property(hit, "map_package") != landscape.get_path_name().split(".")[0]
                or not isinstance(_property(hit, "error"), str)):
            raise RuntimeError("BOB native Landscape hit bridge rejected the sample or map")
        if status == "MISSING_HIT" and blocking is False:
            if (_property(hit, "hit_actor") is not None
                    or _property(hit, "hit_component") is not None
                    or any(_property(hit, name) != "" for name in (
                        "actor_path", "actor_class_path", "component_path", "component_class_path",
                    ))):
                raise RuntimeError("BOB native Landscape miss supplied inconsistent ownership")
            return None
        if (status != "OWNED_LANDSCAPE_HIT" or blocking is not True
                or _property(hit, "error") != ""
                or _property(hit, "impact_point") is None):
            raise RuntimeError("BOB native Landscape hit bridge result is invalid")
        actor, component = _property(hit, "hit_actor"), _property(hit, "hit_component")
        if (actor != landscape or component is None
                or not any(component == owned for owned in components)
                or component.get_class().get_path_name() != HEIGHTFIELD_CLASS_PATH
                or _property(hit, "actor_path") != landscape.get_path_name()
                or _property(hit, "actor_class_path") != landscape.get_class().get_path_name()
                or _property(hit, "component_path") != component.get_path_name()
                or _property(hit, "component_class_path") != HEIGHTFIELD_CLASS_PATH):
            raise RuntimeError("BOB native Landscape hit bridge owner identity differs")
    blocking = _property(hit, "blocking_hit")
    if blocking is False:
        return None
    if blocking is not True:
        raise RuntimeError("BOB Landscape HitResult blocking status is unavailable")
    actor = _property(hit, "hit_actor")
    component = _property(hit, "hit_component")
    if (actor is None or actor != landscape or component is None
            or not any(component == owned for owned in components)):
        raise RuntimeError("BOB Landscape HitResult actor/component ownership is unknown or foreign")
    measured = _hit_result(hit, start, end)
    if (measured["actor_path"] != landscape.get_path_name()
            or measured["component_path"] != component.get_path_name()):
        raise RuntimeError("BOB Landscape HitResult owner identity changed")
    return measured["impact_cm"][2] / 100.0


def measure_smooth_terrain_fit(
    world,
    profile,
    smooth_vertices,
    smooth_meta,
    *,
    exact_sha,
    contact_band_max_m,
    geometry_inspection_view,
    sample_sink=None,
    landscape=None,
):
    """Inspect existing traces; optionally hand all raw rows to a trusted sink.

    The sink receives detached ``samples`` and ``inspection`` keyword values
    after the real inspector completes. Existing callers retain the same
    measurements and report. The sink is an integration callback, never a
    caller-supplied MCP argument. ``landscape`` is also a trusted integration
    argument: when provided, ignore other actors and require blocking status
    plus exact hit actor/owned-component identity. Use the internal native
    ``YacsBobLandscapeHitLibrary`` when present and verify its fixed checkpoint
    identity before the first trace; otherwise require the original reflected
    HitResult fields. An unavailable or rejected native bridge never
    falls back to a permissive reading. Its actual UE reflection/build/runtime
    still needs native proof; synthetic checks do not establish that interface.
    This function neither writes an export nor certifies the selected scene.
    The default unfiltered trace retains its original assumption that other
    collidable geometry cannot intercept the measurement.
    """
    if sample_sink is not None and not callable(sample_sink):
        raise TypeError("sample_sink must be a trusted callable or None")
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
    ignored, components = [], []
    if landscape is not None:
        ignored, components = _landscape_measurement_scope(world, landscape)

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
            ignored,
            unreal.DrawDebugTrace.NONE,
            True,
        )
        if landscape is None:
            values = () if hit is None else hit.to_tuple()
            candidates = [
                float(value.z) / 100.0
                for value in values
                if all(hasattr(value, key) for key in ("x", "y", "z"))
                and abs(float(value.x) - x_cm) < 0.1
                and abs(float(value.y) - y_cm) < 0.1
                and abs(float(value.z) - road_z_cm) < 9999.0
            ]
            landscape_z_m = candidates[0] if candidates else None
        else:
            landscape_z_m = _landscape_hit_height(
                hit, [x_cm, y_cm, road_z_cm + 10000.0],
                [x_cm, y_cm, road_z_cm - 10000.0], landscape, components,
            )
        station_index = sample_index // section_points
        lateral_index = sample_index % section_points
        row = rows[station_index]
        samples.append(
            {
                "station_m": float(row["station_m"]),
                "lateral_m": float(row["lateral_m"][lateral_index]),
                "local_xy_m": [x_m, y_m],
                "road_surface_z_m": road_z_m,
                "landscape_z_m": landscape_z_m,
            }
        )

    inspection = inspect_terrain_fit(
        samples,
        exact_sha=exact_sha,
        contact_band_max_m=float(contact_band_max_m),
        structure_review_threshold_m=structure_threshold_m,
        geometry_inspection_view=geometry_inspection_view,
    )
    if sample_sink is not None:
        sample_sink(samples=deepcopy(samples), inspection=deepcopy(inspection))
    return inspection


def apply_cut_patch(world, root, exact_sha, pre_fit):
    manifest_path = root / PATCH_MANIFEST
    patch = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = json.loads((root / "ma2141-profile-candidate.json").read_text(encoding="utf-8"))
    policy = json.loads((ROOT / "worldgen/terrain/adaptive_terrain_policy.json").read_text(encoding="utf-8"))
    limits = cut_limits(profile.get("presentation_plan", {}), policy)
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
        or not profile_plan_valid(profile)
        or patch.get("cut_limits") != limits
        or patch.get("max_cut_limit_m") != limits["cliff_m"]
        or not inspection_within_cut_limits(pre_fit, limits)
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
        "patch_cut_limits": patch["cut_limits"],
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
