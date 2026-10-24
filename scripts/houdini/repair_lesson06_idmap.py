"""Bounded Lesson06 repair/replay; never save or rebuild Lesson02-05 outputs.

Run each domain in a separate CPU hython process. --verify rebuilds only the
saved IDMap chain from retained mask files and compares every native sample.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import hou
import numpy as np

PROJECT = Path(__file__).resolve().parents[2]
WORLD = PROJECT / 'worldgen/houdini/sa_calobra'
NAMES = ['grass', 'grass 2', 'sand', 'cliffs', 'scree']
FILES = ['sop_PE_heightield_idmap_layers.hda', 'sop_PE_Heightfield_id_to_layer.hda']


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def volume(geo, name):
    return next(p for p in geo.prims() if p.attribValue('name') == name)


def values(geo, name):
    return np.frombuffer(volume(geo, name).allVoxelsAsString(), np.float32)


def lattice(p):
    return {'resolution': list(p.resolution()),
            'origin': list(p.indexToPos((0, 0, 0))),
            'x': list(p.indexToPos((1, 0, 0)) - p.indexToPos((0, 0, 0))),
            'y': list(p.indexToPos((0, 1, 0)) - p.indexToPos((0, 0, 0)))}


def read(path):
    g = hou.Geometry()
    g.loadFromFile(str(path))
    return g


def geometry(node):
    node.cook(force=True)
    g = node.geometry()
    assert not node.errors(), (node.path(), node.errors())
    return g


def prepare_hdas(corpus, readonly=False):
    original = corpus / 'P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls'
    target = WORLD / 'otls/lesson06_reviewed'
    target.mkdir(exist_ok=True)
    rows = []
    for filename in FILES:
        src, dst = original / filename, target / filename
        definition = hou.hda.definitionsInFile(str(src))[0]
        if readonly:
            assert dst.is_file(), dst
        else:
            if not dst.exists():
                definition.copyToHDAFile(str(dst))
            hou.hda.installFile(str(dst))
            copied = hou.hda.definitionsInFile(str(dst))[0]
            if 'idmap_layers' in filename:
                # HDAModule kwargs contains type, not node (SideFX HOM 22.0).
                source = copied.sections()['PythonModule'].contents()
                assert "node = kwargs['node']" in source or 'kwargs.get("node")' in source
                if "node = kwargs['node']" in source:
                    copied.addSection('PythonModule', 'node = kwargs.get("node")\nif node is not None:\n    for output in node.outputs():\n        output.cook(force=True)\n')
            else:
                group = copied.parmTemplateGroup()
                menu = group.find('id_layer')
                source = menu.itemGeneratorScript()
                assert 'int(i*sf)' in source or 'int(round(i*sf))' in source
                updated = source.replace('int(i*sf)', 'int(round(i*sf))').replace('if geo.dictAttribValue("id"):', 'if geo.findGlobalAttrib("id") is not None and geo.dictAttribValue("id"):')
                if updated != source:
                    menu.setItemGeneratorScript(updated)
                    group.replace('id_layer', menu)
                    copied.setParmTemplateGroup(group)
        installed = hou.hda.definitionsInFile(str(dst))[0]
        # Algorithms must remain byte-identical to the original source bundle.
        assert installed.sections()['Contents.gz'].contents() == definition.sections()['Contents.gz'].contents()
        rows.append({'original': str(src), 'original_sha256': digest(src),
                     'loaded': str(dst), 'loaded_sha256': digest(dst),
                     'contents_identical': True})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--corpus', type=Path, required=True)
    ap.add_argument('--hip', type=Path, required=True)
    ap.add_argument('--output-hip', type=Path)
    ap.add_argument('--root', type=Path, required=True)
    ap.add_argument('--area', choices=['context', 'working'], required=True)
    ap.add_argument('--verify', action='store_true')
    a = ap.parse_args()
    assert hou.applicationVersionString() == '22.0.466'
    assert os.environ.get('HOUDINI_OCL_DEVICETYPE') == 'CPU'
    rows = prepare_hdas(a.corpus, readonly=a.verify)
    hou.setUpdateMode(hou.updateMode.Manual)
    hou.hipFile.load(str(a.hip), suppress_save_prompt=True)
    if not a.verify:
        for row in rows:
            hou.hda.installFile(row['loaded'])
            hou.hda.definitionsInFile(row['loaded'])[0].setIsPreferred(True)
    for area in ['CONTEXT', 'WORKING']:
        group = hou.node('/obj/LESSON06_' + area)
        for name, row in zip(['ID_MAP_LAYERS', 'ID_TO_LAYER'], rows):
            node = group.node(name)
            assert Path(node.type().definition().libraryFilePath()).resolve() == Path(row['loaded']).resolve()
            if not a.verify:
                node.matchCurrentDefinition()
            else:
                assert node.matchesCurrentDefinition(), node.path()
        if not a.verify:
            decoder = group.node('ID_TO_LAYER')
            decoder.destroy()
            decoder = group.createNode('PE_Heightfield_id_to_layer', 'ID_TO_LAYER')
            decoder.setInput(0, group.node('FINAL_CACHE'))
            print('DECODER_DEFINITION', decoder.type().definition().libraryFilePath(), flush=True)
    g = hou.node('/obj/LESSON06_' + a.area.upper())
    out = a.root / a.area
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / ('reopen.json' if a.verify else 'repair.json')
    assert not report_path.exists(), 'Do not overwrite completed proof'
    baseline_node = hou.node('/obj/LESSON05_' + a.area.upper() + '/FINAL_CACHE')
    baseline_path = baseline_node.parm('file').eval()
    baseline = read(baseline_path)
    base_lattice = lattice(volume(baseline, 'height'))
    assert base_lattice['resolution'] == ([7154, 9829, 1] if a.area == 'working' else [2048, 2048, 1])
    report = {'status': 'IN_PROGRESS', 'area': a.area, 'base_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PROJECT, text=True).strip(),
              'input_hip': str(a.hip), 'input_hip_sha256': digest(a.hip), 'hda': rows,
              'baseline': baseline_path, 'baseline_sha256': digest(baseline_path),
              'lattice': base_lattice, 'masks': {}, 'materials': {}}
    old_path = Path('D:/yacs/work/lesson06-idmap-20261018') / a.area / 'final.bgeo.sc'
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    if not a.verify:
        old = read(old_path)
        for name in NAMES:
            safe = name.replace(' ', '_')
            om = g.node('MERGE_' + safe.upper() + '_MASK')
            producer = om.parm('objpath1').eval()
            mask_path = out / (safe + '_mask.bgeo.sc')
            # Reuse retained tint/cliff/scree samples. Only read the unchanged
            # grass/sand selectors fed by the saved Source + Manual caches.
            if mask_path.exists():
                source, layer = read(mask_path), 'mask'
            elif name == 'grass 2':
                source, layer = old, 'ramp_layer'
            elif name in ['cliffs', 'scree']:
                source, layer = baseline, {'cliffs': 'cliff', 'scree': 'scree'}[name]
            else:
                source, layer = geometry(hou.node(producer)), 'mask'
            assert lattice(volume(source, layer)) == base_lattice, (name, 'grid mismatch')
            mask = hou.Geometry()
            mask.merge(source)
            mask.deletePrims([p for p in mask.prims() if p.attribValue('name') != layer], True)
            volume(mask, layer).setAttribValue('name', 'mask')
            if mask_path.exists():
                assert volume(read(mask_path), 'mask').allVoxelsAsString() == volume(mask, 'mask').allVoxelsAsString(), 'Retained mask changed'
            else:
                mask.saveToFile(str(mask_path))
            f = g.createNode('file', 'RETAINED_' + safe.upper())
            f.parm('file').set(str(mask_path))
            n = g.createNode('null', 'OUT_RETAINED_' + safe.upper())
            n.setInput(0, f)
            n.setComment('Unchanged source mask: ' + producer + '; retained layer: ' + layer)
            om.parm('objpath1').set(n.path())
            report['masks'][name] = {'producer': producer, 'source_layer': {'grass 2': 'ramp_layer', 'cliffs': 'cliff', 'scree': 'scree'}.get(name, 'mask'), 'cache': str(mask_path), 'sha256': digest(mask_path)}
            print('MASK_RETAINED', a.area, name, flush=True)
        del old
    else:
        previous = json.loads((out / 'repair.json').read_text())
        report['masks'] = previous['masks']
        for info in report['masks'].values():
            assert digest(info['cache']) == info['sha256']
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    # Native encoder owns generation. NumPy below is an independent comparison
    # oracle only; it never writes encoded or decoded geometry.
    expected = np.zeros(np.prod(base_lattice['resolution']), np.float32)
    encoder_file = a.corpus / 'P1_02_Landscape_Workflow/Materialy/ProjectFiles_LandscapeWorkflow3/ProjectFiles_LandscapeWorkflow/Houdini/Packages/PegasusDemo/otls/sop_PE_Heightfield_Layers_to_ID.2.0.hda'
    original_encoder = hou.hda.definitionsInFile(str(encoder_file))[0]
    report['encoder'] = {'original_sha256': digest(encoder_file), 'contents_identical': True, 'adaptation': 'Inherited empty-metadata menu guard only'}
    for name in NAMES:
        safe = name.replace(' ', '_')
        n = g.node(safe + '_layer')
        assert n.type().name() == 'PE_Heightfield_Layers_to_ID::2.0'
        assert n.type().definition().sections()['Contents.gz'].contents() == original_encoder.sections()['Contents.gz'].contents()
        assert n.parm('id_layer').eval() == NAMES.index(name)
        assert n.parm('layer_1').eval() == 'mask'
        assert n.inputs()[1] == g.node('MERGE_' + safe.upper() + '_MASK')
        retained_null = hou.node(n.inputs()[1].parm('objpath1').eval())
        assert Path(retained_null.inputs()[0].parm('file').eval()).resolve() == Path(report['masks'][name]['cache']).resolve()
        mask_geo = read(report['masks'][name]['cache'])
        assert lattice(volume(mask_geo, 'mask')) == base_lattice
        mask = values(mask_geo, 'mask')
        assert np.isfinite(mask).all()
        code = n.parm('id').evalAsInt()
        threshold = n.parm('tolerance_1').eval()
        assert threshold == 0.5
        expected[mask >= threshold] = np.float32(code / 255.0)
        report['materials'][name] = {'code': code, 'threshold': threshold, 'source_min': float(mask.min()), 'source_max': float(mask.max()), 'source_selected': int(np.count_nonzero(mask >= threshold))}
    start = time.monotonic()
    final = g.node('scree_layer')
    final.cook(force=True)
    cooked = geometry(final)
    report['native_cook_seconds'] = time.monotonic() - start
    actual = values(cooked, 'id')
    bad = np.flatnonzero(actual != expected)
    report['raw_voxel_threshold_mismatches'] = int(len(bad))
    report['native_sampling_checks'] = []
    if len(bad):
        # VEX volumesample samples in world space using float32 @P. On the
        # 3.90625 m Context lattice this can differ from a direct array lookup.
        sampled_codes = np.zeros(len(bad), np.float32)
        native_samples = {}
        for name in NAMES:
            original = g.node(name.replace(' ', '_') + '_layer/volumewrangle1')
            probe_input = g.createNode('object_merge', 'PROBE_INPUT')
            probe_input.parm('objpath1').set(original.inputs()[0].path())
            probe = original.copyTo(g)
            probe.setInput(0, probe_input)
            # Diagnostic measurement of the exact original volumesample call.
            # It never feeds an authoring node or overwrites a source mask.
            probe.parm('snippet').set('f@id = volumesample(0, "mask", @P);')
            sampled = values(geometry(probe), 'id')[bad].copy()
            native_samples[name] = sampled
            sampled_codes[sampled >= report['materials'][name]['threshold']] = report['materials'][name]['code']
            probe.destroy()
            probe_input.destroy()
        for offset, i in enumerate(bad):
            code = float(sampled_codes[offset])
            assert abs(float(actual[i]*255) - code) < 0.0001, (int(i), code, float(actual[i]*255))
            report['native_sampling_checks'].append({'index': int(i), 'code': code, 'samples': {n:float(native_samples[n][offset]) for n in NAMES}})
            expected[i] = np.float32(code / 255.0)
    assert np.array_equal(actual, expected), ('source-placement mismatch', np.count_nonzero(actual != expected))
    report['placement_mismatches'] = 0
    report['invariants'] = {}
    for name in ['height', 'r', 'g', 'b', 'roughness', 'Alpha']:
        assert lattice(volume(cooked, name)) == lattice(volume(baseline, name))
        assert volume(cooked, name).allVoxelsAsString() == volume(baseline, name).allVoxelsAsString(), name
        report['invariants'][name] = 'BIT_EXACT'
    cache_path = out / 'final.bgeo.sc'
    if not a.verify:
        if cache_path.exists():
            assert volume(read(cache_path), 'id').allVoxelsAsString() == volume(cooked, 'id').allVoxelsAsString()
        else:
            cooked.saveToFile(str(cache_path))
        g.node('FINAL_CACHE').parm('file').set(str(cache_path))
    cached = read(cache_path)
    assert volume(cached, 'id').allVoxelsAsString() == volume(cooked, 'id').allVoxelsAsString()
    report['cache'] = str(cache_path)
    report['cache_sha256'] = digest(cache_path)
    report['fresh_native_id_matches_cache'] = True
    # Original decoder from LandscapeWorkflow3, with menu rounding correction.
    decoder = g.node('ID_TO_LAYER')
    decoder.setInput(0, g.node('FINAL_CACHE'))
    decoder.parm('srcname1').set('id')
    decoder.parm('dstname1').set('mask')
    tokens = decoder.parm('id_layer').menuItems()
    assert tokens == tuple(str(report['materials'][n]['code']) for n in NAMES), tokens
    res = base_lattice['resolution']
    shape = (res[1], res[0])
    previews = {'height': values(cached, 'height').reshape(shape)[::8, ::8], 'id': actual.reshape(shape)[::8, ::8]}
    for name in NAMES:
        row = report['materials'][name]
        decoder.parm('id_layer').set(str(row['code']))
        decoded_geo = geometry(decoder)
        decoded = values(decoded_geo, 'mask')
        selected = actual == np.float32(row['code'] / 255.0)
        assert np.array_equal(decoded > 0.5, selected), name
        row['decoded_spatial_mismatches'] = 0
        row['count'] = int(np.count_nonzero(selected))
        previews[name] = decoded.reshape(shape)[::8, ::8].copy()
        # Exercise native Ramp and Isolate. Both must preserve ID and height.
        node = g.node(name.replace(' ', '_') + '_layer')
        for mode in [1, 2]:
            node.parm('input').set(mode)
            visible = geometry(node)
            assert volume(visible, 'height').allVoxelsAsString() == volume(baseline, 'height').allVoxelsAsString()
            row['native_' + ('ramp' if mode == 1 else 'isolate')] = {'errors': list(node.errors()), 'warnings': list(node.warnings()), 'detail_attributes': [v.name() for v in visible.globalAttribs()]}
        node.parm('input').set(1)
        print('VERIFIED', a.area, name, row['count'], flush=True)
        # Preserve native-resolution closeup around an actual decoded sample.
        indices = np.flatnonzero(selected)
        if len(indices):
            y, x = divmod(int(indices[len(indices)//2]), shape[1])
            y, x = max(0, min(y-128, shape[0]-256)), max(0, min(x-128, shape[1]-256))
            source = values(read(report['masks'][name]['cache']), 'mask').reshape(shape)
            np.savez_compressed(out / ('detail_' + name.replace(' ', '_') + '.npz'), source=source[y:y+256, x:x+256], decoded=decoded.reshape(shape)[y:y+256, x:x+256], id=actual.reshape(shape)[y:y+256, x:x+256], height=values(cached, 'height').reshape(shape)[y:y+256, x:x+256])
            row['detail_window_xy'] = [x, y, 256, 256]
    np.savez_compressed(out / 'native_previews.npz', **previews)
    # Full-resolution perimeter samples enable cross-grid boundary assessment.
    id_grid = actual.reshape(shape)
    np.savez_compressed(out / 'boundary.npz', id=id_grid if a.area == 'context' else np.concatenate([id_grid[0], id_grid[-1], id_grid[:,0], id_grid[:,-1]]))
    if not a.verify:
        assert a.output_hip and not a.output_hip.exists()
        decoder.parm('id_layer').set('0')
        g.layoutChildren()
        hou.hipFile.save(str(a.output_hip))
        report['output_hip'] = str(a.output_hip)
        report['output_hip_sha256'] = digest(a.output_hip)
    assert digest(baseline_path) == report['baseline_sha256']
    report['status'] = 'NATIVE_AREA_PASS'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('NATIVE_AREA_PASS', a.area, 'fresh_reopen' if a.verify else 'repair', flush=True)


if __name__ == '__main__':
    main()
