import unreal

print("=== INSPECTING LandscapeCircleHeightPatch ===")
for m in dir(unreal.LandscapeCircleHeightPatch):
    if not m.startswith("_"):
        print(f"  {m}")

print("\n=== INSPECTING LandscapeTexturePatch ===")
for m in dir(unreal.LandscapeTexturePatch):
    if not m.startswith("_"):
        print(f"  {m}")
