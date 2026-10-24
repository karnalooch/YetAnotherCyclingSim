"""Offline tests: fixed vendor API fixture and tamper-aware source staging."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name('acquire_l07_polyhaven.py')
sp = importlib.util.spec_from_file_location('l07acquire', MODULE)
mod = importlib.util.module_from_spec(sp)
sp.loader.exec_module(mod)
SELECTION = Path(__file__).with_name('lesson07_polyhaven_sources.json')


def sample_tree(slug):
    result = {}
    for kind, suffix in (
        ('diffuse', 'diff'), ('rough', 'rough'), ('nor_gl', 'nor_gl'),
        ('nor_dx', 'nor_dx'), ('disp', 'disp'), ('ao', 'ao')
    ):
        result[kind] = {}
        for res in ('2k', '4k'):
            result[kind][res] = {}
            for ext in ('png', 'jpg', 'exr'):
                name = f'{slug}_{suffix}_{res}.{ext}'
                result[kind][res][ext] = {
                    'url': f'https://dl.polyhaven.org/file/ph-assets/Textures/{ext}/{res}/{slug}/{name}',
                    'size': 100,
                    'md5': '0' * 32,
                }
    return result


def fake_reader(path):
    kind, slug = path.split('/')
    if kind == 'info':
        titles = {x['slug']: x['name'] for x in mod.require_manifest(SELECTION)['assets']}
        return {'name': titles[slug], 'type': 1, 'files_hash': 'abcd'}
    if kind == 'files':
        return sample_tree(slug)
    raise KeyError(path)


class SelectionTests(unittest.TestCase):
    def test_fixed_manifest_and_roles(self):
        s = mod.require_manifest(SELECTION)
        self.assertEqual(len(s['assets']), 8)
        self.assertEqual(len(s['unreal_array']), 5)

    def test_manifest_rejects_wrong_license(self):
        s = mod.require_manifest(SELECTION)
        s['license'] = 'unknown'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'selection.json'
            p.write_text(json.dumps(s), encoding='utf-8')
            with self.assertRaises(ValueError):
                mod.require_manifest(p)

    def test_manifest_rejects_traversal_slug(self):
        s = mod.require_manifest(SELECTION)
        s['assets'][0]['slug'] = '../../evil'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'selection.json'
            p.write_text(json.dumps(s), encoding='utf-8')
            with self.assertRaises(ValueError):
                mod.require_manifest(p)

    def test_manifest_rejects_unknown_role(self):
        s = mod.require_manifest(SELECTION)
        s['houdini']['grass'] = 'surprise'
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'selection.json'
            p.write_text(json.dumps(s), encoding='utf-8')
            with self.assertRaises(ValueError):
                mod.require_manifest(p)

    def test_plan_has_required_45_maps(self):
        plan = mod.build_plan(mod.require_manifest(SELECTION), reader=fake_reader)
        self.assertEqual(plan['file_count'], 45)
        self.assertEqual(len(plan['publisher_assets']), 8)
        self.assertEqual(len([x for x in plan['files'] if x['resolution'] == '4k']), 20)
        self.assertEqual(len([x for x in plan['files'] if x['resolution'] == '2k']), 25)

    def test_plan_rejects_wrong_publisher_title(self):
        def reader(p):
            r = fake_reader(p)
            if p.startswith('info/'):
                r['name'] = 'Fake Name'
            return r
        with self.assertRaisesRegex(ValueError, 'Publisher type/title mismatch'):
            mod.build_plan(mod.require_manifest(SELECTION), reader=reader)

    def test_real_vendor_capitalized_map_keys(self):
        tree = sample_tree("dark_rock")
        for small, canonical in (("diffuse", "Diffuse"), ("rough", "Rough"), ("disp", "Displacement"), ("ao", "AO")):
            tree[canonical] = tree.pop(small)
        for kind in ("diffuse", "rough", "disp", "ao", "nor_gl", "nor_dx"):
            item = mod.choose_file(tree, "dark_rock", kind, "4k", ("png",))
            self.assertEqual(item["map"], kind)

    def test_missing_map_fails_closed(self):
        tree = sample_tree('dark_rock')
        del tree['disp']['4k']
        with self.assertRaisesRegex(ValueError, 'No suitable source file'):
            mod.choose_file(tree, 'dark_rock', 'disp', '4k', ('exr',))

    def test_fallback_format_requires_publisher_list(self):
        tree = sample_tree('dark_rock')
        del tree['disp']['4k']['exr']
        chosen = mod.choose_file(tree, 'dark_rock', 'disp', '4k', ('exr', 'png'))
        self.assertEqual(chosen['format'], 'png')

    def test_source_url_valid(self):
        name = mod.validate_source_url('https://dl.polyhaven.org/file/ph-assets/Textures/png/2k/dark_rock/dark_rock_nor_gl_2k.png', 'dark_rock')
        self.assertEqual(name, 'dark_rock_nor_gl_2k.png')

    def test_source_url_rejects_bad_host(self):
        with self.assertRaises(ValueError):
            mod.validate_source_url('https://other.example/file/ph-assets/Textures/dark_rock_diff_2k.png', 'dark_rock')

    def test_source_url_rejects_parent_path(self):
        with self.assertRaises(ValueError):
            mod.validate_source_url('https://dl.polyhaven.org/file/ph-assets/Textures/../dark_rock_diff_2k.png', 'dark_rock')

    def test_source_url_rejects_query(self):
        with self.assertRaises(ValueError):
            mod.validate_source_url('https://dl.polyhaven.org/file/ph-assets/Textures/dark_rock_diff_2k.png?token=x', 'dark_rock')

    def test_oversized_provider_file_fails_closed(self):
        tree = sample_tree('dark_rock')
        tree['disp']['4k']['exr']['size'] = mod.MAX_FILE_BYTES + 1
        with self.assertRaises(ValueError):
            mod.choose_file(tree, 'dark_rock', 'disp', '4k', ('exr',))


class AcquisitionTests(unittest.TestCase):
    def test_verified_local_file_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'dark_rock' / '4k' / 'dark_rock_diff_4k.jpg'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'abc')
            spec = {'slug': 'dark_rock', 'resolution': '4k', 'name': p.name, 'size': 3,
                    'url': 'https://dl.polyhaven.org/file/ph-assets/Textures/jpg/4k/dark_rock/dark_rock_diff_4k.jpg',
                    'provider_md5': hashlib.md5(b'abc').hexdigest()}
            observed = mod.verify_existing(p, spec)
            self.assertEqual(observed['sha256'], hashlib.sha256(b'abc').hexdigest())
            self.assertEqual(observed['status'], 'REUSED_VERIFIED')
            self.assertEqual(mod.download_one(Path(d), spec)['status'], 'REUSED_VERIFIED')

    def test_existing_tamper_aborts_without_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'dark_rock' / '4k' / 'dark_rock_diff_4k.jpg'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'original')
            spec = {'slug': 'dark_rock', 'resolution': '4k', 'name': p.name, 'size': 3,
                    'provider_md5': hashlib.md5(b'abc').hexdigest()}
            with self.assertRaisesRegex(ValueError, 'refuse overwrite'):
                mod.verify_existing(p, spec)
            self.assertEqual(p.read_bytes(), b'original')

    def test_verify_rejects_modified_readback(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sel = mod.require_manifest(SELECTION)
            relative = 'dark_rock/4k/dark_rock_diff_4k.jpg'
            p = root / relative
            p.parent.mkdir(parents=True)
            p.write_bytes(b'abc')
            report = {'status': 'PH_CC0_SOURCE_BYTES_VERIFIED_NOT_INSTALLED', 'source_selection': sel,
                      'verified_bytes': 3, 'downloaded_files': [
                          {'relative_path': relative, 'size': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}]}
            (root / 'source-verification.json').write_text(json.dumps(report), encoding='utf-8')
            self.assertEqual(mod.main(['verify', '--selection', str(SELECTION), '--destination', str(root)]), 0)
            p.write_bytes(b'def')
            with self.assertRaises(ValueError):
                mod.main(['verify', '--selection', str(SELECTION), '--destination', str(root)])

    def test_readback_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sel = mod.require_manifest(SELECTION)
            report = {'status': 'PH_CC0_SOURCE_BYTES_VERIFIED_NOT_INSTALLED', 'source_selection': sel,
                      'verified_bytes': 0, 'downloaded_files': [
                          {'relative_path': '../../danger', 'size': 1, 'sha256': 'x'}]}
            (root / 'source-verification.json').write_text(json.dumps(report), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Invalid manifest path'):
                mod.main(['verify', '--selection', str(SELECTION), '--destination', str(root)])


if __name__ == '__main__':
    unittest.main()
