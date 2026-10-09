"""Retain completed TPP evidence under the configured persistent workspace.

This copies and verifies evidence already captured; it never starts Unreal,
rerenders, changes the source, grants visual acceptance, or claims remote backup.
Incomplete staging copies remain distinguishable from published retention.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.manage_local_workspace import load_workspace
from scripts.proof.package_sa_calobra_tpp_survey import digest, validate

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_FILES = 50_000
MAX_ENTRIES = 100_000
MAX_TOTAL_BYTES = 32 * 1024**3
MAX_FILE_BYTES = 4 * 1024**3
METADATA = ".yacs-retention"
SURVEY = Path("terrain-erosion-mesh/tpp-survey")


def no_link(path):
    metadata = path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or getattr(metadata, "st_file_attributes", 0) & 0x400
    ):
        raise ValueError(f"Evidence cannot contain a symlink or reparse point: {path}")
    return metadata


def inventory(root, *, exclude_metadata=False):
    """Bound all regular files and retain empty-directory topology as well."""
    root = Path(root)
    if not stat.S_ISDIR(no_link(root).st_mode):
        raise ValueError("Evidence source must be a regular directory")
    files, directories, names, total = [], [], set(), 0
    for directory, children, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        if current == root and METADATA in children:
            if not exclude_metadata:
                raise ValueError("Source uses reserved retention metadata directory")
            children.remove(METADATA)
        for name in children + filenames:
            path = current / name
            relative = path.relative_to(root).as_posix()
            parts = PurePosixPath(relative)
            if (
                "\\" in relative
                or ":" in relative
                or ".." in parts.parts
                or relative.casefold() in names
            ):
                raise ValueError(f"Unsafe or case-colliding evidence path: {relative}")
            names.add(relative.casefold())
            if len(names) > MAX_ENTRIES:
                raise ValueError("Evidence exceeds bounded retention entry count")
            metadata = no_link(path)
            if name in children:
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ValueError(f"Non-directory evidence entry: {relative}")
                directories.append(relative)
                continue
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(
                    f"Evidence must contain regular files only: {relative}"
                )
            total += metadata.st_size
            if (
                len(files) >= MAX_FILES
                or metadata.st_size > MAX_FILE_BYTES
                or total > MAX_TOTAL_BYTES
            ):
                raise ValueError("Evidence exceeds bounded retention inventory")
            files.append(
                {
                    "path": relative,
                    "size_bytes": metadata.st_size,
                    "sha256": digest(path),
                }
            )
    if not files:
        raise ValueError("Evidence inventory is empty")
    return {
        "files": sorted(files, key=lambda row: row["path"]),
        "directories": sorted(directories),
        "file_count": len(files),
        "size_bytes": total,
    }


def read_json(path, max_bytes=20_000_000):
    if not stat.S_ISREG(no_link(path).st_mode) or path.stat().st_size > max_bytes:
        raise ValueError(f"Invalid bounded JSON evidence file: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_source(source, expected_sha):
    survey_root = source / SURVEY
    report, _ = validate(survey_root, expected_sha)
    restoration = read_json(source / "checkout-restoration.json")
    if (
        restoration.get("status") != "PASS"
        or restoration.get("exact_sha") != expected_sha
        or restoration.get("tracked_changes") != []
    ):
        raise ValueError("Checkout restoration must pass at the captured exact SHA")
    review = survey_root / "review"
    verification = read_json(review / "package-verification.json")
    if (
        verification.get("technical_status") != "VALIDATED"
        or verification.get("exact_sha") != expected_sha
        or verification.get("survey_sha256") != digest(survey_root / "survey.json")
        or verification.get("visual_acceptance") != "PENDING_REVIEW"
        or verification.get("performance_acceptance") != "NOT_MEASURED"
    ):
        raise ValueError(
            "Survey review package was not validated for this captured evidence"
        )
    expected_frames = [
        {
            key: row[key]
            for key in (
                "frame_id",
                "file",
                "sha256",
                "size_bytes",
                "width_px",
                "height_px",
            )
        }
        for row in report["frames"]
    ]
    if verification.get("primary_frames") != expected_frames or verification.get(
        "frame_count"
    ) != len(expected_frames):
        raise ValueError("Review package primary frame inventory mismatch")
    listed = verification.get("derived_files")
    if not isinstance(listed, list) or not listed:
        raise ValueError("Review package has no derived-file verification inventory")
    expected_names = set()
    for item in listed:
        name = item["file"]
        relative = PurePosixPath(name)
        if (
            not name
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in name
            or ":" in name
            or name in expected_names
        ):
            raise ValueError("Unsafe or duplicate review package path")
        expected_names.add(name)
        path = review / name
        if path.stat().st_size != item["size_bytes"] or digest(path) != item["sha256"]:
            raise ValueError("Review package derived-file hash/size mismatch")
    actual_names = {row["path"] for row in inventory(review)["files"]}
    if actual_names != expected_names | {"package-verification.json"}:
        raise ValueError("Review package derived-file inventory mismatch")
    return report, digest(review / "package-verification.json")


def copy_file(source, destination):
    with source.open("rb") as original, destination.open("xb") as copied:
        shutil.copyfileobj(original, copied, 4 * 1024 * 1024)


def publish_no_replace(staging, destination):
    """Publish one same-volume directory atomically, rejecting any collision."""
    if os.name == "nt":
        # Windows os.rename rejects an existing destination directory.
        staging.rename(destination)
        return
    if sys.platform != "linux":
        raise RuntimeError(
            "Atomic directory publication is supported on Windows and Linux only"
        )
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise RuntimeError("Host lacks renameat2; refusing non-atomic publication")
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(staging), -100, os.fsencode(destination), 1):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def write_manifest(root, manifest):
    temporary = root / METADATA / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(root / METADATA / "manifest.json")


def retain(source, expected_sha, run_id, attempt, workspace_config):
    if not isinstance(expected_sha, str) or not SHA40.fullmatch(expected_sha):
        raise ValueError("Retention requires an exact lowercase SHA40")
    if (
        type(run_id) is not int
        or run_id <= 0
        or type(attempt) is not int
        or attempt <= 0
    ):
        raise ValueError("run_id and attempt must be positive integers")
    if workspace_config is None:
        raise ValueError("An explicit workspace configuration is required")
    config = load_workspace(Path(workspace_config))
    original = Path(source).absolute()
    for path in (original, *original.parents):
        no_link(path)
    source = original.resolve(strict=True)
    destination = (
        Path(config["work"])
        / "proofs/sa-calobra-tpp"
        / expected_sha
        / f"{run_id}-{attempt}"
    )
    if (
        destination == source
        or destination.is_relative_to(source)
        or source.is_relative_to(destination)
    ):
        raise ValueError("Retention source and destination must be disjoint")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Retention destination already exists; never overwrite")
    before = inventory(source)
    report, package_sha = validate_source(source, expected_sha)
    destination.parent.mkdir(parents=True, exist_ok=True)
    for path in (destination.parent, *destination.parent.parents):
        no_link(path)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{run_id}-{attempt}.staging-", dir=destination.parent)
    )
    metadata = staging / METADATA
    manifest = {
        "schema_version": 1,
        "status": "STAGING",
        "exact_sha": expected_sha,
        "run_id": run_id,
        "attempt": attempt,
        "source": str(source),
        "destination": str(destination),
        "workspace_config": config["config"],
        "remote_backup": "UNVERIFIED",
        "remote_transport_note": "GitHub Actions artifacts have 90-day retention; durable remote backup is unverified.",
        "visual_acceptance": "PENDING_REVIEW",
        "performance_acceptance": "NOT_MEASURED",
        "source_scene": report["source_scene"],
        "survey_frame_count": report["frame_count"],
        "package_verification_sha256": package_sha,
        "inventory": before,
        "source_preserved": False,
        "destination_verified": False,
    }
    metadata.mkdir()
    write_manifest(staging, manifest)
    published = False
    try:
        for directory in before["directories"]:
            (staging / directory).mkdir(parents=True, exist_ok=True)
        for item in before["files"]:
            target = staging / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            copy_file(source / item["path"], target)
            if (
                target.stat().st_size != item["size_bytes"]
                or digest(target) != item["sha256"]
            ):
                raise ValueError("Copied evidence hash/size mismatch")
        if inventory(source) != before:
            raise ValueError("Source evidence changed while retaining")
        if inventory(staging, exclude_metadata=True) != before:
            raise ValueError("Staged evidence inventory mismatch")
        manifest["status"] = "VERIFIED_STAGING"
        write_manifest(staging, manifest)
        publish_no_replace(staging, destination)
        published = True
        if inventory(destination, exclude_metadata=True) != before:
            raise ValueError("Published evidence inventory mismatch")
        if inventory(source) != before:
            raise ValueError("Source evidence changed during publication")
        manifest.update(
            status="LOCAL_RETAINED", source_preserved=True, destination_verified=True
        )
        write_manifest(destination, manifest)
    except Exception as error:
        manifest.update(status="RETENTION_FAILED", error=str(error))
        write_manifest(destination if published else staging, manifest)
        raise
    receipt = {
        key: manifest[key]
        for key in (
            "status",
            "exact_sha",
            "run_id",
            "attempt",
            "destination",
            "remote_backup",
            "remote_transport_note",
            "visual_acceptance",
            "performance_acceptance",
            "source_preserved",
            "destination_verified",
            "survey_frame_count",
            "package_verification_sha256",
        )
    }
    receipt.update(
        manifest=str(destination / METADATA / "manifest.json"),
        manifest_sha256=digest(destination / METADATA / "manifest.json"),
        files_verified=before["file_count"],
        bytes_verified=before["size_bytes"],
    )
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--attempt", type=int, required=True)
    parser.add_argument("--workspace-config", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            retain(
                args.source,
                args.expected_sha,
                args.run_id,
                args.attempt,
                args.workspace_config,
            )
        )
    )


if __name__ == "__main__":
    main()
