"""Read and validate normalized GIS candidates without integrating Unreal consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import rasterio

from normalize_sa_calobra_context import sha256


def verify(manifest_path):
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        report.get("status") != "normalized_candidate"
        or report.get("runtime_integration") is not False
    ):
        raise ValueError("Unadmitted candidate state")
    expected = report["fingerprint"]
    content = {k: v for k, v in report.items() if k != "fingerprint"}
    actual = hashlib.sha256(
        json.dumps(
            content,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    if actual != expected:
        raise ValueError("Stale manifest fingerprint")
    if (manifest_path.parent / "failure_receipt.json").exists():
        raise ValueError("Directory contains a failed producer receipt")
    for layer in report["outputs"]:
        relative = Path(layer["path"])
        if relative.is_absolute() or len(relative.parts) != 1:
            raise ValueError("Unsafe output path")
        path = manifest_path.parent / relative
        if (
            not path.is_file()
            or path.stat().st_size != layer["size_bytes"]
            or sha256(path) != layer["sha256"]
        ):
            raise ValueError("Missing/stale derived bytes: " + layer["layer_id"])
        if path.suffix == ".tif":
            with rasterio.open(path) as ds:
                grid = report["grid"]
                if (
                    ds.crs.to_string() != grid["crs"]
                    or ds.width != grid["width"]
                    or ds.height != grid["height"]
                    or list(ds.transform)[:6] != grid["transform"]
                    or ds.nodata != layer["nodata"]
                    or ds.dtypes[0] != layer["dtype"]
                ):
                    raise ValueError(
                        "Consumer grid/NoData/dtype mismatch: " + layer["layer_id"]
                    )
                values = ds.read(1)
                if (
                    hashlib.sha256(values.tobytes(order="C")).hexdigest()
                    != layer["logical_sha256"]
                ):
                    raise ValueError("Logical output mismatch: " + layer["layer_id"])
    return {
        "status": "PASS",
        "fingerprint": expected,
        "layers": len(report["outputs"]),
        "consumer_proof": "GIS read contract only; no Landscape/PCG integration or 2A acceptance",
        "blocked_layers": report["blocked_layers"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest)))
