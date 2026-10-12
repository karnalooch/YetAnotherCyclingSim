"""CPU contract checks; no Unreal import or host operations."""

import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from scripts.assets.pcg_rock_contact_policy import (
    evaluate,
    trial_policy,
    refined_trial_policy,
)


def helpers():
    path = Path(__file__).with_name("sa_calobra_pcg_collection_contact.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def identity(path):
        raw = Path(path).read_bytes()
        return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    namespace = {
        "require": require,
        "Path": Path,
        "json": json,
        "q": SimpleNamespace(identity=identity),
        "map_identity": lambda sources: sources["terrain"]["map_identity"],
    }
    nodes = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef)
        and n.name
        in {
            "batch_members",
            "complete",
            "measurement",
            "verify_marker",
            "verify_terrain",
            "read_json",
            "contact_mode",
            "verify_all_marker",
            "verify_batch_receipt",
            "verify_raw_samples",
            "read_contact_batches",
        }
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


class ContactContract(unittest.TestCase):
    def test_marker_wrong_action_missing_or_failed_rejected(self):
        verify = helpers()["verify_marker"]
        marker = {
            "action": "collection-contact-03",
            "code_sha": "a" * 40,
            "exit_code": 0,
            "staged_bytes_unchanged": True,
            "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
        }
        verify(marker, "a" * 40, 3)
        for key, value in (
            ("action", "collection-contact-04"),
            ("code_sha", "b" * 40),
            ("exit_code", False),
            ("exit_code", 1),
            ("staged_bytes_unchanged", False),
        ):
            with self.assertRaises(ValueError):
                verify({**marker, key: value}, "a" * 40, 3)
        with self.assertRaises(ValueError):
            verify({}, "a" * 40, 3)

    def test_terrain_hash_or_transform_drift_rejected(self):
        verify = helpers()["verify_terrain"]
        identity = {"sha256": "a" * 64, "bytes": 10}
        transform = {"location": [0, 0, 0], "scale": [50, 50, 1], "rotation": [0, 0, 0]}
        verify(identity, dict(identity), transform, dict(transform))
        with self.assertRaises(ValueError):
            verify(identity, {**identity, "sha256": "b" * 64}, transform, transform)
        with self.assertRaises(ValueError):
            verify(
                identity, identity, transform, {**transform, "location": [0, 0, 0.01]}
            )

    def test_batches_cover_twenty_once(self):
        split = helpers()["batch_members"]
        rows = [{"id": f"r{i:02d}"} for i in reversed(range(20))]
        result = [m["id"] for i in range(10) for m in split(rows, i)]
        self.assertEqual(result, sorted(m["id"] for m in rows))
        for index in (-1, 10, True):
            with self.assertRaises(ValueError):
                split(rows, index)
        with self.assertRaises(ValueError):
            split(rows[:-1] + [rows[0]], 0)

    def test_missing_ground_and_unpaired_fail(self):
        complete = helpers()["complete"]
        grid = {
            "sample_count": 10,
            "valid_ground_count": 10,
            "unpaired_mesh_hits": 0,
            "fit": {"a": 1},
        }
        self.assertTrue(complete(grid))
        self.assertFalse(complete({**grid, "valid_ground_count": 9}))
        self.assertFalse(complete({**grid, "unpaired_mesh_hits": 1}))
        self.assertFalse(complete({**grid, "fit": None}))

    def test_frozen_numeric_gates(self):
        measure = helpers()["measurement"]
        fit = {
            "required_embedding_cm": 1.0,
            "root_zero_sampled_air_cm": 50000.0,
            "exposure_max_cm": 9.0,
            "exposed_count": 10,
            "max_positive_bottom_gap_cm": 0.0,
        }
        grid = {
            "grid_size": 65,
            "max_local_slope_deg": 5.0,
            "sample_count": 10,
            "valid_ground_count": 10,
            "fit": fit,
        }
        m = measure(
            {"bounds_cm": {"extent": [5, 5, 5]}}, {**grid, "grid_size": 33}, grid
        )
        passed = evaluate(m, trial_policy())
        self.assertEqual(passed["status"], "PASS_SAMPLED_CONTACT_ONLY")
        self.assertFalse(passed["full_qualification"])
        self.assertFalse(passed["placement"])
        for field, value in (
            ("required_embedding_cm", 2.01),
            ("max_positive_bottom_gap_cm", 1e-12),
        ):
            changed = {**m, "fit": {**fit, field: value}}
            self.assertEqual(evaluate(changed, trial_policy())["status"], "REJECTED")
        self.assertEqual(
            evaluate({**m, "max_local_slope_deg": 10.01}, trial_policy())["status"],
            "REJECTED",
        )
        refined = measure(
            {"bounds_cm": {"extent": [5, 5, 5]}}, grid, {**grid, "grid_size": 129}
        )
        self.assertEqual(
            evaluate(refined, refined_trial_policy())["status"],
            "PASS_SAMPLED_CONTACT_ONLY",
        )


class AllContactReadback(unittest.TestCase):
    """Read the real reader with synthetic bytes; never imports Unreal."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pcg365-contact-all-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.output = self.root / "proof/collection-contact-all"
        self.output.mkdir(parents=True)
        self.h = helpers()
        self.head = "a" * 40
        self.inventory = {
            "catalog": {"bytes": 100, "sha256": "c" * 64},
            "meshes": [
                {"id": f"rock{i:02d}", "saved_package": {"sha256": str(i)}}
                for i in range(20)
            ],
        }
        self.sources = {"terrain": {"map_identity": {"bytes": 1, "sha256": "d" * 64}}}
        self.contact = {
            "points": [
                {"candidate_id": f"point-{i}", "world_xy_cm": [i, i + 1]}
                for i in range(5)
            ]
        }
        request = self.root / "contact-request.json"
        request.write_text(json.dumps(self.contact), encoding="utf-8")
        terrain = self.sources["terrain"]["map_identity"]
        shared = {
            "code_sha": self.head,
            "catalog": self.inventory["catalog"],
            "source_contract": self.sources["terrain"],
            "contact_request": self.h["q"].identity(request),
            "terrain_file_before": terrain,
            "terrain_file_after": terrain,
            "ground_transform": {"location": [0, 0, 0], "scale": [50, 50, 1]},
            "terrain_modified": False,
            "placement": False,
            "qualified_assets": [],
            "full_qualification": False,
            "map_saved": False,
        }
        batches = []
        for index in range(10):
            directory = self.output / f"batch-{index:02d}"
            directory.mkdir()
            meshes = self.h["batch_members"](self.inventory["meshes"], index)
            cases = []
            for mesh in meshes:
                for point_index, point in enumerate(self.contact["points"]):
                    grids = []
                    for size in (33, 65):
                        raw = (
                            directory
                            / f"{mesh['id']}-point{point_index}-grid{size}.json"
                        )
                        raw.write_text(
                            '{"support_rows":[],"rejected_rows":[]}', encoding="utf-8"
                        )
                        grids.append(
                            {
                                "grid_size": size,
                                "raw_samples": {
                                    "path": raw.name,
                                    **self.h["q"].identity(raw),
                                },
                            }
                        )
                    cases.append(
                        {
                            "mesh_id": mesh["id"],
                            "point_index": point_index,
                            **point,
                            "grids": grids,
                        }
                    )
            batches.append(
                {
                    "directory": directory.name,
                    "result": {
                        **copy.deepcopy(shared),
                        "status": "COLLECTION_CONTACT_BATCH_MEASURED",
                        "batch_index": index,
                        "meshes": meshes,
                        "cases": cases,
                    },
                }
            )
        self.receipt = {
            **shared,
            "action": "collection-contact-all",
            "status": "COLLECTION_CONTACT_ALL_MEASURED",
            "contact_execution_mode": "SINGLE_PROCESS_ALL_BATCHES",
            "meshes": self.inventory["meshes"],
            "asset_compilation_loading_barrier_completed": True,
            "batches": batches,
        }
        self.marker = {
            "action": "collection-contact-all",
            "code_sha": self.head,
            "exit_code": 0,
            "staged_bytes_unchanged": True,
            "proof_admission": "LOCAL_DIAGNOSTIC_ONLY",
        }
        self.save()

    def save(self):
        (self.output / "launcher-completed.json").write_text(
            json.dumps(self.marker), encoding="utf-8"
        )
        (self.output / "collection-contact-all-receipt.json").write_text(
            json.dumps(self.receipt), encoding="utf-8"
        )

    def read(self):
        return self.h["read_contact_batches"](
            self.root, self.head, self.inventory, self.sources, self.contact
        )

    def test_complete_single_process_readback(self):
        mode, cases, receipts = self.read()
        self.assertEqual(mode, "SINGLE_PROCESS_ALL_BATCHES")
        self.assertEqual(len(cases), 100)
        self.assertEqual(len({case["mesh_id"] for case in cases}), 20)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(
            receipts[0]["sha256"],
            self.h["q"].identity(self.output / "collection-contact-all-receipt.json")[
                "sha256"
            ],
        )

    def test_legacy_layout_remains_readable_and_requires_every_exit(self):
        legacy = self.root / "legacy"
        legacy.mkdir()
        (legacy / "contact-request.json").write_bytes(
            (self.root / "contact-request.json").read_bytes()
        )
        for index, batch in enumerate(self.receipt["batches"]):
            action = f"collection-contact-{index:02d}"
            directory = legacy / "proof" / action
            directory.mkdir(parents=True)
            result = batch["result"]
            for case in result["cases"]:
                for grid in case["grids"]:
                    name = grid["raw_samples"]["path"]
                    (directory / name).write_bytes(
                        (self.output / batch["directory"] / name).read_bytes()
                    )
            (directory / f"{action}-receipt.json").write_text(
                json.dumps(result), encoding="utf-8"
            )
            (directory / "launcher-completed.json").write_text(
                json.dumps({**self.marker, "action": action}), encoding="utf-8"
            )
        read = self.h["read_contact_batches"]
        mode, cases, receipts = read(
            legacy, self.head, self.inventory, self.sources, self.contact
        )
        self.assertEqual(mode, "PER_BATCH_PROCESSES")
        self.assertEqual(len(cases), 100)
        self.assertEqual(len(receipts), 10)
        (legacy / "proof/collection-contact-07/launcher-completed.json").unlink()
        with self.assertRaises(FileNotFoundError):
            read(legacy, self.head, self.inventory, self.sources, self.contact)

    def test_missing_or_invalid_all_marker_rejected(self):
        original = dict(self.marker)
        for key, value in (
            ("action", "collection-contact-00"),
            ("code_sha", "b" * 40),
            ("exit_code", False),
            ("exit_code", -1073741819),
            ("staged_bytes_unchanged", False),
            ("proof_admission", "PASS"),
        ):
            self.marker = {**original, key: value}
            self.save()
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.read()
        (self.output / "launcher-completed.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.read()

    def test_all_receipt_and_barrier_tampering_rejected(self):
        original = copy.deepcopy(self.receipt)
        for key, value in (
            ("code_sha", "b" * 40),
            ("meshes", self.inventory["meshes"][:-1]),
            ("source_contract", {}),
            ("contact_request", {}),
            ("asset_compilation_loading_barrier_completed", False),
        ):
            self.receipt = {**copy.deepcopy(original), key: value}
            self.save()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.read()

    def test_batch_source_mesh_or_head_tampering_rejected(self):
        original = copy.deepcopy(self.receipt)
        for key, value in (
            ("source_contract", {}),
            ("meshes", []),
            ("code_sha", "b" * 40),
        ):
            self.receipt = copy.deepcopy(original)
            self.receipt["batches"][4]["result"][key] = value
            self.save()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.read()

    def test_missing_duplicate_case_or_batch_rejected(self):
        original = copy.deepcopy(self.receipt)
        self.receipt["batches"][7]["result"]["cases"].pop()
        self.save()
        with self.assertRaises(ValueError):
            self.read()
        self.receipt = copy.deepcopy(original)
        cases = self.receipt["batches"][7]["result"]["cases"]
        cases[-1] = copy.deepcopy(cases[0])
        self.save()
        with self.assertRaises(ValueError):
            self.read()
        self.receipt = copy.deepcopy(original)
        self.receipt["batches"].pop()
        self.save()
        with self.assertRaises(ValueError):
            self.read()

    def test_changed_raw_bytes_rejected(self):
        raw = self.receipt["batches"][0]["result"]["cases"][0]["grids"][0][
            "raw_samples"
        ]
        (self.output / "batch-00" / raw["path"]).write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Raw grid drift"):
            self.read()

    def test_raw_path_escape_rejected(self):
        raw = self.receipt["batches"][0]["result"]["cases"][0]["grids"][0][
            "raw_samples"
        ]
        outside = self.output / "outside.json"
        outside.write_text("outside", encoding="utf-8")
        raw.update(path="../outside.json", **self.h["q"].identity(outside))
        self.save()
        with self.assertRaisesRegex(ValueError, "Raw grid drift"):
            self.read()

    def test_mixed_layout_or_fake_child_exit_rejected(self):
        other = self.root / "proof/collection-contact-00"
        other.mkdir()
        with self.assertRaisesRegex(ValueError, "Mixed contact"):
            self.read()
        other.rmdir()
        (self.output / "batch-00/launcher-completed.json").write_text(
            "{}", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "independent process exit"):
            self.read()


if __name__ == "__main__":
    unittest.main()
