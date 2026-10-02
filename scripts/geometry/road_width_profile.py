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


def boundary_width_profile(source_profile, rows):
    """Reparameterize observations onto sampled boundary distance in metres.

    Uneven source keys/native cubic handles must not introduce width-rate kinks.
    This is presentation distance only; canonical source/physics stay separate.
    """
    validate_width_profile(source_profile)
    distances = [0.0]
    stations = {}
    for i, row in enumerate(rows):
        s = row["station_m"]
        if s in stations or (i and s <= rows[i - 1]["station_m"]):
            raise ValueError("Unordered boundary distance samples")
        if i:
            step = math.dist(rows[i - 1]["anchor_xy_m"], row["anchor_xy_m"])
            if not math.isfinite(step) or step <= 0:
                raise ValueError("Boundary distance stops")
            distances.append(distances[-1] + step)
        stations[s] = distances[i]
    samples = []
    for observation in source_profile["samples"]:
        if observation["station_m"] not in stations:
            raise ValueError("Width observation lacks a boundary-distance sample")
        samples.append(dict(observation, station_m=stations[observation["station_m"]]))
    return dict(
        source_profile,
        samples=samples,
        parameterization="sampled reference-boundary distance",
    ), distances
