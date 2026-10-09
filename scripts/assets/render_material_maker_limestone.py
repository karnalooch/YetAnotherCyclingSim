"""Render and verify a limestone graph using the reviewed MM source and Godot."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from check_material_maker_limestone import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    export = args.output / "export"
    if export.exists():
        raise FileExistsError("Refusing an existing export directory")
    export.mkdir()
    prefix = export / "SaCalobra_PaleLimestone"
    log_path = args.output / "source-runner.log"
    command = [
        str(args.godot.resolve()),
        "--path",
        str(args.source.resolve()),
        "--script",
        str(Path(__file__).with_suffix(".gd").resolve()),
        "--",
        str(args.graph.resolve()),
        str(prefix.resolve()),
    ]
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            command,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    log = log_path.read_text(encoding="utf-8", errors="replace")
    if result.returncode or any(
        token in log
        for token in (
            "COMPUTE SHADER ERROR",
            "SCRIPT ERROR",
            "shader error:",
            "errors encountered when exporting",
            "Could not export",
        )
    ):
        raise RuntimeError("MM render failed; inspect " + str(log_path))
    native = json.loads(Path(str(prefix) + "_native-check.json").read_text())
    if not native["valid"] or len(native["images"]) != 4:
        raise RuntimeError("Native image decoding failed")
    check(args.output)
    receipt = {
        "source_commit": subprocess.check_output(
            ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
        ).strip(),
        "godot_sha256": hashlib.sha256(args.godot.read_bytes()).hexdigest(),
        "graph_sha256": hashlib.sha256(args.graph.read_bytes()).hexdigest(),
        "engine": native["engine"],
        "command": command,
        "exit_code": result.returncode,
        "upstream_diagnostics": [
            line for line in log.splitlines() if line.startswith(("ERROR:", "WARNING:"))
        ],
        "status": "MAP_CHECKS_PASS_UE_REVIEW_PENDING",
    }
    (args.output / "render-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
