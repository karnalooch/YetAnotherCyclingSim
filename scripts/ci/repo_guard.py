"""Fail-closed repository hygiene checks for Unreal Engine source repositories."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAX_NON_LFS_BLOB_BYTES = 10 * 1024 * 1024

LFS_EXTENSIONS = {
    ".blend",
    ".exr",
    ".fbx",
    ".flac",
    ".hdr",
    ".mp3",
    ".tga",
    ".uasset",
    ".umap",
    ".wav",
}

GENERATED_COMPONENTS = {
    ".vs",
    "Binaries",
    "DerivedDataCache",
    "Intermediate",
    "Saved",
}


def git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout


def tracked_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    return [item.decode("utf-8") for item in output.split(b"\0") if item]


def lfs_filter(path: str) -> str:
    output = git("check-attr", "filter", "--", path).strip()
    return output.rsplit(":", maxsplit=1)[-1].strip() if ":" in output else ""


def blob_size(path: str) -> int:
    return int(git("cat-file", "-s", f"HEAD:{path}").strip())


def main() -> int:
    problems: list[str] = []

    for path in tracked_files():
        pure = Path(path)

        generated = GENERATED_COMPONENTS.intersection(pure.parts)
        if generated:
            problems.append(
                f"{path}: generated Unreal/IDE path is tracked ({sorted(generated)[0]})"
            )

        filter_name = lfs_filter(path)
        if pure.suffix.lower() in LFS_EXTENSIONS and filter_name != "lfs":
            problems.append(
                f"{path}: binary asset extension {pure.suffix.lower()} must use Git LFS"
            )

        size = blob_size(path)
        if size > MAX_NON_LFS_BLOB_BYTES and filter_name != "lfs":
            mib = size / (1024 * 1024)
            problems.append(
                f"{path}: Git blob is {mib:.1f} MiB; files over 10 MiB must use Git LFS"
            )

    if problems:
        print("repository policy: FAIL", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("repository policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
