import unreal

print("=== SEARCHING UNREAL MODULE FOR LANDSCAPE ===")
landscape_items = [name for name in dir(unreal) if "landscape" in name.lower()]
print(f"Total landscape items in unreal module: {len(landscape_items)}")
for item in sorted(landscape_items):
    obj = getattr(unreal, item)
    try:
        if issubclass(obj, unreal.Object) or issubclass(obj, unreal.StructBase):
            print(f"  [Class/Struct] {item}")
        else:
            print(f"  [Other] {item}")
    except Exception:
        print(f"  [Attr] {item}")

print("\n=== SEARCHING FOR EDIT LAYER / BRUSH / API ===")
layer_items = [name for name in dir(unreal) if "editlayer" in name.lower() or "landscapelayer" in name.lower()]
for item in layer_items:
    print(f"  {item}")

# Let's inspect HoudiniPublicAPI
api = unreal.HoudiniPublicAPIBlueprintLib.get_api()
print(f"\nHoudini API methods:")
for m in dir(api):
    if not m.startswith("_"):
        print(f"  api.{m}")
