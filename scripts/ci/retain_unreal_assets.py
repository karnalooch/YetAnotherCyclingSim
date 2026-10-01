"""Move materialized Unreal assets to a persistent archive without deleting bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def retain(workspace: Path, archive: Path) -> dict:
    workspace = workspace.resolve()
    archive = archive.resolve()
    if archive == workspace or archive.is_relative_to(workspace):
        raise ValueError("Asset archive must be outside the mutable worktree")
    if archive.exists():
        raise FileExistsError("Retention destination already exists; never overwrite")
    archive.mkdir(parents=True)
    manifest = {"schema_version": 1, "workspace": str(workspace), "assets": []}
    content = workspace / "Content"
    if content.is_symlink():
        raise ValueError("Content cannot be a symbolic link")
    for source in sorted(content.rglob("*")) if content.exists() else []:
        if source.suffix.lower() not in {".umap", ".uasset"}:
            continue
        if source.is_symlink() or not source.resolve().is_relative_to(workspace):
            raise ValueError(f"Asset escapes workspace: {source}")
        if not source.is_file():
            continue
        with source.open("rb") as stream:
            if stream.read(48).startswith(
                b"version https://git-lfs.github.com/spec/v1\n"
            ):
                continue
        relative = source.relative_to(workspace)
        sha = digest(source)
        size = source.stat().st_size
        destination = archive / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Same-volume rename preserves the original bytes. Cross-volume moves
        # fail closed instead of copying and subsequently deleting a source.
        source.rename(destination)
        if destination.stat().st_size != size or digest(destination) != sha:
            raise RuntimeError(f"Retained asset verification failed: {destination}")
        manifest["assets"].append(
            {"path": relative.as_posix(), "sha256": sha, "size_bytes": size}
        )
        # Persist every successful move even if a later asset fails.
        (archive / "retention.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    (archive / "retention.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    result = retain(args.workspace, args.archive)
    print(f"ASSET RETENTION PASS: {len(result['assets'])} asset(s); {args.archive}")


if __name__ == "__main__":
    main()
