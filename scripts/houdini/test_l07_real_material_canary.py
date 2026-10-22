"""CPU safety tests: five CC0 Pegasus HDA stages on real accepted source crops."""
import importlib.util
from pathlib import Path
import unittest
import zlib
import struct

p=Path(__file__).with_name("l07_real_material_canary.py")
spec=importlib.util.spec_from_file_location("l07_real_canary",p)
canary=importlib.util.module_from_spec(spec)
spec.loader.exec_module(canary)


class MaterialSiteTests(unittest.TestCase):
    def test_five_exact_role_assignments(self):
        self.assertEqual([x[0] for x in canary.ROLES],["rock","grass","sand","cliff","scree"])
        self.assertEqual([x[1] for x in canary.ROLES],
            ["dark_rock","sparse_grass","dense_sand","dark_rock_02","gray_rocks"])

    def test_masks_reference_bona_fide_stage2_or_explicit_scree_proxy(self):
        self.assertEqual([x[2] for x in canary.ROLES],
            [None,"grass_mask","sand_mask","cliff_mask","cliff_mask"])
        self.assertEqual(sum(bool(x[4]) for x in canary.ROLES),4)

    def test_stated_source_tile_size_and_height_immutable(self):
        self.assertEqual([x[3] for x in canary.ROLES],[1000.0,100.0,500.0,100.0,100.0])
        self.assertEqual(canary.SIZE,256)
        self.assertEqual(len(canary.PIN_HDA),64)
        self.assertEqual(canary.PROTECTED,
            ("height","mask","Alpha","grass_mask","sand_mask","cliff_mask","ramp_layer"))

    def test_compare_protected_detects_corrupted_height(self):
        expected={name:"sha_"+name for name in canary.PROTECTED}
        changed=dict(expected)
        changed["height"]="bad"
        with self.assertRaisesRegex(ValueError,"height"):
            canary.compare_protected(expected,changed,"rock")

    def test_compare_protected_detects_missing_mask(self):
        expected={name:"sha_"+name for name in canary.PROTECTED}
        changed=dict(expected)
        del changed["cliff_mask"]
        with self.assertRaisesRegex(ValueError,"cliff_mask"):
            canary.compare_protected(expected,changed,"cliff")

    def test_compare_protected_accepts_unchanged_protected_fields(self):
        expected={name:"sha_"+name for name in canary.PROTECTED}
        changed={**expected,"r":"rgb","roughness":"rough"}
        self.assertIsNone(canary.compare_protected(expected,changed,"grass"))

    def test_bounded_native_float32_rounding_restoration(self):
        self.assertTrue(canary.is_bounded_float_rounding(0.000030517578125,268))
        self.assertTrue(canary.is_bounded_float_rounding(0.0,0))
        self.assertFalse(canary.is_bounded_float_rounding(0.00011,268))
        self.assertFalse(canary.is_bounded_float_rounding(0.00003,10000))
        self.assertFalse(canary.is_bounded_float_rounding(float("nan"),1))
        self.assertFalse(canary.is_bounded_float_rounding(float("inf"),1))
        self.assertFalse(canary.is_bounded_float_rounding(-0.0001,1))

    def test_next_hda_uses_reopened_scratch_not_raw_material(self):
        source=Path(canary.__file__).read_text(encoding="utf-8")
        self.assertIn('previous=geo_obj.createNode("file","LOAD_SAFE_"+role.upper())',source)
        self.assertNotIn('previous=material',source)
        self.assertIn('target.setAllVoxelsFromString(original.tobytes())',source)

    def test_stage3_switch_is_explicitly_optional(self):
        self.assertEqual(canary.selected_mask("scree","cliff_mask",None),"cliff_mask")
        self.assertEqual(canary.selected_mask("scree","cliff_mask","39794174742-1"),"scree_mask")
        self.assertEqual(canary.selected_mask("cliff","cliff_mask","39794174742-1"),"cliff_mask")
        self.assertEqual(canary.selected_mask("grass","grass_mask","39794174742-1"),"grass_mask")

    def test_historical_scree_never_added_to_protected_production_layers(self):
        self.assertNotIn("scree_mask",canary.PROTECTED)
        self.assertEqual(canary.SIZE,256)

    def test_real_scree_verifier_is_called_by_correct_import_alias(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        class FakeArchive:
            files=["scree_mask"]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def __getitem__(self, key):
                self.files.index(key)
                return object()

        source=SimpleNamespace(
            float32="float32",
            load=lambda *args, **kwargs: FakeArchive(),
            array=lambda *args, **kwargs: SimpleNamespace(shape=(256,256)),
            isfinite=lambda _: SimpleNamespace(all=lambda: True),
        )
        receipt={"site_has_scree":True,"scree_nonzero":8619,
                 "source_stage3_upstream_lineage_accepted":False}
        with patch("scripts.houdini.verify_l07_scree_crop.verify", return_value=receipt) as check:
            mask, observed=canary.read_historical_scree_source("39785285512-1","39794174742-1",source)
            self.assertEqual(mask.shape,(256,256))
            self.assertEqual(observed["scree_nonzero"],8619)
            check.assert_called_once_with(
                canary.CROP_ROOT/"39794174742-1",canary.CROP_ROOT/"39785285512-1",source)

    def test_png_chunk_crc(self):
        payload=b"abc"
        block=canary.png_chunk(b"tEXt",payload)
        self.assertEqual(struct.unpack(">I",block[:4])[0],len(payload))
        self.assertEqual(struct.unpack(">I",block[-4:])[0],zlib.crc32(b"tEXt"+payload)&0xFFFFFFFF)


if __name__=="__main__":
    unittest.main()
