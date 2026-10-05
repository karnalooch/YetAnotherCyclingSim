"""Read-only BaseColor analysis and offline Texture Graph recipe planning.

This CLI does not connect to UE; the opt-in editor adapter is a separate plugin.
Only diagnostic images/JSON are written, into a fresh ignored evidence directory.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import uuid

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path("Saved/RuntimeProof/TextureMaterialPrep")
MAX_BYTES = 64 * 1024 * 1024
MAX_SIDE = 4096
POLICY = "basecolor-screen-v1-provisional"
DEFAULTS = {
    "SeamBlendWidth": 0.05,
    "DeLightStrength": 0.0,
    "ColorGain": [1.0, 1.0, 1.0],
    "HeightStrength": 0.5,
    "NormalStrength": 1.0,
    "RoughnessMin": 0.55,
    "RoughnessMax": 0.9,
    "MacroVariation": 0.0,
    "Seed": 0,
    "GenerateAO": False,
}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def finite_number(value: object, low: float, high: float, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name}: finite number required")
    if not low <= value <= high:
        raise ValueError(f"{name}: expected {low}..{high}")
    return float(value)


def scale_metadata(world_size: list[float] | None, width: int, height: int) -> dict:
    if world_size is None:
        return {"status": "unresolved", "world_size_m": None, "pixels_per_meter": None}
    if not isinstance(world_size, list) or len(world_size) != 2:
        raise ValueError("world size must contain X/Y metres")
    x, y = [finite_number(v, 1e-6, 1e6, "world size") for v in world_size]
    return {
        "status": "proposed",
        "world_size_m": [x, y],
        "pixels_per_meter": [width / x, height / y],
    }


def read_source(path: Path, *, transfer: str = "srgb") -> tuple[np.ndarray, dict]:
    if transfer not in ("srgb", "linear"):
        raise ValueError("unsupported transfer function")
    # Hash exactly the bounded bytes decoded, not a second potentially changed read.
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("source exceeds the 64 MiB analysis limit")
    with Image.open(io.BytesIO(data)) as im:
        if im.format != "PNG" or im.mode not in ("RGB", "RGBA"):
            raise ValueError("only opaque 8-bit RGB/RGBA PNG BaseColor is supported")
        # Pillow can decode a 16-bit RGB PNG as RGB8; reject before silent loss.
        if data[24] != 8:
            raise ValueError("PNG source bit depth must be 8; no silent downconversion")
        if getattr(im, "n_frames", 1) != 1:
            raise ValueError("animated PNG is unsupported")
        if im.info.get("icc_profile") or "chromaticity" in im.info:
            raise ValueError(
                "profiled PNG requires a separately verified color decoder"
            )
        expected_gamma = 0.45455 if transfer == "srgb" else 1.0
        if "gamma" in im.info and abs(im.info["gamma"] - expected_gamma) > 1e-5:
            raise ValueError("PNG gamma conflicts with the declared input transfer")
        w, h = im.size
        if min(w, h) < 8 or max(w, h) > MAX_SIDE:
            raise ValueError("analysis requires dimensions between 8 and 4096 px")
        if "transparency" in im.info:
            raise ValueError("PNG transparency is unsupported for opaque BaseColor")
        raw = np.array(im)
        if (
            transfer == "srgb"
            and raw.shape[-1] == 4
            and not np.all(raw[:, :, 3] == 255)
        ):
            raise ValueError("non-opaque alpha is unsupported")
        rgb = raw[:, :, :3].copy()
    return rgb, {
        "sha256": digest(data),
        "name": path.name,
        "bytes": len(data),
        "resolution": [w, h],
        "bit_depth": 8,
        "role": "BaseColor" if transfer == "srgb" else "linear data RGB; alpha unused",
        "transfer": f"{transfer} declared by caller",
        "provenance": "unverified",
    }


def stats(values: np.ndarray) -> dict:
    return {
        "mean": float(np.mean(values, dtype=np.float64)),
        "p95": float(np.percentile(values, 95)),
        "max": float(np.max(values)),
    }


def seam_metrics(linear: np.ndarray, axis: int) -> dict:
    # Move the measured direction to columns; edge samples retain all channels.
    a = np.swapaxes(linear, axis, 1) if axis != 1 else linear
    wrap = a[:, 0] - a[:, -1]
    edge = stats(np.abs(wrap))
    interior = float(np.mean(np.abs(np.diff(a, axis=1)), dtype=np.float64))
    gradients = np.concatenate(
        (np.abs(wrap - (a[:, -1] - a[:, -2])), np.abs((a[:, 1] - a[:, 0]) - wrap)),
        axis=0,
    )
    return {
        "boundary": edge,
        "interior_step_mean": interior,
        "boundary_to_interior_ratio": edge["mean"] / interior if interior else None,
        "wrap_gradient_mismatch": stats(gradients),
    }


def measure(linear: np.ndarray) -> dict:
    """Measure an H x W x 3 linear RGB array without modifying its pixels."""
    a = np.asarray(linear, dtype=np.float32)
    if a.ndim != 3 or a.shape[2] != 3 or min(a.shape[:2]) < 8:
        raise ValueError("expected H x W x 3 linear RGB with sides >= 8")
    if max(a.shape[:2]) > MAX_SIDE or not np.isfinite(a).all():
        raise ValueError("non-finite or oversized image")
    if np.min(a) < 0 or np.max(a) > 1:
        raise ValueError("linear RGB must be normalized to [0,1]")
    axes = {"x": seam_metrics(a, 1), "y": seam_metrics(a, 0)}
    luminance = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    grid = np.array(
        [
            [cell.mean(dtype=np.float64) for cell in np.array_split(row, 8, axis=1)]
            for row in np.array_split(luminance, 8, axis=0)
        ]
    )
    gy, gx = np.mgrid[-1:1:8j, -1:1:8j]
    design = np.column_stack((np.ones(64), gx.ravel(), gy.ravel()))
    coefficients = np.linalg.lstsq(design, grid.ravel(), rcond=None)[0]
    total = float(np.sum((grid - grid.mean()) ** 2))
    residual = float(np.sum((grid.ravel() - design @ coefficients) ** 2))
    luma = {
        "mean": float(luminance.mean(dtype=np.float64)),
        "quantiles": dict(
            zip(
                ("p01", "p05", "p50", "p95", "p99"),
                np.percentile(luminance, [1, 5, 50, 95, 99]).tolist(),
            )
        ),
        "near_black_fraction": float(np.mean(luminance <= 0.001)),
        "near_white_fraction": float(np.mean(luminance >= 0.999)),
        "grid_8x8_std": float(grid.std()),
        "row_mean_range": float(np.ptp(luminance.mean(axis=1))),
        "column_mean_range": float(np.ptp(luminance.mean(axis=0))),
        "plane_coefficients": coefficients.tolist(),
        "plane_explained_variance": max(0.0, 1 - residual / total)
        if total > 1e-12
        else None,
    }
    reasons = []
    for name, item in axes.items():
        boundary = item["boundary"]
        absolute_limit = 0.002 if item["interior_step_mean"] < 0.001 else 0.025
        ratio = item["boundary_to_interior_ratio"]
        if boundary["mean"] > absolute_limit or boundary["p95"] > 0.075:
            reasons.append(f"{name}: boundary contrast")
        if item["interior_step_mean"] >= 0.001 and ratio > 1.25:
            reasons.append(f"{name}: boundary/interior ratio")
        if item["wrap_gradient_mismatch"]["p95"] > 0.05:
            reasons.append(f"{name}: gradient mismatch")
    return {
        "axes": axes,
        "luminance": luma,
        "channel_means": a.mean(axis=(0, 1), dtype=np.float64).tolist(),
        "channel_clipped_fraction": np.mean(
            (a <= 0.001) | (a >= 0.999), axis=(0, 1)
        ).tolist(),
        "screening": {
            "policy": POLICY,
            "status": "review_required" if reasons else "within_provisional_limits",
            "reasons": reasons,
        },
        "admission": "review_required",
    }


def analyze(rgb: np.ndarray) -> dict:
    if rgb.dtype != np.uint8:
        raise ValueError("analyze expects 8-bit sRGB pixels")
    s = rgb.astype(np.float32) / 255
    return measure(np.where(s <= 0.04045, s / 12.92, ((s + 0.055) / 1.055) ** 2.4))


def compare_luminance(before: dict, after: dict) -> dict:
    b, a = before["luminance"], after["luminance"]
    drift = a["mean"] - b["mean"]
    relative = drift / b["mean"] if b["mean"] >= 0.001 else None
    clipping_delta = (a["near_black_fraction"] + a["near_white_fraction"]) - (
        b["near_black_fraction"] + b["near_white_fraction"]
    )
    low_frequency_delta = a["grid_8x8_std"] - b["grid_8x8_std"]
    return {
        "mean_absolute_drift": drift,
        "mean_relative_drift": relative,
        "clipping_fraction_increase": clipping_delta,
        "low_frequency_std_change": low_frequency_delta,
        "channel_mean_shift": [
            y - x for x, y in zip(before["channel_means"], after["channel_means"])
        ],
        "flags": [
            name
            for name, failed in (
                (
                    "mean_drift",
                    abs(relative) > 0.1 if relative is not None else abs(drift) > 0.001,
                ),
                ("clipping_increase", clipping_delta > 0.005),
            )
            if failed
        ],
        "status": "review_required",
        "physical_delighting_proven": False,
    }


def prepare_recipe(
    source: dict,
    parameters: dict,
    resolution: int = 512,
    world_size: list[float] | None = None,
) -> dict:
    if type(resolution) is not int or resolution not in (256, 512, 1024, 2048, 4096):
        raise ValueError("unsupported explicit output resolution")
    if not isinstance(parameters, dict) or parameters.keys() - DEFAULTS.keys():
        raise ValueError("unknown recipe parameter(s)")
    values = {**DEFAULTS, **parameters}
    for name in (
        "SeamBlendWidth",
        "DeLightStrength",
        "HeightStrength",
        "NormalStrength",
        "RoughnessMin",
        "RoughnessMax",
        "MacroVariation",
    ):
        upper = {"SeamBlendWidth": 0.25, "NormalStrength": 4}.get(name, 1)
        values[name] = finite_number(values[name], 0, upper, name)
    gain = values["ColorGain"]
    if not isinstance(gain, list) or len(gain) != 3:
        raise ValueError("ColorGain requires three linear multipliers")
    values["ColorGain"] = [finite_number(v, 0.5, 2, "ColorGain") for v in gain]
    if values["RoughnessMin"] > values["RoughnessMax"]:
        raise ValueError("RoughnessMin exceeds RoughnessMax")
    if type(values["Seed"]) is not int or not 0 <= values["Seed"] <= 2147483647:
        raise ValueError("Seed must be an integer in 0..2147483647")
    if values["GenerateAO"] is not False:
        raise ValueError("AO is unsupported by the initial foundation")
    candidate = {
        "schema_version": 1,
        "source": source,
        "parameters": values,
        "output_resolution": [resolution, resolution],
        "scale": scale_metadata(world_size, resolution, resolution),
        "graph": "TG_YACS_MaterialPrep",
        "graph_hash": None,
        "engine_build": None,
        "outputs": ["BaseColor", "Height", "Normal", "Roughness", "MacroMask"],
    }
    return {
        **candidate,
        "draft_recipe_id": digest(canonical(candidate).encode()),
        "status": "blocked",
        "error_code": "UE_CONNECTION_REQUIRED",
        "execution_identity": None,
        "blockers": [
            "verified graph, engine binding, routing and export/reopen proof required"
        ],
    }


def inspect_capabilities(project: Path, engine: Path) -> dict:
    build = json.loads(
        (engine / "Engine/Build/Build.version").read_text(encoding="utf-8-sig")
    )
    descriptor = json.loads(project.read_text(encoding="utf-8-sig"))
    plugins = {
        item["Name"]: item.get("Enabled") for item in descriptor.get("Plugins", [])
    }
    paths = {
        "TextureGraph": "Engine/Plugins/TextureGraph/TextureGraph.uplugin",
        "ToolsetRegistry": "Engine/Plugins/Experimental/ToolsetRegistry/ToolsetRegistry.uplugin",
        "ModelContextProtocol": "Engine/Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin",
    }
    facts = {}
    for name, relative in paths.items():
        path = engine / relative
        entry = {
            "installed": path.is_file(),
            "project_explicitly_enabled": plugins.get(name) is True,
        }
        if path.is_file():
            data = path.read_bytes()
            desc = json.loads(data.decode("utf-8-sig"))
            entry.update(
                {
                    "descriptor_sha256": digest(data),
                    "version_name": desc.get("VersionName"),
                    "enabled_by_default": desc.get("EnabledByDefault", False),
                }
            )
        facts[name] = entry
    return {
        "schema_version": 1,
        "status": "blocked",
        "error_code": "UE_CONNECTION_REQUIRED",
        "engine_build": build,
        "plugins": facts,
        "probe": "filesystem_only",
        "runtime_reflection_verified": False,
        "mcp_registered": False,
        "supported": ["analyze_basecolor_png", "draft_recipe"],
        "unsupported": [
            "render_preview",
            "export_pbr_set",
            "ue_readback",
            "mcp_routing",
        ],
    }


def new_evidence_directory(root: Path = ROOT) -> Path:
    root = root.resolve()
    parent = root / EVIDENCE
    if not parent.resolve().is_relative_to(root):
        raise ValueError("evidence directory escapes repository through a link")
    parent.mkdir(parents=True, exist_ok=True)
    run = parent / uuid.uuid4().hex
    run.mkdir(exist_ok=False)
    return run


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def save_panel(path: Path, pixels: np.ndarray, label: str) -> None:
    im = Image.fromarray(pixels)
    canvas = Image.new("RGB", (max(640, im.width), im.height + 42), "#222222")
    canvas.paste(im, (0, 42))
    ImageDraw.Draw(canvas).text((8, 8), label, fill="white")
    with path.open("xb") as stream:
        canvas.save(stream, format="PNG")


def write_previews(run: Path, rgb: np.ndarray, scale: dict) -> None:
    im = Image.fromarray(rgb)
    im.thumbnail((256, 256), Image.Resampling.LANCZOS)
    small = np.asarray(im)
    h, w = rgb.shape[:2]
    label = f"DIAGNOSTIC sRGB | source {w}x{h} | tile metres {scale['world_size_m']}"
    sampling = "native tile pixels" if im.size == (w, h) else "downsampled tile"
    for n in (2, 4):
        save_panel(
            run / f"tiling-{n}x{n}.png",
            np.tile(small, (n, n, 1)),
            label + f"\n{n}x{n}; preview tile {im.width}x{im.height}; {sampling}",
        )
    save_panel(
        run / "half-offset-preview.png",
        np.roll(small, (small.shape[0] // 2, small.shape[1] // 2), (0, 1)),
        label + "\nHalf-offset diagnostic preview",
    )
    band = min(32, min(h, w) // 2)
    rows = slice(max(0, h // 2 - 256), min(h, h // 2 + 256))
    cols = slice(max(0, w // 2 - 256), min(w, w // 2 + 256))
    save_panel(
        run / "seam-x-1to1.png",
        np.concatenate((rgb[rows, -band:], rgb[rows, :band]), axis=1),
        label + "\nX wrap; central rows; native pixels 1:1",
    )
    save_panel(
        run / "seam-y-1to1.png",
        np.concatenate((rgb[-band:, cols], rgb[:band, cols]), axis=0),
        label + "\nY wrap; central columns; native pixels 1:1",
    )
    corner = np.concatenate((rgb[-band:], rgb[:band]), axis=0)
    corner = np.concatenate((corner[:, -band:], corner[:, :band]), axis=1)
    save_panel(
        run / "corner-1to1.png",
        corner,
        label + "\nFour-corner junction; native pixels 1:1",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser(
        "capabilities", help="filesystem facts only; never claims reflection readiness"
    )
    cap.add_argument("--project", type=Path, required=True)
    cap.add_argument("--engine-root", type=Path, required=True)
    for command in ("analyze", "plan"):
        item = sub.add_parser(command)
        item.add_argument("--source", type=Path, required=True)
        item.add_argument("--input-color-space", choices=("srgb",), required=True)
        item.add_argument("--world-size-m", type=float, nargs=2)
        if command == "analyze":
            item.add_argument(
                "--baseline", type=Path, help="same-size sRGB PNG before processing"
            )
        else:
            item.add_argument(
                "--parameters", type=Path, help="JSON object of proposed TG parameters"
            )
            item.add_argument("--resolution", type=int, default=512)
    args = parser.parse_args(argv)
    try:
        if args.command == "capabilities":
            print(
                json.dumps(
                    inspect_capabilities(args.project, args.engine_root), indent=2
                )
            )
            return 0
        rgb, source = read_source(args.source)
        scale = scale_metadata(args.world_size_m, *source["resolution"])
        if args.command == "plan":
            parameters = (
                json.loads(args.parameters.read_text(encoding="utf-8"))
                if args.parameters
                else {}
            )
            report = prepare_recipe(
                source, parameters, args.resolution, args.world_size_m
            )
        else:
            report = {
                "schema_version": 1,
                "source": source,
                "scale": scale,
                "representation": "uncompressed PNG decoded to linear RGB",
                "metrics": analyze(rgb),
                "ue_validation": "not_run",
                "visual_acceptance": "pending",
            }
            if args.baseline:
                baseline, identity = read_source(args.baseline)
                if baseline.shape != rgb.shape:
                    raise ValueError(
                        "baseline and candidate dimensions must match; no implicit resampling"
                    )
                report["baseline"] = identity
                report["delight_comparison"] = compare_luminance(
                    analyze(baseline), report["metrics"]
                )
        run = new_evidence_directory()
        write_json(run / f"{args.command}.json", report)
        if args.command == "analyze":
            write_previews(run, rgb, scale)
        write_json(
            run / "receipt.json",
            {
                "status": "evidence_written",
                "admission": "review_required",
                "files": {
                    p.name: digest(p.read_bytes())
                    for p in sorted(run.iterdir())
                    if p.is_file()
                },
            },
        )
        print(run)
        return 0
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        print(f"texture-material-prep: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
