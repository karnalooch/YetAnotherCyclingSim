#!/usr/bin/env python3
"""Cook one Houdini TOP network under hython and emit a small proof report."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hip", required=True, type=Path)
    parser.add_argument("--top", required=True)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    try:
        import hou
    except ImportError:
        print("[error] this script must run under SideFX hython", file=sys.stderr)
        return 2

    args = parse_args()
    hip = args.hip.resolve()
    report = args.report.resolve()
    if not hip.is_file():
        print(f"[error] Houdini HIP does not exist: {hip}", file=sys.stderr)
        return 2

    started = time.time()
    try:
        hou.hipFile.load(str(hip))
        target = hou.node(args.top)
        if target is None:
            raise RuntimeError(f"TOP path does not exist: {args.top}")

        cook_target = target
        if not hasattr(cook_target, "cookWorkItems"):
            if not hasattr(target, "displayNode"):
                raise RuntimeError(
                    f"node at {args.top} is not a TOP node/network and has no display node"
                )
            cook_target = target.displayNode()
        if cook_target is None or not hasattr(cook_target, "cookWorkItems"):
            raise RuntimeError(f"TOP network has no cookable output: {args.top}")

        cook_target.cookWorkItems(block=True)
    except Exception as exc:
        print(f"[error] Houdini TOP cook failed: {exc}", file=sys.stderr)
        return 3

    payload = {
        "schema_version": 1,
        "status": "PASS",
        "hip": str(hip),
        "top_path": args.top,
        "houdini_version": hou.applicationVersionString(),
        "duration_seconds": round(time.time() - started, 3),
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[ok] cooked {args.top} with Houdini {payload['houdini_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
