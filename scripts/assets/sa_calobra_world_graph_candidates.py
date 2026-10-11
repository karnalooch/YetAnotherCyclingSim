"""CPU XY probes for #365 native consumption; no assets, height or contact admission.

The explicit radius is a conservative probe envelope in metres, not an asset
qualification. Native consumers must recheck the qualified transformed envelope
and admitted terrain contact before spawning. Arrays use the authenticated 0.5m
grid; XY is converted to Unreal centimetres only in output records.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import tempfile
import argparse
import json

import numpy as np
import rasterio

from prepare_sa_calobra_world_graph_inputs import canonical, prepare
from read_sa_calobra_pcg_masks import evaluate


@dataclass(frozen=True)
class LatticeRecipe:
    spacing_cells: int
    seed: int
    radius_m: float
    clearance_m: float
    band_priority: tuple[int, int, int]

    def validate(self):
        if type(self.spacing_cells) is not int or self.spacing_cells < 1:
            raise ValueError("Positive integer spacing_cells required")
        if type(self.seed) is not int or not 0 <= self.seed <= 2147483647:
            raise ValueError("Seed outside admitted integer range")
        if (
            type(self.radius_m) not in (int, float)
            or type(self.clearance_m) not in (int, float)
            or not math.isfinite(self.radius_m)
            or self.radius_m <= 0
            or not math.isfinite(self.clearance_m)
            or self.clearance_m < 0
        ):
            raise ValueError(
                "Finite positive radius_m and nonnegative clearance_m required"
            )
        if (
            not isinstance(self.band_priority, tuple)
            or len(self.band_priority) != 3
            or any(type(b) is not int for b in self.band_priority)
            or set(self.band_priority) != {0, 1, 2}
        ):
            raise ValueError(
                "Explicit overlapping selector priority permutation required"
            )


def candidate_id(row: int, col: int) -> str:
    """Geographic anchor identity, independent of seed/order/manifest hashes."""
    return hashlib.sha256(
        canonical(["sa-calobra-EPSG25831-0.5m-origin483000.25,4409516.25-v1", row, col])
    ).hexdigest()


def random_unit(identity: str, seed: int, stream: str) -> float:
    """Named streams avoid changing density draws when other draws are added."""
    if not isinstance(stream, str) or not stream:
        raise ValueError("Explicit randomness stream required")
    digest = hashlib.sha256(canonical([identity, seed, stream])).digest()
    return (int.from_bytes(digest[:8], "big") >> 11) / (1 << 53)


derived_random = random_unit


def point_seed(identity: str, seed: int) -> int:
    return (
        int.from_bytes(
            hashlib.sha256(canonical([identity, seed, "native_point_seed"])).digest()[
                :4
            ],
            "big",
        )
        & 0x7FFFFFFF
    )


def footprint_guard(
    selectors, distances, weights, exclusions, row, col, band, radius_m
):
    """Conservative square enclosing the circular envelope, including cell edges.

    This intentionally overrejects corners rather than miss partial pixel overlap.
    Terrain/support height is unavailable here and remains pending native proof.
    """
    reach = math.floor(radius_m / 0.5 + 0.5)
    r0, r1, c0, c1 = row - reach, row + reach + 1, col - reach, col + reach + 1
    height, width = distances.shape
    if r0 < 0 or c0 < 0 or r1 > height or c1 > width:
        return "footprint_outside_aoi"
    window = np.s_[r0:r1, c0:c1]
    if np.any(selectors[band][window] != 1):
        return "footprint_semantic_or_unknown"
    if np.any(exclusions[window] != 0):
        return "footprint_exclusion_or_unknown"
    d, w = distances[window], weights[band][window]
    if np.any(~np.isfinite(d)) or np.any(d < 0):
        return "footprint_unknown_clearance"
    if np.any(~np.isfinite(w)) or np.any(w < 0) or np.any(w > 1):
        return "footprint_unknown_weight"
    return None


def candidates(selectors, distances, density_weights, exclusion_reasons, recipe):
    """Prepare deterministic sparse XY probes, never native placement approval.

    Highest-priority eligible *centre* band owns an overlapping anchor. Failure
    of its full footprint rejects it; fallback to another band is forbidden.
    All anchors, including rejected ones, are returned for diagnostic inventory.
    """
    recipe.validate()
    if (
        not isinstance(distances, np.ndarray)
        or distances.ndim != 2
        or 0 in distances.shape
    ):
        raise ValueError("Nonempty two-dimensional distance grid required")
    height, width = distances.shape
    if any(
        not isinstance(array, np.ndarray)
        for array in (selectors, density_weights, exclusion_reasons)
    ):
        raise ValueError("Numeric numpy raster arrays required")
    if (
        selectors.shape != (3, height, width)
        or density_weights.shape != selectors.shape
        or exclusion_reasons.shape != distances.shape
    ):
        raise ValueError(
            "Aligned three-band selector/weight and single-band grids required"
        )
    if (
        selectors.dtype != np.uint8
        or exclusion_reasons.dtype != np.uint16
        or not np.issubdtype(distances.dtype, np.floating)
        or not np.issubdtype(density_weights.dtype, np.floating)
    ):
        raise ValueError(
            "uint8 selectors, uint16 exclusions and floating distance/weight grids required"
        )
    if np.any(~np.isin(selectors, [0, 1, 255])):
        raise ValueError("Unrecognized selector state")
    records = []
    for row in range(0, height, recipe.spacing_cells):
        for col in range(0, width, recipe.spacing_cells):
            identity = candidate_id(row, col)
            band = next(
                (b for b in recipe.band_priority if selectors[b, row, col] == 1), None
            )
            record = {
                "candidate_id": identity,
                "source_cell": [row, col],
                "point_seed": point_seed(identity, recipe.seed),
                "world_xy_cm": [col * 50, row * 50],
                "band": band,
                "selected": False,
                "reason": "no_selected_center",
            }
            if band is not None:
                result = evaluate(
                    selectors,
                    distances,
                    col * 50,
                    row * 50,
                    band,
                    recipe.radius_m,
                    recipe.clearance_m,
                )
                record.update(result)
                if result["selected"]:
                    reason = footprint_guard(
                        selectors,
                        distances,
                        density_weights,
                        exclusion_reasons,
                        row,
                        col,
                        band,
                        recipe.radius_m,
                    )
                    if reason is None and random_unit(
                        identity, recipe.seed, "density"
                    ) >= float(density_weights[band, row, col]):
                        reason = "density_thinned"
                    if reason is not None:
                        record.update(selected=False, reason=reason)
            records.append(record)
    return {
        "schema_version": 1,
        "status": "CPU_XY_PROBES_ONLY",
        "placement": False,
        "qualified_assets": [],
        "native_execution": "NOT_RUN",
        "terrain_contact": "PENDING",
        "performance_pass": False,
        "probe_envelope": "unqualified conservative horizontal radius_m; XY only",
        "overlap_policy": "first_selected_center_in_explicit_priority_no_fallback",
        "recipe": {**recipe.__dict__, "band_priority": list(recipe.band_priority)},
        "candidates": records,
    }


def authenticated_inputs(root: Path, config_path: Path, scratch_parent: Path):
    """Authenticate all existing products before loading; scratch is caller-owned.

    Reuses the existing strict input adapter without changing its v1 schema.
    No receipt is admitted as native proof. Caller retains returned source receipt.
    """
    with tempfile.TemporaryDirectory(
        prefix="world-graph-auth-", dir=scratch_parent
    ) as work:
        receipt = prepare(root, config_path, Path(work) / "receipt")
    arrays = []
    for relative, band in (
        ("pcg-masks-v1-2026-10-04/vegetation-selectors.tif", None),
        ("pcg-masks-v1-2026-10-04/exclusion-distance-lower-bound.tif", 1),
        ("mask-transitions-v1a-2026-10-04/vegetation-density-weight.tif", None),
        ("pcg-masks-v1-2026-10-04/exclusion-reasons.tif", 1),
    ):
        with rasterio.open(root / relative) as dataset:
            arrays.append(dataset.read() if band is None else dataset.read(band))
    # Reject concurrent source changes between authentication and raster reads.
    for item in receipt["files"]:
        if (
            hashlib.sha256((root / item["path"]).read_bytes()).hexdigest()
            != item["sha256"]
        ):
            raise ValueError(
                "Authenticated product changed during read: " + item["path"]
            )
    return receipt, tuple(arrays)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spacing-cells", type=int, required=True)
    parser.add_argument("--radius-m", type=float, required=True)
    parser.add_argument("--clearance-m", type=float, required=True)
    parser.add_argument("--band-priority", type=int, nargs=3, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve existing CPU candidate receipt")
    source, arrays = authenticated_inputs(args.root, args.config, args.output.parent)
    recipe = LatticeRecipe(
        args.spacing_cells,
        source["configuration"]["seed"],
        args.radius_m,
        args.clearance_m,
        tuple(args.band_priority),
    )
    result = candidates(*arrays, recipe)
    result["authenticated_inputs"] = source
    result["producer_sha256_lf"] = hashlib.sha256(
        Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    result["fingerprint"] = hashlib.sha256(canonical(result)).hexdigest()
    args.output.mkdir(exist_ok=False)
    (args.output / "world-graph-candidates.json").write_bytes(canonical(result))
    print(
        json.dumps({"status": result["status"], "fingerprint": result["fingerprint"]})
    )
