"""Render only the current dry_varied asphalt twice in the persistent workspace.

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

from scripts.assets.road_material_contract import (
    FAMILY,
    VARIANT,
    _catalog,
    _read,
    check_asphalt_source,
)
from scripts.manage_local_workspace import load_workspace
from scripts.ue.official_mcp_source_probe import bounded_files, checked_path

GODOT_ARCHIVE_SHA = "731980f9608d61333e5baf54a2ef17210acc7a538446c0cb9969f002aca1e953"
MM_ARCHIVE_SHA = "deb4416bc939861d48097a866a8b2bf0363c29ff64874f2e04478658ff900808"
MM_SOURCE_SHA = "4d29a815489866aae483281cf44b2cfe48d3cc3e"
GODOT_NAME = "Godot_v4.7.2-stable_win64.exe"
CHANNELS = ("BaseColor", "Normal_DX", "ORM", "Height", "DetailMasks")
PRIMED_ICON_IMPORTS = frozenset(
    (
        "addons/flexible_layout/arrow.svg.import",
        "addons/flexible_layout/tab.svg.import",
        "material_maker/icons/godot_logo.svg.import",
        "material_maker/icons/grab.svg.import",
        *(
            "material_maker/windows/about/" + name + ".svg.import"
            for name in (
                "bluesky",
                "discord",
                "epic_megagrant",
                "facebook",
                "github",
                "itchio",
                "mastodon",
                "patreon",
                "x",
                "youtube",
            )
        ),
        "splash_screen/arrow.svg.import",
        "splash_screen/splash_title.svg.import",
    )
)


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


def import_metadata(raw: str) -> dict:
    """Read the literal-only subset of Godot import metadata, never Variants.

    JSON literals admit numbers, strings, lists and dictionaries, including the
    multiline texture metadata. Godot Object/Resource constructor expressions
    and duplicate assignments are rejected before any native parser runs.
    """
    sections = {}
    current = None
    pending = ""
    key = ""
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        if not pending and re.fullmatch(r"\[[a-z]+\]", line):
            current = line[1:-1]
            if current in sections:
                raise ValueError("Duplicate import metadata section")
            sections[current] = {}
            continue
        if not pending:
            if current is None or "=" not in line:
                raise ValueError("Invalid import metadata assignment")
            key, line = line.split("=", 1)
            if not re.fullmatch(r"[A-Za-z0-9_/.]+", key) or key in sections[current]:
                raise ValueError("Invalid or duplicate import metadata key")
        pending += line + "\n"
        try:
            value = json.loads(pending)
        except json.JSONDecodeError:
            continue
        sections[current][key] = value
        pending = ""
    if pending or set(sections) != {"remap", "deps", "params"}:
        raise ValueError("Import metadata contains an unsupported non-literal value")
    return sections


def primed_source_identity(source: Path) -> dict:
    """Admit only the observed Godot-generated UI texture import metadata.

    Godot --import is required by the existing producer. Its tracked SVG import
    metadata is separate from program/graph inputs and is retained explicitly.
    No cleanup, source rewrite, new import or unlisted change is permitted.
    """
    if git(source, "rev-parse", "HEAD") != MM_SOURCE_SHA:
        raise ValueError("Material Maker source is not the pinned revision")
    if git(source, "diff", "--cached", "--name-only", "HEAD"):
        raise ValueError("Material Maker source has staged changes")
    changes = git(source, "diff", "--name-status", "--no-renames", "HEAD")
    imports = {}
    budget = [0]
    for line in changes.splitlines():
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] != "M" or fields[1] not in PRIMED_ICON_IMPORTS:
            raise ValueError("Unadmitted Material Maker source change: " + line[:512])
        relative = fields[1]
        path = source / relative
        checked_path(source, path)
        raw, retained, _identity = _read(path, 65536, budget)
        parser = import_metadata(raw.decode("utf-8"))
        if (parser["remap"].get("importer"), parser["remap"].get("type")) not in {
            ("texture", "CompressedTexture2D"),
            ("svg", "DPITexture"),
        } or parser["deps"].get("source_file") != "res://" + relative.removesuffix(
            ".import"
        ):
            raise ValueError("Primed SVG import metadata has unexpected semantics")
        if (
            set(parser["remap"])
            - {"importer", "type", "uid", "metadata"}
            - {
                key
                for key in parser["remap"]
                if key == "path" or key.startswith("path.")
            }
        ):
            raise ValueError("Unexpected primed texture remap key")
        targets = [
            value
            for key, value in parser["remap"].items()
            if key == "path" or key.startswith("path.")
        ]
        destinations = parser["deps"].get("dest_files")
        if not targets or not isinstance(destinations, list) or not destinations:
            raise ValueError("Primed texture cache destinations are missing")
        for remap in [*targets, *destinations]:
            if (
                not isinstance(remap, str)
                or not remap.startswith("res://.godot/imported/")
                or ".." in remap.split("/")
                or "\\" in remap
                or not remap.endswith((".ctex", ".dpitex"))
            ):
                raise ValueError("Primed SVG texture remap escaped the imported cache")
        blob = git(source, "rev-parse", "HEAD:" + relative)
        if not re.fullmatch(r"[0-9a-f]{40}", blob):
            raise ValueError("Primed SVG import has no pinned source blob")
        imports[relative] = {"source_blob_id": blob, "sha256": retained["sha256"]}
    return {
        "source_commit": MM_SOURCE_SHA,
        "program_inputs_unchanged": True,
        "primed_icon_imports": imports,
    }


def source_recipe(catalog: dict) -> tuple[dict, dict]:
    """Select the one strictly pinned recipe before any authoring or render."""
    _catalog(catalog)
    family = next(item for item in catalog["families"] if item["id"] == FAMILY)
    variant = next(item for item in family["variants"] if item["id"] == VARIANT)
    return family, variant


def prove(expected_head: str, run: str, attempt: str) -> dict:
    from scripts.assets import material_forge as forge

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
    primed_source = primed_source_identity(source)
    for path in (
        source / "project.godot",
        source / ".godot/global_script_class_cache.cfg",
        mm.parent / "nodes/material.mmg",
    ):
        checked_path(workspace, path)
        sha(path)
    checked_path(workspace, source / ".godot/imported")
    family, variant = source_recipe(forge.load_catalog())
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
        directory = proof_root / name / FAMILY / VARIANT
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
    if primed_source_identity(source) != primed_source:
        raise ValueError(
            "Material Maker program or primed icon inputs changed during replay"
        )
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
        "primed_source_identity": primed_source,
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
