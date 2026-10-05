#!/usr/bin/env python3
"""Read-only diagnostics of an isolated UE Texture Graph export receipt.

Pixel processing remains in UE. This command only measures and makes previews.
It never grants material admission or modifies a texture asset.
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image

from texture_material_prep import (
    analyze,
    compare_luminance,
    digest,
    measure,
    new_evidence_directory,
    read_source,
    save_panel,
    scale_metadata,
    write_json,
    write_previews,
)

ROLES = ("BaseColor", "Height", "Normal", "Roughness", "MacroMask")


def inspect_bundle(directory: Path) -> tuple[dict, dict[str, np.ndarray]]:
    directory = directory.resolve(strict=True)
    receipt_bytes = (directory / "ue-receipt.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt.get("status") != "exported_review_required":
        raise ValueError("UE export did not complete with readback")
    job = receipt.get("job_id", "")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", job):
        raise ValueError("invalid job identity")
    folder = f"/Game/Generated/YACS/TextureMaterialPrep/Runs/{job}"
    if receipt.get("output_folder") != folder:
        raise ValueError("unexpected asset namespace")
    recipe = receipt["recipe"]
    resolution = recipe["resolution"]
    if type(resolution) is not int or resolution not in (128, 256, 512, 1024):
        raise ValueError("unsupported resolution")
    world = recipe["worldSizeMeters"]
    scale = scale_metadata([world["x"], world["y"]], resolution, resolution)
    if set(receipt["outputs"]) != set(ROLES):
        raise ValueError("missing or additional output role")
    pixels, results = {}, {}
    for role in ROLES:
        entry = receipt["outputs"][role]
        name = f"{role}.png"
        if entry["file"] != name or entry["asset"] != f"{folder}/{role}.{role}":
            raise ValueError("output role/path mismatch")
        if entry["srgb"] is not (role == "BaseColor"):
            raise ValueError("output color space mismatch")
        path = directory / name
        if path.resolve().parent != directory:
            raise ValueError("linked output escapes bundle")
        rgb, identity = read_source(
            path, transfer="srgb" if role == "BaseColor" else "linear"
        )
        if identity["resolution"] != [resolution, resolution]:
            raise ValueError("output resolution mismatch")
        pixels[role] = rgb
        metric = (
            analyze(rgb)
            if role == "BaseColor"
            else measure(rgb.astype(np.float64) / 255)
        )
        if role != "BaseColor":
            metric["screening"] = {
                "policy": "linear-data-measurements-only",
                "status": "review_required",
                "reasons": ["BaseColor thresholds do not apply to data maps"],
            }
        result = {
            "identity": identity,
            "metrics": metric,
            "encoding": "srgb" if role == "BaseColor" else "linear",
        }
        if role == "Normal":
            vectors = rgb.astype(np.float64) / 127.5 - 1
            lengths = np.linalg.norm(vectors, axis=2)
            normalized = vectors / np.maximum(lengths[..., None], 1e-8)
            angles = {}
            for axis, left, right in (
                ("x", normalized[:, 0], normalized[:, -1]),
                ("y", normalized[0], normalized[-1]),
            ):
                values = np.degrees(
                    np.arccos(np.clip(np.sum(left * right, axis=1), -1, 1))
                )
                angles[axis] = {
                    "mean_deg": float(values.mean()),
                    "max_deg": float(values.max()),
                }
            result["normal"] = {
                "unit_length_error_max": float(np.abs(lengths - 1).max()),
                "negative_z_fraction": float((vectors[..., 2] < 0).mean()),
                "wrap_angles": angles,
                "directx_ramp_acceptance": "pending_editor_visual_proof",
            }
        results[role] = result
    baseline, baseline_identity = read_source(directory / "Source.png")
    failures = []
    if (
        float(np.ptp(baseline.astype(float), axis=(0, 1)).max()) > 32
        and float(np.ptp(pixels["BaseColor"].astype(float), axis=(0, 1)).max()) < 2
    ):
        failures.append("BaseColor collapsed to a constant despite a varying source")
    roughness = pixels["Roughness"].astype(float) / 255
    if "roughnessMin" in recipe and (
        roughness.min() < recipe["roughnessMin"] - 2 / 255
        or roughness.max() > recipe["roughnessMax"] + 2 / 255
    ):
        failures.append("Roughness is outside the requested range")
    if results["Normal"]["normal"]["unit_length_error_max"] > 0.03:
        failures.append("Normal vectors are not unit length")
    report = {
        "schema_version": 1,
        "job_id": job,
        "ue_receipt_sha256": digest(receipt_bytes),
        "engine_version": receipt["engine_version"],
        "graph_asset": receipt["graph_asset"],
        "recipe": recipe,
        "scale": scale,
        "source": baseline_identity,
        "outputs": results,
        "delight_comparison": compare_luminance(
            analyze(baseline), analyze(pixels["BaseColor"])
        ),
        "admission": "review_required",
        "technical_validation": "failed" if failures else "diagnostics_complete",
        "failures": failures,
        "reopen_validation": receipt.get("reopen_validation", "pending"),
        "visual_acceptance": "pending",
        "compression_readback": "source_mips_only; GPU compressed sampling pending",
    }
    return report, pixels


def inspect_reopen(directory: Path, job_id: str, pixels: dict) -> dict:
    directory = directory.resolve(strict=True)
    receipt = json.loads((directory / "reopen.json").read_text(encoding="utf-8"))
    if (
        receipt.get("job_id") != job_id
        or receipt.get("status") != "reopened_settings_verified"
    ):
        raise ValueError("reopen receipt does not match the completed job")
    hashes = {}
    for role in ROLES:
        path = directory / (role + ".png")
        if path.resolve().parent != directory:
            raise ValueError("reopened image escapes evidence directory")
        image, identity = read_source(
            path, transfer="srgb" if role == "BaseColor" else "linear"
        )
        if not np.array_equal(image, pixels[role]):
            raise ValueError(f"reopened {role} pixels differ")
        hashes[role] = identity["sha256"]
    return {"status": "verified_pixels_and_settings", "sha256": hashes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--reopen", type=Path, help="fresh-editor reopen evidence directory"
    )
    args = parser.parse_args()
    report, pixels = inspect_bundle(args.bundle)
    if args.reopen:
        report["reopen_validation"] = inspect_reopen(
            args.reopen, report["job_id"], pixels
        )
    run = new_evidence_directory()
    write_json(run / "bundle-validation.json", report)
    for role, rgb in pixels.items():
        target = run / role
        target.mkdir()
        if role == "BaseColor":
            write_previews(target, rgb, report["scale"])
        else:
            im = Image.fromarray(rgb)
            im.thumbnail((256, 256), Image.Resampling.NEAREST)
            for count in (2, 4):
                save_panel(
                    target / f"tiling-{count}x{count}.png",
                    np.tile(np.asarray(im), (count, count, 1)),
                    f"DIAGNOSTIC {role} linear encoded channels | {count}x{count}; visual review required",
                )
    print(run)
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
