"""Render only the current road asphalt base twice in the persistent workspace.

Reuses the pinned Material Forge producer. This establishes source determinism,
not Unreal consumption, human appearance acceptance or performance admission.
It never provisions tools, cleans caches, modifies a map or starts Unreal/MCP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.assets import material_forge as forge
from scripts.assets.road_material_contract import check_asphalt_source
from scripts.manage_local_workspace import load_workspace
from scripts.ue.official_mcp_source_probe import bounded_files, checked_path

GODOT_ARCHIVE_SHA = "731980f9608d61333e5baf54a2ef17210acc7a538446c0cb9969f002aca1e953"
MM_ARCHIVE_SHA = "deb4416bc939861d48097a866a8b2bf0363c29ff64874f2e04478658ff900808"
MM_SOURCE_SHA = "4d29a815489866aae483281cf44b2cfe48d3cc3e"
GODOT_NAME = "Godot_v4.7.2-stable_win64.exe"
CHANNELS = ("BaseColor", "Normal_DX", "ORM", "Height", "DetailMasks")


def sha(path: Path) -> str:
    before = path.stat()
    if not path.is_file() or before.st_size > 512 * 1024 * 1024:
        raise ValueError("Missing or oversized pinned input: " + path.name)
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Pinned input changed during read: " + path.name)
    return value.hexdigest()


def git(directory: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(directory), *args], text=True, timeout=30
    ).strip()


def one_file(root: Path, name: str) -> Path:
    matches = [path for path in bounded_files(root) if path.name == name]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous pinned tool: " + name)
    return matches[0]


def prove(expected_head: str, run: str, attempt: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_head):
        raise ValueError("Invalid exact repository SHA")
    if not all(re.fullmatch(r"[0-9]{1,20}", value) for value in (run, attempt)):
        raise ValueError("Invalid workflow identity")
    if git(ROOT, "rev-parse", "HEAD") != expected_head or git(
        ROOT, "status", "--porcelain", "--untracked-files=no"
    ):
        raise ValueError("Source proof requires an exact clean tracked checkout")
    config = load_workspace()
    workspace = Path(config["root"])
    tools = workspace / "tool-cache/material-forge"
    checked_path(workspace, tools)
    godot_archive = tools / "Godot_v4.7.2-stable_win64.exe.zip"
    mm_archive = tools / "material_maker_1_7_windows.zip"
    for path, expected in (
        (godot_archive, GODOT_ARCHIVE_SHA),
        (mm_archive, MM_ARCHIVE_SHA),
    ):
        checked_path(workspace, path)
        if sha(path) != expected:
            raise ValueError("Pinned tool archive hash mismatch: " + path.name)
    godot = one_file(tools / "godot-4.7.2-stable", GODOT_NAME)
    mm = one_file(tools / "material-maker-1.7", "material_maker.exe")
    checked_path(workspace, godot)
    checked_path(workspace, mm)
    # Authenticate executable bytes against the approved archive, without extraction.
    for archive, executable in ((godot_archive, godot), (mm_archive, mm)):
        with zipfile.ZipFile(archive) as bundle:
            entries = [
                item
                for item in bundle.infolist()
                if Path(item.filename).name == executable.name
            ]
            if len(entries) != 1 or entries[0].file_size > 512 * 1024 * 1024:
                raise ValueError("Missing, ambiguous or oversized archived executable")
            with bundle.open(entries[0]) as stream:
                archived_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if sha(executable) != archived_hash:
            raise ValueError("Installed executable differs from its approved archive")
    source = tools / ("material-maker-source-" + MM_SOURCE_SHA)
    checked_path(workspace, source)
    source_head = git(source, "rev-parse", "HEAD")
    source_status = git(source, "status", "--porcelain", "--untracked-files=no")
    if source_head != MM_SOURCE_SHA or source_status:
        print(
            json.dumps(
                {
                    "material_maker_source_head": source_head,
                    "tracked_changes": source_status[:4096],
                    "tracked_changes_truncated": len(source_status) > 4096,
                }
            )
        )
        raise ValueError("Material Maker source is not the pinned clean revision")
    for path in (
        source / "project.godot",
        source / ".godot/global_script_class_cache.cfg",
        mm.parent / "nodes/material.mmg",
    ):
        checked_path(workspace, path)
        sha(path)
    checked_path(workspace, source / ".godot/imported")
    family = next(
        item
        for item in forge.load_catalog()["families"]
        if item["id"] == "aged_mountain_asphalt"
    )
    variant = next(item for item in family["variants"] if item["id"] == "base")
    upstreams = forge.load_upstreams()
    work = Path(config["work"])
    checked_path(workspace, work)
    proof_root = (
        work / "material-forge/road-asphalt" / expected_head / (run + "-" + attempt)
    )
    ancestor = proof_root
    while not ancestor.exists():
        ancestor = ancestor.parent
    checked_path(workspace, ancestor)
    proof_root.mkdir(parents=True, exist_ok=False)
    receipts = []
    for name in ("run-a", "run-b"):
        directory = proof_root / name / "aged_mountain_asphalt/base"
        entry = forge.author_variant(mm.parent, directory, family, variant, upstreams)
        log = proof_root / (name + "-render.log")
        with log.open("xb") as stream:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/assets/render_material_forge.py"),
                    "--godot",
                    str(godot),
                    "--source",
                    str(source),
                    "--variant",
                    str(directory),
                    "--resolution",
                    "2048",
                    "--timeout-seconds",
                    "300",
                ],
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=360,
                check=False,
            )
        if result.returncode:
            raise ValueError("Road asphalt render failed: " + name)
        checked = check_asphalt_source(directory)
        receipts.append(
            {
                "run": name,
                "directory": str(directory.relative_to(proof_root)),
                "fingerprint": entry["fingerprint"],
                "source": checked,
                "graph_sha256": sha(directory / "Material.ptex"),
                "map_sha256": {
                    channel: forge._json(directory / "validation.json")["maps"][
                        channel
                    ]["sha256"]
                    for channel in CHANNELS
                },
            }
        )
    if any(
        receipts[0][key] != receipts[1][key]
        for key in ("fingerprint", "graph_sha256", "map_sha256")
    ):
        raise ValueError("Two-run asphalt graph or raw map determinism failed")
    receipt = {
        "schema_version": 1,
        "issue": 364,
        "exact_sha": expected_head,
        "run": run,
        "attempt": attempt,
        "status": "ROAD_ASPHALT_SOURCE_DETERMINISM_PASS",
        "source_fingerprint": forge.source_fingerprint(),
        "runs": receipts,
        "godot_sha256": sha(godot),
        "material_maker_sha256": sha(mm),
        "tool_archive_hashes_verified": True,
        "source_commit": MM_SOURCE_SHA,
        "two_run_graph_and_map_bytes_equal": True,
        "rendered_variant_count": 2,
        "unreal_consumption_verified": False,
        "world_mutation": False,
        "human_visual_status": "PENDING_FINAL_M3",
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }
    target = proof_root / "source-proof.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "exact_sha": expected_head,
                "graph_sha256": receipts[0]["graph_sha256"],
                "map_sha256": receipts[0]["map_sha256"],
                "source_proof_sha256": sha(target),
                "human_visual_status": "PENDING_FINAL_M3",
            }
        )
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    prove(args.expected_head, args.run, args.attempt)
