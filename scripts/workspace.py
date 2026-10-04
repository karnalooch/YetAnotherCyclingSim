"""Resolve the owner's persistent workspace and validate its launch contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def load_workspace(config_path: Path | None = None) -> dict:
    """Use one explicit local config; never infer a runner or chat checkout."""
    path = config_path or Path(
        os.environ.get(
            "YACS_WORKSPACE_CONFIG",
            Path(__file__).resolve().parents[2] / "workspace.json",
        )
    )
    path = path.resolve(strict=True)
    config = json.loads(path.read_text(encoding="utf-8-sig"))
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported workspace schema")
    root = path.parent
    for key in ("project", "data", "cache", "checkpoints", "work"):
        relative = Path(config[key])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Workspace path must remain below its root: {key}")
        resolved = (root / relative).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"Workspace path escapes through a link: {key}")
        config[key] = str(resolved)
    config["config"] = str(path)
    config["root"] = str(root)
    checkpoint = config.get("checkpoint", "")
    if checkpoint and (
        Path(checkpoint).name != checkpoint or checkpoint in (".", "..")
    ):
        raise ValueError("Checkpoint must be a directory name")
    return config


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def inspect_workspace(config: dict) -> dict:
    project = Path(config["project"])
    errors = []
    if Path(__file__).resolve().parents[1] != project:
        errors.append("Tool checkout differs from the configured project")
    package = config["map"]
    if not package.startswith("/Game/") or ".." in package.split("/"):
        raise ValueError("Invalid configured map package")
    paths = {
        "uproject": project / "YetAnotherCyclingSim.uproject",
        "map": project / "Content" / (package.removeprefix("/Game/") + ".umap"),
        "editor": Path(config["engine"]) / "Engine/Binaries/Win64/UnrealEditor.exe",
        "runtime_module": project
        / "Binaries/Win64/UnrealEditor-YetAnotherCyclingSim.dll",
        "editor_module": project
        / "Binaries/Win64/UnrealEditor-YetAnotherCyclingSimEditor.dll",
    }
    for name, path in paths.items():
        if not path.is_file():
            errors.append(f"Missing {name}: {path}")
        elif name == "map":
            with path.open("rb") as stream:
                if stream.read(42).startswith(
                    b"version https://git-lfs.github.com/spec/v1"
                ):
                    errors.append("Map is an unhydrated Git LFS pointer")
    checkpoint = (
        Path(config["checkpoints"]) / config["checkpoint"] / "reopen-verification.json"
    )
    if not checkpoint.is_file():
        errors.append("Checkpoint has no reopen verification")
    else:
        proof = json.loads(checkpoint.read_text(encoding="utf-8-sig"))
        if proof.get("status") != "PASS" or proof.get("map_package") != package:
            errors.append("Checkpoint reopen verification did not pass for this map")
        elif paths["map"].is_file() and digest(paths["map"]) != proof.get("map_sha256"):
            errors.append(
                "Map has changed since checkpoint verification; verify the new checkpoint"
            )
    return {
        "status": "FAIL" if errors else "PASS",
        "errors": errors,
        "paths": {key: str(value) for key, value in paths.items()},
        "map_package": package,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("doctor", "open"))
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    config = load_workspace(args.config)
    report = inspect_workspace(config)
    print(json.dumps(report, indent=2))
    if report["errors"]:
        return 1
    if args.command == "open":
        if os.name == "nt":
            query = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name = 'UnrealEditor.exe'\" | "
                    "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            if query.stdout.strip():
                print(
                    "An Unreal Editor is already running. Reuse or close it before opening another."
                )
                return 1
        env = os.environ.copy()
        env["YACS_WORKSPACE_CONFIG"] = config["config"]
        env["YACS_ASSET_ROOT"] = str(
            Path(config["data"]) / "world-data/sa-calobra-working-v1"
        )
        subprocess.Popen(
            [
                report["paths"]["editor"],
                report["paths"]["uproject"],
                config["map"],
                "-NoP4",
                "-NoSplash",
                f"-ZenDataPath={Path(config['cache']) / 'Zen'}",
            ],
            cwd=config["project"],
            env=env,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
