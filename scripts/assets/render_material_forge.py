"""Render one Material Forge graph through a primed Material Maker source runtime.

The Material Maker source checkout is pinned and pre-imported with Godot so its
script-class/import cache exists before rendering. The render itself uses the
YACS GDScript adapter inside that source project, then CPU validation binds the
native Godot decode receipt to the exact output bytes.
"""

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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=2048)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    if args.timeout_seconds < 1:
        raise ValueError("--timeout-seconds must be positive")

    godot = args.godot.resolve()
    source = args.source.resolve()
    if not godot.is_file():
        raise FileNotFoundError(f"Godot executable missing: {godot}")
    if not (source / "project.godot").is_file():
        raise FileNotFoundError(f"Material Maker source project missing: {source}")

    class_cache = source / ".godot" / "global_script_class_cache.cfg"
    imported = source / ".godot" / "imported"
    if not class_cache.is_file():
        raise RuntimeError(
            "Material Maker source cache is not primed; "
            "run pinned Godot --import before rendering"
        )
    if not imported.is_dir():
        raise RuntimeError("Material Maker source imported resource cache is missing")

    forge = _load_forge()
    graph = args.variant / "Material.ptex"
    provenance = args.variant / "provenance.json"
    if not graph.is_file() or not provenance.is_file():
        raise FileNotFoundError("Variant is missing Material.ptex or provenance.json")

    export = args.variant / "export"
    if export.exists():
        raise FileExistsError("Refusing existing export directory")
    export.mkdir(parents=True)

    prefix = export / forge.EXPORT_PREFIX
    log_path = args.variant / "source-runner.log"
    command = [
        str(godot),
        "--path",
        str(source),
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

    log = result.stdout or ""
    log_path.write_text(log, encoding="utf-8")

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

    native_path = Path(str(prefix) + "_native-check.json")
    if not native_path.is_file():
        raise RuntimeError("Godot native decode receipt is missing")
    native = json.loads(native_path.read_text(encoding="utf-8"))
    if native.get("valid") is not True or len(native.get("images", {})) != 5:
        raise RuntimeError("Godot native image decoding did not admit all five maps")

    validation = forge.check_variant(args.variant, args.resolution)
    source_commit = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    receipt = {
        "producer": "Material Maker source runtime under pinned Godot",
        "source_commit": source_commit,
        "source_class_cache_sha256": _sha256(class_cache),
        "source_imported_file_count": len(
            [path for path in imported.iterdir() if path.is_file()]
        ),
        "godot_sha256": _sha256(godot),
        "graph_sha256": _sha256(graph),
        "engine": native["engine"],
        "command": command,
        "exit_code": result.returncode,
        "upstream_diagnostics": [
            line for line in log.splitlines() if line.startswith(("ERROR:", "WARNING:"))
        ],
        "validation_sha256": _sha256(args.variant / "validation.json"),
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
