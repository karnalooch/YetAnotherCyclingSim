"""Create a transient MID and adjust one scalar, without saving source .uasset."""
def run(unreal, context, parameters):
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = [a for a in editor.get_all_level_actors()
               if a.get_path_name() == parameters["actor_path"]]
    if len(matches) != 1:
        raise ValueError("Unique owner actor required")
    actor = matches[0]
    if any(token in actor.get_class().get_name().lower()
           for token in ("landscape", "road", "spline", "terrain")):
        raise ValueError("Source of truth material owner excluded from generic preview")
    comp = actor.get_component_by_class(unreal.MeshComponent)
    if comp is None:
        raise ValueError("Actor lacks mesh material slots")
    index = int(parameters["material_slot"])
    mid = comp.create_dynamic_material_instance(index)
    if mid is None:
        raise ValueError("Could not produce a transient dynamic material")
    parameter = parameters["parameter"]
    value = float(parameters["value"])
    old = float(mid.get_scalar_parameter_value(parameter))
    try:
        mid.set_scalar_parameter_value(parameter, value)
        actual = float(mid.get_scalar_parameter_value(parameter))
        if abs(actual - value) > 0.001:
            raise ValueError("Transient material parameter readback failed")
    except Exception:
        mid.set_scalar_parameter_value(parameter, old)
        raise
    return {
        "status": "APPLIED_PREVIEW",
        "map_saved": False,
        "actor": parameters["actor_path"],
        "material_slot": index,
        "parameter": parameter,
        "previous_scalar": old,
        "new_scalar": actual,
        "persisted_asset": False,
    }
