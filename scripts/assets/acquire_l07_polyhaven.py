#!/usr/bin/env python3
"""Acquire YACS Lesson07 selected Poly Haven CC0 surface maps, without touching terrain.

Trusted input is the checked-in owner-approved selection manifest, not URL
patterns. The vendor's official /files API supplies download URLs and MD5s.
All downloads go to a separate immutable D:-work directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

API = "https://api.polyhaven.com"
USER_AGENT = "YACS-L07-Pegasus-PBR/1.0 (Poly Haven CC0, https://polyhaven.com/)"
MAX_FILE_BYTES = 280_000_000
MAX_TOTAL_BYTES = 2_100_000_000
MAX_ASSETS = 8
CHUNK = 1 << 20
SLUG_RE = re.compile(r"^[a-z0-9_]{3,80}$")
MD5_RE = re.compile(r"^[0-9a-fA-F]{32}$")
SOURCE_HOST = "dl.polyhaven.org"
MAPS_HOUDINI = (
    ("diffuse", ("jpg", "png")),
    ("rough", ("png", "jpg")),
    ("nor_gl", ("png",)),
    ("disp", ("exr", "png")),
)
MAPS_UE = (
    ("diffuse", ("jpg", "png")),
    ("rough", ("png", "jpg")),
    ("nor_dx", ("png",)),
    ("ao", ("png", "jpg")),
    ("disp", ("png",)),
)


def digest(path: Path, name: str) -> str:
    h = hashlib.new(name)
    with path.open("rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def validate_source_url(url: str, slug: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != SOURCE_HOST:
        raise ValueError(f"Untrusted Poly Haven file host: {parsed.netloc}")
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise ValueError("Unexpected URL credentials/port/query/fragment")
    if not parsed.path.startswith("/file/ph-assets/Textures/"):
        raise ValueError("File URL outside official Poly Haven texture tree")
    filename = parsed.path.rsplit("/", 1)[-1]
    if not filename.startswith(slug + "_") or not re.fullmatch(r"[a-z0-9_]+\.(jpg|png|exr)", filename):
        raise ValueError(f"Untrusted texture filename: {filename}")
    if "%" in parsed.path or ".." in parsed.path:
        raise ValueError("Encoded/parent file path is forbidden")
    return filename


def safe_json_get(path: str, timeout: int = 35) -> dict:
    url = f"{API}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected API HTTP {response.status}")
        data = response.read(2_500_001)
    if len(data) > 2_500_000:
        raise ValueError("API response too large")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("API response is not a JSON object")
    return result


def require_manifest(manifest_path: Path) -> dict:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("license") != "CC0":
        raise ValueError("Wrong selection manifest/license")
    assets = data.get("assets")
    if not isinstance(assets, list) or len(assets) != MAX_ASSETS:
        raise ValueError("Exactly eight owner-approved assets required")
    slugs = [a["slug"] for a in assets]
    if not all(SLUG_RE.fullmatch(s) for s in slugs) or len(slugs) != len(set(slugs)):
        raise ValueError("Unsafe or duplicate Poly Haven slug")
    by_slug = set(slugs)
    houdini = data.get("houdini", {})
    ue = data.get("unreal_array", [])
    if set(houdini) != {"rock", "grass", "sand", "cliff", "scree"} or len(ue) != 5:
        raise ValueError("Selection must identify five Houdini roles and five Unreal slots")
    if any(s not in by_slug for s in list(houdini.values()) + ue):
        raise ValueError("Selected role references missing asset")
    if data.get("unreal_texture_size") != 2048 or data.get("houdini_texture_size") != 4096:
        raise ValueError("Unexpected material texture resolutions")
    return data


def choose_file(tree: dict, slug: str, kind: str, resolution: str, formats: tuple[str, ...]) -> dict:
    vendor_key = {"diffuse": "Diffuse", "rough": "Rough", "disp": "Displacement", "ao": "AO"}.get(kind, kind)
    types = tree.get(vendor_key, tree.get(kind, {}))
    if not isinstance(types, dict):
        raise ValueError(f"Missing {kind} tree for {slug}")
    variants = types.get(resolution, {})
    if not isinstance(variants, dict):
        raise ValueError(f"Missing {resolution} {kind} for {slug}")
    for ext in formats:
        item = variants.get(ext)
        if isinstance(item, dict) and all(k in item for k in ("url", "size", "md5")):
            name = validate_source_url(item["url"], slug)
            size = item["size"]
            md5 = item["md5"]
            if not isinstance(size, int) or not 0 < size <= MAX_FILE_BYTES:
                raise ValueError(f"Unsupported vendor file size: {slug}/{kind}/{resolution}")
            if not isinstance(md5, str) or not MD5_RE.fullmatch(md5):
                raise ValueError(f"Invalid vendor MD5: {slug}/{kind}/{resolution}")
            if not name.endswith("." + ext):
                raise ValueError(f"Incorrect extension for {slug}/{kind}/{resolution}")
            return {"slug": slug, "map": kind, "resolution": resolution,
                    "format": ext, "name": name, "url": item["url"],
                    "size": size, "provider_md5": md5.lower()}
    raise ValueError(f"No suitable source file for {slug}/{kind}/{resolution}: root={list(tree)} map_keys={list(types)} formats={list(variants)}")


def build_plan(selection: dict, reader=safe_json_get) -> dict:
    houdini_slugs = set(selection["houdini"].values())
    ue_slugs = set(selection["unreal_array"])
    planned = []
    infos = []
    for a in selection["assets"]:
        slug = a["slug"]
        info = reader(f"info/{slug}")
        files = reader(f"files/{slug}")
        if info.get("type") != 1 or info.get("name") != a["name"]:
            raise ValueError(f"Publisher type/title mismatch for {slug}: {info.get('name')}")
        infos.append({"slug": slug, "name": a["name"],
                      "publisher_page": f"https://polyhaven.com/a/{slug}",
                      "provider_files_hash": info.get("files_hash"),
                      "publisher_api_files_sha256": hashlib.sha256(
                          json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
                      ).hexdigest()})
        if slug in houdini_slugs:
            planned.extend(choose_file(files, slug, kind, "4k", formats)
                           for kind, formats in MAPS_HOUDINI)
        if slug in ue_slugs:
            planned.extend(choose_file(files, slug, kind, "2k", formats)
                           for kind, formats in MAPS_UE)
    names = [(p["slug"], p["name"]) for p in planned]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate staged filename")
    total = sum(x["size"] for x in planned)
    if total > MAX_TOTAL_BYTES:
        raise ValueError(f"Download plan exceeds bounded budget: {total} bytes")
    return {"status": "VENDOR_PLAN_VERIFIED_NO_DOWNLOADS", "schema_version": 1,
            "license": "CC0", "license_url": "https://polyhaven.com/license",
            "api": API, "selection": selection, "publisher_assets": infos,
            "file_count": len(planned), "planned_bytes": total,
            "files": planned}


def verify_existing(destination: Path, spec: dict) -> dict | None:
    if not destination.exists():
        return None
    if not destination.is_file() or destination.stat().st_size != spec["size"] or digest(destination, "md5") != spec["provider_md5"]:
        raise ValueError(f"Existing file differs from publisher checksum; refuse overwrite: {destination}")
    return {"relative_path": f"{spec['slug']}/{spec['resolution']}/{spec['name']}",
            "size": spec["size"], "provider_md5": spec["provider_md5"],
            "sha256": digest(destination, "sha256"), "source_url": spec["url"],
            "status": "REUSED_VERIFIED"}


def download_one(root: Path, spec: dict) -> dict:
    destination = root / spec["slug"] / spec["resolution"] / spec["name"]
    existing = verify_existing(destination, spec)
    if existing:
        return existing
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + ".partial")
    if temp.exists():
        temp.unlink()  # only remove incomplete scratch output, never an accepted file
    for attempt in range(3):
        h_md5 = hashlib.md5()
        h_sha = hashlib.sha256()
        read_size = 0
        req = urllib.request.Request(spec["url"], headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=100) as response, temp.open("xb") as output:
                if response.status != 200:
                    raise IOError(f"Source download returned HTTP {response.status}")
                if urlsplit(response.url).hostname != SOURCE_HOST or not response.url.startswith("https://"):
                    raise ValueError("Source download redirected outside official host")
                while True:
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    read_size += len(chunk)
                    if read_size > spec["size"]:
                        raise IOError("Source payload exceeds stated byte count")
                    h_md5.update(chunk)
                    h_sha.update(chunk)
                    output.write(chunk)
            if read_size != spec["size"] or h_md5.hexdigest() != spec["provider_md5"]:
                raise IOError(f"Publisher checksum mismatch: {spec['name']}")
            os.replace(temp, destination)
            return {"relative_path": f"{spec['slug']}/{spec['resolution']}/{spec['name']}",
                    "size": read_size, "provider_md5": spec["provider_md5"],
                    "sha256": h_sha.hexdigest(), "source_url": spec["url"],
                    "status": "DOWNLOADED_VERIFIED"}
        except (OSError, urllib.error.URLError, ValueError):
            temp.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Unreachable")


def acquire(plan: dict, root: Path) -> dict:
    # Intentionally D:-only on Windows, never C: or the canonical D:\yacs\project checkout.
    if os.name == "nt":
        rp = str(root.resolve()).lower().replace("/", "\\")
        if not rp.startswith("d:\\yacs\\work\\"):
            raise ValueError("Acquisition root must stay in D:\\yacs\\work")
    root.mkdir(parents=True, exist_ok=True)
    completed = []
    for index, spec in enumerate(plan["files"], 1):
        result = download_one(root, spec)
        completed.append(result)
        print(f"[{index}/{len(plan['files'])}] {result['status']}: {result['relative_path']}", flush=True)
    report = {"status": "PH_CC0_SOURCE_BYTES_VERIFIED_NOT_INSTALLED", "schema_version": 1,
              "source_count": len(plan["publisher_assets"]), "download_file_count": len(completed),
              "verified_bytes": sum(x["size"] for x in completed),
              "source_selection": plan["selection"], "publisher_assets": plan["publisher_assets"],
              "license": "CC0", "license_url": plan["license_url"],
              "downloaded_files": completed,
              "houdini_cook": False, "unreal_import": False, "landscape_modified": False}
    output = root / "source-verification.json"
    part = root / "source-verification.json.partial"
    part.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(part, output)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "acquire", "verify"))
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    selection = require_manifest(args.selection)
    if args.mode == "verify":
        report_path = args.destination / "source-verification.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("status") != "PH_CC0_SOURCE_BYTES_VERIFIED_NOT_INSTALLED":
            raise ValueError("No verified source report found")
        assert report["source_selection"] == selection, "Selection changed since acquisition"
        for spec in report["downloaded_files"]:
            dest = (args.destination / spec["relative_path"]).resolve()
            if not dest.is_relative_to(args.destination.resolve()):
                raise ValueError("Invalid manifest path")
            if dest.stat().st_size != spec["size"] or digest(dest, "sha256") != spec["sha256"]:
                raise ValueError(f"Source verification mismatch: {dest}")
        print(json.dumps({"status": "READBACK_VERIFIED", "files": len(report["downloaded_files"]),
                          "total_bytes": report["verified_bytes"]}))
        return 0
    plan = build_plan(selection)
    if args.mode == "plan":
        print(json.dumps({"status": plan["status"], "file_count": plan["file_count"],
                          "planned_bytes": plan["planned_bytes"],
                          "assets": [x["slug"] for x in plan["publisher_assets"]]}, indent=2))
        return 0
    result = acquire(plan, args.destination)
    print(json.dumps({"status": result["status"], "files": result["download_file_count"],
                      "bytes": result["verified_bytes"]}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"POLYHAVEN_ACQUISITION_FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
