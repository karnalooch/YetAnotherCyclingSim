"""Real-raster regression tests for diagnostic source-height witnesses."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import rasterio
from rasterio.transform import from_origin

import prepare_sa_calobra_pcg_contact as contact


class ContactWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=contact.ROOT / "Saved")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dtm = self.root / "source.tif"
        self.profile = self.root / "profile.json"
        self.inventory = self.root / "inventory.json"
        self.candidates = self.root / "candidates.json"
        self.inventory.write_text(
            json.dumps(
                [
                    {
                        "object_path": contact.MESH,
                        "bounds_origin_cm": [0, 0, 0],
                        "bounds_extent_cm": [0.01, 0.01, 0.01],
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.candidates.write_text(
            json.dumps(
                {
                    "status": "CPU_XY_PROBES_ONLY",
                    "placement": False,
                    "fingerprint": "fixture",
                    "candidates": [
                        {
                            "selected": True,
                            "candidate_id": "probe",
                            "world_xy_cm": [25, 25],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.write_raster()

    def write_raster(self, nodata=False):
        rows, cols = np.indices((4, 4))
        values = (100 + rows + cols).astype("float32")
        if nodata:
            values[0, 0] = -32767
        with rasterio.open(
            self.dtm,
            "w",
            driver="GTiff",
            width=4,
            height=4,
            count=1,
            dtype="float32",
            crs="EPSG:25831",
            nodata=-32767,
            transform=from_origin(483000, 4409516.5, 0.5, 0.5),
        ) as dataset:
            dataset.write(values, 1)
            bounds = list(dataset.bounds)
        self.profile.write_text(
            json.dumps(
                {
                    "source_sha256": contact.sha(self.dtm),
                    "source_size_bytes": self.dtm.stat().st_size,
                    "source_bounds_m": bounds,
                    "axis_mapping": "fixture",
                }
            ),
            encoding="utf-8",
        )

    def prepare(self):
        with patch.object(contact, "PROFILE", self.profile):
            return contact.prepare(
                self.dtm,
                self.inventory,
                contact.sha(self.inventory),
                self.candidates,
                contact.sha(self.candidates),
            )

    def test_bilinear_plane_from_real_geotiff(self):
        result = self.prepare()
        self.assertFalse(result["placement"])
        self.assertEqual(result["status"], "SOURCE_HEIGHT_MEASUREMENT_INPUT_ONLY")
        samples = result["points"][0]["samples"]
        self.assertEqual(len(samples), 81)
        self.assertAlmostEqual(samples[40]["source_height_m"], 101.0, places=7)
        for sample in samples:
            x, y = sample["world_xy_cm"]
            self.assertAlmostEqual(
                sample["source_height_m"], 100 + (x + y) / 50, delta=2e-5
            )
            self.assertEqual(sample["source_cells"], [0, 0, 1, 1])
        self.assertEqual(result["contact_limits"], "REQUIRED_UNSET_MEASURE_FIRST")

    def test_nodata_in_any_interpolation_neighbour_rejected(self):
        self.write_raster(nodata=True)
        with self.assertRaisesRegex(ValueError, "Unknown source support neighbourhood"):
            self.prepare()

    def test_wrong_source_identity_rejected(self):
        profile = json.loads(self.profile.read_text(encoding="utf-8"))
        profile["source_sha256"] = "0" * 64
        self.profile.write_text(json.dumps(profile), encoding="utf-8")
        with self.assertRaisesRegex(
            ValueError, "Terrain Authority source identity drift"
        ):
            self.prepare()

    def test_drift_after_dataset_close_rejected(self):
        real_open = rasterio.open
        dtm = self.dtm

        class ChangedOnClose:
            def __enter__(self):
                self.dataset = real_open(dtm)
                return self.dataset.__enter__()

            def __exit__(self, *args):
                result = self.dataset.__exit__(*args)
                with dtm.open("ab") as stream:
                    stream.write(b"changed-after-read")
                return result

        with patch.object(contact.rasterio, "open", return_value=ChangedOnClose()):
            with self.assertRaisesRegex(
                ValueError, "Source changed during contact witness preparation"
            ):
                self.prepare()


if __name__ == "__main__":
    unittest.main()
