"""Deterministic, presentation-only TPP inspection of the frozen road windows.

The saved pavement has no riding collision. This planner reads the accepted
output bytes and never executes a road builder, joins unknown intervals, or
uses its derived centreline as route/physics authority. All input geometry is
in metres; Unreal camera and sphere positions are returned in centimetres.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re

FROZEN_SHA = "c5573b3cf545c51ce83ad1fb0a5ca3111f5ad7f6"
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
REPOSITORY_RECIPE = (
    Path(__file__).resolve().parents[2]
    / "worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json"
)
CONTRACT = "sa_calobra_bidirectional_tpp_survey_v1"


def _finite(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be finite, not bool")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class SurveyConfig:
    exact_sha: str
    spacing_m: float = 20.0
    trailing_m: float = 5.0
    camera_height_m: float = 2.2
    lookahead_m: float = 8.0
    sphere_radius_m: float = 0.4
    fov_deg: float = 76.0
    max_frames: int = 4096

    def __post_init__(self):
        if not isinstance(self.exact_sha, str) or not SHA40.fullmatch(self.exact_sha):
            raise ValueError("survey requires an exact lowercase SHA40")
        for name in (
            "spacing_m", "trailing_m", "camera_height_m", "lookahead_m", "sphere_radius_m"
        ):
            value = _finite(getattr(self, name), name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, value)
        fov = _finite(self.fov_deg, "fov_deg")
        if not 1 <= fov < 179:
            raise ValueError("fov_deg outside [1,179)")
        object.__setattr__(self, "fov_deg", fov)
        if type(self.max_frames) is not int or not 4 <= self.max_frames <= 4096:
            raise ValueError("max_frames must be an integer in [4,4096]")


def load_frozen_windows(frozen_root, *, recipe_path=None, expected_window_count=184):
    """Verify every trusted recipe input and read the checkpoint's road sections.

    ``recipe_path`` defaults to the tracked recipe, never an unverified manifest
    inside the input directory. An explicit recipe is useful for isolated tests.
    The additional hairpin receives the same 4 cm pavement lift as the saved
    checkpoint. This operation does not execute the retained support consumers.
    """
    root = Path(frozen_root).resolve()
    recipe_path = Path(recipe_path) if recipe_path is not None else REPOSITORY_RECIPE
    recipe = json.loads(recipe_path.read_text(encoding="utf-8-sig"))
    if recipe.get("accepted_sha") != FROZEN_SHA or recipe.get("owner_artifact_exception") is not True:
        raise ValueError("No owner-authorized frozen road artifact identity")
    if type(expected_window_count) is not int or expected_window_count < 1:
        raise ValueError("expected_window_count must be a positive integer")
    listed = set()
    for item in recipe["inputs"]:
        name = item["path"]
        relative = PurePosixPath(name)
        if (
            not name or "\\" in name or ":" in name or relative.is_absolute()
            or ".." in relative.parts or name in listed
        ):
            raise ValueError("Unsafe/duplicate frozen source path: " + name)
        listed.add(name)
        path = root.joinpath(*relative.parts).resolve()
        if not path.is_relative_to(root):
            raise ValueError("Frozen source escapes its root: " + name)
        if path.stat().st_size != item["size_bytes"] or _digest(path) != item["sha256"]:
            raise ValueError("Frozen source hash/size mismatch: " + name)
    required = {"Network/network.json", "network-native-proof.json", "ma2141-profile-candidate.json"}
    if not required <= listed:
        raise ValueError("Frozen road documents are missing from the trusted recipe")
    local_recipe = root / "source-recipe.json"
    if local_recipe.exists() and json.loads(local_recipe.read_text(encoding="utf-8-sig")) != recipe:
        raise ValueError("Local frozen recipe differs from the trusted repository recipe")

    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8-sig"))

    network, native, profile = (read(name) for name in (
        "Network/network.json", "network-native-proof.json", "ma2141-profile-candidate.json"
    ))
    if any(report.get("exact_sha") != FROZEN_SHA for report in (network, native, profile)):
        raise ValueError("Mixed frozen road revisions")
    native_ids = [row["id"] for row in native["windows"]]
    if len(set(native_ids)) != len(native_ids) or len(native_ids) != expected_window_count:
        raise ValueError("Duplicate/incomplete native construction inventory")
    if native.get("construction_window_count") != expected_window_count:
        raise ValueError("Native construction window count mismatch")
    native_ids = set(native_ids)
    windows = [
        row for row in network["approved"] + network["owner_reviewed"] + network["nudo"]["windows"]
        if row["id"] in native_ids
    ]
    if len(windows) != expected_window_count or {row["id"] for row in windows} != native_ids:
        raise ValueError("Native constructed geometry missing/duplicated")
    if "accepted-hairpin" in native_ids:
        raise ValueError("Frozen window id collides with the checkpoint hairpin")
    hairpin = []
    for row in profile["stations"]:
        hairpin.append([
            [xy[0], xy[1], _finite(z, "hairpin height") + 0.04]
            for xy, z in zip(row["xy_local_m"], row["candidate_ground_m"], strict=True)
        ])
    windows.append({"id": "accepted-hairpin", "sections": hairpin})
    return {
        "source_identity": {
            "accepted_road_sha": FROZEN_SHA,
            "recipe_sha256": _digest(recipe_path),
            "source_run_id": recipe.get("source_run_id"),
            "verified_input_count": len(listed),
            "network_window_count": expected_window_count,
            "checkpoint_hairpin_count": 1,
            "hairpin_pavement_lift_m": 0.04,
            "geometry_consumers_executed": False,
            "admission": recipe.get("admission", "Owner frozen visual output only"),
        },
        "windows": windows,
    }


def _centreline(window):
    rows = window["sections"]
    if len(rows) < 2:
        raise ValueError("Window requires at least two cross sections")
    width = len(rows[0])
    if width < 2:
        raise ValueError("Cross section requires at least two pavement points")
    centres = []
    duplicates = 0
    for row in rows:
        if len(row) != width or any(len(point) != 3 for point in row):
            raise ValueError("Incomplete pavement cross sections")
        centre = tuple(math.fsum(_finite(p[axis], "pavement coordinate") for p in row) / width
                       for axis in range(3))
        if centres and math.dist(centres[-1], centre) <= 1e-9:
            duplicates += 1
        else:
            centres.append(centre)
    if len(centres) < 2:
        raise ValueError("Window centreline has zero length")
    stations = [0.0]
    for a, b in zip(centres, centres[1:]):
        if math.hypot(b[0] - a[0], b[1] - a[1]) <= 1e-9:
            raise ValueError("Window has a vertical/undefined horizontal tangent")
        stations.append(_finite(stations[-1] + math.dist(a, b), "window arc length"))
    return centres, stations, duplicates


def _pose(centres, stations, station):
    index = min(bisect_right(stations, station) - 1, len(centres) - 2)
    a, b = centres[index:index + 2]
    span = stations[index + 1] - stations[index]
    fraction = (station - stations[index]) / span
    point = tuple(a[i] + fraction * (b[i] - a[i]) for i in range(3))
    # Preserve endpoint source coordinates exactly, avoiding arithmetic drift.
    if station == 0:
        point = centres[0]
    elif station == stations[-1]:
        point = centres[-1]
    tangent = tuple((b[i] - a[i]) / span for i in range(3))
    return point, tangent


def build_survey_plan(windows, config, *, source_identity=None):
    """Return endpoint-inclusive forward/reverse poses for each independent window.

    ``station_m`` is the derived 3D centreline distance inside this window, not
    canonical route chainage. No interval connection is inferred from a small
    endpoint gap. Camera offsets use the same local tangent in both directions.
    """
    windows = list(windows)
    if not windows or any(not isinstance(w.get("id"), str) or not w["id"] for w in windows):
        raise ValueError("Survey requires named frozen windows")
    if len({w["id"] for w in windows}) != len(windows):
        raise ValueError("Duplicate frozen window id")
    windows.sort(key=lambda row: row["id"])
    prepared, summaries = [], []
    total = 0
    for index, window in enumerate(windows):
        centres, stations, duplicates = _centreline(window)
        length = stations[-1]
        ratio = length / config.spacing_m
        if not math.isfinite(ratio) or ratio + 1 > config.max_frames / 2:
            raise ValueError("Survey exceeds frame budget before sample allocation")
        intervals = math.ceil(ratio)
        count = intervals + 1
        total += 2 * count
        if total > config.max_frames:
            raise ValueError(f"Survey exceeds frame budget ({total}>{config.max_frames})")
        sample_stations = [length * i / intervals for i in range(intervals)] + [length]
        prepared.append((index, window["id"], centres, stations, sample_stations))
        summary = {
            "window_id": window["id"], "length_m": length,
            "samples_per_direction": count, "max_spacing_m": length / intervals,
            "start_cm": [v * 100 for v in centres[0]],
            "end_cm": [v * 100 for v in centres[-1]],
            "cross_section_count": len(window["sections"]),
            "duplicate_centre_sections_removed": duplicates,
            "connection_to_other_windows": "UNVERIFIED",
        }
        for name in ("station_start_m", "station_end_m"):
            if name in window:
                summary["source_" + name] = _finite(window[name], name)
        summaries.append(summary)
    frames = []
    for direction in ("forward", "reverse"):
        pass_windows = prepared if direction == "forward" else reversed(prepared)
        sign = 1 if direction == "forward" else -1
        for index, window_id, centres, stations, sample_stations in pass_windows:
            distances = sample_stations if sign == 1 else reversed(sample_stations)
            for sample_index, station in enumerate(distances):
                road, forward = _pose(centres, stations, station)
                forward = tuple(sign * v for v in forward)
                ball = tuple(road[i] + (config.sphere_radius_m if i == 2 else 0) for i in range(3))
                camera = tuple(road[i] - config.trailing_m * forward[i]
                               + (config.camera_height_m if i == 2 else 0) for i in range(3))
                target = tuple(ball[i] + config.lookahead_m * forward[i] for i in range(3))
                frame_id = f"window-{index:04d}-{direction}-{sample_index:05d}"
                frames.append({
                    "frame_id": frame_id, "index": len(frames),
                    "window_id": window_id, "direction": direction,
                    "sample_index": sample_index, "station_m": station,
                    "distance_along_window_m": station,
                    "travel_distance_m": station if sign == 1 else stations[-1] - station,
                    "road_position_cm": [v * 100 for v in road],
                    "ball_location_cm": [v * 100 for v in ball],
                    "road_forward_unit": list(forward),
                    "camera_location_cm": [v * 100 for v in camera],
                    "target_cm": [v * 100 for v in target],
                    "fov_deg": config.fov_deg,
                    "sphere_radius_cm": config.sphere_radius_m * 100,
                    "file": f"frames/{frame_id}.png",
                })
    transitions = [{
        "from_window_id": a["window_id"], "to_window_id": b["window_id"],
        "endpoint_gap_m": math.dist(a["end_cm"], b["start_cm"]) / 100,
        "continuity": "UNVERIFIED", "captured_connection": False,
        "ordering": "lexical_window_id_for_replay_only",
    } for a, b in zip(summaries, summaries[1:])]
    result = {
        "schema_version": 1, "contract": CONTRACT, "exact_sha": config.exact_sha,
        "presentation_only": True, "physics_playback": False,
        "continuous_route": False, "camera_collision_adjusted": False,
        "route_or_terrain_modified": False,
        "chainage_policy": "per_window_derived_3d_arc_length_not_route_physics",
        "scope": "all_verified_frozen_windows_both_directions_not_whole_landscape_acceptance",
        "source_identity": dict(source_identity or {}), "config": asdict(config),
        "frame_count": len(frames), "windows": summaries,
        "transitions": transitions, "frames": frames,
    }
    # Catch numerical overflow and non-JSON metadata before an expensive capture.
    json.dumps(result, allow_nan=False)
    return result
