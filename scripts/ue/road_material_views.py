"""Deterministic whole-network material views from the authenticated TPP survey.

Select existing rider poses in both directions in every occupied 250 m road
cell, plus the retained comparison, Nudo, hairpin and elevation-extreme views.
This samples appearance across the current area; it does not claim exhaustive
pixel visibility, owner acceptance, source geography or road/physics authority.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re

from scripts.proof.sa_calobra_shoulder_contact import FRAME_IDS, SURVEY_SHA256

SURVEY = "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
CELL_SIZE_CM = 25000.0
MAX_BYTES = 1024 * 1024
MAX_FRAMES = 80
EXPECTED_WINDOWS = 185
EXPECTED_CELLS = 24
FRAME_PATTERN = re.compile(r"window-[0-9]{4}-(forward|reverse)-[0-9]{5}\Z")


def require(value, message):
    if not value:
        raise ValueError(message)


def _vector(raw):
    value = json.loads(raw)
    require(isinstance(value, list) and len(value) == 3
            and all(type(v) in (int, float) and math.isfinite(v) for v in value),
            "Invalid authenticated road view vector")
    return [float(v) for v in value]


def _read_rows(raw, required_sha256):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_BYTES
            and hashlib.sha256(raw).hexdigest() == required_sha256,
            "Whole-network camera source hash/size differs")
    result, names = [], set()
    for index, row in enumerate(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))):
        frame = row.get("frame_id", "")
        match = FRAME_PATTERN.fullmatch(frame)
        require(index < 4096 and match and frame not in names,
                "Invalid or duplicate survey frame ID")
        names.add(frame)
        direction = row["direction"]
        require(direction == match[1] and row["window_id"]
                and row["native_readiness_status"] == "NATIVE_LOADING_AND_MIPS_READY"
                and row["visual_review_status"] == "UNREVIEWED",
                "Survey frame provenance differs")
        vectors = {name: _vector(row[name]) for name in
                   ("road_position_cm", "camera_location_cm", "target_cm")}
        station = float(row["station_m"])
        require(math.isfinite(station) and station >= 0
                and float(row["fov_deg"]) == 76.0
                and int(row["width_px"]) == 1280 and int(row["height_px"]) == 720
                and math.dist(vectors["camera_location_cm"], vectors["target_cm"]) > 100
                and math.dist(vectors["road_position_cm"], vectors["camera_location_cm"]) < 2500,
                "Road view station/pose/FOV/resolution differs")
        require(all(0 <= v <= 201650.0 for v in vectors["road_position_cm"][:2]),
                "Road view lies outside the accepted current Landscape")
        result.append({"frame_id": frame, "window_id": row["window_id"],
                       "direction": direction, "station_m": station,
                       "fov_deg": 76.0, **vectors})
    return result


def select_network_views(raw, required_sha256=SURVEY_SHA256):
    """Return source-pinned poses and explicit spatial-sampling evidence."""
    try:
        rows = _read_rows(raw, required_sha256)
        windows, pairs, cells = {}, {}, {}
        for row in rows:
            window = row["window_id"]
            windows.setdefault(window, []).append(row)
            key = (window, row["station_m"])
            pair = pairs.setdefault(key, {})
            require(row["direction"] not in pair, "Ambiguous directional survey pose")
            pair[row["direction"]] = row
        require(len(windows) == EXPECTED_WINDOWS, "Incomplete frozen road-window inventory")
        for key, pair in pairs.items():
            require(set(pair) == {"forward", "reverse"}, "Missing paired travel direction")
            point = pair["forward"]["road_position_cm"]
            require(point == pair["reverse"]["road_position_cm"],
                    "Paired road station coordinates differ")
            cell = tuple(math.floor(v / CELL_SIZE_CM) for v in point[:2])
            cells.setdefault(cell, []).append(key)
        require(len(cells) == EXPECTED_CELLS, "Occupied road-cell inventory differs")
        window_limits = {name: (min(r["station_m"] for r in group),
                                max(r["station_m"] for r in group))
                         for name, group in windows.items()}
        chosen = {}

        def add_pair(key):
            for row in pairs[key].values():
                chosen[row["frame_id"]] = row

        for cell, keys in sorted(cells.items()):
            centre = tuple((v + 0.5) * CELL_SIZE_CM for v in cell)

            def score(key):
                point = pairs[key]["forward"]["road_position_cm"]
                endpoint = key[1] in window_limits[key[0]]
                return (endpoint, math.dist(point[:2], centre), key)

            add_pair(min(keys, key=score))
        by_id = {row["frame_id"]: row for row in rows}
        require(set(FRAME_IDS) <= set(by_id), "Original four comparison views are missing")
        for frame_id in FRAME_IDS:
            chosen[frame_id] = by_id[frame_id]
        for name, fractions in (("nudo-0", (0.5,)), ("nudo-1", (0.5,)),
                                ("nudo-2", (0.5,)),
                                ("accepted-hairpin", (0.25, 0.5, 0.75))):
            require(name in windows, "Exceptional road source has no retained survey views")
            first, last = window_limits[name]
            keys = [key for key in pairs if key[0] == name]
            for fraction in fractions:
                target = first + (last - first) * fraction
                add_pair(min(keys, key=lambda key: (abs(key[1] - target), key)))
        for extreme in (min, max):
            key = extreme(pairs, key=lambda key:
                          (pairs[key]["forward"]["road_position_cm"][2], key))
            add_pair(key)
        require(48 <= len(chosen) <= MAX_FRAMES, "Whole-network review exceeds its frame budget")
        order = list(FRAME_IDS) + sorted(set(chosen) - set(FRAME_IDS))
        frames = [chosen[name] for name in order]
        represented = {}
        for row in frames:
            cell = tuple(math.floor(v / CELL_SIZE_CM) for v in row["road_position_cm"][:2])
            represented.setdefault(cell, set()).add(row["direction"])
        require(set(represented) == set(cells)
                and all(v == {"forward", "reverse"} for v in represented.values()),
                "A road cell lacks both travel directions")
        return {"schema_version": 1, "survey_sha256": required_sha256,
                "sampling": "all_occupied_250m_road_cells_both_directions_plus_exceptions",
                "cell_size_m": CELL_SIZE_CM / 100,
                "source_window_count": len(windows),
                "occupied_road_cells": [list(c) for c in sorted(cells)],
                "represented_window_count": len({r["window_id"] for r in frames}),
                "frame_count": len(frames), "frames": frames,
                "exhaustive_road_pixel_visibility": False,
                "whole_area_owner_accepted": False,
                "performance_pass": False}
    except (KeyError, TypeError, OverflowError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid authenticated whole-network camera survey") from exc


def current_view_plan(root=None):
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    return select_network_views((root / SURVEY).read_bytes())


if __name__ == "__main__":
    print(json.dumps(current_view_plan(), sort_keys=True, allow_nan=False))
