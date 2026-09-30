#!/usr/bin/env python3
"""Extract a deterministic native-metric DTM patch for Gate C.3 rider proof.

The patch is cut directly from the prepared 1 m hybrid MASE/Veneto GeoTIFF.
It never samples Unreal Landscape collision and never changes route/physics truth.
Its center is the versioned Gate C proof XY derived from the actual PCGEx rider proof,
not a separately re-selected station on the prepared SP638 source polyline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.windows import Window

TARGET_CRS = "EPSG:32632"
TARGET_BOUNDS = (730406.587, 5148246.775, 738406.587, 5156246.775)
PATCH_EXTENT_M = 512.0
PATCH_VERTEX_COUNT = 513


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def source_heightfield_path() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "PreparedMasePstLidar1x1"
        / "passo_giau_mase_pst_hybrid_1m_8km_epsg32632.tif"
    )


def output_root() -> Path:
    return (
        repository_root()
        / "ExternalAssets"
        / "Terrain"
        / "PassoGiau"
        / "PreparedNearField"
    )


def pipeline_manifest_path() -> Path:
    return repository_root() / "worldgen" / "embark" / "passo_giau_terrain_pipeline.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def proof_hairpin_focus() -> tuple[float, float, dict[str, Any]]:
    path = pipeline_manifest_path()
    if not path.is_file():
        raise FileNotFoundError(f"terrain pipeline manifest is missing: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    proof = (payload.get("proof_locations") or {}).get("gate_c_hairpin")
    if not isinstance(proof, dict):
        raise ValueError("pipeline manifest is missing proof_locations.gate_c_hairpin")

    focus_epsg = proof.get("focus_epsg32632_m")
    focus_ue = proof.get("focus_ue_m")
    if not isinstance(focus_epsg, list) or len(focus_epsg) != 2:
        raise ValueError("Gate C proof focus_epsg32632_m must contain exactly two values")
    if not isinstance(focus_ue, list) or len(focus_ue) != 2:
        raise ValueError("Gate C proof focus_ue_m must contain exactly two values")

    focus_x = float(focus_epsg[0])
    focus_y = float(focus_epsg[1])
    focus_ue_x = float(focus_ue[0])
    focus_ue_y = float(focus_ue[1])
    values = np.asarray([focus_x, focus_y, focus_ue_x, focus_ue_y], dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise ValueError("Gate C proof focus contains non-finite coordinates")

    expected_ue_x = focus_x - TARGET_BOUNDS[0]
    expected_ue_y = TARGET_BOUNDS[3] - focus_y
    coordinate_delta_m = float(
        np.hypot(expected_ue_x - focus_ue_x, expected_ue_y - focus_ue_y)
    )
    if coordinate_delta_m > 0.01:
        raise ValueError(
            "Gate C proof EPSG/UE focus coordinates disagree: "
            f"delta={coordinate_delta_m:.6f} m"
        )

    selection_basis = str(proof.get("selection_basis", "")).strip()
    if not selection_basis:
        raise ValueError("Gate C proof location is missing selection_basis")
    if float(proof.get("max_render_focus_xy_drift_m", -1.0)) <= 0.0:
        raise ValueError("Gate C proof location has invalid max_render_focus_xy_drift_m")

    return focus_x, focus_y, proof


def main() -> int:
    source = source_heightfield_path()
    if not source.is_file():
        raise FileNotFoundError(f"native metric DTM is missing: {source}")

    focus_x, focus_y, proof_location = proof_hairpin_focus()

    with rasterio.open(source) as dataset:
        if dataset.count != 1:
            raise ValueError(f"expected one DTM band, got {dataset.count}")
        if dataset.crs is None or dataset.crs.to_epsg() != 32632:
            raise ValueError(f"expected {TARGET_CRS}, got {dataset.crs}")
        cell_x = abs(float(dataset.transform.a))
        cell_y = abs(float(dataset.transform.e))
        if abs(cell_x - 1.0) > 1e-6 or abs(cell_y - 1.0) > 1e-6:
            raise ValueError(
                f"native DTM spacing drifted from 1 m: x={cell_x} y={cell_y}"
            )

        center_row, center_col = dataset.index(focus_x, focus_y)
        half = PATCH_VERTEX_COUNT // 2
        row_off = center_row - half
        col_off = center_col - half
        if (
            row_off < 0
            or col_off < 0
            or row_off + PATCH_VERTEX_COUNT > dataset.height
            or col_off + PATCH_VERTEX_COUNT > dataset.width
        ):
            raise ValueError(
                "selected C.3 proof-focus patch falls outside native DTM bounds: "
                f"row={center_row} col={center_col}"
            )

        window = Window(
            col_off=col_off,
            row_off=row_off,
            width=PATCH_VERTEX_COUNT,
            height=PATCH_VERTEX_COUNT,
        )
        masked = dataset.read(1, window=window, masked=True).astype(np.float32)
        if np.ma.count_masked(masked):
            raise ValueError(
                f"native C.3 patch contains {int(np.ma.count_masked(masked))} masked samples"
            )
        heights = np.asarray(masked, dtype=np.float32)
        if heights.shape != (PATCH_VERTEX_COUNT, PATCH_VERTEX_COUNT):
            raise ValueError(f"native C.3 patch shape drifted: {heights.shape}")
        if not np.all(np.isfinite(heights)):
            raise ValueError("native C.3 patch contains non-finite heights")

        window_transform = dataset.window_transform(window)
        north_x, north_y = rasterio.transform.xy(
            window_transform,
            0,
            0,
            offset="center",
        )
        south_x, south_y = rasterio.transform.xy(
            window_transform,
            PATCH_VERTEX_COUNT - 1,
            0,
            offset="center",
        )
        east_x, _ = rasterio.transform.xy(
            window_transform,
            0,
            PATCH_VERTEX_COUNT - 1,
            offset="center",
        )

    # Raster rows run north -> south, while build_terrain_skin_mesh expects UE Y
    # to descend across rows. UE Y increases southward, so reverse the rows.
    ue_rows = np.flipud(heights).astype("<f4", copy=False)
    first_ue_x_m = float(north_x) - TARGET_BOUNDS[0]
    first_ue_y_m = TARGET_BOUNDS[3] - float(south_y)
    last_ue_x_m = float(east_x) - TARGET_BOUNDS[0]
    last_ue_y_m = TARGET_BOUNDS[3] - float(north_y)

    out = output_root()
    out.mkdir(parents=True, exist_ok=True)
    binary_path = out / "passo_giau_native_dtm_patch_f32le.bin"
    metadata_path = out / "passo_giau_native_dtm_patch.json"
    binary_path.write_bytes(ue_rows.tobytes(order="C"))

    metadata = {
        "schema_version": 1,
        "proof_gate": "C.3",
        "source": {
            "kind": "prepared native metric DTM",
            "path": str(source.relative_to(repository_root())).replace("\\", "/"),
            "sha256": sha256_file(source),
            "crs": TARGET_CRS,
            "grid_step_m": 1.0,
            "landscape_collision_sampled": False,
        },
        "hairpin_selection": {
            "source": "versioned Gate C proof XY derived from PCGEx rider proof",
            "focus_epsg32632_m": [
                round(focus_x, 3),
                round(focus_y, 3),
            ],
            "focus_ue_m": [
                float(proof_location["focus_ue_m"][0]),
                float(proof_location["focus_ue_m"][1]),
            ],
            "selection_basis": proof_location["selection_basis"],
            "reference_pcgex_focus_distance_m": float(
                proof_location["reference_pcgex_focus_distance_m"]
            ),
            "reference_pcgex_execution_output_sha256": proof_location[
                "reference_pcgex_execution_output_sha256"
            ],
            "reference_workflow_run_id": int(proof_location["reference_workflow_run_id"]),
            "max_render_focus_xy_drift_m": float(
                proof_location["max_render_focus_xy_drift_m"]
            ),
            "canonical_route_authority_preserved": True,
        },
        "grid": {
            "extent_m": PATCH_EXTENT_M,
            "rows": PATCH_VERTEX_COUNT,
            "columns": PATCH_VERTEX_COUNT,
            "sample_count": PATCH_VERTEX_COUNT * PATCH_VERTEX_COUNT,
            "step_x_m": 1.0,
            "step_y_m": 1.0,
            "x_order": "ue_x_ascending",
            "row_order": "ue_y_descending",
            "first_ue_x_m": round(first_ue_x_m, 6),
            "first_ue_y_m": round(first_ue_y_m, 6),
            "last_ue_x_m": round(last_ue_x_m, 6),
            "last_ue_y_m": round(last_ue_y_m, 6),
            "elevation_min_m": round(float(np.min(ue_rows)), 6),
            "elevation_max_m": round(float(np.max(ue_rows)), 6),
        },
        "binary": {
            "file": binary_path.name,
            "dtype": "float32-le",
            "layout": "row-major",
            "byte_count": binary_path.stat().st_size,
            "sha256": sha256_file(binary_path),
        },
        "yacs_policy": {
            "presentation_only": True,
            "authoritative_route_geometry": False,
            "authoritative_physics": False,
            "native_dtm_direct": True,
            "smoothing_applied": False,
            "road_constraints_applied": False,
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "Gate C.3 native DTM patch: "
        f"{PATCH_VERTEX_COUNT}x{PATCH_VERTEX_COUNT} @ 1 m, "
        f"focus_ue=({proof_location['focus_ue_m'][0]:.3f},"
        f"{proof_location['focus_ue_m'][1]:.3f}) m, "
        "selection=pinned-pcgex-proof-xy"
    )
    print(f"[ok] {metadata_path}")
    print(f"[ok] {binary_path}: {binary_path.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
