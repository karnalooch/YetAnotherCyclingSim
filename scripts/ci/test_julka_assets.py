from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
JULKA = ROOT / "tools" / "julka"
sys.path.insert(0, str(JULKA))

from julka_core.cli import (
    cmd_audit_root,
    cmd_cleanup,
    cmd_doctor,
    cmd_plan,
    cmd_status,
    cmd_verify,
    load_catalog_file,
    operation_lock,
    run,
)  # noqa: E402
from julka_core.models import (
    JulkaError,
    canonical_digest,
    safe_relative_path,
    topological_assets,
    validate_catalog,
)  # noqa: E402


class JulkaCatalogContractTests(unittest.TestCase):
    def test_p1_context_registry_preserves_fail_closed_admission(self) -> None:
        catalog = load_catalog_file()
        registry = catalog["source_registry"]
        self.assertEqual(registry["btn_vector_context"]["admitted_file_count"], 30)
        self.assertEqual(registry["siose_2014_wfs"]["admitted_file_count"], 0)
        self.assertEqual(registry["catastro_buildings_wfs"]["admitted_file_count"], 0)
        self.assertEqual(len(topological_assets(catalog, "sa-calobra-p1-context")), 45)

    def test_normalized_candidate_is_not_whole_world_authority(self) -> None:
        catalog = load_catalog_file()
        self.assertEqual(
            len(topological_assets(catalog, "sa-calobra-2a-context-candidate")), 56
        )
        self.assertEqual(
            catalog["source_registry"]["normalized_context_v1"]["status"], "candidate"
        )
        pending = catalog["profiles"]["sa-calobra-2a-world-authority"][
            "incomplete_layers"
        ]
        self.assertIn("canopy_height", pending)
        self.assertIn("road_footprint", pending)
        self.assertIn("current_land_cover_with_confidence", pending)

    def test_missing_local_context_cannot_pass_restore_plan(self) -> None:
        import argparse

        with (
            tempfile.TemporaryDirectory() as directory,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            args = argparse.Namespace(
                root=Path(directory), repo=ROOT, profile="sa-calobra-btn-context"
            )
            self.assertEqual(cmd_plan(args), 3)
            self.assertEqual(cmd_verify(args), 1)

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

    def test_audit_counts_distinct_files_and_deduplicates_hardlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.laz"
            first.write_bytes(b"LASF")
            (root / "second.tif").write_bytes(b"different")
            os.link(first, root / "linked.laz")
            output = io.StringIO()
            args = type("Args", (), {"root": root, "hash": False, "output": None})()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cmd_audit_root(args), 0)
            report = json.loads(output.getvalue().split("Asset files:", 1)[0])
            self.assertEqual(report["asset_file_count"], 3)
            self.assertEqual(report["logical_bytes"], 17)
            self.assertEqual(report["unique_file_id_logical_bytes"], 13)
            records = {row["path"]: row for row in report["files"]}
            self.assertEqual(
                records["first.laz"]["unique_file_id"],
                records["linked.laz"]["unique_file_id"],
            )
            self.assertNotEqual(
                records["first.laz"]["unique_file_id"],
                records["second.tif"]["unique_file_id"],
            )

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

    def test_incomplete_layers_cannot_pass_even_with_all_catalog_bytes_present(
        self,
    ) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["profiles"]["code"]["incomplete_layers"] = ["ROADS: not admitted"]
        with tempfile.TemporaryDirectory() as temporary:
            args = type(
                "Args",
                (),
                {
                    "root": Path(temporary),
                    "repo": ROOT,
                    "profile": "code",
                    "verify": True,
                },
            )()
            with patch("julka_core.cli.load_catalog_file", return_value=catalog):
                for operation in (cmd_status, cmd_plan, cmd_verify):
                    with self.subTest(operation=operation.__name__):
                        with contextlib.redirect_stdout(io.StringIO()):
                            self.assertNotEqual(operation(args), 0)

    def test_doctor_reports_missing_tools_without_aborting_remaining_checks(
        self,
    ) -> None:
        with patch(
            "julka_core.cli.subprocess.run",
            side_effect=FileNotFoundError("missing executable"),
        ):
            self.assertEqual(run(["missing-tool"]).returncode, 127)
            output = io.StringIO()
            args = type("Args", (), {"root": ROOT, "project": None})()
            with contextlib.redirect_stdout(output):
                self.assertEqual(cmd_doctor(args), 1)
            self.assertIn("Git LFS", output.getvalue())
            self.assertIn("GitHub Release access", output.getvalue())

    def test_relative_asset_root_reports_missing_files_without_path_error(self) -> None:
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as temporary:
            try:
                os.chdir(temporary)
                args = type(
                    "Args",
                    (),
                    {
                        "root": Path("assets"),
                        "repo": ROOT,
                        "profile": "sa-calobra-working",
                        "verify": True,
                    },
                )()
                with patch("julka_core.cli.lfs_records", return_value=[]):
                    for operation in (cmd_status, cmd_plan, cmd_verify):
                        with self.subTest(operation=operation.__name__):
                            with contextlib.redirect_stdout(io.StringIO()):
                                operation(args)
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
