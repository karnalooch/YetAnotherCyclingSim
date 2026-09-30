"""Fail closed when the final YACS architecture/tooling boundaries drift."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UE_MCP_VERSION = "1.3.9"
UE_MCP_COMMIT = "d79a34bb6e7a5883457efe8f33c9f85b1ba3e136"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_json(path: str) -> dict:
    return json.loads(read(path))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    bible = read("docs/WORLD_BUILDING_BIBLE.md")
    require(
        "Embark production-pattern review first" in bible,
        "World Bible lost Embark-first admission",
    )
    require(
        "1. **Unreal Engine native first**" not in bible,
        "World Bible reverted to native-first order",
    )
    require(
        "AStage3PrototypeTerrainActor" in bible
        and "frozen legacy regression scaffolding" in bible,
        "legacy prototype retirement boundary is missing",
    )

    project = load_json("YetAnotherCyclingSim.uproject")
    roadforge_project = next(p for p in project["Plugins"] if p["Name"] == "RoadForge")
    require(
        roadforge_project.get("TargetAllowList") == ["Editor"],
        "RoadForge project plugin must be Editor-only",
    )

    roadforge = load_json("Plugins/RoadForge/RoadForge.uplugin")
    module = next(m for m in roadforge["Modules"] if m["Name"] == "RoadForge")
    require(module.get("Type") == "Editor", "RoadForge module must not be Runtime")
    require(
        module.get("TargetAllowList") == ["Editor"],
        "RoadForge module target allow-list drifted",
    )

    header = read(
        "Source/YetAnotherCyclingSim/Public/Cycling/Stage3PrototypeTerrainActor.h"
    )
    require(
        "LEGACY M3 PROTOTYPE WORLD - FROZEN" in header,
        "prototype world freeze marker is missing",
    )

    package = load_json("tools/ue-mcp/package.json")
    require(
        package["dependencies"].get("ue-mcp") == UE_MCP_VERSION,
        "ue-mcp direct pin drifted",
    )
    require(
        package.get("yacs", {}).get("upstream_commit") == UE_MCP_COMMIT,
        "ue-mcp provenance metadata drifted",
    )
    require(
        package.get("overrides", {}).get("fast-uri") == "3.1.7",
        "fast-uri security override drifted",
    )

    lock = load_json("tools/ue-mcp/package-lock.json")
    require(lock.get("lockfileVersion") == 3, "unexpected npm lockfile version")
    require(
        lock["packages"][""]["dependencies"].get("ue-mcp") == UE_MCP_VERSION,
        "lock root ue-mcp pin drifted",
    )
    require(
        lock["packages"]["node_modules/ue-mcp"].get("version") == UE_MCP_VERSION,
        "locked ue-mcp version drifted",
    )
    require(
        lock["packages"]["node_modules/fast-uri"].get("version") == "3.1.7",
        "patched fast-uri lock version drifted",
    )

    setup = read("scripts/ue/Setup-YacsUeMcp.ps1")
    require(
        "npm ci --ignore-scripts" in setup,
        "UE-MCP setup must use npm ci --ignore-scripts",
    )
    require(
        "$Npm.Source install" not in setup,
        "UE-MCP setup must not use npm install",
    )

    provenance = read("docs/legal/DEPENDENCY_PROVENANCE.md")
    require(
        UE_MCP_COMMIT in provenance and "db-lyon ue-mcp" in provenance,
        "ue-mcp provenance ledger entry missing",
    )

    tooling = read("docs/UNREAL_TOOLING_PLUGIN_PLAN.md")
    require(
        "**RoadForge Mesh Core** | INCLUDED / EDITOR-ONLY" in tooling,
        "RoadForge current lifecycle status drifted",
    )
    require(
        "| **RoadForge** | spline-to-road presentation" not in tooling,
        "RoadForge still appears as a future candidate",
    )

    print("final architecture/tooling contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
