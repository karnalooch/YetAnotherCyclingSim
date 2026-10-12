"""Archive verified old quarantines; prune only with an exact reviewed compression receipt.

Tar preserves regular-file bytes and directory entries, not NTFS ACLs or ADS.
Default invocation is a read-only preview. Never touches runner _work.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import time
import sys
import math
from concurrent.futures import ThreadPoolExecutor

RETENTION = Path("D:/yacs/work/runner-retention")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def no_links(path):
    path = Path(path).absolute()
    for item in [path, *path.parents]:
        if item.exists() or item.is_symlink():
            info = item.lstat()
            require(
                not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & 0x400),
                "Link/reparse refused",
            )
    return path.resolve()


def confined(path, root):
    root, path = no_links(root), no_links(path)
    require(path != root and path.is_relative_to(root), "Path escaped retention")
    return path


def member_path(value):
    require(
        type(value) is str and value and "\\" not in value and ":" not in value,
        "Unsafe archive path",
    )
    path = PurePosixPath(value)
    require(
        not path.is_absolute()
        and all(p not in (".", "..", "") for p in path.parts)
        and path.as_posix() == value,
        "Unsafe archive path",
    )
    return value


def canonical(rows):
    result, seen = [], set()
    require(type(rows) is list, "Invalid inventory")
    for row in rows:
        name = member_path(row["path"])
        require(
            name.casefold() not in seen and type(row["directory"]) is bool,
            "Duplicate inventory path/type",
        )
        seen.add(name.casefold())
        item = {"path": name, "directory": row["directory"]}
        if not row["directory"]:
            require(
                type(row["bytes"]) is int
                and row["bytes"] >= 0
                and type(row["sha256"]) is str
                and re.fullmatch("[0-9a-f]{64}", row["sha256"]),
                "Invalid file identity",
            )
            item.update(bytes=row["bytes"], sha256=row["sha256"])
        result.append(item)
    return sorted(result, key=lambda row: row["path"])


def assert_no_nonempty_ads(path):
    """NTFS alternate-stream bytes are outside tar; refuse rather than lose them."""
    if os.name != "nt":
        return
    import ctypes
    from ctypes import wintypes

    class StreamData(ctypes.Structure):
        _fields_ = [("size", ctypes.c_longlong), ("name", wintypes.WCHAR * 296)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    first = kernel.FindFirstStreamW
    first.argtypes = [
        wintypes.LPCWSTR,
        ctypes.c_int,
        ctypes.POINTER(StreamData),
        wintypes.DWORD,
    ]
    first.restype = wintypes.HANDLE
    next_stream = kernel.FindNextStreamW
    next_stream.argtypes = [wintypes.HANDLE, ctypes.POINTER(StreamData)]
    next_stream.restype = wintypes.BOOL
    close = kernel.FindClose
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    data = StreamData()
    handle = first(str(path), 0, ctypes.byref(data), 0)
    if handle == ctypes.c_void_p(-1).value:
        require(ctypes.get_last_error() == 38, "Cannot enumerate alternate streams")
        return
    try:
        while True:
            require(
                data.name == "::$DATA" or data.size == 0, "Nonempty NTFS ADS refused"
            )
            if not next_stream(handle, ctypes.byref(data)):
                require(
                    ctypes.get_last_error() == 38, "Alternate-stream enumeration failed"
                )
                break
    finally:
        close(handle)


_PROGRESS = False


def progress(message):
    if _PROGRESS:
        print(message, file=sys.stderr, flush=True)


def hash_inventory_file(job):
    item, root, expected = job
    item = no_links(item)
    info = item.stat()
    require(
        stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
        "Nonregular/hardlinked file refused",
    )
    require(
        (info.st_size, info.st_mtime_ns, info.st_ino) == expected,
        "Source changed before hashing",
    )
    assert_no_nonempty_ads(item)
    digest = sha(item)
    no_links(item)
    after = item.stat()
    require(
        (after.st_size, after.st_mtime_ns, after.st_ino) == expected,
        "Source changed while hashing",
    )
    return {
        "path": item.relative_to(root).as_posix(),
        "directory": False,
        "bytes": info.st_size,
        "sha256": digest,
    }


def inventory(path):
    path = no_links(path)
    require(path.is_dir(), "Retained tree missing")
    assert_no_nonempty_ads(path)
    progress("inventory start: " + str(path))
    rows, jobs = [], []
    # Serial traversal and path/type checks; only file reads use four workers.
    for directory, dirs, files in os.walk(path, followlinks=False):
        no_links(directory)
        for name in sorted(dirs + files):
            item = no_links(Path(directory) / name)
            info = item.stat()
            require(
                stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode),
                "Special file refused",
            )
            if stat.S_ISDIR(info.st_mode):
                assert_no_nonempty_ads(item)
                rows.append(
                    {"path": item.relative_to(path).as_posix(), "directory": True}
                )
            else:
                require(info.st_nlink == 1, "Hardlink refused")
                jobs.append((item, path, (info.st_size, info.st_mtime_ns, info.st_ino)))
    last = time.monotonic()
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix="retention-sha") as pool:
        for count, row in enumerate(pool.map(hash_inventory_file, jobs), 1):
            rows.append(row)
            if time.monotonic() - last >= 10:
                progress("inventory files: %d/%d" % (count, len(jobs)))
                last = time.monotonic()
    progress("inventory completed: %d files" % len(jobs))
    return canonical(rows)


def verified_source(receipt_path, root=RETENTION, expected_sha=None):
    receipt_path = confined(receipt_path, root)
    require(
        receipt_path.parent == no_links(root)
        and receipt_path.name.endswith(".verified.json"),
        "Require direct verified quarantine receipt",
    )
    receipt_sha = sha(receipt_path)
    require(
        expected_sha is None or receipt_sha == expected_sha,
        "Quarantine receipt SHA drift",
    )
    receipt = json.loads(receipt_path.read_bytes())
    require(
        receipt["status"] == "QUARANTINED_VERIFIED_NO_BYTES_DELETED"
        and receipt["bytes_deleted"] == 0,
        "Quarantine is not verified",
    )
    source = confined(receipt["destination"], root)
    require(
        source.parent == no_links(root) and source.is_dir(),
        "Only direct retained trees allowed",
    )
    rows = canonical(receipt["inventory"])
    require(inventory(source) == rows, "Verified retained tree drift")
    require(sha(receipt_path) == receipt_sha, "Receipt changed during read")
    return receipt_path, receipt_sha, source, rows


def preview(root=RETENTION, minimum_age_hours=24):
    root = no_links(root)
    require(
        root.is_dir()
        and type(minimum_age_hours) in (int, float)
        and minimum_age_hours >= 24,
        "At least 24h old retention required",
    )
    entries = []
    for path in sorted(root.glob("*.verified.json")):
        receipt_path, receipt_sha, source, rows = verified_source(path, root)
        newest = max(
            [source.stat().st_mtime] + [p.stat().st_mtime for p in source.rglob("*")]
        )
        if newest > time.time() - minimum_age_hours * 3600:
            continue
        entries.append(
            {
                "receipt": str(receipt_path),
                "receipt_sha256": receipt_sha,
                "source": str(source),
                "files": sum(not r["directory"] for r in rows),
                "bytes": sum(r.get("bytes", 0) for r in rows),
            }
        )
    return {
        "status": "PREVIEW_ONLY",
        "writes": False,
        "deletes": False,
        "entries": entries,
    }


def verify_archive(path, rows, expected_sha=None):
    path = no_links(path)
    require(expected_sha is None or sha(path) == expected_sha, "Archive SHA drift")
    # Read through gzip EOF so CRC/truncation is checked beyond tar end markers.
    progress("archive gzip CRC readback: " + str(path))
    with gzip.open(path, "rb") as stream:
        total, last = 0, time.monotonic()
        while block := stream.read(1024 * 1024):
            total += len(block)
            if time.monotonic() - last >= 10:
                progress("gzip readback bytes: %d" % total)
                last = time.monotonic()
    progress("archive member SHA readback: " + str(path))
    actual = []
    with tarfile.open(path, "r:gz") as archive:
        seen = set()
        for item in archive:
            name = member_path(item.name)
            require(name.casefold() not in seen, "Duplicate tar entry")
            seen.add(name.casefold())
            require(item.isdir() or item.isreg(), "Tar links/special entries refused")
            row = {"path": name, "directory": item.isdir()}
            if item.isreg():
                stream = archive.extractfile(item)
                require(stream is not None, "Unreadable tar member")
                with stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                row.update(bytes=item.size, sha256=digest)
            actual.append(row)
    require(canonical(actual) == canonical(rows), "Tar inventory/hash differs")


def idle():
    # Support both python -m and direct script invocation from any working directory.
    root = str(Path(__file__).resolve().parents[2])
    if root not in sys.path:
        sys.path.insert(0, root)
    from scripts.runner.archive_stale_probe_runs import host_idle

    host_idle()


def archive_retained(
    receipt, expected_sha, root=RETENTION, guard=idle, minimum_age_hours=24
):
    receipt, receipt_sha, source, rows = verified_source(receipt, root, expected_sha)
    newest = max(
        [source.stat().st_mtime] + [p.stat().st_mtime for p in source.rglob("*")]
    )
    require(
        type(minimum_age_hours) in (int, float)
        and math.isfinite(minimum_age_hours)
        and minimum_age_hours >= 0,
        "Invalid reviewed quarantine minimum age",
    )
    require(
        newest <= time.time() - minimum_age_hours * 3600,
        "Quarantine is newer than reviewed minimum age",
    )
    guard()
    archive = confined(source.with_name(source.name + ".tar.gz"), root)
    result_path = confined(source.with_name(source.name + ".compression.json"), root)
    require(
        not archive.exists() and not result_path.exists(),
        "Preserve previous archive/receipt",
    )
    source_bytes = sum(row.get("bytes", 0) for row in rows)
    required_free = math.ceil(source_bytes * 1.01) + len(rows) * 4096 + 1024 * 1024
    free_before = shutil.disk_usage(no_links(root)).free
    require(
        free_before >= required_free,
        "Insufficient free space for worst-case archive; source preserved",
    )
    # Exclusive creation; failed archive is retained diagnostically, never triggers prune.
    progress("archive write start: " + str(archive))
    with archive.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1, mtime=0) as zipped:
            with tarfile.open(
                fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT
            ) as tar:
                last = time.monotonic()
                for count, row in enumerate(rows, 1):
                    target = no_links(source / row["path"])
                    tar.add(target, arcname=row["path"], recursive=False)
                    if time.monotonic() - last >= 10:
                        progress("archive entries: %d/%d" % (count, len(rows)))
                        last = time.monotonic()
        raw.flush()
        os.fsync(raw.fileno())
    verify_archive(archive, rows)
    require(
        inventory(source) == rows and sha(receipt) == receipt_sha,
        "Source/receipt drift while archiving",
    )
    archive_sha = sha(archive)
    result = {
        "schema_version": 1,
        "status": "ARCHIVE_VERIFIED_SOURCE_RETAINED",
        "source": str(source),
        "quarantine_receipt": str(receipt),
        "quarantine_receipt_sha256": receipt_sha,
        "archive": str(archive),
        "archive_sha256": archive_sha,
        "archive_bytes": archive.stat().st_size,
        "inventory": rows,
        "source_bytes": sum(r.get("bytes", 0) for r in rows),
        "source_pruned": False,
        "minimum_age_hours": minimum_age_hours,
        "free_bytes_before_archive": free_before,
        "required_free_archive_bytes": required_free,
        "nonempty_ntfs_ads": "REJECTED_BY_SOURCE_INVENTORY",
        "preservation": "REGULAR_FILE_BYTES_AND_DIRECTORIES_ONLY",
        "ntfs_acl_ads_preserved": False,
    }
    guard()
    with result_path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    return {"receipt": str(result_path), "receipt_sha256": sha(result_path), **result}


def prune_retained(receipt, expected_sha, root=RETENTION, guard=idle):
    receipt = confined(receipt, root)
    require(
        receipt.parent == no_links(root)
        and receipt.name.endswith(".compression.json")
        and re.fullmatch("[0-9a-f]{64}", expected_sha or "")
        and sha(receipt) == expected_sha,
        "Exact reviewed compression receipt required",
    )
    result = json.loads(receipt.read_bytes())
    require(
        result["schema_version"] == 1
        and result["status"] == "ARCHIVE_VERIFIED_SOURCE_RETAINED"
        and result["source_pruned"] is False
        and result["ntfs_acl_ads_preserved"] is False,
        "Unknown compression receipt",
    )
    qpath, qsha, source, rows = verified_source(
        result["quarantine_receipt"], root, result["quarantine_receipt_sha256"]
    )
    require(
        str(source) == result["source"] and rows == canonical(result["inventory"]),
        "Compression source binding differs",
    )
    archive = confined(result["archive"], root)
    require(
        archive.parent == no_links(root)
        and archive == source.with_name(source.name + ".tar.gz"),
        "Archive identity/path differs",
    )
    require(archive.stat().st_size == result["archive_bytes"], "Archive size drift")
    verify_archive(archive, rows, result["archive_sha256"])
    guard()
    # Final complete source and immutable receipt re-read immediately before prune.
    require(
        inventory(source) == rows
        and sha(qpath) == qsha
        and sha(receipt) == expected_sha
        and sha(archive) == result["archive_sha256"],
        "Drift before retained-tree prune",
    )
    no_links(source)
    completed = confined(source.with_name(source.name + ".pruned.json"), root)
    require(not completed.exists(), "Prune completion receipt already exists")
    # Python filesystem end-to-end; never a path under _work, never recursive shell deletion.
    guard()  # Recheck idle admission after potentially long final verification.
    shutil.rmtree(source)
    summary = {
        "status": "RETAINED_TREE_PRUNED_VERIFIED_ARCHIVE_KEPT",
        "source": str(source),
        "archive": str(archive),
        "archive_sha256": result["archive_sha256"],
        "compression_receipt_sha256": expected_sha,
        "original_work_mutated": False,
        "ntfs_acl_ads_preserved": False,
    }
    with completed.open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2)
    return summary


def main():
    global _PROGRESS
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--archive",
        type=Path,
        help="Verified quarantine receipt; writes archive, never deletes",
    )
    modes.add_argument(
        "--apply",
        type=Path,
        help="Reviewed compression receipt; prunes retained copy only",
    )
    parser.add_argument("--expected-receipt-sha256")
    parser.add_argument(
        "--minimum-age-hours",
        type=float,
        default=24,
        help="Archive age, explicitly use 0 for reviewed fresh quarantines",
    )
    parser.add_argument(
        "--progress", action="store_true", help="Phase progress on stderr"
    )
    args = parser.parse_args()
    _PROGRESS = args.progress
    if args.archive or args.apply:
        require(
            re.fullmatch("[0-9a-f]{64}", args.expected_receipt_sha256 or ""),
            "Exact receipt SHA required",
        )
        operation = archive_retained if args.archive else prune_retained
        keywords = {"minimum_age_hours": args.minimum_age_hours} if args.archive else {}
        print(
            json.dumps(
                operation(
                    args.archive or args.apply, args.expected_receipt_sha256, **keywords
                ),
                indent=2,
            )
        )
    else:
        require(
            args.expected_receipt_sha256 is None, "SHA requires explicit archive/apply"
        )
        print(json.dumps(preview(), indent=2))


if __name__ == "__main__":
    main()
