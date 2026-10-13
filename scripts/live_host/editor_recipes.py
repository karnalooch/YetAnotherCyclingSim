"""Audited versioned Unreal editor recipes — same persistent process, no restart.

The HTTP/browser/Actions request NEVER contains executable Python. An approved
Git commit can supply new repo-owned recipe modules only after a separate
exact-SHA CI/owner staging operation. Stage artifacts under the dedicated
interactive account's ACL-protected Live Host root; never in a runner checkout.

This is NOT a sandbox against malicious trusted Python. Use only owner-reviewed
repository source, exact binary identities and targeted native proof. Restrict
committed authoring to an explicitly declared reversible asset set.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import shutil

from scripts.live_host.protocol import (
    Rejected, need, file_proof, load_bounded_json, RECIPE_NAME, SHA_PATTERN,
    DIGEST_PATTERN,
)

CATALOG_LIMIT = 8192
MAX_SOURCE_BYTES = 512 * 1024
MAX_ASSET_BYTES = 256 * 1024 * 1024
APPROVED_REPOSITORY = "karnalooch/YetAnotherCyclingSim"
FROZEN_PREFIXES = (
    "Content/Worlds/SaCalobra/",
    "Content/Generated/YACS/SaCalobra/WholeMapPreparation/",
    "Content/Generated/YACS/RoadAsphaltConsumer/",
)
# Base_DTM and frozen original Landscape/map files are NEVER writable
# via this generic recipe layer, even under a technically valid author request.


def safe_regular(path: Path, root: Path) -> Path:
    root = root.resolve(strict=True)
    candidate = root / path
    need(candidate.is_relative_to(root), "Recipe path outside live-host root")
    probe = candidate
    while probe != root:
        need(not probe.is_symlink(), "Aliased recipe or parent path is forbidden")
        probe = probe.parent
    need(candidate.is_file() and not candidate.is_symlink(),
         "Missing or aliased exact recipe source")
    return candidate


def author_asset_path(project: Path, relative: str) -> Path:
    need(type(relative) is str and relative.startswith("Content/")
         and "\\" not in relative and ":" not in relative
         and all(x not in (".", "..", "") for x in relative.split("/")),
         "Unsafe authored asset path")
    need(relative.endswith((".uasset", ".umap")),
         "Only UE native packages may be checkpointed")
    need(not any(relative.startswith(prefix) for prefix in FROZEN_PREFIXES)
         and "Base_DTM" not in relative
         and "Landscape" not in relative,
         "Frozen map, DTM or road cannot be edited by generic recipe")
    target = project / relative
    need(target.is_relative_to(project), "Authoring path escaped project")
    # Do not let a source symlink redirect a trusted project write.
    cursor = project
    need(not cursor.is_symlink(), "Aliased authoring project refused")
    for part in target.relative_to(project).parts[:-1]:
        cursor = cursor / part
        need(not cursor.is_symlink(), "Authoring directory alias forbidden")
    need(not target.is_symlink(), "Authored asset alias forbidden")
    return target


def parse_manifest(root: Path, request: dict) -> tuple[dict, Path]:
    revision = request["recipe_revision"]
    recipe = request["recipe"]
    need(type(revision) is str and SHA_PATTERN.fullmatch(revision),
         "Invalid recipe source revision")
    need(type(recipe) is str and RECIPE_NAME.fullmatch(recipe),
         "Invalid approved recipe name")
    stage = root / "recipes" / revision
    manifest = safe_regular(stage / (recipe + ".json"), root)
    contract = load_bounded_json(manifest, CATALOG_LIMIT)
    need(set(contract) == {
        "schema_version", "repository", "revision", "recipe", "source_path",
        "sha256", "intents", "capability", "parameters", "asset_scope",
        "review_issue", "ci_admitted"
    }, "Incomplete recipe provenance/parameter contract")
    need(contract["schema_version"] == 1
         and contract["repository"] == APPROVED_REPOSITORY
         and contract["revision"] == revision
         and contract["recipe"] == recipe
         and contract["source_path"] == "scripts/live_host/recipes/" + recipe + ".py"
         and contract["sha256"] == request["recipe_sha256"]
         and contract["ci_admitted"] is True
         and type(contract["review_issue"]) is int and contract["review_issue"] >= 1,
         "Untrusted or unproven recipe author")
    need(type(contract["intents"]) is list and request["intent"] in contract["intents"]
         and all(x in ("preview", "author") for x in contract["intents"]),
         "Recipe mode is not authorized")
    need(type(contract["capability"]) is str
         and contract["capability"] in {
             "world_inspection", "actor_presentation", "material_presentation",
             "lighting_presentation", "asset_authoring", "pcg_authoring",
             "animation_authoring", "editor_tooling"
         }, "Unknown or unconstrained editor capability")
    script = safe_regular(stage / (recipe + ".py"), root)
    need(0 < script.stat().st_size <= MAX_SOURCE_BYTES,
         "Versioned executable source is missing or exceeds source budget")
    need(file_proof(script)["sha256"] == request["recipe_sha256"],
         "Recipe source changed since audited commit")
    return contract, script


def verify_parameters(schema: dict, parameters: dict) -> None:
    need(type(schema) is dict and type(parameters) is dict
         and set(schema) == set(parameters) and len(schema) <= 32,
         "Recipe arguments differ from exact declared schema")
    for name, rule in schema.items():
        need(type(name) is str and RECIPE_NAME.fullmatch(name)
             and type(rule) is dict and set(rule) <= {
                 "type", "minimum", "maximum", "enum"
             }, "Recipe argument schema changed")
        item = parameters[name]
        kind = rule.get("type")
        if kind == "boolean":
            need(type(item) is bool, "Boolean recipe input required: " + name)
        elif kind == "number":
            need(type(item) in (int, float) and math.isfinite(float(item)),
                 "Finite numeric recipe input required: " + name)
            need(type(rule.get("minimum")) in (int, float)
                 and type(rule.get("maximum")) in (int, float)
                 and rule["minimum"] <= item <= rule["maximum"],
                 "Recipe numeric range denied: " + name)
        elif kind == "vec3":
            need(type(item) is list and len(item) == 3
                 and all(type(v) in (int, float) and math.isfinite(float(v))
                         and abs(float(v)) <= 1e7 for v in item),
                 "Finite bounded 3D vector required: " + name)
        elif kind == "enum":
            need(type(item) is str and type(rule.get("enum")) is list
                 and len(rule["enum"]) <= 100
                 and item in rule["enum"],
                 "Recipe value outside allowed exact enum: " + name)
        elif kind == "string":
            need(type(item) is str and len(item) <= 256
                 and not any(ord(c) < 32 for c in item),
                 "Malformed bounded recipe string: " + name)
        else:
            raise Rejected("Unknown recipe argument type: " + name)


def reserve_backups(
    *, project: Path, session_root: Path, request: dict, contract: dict
) -> tuple[dict, dict]:
    """Strict one-time backups; never silently overwrite the saved world."""
    assets = contract["asset_scope"]
    need(type(assets) is list and len(assets) <= 32
         and len(set(assets)) == len(assets), "Invalid authored assets list")
    if request["intent"] == "preview":
        need(not assets, "Preview must not declare disk authoring")
        return {}, {}
    need(project.name == "project" and project.parent == Path("D:/yacs"),
         "Only the canonical authoring workspace may save assets")
    need(0 < len(assets) <= 32, "No explicit bounded authoring scope")
    before = {}
    dest = session_root / "backups" / (
        f"{request['sequence']:06d}-{request['request_id']}"
    )
    need(not dest.exists(), "Authoring backup exists; refuse replay")
    dest.mkdir(parents=True, exist_ok=False)
    for name in assets:
        path = author_asset_path(project, name)
        need(path.is_file() and path.stat().st_size <= MAX_ASSET_BYTES,
             "Missing, oversized or unversioned authored package: " + name)
        proof = file_proof(path)
        output = dest / name
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, output)
        need(file_proof(output) == proof, "Failed to retain authentic backup")
        before[name] = proof
    return before, {"directory": str(dest), "files": before}


def load_and_run(
    *, unreal, live, root: Path, project: Path, request: dict,
    session_root: Path
) -> dict:
    """Execute precisely one reviewed module inside existing native editor tick."""
    root = root.resolve()
    project = project.resolve()
    contract, script = parse_manifest(root, request)
    verify_parameters(contract["parameters"], request["parameters"])
    before, rollback = reserve_backups(
        project=project, session_root=session_root, request=request,
        contract=contract,
    )
    from scripts.live_host.protocol import MAP_SHA256, MAP_PACKAGE
    # Diagnostic original map always protected, even for broad author recipes.
    diagnostic = project / "Content" / (MAP_PACKAGE.removeprefix("/Game/") + ".umap")
    diagnostic_before = file_proof(diagnostic) if diagnostic.is_file() else None
    if diagnostic_before:
        need(diagnostic_before["sha256"] == MAP_SHA256, "Accepted map source differs")
    # Namespaced non-cached import; verified source digest and schema previously
    # bound to this exact request. Execution still trusts reviewed repository code.
    module_name = "_yacs_live_" + request["recipe"] + "_" + request["recipe_revision"][:12]
    spec = importlib.util.spec_from_file_location(module_name, str(script))
    need(spec is not None and spec.loader is not None, "Recipe loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    need(callable(getattr(module, "run", None)), "Audited module lacks run()")
    context = {
        "live": live, "project": project, "intent": request["intent"],
        "asset_scope": tuple(contract["asset_scope"]),
        "request_id": request["request_id"],
        "revision": request["recipe_revision"],
        "capability": contract["capability"],
    }
    result = module.run(unreal, context, request["parameters"])
    need(type(result) is dict
         and result.get("status") in ("APPLIED_PREVIEW", "AUTHORING_CHECKPOINTED"),
         "Recipe returned no authenticated native result")
    if request["intent"] == "preview":
        need(result["status"] == "APPLIED_PREVIEW" and result.get("map_saved") is False,
             "A visual preview cannot imply a persisted source save")
    else:
        need(result["status"] == "AUTHORING_CHECKPOINTED"
             and result.get("changed_assets") == contract["asset_scope"],
             "Only declared source assets may be checkpointed")
    if diagnostic_before:
        need(file_proof(diagnostic) == diagnostic_before,
             "Frozen accepted map changed during editor recipe")
    return {
        "status": result["status"],
        "recipe": request["recipe"],
        "recipe_revision": request["recipe_revision"],
        "recipe_source_sha256": request["recipe_sha256"],
        "intent": request["intent"],
        "native_readback": result,
        "undo_backup": rollback,
        "preexisting_assets": before,
        "placement": False,
        "performance_pass": False,
    }
