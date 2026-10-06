"""Render one Material Forge graph through reviewed Material Maker source + Godot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORGE_PATH = ROOT / "scripts/assets/material_forge.py"


def _load_forge():
    spec = importlib.util.spec_from_file_location("yacs_material_forge", FORGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Material Forge")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=2048)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Maximum render process duration; cold source checkouts may need a larger value.",
    )
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        raise ValueError("--timeout-seconds must be positive")

    forge = _load_forge()
    graph = args.variant / "Material.ptex"
    provenance = args.variant / "provenance.json"
    if not graph.exists() or not provenance.exists():
        raise FileNotFoundError("Variant is missing Material.ptex or provenance.json")

    export = args.variant / "export"
    if export.exists():
        raise FileExistsError("Refusing existing export directory")
    export.mkdir(parents=True)

    prefix = export / forge.EXPORT_PREFIX
    log_path = args.variant / "source-runner.log"
    command = [
        str(args.godot.resolve()),
        "--path",
        str(args.source.resolve()),
        "--script",
        str(Path(__file__).with_suffix(".gd").resolve()),
        "--",
        str(graph.resolve()),
        str(prefix.resolve()),
        str(args.resolution),
    ]
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "timeout": args.timeout_seconds,
    }
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(command, **kwargs)
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        log_path.write_text(
            partial
            + f"\nYACS_RENDER_TIMEOUT seconds={args.timeout_seconds}\n",
            encoding="utf-8",
        )
        raise RuntimeError(
            f"Material Forge render timed out after {args.timeout_seconds}s; "
            f"inspect {log_path}"
        ) from exc
    log_path.write_text(result.stdout or "", encoding="utf-8")
    log = result.stdout or ""

    fatal_tokens = (
        "COMPUTE SHADER ERROR",
        "SCRIPT ERROR",
        "shader error:",
        "errors encountered when exporting",
        "Could not export",
        "YACS_RENDER_FAILED",
    )
    if result.returncode or any(token in log for token in fatal_tokens):
        raise RuntimeError(f"Material Forge render failed; inspect {log_path}")

    native = json.loads(Path(str(prefix) + "_native-check.json").read_text())
    if not native.get("valid") or len(native.get("images", {})) != 5:
        raise RuntimeError("Godot native image decoding failed")

    validation = forge.check_variant(args.variant, args.resolution)
    receipt = {
        "source_commit": subprocess.check_output(
            ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
        ).strip(),
        "godot_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
        "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
        "engine": native["engine"],
        "command": command,
        "exit_code": result.returncode,
        "upstream_diagnostics": [
            line for line in log.splitlines() if line.startswith(("ERROR:", "WARNING:"))
        ],
        "validation_sha256": hashlib.sha256(
            (args.variant / "validation.json").read_bytes()
        ).hexdigest(),
        "status": validation["status"],
    }
    (args.variant / "render-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )

    provenance_data = json.loads(provenance.read_text(encoding="utf-8"))
    provenance_data["status"] = validation["status"]
    provenance_data["render_receipt"] = "render-receipt.json"
    provenance.write_text(
        json.dumps(provenance_data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
