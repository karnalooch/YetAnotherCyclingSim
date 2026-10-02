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
