"""Change one existing editor light intensity, transiently and read it back."""
def run(unreal, context, parameters):
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = [a for a in editor.get_all_level_actors()
               if a.get_path_name() == parameters["actor_path"]]
    if len(matches) != 1:
        raise ValueError("Unique light actor required")
    actor = matches[0]
    light = actor.get_component_by_class(unreal.LightComponent)
    if light is None:
        raise ValueError("Actor has no LightComponent")
    old = float(light.get_editor_property("intensity"))
    value = float(parameters["intensity"])
    try:
        light.set_intensity(value)
        actual = float(light.get_editor_property("intensity"))
        if abs(actual - value) > max(0.001, value * 0.0001):
            raise ValueError("Native light intensity readback differs")
    except Exception:
        light.set_intensity(old)
        raise
    return {
        "status": "APPLIED_PREVIEW",
        "map_saved": False,
        "actor": parameters["actor_path"],
        "previous_intensity": old,
        "new_intensity": actual,
    }
