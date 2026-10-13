"""Bounded pre-job maintenance of the two persistent CI helper object stores.

No checkout, prune, gc, reflog expiry, asset cleanup or editor operation.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import time
import uuid

TARGETS = ("_bootstrap-cleanup", "_blender-mf-reference")
GIB = 1024**3
GIT_OPTIONS = ["-c", "core.packedGitLimit=128m", "-c", "core.packedGitWindowSize=16m"]


class MaintenanceBusy(ValueError):
    """Maintenance may wait without preventing an otherwise safe CI job."""


def command(args: list[str], *, timeout: int = 120) -> bytes:
    with subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=os.name != "nt",
    ) as process:
        try:
            output, error = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Stop only the process tree started here, including pack-objects.
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    check=True,
                    timeout=15,
                )
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise RuntimeError("Git maintenance command timed out") from None
        if process.returncode:
            raise RuntimeError(
                f"Command exit {process.returncode}: {error.decode(errors='replace')[-1500:]}"
            )
        return output


def git(root: Path, *args: str) -> bytes:
    return command(["git", *GIT_OPTIONS, "-C", str(root), *args])


def no_links(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink() or (
            part.exists()
            and getattr(part.lstat(), "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError(f"Linked path refused: {part}")
    return path


def workspace_paths(config_path: Path) -> tuple[Path, Path]:
    config_path = no_links(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    # This host contract intentionally does not discover arbitrary repositories.
    if config.get("schema_version") != 1 or config.get("runner") != "runner":
        raise ValueError("Expected schema 1 and canonical relative runner root")
    workspace = config_path.parent
    return workspace, no_links(workspace / "runner")


def assert_processes(
    processes: list[dict], current_pid: int, runner: Path, targets: list[Path]
) -> None:
    by_id = {int(p["ProcessId"]): p for p in processes}
    ancestors = set()
    cursor = current_pid
    while cursor:
        if cursor in ancestors or cursor not in by_id:
            raise ValueError("Unknown/cyclic job process ancestry")
        ancestors.add(cursor)
        if by_id[cursor]["Name"].lower() == "runner.worker.exe":
            break
        cursor = int(by_id[cursor]["ParentProcessId"])
    workers = [p for p in processes if p["Name"].lower() == "runner.worker.exe"]
    expected = os.path.normcase(str(runner / "bin" / "Runner.Worker.exe"))
    if (
        len(workers) != 1
        or int(workers[0]["ProcessId"]) not in ancestors
        or os.path.normcase(workers[0].get("ExecutablePath") or "") != expected
    ):
        raise ValueError("Exactly one canonical ancestor Worker required")
    if not targets:
        return
    for p in processes:
        name = p["Name"].lower()
        if name == "git.exe":
            raise MaintenanceBusy("Another Git process is active")
        if int(p["ProcessId"]) in ancestors:
            continue
        cmd = p.get("CommandLine")
        if (
            name
            in {
                "unrealeditor.exe",
                "unrealeditor-cmd.exe",
                "blender.exe",
                "shadercompileworker.exe",
            }
            and not cmd
        ):
            raise ValueError("Unreadable native process ownership")
        normalized = (cmd or "").replace("/", "\\").lower()
        if any(str(t).replace("/", "\\").lower() in normalized for t in targets):
            raise MaintenanceBusy("A maintenance target has an active process")


def process_guard(workspace: Path, runner: Path, targets: list[Path]) -> None:
    if os.name != "nt":
        raise ValueError("Automatic maintenance is Windows-only")
    pwsh = no_links(workspace / "tools/powershell-7.6.6-win-x64/pwsh.exe")
    raw = command(
        [
            str(pwsh),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "@(Get-CimInstance Win32_Process -ErrorAction Stop | Select-Object Name,ProcessId,ParentProcessId,ExecutablePath,CommandLine) | ConvertTo-Json -Compress",
        ],
        timeout=20,
    )
    assert_processes(json.loads(raw), os.getpid(), runner, targets)


def object_inventory(root: Path) -> bytes:
    return git(
        root,
        "cat-file",
        "--batch-all-objects",
        "--batch-check=%(objectname) %(objecttype) %(objectsize)",
    )


def metadata(root: Path) -> dict:
    def digest(relative: str) -> str:
        path = root / ".git" / relative
        return (
            hashlib.sha256(path.read_bytes()).hexdigest()
            if path.exists()
            else "MISSING"
        )

    return {
        "head": git(root, "rev-parse", "HEAD").decode().strip(),
        "refs": git(root, "for-each-ref", "--format=%(objectname) %(refname)").decode(),
        "reflogs": git(root, "reflog", "show", "--all", "--format=%H %gD %gs").decode(),
        "status_hex": git(
            root, "status", "--porcelain=v1", "--untracked-files=all"
        ).hex(),
        **{key: digest(key) for key in ("index", "config", "shallow")},
    }


def validate_target(root: Path) -> list[Path]:
    no_links(root)
    no_links(root / ".git")
    if not (root / ".git").is_dir():
        raise ValueError("Independent Git directory required")
    for relative in (
        "commondir",
        "worktrees",
        "objects/info/alternates",
        "objects/info/http-alternates",
    ):
        if (root / ".git" / relative).exists():
            raise ValueError("Shared Git storage refused")
    for directory, dirs, files in os.walk(root / ".git", followlinks=False):
        for name in dirs + files:
            path = no_links(Path(directory) / name)
            if name.endswith((".lock", ".keep", ".promisor")):
                raise ValueError("Locked, kept or partial Git store refused")
    if (
        Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        != root.resolve()
    ):
        raise ValueError("Unexpected Git top level")
    return sorted((root / ".git/objects/pack").glob("*.pack"))


def maintain_target(root: Path, guard, *, journal: Path, min_packs: int = 8) -> dict:
    journal = no_links(journal)
    pending = no_links(journal / "PENDING.json")
    if pending.exists():
        raise ValueError(
            f"Unverified previous mutation; manual recovery required: {pending}"
        )
    if not root.exists():
        return {"name": root.name, "status": "ABSENT"}
    packs = validate_target(root)
    size = sum(p.stat().st_size for p in packs)
    row = {"name": root.name, "packs_before": len(packs), "pack_bytes_before": size}
    if size > 4 * GIB:
        raise ValueError(
            "Pack backlog exceeds 4 GiB; reviewed manual recovery required"
        )
    if len(packs) < 2 or (len(packs) < min_packs and size < GIB):
        return {**row, "status": "BELOW_THRESHOLD"}
    try:
        guard()
    except MaintenanceBusy as exc:
        return {**row, "status": "DEFERRED_BUSY", "reason": str(exc)}
    before = object_inventory(root)
    raw_size = sum(int(line.split()[2]) for line in before.splitlines())
    if raw_size > 2 * GIB or shutil.disk_usage(root).free < 5 * GIB + raw_size:
        raise ValueError("Insufficient reserve or oversized unique object store")
    git(root, "fsck", "--full", "--no-dangling")
    state = metadata(root)
    try:
        guard()
    except MaintenanceBusy as exc:
        return {**row, "status": "DEFERRED_BUSY", "reason": str(exc)}
    journal.mkdir(parents=True, exist_ok=True)
    identity = uuid.uuid4().hex
    inventory_path = journal / f"{identity}.objects-before.txt"
    with inventory_path.open("xb") as handle:
        handle.write(before)
    # Persist the recovery evidence BEFORE invoking the only mutating command.
    # Any timeout, verification error or crash leaves this latch in place, even
    # if repack already reduced the store below the next job's threshold.
    with pending.open("x", encoding="utf-8") as handle:
        json.dump(
            {"inventory": str(inventory_path), "metadata": state}, handle, indent=2
        )
        handle.flush()
        os.fsync(handle.fileno())
    git(
        root,
        "-c",
        "pack.threads=1",
        "-c",
        "pack.windowMemory=16m",
        "repack",
        "-a",
        "-d",
        "--keep-unreachable",
        "--no-write-bitmap-index",
    )
    git(root, "fsck", "--full", "--no-dangling")
    after = object_inventory(root)
    if before != after or state != metadata(root):
        raise RuntimeError(
            "Post-repack conservation failed; further maintenance blocked"
        )
    final = validate_target(root)
    result = {
        **row,
        "status": "PASS",
        "head": state["head"],
        "objects": len(before.splitlines()),
        "inventory_sha256": hashlib.sha256(before).hexdigest(),
        "metadata_unchanged": True,
        "packs_after": len(final),
        "pack_bytes_after": sum(p.stat().st_size for p in final),
    }
    (journal / f"{identity}.verified.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    pending.unlink()
    return result


@contextlib.contextmanager
def exclusive_lock(path: Path):
    no_links(path)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    try:
        yield
    finally:
        path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-config", type=Path, required=True)
    args = parser.parse_args()
    workspace, runner = workspace_paths(args.workspace_config)
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_REPOSITORY") != "karnalooch/YetAnotherCyclingSim"
    ):
        raise ValueError("Canonical Actions job required")
    run, attempt = (
        os.environ.get(k, "") for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")
    )
    if not all(re.fullmatch(r"[1-9][0-9]*", value) for value in (run, attempt)):
        raise ValueError("Exact run and attempt required")
    targets = [
        no_links(runner / "_work/YetAnotherCyclingSim/YetAnotherCyclingSim" / name)
        for name in TARGETS
    ]
    output = no_links(workspace / "work/runner-git-maintenance")
    output.mkdir(parents=True, exist_ok=True)
    receipt = {
        "schema_version": 1,
        "run_id": run,
        "attempt": attempt,
        "started_unix": time.time(),
        "status": "RUNNING",
        "entries": [],
    }
    filename = output / f"{run}-{attempt}-{uuid.uuid4().hex}.json"

    def save():
        filename.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    try:
        with exclusive_lock(output / "maintenance.lock"):
            # Prove job ownership even on a no-op, but inspect competing Git and
            # native processes only when a target actually needs maintenance.
            process_guard(workspace, runner, [])
            save()
            for target in targets:
                guard = lambda: process_guard(workspace, runner, [target])
                receipt["entries"].append(
                    maintain_target(target, guard, journal=output / target.name)
                )
                save()
            receipt["status"] = "PASS"
    except Exception as exc:
        receipt.update(status="FAIL", error=str(exc))
        raise
    finally:
        save()
        print(f"Git pack maintenance {receipt['status']}: {filename}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
