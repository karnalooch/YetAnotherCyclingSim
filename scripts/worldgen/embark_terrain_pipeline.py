#!/usr/bin/env python3
"""Orchestrate the Passo Giau Embark-style terrain authoring pipeline.

The script intentionally does not recreate unpublished Embark internals. It wires
YACS-owned data to documented Houdini PDG, Gaea2Houdini, Houdini heightfield HDA,
and Unreal proof boundaries and fails closed when a required recipe/tool is absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "worldgen/embark/passo_giau_terrain_pipeline.json"


class PipelineError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight")
    preflight.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    preflight.add_argument("--report", type=Path, required=True)

    run = sub.add_parser("run")
    run.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    run.add_argument("--expected-branch", required=True)
    run.add_argument("--expected-head", required=True)
    run.add_argument("--artifact-root", type=Path)

    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PipelineError(f"missing JSON file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PipelineError(f"JSON root must be an object: {path}")
    return data


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_executable(env_key: str, fallback_names: Sequence[str]) -> Path | None:
    explicit = os.environ.get(env_key, "").strip()
    if explicit:
        path = Path(explicit).expanduser()
        if path.is_file():
            return path.resolve()
        return None

    for name in fallback_names:
        resolved = shutil.which(name)
        if resolved:
            return Path(resolved).resolve()
    return None


def run_capture(command: Sequence[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise PipelineError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return (completed.stdout or completed.stderr).strip()


def tool_identity(name: str, path: Path, version_command: Sequence[str]) -> dict[str, Any]:
    version = run_capture(version_command)
    return {
        "name": name,
        "path": str(path),
        "sha256": sha256_file(path),
        "version_output": version,
    }


def preflight(config_path: Path, report_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = load_json(config_path)
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    if config.get("pipeline_id") != "passo-giau-embark-landscape-v1":
        raise PipelineError("unexpected pipeline_id")

    recipes = config["recipes"]
    hip = repo_path(recipes["houdini_hip"])
    gaea_recipe = repo_path(recipes["gaea_terrain"])
    heightfield_hda = repo_path(recipes["houdini_heightfield_hda"])
    recipe_contract = repo_path(recipes["recipe_contract"])

    for label, path in (
        ("Houdini HIP recipe", hip),
        ("YACS heightfield HDA", heightfield_hda),
        ("Gaea terrain recipe", gaea_recipe),
        ("recipe contract", recipe_contract),
    ):
        record(label, path.is_file(), str(path))

    hython = resolve_executable(config["tools"]["houdini"]["executable_env"], ("hython", "hython.exe"))
    gaea_swarm = resolve_executable(config["tools"]["gaea"]["swarm_env"], ("Gaea.Swarm.exe",))
    gaea_exe = resolve_executable(config["tools"]["gaea"]["ui_env"], ("Gaea.exe",))
    pwsh = resolve_executable("YACS_PWSH", ("pwsh", "pwsh.exe"))

    record("Houdini hython", hython is not None, str(hython) if hython else "not found")
    record("Gaea Build Swarm", gaea_swarm is not None, str(gaea_swarm) if gaea_swarm else "not found")
    record("Gaea UI executable", gaea_exe is not None, str(gaea_exe) if gaea_exe else "not found")
    record("PowerShell 7", pwsh is not None, str(pwsh) if pwsh else "not found")

    tools: dict[str, Any] = {}
    if hython is not None:
        try:
            tools["houdini"] = tool_identity(
                "Houdini",
                hython,
                (
                    str(hython),
                    "-c",
                    "import hou; print(hou.applicationVersionString())",
                ),
            )
            record("Houdini license/version probe", True, tools["houdini"]["version_output"])
        except PipelineError as exc:
            record("Houdini license/version probe", False, str(exc))

    if gaea_exe is not None:
        try:
            tools["gaea"] = tool_identity(
                "Gaea",
                gaea_exe,
                (str(gaea_exe), "-Version"),
            )
            record("Gaea version probe", True, tools["gaea"]["version_output"])
        except PipelineError as exc:
            record("Gaea version probe", False, str(exc))

    recipe_validation_report = report_path.resolve().parent / "houdini-recipe-validation.json"
    if hython is not None and hip.is_file() and heightfield_hda.is_file():
        try:
            validation_output = run_capture(
                (
                    str(hython),
                    str(repo_path("scripts/houdini/validate_embark_recipe.py")),
                    "--hip",
                    str(hip),
                    "--hda",
                    str(heightfield_hda),
                    "--preprocess-top",
                    recipes["houdini_preprocess_top"],
                    "--finalize-top",
                    recipes["houdini_finalize_top"],
                    "--gaea-processor",
                    recipes["houdini_gaea_processor_node"],
                    "--gaea-output",
                    recipes["houdini_gaea_bridge_node"],
                    "--report",
                    str(recipe_validation_report),
                )
            )
            record("Houdini/Gaea2Houdini recipe contract", True, validation_output)
        except PipelineError as exc:
            record("Houdini/Gaea2Houdini recipe contract", False, str(exc))

    failed = [check for check in checks if check["status"] != "PASS"]
    payload = {
        "schema_version": 1,
        "pipeline_id": config["pipeline_id"],
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "status": "PASS" if not failed else "FAIL",
        "checks": checks,
        "tools": tools,
        "recipe_hashes": {
            "houdini_hip": sha256_file(hip) if hip.is_file() else None,
            "houdini_heightfield_hda": sha256_file(heightfield_hda) if heightfield_hda.is_file() else None,
            "gaea_terrain": sha256_file(gaea_recipe) if gaea_recipe.is_file() else None,
        },
    }
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if failed:
        names = ", ".join(check["name"] for check in failed)
        raise PipelineError(f"Embark terrain preflight failed: {names}")

    payload["_resolved"] = {
        "hython": str(hython),
        "gaea_swarm": str(gaea_swarm),
        "gaea_exe": str(gaea_exe),
        "pwsh": str(pwsh),
    }
    return payload


def ensure_output(path: Path, stage: str) -> None:
    if not path.is_file():
        raise PipelineError(f"{stage} did not produce required output: {path}")


def run_stage(
    manifest: dict[str, Any],
    name: str,
    command: Sequence[str],
    *,
    expected_outputs: Sequence[Path] = (),
    env: dict[str, str] | None = None,
) -> None:
    started = time.time()
    completed = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        env=env,
        check=False,
        text=True,
    )
    entry: dict[str, Any] = {
        "name": name,
        "command": list(command),
        "exit_code": completed.returncode,
        "duration_seconds": round(time.time() - started, 3),
    }
    manifest["stages"].append(entry)
    if completed.returncode != 0:
        raise PipelineError(f"stage {name} failed with exit code {completed.returncode}")

    outputs: dict[str, str] = {}
    for path in expected_outputs:
        ensure_output(path, name)
        outputs[str(path)] = sha256_file(path)
    entry["output_sha256"] = outputs


def expand_gaea_variables(config: dict[str, Any]) -> dict[str, str]:
    outputs = config["outputs"]
    values: dict[str, str] = {}
    for key, raw in config["gaea"]["variables"].items():
        value = str(raw)
        for output_key, output_value in outputs.items():
            value = value.replace(f"${{{output_key}}}", str(repo_path(output_value)))
        values[key] = value
    return values


def run_pipeline(
    config_path: Path,
    expected_branch: str,
    expected_head: str,
    artifact_root_override: Path | None,
) -> Path:
    config_path = config_path.resolve()
    config = load_json(config_path)
    outputs = config["outputs"]
    run_manifest_path = repo_path(outputs["run_manifest"])
    dcc_handoff_path = repo_path(outputs["dcc_handoff_manifest"])
    preflight_report = run_manifest_path.parent / "toolchain-preflight.json"
    preflight_payload = preflight(config_path, preflight_report)
    resolved = preflight_payload.pop("_resolved")

    hython = Path(resolved["hython"])
    pwsh = Path(resolved["pwsh"])

    hip = repo_path(config["recipes"]["houdini_hip"])
    heightfield_hda = repo_path(config["recipes"]["houdini_heightfield_hda"])
    gaea_recipe = repo_path(config["recipes"]["gaea_terrain"])
    pdg_output = repo_path(outputs["pdg_heightfield"])
    gaea_output = repo_path(outputs["gaea_heightfield"])
    houdini_output = repo_path(outputs["houdini_heightfield"])
    gaea_vars = repo_path(outputs["gaea_vars"])
    prepared_root = repo_path(outputs["prepared_unreal_root"])
    artifact_root = (
        artifact_root_override.resolve()
        if artifact_root_override
        else repo_path(outputs["artifact_root"])
    )

    for path in (
        pdg_output.parent,
        gaea_output.parent,
        houdini_output.parent,
        gaea_vars.parent,
        prepared_root,
        artifact_root,
    ):
        path.mkdir(parents=True, exist_ok=True)

    gaea_vars.write_text(
        json.dumps(expand_gaea_variables(config), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "pipeline_id": config["pipeline_id"],
        "config_sha256": sha256_file(config_path),
        "expected_branch": expected_branch,
        "expected_head": expected_head,
        "toolchain_preflight": preflight_payload,
        "stages": [],
    }

    python = sys.executable
    source = config["source"]
    run_stage(
        manifest,
        "download_mase",
        (python, str(repo_path(source["download_mase"]))),
        expected_outputs=(repo_path(source["mase_report"]),),
    )
    run_stage(
        manifest,
        "download_veneto",
        (python, str(repo_path(source["download_veneto"]))),
        expected_outputs=(repo_path(source["veneto_report"]),),
    )
    run_stage(
        manifest,
        "prepare_baseline_diagnostics",
        (python, str(repo_path(source["prepare_baseline_diagnostics"]))),
    )

    houdini_env = os.environ.copy()
    houdini_env.update(
        {
            "YACS_EMBARK_PIPELINE_CONFIG": str(config_path),
            "YACS_EMBARK_PDG_OUTPUT": str(pdg_output),
            "YACS_EMBARK_GAEA_RECIPE": str(gaea_recipe),
            "YACS_EMBARK_GAEA_VARS": str(gaea_vars),
            "YACS_EMBARK_GAEA_OUTPUT": str(gaea_output),
            "YACS_EMBARK_HOUDINI_OUTPUT": str(houdini_output),
            "YACS_EMBARK_HEIGHTFIELD_HDA": str(heightfield_hda),
        }
    )

    cook_script = repo_path("scripts/houdini/cook_top_network.py")
    pdg_report = pdg_output.parent / "houdini-pdg-preprocess.json"
    run_stage(
        manifest,
        "houdini_pdg_preprocess",
        (
            str(hython),
            str(cook_script),
            "--hip",
            str(hip),
            "--top",
            config["recipes"]["houdini_preprocess_top"],
            "--report",
            str(pdg_report),
        ),
        expected_outputs=(pdg_output, pdg_report),
        env=houdini_env,
    )

    gaea_bridge_report = gaea_output.parent / "houdini-gaea2houdini-bridge.json"
    run_stage(
        manifest,
        "gaea2houdini_shape",
        (
            str(hython),
            str(repo_path("scripts/houdini/cook_houdini_node.py")),
            "--hip",
            str(hip),
            "--hda",
            str(heightfield_hda),
            "--node",
            config["recipes"]["houdini_gaea_bridge_node"],
            "--report",
            str(gaea_bridge_report),
        ),
        expected_outputs=(gaea_output, gaea_bridge_report),
        env=houdini_env,
    )

    finalize_report = houdini_output.parent / "houdini-finalize.json"
    run_stage(
        manifest,
        "houdini_heightfield_finalize",
        (
            str(hython),
            str(cook_script),
            "--hip",
            str(hip),
            "--top",
            config["recipes"]["houdini_finalize_top"],
            "--report",
            str(finalize_report),
        ),
        expected_outputs=(houdini_output, finalize_report),
        env=houdini_env,
    )

    dcc_handoff = {
        **manifest,
        "handoff_status": "PASS",
        "handoff_output_sha256": sha256_file(houdini_output),
    }
    dcc_handoff_path.parent.mkdir(parents=True, exist_ok=True)
    dcc_handoff_path.write_text(
        json.dumps(dcc_handoff, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    finalizer = repo_path("scripts/assets/finalize_passo_giau_embark_heightfield.py")
    terrain_report = prepared_root / "terrain-report.json"
    terrain_r16 = prepared_root / "passo_giau_embark_ue_landscape_4033.r16"
    run_stage(
        manifest,
        "finalize_unreal_heightfield",
        (
            python,
            str(finalizer),
            "--source",
            str(houdini_output),
            "--dcc-handoff-manifest",
            str(dcc_handoff_path),
            "--output-dir",
            str(prepared_root),
        ),
        expected_outputs=(terrain_report, terrain_r16),
    )

    run_stage(
        manifest,
        "download_road",
        (python, str(repo_path(source["download_road"]))),
    )
    run_stage(
        manifest,
        "prepare_road",
        (python, str(repo_path(source["prepare_road"]))),
        expected_outputs=(repo_path(source["road_report"]),),
    )

    wrapper = repo_path(config["tools"]["unreal"]["proof_wrapper"])
    run_stage(
        manifest,
        "unreal_author_and_rider_proof",
        (
            str(pwsh),
            "-NoProfile",
            "-File",
            str(wrapper),
            "-ExpectedBranch",
            expected_branch,
            "-ExpectedHead",
            expected_head,
            "-ArtifactRoot",
            str(artifact_root),
            "-IncludeRoad",
            "-PreparedTerrainRoot",
            str(prepared_root),
            "-SkipTerrainPreparation",
        ),
        expected_outputs=(artifact_root / "passo_giau_landscape_spike_proof.json",),
    )

    manifest["source_report_sha256"] = {
        "mase": sha256_file(repo_path(source["mase_report"])),
        "veneto": sha256_file(repo_path(source["veneto_report"])),
        "road": sha256_file(repo_path(source["road_report"])),
    }
    manifest["final_status"] = "PASS"
    run_manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run_manifest_path


def main() -> int:
    args = parse_args()
    try:
        if args.command == "preflight":
            payload = preflight(args.config.resolve(), args.report.resolve())
            payload.pop("_resolved", None)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        manifest = run_pipeline(
            args.config,
            args.expected_branch,
            args.expected_head,
            args.artifact_root,
        )
        print(f"[ok] Embark terrain pipeline manifest: {manifest}")
        return 0
    except (OSError, ValueError, KeyError, PipelineError, json.JSONDecodeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
