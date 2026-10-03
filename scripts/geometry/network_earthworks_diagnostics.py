"""Diagnostic bounds for a uniform preview-height shift; never author geometry."""

import math


def height_fit_bounds(
    max_cut_m, max_core_support_m, max_shoulder_support_m, *, cut_cap_m, support_cap_m
):
    """Bound an upward translation using the measured raster CUT and support.

    This is only a necessary screen, not a vertical-profile solver.
    It cannot prove source height, joins, contact or admissibility of a shift.
    Signed shoulder gaps retain below-terrain evidence instead of clipping it
    to zero. No height change is applied.
    """
    values = (
        max_cut_m,
        max_core_support_m,
        max_shoulder_support_m,
        cut_cap_m,
        support_cap_m,
    )
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in values
    ):
        raise ValueError("Finite earthworks measurements required")
    if max_cut_m < 0 or min(cut_cap_m, support_cap_m) <= 0:
        raise ValueError("Invalid earthworks measurements or limits")
    lower = max(0.0, max_cut_m - cut_cap_m)
    upper = min(
        support_cap_m - max_core_support_m, support_cap_m - max_shoulder_support_m
    )
    return {
        "method": "UNIFORM_UPWARD_TRANSLATION_DIAGNOSTIC_ONLY",
        "max_cut_m": float(max_cut_m),
        "max_core_support_m": float(max_core_support_m),
        "max_shoulder_support_m": float(max_shoulder_support_m),
        "cut_cap_m": float(cut_cap_m),
        "support_cap_m": float(support_cap_m),
        "minimum_lift_for_cut_m": float(lower),
        "maximum_lift_for_support_m": float(upper),
        "bounds_overlap": lower <= upper,
        "height_change_applied": False,
        "source_height_verified": False,
        "road_admitted": False,
    }


def uniform_height_candidate(bounds):
    """Choose a deterministic local candidate inside measured shift bounds.

    The candidate is deliberately diagnostic.  A constant window translation
    preserves the already-inspected local grade, bank and facet normals, but it
    says nothing about the absolute road height or joins to adjacent windows.
    Callers must remeasure CUT/support using the translated geometry and must
    not author it from this receipt.
    """
    if not isinstance(bounds, dict) or bounds.get("method") != (
        "UNIFORM_UPWARD_TRANSLATION_DIAGNOSTIC_ONLY"
    ):
        raise ValueError("Measured uniform-height bounds required")
    lower = bounds.get("minimum_lift_for_cut_m")
    upper = bounds.get("maximum_lift_for_support_m")
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in (lower, upper)
    ):
        raise ValueError("Finite height-fit bounds required")
    overlap = lower <= upper
    return {
        "method": "BOUNDED_UNIFORM_WINDOW_PROFILE_CANDIDATE",
        "status": "CANDIDATE_REQUIRES_LOCAL_REMEASUREMENT"
        if overlap
        else "REJECT_INCOMPATIBLE_CUT_SUPPORT_BOUNDS",
        "candidate_lift_m": float((lower + upper) / 2) if overlap else None,
        "minimum_lift_for_cut_m": float(lower),
        "maximum_lift_for_support_m": float(upper),
        "bounds_overlap": overlap,
        "height_change_applied": False,
        "source_height_verified": False,
        "adjacent_joins_verified": False,
        "native_landscape_verified": False,
        "road_admitted": False,
    }
