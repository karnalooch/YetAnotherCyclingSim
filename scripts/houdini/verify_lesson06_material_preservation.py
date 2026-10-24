"""Compare native UE height/mask readback before and after RGB-only binding."""
import hashlib
import json
import sys
from pathlib import Path
from repair_lesson06_idmap import read, volume, lattice

ROOT = Path(__file__).resolve().parents[2]
stage = sys.argv[1] if len(sys.argv)>1 else 'Lesson06MaterialSampling'
assert stage in ('Lesson06MaterialSampling','Lesson06ContextColor')
OUT = ROOT / 'Saved/RuntimeProof' / stage
BASE = ROOT / 'Saved/RuntimeProof/Lesson06DTMContext'
assert (OUT / 'native_after/complete.json').exists()
rows = []
samples = 0
for file in sorted((OUT / 'native_after').glob('*.bgeo.sc')):
    before = read(BASE / 'dtm_readback_originals' / file.name)
    after = read(file)
    labels = {p.attribValue('name') for p in before.prims()}
    assert labels == {p.attribValue('name') for p in after.prims()}
    for label in labels:
        a, b = volume(before, label), volume(after, label)
        assert lattice(a) == lattice(b), (file.name, label, 'lattice')
        assert a.allVoxelsAsString() == b.allVoxelsAsString(), (file.name, label)
        if label == 'height':
            x, y, z = a.resolution()
            samples += x * y * z
    rows.append({'name': file.stem, 'volumes': sorted(labels), 'status': 'BIT_EXACT'})
    print('UNCHANGED', file.name, flush=True)
assert len(rows) == 5
sources = json.loads((BASE / 'source_retention_current.json').read_text())['files']
for file, expected in sources.items():
    with open(file, 'rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    assert actual == expected, file
report = {'status': 'BIT_EXACT', 'height_samples': samples, 'tiles': rows,
          'source_files_verified': sources,
          'scope': 'Native readback of four Working actors and retained original Context; DTM Context geometry is covered by unchanged actor structure and RGB-only import scope.'}
(OUT / 'preservation.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS', samples, 'height samples;', len(sources), 'source files', flush=True)
