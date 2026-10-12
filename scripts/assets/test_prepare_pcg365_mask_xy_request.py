"""Request checks and authenticated reconstruction failure regressions."""

import copy
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import prepare_pcg365_mask_xy_request as request


def fingerprint(receipt):
    receipt.pop("fingerprint", None)
    receipt["fingerprint"] = request.digest(request.canonical(receipt))
    return receipt


def fixture():
    return fingerprint(
        {
            "status": "CPU_XY_PROBES_ONLY",
            "placement": False,
            "qualified_assets": [],
            "recipe": {"seed": 42, "band_priority": [0, 1, 2]},
            "candidates": [
                {
                    "candidate_id": str(i) * 64,
                    "source_cell": [i, i],
                    "world_xy_cm": [50 * i, 50 * i],
                    "selected": True,
                    "band": 0,
                    "point_seed": i + 1,
                }
                for i in (2, 1)
            ],
        }
    )


class RequestTests(unittest.TestCase):
    def test_order_and_rejected_rows(self):
        receipt = fixture()
        receipt["candidates"].append({"selected": False})
        result = request.validate_request_data(fingerprint(receipt))
        self.assertEqual([p["candidate_id"] for p in result], ["1" * 64, "2" * 64])
        receipt["candidates"].reverse()
        self.assertEqual(request.validate_request_data(fingerprint(receipt)), result)

    def test_hash_drift(self):
        receipt = fixture()
        receipt["candidates"][0]["point_seed"] += 1
        with self.assertRaisesRegex(ValueError, "fingerprint drift"):
            request.validate_request_data(receipt)

    def test_counts_and_collisions(self):
        for rows in ([], [dict(fixture()["candidates"][0]) for _ in range(17)]):
            receipt = fixture()
            receipt["candidates"] = rows
            with self.assertRaisesRegex(ValueError, "sixteen"):
                request.validate_request_data(fingerprint(receipt))
        for key in ("candidate_id", "world_xy_cm", "point_seed"):
            receipt = fixture()
            receipt["candidates"][1][key] = copy.deepcopy(receipt["candidates"][0][key])
            if key == "world_xy_cm":
                receipt["candidates"][1]["source_cell"] = receipt["candidates"][0][
                    "source_cell"
                ]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Duplicate"):
                request.validate_request_data(fingerprint(receipt))

    def test_unqualified_contract_and_mapping_fail_closed(self):
        for key, value in (
            ("placement", True),
            ("qualified_assets", ["mesh"]),
            ("status", "PASS"),
        ):
            receipt = fixture()
            receipt[key] = value
            with self.assertRaises(ValueError):
                request.validate_request_data(fingerprint(receipt))
        for key, value in (
            ("selected", 1),
            ("point_seed", 0),
            ("band", True),
            ("world_xy_cm", [float("inf"), 0]),
        ):
            receipt = fixture()
            receipt["candidates"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                request.validate_request_data(fingerprint(receipt))

    def test_prepare_rebuild_and_actual_file_hash(self):
        scratch = Path(__file__).resolve().parents[2] / "Saved"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            producer = root / "cpu.py"
            producer.write_bytes(b"# pinned producer\n")
            receipt = fixture()
            receipt["authenticated_inputs"] = {
                "files": [{"sha256": "source"}],
                "configuration": {"seed": 42},
            }
            receipt["producer_sha256_lf"] = request.digest(producer.read_bytes())
            fingerprint(receipt)
            path = root / "candidates.json"
            path.write_bytes(request.canonical(receipt))
            rebuilt = {
                k: v
                for k, v in receipt.items()
                if k
                not in ("fingerprint", "authenticated_inputs", "producer_sha256_lf")
            }
            cpu = SimpleNamespace(
                __file__=str(producer),
                authenticated_inputs=lambda *args: (
                    receipt["authenticated_inputs"],
                    (),
                ),
                LatticeRecipe=lambda **kwargs: kwargs,
                candidates=lambda *args: copy.deepcopy(rebuilt),
            )
            with patch.dict("sys.modules", {"sa_calobra_world_graph_candidates": cpu}):
                result = request.prepare(
                    root, root / "config", path, request.digest(path.read_bytes()), root
                )
                self.assertFalse(result["placement"])
                self.assertEqual(result["z_carrier_cm"], 0)
                self.assertEqual(len(result["points"]), 2)
                with self.assertRaisesRegex(ValueError, "file identity"):
                    request.prepare(root, root / "config", path, "0" * 64, root)
                rebuilt["candidates"][0]["selected"] = False
                with self.assertRaisesRegex(ValueError, "reconstruction drift"):
                    request.prepare(
                        root,
                        root / "config",
                        path,
                        request.digest(path.read_bytes()),
                        root,
                    )


if __name__ == "__main__":
    unittest.main()
