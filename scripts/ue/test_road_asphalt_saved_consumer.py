"""Synthetic save/reload contract tests; these never import Unreal or save a map."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.ue import road_asphalt_saved_consumer as saved
from scripts.ue.test_road_asphalt_slot_canary import CanaryTests


class RoadAsphaltSavedConsumerContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CanaryTests()
        self.fixture.setUp()
        self.old = self.fixture.snapshot()
        source = saved.session.operation.MAP_PACKAGE
        source_world = source + "." + source.rsplit("/", 1)[-1]
        self.old["map_package"] = source
        self.old["world"] = source_world
        road = source_world + ":PersistentLevel.YACS_PERSIST_ROAD"
        support = source_world + ":PersistentLevel.YACS_PERSIST_SUPPORT_000"
        self.old["road_supports"][0]["actor"] = road
        self.old["road_supports"][0]["component"] = road + ".DynamicMeshComponent"
        self.old["mesh_material_collision_snapshot"][0]["component"] = (
            road + ".DynamicMeshComponent"
        )
        self.old["road_supports"][1]["actor"] = support
        self.old["road_supports"][1]["component"] = support + ".DynamicMeshComponent"
        self.old["mesh_material_collision_snapshot"][1]["component"] = (
            support + ".DynamicMeshComponent"
        )
        self.old["actors"] = [
            (road, [1.0, 2.0, 3.0]),
            (support, [4.0, 5.0, 6.0]),
        ]
        self.new_material = (
            saved.PACKAGE
            + "/aged_mountain_asphalt/base/6b381516854c/MI_MaterialForge.MI_MaterialForge"
        )

    def new_inventory(self):
        value = deepcopy(self.old)
        value["road_supports"][0]["slots"] = [{
            "path": self.new_material,
            "parent": self.new_material.rsplit("/", 1)[0]
            + "/M_MaterialForge.M_MaterialForge",
            "class": "MaterialInstanceConstant",
            "effective_color": None,
        }]
        value["mesh_material_collision_snapshot"][0]["materials"] = [
            self.new_material
        ]
        return value

    def test_native_actor_tuples_equal_authentic_json_arrays_without_field_loss(self):
        # The real Unreal inventory builds actors with sorted((path, transform)
        # for actor ...), so the current process owns tuples. Persisted JSON
        # always restores arrays. Both must hash to the same exact scene bytes.
        native = deepcopy(self.old)
        native["actors"] = [
            ("/Game/Map.Map:PersistentLevel.Road", [1.0, 2.0, 3.0]),
            ("/Game/Map.Map:PersistentLevel.Support", [4.0, 5.0, 6.0]),
        ]
        retained = deepcopy(native)
        retained["actors"] = [list(row) for row in retained["actors"]]
        self.assertNotEqual(native, retained)
        self.assertEqual(
            saved.inventory_digest(native),
            saved.inventory_digest(retained),
        )
        retained["actors"][1][1][2] = 9.0
        self.assertNotEqual(
            saved.inventory_digest(native),
            saved.inventory_digest(retained),
        )

    def test_only_road_slot_zero_changes_across_derived_save(self):
        after = self.new_inventory()
        signature = saved.expected_saved_inventory(
            self.old, after, self.new_material,
            observed_map_package=saved.session.operation.MAP_PACKAGE,
        )
        self.assertEqual(len(signature), 64)
        for mutation in (
            lambda snapshot: snapshot["road_supports"][1].update(vertices=-1),
            lambda snapshot: snapshot["landscape"].update(component_count=1023),
            lambda snapshot: snapshot["mesh_material_collision_snapshot"][1][
                "materials"
            ].append("unexpected"),
        ):
            changed = deepcopy(after)
            mutation(changed)
            with self.assertRaises(ValueError):
                saved.expected_saved_inventory(
                    self.old, changed, self.new_material,
                    observed_map_package=saved.session.operation.MAP_PACKAGE,
                )

    def test_source_slot_binding_before_save_and_new_map_names_after_save(self):
        source = saved.session.operation.MAP_PACKAGE
        source_world = source + "." + source.rsplit("/", 1)[-1]
        target_world = saved.MAP + "." + saved.MAP.rsplit("/", 1)[-1]
        temporary = self.new_inventory()
        first = saved.expected_saved_inventory(
            self.old, temporary, self.new_material,
            observed_map_package=source,
        )

        def renamed(value):
            if isinstance(value, str):
                return (
                    value.replace(source_world, target_world)
                    .replace(source, saved.MAP)
                )
            if isinstance(value, list):
                return [renamed(item) for item in value]
            if isinstance(value, tuple):
                return [renamed(item) for item in value]
            if isinstance(value, dict):
                return {renamed(k): renamed(v) for k, v in value.items()}
            return value

        persisted = renamed(temporary)
        second = saved.expected_saved_inventory(
            self.old, persisted, self.new_material,
            observed_map_package=saved.MAP,
        )
        self.assertEqual(first, second)
        with self.assertRaisesRegex(ValueError, "approved save phase"):
            saved.expected_saved_inventory(
                self.old, temporary, self.new_material,
                observed_map_package=saved.MAP,
            )
        with self.assertRaisesRegex(ValueError, "approved save phase"):
            saved.expected_saved_inventory(
                self.old, persisted, self.new_material,
                observed_map_package="/Game/Unauthorized/Map",
            )
        altered = deepcopy(persisted)
        altered["actors"][0][1][0] = -1.0
        with self.assertRaisesRegex(ValueError, "changed geometry"):
            saved.expected_saved_inventory(
                self.old, altered, self.new_material,
                observed_map_package=saved.MAP,
            )

    def test_savemap_may_keep_original_world_until_fresh_editor_reload(self):
        def mock_editor(package):
            world = SimpleNamespace(
                get_path_name=lambda: package + "." + package.rsplit("/", 1)[-1]
            )
            system = SimpleNamespace(get_editor_world=lambda: world)
            return SimpleNamespace(
                UnrealEditorSubsystem=object(),
                get_editor_subsystem=lambda cls: system,
            )

        source = saved.session.operation.MAP_PACKAGE
        for package in (source, saved.MAP):
            with self.subTest(package=package):
                self.assertEqual(
                    saved.active_map_after_save(mock_editor(package)), package
                )
                stage = self.new_inventory()
                stage["map_package"] = package
                if package == saved.MAP:
                    # The other test verifies exact actor path rebasing
                    # rather than weakening the complete scene equality.
                    self.assertNotEqual(stage["map_package"], self.old["map_package"])
        with self.assertRaisesRegex(ValueError, "unapproved map"):
            saved.active_map_after_save(mock_editor("/Game/Unapproved/L_Other"))

    def test_world_identity_normalizes_but_materials_are_not_aliases(self):
        before = saved.session.operation.MAP_PACKAGE
        after = saved.MAP
        for old, new in (
            (before + "." + before.rsplit("/", 1)[-1], after + "." + after.rsplit("/", 1)[-1]),
            (before + ".L", after + ".L"),
        ):
            self.assertEqual(
                saved.normalized(old + ":PersistentLevel.Actor", before),
                saved.normalized(new + ":PersistentLevel.Actor", after),
            )
        original = {"material": "/Game/Textures/Test.T_Test"}
        self.assertEqual(saved.normalized(original, before), original)
        self.assertEqual(saved.normalized(original, after), original)

    def test_durable_manifest_copies_are_byte_pinned_not_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            retained = Path(directory) / "retained"
            rows = []
            for index in range(7):
                relative = (
                    saved.MAP_FILE
                    if index == 0
                    else saved.PREFIX + f"test/T_{index:02d}.uasset"
                )
                data = f"SYNTHETIC SAVED MATERIAL ASSET {index}".encode()
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                rows.append({
                    "path": relative,
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                })
            with patch.object(saved, "ROOT", root):
                delivered = saved.retain_files(retained, rows)
                self.assertEqual(len(delivered), 7)
                saved.verify_retained_files(retained, delivered)
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    saved.retain_files(retained, rows)
                (retained / delivered[-1]["storage"]).write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "differs"):
                    saved.verify_retained_files(retained, delivered)

    def test_generated_package_tree_audits_directories_and_all_seven_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / saved.PREFIX
            expected_paths = [saved.MAP_FILE] + [
                saved.PREFIX + f"aged_mountain_asphalt/base/abcdef/T_{i}.uasset"
                for i in range(6)
            ]
            for i, relative in enumerate(expected_paths):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(f"native-package-{i}".encode("utf-8"))
            with patch.object(saved, "ROOT", root):
                rows = saved.produced_files()
                self.assertEqual(
                    [row["path"] for row in rows], sorted(expected_paths)
                )
                self.assertEqual(len(rows), 7)
                extra = folder / "aged_mountain_asphalt/base/abcdef/UNAPPROVED.txt"
                extra.write_text("not a package", encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, "Unapproved generated road-material file type"
                ):
                    saved.produced_files()
                extra.unlink()
                # Never silently accept an asset file with a real path alias.
                alias = folder / "aged_mountain_asphalt/base/abcdef/ALIAS.uasset"
                try:
                    alias.symlink_to(root / expected_paths[1])
                except (OSError, NotImplementedError):
                    pass  # Symlink privilege may be unavailable on Windows.
                else:
                    with self.assertRaisesRegex(ValueError, "reparse|symlink"):
                        saved.produced_files()

    def test_schema_and_packages_are_fixed_to_new_separate_namespace(self):
        self.assertEqual(
            saved.MAP_FILE,
            "Content/Generated/YACS/RoadAsphaltConsumer/L_SaCalobraRoadAsphaltReview.umap",
        )
        self.assertNotEqual(saved.MAP, saved.session.operation.MAP_PACKAGE)
        self.assertTrue(saved.MAP.startswith(saved.PACKAGE + "/"))
        self.assertTrue(saved.PREFIX.startswith("Content/Generated/YACS/"))
        self.assertNotIn("Worlds/SaCalobra", saved.MAP)
        self.assertEqual(saved.TEXTURES["NormalTex"], "Normal_DX")
        self.assertEqual(saved.MAX_ASSET_COUNT, 64)


if __name__ == "__main__":
    unittest.main()
