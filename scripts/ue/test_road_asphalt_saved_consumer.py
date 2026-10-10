"""Synthetic save/reload contract tests; these never import Unreal or save a map."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.ue import road_asphalt_saved_consumer as saved
from scripts.ue.test_road_asphalt_slot_canary import CanaryTests


class RoadAsphaltSavedConsumerContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CanaryTests()
        self.fixture.setUp()
        self.old = self.fixture.snapshot()
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
            self.old, after, self.new_material
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
                    self.old, changed, self.new_material
                )

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
