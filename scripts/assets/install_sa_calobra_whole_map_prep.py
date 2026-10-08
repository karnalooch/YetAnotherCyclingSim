"""Verify or install the three retained whole-map preparation package families.

Default is a read-only plan. --apply publishes only missing, hash-verified files
through the existing checkpoint restorer; existing differing bytes are never
replaced. No editor, map save, geometry reconstruction or native proof is run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.assets.restore_workspace_data import restore, safe_path, verify
from scripts.manage_local_workspace import load_workspace
from scripts.ue import sa_calobra_whole_map_prep as prep

ASSETS = (
    prep.MASTER_PATH,
    prep.INSTANCE_PATH,
    prep.MASTER_PACKAGE + "/T_WholeMapWeights",
)
SUFFIXES = (".uasset", ".uexp", ".ubulk", ".uptnl", ".m.ubulk")
MAX_PACKAGE_BYTES = 512 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_receipt(root, name):
    payload = prep.checked_bytes(safe_path(root, name), 8 * 1024 * 1024)
    value = json.loads(payload)
    require(isinstance(value, dict), "Invalid receipt: " + name)
    return value, hashlib.sha256(payload).hexdigest()


def identity(row):
    require(isinstance(row, dict), "Invalid package member")
    digest, size = row.get("sha256"), row.get("size_bytes")
    require(
        isinstance(digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
        and type(size) is int
        and 0 < size <= MAX_PACKAGE_BYTES,
        "Invalid package member hash or size",
    )
    return digest, size


def resolve_project(project=None, workspace_config=None):
    require(
        (project is None) != (workspace_config is None),
        "Provide exactly one destination project or workspace config",
    )
    if workspace_config is not None:
        project = load_workspace(Path(workspace_config))["project"]
    project = Path(project).resolve(strict=True)
    require(
        project.is_dir()
        and safe_path(project, "YetAnotherCyclingSim.uproject").is_file(),
        "Destination must be an existing YetAnotherCyclingSim project",
    )
    return project


def package_manifest(proof_root, master, retained):
    """Map only explicit retained bytes to the three fixed Content families."""
    generated = master.get("generated_assets", [])
    require(
        isinstance(generated, list)
        and len(generated) == 3
        and all(isinstance(row, dict) for row in generated)
        and {row.get("asset") for row in generated} == set(ASSETS),
        "Expected exactly three generated package families",
    )
    members = {}
    for row in generated:
        asset = row["asset"]
        stem = "Content/" + asset.removeprefix("/Game/")
        primary = stem + ".uasset"
        require(row.get("file") == primary, "Generated primary path changed")
        identity(row)
        files = row.get("package_files", [])
        require(isinstance(files, list) and files, "Package member inventory missing")
        family = {}
        for member in files:
            require(isinstance(member, dict), "Invalid generated package member")
            name = member.get("file")
            require(isinstance(name, str), "Invalid generated package path")
            safe_path(proof_root, name)
            require(
                name in {stem + suffix for suffix in SUFFIXES},
                "Generated member outside the fixed package family",
            )
            require(name not in members, "Duplicate generated package target")
            identity(member)
            family[name] = member
            members[name] = dict(member, asset=asset)
        require(
            primary in family and identity(family[primary]) == identity(row),
            "Generated primary identity differs from its member inventory",
        )
    rows = retained.get("files", [])
    require(
        isinstance(rows, list) and len(rows) == len(members),
        "Retained package member inventory is incomplete",
    )
    result, sources, targets = [], set(), set()
    for row in rows:
        require(isinstance(row, dict), "Invalid retained package member")
        name, source = row.get("source_file"), row.get("path")
        require(
            isinstance(name, str) and isinstance(source, str),
            "Invalid retained source or destination path",
        )
        safe_path(proof_root, name)
        source_path = safe_path(proof_root, source)
        require(name in members, "Retained destination outside the fixed packages")
        expected = members[name]
        require(
            source == "generated-assets/" + PurePosixPath(name).name
            and row.get("asset") == expected["asset"]
            and identity(row) == identity(expected),
            "Retained package identity differs from the saved master",
        )
        require(
            source.casefold() not in sources and name.casefold() not in targets,
            "Duplicate retained package source or destination",
        )
        sources.add(source.casefold())
        targets.add(name.casefold())
        require(source_path.is_file(), "Retained package member is missing: " + source)
        require(
            source_path.stat().st_size == row["size_bytes"],
            "Checkpoint content mismatch: " + source,
        )
        # Verify every source before invoking the restorer, including dry-run.
        # Its staging verification also rejects source changes during a copy.
        verify(source_path, dict(row, path=source))
        result.append(
            {
                "path": name,
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "storage": {"asset": source, "release": "retained whole-map proof"},
            }
        )
    require(
        targets == {name.casefold() for name in members},
        "Retained package destinations are incomplete",
    )
    directory = safe_path(proof_root, "generated-assets")
    actual = {path.relative_to(proof_root).as_posix() for path in directory.iterdir()}
    require(
        actual == {row["storage"]["asset"] for row in result},
        "Unrecorded file in retained package families",
    )
    return {"schema_version": 1, "files": sorted(result, key=lambda row: row["path"])}


def validate_proof(proof_root):
    master, master_sha = read_receipt(proof_root, "whole-map-master-receipt.json")
    retained, retained_sha = read_receipt(
        proof_root, "generated-assets-verification.json"
    )
    head = master.get("exact_sha")
    require(
        isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40}", head) is not None,
        "Invalid material proof revision",
    )
    require(
        master.get("schema_version") == 1
        and master.get("status") == "WHOLE_MAP_FIXED_MASTER_SAVED"
        and master.get("master") == prep.MASTER_PATH
        and master.get("instance") == prep.INSTANCE_PATH
        and master.get("map_saved") is False
        and master.get("geometry_changed") is False,
        "Master receipt does not describe the saved preparation candidate",
    )
    require(
        retained.get("schema_version") == 1
        and retained.get("status") == "GENERATED_MATERIAL_PACKAGES_RETAINED"
        and retained.get("exact_sha") == head
        and retained.get("master_receipt_sha256") == master_sha
        and retained.get("source_preserved") is True
        and retained.get("destination_verified") is True,
        "Retained material receipt is stale or incomplete",
    )
    inputs = prep.load_inputs(safe_path(proof_root, "whole-map-prep"))
    recipe = prep.rendering_recipe()
    require(
        master.get("prep_manifest_sha256") == inputs["manifest_sha256"]
        and master.get("rendering_recipe") == recipe
        and master.get("rendering_recipe_sha256")
        == hashlib.sha256(prep.canonical(recipe)).hexdigest(),
        "Prepared bundle or current rendering recipe differs from the master",
    )
    native, native_sha = read_receipt(proof_root, "native-proof-verification.json")
    cleanup, cleanup_sha = read_receipt(proof_root, "checkout-restoration.json")
    capture, capture_sha = read_receipt(
        proof_root, "capture/whole-map-prep/whole-map-prep-receipt.json"
    )
    require(
        native.get("status") == "WHOLE_MAP_EVIDENCE_VERIFIED"
        and native.get("exact_sha") == head
        and native.get("surface_manifest_sha256") == inputs["manifest_sha256"]
        and native.get("surface_manifest_fingerprint")
        == inputs["manifest"]["fingerprint"]
        and native.get("component_count") == 1024
        and native.get("primary_frame_count") == 43
        and native.get("native_trial_applied") is False
        and capture.get("status") == "WHOLE_MAP_PREPARATION_PASS"
        and capture.get("exact_sha") == head
        and capture.get("capture_complete") is True
        and capture.get("fresh_process_master_verified") is True
        and capture.get("master_receipt_sha256") == master_sha
        and capture.get("prep_manifest_sha256") == inputs["manifest_sha256"]
        and capture.get("error") is None,
        "Completed native preparation evidence is missing or stale",
    )
    require(
        cleanup.get("status") == "PASS"
        and cleanup.get("exact_sha") == head
        and cleanup.get("tracked_checkout_unchanged") is True
        and cleanup.get("retained_source_unchanged") is True
        and cleanup.get("prepared_bundle_unchanged") is True
        and cleanup.get("errors") == [],
        "Completed source and checkout conservation evidence is missing",
    )
    manifest = package_manifest(proof_root, master, retained)
    return manifest, {
        "exact_sha": head,
        "master_receipt_sha256": master_sha,
        "retained_packages_receipt_sha256": retained_sha,
        "native_verification_sha256": native_sha,
        "capture_receipt_sha256": capture_sha,
        "checkout_restoration_sha256": cleanup_sha,
        "prep_manifest_sha256": inputs["manifest_sha256"],
    }


def install(proof_root, *, project=None, workspace_config=None, apply=False):
    proof_root = Path(proof_root).resolve(strict=True)
    project = resolve_project(project, workspace_config)
    require(
        not project.is_relative_to(proof_root),
        "Destination project must not be inside the retained proof",
    )
    manifest, evidence = validate_proof(proof_root)
    expected = {row["path"] for row in manifest["files"]}
    for row in manifest["files"]:
        target = safe_path(project, row["path"])
        if target.exists():
            require(
                target.is_file() and target.stat().st_size == row["size_bytes"],
                "Checkpoint content mismatch: " + row["path"],
            )
    for asset in ASSETS:
        primary = safe_path(
            project, "Content/" + asset.removeprefix("/Game/") + ".uasset"
        )
        for path in primary.parent.glob(primary.stem + ".*"):
            relative = path.relative_to(project).as_posix()
            safe_path(project, relative)
            require(
                relative in expected, "Unrecorded existing package sidecar: " + relative
            )
    # The existing restorer validates all existing targets first, rejects any
    # differing owner bytes, stages missing payloads and publishes atomically.
    result = restore(manifest, proof_root, project, apply=apply)
    return {
        "schema_version": 1,
        "status": "WHOLE_MAP_PREP_PACKAGES_INSTALLED"
        if apply
        else "WHOLE_MAP_PREP_INSTALL_DRY_RUN",
        **evidence,
        "proof_root": str(proof_root),
        "project": str(project),
        "applied": bool(apply),
        "package_count": 3,
        "member_count": len(manifest["files"]),
        "existing_verified": result["existing_verified"],
        "restored": result["restored"],
        "missing": [row["path"] for row in result["missing"]],
        "files": manifest["files"],
        "source_dependencies": "Existing Git LFS textures; verified by preview() in the destination editor",
        "map_saved": False,
        "editor_launched": False,
        "transient_v8_reconstructed": False,
        "visual_acceptance": "PENDING_OWNER",
        "performance_acceptance": "NOT_MEASURED",
        "preview_bundle": str(proof_root / "whole-map-prep"),
        "preview_master_receipt": str(proof_root / "whole-map-master-receipt.json"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-root", required=True, type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--project", type=Path)
    destination.add_argument("--workspace-config", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    report = install(
        args.proof_root,
        project=args.project,
        workspace_config=args.workspace_config,
        apply=args.apply,
    )
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
