"""Probe the UE 5.8 Geometry Script / Dynamic Mesh Python surface for R4.1B.3.

This is intentionally read-only. It does not load or mutate project maps. The
result is a small JSON capability snapshot used to implement the local SP638
earthwork corridor against APIs that actually exist on the trusted yacs-ue58
runner instead of guessing generated Python names.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import traceback

import unreal


INTERESTING_TOKENS = (
    "GeometryScript",
    "DynamicMesh",
    "GeneratedDynamicMesh",
    "GeometryScriptLibrary",
)


def _safe_dir(obj) -> list[str]:
    try:
        return sorted(name for name in dir(obj) if not name.startswith("__"))
    except Exception:
        return []


def main() -> None:
    output_value = os.environ.get("YACS_GEOMETRY_SCRIPT_PROBE_JSON", "")
    if not output_value:
        raise RuntimeError("YACS_GEOMETRY_SCRIPT_PROBE_JSON is required")

    output_path = Path(output_value)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    unreal_names = sorted(
        name for name in dir(unreal)
        if any(token.lower() in name.lower() for token in INTERESTING_TOKENS)
    )

    classes: dict[str, list[str]] = {}
    for name in unreal_names:
        obj = getattr(unreal, name, None)
        members = _safe_dir(obj)
        if members:
            classes[name] = members

    preferred = [
        "DynamicMesh",
        "DynamicMeshActor",
        "DynamicMeshComponent",
        "GeneratedDynamicMeshActor",
        "GeometryScript_MeshEdits",
        "GeometryScript_Primitives",
        "GeometryScript_Normals",
        "GeometryScript_UVs",
        "GeometryScriptSimpleMeshBuffers",
        "GeometryScriptTriangleList",
        "GeometryScriptPrimitiveOptions",
        "GeometryScriptAppendMeshOptions",
    ]
    presence = {name: hasattr(unreal, name) for name in preferred}

    method_docs: dict[str, str] = {}
    for owner_name, method_name in (
        ("DynamicMesh", "append_buffers_to_mesh"),
        ("DynamicMesh", "add_vertex_to_mesh"),
        ("DynamicMesh", "add_triangle_to_mesh"),
        ("DynamicMesh", "recompute_normals"),
        ("GeneratedDynamicMeshActor", "get_dynamic_mesh_component"),
        ("DynamicMeshComponent", "set_dynamic_mesh"),
    ):
        owner = getattr(unreal, owner_name, None)
        method = getattr(owner, method_name, None) if owner is not None else None
        method_docs[f"{owner_name}.{method_name}"] = str(
            getattr(method, "__doc__", "") or ""
        )

    payload = {
        "schema_version": 1,
        "geometry_script_probe": "PASS",
        "engine_version": str(unreal.SystemLibrary.get_engine_version()),
        "matched_unreal_symbols": unreal_names,
        "preferred_symbol_presence": presence,
        "method_docs": method_docs,
        "symbol_members": classes,
        "read_only": True,
        "map_loaded": False,
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    unreal.log(
        "[YacsGeometryScriptProbe] PASS: "
        f"symbols={len(unreal_names)} output={output_path}"
    )
    for name, available in presence.items():
        unreal.log(f"[YacsGeometryScriptProbe] PREFERRED {name}={available}")
    for name, doc in method_docs.items():
        first_line = doc.splitlines()[0] if doc else "<no-doc>"
        unreal.log(f"[YacsGeometryScriptProbe] METHOD {name}: {first_line}")


try:
    main()
except Exception as exc:
    unreal.log_error(f"[YacsGeometryScriptProbe] FAILURE: {exc}")
    unreal.log_error(traceback.format_exc())
    raise
