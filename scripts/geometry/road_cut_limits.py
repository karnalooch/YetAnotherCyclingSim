"""Bound deeper preview cuts to evidence-marked cliff spans, never the route."""

from scripts.geometry.curved_road_plan import ANCHOR_RECIPE


def cut_limits(plan, policy):
    ordinary = float(policy["strategies"]["native_blend"]["max_ground_adjustment_m"])
    spans = []
    maximum = ordinary
    if plan.get("recipe") == ANCHOR_RECIPE:
        for span in plan["controlled_width"]["edge_constraint"]["terrain_spans"]:
            if "CLIFF" in span["roles"] and "MOUNTAIN" in span["roles"]:
                spans.append([span["start_station_m"], span["end_station_m"]])
        if spans:
            maximum = min(
                float(policy["strategies"]["retaining_or_cliff"]["max_ground_adjustment_m"]),
                float(policy["thresholds"]["retaining_cut_fill_m"]),
            )
    return {"ordinary_m": ordinary, "cliff_m": maximum, "cliff_spans_m": spans}


def station_cut_limit(limits, station):
    if any(start <= station < end for start, end in limits["cliff_spans_m"]):
        return limits["cliff_m"]
    return limits["ordinary_m"]


def inspection_within_cut_limits(inspection, limits):
    rows = inspection.get("station_summaries", [])
    return bool(rows) and all(
        row["max_cut_required_m"] <= station_cut_limit(limits, row["station_m"])
        for row in rows
    )


def receipt_within_cut_limits(plan, receipt, policy):
    limits = cut_limits(plan, policy)
    depth = receipt.get("patch_max_cut_m", -1.0)
    return (
        receipt.get("patch_cut_limits") == limits
        and 0.0 < depth <= limits["cliff_m"] + 1e-6
    )


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    from scripts.geometry.curved_road_plan import profile_plan_valid

    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    profile = json.loads((args.artifact_root / "ma2141-profile-candidate.json").read_text(encoding="utf-8"))
    receipt = json.loads((args.artifact_root / "bob-road-earthworks-cut-proof.json").read_text(encoding="utf-8"))
    policy = json.loads((Path(__file__).resolve().parents[2] / "worldgen/terrain/adaptive_terrain_policy.json").read_text(encoding="utf-8"))
    if (
        not profile_plan_valid(profile)
        or receipt.get("exact_sha") != profile.get("exact_sha")
        or not receipt_within_cut_limits(profile["presentation_plan"], receipt, policy)
    ):
        raise SystemExit("CUT receipt spatial policy mismatch")
    print("CUT receipt spatial policy: PASS")
