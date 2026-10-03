"""Inventory and retire only positively named obsolete Italy payloads on a runner.

Never prune a shared LFS object cache or change tracked Git history. The immutable
plan records byte hashes; apply rechecks every payload before deleting any file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT_NAMES = ("_embark-terrain-worktree", "_terrain-recovery-worktree")
PREFIXES = ("ExternalAssets/Terrain/PassoGiau/", "Content/Worlds/PassoGiau/")
EXACT = {
    "Content/Prototype/Maps/L_PassoGiauTerrainSpike.umap",
    "Content/WorldGen/PCGEx/PCG_PassoGiau_SP638_Corridor.uasset",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def approved(relative: Path) -> bool:
    parts = relative.parts
    if not parts or ".." in parts or relative.is_absolute():
        return False
    if parts[0] in ROOT_NAMES:
        suffix = Path(*parts[1:]).as_posix()
    elif parts[0] == "_yacs-retained-lfs":
        # Retention archives have variable run/attempt and before/after folders.
        indexes = [
            i for i, value in enumerate(parts) if value in {"Content", "ExternalAssets"}
        ]
        if len(indexes) != 1:
            return False
        suffix = Path(*parts[indexes[0] :]).as_posix()
    else:
        return False
    return suffix in EXACT or any(suffix.startswith(prefix) for prefix in PREFIXES)


def checked_path(workspace: Path, relative: Path) -> Path:
    if not approved(relative):
        raise ValueError(f"Unapproved retirement path: {relative}")
    current = workspace
    for part in relative.parts:
        current /= part
        if current.is_symlink() or (
            hasattr(os.path, "isjunction") and os.path.isjunction(current)
        ):
            raise ValueError(f"Linked retirement path: {current}")
    if not current.resolve().is_relative_to(workspace):
        raise ValueError("Retirement path escapes workspace")
    return current


def inventory(workspace: Path) -> dict:
    workspace = workspace.resolve(strict=True)
    entries = []
    for name in (*ROOT_NAMES, "_yacs-retained-lfs"):
        root = workspace / name
        if root.is_symlink() or (
            hasattr(os.path, "isjunction") and os.path.isjunction(root)
        ):
            raise ValueError(f"Linked retirement root: {root}")
        if not root.exists():
            continue
        # No following directory symlinks/junctions, even within named Italy trees.
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [
                d
                for d in dirs
                if d != ".git"
                and not (Path(directory) / d).is_symlink()
                and not (
                    hasattr(os.path, "isjunction")
                    and os.path.isjunction(Path(directory) / d)
                )
            ]
            for name in files:
                path = Path(directory) / name
                relative = path.relative_to(workspace)
                if not approved(relative):
                    continue
                path = checked_path(workspace, relative)
                with path.open("rb") as stream:
                    if stream.read(48).startswith(
                        b"version https://git-lfs.github.com/spec/v1\n"
                    ):
                        continue
                entries.append(
                    {
                        "path": relative.as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": digest(path),
                    }
                )
    return {
        "schema_version": 1,
        "workspace": str(workspace),
        "assets": sorted(entries, key=lambda x: x["path"]),
        "shared_lfs_cache": "UNTOUCHED",
        "tracked_history": "UNTOUCHED",
    }


def apply(plan: dict, workspace: Path, receipt: Path) -> dict:
    workspace = workspace.resolve(strict=True)
    if plan.get("schema_version") != 1 or plan.get("workspace") != str(workspace):
        raise ValueError("Retirement plan identity mismatch")
    if receipt.exists():
        raise FileExistsError("Retirement receipt already exists")
    entries = plan["assets"]
    if len({e["path"] for e in entries}) != len(entries):
        raise ValueError("Duplicate retirement path")
    paths = []
    for entry in entries:
        path = checked_path(workspace, Path(entry["path"]))
        if (
            not path.is_file()
            or path.stat().st_size != entry["size_bytes"]
            or digest(path) != entry["sha256"]
        ):
            raise ValueError(f"Payload changed since inventory: {entry['path']}")
        paths.append(path)
    result = {
        "schema_version": 1,
        "workspace": str(workspace),
        "deleted": [],
        "reclaimed_payload_bytes": 0,
        "shared_lfs_cache": "UNTOUCHED",
        "tracked_history": "UNTOUCHED",
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for path, entry in zip(paths, entries):
        path.unlink()
        result["deleted"].append(entry)
        result["reclaimed_payload_bytes"] += entry["size_bytes"]
        receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.apply:
        if not args.receipt:
            parser.error("--apply requires --receipt")
        result = apply(
            json.loads(args.plan.read_text(encoding="utf-8")),
            args.workspace,
            args.receipt,
        )
        print(
            f"ITALY RETIREMENT: deleted {len(result['deleted'])}, reclaimed {result['reclaimed_payload_bytes']} payload bytes"
        )
    else:
        if args.plan.exists():
            raise FileExistsError("Retirement plan already exists")
        result = inventory(args.workspace)
        args.plan.parent.mkdir(parents=True, exist_ok=True)
        args.plan.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"ITALY INVENTORY: {len(result['assets'])} eligible payloads")


if __name__ == "__main__":
    main()
