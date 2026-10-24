"""Read-only inventory of actual rock StaticMesh assets in the open Live Host.

Issue #476 is the control plane and #365/#368 own rock qualification/dressing.
The independent LIVE diagnostic project is not the natural20 collection studio.
No asset loading, source copying, actor spawn, trace, terrain mutation or save.
"""
from __future__ import annotations

import re

MAX_REGISTRY_ASSETS = 8192
MAX_RETURNED_ROCKS = 24
ROCK_NAME = re.compile(r"(rock|boulder|limestone|cliff|scree|stone|pebble)", re.I)


def inspect_registry(unreal) -> dict:
    """Collect names, not mesh payloads; never infer existence from a Git receipt."""
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    records = registry.get_assets_by_path(unreal.Name("/Game"), recursive=True)
    total = len(records)
    if total > MAX_REGISTRY_ASSETS:
        return {
            "scan_status": "BUDGET_EXCEEDED_NO_INVENTORY",
            "registry_assets": total,
            "matching_static_meshes": 0,
            "mesh_packages": [],
        }
    matched = set()
    static_total = 0
    for record in records:
        class_path = getattr(record, "asset_class_path", None)
        class_name = str(getattr(class_path, "asset_name", ""))
        # The modern UE 5.8 AssetData stores the reflected class in
        # TopLevelAssetPath.asset_name; no asset is loaded to test its class.
        if class_name != "StaticMesh":
            continue
        static_total += 1
        package = str(getattr(record, "package_name", ""))
        if (
            package.startswith("/Game/")
            and len(package) <= 220
            and ROCK_NAME.search(package)
        ):
            matched.add(package)
    packages = sorted(matched)
    return {
        "scan_status": "COMPLETE",
        "registry_assets": total,
        "static_mesh_assets": static_total,
        "matching_static_meshes": len(packages),
        "mesh_packages": packages[:MAX_RETURNED_ROCKS],
        "returned_truncated": len(packages) > MAX_RETURNED_ROCKS,
    }


def run(unreal, context, parameters):
    if context.get("intent") != "preview" or parameters != {}:
        raise ValueError("Only empty-parameter read-only rock inventory is authorized")
    if context.get("asset_scope") != ():
        raise ValueError("Rock inventory cannot declare writable asset paths")
    world = context["live"].world
    if world.get_path_name().split(".")[0] != context["live"].map_package:
        raise ValueError("Unexpected world: refuse an unrelated Editor")

    try:
        inventory = inspect_registry(unreal)
    except Exception as exc:
        # Return a truthful diagnostic without poisoning the no-retry command
        # queue. Do not disguise an API failure as an empty /Game registry.
        inventory = {
            "scan_status": "API_UNAVAILABLE_NOT_PROVEN",
            "registry_error_type": type(exc).__name__,
            "matching_static_meshes": None,
            "mesh_packages": [],
        }

    return {
        "status": "APPLIED_PREVIEW",
        "action": "READ_ONLY_NATIVE_ROCK_ASSET_INVENTORY",
        "world_package": context["live"].map_package,
        "inventory": inventory,
        "all_100_terrain_contacts_rejected": True,
        "contact_qualification": "NOT_ADMITTED",
        "qualified_assets": [],
        "gallery_spawned": False,
        "placement": False,
        "map_saved": False,
        "source_packages_changed": False,
    }
