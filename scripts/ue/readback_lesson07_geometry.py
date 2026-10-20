import json
import math
import os
from pathlib import Path
import unreal

LEVEL_PATH = "/Game/Generated/YACS/Lesson07_Unified/L_SaCalobra_Lesson07"
REPORT_PATH = Path(os.environ.get(
    "YACS_LESSON07_READBACK_PATH",
    "D:/yacs/work/lesson07-unified-20261019/ue_landscape_geometry_readback.json",
))

def on_source_grid(x_m, z_m):
    ax = (x_m + 3999.75) / 0.5
    az = (3999.75 - z_m) / 0.5
    return abs(ax - round(ax)) < 1e-5 and abs(az - round(az)) < 1e-5

def actor_height_step_cm(scale_z):
    if not math.isfinite(scale_z) or scale_z <= 0:
        raise ValueError("Invalid Landscape Scale.Z")
    return float(scale_z) / 128.0

def read_component_int(component, prop_name):
    # Missing UPROPERTY fields are UNKNOWN, not made up from assumed layout.
    try:
        return int(component.get_editor_property(prop_name))
    except Exception:
        return None


def actual_component_settings(components):
    properties = ("component_size_quads", "subsection_size_quads",
                  "num_subsections", "section_base_x", "section_base_y")
    observed = {}
    for prop in properties:
        values = [read_component_int(comp, prop) for comp in components]
        observed[prop] = {
            "values": sorted({v for v in values if v is not None}),
            "read_count": len(values) - values.count(None),
            "total": len(values),
            "complete": bool(values) and None not in values,
        }
    return observed


def main():
    world = unreal.EditorLoadingAndSavingUtils.load_map(LEVEL_PATH)
    if not world:
        raise RuntimeError(f"Failed to load map: {LEVEL_PATH}")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = actor_subsystem.get_all_level_actors()

    landscapes = [a for a in actors if isinstance(a, unreal.LandscapeProxy)]
    print(f"Found {len(landscapes)} landscape actors in level.")

    landscape_data = []
    total_components = 0

    for la in sorted(landscapes, key=lambda x: x.get_name()):
        name = la.get_name()
        loc = la.get_actor_location()
        scale = la.get_actor_scale3d()
        origin, extent = la.get_actor_bounds(False)
        comps = la.get_components_by_class(unreal.LandscapeComponent)
        num_comps = len(comps)
        total_components += num_comps

        mat = la.get_editor_property("landscape_material")
        mat_name = mat.get_path_name() if mat else None

        info = {
            "name": name,
            "class": la.get_class().get_name(),
            "location_cm": [loc.x, loc.y, loc.z],
            "scale": [scale.x, scale.y, scale.z],
            "bounds_origin_cm": [origin.x, origin.y, origin.z],
            "bounds_extent_cm": [extent.x, extent.y, extent.z],
            "component_count": num_comps,
            "actual_component_properties": actual_component_settings(comps),
            "expected_design_not_observed": {
                "component_grid": "32x32", "section_quads": 127,
                "num_subsections": 2, "component_quads": 254,
                "tile_quads": 8128, "tile_vertices": 8129,
            },
            "assigned_material": mat_name,
        }
        landscape_data.append(info)
        print(f"  Landscape: {name}, comps={num_comps}, mat={mat_name}")

    query_points = [
        {"name": "Puig Major Summit", "x_ue": -128375.0, "y_ue": 349525.0, "x_h": -1283.75, "z_h": 3495.25, "expected_h_m": 1437.16},
        {"name": "Sa Calobra Cove Beach", "x_ue": 47000.0, "y_ue": -106000.0, "x_h": 470.0, "z_h": -1060.0, "expected_h_m": 10.34},
        {"name": "Inland Center (0, 0)", "x_ue": 0.0, "y_ue": 0.0, "x_h": 0.0, "z_h": 0.0, "expected_h_m": 473.51},
        {"name": "Scree Cluster 1 Centroid", "x_ue": -250278.0, "y_ue": 184595.0, "x_h": -2502.78, "z_h": 1845.95, "expected_h_m": 460.95},
    ]

    scales = {a["name"]: float(a["scale"][2]) for a in landscape_data}
    sampled_points = []
    problems = []
    rounded_reference_warnings = []
    for qp in query_points:
        start = unreal.Vector(qp["x_ue"], qp["y_ue"], 200000.0)
        end = unreal.Vector(qp["x_ue"], qp["y_ue"], -50000.0)
        hit = unreal.SystemLibrary.line_trace_single(
            world,
            start,
            end,
            unreal.TraceTypeQuery.TRACE_TYPE_QUERY1,
            True,
            [],
            unreal.DrawDebugTrace.NONE,
            True
        )
        d = hit.to_dict()
        if d.get("blocking_hit"):
            impact = d["impact_point"]
            hit_z_cm = float(impact.z)
            hit_z_m = hit_z_cm / 100.0
            actor_hit = d["hit_actor"].get_name() if d.get("hit_actor") else None
            sampled = dict(qp)
            sampled["hit_z_cm"] = hit_z_cm
            sampled["hit_z_m"] = hit_z_m
            sampled["hit_actor"] = actor_hit
            if qp["expected_h_m"] is not None:
                delta_m = hit_z_m - qp["expected_h_m"]
                delta_cm = delta_m * 100.0
                sampled["delta_m"] = delta_m
                sampled["delta_cm"] = delta_cm
                step_cm = actor_height_step_cm(scales[actor_hit]) if actor_hit in scales else None
                sampled["actor_quantization_step_cm"] = step_cm
                sampled["on_source_grid"] = on_source_grid(qp["x_h"], qp["z_h"])
                sampled["quantization_steps"] = delta_cm / step_cm if step_cm else None
                if step_cm is None:
                    problems.append(f"{qp['name']}: hit unexpected actor {actor_hit}")
                elif sampled["on_source_grid"] and abs(delta_cm) > step_cm / 2.0 + 0.1:
                    rounded_reference_warnings.append(
                        f"{qp['name']}: {delta_cm:.2f}cm differs from a rounded historical "
                        f"reference, not an authoritative source voxel/interpolation."
                    )
                print(f"  Hit {qp['name']}: {hit_z_m:.3f}m, rounded ref={qp['expected_h_m']}, delta={delta_cm:.2f}cm, actor={actor_hit}; exact native L06 witness still required")
            else:
                print(f"  Hit {qp['name']}: Z = {hit_z_m:.3f} m, actor={actor_hit}")
            sampled_points.append(sampled)
        else:
            print(f"  Trace on {qp['name']} did not hit landscape via line trace")
            sampled_points.append({**qp, "hit": False})
            problems.append(f"{qp['name']}: collision trace did not hit Landscape")

    report = {
        "status": "FAILED_COLLISION_TRACE" if problems else "PENDING_SOURCE_HEIGHT_AND_SEAM_VERIFICATION",
        "rounded_reference_warnings": rounded_reference_warnings,
        "geometry_accepted": False,
        "reasons": problems,
        "warning": "Collision raycasts are not raw Landscape height vertex readback.",
        "level": LEVEL_PATH,
        "total_landscape_actors": len(landscapes),
        "total_components": total_components,
        "expected_total_components": 4096,
        "components_pass": total_components == 4096 and len(landscapes) == 4,
        "actor_quantization_step_cm": {
            name: actor_height_step_cm(z) for name, z in scales.items()
        },
        "native_component_properties_complete": all(
            all(row["actual_component_properties"][prop]["complete"]
                for prop in ("component_size_quads", "subsection_size_quads",
                             "num_subsections"))
            for row in landscape_data
        ),
        "source_height_interpolation_proved": False,
        "visibility_layer_proved_in_ue": False,
        "transport_envelope": {
            "source_domain": "8000x8000 m, 16000x16000 cells at 0.5m spacing",
            "transport_envelope": "8128x8128 m, 4 tiles of 8129x8129 vertices (16257x16257 total envelope)",
            "padding_handling": "UNVERIFIED IN EXISTING UE MAP; original bake predated visibility-preserving transfer.",
            "quantization_unit_cm": None,
            "note": "Scale.Z differs by actor. Rounded source landmarks are not a true interpolated-height reference."
        },
        "landscapes": landscape_data,
        "sampled_heights": sampled_points,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"Saved geometry readback report to {REPORT_PATH}")

    unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")

if __name__ == "__main__":
    main()
