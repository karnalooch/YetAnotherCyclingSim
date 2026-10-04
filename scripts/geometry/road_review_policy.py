"""Owner policy: measurable road deviations remain visible for human review."""

import math

WIDTH_TOLERANCE_FRACTION = 0.05


def review_surface(sections):
    from scripts.geometry.network_pavement import surface_inspection

    try:
        return surface_inspection(sections)
    except ValueError as exc:
        return {
            "status": "REVIEW_REQUIRED",
            "reason": str(exc),
            "engineering_admitted": False,
        }


def width_review(sections, connection=False):
    """Apply +/-5% to the explicit network/accepted-approach base envelope."""
    lower = 5.0 * (1 - WIDTH_TOLERANCE_FRACTION)
    upper = (5.5 if connection else 5.0) * (1 + WIDTH_TOLERANCE_FRACTION)
    widths = [math.dist(r[0][:2], r[-1][:2]) for r in sections]
    return {
        "minimum_m": min(widths),
        "maximum_m": max(widths),
        "allowed_minimum_m": lower,
        "allowed_maximum_m": upper,
        "tolerance_fraction": WIDTH_TOLERANCE_FRACTION,
        "status": "PASS"
        if min(widths) >= lower - 1e-8 and max(widths) <= upper + 1e-8
        else "REVIEW_REQUIRED",
    }
