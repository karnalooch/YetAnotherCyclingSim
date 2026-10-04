"""Verify or restore a checkpoint data manifest from downloaded release assets.

Default: verify existing files and report missing ones. --apply restores only
missing files, verifies every byte and never replaces an existing file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile


def safe_path(root: Path, relative: str) -> Path:
    parts = PurePosixPath(relative)
    if (
        not relative
        or parts.is_absolute()
        or ".." in parts.parts
        or "\\" in relative
        or ":" in relative
    ):
        raise ValueError("Unsafe manifest path: " + relative)
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Manifest path escapes destination: " + relative)
    return path


def verify(path: Path, item: dict) -> None:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    if path.stat().st_size != item["size_bytes"] or h.hexdigest() != item["sha256"]:
        raise ValueError("Checkpoint content mismatch: " + item["path"])


def restore(
    manifest: dict, bundle: Path, destination: Path, apply: bool = False
) -> dict:
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema")
    items = manifest["files"]
    if len({item["path"] for item in items}) != len(items):
        raise ValueError("Duplicate destination in manifest")
    # Check all existing destinations before writing anything.
    missing = []
    for item in items:
        target = safe_path(destination, item["path"])
        safe_path(bundle, item["storage"]["asset"])
        if target.exists():
            verify(target, item)
        else:
            missing.append(item)
    if apply:
        for item in missing:
            target = safe_path(destination, item["path"])
            source = safe_path(bundle, item["storage"]["asset"])
            if not source.is_file():
                raise FileNotFoundError(
                    f"Download {item['storage']['release']} asset {source.name}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".yacs-restore-", dir=target.parent
            ) as temp:
                staged = Path(temp) / "payload"
                member = item["storage"].get("member")
                if member:
                    with (
                        zipfile.ZipFile(source) as archive,
                        archive.open(member) as stream,
                        staged.open("wb") as output,
                    ):
                        shutil.copyfileobj(stream, output, 4 * 1024 * 1024)
                else:
                    shutil.copyfile(source, staged)
                verify(staged, item)
                # Same-volume atomic publication; fails if an owner file appeared.
                # Removing the temporary link afterwards leaves the final bytes intact.
                target.hardlink_to(staged)
                verify(target, item)
    return {
        "status": "PASS" if apply or not missing else "MISSING",
        "existing_verified": len(items) - len(missing),
        "restored": len(missing) if apply else 0,
        "missing": []
        if apply
        else [{"path": i["path"], "storage": i["storage"]} for i in missing],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = restore(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        args.bundle,
        args.destination,
        args.apply,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
