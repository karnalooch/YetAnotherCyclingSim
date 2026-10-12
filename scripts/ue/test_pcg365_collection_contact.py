"""CPU contract checks; no Unreal import or host operations."""

import ast
from pathlib import Path
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

    namespace = {"require": require}
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


if __name__ == "__main__":
    unittest.main()
