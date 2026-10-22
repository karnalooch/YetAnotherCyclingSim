"""Deterministic real-sand site search guards, independent of native Houdini."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

FILE=Path(__file__).with_name("l07_scan_real_sand_sites.py")
sp=importlib.util.spec_from_file_location("l07_sand_scan",FILE)
scan=importlib.util.module_from_spec(sp)
sp.loader.exec_module(scan)


class FakeMaskVolume:
    def voxel(self,coords):
        i,j,_=coords
        if 50<=i<=200 and 50<=j<=200:
            return 0.6
        return 0.0


class ScanContract(unittest.TestCase):
    def test_actual_16k_source_pin_and_safe_256_crop(self):
        self.assertEqual(scan.PIN_SHA,
             "203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8")
        self.assertEqual(scan.WINDOW,256)
        self.assertEqual(scan.GRID,(16000,16000,1))
        self.assertEqual(scan.STEP,32)

    def test_256_crop_coverage_sampling(self):
        found=scan.refine_neighborhood(FakeMaskVolume(),128,128)
        self.assertEqual(found["sample_count"],1024)
        self.assertGreater(found["positive_samples"],0)
        self.assertGreater(found["mean"],0)
        self.assertLessEqual(found["max"],1)

    def test_diverse_selection_does_not_recommend_near_duplicates(self):
        rows=[
            {"i":500,"j":500,"refined":{"mean":.6,"positive_samples":100}},
            {"i":501,"j":501,"refined":{"mean":.9,"positive_samples":110}},
            {"i":1600,"j":1600,"refined":{"mean":.5,"positive_samples":100}},
        ]
        result=scan.select_diverse(rows,3)
        self.assertEqual(len(result),2)
        self.assertEqual((result[0]["i"],result[0]["j"]),(501,501))
        self.assertEqual((result[1]["i"],result[1]["j"]),(1600,1600))

    def test_no_sand_is_not_promoted_to_positive(self):
        result=scan.select_diverse([],8)
        self.assertEqual(result,[])


if __name__=="__main__":
    unittest.main()
