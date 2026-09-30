#!/usr/bin/env python3
"""Cook/render one configured Houdini node under hython."""

from __future__ import annotations

import argparse
import json
import sys
import time
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
    p.add_argument("--node", required=True)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()

    started = time.time()
    try:
        hou.hda.installFile(str(a.hda.resolve()))
        hou.hipFile.load(str(a.hip.resolve()))
        node = hou.node(a.node)
        if node is None:
            raise RuntimeError(f"Houdini node does not exist: {a.node}")

        if hasattr(node, "render"):
            node.render(verbose=True)
        elif hasattr(node, "cook"):
            node.cook(force=True)
        else:
            raise RuntimeError(f"node is not cookable/renderable: {a.node}")

        errors = tuple(node.errors()) if hasattr(node, "errors") else ()
        if errors:
            raise RuntimeError("node reported errors: " + " | ".join(errors))
    except Exception as exc:
        print(f"[error] Houdini node cook failed: {exc}", file=sys.stderr)
        return 3

    payload = {
        "schema_version": 1,
        "status": "PASS",
        "houdini_version": hou.applicationVersionString(),
        "hip": str(a.hip.resolve()),
        "hda": str(a.hda.resolve()),
        "node_path": a.node,
        "duration_seconds": round(time.time() - started, 3),
    }
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] cooked Houdini node {a.node}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
