"""Unit tests for chunked full-domain 16000x16000 Houdini producer."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MOD_PATH = Path(__file__).with_name("l07_full_domain_producer.py")
spec = importlib.util.spec_from_file_location("l07_full_domain_producer", MOD_PATH)
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


class FullDomainProducerTests(unittest.TestCase):
    def test_quadrant_halo_windows_cover_16000_domain(self):
        w00 = producer.compute_tile_window(0, 0, core=8000, halo=304)
        w10 = producer.compute_tile_window(1, 0, core=8000, halo=304)
        w01 = producer.compute_tile_window(0, 1, core=8000, halo=304)
        w11 = producer.compute_tile_window(1, 1, core=8000, halo=304)

        self.assertEqual(w00["core"], [0, 0, 8000, 8000])
        self.assertEqual(w00["halo_window"], [0, 0, 8304, 8304])
        self.assertEqual(w00["core_offset_in_halo"], [0, 0, 8000, 8000])
        self.assertEqual(w00["halo_first_world_xyz"], [-3999.75, 0.0, 3999.75])

        self.assertEqual(w11["core"], [8000, 8000, 16000, 16000])
        self.assertEqual(w11["halo_window"], [7696, 7696, 16000, 16000])
        self.assertEqual(w11["core_offset_in_halo"], [304, 304, 8304, 8304])

        # Adjacent core edges meet seamlessly at 8000
        self.assertEqual(w00["core"][2], w10["core"][0])
        self.assertEqual(w00["core"][3], w01["core"][1])

    def test_halo_smaller_than_145m_occlusion_rejected(self):
        with self.assertRaisesRegex(ValueError, "145m"):
            producer.compute_tile_window(0, 0, core=8000, halo=280)

    def test_five_class_id_encoding_matches_pegasus_vex_order(self):
        import numpy as np

        grass = np.array([[0.0, 0.8, 0.9, 0.9, 0.9, 0.9]], dtype=np.float32)
        ramp = np.array([[0.0, 0.0, 0.7, 0.7, 0.7, 0.7]], dtype=np.float32)
        sand = np.array([[0.0, 0.0, 0.0, 0.6, 0.6, 0.6]], dtype=np.float32)
        cliff = np.array([[0.0, 0.0, 0.0, 0.0, 0.9, 0.9]], dtype=np.float32)
        scree = np.array([[0.0, 0.0, 0.0, 0.0, 0.0, 0.8]], dtype=np.float32)
        ids = producer.compute_five_class_id_u8(grass, ramp, sand, cliff, scree, np)
        self.assertEqual(ids.tolist(), [[0, 0, 64, 128, 191, 255]])

    def test_srgb_conversion_matches_iec_standard(self):
        import numpy as np

        lin = np.array([[[0.0, 0.21404114, 1.0]]], dtype=np.float32)
        srgb = producer.linear_to_srgb_u8(lin, np)
        self.assertEqual(srgb.tolist(), [[[0, 128, 255]]])


if __name__ == "__main__":
    unittest.main()
