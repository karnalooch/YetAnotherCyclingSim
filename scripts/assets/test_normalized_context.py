from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

import normalize_sa_calobra_context as producer
import verify_normalized_context as consumer


class NormalizationTests(unittest.TestCase):
    def test_planar_slope_and_downslope_aspect(self):
        # East-rising plane: slope=atan(2), downslope west=270 degrees.
        z = np.tile(np.arange(5) * 1.0, (5, 1))
        d = producer.terrain_layers(z, 0.5, -999)
        np.testing.assert_allclose(d["slope"], np.degrees(np.arctan(2)), rtol=1e-6)
        np.testing.assert_allclose(d["aspect"], 270)
        np.testing.assert_allclose(d["roughness"], 2)

    def test_north_rising_plane_faces_south(self):
        z = np.tile(-np.arange(5).reshape(-1, 1), (1, 5)).astype(float)
        np.testing.assert_allclose(producer.terrain_layers(z, 0.5, -999)["aspect"], 180)

    def test_flat_aspect_is_unknown(self):
        d = producer.terrain_layers(np.ones((5, 5)), 0.5, -999)
        self.assertTrue(np.all(d["aspect"] == producer.NODATA))
        self.assertTrue(np.all(d["slope"] == 0))

    def test_nodata_halo_invalidates_derivatives_without_filling_ground(self):
        z = np.ones((5, 5))
        z[0, 0] = -999
        d = producer.terrain_layers(z, 0.5, -999)
        self.assertEqual(d["slope"][0, 0], producer.NODATA)
        self.assertEqual(d["elevation"][0, 0], 1)
        self.assertEqual(d["slope"][2, 2], 0)

    def test_esri_even_odd_holes_ignore_orientation(self):
        outer = [[0, 0], [0, 4], [4, 4], [4, 0], [0, 0]]
        inner = [[1, 1], [1, 3], [3, 3], [3, 1], [1, 1]]
        self.assertEqual(producer.esri_polygon([inner, outer]).area, 12)

    def test_unclosed_ring_fails(self):
        with self.assertRaisesRegex(ValueError, "Unclosed"):
            producer.esri_polygon([[[0, 0], [1, 0], [1, 1], [0, 1]]])

    def test_actual_gml_surface_patch_supported(self):
        f = ET.fromstring(
            '<Building xmlns:g="http://www.opengis.net/gml/3.2"><g:Surface srsName="urn:ogc:def:crs:EPSG::25831"><g:patches><g:PolygonPatch><g:exterior><g:LinearRing><g:posList srsDimension="2">0 0 2 0 2 2 0 2 0 0</g:posList></g:LinearRing></g:exterior></g:PolygonPatch></g:patches></g:Surface></Building>'
        )
        self.assertEqual(producer.gml_polygons(f).area, 4)
        f.find(".//" + producer.GML + "Surface").set("srsName", "EPSG:4326")
        with self.assertRaisesRegex(ValueError, "CRS"):
            producer.gml_polygons(f)

    def test_partial_or_missing_ids_fail(self):
        ids = {"objectIds": [1, 2], "objectIdFieldName": "OBJECTID"}
        data = {
            "spatialReference": {"wkid": 25831},
            "features": [{"attributes": {"OBJECTID": 1}}],
        }
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            producer.complete_features(data, ids)
        data["exceededTransferLimit"] = True
        with self.assertRaisesRegex(ValueError, "transfer"):
            producer.complete_features(data, ids)

    def test_pinned_source_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "raw"
            p.write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "stale"):
                producer.verified(
                    p, {"file": "raw", "size_bytes": 5, "sha256": "a" * 64}
                )

    def test_consumer_detects_manifest_and_file_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "manifest.json"
            data = Path(tmp) / "geometry.json"
            data.write_bytes(b"{}")
            report = {
                "status": "normalized_candidate",
                "runtime_integration": False,
                "outputs": [
                    {
                        "path": data.name,
                        "size_bytes": 2,
                        "sha256": producer.sha256(data),
                        "layer_id": "geometry",
                    }
                ],
                "blocked_layers": ["road"],
            }
            report["fingerprint"] = hashlib.sha256(
                json.dumps(
                    report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest()
            producer.write_json(p, report)
            self.assertEqual(consumer.verify(p)["status"], "PASS")
            data.write_bytes(b"[]")
            with self.assertRaisesRegex(ValueError, "stale derived"):
                consumer.verify(p)
            report["blocked_layers"] = []
            producer.write_json(p, report)
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                consumer.verify(p)


if __name__ == "__main__":
    unittest.main()
