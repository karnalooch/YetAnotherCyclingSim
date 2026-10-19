import hou

fc = hou.node("/obj").createNode("geo").createNode("filecache::2.0")
print("filecache::2.0 children:")
for c in fc.children():
    print(f"  {c.name()} ({c.type().name()})")
    if "rop" in c.type().name() or "render" in c.name().lower():
        print(f"    found rop: {c.name()}")
