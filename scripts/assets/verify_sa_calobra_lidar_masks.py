"""Independent reader for LiDAR evidence; byte/read PASS is not planting admission."""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import rasterio


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(manifest_path):
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        report.get("status") != "LIDAR_EVIDENCE_CANDIDATE"
        or report.get("geometry_mutation") is not False
    ):
        raise ValueError("Unadmitted LiDAR candidate state")
    content = {k: v for k, v in report.items() if k != "fingerprint"}
    expected = hashlib.sha256(
        json.dumps(
            content, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    if expected != report["fingerprint"]:
        raise ValueError("Stale LiDAR manifest fingerprint")
    if (manifest_path.parent / "failure-receipt.json").exists():
        raise ValueError("Failed producer directory")
    grid = report["grid"]
    if (grid["crs"], grid["width"], grid["height"], grid["transform"]) != (
        "EPSG:25831",
        4033,
        4033,
        [0.5, 0, 483000, 0, -0.5, 4409516.5],
    ):
        raise ValueError("Unadmitted native grid")
    for row in report["outputs"]:
        relative = Path(row["path"])
        if relative.is_absolute() or len(relative.parts) != 1:
            raise ValueError("Unsafe derived path")
        path = manifest_path.parent / relative
        if path.stat().st_size != row["size_bytes"] or digest(path) != row["sha256"]:
            raise ValueError("Stale derived bytes: " + row["path"])
        if path.suffix == ".tif":
            with rasterio.open(path) as ds:
                if (
                    ds.width,
                    ds.height,
                    ds.count,
                    ds.dtypes[0],
                    ds.nodata,
                    ds.crs.to_string(),
                    list(ds.transform)[:6],
                ) != (
                    4033,
                    4033,
                    row["bands"],
                    row["dtype"],
                    row["nodata"],
                    grid["crs"],
                    grid["transform"],
                ):
                    raise ValueError("Reader grid/dtype/NoData mismatch")
                data = ds.read()
            if hashlib.sha256(data.tobytes()).hexdigest() != row["logical_sha256"]:
                raise ValueError("Logical hash mismatch")
            values = data[data != row["nodata"]]
            if values.size and not np.isfinite(values).all():
                raise ValueError("Nonfinite derived evidence")
            if "fraction" in path.name and ((values < 0) | (values > 1)).any():
                raise ValueError("Return fraction outside [0,1]")
            if "height-candidate" in path.name and (values < 0).any():
                raise ValueError("Negative height admitted")

    def read(name):
        with rasterio.open(manifest_path.parent / name) as ds:
            return ds.read()

    counts = read("class-counts.tif")
    total = counts.sum(axis=0, dtype=np.uint64)
    expected_occupancy = np.zeros(total.shape, dtype=np.uint8)
    for i in range(6):
        expected_occupancy[counts[i] > 0] |= 1 << i
    expected_occupancy[total == 0] = 255
    if not np.array_equal(expected_occupancy, read("class-occupancy.tif")[0]):
        raise ValueError("Occupancy inconsistent with class counts")
    if int(total.sum()) != report["counts"]["accepted_aoi"]:
        raise ValueError("Accepted count mismatch")
    first, vegetation = (
        read("first-return-count.tif")[0],
        read("vegetation-first-return-count.tif")[0],
    )
    if np.any(vegetation > first):
        raise ValueError("Vegetation first returns exceed denominator")
    fraction = read("vegetation-return-fraction.tif")[0]
    expected_fraction = np.full(first.shape, -32767, dtype=np.float32)
    np.divide(vegetation, first, out=expected_fraction, where=first > 0)
    if not np.array_equal(fraction, expected_fraction):
        raise ValueError("Fraction inconsistent with first return counts")
    return {
        "status": "PASS_CANDIDATE_INTEGRITY_ONLY",
        "fingerprint": expected,
        "products": len(report["outputs"]),
        "counts": report["counts"],
        "planting": report["planting"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest)))
