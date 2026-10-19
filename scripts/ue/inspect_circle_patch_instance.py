import unreal

patch = unreal.new_object(unreal.LandscapeCircleHeightPatch)
for p in dir(patch):
    if not p.startswith("_"):
        try:
            val = getattr(patch, p)
            if not callable(val):
                print(f"prop: {p} = {val}")
        except Exception:
            pass
