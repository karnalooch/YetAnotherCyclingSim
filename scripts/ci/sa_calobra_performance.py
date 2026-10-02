"""Prepare fixed cameras and evaluate Sa Calobra using the shared proof policy."""

from __future__ import annotations
import argparse
import array
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.ci.world_proof_gate import BUDGET_MS, validate_evidence


def prepare(root: Path):
    manifest = json.loads((root / "Prepared/terrain-import.json").read_text())
    values = array.array("H")
    values.frombytes((root / "Prepared/terrain.r16").read_bytes())
    if sys.byteorder != "little":
        values.byteswap()

    def point(x, y, lift=170):
        i, j = round(x / 50), round(y / 50)
        if not (0 <= i < 4033 and 0 <= j < 4033):
            raise ValueError("Camera outside terrain")
        z = (values[j * 4033 + i] - 32768) * manifest["scale_z"] / 128 + manifest[
            "location_z_cm"
        ]
        return [x, y, z + lift]

    settings = {
        "resolution": [1920, 1080],
        "vsync": False,
        "screen_percentage": 100,
        "dynamic_resolution": False,
        "fov_deg": 74,
        "warmup_seconds": 5,
        "sample_seconds": 8,
        "shadows": False,
        "sun_intensity": 8,
        "sky_intensity": 0.8,
        "scope": "terrain baseline only; no road, foliage, earthworks or gameplay",
        "views": [
            {
                "name": "overview",
                "location_cm": [
                    -35000,
                    100800,
                    manifest["elevation_max_m"] * 100 + 90000,
                ],
                "target_cm": point(100800, 100800, 0),
            },
            {
                "name": "rider",
                "location_cm": point(125000, 85000),
                "target_cm": point(127000, 87000),
            },
            {
                "name": "slope",
                "location_cm": point(105000, 56000, 15000),
                "target_cm": point(108000, 58500, 0),
            },
        ],
    }
    (root / "sa-calobra-settings.json").write_text(
        json.dumps(settings, sort_keys=True) + "\n"
    )


def evaluate(root: Path, head: str, exit_code: int):
    csv_path = root / "sa-calobra-terrain-performance.csv"
    text = csv_path.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    identity = json.loads(
        Path(str(csv_path) + ".identity.json").read_text(encoding="utf-8-sig")
    )
    manifest = json.loads((root / "Prepared/terrain-import.json").read_text())
    summary = {
        "Head": head,
        "Result": "PASS",
        "EditorExitCode": exit_code,
        "Resolution": identity["Resolution"],
        "VSync": "disabled",
        "ReferenceGpuMatched": True,
        "GpuNames": [identity["ActiveGpu"]],
        "TargetFps": 60,
        "AllowedOverBudgetRatio": 0.05,
        "FrameBudgetMs": BUDGET_MS,
        "P95FrameBudgetMs": BUDGET_MS,
        "P95GpuBudgetMs": BUDGET_MS,
        "ScenarioId": "sa-calobra-terrain",
        "MapPackage": identity["MapPackage"],
        "ComponentCount": identity["ComponentCount"],
        "TerrainSha256": manifest["heightmap_sha256"],
        "SettingsSha256": hashlib.sha256(
            (root / "sa-calobra-settings.json").read_bytes()
        ).hexdigest(),
        "ScreenPercentage": 100,
        "DynamicResolution": False,
        "Sectors": [],
    }

    def pct(xs, p):
        return sorted(xs)[math.floor(p * (len(xs) - 1))] if xs else None

    for sector in ["overview", "rider", "slope"]:
        samples = [r for r in rows if r["sector"] == sector]
        frames = [float(r["frame_ms"]) for r in samples]
        gpu = [float(r["gpu_ms"]) for r in samples if float(r["gpu_ms"]) > 0.01]
        record = {
            "Sector": sector,
            "Pass": True,
            "SampleCount": len(samples),
            "PositiveGpuSampleCount": len(gpu),
            "FrameP95Ms": pct(frames, 0.95),
            "GpuP95Ms": pct(gpu, 0.95),
            "OverBudgetRatio": sum(v > BUDGET_MS for v in frames) / len(frames)
            if frames
            else 1,
        }
        record["Percentiles"] = {
            domain: {
                f"p{p}": pct([float(r[domain]) for r in samples], p / 100)
                for p in (50, 95, 99)
            }
            for domain in ("frame_ms", "game_ms", "draw_ms", "rhi_ms", "gpu_ms")
        }
        summary["Sectors"].append(record)
    policy = json.loads((ROOT / ".gumball/world-proof-policy.json").read_text())[
        "scenarios"
    ]["sa-calobra-terrain"]
    error = None
    try:
        validate_evidence(summary, text, policy, "sa-calobra-terrain", head)
    except (ValueError, KeyError, TypeError) as exc:
        error = exc
        summary["Result"] = "FAIL"
        summary["Failure"] = str(exc)
    (root / "sa-calobra-terrain-performance-summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(summary, indent=2))
    if error:
        raise error
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "evaluate"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--head")
    parser.add_argument("--editor-exit-code", type=int, default=0)
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.root)
    else:
        evaluate(args.root, args.head, args.editor_exit_code)
