"""Bounded visual traversal planning. Not physics playback or an FPS benchmark.

One light pass: 12 virtual seconds, 25 thumbnails, 161 cheap terrain queries
(including focus margins). At most one 4-second, 10 Hz detail window is selected.
Signals nominate inspection locations; they never grant visual acceptance.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SPEED_MPS = 10.0
SCOUT_SECONDS = 12.0
SCOUT_FPS = 2
DETAIL_FPS = 10
CONTEXT_SECONDS = 2.0
EYE_HEIGHT_CM = 160.0
ROAD_INTRUSION_M = 0.20  # Diagnostic trigger, NOT a terrain acceptance budget.


def finite(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number, not bool")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True)
class ProbeConfig:
    exact_sha: str
    mode: str = "light"
    center_m: float = 15415.0
    wide: bool = False

    def __post_init__(self):
        if not SHA40.fullmatch(self.exact_sha):
            raise ValueError("probe requires an exact lowercase SHA40")
        if self.mode not in {"light", "focus"}:
            raise ValueError("probe mode must be light or focus")
        center = finite(self.center_m, "center_m")
        if not 0 <= center <= 1_000_000:
            raise ValueError("center_m outside supported route range")
        if not isinstance(self.wide, bool):
            raise ValueError("wide must be bool")
        object.__setattr__(self, "center_m", center)

    def to_dict(self):
        return asdict(self)


def sample_plan(config, slice_start_m, slice_end_m):
    """Sample the ORIGINAL native spline before any transient slicing.

    Virtual t=6 is center_m. Reserve +/-2s around scout endpoints too, so a
    finding at either edge still gets the requested full context. Never clamp
    or move a requested frame silently to find a more attractive viewpoint.
    """
    lo = finite(slice_start_m, "slice_start_m")
    hi = finite(slice_end_m, "slice_end_m")
    ticks = range(-20, 141) if config.mode == "light" else range(40, 81)
    result = []
    for tick in ticks:
        seconds = tick / DETAIL_FPS
        station = config.center_m + (seconds - SCOUT_SECONDS / 2) * SPEED_MPS
        if not lo <= station <= hi:
            raise ValueError("requested traversal/context exceeds prepared corridor")
        result.append({"tick": tick, "time_s": seconds, "station_m": station})
    return result


def terrain_event(sample, ground_z_m):
    """Collision height is a locator, not render height or mesh acceptance."""
    if ground_z_m is None:
        return {**sample, "kind": "unmeasured_ground", "severity": None}
    ground = finite(ground_z_m, "ground_z_m")
    road = finite(sample["road_z_m"], "road_z_m")
    intrusion = ground - road
    if intrusion <= ROAD_INTRUSION_M:
        return None
    return {
        **sample,
        "kind": "landscape_collision_above_road",
        "ground_z_m": ground,
        "intrusion_m": intrusion,
        "severity": intrusion,
        "threshold_m": ROAD_INTRUSION_M,
        "render_defect_confirmed": False,
    }


def select_focus(events):
    """At most one hotspot; unknowns are reported, not interpreted as clean."""
    measured = [
        e for e in events if e["severity"] is not None and 0 <= e["tick"] <= 120
    ]
    if not measured:
        return None
    # Stable tie-break near center avoids arbitrary first-frame selection.
    return max(
        measured, key=lambda e: (e["severity"], -abs(e["tick"] - 60), -e["tick"])
    )


def frame_plan(config, samples, focus=None):
    by_tick = {row["tick"]: row for row in samples}
    output = []
    if config.mode == "light":
        output.extend(
            {**by_tick[t], "group": "scout", "size": [960, 540], "fps": 2, "fov": 76.0}
            for t in range(0, 121, 5)
        )
    center = 60 if config.mode == "focus" else (focus["tick"] if focus else None)
    if center is not None:
        groups = [("focus", 76.0)] + ([("wide", 105.0)] if config.wide else [])
        for group, fov in groups:
            for tick in range(center - 20, center + 21):
                if tick not in by_tick:
                    raise ValueError(
                        "focus context was not sampled from the original spline"
                    )
                output.append(
                    {
                        **by_tick[tick],
                        "group": group,
                        "size": [1920, 1080],
                        "fps": 10,
                        "fov": fov,
                    }
                )
    counts = {}
    for row in output:
        group = row["group"]
        index = counts.get(group, 0)
        row["index"] = index
        row["file"] = f"{group}/frame_{index:04d}.png"
        counts[group] = index + 1
    if len(output) > 107:
        raise ValueError("probe frame budget exceeded")
    return output


def performance_hotspots(rows, context, config):
    """Opt-in bridge for existing distance-tagged CSV, not time-axis guessing.

    Legacy Alpine Journey timings cannot be mapped onto SP638. A matching
    route/world/SHA sidecar is mandatory; rel_s from sector tests is NOT ride t.
    """
    if (
        context.get("exact_sha") != config.exact_sha
        or context.get("route_id") != "SP638-presentation"
    ):
        raise ValueError("performance source SHA/route mismatch")
    threshold = finite(context.get("frame_threshold_ms"), "frame_threshold_ms")
    if threshold <= 0:
        raise ValueError("frame_threshold_ms must be positive")
    result = []
    for row in rows:
        ms = finite(row["frame_ms"], "frame_ms")
        station = finite(row["distance_m"], "distance_m")
        if ms < 0 or station < 0:
            raise ValueError("performance frame time/distance must be nonnegative")
        if ms > threshold:
            result.append(
                {
                    "station_m": station,
                    "frame_ms": ms,
                    "source_rel_s": row.get("rel_s"),
                    "kind": "performance_locator_not_visual_failure",
                }
            )
    return sorted(result, key=lambda r: (-r["frame_ms"], r["station_m"]))
