"""Read-only geometry collision census at four source-bound Sa Calobra cameras.

A visibility-channel blocking hit is not rendered-pixel or shadow-caster proof.
The tool never mutates collision, meshes, Landscape, roads or production assets.
"""

from __future__ import annotations

import math

GEOMETRY_IDS = (
    "near-landscape-2",
    "seam-close",
    "ground-1-2",
    "window-0021-forward-00005",
)
XY_OFFSETS_CM = (
    (0, 0),
    (-200, 0),
    (200, 0),
    (0, -200),
    (0, 200),
    (-200, -200),
    (-200, 200),
    (200, -200),
    (200, 200),
)
TRACE_TOP_CM = 150000
TRACE_BOTTOM_CM = -150000


def trace_plan(views):
    lookup = {view["frame_id"]: view for view in views}
    if len(lookup) != len(views) or not set(GEOMETRY_IDS) <= set(lookup):
        raise ValueError("Source-bound geometry camera inventory is incomplete")
    plan = []
    for frame_id in GEOMETRY_IDS:
        target = lookup[frame_id]["target"]
        if len(target) != 3 or not all(math.isfinite(float(v)) for v in target):
            raise ValueError("Geometry target contains invalid world coordinates")
        for dx, dy in XY_OFFSETS_CM:
            x, y = target[0] + dx, target[1] + dy
            plan.append(
                {
                    "frame_id": frame_id,
                    "offset_cm": [dx, dy],
                    "start_cm": [x, y, TRACE_TOP_CM],
                    "end_cm": [x, y, TRACE_BOTTOM_CM],
                }
            )
    return plan


def _property(hit, name):
    getter = getattr(hit, "get_editor_property", None)
    if callable(getter):
        try:
            return getter(name)
        except Exception:  # noqa: BLE001 - Unreal StructBase raises generic Exception
            pass
    try:
        return getattr(hit, name, None)
    except Exception:  # noqa: BLE001 - missing Unreal reflected property
        return None


def _vector(value, label):
    if value is None:
        return None
    result = [float(getattr(value, axis)) for axis in ("x", "y", "z")]
    if not all(math.isfinite(number) for number in result):
        raise ValueError("Nonfinite geometry " + label)
    return result


def _hit_result(hit, start, end):
    if hit is None:
        return None
    location = _vector(_property(hit, "impact_point"), "impact point")
    if location is None:
        # UE5.8 HitResult reflection can reject impact_point even though
        # the native StructBase.to_tuple() exposes its actual trace vectors.
        # Reuse the same collinear-interior policy as the proven source probe.
        candidates = []
        direction = [b - a for a, b in zip(start, end, strict=True)]
        length2 = sum(d * d for d in direction)
        for item in hit.to_tuple():
            if not all(hasattr(item, axis) for axis in ("x", "y", "z")):
                continue
            p = _vector(item, "tuple vector")
            t = sum(
                (x - a) * d for x, a, d in zip(p, start, direction, strict=True)
            ) / length2
            residual = sum(
                (x - a - t * d) ** 2
                for x, a, d in zip(p, start, direction, strict=True)
            )
            if 1e-7 < t < 1 - 1e-7 and residual <= 1.0:
                candidates.append((t, p))
        if not candidates:
            raise RuntimeError("Native HitResult has no valid interior ray hit")
        location = min(candidates, key=lambda row: row[0])[1]
    direction = [b - a for a, b in zip(start, end, strict=True)]
    length2 = sum(d * d for d in direction)
    if not length2:
        raise RuntimeError("Degenerate native geometry ray")
    t = sum(
        (x - a) * d for x, a, d in zip(location, start, direction, strict=True)
    ) / length2
    residual = sum(
        (x - a - t * d) ** 2
        for x, a, d in zip(location, start, direction, strict=True)
    )
    if not 1e-7 < t < 1 - 1e-7 or residual > 1.0:
        raise RuntimeError("Geometry trace impact is not on the inspected ray")
    actor = _property(hit, "hit_actor")
    component = _property(hit, "hit_component")
    normal = _vector(_property(hit, "impact_normal"), "impact normal")
    face = _property(hit, "face_index")
    shadow = None
    if component is not None:
        flag = _property(component, "cast_shadow")
        if type(flag) is bool:
            shadow = flag
    return {
        "impact_cm": location,
        "actor_path": actor.get_path_name() if actor is not None else None,
        "component_path": (
            component.get_path_name() if component is not None else None
        ),
        "impact_normal": normal,
        "face_index": face if type(face) is int else None,
        "component_cast_shadow": shadow,
    }


def classify_surface(world_hit, landscape_hit, owner_path):
    if landscape_hit is None:
        return "LANDSCAPE_COLLISION_MISSING"
    if (
        landscape_hit["actor_path"] is not None
        and landscape_hit["actor_path"] != owner_path
    ):
        return "LANDSCAPE_ACTOR_IDENTITY_MISMATCH"
    if world_hit is None:
        return "WORLD_COLLISION_MISSING"
    if world_hit["actor_path"] == owner_path:
        return "LANDSCAPE_FIRST_HIT"
    if world_hit["actor_path"] is None:
        return "WORLD_HIT_OWNER_UNKNOWN"
    if world_hit["impact_cm"][2] > landscape_hit["impact_cm"][2] + 2.0:
        return "NON_LANDSCAPE_SURFACE_ABOVE"
    return "NON_LANDSCAPE_HIT_REVIEW"


def capture_geometry_collision(api, world, landscape, views):
    subsystem = api.get_editor_subsystem(api.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    if landscape not in actors:
        raise RuntimeError("Read-only geometry census cannot locate Landscape actor")
    paths = sorted(actor.get_path_name() for actor in actors)
    if len(set(paths)) != len(paths):
        raise RuntimeError("Read-only geometry actor paths are ambiguous")
    ignored_for_landscape = [actor for actor in actors if actor != landscape]
    owner_path = landscape.get_path_name()
    samples = []
    for row in trace_plan(views):
        start, end = row["start_cm"], row["end_cm"]

        def query(ignore):
            hit = api.SystemLibrary.line_trace_single(
                world,
                api.Vector(*start),
                api.Vector(*end),
                api.TraceTypeQuery.ECC_VISIBILITY,
                True,
                ignore,
                api.DrawDebugTrace.NONE,
                True,
            )
            return _hit_result(hit, start, end)

        landscape_hit = query(ignored_for_landscape)
        world_hit = query([])
        samples.append(
            {
                **row,
                "landscape_hit": landscape_hit,
                "world_hit": world_hit,
                "category": classify_surface(world_hit, landscape_hit, owner_path),
                "height_delta_cm": (
                    round(
                        world_hit["impact_cm"][2] - landscape_hit["impact_cm"][2],
                        5,
                    )
                    if landscape_hit is not None and world_hit is not None
                    else None
                ),
            }
        )
    return {
        "schema_version": 1,
        "status": "COLLISION_GEOMETRY_CAPTURED_FOR_REVIEW",
        "owner_path": owner_path,
        "actor_paths": paths,
        "sample_count": len(samples),
        "samples": samples,
        "mutation_performed": False,
        "geometry_defect_confirmed": False,
        "rendered_pixel_depth_verified": False,
        "shadow_caster_identity_verified": False,
        "scope": (
            "Complex vertical visibility collision: first all-actor hit versus "
            "Landscape-only. Collision-disabled meshes, renderer pixel depth "
            "and actual shadow casters are not covered. Non-Landscape hits "
            "might be valid roads, rocks or overhangs."
        ),
        "visual_acceptance": "PENDING_OWNER",
    }


def validate_geometry_collision(report, captures):
    """Bounded, independent validation; never authorizes speculative geometry edits."""
    from scripts.ci.sa_calobra_whole_map_workflow import require

    lookup = {
        row["frame_id"]: row
        for row in captures
        if row.get("mode") == "prepared"
    }
    require(
        all(name in lookup for name in GEOMETRY_IDS),
        "Missing source-bound geometry capture poses",
    )
    expected = trace_plan(
        [
            {"frame_id": name, "target": lookup[name]["target_cm"]}
            for name in GEOMETRY_IDS
        ]
    )
    require(
        report.get("schema_version") == 1
        and report.get("status") == "COLLISION_GEOMETRY_CAPTURED_FOR_REVIEW"
        and report.get("mutation_performed") is False
        and report.get("geometry_defect_confirmed") is False
        and report.get("rendered_pixel_depth_verified") is False
        and report.get("shadow_caster_identity_verified") is False
        and report.get("visual_acceptance") == "PENDING_OWNER",
        "Geometry witness cannot assert repairs or visual acceptance",
    )
    actors = report.get("actor_paths", [])
    owner = report.get("owner_path")
    require(
        isinstance(actors, list)
        and all(isinstance(s, str) and s for s in actors)
        and actors == sorted(set(actors))
        and owner in actors,
        "Geometry witness actor inventory is incomplete",
    )
    samples = report.get("samples", [])
    require(
        len(samples) == len(expected) == report.get("sample_count") == 36,
        "Geometry witness sample inventory is incomplete",
    )
    labels = (
        "LANDSCAPE_COLLISION_MISSING",
        "LANDSCAPE_ACTOR_IDENTITY_MISMATCH",
        "WORLD_COLLISION_MISSING",
        "LANDSCAPE_FIRST_HIT",
        "WORLD_HIT_OWNER_UNKNOWN",
        "NON_LANDSCAPE_SURFACE_ABOVE",
        "NON_LANDSCAPE_HIT_REVIEW",
    )
    for sample, frame in zip(samples, expected, strict=True):
        require(
            all(
                sample.get(k) == frame[k]
                for k in ("frame_id", "offset_cm", "start_cm", "end_cm")
            ),
            "Geometry witness ray or target changed",
        )
        world_hit = sample.get("world_hit")
        landscape_hit = sample.get("landscape_hit")
        for hit in (world_hit, landscape_hit):
            if hit is None:
                continue
            impact = hit.get("impact_cm")
            require(
                isinstance(impact, list)
                and len(impact) == 3
                and all(
                    type(v) in (float, int) and math.isfinite(v) for v in impact
                )
                and frame["start_cm"][2] > impact[2] > frame["end_cm"][2]
                and abs(impact[0] - frame["start_cm"][0]) <= 1.0
                and abs(impact[1] - frame["start_cm"][1]) <= 1.0
                and hit.get("actor_path") in (None, *actors),
                "Geometry hit is out of trace bounds or actor inventory",
            )
        require(
            sample.get("category")
            == classify_surface(world_hit, landscape_hit, owner)
            and sample["category"] in labels,
            "Geometry witness category does not match collision data",
        )
        expected_delta = (
            round(
                world_hit["impact_cm"][2] - landscape_hit["impact_cm"][2],
                5,
            )
            if world_hit is not None and landscape_hit is not None
            else None
        )
        require(
            sample.get("height_delta_cm") == expected_delta,
            "Geometry witness height delta changed",
        )
    return {
        "status": "COLLISION_GEOMETRY_EVIDENCE_VERIFIED",
        "sample_count": len(samples),
        "categories": {
            label: sum(s["category"] == label for s in samples)
            for label in labels
        },
        "geometry_defect_confirmed": False,
        "shadow_caster_identity_verified": False,
        "rendered_pixel_depth_verified": False,
        "visual_acceptance": "PENDING_OWNER",
    }
