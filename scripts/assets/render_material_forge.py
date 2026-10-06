"""Render one Material Forge graph with Material Maker 1.7 release CLI.

Material Maker is the producer. A separate pinned Godot executable is used only
to decode the five produced images and bind a native-read receipt to their exact
bytes before CPU validation.
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
DECODER_PROJECT = ROOT / "tools/material-forge/godot-decoder"


def _load_forge():
    spec = importlib.util.spec_from_file_location("yacs_material_forge", FORGE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Material Forge")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_logged(
    command: list[str],
    *,
    cwd: Path,
    log_path: Path,
    timeout_seconds: int,
    label: str,
) -> subprocess.CompletedProcess[str]:
    kwargs = {
        "cwd": str(cwd),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "timeout": timeout_seconds,
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
            partial + f"\nYACS_{label.upper()}_TIMEOUT seconds={timeout_seconds}\n",
            encoding="utf-8",
        )
        raise RuntimeError(
            f"Material Forge {label} timed out after {timeout_seconds}s; "
            f"inspect {log_path}"
        ) from exc
    log_path.write_text(result.stdout or "", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--material-maker",
        type=Path,
        required=True,
        help="Material Maker 1.7 release executable (console wrapper is allowed).",
    )
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--variant", type=Path, required=True)
    parser.add_argument("--resolution", type=int, default=2048)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    args = parser.parse_args()

    if args.timeout_seconds < 1:
        raise ValueError("--timeout-seconds must be positive")
    # Material Maker 1.7 parses --size but its CLI exporter still passes the
    # hard-coded 2048 image_size to export_material. Fail closed rather than
    # pretending another requested resolution was honored.
    if args.resolution != 2048:
        raise ValueError("Material Maker 1.7 CLI proof is pinned to 2048 output")

    material_maker = args.material_maker.resolve()
    godot = args.godot.resolve()
    if not material_maker.is_file():
        raise FileNotFoundError(f"Material Maker executable missing: {material_maker}")
    if not godot.is_file():
        raise FileNotFoundError(f"Godot executable missing: {godot}")
    if not (DECODER_PROJECT / "project.godot").is_file():
        raise FileNotFoundError("Material Forge Godot decoder project is missing")

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
    producer_log = args.variant / "material-maker-cli.log"
    decoder_log = args.variant / "godot-native-decode.log"

    producer_command = [
        str(material_maker),
        "--export-material",
        "-o",
        str(export.resolve()),
        "--target",
        "YACS/Textures",
        "--output-file",
        forge.EXPORT_PREFIX,
        str(graph.resolve()),
    ]
    producer = _run_logged(
        producer_command,
        cwd=material_maker.parent,
        log_path=producer_log,
        timeout_seconds=args.timeout_seconds,
        label="producer",
    )
    producer_text = producer.stdout or ""
    fatal_tokens = (
        "COMPUTE SHADER ERROR",
        "SCRIPT ERROR",
        "shader error:",
        "errors encountered when exporting",
        "Could not export",
        "Failed to load",
    )
    if producer.returncode or any(token in producer_text for token in fatal_tokens):
        raise RuntimeError(f"Material Maker release export failed; inspect {producer_log}")

    expected = [
        export / f"{forge.EXPORT_PREFIX}_{suffix}"
        for suffix in (
            "BaseColor.png",
            "Normal_DX.png",
            "ORM.png",
            "Height.exr",
            "DetailMasks.png",
        )
    ]
    missing = [str(path) for path in expected if not path.is_file()]
    if missing:
        raise RuntimeError(
            "Material Maker release export did not produce the five-map contract: "
            + ", ".join(missing)
        )

    decoder_command = [
        str(godot),
        "--headless",
        "--path",
        str(DECODER_PROJECT.resolve()),
        "--script",
        "res://verify_outputs.gd",
        "--",
        str(prefix.resolve()),
        str(args.resolution),
    ]
    decoder = _run_logged(
        decoder_command,
        cwd=DECODER_PROJECT,
        log_path=decoder_log,
        timeout_seconds=90,
        label="native_decode",
    )
    decoder_text = decoder.stdout or ""
    if decoder.returncode or "YACS_NATIVE_DECODE_PASS" not in decoder_text:
        raise RuntimeError(f"Godot native decode failed; inspect {decoder_log}")

    native_path = Path(str(prefix) + "_native-check.json")
    if not native_path.is_file():
        raise RuntimeError("Godot native decode receipt is missing")
    native = json.loads(native_path.read_text(encoding="utf-8"))
    if native.get("valid") is not True or len(native.get("images", {})) != 5:
        raise RuntimeError("Godot native image decoding did not admit all five maps")

    validation = forge.check_variant(args.variant, args.resolution)
    receipt = {
        "producer": "Material Maker 1.7 release CLI",
        "producer_sha256": hashlib.sha256(material_maker.read_bytes()).hexdigest(),
        "godot_role": "native_image_decoder_only",
        "godot_sha256": hashlib.sha256(godot.read_bytes()).hexdigest(),
        "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
        "native_engine": native["engine"],
        "producer_command": producer_command,
        "producer_exit_code": producer.returncode,
        "decoder_command": decoder_command,
        "decoder_exit_code": decoder.returncode,
        "upstream_diagnostics": [
            line
            for line in producer_text.splitlines()
            if line.startswith(("ERROR:", "WARNING:"))
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
