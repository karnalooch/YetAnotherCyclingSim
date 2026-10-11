"""Render the eight authored local road crack motifs twice on the existing host.

Reuse the admitted Material Maker/Godot install and unchanged GDScript exporter.
The receipt observes each owned process exit and authenticates the two original
source bundles. It does not import assets, place decals or change an Unreal map.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.assets import material_forge_road_decals as decals
from scripts.assets import run_road_asphalt_source_proof as admitted
from scripts.manage_local_workspace import load_workspace
from scripts.ue.official_mcp_source_probe import checked_path

PROCESS_SECONDS = 180
TOTAL_SECONDS = 1200
# Original adapted PBR node, identical in both retained Godot source bundles 27f.
PBR_NODE_SHA256 = "e98108049b3552ada5ef510d94bee254856bcdfc91bc8589e9ddb48e3423fabc"
FATAL_TOKENS = (
    "COMPUTE SHADER ERROR", "SCRIPT ERROR", "shader error:",
    "errors encountered when exporting", "Could not export", "YACS_RENDER_FAILED",
)
SOURCE_FILES = (
    "scripts/assets/run_road_decals_source_proof.py",
    "scripts/assets/material_forge_road_decals.py",
    "scripts/assets/material_forge.py",
    "scripts/assets/build_material_maker_limestone.py",
    "scripts/assets/render_material_forge.gd",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def write_once(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    require(len(raw) <= 2 * 1024 * 1024, "Crack source receipt exceeds its bound")
    with path.open("xb") as stream:
        stream.write(raw)


def exact_source(expected_head):
    require(re.fullmatch(r"[0-9a-f]{40}", expected_head), "Invalid exact source SHA")
    require(admitted.git(ROOT, "rev-parse", "HEAD") == expected_head
            and not admitted.git(ROOT, "status", "--porcelain", "--untracked-files=no"),
            "Crack source proof requires an exact clean tracked checkout")
    for relative in SOURCE_FILES:
        require(admitted.git(ROOT, "rev-parse", expected_head + ":" + relative)
                == admitted.git(ROOT, "hash-object", "--no-filters", str(ROOT / relative)),
                "Crack source executable bytes differ from their committed revision")
    for path in (decals.DEFAULT_RECIPE, decals.forge.DEFAULT_UPSTREAMS):
        admitted.git(ROOT, "ls-files", "--error-unmatch", str(path.relative_to(ROOT)))


def runtime(config):
    workspace = Path(config["root"])
    tools = workspace / "tool-cache/material-forge"
    checked_path(workspace, tools)
    pins = {}
    programs = {}
    for role, archive_name, expected_sha, directory, executable_name in (
        ("godot", "Godot_v4.7.2-stable_win64.exe.zip", admitted.GODOT_ARCHIVE_SHA,
         "godot-4.7.2-stable", admitted.GODOT_NAME),
        ("material_maker", "material_maker_1_7_windows.zip", admitted.MM_ARCHIVE_SHA,
         "material-maker-1.7", "material_maker.exe"),
    ):
        archive = tools / archive_name
        checked_path(workspace, archive)
        require(admitted.sha(archive) == expected_sha, "Pinned crack producer archive differs")
        executable = admitted.one_file(tools / directory, executable_name)
        checked_path(workspace, executable)
        with zipfile.ZipFile(archive) as bundle:
            entries = [row for row in bundle.infolist() if Path(row.filename).name == executable.name]
            require(len(entries) == 1 and 0 < entries[0].file_size <= 512 * 1024 * 1024,
                    "Ambiguous, missing or oversized archived crack producer")
            with bundle.open(entries[0]) as stream:
                executable_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        require(admitted.sha(executable) == executable_sha,
                "Installed crack producer differs from the approved archive")
        pins[str(archive)] = expected_sha
        pins[str(executable)] = executable_sha
        programs[role] = executable
    source = tools / ("material-maker-source-" + admitted.MM_SOURCE_SHA)
    checked_path(workspace, source)
    primed = admitted.primed_source_identity(source)
    for path in (source / "project.godot", source / ".godot/global_script_class_cache.cfg",
                 programs["material_maker"].parent / "nodes/material.mmg"):
        checked_path(workspace, path)
        pins[str(path)] = admitted.sha(path)
    require(pins[str(programs["material_maker"].parent / "nodes/material.mmg")] == PBR_NODE_SHA256,
            "Material Maker PBR node differs from both authenticated 27f source bundles")
    checked_path(workspace, source / ".godot/imported")
    return {"workspace": workspace, "source": source, "programs": programs,
            "pins": pins, "primed_source_identity": primed}


def verify_runtime(value):
    for path, digest in value["pins"].items():
        checked_path(value["workspace"], Path(path))
        require(admitted.sha(Path(path)) == digest, "Crack producer changed during the two runs")
    require(admitted.primed_source_identity(value["source"]) == value["primed_source_identity"],
            "Material Maker program or admitted primed imports changed")


def render_owned(command, seconds, records):
    """Observe the one child directly; retain failure logs and its real exit."""
    require(type(seconds) is int and 0 < seconds <= PROCESS_SECONDS, "Invalid render deadline")
    log = Path(command["log_path"])
    record = {"motif": command["motif"], "argv": command["argv"], "log_path": str(log),
              "pid": None, "exit_observed": False, "exit_code": None,
              "stopped_on_failure": False, "deadline_seconds": seconds}
    records.append(record)
    started = time.monotonic()
    process = None
    try:
        with log.open("xb") as stream:
            kwargs = {"stdout": stream, "stderr": subprocess.STDOUT, "cwd": ROOT}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            process = subprocess.Popen(command["argv"], **kwargs)
            record["pid"] = process.pid
            try:
                record["exit_code"] = process.wait(timeout=seconds)
                record["exit_observed"] = True
            except subprocess.TimeoutExpired:
                record["stopped_on_failure"] = True
                process.kill()
                record["exit_code"] = process.wait(timeout=10)
                record["exit_observed"] = True
                raise ValueError("Owned crack render exceeded its deadline: " + command["motif"])
        require(type(record["exit_code"]) is int and record["exit_code"] == 0,
                "Owned crack render exited nonzero: " + command["motif"])
        require(log.stat().st_size <= 16 * 1024 * 1024, "Crack renderer log exceeds its bound")
        text = log.read_text(encoding="utf-8", errors="replace")
        require(not any(token.casefold() in text.casefold() for token in FATAL_TOKENS),
                "Crack renderer reported a shader/export failure")
    finally:
        if process is not None and process.poll() is None:
            record["stopped_on_failure"] = True
            process.kill()
            record["exit_code"] = process.wait(timeout=10)
            record["exit_observed"] = True
        record["elapsed_seconds"] = time.monotonic() - started
        if log.is_file():
            record["log_sha256"] = admitted.sha(log)


def prove(expected_head, run, attempt):
    exact_source(expected_head)
    require(all(re.fullmatch(r"[1-9][0-9]{0,19}", item) for item in (run, attempt)),
            "Invalid workflow run identity")
    config = load_workspace()
    producer = runtime(config)
    work = Path(config["work"])
    checked_path(producer["workspace"], work)
    proof = work / "material-forge/road-decals" / expected_head / (run + "-" + attempt)
    ancestor = proof
    while not ancestor.exists():
        ancestor = ancestor.parent
    checked_path(producer["workspace"], ancestor)
    proof.mkdir(parents=True, exist_ok=False)
    checked_path(producer["workspace"], proof)
    source_id = decals.source_identity()
    receipt = {"schema_version": 1, "issue": 364, "exact_sha": expected_head,
               "run": run, "attempt": attempt, "status": "ROAD_DECALS_SOURCE_RUNNING",
               "source_identity": source_id, "host_script_sha256": admitted.sha(Path(__file__)),
               "tool_input_sha256": producer["pins"],
               "primed_source_identity": producer["primed_source_identity"],
               "tool_archive_hashes_verified": True, "processes": [], "runs": [],
               "two_run_graph_and_map_bytes_equal": False, "native_process_exit_verified": False,
               "unreal_consumption_verified": False, "world_mutation": False,
               "human_visual_status": "PENDING_FINAL_M3", "performance_status": "DEFERRED_AFTER_M3",
               "performance_pass": False, "error": None}
    started = time.monotonic()
    try:
        for repeat in ("run-a", "run-b"):
            directory = proof / repeat
            authored = decals.author(producer["programs"]["material_maker"].parent, directory)
            commands = decals.render_commands(directory, producer["programs"]["godot"], producer["source"])
            require(authored["source_identity"] == source_id == commands["source_identity"]
                    and len(commands["commands"]) == 8, "Crack recipe changed or command coverage differs")
            for command in commands["commands"]:
                require(command["required_process_exit"] == 0, "Crack renderer requires an actual zero exit")
                remaining = int(TOTAL_SECONDS - (time.monotonic() - started))
                require(remaining > 0, "Complete crack source deadline exceeded")
                render_owned(command, min(PROCESS_SECONDS, remaining), receipt["processes"])
                receipt["processes"][-1]["repeat"] = repeat
            validated = decals.validate(directory)
            require(validated["status"] == "DECAL_MAP_CHECKS_PASS_UE_REVIEW_PENDING", "Crack map validation failed")
            receipt["runs"].append({"repeat": repeat, "directory": repeat,
                                     "manifest_sha256": admitted.sha(directory / "run-manifest.json")})
        compared = decals.compare(proof / "run-a", proof / "run-b")
        require(compared.get("deterministic") is True and compared.get("motif_count") == 8
                and compared.get("maps_per_motif") == 5 and compared.get("native_decode_verified") is True,
                "Two-run crack map/graph bytes differ")
        verify_runtime(producer)
        exact_source(expected_head)
        require(decals.source_identity() == source_id, "Crack source input bytes changed")
        require(len(receipt["processes"]) == 16 and all(
            row["exit_observed"] is True and type(row["exit_code"]) is int and row["exit_code"] == 0
            and row["stopped_on_failure"] is False for row in receipt["processes"]),
            "Crack source does not have sixteen observed successful owned processes")
        receipt.update(status="ROAD_DECALS_SOURCE_DETERMINISM_PASS", comparison=compared,
                       native_process_exit_verified=True, two_run_graph_and_map_bytes_equal=True)
    except Exception as exc:
        receipt.update(status="ROAD_DECALS_SOURCE_FAILED", error=str(exc))
        raise
    finally:
        receipt["elapsed_seconds"] = time.monotonic() - started
        write_once(proof / "source-proof.json", receipt)
    print(json.dumps({"status": receipt["status"], "exact_sha": expected_head,
                      "source_proof_sha256": admitted.sha(proof / "source-proof.json"),
                      "completed_render_count": len(receipt["processes"]),
                      "unreal_consumption_verified": False}, allow_nan=False))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--attempt", required=True)
    options = parser.parse_args()
    prove(options.expected_head, options.run, options.attempt)
