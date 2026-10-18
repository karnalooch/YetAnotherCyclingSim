import argparse
import json
import pathlib
import hou
import numpy as np
import hashlib
from lesson04_height_encoding import decode_h22_readback

ap = argparse.ArgumentParser()
ap.add_argument("--export-root", type=pathlib.Path, required=True)
ap.add_argument("--transfer-root", type=pathlib.Path, required=True)
ap.add_argument(
    "--allow-mismatch",
    action="store_true",
    help="Write baseline diagnostics without admitting the repair",
)
args = ap.parse_args()
folder = args.export_root.resolve()
transfer = args.transfer_root.resolve()
manifest = json.loads((transfer / "manifest.json").read_text())
assert (folder / "complete.json").exists(), "Require a completed native export"
results = []
edges = {}
inventory = {r["name"]: r for r in json.loads((folder / "inventory.json").read_text())}
for tile in manifest["tiles"]:
    name = tile["name"]
    g = hou.Geometry()
    g.loadFromFile(str(folder / (name + ".bgeo.sc")))
    p = next(
        p
        for p in g.prims()
        if isinstance(p, hou.Volume) and p.attribValue("name") == "height"
    )
    assert list(p.resolution()) == tile["resolution"]
    np.testing.assert_allclose(
        p.indexToPos((0, 0, 0)), tile["index0"], atol=0.0001, rtol=0
    )
    origin = np.asarray(p.indexToPos((0, 0, 0)))
    np.testing.assert_allclose(
        np.asarray(p.indexToPos((1, 0, 0))) - origin,
        [tile["spacing_m"], 0, 0],
        atol=0.0001,
        rtol=0,
    )
    np.testing.assert_allclose(
        np.asarray(p.indexToPos((0, 1, 0))) - origin,
        [0, 0, -tile["spacing_m"]],
        atol=0.0001,
        rtol=0,
    )
    actual = (
        np.frombuffer(p.allVoxelsAsString(), np.float32)
        .reshape(tile["resolution"][1], tile["resolution"][0])
        .copy()
    )
    codes, actual = decode_h22_readback(actual, inventory[name]["scale"][2])
    expected = np.load(transfer / (name + "_expected.npy"), mmap_mode="r")
    err = actual.astype(np.float64) - expected
    np.save(folder / (name + "_height.npy"), actual)
    results.append(
        {
            "name": name,
            "samples": actual.size,
            "minimum_m": float(actual.min()),
            "maximum_m": float(actual.max()),
            "error_min_m": float(err.min()),
            "error_max_m": float(err.max()),
            "error_max_abs_m": float(np.max(np.abs(err))),
            "error_mean_abs_m": float(np.mean(np.abs(err))),
            "error_p95_abs_m": float(np.percentile(np.abs(err), 95)),
        }
    )
    results[-1]["native_uint16_sha256"] = hashlib.sha256(codes.tobytes()).hexdigest()
    results[-1]["all_codes_match_expected"] = (
        results[-1]["native_uint16_sha256"] == tile["expected_codes_sha256"]
    )
    edges[name] = [
        actual[0].copy(),
        actual[-1].copy(),
        actual[:, 0].copy(),
        actual[:, -1].copy(),
    ]
    for p in g.prims():
        if isinstance(p, hou.Volume) and p.attribValue("name") == "visibility":
            mask = (
                np.frombuffer(p.allVoxelsAsString(), np.float32)
                .reshape(tile["resolution"][1], tile["resolution"][0])
                .copy()
            )
            np.save(folder / (name + "_visibility.npy"), mask)
            results[-1]["visibility"] = {
                "min": float(mask.min()),
                "max": float(mask.max()),
                "hidden_vertices": int(np.count_nonzero(mask >= 0.5)),
            }
    g.clear()
seams = []
for a, ae, b, be in [
    ("0_0", 3, "1_0", 2),
    ("0_1", 3, "1_1", 2),
    ("0_1", 1, "0_0", 0),
    ("1_1", 1, "1_0", 0),
]:
    x = edges["SaCalobra_Detail_" + a][ae]
    y = edges["SaCalobra_Detail_" + b][be]
    seams.append(
        {"tiles": [a, b], "samples": len(x), "max_abs_m": float(np.max(np.abs(x - y)))}
    )
matched = (
    all(
        r["all_codes_match_expected"]
        and r["error_max_abs_m"] <= manifest["quantization_step_m"] / 2 + 1e-8
        for r in results
    )
    and all(r["max_abs_m"] == 0 for r in seams)
    and all(inventory[r["name"]]["scale"][2] == manifest["scale_z"] for r in results)
)
report = {
    "status": "MATCH" if matched else "MISMATCH",
    "native_export": str(folder),
    "tiles": results,
    "complete_shared_edges": seams,
    "total_samples_including_duplicate_edges": sum(x["samples"] for x in results),
    "visual_acceptance": False,
    "performance_pass": False,
}
(folder / "measurements.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report), flush=True)

if not args.allow_mismatch and not matched:
    raise RuntimeError(
        "Native Landscape differs from the prepared Lesson04 target; see measurements.json"
    )
