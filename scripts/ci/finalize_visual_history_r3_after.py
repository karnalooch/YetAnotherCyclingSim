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

ARTIFACTS = {
    "before": 10925330926,  # R2 / CI #398
    "now": 10926354963,     # R3 accepted pre-merge / CI #417
    "after": 10927694053,   # merged main / CI #421
}

MERGE_SHA = "02ff23f0a24228432ae9c34eb65aa4cb3694ae1d"

CAPTURES = [
    {
        "id": "01-valley-1200m",
        "filename": "01_valley_1200m_triptych.jpg",
        "source": "01_meadow_valley_1200m_AFTER.png",
        "label": "Valley",
        "distance": 1200,
        "before_sha": "de391fb72074f2ad74d1ce8f7e2f7a2520f1581107ce40fa2f1c36503fae7abb",
        "now_sha": "169ff6fff360994cb0fe3eba078f611f0c380d7c9b416ef1782c304927280258",
        "after_sha": "5cefb738c8e051d4603fe6cbcc13d7400ed80b9f95732897edf1a949456d90bd",
    },
    {
        "id": "02-forest-4900m",
        "filename": "02_forest_4900m_triptych.jpg",
        "source": "02_forest_sector_4900m_AFTER.png",
        "label": "Forest",
        "distance": 4900,
        "before_sha": "c1b1b6a3109eca4e4e9d355e9bdf4165b83f452fd9560ee2e4fef48165d33725",
        "now_sha": "56233de89d8629524b9d85cc7b2ecd367a43887d8dfc42f2921018c44d326a2c",
        "after_sha": "867144551a0cbdf5f0ac6a2847f04b43a6bf476e877c7a5aac56f3a4a1b96ba8",
    },
    {
        "id": "03-high-alpine-8000m",
        "filename": "03_high_alpine_8000m_triptych.jpg",
        "source": "03_high_valley_mountains_8000m_AFTER.png",
        "label": "High Alpine",
        "distance": 8000,
        "before_sha": "d1491bbfd506d345897b220eec83f53167090e57e35f14ce38f9a961ef64cea3",
        "now_sha": "189e3f63fabbbaa85b96d9cadc918e19af1dc8f69c80d9cba6fba4638126b317",
        "after_sha": "7dc5dfd184092dab5852c45fea255b67523e10774c12597acd6aeeebb0a60d76",
    },
]

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def font(size: int, bold: bool = False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)

def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def download_artifact(artifact_id: int) -> zipfile.ZipFile:
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/actions/artifacts/{artifact_id}/zip",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "yacs-visual-history-finalizer",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return zipfile.ZipFile(io.BytesIO(response.read()))

def load_verified(zf: zipfile.ZipFile, filename: str, expected_sha: str) -> Image.Image:
    matches = [n for n in zf.namelist() if n == filename or n.endswith("/" + filename)]
    if len(matches) != 1:
        raise RuntimeError(f"{filename}: expected exactly one artifact entry, found {matches!r}")
    data = zf.read(matches[0])
    actual = sha_bytes(data)
    if actual != expected_sha:
        raise RuntimeError(f"{filename}: SHA mismatch: {actual} != {expected_sha}")
    return Image.open(io.BytesIO(data)).convert("RGB")

def fit(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    sw, sh = img.size
    scale = max(tw / sw, th / sh)
    resized = img.resize((round(sw * scale), round(sh * scale)), Image.Resampling.LANCZOS)
    x = (resized.width - tw) // 2
    y = (resized.height - th) // 2
    return resized.crop((x, y, x + tw, y + th))

OUT.mkdir(parents=True, exist_ok=True)
zips = {name: download_artifact(aid) for name, aid in ARTIFACTS.items()}

manifest_path = ROOT / "manifest.json"
hashes_path = ROOT / "capture-hashes.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
hashes_doc = json.loads(hashes_path.read_text(encoding="utf-8"))
manifest_caps = {x["capture_id"]: x for x in manifest["captures"]}
hash_caps = {x["capture_id"]: x for x in hashes_doc["captures"]}

panel_w, image_h, header_h, hud_h = 640, 360, 60, 156
W, H = panel_w * 3, header_h + image_h + hud_h
BG = (16, 19, 23)
HEADER = (10, 12, 15)
HUD = (18, 21, 26)
TEXT = (239, 242, 246)
MUTED = (174, 181, 191)
GOOD = (137, 223, 157)
BORDER = (73, 80, 91)

for cap in CAPTURES:
    before = fit(load_verified(zips["before"], cap["source"], cap["before_sha"]), (panel_w, image_h))
    now = fit(load_verified(zips["now"], cap["source"], cap["now_sha"]), (panel_w, image_h))
    after = fit(load_verified(zips["after"], cap["source"], cap["after_sha"]), (panel_w, image_h))

    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, W, header_h), fill=HEADER)
    draw.text((22, 10), "YACS VISUAL HISTORY", font=font(22, True), fill=TEXT)
    draw.text((22, 36), f"VH-3G-R3-001 · Stage 3G / R3 · {cap['label']} · {cap['distance']} m", font=font(13), fill=MUTED)

    for i, image in enumerate((before, now, after)):
        x = i * panel_w
        canvas.paste(image, (x, header_h))
        draw.rectangle((x, header_h + image_h, x + panel_w - 1, H - 1), fill=HUD)
        if i:
            draw.line((x, header_h, x, H), fill=BORDER, width=2)

    blocks = [
        [
            ("BEFORE · VISUAL_ACCEPTED", 18, True, GOOD),
            ("R2 merged baseline · fd77094", 13, False, TEXT),
            ("CI #398 / 36299298530", 12, False, MUTED),
            ("Automation PASS · Fresh Load PASS", 12, False, MUTED),
            ("Map Check 0/0 · Visual Capture PASS", 12, False, MUTED),
        ],
        [
            ("NOW · VISUAL_ACCEPTED", 18, True, GOOD),
            ("R3 pre-merge · 58c89674", 13, False, TEXT),
            ("CI #417 / 36305204327", 12, False, MUTED),
            ("Automation PASS · Fresh Load PASS", 12, False, MUTED),
            ("Map Check 0/0 · Visual Capture PASS", 12, False, MUTED),
        ],
        [
            ("AFTER · MERGED / VISUAL_ACCEPTED", 17, True, GOOD),
            ("main · 02ff23f0", 13, False, TEXT),
            ("CI #421 / 36308910299", 12, False, MUTED),
            ("Automation PASS · Fresh Load PASS", 12, False, MUTED),
            ("Map Check 0/0 · Visual Capture PASS", 12, False, MUTED),
        ],
    ]
    for i, lines in enumerate(blocks):
        y = header_h + image_h + 10
        for text_value, size, bold, color in lines:
            draw.text((i * panel_w + 16, y), text_value, font=font(size, bold), fill=color)
            y += 27

    out = OUT / cap["filename"]
    canvas.save(out, "JPEG", quality=90, optimize=True, progressive=False, subsampling=0)
    trip_sha = sha_file(out)

    item = manifest_caps[cap["id"]]
    item["after"] = {
        "commit_sha": MERGE_SHA,
        "image": f"CI artifact: FinalProof/Visual/{cap['source']}",
        "sha256": cap["after_sha"],
        "status": "VISUAL_ACCEPTED",
    }
    item["triptych_image"] = f"captures/{cap['filename']}"
    item["triptych_sha256"] = trip_sha
    item["triptych_storage_status"] = "DURABLY_STORED"
    item["triptych_resolution"] = f"{W}x{H}"
    item["triptych_size_bytes"] = out.stat().st_size
    item.pop("triptych_expected_path", None)

    h = hash_caps[cap["id"]]
    h["after_sha256"] = cap["after_sha"]
    h["triptych_sha256"] = trip_sha
    h["triptych_image"] = f"captures/{cap['filename']}"

hashes_doc["accepted_after"] = {
    "commit_sha": MERGE_SHA,
    "workflow_run_id": 36308910299,
    "workflow_run_number": 421,
    "proof_artifact_name": "stage3g-full-validation-36308910299-1",
}
hashes_doc["note"] = (
    "BEFORE is the merged R2 baseline; NOW is the accepted R3 pre-merge revision; "
    "AFTER is the exact merged implementation SHA on main proven by CI #421. "
    "The repository-retained triptychs contain all three genuine captures."
)
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
hashes_path.write_text(json.dumps(hashes_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

for cap in CAPTURES:
    p = OUT / cap["filename"]
    print(f"{p}: sha256={sha_file(p)} bytes={p.stat().st_size} resolution={W}x{H}")
