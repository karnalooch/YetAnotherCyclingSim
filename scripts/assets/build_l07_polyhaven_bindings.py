#!/usr/bin/env python3
"""Build reversible Houdini and Unreal source bindings from verified Poly Haven files.

No UE import, HDA execution, terrain work, mask change, or conversion.
A downstream producer must prove the original Pegasus ORD(p) channel layout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

HOU_KINDS = ('diff', 'rough', 'nor_gl', 'disp')
UE_KINDS = ('diff', 'rough', 'nor_dx', 'ao', 'disp')


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def map_kind(slug: str, resolution: str, filename: str) -> str:
    for suffix in (*HOU_KINDS, *UE_KINDS):
        if filename.startswith(f'{slug}_{suffix}_{resolution}.'):
            if filename.rsplit('.', 1)[-1].lower() in ('png', 'jpg', 'exr'):
                return suffix
    raise ValueError(f'Unknown publisher file suffix: {filename}')


def load_map(root: Path, receipt: dict, selection: dict) -> dict:
    if receipt.get('status') != 'PH_CC0_SOURCE_BYTES_VERIFIED_NOT_INSTALLED':
        raise ValueError('Sources have not passed publisher MD5 verification')
    if receipt.get('source_selection') != selection:
        raise ValueError('Acquisition selection differs from current owner selection')
    out: dict[tuple[str, str, str], dict] = {}
    expected = set()
    for slug in selection['houdini'].values():
        expected.update((slug, '4k', kind) for kind in HOU_KINDS)
    for slug in selection['unreal_array']:
        expected.update((slug, '2k', kind) for kind in UE_KINDS)
    records = receipt.get('downloaded_files', [])
    if len(records) != len(expected):
        raise ValueError(f'Incomplete source receipt: {len(records)} vs {len(expected)}')
    for record in records:
        relative = record['relative_path']
        parts = Path(relative.replace('\\', '/')).parts
        if len(parts) != 3 or any(p in ('..', '.') for p in parts):
            raise ValueError(f'Unexpected source path: {relative}')
        slug, resolution, filename = parts
        kind = map_kind(slug, resolution, filename)
        key = (slug, resolution, kind)
        if key in out or key not in expected:
            raise ValueError(f'Duplicate or unauthorized source map: {key}')
        absolute = (root / slug / resolution / filename).resolve()
        if not absolute.is_relative_to(root.resolve()):
            raise ValueError('Source file escapes isolated root')
        if absolute.stat().st_size != record['size'] or sha(absolute) != record['sha256']:
            raise ValueError(f'File changed after source verification: {relative}')
        out[key] = {'path': str(absolute), 'sha256': record['sha256'],
                    'publisher_md5': record['provider_md5'], 'bytes': record['size'],
                    'role': kind, 'resolution': resolution,
                    'colorspace': 'sRGB' if kind == 'diff' else 'linear',
                    'normal_convention': 'OpenGL' if kind == 'nor_gl' else 'DirectX' if kind == 'nor_dx' else None}
    if set(out) != expected:
        raise ValueError('Map set does not match the selected 5 Houdini + 5 Unreal roles')
    return out


def prepare(root: Path, selection_file: Path) -> dict:
    selection = json.loads(selection_file.read_text(encoding='utf-8'))
    if selection.get('schema_version') != 1 or selection.get('license') != 'CC0':
        raise ValueError('Invalid source selection')
    receipt = json.loads((root / 'source-verification.json').read_text(encoding='utf-8'))
    maps = load_map(root, receipt, selection)
    houdini = []
    for role, slug in selection['houdini'].items():
        files = {kind: maps[(slug, '4k', kind)] for kind in HOU_KINDS}
        houdini.append({'role': role, 'slug': slug, 'files': files,
                        'hda_file_parms': {'filename1': files['diff']['path'],
                                           'filename2': files['rough']['path'],
                                           'filename3': files['disp']['path']},
                        'normal_source': files['nor_gl']['path']})
    unreal = []
    for index, slug in enumerate(selection['unreal_array']):
        files = {kind: maps[(slug, '2k', kind)] for kind in UE_KINDS}
        unreal.append({'index': index, 'slug': slug, 'files': files,
                       'conversion': 'NOT_PERFORMED',
                       'ordp_packing': 'BLOCKED_PENDING_ORIGINAL_SHADER_CHANNEL_PROOF'})
    return {'schema_version': 1, 'status': 'SOURCE_BINDINGS_VERIFIED_NO_MATERIAL_IMPORT',
            'license': 'CC0', 'owner_original_asset_1_to_1': False,
            'heightfield_modified': False, 'masks_modified': False,
            'houdini_cook': False, 'unreal_import': False,
            'source_receipt_sha256': sha(root / 'source-verification.json'),
            'houdini': houdini, 'unreal': unreal}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--selection', type=Path, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve()
    if __import__('os').name == 'nt':
        rp = str(root).lower().replace('/', '\\')
        if not rp.startswith('d:\\yacs\\work\\'):
            raise ValueError('Refuse source binding outside D:/yacs/work')
    result = prepare(root, args.selection)
    target = root / 'bindings-v1.json'
    data = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if target.exists() and target.read_text(encoding='utf-8') != data:
        raise ValueError('Existing bindings differ. Refuse overwrite; use a new versioned path.')
    if not target.exists():
        target.write_text(data, encoding='utf-8')
    print(json.dumps({'status': result['status'], 'houdini_roles': len(result['houdini']),
                      'unreal_slots': len(result['unreal']), 'manifest': str(target)}))


if __name__ == '__main__':
    main()
