"""Tests for real Stage1/Stage2 coastal sand spatial-source selection."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

FILE=Path(__file__).with_name("l07_sand_height_alpha_site.py")
spec=importlib.util.spec_from_file_location("l07_sand_site",FILE)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ExampleVolume:
    def __init__(self,number):
        self.number=number
    def voxel(self,p):
        return self.number


class HeightAlphaSiteContract(unittest.TestCase):
    def test_accepted_height_and_mask_source_pins(self):
        self.assertEqual(m.STAGE1_SHA,"08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952")
        self.assertEqual(m.PIN_MASK_SHA,"203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8")
        self.assertEqual(m.GRID,(16000,16000,1))
        self.assertEqual(m.SIZE,256)

    def test_coarse_source_alpha_valid_low_elevation_coverage(self):
        site={"i":2528,"j":8160}
        data=m.sample_region(ExampleVolume(12.5),ExampleVolume(1.0),site)
        self.assertEqual(data["total"],256)
        self.assertEqual(data["alpha_valid"],256)
        self.assertEqual(data["valid_low_elevation_fraction"],1.0)
        self.assertEqual(data["valid_height_mean"],12.5)

    def test_outside_alpha_is_not_a_valid_real_source(self):
        data=m.sample_region(ExampleVolume(12.5),ExampleVolume(0.0),{"i":2528,"j":8160})
        self.assertEqual(data["alpha_valid"],0)
        self.assertEqual(data["valid_low_elevation_fraction"],0)

    def test_high_elevation_does_not_count_as_coastal_height(self):
        data=m.sample_region(ExampleVolume(370),ExampleVolume(1),{"i":2528,"j":8160})
        self.assertEqual(data["alpha_fraction"],1)
        self.assertEqual(data["valid_low_elevation_fraction"],0)

    def test_best_site_is_determined_by_stage1_quality_before_sand_density(self):
        sites=[
            {"stage2":{"i":500,"j":500,"refined":{"mean":1.0}},
             "stage1":{"alpha_fraction":.50,"valid_low_elevation_fraction":.45}},
            {"stage2":{"i":1000,"j":1000,"refined":{"mean":.75}},
             "stage1":{"alpha_fraction":1.0,"valid_low_elevation_fraction":.99}}
        ]
        result=m.order_candidates(sites)
        self.assertEqual(result[0]["stage2"]["i"],1000)


if __name__=="__main__":
    unittest.main()
