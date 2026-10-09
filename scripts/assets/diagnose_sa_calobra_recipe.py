"""Diagnose saved whole-map recipe vs local files; repair only CRLF normalization.

Never edits Unreal packages, source receipts, map, or material parameters. Only
rewrites the catalogue when its LF-normalized bytes exactly match the SHA256
already recorded in the immutable accepted native proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.ue import sa_calobra_whole_map_prep as prep


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def differences(expected, actual, prefix=""):
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(expected.keys() | actual.keys())
        for key in keys:
            name = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected or key not in actual:
                yield name
            else:
                yield from differences(expected[key], actual[key], name)
    elif expected != actual:
        yield prefix


def check(proof_root: Path, backup_dir: Path, normalize_lf: bool = False):
    proof_root = proof_root.resolve(strict=True)
    master_path = proof_root / "whole-map-master-receipt.json"
    master_raw = master_path.read_bytes()
    master = json.loads(master_raw)
    if master.get("status") != "WHOLE_MAP_FIXED_MASTER_SAVED":
        raise ValueError("Proof master is not an accepted saved candidate")

    expected = master["rendering_recipe"]
    expected_hash = master["rendering_recipe_sha256"]
    if sha256(prep.canonical(expected)) != expected_hash:
        raise ValueError("Proof master's recipe digest does not match its contents")

    manifest_path = proof_root / "whole-map-prep/surface-prep-manifest.json"
    manifest_hash = sha256(manifest_path.read_bytes())
    if manifest_hash != master.get("prep_manifest_sha256"):
        raise ValueError(
            "Source manifest differs from accepted proof: "
            f"proof={master.get('prep_manifest_sha256')} actual={manifest_hash}"
        )

    relative = expected.get("source_catalogue")
    if relative != "worldgen/materials/sa_calobra_texture_library_v2_20261005.json":
        raise ValueError(f"Unexpected source catalogue path: {relative!r}")
    catalogue_path = prep.ROOT / relative
    source = catalogue_path.read_bytes()
    pinned = expected["source_catalogue_sha256"]
    actual = sha256(source)

    if actual != pinned:
        normalized = source.replace(b"\r\n", b"\n")
        normalized_hash = sha256(normalized)
        if normalized == source or normalized_hash != pinned:
            raise ValueError(
                "Catalogue differs from immutable recipe (not just CRLF). "
                f"expected={pinned}, actual={actual}, normalized={normalized_hash}. "
                "No file changed; review the local Git checkout or modifications."
            )
        if not normalize_lf:
            raise ValueError(
                "Catalogue differs ONLY in CRLF line endings. "
                "Re-run the launcher, which safely normalizes LF after backing up "
                "the original bytes; no other content will be changed."
            )
        backup_dir = backup_dir.resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / ("catalogue-before-" + actual[:16] + ".json.bak")
        if backup.exists() and sha256(backup.read_bytes()) != actual:
            raise ValueError("Existing catalogue backup name conflicts")
        if not backup.exists():
            backup.write_bytes(source)
        if sha256(backup.read_bytes()) != actual:
            raise ValueError("Catalogue backup integrity check failed")
        temporary = catalogue_path.with_name(catalogue_path.name + ".review-tmp")
        if temporary.exists():
            raise ValueError("Refusing to overwrite existing temporary catalogue")
        temporary.write_bytes(normalized)
        if sha256(temporary.read_bytes()) != pinned:
            temporary.unlink()
            raise ValueError("Normalized catalogue hash mismatch")
        temporary.replace(catalogue_path)
        actual = sha256(catalogue_path.read_bytes())
        print(f"Only CRLF->LF normalized: {relative}; saved original at {backup}")

    current = prep.rendering_recipe()
    mismatches = list(differences(expected, current))
    current_hash = sha256(prep.canonical(current))
    if mismatches or current_hash != expected_hash:
        raise ValueError(
            "Local rendering recipe is different from proof; "
            f"fields={mismatches[:20]}, expected_sha256={expected_hash}, "
            f"current_sha256={current_hash}. No material/map files changed."
        )
    print(
        json.dumps(
            {
                "status": "MATCH",
                "proof_exact_sha": master["exact_sha"],
                "manifest_sha256": manifest_hash,
                "recipe_sha256": current_hash,
                "catalogue_sha256": actual,
            },
            sort_keys=True,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-root", required=True, type=Path)
    parser.add_argument("--backup-dir", required=True, type=Path)
    parser.add_argument("--normalize-catalogue-lf", action="store_true")
    args = parser.parse_args()
    check(args.proof_root, args.backup_dir, args.normalize_catalogue_lf)


if __name__ == "__main__":
    main()
