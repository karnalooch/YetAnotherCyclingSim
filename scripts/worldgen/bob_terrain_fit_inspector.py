"""Read-only BOB inspection of smooth-road fit against the real Landscape.

This module classifies measured road-surface/Landscape residuals. It never
changes terrain, road geometry, verified case memory or learning state.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.worldgen.adaptive_terrain_solver import BOB_NAME


CONTACT_OK = "CONTACT_OK"
CUT_REQUIRED = "CUT_REQUIRED"
FILL_REQUIRED = "FILL_REQUIRED"
STRUCTURE_REVIEW = "STRUCTURE_REVIEW"
ALL_ACTIONS = (
    CONTACT_OK,
    CUT_REQUIRED,
    FILL_REQUIRED,
    STRUCTURE_REVIEW,
)
_EPSILON_M = 1e-6


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number")
    return result


def classify_terrain_fit_sample(
    *,
    road_surface_z_m: float,
    landscape_z_m: float,
    contact_band_max_m: float,
    structure_review_threshold_m: float,
) -> dict[str, float | str]:
    """Classify one measured road/Landscape residual without authoring anything."""
    road = _number(road_surface_z_m, "road_surface_z_m")
    landscape = _number(landscape_z_m, "landscape_z_m")
    contact_max = _number(contact_band_max_m, "contact_band_max_m")
    structure_threshold = _number(
        structure_review_threshold_m,
        "structure_review_threshold_m",
    )
    if contact_max <= 0.0:
        raise ValueError("contact_band_max_m must be positive")
    if structure_threshold <= contact_max:
        raise ValueError(
            "structure_review_threshold_m must exceed the contact band"
        )

    residual = road - landscape
    cut_required = max(0.0, -residual)
    fill_required = max(0.0, residual - contact_max)
    required_adjustment = max(cut_required, fill_required)

    if required_adjustment + _EPSILON_M >= structure_threshold:
        action = STRUCTURE_REVIEW
    elif cut_required > _EPSILON_M:
        action = CUT_REQUIRED
    elif fill_required > _EPSILON_M:
        action = FILL_REQUIRED
    else:
        action = CONTACT_OK

    return {
        "action": action,
        "residual_m": residual,
        "cut_required_m": cut_required,
        "fill_required_m": fill_required,
        "required_adjustment_m": required_adjustment,
    }


def _action_intervals(
    station_summaries: Sequence[Mapping[str, Any]],
    action: str,
) -> list[dict[str, float]]:
    active = [
        float(row["station_m"])
        for row in station_summaries
        if int(row["class_counts"].get(action, 0)) > 0
    ]
    if not active:
        return []

    intervals: list[dict[str, float]] = []
    start = previous = active[0]
    step = None
    if len(station_summaries) >= 2:
        step = float(station_summaries[1]["station_m"]) - float(
            station_summaries[0]["station_m"]
        )
    if step is None or step <= 0:
        step = 0.5

    for station in active[1:]:
        if math.isclose(station - previous, step, abs_tol=1e-7, rel_tol=0.0):
            previous = station
            continue
        intervals.append({"start_m": start, "end_m": previous})
        start = previous = station
    intervals.append({"start_m": start, "end_m": previous})
    return intervals


def inspect_terrain_fit(
    samples: Sequence[Mapping[str, Any]],
    *,
    exact_sha: str,
    contact_band_max_m: float,
    structure_review_threshold_m: float,
    geometry_inspection_view: str = "road-geometry-inspection",
) -> dict[str, Any]:
    """Aggregate real Landscape traces into BOB's read-only terrain-fit report."""
    if (
        not isinstance(exact_sha, str)
        or len(exact_sha) != 40
        or any(char not in "0123456789abcdef" for char in exact_sha)
    ):
        raise ValueError("exact_sha must be lowercase SHA40")
    if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)):
        raise ValueError("samples must be a sequence")

    contact_max = _number(contact_band_max_m, "contact_band_max_m")
    structure_threshold = _number(
        structure_review_threshold_m,
        "structure_review_threshold_m",
    )
    if contact_max <= 0.0 or structure_threshold <= contact_max:
        raise ValueError("invalid terrain-fit policy thresholds")

    class_counts: Counter[str] = Counter()
    trace_misses: list[dict[str, Any]] = []
    evaluated: list[dict[str, Any]] = []
    by_station: dict[float, list[dict[str, Any]]] = {}

    for index, raw in enumerate(samples):
        if not isinstance(raw, Mapping):
            raise ValueError("terrain-fit sample must be an object")
        station = _number(raw["station_m"], "station_m")
        lateral = _number(raw["lateral_m"], "lateral_m")
        local_xy = raw["local_xy_m"]
        if (
            not isinstance(local_xy, Sequence)
            or isinstance(local_xy, (str, bytes))
            or len(local_xy) != 2
        ):
            raise ValueError("local_xy_m must contain x/y")
        xy = [
            _number(local_xy[0], "local_xy_m.x"),
            _number(local_xy[1], "local_xy_m.y"),
        ]
        road_z = _number(raw["road_surface_z_m"], "road_surface_z_m")
        landscape_raw = raw.get("landscape_z_m")

        identity = {
            "sample_index": index,
            "station_m": station,
            "lateral_m": lateral,
            "local_xy_m": xy,
            "road_surface_z_m": road_z,
        }
        if landscape_raw is None:
            trace_misses.append(identity)
            continue

        landscape_z = _number(landscape_raw, "landscape_z_m")
        classification = classify_terrain_fit_sample(
            road_surface_z_m=road_z,
            landscape_z_m=landscape_z,
            contact_band_max_m=contact_max,
            structure_review_threshold_m=structure_threshold,
        )
        row = {
            **identity,
            "landscape_z_m": landscape_z,
            **classification,
        }
        evaluated.append(row)
        class_counts[str(classification["action"])] += 1
        by_station.setdefault(station, []).append(row)

    station_summaries = []
    for station in sorted(by_station):
        rows = by_station[station]
        counts = Counter(str(row["action"]) for row in rows)
        station_summaries.append(
            {
                "station_m": station,
                "sample_count": len(rows),
                "class_counts": {
                    action: counts.get(action, 0) for action in ALL_ACTIONS
                },
                "max_cut_required_m": max(
                    float(row["cut_required_m"]) for row in rows
                ),
                "max_fill_required_m": max(
                    float(row["fill_required_m"]) for row in rows
                ),
                "max_required_adjustment_m": max(
                    float(row["required_adjustment_m"]) for row in rows
                ),
                "required_actions": [
                    action
                    for action in ALL_ACTIONS
                    if action != CONTACT_OK and counts.get(action, 0) > 0
                ],
            }
        )

    evaluated_count = len(evaluated)
    required_adjustments = [
        float(row["required_adjustment_m"]) for row in evaluated
    ]
    max_cut = max(
        (float(row["cut_required_m"]) for row in evaluated),
        default=0.0,
    )
    max_fill = max(
        (float(row["fill_required_m"]) for row in evaluated),
        default=0.0,
    )
    rms_adjustment = (
        math.sqrt(
            sum(value * value for value in required_adjustments)
            / evaluated_count
        )
        if evaluated_count
        else 0.0
    )
    action_samples = [
        row for row in evaluated if row["action"] != CONTACT_OK
    ]
    worst = sorted(
        action_samples,
        key=lambda row: (
            -float(row["required_adjustment_m"]),
            float(row["station_m"]),
            float(row["lateral_m"]),
        ),
    )[:100]

    complete = len(trace_misses) == 0 and evaluated_count == len(samples)
    return {
        "schema_version": 1,
        "inspection_policy_id": "bob-road-terrain-fit-v1",
        "inspector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "architect": BOB_NAME,
        "role": "INSPECTOR_ONLY",
        "status": "REVIEW_REQUIRED" if complete else "INSPECTION_INCOMPLETE",
        "inspection_complete": complete,
        "exact_sha": exact_sha,
        "geometry_inspection_view": geometry_inspection_view,
        "policy": {
            "contact_band_min_m": 0.0,
            "contact_band_max_m": contact_max,
            "structure_review_threshold_m": structure_threshold,
            "structure_threshold_source": (
                "adaptive_terrain_policy.thresholds.retaining_cut_fill_m"
            ),
        },
        "sample_count": len(samples),
        "evaluated_sample_count": evaluated_count,
        "trace_miss_count": len(trace_misses),
        "class_counts": {
            action: class_counts.get(action, 0) for action in ALL_ACTIONS
        },
        "terrain_above_road_sample_count": sum(
            1 for row in evaluated if float(row["cut_required_m"]) > _EPSILON_M
        ),
        "terrain_below_supported_road_sample_count": sum(
            1 for row in evaluated if float(row["fill_required_m"]) > _EPSILON_M
        ),
        "max_cut_required_m": max_cut,
        "max_fill_required_m": max_fill,
        "max_required_adjustment_m": max(max_cut, max_fill),
        "rms_required_adjustment_m": rms_adjustment,
        "cut_intervals_m": _action_intervals(station_summaries, CUT_REQUIRED),
        "fill_intervals_m": _action_intervals(station_summaries, FILL_REQUIRED),
        "structure_review_intervals_m": _action_intervals(
            station_summaries,
            STRUCTURE_REVIEW,
        ),
        "station_summaries": station_summaries,
        "worst_action_samples": worst,
        "trace_misses": trace_misses[:100],
        "earthworks_authoring_permitted": False,
        "geometry_repair_executed": False,
        "road_admitted": False,
        "eligible_for_learning": False,
        "contextual_structure_review_status": "SEPARATE_BOB_CHECKS_REQUIRED",
        "next_actions": [
            "review road-geometry-inspection beside this residual report",
            "treat terrain above the ribbon inside the road footprint as CUT_REQUIRED",
            "treat unsupported ribbon above the contact band as FILL_REQUIRED",
            "escalate large adjustments to structure review before any earthworks lesson",
            "preserve Base_DTM and canonical road XY",
        ],
    }
