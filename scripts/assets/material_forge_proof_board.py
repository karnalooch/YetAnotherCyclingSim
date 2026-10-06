"""Build compact visual review boards from one validated Material Forge run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


PREFIX = "YACS_Material"
CHANNELS = ("BaseColor", "Normal_DX", "ORM", "DetailMasks")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _entry_image(root: Path, entry: dict, channel: str) -> Image.Image:
    path = root / entry["directory"] / "export" / f"{PREFIX}_{channel}.png"
    return Image.open(path).convert("RGB")


def _label(entry: dict) -> str:
    return f"{entry['family']} / {entry['variant']}"


def _contact_sheet(root: Path, entries: list[dict], channel: str, output: Path) -> None:
    cell_w, cell_h = 420, 450
    image_size = 396
    canvas = Image.new("RGB", (cell_w * 3, cell_h * 3), "white")
    draw = ImageDraw.Draw(canvas)
    for index, entry in enumerate(entries):
        source = _entry_image(root, entry, channel)
        thumb = ImageOps.fit(source, (image_size, image_size))
        x = (index % 3) * cell_w + 12
        y = (index // 3) * cell_h + 12
        canvas.paste(thumb, (x, y))
        draw.text((x, y + image_size + 8), _label(entry), fill="black")
    canvas.save(output, quality=92)


def _tiling_sheet(root: Path, entries: list[dict], output: Path) -> None:
    cell_w, cell_h = 420, 450
    tile_size = 132
    canvas = Image.new("RGB", (cell_w * 3, cell_h * 3), "white")
    draw = ImageDraw.Draw(canvas)
    for index, entry in enumerate(entries):
        source = ImageOps.fit(_entry_image(root, entry, "BaseColor"), (tile_size, tile_size))
        x = (index % 3) * cell_w + 12
        y = (index // 3) * cell_h + 12
        for row in range(3):
            for column in range(3):
                canvas.paste(source, (x + column * tile_size, y + row * tile_size))
        draw.text((x, y + tile_size * 3 + 8), _label(entry), fill="black")
    canvas.save(output, quality=92)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((args.run / "run-manifest.json").read_text(encoding="utf-8"))
    entries = manifest["variants"]
    if len(entries) != 9:
        raise RuntimeError(f"Expected nine variants, found {len(entries)}")

    args.output.mkdir(parents=True, exist_ok=False)
    boards = []
    for channel in CHANNELS:
        path = args.output / f"{channel.lower()}-contact.jpg"
        _contact_sheet(args.run, entries, channel, path)
        boards.append(path)
    tiling = args.output / "basecolor-3x3-tiling.jpg"
    _tiling_sheet(args.run, entries, tiling)
    boards.append(tiling)

    receipt = {
        "status": "VISUAL_BOARDS_READY_OWNER_REVIEW_PENDING",
        "source_run": str(args.run),
        "variants": [_label(entry) for entry in entries],
        "boards": {
            path.name: {"sha256": _sha256(path), "size_bytes": path.stat().st_size}
            for path in boards
        },
    }
    (args.output / "visual-board-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
