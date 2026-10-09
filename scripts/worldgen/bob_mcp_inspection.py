"""Read-only BOB domain delegation prepared for the bounded official MCP spike.

This is neither an MCP server nor a registered Epic tool. Native sample exports
use the five fields assembled by ``measure_smooth_terrain_fit`` in
``scripts/ue/bob_road_earthworks_cut.py``. That producer currently does not save
the raw samples, so an aggregate terrain-fit report cannot substitute for them.
An input's declared native provenance requires separate host proof; this adapter
only proves hash-bound domain execution and repeatability.
"""

from __future__ import annotations

import ast
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Mapping

from scripts.worldgen import bob_terrain_fit_inspector
from scripts.worldgen.bob_terrain_fit_inspector import inspect_terrain_fit


ROOT = Path(__file__).resolve().parents[2]
ADAPTER = "scripts/worldgen/bob_mcp_inspection.py"
INSPECTOR = "scripts/worldgen/bob_terrain_fit_inspector.py"
POLICY = "worldgen/terrain/adaptive_terrain_policy.json"
CONTACT_PRODUCER = "scripts/assets/prepare_ma2141_road_preview.py"
SOURCE_PATHS = (
    ADAPTER,
    INSPECTOR,
    "scripts/worldgen/adaptive_terrain_solver.py",
    POLICY,
    CONTACT_PRODUCER,
    "scripts/ue/ma2141_road_preview.py",
    "scripts/ue/bob_road_earthworks_cut.py",
)
NATIVE_PRODUCER = "scripts.ue.bob_road_earthworks_cut.measure_smooth_terrain_fit"
NATIVE_SAMPLE_SOURCE = "unreal.SystemLibrary.line_trace_single"
SAMPLE_FIELDS = {
    "station_m", "lateral_m", "local_xy_m", "road_surface_z_m", "landscape_z_m",
}
REQUEST_FIELDS = {
    "exact_sha", "native_samples_path", "native_samples_sha256", "source_sha256",
}
ENVELOPE_FIELDS = {
    "schema_version", "exact_sha", "region_id", "producer", "sample_source",
    "geometry_inspection_view", "source_sha256", "samples",
}
FALSE_FLAGS = (
    "earthworks_authoring_permitted", "geometry_repair_executed",
    "road_admitted", "eligible_for_learning",
)
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
MAX_INPUT_BYTES = 32 * 1024 * 1024


def canonical_json_bytes(value: Any) -> bytes:
    """Encoding used by the returned artifact hashes, without changing inputs."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _fields(value: Any, expected: set[str], name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError(f"{name} must contain exactly {sorted(expected)}")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _json(raw: bytes) -> Any:
    def reject_constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                      parse_constant=reject_constant)


def _read_bound_file(root: Path, relative: str, expected_sha256: str) -> tuple[Path, bytes]:
    if (not isinstance(relative, str) or not relative
            or "\\" in relative or ":" in relative or "\x00" in relative):
        raise ValueError("evidence path must be an explicit relative path")
    path = Path(relative)
    if path.is_absolute() or any(part in {".", ".."} for part in relative.split("/")):
        raise ValueError("evidence path is outside the admitted root")
    if not isinstance(expected_sha256, str) or not SHA256.fullmatch(expected_sha256):
        raise ValueError("expected SHA256 must be lowercase hexadecimal")
    root = Path(root).absolute()
    candidate = root / path
    for ancestor in (candidate, *candidate.parents):
        try:
            metadata = ancestor.lstat()
        except OSError as exc:
            raise ValueError("missing evidence path") from exc
        if (stat.S_ISLNK(metadata.st_mode)
                or getattr(metadata, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
            raise ValueError("symlink/reparse evidence paths are not admitted")
    if root.resolve() not in candidate.resolve().parents or not candidate.is_file():
        raise ValueError("missing or path-escaping evidence")
    before = candidate.stat()
    if before.st_size > MAX_INPUT_BYTES:
        raise ValueError("evidence exceeds the bounded input size")
    with candidate.open("rb") as handle:
        raw = handle.read(MAX_INPUT_BYTES + 1)
    after = candidate.stat()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("evidence exceeds the bounded input size")
    identity = lambda info: (info.st_dev, info.st_ino, info.st_size,
                             info.st_mtime_ns, info.st_ctime_ns)
    if identity(before) != identity(after) or len(raw) != before.st_size:
        raise ValueError("evidence changed while being read")
    if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise ValueError("materialized evidence required, not a Git LFS pointer")
    if _digest(raw) != expected_sha256:
        raise ValueError(f"stale SHA256 for {relative}")
    return candidate, raw


def _git(root: Path, *arguments: str) -> bytes:
    try:
        return subprocess.run(["git", "-C", str(root), *arguments], check=True,
                              capture_output=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("repository SHA/source verification unavailable") from exc


def _sources(root: Path, exact_sha: str, expected: Any) -> dict[str, bytes]:
    _fields(expected, set(SOURCE_PATHS), "source_sha256")
    # The executing inspector belongs to this checkout. A caller cannot replace
    # repository_root with another tree while retaining this imported function.
    if root.resolve() != ROOT.resolve():
        raise ValueError("repository root differs from the executing domain code")
    if _git(root, "rev-parse", "HEAD").decode().strip() != exact_sha:
        raise ValueError("exact_sha does not identify the current repository HEAD")
    for relative, executed_path in (
        (ADAPTER, Path(__file__)), (INSPECTOR, Path(bob_terrain_fit_inspector.__file__)),
    ):
        if _digest(executed_path.read_bytes()) != expected[relative]:
            raise ValueError(f"executing domain source hash mismatch: {relative}")
    sources = {}
    for relative in SOURCE_PATHS:
        _, raw = _read_bound_file(root, relative, expected[relative])
        if raw != _git(root, "show", f"{exact_sha}:{relative}"):
            raise ValueError(f"domain source differs from exact_sha: {relative}")
        sources[relative] = raw
    return sources


def _policy_arguments(sources: Mapping[str, bytes]) -> dict[str, float]:
    # Read the fixed approved caller's construction parameter, without importing
    # the asset producer or accepting engineering thresholds from the request.
    assignments = [node.value for node in ast.parse(sources[CONTACT_PRODUCER]).body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name)
                           and target.id == "PAVEMENT_THICKNESS_M"
                           for target in node.targets)]
    if len(assignments) != 1 or not isinstance(assignments[0], ast.Constant):
        raise ValueError("approved pavement contact parameter is unavailable")
    contact = assignments[0].value
    policy = _json(sources[POLICY])
    structure = policy["thresholds"]["retaining_cut_fill_m"]
    for value in (contact, structure):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("invalid pinned terrain-fit thresholds")
    if not 0 < contact < structure:
        raise ValueError("invalid pinned terrain-fit thresholds")
    return {"contact_band_max_m": float(contact),
            "structure_review_threshold_m": float(structure)}


def inspect_bob_request(
    request: Mapping[str, Any], *, evidence_root: Path, repository_root: Path = ROOT,
) -> dict[str, Any]:
    """Delegate one explicit, hash-bound sample export and return result/proof/receipt.

    The integration selects the admitted evidence root; it is not a tool argument.
    Request fields are ``REQUEST_FIELDS``. The JSON envelope is
    ``ENVELOPE_FIELDS`` with producer/source constants above, the current exact
    SHA, region ``sa_calobra``, a before/after geometry inspection view, source
    hashes and a nonempty list of original five-field native sample rows.
    No files, world geometry, learning state or admission decisions are written.
    """
    _fields(request, REQUEST_FIELDS, "BOB inspection request")
    exact_sha = request["exact_sha"]
    if not isinstance(exact_sha, str) or not SHA40.fullmatch(exact_sha):
        raise ValueError("exact_sha must be lowercase SHA40")
    root = Path(repository_root)
    sources = _sources(root, exact_sha, request["source_sha256"])
    sample_path, raw = _read_bound_file(
        evidence_root, request["native_samples_path"], request["native_samples_sha256"],
    )
    envelope = _json(raw)
    _fields(envelope, ENVELOPE_FIELDS, "native sample envelope")
    if (type(envelope["schema_version"]) is not int or envelope["schema_version"] != 1
            or envelope["exact_sha"] != exact_sha or envelope["region_id"] != "sa_calobra"
            or envelope["producer"] != NATIVE_PRODUCER
            or envelope["sample_source"] != NATIVE_SAMPLE_SOURCE
            or envelope["source_sha256"] != request["source_sha256"]
            or not isinstance(envelope["geometry_inspection_view"], str)
            or envelope["geometry_inspection_view"] not in {
                "road-geometry-inspection-before", "road-geometry-inspection-after",
            }):
        raise ValueError("native sample identity/source binding mismatch")
    samples = envelope["samples"]
    if not isinstance(samples, list) or not samples:
        raise ValueError("nonempty native sample rows required; aggregate reports are insufficient")
    for sample in samples:
        _fields(sample, SAMPLE_FIELDS, "native sample")
    arguments = {"exact_sha": exact_sha, **_policy_arguments(sources),
                 "geometry_inspection_view": envelope["geometry_inspection_view"]}
    result = inspect_terrain_fit(deepcopy(samples), **arguments)
    direct = bob_terrain_fit_inspector.inspect_terrain_fit(deepcopy(samples), **arguments)
    if result != direct:
        raise ValueError("BOB delegation differs from direct invocation")
    if (result.get("role") != "INSPECTOR_ONLY"
            or result.get("status") not in {"REVIEW_REQUIRED", "INSPECTION_INCOMPLETE"}
            or result.get("inspector_sha256") != request["source_sha256"][INSPECTOR]
            or any(result.get(flag) is not False for flag in FALSE_FLAGS)):
        raise ValueError("BOB result violated the read-only domain contract")
    # Recheck the original bytes and fixed source inventory after delegation.
    _read_bound_file(evidence_root, request["native_samples_path"], request["native_samples_sha256"])
    _sources(root, exact_sha, request["source_sha256"])
    result_hash = _digest(canonical_json_bytes(result))
    proof = {
        "schema_version": 1, "contract": "bob-read-only-domain-delegation-v1",
        "exact_sha": exact_sha, "input": {"path": str(sample_path),
            "sha256": request["native_samples_sha256"], "size_bytes": len(raw)},
        "source_sha256": dict(request["source_sha256"]),
        "adapter_sha256": request["source_sha256"][ADAPTER],
        "call": {"function": "scripts.worldgen.bob_terrain_fit_inspector.inspect_terrain_fit",
                 "arguments": arguments, "sample_count": len(samples)},
        "output": {"artifact": "result", "sha256": result_hash,
                   "encoding": "canonical-json-utf8"},
        "direct_invocation_sha256": _digest(canonical_json_bytes(direct)),
        "direct_invocation_matches": True, "input_bytes_unchanged": True,
        "source_bytes_unchanged": True,
    }
    receipt = {
        "schema_version": 1, "exact_sha": exact_sha,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "domain_role": result["role"], "domain_status": result["status"],
        "result": {"artifact": "result", "sha256": result_hash},
        "proof": {"artifact": "proof", "sha256": _digest(canonical_json_bytes(proof))},
        "mutation_scope": "NONE", "evidence_scope": "DOMAIN_DELEGATION_ONLY",
        "native_capture_verified": False, "official_mcp_verified": False,
        "persistent_content_verified": False,
        **{flag: result[flag] for flag in FALSE_FLAGS},
    }
    return {"result": result, "proof": proof, "receipt": receipt}
