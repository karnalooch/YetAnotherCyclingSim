"""Retain the fixed L07 material packages; upload LFS objects only on a hosted job.

The Windows command reads canonical packages and receipts and creates a new
immutable export. It never invokes Unreal, Git, a scheduled task or cleanup.
The Linux publication command uses an isolated Actions checkout. It uploads
explicit LFS OIDs, downloads them into empty storage, and emits pointer text for
the existing connector to commit. It never updates a remote Git ref.

Reuse: the repository's fixed TPP documentation LFS publication workflow,
actions/upload-artifact, and standard git-lfs push --object-id / fetch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path


REPOSITORY = "karnalooch/YetAnotherCyclingSim"
BRANCH = "codex/365-world-graph"
HOST = Path("D:/yacs")
EXPORT_RELATIVE = "work/lesson07-material-delivery-20261021"
BASE = "Content/Generated/YACS/Lesson07_Unified"
GAME = "/Game/Generated/YACS/Lesson07_Unified"
MI = BASE + "/Materials/MI_Landscape_Instance_YACS.uasset"
MI_PIN = {
    "sha256": "dcd34f9381414c0d63bbd234072ef1b4ac7dd62cf04a4ecc1fe2c48a029d3d2d",
    "size_bytes": 40154,
}
MI_BRANCH_PIN = {
    "sha256": "8c1dc875218a027a5ac83d88f8eedba49769fdd8494d287e7264807082eb11bf",
    "size_bytes": 39740,
}
ARRAY_PINS = {
    "Colour": {
        "sha256": "9efed079b6fba9f1c900c4348b9dceabab785a6eadcaf0ea21a6fe8b775568cf",
        "size_bytes": 24178947,
    },
    "Normal": {
        "sha256": "838a513e1c725e4e69da26715e6dff3734bfa2e98ef7d91a31278c2a0dbaf0f1",
        "size_bytes": 40441798,
    },
    "Masks": {
        "sha256": "e34fb9b1a51d4251058b6cf3da66951f3abc26ac4a6ab1c25f9d348c6923c9e8",
        "size_bytes": 12124066,
    },
}
TEXTURES = (
    "Grass_Normal",
    "Grass_Masks",
    "Cliffs_Colour",
    "Cliffs_Normal",
    "Cliffs_Masks",
)
ARRAYS = {
    channel: BASE + f"/Materials/TA_{channel}_Unified.uasset" for channel in ARRAY_PINS
}
TEXTURE_PATHS = {
    name: BASE + f"/Textures/SurfaceRepair_20261021/T_{name}.uasset"
    for name in TEXTURES
}
FULL_PATHS = tuple(sorted((*TEXTURE_PATHS.values(), *ARRAYS.values(), MI)))
SURFACE_MANIFEST_SHA256 = (
    "e8e0ae6cbd752b6b564a67b830aa16a5c4dbb01db3af9792963e8c6121bc88a6"
)
MACRO_PROVENANCE = {
    "application_run": 39533695950,
    "application_source_commit": "da91a9c66c6d5a6ee30aa6151e6024861291b4d1",
    "candidate_snapshot_sha256": "99c384e9701889aa2cae667b69e1faff32835e2b4440a9953e6f5884439b75ee",
    "evidence": "docs/assets/lesson07-macro-applied-20261021",
    "scope": "Existing approved Macro 0.05 checkpoint; no new scalar mutation",
}
# Populate only from the actual reviewed successful import artifacts. A failed
# import is never admitted and never falls back to the separate MI-only mode.
# Required keys: run_token, source_commit, live_import_sha256, live_import_bytes,
# probe_sha256, probe_bytes. SHA pins bind exact bytes, including their newlines.
SURFACE_PRODUCER: dict | None = {
    "run_token": "39636694686-1",
    "source_commit": "c59f717f11b134f75f695a26b94f8655bd3bd271",
    "live_import_sha256": "c1485abbc5cd56d51bc044c59b8ae7be23f21679ec3fe298014ccb5166542d5b",
    "live_import_bytes": 8989,
    "probe_sha256": "28cc3004e7cbbcae5e159e71426d579d5e8ccdcf7e582f839471ab91ae94f68c",
    "probe_bytes": 3843,
}

MARKERS = {"full": "[l07-export-materials]", "mi-only": "[l07-export-macro]"}
MAX_ASSET_BYTES = 512 * 1024 * 1024
MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_JSON_BYTES = 512 * 1024
RESERVE_BYTES = 5 * 1024 * 1024 * 1024  # Existing home-runner reserve.
PACKAGE_MAGIC = b"\xc1\x83\x2a\x9e"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_sha(value, length=64):
    require(
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value)
        and value != "0" * length,
        "Invalid or unpopulated SHA pin",
    )
    return value


def checked_token(value):
    require(
        isinstance(value, str)
        and re.fullmatch(r"[1-9][0-9]{0,19}-[1-9][0-9]{0,4}", value),
        "Invalid run token",
    )
    return value


def paths_for(mode):
    require(mode in MARKERS, "Unsupported explicit delivery mode")
    return FULL_PATHS if mode == "full" else (MI,)


def producer_for(mode):
    paths_for(mode)
    if mode == "mi-only":
        return None
    require(
        isinstance(SURFACE_PRODUCER, dict),
        "Successful reviewed surface producer pins are pending",
    )
    pin = dict(SURFACE_PRODUCER)
    require(
        set(pin)
        == {
            "run_token",
            "source_commit",
            "live_import_sha256",
            "live_import_bytes",
            "probe_sha256",
            "probe_bytes",
        },
        "Unexpected producer pin fields",
    )
    checked_token(pin["run_token"])
    checked_sha(pin["source_commit"], 40)
    for name in ("live_import", "probe"):
        checked_sha(pin[name + "_sha256"])
        require(
            type(pin[name + "_bytes"]) is int
            and 0 < pin[name + "_bytes"] <= MAX_JSON_BYTES,
            "Invalid receipt size pin",
        )
    return pin


def plain(path):
    """Reject links/reparse points at every existing ancestor; do not resolve them."""
    path = Path(path).absolute()
    for node in (path, *path.parents):
        try:
            info = node.lstat()
        except FileNotFoundError:
            continue
        require(
            not stat.S_ISLNK(info.st_mode)
            and not (getattr(info, "st_file_attributes", 0) & 0x400),
            "Linked or redirected path rejected",
        )
    return path


def digest(path):
    h = hashlib.sha256()
    with plain(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def record(path, *, package=False):
    path = plain(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode), "Expected a regular file")
    limit = MAX_ASSET_BYTES if package else MAX_JSON_BYTES
    require(0 < before.st_size <= limit, "File outside the bounded export size")
    if package:
        with path.open("rb") as stream:
            require(
                stream.read(4) == PACKAGE_MAGIC,
                "Expected hydrated Unreal package bytes",
            )
        for suffix in (".uexp", ".ubulk", ".uptnl", ".upayload"):
            require(
                not path.with_suffix(suffix).exists(),
                "Package sidecar requires separate reviewed scope",
            )
    result = {"sha256": digest(path), "size_bytes": before.st_size}
    after = plain(path).stat()
    require(
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
        "Source changed during read",
    )
    return result


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def parse_json(data):
    require(0 < len(data) <= MAX_JSON_BYTES, "JSON outside size bound")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result

    return json.loads(data.decode("utf-8-sig"), object_pairs_hook=unique)


def native_evidence(host, pin):
    token = pin["run_token"]
    locations = {
        "live-import.json": host
        / f"project/Saved/RuntimeProof/Lesson07SurfaceRepair-20261021/{token}/live-import.json",
        "probe.json": host / f"lesson07-remote/reports/{token}/probe.json",
    }
    evidence = {}
    for filename, path in locations.items():
        prefix = "live_import" if filename == "live-import.json" else "probe"
        expected = {
            "sha256": pin[prefix + "_sha256"],
            "size_bytes": pin[prefix + "_bytes"],
        }
        require(
            record(path) == expected, "Producer receipt bytes differ from reviewed pin"
        )
        data = path.read_bytes()
        require(
            len(data) == expected["size_bytes"]
            and hashlib.sha256(data).hexdigest() == expected["sha256"],
            "Producer receipt changed during read",
        )
        evidence["evidence/" + filename] = data
    validate_native_evidence(evidence, pin)
    return locations, evidence


def validate_native_evidence(evidence, pin):
    live = parse_json(evidence["evidence/live-import.json"])
    probe = parse_json(evidence["evidence/probe.json"])
    for key, expected in {
        "status": "SURFACE_REPAIR_SAVED_NATIVE_READBACK_PENDING_VISUAL",
        "saved": True,
        "failure_count": 0,
        "manifest_sha256": SURFACE_MANIFEST_SHA256,
        "classification_changed": False,
        "terrain_changed": False,
        "map_saved": False,
        "material_instance_changed": False,
        "normal_flatten_preserved": True,
    }.items():
        require(
            type(live.get(key)) is type(expected) and live[key] == expected,
            "Native import success contract differs",
        )
    require(
        live.get("changed_slots") == [0, 3]
        and live.get("other_slots_preserved") == [1, 2, 4]
        and live.get("grass_colour_preserved") is True,
        "Native slice-preservation proof differs",
    )
    imported = {
        name: GAME + f"/Textures/SurfaceRepair_20261021/T_{name}.T_{name}"
        for name in TEXTURES
    }
    require(
        live.get("imported") == imported, "Native imported object allowlist differs"
    )
    require(
        set(live.get("saved_array_hashes", {})) == set(ARRAYS),
        "Saved array hash inventory differs",
    )
    for value in live["saved_array_hashes"].values():
        checked_sha(value)
    for key, expected in {
        "status": "LESSON07_SURFACE_IMPORT_SAVED_IMAGES_REVIEW_PENDING",
        "source_commit": pin["source_commit"],
        "surface_import_verified": True,
        "identity_stable_across_probe": True,
        "client_exit_code": 0,
        "native_tool_call_attempts": 6,
        "native_tool_attempted": True,
        "native_tool_completed": True,
        "editor_started_or_stopped": False,
    }.items():
        require(
            type(probe.get(key)) is type(expected) and probe[key] == expected,
            "Completed producer probe contract differs",
        )
    return live


def export_checkpoint(host, mode, source_commit, run_token):
    """Fixture-injectable core. The CLI fixes host to D:/yacs on Windows."""
    checked_sha(source_commit, 40)
    checked_token(run_token)
    pin = producer_for(mode)
    host = plain(host)
    project = plain(host / "project")
    output = plain(host / EXPORT_RELATIVE / run_token)
    require(not output.exists(), "Export run directory already exists; never overwrite")
    locations, evidence = native_evidence(host, pin) if pin else ({}, {})
    live = validate_native_evidence(evidence, pin) if pin else None
    rows = []
    for relative in paths_for(mode):
        info = record(project / relative, package=True)
        if relative == MI:
            require(info == MI_PIN, "Saved approved Macro checkpoint differs")
        for channel, path in ARRAYS.items():
            if relative == path:
                require(
                    info["sha256"] == live["saved_array_hashes"][channel],
                    "Array differs from native saved receipt",
                )
        rows.append({"path": relative, **info})
    total = sum(row["size_bytes"] for row in rows)
    require(total <= MAX_TOTAL_BYTES, "Combined checkpoint exceeds export bound")
    require(
        shutil.disk_usage(host).free - 2 * total - 2 * MAX_JSON_BYTES >= RESERVE_BYTES,
        "Export would reduce the existing 5 GiB disk reserve",
    )
    manifest = {
        "schema_version": 1,
        "status": "EXPORTED_CHECKPOINT_BRANCH_PENDING",
        "mode": mode,
        "repository": REPOSITORY,
        "branch": BRANCH,
        "delivery_source_commit": source_commit,
        "delivery_run_token": run_token,
        "surface_producer": pin,
        "surface_manifest_sha256": SURFACE_MANIFEST_SHA256 if pin else None,
        "macro_provenance": MACRO_PROVENANCE,
        "assets": rows,
        "evidence": {
            name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
            for name, data in evidence.items()
        },
        "canonical_git_changed": False,
        "native_calls_by_export": 0,
        "branch_integrated": False,
        "visual_acceptance_established_by_export": False,
        "performance_pass": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=False)
    staged = output / "files"
    staged.mkdir()
    for row in rows:
        source, target = project / row["path"], staged / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        with plain(source).open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
        expected = {key: row[key] for key in ("sha256", "size_bytes")}
        require(
            record(target, package=True) == record(source, package=True) == expected,
            "Package changed during export copy",
        )
    data = json_bytes(manifest)
    (output / "manifest.json").write_bytes(data)
    archive = output / "checkpoint.zip"
    with zipfile.ZipFile(
        archive, "x", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as bundle:
        for name in sorted(
            [row["path"] for row in rows] + ["manifest.json", *evidence]
        ):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            with bundle.open(entry, "w", force_zip64=True) as target:
                if name == "manifest.json":
                    target.write(data)
                elif name in evidence:
                    target.write(evidence[name])
                else:
                    with (staged / name).open("rb") as source:
                        shutil.copyfileobj(source, target, 1024 * 1024)
    for row in rows:
        require(
            record(project / row["path"], package=True)
            == {key: row[key] for key in ("sha256", "size_bytes")},
            "Canonical package changed before export completed",
        )
    for filename, path in locations.items():
        require(
            path.read_bytes() == evidence["evidence/" + filename],
            "Producer evidence changed before export completed",
        )
    result = {
        "status": "CHECKPOINT_EXPORT_VERIFIED_BRANCH_PENDING",
        "mode": mode,
        "directory": str(output),
        "asset_count": len(rows),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": digest(archive),
        "manifest_sha256": hashlib.sha256(data).hexdigest(),
        "source_commit": source_commit,
        "run_token": run_token,
        "branch_integrated": False,
    }
    validate_bundle(
        archive,
        result["archive_sha256"],
        result["archive_bytes"],
        result["manifest_sha256"],
        mode,
        source_commit,
        run_token,
    )
    (output / "export-receipt.json").write_bytes(json_bytes(result))
    return result


def validate_bundle(
    archive, archive_sha, archive_bytes, manifest_sha, mode, source_commit, run_token
):
    checked_sha(archive_sha)
    checked_sha(manifest_sha)
    checked_sha(source_commit, 40)
    checked_token(run_token)
    pin = producer_for(mode)
    archive = plain(archive)
    require(
        type(archive_bytes) is int
        and 0 < archive_bytes <= MAX_TOTAL_BYTES + 4 * MAX_JSON_BYTES,
        "Archive outside size bound",
    )
    require(
        archive.stat().st_size == archive_bytes and digest(archive) == archive_sha,
        "Export archive identity differs",
    )
    expected_names = set(paths_for(mode)) | {"manifest.json"}
    if pin:
        expected_names |= {"evidence/live-import.json", "evidence/probe.json"}
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        require(
            len(infos) == len(expected_names)
            and {item.filename for item in infos} == expected_names,
            "Archive contains duplicate, missing or unapproved paths",
        )
        for item in infos:
            require(
                stat.S_IFMT(item.external_attr >> 16) == stat.S_IFREG
                and item.compress_type == zipfile.ZIP_STORED
                and not (item.flag_bits & 1),
                "Archive entry type or encoding differs",
            )
            require(
                0
                < item.file_size
                <= (
                    MAX_ASSET_BYTES
                    if item.filename.endswith(".uasset")
                    else MAX_JSON_BYTES
                ),
                "Archive member outside size bound",
            )
        raw = bundle.read("manifest.json")
        require(
            hashlib.sha256(raw).hexdigest() == manifest_sha,
            "Export manifest identity differs",
        )
        manifest = parse_json(raw)
        for key, expected in {
            "schema_version": 1,
            "status": "EXPORTED_CHECKPOINT_BRANCH_PENDING",
            "mode": mode,
            "repository": REPOSITORY,
            "branch": BRANCH,
            "delivery_source_commit": source_commit,
            "delivery_run_token": run_token,
            "surface_producer": pin,
            "surface_manifest_sha256": SURFACE_MANIFEST_SHA256 if pin else None,
            "macro_provenance": MACRO_PROVENANCE,
            "canonical_git_changed": False,
            "native_calls_by_export": 0,
            "branch_integrated": False,
            "visual_acceptance_established_by_export": False,
            "performance_pass": False,
        }.items():
            require(
                type(manifest.get(key)) is type(expected) and manifest[key] == expected,
                "Export provenance contract differs",
            )
        rows = manifest.get("assets")
        require(
            isinstance(rows, list)
            and len(rows) == len(paths_for(mode))
            and [row.get("path") for row in rows] == list(paths_for(mode)),
            "Export asset allowlist differs",
        )
        evidence = {}
        for name in expected_names - set(paths_for(mode)) - {"manifest.json"}:
            evidence[name] = bundle.read(name)
            prefix = "live_import" if name.endswith("live-import.json") else "probe"
            expected = {
                "sha256": pin[prefix + "_sha256"],
                "size_bytes": pin[prefix + "_bytes"],
            }
            require(
                manifest.get("evidence", {}).get(name) == expected
                and len(evidence[name]) == expected["size_bytes"]
                and hashlib.sha256(evidence[name]).hexdigest() == expected["sha256"],
                "Embedded native evidence differs",
            )
        require(
            set(manifest.get("evidence", {})) == set(evidence),
            "Unexpected evidence inventory",
        )
        live = validate_native_evidence(evidence, pin) if pin else None
        total = 0
        for row in rows:
            require(
                set(row) == {"path", "sha256", "size_bytes"},
                "Unexpected asset record fields",
            )
            checked_sha(row["sha256"])
            require(
                type(row["size_bytes"]) is int
                and 0 < row["size_bytes"] <= MAX_ASSET_BYTES
                and bundle.getinfo(row["path"]).file_size == row["size_bytes"],
                "Asset size differs",
            )
            h = hashlib.sha256()
            with bundle.open(row["path"]) as source:
                first = source.read(4)
                require(
                    first == PACKAGE_MAGIC,
                    "Archive contains a pointer or non-package payload",
                )
                h.update(first)
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    h.update(block)
            require(h.hexdigest() == row["sha256"], "Archive asset SHA256 differs")
            if row["path"] == MI:
                require(
                    {key: row[key] for key in MI_PIN} == MI_PIN,
                    "Archive Macro checkpoint differs",
                )
            for channel, path in ARRAYS.items():
                if row["path"] == path:
                    require(
                        row["sha256"] == live["saved_array_hashes"][channel],
                        "Archive array differs from native save",
                    )
            total += row["size_bytes"]
        require(total <= MAX_TOTAL_BYTES, "Combined archive assets exceed bound")
    return manifest


def pointer(row):
    return f"version https://git-lfs.github.com/spec/v1\noid sha256:{row['sha256']}\nsize {row['size_bytes']}\n"


def git(repo, *args, input_text=None, timeout=120, index_file=None):
    env = os.environ.copy()
    env.update(
        GIT_TERMINAL_PROMPT="0",
        GIT_TRACE="0",
        GIT_CURL_VERBOSE="0",
        GIT_TRACE_CURL="0",
        GIT_AUTHOR_NAME="github-actions[bot]",
        GIT_COMMITTER_NAME="github-actions[bot]",
        GIT_AUTHOR_EMAIL="41898282+github-actions[bot]@users.noreply.github.com",
        GIT_COMMITTER_EMAIL="41898282+github-actions[bot]@users.noreply.github.com",
    )
    if index_file is not None:
        env["GIT_INDEX_FILE"] = str(plain(index_file))
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    # Never print Git configuration, credentials, arbitrary remote responses or
    # subprocess environments. The fixed operation and exit code identify failure.
    require(
        result.returncode == 0,
        f"Isolated Git operation {args[0]} failed with exit {result.returncode}",
    )
    return result.stdout.strip()


def readback_commit(repo, rows, source):
    """Build the local LFS scan tree from verified staged pointers only."""
    entries = []
    for row in rows:
        oid = checked_sha(git(repo, "rev-parse", "--verify", ":" + row["path"]), 40)
        entries.append(f"100644 {oid}\t{row['path']}\n")
    # LFS scans the whole tree before its path filter. A separate empty index
    # prevents unrelated tracked blobs from entering that scan and leaves the
    # publication checkout's real index and HEAD unchanged.
    with tempfile.TemporaryDirectory(prefix="l07-lfs-readback-") as directory:
        index_file = Path(directory) / "index"
        git(repo, "read-tree", "--empty", index_file=index_file)
        git(
            repo,
            "update-index",
            "--index-info",
            input_text="".join(entries),
            index_file=index_file,
        )
        tree = git(repo, "write-tree", index_file=index_file)
    require(
        set(git(repo, "ls-tree", "-r", "--name-only", tree).splitlines())
        == {row["path"] for row in rows},
        "Local readback tree must contain only the exact checkpoint pointers",
    )
    return git(
        repo,
        "commit-tree",
        tree,
        "-p",
        source,
        "-m",
        "Local L07 LFS readback tree; no remote Git ref update",
    )


def stage_lfs(repo, archive, manifest):
    """Populate only the exact package paths in an already isolated checkout."""
    rows = manifest["assets"]
    require(
        not git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        "Isolated publication checkout must start clean",
    )
    for row in rows:
        path = row["path"]
        tracked = git(repo, "ls-tree", "--name-only", "HEAD", "--", path)
        allowed = {pointer(row)}
        if path == MI:
            allowed.add(pointer(MI_BRANCH_PIN))
        for channel, array_path in ARRAYS.items():
            if path == array_path:
                allowed.add(pointer(ARRAY_PINS[channel]))
        if tracked:
            require(
                tracked == path and git(repo, "show", "HEAD:" + path) + "\n" in allowed,
                "Branch asset is outside reviewed baseline and candidate pins",
            )
        else:
            require(
                path in TEXTURE_PATHS.values(),
                "Existing checkpoint asset is missing from branch",
            )
        require(
            git(repo, "check-attr", "filter", "--", path) == path + ": filter: lfs",
            "Existing uasset LFS rule is required",
        )
    with zipfile.ZipFile(archive) as bundle:
        for row in rows:
            target = plain(repo / row["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(row["path"]) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            require(
                record(target, package=True)
                == {key: row[key] for key in ("sha256", "size_bytes")},
                "Isolated package copy differs",
            )
    git(repo, "lfs", "install", "--local", "--skip-smudge")
    git(repo, "add", "--sparse", "--", *(row["path"] for row in rows), timeout=300)
    changed = set(git(repo, "diff", "--cached", "--name-only").splitlines())
    require(
        changed <= {row["path"] for row in rows},
        "Staging changed paths outside exact asset boundary",
    )
    for row in rows:
        require(
            git(repo, "show", ":" + row["path"]) + "\n" == pointer(row),
            "Staged package must be the exact LFS pointer, never raw Git bytes",
        )
    return readback_commit(repo, rows, manifest["delivery_source_commit"])


def verify_server_objects(storage, rows):
    for row in rows:
        oid = row["sha256"]
        obj = storage / "objects" / oid[:2] / oid[2:4] / oid
        require(
            record(obj, package=True)
            == {key: row[key] for key in ("sha256", "size_bytes")},
            "Independent server LFS bytes differ",
        )


def publish_lfs(repo, archive, manifest, output):
    source = manifest["delivery_source_commit"]
    require(
        git(repo, "rev-parse", "HEAD") == source,
        "Publication checkout must match exact delivery source",
    )
    require(
        git(repo, "remote", "get-url", "origin")
        in (f"https://github.com/{REPOSITORY}", f"https://github.com/{REPOSITORY}.git"),
        "Publication remote must be the fixed GitHub repository",
    )
    expected_ref = source + "\trefs/heads/" + BRANCH
    require(
        git(repo, "ls-remote", "origin", "refs/heads/" + BRANCH) == expected_ref,
        "Branch moved before LFS upload; stop without rebasing",
    )
    output = plain(output)
    require(not output.exists(), "Publication evidence directory must be new")
    output.mkdir(parents=True, exist_ok=False)
    local_commit = stage_lfs(repo, archive, manifest)
    rows = manifest["assets"]
    oids = sorted({row["sha256"] for row in rows})
    git(
        repo,
        "lfs",
        "push",
        "--object-id",
        "origin",
        "--stdin",
        input_text="\n".join(oids) + "\n",
        timeout=900,
    )
    storage = output / "independent-lfs-readback"
    storage.mkdir(exist_ok=False)
    require(
        not list(storage.iterdir()), "Independent LFS readback storage must start empty"
    )
    git(
        repo,
        "-c",
        "lfs.storage=" + str(storage),
        "-c",
        "lfs.fetchrecentalways=false",
        "-c",
        "lfs.skipdownloaderrors=false",
        "lfs",
        "fetch",
        "--include=" + ",".join(row["path"] for row in rows),
        "--exclude=",
        "origin",
        local_commit,
        timeout=900,
    )
    verify_server_objects(storage, rows)
    require(
        git(repo, "ls-remote", "origin", "refs/heads/" + BRANCH) == expected_ref,
        "Branch moved during LFS upload; objects retained but connector commit requires new review",
    )
    receipt = {
        "schema_version": 1,
        "status": "REMOTE_LFS_BYTES_VERIFIED_BRANCH_NOT_UPDATED",
        "repository": REPOSITORY,
        "branch": BRANCH,
        "expected_branch_head": source,
        "mode": manifest["mode"],
        "delivery_run_token": manifest["delivery_run_token"],
        "export_archive_sha256": digest(archive),
        "export_manifest_sha256": hashlib.sha256(json_bytes(manifest)).hexdigest(),
        "assets": rows,
        "storage_started_empty": True,
        "canonical_git_changed": False,
        "remote_ref_updated": False,
        "native_calls": 0,
        "visual_acceptance": False,
        "verification": "Explicit OID upload, independent authenticated LFS fetch into empty storage, SHA256 and size verification",
    }
    (output / "server-lfs-readback.json").write_bytes(json_bytes(receipt))
    (output / "git-lfs-pointers.json").write_bytes(
        json_bytes(
            {
                "schema_version": 1,
                "repository": REPOSITORY,
                "branch": BRANCH,
                "expected_branch_head": source,
                "remote_ref_updated": False,
                "tree_elements": [
                    {
                        "path": row["path"],
                        "mode": "100644",
                        "type": "blob",
                        "content": pointer(row),
                    }
                    for row in rows
                ],
            }
        )
    )
    return {
        "directory": str(output),
        "status": receipt["status"],
        "asset_count": len(rows),
    }


def admit_event(path, source_commit):
    event = parse_json(plain(path).read_bytes())
    require(
        event.get("repository", {}).get("full_name") == REPOSITORY
        and event.get("sender", {}).get("login") == "karnalooch"
        and event.get("ref") == "refs/heads/" + BRANCH
        and event.get("after") == checked_sha(source_commit, 40),
        "Owner push/event/source identity differs",
    )
    message = event.get("head_commit", {}).get("message", "")
    require(isinstance(message, str), "Commit message missing")
    modes = [mode for mode, marker in MARKERS.items() if marker in message]
    require(len(modes) == 1, "Exactly one explicit material-export marker is required")
    producer_for(modes[0])
    return modes[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    admit = sub.add_parser("admit")
    admit.add_argument("--event", type=Path, required=True)
    admit.add_argument("--source-commit", required=True)
    export = sub.add_parser("export")
    upload = sub.add_parser("upload-lfs")
    for item in (export, upload):
        item.add_argument("--mode", choices=MARKERS, required=True)
        item.add_argument("--source-commit", required=True)
        item.add_argument("--run-token", required=True)
    upload.add_argument("--archive", type=Path, required=True)
    upload.add_argument("--archive-sha256", required=True)
    upload.add_argument("--archive-bytes", type=int, required=True)
    upload.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    if args.command == "admit":
        print(admit_event(args.event, args.source_commit))
        return
    checked_sha(args.source_commit, 40)
    checked_token(args.run_token)
    require(
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
        and os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH
        and os.environ.get("GITHUB_ACTOR") == "karnalooch"
        and os.environ.get("GITHUB_SHA") == args.source_commit
        and args.run_token
        == os.environ.get("GITHUB_RUN_ID", "")
        + "-"
        + os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "Fixed owner Actions identity is required",
    )
    require(
        admit_event(Path(os.environ["GITHUB_EVENT_PATH"]), args.source_commit)
        == args.mode,
        "Explicit event mode differs",
    )
    if args.command == "export":
        require(
            os.name == "nt" and os.environ.get("RUNNER_ENVIRONMENT") == "self-hosted",
            "Canonical export is Windows read-only host work",
        )
        result = export_checkpoint(HOST, args.mode, args.source_commit, args.run_token)
    else:
        require(
            os.name == "posix"
            and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
            and os.environ.get("RUNNER_OS") == "Linux",
            "LFS upload is restricted to the isolated GitHub-hosted Linux job",
        )
        workspace = plain(Path(os.environ["GITHUB_WORKSPACE"]))
        repo = plain(workspace / ("l07-lfs-" + args.run_token))
        require(
            Path.cwd().absolute() == repo,
            "Upload must run inside its isolated job checkout",
        )
        require(
            plain(args.archive)
            == workspace / ("l07-download-" + args.run_token) / "checkpoint.zip",
            "Unexpected artifact download path",
        )
        manifest = validate_bundle(
            args.archive,
            args.archive_sha256,
            args.archive_bytes,
            args.manifest_sha256,
            args.mode,
            args.source_commit,
            args.run_token,
        )
        result = publish_lfs(
            repo,
            args.archive,
            manifest,
            Path(os.environ["RUNNER_TEMP"]) / ("l07-lfs-proof-" + args.run_token),
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
