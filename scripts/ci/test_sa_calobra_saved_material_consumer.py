"""Boundary regressions for saved material persistence and fresh consumption."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.ci.test_sa_calobra_whole_map_prep import Landscape, fake_api
from scripts.ue import sa_calobra_saved_material_consumer as consumer
from scripts.ue import sa_calobra_whole_map_prep as prep


def capture_fixture():
    rows = [
        dict(
            frame_id=name,
            mode="prepared",
            camera=[i * 1000, i * 1000, 10000],
            target=[i * 1000 + 100, i * 1000, 9000],
            fov=60.0 if name.startswith("ground-") else 58.0,
        )
        for i, name in enumerate(consumer.VIEW_NAMES)
    ]
    return {
        "capture_plan": rows,
        "capture_plan_sha256": hashlib.sha256(prep.canonical(rows)).hexdigest(),
    }


class SourcePlanTests(unittest.TestCase):
    def test_actual_native_world_object_paths_normalize_across_save_as(self):
        def scene(package):
            world = package + "." + package.rsplit("/", 1)[-1]
            actor = world + ":PersistentLevel.Landscape_0"
            component = actor + ".LandscapeComponent_230"
            return {
                "actors": [[actor, [0, 0, 0]]],
                "components": [component],
                "component_forced_lod": [[component, -1]],
                "separate_mesh_materials": [
                    {
                        "component": world
                        + ":PersistentLevel.Road.StaticMeshComponent_0",
                        "materials": ["/Game/Shared/M_Road.M_Road"],
                    }
                ],
                "world": world,
            }

        self.assertEqual(
            consumer.normalized(scene(prep.MAP)),
            consumer.normalized(scene(consumer.MAP)),
        )
        changed = scene(consumer.MAP)
        changed["actors"][0][0] += "_changed"
        self.assertNotEqual(
            consumer.normalized(scene(prep.MAP)), consumer.normalized(changed)
        )
        self.assertEqual(
            consumer.normalized(scene(prep.MAP))["separate_mesh_materials"][0][
                "materials"
            ],
            ["/Game/Shared/M_Road.M_Road"],
        )

    def test_native_entrypoint_bootstrap_imports_outside_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(consumer.__file__).resolve()
            code = (
                "import runpy; value=runpy.run_path("
                + repr(str(script))
                + "); print(value['MAP'])"
            )
            result = subprocess.run(
                [sys.executable, "-I", "-c", code],
                cwd=directory,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), consumer.MAP)

    def test_all_views_reuse_recorded_positions_and_fov(self):
        source = capture_fixture()
        result = consumer.selected_views(source)
        self.assertEqual(tuple(row["name"] for row in result), consumer.VIEW_NAMES)
        self.assertEqual(result[3]["location_cm"], source["capture_plan"][3]["camera"])
        self.assertEqual(result[-1]["fov_deg"], 58.0)

    def test_missing_duplicate_nonfinite_and_changed_plan_rejected(self):
        source = capture_fixture()
        changed = copy.deepcopy(source)
        changed["capture_plan"][0]["camera"][0] += 1
        with self.assertRaisesRegex(RuntimeError, "plan hash"):
            consumer.selected_views(changed)
        for change in (
            lambda rows: rows.pop(0),
            lambda rows: rows.append(rows[0]),
            lambda rows: rows[0].update(camera=[True, 0, 0]),
            lambda rows: rows[0].update(fov=76),
        ):
            changed = copy.deepcopy(source)
            change(changed["capture_plan"])
            changed["capture_plan_sha256"] = hashlib.sha256(
                prep.canonical(changed["capture_plan"])
            ).hexdigest()
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                consumer.selected_views(changed)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.output = Path(self.temp.name) / "proof/consumer"
        self.project.mkdir()
        self.output.mkdir(parents=True)
        canonical = self.project / consumer.CANONICAL_FILE
        canonical.parent.mkdir(parents=True)
        canonical.write_bytes(b"frozen canonical map")
        self.canonical_sha = consumer.digest(canonical)
        asset = "Content/Generated/YACS/SaCalobra/WholeMapPreparation/M_SaCalobraWholeMapPreparation.uasset"
        path = self.project / asset
        path.parent.mkdir(parents=True)
        path.write_bytes(b"native saved material fixture")
        self.assets = [
            {
                "path": asset,
                "size_bytes": path.stat().st_size,
                "sha256": consumer.digest(path),
            }
        ]
        prep.write_json(
            self.output.parent / "capture/whole-map-prep/whole-map-prep-receipt.json",
            capture_fixture(),
        )
        self.landscape = Landscape()
        self.api, self.master, self.instance, self.audits, _ = fake_api(self.landscape)
        self.original = self.landscape.material
        self.original_overrides = [
            component.props["override_material"]
            for component in self.landscape.components
        ]
        self.api.load_asset = lambda path: (
            self.master if path == prep.MASTER_PATH else self.instance
        )
        self.world = object()
        self.saved_binding = None

        def save(_world, package):
            self.assertEqual(package, consumer.MAP)
            self.saved_binding = self.landscape.material
            self.saved_overrides = [
                component.props["override_material"]
                for component in self.landscape.components
            ]
            (self.project / consumer.MAP_FILE).write_bytes(b"derived saved map")
            return True

        def load(path):
            self.landscape.material = (
                self.saved_binding
                if path.endswith(Path(consumer.MAP_FILE).name)
                else self.original
            )
            if path.endswith(Path(consumer.MAP_FILE).name):
                for component, value in zip(
                    self.landscape.components, self.saved_overrides
                ):
                    component.props["override_material"] = value
            return self.world

        self.api.EditorLoadingAndSavingUtils = SimpleNamespace(
            save_map=Mock(side_effect=save), load_map=Mock(side_effect=load)
        )
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for replacement in (
            patch.object(consumer, "ROOT", self.project),
            patch.object(consumer, "CANONICAL_SHA", self.canonical_sha),
            patch.object(
                consumer, "inventory", return_value=copy.deepcopy(self.assets)
            ),
            patch.object(
                consumer, "landscape_for", return_value=(self.world, self.landscape)
            ),
            patch.object(consumer, "snapshot", return_value={"geometry": "frozen"}),
            patch.object(
                consumer,
                "terrain_bounds",
                return_value=[0, 201600, 0, 201600, 0, 100000],
            ),
            patch.object(prep, "verify_instance"),
            patch.object(prep, "mesh_material_snapshot", return_value=[]),
        ):
            self.stack.enter_context(replacement)

    def prepare(self):
        return consumer.prepare(
            self.api,
            self.output,
            self.output.parent,
            "b" * 40,
            self.assets,
            {"exact_sha": "b" * 40},
            {"rendering_recipe_sha256": "c" * 64},
        )

    def test_save_only_derived_map_and_reopen_stored_binding_without_reapply(self):
        manifest = self.prepare()
        self.assertEqual(self.landscape.material, self.original)
        self.assertEqual(
            consumer.digest(self.project / consumer.CANONICAL_FILE), self.canonical_sha
        )
        self.assertEqual(manifest["visual_acceptance"], "PENDING_OWNER")
        self.assertNotIn("fresh_render_receipt", manifest)
        self.assertTrue(
            all(row["location_cm"][2] >= 102000 for row in manifest["traversal"])
        )
        self.assertEqual(manifest["performance_views"][0]["location_cm"][2], 10000)
        with patch.object(
            self.landscape,
            "set_editor_property",
            side_effect=AssertionError("reload must not assign"),
        ):
            loaded, _, _, _, rows = consumer.reload(self.api, self.output, "b" * 40, {})
        self.assertEqual(len(rows), 1024)
        self.assertEqual(
            loaded["map_sha256"], consumer.digest(self.project / consumer.MAP_FILE)
        )
        delivery = consumer.read_json(self.output / "delivery-package-manifest.json")
        self.assertEqual(len(delivery["files"]), 2)
        for row in delivery["files"]:
            self.assertEqual(
                consumer.digest(self.output / row["storage"]["asset"]), row["sha256"]
            )

    def test_partial_setter_failure_restores_every_original_and_saves_nothing(self):
        component = self.landscape.components[230]
        setter = component.set_editor_property
        failed = False

        def failure_once(name, value):
            nonlocal failed
            if value is None and not failed:
                failed = True
                raise RuntimeError("native partial setter failure")
            setter(name, value)

        component.set_editor_property = failure_once
        with self.assertRaisesRegex(RuntimeError, "partial setter"):
            self.prepare()
        self.assertEqual(self.landscape.material, self.original)
        self.assertEqual(
            [row.props["override_material"] for row in self.landscape.components],
            self.original_overrides,
        )
        self.api.EditorLoadingAndSavingUtils.save_map.assert_not_called()
        self.assertFalse((self.output / "consumer-manifest.json").exists())

    def test_failed_native_save_emits_no_admission_and_restores_material(self):
        self.api.EditorLoadingAndSavingUtils.save_map.side_effect = lambda *_args: False
        with self.assertRaisesRegex(RuntimeError, "save failed"):
            self.prepare()
        self.assertEqual(self.landscape.material, self.original)
        self.assertFalse((self.output / "consumer-manifest.json").exists())

    def test_save_as_object_rename_preserves_original_override_rollback(self):
        original_save = self.api.EditorLoadingAndSavingUtils.save_map.side_effect

        def rename_then_save(world, package):
            result = original_save(world, package)
            for component in self.landscape.components:
                component.get_path_name = lambda row=component: (
                    consumer.MAP + ".Landscape.Component_" + str(row.index)
                )
            return result

        self.api.EditorLoadingAndSavingUtils.save_map.side_effect = rename_then_save
        self.prepare()
        self.assertEqual(self.landscape.material, self.original)
        self.assertEqual(
            [row.props["override_material"] for row in self.landscape.components],
            self.original_overrides,
        )

    def test_existing_map_collision_precedes_any_load_or_assignment(self):
        (self.project / consumer.MAP_FILE).write_bytes(b"owner bytes")
        with self.assertRaisesRegex(RuntimeError, "collision"):
            self.prepare()
        self.api.EditorLoadingAndSavingUtils.load_map.assert_not_called()
        self.assertEqual(
            (self.project / consumer.MAP_FILE).read_bytes(), b"owner bytes"
        )

    def test_changed_saved_bytes_rejected_before_native_load(self):
        self.prepare()
        self.api.EditorLoadingAndSavingUtils.load_map.reset_mock()
        (self.project / consumer.MAP_FILE).write_bytes(b"wrong saved map bytes")
        with self.assertRaisesRegex(RuntimeError, "asset bytes differ"):
            consumer.reload(self.api, self.output, "b" * 40, {})
        self.api.EditorLoadingAndSavingUtils.load_map.assert_not_called()

    def test_wrong_saved_binding_is_rejected_instead_of_repaired(self):
        self.prepare()
        self.saved_binding = object()
        with patch.object(
            self.landscape,
            "set_editor_property",
            side_effect=AssertionError("must not repair"),
        ):
            with self.assertRaisesRegex(RuntimeError, "never reapplies"):
                consumer.reload(self.api, self.output, "b" * 40, {})

    def test_stale_manifest_rejected_before_native_load(self):
        self.prepare()
        self.api.EditorLoadingAndSavingUtils.load_map.reset_mock()
        with self.assertRaisesRegex(RuntimeError, "unsupported"):
            consumer.reload(self.api, self.output, "a" * 40, {})
        self.api.EditorLoadingAndSavingUtils.load_map.assert_not_called()

    def test_escaping_asset_and_duplicate_inventory_rejected(self):
        for rows in (
            [dict(self.assets[0], path="Content/../../outside.uasset")],
            self.assets * 2,
        ):
            with self.subTest(rows=rows), self.assertRaises((RuntimeError, ValueError)):
                consumer.verify_assets(rows, self.project)

    def test_render_cleanup_failure_continues_cleanup_and_never_pins_admission(self):
        manifest = self.prepare()
        self.api.unregister_slate_post_tick_callback = Mock(
            side_effect=RuntimeError("callback failure")
        )
        destroy = Mock()
        self.api.EditorActorSubsystem = object
        self.api.get_editor_subsystem = lambda _kind: SimpleNamespace(
            destroy_actor=destroy
        )
        self.api.SystemLibrary.quit_editor = Mock()
        environment = SimpleNamespace(restore=Mock(return_value=[]))
        job = consumer.RenderJob(
            self.api,
            self.output,
            manifest,
            self.world,
            self.landscape,
            SimpleNamespace(audit=Mock()),
        )
        job.handle, job.camera, job.environment = "callback", "camera", environment
        with patch.object(
            consumer, "load_workspace", return_value={"project": str(self.project)}
        ):
            job.stop()
        destroy.assert_called_once_with("camera")
        environment.restore.assert_called_once()
        receipt = consumer.read_json(self.output / "fresh-render-receipt.json")
        self.assertEqual(receipt["status"], "FAILED")
        self.assertTrue(any("callback failure" in row for row in receipt["errors"]))
        self.assertNotIn(
            "fresh_render_receipt",
            consumer.read_json(self.output / "consumer-manifest.json"),
        )
        self.api.SystemLibrary.quit_editor.assert_called_once()

    def test_loading_barrier_cannot_reenter_tick_before_screenshot_task_exists(self):
        manifest = self.prepare()
        actor_subsystem = SimpleNamespace(
            spawn_actor_from_class=Mock(return_value=object())
        )
        self.api.CameraActor = self.api.EditorActorSubsystem = object
        self.api.Vector = lambda *_args: object()
        self.api.get_editor_subsystem = lambda _kind: actor_subsystem
        self.api.register_slate_post_tick_callback = Mock(return_value=0)
        job = consumer.RenderJob(
            self.api,
            self.output,
            manifest,
            self.world,
            self.landscape,
            SimpleNamespace(audit=Mock()),
        )
        job.begin_view = Mock(side_effect=lambda: job.tick(0))
        job.stop = Mock()
        with patch.object(prep, "CaptureEnvironment", return_value=object()):
            job.start()
        job.stop.assert_not_called()
        self.assertFalse(job.busy)

    def test_receipt_write_failure_still_quits_isolated_editor(self):
        manifest = self.prepare()
        self.api.SystemLibrary.quit_editor = Mock()
        job = consumer.RenderJob(
            self.api,
            self.output,
            manifest,
            self.world,
            self.landscape,
            SimpleNamespace(audit=Mock()),
        )
        with (
            patch.object(
                consumer, "load_workspace", return_value={"project": str(self.project)}
            ),
            patch.object(
                prep, "write_json", side_effect=OSError("proof disk unavailable")
            ),
        ):
            with self.assertRaisesRegex(OSError, "disk unavailable"):
                job.stop()
        self.api.SystemLibrary.quit_editor.assert_called_once()


if __name__ == "__main__":
    unittest.main()
