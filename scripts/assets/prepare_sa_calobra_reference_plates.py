"""Prepare source-only reference plates; never classify or mutate world inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.manage_local_workspace import load_workspace  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(config_path: Path, output_name: str) -> dict:
    config = load_workspace(config_path)
    work = Path(config["work"])
    output = (work / output_name).resolve()
    if output.parent != work or output.exists():
        raise ValueError("Use a new direct child of the canonical work directory")
    source = (
        Path(config["data"])
        / "world-data/sa-calobra-working-v1"
        / "mask-transition-review-v1a-2026-10-04"
    )
    manifest_path = source / "review-manifest.json"
    image_path = source / "orthophoto.png"
    if digest(manifest_path) != (
        "aed7f8324102750fd898224a3951e10507b27e6878a7c093def723b4c0a5bf14"
    ):
        raise ValueError("Reference manifest differs from the audited snapshot")
    if digest(image_path) != (
        "36eb65995ccd9ff7b8d169a208f97d2f3c6729c97053c5a5fcba4b3a6c62faa5"
    ):
        raise ValueError("Orthophoto differs from the pinned source")
    image = Image.open(image_path).convert("RGB")
    if image.size != (4033, 4033):
        raise ValueError("Unexpected reference grid")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["grid"]["transform"] != [0.5, 0, 483000, 0, -0.5, 4409516.5]:
        raise ValueError("Unexpected reference transform")
    edges = [round(i * 4033 / 4) for i in range(5)]
    records = []
    output.mkdir()
    for row in range(4):
        for col in range(4):
            x0, x1, y0, y1 = edges[col], edges[col + 1], edges[row], edges[row + 1]
            records.append(
                {
                    "id": f"O{row + 1}{col + 1}",
                    "pixel_bounds_xyxy": [x0, y0, x1, y1],
                    "bounds_epsg25831_wsen_m": [
                        483000 + x0 / 2,
                        4409516.5 - y1 / 2,
                        483000 + x1 / 2,
                        4409516.5 - y0 / 2,
                    ],
                    "pixel_count": (x1 - x0) * (y1 - y0),
                }
            )
    if sum(r["pixel_count"] for r in records) != 4033 * 4033:
        raise ValueError("Reference sectors do not cover the complete input")
    overview = image.resize((1008, 1008), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(overview)
    for r in records:
        x0, y0, x1, y1 = [round(v * 1008 / 4033) for v in r["pixel_bounds_xyxy"]]
        draw.rectangle((x0, y0, min(x1, 1007), min(y1, 1007)), outline="white")
        draw.rectangle((x0 + 2, y0 + 2, x0 + 34, y0 + 20), fill="black")
        draw.text((x0 + 5, y0 + 5), r["id"], fill="white")
    overview_plate = Image.new("RGB", (1008, 1040), "white")
    overview_plate.paste(overview, (0, 0))
    ImageDraw.Draw(overview_plate).text(
        (8, 1016),
        "Ortho 2024 / north-up / reference only | Obra derivada de PNOA CC-BY 4.0 scne.es",
        fill="black",
    )
    overview_plate.save(output / "overview.png")
    for row in range(4):
        panel = Image.new("RGB", (1040, 1160), "white")
        draw = ImageDraw.Draw(panel)
        draw.text(
            (12, 8), f"Sa Calobra / ortho 2024 / north-up / row {row + 1}", fill="black"
        )
        for col in range(4):
            r = records[row * 4 + col]
            x, y = (col % 2) * 520 + 10, (col // 2) * 550 + 35
            crop = image.crop(r["pixel_bounds_xyxy"]).resize(
                (500, 500), Image.Resampling.LANCZOS
            )
            panel.paste(crop, (x, y + 22))
            bounds = r["bounds_epsg25831_wsen_m"]
            draw.text(
                (x, y),
                f"{r['id']} | E {bounds[0]}..{bounds[2]} | ~504m square",
                fill="black",
            )
        draw.text(
            (10, 1140),
            "Obra derivada de PNOA CC-BY 4.0 scne.es | Visual reference, not classification",
            fill="black",
        )
        panel.save(output / f"reference-row-{row + 1}.png")
    report = {
        "status": "REFERENCE_ONLY_NOT_CLASSIFICATION",
        "source_manifest_sha256": digest(manifest_path),
        "source_image_sha256": digest(image_path),
        "source_image_relative_to_data": image_path.relative_to(
            Path(config["data"])
        ).as_posix(),
        "source_date": "2024; exact flight day not verified",
        "grid": manifest["grid"],
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "sectors": records,
        "limitations": [
            "Downsampled RGB appearance; no material class or calibrated confidence.",
            "No red overlay, candidate class raster or classification thresholds consumed.",
            "Ground beneath crowns, shadowed ground and fine grain remain unresolved.",
            "Grid coverage does not imply ground-level observation or surface accuracy.",
        ],
        "outputs": [
            {"path": p.name, "sha256": digest(p)} for p in sorted(output.glob("*.png"))
        ],
    }
    (output / "reference-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-config", required=True, type=Path)
    parser.add_argument("--output-name", required=True)
    args = parser.parse_args()
    result = prepare(args.workspace_config, args.output_name)
    print(
        json.dumps(
            {
                "status": result["status"],
                "sectors": len(result["sectors"]),
                "outputs": len(result["outputs"]),
            }
        )
    )
