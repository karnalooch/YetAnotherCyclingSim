import unreal

print("=== METHODS ON HoudiniPublicAPIAssetWrapper ===")
for m in dir(unreal.HoudiniPublicAPIAssetWrapper):
    if not m.startswith("_"):
        print(f"  {m}")

print("\n=== METHODS ON HoudiniPublicAPIInputWrapper ===")
for m in dir(unreal.HoudiniPublicAPIInputWrapper):
    if not m.startswith("_"):
        print(f"  {m}")

print("\n=== METHODS ON HoudiniPublicAPIBlueprintLib ===")
for m in dir(unreal.HoudiniPublicAPIBlueprintLib):
    if not m.startswith("_"):
        print(f"  {m}")
