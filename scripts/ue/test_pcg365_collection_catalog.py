"""CPU contract tests for the isolated collection reader; never imports Unreal."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


def load_reader(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if (isinstance(node, ast.Import) and all(x.name != "unreal" for x in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "pathlib")
        or (isinstance(node, ast.FunctionDef) and node.name in {"identity", "catalog", "source"})
    ]

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    namespace = {"require": require}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["catalog"]


class CatalogContract(unittest.TestCase):
    reader_path = Path(__file__).with_name("sa_calobra_pcg_rock_collection.py")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "rock-collection").mkdir()
        families = [*(f"namaqualand_boulder_0{i}" for i in range(2, 7)),
                    "rock_07", "rock_09", "boulder_01"]
        names = [f"{family}_{i:02d}" for i in range(1, 4) for family in families][:20]
        self.data = {"schema_version": 1, "placement": False, "qualified_assets": [], "variants": []}
        for name in names:
            raw = ("contract fixture, not a native FBX: " + name).encode()
            relative = f"rock-collection/{name}.fbx"
            (self.root / relative).write_bytes(raw)
            self.data["variants"].append({
                "id": name, "source_relative": relative,
                "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
                "base_source_sha256": "a" * 64,
                "expected_native_bounds_cm": {"min": [0, 0, 0], "max": [1, 2, 3]},
                "expected_lod0_triangles": 1,
            })
        self.reader = load_reader(self.reader_path)

    def read(self):
        (self.root / "rock-collection-catalog.json").write_text(json.dumps(self.data), encoding="utf-8")
        return self.reader(self.root)

    def test_eight_family_ids_accepted(self):
        rows, identity = self.read()
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({row["id"].rsplit("_", 1)[0] for row in rows}), 8)
        self.assertGreater(identity["bytes"], 0)

    def test_duplicate_id_rejected(self):
        self.data["variants"][1]["id"] = self.data["variants"][0]["id"]
        with self.assertRaises(ValueError):
            self.read()

    def test_path_traversal_rejected(self):
        self.data["variants"][0]["source_relative"] = "rock-collection/../outside.fbx"
        with self.assertRaises(ValueError):
            self.read()

    def test_placement_rejected(self):
        self.data["placement"] = True
        with self.assertRaises(ValueError):
            self.read()

    def test_hash_drift_rejected(self):
        row = self.data["variants"][0]
        (self.root / row["source_relative"]).write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.read()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reader", type=Path, default=CatalogContract.reader_path)
    args, remaining = parser.parse_known_args()
    CatalogContract.reader_path = args.reader
    unittest.main(argv=[__file__, *remaining])
