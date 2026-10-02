"""Read-only BOB inspection of an inferred road-profile assessment.

Symptoms are model differences, never inferred wall dimensions or repair orders.
No input, terrain layer or verified-case memory is modified.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping

from scripts.worldgen.adaptive_terrain_solver import BOB_NAME


# Versioned inspection contract for the admitted 300 m Ma-2141 experiment.
# The producer shares these values; a candidate cannot choose its own thresholds.
STATION_STEP_M = 0.5
PROFILE_LENGTH_M = 300.0
REVIEW_DELTA_M = 0.5
REVIEW_GRADE = 0.25
REVIEW_CROSSFALL = 0.12
PLANE_TOLERANCE_M = 1e-6


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a finite numeric sample")
    if not math.isfinite(value):
        raise ValueError("Expected a finite numeric sample")
    return float(value)


def inspect_road_profile(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Group measured symptoms by contiguous chainage; never issue a road PASS."""
    report = {
        "schema_version": 2,
        "inspection_policy_id": "ma2141-profile-inspection-v2",
        "inspector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "architect": BOB_NAME,
        "role": "INSPECTOR_ONLY",
        "status": "INSPECTION_INCOMPLETE",
        "inspection_complete": False,
        "exact_sha": candidate.get("exact_sha")
        if isinstance(candidate, Mapping)
        else None,
        "provenance_check": "DECLARED_HASH_FORMAT_ONLY",
        "findings": [],
        "unverified_checks": [
            "source_identity_and_xy_preservation",
            "geographic_pavement_edges",
            "curve_and_edge_smoothness",
            "retaining_structures",
            "hairpin_branch_clearance",
            "continuous_contact",
            "native_contact_of_regularized_profile",
            "road_collision",
            "rider_visual",
            "bounded_ride",
            "performance",
        ],
        "earthworks_authoring_permitted": False,
        "geometry_repair_executed": False,
        "road_admitted": False,
        "eligible_for_learning": False,
        "next_actions": [
            "review flagged chainage against pinned imagery and dated ground-level references",
            "distinguish pavement footprint, source epoch, DTM representation and retaining support",
            "inspect curve/edge smoothness in plan view and from the rider camera",
            "preserve Base_DTM; this report is not a Road_Earthworks command",
        ],
    }
    try:
        if not isinstance(candidate, Mapping):
            raise ValueError("Expected a candidate mapping")
        hashes = {}
        for key, size in (
            ("exact_sha", 40),
            ("source_sha256", 64),
            ("profile_sha256", 64),
            ("heightmap_sha256", 64),
            ("imagery_sha256", 64),
            ("producer_sha256", 64),
        ):
            value = candidate[key]
            if (
                not isinstance(value, str)
                or len(value) != size
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise ValueError(f"Invalid {key}")
            hashes[key] = value
        if candidate.get("source_xy_preserved") is not True:
            raise ValueError("Source XY preservation is not established")
        parameters = candidate["parameters"]
        expected = {
            "station_step_m": STATION_STEP_M,
            "review_delta_m": REVIEW_DELTA_M,
            "review_grade": REVIEW_GRADE,
            "review_crossfall": REVIEW_CROSSFALL,
        }
        for key, value in expected.items():
            if _number(parameters[key]) != value:
                raise ValueError(f"Candidate conflicts with inspector policy: {key}")
        step = STATION_STEP_M
        thresholds = {
            "CUT_DIFFERENCE": REVIEW_DELTA_M,
            "FILL_DIFFERENCE": REVIEW_DELTA_M,
            "CROSSFALL": REVIEW_CROSSFALL,
            "GRADE": REVIEW_GRADE,
        }
        rows = candidate["stations"]
        if len(rows) != int(PROFILE_LENGTH_M / step) + 1:
            raise ValueError("Expected full 0-300 m coverage at 0.5 m spacing")
        stations, centers = [], []
        values = {key: [] for key in thresholds}
        for row in rows:
            stations.append(_number(row["station_m"]))
            declared_center = _number(row["candidate_center_m"])
            lateral = [_number(x) for x in row["lateral_m"]]
            ground = [_number(x) for x in row["native_ground_m"]]
            target = [_number(x) for x in row["candidate_ground_m"]]
            if len(lateral) != 25 or len(ground) != 25 or len(target) != 25:
                raise ValueError("Expected 25 full-width samples per station")
            if any(b <= a for a, b in zip(lateral, lateral[1:])):
                raise ValueError("Unordered transverse samples")
            delta = [_number(a - b) for a, b in zip(target, ground)]
            values["CUT_DIFFERENCE"].append(max(0.0, -min(delta)))
            values["FILL_DIFFERENCE"].append(max(0.0, max(delta)))
            span = _number(lateral[-1] - lateral[0])
            slope = _number(_number(target[-1] - target[0]) / span)
            center = _number(target[0] - slope * lateral[0])
            if any(
                abs(_number(z - _number(center + slope * offset))) > PLANE_TOLERANCE_M
                for offset, z in zip(lateral, target)
            ):
                raise ValueError(
                    "Candidate transverse section is not a consistent plane"
                )
            if abs(_number(declared_center - center)) > PLANE_TOLERANCE_M:
                raise ValueError("Declared center conflicts with transverse samples")
            centers.append(center)
            values["CROSSFALL"].append(abs(slope))
        if stations[0] != 0.0 or stations[-1] != PROFILE_LENGTH_M:
            raise ValueError("Expected full 0-300 m chainage domain")
        if any(
            not math.isclose(b - a, step, abs_tol=1e-7, rel_tol=0)
            for a, b in zip(stations, stations[1:])
        ):
            raise ValueError("Missing, duplicate or unordered chainage samples")
        values["GRADE"] = [abs(b - a) / step for a, b in zip(centers, centers[1:])]
        findings = []
        for kind, samples in values.items():
            samples = [_number(value) for value in samples]
            start = None
            for index in range(len(samples) + 1):
                flagged = index < len(samples) and samples[index] > thresholds[kind]
                if flagged and start is None:
                    start = index
                if not flagged and start is not None:
                    peak = max(range(start, index), key=lambda i: samples[i])
                    findings.append(
                        {
                            "kind": kind,
                            "start_station_m": stations[start],
                            "end_station_m": stations[
                                index if kind == "GRADE" else index - 1
                            ],
                            "peak_station_m": stations[peak],
                            "peak_value": samples[peak],
                            "unit": "ratio" if kind in ("GRADE", "CROSSFALL") else "m",
                            "review_trigger": thresholds[kind],
                            "sample_count": index - start,
                            "cause": "UNRESOLVED",
                        }
                    )
                    start = None
        report.update(
            {
                "status": "REVIEW_REQUIRED" if findings else "REVIEW_PENDING",
                "inspection_complete": True,
                "input_provenance": hashes,
                "station_count": len(stations),
                "findings": findings,
                "threshold_semantics": "experimental review triggers, not engineering acceptance limits",
                "measurement_semantics": "candidate-minus-DTM sample differences, not construction dimensions",
            }
        )
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        report["incomplete_reason"] = str(error)
    return report
