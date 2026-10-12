"""Offline rock asset census: no false qualification or current-world placement."""
from __future__ import annotations

from pathlib import Path
import unittest

from scripts.live_host.recipes import rock_asset_audit as audit

ROOT = Path(__file__).resolve().parents[2]


class FakeClass:
    def __init__(self, name):
        self.asset_name = name


class FakeAsset:
    def __init__(self, package, kind="StaticMesh"):
        self.asset_class_path = FakeClass(kind)
        self.package_name = package


class FakeRegistry:
    def __init__(self, assets, fail=False):
        self.assets = assets
        self.fail = fail

    def get_assets_by_path(self, name, recursive):
        if self.fail:
            raise RuntimeError("read-only registry offline")
        assert name == "/Game" and recursive is True
        return self.assets


class FakeUnreal:
    Name = str

    def __init__(self, assets, fail=False):
        registry = FakeRegistry(assets, fail=fail)
        self.AssetRegistryHelpers = type(
            "RegistryHelpers",
            (),
            {"get_asset_registry": staticmethod(lambda: registry)},
        )


class FakeWorld:
    def __init__(self, name):
        self.name = name

    def get_path_name(self):
        return self.name + "." + Path(self.name).name


class FakeLive:
    map_package = (
        "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/"
        "L_SaCalobraMaterialReview"
    )

    def __init__(self):
        self.world = FakeWorld(self.map_package)


def context():
    return {
        "intent": "preview",
        "asset_scope": (),
        "live": FakeLive(),
    }


class RockAuditContract(unittest.TestCase):
    def test_real_static_mesh_candidates_are_only_registry_observations(self):
        api = FakeUnreal([
            FakeAsset("/Game/Rocks/SM_Limestone_01"),
            FakeAsset("/Game/Generated/YACS/SM_Boulder"),
            FakeAsset("/Game/Textures/T_Rock_Albedo", "Texture2D"),
            FakeAsset("/Engine/Rocks/SM_Engine", "StaticMesh"),
            FakeAsset("/Game/Vegetation/SM_Pine"),
        ])
        result = audit.run(api, context(), {})
        self.assertEqual(result["status"], "APPLIED_PREVIEW")
        self.assertEqual(result["inventory"]["registry_assets"], 5)
        self.assertEqual(result["inventory"]["matching_static_meshes"], 2)
        self.assertEqual(result["inventory"]["mesh_packages"], [
            "/Game/Generated/YACS/SM_Boulder",
            "/Game/Rocks/SM_Limestone_01",
        ])
        self.assertTrue(result["all_100_terrain_contacts_rejected"])
        self.assertEqual(result["qualified_assets"], [])
        self.assertFalse(result["gallery_spawned"])
        self.assertFalse(result["placement"])
        self.assertFalse(result["map_saved"])
        self.assertFalse(result["source_packages_changed"])

    def test_absent_collection_is_not_a_false_contact_pass(self):
        result = audit.run(FakeUnreal([]), context(), {})
        self.assertEqual(result["inventory"]["scan_status"], "COMPLETE")
        self.assertEqual(result["inventory"]["matching_static_meshes"], 0)
        self.assertEqual(result["contact_qualification"], "NOT_ADMITTED")

    def test_native_api_error_reports_uncertainty_not_zero_assets(self):
        result = audit.run(FakeUnreal([], fail=True), context(), {})
        self.assertEqual(
            result["inventory"]["scan_status"], "API_UNAVAILABLE_NOT_PROVEN"
        )
        self.assertIsNone(result["inventory"]["matching_static_meshes"])

    def test_editor_world_and_intent_are_bounded(self):
        api = FakeUnreal([])
        for changes in (
            {"intent": "author"},
            {"asset_scope": ("Content/Rocks/SM_Test.uasset",)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                audit.run(api, {**context(), **changes}, {})
        with self.assertRaises(ValueError):
            audit.run(api, context(), {"site": "P3"})
        other = context()
        other["live"].world = FakeWorld("/Game/OtherMap")
        with self.assertRaises(ValueError):
            audit.run(api, other, {})

    def test_caps_guard_memory_and_receipt_size(self):
        small = [FakeAsset(f"/Game/Rock/SM_{i:03d}") for i in range(30)]
        result = audit.inspect_registry(FakeUnreal(small))
        self.assertEqual(result["matching_static_meshes"], 30)
        self.assertEqual(len(result["mesh_packages"]), audit.MAX_RETURNED_ROCKS)
        self.assertTrue(result["returned_truncated"])
        big = [
            FakeAsset("/Game/Rock/SM_T")
            for _ in range(audit.MAX_REGISTRY_ASSETS + 1)
        ]
        result = audit.inspect_registry(FakeUnreal(big))
        self.assertEqual(result["scan_status"], "BUDGET_EXCEEDED_NO_INVENTORY")
        self.assertEqual(result["mesh_packages"], [])

    def test_hard_no_authoring_methods_in_recipe(self):
        source = (ROOT / "scripts/live_host/recipes/rock_asset_audit.py").read_text()
        for forbidden in (
            "spawn_actor", "save_asset", "save_all", "set_editor_property",
            "set_actor_location", "load_asset", "copy2(", "unreal.SystemLibrary",
            "get_assets_by_object_path",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
