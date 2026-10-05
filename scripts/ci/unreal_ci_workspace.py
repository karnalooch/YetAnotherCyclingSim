"""Keep verified isolated Unreal outputs in place across serialized CI jobs.

The pointer selects a candidate worktree, never authorizes binary/proof reuse.
Resolve-YacsUnrealCiCache.ps1 remains the provenance and environment authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from scripts.ci.retain_unreal_assets import digest, retain

WARM = "_unreal-ci-warm"
POINTER = "_yacs-unreal-ci/active.json"
STATE = "Saved/BuildCache/UnrealCi/state.json"
BINARY_NAMES = (
    "UnrealEditor-YetAnotherCyclingSim.dll",
    "UnrealEditor-YetAnotherCyclingSimEditor.dll",
)


def safe_path(workspace: Path, name: str) -> Path:
    if name != WARM and not re.fullmatch(r"_unreal-build-[0-9]+-[0-9]+", name):
        raise ValueError("Invalid Unreal cache worktree name")
    root = workspace / name
    if root.is_symlink() or root.resolve().parent != workspace.resolve():
        raise ValueError("Unreal cache worktree escapes workspace")
    # Windows junctions must not redirect any cache/provenance path either.
    for path in [root, *root.rglob("*")] if root.exists() else []:
        if path.is_symlink() or (
            path.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
            if hasattr(path.lstat(), "st_file_attributes")
            else False
        ):
            raise ValueError(f"Refuse cache through link/junction: {path}")
    return root


def read_state(root: Path) -> dict:
    value = json.loads((root / STATE).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Invalid Unreal state object")  # noqa: TRY004 - malformed artifact
    return value


def verified(root: Path) -> dict:
    state = read_state(root)
    if state.get("SchemaVersion") != 3 or any(
        state.get(field) is not True for field in ("CompilePassed", "ProofPassed")
    ):
        raise ValueError("Unreal state is not verified")
    for field in (
        "CompileFingerprint",
        "ProofFingerprint",
        "EnvironmentIdentity",
        "EngineIdentity",
        "ToolchainIdentity",
        "EngineRoot",
        "CompileHead",
        "ProofHead",
        "UpdatedUtc",
    ):
        if (
            not isinstance(state.get(field), str)
            or not state[field]
            or state[field] == "unresolved"
        ):
            raise ValueError(f"Missing Unreal provenance: {field}")
    if not (root / ".git").exists() or any(
        not (root / "Binaries/Win64" / name).is_file() for name in BINARY_NAMES
    ):
        raise ValueError("Verified Unreal worktree or binaries missing")
    return state


def pointer_path(workspace: Path) -> Path:
    folder = workspace / Path(POINTER).parent
    if folder.is_symlink() or getattr(folder, "is_junction", lambda: False)():
        raise ValueError("Unreal pointer directory is a link/junction")
    path = workspace / POINTER
    if path.is_symlink():
        raise ValueError("Unreal pointer is a symbolic link")
    return path


def write_pointer(workspace: Path, name: str) -> None:
    path = pointer_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    if temporary.is_symlink():
        raise ValueError("Unreal temporary pointer is a symbolic link")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump({"schema_version": 1, "worktree": name}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def select(workspace: Path) -> str:
    path = pointer_path(workspace)
    if path.exists():
        pointer = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(pointer, dict) or pointer.get("schema_version") != 1:
            raise ValueError("Invalid Unreal workspace pointer; preserve all worktrees")
        name = pointer.get("worktree")
        if not isinstance(name, str):
            raise ValueError("Missing Unreal worktree pointer")
        root = safe_path(workspace, name)
        if not (root / ".git").exists():
            raise ValueError(
                "Active Unreal worktree is missing; preserve all worktrees"
            )
        # Invalidated state is intentionally retained: the normal resolver will
        # require fresh work after an interrupted compile or Automation run.
        return name
    candidates = []
    for root in [workspace / WARM, *workspace.glob("_unreal-build-*")]:
        root = safe_path(workspace, root.name)
        try:
            state = verified(root)
        except (OSError, ValueError):
            continue
        candidates.append((state["UpdatedUtc"], root.name))
    if candidates:
        name = max(candidates)[1]
        write_pointer(workspace, name)
        return name
    return WARM


def publish(
    workspace: Path, name: str, head: str, compile_fp: str, proof_fp: str
) -> None:
    root = safe_path(workspace, name)
    state = verified(root)
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    if actual != head or state["ProofHead"] != head:
        raise ValueError("Unreal publication HEAD/proof provenance mismatch")
    if (
        state["CompileFingerprint"] != compile_fp
        or state["ProofFingerprint"] != proof_fp
    ):
        raise ValueError("Unreal publication fingerprints mismatch")
    summary = json.loads(
        (root / "Saved/RuntimeProof/CI/Unreal/unreal_ci_summary.json").read_text(
            encoding="utf-8-sig"
        )
    )
    if summary.get("Head") != head or summary.get("ExpectedHead") != head:
        raise ValueError("Unreal publication Automation summary HEAD mismatch")
    if summary["Failed"] != 0 or summary["Errors"] != 0 or summary["Discovered"] <= 0:
        raise ValueError("Unreal publication requires green Automation")
    write_pointer(workspace, name)


def standalone(root: Path) -> None:
    """Preserve outputs when actions/checkout expects a .git directory.

    The reviewed checkout implementation treats linked .git files as absent
    repositories and may delete their contents. Copy only Git metadata first;
    retain asset bytes, outputs and cache state at their existing paths.
    """
    if not (root / ".git").is_file():
        return
    origin = subprocess.check_output(
        ["git", "remote", "get-url", "origin"], cwd=root, text=True
    ).strip()
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    with tempfile.TemporaryDirectory(
        prefix="yacs-cache-git-", dir=root.parent
    ) as directory:
        clone = Path(directory) / "clone"
        environment = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")
        subprocess.run(
            ["git", "clone", "--no-hardlinks", "--no-checkout", str(root), str(clone)],
            check=True,
            capture_output=True,
            env=environment,
        )
        subprocess.run(
            ["git", "remote", "set-url", "origin", origin], cwd=clone, check=True
        )
        subprocess.run(
            ["git", "reset", "--mixed", head],
            cwd=clone,
            check=True,
            capture_output=True,
        )
        backup = root / ".git-linked-backup"
        if backup.exists():
            raise ValueError("Previous Git metadata migration incomplete")
        os.replace(root / ".git", backup)
        try:
            os.replace(clone / ".git", root / ".git")
        except BaseException:
            os.replace(backup, root / ".git")
            raise
        backup.unlink()


def prepare_checkout_directory(workspace: Path, name: str, run: str) -> None:
    """Keep actions/checkout away from destructive fallback on warm UE caches.

    actions/checkout removes every child when an existing target lacks a .git
    directory or its fetch URL differs from the requested repository. On a UE
    cache that can mean hundreds of thousands of Intermediate/Binaries files.

    Preserve an incomplete fallback with an atomic same-volume rename instead;
    normalize a valid repository's origin to the canonical Actions URL.
    """
    root = safe_path(workspace, name)
    if not root.exists():
        return

    git_dir = root / ".git"
    if not git_dir.is_dir():
        quarantine_root = workspace / "_yacs-unreal-ci" / "quarantine"
        if (
            quarantine_root.is_symlink()
            or getattr(quarantine_root, "is_junction", lambda: False)()
        ):
            raise ValueError("Unreal quarantine directory is a link/junction")
        quarantine_root.mkdir(parents=True, exist_ok=True)
        target = quarantine_root / f"{run}-{name}"
        if target.exists():
            raise ValueError(f"Unreal quarantine destination already exists: {target}")
        os.replace(root, target)
        print(
            f"UNREAL WORKSPACE: quarantined incomplete checkout {name} -> "
            f"{target.relative_to(workspace)}"
        )
        return

    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    if not repository:
        raise ValueError(
            "GITHUB_REPOSITORY is required to validate Unreal checkout origin"
        )
    expected_origin = f"{server}/{repository}"

    try:
        remotes = subprocess.check_output(
            ["git", "remote"],
            cwd=root,
            text=True,
            stderr=subprocess.STDOUT,
        ).splitlines()
    except subprocess.CalledProcessError as error:
        raise ValueError(
            "Existing Unreal checkout has unreadable Git metadata"
        ) from error

    if "origin" not in remotes:
        subprocess.run(
            ["git", "remote", "add", "origin", expected_origin],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"UNREAL WORKSPACE: added canonical origin for {name}: {expected_origin}")
        return

    actual_origin = subprocess.check_output(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()
    if actual_origin != expected_origin:
        subprocess.run(
            ["git", "remote", "set-url", "origin", expected_origin],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        print(
            f"UNREAL WORKSPACE: normalized origin for {name}: "
            f"{actual_origin!r} -> {expected_origin!r}"
        )


def retain_local_lfs_objects(root: Path, archive: Path) -> None:
    """Archive private LFS object bytes; never move a shared linked Git store."""
    if not (root / ".git").is_dir():
        return
    objects = root / ".git/lfs/objects"
    entries = []
    for source in sorted(objects.rglob("*")) if objects.exists() else []:
        if not source.is_file():
            continue
        relative = source.relative_to(objects)
        destination = archive / "git-lfs-objects" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        sha = digest(source)
        size = source.stat().st_size
        source.rename(destination)
        if destination.stat().st_size != size or digest(destination) != sha:
            raise RuntimeError("LFS object retention failed; preserve worktree")
        entries.append({"path": relative.as_posix(), "sha256": sha, "size_bytes": size})
        (archive / "git-lfs-objects.json").write_text(
            json.dumps(entries, indent=2) + "\n", encoding="utf-8"
        )


def cleanup(workspace: Path, active: str, run: str) -> None:
    # Re-read before deletion. Publication is serialized by workflow concurrency.
    if active != select(workspace):
        raise ValueError("Active cache changed before cleanup")
    for root in workspace.glob("_unreal-build-*"):
        root = safe_path(workspace, root.name)
        if root.name == active:
            continue
        if not (root / ".git").exists():
            raise ValueError("Refuse non-worktree cleanup")
        archive = workspace / "_yacs-retained-lfs" / f"cache-{run}-{root.name}"
        retain(root, archive)
        retain_local_lfs_objects(root, archive)
        shutil.rmtree(root)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("select", "publish"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--worktree")
    parser.add_argument("--head")
    parser.add_argument("--compile-fingerprint")
    parser.add_argument("--proof-fingerprint")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    if not re.fullmatch(r"[0-9]+-[0-9]+", args.run):
        raise ValueError("Invalid run/attempt")
    if args.action == "publish":
        publish(
            workspace,
            args.worktree,
            args.head,
            args.compile_fingerprint,
            args.proof_fingerprint,
        )
        print(f"UNREAL WORKSPACE: published={args.worktree}")
    else:
        active = select(workspace)
        root = safe_path(workspace, active)
        if (root / ".git").exists():
            # actions/checkout itself can replace tracked assets before the
            # later sanitization step; retain bytes before entering it.
            retain(
                root, workspace / "_yacs-retained-lfs" / f"checkout-{args.run}-{active}"
            )
        standalone(root)
        prepare_checkout_directory(workspace, active, args.run)
        cleanup(workspace, active, args.run)
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as stream:
            stream.write(f"YACS_UNREAL_WORKTREE={active}\n")
        print(f"UNREAL WORKSPACE: selected={active}; provenance validation pending")


if __name__ == "__main__":
    main()
