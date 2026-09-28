#!/usr/bin/env python3
"""YACS semantic asset discovery, selection and acquisition library.

This module sits above the existing curated Stage 3G downloader. It turns a
repo-owned world-authoring preset into deterministic semantic asset choices.

Automatic acquisition is deliberately fail-closed:
- only repo-declared providers are accepted;
- only repo-declared licenses are accepted;
- download URLs must resolve to an allowlisted HTTPS host;
- downloaded bytes stay in the ignored ExternalAssets cache;
- no Unreal asset is persisted automatically by this module.

The existing download_stage3g_assets.py remains the low-level file resolver and
checksum-aware transfer implementation for Poly Haven source files.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from download_stage3g_assets import (  # noqa: E402
    PlannedDownload,
    bytes_to_mib,
    collision_safe_target,
    download_file,
    http_json,
    plan_asset_downloads,
)

DEFAULT_CATALOG = REPO_ROOT / "worldgen" / "assets" / "catalog.json"
DEFAULT_PRESET = (
    REPO_ROOT / "worldgen" / "presets" / "alpine_roadside_grove_v1.json"
)
DEFAULT_CACHE = REPO_ROOT / "ExternalAssets" / "WorldLibrary"
DEFAULT_USER_AGENT = (
    "YetAnotherCyclingSim-WorldAuthoringLibrary/1.0 "
    "(+https://github.com/karnalooch/YetAnotherCyclingSim)"
)

POLYHAVEN_TYPE_NAMES = {
    0: "hdri",
    1: "texture",
    2: "model",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")
SAFE_ASSET_ID_RE = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class RankedCandidate:
    asset_id: str
    provider: str
    kind: str
    name: str
    category: str
    tags: tuple[str, ...]
    score: int
    reasons: tuple[str, ...]
    polycount: int | None
    has_lods: bool
    thumbnail_url: str | None


@dataclass(frozen=True)
class SelectedSlot:
    slot: str
    source: str
    catalog_asset_id: str | None
    provider: str
    provider_asset_id: str
    kind: str
    lifecycle_status: str
    ue_asset_path: str | None
    score: int | None
    reasons: tuple[str, ...]


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def normalize_tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(value.lower()))


def validate_generated_root(path: str) -> None:
    normalized = path.rstrip("/")
    if not (
        normalized == "/Game/Generated/YACS"
        or normalized.startswith("/Game/Generated/YACS/")
    ):
        raise ValueError(
            "generated_root must stay under /Game/Generated/YACS/**; "
            f"got {path!r}"
        )


def validate_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("schema_version") != 1:
        raise ValueError("unsupported asset catalog schema")
    validate_generated_root(str(catalog.get("generated_content_root", "")))

    providers = catalog.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ValueError("asset catalog requires providers")

    assets = catalog.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("asset catalog requires assets")

    seen: set[str] = set()
    for asset in assets:
        asset_id = str(asset.get("id", ""))
        if not asset_id or asset_id in seen:
            raise ValueError(f"invalid or duplicate catalog asset id {asset_id!r}")
        seen.add(asset_id)
        if asset.get("lifecycle_status") not in {
            "approved",
            "candidate",
            "reference",
            "blocked",
        }:
            raise ValueError(f"{asset_id}: invalid lifecycle_status")
        source = asset.get("source") or {}
        if source.get("provider") not in providers:
            raise ValueError(f"{asset_id}: unknown provider")
        ue_path = asset.get("ue_asset_path")
        if ue_path is not None and not str(ue_path).startswith("/Game/"):
            raise ValueError(f"{asset_id}: invalid Unreal asset path")


def validate_preset(preset: dict[str, Any], catalog: dict[str, Any]) -> None:
    if preset.get("schema_version") != 1:
        raise ValueError("unsupported world-authoring preset schema")

    validate_generated_root(str(preset.get("generated_root", "")))

    policy = preset.get("asset_policy") or {}
    allowed_providers = list(policy.get("allowed_providers") or [])
    allowed_licenses = list(policy.get("allowed_licenses") or [])
    if not allowed_providers:
        raise ValueError("preset requires at least one allowed provider")
    if not allowed_licenses:
        raise ValueError("preset requires at least one allowed license")

    for provider_id in allowed_providers:
        provider = catalog["providers"].get(provider_id)
        if provider is None:
            raise ValueError(f"preset references unknown provider {provider_id!r}")
        license_name = str(provider.get("asset_license", ""))
        if license_name not in allowed_licenses:
            raise ValueError(
                f"provider {provider_id!r} license {license_name!r} "
                "is not allowed by preset"
            )

    max_download_mib = policy.get("max_download_mib")
    if (
        not isinstance(max_download_mib, int)
        or max_download_mib <= 0
        or max_download_mib > 4096
    ):
        raise ValueError("max_download_mib must be an integer inside 1..4096")

    composition = preset.get("composition") or {}
    size_m = composition.get("size_m")
    if (
        not isinstance(size_m, list)
        or len(size_m) != 2
        or any(float(value) <= 0.0 for value in size_m)
    ):
        raise ValueError("composition.size_m must contain two positive values")

    slots = preset.get("asset_slots")
    if not isinstance(slots, list) or not slots:
        raise ValueError("preset requires asset_slots")

    slot_names: set[str] = set()
    for slot in slots:
        slot_name = str(slot.get("slot", ""))
        if not slot_name or slot_name in slot_names:
            raise ValueError(f"invalid or duplicate slot {slot_name!r}")
        slot_names.add(slot_name)

        if slot.get("kind") not in {"model", "texture"}:
            raise ValueError(f"{slot_name}: unsupported asset kind")
        if not slot.get("semantic_roles"):
            raise ValueError(f"{slot_name}: semantic_roles cannot be empty")
        if not slot.get("search_terms"):
            raise ValueError(f"{slot_name}: search_terms cannot be empty")


def catalog_matches(
    catalog: dict[str, Any],
    slot: dict[str, Any],
    preferred_statuses: list[str],
) -> list[dict[str, Any]]:
    roles = set(str(value) for value in slot["semantic_roles"])
    result: list[dict[str, Any]] = []

    for asset in catalog["assets"]:
        if asset.get("lifecycle_status") not in preferred_statuses:
            continue
        asset_roles = set(str(value) for value in asset.get("semantic_roles", []))
        if not roles.intersection(asset_roles):
            continue
        capabilities = asset.get("capabilities") or {}
        if slot["slot"] == "mass_conifer" and not capabilities.get(
            "pcg_mass_scatter", False
        ):
            continue
        result.append(asset)

    status_rank = {status: index for index, status in enumerate(preferred_statuses)}
    result.sort(
        key=lambda asset: (
            status_rank.get(str(asset["lifecycle_status"]), 999),
            str(asset["id"]),
        )
    )
    return result


def metadata_kind(metadata: dict[str, Any]) -> str:
    type_code = metadata.get("type")
    if not isinstance(type_code, int) or type_code not in POLYHAVEN_TYPE_NAMES:
        return "unknown"
    return POLYHAVEN_TYPE_NAMES[type_code]


def rank_polyhaven_candidate(
    asset_id: str,
    metadata: dict[str, Any],
    slot: dict[str, Any],
) -> RankedCandidate | None:
    if not SAFE_ASSET_ID_RE.fullmatch(asset_id):
        return None

    kind = metadata_kind(metadata)
    if kind != slot["kind"]:
        return None

    excluded = set(str(value) for value in slot.get("excluded_source_ids", []))
    if asset_id in excluded:
        return None

    max_polycount = slot.get("max_polycount")
    polycount_raw = metadata.get("polycount")
    polycount = int(polycount_raw) if isinstance(polycount_raw, (int, float)) else None
    if (
        max_polycount is not None
        and polycount is not None
        and polycount > int(max_polycount)
    ):
        return None

    name = str(metadata.get("name", ""))
    category = str(metadata.get("category", ""))
    description = str(metadata.get("description", ""))
    tags = tuple(str(value) for value in metadata.get("tags", []) if value)

    name_tokens = normalize_tokens(name)
    category_tokens = normalize_tokens(category)
    description_tokens = normalize_tokens(description)
    tag_tokens: set[str] = set()
    for tag in tags:
        tag_tokens.update(normalize_tokens(tag))

    search_terms = [str(value).lower() for value in slot.get("search_terms", [])]
    score = 0
    reasons: list[str] = []

    for term in search_terms:
        tokens = normalize_tokens(term)
        if not tokens:
            continue
        if tokens.issubset(name_tokens):
            score += 12
            reasons.append(f"name:{term}")
        if tokens.issubset(tag_tokens):
            score += 8
            reasons.append(f"tag:{term}")
        if tokens.issubset(category_tokens):
            score += 5
            reasons.append(f"category:{term}")
        if tokens.issubset(description_tokens):
            score += 2
            reasons.append(f"description:{term}")

    preferred_source_ids = [
        str(value) for value in slot.get("preferred_source_ids", [])
    ]
    if asset_id in preferred_source_ids:
        preference = len(preferred_source_ids) - preferred_source_ids.index(asset_id)
        score += 50 + preference
        reasons.append("preferred_source_id")

    has_lods = bool(metadata.get("lods"))
    if slot.get("prefer_lods") and has_lods:
        score += 10
        reasons.append("lods")

    if kind == "model" and polycount is not None:
        if polycount <= 50_000:
            score += 6
            reasons.append("polycount<=50k")
        elif polycount <= 100_000:
            score += 3
            reasons.append("polycount<=100k")

    if score <= 0:
        return None

    return RankedCandidate(
        asset_id=asset_id,
        provider="polyhaven",
        kind=kind,
        name=name,
        category=category,
        tags=tags,
        score=score,
        reasons=tuple(sorted(set(reasons))),
        polycount=polycount,
        has_lods=has_lods,
        thumbnail_url=(
            str(metadata["thumbnail_url"])
            if isinstance(metadata.get("thumbnail_url"), str)
            else None
        ),
    )


def rank_polyhaven_assets(
    assets_payload: dict[str, Any],
    slot: dict[str, Any],
) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for asset_id, metadata in assets_payload.items():
        if not isinstance(metadata, dict):
            continue
        candidate = rank_polyhaven_candidate(str(asset_id), metadata, slot)
        if candidate is not None:
            ranked.append(candidate)

    ranked.sort(key=lambda item: (-item.score, item.asset_id))
    return ranked


def select_slots(
    catalog: dict[str, Any],
    preset: dict[str, Any],
    live_assets: dict[str, Any] | None,
) -> tuple[list[SelectedSlot], dict[str, list[RankedCandidate]]]:
    policy = preset["asset_policy"]
    preferred_statuses = [
        str(value) for value in policy.get("preferred_lifecycle_status", ["approved"])
    ]

    selections: list[SelectedSlot] = []
    discovery: dict[str, list[RankedCandidate]] = {}

    for slot in preset["asset_slots"]:
        slot_name = str(slot["slot"])
        local = catalog_matches(catalog, slot, preferred_statuses)
        if local:
            chosen = local[0]
            source = chosen["source"]
            selections.append(
                SelectedSlot(
                    slot=slot_name,
                    source="catalog",
                    catalog_asset_id=str(chosen["id"]),
                    provider=str(source["provider"]),
                    provider_asset_id=str(source["asset_id"]),
                    kind=str(slot["kind"]),
                    lifecycle_status=str(chosen["lifecycle_status"]),
                    ue_asset_path=(
                        str(chosen["ue_asset_path"])
                        if chosen.get("ue_asset_path")
                        else None
                    ),
                    score=None,
                    reasons=("approved_catalog_match",),
                )
            )
            continue

        if not policy.get("auto_acquire_missing", False):
            raise RuntimeError(
                f"{slot_name}: no approved catalog asset and auto acquisition disabled"
            )
        if live_assets is None:
            raise RuntimeError(
                f"{slot_name}: live provider metadata is required for discovery"
            )

        ranked = rank_polyhaven_assets(live_assets, slot)
        discovery[slot_name] = ranked[:10]
        if not ranked:
            raise RuntimeError(f"{slot_name}: no live Poly Haven candidate matched")

        chosen = ranked[0]
        selections.append(
            SelectedSlot(
                slot=slot_name,
                source="discovery",
                catalog_asset_id=None,
                provider="polyhaven",
                provider_asset_id=chosen.asset_id,
                kind=chosen.kind,
                lifecycle_status="acquired_candidate",
                ue_asset_path=None,
                score=chosen.score,
                reasons=chosen.reasons,
            )
        )

    return selections, discovery


def validate_download_url(url: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"download URL must use HTTPS: {url}")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError(f"download URL has no host: {url}")
    if not any(
        hostname == host or hostname.endswith("." + host)
        for host in allowed_hosts
    ):
        raise ValueError(f"download host {hostname!r} is not allowlisted")


def build_download_plan(
    catalog: dict[str, Any],
    preset: dict[str, Any],
    selections: list[SelectedSlot],
    provider_file_payloads: dict[str, Any],
) -> list[PlannedDownload]:
    resolution = str(preset["asset_policy"]["resolution"])
    by_slot = {str(slot["slot"]): slot for slot in preset["asset_slots"]}
    plan: list[PlannedDownload] = []

    for selection in selections:
        if selection.source != "discovery":
            continue
        slot = by_slot[selection.slot]
        payload = provider_file_payloads.get(selection.provider_asset_id)
        if payload is None:
            raise RuntimeError(
                f"missing /files payload for {selection.provider_asset_id}"
            )
        spec = {
            "id": selection.provider_asset_id,
            "role": selection.slot,
            "kind": selection.kind,
            "maps": list(slot.get("required_maps", [])),
        }
        plan.extend(plan_asset_downloads(spec, payload, resolution))

    provider = catalog["providers"]["polyhaven"]
    allowed_hosts = {
        str(value).lower() for value in provider["allowed_download_hosts"]
    }
    for item in plan:
        validate_download_url(item.leaf.url, allowed_hosts)

    unique: dict[str, PlannedDownload] = {}
    for item in plan:
        unique.setdefault(item.leaf.url, item)
    return sorted(
        unique.values(),
        key=lambda item: (
            item.asset_id,
            item.map_type or "",
            item.leaf.filename.lower(),
            item.leaf.url,
        ),
    )


def serialize_candidate(candidate: RankedCandidate) -> dict[str, Any]:
    return {
        **asdict(candidate),
        "tags": list(candidate.tags),
        "reasons": list(candidate.reasons),
    }


def serialize_selection(selection: SelectedSlot) -> dict[str, Any]:
    return {
        **asdict(selection),
        "reasons": list(selection.reasons),
    }


def write_plan(
    output_path: Path,
    catalog: dict[str, Any],
    preset: dict[str, Any],
    selections: list[SelectedSlot],
    discovery: dict[str, list[RankedCandidate]],
    downloads: list[dict[str, Any]],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "library": "YACS World Authoring Library",
        "preset_id": preset["id"],
        "seed": int(preset["seed"]),
        "generated_root": preset["generated_root"],
        "composition": preset["composition"],
        "pcg": preset["pcg"],
        "provider_credit": catalog["providers"]["polyhaven"]["credit"],
        "selections": [serialize_selection(item) for item in selections],
        "discovery": {
            slot: [serialize_candidate(item) for item in candidates]
            for slot, candidates in sorted(discovery.items())
        },
        "downloads": downloads,
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve a YACS world-authoring preset into deterministic assets."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--preset", type=Path, default=DEFAULT_PRESET)
    parser.add_argument("--destination", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Selection-plan JSON path (default: destination/selection-plan.json).",
    )
    parser.add_argument(
        "--live-discovery",
        action="store_true",
        help="Query Poly Haven /assets even when approved catalog assets satisfy slots.",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download only slots that had to be filled by live discovery.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = load_json(args.catalog)
    preset = load_json(args.preset)
    validate_catalog(catalog)
    validate_preset(preset, catalog)

    provider = catalog["providers"]["polyhaven"]
    api_base = str(provider["api_base"]).rstrip("/")
    live_assets: dict[str, Any] | None = None

    approved_missing = False
    preferred_statuses = [
        str(value)
        for value in preset["asset_policy"].get(
            "preferred_lifecycle_status", ["approved"]
        )
    ]
    for slot in preset["asset_slots"]:
        if not catalog_matches(catalog, slot, preferred_statuses):
            approved_missing = True
            break

    if args.live_discovery or approved_missing:
        live_assets = http_json(
            api_base + "/assets",
            user_agent=DEFAULT_USER_AGENT,
            timeout=args.timeout,
        )
        if not isinstance(live_assets, dict):
            raise RuntimeError("Poly Haven /assets returned non-object JSON")

    selections, discovery = select_slots(catalog, preset, live_assets)

    provider_file_payloads: dict[str, Any] = {}
    if args.download:
        for selection in selections:
            if selection.source != "discovery":
                continue
            asset_id = selection.provider_asset_id
            provider_file_payloads[asset_id] = http_json(
                f"{api_base}/files/{asset_id}",
                user_agent=DEFAULT_USER_AGENT,
                timeout=args.timeout,
            )

    plan = build_download_plan(
        catalog, preset, selections, provider_file_payloads
    )

    max_bytes = int(preset["asset_policy"]["max_download_mib"]) * 1024 * 1024
    known_bytes = sum(item.leaf.size or 0 for item in plan)
    if known_bytes > max_bytes:
        raise RuntimeError(
            "download plan is "
            f"{bytes_to_mib(known_bytes):.1f} MiB, above preset cap "
            f"{preset['asset_policy']['max_download_mib']} MiB"
        )

    downloads: list[dict[str, Any]] = []
    if args.download:
        occupied_by_asset: dict[str, dict[str, str]] = {}
        for item in plan:
            asset_dir = args.destination / "polyhaven" / item.asset_id
            occupied = occupied_by_asset.setdefault(item.asset_id, {})
            target = collision_safe_target(asset_dir, item.leaf, occupied)
            status = download_file(
                item.leaf,
                target,
                user_agent=DEFAULT_USER_AGENT,
                timeout=args.timeout,
                force=args.force,
            )
            downloads.append(
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
                    "status": status,
                }
            )

    output = args.output or (args.destination / "selection-plan.json")
    write_plan(
        output,
        catalog,
        preset,
        selections,
        discovery,
        downloads,
    )

    print("YACS World Authoring Library: PASS")
    print(f"Preset: {preset['id']}")
    for selection in selections:
        print(
            f"  {selection.slot}: {selection.provider_asset_id} "
            f"[{selection.source}/{selection.lifecycle_status}]"
        )
    print(f"Known download size: {bytes_to_mib(known_bytes):.1f} MiB")
    print(f"Plan: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
