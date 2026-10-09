"""Collect bounded installed Epic source evidence without activating Unreal MCP.

This filesystem probe records declarations for a later human/API review. It
does not establish runtime schemas, restrict a server, execute tools or admit
the #384 spike. Epic excerpts stay in ignored Saved evidence and bounded native
job logs; the installed source is never copied into the repository.
"""

from __future__ import annotations

import argparse
import ast
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
MAX_CONSOLE_LINES = 500
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


def source_priority(path: Path, role: str) -> tuple[int, str]:
    """Prefer real stock implementations; shipped tests never spend their budget first."""
    name = path.name
    if (any(part.lower() == "test" or part.lower().endswith("tests") for part in path.parts)
            or name.lower() == "test.py" or name.lower().startswith("test_")):
        return 100, path.as_posix()
    registry = (
        "ToolsetRegistrySubsystem.h", "Toolset.h", "Toolset.cpp", "ToolsetRegistry.cpp",
        "ToolsetRegistrySubsystem.cpp", "ToolsetRegistry.h", "__init__.py", "UToolsetRegistry.h",
        "UToolsetRegistry.cpp", "ToolsetDefinition.h",
    )
    if role == "ToolsetRegistry" and name in registry:
        return registry.index(name), path.as_posix()
    if role == "AutomationTestToolset" and name in {"AutomationTestToolset.h", "AutomationTestToolset.cpp"}:
        return int(path.suffix == ".cpp"), path.as_posix()
    if role == "ModelContextProtocol":
        if "Settings" in name and path.suffix == ".h":
            return 0, path.as_posix()
        if "ModelContextProtocolEditor" in name and path.suffix == ".cpp":
            return 1, path.as_posix()
        if "Toolset" in name and path.suffix in {".h", ".cpp"}:
            return 2, path.as_posix()
        if name == "ModelContextProtocolModule.cpp":
            return 3, path.as_posix()
        if name == "IModelContextProtocolModule.h":
            return 4, path.as_posix()
    if name in {"scene.py", "actor.py", "object.py"}:
        return ("scene.py", "actor.py", "object.py").index(name), path.as_posix()
    return 50, path.as_posix()


# Narrow evidence selectors use confirmed paths and observed/documented names.
# They collect source contexts; they do not implement or verify API wiring.
# Optional anchors never establish a capability or turn their absence into a blocker.
SEMANTIC_ANCHORS = {
    "Toolset.h": ((r"\bSetNameFilters\s*\(", 0, 4), (r"\bExecuteTool\s*\(", 0, 4)),
    "Toolset.cpp": ((r"FToolset::SetNameFilters\s*\(", 0, 85),
                    (r"FToolset::ExecuteTool\s*\(", 0, 30)),
    "ToolsetRegistry.cpp": ((r"FToolsetRegistry::ExecuteTool\s*\(", 0, 75),
                           (r"FToolsetRegistry::RegisterToolset\s*\(", 0, 45)),
    "ToolsetRegistrySubsystem.cpp": ((r"GetDefault<UToolsetRegistrySettings>", 8, 35),),
    "ModelContextProtocolToolsetRegistryAdapter.cpp": (
        (r"bEnableToolSearch", 7, 45),
        (r"ToolsetRegistry->ExecuteTool\s*\(", 18, 28),
    ),
    "ModelContextProtocolEditor.cpp": ((r"StartServer\s*\(", 8, 8),
                                      (r"OnRefreshTools", 2, 12)),
    "AutomationTestToolset.cpp": ((r"UAutomationTestToolset::RunTests\s*\(", 0, 110),
                                  (r"UAutomationTestToolset::GetTestResults\s*\(", 0, 55)),
    "AutomationTestToolset.h": ((r"\bRunTests\s*\(", 3, 8),
                               (r"\bGetTest(?:Status|Results)\s*\(", 2, 4)),
    "__init__.py": ((r"^def tool_call\s*\(", 0, 15),),
}


def semantic_spans(lines: list[str], path: Path) -> list[tuple[int, int]]:
    """Select fixed native control-flow contexts and actual Python read bodies."""
    if path.name in {"actor.py", "scene.py", "object.py"}:
        try:
            tree = ast.parse("\n".join(lines))
        except SyntaxError:
            return []
        methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name.startswith(("get_", "list_", "find_", "is_", "exists"))]
        methods.sort(key=lambda node: node.lineno)
        return [(max(0, min([node.lineno, *[item.lineno for item in node.decorator_list]]) - 1),
                 min(node.end_lineno or node.lineno, node.lineno + 55)) for node in methods[:2]]
    spans = []
    for pattern, before, after in SEMANTIC_ANCHORS.get(path.name, ()):
        for index, line in enumerate(lines):
            if not re.search(pattern, line):
                continue
            start, end = max(0, index - before), min(len(lines), index + after)
            # For an anchored C++ definition stop at its closing brace, so a
            # short function does not spend its budget on following methods.
            if "::" in pattern and before == 0:
                depth = 0
                opened = False
                for cursor in range(index, end):
                    code = re.sub(r'"(?:\\.|[^"\\])*"|//.*', "", lines[cursor])
                    depth += code.count("{") - code.count("}")
                    opened |= "{" in code
                    if opened and depth <= 0:
                        end = cursor + 1
                        break
            spans.append((start, end))
            break
    return spans


def selected_excerpts(
    data: bytes, budget: int, path: Path | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Retain concise contexts, never a wholesale copy of an Epic source file."""
    lines = data.decode("utf-8-sig").splitlines()
    spans = semantic_spans(lines, path) if path is not None else []
    semantic = bool(spans)
    for index, line in enumerate(lines):
        if not semantic and INTEREST.search(line):
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
            "selection": "semantic_context" if semantic else "declaration_context",
            "budget_truncated": end < spans[len(excerpts)][1],
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
        per_file_limit = {"Toolset.cpp": 120, "ToolsetRegistry.cpp": 120,
                          "ToolsetRegistrySubsystem.cpp": 65}.get(path.name, 80) if role == "ToolsetRegistry" else 150
        available = min(available, per_file_limit)
        excerpts, used = selected_excerpts(data, available, path)
        remaining_lines -= used
        role_lines[role] = role_lines.get(role, 550) - used
        item = {
            "path": path.relative_to(engine_root).as_posix(),
            "role": role,
            "bytes": len(data),
            "sha256": digest(data),
            "selected_excerpts": excerpts,
        }
        if path.name in {"actor.py", "scene.py", "object.py"} and source_priority(path, role)[0] < 50:
            lines = data.decode("utf-8-sig").splitlines()
            try:
                tree = ast.parse("\n".join(lines))
                definitions = sorted((node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)),
                                     key=lambda node: node.lineno)
                item["python_declarations"] = {
                    "total": len(definitions), "truncated": len(definitions) > 32,
                    "definitions": [{"line": node.lineno, "signature_first_line": lines[node.lineno - 1][:240]}
                                    for node in definitions[:32]],
                }
            except SyntaxError:
                item["python_declarations"] = {"status": "SOURCE_PARSE_UNESTABLISHED"}
        receipt["inventory"].append(item)
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
                paths = []
                for relative in ("Source", "Content/Python", "Config"):
                    source_root = root / relative
                    if source_root.is_dir():
                        checked_path(engine_root, source_root)
                        paths.extend(bounded_files(source_root))
                # Sort across Source/Python/Config together so native helpers
                # cannot consume the role budget before the Python adapter.
                for path in sorted(paths, key=lambda item: source_priority(item, name)):
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
    lines.extend(f"BLOCKER: {str(item)[:600]}" for item in receipt["blockers"][:16])

    def scalar(value: Any, limit: int = 256) -> Any:
        return value[:limit] if isinstance(value, str) else value if isinstance(value, (bool, int, float)) else None

    build = receipt.get("engine_build", {})
    engine = {key: scalar(build.get(key)) for key in (
        "MajorVersion", "MinorVersion", "PatchVersion", "Changelist", "CompatibleChangelist",
        "IsLicenseeVersion", "IsPromotedBuild", "BranchName", "BuildId",
    )}
    engine["root"] = scalar(receipt.get("engine_root"), 512)
    engine["project_association"] = scalar(receipt.get("project_engine_association"))
    build_record = next((item for item in receipt["inventory"] if item["role"] == "engine_build"), {})
    engine["build_version_sha256"] = build_record.get("sha256")
    lines.append("ENGINE_IDENTITY " + json.dumps(engine, sort_keys=True))

    for name, plugin in sorted(receipt.get("plugins", {}).items())[:16]:
        metadata = {key: scalar(plugin.get(key), 512) for key in (
            "descriptor_path", "version", "version_name", "enabled_by_default",
        )}
        metadata["name"] = scalar(name, 128)
        metadata["modules"] = [scalar(item, 128) for item in plugin.get("modules", [])[:16]]
        record = next((item for item in receipt["inventory"] if item["path"] == plugin.get("descriptor_path")), {})
        metadata["descriptor_sha256"] = record.get("sha256")
        lines.append("PLUGIN_IDENTITY " + json.dumps(metadata, sort_keys=True))

    observed = receipt.get("running_editor", {})
    if not isinstance(observed, dict):
        observed = {}
    host = {key: scalar(observed.get(key), 1024) for key in (
        "status", "inspected_at_utc", "active_engine_matches_resolver", "active_plugin_state_verified",
    )}
    processes = observed.get("processes", [])
    if not isinstance(processes, list):
        processes = []
    host["observed_process_count"] = len(processes)
    host["processes"] = [
        {key: scalar(item.get(key), 512) for key in (
            "process_id", "name", "executable_path", "executable_sha256",
            "executable_under_resolved_engine", "plugin_state_verified",
        )}
        for item in processes[:8] if isinstance(item, dict)
    ]
    host["process_list_truncated"] = len(processes) > 8
    lines.append("RUNNING_EDITOR_OBSERVATION " + json.dumps(host, sort_keys=True))

    # Fixed role/file budgets expose useful primary definitions through native
    # logs when artifact download is unavailable. Never print arbitrary content
    # from process command lines, secret files, tests or an entire source tree.
    roles = ("ToolsetRegistry", "ModelContextProtocol", "AutomationTestToolset")
    other_roles = sorted({item["role"] for item in receipt["inventory"]} - set(roles) - {"engine_build"})
    generic_remaining = 90
    role_budgets = {"ToolsetRegistry": 170, "ModelContextProtocol": 140, "AutomationTestToolset": 100}
    console_files = {
        "ToolsetRegistry": (("Toolset.cpp", 80), ("ToolsetRegistry.cpp", 50),
                            ("ToolsetRegistrySubsystem.cpp", 20), ("Toolset.h", 10),
                            ("__init__.py", 10), ("ToolsetRegistrySubsystem.h", 10)),
        "ModelContextProtocol": (("ModelContextProtocolToolsetRegistryAdapter.cpp", 90),
                                 ("ModelContextProtocolEditor.cpp", 25),
                                 ("ModelContextProtocolSettings.h", 25)),
        "AutomationTestToolset": (("AutomationTestToolset.cpp", 80),
                                  ("AutomationTestToolset.h", 20)),
    }
    for role in (*roles, *other_roles):
        candidates = [item for item in receipt["inventory"] if item["role"] == role
                      and source_priority(Path(item["path"]), role)[0] < 50
                      and Path(item["path"]).suffix in {".h", ".cpp", ".py"}]
        candidates.sort(key=lambda item: source_priority(Path(item["path"]), role))
        if role in console_files:
            console_order = tuple(name for name, _ in console_files[role])
            candidates = [item for item in candidates if Path(item["path"]).name in console_order]
            candidates.sort(key=lambda item: (
                console_order.index(Path(item["path"]).name),
                source_priority(Path(item["path"]), role),
            ))
        remaining = role_budgets.get(role, generic_remaining)
        for item in candidates:
            file_remaining = dict(console_files[role])[Path(item["path"]).name] if role in roles else 30
            if item.get("python_declarations") and len(lines) < MAX_CONSOLE_LINES:
                lines.append(f"DECLARATIONS {item['path']} sha256={item['sha256']} "
                             + json.dumps(item["python_declarations"], sort_keys=True))
            for excerpt in item["selected_excerpts"]:
                room = min(remaining, file_remaining, MAX_CONSOLE_LINES - len(lines) - 1)
                if room <= 0:
                    break
                selected = excerpt["text"].splitlines()[:room]
                if selected:
                    end_line = excerpt["start_line"] + len(selected) - 1
                    clipped = excerpt.get("budget_truncated", False) or len(selected) < len(excerpt["text"].splitlines())
                    lines.append(f"SOURCE {item['path']}:{excerpt['start_line']}-{end_line} "
                                 f"sha256={item['sha256']} budget_truncated={str(clipped).lower()}")
                    lines.extend(selected)
                    remaining -= len(selected)
                    file_remaining -= len(selected)
        if role not in roles:
            generic_remaining = remaining
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
