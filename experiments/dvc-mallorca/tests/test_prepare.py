from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prepare import prepare_heightfield, sha256_file  # noqa: E402


class PrepareHeightfieldTests(unittest.TestCase):
    def make_source(self, root: Path) -> tuple[Path, Path]:
        source = root / "source.tif"
        values = np.arange(64, dtype=np.float32).reshape(8, 8)
        with rasterio.open(
            source,
            "w",
            driver="GTiff",
            width=8,
            height=8,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(2.8, 39.73, 0.001, 0.001),
        ) as dataset:
            dataset.write(values, 1)
        metadata = root / "source.json"
        metadata.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "id": "fixture",
                    "expected_sha256": sha256_file(source),
                }
            ),
            encoding="utf-8",
        )
        return source, metadata

    def test_repeated_preparation_is_byte_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, metadata = self.make_source(root)
            output = root / "prepared.f32"
            report = root / "report.json"

            first = prepare_heightfield(
                source=source,
                source_metadata_path=metadata,
                output=output,
                report_path=report,
                size=17,
                resampling_name="bilinear",
                producer_version=1,
            )
            first_hashes = (sha256_file(output), sha256_file(report))
            second = prepare_heightfield(
                source=source,
                source_metadata_path=metadata,
                output=output,
                report_path=report,
                size=17,
                resampling_name="bilinear",
                producer_version=1,
            )

            self.assertEqual(first, second)
            self.assertEqual(first_hashes, (sha256_file(output), sha256_file(report)))
            self.assertTrue(first["policy"]["experimental_only"])
            self.assertFalse(first["policy"]["production_authority"])

    def test_checksum_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, metadata = self.make_source(root)
            payload = json.loads(metadata.read_text(encoding="utf-8"))
            payload["expected_sha256"] = "0" * 64
            metadata.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "source SHA-256 mismatch"):
                prepare_heightfield(
                    source=source,
                    source_metadata_path=metadata,
                    output=root / "prepared.f32",
                    report_path=root / "report.json",
                    size=17,
                    resampling_name="bilinear",
                    producer_version=1,
                )


if __name__ == "__main__":
    unittest.main()
