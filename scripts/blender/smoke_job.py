#!/usr/bin/env python3
"""Minimal deterministic Blender smoke job for the YACS headless lane."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    tail = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--expected-version", required=True)
    return parser.parse_args(tail)


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    report = args.report.resolve()
    try:
        expected = tuple(int(part) for part in args.expected_version.split("."))
        actual = tuple(int(part) for part in bpy.app.version[:3])
        if actual != expected:
            raise RuntimeError(
                f"bpy version mismatch: expected {expected}, got {actual}"
            )
        if not bpy.app.background:
            raise RuntimeError("Blender is not running in background mode")

        vertices = (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        )
        faces = ((0, 1, 2),)
        mesh = bpy.data.meshes.new("YACS_Headless_Smoke_Mesh")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new("YACS_Headless_Smoke_Object", mesh)
        bpy.context.scene.collection.objects.link(obj)

        if len(mesh.vertices) != 3 or len(mesh.polygons) != 1:
            raise RuntimeError("Unexpected smoke mesh topology")

        geometry_payload = json.dumps(
            {"vertices": vertices, "faces": faces},
            separators=(",", ":"),
        ).encode("utf-8")
        payload = {
            "schema_version": 1,
            "status": "PASS",
            "background": bool(bpy.app.background),
            "blender_version": ".".join(str(value) for value in actual),
            "mesh": {
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "geometry_sha256": hashlib.sha256(geometry_payload).hexdigest(),
            },
        }
        write_report(report, payload)
        print("[ok] YACS Blender headless smoke PASS")
        return 0
    except Exception as exc:
        write_report(
            report,
            {
                "schema_version": 1,
                "status": "FAIL",
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
