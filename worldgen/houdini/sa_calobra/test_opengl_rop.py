import hou

geo = hou.node("/obj").createNode("geo")
rop = hou.node("/out").createNode("opengl")
print("OpenGL ROP parms:")
for p in rop.parms():
    if any(k in p.name() for k in ["picture", "camera", "execute", "render"]):
        print(f"  {p.name()} = {p.eval()}")
