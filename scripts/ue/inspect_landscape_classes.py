import unreal

print("=== CyclingLandscapeEarthworksLibrary ===")
for m in dir(unreal.CyclingLandscapeEarthworksLibrary):
    if not m.startswith("_"):
        print(f"  {m}")

print("\n=== LandscapeEditLayer ===")
for m in dir(unreal.LandscapeEditLayer):
    if not m.startswith("_"):
        print(f"  {m}")

print("\n=== LandscapeProxy ===")
for m in dir(unreal.LandscapeProxy):
    if "layer" in m.lower():
        print(f"  {m}")

