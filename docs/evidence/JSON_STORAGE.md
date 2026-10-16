# Evidence JSON storage

Current storage rule for #365 / PR #474. World methodology remains in the
[World Building Bible](../WORLD_BUILDING_BIBLE.md); CI authority remains in
[CI validation tiers](../CI_VALIDATION_TIERS.md).

## Reviewed cleanup

Fourteen oversized historical rock run receipts were converted to `.json.gz`
using Python's standard gzip implementation, extending the existing natural20
`compressed-evidence.json` convention. Decompression preserves every original
byte, including CRLF, failure status and original producer SHA. SHA256 and the
original Git blob identity are checked. Historical `evidence.json` manifests
remain unchanged: their paths name captured originals and their hashes apply to
decompressed bytes. This is storage maintenance, not new runtime or visual proof.

Indexes: [large rocks](../assets/pcg365-large-rocks-20261012/compressed-evidence.json)
and [natural20](../assets/pcg365-natural20-20261012/compressed-evidence.json).
From the repository root, run `python scripts/ci/check_evidence_storage.py`.
To read an archive, use `gzip.open(path, "rb").read()`; to restore an original for
a historical external tool, decompress into an isolated temporary directory,
verify the index's original SHA256 and use that explicit path. Do not recommit it.

## Prevent recurrence

Ordinary CI verifies archive integrity and rejects new raw JSON above 1 MiB in
`docs/`. Four exact-byte exceptions preserve source/replay data pending a separate
consumer-aware migration, rather than deleting them merely because they are large:

- `docs/experiments/sa-calobra-road-materials-20261011/b9fd/road-asphalt-saved-manifest.json`
- `docs/experiments/sa-calobra-tpp-survey-20261008/manifest.json`
- `docs/experiments/sa-calobra-roadside-visibility-prestudy-20261008/observations.json`
- `docs/assets/pcg365-local-rock-pack-20261012/source-variant-pack.json`

Exceptions are pinned by original Git blob, not wildcard paths or extensible size
budgets. Schemas, recipes, source responses, geographic data and current Houdini
reports were not blanket-deleted or globally reformatted. Root Git attributes,
Unreal assets, source terrain, Live Host and physics inputs were not changed.
Existing Git history still retains the original blobs; no force push or history
rewrite is part of this cleanup. This reduces current checkout/review payload,
not the size of a complete historical clone.

The temporary PR474 audit/migration workflow is retired in the migration commit;
permanent checks live in the existing primary CI rather than another workflow.
The reusable large-file policy already belongs to Gumball; YACS-specific receipt
pins and historical paths stay downstream and are not a new proof framework.

## Implementation references

- Python gzip: https://docs.python.org/3/library/gzip.html
- Existing repository convention: natural20 `compressed-evidence.json`.
- Source audit revision: `b2b3f490aa228058b5cb4e6a09ec39e1254c0856`.
