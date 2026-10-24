"""Unit tests for the accepted Sa Calobra 16K sand producer audit."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).with_name("l07_sand_source_audit.py")
spec=importlib.util.spec_from_file_location("l07_sand_producer",PATH)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def sample_report(sand_max:float=0.8)->dict:
    out={"stage":"stage2_masks","output_file":str(m.SOURCE),"sha256":m.PIN_SHA256}
    for name in ("grass_mask","sand_mask","cliff_mask","ramp_layer"):
        upper=sand_max if name=="sand_mask" else 1.0
        out[name]={"min":0.0,"max":upper,"mean":0.0 if upper==0 else 0.05*upper,
                   "count":256000000}
    return out


class SandSourceTests(unittest.TestCase):
    def test_exact_pinned_cache_identifiers(self):
        self.assertEqual(m.PIN_SIZE,1167222140)
        self.assertEqual(len(m.PIN_SHA256),64)
        self.assertEqual(m.ROOT.as_posix(),"D:/yacs/work/lesson06-unified-20261019")

    def test_source_has_positive_sand_value(self):
        stats=m.validate_producer_report(sample_report())["sand_mask"]
        self.assertGreater(stats["max"],0.0)

    def test_source_all_zero_sand_is_not_a_coast_pass(self):
        stats=m.validate_producer_report(sample_report(0.0))["sand_mask"]
        self.assertEqual(stats["max"],0.0)
        self.assertEqual(stats["mean"],0.0)

    def test_wrong_stage_sha_cannot_be_promoted(self):
        info=sample_report()
        info["sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"hash"):
            m.validate_producer_report(info)

    def test_sand_mean_cannot_exceed_source_max(self):
        info=sample_report()
        info["sand_mask"]["mean"]=1.0
        with self.assertRaisesRegex(ValueError,"range"):
            m.validate_producer_report(info)


if __name__=="__main__":
    unittest.main()
