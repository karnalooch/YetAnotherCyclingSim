"""Offline fail-closed review-marker tests; no native Unreal and no asset authoring."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = ROOT / "worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json"
SOURCE = HERE / "pcg365_red_marker_preview.py"


def helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"site_check"}
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    def require(ok, message):
        if not ok:
            raise RuntimeError(message)
    globals_ = {
        "require": require,
        "REQUIRED_PRODUCER": "d361e7651d16ff424ae4e812c7d8cbe1fe81d662",
        "REQUIRED_RUN": "38278235093-1",
        "EXPECTED_IDS": ["P0", "P1", "P2", "P3", "P4"],
        "EXPECTED_XY": [[16800,70400],[4800,96800],[184800,180800],[181600,189600],[91200,200800]],
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), globals_)
    return globals_["site_check"]


class RedMarkerReview(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.readback = {
            "code_sha": self.manifest["source_producer_sha"],
            "status": "COLLECTION_CONTACT_FRESH_READBACK",
            "placement": False,
            "cases": [
                {
                    "mesh_id": f"rock{i:02d}",
                    "point_index": n,
                    "world_xy_cm": site["xy_cm"],
                    "policy_decision": {"status": "REJECTED"},
                }
                for n, site in enumerate(self.manifest["markers"])
                for i in range(20)
            ],
        }

    def test_exact_five_sites_accept_historical_rejections_only(self):
        sites = helpers()(self.manifest, self.readback)
        self.assertEqual([s["id"] for s in sites], ["P0", "P1", "P2", "P3", "P4"])
        self.assertEqual(len(self.readback["cases"]), 100)
        self.assertFalse(self.manifest["placement"])

    def test_site_coordinate_or_decision_drift_fails(self):
        self.manifest["markers"][0]["xy_cm"] = [1, 1]
        with self.assertRaisesRegex(RuntimeError, "five frozen"):
            helpers()(self.manifest, self.readback)
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.readback["cases"][0]["policy_decision"]["status"] = "PASS_SAMPLED_CONTACT_ONLY"
        with self.assertRaisesRegex(RuntimeError, "Site input"):
            helpers()(self.manifest, self.readback)

    def test_missing_or_duplicate_case_refused(self):
        self.readback["cases"].pop()
        with self.assertRaisesRegex(RuntimeError, "complete 20x5"):
            helpers()(self.manifest, self.readback)
        self.setUp()
        self.readback["cases"][0] = dict(self.readback["cases"][1])
        with self.assertRaisesRegex(RuntimeError, "complete 20x5"):
            helpers()(self.manifest, self.readback)

    def test_scope_and_hash_pins_not_optional(self):
        self.manifest["placement"] = True
        with self.assertRaisesRegex(RuntimeError, "scope drift"):
            helpers()(self.manifest, self.readback)
        self.manifest["placement"] = False
        self.manifest["source_producer_sha"] = "f" * 40
        with self.assertRaisesRegex(RuntimeError, "Wrong producer"):
            helpers()(self.manifest, self.readback)


if __name__ == "__main__":
    unittest.main()
