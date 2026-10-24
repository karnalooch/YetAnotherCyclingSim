"""Exercise relocatable identity and fail-closed mask input authentication."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import rasterio
from rasterio.transform import Affine

from scripts.assets.prepare_sa_calobra_world_graph_inputs import (
    canonical,
    REQUIRED_PRODUCTS,
    GRID,
    prepare,
    validate_config,
)

CONFIG = (
    Path(__file__).resolve().parents[2]
    / "worldgen/sa_calobra/world_graph_inputs_v1.json"
)


class WorldGraphInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def fixture(self, directory, grid_change=False):
        config = copy.deepcopy(self.config)
        for name, pin in config["sources"].items():
            path = directory / pin["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            products = []
            for filename, (bands, dtype, nodata) in REQUIRED_PRODUCTS[name].items():
                product = path.parent / filename
                with rasterio.open(
                    product,
                    "w",
                    driver="GTiff",
                    width=4033,
                    height=4033,
                    count=bands,
                    dtype=dtype,
                    nodata=nodata,
                    crs=GRID["crs"],
                    transform=Affine(*GRID["transform"]),
                    compress="DEFLATE",
                ):
                    pass
                products.append(
                    {
                        "path": filename,
                        "sha256": hashlib.sha256(product.read_bytes()).hexdigest(),
                        "size_bytes": product.stat().st_size,
                        "bands": bands,
                        "dtype": dtype,
                        "nodata": nodata,
                    }
                )
            manifest = {
                "geometry_mutation": False,
                "grid": copy.deepcopy(config["grid"]),
                "status": "READY_FOR_BOUNDED_MASK_CONSUMER_WITH_FALLBACKS"
                if name == "pcg"
                else "TRANSITION_AND_TOPOLOGY_REVIEW_CANDIDATE",
                "world_mapping": config["world_mapping"],
                "hard_exclusions_modified": False,
                "consumer_contract": {
                    "decision": "Reject unknown; require radius+clearance"
                },
                "unresolved_world_authority": ["native graph not admitted"],
                "source_manifests": [config["sources"]["pcg"]],
                "outputs": products,
            }
            if grid_change:
                manifest["grid"]["width"] = 99
            manifest["fingerprint"] = hashlib.sha256(
                json.dumps(
                    manifest, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
            ).hexdigest()
            path.write_bytes(canonical(manifest))
            pin["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            pin["fingerprint"] = manifest["fingerprint"]
        cfg = directory / "config.json"
        cfg.write_bytes(canonical(config))
        return cfg

    def test_deterministic_relocation_and_seed_identity(self):
        a, b = self.root / "a", self.root / "b"
        ca, cb = self.fixture(a), self.fixture(b)
        prepare(a, ca, a / "out")
        prepare(b, cb, b / "out")
        self.assertEqual(
            (a / "out/world-graph-inputs.json").read_bytes(),
            (b / "out/world-graph-inputs.json").read_bytes(),
        )
        changed = json.loads(cb.read_text())
        changed["seed"] += 1
        cb.write_bytes(canonical(changed))
        result = prepare(b, cb, b / "seed")
        original = json.loads((a / "out/world-graph-inputs.json").read_text())
        self.assertNotEqual(result["fingerprint"], original["fingerprint"])
        self.assertFalse(result["placement"])
        self.assertEqual(result["native_execution"], "NOT_RUN")
        self.assertEqual(result["qualified_assets"], [])
        self.assertEqual(
            result["exclusion_contract"]["evaluate_reference"],
            "scripts/assets/read_sa_calobra_pcg_masks.py:evaluate",
        )
        self.assertIn("Reject selector255", result["unknown_contract"])
        self.assertIn("never promote unknown", result["unknown_contract"])
        self.assertEqual(
            result["exclusion_contract"]["bits"]["2"],
            "shoulder conservative 0.51m envelope",
        )

    def test_tampered_product_rejected(self):
        config = self.fixture(self.root)
        product = (
            self.root
            / Path(self.config["sources"]["pcg"]["path"]).parent
            / "vegetation-selectors.tif"
        )
        product.write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "Stale mask product"):
            prepare(self.root, config, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_authenticated_wrong_grid_rejected(self):
        config = self.fixture(self.root, grid_change=True)
        with self.assertRaisesRegex(ValueError, "spatial grid"):
            prepare(self.root, config, self.root / "out")

    def test_malformed_seed_and_hash_rejected(self):
        for seed in (True, -1, 1.5, "36501", 2147483648):
            config = copy.deepcopy(self.config)
            config["seed"] = seed
            with self.assertRaisesRegex(ValueError, "Seed"):
                validate_config(config)
        for value in ("../escape", "A" * 64, "f" * 63, 1):
            config = copy.deepcopy(self.config)
            config["sources"]["pcg"]["sha256"] = value
            with self.assertRaisesRegex(ValueError, "hash"):
                validate_config(config)

    def test_manifest_tamper_and_existing_output_rejected(self):
        config = self.fixture(self.root)
        path = self.root / self.config["sources"]["pcg"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "manifest hash"):
            prepare(self.root, config, self.root / "out")
        (self.root / "out").mkdir()
        with self.assertRaises(FileExistsError):
            prepare(self.root, config, self.root / "out")

    def test_authenticated_status_and_parent_disagreement_rejected(self):
        for name, field, value, error in (
            ("pcg", "status", "UNREVIEWED", "fingerprint/status"),
            ("transitions", "hard_exclusions_modified", True, "hard exclusions"),
            ("transitions", "source_manifests", [], "parent differs"),
        ):
            with self.subTest(field=field):
                directory = self.root / field
                cfg = self.fixture(directory)
                config = json.loads(cfg.read_text())
                path = directory / config["sources"][name]["path"]
                manifest = json.loads(path.read_text())
                manifest[field] = value
                del manifest["fingerprint"]
                manifest["fingerprint"] = hashlib.sha256(
                    json.dumps(
                        manifest, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode()
                ).hexdigest()
                path.write_bytes(canonical(manifest))
                config["sources"][name]["fingerprint"] = manifest["fingerprint"]
                config["sources"][name]["sha256"] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                cfg.write_bytes(canonical(config))
                with self.assertRaisesRegex(ValueError, error):
                    prepare(directory, cfg, directory / "out")

    def test_required_product_missing_duplicate_or_wrong_bands_rejected(self):
        for mutation in ("missing", "duplicate", "bands", "raster_bands"):
            with self.subTest(mutation=mutation):
                directory = self.root / mutation
                cfg = self.fixture(directory)
                config = json.loads(cfg.read_text())
                path = directory / config["sources"]["pcg"]["path"]
                manifest = json.loads(path.read_text())
                if mutation == "missing":
                    manifest["outputs"].pop(0)
                elif mutation == "duplicate":
                    manifest["outputs"].append(copy.deepcopy(manifest["outputs"][0]))
                elif mutation == "bands":
                    manifest["outputs"][0]["bands"] = 1
                else:
                    product = path.parent / manifest["outputs"][0]["path"]
                    with rasterio.open(
                        product,
                        "w",
                        driver="GTiff",
                        width=4033,
                        height=4033,
                        count=1,
                        dtype="uint8",
                        nodata=255,
                        crs=GRID["crs"],
                        transform=Affine(*GRID["transform"]),
                        compress="DEFLATE",
                    ):
                        pass
                    manifest["outputs"][0].update(
                        sha256=hashlib.sha256(product.read_bytes()).hexdigest(),
                        size_bytes=product.stat().st_size,
                    )
                del manifest["fingerprint"]
                manifest["fingerprint"] = hashlib.sha256(
                    json.dumps(
                        manifest, sort_keys=True, separators=(",", ":"), allow_nan=False
                    ).encode()
                ).hexdigest()
                path.write_bytes(canonical(manifest))
                config["sources"]["pcg"].update(
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    fingerprint=manifest["fingerprint"],
                )
                cfg.write_bytes(canonical(config))
                with self.assertRaisesRegex(ValueError, "product|raster contract"):
                    prepare(directory, cfg, directory / "out")


if __name__ == "__main__":
    unittest.main()
