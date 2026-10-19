import unreal

out = []
for name in dir(unreal):
    if "landscape" in name.lower() and ("subsystem" in name.lower() or "library" in name.lower() or "manager" in name.lower() or "patch" in name.lower()):
        cls = getattr(unreal, name)
        out.append(f"\n=== {name} ===")
        for m in dir(cls):
            if not m.startswith("_"):
                out.append(f"  {m}")

# Check LandscapeProxy methods matching edit layer
out.append("\n=== LandscapeProxy ===")
for m in dir(unreal.LandscapeProxy):
    if not m.startswith("_"):
        out.append(f"  {m}")

with open("D:/yacs/project/worldgen/houdini/sa_calobra/landscape_api_dump.txt", "w") as f:
    f.write("\n".join(out))

print("Wrote landscape_api_dump.txt")
unreal.SystemLibrary.execute_console_command(None, "QUIT_EDITOR")
