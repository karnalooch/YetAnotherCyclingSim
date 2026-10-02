"""Curated construction references for BOB.

This is study material, not verified-case memory. Reading a source can shape a
hypothesis or a bounded lesson, but it can never grant production authoring,
road admission, or learning admission by itself.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIBRARY_PATH = ROOT / "worldgen/terrain/bob_construction_knowledge.json"

LIBRARY_ID = "bob-construction-knowledge-v1"
ROLE = "STUDY_REFERENCE_ONLY"
REFERENCE_AUTHORITY = "REFERENCE_ONLY"


def _validate_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def load_construction_knowledge(path: Path = DEFAULT_LIBRARY_PATH):
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("schema_version") != 1:
        raise ValueError("BOB construction knowledge schema_version must be 1")
    if data.get("library_id") != LIBRARY_ID:
        raise ValueError("Unexpected BOB construction knowledge library_id")
    if data.get("role") != ROLE:
        raise ValueError("BOB construction knowledge must remain study-only")

    boundary = data.get("memory_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("BOB construction knowledge requires a memory boundary")
    if boundary.get("verified_case_memory") != "worldgen/terrain/verified_terrain_cases.json":
        raise ValueError("BOB verified-case memory boundary changed")
    rules = boundary.get("rules")
    if not isinstance(rules, list) or len(rules) < 3:
        raise ValueError("BOB construction knowledge requires explicit separation rules")

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("BOB construction knowledge requires entries")

    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("BOB construction knowledge entries must be objects")
        entry_id = _validate_text(entry.get("id"), "entry.id")
        if entry_id in seen:
            raise ValueError(f"Duplicate BOB knowledge entry {entry_id}")
        seen.add(entry_id)
        _validate_text(entry.get("domain"), "entry.domain")
        if entry.get("authority") != REFERENCE_AUTHORITY:
            raise ValueError("Reference material cannot claim verified authority")
        source = entry.get("source")
        if not isinstance(source, dict):
            raise ValueError("BOB knowledge entry requires a source")
        _validate_text(source.get("publisher"), "source.publisher")
        _validate_text(source.get("title"), "source.title")
        url = _validate_text(source.get("url"), "source.url")
        if not url.startswith("https://"):
            raise ValueError("BOB knowledge sources must use HTTPS")
        _validate_text(source.get("retrieved"), "source.retrieved")
        for field in ("principles", "bob_constraints"):
            values = entry.get(field)
            if not isinstance(values, list) or not values:
                raise ValueError(f"BOB knowledge entry requires {field}")
            for value in values:
                _validate_text(value, field)

    return data, hashlib.sha256(raw).hexdigest()


def construction_study_manifest(
    domains: Iterable[str],
    path: Path = DEFAULT_LIBRARY_PATH,
):
    data, digest = load_construction_knowledge(path)
    requested = tuple(dict.fromkeys(_validate_text(domain, "domain") for domain in domains))
    if not requested:
        raise ValueError("BOB study manifest requires at least one domain")

    selected = [
        entry
        for entry in data["entries"]
        if entry["domain"] in requested
    ]
    available = {entry["domain"] for entry in selected}
    missing = [domain for domain in requested if domain not in available]
    if missing:
        raise ValueError(f"BOB knowledge library is missing domains: {', '.join(missing)}")

    return {
        "library_id": data["library_id"],
        "library_sha256": digest,
        "role": ROLE,
        "requested_domains": list(requested),
        "knowledge_entry_ids": [entry["id"] for entry in selected],
        "source_urls": [entry["source"]["url"] for entry in selected],
        "verified_case_memory_modified": False,
        "knowledge_can_grant_admission": False,
        "knowledge_can_grant_learning_admission": False,
    }
