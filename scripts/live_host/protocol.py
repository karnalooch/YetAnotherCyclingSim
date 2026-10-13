"""Fail-closed, standard-library-only contracts for YACS Live Host (#476).

No Unreal, subprocess, network service, arbitrary code, or filesystem mutation
during import. Validate every remote request before entering the editor thread.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PRODUCER_SHA = "d361e7651d16ff424ae4e812c7d8cbe1fe81d662"
PRODUCER_RUN = "38278235093-1"
MAP_SHA256 = "bf2b92945865e2307990b6d3da40095dfa0774d28affb32a1e42e55f288764dd"
STAGE = Path(
    "D:/yacs/work/pcg365/"
    + PRODUCER_SHA
    + "/"
    + PRODUCER_RUN
)
MAP_PACKAGE = "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview"
SITE_IDS = ("P0", "P1", "P2", "P3", "P4")
SITE_XY = (
    (16800, 70400),
    (4800, 96800),
    (184800, 180800),
    (181600, 189600),
    (91200, 200800),
)
INSTANCE_PATTERN = re.compile(r"[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\Z")
REQUEST_PATTERN = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}\Z")
SHA_PATTERN = re.compile(r"[a-f0-9]{40}\Z")
MAX_REQUEST_BYTES = 4096
MAX_RECIPE_ARGS_BYTES = 2048
RECIPE_NAME = re.compile(r"[a-z][a-z0-9_]{2,47}\Z")
DIGEST_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
RECIPE_INTENTS = frozenset(("preview", "author"))


class Rejected(ValueError):
    """A user, source, transport, or proof contract was not satisfied."""


def need(condition: bool, explanation: str) -> None:
    if not condition:
        raise Rejected(explanation)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def file_proof(path: Path) -> dict:
    need(path.is_file() and not path.is_symlink(), "Missing/aliased proof file")
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def load_bounded_json(path: Path, size: int = MAX_REQUEST_BYTES) -> dict:
    need(path.is_file() and not path.is_symlink(), "Input is not a regular file")
    need(0 < path.stat().st_size <= size, "Input length is not bounded")
    with path.open("rb") as stream:
        raw = stream.read(size + 1)
    need(len(raw) <= size, "Input changed or exceeded byte limit")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise Rejected("Invalid JSON input") from exc
    need(type(value) is dict, "Top-level JSON object required")
    return value


def validate_request(value: dict, *, session: str, source_sha: str, last_sequence: int) -> dict:
    need(type(value) is dict, "JSON object required")
    need(type(session) is str and INSTANCE_PATTERN.fullmatch(session) is not None,
         "Invalid live-host session identity")
    need(type(source_sha) is str and SHA_PATTERN.fullmatch(source_sha) is not None,
         "Invalid exact installed code revision")
    common = {"schema_version", "session", "source_sha", "request_id", "sequence", "action"}
    action = value.get("action")
    allowed = {
        "focus_site": {"site"},
        "focus_road": set(),
        "set_markers_visible": {"visible"},
        "inspect": set(),
        "run_recipe": {"recipe", "recipe_revision", "recipe_sha256", "intent", "parameters"},
    }
    need(type(action) is str and action in allowed,
         "Command is not in the read-only visual allowlist")
    need(set(value) == common | allowed[action], "Unexpected/missing request fields")
    need(type(value["schema_version"]) is int and value["schema_version"] == 1,
         "Unsupported request version")
    need(value["session"] == session and value["source_sha"] == source_sha,
         "Request targets another Editor/session/revision")
    need(type(value["request_id"]) is str
         and REQUEST_PATTERN.fullmatch(value["request_id"]) is not None,
         "Invalid request ID")
    need(type(last_sequence) is int and last_sequence >= 0,
         "Invalid prior command sequence")
    need(type(value["sequence"]) is int
         and value["sequence"] == last_sequence + 1
         and value["sequence"] <= 999999,
         "Out-of-order, replayed or invalid request sequence")
    if action == "focus_site":
        need(type(value["site"]) is str and value["site"] in SITE_IDS,
             "Camera target must be one frozen marker")
    if action == "set_markers_visible":
        need(type(value["visible"]) is bool, "Marker visibility must be a JSON boolean")
    if action == "run_recipe":
        need(type(value["recipe"]) is str and RECIPE_NAME.fullmatch(value["recipe"]),
             "Editor recipe must be a fixed identifier, never a source path")
        need(type(value["recipe_revision"]) is str
             and SHA_PATTERN.fullmatch(value["recipe_revision"]),
             "Recipe revision must be an exact commit SHA")
        need(type(value["recipe_sha256"]) is str
             and DIGEST_PATTERN.fullmatch(value["recipe_sha256"]),
             "Recipe code must have an exact SHA256")
        need(value["intent"] in RECIPE_INTENTS and type(value["intent"]) is str,
             "Invalid preview/author intent")
        params = value["parameters"]
        need(type(params) is dict and len(params) <= 32
             and all(type(key) is str
                     and re.fullmatch(r"[a-z][a-z0-9_]{0,47}", key)
                     for key in params),
             "Recipe parameters must have a bounded named schema")
        need(len(json.dumps(params, allow_nan=False).encode("utf-8"))
             <= MAX_RECIPE_ARGS_BYTES, "Recipe parameters exceed request budget")
    return value


def validate_red_manifest(value: dict) -> None:
    need(type(value) is dict and value.get("schema_version") == 1,
         "Red review manifest schema changed")
    need(value.get("source_producer_sha") == PRODUCER_SHA
         and value.get("source_run") == PRODUCER_RUN
         and value.get("source_map_sha256") == MAP_SHA256
         and value.get("map_package") == MAP_PACKAGE,
         "Frozen source/map provenance drift")
    need(value.get("scope") == "OWNER_VISUAL_DIAGNOSTIC_NOT_PLACEMENT"
         and value.get("placement") is False
         and value.get("qualified_assets") == []
         and value.get("full_qualification") is False
         and value.get("performance_pass") is False,
         "Visual source must never grant production placement")
    sites = value.get("markers")
    need(type(sites) is list and len(sites) == 5, "Five historical sites required")
    need(all(type(s) is dict for s in sites), "Invalid site entries")
    need(tuple(s.get("id") for s in sites) == SITE_IDS
         and tuple(tuple(s.get("xy_cm", ())) for s in sites) == SITE_XY
         and all(s.get("status") == "REJECTED" for s in sites),
         "Site location, order or rejection drift")


def safe_session_root(root: Path, session: str) -> Path:
    need(type(session) is str and INSTANCE_PATTERN.fullmatch(session) is not None,
         "Invalid session path")
    return root / "sessions" / session


def existing_abslog_only(session: Path) -> None:
    need(session.is_dir() and not session.is_symlink(), "Owned new session missing")
    entries = list(session.iterdir())
    need(all(entry.name == "editor.log" and entry.is_file() and not entry.is_symlink()
             for entry in entries), "Old/unknown data in a new Editor session")


def normalize_capture_result(status: dict) -> bool:
    """No historical screenshot or HTTP OK can count as a LIVE result."""
    return (
        type(status) is dict
        and status.get("status") == "LIVE_VIDEO_VERIFIED"
        and status.get("owner_handoff") is True
        and status.get("browser_frames_received") is True
        and status.get("post_job_alive") is True
        and status.get("placement") is False
    )
