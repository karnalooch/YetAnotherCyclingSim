"""Measure and visualize Component_230 cliff baseline/candidate screenshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.assets.prepare_sa_calobra_cliff_erosion_handoff import label_components_8


THRESHOLDS = (0.05, 0.10, 0.15)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_metrics(path: Path) -> dict[str, object]:
    image = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
    luma = (
        image[..., 0] * 0.2126
        + image[..., 1] * 0.7152
        + image[..., 2] * 0.0722
    )
    thresholds = {}
    for threshold in THRESHOLDS:
        mask = luma < threshold
        labels = label_components_8(mask)
        counts = np.bincount(labels.ravel())
        regions = counts[1:] if len(counts) > 1 else np.empty(0, dtype=np.int64)
        thresholds[f"{threshold:.2f}"] = {
            "pixels": int(mask.sum()),
            "fraction": float(mask.mean()),
            "region_count": int((regions > 0).sum()),
            "largest_region_pixels": int(regions.max()) if len(regions) else 0,
            "regions_ge_50px": int((regions >= 50).sum()),
            "regions_ge_250px": int((regions >= 250).sum()),
        }
    return {
        "sha256": digest(path),
        "mean_luma": float(luma.mean()),
        "p01_luma": float(np.quantile(luma, 0.01)),
        "p05_luma": float(np.quantile(luma, 0.05)),
        "thresholds": thresholds,
    }


def comparison_board(paths: list[tuple[str, Path]], output: Path) -> None:
    opened = [(title, Image.open(path).convert("RGB")) for title, path in paths]
    width = max(image.width for _, image in opened)
    height = max(image.height for _, image in opened)
    title_height = 28
    canvas = Image.new("RGB", (width * 2, (height + title_height) * 2))
    draw = ImageDraw.Draw(canvas)
    for index, (title, image) in enumerate(opened):
        x = (index % 2) * width
        y = (index // 2) * (height + title_height)
        canvas.paste(image, (x, y + title_height))
        draw.text((x + 8, y + 7), title, fill=(255, 255, 255))
    canvas.save(output)


def dark_mask_board(baseline: Path, candidate: Path, output: Path) -> None:
    panels = []
    for title, path in (("baseline lighting-only < .05", baseline), ("candidate lighting-only < .05", candidate)):
        rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255.0
        luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
        mask = luma < 0.05
        picture = np.zeros((*mask.shape, 3), dtype=np.uint8)
        picture[mask] = [255, 255, 255]
        image = Image.fromarray(picture)
        panel = Image.new("RGB", (image.width, image.height + 28))
        panel.paste(image, (0, 28))
        ImageDraw.Draw(panel).text((8, 7), title, fill=(255, 255, 255))
        panels.append(panel)
    canvas = Image.new("RGB", (panels[0].width * 2, panels[0].height))
    canvas.paste(panels[0], (0, 0))
    canvas.paste(panels[1], (panels[0].width, 0))
    canvas.save(output)


def main(root: Path) -> dict[str, object]:
    names = {
        "baseline_lit": root / "01-baseline-lit.png",
        "baseline_lighting_only": root / "02-baseline-lighting-only.png",
        "candidate_lit": root / "03-candidate-lit.png",
        "candidate_lighting_only": root / "04-candidate-lighting-only.png",
    }
    for path in names.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    metrics = {name: image_metrics(path) for name, path in names.items()}
    baseline = metrics["baseline_lighting_only"]
    candidate = metrics["candidate_lighting_only"]
    deltas = {}
    for threshold in THRESHOLDS:
        key = f"{threshold:.2f}"
        b = baseline["thresholds"][key]
        c = candidate["thresholds"][key]
        deltas[key] = {
            "pixel_delta": c["pixels"] - b["pixels"],
            "pixel_ratio": (
                c["pixels"] / b["pixels"] if b["pixels"] else None
            ),
            "largest_region_delta": (
                c["largest_region_pixels"] - b["largest_region_pixels"]
            ),
            "largest_region_ratio": (
                c["largest_region_pixels"] / b["largest_region_pixels"]
                if b["largest_region_pixels"]
                else None
            ),
        }

    board = root / "component230-cliff-comparison.png"
    comparison_board(
        [
            ("BASELINE / Lit", names["baseline_lit"]),
            ("CANDIDATE / Lit", names["candidate_lit"]),
            ("BASELINE / Lighting Only", names["baseline_lighting_only"]),
            ("CANDIDATE / Lighting Only", names["candidate_lighting_only"]),
        ],
        board,
    )
    masks = root / "component230-dark-mask-005.png"
    dark_mask_board(
        names["baseline_lighting_only"],
        names["candidate_lighting_only"],
        masks,
    )
    report = {
        "schema_version": 1,
        "status": "COMPONENT230_CLIFF_METRICS_READY",
        "metrics": metrics,
        "lighting_only_deltas": deltas,
        "comparison_board": {
            "path": board.name,
            "sha256": digest(board),
        },
        "dark_mask_board": {
            "path": masks.name,
            "sha256": digest(masks),
        },
    }
    (root / "component230-cliff-metrics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["lighting_only_deltas"], sort_keys=True))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    main(args.root)
