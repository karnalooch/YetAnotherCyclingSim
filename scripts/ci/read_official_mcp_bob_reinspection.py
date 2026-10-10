"""One-off, read-only comparison of the fixed failed #384 retained BOB bundle.

No CLI inputs, Editor, transport, producer or admission. The trusted Windows
harness supplies only the fresh output root and its executing revision.
"""

from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import types
from typing import Any

ROOT = Path(__file__).absolute().parents[2]
HELPER = "scripts/ci/read_official_mcp_bob_reinspection.py"
OLD_SHA = "4fe6c4f50db0e7a8b2883429209dd193e01159dd"
OLD_RUN = "38025560494-1"
OLD_ROOT = Path("D:/yacs/runner/_work/s384/38025560494-1")
OLD_ARTIFACT = Path(
    "D:/yacs/runner/_work/YetAnotherCyclingSim/YetAnotherCyclingSim/"
    "_official-mcp-native-probe/Saved/RuntimeProof/OfficialMcpBobSession/38025560494-1"
)
PROOF_ROOT = OLD_ROOT / "Saved/RuntimeProof/OfficialMcpBob"
HOST_SHA = "5f0d9cfae844b00d43dbcac7cd3c4e21103423439db1bf6fcc45f0212f4465f0"
BUNDLE_NAMES = (
    "capture-proof.json",
    "direct-inspection.json",
    "native-samples.json",
    "proof.json",
    "receipt.json",
    "result.json",
)
# Exact committed 4fe6 domain inventory, authenticated again against the old
# host-bound context before importing any retained repository module.
SOURCES = {
    "scripts/worldgen/bob_mcp_inspection.py": "3469fa92a013f1be0bf0a843a3fadd39db2122a96f4b844984106a553c8841e8",
    "scripts/worldgen/bob_terrain_fit_inspector.py": "0a50f499ce34a35d528822a6562c8d8508347c09324dcdd09460332aee5a7ebf",
    "scripts/worldgen/adaptive_terrain_solver.py": "bf1ec4d19e568adc79e4db23bb53c4d5f4e266cbf11a895766db9a190bd4429c",
    "worldgen/terrain/adaptive_terrain_policy.json": "48104642fc6743b0cb5debada0adf7536772578e5124c0a94cd43716a45deea0",
    "scripts/assets/prepare_ma2141_road_preview.py": "0d2a497d6d815d24b466123b03d74ee5020d2f8147396fbc89ab5724f7e35654",
    "scripts/ue/ma2141_road_preview.py": "8cd6495afc9d0b28c121f6a0bb6bd27bc6eecf1898b91b55be9e69d486a92986",
    "scripts/ue/bob_road_earthworks_cut.py": "528718ff75827a3d2a8338f42bafbae898d3ba5df1d86285a6e041dc360ecb62",
    "scripts/ue/sa_calobra_geometry_collision_witness.py": "c664ca1eb3a6852b4223b9f7e20e5add7e7f9bde46f5fdf4922b593a85424c83",
}
FALSE_FLAGS = (
    "earthworks_authoring_permitted",
    "geometry_repair_executed",
    "road_admitted",
    "eligible_for_learning",
)
UNANCHORED = "CURRENT_OBSERVED_RETAINED_BYTES; NO_ORIGINAL_HOST_HASH"


def _require(value: Any, message: str) -> None:
    if not value:
        raise ValueError(message)


def _safe(path: Path) -> None:
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        _require(
            not stat.S_ISLNK(info.st_mode)
            and not getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400),
            "The fixed reinspection refuses symlinks and junctions",
        )


def _read(
    path: Path, limit: int, budget: list[int] | None = None
) -> tuple[bytes, dict]:
    _safe(path)
    before = path.stat()
    _require(
        stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit,
        "A fixed diagnostic input is not a bounded nonempty regular file",
    )
    if budget is not None:
        budget[0] += before.st_size
        _require(budget[0] <= 64 * 1024 * 1024, "The six bundle files exceed 64MiB")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    _safe(path)
    after = path.stat()
    identity = lambda info: (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )
    _require(
        identity(before) == identity(after) and len(raw) == before.st_size,
        "A retained diagnostic input changed during its bounded read",
    )
    return raw, {
        "path": str(path),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _object(raw: bytes) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            _require(key not in value, "A diagnostic JSON object has duplicate fields")
            value[key] = item
        return value

    def reject_constant(_):
        raise ValueError("A diagnostic JSON contains a nonfinite number")

    value = json.loads(
        raw.decode("utf-8-sig"),
        object_pairs_hook=unique,
        parse_constant=reject_constant,
    )
    _require(isinstance(value, dict), "A diagnostic JSON root must be an object")
    return value


def _git(root: Path, *args: str) -> bytes:
    # Only the two fixed trusted roots and literal HEAD/source blobs are read.
    output = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(root),
            *args,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
    ).stdout
    _require(len(output) <= 1024 * 1024, "A fixed Git diagnostic exceeds 1MiB")
    return output


def _anchored(identity: dict, expected: Any) -> dict:
    result = {**identity, "identity_scope": UNANCHORED}
    if expected is not None:
        _require(
            isinstance(expected, dict) and expected == identity,
            "A retained input differs from its original host identity",
        )
        result["identity_scope"] = "MATCHES_ORIGINAL_HOST_RECEIPT"
    return result


def _differences(saved: Any, repeated: Any) -> dict:
    paths: list[str] = []
    nodes = 0
    truncated = False
    pending = [("$", saved, repeated, 0)]
    while pending:
        if nodes >= 50000 or len(paths) >= 16:
            truncated = True
            break
        path, left, right, depth = pending.pop()
        nodes += 1
        if depth > 12:
            truncated = True
            continue
        if isinstance(left, dict) and isinstance(right, dict):
            keys = sorted(set(left) | set(right))
            if len(keys) + len(pending) > 50000:
                truncated = True
                continue
            for key in reversed(keys):
                child = path + "/" + str(key).replace("~", "~0").replace("/", "~1")
                if key not in left or key not in right:
                    paths.append(child[:512])
                    if len(paths) >= 16:
                        truncated = True
                        break
                else:
                    pending.append((child, left[key], right[key], depth + 1))
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                paths.append(path[:512] + "/length")
            if len(left) + len(pending) > 50000:
                truncated = True
                continue
            for index in reversed(range(min(len(left), len(right)))):
                pending.append(
                    (path + "/" + str(index), left[index], right[index], depth + 1)
                )
        elif left != right:
            paths.append(path[:512])
    return {"field_paths": paths[:16], "truncated": truncated, "nodes_visited": nodes}


def _rms(value: dict) -> dict:
    number = value.get("rms_required_adjustment_m")
    _require(
        type(number) in (int, float) and math.isfinite(number), "RMS is not finite"
    )
    return {"repr": repr(number), "float_hex": float(number).hex()}


def main() -> None:
    _require(
        os.name == "nt" and len(sys.argv) == 1 and sys.dont_write_bytecode,
        "The fixed diagnostic requires owned Windows Python -B without CLI arguments",
    )
    run = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    current_sha = os.environ.get("YACS_BOB_REINSPECTION_EXPECTED_HEAD", "")
    _require(
        bool(re.fullmatch(r"[1-9][0-9]{0,19}", run))
        and bool(re.fullmatch(r"[1-9][0-9]{0,5}", attempt))
        and bool(re.fullmatch(r"[0-9a-f]{40}", current_sha)),
        "Current owned run/source is absent",
    )
    expected_root = OLD_ARTIFACT.parents[3]
    _require(
        ROOT == expected_root,
        "The diagnostic must execute in its fixed Actions checkout",
    )
    artifact = ROOT / "Saved/RuntimeProof/OfficialMcpBobSession" / (run + "-" + attempt)
    _require(
        os.environ.get("YACS_BOB_REINSPECTION_ARTIFACT_ROOT", "") == str(artifact)
        and artifact != OLD_ARTIFACT,
        "The diagnostic output must be the fresh owned run",
    )
    _safe(artifact)
    _require(
        _git(ROOT, "rev-parse", "HEAD").decode().strip() == current_sha,
        "The executing diagnostic has a different HEAD",
    )
    helper_raw, helper_identity = _read(ROOT / HELPER, 1024 * 1024)
    _require(
        helper_raw == _git(ROOT, "show", current_sha + ":" + HELPER),
        "The executing diagnostic differs from its committed source",
    )
    host_raw, host_identity = _read(
        OLD_ARTIFACT / "accepted-session-build.json", 1024 * 1024
    )
    _require(
        host_identity["size_bytes"] == 445099 and host_identity["sha256"] == HOST_SHA,
        "The original failed host raw anchor differs",
    )
    host = _object(host_raw)  # Authenticate the immutable raw bytes BEFORE parsing.
    _require(
        host.get("schema_version") == 1
        and host.get("exact_sha") == OLD_SHA
        and host.get("run") == "38025560494"
        and host.get("attempt") == "1"
        and host.get("status") == "BLOCKED"
        and host.get("session_root") == str(OLD_ROOT),
        "The pinned original failure source/run/root differs",
    )
    context_raw, context_identity = _read(
        PROOF_ROOT / "session-context.json", 1024 * 1024
    )
    context_anchor = _anchored(context_identity, host["proof_files"]["session_context"])
    context = _object(context_raw)
    _require(
        set(context)
        == {
            "schema_version",
            "exact_sha",
            "source_sha256",
            "profile_sha256",
            "profile_source_sha",
            "consumer_source_sha",
            "consumer_assets",
            "landscape",
        }
        and context["schema_version"] == 1
        and context["exact_sha"] == OLD_SHA,
        "The original operation context contract differs",
    )
    marker_raw, marker_identity = _read(
        PROOF_ROOT / "transport-context.json", 1024 * 1024
    )
    marker_anchor = _anchored(marker_identity, host["proof_files"]["transport_context"])
    marker = _object(marker_raw)
    _require(
        set(marker)
        == {
            "schema_version",
            "exact_sha",
            "project_root",
            "owned_editor_pid",
            "source_sha256",
            "session_context_sha256",
        }
        and marker["schema_version"] == 1
        and marker["exact_sha"] == OLD_SHA
        and marker["project_root"] == str(OLD_ROOT)
        and marker["owned_editor_pid"] == 29376
        and marker["session_context_sha256"] == context_identity["sha256"],
        "The pinned transport context differs",
    )
    _require(
        _git(OLD_ROOT, "rev-parse", "HEAD").decode().strip() == OLD_SHA,
        "The retained source checkout has a different HEAD",
    )
    _require(
        isinstance(context["source_sha256"], dict)
        and all(
            context["source_sha256"].get(path) == digest
            and marker["source_sha256"].get(path) == digest
            for path, digest in SOURCES.items()
        ),
        "The domain sources differ from the original host-bound source context",
    )
    source_bytes = {}
    for relative, digest in SOURCES.items():
        raw, identity = _read(OLD_ROOT / relative, 1024 * 1024)
        _require(
            identity["sha256"] == digest
            and raw == _git(OLD_ROOT, "show", OLD_SHA + ":" + relative),
            "A retained domain source differs from exact committed 4fe6 bytes",
        )
        source_bytes[relative] = raw
    # Namespace packages must not acquire an extra executable initializer.
    for relative in ("scripts/__init__.py", "scripts/worldgen/__init__.py"):
        _require(
            not (OLD_ROOT / relative).exists(),
            "Unexpected retained package initializer",
        )
    _require(
        not any(
            name == "scripts" or name.startswith("scripts.") for name in sys.modules
        ),
        "Repository modules were imported before fixed source verification",
    )
    # Fixed namespace paths exclude an installed package initializer. Load only
    # these three authenticated pure source byte strings; -B alone would still
    # allow a stale retained .pyc to execute. No dynamic operation/producer input.
    for name in ("scripts", "scripts.worldgen"):
        package = types.ModuleType(name)
        package.__package__ = name
        package.__path__ = [str(OLD_ROOT / name.replace(".", "/"))]
        package.__spec__ = importlib.machinery.ModuleSpec(
            name, loader=None, is_package=True
        )
        sys.modules[name] = package
        if "." in name:
            parent, child = name.rsplit(".", 1)
            setattr(sys.modules[parent], child, package)
    for name in (
        "scripts.worldgen.adaptive_terrain_solver",
        "scripts.worldgen.bob_terrain_fit_inspector",
        "scripts.worldgen.bob_mcp_inspection",
    ):
        relative = name.replace(".", "/") + ".py"
        source_path = OLD_ROOT / relative
        spec = importlib.util.spec_from_file_location(name, source_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        parent, child = name.rsplit(".", 1)
        setattr(sys.modules[parent], child, module)
        exec(compile(source_bytes[relative], str(source_path), "exec"), module.__dict__)
    adapter = sys.modules["scripts.worldgen.bob_mcp_inspection"]
    _require(
        tuple(adapter.SOURCE_PATHS) == tuple(SOURCES),
        "The retained adapter source inventory differs",
    )
    for name in (
        "scripts.worldgen.bob_mcp_inspection",
        "scripts.worldgen.bob_terrain_fit_inspector",
        "scripts.worldgen.adaptive_terrain_solver",
    ):
        module = sys.modules[name]
        _require(
            Path(module.__file__).absolute()
            == OLD_ROOT / (name.replace(".", "/") + ".py"),
            "A pure domain module was imported outside the fixed retained checkout",
        )
    budget = [0]
    raw_bundle, bundle_identities = {}, {}
    for name in BUNDLE_NAMES:
        raw, identity = _read(PROOF_ROOT / "bundle" / name, 32 * 1024 * 1024, budget)
        raw_bundle[name] = raw
        bundle_identities[name] = _anchored(
            identity, host.get("bundle_files", {}).get(name)
        )
    values = {name: _object(raw) for name, raw in raw_bundle.items()}
    samples = values["native-samples.json"]
    capture = values["capture-proof.json"]
    _require(
        samples.get("exact_sha") == OLD_SHA
        and samples.get("source_sha256") == SOURCES
        and capture.get("exact_sha") == OLD_SHA
        and capture.get("source_sha256") == context["source_sha256"]
        and capture.get("context_sha256") == context_identity["sha256"]
        and capture.get("native_sample_sha256")
        == bundle_identities["native-samples.json"]["sha256"]
        and capture.get("sample_count") == len(samples["samples"]),
        "The retained sample/capture provenance differs",
    )
    saved, proof, receipt, direct = (
        values[name]
        for name in (
            "result.json",
            "proof.json",
            "receipt.json",
            "direct-inspection.json",
        )
    )
    _require(
        saved.get("exact_sha")
        == proof.get("exact_sha")
        == receipt.get("exact_sha")
        == OLD_SHA
        and saved.get("role") == "INSPECTOR_ONLY"
        and saved.get("status") in {"REVIEW_REQUIRED", "INSPECTION_INCOMPLETE"}
        and all(
            saved.get(flag) is False and capture.get(flag) is False
            for flag in FALSE_FLAGS
        )
        and receipt["result"]["sha256"] == bundle_identities["result.json"]["sha256"]
        and receipt["proof"]["sha256"] == bundle_identities["proof.json"]["sha256"],
        "The retained domain flags or producer receipt hashes differ",
    )
    repeated = adapter.inspect_bob_request(
        {
            "exact_sha": OLD_SHA,
            "native_samples_path": "native-samples.json",
            "native_samples_sha256": bundle_identities["native-samples.json"]["sha256"],
            "source_sha256": SOURCES,
        },
        evidence_root=PROOF_ROOT / "bundle",
        repository_root=OLD_ROOT,
    )
    # A fresh receipt timestamp is intentionally separate; result/proof equality
    # uses the exact existing client conjunction with no normalization/tolerance.
    result_equal = repeated["result"] == saved
    proof_equal = repeated["proof"] == proof
    editor_raw, editor_identity = _read(
        OLD_ARTIFACT / "owned-editor.log", 32 * 1024 * 1024
    )
    editor_anchor = _anchored(
        editor_identity, host["proof_files"].get("failure/owned-editor.log")
    )
    versions = []
    for index, line in enumerate(
        editor_raw.decode("utf-8", errors="replace").splitlines(), 1
    ):
        observed = re.search(
            r"LogPython:\s*(?:Using Python|Python version)\s*[:=]?\s*([0-9]+\.[0-9]+\.[0-9]+)",
            line,
            re.IGNORECASE,
        )
        if observed:
            versions.append(
                {
                    "line": index,
                    "text": observed.group(0)[:512],
                    "identity_scope": editor_anchor["identity_scope"],
                }
            )
            if len(versions) == 2:
                break
    diagnostics = {
        "schema_version": 1,
        "exact_sha": current_sha,
        "source_only": True,
        "previous_run": OLD_RUN,
        "previous_exact_sha": OLD_SHA,
        "original_failed_status": host["status"],
        "status": "FIXED_RETAINED_DOMAIN_COMPARISON_OBSERVED; NO_NATIVE_ADMISSION",
        "editor_launched": False,
        "compile_performed": False,
        "listener_started": False,
        "official_mcp_transport_verified": False,
        "official_mcp_admitted": False,
        "native_bob_capture_verified": False,
        "native_automation_verified": False,
        "persistent_world_mutation": False,
        "performance_pass": False,
        "helper_source": helper_identity,
        "original_host": host_identity,
        "context": context_anchor,
        "transport_context": marker_anchor,
        "bundle_files": bundle_identities,
        "bundle_bytes_read": budget[0],
        "source_sha256": SOURCES,
        "host_python_version": list(sys.version_info[:3]),
        "editor_log": editor_anchor,
        "editor_python_version_lines": versions,
        "saved_direct_result_equal": saved == direct,
        "saved_reinspection_result_equal": result_equal,
        "saved_reinspection_proof_equal": proof_equal,
        "original_client_parity_conjunction_now": result_equal and proof_equal,
        "result_differences": _differences(saved, repeated["result"]),
        "proof_differences": _differences(proof, repeated["proof"]),
        "rms": {
            "saved": _rms(saved),
            "direct": _rms(direct),
            "reinspection": _rms(repeated["result"]),
        },
        "sample_count": len(samples["samples"]),
        "input_sha256": bundle_identities["native-samples.json"]["sha256"],
        "proof_input_paths_equal": proof["input"]["path"]
        == repeated["proof"]["input"]["path"],
        "saved_proof_input": proof["input"],
        "reinspection_proof_input": repeated["proof"]["input"],
        "saved_output_sha256": proof["output"]["sha256"],
        "reinspection_output_sha256": repeated["proof"]["output"]["sha256"],
        "saved_direct_sha256": proof["direct_invocation_sha256"],
        "reinspection_direct_sha256": repeated["proof"]["direct_invocation_sha256"],
    }
    final_budget = [0]
    for name, identity in bundle_identities.items():
        _, after = _read(PROOF_ROOT / "bundle" / name, 32 * 1024 * 1024, final_budget)
        _require(
            all(
                after[key] == identity[key] for key in ("path", "size_bytes", "sha256")
            ),
            "A retained bundle input changed during pure reinspection",
        )
    diagnostics["bundle_bytes_read_final_pass"] = final_budget[0]
    for path, raw, limit in (
        (OLD_ARTIFACT / "accepted-session-build.json", host_raw, 1024 * 1024),
        (PROOF_ROOT / "session-context.json", context_raw, 1024 * 1024),
        (PROOF_ROOT / "transport-context.json", marker_raw, 1024 * 1024),
    ):
        _require(
            _read(path, limit)[0] == raw,
            "A retained anchor/context changed during reinspection",
        )
    _require(
        _git(OLD_ROOT, "rev-parse", "HEAD").decode().strip() == OLD_SHA,
        "The retained HEAD changed during reinspection",
    )
    encoded = (json.dumps(diagnostics, sort_keys=True, allow_nan=False) + "\n").encode()
    _require(len(encoded) <= 1024 * 1024, "The fixed diagnostic exceeds 1MiB")
    _safe(artifact)
    with (artifact / "fixed-bob-reinspection.json").open("xb") as stream:
        stream.write(encoded)
    summary = {
        key: diagnostics[key]
        for key in (
            "status",
            "previous_run",
            "previous_exact_sha",
            "original_failed_status",
            "host_python_version",
            "editor_python_version_lines",
            "saved_direct_result_equal",
            "saved_reinspection_result_equal",
            "saved_reinspection_proof_equal",
            "original_client_parity_conjunction_now",
            "result_differences",
            "proof_differences",
            "rms",
            "sample_count",
            "input_sha256",
            "proof_input_paths_equal",
            "saved_proof_input",
            "reinspection_proof_input",
            "saved_output_sha256",
            "reinspection_output_sha256",
            "saved_direct_sha256",
            "reinspection_direct_sha256",
            "source_only",
            "official_mcp_admitted",
        )
    }
    console = json.dumps(summary, sort_keys=True, allow_nan=False)
    _require(
        len(console.encode()) <= 16 * 1024,
        "The selected diagnostic console exceeds 16KiB",
    )
    print("FIXED_BOB_REINSPECTION " + console)


if __name__ == "__main__":
    main()
