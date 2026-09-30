#!/usr/bin/env python3
"""Download the curated Stage 3G source-asset bundle from Poly Haven.

The script intentionally downloads source files into an ignored local cache.
Nothing is imported into Unreal Engine automatically. Import, LOD/Nanite choices,
material setup, and performance validation remain explicit home-PC work.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import unquote, urlparse

REPOSITORY_URL = "https://github.com/karnalooch/YetAnotherCyclingSim"
DEFAULT_USER_AGENT = (
    "YetAnotherCyclingSim-Stage3GAssetBootstrap/1.0 "
    f"(+{REPOSITORY_URL})"
)
CHUNK_SIZE = 1024 * 1024

MAP_ALIASES: dict[str, tuple[str, ...]] = {
    "diffuse": ("diffuse", "_diff", "albedo", "basecolor", "base_color"),
    "normal_dx": ("nor_dx", "normal_dx", "normal (dx)", "normal_dx"),
    "normal_gl": ("nor_gl", "normal_gl", "normal (gl)", "normal_gl"),
    "roughness": ("roughness", "rough"),
    "displacement": ("displacement", "_disp", "/disp", "height"),
    "mask": ("mask",),
    "alpha": ("alpha",),
    "arm": ("arm", "ao/rough/metal", "ao_rough_metal"),
    "ao": ("ambient_occlusion", "/ao", "_ao"),
}

EXTENSION_PREFERENCE: dict[str, tuple[str, ...]] = {
    "diffuse": (".jpg", ".png", ".exr"),
    "normal_dx": (".png", ".jpg", ".exr"),
    "roughness": (".jpg", ".png", ".exr"),
    "displacement": (".png", ".exr", ".jpg"),
    "mask": (".png", ".jpg", ".exr"),
    "alpha": (".png", ".jpg", ".exr"),
    "arm": (".png", ".jpg", ".exr"),
    "ao": (".jpg", ".png", ".exr"),
}


@dataclass(frozen=True)
class DownloadLeaf:
    path: tuple[str, ...]
    url: str
    size: int | None
    md5: str | None

    @property
    def decoded_url(self) -> str:
        return unquote(self.url)

    @property
    def extension(self) -> str:
        return Path(urlparse(self.decoded_url).path).suffix.lower()

    @property
    def filename(self) -> str:
        name = Path(urlparse(self.decoded_url).path).name
        return name or "download.bin"

    @property
    def haystack(self) -> str:
        path_text = "/".join(self.path)
        return f"{path_text} {self.decoded_url}".lower().replace("-", "_")


@dataclass(frozen=True)
class PlannedDownload:
    asset_id: str
    role: str
    leaf: DownloadLeaf
    map_type: str | None = None


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    parser = argparse.ArgumentParser(
        description="Download the curated CC0 Stage 3G source assets from Poly Haven."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=script_dir / "stage3g_polyhaven.json",
        help="Asset manifest JSON (default: %(default)s).",
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=repo_root / "ExternalAssets" / "Stage3G" / "PolyHaven",
        help="Ignored local source-asset cache (default: %(default)s).",
    )
    parser.add_argument(
        "--resolution",
        choices=("1k", "2k", "4k", "8k"),
        default=None,
        help="Override the manifest default texture resolution.",
    )
    parser.add_argument(
        "--asset",
        action="append",
        default=[],
        metavar="ASSET_ID",
        help="Download only one asset ID. Repeat to select several.",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="Also include manifest entries marked disabled by default.",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Resolve API metadata and print the download plan without downloading.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even when the cached file matches the API MD5.",
    )
    parser.add_argument(
        "--max-total-mib",
        type=int,
        default=1536,
        help="Safety cap for the selected download set in MiB (default: %(default)s).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds per request (default: %(default)s).",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != 1:
        raise ValueError(
            f"Unsupported manifest schema: {manifest.get('schema_version')!r}"
        )
    if not isinstance(manifest.get("assets"), list) or not manifest["assets"]:
        raise ValueError("Manifest must contain a non-empty 'assets' list")
    return manifest


def http_json(url: str, user_agent: str, timeout: int) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def iter_download_leaves(
    node: Any, path: tuple[str, ...] = ()
) -> Iterator[DownloadLeaf]:
    if isinstance(node, dict):
        url = node.get("url")
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            size = node.get("size")
            md5 = node.get("md5")
            yield DownloadLeaf(
                path=path,
                url=url,
                size=int(size) if isinstance(size, (int, float)) else None,
                md5=md5.lower() if isinstance(md5, str) else None,
            )
        for key, value in node.items():
            if key in {"url", "size", "md5"}:
                continue
            yield from iter_download_leaves(value, path + (str(key),))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_download_leaves(value, path + (str(index),))


def detect_map_type(leaf: DownloadLeaf) -> str | None:
    haystack = leaf.haystack
    if any(alias in haystack for alias in MAP_ALIASES["normal_gl"]):
        return "normal_gl"
    for map_type in (
        "normal_dx",
        "diffuse",
        "roughness",
        "displacement",
        "mask",
        "alpha",
        "arm",
        "ao",
    ):
        if any(alias in haystack for alias in MAP_ALIASES[map_type]):
            return map_type
    return None


def has_resolution(leaf: DownloadLeaf, resolution: str) -> bool:
    token = resolution.lower()
    return bool(
        re.search(
            rf"(^|[/_]){re.escape(token)}([/_.]|$)",
            leaf.haystack,
        )
    )


def group_key(leaf: DownloadLeaf) -> str:
    if leaf.path:
        tail = leaf.path[-1].lower().lstrip(".")
        if tail in {
            "jpg",
            "jpeg",
            "png",
            "exr",
            "fbx",
            "gltf",
            "glb",
            "usd",
            "blend",
        }:
            return "/".join(leaf.path[:-1]).lower()
    url_path = unquote(urlparse(leaf.url).path)
    return str(Path(url_path).with_suffix("")).lower()


def extension_rank(map_type: str, extension: str) -> int:
    preferences = EXTENSION_PREFERENCE.get(
        map_type, (".png", ".jpg", ".exr")
    )
    try:
        return preferences.index(extension)
    except ValueError:
        return len(preferences) + 10


def select_texture_files(
    leaves: Iterable[DownloadLeaf],
    resolution: str,
    requested_maps: set[str],
) -> list[tuple[DownloadLeaf, str]]:
    grouped: dict[tuple[str, str], list[DownloadLeaf]] = {}
    for leaf in leaves:
        if leaf.extension not in {".jpg", ".jpeg", ".png", ".exr"}:
            continue
        if not has_resolution(leaf, resolution):
            continue
        map_type = detect_map_type(leaf)
        if (
            map_type is None
            or map_type == "normal_gl"
            or map_type not in requested_maps
        ):
            continue
        grouped.setdefault((map_type, group_key(leaf)), []).append(leaf)

    selected: list[tuple[DownloadLeaf, str]] = []
    for (map_type, _), candidates in sorted(grouped.items()):
        best = min(
            candidates,
            key=lambda item: (
                extension_rank(map_type, item.extension),
                item.url,
            ),
        )
        selected.append((best, map_type))
    return selected


def select_model_geometry(
    leaves: Iterable[DownloadLeaf], resolution: str
) -> list[DownloadLeaf]:
    selected: list[DownloadLeaf] = []
    for leaf in leaves:
        if leaf.extension != ".fbx":
            continue
        explicit_resolutions = {
            value
            for value in ("1k", "2k", "4k", "8k")
            if has_resolution(leaf, value)
        }
        if explicit_resolutions and resolution not in explicit_resolutions:
            continue
        selected.append(leaf)
    return deduplicate_leaves(selected)


def deduplicate_leaves(
    leaves: Iterable[DownloadLeaf],
) -> list[DownloadLeaf]:
    by_url: dict[str, DownloadLeaf] = {}
    for leaf in leaves:
        by_url.setdefault(leaf.url, leaf)
    return sorted(
        by_url.values(),
        key=lambda item: (item.filename.lower(), item.url),
    )


def plan_asset_downloads(
    asset: dict[str, Any],
    api_payload: Any,
    resolution: str,
) -> list[PlannedDownload]:
    asset_id = str(asset["id"])
    role = str(asset["role"])
    kind = str(asset["kind"])
    requested_maps = set(asset.get("maps", []))
    leaves = deduplicate_leaves(iter_download_leaves(api_payload))

    planned: list[PlannedDownload] = []
    if kind == "texture":
        texture_files = select_texture_files(
            leaves, resolution, requested_maps
        )
        if not texture_files:
            raise RuntimeError(
                f"{asset_id}: no {resolution} texture maps matched the manifest"
            )
        planned.extend(
            PlannedDownload(
                asset_id=asset_id,
                role=role,
                leaf=leaf,
                map_type=map_type,
            )
            for leaf, map_type in texture_files
        )
    elif kind == "model":
        geometry = select_model_geometry(leaves, resolution)
        if not geometry:
            raise RuntimeError(
                f"{asset_id}: no FBX geometry found in Poly Haven API response"
            )
        planned.extend(
            PlannedDownload(
                asset_id=asset_id,
                role=role,
                leaf=leaf,
                map_type=None,
            )
            for leaf in geometry
        )
        planned.extend(
            PlannedDownload(
                asset_id=asset_id,
                role=role,
                leaf=leaf,
                map_type=map_type,
            )
            for leaf, map_type in select_texture_files(
                leaves, resolution, requested_maps
            )
        )
    else:
        raise ValueError(
            f"{asset_id}: unsupported asset kind {kind!r}"
        )

    unique: dict[str, PlannedDownload] = {}
    for item in planned:
        unique.setdefault(item.leaf.url, item)
    return sorted(
        unique.values(),
        key=lambda item: (
            item.asset_id,
            item.leaf.filename.lower(),
            item.leaf.url,
        ),
    )


def bytes_to_mib(value: int | None) -> float:
    return (value or 0) / (1024 * 1024)


def md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_matches(path: Path, leaf: DownloadLeaf) -> bool:
    if not path.is_file():
        return False
    if leaf.size is not None and path.stat().st_size != leaf.size:
        return False
    if leaf.md5 is not None and md5_file(path).lower() != leaf.md5:
        return False
    return True


def download_file(
    leaf: DownloadLeaf,
    target: Path,
    user_agent: str,
    timeout: int,
    force: bool,
) -> str:
    if not force and file_matches(target, leaf):
        return "cached"

    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        leaf.url,
        headers={"User-Agent": user_agent},
    )
    temp_path = target.with_name(target.name + ".part")
    if temp_path.exists():
        temp_path.unlink()

    try:
        with (
            urllib.request.urlopen(request, timeout=timeout) as response,
            temp_path.open("wb") as output,
        ):
            shutil.copyfileobj(
                response,
                output,
                length=CHUNK_SIZE,
            )
        if (
            leaf.size is not None
            and temp_path.stat().st_size != leaf.size
        ):
            raise RuntimeError(
                f"size mismatch for {target.name}: "
                f"expected {leaf.size}, got {temp_path.stat().st_size}"
            )
        if leaf.md5 is not None:
            actual_md5 = md5_file(temp_path).lower()
            if actual_md5 != leaf.md5:
                raise RuntimeError(
                    f"MD5 mismatch for {target.name}: "
                    f"expected {leaf.md5}, got {actual_md5}"
                )
        os.replace(temp_path, target)
        return "downloaded"
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def collision_safe_target(
    asset_dir: Path,
    leaf: DownloadLeaf,
    occupied: dict[str, str],
) -> Path:
    filename = leaf.filename
    key = filename.lower()
    previous_url = occupied.get(key)
    if previous_url is None or previous_url == leaf.url:
        occupied[key] = leaf.url
        return asset_dir / filename

    prefix_source = "/".join(leaf.path[:-1]) or leaf.url
    prefix = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "_",
        prefix_source,
    ).strip("_")[-80:]
    filename = (
        f"{prefix}__{filename}"
        if prefix
        else f"duplicate__{filename}"
    )
    occupied[filename.lower()] = leaf.url
    return asset_dir / filename


def write_download_index(
    destination: Path,
    manifest: dict[str, Any],
    resolution: str,
    downloads: list[dict[str, Any]],
) -> None:
    payload = {
        "schema_version": 1,
        "provider": manifest["provider"],
        "resolution": resolution,
        "notice": (
            "Local ignored source cache. "
            "Import into Unreal is a separate validated step."
        ),
        "files": downloads,
    }
    destination.mkdir(parents=True, exist_ok=True)
    index_path = destination / "download-index.json"
    index_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    provider = manifest["provider"]
    api_base = str(provider["api_base"]).rstrip("/")
    resolution = (
        args.resolution
        or str(manifest["defaults"]["resolution"])
    )
    user_agent = str(
        provider.get("user_agent")
        or DEFAULT_USER_AGENT
    )
    selected_ids = set(args.asset)

    assets: list[dict[str, Any]] = []
    for asset in manifest["assets"]:
        asset_id = str(asset["id"])
        if selected_ids and asset_id not in selected_ids:
            continue
        enabled = bool(asset.get("enabled", True))
        if not enabled and not args.include_optional:
            continue
        assets.append(asset)

    missing_ids = selected_ids - {
        str(asset["id"])
        for asset in manifest["assets"]
    }
    if missing_ids:
        raise ValueError(
            "Unknown asset IDs: "
            + ", ".join(sorted(missing_ids))
        )
    if not assets:
        raise ValueError("No assets selected")

    print("YACS Stage 3G source-asset bootstrap")
    print(
        f"Provider: {provider['name']} — "
        f"{provider['asset_license']}"
    )
    print(f"API credit: {provider['api_credit']}")
    print(f"Resolution: {resolution}")
    print(f"Destination: {args.destination}")
    print()

    plan: list[PlannedDownload] = []
    for asset in assets:
        asset_id = str(asset["id"])
        endpoint = f"{api_base}/files/{asset_id}"
        print(
            f"Resolving {asset_id} "
            f"({asset['role']})..."
        )
        payload = http_json(
            endpoint,
            user_agent=user_agent,
            timeout=args.timeout,
        )
        plan.extend(
            plan_asset_downloads(
                asset,
                payload,
                resolution,
            )
        )

    total_known_bytes = sum(
        item.leaf.size or 0 for item in plan
    )
    unknown_sizes = sum(
        1 for item in plan if item.leaf.size is None
    )
    print()
    print(f"Selected files: {len(plan)}")
    print(
        "Known download size: "
        f"{bytes_to_mib(total_known_bytes):.1f} MiB"
    )
    if unknown_sizes:
        print(
            "Files with unknown API size: "
            f"{unknown_sizes}"
        )

    max_bytes = args.max_total_mib * 1024 * 1024
    if total_known_bytes > max_bytes:
        raise RuntimeError(
            f"Planned download is "
            f"{bytes_to_mib(total_known_bytes):.1f} MiB, "
            f"above the {args.max_total_mib} MiB safety cap. "
            "Raise --max-total-mib deliberately to continue."
        )

    by_asset: dict[str, list[PlannedDownload]] = {}
    for item in plan:
        by_asset.setdefault(
            item.asset_id,
            [],
        ).append(item)
    for asset_id, items in by_asset.items():
        subtotal = sum(
            item.leaf.size or 0
            for item in items
        )
        print(
            f"  {asset_id}: {len(items)} files, "
            f"{bytes_to_mib(subtotal):.1f} MiB"
        )
        if args.list_only:
            for item in items:
                label = item.map_type or "geometry"
                print(
                    f"    - {label:12} "
                    f"{item.leaf.filename}"
                )

    if args.list_only:
        print(
            "\nList-only mode: nothing downloaded."
        )
        return 0

    index_rows: list[dict[str, Any]] = []
    occupied_by_asset: dict[str, dict[str, str]] = {}
    for item in plan:
        asset_dir = args.destination / item.asset_id
        occupied = occupied_by_asset.setdefault(
            item.asset_id,
            {},
        )
        target = collision_safe_target(
            asset_dir,
            item.leaf,
            occupied,
        )
        print(
            f"[{item.asset_id}] "
            f"{item.leaf.filename} ...",
            end=" ",
            flush=True,
        )
        status = download_file(
            item.leaf,
            target,
            user_agent=user_agent,
            timeout=args.timeout,
            force=args.force,
        )
        print(status)
        index_rows.append(
            {
                "asset_id": item.asset_id,
                "role": item.role,
                "map_type": item.map_type,
                "source_url": item.leaf.url,
                "relative_path": str(
                    target.relative_to(args.destination)
                ).replace("\\", "/"),
                "size": item.leaf.size,
                "md5": item.leaf.md5,
            }
        )

    write_download_index(
        args.destination,
        manifest,
        resolution,
        index_rows,
    )
    print("\nDownload complete.")
    print(
        "Source files remain outside Git. "
        "Import only the assets needed by Stage 3G, "
        "then validate them on the home PC."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ValueError,
        RuntimeError,
        urllib.error.URLError,
        urllib.error.HTTPError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
