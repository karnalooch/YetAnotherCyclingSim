"""Append source-owned material UV fields; never edit source mesh buffers.

UV0 stores (distance from the inner pavement edge, distance along that edge)
in centimetres. Optional UV1 measures the actual outer edge independently.
Each authenticated outer quad gets affine, nondegenerate charts. World-
projected PBR textures do not use these charts for texture scale.
Only selected top triangles are set; walls/interior/parapets have no new UVs.

The stock UE 5.8 SetMeshTriangleUVs operation creates all three overlay elements
in one call. Installed source and Python reflection are recorded before use:
https://dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/GeometryScript/UVs/SetMeshTriangleUVs
https://dev.epicgames.com/documentation/unreal-engine/BlueprintAPI/GeometryScript/UVs/SetNumUVChannels
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import struct

from scripts.ci import official_mcp_bob_session as session
from scripts.ue import road_shoulder_sources as sources

CHANNEL = 0
OUTER_CHANNEL = 1
HASH_FORMAT = "blake3-256-le-i32-f64-material-uv-v1"
ENGINE_VERSION = "5.8.2-56702186+++UE5+Release-5.8"
API_ROOT = "Plugins/Runtime/GeometryScripting/Source/GeometryScriptingCore/"
API_FILES = {
    API_ROOT + "Public/GeometryScript/MeshUVFunctions.h": ("SetNumUVSets", "SetMeshTriangleUVs"),
    API_ROOT + "Private/MeshUVFunctions.cpp": ("SetNumUVSets", "SetMeshTriangleUVs"),
    API_ROOT + "Public/GeometryScript/GeometryScriptTypes.h": ("FGeometryScriptUVTriangle", "UV0", "UV1", "UV2"),
    API_ROOT + "Public/GeometryScript/MeshQueryFunctions.h": ("GetNumUVSets",),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _float32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def triangle_coordinates(owner):
    """Derive actual metric distance from immutable source, without mutation."""
    return _triangle_coordinates(owner, outer=False)


def outer_triangle_coordinates(owner):
    """UV1 measures the actual outer edge, including source miter and taper.

    The second coordinate remains distance along that same edge. Packing inner
    and outer distances into one chart would make parallel strips degenerate.
    This source field does not classify Landscape contact or move either edge.
    """
    return _triangle_coordinates(owner, outer=True)


def _triangle_coordinates(owner, *, outer):
    require(owner.get("material_target") is True and owner.get("kind") != "parapet",
            "Material edge coordinates require a source-owned outer top")
    sections = owner.get("sections_cm")
    require(isinstance(sections, (list, tuple)) and 3 <= len(sections) <= sources.MAX_SECTIONS
            and all(isinstance(row, (list, tuple)) and len(row) == 27 for row in sections),
            "Material edge source cross-sections are incomplete")
    coordinates = []
    for section, (current, following) in enumerate(zip(sections, sections[1:])):
        for column in (0, 25):
            a, b = current[column:column + 2]
            c, d = following[column:column + 2]
            points = (a, b, c, d)
            require(all(isinstance(point, (tuple, list)) and len(point) == 3
                        and all(type(v) in (int, float) and math.isfinite(v) for v in point)
                        for point in points), "Nonfinite material edge source coordinate")
            origin, end, opposite = ((a, c, b) if column == 0 else (b, d, a)) if outer else (
                (b, d, a) if column == 0 else (a, c, b))
            dx, dy = end[0] - origin[0], end[1] - origin[1]
            length = math.hypot(dx, dy)
            require(1e-6 < length <= 10000.0, "Degenerate or unbounded material edge segment")
            tx, ty = dx / length, dy / length
            width = tx * (opposite[1] - origin[1]) - ty * (opposite[0] - origin[0])
            require(abs(width) > 1e-6, "Degenerate source shoulder width")
            sign = 1.0 if width > 0 else -1.0
            uv = []
            for point in points:
                px, py = point[0] - origin[0], point[1] - origin[1]
                across = sign * (tx * py - ty * px)
                along = tx * px + ty * py
                require(-0.0001 <= across <= 100.0 and abs(along) <= 10000.0,
                        "Material edge field escaped the source shoulder domain")
                uv.append((_float32(max(0.0, across)), _float32(along)))
            for side, corners in enumerate(((0, 1, 2), (1, 3, 2))):
                triangle = tuple(uv[index] for index in corners)
                p, q, r = triangle
                area = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
                require(abs(area) > 1e-6, "Material UV chart would create a degenerate tangent basis")
                coordinates.append((section * 52 + column * 2 + side, triangle))
    require([tid for tid, _ in coordinates] == list(owner.get("selected_triangle_ids", [])),
            "Material edge coordinates differ from the exact selected source top IDs")
    return coordinates


def native_api_evidence(api):
    """Verify the installed 5.8 APIs, including the actual struct constructor."""
    require(api.SystemLibrary.get_engine_version() == ENGINE_VERSION,
            "Material edge authoring requires the proved UE 5.8.2 build")
    engine = Path(api.Paths.convert_relative_path_to_full(api.Paths.engine_dir())).resolve()
    installed = {}
    for relative, symbols in API_FILES.items():
        path = session._safe_path(engine, relative)
        identity = session._identity(path, 4 * 1024 * 1024)
        text = path.read_text(encoding="utf-8-sig")
        require(all(symbol in text for symbol in symbols), "Installed material UV API source differs")
        installed[relative] = {**identity, "verified_symbols": list(symbols)}
    signatures = {}
    require(callable(getattr(api, "DynamicMesh", None)), "Native transient UV probe mesh is unavailable")
    probe = api.DynamicMesh()
    for name, method, parameters in (
        ("set_num_uv_sets", api.GeometryScript_UVs.set_num_uv_sets, ("target_mesh", "num_uv_sets")),
        ("set_mesh_triangle_u_vs", api.GeometryScript_UVs.set_mesh_triangle_u_vs,
         ("target_mesh", "uv_set_index", "triangle_id", "u_vs", "defer_change_notifications")),
        ("GeometryScriptUVTriangle", api.GeometryScriptUVTriangle, ("uv0", "uv1", "uv2")),
        ("DynamicMesh.get_num_uv_sets", probe.get_num_uv_sets, ("get_num_uv_sets",)),
    ):
        doc = str(getattr(method, "__doc__", "") or "")
        require(callable(method) and len(doc) <= 32768 and all(p in doc for p in parameters),
                "Installed material UV Python signature differs: " + name)
        signatures[name] = {"signature": doc[:2048], "sha256": hashlib.sha256(doc.encode()).hexdigest()}
    # This is a real native round trip on an unrelated transient mesh. Symbol
    # presence cannot prove whether this engine clamps zero to one. Fail before
    # modifying a source owner if the stock API cannot restore zero UV channels.
    round_trip = verify_zero_uv_round_trip(api, probe)
    return {"engine_version": ENGINE_VERSION, "installed_sources": installed,
            "native_signatures": signatures, "zero_uv_round_trip": round_trip,
            "engine_source_redistributed": False}


def verify_zero_uv_round_trip(api, probe):
    require(api.GeometryScript_UVs.set_num_uv_sets(probe, 1) == probe
            and probe.get_num_uv_sets() == 1, "Native UV preflight could not create exactly one channel")
    require(api.GeometryScript_UVs.set_num_uv_sets(probe, 0) == probe
            and probe.get_num_uv_sets() == 0,
            "Native SetNumUVSets clamps/rejects zero; exact source UV rollback is unavailable")
    return {"transient_mesh_only": True, "requested_counts": [1, 0], "observed_counts": [1, 0],
            "zero_channels_restored": True, "consumer_mesh_mutated": False}


def apply(api, component, coordinates, original_uv_set_count):
    """Append only channel zero on the proved UV-free source; one call per top."""
    require(original_uv_set_count == CHANNEL, "The edge shader requires the proved zero-UV source")
    _append(api, component, coordinates, CHANNEL)


def apply_outer(api, component, coordinates):
    """Append UV1 only after the caller has witnessed the complete UV0 stage."""
    _append(api, component, coordinates, OUTER_CHANNEL)


def _append(api, component, coordinates, channel):
    mesh = component.get_dynamic_mesh()
    require(mesh.get_num_uv_sets() == channel, "Material UV append would replace an existing channel")
    require(api.GeometryScript_UVs.set_num_uv_sets(mesh, channel + 1) == mesh,
            "Native material UV channel creation failed")
    for tid, uv in coordinates:
        values = api.GeometryScriptUVTriangle(
            uv0=api.Vector2D(*uv[0]), uv1=api.Vector2D(*uv[1]), uv2=api.Vector2D(*uv[2]))
        result = api.GeometryScript_UVs.set_mesh_triangle_u_vs(
            mesh, channel, tid, values, defer_change_notifications=True)
        require(len(result) == 2 and result[0] == mesh and result[1] is True,
                "Native material UV setter rejected source triangle " + str(tid))
    component.notify_mesh_modified()


def rollback(api, component, original_uv_set_count):
    """Discard only the appended channel; the caller verifies the full old hash."""
    require(original_uv_set_count == CHANNEL, "Material UV rollback escaped its source prefix")
    mesh = component.get_dynamic_mesh()
    require(mesh.get_num_uv_sets() in (original_uv_set_count, original_uv_set_count + 1),
            "Material UV rollback would discard an unowned channel")
    require(api.GeometryScript_UVs.set_num_uv_sets(mesh, original_uv_set_count) == mesh,
            "Native appended material UV removal failed")
    require(mesh.get_num_uv_sets() == original_uv_set_count, "Native rollback did not restore zero UV channels")
    component.notify_mesh_modified()


def rollback_outer(api, component):
    """Remove only the explicitly owned UV1, preserving the complete UV0 stage."""
    mesh = component.get_dynamic_mesh()
    require(mesh.get_num_uv_sets() in (OUTER_CHANNEL, OUTER_CHANNEL + 1),
            "Outer material UV rollback would discard an unowned channel")
    require(api.GeometryScript_UVs.set_num_uv_sets(mesh, OUTER_CHANNEL) == mesh
            and mesh.get_num_uv_sets() == OUTER_CHANNEL,
            "Native outer material UV removal did not restore the UV0 prefix")
    component.notify_mesh_modified()


def verify_native(before, snapshot, owner):
    """Require every new triangle coordinate and every original corner byte."""
    return _verify_field(before, snapshot, owner, CHANNEL)


def verify_outer_native(inner_stage, snapshot, owner):
    """Read the real UV1 witness and compare its full UV0/normal prefix hash."""
    require(all(inner_stage.get(key) == snapshot.get("summary", {}).get(key)
                for key in ("vertex_count", "triangle_count", "positions_indices_blake3")),
            "Outer material field changed source geometry")
    return _verify_field(inner_stage, snapshot, owner, OUTER_CHANNEL)


def verify_inner_stage(before, owner, stage):
    """Validate the retained UV0 stage used by a final native prefix comparison.

    The caller's immutable saved receipt supplies this earlier native witness;
    it is not a new read of UV0. The final UV1 inspection must independently
    match its complete normal/UV0 prefix before this chain is admitted.
    """
    require(isinstance(stage, dict) and set(stage) == {"summary", "edge_attribute"},
            "The retained inner material UV stage is missing")
    summary, attribute = stage["summary"], stage["edge_attribute"]
    require(isinstance(summary, dict) and set(summary) == set(before)
            and before.get("uv_set_count") == CHANNEL and summary.get("uv_set_count") == OUTER_CHANNEL
            and all(summary.get(key) == before.get(key)
                    for key in ("vertex_count", "triangle_count", "positions_indices_blake3"))
            and all(isinstance(summary.get(key), str) and re.fullmatch(r"[0-9a-f]{64}", summary[key])
                    for key in ("positions_indices_blake3", "triangle_corner_normals_uv_blake3", "material_ids_blake3"))
            and isinstance(attribute, dict), "Retained UV0 stage geometry or native hashes differ")
    expected = _field_receipt(before, owner, CHANNEL, attribute.get("uv_blake3"))
    require(attribute == expected, "Retained UV0 stage no longer matches the source edge field")
    return expected


def _verify_field(before, snapshot, owner, channel):
    witness = snapshot.get("material_uv")
    require(before["uv_set_count"] == channel and snapshot["summary"]["uv_set_count"] == channel + 1
            and isinstance(witness, dict) and type(witness.get("preserved_uv_set_count")) is int
            and witness.get("preserved_uv_set_count") == channel
            and witness.get("hash_format") == HASH_FORMAT
            and witness.get("preserved_triangle_corner_normals_uv_blake3")
            == before["triangle_corner_normals_uv_blake3"],
            "Original normals/UV prefix changed or the appended material channel is missing")
    coordinates = outer_triangle_coordinates(owner) if channel == OUTER_CHANNEL else triangle_coordinates(owner)
    expected = [[tid, *(v for uv in triangle for v in uv)] for tid, triangle in coordinates]
    actual = witness.get("triangles")
    require(type(witness.get("set_triangle_count")) is int and witness["set_triangle_count"] == len(expected)
            and isinstance(actual, list) and len(actual) == len(expected),
            "New material UV escaped the exact selected tops or touched a wall/interior/parapet")
    for wanted, received in zip(expected, actual, strict=True):
        require(isinstance(received, list) and len(received) == 7
                and type(received[0]) is int and received[0] == wanted[0]
                and all(type(v) in (int, float) and math.isfinite(v) for v in received[1:])
                and all(abs(a - b) <= 0.0001 for a, b in zip(wanted[1:], received[1:], strict=True)),
                "New material UV source-distance witness differs")
    return _field_receipt(before, owner, channel, witness.get("uv_blake3"))


def _field_receipt(before, owner, channel, uv_hash):
    require(isinstance(uv_hash, str) and re.fullmatch(r"[0-9a-f]{64}", uv_hash),
            "Complete appended material UV digest is missing")
    coordinates = outer_triangle_coordinates(owner) if channel == OUTER_CHANNEL else triangle_coordinates(owner)
    expected = [[tid, *(v for uv in triangle for v in uv)] for tid, triangle in coordinates]
    return {"channel": channel, "units": "centimetres",
            "coordinates": "outer_distance_and_along_edge" if channel == OUTER_CHANNEL else "inner_distance_and_along_edge",
            "set_triangle_count": len(expected), "unset_nonselected_triangles": True,
            "hash_format": HASH_FORMAT, "uv_blake3": uv_hash,
            "source_coordinates_sha256": hashlib.sha256(json.dumps(
                expected, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
            "original_normals_uv_prefix_blake3": before["triangle_corner_normals_uv_blake3"]}
