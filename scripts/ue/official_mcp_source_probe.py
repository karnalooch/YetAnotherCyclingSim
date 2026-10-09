"""Collect bounded installed Epic source evidence without activating Unreal MCP.

This filesystem probe records declarations for a later human/API review. It
does not establish runtime schemas, restrict a server, execute tools or admit
the #384 spike. Epic source excerpts belong only in ignored Saved artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any


EXPECTED_ENGINE = (5, 8, 2, 56702186)
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_SOURCE_FILES = 4096
MAX_DEPTH = 12
MAX_EXCERPT_LINES = 2400
PLUGIN_ROOTS = {
    "ModelContextProtocol": "Engine/Plugins/Experimental/ModelContextProtocol",
    "ToolsetRegistry": "Engine/Plugins/Experimental/ToolsetRegistry",
}
TOOLSET_NAMES = {
    "AutomationTestToolset", "EditorToolset", "SceneToolset", "ActorToolset",
    "ObjectToolset", "SceneTools", "ActorTools", "ObjectTools",
}
SOURCE_SUFFIXES = {".h", ".cpp", ".py", ".ini", ".cs"}
INTEREST = re.compile(
    r"\b(?:AllowedNames|BlockedNames|SetNameFilters|IsToolEnabled|ExecuteTool|"
    r"RegisterToolset|GetToolsetJsonSchema\w*|OnRefreshTools|RefreshTools|"
    r"DiscoverTests|ListTests|RunTests|GetTestStatus|GetTestResults|StopTests|"
    r"SceneTools|ActorTools|ObjectTools|ModelContextProtocolSettings|"
    r"ToolsetRegistrySettings|ToolsetRegistrySubsystem|AddTool|StartServer|"
    r"DefaultBindAddress|bEnableToolSearch|AutoStartServer|ServerPort|ServerUrl)\b"
    r"|\b(?:class|def)\s+|@toolset_registry\.tool_call|AICallable|AIIgnore|"
    r"(?:list_toolsets|describe_toolset|call_tool|require_editable|tool_call)"
)


class ProbeBlocked(ValueError):
    """A bounded evidence collection invariant was not satisfied."""


class SourceBudgetExceeded(ProbeBlocked):
    """Global source collection must stop before another file is read."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_path(root: Path, path: Path) -> Path:
    """Reject traversal, symlinks and Windows junction/reparse-point escapes."""
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise ProbeBlocked("PATH_OUTSIDE_SCOPE") from exc
    if ".." in relative.parts:
        raise ProbeBlocked("PATH_TRAVERSAL")
    cursor = root
    for part in ("", *relative.parts):
        if part:
            cursor = cursor / part
        info = cursor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ProbeBlocked(f"LINK_OR_REPARSE_POINT: {cursor.name}")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ProbeBlocked("PATH_OUTSIDE_SCOPE")
    return path


def bounded_files(root: Path, *, descriptors_only: bool = False) -> list[Path]:
    """Walk one approved tree, with fixed entry/depth limits and no link follows."""
    result: list[Path] = []
    count = 0

    def visit(directory: Path, depth: int) -> None:
        nonlocal count
        if depth > MAX_DEPTH:
            raise ProbeBlocked("SOURCE_TREE_DEPTH_LIMIT")
        checked_path(root, directory)
        with os.scandir(directory) as entries:
            bounded_entries = []
            for entry in entries:
                count += 1
                if count > MAX_ENTRIES:
                    raise ProbeBlocked("SOURCE_TREE_ENTRY_LIMIT")
                bounded_entries.append(entry)
            for entry in sorted(bounded_entries, key=lambda item: item.name):
                path = checked_path(root, Path(entry.path))
                if entry.is_dir(follow_symlinks=False):
                    if descriptors_only and entry.name in {
                        "Source", "Content", "Binaries", "Intermediate", "Resources",
                        "Build", "Config", "ThirdParty",
                    }:
                        continue
                    visit(path, depth + 1)
                elif entry.is_file(follow_symlinks=False):
                    if not descriptors_only or path.suffix == ".uplugin":
                        result.append(path)

    visit(root, 0)
    return sorted(result)


def read_bounded(root: Path, path: Path) -> bytes:
    checked_path(root, path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
        raise ProbeBlocked(f"UNSUPPORTED_OR_OVERSIZED_FILE: {path.name}")
    with path.open("rb") as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    after = path.stat()
    if len(data) > MAX_FILE_BYTES:
        raise ProbeBlocked(f"OVERSIZED_FILE: {path.name}")
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ProbeBlocked(f"SOURCE_CHANGED_DURING_READ: {path.name}")
    return data


def selected_excerpts(data: bytes, budget: int) -> tuple[list[dict[str, Any]], int]:
    """Retain concise contexts, never a wholesale copy of an Epic source file."""
    lines = data.decode("utf-8-sig").splitlines()
    spans: list[tuple[int, int]] = []
    for index, line in enumerate(lines):
        if INTEREST.search(line):
            start, end = max(0, index - 1), min(len(lines), index + 9)
            if spans and start <= spans[-1][1]:
                # A single selected block is capped even if many adjacent lines match.
                end = min(end, spans[-1][0] + 36)
                spans[-1] = (spans[-1][0], max(spans[-1][1], end))
            elif len(spans) < 12:
                spans.append((start, min(end, start + 36)))
    excerpts = []
    used = 0
    for start, end in spans:
        end = min(end, start + budget - used)
        if end <= start:
            break
        excerpts.append({
            "start_line": start + 1,
            "end_line": end,
            "text": "\n".join(line[:600] for line in lines[start:end]),
        })
        used += end - start
    return excerpts, used


def collect(
    *, engine_root: Path, project: Path, repository_root: Path,
    expected_sha: str, actual_sha: str, host_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "issue": 384,
        "status": "BLOCKED",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "exact_sha": expected_sha,
        "actual_sha": actual_sha,
        "probe": "installed_filesystem_only",
        "engine_root": str(engine_root),
        "project": str(project),
        "inventory": [],
        "plugins": {},
        "blockers": [],
        "running_editor": host_context or {"status": "UNVERIFIED"},
        "guard_parity_verified": False,
        "runtime_schema_verified": False,
        "mcp_server_started": False,
        "plugin_activation_performed": False,
        "official_mcp_admitted": False,
        "persistent_content_mutation_performed": False,
        "performance_status": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }
    total_bytes = 0
    remaining_lines = MAX_EXCERPT_LINES
    role_lines = {"ToolsetRegistry": 650, "ModelContextProtocol": 850,
                  "AutomationTestToolset": 350}

    def record(path: Path, role: str) -> bytes:
        nonlocal total_bytes, remaining_lines
        if len(receipt["inventory"]) >= MAX_SOURCE_FILES:
            raise SourceBudgetExceeded("SOURCE_FILE_COUNT_LIMIT")
        checked_path(engine_root, path)
        if total_bytes + path.stat().st_size > MAX_TOTAL_BYTES:
            raise SourceBudgetExceeded("SOURCE_TOTAL_BYTE_LIMIT")
        data = read_bounded(engine_root, path)
        total_bytes += len(data)
        if total_bytes > MAX_TOTAL_BYTES:
            raise SourceBudgetExceeded("SOURCE_TOTAL_BYTE_LIMIT")
        available = min(remaining_lines, role_lines.get(role, 550))
        excerpts, used = selected_excerpts(data, available)
        remaining_lines -= used
        role_lines[role] = available - used
        receipt["inventory"].append({
            "path": path.relative_to(engine_root).as_posix(),
            "role": role,
            "bytes": len(data),
            "sha256": digest(data),
            "selected_excerpts": excerpts,
        })
        return data

    try:
        if host_context is not None and not isinstance(host_context, dict):
            raise ProbeBlocked("INVALID_HOST_CONTEXT")
        if host_context and host_context.get("probe_input_error"):
            raise ProbeBlocked(f"INVALID_HOST_CONTEXT: {host_context['probe_input_error']}")
        if not re.fullmatch(r"[0-9a-f]{40}", expected_sha) or actual_sha != expected_sha:
            raise ProbeBlocked("REPOSITORY_SHA_MISMATCH")
        if project.absolute() != (repository_root / "YetAnotherCyclingSim.uproject").absolute():
            raise ProbeBlocked("PROJECT_MUST_BE_CANONICAL_REPOSITORY_DESCRIPTOR")
        project_bytes = read_bounded(repository_root, project)
        descriptor = json.loads(project_bytes.decode("utf-8-sig"))
        if not isinstance(descriptor, dict) or not isinstance(descriptor.get("Plugins", []), list):
            raise ProbeBlocked("INVALID_PROJECT_DESCRIPTOR")
        if any(not isinstance(item, dict) or "Name" not in item for item in descriptor.get("Plugins", [])):
            raise ProbeBlocked("INVALID_PROJECT_PLUGIN_DESCRIPTOR")
        receipt["project_sha256"] = digest(project_bytes)
        receipt["project_engine_association"] = descriptor.get("EngineAssociation")
        if descriptor.get("EngineAssociation") != "5.8":
            raise ProbeBlocked("PROJECT_ENGINE_ASSOCIATION_MISMATCH")
        receipt["project_explicit_plugins"] = {
            item["Name"]: item.get("Enabled") for item in descriptor.get("Plugins", [])
        }
        build = json.loads(record(engine_root / "Engine/Build/Build.version", "engine_build"))
        if not isinstance(build, dict):
            raise ProbeBlocked("INVALID_ENGINE_BUILD_DESCRIPTOR")
        receipt["engine_build"] = build
        version = tuple(build.get(key) for key in (
            "MajorVersion", "MinorVersion", "PatchVersion", "Changelist",
        ))
        if version != EXPECTED_ENGINE:
            raise ProbeBlocked("ENGINE_VERSION_MISMATCH: expected 5.8.2-56702186")
        if host_context and host_context.get("active_engine_matches_resolver") is False:
            receipt["blockers"].append("RUNNING_EDITOR_ENGINE_MISMATCH_OR_UNVERIFIED_PATH")

        roots = {name: engine_root / relative for name, relative in PLUGIN_ROOTS.items()}
        toolsets_root = engine_root / "Engine/Plugins/Experimental/Toolsets"
        if not toolsets_root.is_dir():
            raise ProbeBlocked("MISSING_EXPERIMENTAL_TOOLSETS_TREE")
        checked_path(engine_root, toolsets_root)
        for path in bounded_files(toolsets_root, descriptors_only=True):
            relevant = path.stem in TOOLSET_NAMES
            python_root = path.parent / "Content/Python"
            if python_root.is_dir():
                checked_path(engine_root, python_root)
                # Find a relevant shipped module by filename without guessing
                # which plugin contains generic editor toolsets on this build.
                relevant = relevant or any(
                    re.fullmatch(r"(?:actor|scene|object)(?:_tools|_toolset)?", item.stem, re.I)
                    for item in bounded_files(python_root)
                    if item.suffix == ".py"
                )
            if relevant:
                if path.stem in roots:
                    raise ProbeBlocked(f"AMBIGUOUS_PLUGIN_DESCRIPTOR: {path.stem}")
                roots[path.stem] = path.parent
        for required in ("AutomationTestToolset",):
            if required not in roots:
                receipt["blockers"].append(f"MISSING_PLUGIN_DESCRIPTOR: {required}")

        source_texts: dict[str, list[str]] = {}
        priority_roles = ("ToolsetRegistry", "ModelContextProtocol", "AutomationTestToolset")
        ordered_roots = sorted(roots.items(), key=lambda item: (
            priority_roles.index(item[0]) if item[0] in priority_roles else len(priority_roles), item[0],
        ))
        for name, root in ordered_roots:
            try:
                plugin = json.loads(record(root / f"{name}.uplugin", name))
                if not isinstance(plugin, dict) or not isinstance(plugin.get("Modules", []), list):
                    raise ProbeBlocked("INVALID_PLUGIN_DESCRIPTOR")
                if any(not isinstance(item, dict) for item in plugin.get("Modules", [])):
                    raise ProbeBlocked("INVALID_PLUGIN_MODULE_DESCRIPTOR")
                receipt["plugins"][name] = {
                    "descriptor_path": (root / f"{name}.uplugin").relative_to(engine_root).as_posix(),
                    "version": plugin.get("Version"),
                    "version_name": plugin.get("VersionName"),
                    "enabled_by_default": plugin.get("EnabledByDefault"),
                    "modules": [item.get("Name") for item in plugin.get("Modules", [])],
                }
                sources = []
                for relative in ("Source", "Content/Python", "Config"):
                    source_root = root / relative
                    if source_root.is_dir():
                        checked_path(engine_root, source_root)
                        paths = bounded_files(source_root)
                        paths.sort(key=lambda item: (
                            not re.search(r"(?:Settings|Subsystem|Toolset(?:Registry)?\.(?:h|cpp)$|"
                                          r"AutomationTestToolset|ModelContextProtocolEditor|"
                                          r"(?:scene|actor|object)\.py$)", item.name),
                            item.as_posix(),
                        ))
                        for path in paths:
                            if path.suffix in SOURCE_SUFFIXES:
                                data = record(path, name)
                                sources.append(data.decode("utf-8-sig"))
                source_texts[name] = sources
                if not sources:
                    receipt["blockers"].append(f"MISSING_PLUGIN_SOURCES: {name}")
            except SourceBudgetExceeded:
                raise
            except (OSError, ValueError, UnicodeError) as exc:
                receipt["blockers"].append(f"{name}: {exc}")
        combined = "\n".join(text for texts in source_texts.values() for text in texts)
        candidates = {
            "stock_inspection": ("SceneTools", "ActorTools", "ObjectTools"),
            "ToolsetRegistry": ("SetNameFilters", "AllowedNames", "BlockedNames", "ExecuteTool"),
            "AutomationTestToolset": ("DiscoverTests", "ListTests", "RunTests", "GetTestResults"),
            "ModelContextProtocol": ("StartServer", "RefreshTools"),
        }
        receipt["candidate_symbol_observations"] = {
            role: {
                symbol: bool(re.search(r"\b" + symbol + r"\b", combined if role == "stock_inspection"
                                       else "\n".join(source_texts.get(role, []))))
                for symbol in symbols
            }
            for role, symbols in candidates.items()
        }
        receipt["semantic_mapping_status"] = "PRIMARY_SOURCE_REVIEW_REQUIRED"
        receipt["excerpt_limit_reached"] = remaining_lines == 0
        if not receipt["blockers"]:
            receipt["status"] = "SOURCE_EVIDENCE_COLLECTED"
    except (OSError, ValueError, UnicodeError) as exc:
        receipt["blockers"].append(str(exc))
    receipt["source_file_count"] = len(receipt["inventory"])
    receipt["source_total_bytes"] = total_bytes
    receipt["limitations"] = [
        "Declarations and name-filter symbols require review of actual control flow.",
        "Running-editor paths, if observed, do not prove active plugin or registry state.",
        "No map/object read, MCP transport, test run, BOB dispatch or guard parity was proved.",
    ]
    return receipt


def write_receipt(receipt: dict[str, Any], *, repository_root: Path, artifact_root: Path) -> Path:
    saved = repository_root / "Saved"
    # Existing ancestors must be safe before mkdir can write anything.
    if ".." in artifact_root.parts or not artifact_root.absolute().is_relative_to(saved.absolute()):
        raise ProbeBlocked("ARTIFACT_ROOT_MUST_BE_UNDER_PROJECT_SAVED")
    cursor = artifact_root
    while not cursor.exists():
        cursor = cursor.parent
    checked_path(repository_root, cursor)
    artifact_root.mkdir(parents=True, exist_ok=True)
    checked_path(repository_root, artifact_root)
    target = artifact_root / "official-mcp-source-probe.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write("\n")
    return target


def console_summary(receipt: dict[str, Any]) -> str:
    lines = [
        f"Official MCP source probe: {receipt['status']}",
        f"Repository SHA: {receipt['actual_sha']}",
        f"Files: {receipt['source_file_count']}; bytes: {receipt['source_total_bytes']}",
        "Guard parity / runtime schemas / official MCP admission: UNVERIFIED",
    ]
    lines.extend(f"BLOCKER: {item}" for item in receipt["blockers"])
    # Keep remote logs useful and small; the artifact retains the wider excerpt set.
    for role in ("ToolsetRegistry", "AutomationTestToolset", "ModelContextProtocol", "EditorToolset"):
        candidates = [item for item in receipt["inventory"] if item["role"] == role]
        priority = ("ToolsetRegistrySubsystem.h", "Toolset.h", "AutomationTestToolset.h")
        candidates.sort(key=lambda item: (Path(item["path"]).name not in priority, item["path"]))
        shown = 0
        for item in candidates:
            for excerpt in item["selected_excerpts"]:
                if shown >= 12:
                    break
                selected = excerpt["text"].splitlines()[: min(6, 12 - shown)]
                if selected:
                    lines.append(f"SOURCE {item['path']}:{excerpt['start_line']} sha256={item['sha256']}")
                    lines.extend(selected)
                    shown += len(selected)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine-root", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--actual-sha", required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--host-context", type=Path)
    args = parser.parse_args()
    context = None
    if args.host_context:
        try:
            data = read_bounded(args.repository_root, args.host_context)
            context = json.loads(data.decode("utf-8-sig"))
        except (OSError, ValueError, UnicodeError) as exc:
            context = {"status": "INVALID_HOST_CONTEXT", "probe_input_error": str(exc)}
    receipt = collect(
        engine_root=args.engine_root, project=args.project, repository_root=args.repository_root,
        expected_sha=args.expected_sha, actual_sha=args.actual_sha, host_context=context,
    )
    path = write_receipt(receipt, repository_root=args.repository_root, artifact_root=args.artifact_root)
    print(console_summary(receipt))
    print(f"Evidence: {path}")
    return 0 if receipt["status"] == "SOURCE_EVIDENCE_COLLECTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
