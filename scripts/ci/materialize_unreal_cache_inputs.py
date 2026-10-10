"""Repair CRLF-only checkout drift in a serialized Unreal CI cache worktree.

Old Windows worktrees may retain CRLF for files after .gitattributes gains
eol=lf, despite git reset --hard returning success. Rewrite ONLY tracked
C#/critical PowerShell inputs from authenticated HEAD Git blobs. Never modify binaries,
cache state, assets, the source index, or the interactive authoring checkout.

The caller must already hold the normal Unreal CI host lock and supply the
exact HEAD and hosted compile/proof fingerprints. Any difference beyond EOL
fails closed before build or cache reuse.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

from scripts.ci.classify_changes import (
    UE_CRITICAL_CONFIG,
    UNREAL_COMPILE_TOOLING_EXACT,
    UNREAL_PROOF_EXACT,
    _is_unknown_runtime_compile_input,
    _is_unreal_compile_input,
    unreal_compile_fingerprint,
    unreal_proof_fingerprint,
)

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_TARGETS = 256
MAX_FILE_BYTES = 2 * 1024 * 1024


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        timeout=35,
    ).stdout


def critical_paths(root: Path) -> list[str]:
    names = [
        value.decode("utf-8")
        for value in git(root, "ls-files", "-z").split(b"\0")
        if value
    ]
    tracked = set(names)
    required = {
        path
        for path in UNREAL_COMPILE_TOOLING_EXACT | UNREAL_PROOF_EXACT
        if path.endswith(".ps1")
    }
    require(required.issubset(tracked), "Required Unreal proof scripts are not tracked")
    # Only C# build rules and explicitly named fingerprinted PowerShell scripts.
    paths = sorted(required | {p for p in names if p.endswith(".cs")})
    require(10 <= len(paths) <= MAX_TARGETS, "Unreal source list is outside bounds")
    return paths


def fingerprint_paths(root: Path) -> list[str]:
    """Enumerate exactly the existing tracked inputs of Unreal compile/proof.

    Unlike critical_paths(), this is READ-ONLY and also covers native sources,
    manifests, project and config files. A stale non-PS1/non-CS raw byte must
    invalidate the candidate cache before actions/checkout rewrites it.
    """
    names = {
        value.decode("utf-8")
        for value in git(root, "ls-files", "-z").split(b"\0")
        if value
    }
    required = UNREAL_COMPILE_TOOLING_EXACT | UNREAL_PROOF_EXACT
    required |= UE_CRITICAL_CONFIG | {"YetAnotherCyclingSim.uproject"}
    result = {name for name in required if (root / name).is_file()}
    for name in names:
        if not name.startswith(("Source/", "Plugins/", "Config/", "Build/")):
            continue
        if _is_unreal_compile_input(name) or _is_unknown_runtime_compile_input(name):
            result.add(name)
    require(result.issubset(names), "Fingerprint input not tracked by Git")
    require(1 <= len(result) <= 512, "Fingerprint input inventory is out of bounds")
    return sorted(result)


def raw_fingerprint_source_drift(root: Path) -> str | None:
    """Return first noncanonical fingerprint input; no mutations or trust grants.

    A tracked file can have different working-tree bytes from its raw Git blob
    even when git status reports clean under text-conversion filters.
    """
    for relative in fingerprint_paths(root):
        posix = PurePosixPath(relative)
        require(
            bool(posix.parts)
            and ".." not in posix.parts
            and not posix.is_absolute()
            and "\\" not in relative,
            "Invalid fingerprint input path",
        )
        path = root.joinpath(*posix.parts)
        require(
            path.is_file()
            and not path.is_symlink()
            and path.resolve().is_relative_to(root.resolve()),
            "Fingerprint input is missing or redirected",
        )
        current = path.read_bytes()
        require(len(current) <= MAX_FILE_BYTES, "Fingerprint input exceeds size bound")
        committed = git(root, "show", "HEAD:" + relative)
        require(len(committed) <= MAX_FILE_BYTES, "Git source exceeds size bound")
        if current != committed:
            return relative
    return None


def validate_target(root: Path, relative: str) -> tuple[Path, bytes]:
    posix = PurePosixPath(relative)
    require(
        bool(posix.parts)
        and ".." not in posix.parts
        and not posix.is_absolute()
        and "\\" not in relative
        and "\x00" not in relative,
        "Unsafe fingerprint source path",
    )
    path = root.joinpath(*posix.parts)
    cursor = root
    for index, part in enumerate(posix.parts):
        cursor = cursor / part
        info = cursor.lstat()
        require(
            not stat.S_ISLNK(info.st_mode)
            and not (
                getattr(info, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            ),
            "Fingerprint input or ancestor is a link/junction",
        )
        require(
            stat.S_ISREG(info.st_mode)
            if index == len(posix.parts) - 1
            else stat.S_ISDIR(info.st_mode),
            "Fingerprint input must have regular directory ancestry",
        )
    require(0 < info.st_size <= MAX_FILE_BYTES, "Fingerprint input size exceeds bound")
    attrs = git(root, "check-attr", "eol", "--", relative).decode("utf-8").strip()
    require(
        attrs == f"{relative}: eol: lf",
        "Missing pinned LF checkout attribute: " + relative,
    )
    committed = git(root, "show", "HEAD:" + relative)
    require(
        0 < len(committed) <= MAX_FILE_BYTES and b"\r" not in committed,
        "Committed fingerprint input must have canonical LF bytes",
    )
    return path, committed


def materialize(root: Path, paths: list[str]) -> dict:
    """Repair CRLF-only drift and verify every restored Git blob."""
    require(len(set(paths)) == len(paths), "Duplicate input path")
    require(0 < len(paths) <= MAX_TARGETS, "Invalid input count")
    # A CRLF-only file may itself appear dirty after the LF policy changed.
    # Reject staged/index changes, and allow only proven EOL drift in named files.
    require(
        not git(root, "diff", "--cached", "--name-only", "-z", "HEAD"),
        "Unreal cache index has staged source modifications",
    )
    dirty = {
        raw.decode("utf-8")
        for raw in git(root, "diff", "--name-only", "-z", "HEAD").split(b"\0")
        if raw
    }
    targets = []
    expected = {}
    observed = {}
    for name in paths:
        path, blob = validate_target(root, name)
        current = path.read_bytes()
        if current != blob:
            require(
                current.replace(b"\r\n", b"\n") == blob,
                "Fingerprint source has non-EOL changes: " + name,
            )
            targets.append(name)
            observed[name] = current
        expected[name] = blob
    require(
        dirty.issubset(set(targets)),
        "Unreal cache has unrelated tracked source modifications",
    )
    # Windows git checkout-index may reproduce the wrong worktree EOL after a
    # historical attributes change. Write the pre-authenticated HEAD blob bytes
    # atomically instead; neither the index nor the cache stamp is modified.
    for name in targets:
        path = root / name
        require(
            path.read_bytes() == observed[name],
            "Fingerprint input changed after preflight: " + name,
        )
        fd, temporary = tempfile.mkstemp(prefix=".yacs-unreal-eol-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(expected[name])
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    for name, blob in expected.items():
        require(
            (root / name).read_bytes() == blob,
            "Git checkout did not materialize canonical source: " + name,
        )
    require(
        not git(root, "status", "--porcelain", "--untracked-files=no"),
        "Canonical materialization altered tracked source",
    )
    return {
        "checked": len(expected),
        "restored": len(targets),
        "repaired_files": targets,
        "git_index_changed": False,
    }


def verify(root: Path, head: str, compile_fp: str, proof_fp: str) -> dict:
    require(bool(SHA40.fullmatch(head)), "Malformed expected source SHA")
    require(
        bool(SHA64.fullmatch(compile_fp)) and bool(SHA64.fullmatch(proof_fp)),
        "Malformed expected hosted fingerprints",
    )
    require(
        git(root, "rev-parse", "HEAD").decode("ascii").strip() == head,
        "Unreal cache checkout HEAD mismatch",
    )
    evidence = materialize(root, critical_paths(root))
    actual_compile = unreal_compile_fingerprint(root)
    actual_proof = unreal_proof_fingerprint(root)
    if actual_compile != compile_fp or actual_proof != proof_fp:
        drift = raw_fingerprint_source_drift(root)
        raise ValueError(
            "Physical Unreal cache fingerprints differ from hosted exact HEAD; "
            f"compile_matches={actual_compile == compile_fp}; "
            f"proof_matches={actual_proof == proof_fp}; "
            f"first_noncanonical_input={drift or 'none'}"
        )
    return {
        "status": "UNREAL_CANONICAL_CHECKOUT_VERIFIED",
        "exact_sha": head,
        "physical_compile_fingerprint": actual_compile,
        "physical_proof_fingerprint": actual_proof,
        **evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-compile-fingerprint", required=True)
    parser.add_argument("--expected-proof-fingerprint", required=True)
    options = parser.parse_args()
    report = verify(
        options.repo_root.resolve(),
        options.expected_head,
        options.expected_compile_fingerprint,
        options.expected_proof_fingerprint,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
