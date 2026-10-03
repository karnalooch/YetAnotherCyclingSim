"""Julka's read-only-first asset inventory and verified acquisition commands."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .models import JulkaError, load_json, topological_assets, validate_catalog

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "catalog.json"
DEFAULT_ROOT = Path(os.environ.get("YACS_ASSET_ROOT", Path.home() / "YACS-Assets"))
AUDIT_EXTENSIONS = {
    ".uasset",
    ".umap",
    ".tif",
    ".tiff",
    ".laz",
    ".las",
    ".gpkg",
    ".shp",
    ".shx",
    ".dbf",
    ".prj",
    ".qmd",
    ".fbx",
    ".obj",
    ".wav",
    ".mp3",
    ".ogg",
    ".zip",
    ".pbf",
}
SENSITIVE_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".ssh",
    ".aws",
    ".azure",
    ".docker",
    ".kube",
    ".config",
    "credentials",
    "secrets",
    "tokens",
    "node_modules",
}


def run(
    command: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def load_catalog_file(path: Path = CATALOG_PATH) -> dict[str, Any]:
    catalog = load_json(path)
    validate_catalog(catalog)
    return catalog


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextlib.contextmanager
def operation_lock(state_root: Path):
    """Serialize mutating Julka operations across processes on Windows and POSIX."""
    state_root = state_root.absolute()
    if state_root.is_symlink() or (
        hasattr(state_root, "is_junction") and state_root.is_junction()
    ):
        raise JulkaError(f"Julka state directory is a link/junction: {state_root}")
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / "operation.lock"
    with lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise JulkaError(
                    f"another Julka operation is using this asset root: {state_root}"
                ) from exc
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise JulkaError(
                    f"another Julka operation is using this asset root: {state_root}"
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def assert_no_reparse_components(path: Path, boundary: Path) -> None:
    boundary = boundary.absolute()
    path = path.absolute()
    try:
        relative = path.relative_to(boundary)
    except ValueError as exc:
        raise JulkaError(f"managed path escapes its configured root: {path}") from exc
    components = [
        boundary,
        *(
            boundary.joinpath(*relative.parts[:index])
            for index in range(1, len(relative.parts) + 1)
        ),
    ]
    for component in components:
        if component.is_symlink() or (
            hasattr(component, "is_junction") and component.is_junction()
        ):
            raise JulkaError(
                f"managed path traverses a symbolic link/junction: {component}"
            )


def asset_path(root: Path, asset: dict[str, Any]) -> Path:
    root = root.absolute()
    path = (root / "sources").joinpath(*asset["path"].split("/"))
    assert_no_reparse_components(path, root)
    return path


def receipt_path(root: Path, catalog: dict[str, Any]) -> Path:
    root = root.absolute()
    path = root / "sources" / Path(catalog["receipt"]["path"])
    assert_no_reparse_components(path, root)
    return path


def lfs_records(
    catalog: dict[str, Any], profile_name: str, repo: Path
) -> list[dict[str, Any]]:
    profiles = catalog["profiles"]
    if profile_name not in profiles:
        raise JulkaError(f"unknown profile {profile_name!r}")
    profile_chain: list[str] = []

    def add_profile(name: str) -> None:
        if name in profile_chain:
            raise JulkaError(f"profile inheritance cycle includes {name!r}")
        profile_chain.append(name)
        for parent in profiles[name].get("extends", []):
            add_profile(parent)

    add_profile(profile_name)
    exact = {
        path
        for name in profile_chain
        for path in profiles[name].get("git_lfs_paths", [])
    }
    extensions = {
        ext.lower()
        for name in profile_chain
        for ext in profiles[name].get("git_lfs_extensions", [])
    }
    if not exact and not extensions:
        return []
    result = run(["git", "lfs", "ls-files", "--json", "--long", "HEAD"], cwd=repo)
    if result.returncode:
        raise JulkaError(
            f"cannot inspect Git LFS profile {profile_name}: {result.stderr.strip()}"
        )
    entries = json.loads(result.stdout).get("files", [])
    selected = [
        entry
        for entry in entries
        if entry.get("name") in exact
        or Path(entry.get("name", "")).suffix.lower() in extensions
    ]
    missing_paths = exact - {entry.get("name") for entry in selected}
    if missing_paths:
        raise JulkaError(
            "profile Git LFS paths are absent from this commit: "
            + ", ".join(sorted(missing_paths))
        )
    return sorted(selected, key=lambda item: item["name"])


def is_lfs_materialized(
    path: Path, record: dict[str, Any], *, verify: bool = False
) -> tuple[bool, str]:
    if not path.is_file():
        return False, "MISSING"
    with path.open("rb") as stream:
        pointer = stream.read(128).startswith(
            b"version https://git-lfs.github.com/spec/v1"
        )
    if pointer:
        return False, "POINTER-ONLY"
    if path.stat().st_size != int(record["size"]):
        return False, "SIZE-MISMATCH"
    if verify and (
        record.get("oid_type") != "sha256" or hash_file(path) != record.get("oid")
    ):
        return False, "SHA256-MISMATCH"
    return True, "SHA256-VERIFIED" if verify else "MATERIALIZED (hash not checked)"


def cmd_profiles(_: argparse.Namespace) -> int:
    catalog = load_catalog_file()
    print("Profiles (closure includes inherited/dependent assets):")
    for name, profile in sorted(catalog["profiles"].items()):
        assets = topological_assets(catalog, name)
        size = sum(item["size_bytes"] for item in assets)
        manual = sum(asset["backend"]["type"] == "manual-cnig" for asset in assets)
        suffix = f"  {manual} manual source tile(s)" if manual else ""
        if profile.get("incomplete_layers"):
            suffix += "  INCOMPLETE LAYERS: " + ", ".join(profile["incomplete_layers"])
        if profile.get("manual_only"):
            suffix += "  inventory only; no automatic hydrate"
        print(
            f"  {name:28} {len(assets):2} files  {size:,} B  {profile['description']}{suffix}"
        )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks: list[tuple[str, list[str] | None, str | None]] = [
        ("Python 3.12+", [sys.executable, "--version"], None),
        ("Git", ["git", "--version"], None),
        ("Git LFS", ["git", "lfs", "version"], None),
        ("uv", ["uv", "--version"], None),
        ("GitHub CLI", ["gh", "--version"], None),
        ("DVC", ["dvc", "--version"], None),
        (
            "Unreal project",
            None,
            str(args.project) if args.project else "not requested",
        ),
    ]
    failures = 0
    for label, command, note in checks:
        if label == "Python 3.12+":
            version = sys.version_info
            okay = version >= (3, 12)
            detail = sys.version.split()[0]
        elif label == "Unreal project":
            okay = bool(args.project and Path(args.project).is_file())
            detail = note or "not requested"
        else:
            result = run(command or [])
            okay = result.returncode == 0
            detail = (
                (result.stdout or result.stderr).strip().splitlines()[0]
                if okay
                else "not installed / unavailable"
            )
        required = label not in {"DVC", "Unreal project"}
        failures += not okay and required
        print(
            f"{'PASS' if okay else 'FAIL' if required else 'INFO':4} {label}: {detail}"
        )
    auth = run(["gh", "auth", "status"])
    print(
        f"{'PASS' if auth.returncode == 0 else 'FAIL'} GitHub Release access: {'authenticated' if auth.returncode == 0 else 'run gh auth login'}"
    )
    failures += auth.returncode != 0
    print(f"INFO asset root: {args.root}")
    print(
        "INFO doctor is read-only; it never installs tools or changes Unreal settings."
    )
    return 1 if failures else 0


def cmd_status(args: argparse.Namespace) -> int:
    catalog = load_catalog_file()
    root = Path(args.root)
    assets = topological_assets(catalog, args.profile)
    missing = 0
    failures = 0
    for asset in assets:
        path = asset_path(root, asset)
        if not path.is_file():
            state = (
                "MANUAL REQUIRED"
                if asset["backend"]["type"] == "manual-cnig"
                else "MISSING"
            )
            missing += 1
        else:
            size = path.stat().st_size
            if size != asset["size_bytes"]:
                state = f"SIZE-MISMATCH ({size:,} B)"
                failures += 1
            elif args.verify and hash_file(path) != asset["sha256"]:
                state = "SHA256-MISMATCH"
                failures += 1
            elif args.verify:
                with path.open("rb") as stream:
                    signature = stream.read(4).hex()
                expected_signature = asset.get("signature_hex")
                if expected_signature and signature != expected_signature:
                    state = "SIGNATURE-MISMATCH"
                    failures += 1
                else:
                    state = (
                        "PRESENT+SHA256"
                        if expected_signature
                        else "PRESENT+SHA256 (signature unpinned)"
                    )
            else:
                state = (
                    "PRESENT+SHA256" if args.verify else "PRESENT (hash not checked)"
                )
        print(f"{state:28} {asset['path']}")
    lfs = lfs_records(catalog, args.profile, Path(args.repo).resolve())
    for record in lfs:
        path = Path(args.repo).resolve() / record["name"]
        assert_no_reparse_components(path, Path(args.repo).resolve())
        okay, state = is_lfs_materialized(path, record, verify=args.verify)
        print(f"{state:28} {record['size']:>12,} B  Git LFS: {record['name']}")
        if not okay:
            missing += 1
            failures += state == "SHA256-MISMATCH" or state == "SIZE-MISMATCH"
    profile = catalog["profiles"][args.profile]
    if any(asset["backend"]["type"] == "github-release" for asset in assets):
        receipt = receipt_path(root, catalog)
        if (
            receipt.is_file()
            and receipt.stat().st_size == catalog["receipt"]["size_bytes"]
        ):
            receipt_state = "PRESENT (hash not checked)"
        elif receipt.exists():
            receipt_state = "SIZE-MISMATCH"
            failures += 1
        else:
            receipt_state = "MISSING"
            missing += 1
        print(f"{receipt_state:28} provider receipt: {receipt.relative_to(root)}")
    if profile.get("incomplete_layers"):
        print("INCOMPLETE LAYERS: " + "; ".join(profile["incomplete_layers"]))
    if profile.get("manual_only"):
        print("ARCHIVE STATUS: inventory only; no automatic hydration")
    if any(asset["backend"]["type"] == "github-release" for asset in assets):
        print(
            "REMOTE STATUS: UNKNOWN (status is local-only; hydrate checks authorized Release metadata before transfer)."
        )
    print(
        f"Summary: {len(assets) - sum(not asset_path(root, asset).is_file() for asset in assets)}/{len(assets)} catalog assets present; LFS objects={len(lfs)}; root={root}"
    )
    if args.verify:
        return 1 if missing or failures else 0
    return 1 if missing or failures else 0


def cmd_inventory(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    result = run(["git", "lfs", "ls-files", "--json", "--long", "HEAD"], cwd=repo)
    if result.returncode:
        raise JulkaError(f"cannot read Git LFS inventory: {result.stderr.strip()}")
    try:
        entries = json.loads(result.stdout).get("files", [])
    except json.JSONDecodeError as exc:
        raise JulkaError(f"Git LFS returned invalid JSON: {exc}") from exc
    if not isinstance(entries, list):
        raise JulkaError("Git LFS inventory has no files[]")
    total = 0
    missing = 0
    pointer_only = 0
    for entry in sorted(entries, key=lambda item: item.get("name", "")):
        relative = entry.get("name")
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise JulkaError(f"unsafe path from Git LFS: {relative!r}")
        path = repo / relative
        assert_no_reparse_components(path, repo)
        size = int(entry.get("size", 0))
        total += size
        if not path.is_file():
            state = "MISSING"
            missing += 1
        else:
            with path.open("rb") as stream:
                pointer = stream.read(128).startswith(
                    b"version https://git-lfs.github.com/spec/v1"
                )
            if pointer:
                state = "POINTER-ONLY"
                pointer_only += 1
                missing += bool(args.verify)
            elif path.stat().st_size != size:
                state = f"SIZE-MISMATCH ({path.stat().st_size:,} B)"
                missing += 1
            elif args.verify:
                okay = entry.get("oid_type") == "sha256" and hash_file(
                    path
                ) == entry.get("oid")
                state = "SHA256-VERIFIED" if okay else "SHA256-MISMATCH"
                missing += not okay
            else:
                state = "MATERIALIZED (hash not checked)"
        print(f"{state:27} {size:>12,} B  {relative}")
    print(
        f"Git LFS: {len(entries)} objects, {total:,} B; pointer-only={pointer_only}, missing/invalid={missing}"
    )
    print(
        "Git LFS inventory is derived from the selected commit; it does not include ignored local inputs or prove remote restore availability."
    )
    return 1 if missing else 0


def cmd_hydrate_lfs(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    selected = lfs_records(load_catalog_file(), args.profile, repo)
    total = sum(int(entry.get("size", 0)) for entry in selected)
    for entry in selected:
        assert_no_reparse_components(repo / entry["name"], repo)
    need = sum(
        int(entry.get("size", 0))
        for entry in selected
        if not is_lfs_materialized(repo / entry["name"], entry)[0]
    )
    volume_probe = repo
    while not volume_probe.exists() and volume_probe != volume_probe.parent:
        volume_probe = volume_probe.parent
    free = shutil.disk_usage(volume_probe).free
    required = 0 if need == 0 else need * 2 + max(256 * 1024 * 1024, need // 20)
    print(
        f"Git LFS files in approved asset classes: {len(selected)}; missing/materialization needed: {need:,} B of {total:,} B"
    )
    print(
        f"Conservative cache+checkout space target: {required:,} B; available: {free:,} B"
    )
    if not args.apply:
        print(
            f"Plan only for profile {args.profile}. Add --apply to retrieve these exact tracked files."
        )
        return 0
    if free < required:
        raise JulkaError(
            "insufficient conservative free-space budget for Git LFS hydration"
        )
    include = ",".join(entry["name"] for entry in selected)
    if not include:
        print("No matching Git LFS files.")
        return 0
    result = run(["git", "lfs", "pull", f"--include={include}", "--exclude="], cwd=repo)
    if result.returncode:
        raise JulkaError(
            f"git lfs pull failed ({result.returncode}): {result.stderr.strip()}"
        )
    failures = []
    for entry in selected:
        path = repo / entry["name"]
        if (
            not path.is_file()
            or path.stat().st_size != int(entry["size"])
            or hash_file(path) != entry["oid"]
        ):
            failures.append(entry["name"])
    if failures:
        raise JulkaError(
            "LFS hydration returned but SHA/size verification failed: "
            + ", ".join(failures[:10])
        )
    print(f"SHA-256 verified all {len(selected)} selected Git LFS files.")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    catalog = load_catalog_file()
    root = Path(args.root)
    assets = topological_assets(catalog, args.profile)
    need = 0
    manual_missing = 0
    for asset in assets:
        path = asset_path(root, asset)
        already = path.is_file() and path.stat().st_size == asset["size_bytes"]
        if not already and asset["backend"]["type"] == "github-release":
            need += asset["size_bytes"]
        if not already and asset["backend"]["type"] == "manual-cnig":
            manual_missing += 1
        state = (
            "CHECK"
            if already
            else "FETCH"
            if asset["backend"]["type"] == "github-release"
            else "MANUAL"
        )
        print(f"{state:7} {asset['size_bytes']:>12,} B  {asset['path']}")
    if any(asset["backend"]["type"] == "github-release" for asset in assets):
        receipt = receipt_path(root, catalog)
        receipt_present = (
            receipt.is_file()
            and receipt.stat().st_size == catalog["receipt"]["size_bytes"]
        )
        if not receipt_present:
            need += catalog["receipt"]["size_bytes"]
        print(
            f"{'KEEP' if receipt_present else 'FETCH':7} {catalog['receipt']['size_bytes']:>12,} B  provider receipt: {receipt.relative_to(root)}"
        )
    repo = Path(args.repo).resolve()
    lfs = lfs_records(catalog, args.profile, repo)
    lfs_need = 0
    for record in lfs:
        path = repo / record["name"]
        assert_no_reparse_components(path, repo)
        materialized, state = is_lfs_materialized(path, record)
        if not materialized:
            lfs_need += int(record["size"])
        print(f"LFS {state:17} {record['size']:>12,} B  {record['name']}")
    volume_probe = root
    while not volume_probe.exists() and volume_probe != volume_probe.parent:
        volume_probe = volume_probe.parent
    free = shutil.disk_usage(volume_probe).free
    # A staging directory is atomically renamed after verification, so bytes do not double.
    required = 0 if need == 0 else need + max(256 * 1024 * 1024, need // 20)
    print(
        f"Transfer needed: {need:,} B; safe-space target incl. 5%/256 MiB margin: {required:,} B"
    )
    print(
        f"Free on destination volume: {free:,} B; {'ENOUGH' if free >= required else 'INSUFFICIENT'}"
    )
    print(f"Git LFS bytes to hydrate on repository volume: {lfs_need:,} B")
    if manual_missing:
        print(
            f"MANUAL ACQUISITION REQUIRED: {manual_missing} raw MDT source tiles are not present under the configured asset root."
        )
    profile = catalog["profiles"][args.profile]
    if profile.get("incomplete_layers"):
        print(
            "Profile also lacks separately reviewed/acquired layers: "
            + "; ".join(profile["incomplete_layers"])
        )
    print(
        "Remote metadata is not a backup proof; restoration is verified only after local SHA-256 checks."
    )
    return (
        3
        if manual_missing or profile.get("manual_only")
        else 0
        if free >= required
        else 2
    )


def cmd_verify(args: argparse.Namespace) -> int:
    catalog = load_catalog_file()
    root = Path(args.root)
    failures = 0
    for asset in topological_assets(catalog, args.profile):
        path = asset_path(root, asset)
        if not path.is_file():
            print(f"MISSING {asset['path']}")
            failures += 1
            continue
        size = path.stat().st_size
        digest = hash_file(path)
        expected_signature = asset.get("signature_hex")
        signature_ok = (
            not expected_signature
            or path.open("rb").read(4).hex() == expected_signature
        )
        okay = (
            size == asset["size_bytes"] and digest == asset["sha256"] and signature_ok
        )
        print(
            f"{'PASS' if okay else 'FAIL'} {asset['path']} ({size:,} B, SHA-256 {digest})"
        )
        if not signature_ok:
            print(f"  signature mismatch (expected {asset.get('signature_hex')})")
        failures += not okay
    for record in lfs_records(catalog, args.profile, Path(args.repo).resolve()):
        path = Path(args.repo).resolve() / record["name"]
        assert_no_reparse_components(path, Path(args.repo).resolve())
        okay, state = is_lfs_materialized(path, record, verify=True)
        print(f"{state} Git LFS {record['name']}")
        failures += not okay
    profile = catalog["profiles"][args.profile]
    if any(
        asset["backend"]["type"] == "github-release"
        for asset in topological_assets(catalog, args.profile)
    ):
        receipt = receipt_path(root, catalog)
        receipt_ok = (
            receipt.is_file()
            and receipt.stat().st_size == catalog["receipt"]["size_bytes"]
            and hash_file(receipt) == catalog["receipt"]["sha256"]
        )
        print(
            f"{'PASS' if receipt_ok else 'FAIL'} provider receipt {receipt.relative_to(root)}"
        )
        failures += not receipt_ok
    if profile.get("incomplete_layers"):
        print("INCOMPLETE LAYERS: " + "; ".join(profile["incomplete_layers"]))
    print(f"Verification: {'PASS' if failures == 0 else 'FAIL'} ({failures} issue(s))")
    return 1 if failures else 0


def _cmd_hydrate(args: argparse.Namespace) -> int:
    catalog = load_catalog_file()
    assets = topological_assets(catalog, args.profile)
    if catalog["profiles"][args.profile].get("manual_only"):
        raise JulkaError(
            "archive is inventory-only and cannot be automatically hydrated"
        )
    manual = [asset for asset in assets if asset["backend"]["type"] == "manual-cnig"]
    for asset in manual:
        path = asset_path(Path(args.root), asset)
        if (
            not path.is_file()
            or path.stat().st_size != asset["size_bytes"]
            or hash_file(path) != asset["sha256"]
        ):
            raise JulkaError(
                f"raw MDT input {asset['provider_catalog_name']} is not locally verified; "
                "acquire from the official CNIG catalog, then run `adopt-mdt`"
            )
    release_assets = [
        asset for asset in assets if asset["backend"]["type"] == "github-release"
    ]
    if not release_assets:
        print("This profile has no Release-backed assets.")
        return 0
    if not args.apply:
        print(
            "Dry run only. Add --apply after reviewing `julka plan` to download and verify."
        )
        return cmd_plan(
            argparse.Namespace(profile=args.profile, root=args.root, repo=args.repo)
        )
    if (
        cmd_plan(
            argparse.Namespace(profile=args.profile, root=args.root, repo=args.repo)
        )
        != 0
    ):
        raise JulkaError("destination volume failed the free-space preflight")
    gh = run(["gh", "auth", "status"])
    if gh.returncode:
        raise JulkaError(
            "GitHub authentication unavailable; run `gh auth login` and retry"
        )

    root = Path(args.root).resolve()
    state_root = root / ".julka"
    state_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="staging-release-", dir=state_root))
    try:
        existing: set[str] = set()
        for asset in release_assets:
            target = asset_path(root, asset)
            if target.exists():
                if (
                    target.stat().st_size != asset["size_bytes"]
                    or hash_file(target) != asset["sha256"]
                ):
                    raise JulkaError(
                        f"refusing to overwrite an existing corrupt or unverified source: {target}"
                    )
                existing.add(asset["asset_id"])
        by_release: dict[str, list[dict[str, Any]]] = {}
        for asset in release_assets:
            by_release.setdefault(asset["acquisition"]["release_tag"], []).append(asset)
        for tag, group_assets in by_release.items():
            meta = run(
                [
                    "gh",
                    "release",
                    "view",
                    tag,
                    "--repo",
                    catalog["repository"],
                    "--json",
                    "isDraft,tagName,assets",
                ]
            )
            if meta.returncode:
                raise JulkaError(f"cannot inspect Release {tag}: {meta.stderr.strip()}")
            release = json.loads(meta.stdout)
            if not release.get("isDraft") or release.get("tagName") != tag:
                raise JulkaError(
                    f"Release {tag} is missing or is no longer the expected private draft"
                )
            remote = {item["name"]: item for item in release.get("assets", [])}
            receipt = catalog["receipt"]
            receipt_remote = remote.get(receipt["release_asset"])
            if (
                not receipt_remote
                or receipt_remote.get("size") != receipt["size_bytes"]
                or receipt_remote.get("digest") != f"sha256:{receipt['sha256']}"
            ):
                raise JulkaError(
                    "Release receipt is missing or differs from the pinned receipt identity"
                )
            receipt_target = receipt_path(root, catalog)
            if receipt_target.exists():
                if (
                    receipt_target.stat().st_size != receipt["size_bytes"]
                    or hash_file(receipt_target) != receipt["sha256"]
                ):
                    raise JulkaError(
                        f"refusing to overwrite an unverified source receipt: {receipt_target}"
                    )
                receipt_data = json.loads(receipt_target.read_text(encoding="utf-8"))
            else:
                receipt_download = run(
                    [
                        "gh",
                        "release",
                        "download",
                        tag,
                        "--repo",
                        catalog["repository"],
                        "--pattern",
                        receipt["release_asset"],
                        "--dir",
                        str(staging),
                    ]
                )
                if receipt_download.returncode:
                    raise JulkaError(
                        f"cannot download source receipt: {receipt_download.stderr.strip()}"
                    )
                downloaded_receipt_path = staging / receipt["release_asset"]
                if (
                    downloaded_receipt_path.stat().st_size != receipt["size_bytes"]
                    or hash_file(downloaded_receipt_path) != receipt["sha256"]
                ):
                    raise JulkaError(
                        "downloaded source receipt does not match its pinned SHA-256"
                    )
                receipt_data = json.loads(
                    downloaded_receipt_path.read_text(encoding="utf-8")
                )
            receipt_records = {
                row["delivered_name"]: row for row in receipt_data.get("files", [])
            }
            if len(receipt_records) != 17 or receipt_data.get("verification", {}).get(
                "total_size_bytes"
            ) != sum(item["size_bytes"] for item in group_assets):
                raise JulkaError(
                    "source receipt does not describe exactly the pinned 17-file package"
                )
            if len(group_assets) != 17:
                raise JulkaError(
                    f"Release {tag} is expected to provide exactly 17 pinned files; found {len(group_assets)}"
                )
            for asset in group_assets:
                acquisition = asset["acquisition"]
                row = receipt_records.get(acquisition["release_asset"])
                if (
                    not row
                    or row.get("size_bytes") != asset["size_bytes"]
                    or row.get("sha256") != asset["sha256"]
                    or row.get("catalog_name") != asset.get("provider_catalog_name")
                ):
                    raise JulkaError(f"receipt mapping differs for {asset['asset_id']}")
                remote_item = remote.get(acquisition["release_asset"])
                if not remote_item:
                    raise JulkaError(
                        f"Release is missing {acquisition['release_asset']}"
                    )
                if (
                    remote_item.get("size") != asset["size_bytes"]
                    or remote_item.get("digest") != f"sha256:{asset['sha256']}"
                ):
                    raise JulkaError(
                        f"remote metadata does not match the pinned receipt for {asset['asset_id']}"
                    )
                if asset["asset_id"] in existing:
                    continue
                result = run(
                    [
                        "gh",
                        "release",
                        "download",
                        tag,
                        "--repo",
                        catalog["repository"],
                        "--pattern",
                        acquisition["release_asset"],
                        "--dir",
                        str(staging),
                    ]
                )
                if result.returncode:
                    raise JulkaError(
                        f"download failed for {asset['asset_id']}: {result.stderr.strip()}"
                    )
                downloaded = staging / acquisition["release_asset"]
                if (
                    downloaded.stat().st_size != asset["size_bytes"]
                    or hash_file(downloaded) != asset["sha256"]
                ):
                    raise JulkaError(
                        f"download checksum mismatch for {asset['asset_id']}; staging retained at {staging}"
                    )
        for asset in release_assets:
            source = staging / asset["acquisition"]["release_asset"]
            if not source.exists():
                continue
            target = staging / asset["asset_id"]
            source.replace(target)
        # All downloads are verified before any managed destination is touched.
        receipt_target = receipt_path(root, catalog)
        if receipt_target.exists() and (
            receipt_target.stat().st_size != catalog["receipt"]["size_bytes"]
            or hash_file(receipt_target) != catalog["receipt"]["sha256"]
        ):
            raise JulkaError(
                f"refusing to overwrite an existing unverified source receipt: {receipt_target}"
            )
        for asset in release_assets:
            target = asset_path(root, asset)
            if target.exists():
                if (
                    target.stat().st_size != asset["size_bytes"]
                    or hash_file(target) != asset["sha256"]
                ):
                    raise JulkaError(
                        f"refusing to overwrite an existing corrupt or unverified source: {target}"
                    )
                continue
        for asset in release_assets:
            target = asset_path(root, asset)
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            (staging / asset["asset_id"]).replace(target)
        if not receipt_target.exists():
            receipt_target.parent.mkdir(parents=True, exist_ok=True)
            (staging / catalog["receipt"]["release_asset"]).replace(receipt_target)
        try:
            staging.rmdir()
        except OSError:
            pass
        print(
            f"Restored and SHA-256 verified {len(release_assets) - len(existing)} Release assets; total profile assets={len(assets)}"
        )
        print(
            "Source bytes are unchanged; the Release copy is a transport mirror, not a second provenance authority."
        )
        return 0
    except Exception:
        print(
            f"No unverified file was promoted; a verified promotion can be partial if interrupted. Rerun to resume; staging: {staging}",
            file=sys.stderr,
        )
        raise


def _cmd_adopt_mdt(args: argparse.Namespace) -> int:
    catalog = load_catalog_file()
    source_root = Path(args.source_dir).resolve(strict=True)
    root = Path(args.root).resolve()
    assets = [
        asset
        for asset in topological_assets(catalog, "sa-calobra-8x8")
        if asset["backend"]["type"] == "manual-cnig"
    ]
    if len(assets) != 17:
        raise JulkaError(
            f"expected exactly 17 manifest-pinned MDT inputs, found {len(assets)}"
        )
    missing: list[str] = []
    for asset in assets:
        source = source_root / asset["provider_catalog_name"]
        if (
            not source.is_file()
            or source.stat().st_size != asset["size_bytes"]
            or hash_file(source) != asset["sha256"]
        ):
            missing.append(asset["provider_catalog_name"])
    if missing:
        raise JulkaError(
            "source directory does not contain all 17 exact verified MDT tiles: "
            + ", ".join(missing)
        )
    pending: list[dict[str, Any]] = []
    for asset in assets:
        target = asset_path(root, asset)
        if target.exists():
            if (
                target.stat().st_size != asset["size_bytes"]
                or hash_file(target) != asset["sha256"]
            ):
                raise JulkaError(
                    f"refusing to overwrite existing unverified MDT source: {target}"
                )
        else:
            pending.append(asset)
    copied_bytes = sum(asset["size_bytes"] for asset in pending)
    volume_probe = root
    while not volume_probe.exists() and volume_probe != volume_probe.parent:
        volume_probe = volume_probe.parent
    required = (
        0
        if copied_bytes == 0
        else copied_bytes + max(256 * 1024 * 1024, copied_bytes // 20)
    )
    free = shutil.disk_usage(volume_probe).free
    print(
        f"Verified source set: 17 files / {copied_bytes:,} B; destination margin target: {required:,} B; free: {free:,} B"
    )
    if not args.apply:
        print(
            "Plan only; source files are read-only. Add --apply to copy the verified set into Julka's managed root."
        )
        return 0
    if free < required:
        raise JulkaError("insufficient conservative free-space budget for source copy")
    state = root / ".julka"
    state.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="staging-mdt-", dir=state))
    try:
        for asset in pending:
            source = source_root / asset["provider_catalog_name"]
            target = staging / asset["asset_id"]
            shutil.copy2(source, target)
            if (
                target.stat().st_size != asset["size_bytes"]
                or hash_file(target) != asset["sha256"]
            ):
                raise JulkaError(
                    f"staged copy failed verification: {asset['provider_catalog_name']}"
                )
        targets = [(asset, root / "sources" / asset["path"]) for asset in pending]
        for asset, target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            (staging / asset["asset_id"]).replace(target)
        try:
            staging.rmdir()
        except OSError:
            pass
        print(
            f"Copied and SHA-256 verified {len(pending)} missing MDT inputs; originals were not modified."
        )
        return 0
    except Exception:
        print(
            f"Originals were not modified. Inspect staging before any manual cleanup: {staging}",
            file=sys.stderr,
        )
        raise


def cmd_explain(args: argparse.Namespace) -> int:
    catalog = load_catalog_file()
    for asset in catalog["assets"]:
        if asset["asset_id"] != args.asset_id:
            continue
        asset_id = asset["asset_id"]
        if asset_id.startswith("mdt50-"):
            metadata_key = "mds_surface"
        elif asset_id.startswith("mdt-"):
            metadata_key = "mdt_source"
        elif asset_id.startswith("lidar-"):
            metadata_key = "pnoa_lidar"
        elif asset_id.startswith("ortho-"):
            metadata_key = "pnoa_ortho"
        else:
            metadata_key = None
        output = {
            "asset": asset,
            "gis_metadata": catalog["gis_metadata_profiles"].get(metadata_key)
            if metadata_key
            else None,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    raise JulkaError(f"unknown asset ID {args.asset_id!r}")


def cmd_audit_root(args: argparse.Namespace) -> int:
    requested = Path(args.root).absolute()
    components = list(reversed(requested.parents)) + [requested]
    for component in components:
        try:
            if component.is_symlink() or (
                hasattr(component, "is_junction") and component.is_junction()
            ):
                raise JulkaError(
                    f"audit root traverses a symbolic link/junction: {component}"
                )
        except OSError as exc:
            raise JulkaError(
                f"cannot inspect audit-root path component {component}: {exc}"
            ) from exc
    root = requested.resolve(strict=True)
    if not root.is_dir() or root == Path(root.anchor):
        raise JulkaError(
            "audit root must be an existing, explicitly chosen subdirectory; drive roots are rejected"
        )
    records: list[dict[str, Any]] = []
    unique: dict[tuple[int, int], int] = {}
    stack = [root]
    skipped_links = 0
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    name = entry.name
                    if name.lower() in SENSITIVE_DIRS:
                        continue
                    try:
                        if entry.is_symlink() or (
                            hasattr(entry, "is_junction") and entry.is_junction()
                        ):
                            skipped_links += 1
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                            continue
                        if (
                            not entry.is_file(follow_symlinks=False)
                            or Path(name).suffix.lower() not in AUDIT_EXTENSIONS
                        ):
                            continue
                        info = entry.stat(follow_symlinks=False)
                        identity = (int(info.st_dev), int(info.st_ino))
                        record: dict[str, Any] = {
                            "path": Path(entry.path).relative_to(root).as_posix(),
                            "size_bytes": int(info.st_size),
                            "mtime_ns": int(info.st_mtime_ns),
                            "state": "unexamined",
                            "sha256": None,
                            "unique_file_id": f"{info.st_dev}:{info.st_ino}",
                        }
                        if args.hash:
                            record["sha256"] = hash_file(Path(entry.path))
                            record["state"] = "hashed"
                        records.append(record)
                        unique.setdefault(identity, int(info.st_size))
                    except OSError as exc:
                        records.append(
                            {
                                "path": Path(entry.path).relative_to(root).as_posix(),
                                "state": "unexamined",
                                "error": str(exc),
                            }
                        )
        except OSError as exc:
            records.append(
                {
                    "path": current.relative_to(root).as_posix() or ".",
                    "state": "unexamined",
                    "error": str(exc),
                }
            )
    records.sort(key=lambda row: row["path"])
    logical = sum(int(row.get("size_bytes", 0)) for row in records)
    unique_logical = sum(unique.values())
    report = {
        "schema_version": 1,
        "root": str(root),
        "generated_at_utc": __import__("datetime")
        .datetime.now(__import__("datetime").timezone.utc)
        .isoformat(),
        "hashes_computed": bool(args.hash),
        "physical_disk_recovery_estimate": None,
        "asset_file_count": len(records),
        "logical_bytes": logical,
        "unique_file_id_logical_bytes": unique_logical,
        "skipped_reparse_points": skipped_links,
        "files": records,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output).resolve()
        if output == root or root in output.parents:
            raise JulkaError("audit report must be written outside the scanned root")
        if output.exists():
            raise JulkaError(f"refusing to overwrite existing audit report: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
        print(f"Audit report written locally: {output}")
    else:
        print(encoded, end="")
    print(
        f"Asset files: {len(records)}; logical={logical:,} B; unique file-ID logical={unique_logical:,} B; skipped links={skipped_links}"
    )
    print(
        "These are logical sizes, not physical allocation or safely recoverable space; scan errors remain unexamined."
    )
    return 0 if not any("error" in row for row in records) else 1


def cmd_cleanup(args: argparse.Namespace) -> int:
    root = Path(args.root).absolute()
    assert_no_reparse_components(root, Path(root.anchor))
    if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
        raise JulkaError(
            f"cleanup root is a link/junction and will not be traversed: {root}"
        )
    candidates = [
        root / "derived-cache",
        root / ".julka" / "dvc-workspace" / ".dvc" / "cache",
    ]
    state = root / ".julka"
    state_is_real_dir = (
        state.is_dir()
        and not state.is_symlink()
        and not (hasattr(state, "is_junction") and state.is_junction())
    )
    interrupted = sorted(state.glob("staging-*")) if state_is_real_dir else []
    total = 0
    errors: list[str] = []
    for candidate in candidates:
        if candidate.is_symlink() or (
            hasattr(candidate, "is_junction") and candidate.is_junction()
        ):
            print(f"SKIPPED LINK/JUNCTION (not scanned) {candidate}")
            continue
        if not candidate.exists():
            continue
        size = 0
        skipped = 0
        stack = [candidate]
        while stack:
            current = stack.pop()
            if current.is_symlink() or (
                hasattr(current, "is_junction") and current.is_junction()
            ):
                skipped += 1
                continue
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if entry.is_symlink() or (
                            hasattr(entry, "is_junction") and entry.is_junction()
                        ):
                            skipped += 1
                        elif entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            size += entry.stat(follow_symlinks=False).st_size
            except OSError as exc:
                errors.append(f"{current}: {exc}")
        total += size
        print(
            f"REGENERABLE CACHE (plan only) {candidate}: {size:,} B; skipped links={skipped}"
        )
    for staging in interrupted:
        print(f"INTERRUPTED STAGING (manual review; never auto-delete) {staging}")
    print(
        f"Potential cache bytes: {total:,}. This command is plan-only; no files were removed."
    )
    print(
        "Git LFS objects, source assets, prepared outputs, evidence and engine project data are never cleanup candidates."
    )
    if errors:
        print("INCOMPLETE CACHE SCAN: " + "; ".join(errors))
    return 1 if errors else 0


def dvc_workspace(root: Path) -> tuple[Path, Path]:
    state = root.resolve() / ".julka"
    return state / "dvc-workspace", state / "dvc-remote"


def _cmd_local_store(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    workspace, remote = dvc_workspace(root)
    state = root / ".julka"
    assert_no_reparse_components(workspace, state)
    assert_no_reparse_components(remote, state)
    if args.action == "init":
        if (workspace / ".dvc").exists():
            print(f"Already initialized: {workspace}")
            return 0
        if not args.apply:
            print(f"Would create local DVC workspace: {workspace}")
            print(f"Would create local DVC remote: {remote}")
            print(
                "This is a plan only. Add --apply to initialize; this is not a second-device backup."
            )
            return 0
    dvc = run(["dvc", "--version"])
    if dvc.returncode:
        raise JulkaError(
            "DVC optional tool is not installed; install with `uv sync --extra dvc`"
        )
    if args.action == "init":
        workspace.mkdir(parents=True, exist_ok=True)
        remote.mkdir(parents=True, exist_ok=True)
        initialized = run(["dvc", "init", "--no-scm"], cwd=workspace)
        if initialized.returncode:
            raise JulkaError(f"DVC init failed: {initialized.stderr.strip()}")
        configured = run(
            ["dvc", "remote", "add", "--default", "local", remote.as_uri()],
            cwd=workspace,
        )
        if configured.returncode:
            raise JulkaError(
                f"DVC local remote configuration failed: {configured.stderr.strip()}"
            )
        print(f"Local DVC workspace: {workspace}")
        print(f"Local DVC remote: {remote}")
        print("This is a local cache, not a second-device or cloud backup.")
        return 0
    if not args.path:
        raise JulkaError("local-store add requires --path")
    if not (workspace / ".dvc").exists():
        raise JulkaError("initialize first: julka local-store init")
    source = Path(args.path).resolve(strict=True)
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise JulkaError(
            "DVC only tracks inputs inside this configured Julka asset root"
        ) from exc
    if not args.apply:
        print(f"Would DVC-track this existing input without moving it: {source}")
        print(
            "This duplicates the bytes into DVC cache/remote and consumes additional disk space."
        )
        print("Add --apply to stage and push to the local DVC remote.")
        return 0
    if not args.asset_id.replace("-", "").replace("_", "").isalnum():
        raise JulkaError(
            "asset-id may contain only ASCII letters, digits, hyphens and underscores"
        )
    if source.is_dir():
        source_bytes = sum(
            item.stat().st_size
            for item in source.rglob("*")
            if item.is_file() and not item.is_symlink()
        )
    else:
        source_bytes = source.stat().st_size
    volume_probe = workspace
    while not volume_probe.exists() and volume_probe != volume_probe.parent:
        volume_probe = volume_probe.parent
    required = (
        0
        if source_bytes == 0
        else source_bytes * 3 + max(256 * 1024 * 1024, source_bytes // 20)
    )
    free = shutil.disk_usage(volume_probe).free
    print(
        f"DVC add may need up to {required:,} B additional free space (source + cache + local remote); available={free:,} B"
    )
    if free < required:
        raise JulkaError(
            "insufficient conservative free-space budget for local DVC duplication"
        )
    target = workspace / "tracked" / args.asset_id
    pointer = target.with_suffix(target.suffix + ".dvc")
    assert_no_reparse_components(target, workspace)
    assert_no_reparse_components(pointer, workspace)
    if target.exists() or pointer.exists():
        raise JulkaError(
            f"refusing to replace an existing DVC output or pointer: {target}"
        )
    pointer.parent.mkdir(parents=True, exist_ok=True)
    added = run(["dvc", "add", "--out", str(target), str(source)], cwd=workspace)
    if added.returncode:
        raise JulkaError(f"DVC add failed: {added.stderr.strip()}")
    pushed = run(["dvc", "push", "--remote", "local", str(pointer)], cwd=workspace)
    if pushed.returncode:
        raise JulkaError(f"DVC push to local remote failed: {pushed.stderr.strip()}")
    print(f"Tracked source without moving it. DVC pointer: {pointer}")
    print(f"Local remote copy: {remote}; no cross-device durability is implied.")
    return 0


def _with_root_lock(args: argparse.Namespace, operation: Any) -> int:
    requested_root = Path(args.root).absolute()
    assert_no_reparse_components(requested_root, Path(requested_root.anchor))
    if requested_root.is_symlink() or (
        hasattr(requested_root, "is_junction") and requested_root.is_junction()
    ):
        raise JulkaError(f"asset root is a link/junction: {requested_root}")
    with operation_lock(requested_root.resolve() / ".julka"):
        return operation(args)


def cmd_hydrate(args: argparse.Namespace) -> int:
    return _with_root_lock(args, _cmd_hydrate) if args.apply else _cmd_hydrate(args)


def cmd_adopt_mdt(args: argparse.Namespace) -> int:
    return _with_root_lock(args, _cmd_adopt_mdt) if args.apply else _cmd_adopt_mdt(args)


def cmd_local_store(args: argparse.Namespace) -> int:
    return (
        _with_root_lock(args, _cmd_local_store)
        if args.apply
        else _cmd_local_store(args)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="julka", description="YACS local-first asset manager"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("profiles", help="list curated install profiles").set_defaults(
        func=cmd_profiles
    )
    inventory = sub.add_parser(
        "inventory", help="inventory Git LFS-backed production assets"
    )
    inventory.add_argument("--repo", type=Path, default=REPO_ROOT)
    inventory.add_argument(
        "--verify", action="store_true", help="hash materialized payloads"
    )
    inventory.set_defaults(func=cmd_inventory)
    lfs = sub.add_parser(
        "hydrate-lfs", help="plan/restore tracked Unreal and raster files from Git LFS"
    )
    lfs.add_argument("--repo", type=Path, default=REPO_ROOT)
    lfs.add_argument("--profile", default="editor")
    lfs.add_argument("--apply", action="store_true")
    lfs.set_defaults(func=cmd_hydrate_lfs)
    doctor = sub.add_parser("doctor", help="read-only workstation capability audit")
    doctor.add_argument("--project", help="optional .uproject path to inspect")
    doctor.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    doctor.set_defaults(func=cmd_doctor)
    status = sub.add_parser("status", help="show local inventory without downloading")
    status.add_argument("--profile", default="sa-calobra-working")
    status.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    status.add_argument("--repo", type=Path, default=REPO_ROOT)
    status.add_argument(
        "--verify", action="store_true", help="hash every present file (can take time)"
    )
    status.set_defaults(func=cmd_status)
    plan = sub.add_parser("plan", help="estimate space and transfers without changes")
    plan.add_argument("--profile", default="sa-calobra-working")
    plan.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    plan.add_argument("--repo", type=Path, default=REPO_ROOT)
    plan.set_defaults(func=cmd_plan)
    verify = sub.add_parser("verify", help="full size and SHA-256 verification")
    verify.add_argument("--profile", default="sa-calobra-working")
    verify.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    verify.add_argument("--repo", type=Path, default=REPO_ROOT)
    verify.set_defaults(func=cmd_verify)
    hydrate = sub.add_parser(
        "hydrate", help="restore exact profile from configured free remote"
    )
    hydrate.add_argument("--profile", default="sa-calobra-working")
    hydrate.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    hydrate.add_argument("--repo", type=Path, default=REPO_ROOT)
    hydrate.add_argument(
        "--apply", action="store_true", help="perform verified download after preflight"
    )
    hydrate.set_defaults(func=cmd_hydrate)
    explain = sub.add_parser(
        "explain", help="show provenance and exact identity for one asset"
    )
    explain.add_argument("asset_id")
    explain.set_defaults(func=cmd_explain)
    audit = sub.add_parser(
        "audit-root", help="read-only, scoped inventory of selected asset directories"
    )
    audit.add_argument("--root", required=True, type=Path)
    audit.add_argument(
        "--hash",
        action="store_true",
        help="compute SHA-256; may take substantial time and I/O",
    )
    audit.add_argument(
        "--output",
        type=Path,
        help="optional local JSON report path outside the scanned root",
    )
    audit.set_defaults(func=cmd_audit_root)
    adopt = sub.add_parser(
        "adopt-mdt",
        help="verify and copy the 17 existing MDT sources without modifying originals",
    )
    adopt.add_argument("--source-dir", required=True, type=Path)
    adopt.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    adopt.add_argument(
        "--apply",
        action="store_true",
        help="copy verified files into managed local storage",
    )
    adopt.set_defaults(func=cmd_adopt_mdt)
    cleanup = sub.add_parser(
        "cleanup", help="show known disposable cache sizes (never deletes)"
    )
    cleanup.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    cleanup.set_defaults(func=cmd_cleanup)
    store = sub.add_parser(
        "local-store", help="opt-in DVC local cache for selected inputs"
    )
    store.add_argument("action", choices=["init", "add"])
    store.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    store.add_argument(
        "--path", help="existing file or directory under the configured asset root"
    )
    store.add_argument(
        "--asset-id",
        default="local-input",
        help="safe filename stem for the DVC pointer",
    )
    store.add_argument(
        "--apply", action="store_true", help="write the DVC pointer and local cache"
    )
    store.set_defaults(func=cmd_local_store)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (JulkaError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"julka: error: {exc}", file=sys.stderr)
        return 2
