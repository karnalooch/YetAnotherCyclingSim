import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).with_name('build_l07_polyhaven_bindings.py')
spec = importlib.util.spec_from_file_location('l07bindings', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SELECTION = Path(__file__).with_name('lesson07_polyhaven_sources.json')


def fixture(root):
    sel = json.loads(SELECTION.read_text(encoding='utf-8'))
    files = []
    wanted = {(slug, '4k', k) for slug in sel['houdini'].values() for k in module.HOU_KINDS}
    wanted.update((slug, '2k', k) for slug in sel['unreal_array'] for k in module.UE_KINDS)
    for slug, resolution, kind in sorted(wanted):
        filename = f'{slug}_{kind}_{resolution}.png'
        p = root / slug / resolution / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes((filename * 2).encode())
        files.append({'relative_path': f'{slug}/{resolution}/{filename}', 'size': p.stat().st_size,
                      'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                      'provider_md5': hashlib.md5(p.read_bytes()).hexdigest()})
    report = {'status': 'PH_CC0_SOURCE_BYTES_VERIFIED_NOT_INSTALLED',
              'source_selection': sel, 'downloaded_files': files}
    (root / 'source-verification.json').write_text(json.dumps(report), encoding='utf-8')
    return sel, report


class TestBindings(unittest.TestCase):
    def test_build_all_ten_assignments_from_45_maps(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sel, receipt = fixture(root)
            result = module.prepare(root, SELECTION)
            self.assertEqual(result['status'], 'SOURCE_BINDINGS_VERIFIED_NO_MATERIAL_IMPORT')
            self.assertEqual(len(result['houdini']), 5)
            self.assertEqual(len(result['unreal']), 5)
            self.assertEqual(result['houdini'][0]['slug'], 'dark_rock')
            self.assertEqual(result['unreal'][3]['slug'], 'dark_rock_02')
            self.assertEqual(result['houdini'][0]['files']['nor_gl']['normal_convention'], 'OpenGL')
            self.assertEqual(result['unreal'][3]['files']['nor_dx']['normal_convention'], 'DirectX')
            self.assertFalse(result['heightfield_modified'])
            self.assertFalse(result['houdini_cook'])

    def test_rejects_changed_source_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sel, receipt = fixture(root)
            p = root / receipt['downloaded_files'][0]['relative_path']
            p.write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'File changed'):
                module.prepare(root, SELECTION)

    def test_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sel, receipt = fixture(root)
            receipt['downloaded_files'].pop()
            (root / 'source-verification.json').write_text(json.dumps(receipt), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Incomplete source receipt'):
                module.prepare(root, SELECTION)

    def test_rejects_selection_drift(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sel, receipt = fixture(root)
            sel['houdini']['rock'] = 'gray_rocks'
            p = root / 'changed.json'
            p.write_text(json.dumps(sel), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'differs'):
                module.prepare(root, p)

    def test_rejects_directory_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sel, receipt = fixture(root)
            receipt['downloaded_files'][0]['relative_path'] = '../../evil'
            (root / 'source-verification.json').write_text(json.dumps(receipt), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unexpected source path'):
                module.prepare(root, SELECTION)


if __name__ == '__main__':
    unittest.main()
