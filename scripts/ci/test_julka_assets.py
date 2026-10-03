from __future__ import annotations

import ast
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JULKA = ROOT / "tools" / "julka"
sys.path.insert(0, str(JULKA))

from julka_core.cli import (
    cmd_audit_root,
    cmd_cleanup,
    cmd_local_store,
    load_catalog_file,
    operation_lock,
)  # noqa: E402
from julka_core.models import (
    JulkaError,
    canonical_digest,
    safe_relative_path,
    topological_assets,
    validate_catalog,
)  # noqa: E402


class JulkaCatalogContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(
            (JULKA / "data" / "catalog.json").read_text(encoding="utf-8")
        )

    def test_catalog_pins_complete_17_asset_receipt(self) -> None:
        validate_catalog(self.catalog)
        self.assertEqual(
            self.catalog["receipt"]["path"],
            "sa-calobra-working-v1/manual_cnig_receipt_2026-10-03.json",
        )
        assets = self.catalog["assets"]
        self.assertEqual(len(assets), 34)
        release_assets = [
            row for row in assets if row["backend"]["type"] == "github-release"
        ]
        self.assertEqual(len(release_assets), 17)
        self.assertEqual(
            sum(row["size_bytes"] for row in release_assets), 3_339_596_438
        )
        self.assertEqual(len({row["sha256"] for row in assets}), 34)
        self.assertEqual(
            sum(row["signature_hex"] == "4c415346" for row in release_assets), 9
        )
        self.assertEqual(
            sum(row["signature_hex"] == "49492b00" for row in release_assets), 8
        )
        manual_assets = [
            row for row in assets if row["backend"]["type"] == "manual-cnig"
        ]
        self.assertEqual(len(manual_assets), 17)
        self.assertTrue(all("signature_hex" not in row for row in manual_assets))

    def test_filename_mapping_is_explicit_and_lossless(self) -> None:
        rows = [
            row
            for row in self.catalog["assets"]
            if row["backend"]["type"] == "github-release"
        ]
        self.assertEqual(
            sum(
                row["provider_catalog_name"] != row["acquisition"]["release_asset"]
                for row in rows
            ),
            13,
        )
        self.assertEqual(len({row["acquisition"]["release_asset"] for row in rows}), 17)
        self.assertEqual(len({row["path"] for row in rows}), 17)

    def test_profile_closure_contains_all_source_assets(self) -> None:
        self.assertEqual(
            len(topological_assets(self.catalog, "sa-calobra-working")), 17
        )
        full = topological_assets(self.catalog, "sa-calobra-8x8")
        self.assertEqual(len(full), 34)
        self.assertEqual(
            sum(row["backend"]["type"] == "manual-cnig" for row in full), 17
        )
        self.assertEqual(
            len(self.catalog["profiles"]["sa-calobra-8x8"]["incomplete_layers"]), 3
        )
        self.assertFalse(self.catalog["storage_policy"]["paid_services"])
        self.assertIn("not a backup", self.catalog["storage_policy"]["local_copy"])

    def test_mdt_records_match_existing_preparation_manifest(self) -> None:
        source = (ROOT / "scripts/assets/prepare_sa_calobra_mdt50cm.py").read_text(
            encoding="utf-8"
        )
        module = ast.parse(source)
        manifest = next(
            ast.literal_eval(node.value)
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "EXPECTED_INPUTS"
                for target in node.targets
            )
        )
        records = {
            row["provider_catalog_name"]: (row["size_bytes"], row["sha256"])
            for row in self.catalog["assets"]
            if row["backend"]["type"] == "manual-cnig"
        }
        self.assertEqual(
            records, {name: (size, digest) for name, size, digest in manifest}
        )

    def test_gis_metadata_never_silently_fills_uninspected_source_fields(self) -> None:
        required = {
            "xy_crs",
            "xy_unit",
            "vertical_datum",
            "footprint",
            "resolution_or_density",
            "classification",
            "nodata",
        }
        self.assertTrue(
            all(
                required.issubset(value)
                for value in self.catalog["gis_metadata_profiles"].values()
            )
        )
        self.assertIn(
            "not verified",
            self.catalog["gis_metadata_profiles"]["mdt_source"]["vertical_datum"],
        )

    def test_unsafe_relative_paths_are_rejected(self) -> None:
        for value in ("../secret", "/absolute/file", "C:/drive/file", "a\\b"):
            with self.subTest(value=value), self.assertRaises(JulkaError):
                safe_relative_path(value)

    def test_asset_identity_mutation_breaks_catalog_contract(self) -> None:
        changed = json.loads(json.dumps(self.catalog))
        changed["assets"][0]["sha256"] = "0" * 64
        changed["assets"][0]["size_bytes"] = -1
        with self.assertRaises(JulkaError):
            validate_catalog(changed)

    def test_canonical_digest_is_order_independent(self) -> None:
        self.assertEqual(
            canonical_digest({"a": 1, "b": 2}), canonical_digest({"b": 2, "a": 1})
        )

    def test_local_audit_is_scoped_and_reports_logical_bytes_without_hashing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tile.laz").write_bytes(b"LASF")
            (root / "notes.txt").write_text("not an asset", encoding="utf-8")
            output = io.StringIO()
            args = type("Args", (), {"root": root, "hash": False, "output": None})()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cmd_audit_root(args), 0)
            report = json.loads(output.getvalue().split("Asset files:", 1)[0])
            self.assertEqual(report["asset_file_count"], 1)
            self.assertEqual(report["logical_bytes"], 4)
            self.assertFalse(report["hashes_computed"])
            self.assertIsNone(report["physical_disk_recovery_estimate"])

    def test_cleanup_is_plan_only_and_keeps_source_and_cache_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "asset-root"
            cache = root / "derived-cache" / "tile"
            source = root / "sources" / "tile"
            cache.mkdir(parents=True)
            source.parent.mkdir(parents=True)
            (cache / "generated.bin").write_bytes(b"cache")
            source.write_bytes(b"source")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cmd_cleanup(type("Args", (), {"root": root})()), 0)
            self.assertEqual((cache / "generated.bin").read_bytes(), b"cache")
            self.assertEqual(source.read_bytes(), b"source")
            self.assertIn("plan only", output.getvalue())

    def test_local_dvc_initialization_is_plan_only_without_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "asset-root"
            output = io.StringIO()
            args = type(
                "Args",
                (),
                {
                    "root": root,
                    "action": "init",
                    "apply": False,
                    "path": None,
                    "asset_id": "local-input",
                },
            )()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cmd_local_store(args), 0)
            self.assertFalse(root.exists())
            self.assertIn("plan only", output.getvalue())

    def test_mutating_root_operations_are_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".julka"
            with operation_lock(state):
                with self.assertRaises(JulkaError):
                    with operation_lock(state):
                        self.fail("a second concurrent operation must not enter")

    def test_catalog_disk_reader_uses_only_checked_in_manifest(self) -> None:
        self.assertEqual(
            load_catalog_file()["dataset_id"], "sa-calobra-cnig-working-v1"
        )


if __name__ == "__main__":
    unittest.main()
