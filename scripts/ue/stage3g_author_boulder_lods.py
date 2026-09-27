"""Apply and verify the canonical Stage 3G Boulder LOD policy.

This script intentionally mutates only SM_Stage3G_Boulder and writes a JSON
proof. The same policy is also applied by stage3g_import_source_assets.py so a
future source reimport cannot silently regress to LOD0-only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import unreal


BOULDER_PATH = (
    "/Game/Prototype/Environment/Stage3G/Imported/Meshes/"
    "SM_Stage3G_Boulder"
)
LOD_POLICY = (
    (1.00, 1.00),
    (0.50, 0.50),
    (0.20, 0.25),
    (0.08, 0.10),
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def triangles(mesh: unreal.StaticMesh) -> list[int]:
    return [
        int(mesh.get_num_triangles(index))
        for index in range(int(mesh.get_num_lods()))
    ]


def main() -> None:
    proof_value = os.environ.get("YACS_STAGE3G_BOULDER_LOD_PROOF", "")
    if not proof_value:
        fail("YACS_STAGE3G_BOULDER_LOD_PROOF is not set")

    mesh = unreal.EditorAssetLibrary.load_asset(BOULDER_PATH)
    if not mesh or not isinstance(mesh, unreal.StaticMesh):
        fail("canonical Stage 3G Boulder mesh is missing")

    before_lod_count = int(mesh.get_num_lods())
    before_triangles = triangles(mesh)

    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    if not subsystem:
        fail("StaticMeshEditorSubsystem is unavailable")

    options = unreal.StaticMeshReductionOptions()
    options.set_editor_property("auto_compute_lod_screen_size", False)
    reduction_settings = []
    for percent_triangles, screen_size in LOD_POLICY:
        settings = unreal.StaticMeshReductionSettings()
        settings.set_editor_property("percent_triangles", percent_triangles)
        settings.set_editor_property("screen_size", screen_size)
        reduction_settings.append(settings)
    options.set_editor_property("reduction_settings", reduction_settings)

    generated = int(subsystem.set_lods(mesh, options))
    if generated != len(LOD_POLICY):
        fail(
            "set_lods returned {} LODs; expected {}".format(
                generated, len(LOD_POLICY)
            )
        )

    if not unreal.EditorAssetLibrary.save_loaded_asset(
        mesh, only_if_is_dirty=False
    ):
        fail("failed to save SM_Stage3G_Boulder after LOD generation")

    after_lod_count = int(mesh.get_num_lods())
    after_triangles = triangles(mesh)
    if after_lod_count != len(LOD_POLICY):
        fail("saved Boulder has {} LODs".format(after_lod_count))
    if not all(
        after_triangles[index] > after_triangles[index + 1]
        for index in range(len(after_triangles) - 1)
    ):
        fail(
            "LOD triangle counts are not strictly decreasing: {}".format(
                after_triangles
            )
        )

    base = after_triangles[0]
    max_ratios = (1.0, 0.55, 0.25, 0.12)
    for index, max_ratio in enumerate(max_ratios[1:], start=1):
        if after_triangles[index] > int(base * max_ratio) + 32:
            fail(
                "LOD{} triangle count {} exceeds policy ceiling {:.0%}".format(
                    index, after_triangles[index], max_ratio
                )
            )

    nanite = mesh.get_editor_property("nanite_settings")
    proof = {
        "schema_version": 1,
        "stage3g_boulder_lod_authoring": "PASS",
        "asset": BOULDER_PATH,
        "before_lod_count": before_lod_count,
        "before_triangles": before_triangles,
        "after_lod_count": after_lod_count,
        "after_triangles": after_triangles,
        "nanite_enabled": bool(nanite.get_editor_property("enabled")),
        "policy": [
            {
                "percent_triangles": percent,
                "screen_size": screen,
            }
            for percent, screen in LOD_POLICY
        ],
        "note": (
            "Conventional deterministic LODs are used instead of enabling "
            "Nanite; PCG instancing remains the placement strategy."
        ),
    }
    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    unreal.log(
        "[Stage3GBoulderLOD] PASS: {} -> {} LODs; tris={}".format(
            before_lod_count, after_lod_count, after_triangles
        )
    )


try:
    main()
except Exception as exc:
    unreal.log_error("[Stage3GBoulderLOD] FAILURE: {}".format(exc))
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
