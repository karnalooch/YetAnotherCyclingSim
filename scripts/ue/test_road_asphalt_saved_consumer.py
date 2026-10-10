"""Synthetic save/reload contract tests; these never import Unreal or save a map."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
            + "/aged_mountain_asphalt/dry_varied/6b381516854c/MI_MaterialForge.MI_MaterialForge"
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

    def test_network_allows_only_source_owned_outer_slots_and_preserves_parapet(self):
        original, after = deepcopy(self.old), self.new_inventory()
        assets = saved.shoulder_material.asset_paths(saved.shoulder_material.DESTINATION_ROOT)
        receipt = {"schema_version": 2, "support_count": 186, "material_target_count": 185,
                   "owners": [], "material": {"assets": assets}}
        for i in range(186):
            target = i != 181
            material = (saved.shoulder_sources.SUPPORT_MATERIAL if target
                        else saved.shoulder_sources.PARAPET_MATERIAL)
            label = original["road_supports"][i + 1]["label"]
            receipt["owners"].append({"support_label": label, "material_target": target,
                "kind": "ordinary" if target else "parapet",
                "source": {"original_material_path": material}})
            for inventory in (original, after):
                inventory["road_supports"][i + 1]["slots"] = [{"path": material}]
                inventory["mesh_material_collision_snapshot"][i + 1]["materials"] = [material]
            if target:
                after["road_supports"][i + 1]["slots"].append({
                    "path": assets["instance"], "parent": assets["master"],
                    "class": "MaterialInstanceConstant", "effective_color": None})
                after["mesh_material_collision_snapshot"][i + 1]["materials"].append(assets["instance"])

        def verify(value, selection=receipt):
            return saved.expected_saved_inventory(
                original, value, self.new_material,
                observed_map_package=saved.session.operation.MAP_PACKAGE,
                shoulder_receipt=selection,
            )

        verify(after)
        self.assertTrue(all(len(row["slots"]) == 1 for row in original["road_supports"][1:]))
        for mutate in (
            lambda value: value["road_supports"][1]["slots"][0].update(path="changed-wall"),
            lambda value: value["road_supports"][182]["slots"].append({"path": assets["instance"]}),
            lambda value: value["road_supports"][186]["slots"].pop(),
            lambda value: value["mesh_material_collision_snapshot"][1].update(collision="BLOCK_ALL"),
            lambda value: value["landscape"].update(component_count=1023),
        ):
            value = deepcopy(after)
            mutate(value)
            with self.assertRaises(ValueError):
                verify(value)
        for mutate in (
            lambda value: value["owners"].pop(),
            lambda value: value["owners"][1].update(support_label=value["owners"][0]["support_label"]),
            lambda value: value["owners"][181].update(material_target=True),
            lambda value: value["material"]["assets"].update(instance="/Game/Unapproved/MI.MI"),
        ):
            value = deepcopy(receipt)
            mutate(value)
            with self.assertRaises(ValueError):
                verify(after, value)

    def test_fresh_road_full_buffers_reject_geometry_corner_or_id_drift(self):
        summary = {"vertex_count": 856250, "triangle_count": 1711760,
                   "uv_set_count": 0, "positions_indices_blake3": "a" * 64,
                   "triangle_corner_normals_uv_blake3": "b" * 64,
                   "material_ids_blake3": "c" * 64}
        component = object()
        road = SimpleNamespace(get_dynamic_mesh_component=lambda: component)
        api = SimpleNamespace(EditorActorSubsystem=object(),
            get_editor_subsystem=lambda _: SimpleNamespace(get_all_level_actors=lambda: [road]))
        with patch.object(saved.baseline, "road_support_actors", return_value=[road]), \
             patch.object(saved.shoulder, "inspect_mesh", return_value={"summary": summary}) as read:
            self.assertEqual(saved.verify_road_mesh(api, summary), summary)
            read.assert_called_once_with(api, component)
            for field in ("positions_indices_blake3", "triangle_corner_normals_uv_blake3", "material_ids_blake3"):
                changed = {**summary, field: "d" * 64}
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "full native buffers"):
                    saved.verify_road_mesh(api, changed)

    def test_downloadable_manifest_must_match_retained_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            proof, retained = Path(directory) / "proof", Path(directory) / "retained"
            proof.mkdir()
            retained.mkdir()
            value = {"shoulder_network": {"selected_triangle_ids": [0, 1, 50, 51]}}
            expected = saved.write_once(retained / saved.MANIFEST, value)
            saved.write_once(proof / saved.MANIFEST, value)
            self.assertEqual(saved.verified_manifest_identity(proof, retained), expected)
            (proof / saved.MANIFEST).write_bytes((proof / saved.MANIFEST).read_bytes().replace(b"50", b"52"))
            with self.assertRaisesRegex(ValueError, "Downloadable material manifest differs"):
                saved.verified_manifest_identity(proof, retained)

    def test_profile_diagnostic_is_retained_once_and_both_copies_remain_byte_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            proof, retained = Path(directory) / "proof", Path(directory) / "retained"
            proof.mkdir()
            retained.mkdir()
            plan = object()
            report = {"synthetic_file_contract_fixture": True, "values": [0, 1, 2]}
            with patch.object(saved.shoulder_sources, "network_profile_report", return_value=report) as read:
                identity = saved.write_profile_diagnostic(proof, retained, plan)
                read.assert_called_once_with(plan)
                with self.assertRaises(FileExistsError):
                    saved.write_profile_diagnostic(proof, retained, plan)
            self.assertEqual(identity["file"], saved.PROFILE_DIAGNOSTIC)
            original = (proof / saved.PROFILE_DIAGNOSTIC).read_bytes()
            self.assertEqual(json.loads(original), report)
            self.assertEqual(identity["sha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(identity["size_bytes"], len(original))
            for folder in (proof, retained):
                path = folder / saved.PROFILE_DIAGNOSTIC
                path.write_bytes(original.replace(b"[0,1,2]", b"[0,1,3]"))
                with self.assertRaisesRegex(ValueError, "diagnostic bytes changed"):
                    saved.verified_profile_identity(proof, retained, identity)
                path.write_bytes(original)
            for changed in (
                {**identity, "file": "../another.json"},
                {**identity, "size_bytes": saved.shoulder_sources.PROFILE_REPORT_MAX_BYTES + 1},
                {**identity, "size_bytes": True},
                {**identity, "sha256": "unverified"},
                {**identity, "extra": 1},
            ):
                with self.assertRaisesRegex(ValueError, "fixed file/byte contract"):
                    saved.verified_profile_identity(proof, retained, changed)
            self.assertEqual(saved.verified_profile_identity(proof, retained, identity), identity)

    def test_editor_dispatch_keeps_source_dependency_role_separate_from_scene_assets(self):
        # Real staging has 14 scene rows and 236 unique dependency rows, with
        # ten valid paths shared across those roles. Only the dependency list
        # belongs to the material validator; the union still guards all files.
        dependencies = list(saved.shoulder_material.SOURCE_PINS.values())
        consumer = [dependencies[0]]
        stage = {"consumer_assets": consumer, "source_dependencies": dependencies}
        rows = consumer + dependencies
        saved.shoulder_material.source_rows(dependencies)
        with self.assertRaisesRegex(ValueError, "duplicate source dependency"):
            saved.shoulder_material.source_rows(rows)
        api = SimpleNamespace(
            Paths=SimpleNamespace(project_dir=lambda: str(saved.ROOT),
                convert_relative_path_to_full=lambda value: value),
            SystemLibrary=SimpleNamespace(get_engine_version=lambda: "5.8.2-56702186+++UE5+Release-5.8",
                quit_editor=Mock()),
        )
        trial = {"result": {"graph_sha256": saved.asphalt_source.GRAPH_SHA256,
                            "source_receipt_sha256": saved.asphalt_source.SOURCE_RECEIPT_SHA256}}
        original, identity = {"native_inventory": {}}, {"sha256": "a" * 64, "size_bytes": 100}
        for action in ("prepare", "reload"):
            with self.subTest(action=action), \
                 patch.dict("os.environ", {"YACS_ROAD_SAVED_ACTION": action}), \
                 patch.dict("sys.modules", {"unreal": api}), \
                 patch.object(saved.session, "_assert_isolated_root"), \
                 patch.object(saved, "proof_paths", return_value=("b" * 40, "a" * 64, "1-1", Path("proof"), Path("retained"))), \
                 patch.object(saved, "verified_staging", return_value=(Path("stage"), identity, stage, {}, rows)), \
                 patch.object(saved, "verified_predecessors", return_value=(original, trial)), \
                 patch.object(saved.baseline, "dirty_packages"), \
                 patch.object(saved.prep, "assert_isolated_bootstrap"), \
                 patch.object(saved.session, "_verify_rows") as verify_files, \
                 patch.object(saved.session, "_identity", return_value=identity), \
                 patch.object(saved, action) as dispatch:
                saved.main()
                self.assertIs(dispatch.call_args.kwargs["source_dependencies"], dependencies)
                self.assertIs(dispatch.call_args.args[-1], rows)
                verify_files.assert_called_once_with(saved.ROOT, rows)

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
                saved.PREFIX + f"aged_mountain_asphalt/dry_varied/abcdef/T_{i}.uasset"
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
                extra = folder / "aged_mountain_asphalt/dry_varied/abcdef/UNAPPROVED.txt"
                extra.write_text("not a package", encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, "Unapproved generated road-material file type"
                ):
                    saved.produced_files()
                extra.unlink()
                # Never silently accept an asset file with a real path alias.
                alias = folder / "aged_mountain_asphalt/dry_varied/abcdef/ALIAS.uasset"
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
