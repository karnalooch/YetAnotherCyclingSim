#!/usr/bin/env python3
"""Validate changed YACS assets without materializing Git LFS payloads."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path, PurePosixPath

from classify_changes import _is_asset, git_changed_paths

LFS_REQUIRED_EXTENSIONS = {
    ".uasset",
    ".umap",
    ".fbx",
    ".blend",
    ".wav",
    ".flac",
    ".mp3",
    ".exr",
    ".hdr",
    ".tga",
}

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1\n"


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def lfs_filter(path: str) -> str:
    output = git("check-attr", "filter", "--", path).strip()
    if ":" not in output:
        return ""
    return output.rsplit(":", maxsplit=1)[-1].strip()


def validate_asset_blob(
    *,
    path: str,
    filter_name: str,
    content: bytes,
) -> list[str]:
    suffix = PurePosixPath(path).suffix.lower()
    problems: list[str] = []

    if suffix in LFS_REQUIRED_EXTENSIONS and filter_name != "lfs":
        problems.append(f"{path}: required Git LFS extension is not using filter=lfs")
        return problems

    if filter_name == "lfs" and not content.startswith(LFS_POINTER_PREFIX):
        problems.append(
            f"{path}: Git LFS payload was materialized in lightweight asset validation"
        )

    return problems


def validate_changed_assets(base: str, head: str) -> tuple[list[str], list[str]]:
    changed = git_changed_paths(base, head)
    assets = [path for path in changed if _is_asset(path)]
    problems: list[str] = []

    for path in assets:
        file_path = Path(path)
        if not file_path.is_file():
            exists_at_head = subprocess.run(
                ["git", "cat-file", "-e", f"{head}:{path}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode == 0
            if not exists_at_head:
                print(f"  DELETE {path}")
                continue
            problems.append(f"{path}: changed asset exists at head but is missing from checkout")
            continue

        problems.extend(
            validate_asset_blob(
                path=path,
                filter_name=lfs_filter(path),
                content=file_path.read_bytes(),
            )
        )

    return assets, problems


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    assets, problems = validate_changed_assets(args.base, args.head)

    print(f"asset-validation: changed assets={len(assets)}")
    for path in assets:
        print(f"  ASSET {path}")

    if problems:
        print("asset-validation: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("asset-validation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
