"""Create the isolated manifest-selected terrain map without deleting assets."""
import json
import os
import sys
from pathlib import Path

import unreal

manifest = json.loads(Path(os.environ["YACS_TERRAIN_MANIFEST"]).read_text(encoding="utf-8"))
package = manifest["map_package"]
if manifest["region_id"] != "sa_calobra" or package != "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline":
    raise RuntimeError("Unadmitted terrain map")
if unreal.EditorAssetLibrary.does_asset_exist(package):
    raise RuntimeError("Terrain map already exists; retain its payload before another authoring attempt")
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not levels.new_level(package, is_partitioned_world=False):
    raise RuntimeError("Failed to create isolated terrain level")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not world or not unreal.EditorLoadingAndSavingUtils.save_map(world, package):
    raise RuntimeError("Failed to save isolated terrain level")
if os.environ.get("YACS_ROAD_CURVE_GUIDES"):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from author_ma2141_curved_edges import author
    author(os.environ["YACS_ROAD_CURVE_GUIDES"])
unreal.log("[RegionTerrainMap] PASS: isolated Sa Calobra map created")
