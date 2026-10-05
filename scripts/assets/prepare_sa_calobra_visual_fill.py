"""Fill presentation gaps without modifying evidence or placement exclusions."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image


def _four_neighbor_sum(values):
    """Return four-connected neighbor sums with constant-zero AOI boundaries."""

    source = np.asarray(values, dtype=np.float32)
    if source.ndim != 2:
        raise ValueError("Expected a 2D array")
    result = np.zeros_like(source, dtype=np.float32)
    result[1:, :] += source[:-1, :]
    result[:-1, :] += source[1:, :]
    result[:, 1:] += source[:, :-1]
    result[:, :-1] += source[:, 1:]
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def repair(weights, availability, reasons, steps=8):
    """Propagate at most 4 m along four-connected non-road/building cells.

    Existing placement rectangles/water buffers are deliberately not shading
    barriers. Unknown evidence remains unknown in the separate source raster.
    No nearby donor means neutral mineral, never invented vegetation.
    """
    if weights.dtype != np.uint8 or weights.shape != (*availability.shape, 4):
        raise ValueError("Expected RGBA8 weights on the availability grid")
    if reasons.shape != availability.shape or not np.isin(availability, [0, 255]).all():
        raise ValueError("Invalid availability/reason grid")
    if (weights[..., :3].sum(axis=2) > 255).any() or (reasons == 65535).any():
        raise ValueError("Invalid weights or unresolved reason NoData")
    if not 1 <= steps <= 16:
        raise ValueError("Unbounded propagation distance")
    hard = (reasons & (1 | 8)) != 0
    known = (availability == 255) & ~hard
    support = known.copy()
    values = weights[..., :3].astype(np.float32) / 255
    values[~known] = 0
    provenance = np.where(known, 0, 2).astype(np.uint8)
    provenance[hard] = 3
    for _ in range(steps):
        count = _four_neighbor_sum(support)
        fill = ~support & ~hard & (count > 0)
        if not fill.any():
            break
        for c in range(3):
            total = _four_neighbor_sum(values[..., c])
            values[..., c][fill] = total[fill] / count[fill]
        support[fill] = True
        provenance[fill] = 1
    # One bounded, low-strength pass. Four-connected neighbors cannot cross a
    # one-cell protected road/building; no wraparound at the AOI boundary.
    count = _four_neighbor_sum(support)
    smooth = support & (count > 0)
    for c in range(3):
        total = _four_neighbor_sum(values[..., c])
        values[..., c][smooth] = (
            0.75 * values[..., c][smooth] + 0.25 * total[smooth] / count[smooth]
        )
    values[hard] = 0
    encoded = np.rint(np.clip(values, 0, 1) * 255).astype(np.uint8)
    excess = np.maximum(encoded.sum(axis=2, dtype=np.int16) - 255, 0)
    largest = encoded.argmax(axis=2)
    for c in range(3):
        selected = largest == c
        encoded[..., c][selected] -= excess[selected].astype(np.uint8)
    result = weights.copy()
    result[..., :3] = encoded
    result[hard] = 0
    return result, provenance


def read_manifest(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    content = {k: v for k, v in data.items() if k != "fingerprint"}
    actual = hashlib.sha256(
        json.dumps(
            content, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    if actual != data["fingerprint"] or data["geometry_mutation"] is not False:
        raise ValueError("Manifest identity mismatch")
    for row in data["outputs"]:
        if Path(row["path"]).name != row["path"]:
            raise ValueError("Unsafe product path")
        if digest(path.parent / row["path"]) != row["sha256"]:
            raise ValueError("Source product identity mismatch")
    return data


def prepare(source, placement, output):
    if output.exists():
        raise FileExistsError("Preserve previous package; use a new directory")
    src = read_manifest(source)
    pcg = read_manifest(placement)
    if src["grid"] != pcg["grid"] or src["grid"]["pixel_size_m"] != 0.5:
        raise ValueError("Frozen grid mismatch")
    if "dry-channel" not in src["semantics"]["A"]:
        raise ValueError("Expected separate availability and dry-channel alpha")
    weights = np.array(Image.open(source.parent / "material-weights.png"))
    available = np.array(Image.open(source.parent / "sample-availability.png"))
    with rasterio.open(placement.parent / "exclusion-reasons.tif") as ds:
        if (
            list(ds.transform)[:6] != src["grid"]["transform"]
            or ds.crs.to_string() != src["grid"]["crs"]
        ):
            raise ValueError("Placement raster registration mismatch")
        reasons = ds.read(1)
    result, provenance = repair(weights, available, reasons)
    output.mkdir(parents=True)
    products = {
        "material-weights.png": result,
        "sample-availability.png": available,
        "inference-kind.png": provenance,
    }
    rows = []
    for name, pixels in products.items():
        path = output / name
        Image.fromarray(pixels).save(path)
        if not np.array_equal(np.array(Image.open(path)), pixels):
            raise ValueError("Output readback mismatch")
        rows.append(
            {"path": name, "sha256": digest(path), "size_bytes": path.stat().st_size}
        )
    report = {
        "status": "PRESENTATION_VISUAL_FILL_CANDIDATE",
        "geometry_mutation": False,
        "production_planting": "NOT_ADMITTED",
        "current_cover_admitted": False,
        "grid": src["grid"],
        "world_mapping": src["world_mapping"],
        "sources": [
            {"path": str(p.resolve()), "sha256": digest(p)} for p in (source, placement)
        ],
        "outputs": rows,
        "source_semantics": src["semantics"],
        "semantics": {
            "R": "Low vegetation appearance, including bounded neighbor inference; no planting authority",
            "G": "Forest-floor appearance, including bounded neighbor inference; no planting authority",
            "B": "Rock appearance, including bounded neighbor inference; no new geology classification",
            "A": "Retained artistic dry-channel appearance, zero over pavement/buildings",
            "neutral": "Mineral residual 1-sum(RGB); all-zero RGB means mineral, not a hole",
            "availability": "Unchanged original observations; inferred pixels remain unknown",
            "inference_kind": "0 observed, 1 neighbor fill, 2 neutral fallback, 3 protected road/building",
        },
        "recipe": {
            "neighbor_steps": 8,
            "maximum_path_m": 4,
            "smoothing_fraction": 0.25,
            "hard_barrier_bits": [1, 8],
            "far_fallback": "neutral mineral residual",
            "unknown_evidence": "retained; inference is appearance only",
            "sampling": "linear data, bilinear for appearance only; placement remains nearest",
        },
        "counts": {
            "observed": int((provenance == 0).sum()),
            "neighbor_filled": int((provenance == 1).sum()),
            "neutral_fallback": int((provenance == 2).sum()),
            "protected_road_building": int((provenance == 3).sum()),
            "original_unknown": int((available == 0).sum()),
            "rgb_sum_max": int(result[..., :3].sum(axis=2).max()),
        },
        "producer_file": "scripts/assets/prepare_sa_calobra_visual_fill.py",
        "producer_sha256_lf": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "references": [
            "https://www.sidefx.com/docs/houdini/heightfields/masking.html",
            "https://dev.epicgames.com/documentation/unreal-engine/landscape-materials-in-unreal-engine",
        ],
    }
    report["fingerprint"] = hashlib.sha256(
        json.dumps(
            report, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    (output / "material-input-manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["counts"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--placement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.placement, args.output)
