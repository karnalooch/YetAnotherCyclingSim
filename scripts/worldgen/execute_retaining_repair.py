"""Execute BOB's bounded shoulder-side repair through the existing mesh path."""
from __future__ import annotations

from scripts.geometry.retaining_repair import replace_shoulder_ground, sample_triangle_grid
from scripts.geometry.sp638_local_corridor import Vec3


def execute_retaining_repair(*, mesh, report, policy, xs, ys, native_heights,
                            constrained_heights, corridor_mesh, profiles,
                            corridor_origin, terrain_origin):
    config = policy["retaining_repair_rule"]["executor"]
    threshold = float(policy["thresholds"]["retaining_cut_fill_m"])
    padding = int(config["tie_in_stations"])
    width = corridor_mesh.cross_section_point_count
    intervals = []
    by_index = {r["station_index"]: r for r in report["decisions"]}
    for side in ("left", "right"):
        flagged = []
        for index in report["escalation_station_indices"]:
            r = by_index[index]
            f = r["features"]
            if (f["nearest_branch_xy_m"] is not None
                    and f["nearest_branch_xy_m"] <= policy["thresholds"]["stacked_branch_xy_m"]
                    and f["nearest_branch_z_separation_m"] is not None
                    and f["nearest_branch_z_separation_m"] >= policy["thresholds"]["stacked_branch_z_m"]):
                raise ValueError("stacked-branch escalation is unsupported by the local retaining executor")
            if max(abs(v) for role,v in r["signed_edge_delta_m"].items() if role.startswith(side+"_")) >= threshold:
                flagged.append(index)
        for index in flagged:
            lo,hi = max(0,index-padding),min(corridor_mesh.station_count-1,index+padding)
            if lo == 0 or hi == corridor_mesh.station_count-1:
                raise ValueError("retaining repair needs measured tie-ins on both ends")
            if intervals and intervals[-1][0] == side and lo <= intervals[-1][2]:
                intervals[-1] = (side,intervals[-1][1],max(hi,intervals[-1][2]))
            else:
                intervals.append((side,lo,hi))
    if report["escalation_station_indices"] and not intervals:
        raise ValueError("escalation has no supported cut/fill side")

    segments = []
    for side,lo,hi in intervals:
        if (hi-lo)*report["measurement_contract"]["sample_step_m"] > config["max_region_length_m"]:
            raise ValueError("retaining region exceeds the bounded executor scope")
        def point(index,role):
            offsets = [i for i,p in enumerate(profiles[index]) if p.role == side+"_"+role]
            if len(offsets) != 1:
                raise ValueError("retaining repair requires one shoulder and tie per side")
            p = corridor_mesh.vertices[index*width+offsets[0]]
            return Vec3(p.x+corridor_origin.x-terrain_origin.x,
                        p.y+corridor_origin.y-terrain_origin.y,
                        p.z+corridor_origin.z-terrain_origin.z)
        for index in range(lo,hi):
            # A deterministic taper occupies the measured tie-in stations.
            strength = lambda i: min(1.0,(i-lo)/padding,(hi-i)/padding)
            segments.append({"inner_start":point(index,"shoulder"),
                             "inner_end":point(index+1,"shoulder"),
                             "outer_start":point(index,"tie"),
                             "outer_end":point(index+1,"tie"),
                             "start_strength":strength(index),"end_strength":strength(index+1)})
    def sample(heights,x,y):
        return sample_triangle_grid(xs,ys,heights,x+terrain_origin.x,y+terrain_origin.y)-terrain_origin.z
    result = replace_shoulder_ground(mesh,segments,
        sample_constrained=lambda x,y:sample(constrained_heights,x,y),
        sample_native=lambda x,y:sample(native_heights,x,y),
        wall_fraction=float(config["wall_fraction"]))
    if intervals and (result.vertical_face_triangle_count == 0 or result.replaced_triangle_count == 0):
        raise ValueError("retaining executor produced no replacement or vertical face")
    if result.max_face_height_m > config["max_face_height_m"]:
        raise ValueError("retaining face exceeds the admitted candidate height")
    evidence = {"status":"GENERATED_PENDING_VALIDATION", "geometry_applied":bool(intervals),
                "rule_id":policy["retaining_repair_rule"]["rule_id"],
                "regions":[{"side":s,"start_station_index":lo,"end_station_index":hi} for s,lo,hi in intervals],
                "segment_count":result.segment_count,
                "replaced_triangle_count":result.replaced_triangle_count,
                "vertical_face_triangle_count":result.vertical_face_triangle_count,
                "max_face_height_m":result.max_face_height_m,
                "ground_replacement":True,"canonical_road_xy_modified":False,
                "technical_acceptance":"PENDING","visual_acceptance":"PENDING_HUMAN_REVIEW",
                "learning_case_promoted":False}
    return result.mesh,evidence
