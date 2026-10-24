"""Pure guard tests for real 16K L06 window selection, no Hou or large files."""
import importlib.util
from pathlib import Path
import unittest

MODULE=Path(__file__).with_name("extract_l07_real_crop.py")
spec=importlib.util.spec_from_file_location("l07_real_crop",MODULE)
crop=importlib.util.module_from_spec(spec)
spec.loader.exec_module(crop)


class TestRealCropContract(unittest.TestCase):
    def test_bounded_scree_site_window(self):
        window=crop.compute_window((8089,11688,0))
        self.assertEqual(window,(7961,11560,8217,11816))
        self.assertEqual(window[2]-window[0],256)
        self.assertEqual(window[3]-window[1],256)

    def test_off_grid_window_denied(self):
        for pos in ((5,5,0),(15980,15980,0),(-1,0,0),(8000,8000,1)):
            with self.subTest(pos=pos):
                with self.assertRaises(ValueError):
                    crop.compute_window(pos)

    def test_pin_known_accepted_cache_hashes(self):
        self.assertEqual(crop.BASE_AND_MASKS['base']['sha256'],
                         '08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952')
        self.assertEqual(crop.BASE_AND_MASKS['masks']['sha256'],
                         '203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8')
        self.assertEqual(crop.GRID,(16000,16000,1))
        self.assertEqual(crop.CROP,256)
        for kind in ('base','masks'):
            self.assertEqual(len(crop.BASE_AND_MASKS[kind]['sha256']),64)

    def test_source_layers_are_exactly_original_cached_names(self):
        self.assertEqual(crop.BASE_AND_MASKS['base']['layers'],('height','mask','Alpha'))
        self.assertEqual(crop.BASE_AND_MASKS['masks']['layers'],
                         ('grass_mask','sand_mask','cliff_mask','ramp_layer'))

    def test_source_size_guard_rejects_unpinned_bytes(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            wrong=Path(tmp)/'stage1_base.bgeo.sc'
            wrong.write_bytes(b'not accepted terrain')
            with self.assertRaises(ValueError):
                crop.check_source(wrong,crop.BASE_AND_MASKS['base'])


if __name__=='__main__':
    unittest.main()
