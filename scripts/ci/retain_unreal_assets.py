"""Move materialized Unreal assets to a persistent archive without deleting bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def persistent_archive_path(archive: Path, actions_workspace: Path | None) -> Path:
    """Keep runner archives outside the entire Actions checkout/cleanup root."""
    archive = archive.resolve()
    if actions_workspace is None:
        return archive
    actions_workspace = actions_workspace.resolve()
    if archive.is_relative_to(actions_workspace):
        # Self-hosted layout: <runner>/_work/<repo>/<repo>. Future checkout
        # cleanup can remove siblings inside GITHUB_WORKSPACE, so use <runner>.
        archive = actions_workspace.parent.parent.parent / archive.relative_to(
            actions_workspace
        )
    if archive.is_relative_to(actions_workspace.parent.parent):
        raise ValueError("Persistent asset archive cannot live under Actions _work")
    return archive


def migrate_legacy_archives(actions_workspace: Path | None) -> None:
    """Preserve archives from earlier proof revisions before checkout cleanup."""
    if actions_workspace is None:
        return
    actions_workspace = actions_workspace.resolve()
    legacy = actions_workspace / "_yacs-retained-lfs"
    if not legacy.exists():
        return
    if legacy.is_symlink():
        raise ValueError("Legacy archive cannot be a symbolic link")
    durable = actions_workspace.parent.parent.parent / legacy.name
    durable.mkdir(parents=True, exist_ok=True)
    for source in sorted(legacy.iterdir()):
        if source.is_symlink():
            raise ValueError("Legacy archive entry cannot be a symbolic link")
        destination = durable / source.name
        if destination.exists():
            raise FileExistsError(
                "Legacy archive collision; never overwrite retained data"
            )
        source.rename(destination)


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
    sources = (
        {
            path
            for path in content.rglob("*")
            if path.suffix.lower() in {".umap", ".uasset"}
        }
        if content.exists()
        else set()
    )
    if (workspace / ".git").exists():
        tracked = subprocess.run(
            ["git", "lfs", "ls-files", "--name-only"],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
        )
        sources.update(workspace / name for name in tracked.stdout.splitlines() if name)
    for source in sorted(sources):
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
    actions_value = os.environ.get("GITHUB_WORKSPACE")
    archive = persistent_archive_path(
        args.archive, Path(actions_value) if actions_value else None
    )
    migrate_legacy_archives(Path(actions_value) if actions_value else None)
    result = retain(args.workspace, archive)
    print(f"ASSET RETENTION PASS: {len(result['assets'])} asset(s); {archive}")


if __name__ == "__main__":
    main()
