"""Producer-to-admission regression; no Unreal or GPU impersonation."""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from scripts.ci.sa_calobra_performance import (
    CONSUMER_MAP,
    CONSUMER_SECTORS,
    CANONICAL_MAP,
    CANONICAL_MAP_SHA256,
    consumer_inputs,
    evaluate,
    prepare_consumer,
    restore_consumer,
)


class SaCalobraPerformanceTests(unittest.TestCase):
    def fixture(self, root, gpu=7.0):
        (root / "Prepared").mkdir()
        (root / "Prepared/terrain-import.json").write_text(
            json.dumps({"heightmap_sha256": "b" * 64})
        )
        (root / "sa-calobra-settings.json").write_text("{}")
        csv = root / "sa-calobra-terrain-performance.csv"
        csv.write_text(
            "sector,rel_s,frame_ms,game_ms,draw_ms,rhi_ms,gpu_ms\n"
            + "".join(
                f"{sector},{i / 60},10,3,2,1,{gpu}\n"
                for sector in ["overview", "rider", "slope"]
                for i in range(120)
            )
        )
        Path(str(csv) + ".identity.json").write_text(
            json.dumps(
                {
                    "MapPackage": "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline",
                    "ComponentCount": 1024,
                    "ActiveGpu": "NVIDIA GeForce RTX 2070 SUPER",
                    "Resolution": "1920x1080",
                }
            )
        )

    def test_producer_summary_passes_shared_raw_sample_admission(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(folder)
            self.fixture(root)
            result = evaluate(root, "a" * 40, 0)
            self.assertEqual(result["Result"], "PASS")
            self.assertEqual(len(result["Sectors"]), 3)

    def test_missing_gpu_fails_and_retains_failure_receipt(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(folder)
            self.fixture(root, 0)
            with self.assertRaises(ValueError):
                evaluate(root, "a" * 40, 0)
            self.assertEqual(
                json.loads(
                    (root / "sa-calobra-terrain-performance-summary.json").read_text()
                )["Result"],
                "FAIL",
            )

    def test_editor_failure_cannot_publish_pass(self):
        with (
            tempfile.TemporaryDirectory() as folder,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            root = Path(folder)
            self.fixture(root)
            with self.assertRaises(ValueError):
                evaluate(root, "a" * 40, 1)


class SavedMaterialPerformanceTests(unittest.TestCase):
    """Exercise saved/rendered provenance and whole-area sampling contracts."""

    def fixture(self, root):
        from PIL import Image

        assets = []
        parent = "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/M_SaCalobraWholeMapPreparation"
        instance = parent.replace("/M_SaCalobra", "/MI_SaCalobra")
        for package, suffix in (
            (CONSUMER_MAP, ".umap"),
            (parent, ".uasset"),
            (instance, ".uasset"),
        ):
            path = "Content/" + package.removeprefix("/Game/") + suffix
            asset = root / path
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(b"unit-test data; never presented as an Unreal asset")
            assets.append(
                {
                    "path": path,
                    "sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                    "size_bytes": asset.stat().st_size,
                }
            )
        poses = [
            {
                "name": f"ground-{row}-{col}",
                "location_cm": [x - 3000, y - 4000, 22000],
                "target_cm": [x, y, 20000],
                "fov_deg": 60,
            }
            for row, x in enumerate((25000, 100000, 175000))
            for col, y in enumerate((25000, 100000, 175000))
        ]
        poses += [
            {
                "name": name,
                "location_cm": [100800, -100000, 250000],
                "target_cm": [100800, 100800, 20000],
                "fov_deg": 58,
            }
            for name in ("overview-north", "overview-south")
        ]
        # Synthetic PNGs validate the evidence contract; never GPU/render proof.
        image_bytes = io.BytesIO()
        Image.new("RGB", (1920, 1080)).save(image_bytes, format="PNG")
        frames = []
        for pose in poses:
            frame = root / "frames" / (pose["name"] + ".png")
            frame.parent.mkdir(exist_ok=True)
            frame.write_bytes(image_bytes.getvalue())
            frames.append(
                dict(
                    name=pose["name"],
                    path=frame.relative_to(root).as_posix(),
                    sha256=hashlib.sha256(frame.read_bytes()).hexdigest(),
                    size_bytes=frame.stat().st_size,
                )
            )
        receipt = {
            "status": "SAVED_MATERIAL_CONSUMER_RENDERED",
            "exact_sha": "a" * 40,
            "map_sha256": assets[0]["sha256"],
            "expected_material_parent": parent,
            "component_count": 1024,
            "fresh_process": True,
            "material_reapplied": False,
            "saved_assets_unchanged": True,
            "capture_settings_restored": True,
            "frame_count": 11,
            "frames": frames,
        }
        fresh = root / "fresh-render-receipt.json"
        fresh.write_text(json.dumps(receipt))
        manifest = {
            "schema_version": 1,
            "exact_sha": "a" * 40,
            "map_package": CONSUMER_MAP,
            "map_sha256": assets[0]["sha256"],
            "canonical_map_package": CANONICAL_MAP,
            "canonical_map_sha256": CANONICAL_MAP_SHA256,
            "terrain_sha256": CANONICAL_MAP_SHA256,
            "terrain_identity_kind": "immutable_canonical_accepted_map",
            "geometry_mutation": False,
            "geometry_snapshot_sha256": "b" * 64,
            "material_recipe_sha256": "c" * 64,
            "expected_material_parent": parent,
            "expected_material_instance": instance,
            "component_count": 1024,
            "assets": assets,
            "performance_views": poses,
            "traversal": [poses[i] for i in (0, 4, 8)],
            "fresh_render_receipt": {
                "path": fresh.name,
                "sha256": hashlib.sha256(fresh.read_bytes()).hexdigest(),
            },
        }
        path = root / "consumer-manifest.json"
        path.write_text(json.dumps(manifest))
        return path, manifest

    def test_source_bound_grid_and_traversal_survive_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path, manifest = self.fixture(root)
            settings = prepare_consumer(root, path, "a" * 40, root)
            self.assertEqual(settings["views"][:-1], manifest["performance_views"])
            self.assertEqual(settings["views"][-1]["path"], manifest["traversal"])
            self.assertEqual([v["name"] for v in settings["views"]], CONSUMER_SECTORS)
            self.assertTrue(settings["lighting_preserved"])

    def test_wrong_commit_asset_bytes_or_unrendered_consumer_rejected(self):
        for defect in (
            "sha",
            "asset",
            "receipt",
            "map",
            "parent",
            "escape",
            "canonical",
            "geometry",
        ):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path, manifest = self.fixture(root)
                if defect == "sha":
                    manifest["exact_sha"] = "c" * 40
                elif defect == "asset":
                    (root / manifest["assets"][0]["path"]).write_bytes(b"changed")
                elif defect == "receipt":
                    (root / "fresh-render-receipt.json").write_text("{}")
                elif defect == "map":
                    manifest["map_package"] = (
                        "/Game/Worlds/SaCalobra/L_SaCalobraTerrainBaseline"
                    )
                elif defect == "parent":
                    manifest["assets"].pop()
                elif defect == "canonical":
                    manifest["terrain_sha256"] = "e" * 64
                elif defect == "geometry":
                    manifest["geometry_mutation"] = True
                else:
                    manifest["assets"][0]["path"] = "../outside.umap"
                path.write_text(json.dumps(manifest))
                with self.assertRaises((ValueError, FileNotFoundError)):
                    consumer_inputs(path, "a" * 40, root)

    def test_incomplete_grid_mislabeled_ground_or_missing_traversal_rejected(self):
        for defect in ("missing", "grid", "traversal", "nonfinite"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                path, manifest = self.fixture(root)
                if defect == "missing":
                    manifest["performance_views"].pop(0)
                elif defect == "grid":
                    manifest["performance_views"][0]["target_cm"][0] = 175000
                elif defect == "traversal":
                    manifest["traversal"] = []
                else:
                    manifest["performance_views"][0]["location_cm"][2] = float("nan")
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    prepare_consumer(root, path, "a" * 40, root)

    def test_missing_changed_or_unrestored_fresh_frames_fail_before_measurement(self):
        for defect in (
            "missing",
            "bytes",
            "duplicate",
            "restoration",
            "dimensions",
            "escape",
        ):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as folder:
                from PIL import Image

                root = Path(folder)
                path, manifest = self.fixture(root)
                receipt_path = root / "fresh-render-receipt.json"
                receipt = json.loads(receipt_path.read_text())
                frame = receipt["frames"][0]
                image_path = root / frame["path"]
                if defect == "missing":
                    image_path.unlink()
                elif defect == "bytes":
                    image_path.write_bytes(b"changed")
                elif defect == "duplicate":
                    receipt["frames"][1] = frame
                elif defect == "restoration":
                    receipt["capture_settings_restored"] = False
                elif defect == "escape":
                    frame["path"] = "../outside.png"
                else:
                    Image.new("RGB", (1280, 720)).save(image_path)
                    frame.update(
                        sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                        size_bytes=image_path.stat().st_size,
                    )
                receipt_path.write_text(json.dumps(receipt))
                manifest["fresh_render_receipt"]["sha256"] = hashlib.sha256(
                    receipt_path.read_bytes()
                ).hexdigest()
                path.write_text(json.dumps(manifest))
                with self.assertRaises((ValueError, FileNotFoundError)):
                    consumer_inputs(path, "a" * 40, root)

    def test_native_wrong_parent_or_incomplete_consumption_fails_shared_gate(self):
        from scripts.ci.test_world_proof_gate import fixture as gate_fixture
        from scripts.ci.world_proof_gate import validate_evidence

        summary, csv, policy = gate_fixture("sa-calobra-material")
        summary.update(
            MapSha256="d" * 64,
            ConsumerManifestSha256="e" * 64,
            MaterialParent=policy["material_parent"],
            MaterialComponentCount=1024,
            RenderInstanceCount=1024,
            LightingPreserved=True,
        )
        validate_evidence(summary, csv, policy, "sa-calobra-material", "a" * 40)
        for key, value in (
            ("MaterialParent", "/Engine/DefaultMaterial"),
            ("MaterialComponentCount", 1023),
            ("LightingPreserved", False),
            ("ConsumerManifestSha256", ""),
        ):
            broken = copy.deepcopy(summary)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_evidence(broken, csv, policy, "sa-calobra-material", "a" * 40)

    def test_retained_consumer_restores_missing_packages_and_never_overwrites(self):
        import shutil

        for conflict in (False, True):
            with (
                self.subTest(conflict=conflict),
                tempfile.TemporaryDirectory() as folder,
            ):
                root = Path(folder)
                path, manifest = self.fixture(root)
                packages = root / "packages"
                packages.mkdir()
                for entry in manifest["assets"]:
                    original = root / entry["path"]
                    retained = packages / original.name
                    shutil.copyfile(original, retained)
                    entry["storage"] = {
                        "asset": "packages/" + original.name,
                        "release": "test retained candidate",
                    }
                    original.unlink()
                path.write_text(json.dumps(manifest))
                target = root / manifest["assets"][0]["path"]
                if conflict:
                    target.write_bytes(b"owner bytes must survive")
                    with self.assertRaises(ValueError):
                        restore_consumer(path, "a" * 40, root)
                    self.assertEqual(target.read_bytes(), b"owner bytes must survive")
                else:
                    self.assertEqual(
                        restore_consumer(path, "a" * 40, root)["restored"], 3
                    )
                    self.assertEqual(
                        restore_consumer(path, "a" * 40, root)["restored"], 0
                    )
