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

    def test_offshore_nodata_height_does_not_abort_stage1_alpha_site_scan(self):
        sample=m.sample_region(ExampleVolume(32768),ExampleVolume(0),{"i":2528,"j":8160})
        self.assertEqual(sample["ignored_outside_alpha_nodata_heights"],256)
        self.assertEqual(sample["invalid_height_inside_valid_alpha"],0)
        self.assertEqual(sample["alpha_fraction"],0)
        inland=m.sample_region(ExampleVolume(32768),ExampleVolume(1),{"i":2528,"j":8160})
        self.assertEqual(inland["invalid_height_inside_valid_alpha"],256)
        self.assertEqual(inland["alpha_fraction"],0)

    def test_high_elevation_does_not_count_as_coastal_height(self):
        data=m.sample_region(ExampleVolume(370),ExampleVolume(1),{"i":2528,"j":8160})
        self.assertEqual(data["alpha_fraction"],1)
        self.assertEqual(data["valid_low_elevation_fraction"],0)

    def test_alpha_joint_source_mask_requires_real_land_overlap(self):
        coast={"i":2528,"j":8160,
               "refined":{"alpha_joint_grid16":[0.85]*256}}
        a=m.sample_region(ExampleVolume(12.5),ExampleVolume(1.0),coast)
        self.assertEqual(a["valid_low_sand_overlap_count"],256)
        self.assertTrue(a["sand_joint_source_aligned"])
        b=m.sample_region(ExampleVolume(12.5),ExampleVolume(0.0),coast)
        self.assertEqual(b["valid_low_sand_overlap_count"],0)
        self.assertFalse(b["alpha_valid"])

    def test_coast_sand_alpha_intersection_outranks_offshore_high_sand(self):
        sites=[
            {"stage2":{"i":1000,"j":1000,"refined":{"mean":0.99}},
             "stage1":{"valid_low_sand_overlap_count":0,
                       "alpha_fraction":0.0,"valid_low_elevation_fraction":0.0}},
            {"stage2":{"i":5000,"j":5000,"refined":{"mean":0.05}},
             "stage1":{"valid_low_sand_overlap_count":5,
                       "alpha_fraction":0.15,"valid_low_elevation_fraction":0.1}},
        ]
        ranked=m.order_candidates(sites)
        self.assertEqual(ranked[0]["stage2"]["i"],5000)

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
