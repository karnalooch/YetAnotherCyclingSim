"""Toggle an existing non-authority actor's visibility in memory."""
def run(unreal, context, parameters):
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = [a for a in subsystem.get_all_level_actors()
               if a.get_path_name() == parameters["actor_path"]]
    if len(matches) != 1:
        raise ValueError("Actor identity not unique in live world")
    actor = matches[0]
    if any(x in actor.get_class().get_name().lower()
           for x in ("landscape", "terrain", "road", "spline")):
        raise ValueError("Frozen world-authority actor visibility denied")
    old = bool(actor.is_hidden_ed())
    actor.set_is_temporarily_hidden_in_editor(not parameters["visible"])
    actual = bool(actor.is_hidden_ed())
    if actual != (not parameters["visible"]):
        actor.set_is_temporarily_hidden_in_editor(old)
        raise ValueError("Native actor visibility readback differs")
    return {
        "status": "APPLIED_PREVIEW",
        "map_saved": False,
        "actor": parameters["actor_path"],
        "previous_hidden": old,
        "now_hidden": actual,
    }
