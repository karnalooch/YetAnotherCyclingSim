#!/usr/bin/env python3
"""Validate the real Houdini/Gaea2Houdini recipe contract under hython."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    try:
        import hou
    except ImportError:
        print("[error] run with SideFX hython", file=sys.stderr)
        return 2

    p = argparse.ArgumentParser()
    p.add_argument("--hip", required=True, type=Path)
    p.add_argument("--hda", required=True, type=Path)
    p.add_argument("--preprocess-top", required=True)
    p.add_argument("--finalize-top", required=True)
    p.add_argument("--gaea-processor", required=True)
    p.add_argument("--gaea-output", required=True)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()

    if not a.hip.is_file() or not a.hda.is_file():
        print("[error] required HIP/HDA recipe asset is missing", file=sys.stderr)
        return 2

    try:
        hou.hda.installFile(str(a.hda.resolve()))
        hou.hipFile.load(str(a.hip.resolve()))
        required = {
            "preprocess_top": a.preprocess_top,
            "finalize_top": a.finalize_top,
            "gaea_processor": a.gaea_processor,
            "gaea_output": a.gaea_output,
        }
        nodes = {}
        for label, path in required.items():
            node = hou.node(path)
            if node is None:
                raise RuntimeError(f"missing required Houdini node: {path}")
            nodes[label] = node

        gaea_type = nodes["gaea_processor"].type().nameWithCategory()
        if "gaea" not in gaea_type.lower():
            raise RuntimeError(
                "configured GAEA_PROCESSOR is not a Gaea2Houdini node: "
                f"{gaea_type}"
            )

        hda_defs = hou.hda.definitionsInFile(str(a.hda.resolve()))
        if not hda_defs:
            raise RuntimeError("YACS heightfield HDA file contains no definitions")

        payload = {
            "schema_version": 1,
            "status": "PASS",
            "houdini_version": hou.applicationVersionString(),
            "hip": str(a.hip.resolve()),
            "hda": str(a.hda.resolve()),
            "required_nodes": {
                label: {
                    "path": node.path(),
                    "type": node.type().nameWithCategory(),
                }
                for label, node in nodes.items()
            },
            "hda_definitions": [definition.nodeTypeName() for definition in hda_defs],
        }
    except Exception as exc:
        print(f"[error] Houdini recipe validation failed: {exc}", file=sys.stderr)
        return 3

    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("[ok] Houdini/Gaea2Houdini recipe contract PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
