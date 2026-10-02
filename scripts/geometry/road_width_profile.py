"""Explicit horizontal pavement widths shared by road authoring and admission.

Lengths are metres; stations refer to source chainage, never physics distance.
Evidence remains attached to each profile. Interpolation cannot add widening.
"""

from __future__ import annotations

import math
from itertools import pairwise


def validate_width_profile(profile):
    samples = profile.get("samples", [])
    if not profile.get("evidence") or len(samples) < 2:
        raise ValueError("Width profile needs observations and evidence")
    previous = -math.inf
    for sample in samples:
        station, left, right = (sample[k] for k in ("station_m", "left_m", "right_m"))
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            for v in (station, left, right)
        ):
            raise ValueError("Nonfinite width profile")
        if station <= previous or min(left, right) <= 0 or not 2 <= left + right <= 12:
            raise ValueError("Unordered or invalid width profile")
        previous = station
    return samples


def width_at(profile, station):
    samples = validate_width_profile(profile)
    if (
        not math.isfinite(station)
        or not samples[0]["station_m"] <= station <= samples[-1]["station_m"]
    ):
        raise ValueError("Width station outside observed domain")
    for first, second in pairwise(samples):
        if station <= second["station_m"]:
            u = (station - first["station_m"]) / (
                second["station_m"] - first["station_m"]
            )
            q = u**3 * (10 + u * (-15 + 6 * u))
            return tuple(
                first[k] + q * (second[k] - first[k]) for k in ("left_m", "right_m")
            )
    raise ValueError("Incomplete width domain")


def offset_edges(center, tangent, widths):
    length = math.hypot(*tangent)
    if not math.isfinite(length) or length <= 1e-9:
        raise ValueError("Road axis stops; cannot construct a normal")
    normal = [-tangent[1] / length, tangent[0] / length]
    left, right = widths
    return [
        [center[k] - left * normal[k] for k in range(2)],
        [center[k] + right * normal[k] for k in range(2)],
    ]
