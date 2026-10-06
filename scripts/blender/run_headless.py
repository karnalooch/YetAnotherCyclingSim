#!/usr/bin/env python3
"""Run pinned Blender jobs headlessly from the persistent YACS workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOOLCHAIN_PATH = Path(__file__).with_name("toolchain.json")
_VERSION_PATTERN = re.compile(
    r"^Blender\s+(?P<version>\d+\.\d+\.\d+)(?:\s|$)", re.MULTILINE
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_toolchain(path: Path = DEFAULT_TOOLCHAIN_PATH) -> dict:
    contract = json.loads(path.read_text(encoding="utf-8-sig"))
    if contract.get("schema_version") != 1:
        raise ValueError("Unsupported Blender toolchain schema")
    version = str(contract.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Blender toolchain version must be an exact x.y.z version")
    relative = Path(str(contract.get("workspace_executable", "")))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Blender executable must be a workspace-relative path")
    python_exit_code = contract.get("python_exit_code")
    if not isinstance(python_exit_code, int) or not 1 <= python_exit_code <= 255:
        raise ValueError("python_exit_code must be in the range 1..255")
    return contract


def resolve_workspace_config(
    explicit: Path | None = None,
    *,
    repo_root: Path = REPO_ROOT,
) -> Path:
    if explicit is not None:
        candidate = explicit
    elif os.environ.get("YACS_WORKSPACE_CONFIG"):
        candidate = Path(os.environ["YACS_WORKSPACE_CONFIG"])
    else:
        candidate = repo_root.parent / "workspace.json"
    return candidate.resolve(strict=True)


def load_workspace_root(config_path: Path) -> Path:
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported workspace schema")
    return config_path.parent.resolve(strict=True)


def resolve_workspace_file(
    workspace_root: Path,
    value: str | Path,
    *,
    label: str,
    must_exist: bool = True,
) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else workspace_root / raw
    candidate = candidate.resolve(strict=must_exist)
    if not candidate.is_relative_to(workspace_root):
        raise ValueError(f"{label} must remain below the YACS workspace root")
    if must_exist and not candidate.is_file():
        raise FileNotFoundError(f"{label} is not a file: {candidate}")
    return candidate


def resolve_blender_executable(
    workspace_root: Path,
    contract: dict,
    override: Path | None = None,
) -> Path:
    value = override if override is not None else contract["workspace_executable"]
    return resolve_workspace_file(
        workspace_root,
        value,
        label="Blender executable",
    )


def resolve_repo_script(script: Path, *, repo_root: Path = REPO_ROOT) -> Path:
    candidate = script if script.is_absolute() else repo_root / script
    candidate = candidate.resolve(strict=True)
    if not candidate.is_relative_to(repo_root.resolve(strict=True)):
        raise ValueError("Blender job script must be repository-owned")
    if not candidate.is_file() or candidate.suffix.lower() != ".py":
        raise ValueError(f"Blender job script must be a Python file: {candidate}")
    return candidate


def resolve_blend_input(workspace_root: Path, blend: Path | None) -> Path | None:
    if blend is None:
        return None
    candidate = resolve_workspace_file(
        workspace_root,
        blend,
        label="Blend input",
    )
    if candidate.suffix.lower() != ".blend":
        raise ValueError("Blend input must use the .blend extension")
    return candidate


def parse_blender_version(output: str) -> str:
    match = _VERSION_PATTERN.search(output)
    if not match:
        raise ValueError("Could not parse Blender version output")
    return match.group("version")


def probe_blender_version(executable: Path) -> str:
    result = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(
            f"Blender version probe failed with exit code {result.returncode}: "
            f"{output.strip()}"
        )
    return parse_blender_version(output)


def require_exact_version(executable: Path, expected: str) -> str:
    actual = probe_blender_version(executable)
    if actual != expected:
        raise RuntimeError(
            f"Blender version mismatch: expected {expected}, got {actual}"
        )
    return actual


def build_command(
    executable: Path,
    script: Path,
    *,
    python_exit_code: int,
    job_args: Sequence[str],
    blend: Path | None = None,
) -> list[str]:
    command = [
        str(executable),
        "--background",
        "--factory-startup",
        "--disable-autoexec",
    ]
    if blend is not None:
        command.append(str(blend))
    command.extend(
        [
            "--python-exit-code",
            str(python_exit_code),
            "--python",
            str(script),
            "--",
        ]
    )
    command.extend(str(value) for value in job_args)
    return command


def current_git_head(repo_root: Path = REPO_ROOT) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = (result.stdout or "").strip()
    return value if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def display_workspace_path(path: Path, workspace_root: Path) -> str:
    try:
        return path.relative_to(workspace_root).as_posix()
    except ValueError:
        return str(path)


def execute_job(
    *,
    contract: dict,
    workspace_root: Path,
    executable: Path,
    script: Path,
    receipt: Path,
    job_args: Sequence[str],
    blend: Path | None,
    repo_root: Path = REPO_ROOT,
) -> int:
    expected_version = str(contract["version"])
    actual_version = require_exact_version(executable, expected_version)
    command = build_command(
        executable,
        script,
        python_exit_code=int(contract["python_exit_code"]),
        job_args=job_args,
        blend=blend,
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    log_path = receipt.with_suffix(".log")
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            command,
            cwd=repo_root,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    duration = round(time.monotonic() - started, 3)
    payload = {
        "schema_version": 1,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "git_head": current_git_head(repo_root),
        "expected_blender_version": expected_version,
        "actual_blender_version": actual_version,
        "blender_executable": display_workspace_path(executable, workspace_root),
        "script": script.relative_to(repo_root).as_posix(),
        "script_sha256": sha256_file(script),
        "blend_input": (
            display_workspace_path(blend, workspace_root) if blend is not None else None
        ),
        "blend_sha256": sha256_file(blend) if blend is not None else None,
        "python_exit_code": int(contract["python_exit_code"]),
        "process_exit_code": result.returncode,
        "duration_seconds": duration,
        "log": display_workspace_path(log_path, workspace_root),
    }
    write_json_atomic(receipt, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return result.returncode


def add_common_tool_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-config", type=Path)
    parser.add_argument(
        "--blender-exe",
        type=Path,
        help="Explicit executable below the workspace root; exact version is still enforced.",
    )
    parser.add_argument(
        "--toolchain",
        type=Path,
        default=DEFAULT_TOOLCHAIN_PATH,
        help=argparse.SUPPRESS,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe", help="Validate the pinned Blender toolchain")
    add_common_tool_args(probe)

    smoke = subparsers.add_parser("smoke", help="Run the repository-owned bpy smoke job")
    add_common_tool_args(smoke)
    smoke.add_argument(
        "--output-dir",
        type=Path,
        default=Path("work/blender/headless-smoke"),
        help="Workspace-relative directory for proof outputs.",
    )

    run = subparsers.add_parser("run", help="Run one repository-owned Blender Python job")
    add_common_tool_args(run)
    run.add_argument("--script", required=True, type=Path)
    run.add_argument("--blend", type=Path)
    run.add_argument("--receipt", required=True, type=Path)
    run.add_argument("job_args", nargs=argparse.REMAINDER)

    args = parser.parse_args()
    contract = load_toolchain(args.toolchain)
    workspace_config = resolve_workspace_config(args.workspace_config)
    workspace_root = load_workspace_root(workspace_config)
    executable = resolve_blender_executable(
        workspace_root,
        contract,
        args.blender_exe,
    )

    if args.command == "probe":
        actual = require_exact_version(executable, str(contract["version"]))
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "PASS",
                    "expected_version": contract["version"],
                    "actual_version": actual,
                    "executable": display_workspace_path(executable, workspace_root),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "smoke":
        output_dir = resolve_workspace_file(
            workspace_root,
            args.output_dir,
            label="Smoke output directory",
            must_exist=False,
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        child_report = output_dir / "blender-report.json"
        receipt = output_dir / "host-receipt.json"
        script = resolve_repo_script(
            Path("scripts/blender/smoke_job.py"),
            repo_root=REPO_ROOT,
        )
        return execute_job(
            contract=contract,
            workspace_root=workspace_root,
            executable=executable,
            script=script,
            receipt=receipt,
            job_args=[
                "--report",
                str(child_report),
                "--expected-version",
                str(contract["version"]),
            ],
            blend=None,
        )

    script = resolve_repo_script(args.script, repo_root=REPO_ROOT)
    blend = resolve_blend_input(workspace_root, args.blend)
    receipt = resolve_workspace_file(
        workspace_root,
        args.receipt,
        label="Receipt",
        must_exist=False,
    )
    job_args = list(args.job_args)
    if job_args and job_args[0] == "--":
        job_args = job_args[1:]
    return execute_job(
        contract=contract,
        workspace_root=workspace_root,
        executable=executable,
        script=script,
        receipt=receipt,
        job_args=job_args,
        blend=blend,
    )


if __name__ == "__main__":
    raise SystemExit(main())
