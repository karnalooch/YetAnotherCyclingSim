"""Pack retained Lesson04 caches for an isolated native Houdini Engine repair.

Houdini HeightField Layer supplies Source+Manual. An integer-grid copy packs
retained samples into overlapping tiles without interpolation. Native Layer
replacement on these grids was measured to introduce 1.98 mm edge differences;
this adapter preserves exact source samples. No HIP is opened or saved.
"""

import argparse
import hashlib
import json
from pathlib import Path

import hou
import numpy as np

from lesson04_height_encoding import (
    additive_codes,
    height_codes,
    h22_transport,
    north_first_uv,
)

SCALE_Z = 585.9375  # +/-1500 m, 0.0457763671875 m per uint16 step, origin Z=0.
BASE_LAYER = "Source_Manual_Lesson04"
DELTA_LAYER = "Lesson04_Procedural_Delta"


def height(geometry):
    return next(
        p
        for p in geometry.prims()
        if isinstance(p, hou.Volume) and p.attribValue("name") == "height"
    )


def values(geometry):
    p = height(geometry)
    return np.frombuffer(p.allVoxelsAsString(), np.float32).reshape(
        p.resolution()[1], p.resolution()[0]
    )


def node(parent, kind, name, inputs=(), **parms):
    n = parent.createNode(kind, name)
    for i, inp in enumerate(inputs):
        n.setInput(i, inp)
    n.setParms(parms)
    return n


def copy_registered(destination_geo, source_geo):
    """Copy coincident samples; retain existing DTM padding, never resample."""
    dst, src = height(destination_geo), height(source_geo)
    origin_d = np.asarray(dst.indexToPos((0, 0, 0)))
    origin_s = np.asarray(src.indexToPos((0, 0, 0)))
    dx = np.asarray(dst.indexToPos((1, 0, 0))) - origin_d
    dy = np.asarray(dst.indexToPos((0, 1, 0))) - origin_d
    np.testing.assert_allclose(
        np.asarray(src.indexToPos((1, 0, 0))) - origin_s, dx, atol=1e-7, rtol=0
    )
    np.testing.assert_allclose(
        np.asarray(src.indexToPos((0, 1, 0))) - origin_s, dy, atol=1e-7, rtol=0
    )
    assert dx[0] > 0 and dy[2] < 0 and abs(dx[2]) + abs(dy[0]) < 1e-7
    offset = np.array(
        [(origin_d[0] - origin_s[0]) / dx[0], (origin_d[2] - origin_s[2]) / dy[2]]
    )
    np.testing.assert_allclose(offset, np.rint(offset), atol=1e-5, rtol=0)
    col, row = np.rint(offset).astype(int)
    target = values(destination_geo).copy()
    reference = values(source_geo)
    r0, r1 = max(0, row), min(reference.shape[0], row + target.shape[0])
    c0, c1 = max(0, col), min(reference.shape[1], col + target.shape[1])
    assert r1 > r0 and c1 > c0, "No registered overlap"
    target[r0 - row : r1 - row, c0 - col : c1 - col] = reference[r0:r1, c0:c1]
    return target


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root", type=Path, required=True)
    ap.add_argument("--transfer-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    args = ap.parse_args()
    source, old, out = (
        p.resolve() for p in (args.source_root, args.transfer_root, args.output_root)
    )
    if out.exists():
        raise ValueError(
            "Use a new output directory; existing evidence is never overwritten"
        )
    if out == source or source in out.parents or out == old or old in out.parents:
        raise ValueError("Derived output must be outside the retained sources")
    if hou.applicationVersionString() != "22.0.466":
        raise ValueError(
            "This encoder requires independently verified Houdini Engine 22.0.466"
        )
    out.mkdir(parents=True)
    geo = hou.node("/obj").createNode(
        "geo", "LESSON04_TRANSFER_ONLY", run_init_scripts=False
    )
    inputs = {}

    def load(path, name, only_height=True):
        inputs[str(path)] = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
        n = node(geo, "file", name, file=path.as_posix())
        return (
            node(geo, "blast", name + "_HEIGHT", [n], group="@name=height", negate=1)
            if only_height
            else n
        )

    s = load(source / "cache/source_working_05m.bgeo.sc", "SOURCE", False)
    m = load(
        source
        / "Pegasus/Landscape/Landscape Heightfield Layers/Pegasus_Landscape_Layer_2_Manual_Edits.bgeo.sc",
        "MANUAL",
    )
    b = node(
        geo,
        "heightfield_layer",
        "SOURCE_PLUS_MANUAL",
        [s, m],
        mode="add",
        layer="height",
    )
    f = load(source / "cache/lesson04_working_material_05m.bgeo.sc", "LESSON04_FINAL")
    report = {
        "schema_version": 1,
        "houdini_version": hou.applicationVersionString(),
        "target_map": "/Game/Generated/YACS/Lesson04Repair_20261018/L_SaCalobra_Lesson04_Test",
        "scale_z": SCALE_Z,
        "origin_z_cm": 0,
        "output_mode": 1,
        "base_layer": BASE_LAYER,
        "delta_layer": DELTA_LAYER,
        "quantization_step_m": SCALE_Z / 12800,
        "tiles": [],
        "input_sha256": inputs,
        "native_reopen": "NOT_RUN",
        "visual_acceptance": False,
        "performance_pass": False,
    }
    seams = []
    for name in (
        "SaCalobra_Detail_0_0",
        "SaCalobra_Detail_1_0",
        "SaCalobra_Detail_0_1",
        "SaCalobra_Detail_1_1",
        "SaCalobra_Context_Valid",
    ):
        print("PREPARE " + name, flush=True)
        original = load(old / (name + ".bgeo.sc"), name, False)
        fg = original.geometry()
        if "Context" not in name:
            ba = copy_registered(fg, b.geometry())
            fa = copy_registered(fg, f.geometry())
        else:
            cs = load(source / "cache/context_source.bgeo.sc", "CONTEXT_SOURCE")
            cf = load(
                source / "cache/lesson04_context_material.bgeo.sc", "CONTEXT_FINAL"
            )
            ba = copy_registered(fg, cs.geometry())
            fa = copy_registered(fg, cf.geometry())
        p = height(fg)
        res = p.resolution()
        pos = tuple(p.indexToPos((0, 0, 0)))
        dx = p.indexToPos((1, 0, 0))[0] - pos[0]
        assert res == ((2017, 2017, 1) if "Context" in name else (3811, 5081, 1)), res
        codes = height_codes(fa, SCALE_Z)
        origin, inv = north_first_uv(pos, res, dx)
        entry = {
            "name": name,
            "resolution": res,
            "index0": pos,
            "spacing_m": dx,
            "uv_origin_cm": origin,
            "uv_inverse_cm": inv,
            "min_m": float(fa.min()),
            "max_m": float(fa.max()),
            "expected_codes_sha256": hashlib.sha256(codes.tobytes()).hexdigest(),
            "files": {},
            "file_sha256": {},
        }
        report["tiles"].append(entry)
        np.save(out / (name + "_expected.npy"), fa)
        np.save(out / (name + "_base.npy"), ba)
        if "Context" not in name:
            seams.append(
                (fa[0].copy(), fa[-1].copy(), fa[:, 0].copy(), fa[:, -1].copy())
            )
        for layer, q in (
            (BASE_LAYER, height_codes(ba, SCALE_Z)),
            (DELTA_LAYER, additive_codes(ba, fa, SCALE_Z)),
        ):
            g = hou.Geometry()
            g.merge(fg)
            # Visibility remains in the copied map's retained source layer. Height
            # writes must not clear/re-normalize that independent ownership mask.
            g.deletePrims(
                [x for x in g.prims() if x.attribValue("name") != "height"], True
            )
            height(g).setAllVoxelsFromString(h22_transport(q, SCALE_Z).tobytes())
            attrs = {
                "unreal_output_name": name,
                "unreal_landscape_output_mode": 1,
                "unreal_landscape_editlayer_name": layer,
                "unreal_landscape_editlayer_clear": 1,
                "unreal_landscape_editlayer_type": 1,
                "unreal_bake_folder": "/Game/Generated/YACS/Lesson04Repair_20261018/Baked",
            }
            for key, val in attrs.items():
                a = g.findPrimAttrib(key) or g.addAttrib(hou.attribType.Prim, key, val)
                for prim in g.prims():
                    prim.setAttribValue(a, val)
            filename = name + "_" + layer + ".bgeo.sc"
            g.saveToFile(str(out / filename))
            entry["files"][layer] = filename
            with (out / filename).open("rb") as stream:
                entry["file_sha256"][layer] = hashlib.file_digest(
                    stream, "sha256"
                ).hexdigest()
            g.clear()
        print("SAVED " + name, flush=True)
    # Complete shared edges, not sparse point probes.
    errors = [
        np.max(np.abs(seams[0][3] - seams[1][2])),
        np.max(np.abs(seams[2][3] - seams[3][2])),
        np.max(np.abs(seams[2][1] - seams[0][0])),
        np.max(np.abs(seams[3][1] - seams[1][0])),
    ]
    report["full_edge_max_error_m"] = [float(x) for x in errors]
    assert max(errors) == 0, errors
    for path, digest in inputs.items():
        assert (
            hashlib.file_digest(Path(path).open("rb"), "sha256").hexdigest() == digest
        ), path
    (out / "manifest.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {"output": str(out), "shared_edge_errors": report["full_edge_max_error_m"]}
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
