"""Live-only reversible actor transform on the authenticated preview world.

Frozen Landscape, roads and DTM owners cannot be changed by this recipe.
Persistent source packages are never saved.
"""
def run(unreal, context, parameters):
    world = context["live"].world
    actor_path = parameters["actor_path"]
    editor = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    matches = [actor for actor in editor.get_all_level_actors()
               if actor.get_path_name() == actor_path]
    if len(matches) != 1:
        raise ValueError("Expected one owned-world actor path")
    actor = matches[0]
    cls = actor.get_class().get_name()
    if any(token in cls.lower() for token in ("landscape", "road", "spline", "terrain")):
        raise ValueError("Frozen world-authority actor cannot be transformed")
    if world.get_path_name().split(".")[0] != context["live"].map_package:
        raise ValueError("Unexpected editor world")
    old_transform = actor.get_actor_transform()
    x, y, z = parameters["location_cm"]
    pitch, yaw, roll = parameters["rotation_deg"]
    if any(abs(float(v)) > 1000000 for v in (x, y, z)):
        raise ValueError("Actor preview location outside bounded map space")
    location = unreal.Vector(x, y, z)
    rotation = unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)
    try:
        actor.set_actor_location(location, False, False)
        actor.set_actor_rotation(rotation, False)
        observed = actor.get_actor_location()
        if (observed - location).length() > 1.0:
            raise ValueError("Native actor transform readback mismatch")
    except Exception:
        actor.set_actor_transform(old_transform, False, False)
        raise
    return {
        "status": "APPLIED_PREVIEW",
        "map_saved": False,
        "actor": actor_path,
        "previous_transform": str(old_transform),
        "native_location_cm": [observed.x, observed.y, observed.z],
        "new_rotation_deg": [pitch, yaw, roll],
        "undo": "Restore the recorded previous transform before committing a checkpoint.",
    }
