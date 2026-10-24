#!/usr/bin/env python3
"""Read-only native Houdini/OIIO probe of all 45 selected PBR source images.

This checks image decoding metadata, not a material cook, UE import or visual PASS.
Outputs are written only to the isolated D: source work directory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for data in iter(lambda: fh.read(1 << 20), b''):
            h.update(data)
    return h.hexdigest()


def native_inspect(path: Path, oi) -> dict:
    image = oi.ImageInput.open(str(path))
    if image is None:
        raise ValueError(f'OpenImageIO cannot decode {path.name}: {oi.geterror()}')
    try:
        spec = image.spec()
        return {'width': int(spec.width), 'height': int(spec.height),
                'channels': int(spec.nchannels), 'pixel_format': str(spec.format),
                'channel_names': list(spec.channelnames)}
    finally:
        image.close()


def inspect(binding: dict, reader, root: Path) -> dict:
    if binding.get('status') != 'SOURCE_BINDINGS_VERIFIED_NO_MATERIAL_IMPORT':
        raise ValueError('Verified source bindings are required')
    images = {}
    for group_name in ('houdini', 'unreal'):
        for role in binding[group_name]:
            for kind, rec in role['files'].items():
                path = Path(rec['path']).resolve()
                if not path.is_relative_to(root.resolve()):
                    raise ValueError('Source image escapes the approved work root')
                expected = 4096 if group_name == 'houdini' else 2048
                if rec['resolution'] != ('4k' if group_name == 'houdini' else '2k'):
                    raise ValueError(f'Wrong source resolution label: {path.name}')
                if hash_file(path) != rec['sha256']:
                    raise ValueError(f'Source bytes changed: {path.name}')
                if str(path) in images:
                    if images[str(path)]['sha256'] != rec['sha256']:
                        raise ValueError('Duplicate image with diverging identity')
                    continue
                meta = reader(path)
                if meta['width'] != expected or meta['height'] != expected:
                    raise ValueError(f'Wrong image dimensions: {path.name}: {meta}')
                if not 1 <= meta['channels'] <= 4:
                    raise ValueError(f'Unsupported channel count: {path.name}')
                if kind.startswith('nor_') and meta['channels'] < 3:
                    raise ValueError(f'Invalid normal channels: {path.name}')
                images[str(path)] = {'sha256': rec['sha256'], 'expected_kind': kind, **meta}
    if len(images) != 45:
        raise ValueError(f'Expected 45 verified unique images, got {len(images)}')
    return {'schema_version': 1, 'status': 'HYTHON_OIIO_HEADERS_VERIFIED_NOT_COOKED',
            'source_count': 8, 'file_count': len(images),
            'verified_images': images, 'houdini_cook': False, 'unreal_import': False,
            'heightfield_modified': False, 'masks_modified': False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if __import__('os').name == 'nt' and not str(root).lower().replace('/', '\\').startswith('d:\\yacs\\work\\'):
        raise ValueError('Refuse native source proof outside D:/yacs/work')
    import hou
    import OpenImageIO as oi
    bindings = json.loads((root / 'bindings-v1.json').read_text(encoding='utf-8'))
    result = inspect(bindings, lambda p: native_inspect(p, oi), root)
    result['houdini_version'] = hou.applicationVersionString()
    target = root / 'hython-image-inspection.json'
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if target.exists() and target.read_text(encoding='utf-8') != payload:
        raise ValueError('Previous image inspection differs; refuse overwrite')
    if not target.exists():
        target.write_text(payload, encoding='utf-8')
    print(json.dumps({'status': result['status'], 'files': len(result['verified_images']),
                      'houdini_version': result['houdini_version'], 'receipt': str(target)}))


if __name__ == '__main__':
    main()
