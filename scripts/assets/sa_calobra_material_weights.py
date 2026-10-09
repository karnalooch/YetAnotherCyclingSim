"""Reference contract for #363 appearance weights; never changes source masks."""

import math

ROLES = ("DryGrass", "ForestLitter", "ExposedRock", "DryMineral", "Scree")


def compose_weights(
    rgba,
    normal_z=1.0,
    *,
    exponent=1.0,
    slope_strength=0.0,
    slope_start_degrees=65.0,
    slope_end_degrees=85.0,
):
    """Normalize base roles, apply bounded rock policy, then retain overlay alpha.

    Defaults preserve source coverage. A means artistic dry channel, not sample
    availability. Projection normals and final detail normals are not inputs.
    """
    if len(rgba) != 4 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in rgba):
        raise ValueError("Expected four finite unit-range mask channels")
    if not math.isfinite(normal_z) or not -1 <= normal_z <= 1:
        raise ValueError("Expected normalized base-surface Z")
    if sum(rgba[:3]) > 1 + 1e-6:
        raise ValueError("RGB mask coverage exceeds one")
    if not math.isfinite(exponent) or not 1 <= exponent <= 2:
        raise ValueError("Blend exponent outside admitted range")
    if not math.isfinite(slope_strength) or not 0 <= slope_strength <= 1:
        raise ValueError("Slope strength outside unit range")
    if not 0 <= slope_start_degrees < slope_end_degrees <= 90:
        raise ValueError("Invalid slope transition interval")
    r, g, b, overlay = rgba
    base = [r, g, b, max(0.0, 1 - r - g - b)]
    base = [v**exponent for v in base]
    total = sum(base)
    base = [v / total for v in base]
    start = math.cos(math.radians(slope_start_degrees))
    end = math.cos(math.radians(slope_end_degrees))
    t = max(0.0, min(1.0, (start - abs(normal_z)) / (start - end)))
    rock = t * t * (3 - 2 * t) * slope_strength
    base = [v * (1 - rock) for v in base]
    base[2] += rock
    return dict(zip(ROLES, [v * (1 - overlay) for v in base] + [overlay], strict=True))
