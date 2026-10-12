"""Preview or relocate reviewed stale probe runs into verified same-volume retention.

No active-worker exception. CLI roots are pinned; tests inject separate temporary roots.
Atomic same-volume rename preserves file bytes, empty directories and NTFS metadata.
Shared Git worktrees, protected branches, hardlinks and reparse points are blocked.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

ROOT = Path("D:/yacs/runner/_work")
ARCHIVES = Path("D:/yacs/work/runner-retention")
REPO = Path("YetAnotherCyclingSim/YetAnotherCyclingSim")
RUN = re.compile(r"[0-9]+-[1-9][0-9]*")
REPO_RUN = re.compile(
    r"(?:_official-mcp-source-probe-|_road-material-native-|_road-material-source-proof-|rm-)[0-9]+-[1-9][0-9]*"
)

STATIC_CHECKOUTS = {
    "_blender-mf-reference",
    "_material-forge-ue-canary",
    "_official-mcp-native-probe",
    "_official-mcp-source-probe",
    "_phase2c-pcgex-cliff",
    "_sa-calobra-tpp-docs",
    "_sa-calobra-tpp-retention",
    "_bootstrap-cleanup",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in [path, *path.parents]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(
            not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0) & 0x400,
            f"Reparse/symlink refused: {part}",
        )
    return path


def eligible(relative):
    p = Path(relative)
    if p.is_absolute() or ".." in p.parts:
        return False
    if len(p.parts) == 2 and p.parts[0] in {"s384", "b384"}:
        name = p.parts[1]
        if p.parts[0] == "b384" and name.endswith("-session-project"):
            name = name.removesuffix("-session-project")
        return bool(RUN.fullmatch(name))
    return (p.parent == REPO and bool(REPO_RUN.fullmatch(p.name))) or (
        p.name in STATIC_CHECKOUTS and p.parent in (Path("."), REPO)
    )


def confined(root, relative):
    require(eligible(relative), "Unknown/protected candidate name")
    root = no_links(root)
    candidate = no_links(root / relative)
    require(
        candidate != root and candidate.is_relative_to(root),
        "Candidate escapes runner root",
    )
    return candidate


def standalone_git(base):
    metadata = no_links(base / ".git")
    require(metadata.is_dir(), f"Shared Git file/worktree is protected: {metadata}")
    require(
        not (metadata / "commondir").exists()
        and not (metadata / "objects/info/alternates").exists(),
        f"Shared Git common/alternate objects are protected: {metadata}",
    )
    registry = metadata / "worktrees"
    if registry.exists():
        no_links(registry)
        require(
            registry.is_dir() and not any(registry.iterdir()),
            f"Git common owner with registered worktrees is protected: {registry}",
        )
    for key in ("core.worktree", "extensions.worktreeConfig"):
        result = subprocess.run(
            [
                "git",
                "--no-optional-locks",
                "-C",
                str(base),
                "config",
                "--local",
                "--get",
                key,
            ],
            capture_output=True,
            text=True,
        )
        require(
            result.returncode == 1 and not result.stdout.strip(),
            f"External Git worktree configuration is protected: {metadata}",
        )
    return metadata


def inventory_row(path, base, name):
    item = no_links(base / name)
    if name == ".git":
        metadata = standalone_git(base)
        head = metadata / "HEAD"
        no_links(head)
        value = head.read_text(encoding="utf-8").strip()
        if value.startswith("ref: "):
            branch = value.removeprefix("ref: refs/heads/")
            require(
                value.startswith("ref: refs/heads/"),
                f"Unknown Git HEAD: {metadata}",
            )
            # Nested standalone plugin repositories move intact; their main
            # branch is not the owning YACS project's protected main.
            if base == path:
                require(
                    not re.match(r"(?i)^(main|master|release(?:/|$)|v[0-9])", branch),
                    f"Main/release branch is protected: {metadata}",
                )
        else:
            require(
                re.fullmatch(r"[0-9a-f]{40}", value),
                f"Unknown Git HEAD is protected: {metadata}",
            )
    info = item.lstat()
    require(
        stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
        "Special filesystem object refused",
    )
    row = {
        "path": item.relative_to(path).as_posix(),
        "directory": stat.S_ISDIR(info.st_mode),
        "mtime_ns": info.st_mtime_ns,
        "mode": stat.S_IMODE(info.st_mode),
    }
    if not row["directory"]:
        require(info.st_nlink == 1, "Hardlinked evidence is protected")
        row.update(bytes=info.st_size, sha256=sha(item))
        after_hash = item.stat()
        require(
            after_hash.st_mtime_ns == info.st_mtime_ns
            and after_hash.st_size == info.st_size,
            "File changed while hashing",
        )
    return row


def inventory(path, workers=4):
    require(
        type(workers) is int and 1 <= workers <= 4, "Inventory worker count must be1..4"
    )
    path = no_links(path)
    require(path.is_dir(), "Candidate directory missing")
    records = []
    # One bounded pool per inventory; directory/reparse checks remain sequential.
    # Batches cap pending work while retaining every per-file ancestor/stat guard.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for directory, dirs, files in os.walk(path, followlinks=False):
            base = no_links(directory)
            for name in sorted(dirs):
                records.append(inventory_row(path, base, name))
            names = sorted(files)
            for start in range(0, len(names), 256):
                batch = names[start : start + 256]
                records.extend(
                    executor.map(lambda name: inventory_row(path, base, name), batch)
                )
    return sorted(records, key=lambda row: row["path"])


def host_idle():
    host = Path(__file__).with_name("Get-YacsUnrealHostState.ps1")
    result = subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(host), "-AsJson"],
        capture_output=True,
        text=True,
        check=True,
    )
    require(json.loads(result.stdout)["status"] == "IDLE", "Unreal host is active")
    # Unknown process-query failures fail closed; no process is terminated.
    code = "$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(Runner\\.(?:Worker|Listener)|UnrealEditor(?:-Cmd)?|UE4Editor(?:-Cmd)?|Blender|UnrealBuildTool|ShaderCompileWorker)\\.exe$' }); ConvertTo-Json -InputObject @($p | Select-Object Name,ProcessId) -Compress"
    processes = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        check=True,
    )
    require(json.loads(processes.stdout) == [], "Runner/UE/DCC/native worker is active")


def git_read(repo, *arguments):
    require(
        not any(
            os.environ.get(k)
            for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_CONFIG_COUNT")
        ),
        "Git environment redirection is protected",
    )
    command = ["git", "--no-optional-locks", "-C", str(repo), *arguments]
    result = subprocess.run(command, capture_output=True, text=True)
    require(
        result.returncode == 0,
        "Protected Git identity unavailable: " + result.stderr.strip(),
    )
    return result.stdout.strip()


def git_commit(repo, ref):
    value = git_read(repo, "rev-parse", "--verify", ref + "^{commit}")
    require(re.fullmatch(r"[0-9a-f]{40}", value), "Invalid protected Git commit")
    return value


def protected_commits(root):
    canonical = no_links(root / REPO)
    require(
        canonical.is_dir(),
        "Canonical repository unavailable for main/release identity guard",
    )
    commits = {git_commit(canonical, "refs/tags/v0.3.1")}
    refs = git_read(canonical, "for-each-ref", "--format=%(refname)").splitlines()
    for ref in refs:
        if re.match(
            r"^refs/(?:heads|remotes/[^/]+)/(?:main|master|release(?:/|$)|v[0-9])", ref
        ) or re.match(r"^refs/tags/v[0-9]", ref):
            commits.add(git_commit(canonical, ref))
    return commits


def protected(root, relative):
    target = confined(root, relative)
    metadata = target / ".git"
    if metadata.is_dir():
        standalone_git(target)
        # Standalone clone only: shared common dirs and external worktrees cannot move.
        require(
            not (metadata / "commondir").exists(),
            "Shared Git common directory is protected",
        )
        for key in ("core.worktree", "extensions.worktreeConfig"):
            result = subprocess.run(
                [
                    "git",
                    "--no-optional-locks",
                    "-C",
                    str(target),
                    "config",
                    "--get",
                    key,
                ],
                capture_output=True,
                text=True,
            )
            require(
                result.returncode == 1 and not result.stdout.strip(),
                "External/worktree Git configuration is protected",
            )
        protected_ids = protected_commits(root)
        head = git_commit(target, "HEAD")
        require(
            head not in protected_ids,
            "Detached/main/release commit identity is protected",
        )
        refs = git_read(target, "for-each-ref", "--format=%(refname)").splitlines()
        for ref in refs:
            if re.match(
                r"^refs/(?:heads|remotes/[^/]+)/(?:main|master|release(?:/|$)|v[0-9])",
                ref,
            ) or re.match(r"^refs/tags/v[0-9]", ref):
                require(
                    head != git_commit(target, ref),
                    "Candidate main/release ref identity is protected",
                )
    current = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if current and attempt:
        require(
            f"{current}-{attempt}" not in Path(relative).name,
            "Current run is protected",
        )
    pointer = root / REPO / "_yacs-unreal-ci/active.json"
    if pointer.exists():
        no_links(pointer)
        value = json.loads(pointer.read_text(encoding="utf-8-sig"))
        require(
            value.get("schema_version") == 1
            and isinstance(value.get("worktree"), str)
            and re.fullmatch(
                r"_unreal-(?:ci-warm|build-[0-9]+-[1-9][0-9]*)", value["worktree"]
            ),
            "Invalid active cache pointer",
        )
        active = no_links(root / REPO / value["worktree"])
        no_links(active / ".git")
        require(
            active.is_dir() and (active / ".git").exists(),
            "Active cache pointer target is missing",
        )
        require(
            value["worktree"] not in Path(relative).parts, "Active cache is protected"
        )


def preview(root=ROOT, minimum_age_hours=24, now=None, progress=False):
    require(minimum_age_hours >= 0, "Nonnegative reviewed stale age required")
    root = no_links(root)
    now = time.time() if now is None else now
    results, blocked, preserved = [], [], []
    for parent in (root, root / "s384", root / "b384", root / REPO):
        if not parent.exists():
            continue
        no_links(parent)
        for item in sorted(parent.iterdir()):
            rel = item.relative_to(root).as_posix()
            if not eligible(rel):
                preserved.append(
                    {
                        "relative": rel,
                        "reason": "Protected infrastructure, canonical/current cache or unknown path; outside explicit allowlist",
                    }
                )
                continue
            if progress:
                print("Inspect candidate: " + rel, file=sys.stderr, flush=True)
            try:
                candidate = confined(root, rel)
                protected(root, rel)
                if candidate.name in STATIC_CHECKOUTS:
                    require(
                        (candidate / ".git").is_dir(),
                        "Static candidate requires standalone root Git checkout",
                    )
                rows = inventory(candidate)
                newest = (
                    max(
                        [candidate.stat().st_mtime_ns]
                        + [row["mtime_ns"] for row in rows]
                    )
                    / 1e9
                )
                require(newest <= now - minimum_age_hours * 3600, "Run is not stale")
                results.append(
                    {
                        "relative": rel,
                        "inventory": rows,
                        "root_mtime_ns": candidate.stat().st_mtime_ns,
                        "bytes": sum(row.get("bytes", 0) for row in rows),
                    }
                )
            except (ValueError, OSError) as error:
                blocked.append({"relative": rel, "reason": str(error)})
    return {
        "schema_version": 1,
        "status": "PREVIEW_ONLY",
        "root": str(root),
        "minimum_age_hours": minimum_age_hours,
        "created_unix": now,
        "candidates": results,
        "blocked": blocked,
        "preserved": preserved,
    }


def quarantine(
    plan, retention_root=ARCHIVES, idle=host_idle, root=ROOT, progress=False
):
    """Same-volume relocation preserves bytes; no space-reclaim claim or deletion."""
    root = no_links(root)
    retention_root = no_links(retention_root)
    require(
        retention_root.is_dir() and not retention_root.is_relative_to(root),
        "Existing retention outside workspace required",
    )
    require(
        root.anchor.lower() == retention_root.anchor.lower(),
        "Same-volume retention required",
    )
    require(
        plan["schema_version"] == 1
        and plan["status"] == "PREVIEW_ONLY"
        and Path(plan["root"]) == root,
        "Reviewed plan root/schema differs",
    )
    require(plan["minimum_age_hours"] >= 0, "Invalid reviewed stale age")
    require(
        len({c["relative"] for c in plan["candidates"]}) == len(plan["candidates"]),
        "Duplicate candidate",
    )
    receipts = []
    for entry in plan["candidates"]:
        relative = entry["relative"]
        if progress:
            print("Retain candidate: " + relative, file=sys.stderr, flush=True)
        target = confined(root, relative)
        protected(root, relative)
        if target.name in STATIC_CHECKOUTS:
            require(
                (target / ".git").is_dir(),
                "Static candidate requires standalone root Git checkout",
            )
        rows = inventory(target)
        require(
            rows == entry["inventory"]
            and target.stat().st_mtime_ns == entry["root_mtime_ns"],
            "Reviewed candidate changed",
        )
        newest = max([entry["root_mtime_ns"]] + [r["mtime_ns"] for r in rows]) / 1e9
        require(
            newest <= time.time() - plan["minimum_age_hours"] * 3600,
            "Candidate no longer stale",
        )
        token = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        destination = no_links(
            retention_root / (Path(relative).name + "-" + token[:16])
        )
        require(not destination.exists(), "Retention destination already exists")
        receipt_path = no_links(retention_root / (token + ".json"))
        require(not receipt_path.exists(), "Retention receipt already exists")
        receipt = {
            "status": "QUARANTINE_PREPARED",
            "source": str(target),
            "destination": str(destination),
            "inventory": rows,
            "bytes": entry["bytes"],
            "bytes_deleted": 0,
            "disk_space_reclaimed": 0,
        }
        idle()
        with receipt_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        idle()
        protected(root, relative)
        require(
            inventory(confined(root, relative)) == rows,
            "Candidate changed before relocation",
        )
        require(
            not no_links(destination).exists(), "Destination appeared before relocation"
        )
        idle()
        target.rename(destination)
        require(
            inventory(destination) == rows,
            "Quarantine verification failed; retained data must be investigated, never deleted",
        )
        receipt["status"] = "QUARANTINED_VERIFIED_NO_BYTES_DELETED"
        verified_path = no_links(receipt_path.with_suffix(".verified.json"))
        idle()
        with verified_path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(receipt, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        receipts.append(receipt)
        if progress:
            print("Verified retained: " + relative, file=sys.stderr, flush=True)
    return receipts


def queue_owned_run(archive_root=ARCHIVES):
    run = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    require(
        RUN.fullmatch(run + "-" + attempt), "Exact numeric GitHub run/attempt required"
    )
    archive_root = no_links(archive_root)
    require(archive_root.is_dir(), "Archive root must exist")
    request = {
        "schema_version": 1,
        "status": "OWNED_RUN_CLEANUP_REQUEST_ONLY",
        "run_id": run,
        "attempt": attempt,
        "queued_unix": time.time(),
        "relative_candidates": [
            "s384/" + run + "-" + attempt,
            "b384/" + run + "-" + attempt,
            "b384/" + run + "-" + attempt + "-session-project",
            *[
                (REPO / (prefix + run + "-" + attempt)).as_posix()
                for prefix in (
                    "_official-mcp-source-probe-",
                    "_road-material-native-",
                    "_road-material-source-proof-",
                    "rm-",
                )
            ],
        ],
        "deletion_performed": False,
        "requires_idle_supervisor": True,
    }
    destination = no_links(
        archive_root / ("owned-run-" + run + "-" + attempt + ".json")
    )
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(request, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum-age-hours", type=int, default=24)
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--queue-owned-run", action="store_true")
    parser.add_argument("--plan-output", type=Path)
    parser.add_argument(
        "--apply-plan", "--apply-reviewplan", dest="apply_plan", type=Path
    )
    parser.add_argument("--expected-plan-sha256")
    args = parser.parse_args()
    if args.queue_owned_run:
        require(
            not args.apply_plan
            and not args.plan_output
            and not args.expected_plan_sha256,
            "Queue mode cannot apply cleanup",
        )
        print(json.dumps(queue_owned_run(), indent=2))
    elif args.apply_plan:
        require(
            args.expected_plan_sha256
            and sha(args.apply_plan) == args.expected_plan_sha256,
            "Exact reviewed plan SHA required",
        )
        raw = args.apply_plan.read_bytes()
        plan = json.loads(raw)
        print(json.dumps(quarantine(plan, progress=args.progress), indent=2))
    else:
        require(
            not args.expected_plan_sha256, "Plan SHA only applies with --apply-plan"
        )
        result = preview(
            minimum_age_hours=args.minimum_age_hours, progress=args.progress
        )
        if args.plan_output:
            no_links(args.plan_output)
            require(
                not args.plan_output.resolve().is_relative_to(ROOT.resolve()),
                "Plan must be outside runner workspace",
            )
            with args.plan_output.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
