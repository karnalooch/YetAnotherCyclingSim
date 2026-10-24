"""Pure safety contract for original historic Stage3 scree diagnostic, no native Hou."""
import copy
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).with_name("verify_l07_scree_crop.py")
spec=importlib.util.spec_from_file_location("stage3_scree_verify",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

FIRST=[-19.249916076660156,0.0,-1780.2501220703125]
LAST=[108.25013732910156,0.0,-1907.7501220703125]


def inputs():
    baseline={
        "status":"REAL_SOURCE_CROPS_VERIFIED_NO_MATERIAL_COOK",
        "crop_resolution":[256,256,1],
        "raw_source_resolution":[16000,16000,1],
        "extent_world":[FIRST.copy(),LAST.copy()],
    }
    report={
        "status":"HISTORICAL_STAGE3_SCREE_CROP_DIAGNOSTIC_NOT_ACCEPTED",
        "stage":"scree",
        "source":{"source_sha256":mod.EXPECTED_SHA,"source_size":96479665},
        "original_16000_grid":[16000,16000,1],
        "crop_size":256,
        "crop_index_window":mod.EXPECTED_WINDOW,
        "historical_scree_authority_admitted":False,
        "producer_upstream_lineage_verified":False,
        "heightfield_modified":False,
        "source_masks_modified":False,
        "layer_metadata":{"scree_mask":{
            "sha256_float32_le":"a"*64,"nonzero":42,
            "first_voxel_world_xyz":FIRST.copy(),
            "last_voxel_world_xyz":LAST.copy()}}
    }
    return report,baseline


class SourceAdmissionTests(unittest.TestCase):
    def test_pinned_exact_historical_sha_and_window(self):
        a,b=inputs()
        self.assertEqual(len(mod.EXPECTED_SHA),64)
        self.assertEqual(mod.validate_provenance(a,b)["nonzero"],42)

    def test_source_sha_mismatch_rejected(self):
        a,b=inputs()
        a["source"]["source_sha256"]="c"*64
        with self.assertRaisesRegex(ValueError,"identity"):
            mod.validate_provenance(a,b)

    def test_out_of_range_window_rejected(self):
        a,b=inputs()
        a["crop_index_window"]=[0,0,256,256]
        with self.assertRaisesRegex(ValueError,"site"):
            mod.validate_provenance(a,b)

    def test_bad_source_lattice_rejected(self):
        a,b=inputs()
        a["layer_metadata"]["scree_mask"]["first_voxel_world_xyz"][0]+=1
        with self.assertRaisesRegex(ValueError,"misregistered"):
            mod.validate_provenance(a,b)

    def test_forged_authority_pass_rejected(self):
        a,b=inputs()
        a["historical_scree_authority_admitted"]=True
        with self.assertRaisesRegex(ValueError,"promoted"):
            mod.validate_provenance(a,b)

    def test_missing_canonical_baseline_rejected(self):
        a,b=inputs()
        b["status"]="no"
        with self.assertRaisesRegex(ValueError,"not accepted"):
            mod.validate_provenance(a,b)


if __name__=="__main__":
    unittest.main()
