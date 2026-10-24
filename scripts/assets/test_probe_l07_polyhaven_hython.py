import importlib.util
from pathlib import Path
import tempfile
import unittest
from test_build_l07_polyhaven_bindings import fixture, module as binding_module, SELECTION

PATH = Path(__file__).with_name('probe_l07_polyhaven_hython.py')
spec = importlib.util.spec_from_file_location('l07nativeprobe', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_reader(path):
    n = 4096 if path.parent.name == '4k' else 2048
    return {'width': n, 'height': n, 'channels': 3,
            'pixel_format': 'uint8', 'channel_names': ['R', 'G', 'B']}


class NativeContractTests(unittest.TestCase):
    def test_exact_45_images_and_both_sizes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            binding = binding_module.prepare(root, SELECTION)
            result = module.inspect(binding, fake_reader, root)
            self.assertEqual(result['status'], 'HYTHON_OIIO_HEADERS_VERIFIED_NOT_COOKED')
            self.assertEqual(result['file_count'], 45)
            self.assertFalse(result['heightfield_modified'])

    def test_tampered_image_blocks_probe(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            binding = binding_module.prepare(root, SELECTION)
            p = Path(binding['houdini'][0]['files']['diff']['path'])
            p.write_bytes(b'tamper')
            with self.assertRaisesRegex(ValueError, 'Source bytes changed'):
                module.inspect(binding, fake_reader, root)

    def test_wrong_resolution_blocks_probe(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            binding = binding_module.prepare(root, SELECTION)
            def wrong_reader(p):
                return {'width': 42, 'height': 42, 'channels': 3,
                        'pixel_format': 'uint8', 'channel_names': ['R','G','B']}
            with self.assertRaisesRegex(ValueError, 'Wrong image dimensions'):
                module.inspect(binding, wrong_reader, root)

    def test_short_normal_map_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            binding = binding_module.prepare(root, SELECTION)
            def wrong_reader(p):
                result = fake_reader(p)
                if 'nor_gl' in p.name:
                    result['channels'] = 1
                return result
            with self.assertRaisesRegex(ValueError, 'Invalid normal channels'):
                module.inspect(binding, wrong_reader, root)


if __name__ == '__main__':
    unittest.main()
