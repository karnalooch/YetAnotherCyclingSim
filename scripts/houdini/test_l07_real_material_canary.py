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

    def test_png_chunk_crc(self):
        payload=b"abc"
        block=canary.png_chunk(b"tEXt",payload)
        self.assertEqual(struct.unpack(">I",block[:4])[0],len(payload))
        self.assertEqual(struct.unpack(">I",block[-4:])[0],zlib.crc32(b"tEXt"+payload)&0xFFFFFFFF)


if __name__=="__main__":
    unittest.main()
