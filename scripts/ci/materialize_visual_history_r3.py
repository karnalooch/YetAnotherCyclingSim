from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = os.environ["YACS_REPO"]
TOKEN = os.environ["GH_TOKEN"]
ROOT = Path("docs/visual-history/stage-3g/R3-valley-high-alpine")
OUT = ROOT / "captures"
OUT.mkdir(parents=True, exist_ok=True)

ARTIFACTS = {
    "before": 10925330926,  # R2 / CI #398
    "now": 10926354963,     # R3 / CI #417
}

CAPTURES = [
    ("01-valley-1200m", "01_valley_1200m_triptych.jpg", "Valley", 1200, "01_meadow_valley_1200m_AFTER.png"),
    ("02-forest-4900m", "02_forest_4900m_triptych.jpg", "Forest", 4900, "02_forest_sector_4900m_AFTER.png"),
    ("03-high-alpine-8000m", "03_high_alpine_8000m_triptych.jpg", "High Alpine", 8000, "03_high_valley_mountains_8000m_AFTER.png"),
]

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)

def download_artifact(artifact_id: int) -> zipfile.ZipFile:
    url = f"https://api.github.com/repos/{REPO}/actions/artifacts/{artifact_id}/zip"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "yacs-visual-history",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as response:
        return zipfile.ZipFile(io.BytesIO(response.read()))

def find_image(zf: zipfile.ZipFile, name: str) -> Image.Image:
    matches = [entry for entry in zf.namelist() if entry.endswith("/" + name) or entry == name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {name} in artifact, found {matches!r}")
    with zf.open(matches[0]) as fp:
        return Image.open(io.BytesIO(fp.read())).convert("RGB")

def fit_cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    sw, sh = img.size
    tw, th = size
    scale = max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

before_zip = download_artifact(ARTIFACTS["before"])
now_zip = download_artifact(ARTIFACTS["now"])

manifest_path = ROOT / "manifest.json"
hashes_path = ROOT / "capture-hashes.json"
summary_path = ROOT / "summary.md"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
hashes_doc = json.loads(hashes_path.read_text(encoding="utf-8"))

panel_w, image_h, hud_h, header_h = 960, 540, 178, 96
width, height = panel_w * 3, header_h + image_h + hud_h
bg = (17, 20, 24)
header_bg = (11, 13, 16)
hud_bg = (18, 21, 26)
border = (72, 78, 88)
txt = (238, 241, 245)
muted = (170, 177, 188)
good = (137, 223, 157)
pending = (241, 196, 103)

by_id = {c["capture_id"]: c for c in manifest["captures"]}
hash_by_id = {c["capture_id"]: c for c in hashes_doc["captures"]}

for capture_id, filename, label, distance, source_name in CAPTURES:
    canvas = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, width, header_h], fill=header_bg)
    draw.text((34, 17), "YACS VISUAL HISTORY", font=font(30, True), fill=txt)
    draw.text((34, 55), "VH-3G-R3-001  •  Stage 3G / R3  •  Valley + High-Alpine PCG", font=font(20), fill=muted)
    draw.text((width - 34, 28), f"{label.upper()}  •  {distance} m", font=font(24, True), fill=txt, anchor="ra")

    before = fit_cover(find_image(before_zip, source_name), (panel_w, image_h))
    now = fit_cover(find_image(now_zip, source_name), (panel_w, image_h))
    after = Image.new("RGB", (panel_w, image_h), (25, 29, 35))
    ad = ImageDraw.Draw(after)
    ad.text((panel_w // 2, image_h // 2 - 40), "AFTER", font=font(44, True), fill=txt, anchor="mm")
    ad.text((panel_w // 2, image_h // 2 + 15), "PENDING", font=font(34, True), fill=pending, anchor="mm")
    ad.text((panel_w // 2, image_h // 2 + 62), "Awaiting merged-main proof", font=font(22), fill=muted, anchor="mm")

    for i, panel in enumerate((before, now, after)):
        x = i * panel_w
        canvas.paste(panel, (x, header_h))
        draw.rectangle([x, header_h + image_h, x + panel_w - 1, height - 1], fill=hud_bg)
        if i:
            draw.line([x, header_h, x, height], fill=border, width=3)

    panel_lines = [
        [
            ("BEFORE  •  VISUAL_ACCEPTED", font(25, True), good),
            ("R2 merged baseline  •  main  •  fd77094", font(18), txt),
            ("Stage 3G / R2  •  CI #398 / 36299298530", font(17), muted),
            (f"{label}  •  {distance} m  •  1920×1080", font(17), muted),
            ("Automation PASS  •  Fresh Load PASS", font(17), muted),
            ("Map Check 0/0  •  Visual Capture PASS", font(17), muted),
        ],
        [
            ("NOW  •  VISUAL_ACCEPTED", font(25, True), good),
            ("feat/stage3g-pcg-biomes-r3  •  58c89674", font(18), txt),
            ("Stage 3G / R3  •  CI #417 / 36305204327", font(17), muted),
            (f"{label}  •  {distance} m  •  1920×1080", font(17), muted),
            ("Automation PASS  •  Fresh Load PASS", font(17), muted),
            ("Map Check 0/0  •  Visual Capture PASS", font(17), muted),
        ],
        [
            ("AFTER  •  PENDING", font(25, True), pending),
            ("main  •  commit pending", font(18), txt),
            ("Stage 3G / R3  •  merged-main proof pending", font(17), muted),
            (f"{label}  •  {distance} m  •  1920×1080", font(17), muted),
            ("Automation pending  •  Fresh Load pending", font(17), muted),
            ("Map Check pending  •  Visual Capture pending", font(17), muted),
        ],
    ]
    for i, lines in enumerate(panel_lines):
        y = header_h + image_h + 14
        for line, face, color in lines:
            draw.text((i * panel_w + 24, y), line, font=face, fill=color)
            y += 26

    path = OUT / filename
    canvas.save(path, "JPEG", quality=88, optimize=True, progressive=False, subsampling=0)
    digest = sha256(path)

    item = by_id[capture_id]
    item["triptych_image"] = f"captures/{filename}"
    item["triptych_sha256"] = digest
    item["triptych_storage_status"] = "DURABLE_REPO"
    item["triptych_size_bytes"] = path.stat().st_size
    item["triptych_resolution"] = f"{width}x{height}"
    item.pop("triptych_expected_path", None)

    hash_item = hash_by_id[capture_id]
    hash_item["triptych_image"] = f"captures/{filename}"
    hash_item["triptych_sha256"] = digest

manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
hashes_path.write_text(json.dumps(hashes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

summary = summary_path.read_text(encoding="utf-8")
summary = summary.replace(
    "`PENDING — awaiting visual acceptance`",
    "`PENDING — awaiting merged-main proof`",
)
summary = summary.replace(
    "No current NOW capture may be promoted to AFTER until the committed-SHA proof and human visual review both pass.",
    "The committed-SHA proof and human visual review have passed for NOW. AFTER remains pending until the accepted R3 change is merged and the merged-main capture/provenance is recorded.",
)
if "## Durable triptych evidence" not in summary:
    summary += """
## Durable triptych evidence

The accepted pre-merge R3 evidence pack is now persisted in-repository at:

- `captures/01_valley_1200m_triptych.jpg`
- `captures/02_forest_4900m_triptych.jpg`
- `captures/03_high_alpine_8000m_triptych.jpg`

Each triptych is generated from the genuine R2 CI #398 baseline artifact and the accepted R3 CI #417 artifact. The AFTER panel intentionally remains PENDING until merged-main proof.
"""
summary_path.write_text(summary, encoding="utf-8")

for path in sorted(OUT.glob("*.jpg")):
    print(path, sha256(path), path.stat().st_size)
