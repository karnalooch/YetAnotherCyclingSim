"""Import newly acquired World Authoring Library candidates into YACS sandbox.

This is a qualification-staging importer, not an automatic acceptance path.
It imports only selections marked as live-discovery candidates and writes only
below /Game/Generated/YACS/Library/Candidates/**.

Required environment variables:
  YACS_WORLD_ASSET_SELECTION_PLAN  selection-plan JSON from yacs_asset_library.py
  YACS_WORLD_ASSET_CACHE           ignored source-cache root used by the selector
  YACS_WORLD_ASSET_IMPORT_PROOF    output JSON proof path

Approved catalog assets that already expose a qualified ue_asset_path are never
reimported by this script.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import traceback
from typing import Any

import unreal


DESTINATION_ROOT = "/Game/Generated/YACS/Library/Candidates/PolyHaven"
SAFE_ID = re.compile(r"^[a-z0-9_]+$")


def fail(message: str) -> None:
    raise RuntimeError(message)


def log(message: str) -> None:
    unreal.log("[YacsAssetCandidateImport] {}".format(message))


def ensure_directory(path: str) -> None:
    if not path.startswith("/Game/Generated/YACS/"):
        fail("candidate import destination escaped generated-content sandbox")
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        if not unreal.EditorAssetLibrary.make_directory(path):
            fail("failed to create {}".format(path))


def source_path(cache_root: Path, relative_path: str) -> Path:
    target = (cache_root / relative_path).resolve()
    try:
        target.relative_to(cache_root.resolve())
    except ValueError as exc:
        raise RuntimeError(
            "selection-plan source path escapes cache: {}".format(target)
        ) from exc
    if not target.is_file():
        fail("candidate source file is missing: {}".format(target))
    return target


def import_source(
    source: Path,
    destination: str,
    *,
    model: bool,
) -> list[str]:
    ensure_directory(destination)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)

    if model:
        options = unreal.FbxImportUI()
        options.set_editor_property("import_mesh", True)
        options.set_editor_property("import_as_skeletal", False)
        options.set_editor_property("import_materials", False)
        options.set_editor_property("import_textures", False)
        static_data = options.get_editor_property("static_mesh_import_data")
        static_data.set_editor_property("combine_meshes", False)
        static_data.set_editor_property("generate_lightmap_u_vs", True)
        task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = [
        str(path)
        for path in (task.get_editor_property("imported_object_paths") or [])
    ]
    if not paths:
        fail("Unreal imported no objects from {}".format(source))
    for path in paths:
        if not path.startswith("/Game/Generated/YACS/"):
            fail("Unreal imported candidate outside generated sandbox: {}".format(path))
    return sorted(paths)


def main() -> None:
    plan_value = os.environ.get("YACS_WORLD_ASSET_SELECTION_PLAN", "")
    cache_value = os.environ.get("YACS_WORLD_ASSET_CACHE", "")
    proof_value = os.environ.get("YACS_WORLD_ASSET_IMPORT_PROOF", "")
    if not plan_value or not cache_value or not proof_value:
        fail(
            "YACS_WORLD_ASSET_SELECTION_PLAN, YACS_WORLD_ASSET_CACHE and "
            "YACS_WORLD_ASSET_IMPORT_PROOF are required"
        )

    plan_path = Path(plan_value).resolve()
    cache_root = Path(cache_value).resolve()
    proof_path = Path(proof_value).resolve()
    payload = json.loads(plan_path.read_text(encoding="utf-8"))

    generated_root = str(payload.get("generated_root", ""))
    if not generated_root.startswith("/Game/Generated/YACS"):
        fail("selection plan generated_root escaped YACS sandbox")

    selections = list(payload.get("selections") or [])
    downloads = list(payload.get("downloads") or [])

    imported_candidates: list[dict[str, Any]] = []
    skipped_approved: list[dict[str, Any]] = []

    for selection in selections:
        source_mode = str(selection.get("source", ""))
        lifecycle = str(selection.get("lifecycle_status", ""))
        provider = str(selection.get("provider", ""))
        asset_id = str(selection.get("provider_asset_id", ""))
        slot = str(selection.get("slot", ""))

        if provider != "polyhaven":
            fail("candidate importer currently accepts only Poly Haven")
        if not SAFE_ID.fullmatch(asset_id):
            fail("unsafe provider asset id {!r}".format(asset_id))

        if source_mode == "catalog" and lifecycle == "approved":
            ue_path = selection.get("ue_asset_path")
            if not isinstance(ue_path, str) or not ue_path.startswith("/Game/"):
                fail("approved catalog selection has no qualified Unreal path")
            skipped_approved.append(
                {
                    "slot": slot,
                    "asset_id": asset_id,
                    "ue_asset_path": ue_path,
                    "reason": "already_qualified",
                }
            )
            continue

        if source_mode != "discovery" or lifecycle != "acquired_candidate":
            fail(
                "automatic candidate import rejected selection state "
                "{}/{}".format(source_mode, lifecycle)
            )

        rows = [
            row
            for row in downloads
            if str(row.get("asset_id", "")) == asset_id
        ]
        if not rows:
            fail("discovered candidate has no downloaded source rows: {}".format(asset_id))

        destination = "{}/{}".format(DESTINATION_ROOT, asset_id)
        imported_paths: list[dict[str, Any]] = []
        for row in sorted(
            rows,
            key=lambda item: (
                str(item.get("map_type") or ""),
                str(item.get("relative_path") or ""),
            ),
        ):
            relative = str(row.get("relative_path", ""))
            if not relative:
                fail("download row has no relative_path")
            source = source_path(cache_root, relative)
            map_type = row.get("map_type")
            is_model = map_type is None and source.suffix.lower() == ".fbx"
            paths = import_source(
                source,
                destination + ("/Geometry" if is_model else "/Textures"),
                model=is_model,
            )
            imported_paths.append(
                {
                    "source": str(source),
                    "source_url": row.get("source_url"),
                    "md5": row.get("md5"),
                    "map_type": map_type,
                    "imported_object_paths": paths,
                }
            )

        imported_candidates.append(
            {
                "slot": slot,
                "provider": provider,
                "asset_id": asset_id,
                "destination": destination,
                "lifecycle_status": "candidate_unqualified",
                "auto_approved": False,
                "imported": imported_paths,
            }
        )

    proof = {
        "schema_version": 1,
        "yacs_asset_candidate_import": "PASS",
        "generated_root": generated_root,
        "candidate_root": DESTINATION_ROOT,
        "selection_plan": str(plan_path),
        "skipped_approved": skipped_approved,
        "imported_candidates": imported_candidates,
        "automatic_acceptance": False,
        "qualification_required": [
            "scale_pivot_orientation",
            "material_wiring",
            "lod_triangle_cost",
            "instancing_behavior",
            "visual_fit",
            "1080p_performance",
        ],
    }
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log(
        "PASS: imported_candidates={} skipped_approved={}".format(
            len(imported_candidates),
            len(skipped_approved),
        )
    )


try:
    main()
except Exception as exc:
    unreal.log_error("[YacsAssetCandidateImport] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
