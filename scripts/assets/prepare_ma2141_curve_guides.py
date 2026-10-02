"""Prepare paired pavement guides for native Unreal spline authoring."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.assets.prepare_ma2141_diagnostic import SOURCE_SHA, sha256
from scripts.assets.prepare_ma2141_road_preview import (
    PROFILE,
    build_trial,
    read_profile,
)


def prepare(prepared, output, exact_sha):
    if output.exists():
        raise FileExistsError("Preserve previous curve guide evidence")
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact SHA required")
    manifest = json.loads((prepared / "terrain-import.json").read_text())
    _, edges = read_profile()
    vertices, _, _ = build_trial(edges, lambda x, y: 0.0, manifest["origin_epsg_m"])
    # Two-and-a-half-metre control spacing removes GIS corners from the dense render
    # control polygon. The two curves share source-chainage input keys.
    guides = [
        {
            "station_m": i * 0.5,
            "edges_xy_m": [vertices[i * 25][:2], vertices[i * 25 + 24][:2]],
        }
        for i in range(0, 601, 5)
    ]
    packet = {
        "schema_version": 1,
        "exact_sha": exact_sha,
        "source_sha256": SOURCE_SHA,
        "profile_sha256": sha256(PROFILE),
        "origin_epsg_m": manifest["origin_epsg_m"],
        "guide_step_m": 2.5,
        "sample_step_m": 0.0625,
        "guides": guides,
    }
    output.write_text(json.dumps(packet, allow_nan=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    prepare(args.prepared_terrain, args.output, args.exact_sha)
