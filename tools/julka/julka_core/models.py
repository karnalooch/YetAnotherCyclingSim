"""Versioned asset identity, profile closure, and storage policy."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA_VERSION = 1
HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
HEX_MD5 = re.compile(r"^[0-9a-f]{32}$")
ASSET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
VALID_CLASSES = {"source", "production", "prepared", "evidence", "cache"}
VALID_BACKENDS = {"git", "git-lfs", "dvc", "github-release", "local", "manual-cnig"}
VALID_STATES = {"acquired", "approved", "candidate", "manual-acquisition-required"}


class JulkaError(RuntimeError):
    """A user-actionable, fail-closed Julka error."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise JulkaError(f"cannot read JSON manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise JulkaError(f"expected a JSON object in {path}")
    return data


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or (path.parts and ":" in path.parts[0])
    ):
        raise JulkaError(f"unsafe repository-relative path: {value!r}")
    return path


def validate_catalog(catalog: dict[str, Any]) -> None:
    if catalog.get("schema_version") != SCHEMA_VERSION:
        raise JulkaError(
            f"unsupported Julka catalog schema: {catalog.get('schema_version')!r}"
        )
    assets = catalog.get("assets")
    profiles = catalog.get("profiles")
    if not isinstance(assets, list) or not isinstance(profiles, dict):
        raise JulkaError("catalog requires assets[] and profiles{}")
    gis_profiles = catalog.get("gis_metadata_profiles")
    required_gis_fields = {
        "xy_crs",
        "xy_unit",
        "vertical_datum",
        "footprint",
        "resolution_or_density",
        "classification",
        "nodata",
    }
    if not isinstance(gis_profiles, dict) or not gis_profiles:
        raise JulkaError(
            "catalog requires explicit GIS metadata profiles, including unknown/uninspected values"
        )
    for name, metadata in gis_profiles.items():
        if not isinstance(metadata, dict) or not required_gis_fields.issubset(metadata):
            raise JulkaError(
                f"GIS metadata profile {name!r} is missing a required field"
            )
    identifiers: set[str] = set()
    paths: set[str] = set()
    for record in assets:
        if not isinstance(record, dict):
            raise JulkaError("every catalog asset must be a JSON object")
        asset_id = record.get("asset_id")
        if (
            not isinstance(asset_id, str)
            or not ASSET_ID.fullmatch(asset_id)
            or asset_id in identifiers
        ):
            raise JulkaError(f"missing or duplicate asset_id: {asset_id!r}")
        identifiers.add(asset_id)
        if record.get("class") not in VALID_CLASSES:
            raise JulkaError(f"{asset_id}: unsupported asset class")
        backend = record.get("backend")
        if not isinstance(backend, dict) or backend.get("type") not in VALID_BACKENDS:
            raise JulkaError(f"{asset_id}: unsupported or missing storage backend")
        state = record.get("status")
        if state not in VALID_STATES:
            raise JulkaError(f"{asset_id}: unsupported or missing provenance status")
        sha256 = record.get("sha256")
        size = record.get("size_bytes")
        if not isinstance(sha256, str) or not HEX_SHA256.fullmatch(sha256):
            raise JulkaError(f"{asset_id}: expected an independently verified SHA-256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise JulkaError(f"{asset_id}: size_bytes must be a non-negative integer")
        signature = record.get("signature_hex")
        if signature is not None and (
            not isinstance(signature, str)
            or not re.fullmatch(r"(?:[0-9a-f]{2}){1,16}", signature)
        ):
            raise JulkaError(
                f"{asset_id}: signature_hex must be an even-length lowercase hex string"
            )
        relative_path = safe_relative_path(record.get("path", ""))
        if relative_path.as_posix() in paths:
            raise JulkaError(f"duplicate asset path: {relative_path.as_posix()!r}")
        paths.add(relative_path.as_posix())
        provenance = record.get("provenance")
        if not isinstance(provenance, dict) or not isinstance(
            provenance.get("license"), str
        ):
            raise JulkaError(f"{asset_id}: license/provenance is required")
        for dependency in record.get("depends_on", []):
            if not isinstance(dependency, str):
                raise JulkaError(f"{asset_id}: dependency IDs must be strings")
        acquisition = record.get("acquisition", {})
        if not isinstance(acquisition, dict):
            raise JulkaError(f"{asset_id}: acquisition must be an object")
        if backend.get("type") == "github-release":
            if not isinstance(acquisition.get("release_tag"), str) or not isinstance(
                acquisition.get("release_asset"), str
            ):
                raise JulkaError(f"{asset_id}: Release tag and asset name are required")
            if (
                Path(acquisition["release_asset"]).name != acquisition["release_asset"]
                or "\\" in acquisition["release_asset"]
            ):
                raise JulkaError(f"{asset_id}: unsafe Release asset filename")

    receipt = catalog.get("receipt")
    if not isinstance(receipt, dict) or not isinstance(
        receipt.get("release_asset"), str
    ):
        raise JulkaError("catalog requires a pinned provider receipt")
    receipt_relative_path = safe_relative_path(receipt.get("path", ""))
    if receipt_relative_path.as_posix() in paths:
        raise JulkaError("provider receipt path collides with an asset path")
    if (
        Path(receipt["release_asset"]).name != receipt["release_asset"]
        or "\\" in receipt["release_asset"]
    ):
        raise JulkaError("unsafe provider receipt Release filename")
    if not HEX_SHA256.fullmatch(str(receipt.get("sha256", ""))):
        raise JulkaError("provider receipt requires a SHA-256")
    if not isinstance(receipt.get("size_bytes"), int) or receipt["size_bytes"] <= 0:
        raise JulkaError("provider receipt requires a positive byte size")

    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise JulkaError(f"profile {name}: expected an object")
        includes = profile.get("extends", [])
        requires = profile.get("requires", [])
        if not isinstance(includes, list) or not isinstance(requires, list):
            raise JulkaError(f"profile {name}: extends/requires must be lists")
        if any(not isinstance(item, str) for item in [*includes, *requires]):
            raise JulkaError(f"profile {name}: profile and asset IDs must be strings")
        exact_lfs = profile.get("git_lfs_paths", [])
        lfs_extensions = profile.get("git_lfs_extensions", [])
        if not isinstance(exact_lfs, list) or not isinstance(lfs_extensions, list):
            raise JulkaError(f"profile {name}: Git LFS selectors must be lists")
        for value in exact_lfs:
            if not isinstance(value, str):
                raise JulkaError(f"profile {name}: Git LFS paths must be strings")
            safe_relative_path(value)
        if any(
            not isinstance(value, str)
            or not value.startswith(".")
            or "/" in value
            or "\\" in value
            for value in lfs_extensions
        ):
            raise JulkaError(
                f"profile {name}: Git LFS extension selectors must be simple extensions"
            )

    for asset in assets:
        for dependency in asset.get("depends_on", []):
            if dependency not in identifiers:
                raise JulkaError(
                    f"{asset['asset_id']}: unknown dependency {dependency!r}"
                )
    for name, profile in profiles.items():
        for included in profile.get("extends", []):
            if included not in profiles:
                raise JulkaError(f"profile {name}: unknown parent profile {included!r}")
        for required in profile.get("requires", []):
            if required not in identifiers:
                raise JulkaError(f"profile {name}: unknown required asset {required!r}")
    for name in profiles:
        profile_assets(catalog, name)


def topological_assets(catalog: dict[str, Any], name: str) -> list[dict[str, Any]]:
    """Resolve a profile and its asset dependencies in deterministic order."""
    validate_catalog(catalog)
    return profile_assets(catalog, name)


def profile_assets(catalog: dict[str, Any], name: str) -> list[dict[str, Any]]:
    profiles = catalog["profiles"]
    if name not in profiles:
        raise JulkaError(
            f"unknown profile {name!r}; available: {', '.join(sorted(profiles))}"
        )
    by_id = {asset["asset_id"]: asset for asset in catalog["assets"]}
    ordered: list[str] = []
    active: set[str] = set()
    finished: set[str] = set()

    def visit_profile(profile_name: str) -> None:
        if profile_name in active:
            raise JulkaError(f"profile inheritance cycle includes {profile_name!r}")
        if profile_name in finished:
            return
        active.add(profile_name)
        profile = profiles[profile_name]
        for parent in profile.get("extends", []):
            visit_profile(parent)
        for asset_id in profile.get("requires", []):
            visit_asset(asset_id)
        active.remove(profile_name)
        finished.add(profile_name)

    def visit_asset(asset_id: str) -> None:
        if asset_id not in by_id:
            raise JulkaError(f"unknown asset dependency {asset_id!r}")
        if asset_id in active:
            raise JulkaError(f"asset dependency cycle includes {asset_id!r}")
        if asset_id in finished:
            return
        active.add(asset_id)
        for dependency in by_id[asset_id].get("depends_on", []):
            visit_asset(dependency)
        active.remove(asset_id)
        finished.add(asset_id)
        ordered.append(asset_id)

    visit_profile(name)
    return [by_id[asset_id] for asset_id in ordered]
