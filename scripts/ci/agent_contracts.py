"""Static, fail-closed YACS role and scoped-policy checks (no agent runtime)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = "docs/ai/ROLE_REGISTRY.json"
SHA = re.compile(r"^[a-f0-9]{40}$")
ACTIVE_MILESTONE = "M3"

REQUIRED_POLICY_MARKERS = {
    "DELIVERY_AND_SCOPE.md": ["## Scope control", "### Remote-first delivery"],
    "M3_WORLD_OPERATIONS.md": [
        "### Live editor collaboration with the owner",
        "### Official Unreal MCP adoption",
        "### Frozen geometry",
        "DEFERRED_AFTER_M3",
    ],
    "DOCS_AND_PLATFORM.md": [
        "### Documentation SSOT and freshness",
        "## Gumball repository baseline",
        "### Problem reporting",
    ],
    "CODE_PHYSICS_UNREAL.md": [
        "## Code rules",
        "## Physics rules",
        "## Unreal Engine rules",
        "## Third-party provenance rules",
    ],
    "GIT_AND_PROJECT.md": [
        "## Git rules",
        "## Issue -> Project -> delivery",
        "## Office and home workflow",
    ],
    "TOOLING_AND_AI_SAFETY.md": [
        "## External tooling architecture policy",
        "## AI safety rules",
    ],
}


def project_file(root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel or rel.startswith("/"):
        raise ValueError(f"invalid project path: {rel!r}")
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"missing/unsafe reference: {rel}")
    return path


def load_registry(root: Path = ROOT) -> dict:
    data = json.loads(project_file(root, REGISTRY).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("role registry must be an object")
    return data


def validate(root: Path = ROOT) -> list[str]:
    errors = []
    try:
        data = load_registry(root)
        if data.get("schema_version") != 1:
            errors.append("invalid role registry schema")
        if data.get("current_milestone") != ACTIVE_MILESTONE:
            errors.append("unexpected active milestone")

        root_text = project_file(root, "AGENTS.md").read_text(encoding="utf-8")
        if len(root_text.splitlines()) > 150:
            errors.append("AGENTS.md must remain <= 150 lines")
        for token in ("docs/ai/README.md", REGISTRY, "docs/README.md"):
            if token not in root_text:
                errors.append(f"root AGENTS missing context router: {token}")

        index = project_file(root, "docs/README.md").read_text(encoding="utf-8")
        if "(ai/README.md)" not in index:
            errors.append("docs index missing agent router")
        project_file(root, "docs/ai/README.md")
        project_file(root, "docs/ai/TASK_HANDOFF.md")
        project_file(root, "docs/ai/DECISION_LIFECYCLE.md")

        expected = set(REQUIRED_POLICY_MARKERS)
        policies = data.get("policy_documents", [])
        if not isinstance(policies, list):
            errors.append("policy_documents must be a list")
            policies = []
        found = set()
        for rel in policies:
            path = project_file(root, rel)
            if path.name in found:
                errors.append(f"duplicate scoped policy: {path.name}")
            found.add(path.name)
            for marker in REQUIRED_POLICY_MARKERS.get(path.name, []):
                if marker not in path.read_text(encoding="utf-8"):
                    errors.append(f"lost scoped policy marker: {path.name}: {marker}")
        if found != expected:
            errors.append("scoped policy inventory drift")

        owners = data.get("domain_owners")
        roles = data.get("roles")
        if not isinstance(owners, dict) or not isinstance(roles, dict):
            return errors + ["invalid domain_owners or roles mapping"]
        if not owners or len(owners) != len(roles):
            errors.append("active role ownership must be one-to-one")
        for domain, rid in owners.items():
            if not isinstance(domain, str) or not isinstance(rid, str):
                errors.append("non-string domain/role mapping")
                continue
            role = roles.get(rid)
            if not isinstance(role, dict):
                errors.append(f"owner for {domain} is missing: {rid}")
                continue
            if role.get("domain") != domain or role.get("status") != "active":
                errors.append(f"invalid domain ownership: {domain}")
            if role.get("milestones") != [ACTIVE_MILESTONE]:
                errors.append(f"out-of-stage active role: {rid}")
        for rid, role in roles.items():
            if not isinstance(role, dict):
                errors.append(f"invalid role card: {rid}")
                continue
            project_file(root, role.get("card"))
            refs = role.get("read_docs")
            if not isinstance(refs, list) or not refs:
                errors.append(f"empty role context: {rid}")
                continue
            for ref in refs:
                project_file(root, ref)
            for forbidden in ("can_admit", "can_merge", "can_dispatch_heavy"):
                if role.get(forbidden) is not False:
                    errors.append(f"role privilege escalation: {rid}/{forbidden}")
        orchestrator = data.get("orchestrator", {})
        for forbidden in ("can_admit", "can_merge", "can_dispatch_heavy"):
            if orchestrator.get(forbidden) is not False:
                errors.append(f"orchestrator privilege escalation: {forbidden}")
        future = data.get("planned_roles", {})
        if not isinstance(future, dict):
            errors.append("planned_roles must be a mapping")
        else:
            for rid, spec in future.items():
                if rid in roles or ACTIVE_MILESTONE in spec.get("milestones", []):
                    errors.append(f"planned role prematurely activated: {rid}")
        resources = data.get("exclusive_resources", [])
        if len(resources) != len(set(resources)):
            errors.append("duplicate exclusive resources")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    return errors


def route_task(
    data: dict,
    domain: str,
    milestone: str,
    claims: tuple[str, ...] = (),
    occupied: tuple[str, ...] = (),
) -> str:
    if milestone != data.get("current_milestone"):
        raise ValueError("milestone is not currently authorized")
    owner = data.get("domain_owners", {}).get(domain)
    role = data.get("roles", {}).get(owner)
    if not role or role.get("status") != "active":
        raise ValueError("no active owner for requested domain")
    if milestone not in role.get("milestones", []):
        raise ValueError("role does not own this milestone")
    resources = set(data.get("exclusive_resources", []))
    if any(claim not in resources for claim in claims):
        raise ValueError("unknown exclusive resource claim")
    if set(claims).intersection(occupied):
        raise ValueError("host resource already owned")
    if claims and owner != "unreal-integration":
        raise ValueError("host operations require bounded Unreal integration")
    return owner


def verify_handoff(task: dict, data: dict) -> str:
    for key in ("issue", "milestone", "domain", "base_sha", "scope", "forbidden"):
        if key not in task:
            raise ValueError(f"handoff missing {key}")
    if not isinstance(task["issue"], int) or task["issue"] < 1:
        raise ValueError("invalid issue")
    if not isinstance(task["base_sha"], str) or not SHA.fullmatch(task["base_sha"]):
        raise ValueError("handoff requires an exact base SHA")
    if not isinstance(task["scope"], list) or not task["scope"]:
        raise ValueError("handoff requires bounded scope")
    if not isinstance(task["forbidden"], list):
        raise ValueError("handoff requires explicit forbidden operations")
    if task.get("admitted") or task.get("merged") or task.get("performance_pass"):
        raise ValueError("agent cannot self-admit, merge or claim performance PASS")
    return route_task(
        data,
        task["domain"],
        task["milestone"],
        tuple(task.get("resource_claims", [])),
        tuple(task.get("occupied_resources", [])),
    )


def main() -> int:
    errors = validate()
    for error in errors:
        print(f"agent-contract: FAIL - {error}", file=sys.stderr)
    if errors:
        return 1
    print("agent-contract: PASS - references, ownership, privileges and policy markers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
