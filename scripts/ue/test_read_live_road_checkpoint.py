"""Fail-closed package, ownership and image validation for fresh #364 proof."""
import copy
import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from scripts.ue import read_live_road_checkpoint as reader


def receipt():
    prefix = 'Content/' + reader.PACKAGE.removeprefix('/Game/') + '/'
    labels = ['YACS_PERSIST_ROAD'] + [f'YACS_PERSIST_SUPPORT_{i:03}' for i in range(185)]
    return {'schema_version': 1, 'status': 'DERIVED_CHECKPOINT_SAVED',
            'revision': reader.SAVED_REVISION, 'map_package': reader.MAP,
            'preset': 'worn', 'active_source_unchanged': True, 'source_world': reader.SOURCE_WORLD,
            'native_mesh_comparison': {'actor_count': 559, 'all_attributes': True,
                                       'epsilon': 0.0, 'road_equal': True},
            'files': [{'path': prefix + name, 'bytes': size, 'sha256': digest}
                      for name, (size, digest) in reader.EXPECTED_FILES.items()],
            'bindings': [{'label': label, 'slot': 0 if label.endswith('ROAD') else 1,
                          'material': reader.PACKAGE + ('/MI_Road.MI_Road' if label.endswith('ROAD')
                                                        else '/MI_Shoulder.MI_Shoulder')}
                         for label in labels],
            'repair': {'road_unchanged': True, 'landscape_mutated': False,
                       'targets': [{'label': 'YACS_PERSIST_SUPPORT_112'}]}}


class CheckpointIdentityTests(unittest.TestCase):
    def test_fixed_saved_identity(self):
        value = receipt()
        self.assertIs(reader.validate_saved_receipt(value), value)

    def test_changed_package_or_duplicate_path_rejected(self):
        for mutation in ('hash', 'path', 'duplicate', 'missing'):
            with self.subTest(mutation=mutation):
                value = receipt()
                if mutation == 'hash':
                    value['files'][0]['sha256'] = '0' * 64
                elif mutation == 'path':
                    value['files'][0]['path'] = '../L_RoadSurface.umap'
                elif mutation == 'duplicate':
                    value['files'][1] = copy.deepcopy(value['files'][0])
                else:
                    value['files'].pop()
                with self.assertRaises(ValueError):
                    reader.validate_saved_receipt(value)

    def test_material_ownership_and_repair_scope_rejected(self):
        for mutation in ('owner', 'slot', 'material', 'repair', 'epsilon'):
            with self.subTest(mutation=mutation):
                value = receipt()
                if mutation == 'owner':
                    value['bindings'][1] = copy.deepcopy(value['bindings'][0])
                elif mutation == 'slot':
                    value['bindings'][0]['slot'] = 1
                elif mutation == 'material':
                    value['bindings'][0]['material'] = '/Engine/Transient.Foreign'
                elif mutation == 'repair':
                    value['repair']['landscape_mutated'] = True
                else:
                    value['native_mesh_comparison']['epsilon'] = 0.001
                with self.assertRaises(ValueError):
                    reader.validate_saved_receipt(value)

    def test_disk_tamper_detected_independently_from_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            path = project / 'Content/test.uasset'
            path.parent.mkdir()
            path.write_bytes(b'original')
            value = {'files': [{'path': 'Content/test.uasset', 'bytes': 8,
                               'sha256': hashlib.sha256(b'original').hexdigest()}]}
            self.assertEqual(reader.verify_packages(project, value), value['files'])
            path.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'Package bytes changed'):
                reader.verify_packages(project, value)

    def test_disk_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'escaped'):
                reader.verify_packages(Path(directory), {'files': [
                    {'path': '../escape', 'bytes': 1, 'sha256': '0' * 64}]})

    def test_screenshot_header_size_and_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'render.png'
            raw = b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR'
            path.write_bytes(raw + struct.pack('>II', 1280, 720) + bytes(5000))
            self.assertEqual(reader.validate_png(path)['bytes'], path.stat().st_size)
            path.write_bytes(raw + struct.pack('>II', 640, 360) + bytes(5000))
            with self.assertRaises(ValueError):
                reader.validate_png(path)


if __name__ == '__main__':
    unittest.main()
