"""Bounded PEG-05 extraction rehearsal from a retained cache; never edits terrain.

Run with hython. This is not full-route cliff delivery or pavement clearance.
The original HDA performs extraction; HOM only binds inputs and records proof.
"""

import argparse
import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

try:
    import hou
except ImportError:
    hou = None


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def inventory(args):
    """Inventory mask windows against all six source route parts; no authoring."""
    import numpy as np
    from PIL import Image
    from shapely.geometry import LineString, box
    from shapely.ops import unary_union

    route = json.loads(args.inventory.read_text())
    if (
        route["source_sha256"]
        != "6520b92486b5d1c63353b8253d388ab21d380c78fda119849311be8344d8ae36"
    ):
        raise RuntimeError("Unexpected full-route source")
    if (
        sha(route["source_path"]) != route["source_sha256"]
        or len(route["parts_epsg25831_m"]) != 6
        or sum(map(len, route["parts_epsg25831_m"])) != 522
        or not all(
            math.isfinite(v)
            for part in route["parts_epsg25831_m"]
            for xy in part
            for v in xy
        )
    ):
        raise RuntimeError("Route identity or finite 6-part/522-point layout differs")
    idmap = Path(
        "D:/yacs/project/SourceContent/Pegasus/Landscape/Textures/T_PE_Terrain_IDmap.png"
    )
    if sha(idmap) != "cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3":
        raise RuntimeError("Current IDMap changed; reverify source orientation first")
    Image.MAX_IMAGE_PIXELS = 300000000
    with Image.open(idmap) as image:
        ids = np.asarray(image)
    if ids.shape != (16000, 16000) or ids.dtype != np.uint8:
        raise RuntimeError("Unexpected current IDMap layout")
    lines = [
        LineString([(e - 483650, 4409899.5 - n) for e, n in part])
        for part in route["parts_epsg25831_m"]
    ]
    union = unary_union(lines)
    buffers = {64: union.buffer(64), 500: union.buffer(500)}
    if not box(-4000, -4000, 3936, 3936).covers(buffers[500]):
        raise RuntimeError("Route corridor exceeds enumerated window domain")
    windows = []
    for iz in range(62):
        for ix in range(62):
            x, z = -4000 + ix * 128, -4000 + iz * 128
            footprint = box(x, z, x + 128, z + 128)
            if not footprint.intersects(buffers[500]):
                continue
            # PNG row increases with Houdini Z; raw volume j runs opposite.
            pixels = ids[iz * 256 : (iz + 1) * 256, ix * 256 : (ix + 1) * 256]
            count = int(np.count_nonzero(pixels == 191))
            windows.append(
                {
                    "ix": ix,
                    "iz": iz,
                    "center_xz": [x + 64, z + 64],
                    "pixel_origin_x_row": [ix * 256, iz * 256],
                    "cliff_pixels": count,
                    "intersects_64m_road_band": footprint.intersects(buffers[64]),
                    "route_parts": [
                        i
                        for i, line in enumerate(lines)
                        if footprint.intersects(line.buffer(64))
                    ],
                }
            )
    roadside = [
        w for w in windows if w["intersects_64m_road_band"] and w["cliff_pixels"]
    ]
    chosen = max(roadside, key=lambda w: w["cliff_pixels"])
    record = {
        "status": "CURRENT_IDMAP_FULL_ROUTE_WINDOW_INVENTORY_NOT_GEOMETRY",
        "producer_sha256": sha(__file__),
        "route_record": str(args.inventory),
        "route_record_sha256": sha(args.inventory),
        "route_source_sha256": route["source_sha256"],
        "parts": len(lines),
        "axis_mapping": "X=E-483650; Z=4409899.5-N; registered by parent four-control-point audit",
        "idmap": str(idmap),
        "idmap_sha256": sha(idmap),
        "class_code": 191,
        "window_m": 128,
        "window_voxels": 256,
        "road_band_m": 64,
        "road_band_status": "candidate inventory band, not a user-specified cliff extent or pavement exclusion",
        "working_corridor_m": 500,
        "windows_500m": len(windows),
        "windows_64m_with_cliff": len(roadside),
        "roadside_cliff_pixels": sum(w["cliff_pixels"] for w in roadside),
        "chosen_window": chosen,
        "windows": windows,
        "coverage_limit": "Window footprint intersects band; cliff pixels are whole-window counts, not exact corridor area. Visibility filtering and pavement exclusions pending.",
        "full_route_geometry": "NOT RUN",
        "unreal": "NOT RUN",
    }
    if args.output.exists():
        raise RuntimeError("Inventory output exists")
    args.output.mkdir(parents=True)
    (args.output / "inventory.json").write_text(
        json.dumps(record, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps({k: v for k, v in record.items() if k != "windows"}))


def batch(args):
    """Serial native source-stage execution and independent planar validation."""
    import numpy as np
    import shapely
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union

    record = json.loads(args.batch.read_text())
    route_path = Path(record["route_record"])
    if sha(route_path) != record["route_record_sha256"]:
        raise RuntimeError("Route record changed")
    route = json.loads(route_path.read_text())
    if sha(route["source_path"]) != record["route_source_sha256"]:
        raise RuntimeError("Original route changed")
    road = unary_union(
        [
            LineString([(e - 483650, 4409899.5 - n) for e, n in part])
            for part in route["parts_epsg25831_m"]
        ]
    )
    windows = [
        w
        for w in record["windows"]
        if w["intersects_64m_road_band"] and w["cliff_pixels"]
    ]
    if args.output.exists():
        raise RuntimeError("Batch output exists; preserve checkpoint")
    args.output.mkdir(parents=True)
    results = []
    seams = {}
    started = time.time()
    for w in windows[: args.batch_limit]:
        while (args.output / "PAUSE").exists():
            time.sleep(1)
        ix, iz = w["ix"], w["iz"]
        out = args.output / f"core_{ix}_{iz}"
        reused = False
        if args.reuse_batch:
            old = args.reuse_batch / f"core_{ix}_{iz}"
            if (old / "validation.json").exists():
                prior = json.loads((old / "receipt.json").read_text())
                if (
                    prior["producer_sha256"]
                    != "ece78990c3ed57138441e4065e899d0060df6ce76f1a2b1169c878034a794aa5"
                    or sha(old / "cliffs.bgeo.sc") != prior["output_sha256"]
                    or sha(old / "candidate.hiplc") != prior["hip_sha256"]
                ):
                    raise RuntimeError("Reuse checkpoint identity changed")
                reload = json.loads((old / "fresh_reopen.json").read_text())
                if (
                    reload["output_disk_reload"] != "PASS"
                    or reload["output_sha256"] != prior["output_sha256"]
                ):
                    raise RuntimeError("Reuse lacks bound disk reload")
                out = old
                reused = True
        command = [
            "D:/yacs/tools/houdini-22.0.466/bin/hython.exe",
            str(Path(__file__).resolve()),
            "--current-crop",
            str(args.batch.resolve()),
            "--window",
            str(ix),
            str(iz),
            "--halo",
            "8",
            "--pre-flow",
            "--road-exclusion",
            "--exclusion-width",
            "12",
            "--otls",
            str(args.otls),
            "--output",
            str(out),
        ]
        if not reused:
            with (args.output / f"core_{ix}_{iz}.log").open("w") as log:
                subprocess.run(
                    command, stdout=log, stderr=subprocess.STDOUT, check=True
                )
        vertices = []
        faces = []
        for line in (out / "cliffs.obj").read_text().splitlines():
            if line.startswith("v "):
                vertices.append(list(map(float, line.split()[1:4])))
            elif line.startswith("f "):
                faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
        vertices = np.asarray(vertices).reshape(-1, 3)
        if not np.isfinite(vertices).all():
            raise RuntimeError("Nonfinite mesh")
        distances = shapely.distance(
            [Polygon(vertices[f][:, [0, 2]]) for f in faces], road
        )
        minimum = float(min(distances)) if len(distances) else None
        if len(distances) and not np.isfinite(distances).all():
            raise RuntimeError("Nonfinite polygon clearance")
        if minimum is not None and minimum < 5:
            raise RuntimeError(f"Core {ix},{iz} violates 5m clearance: {minimum}")
        cx, cz = w["center_xz"]
        edges = {}
        for side, axis, value in [
            ("left", 0, cx - 64),
            ("right", 0, cx + 64),
            ("bottom", 2, cz - 64),
            ("top", 2, cz + 64),
        ]:
            edges[side] = set()
            for face in faces:
                for a, b in zip(face, face[1:] + face[:1]):
                    if (
                        abs(vertices[a, axis] - value) < 0.001
                        and abs(vertices[b, axis] - value) < 0.001
                    ):
                        pair = tuple(
                            sorted(
                                (
                                    tuple(vertices[a]),
                                    tuple(vertices[b]),
                                )
                            )
                        )
                        if pair[0] != pair[1]:
                            edges[side].add(pair)
        checks = []
        for neighbor, side, opposite in [
            ((ix - 1, iz), "left", "right"),
            ((ix, iz - 1), "bottom", "top"),
        ]:
            if neighbor in seams:
                aa = np.asarray(list(edges[side])).reshape(-1, 2, 3)
                bb = np.asarray(list(seams[neighbor][opposite])).reshape(-1, 2, 3)
                equal = len(aa) == len(bb)
                maximum = 0.0
                if equal and len(aa):
                    direct = np.linalg.norm(
                        aa[:, None, :, :] - bb[None, :, :, :], axis=3
                    ).max(axis=2)
                    reverse = np.linalg.norm(
                        aa[:, None, :, :] - bb[None, :, ::-1, :], axis=3
                    ).max(axis=2)
                    distances = np.minimum(direct, reverse)
                    matches = distances.argmin(axis=1)
                    maximum = float(distances[np.arange(len(aa)), matches].max())
                    equal = maximum <= 0.001 and len(set(matches.tolist())) == len(bb)
                checks.append(
                    {
                        "neighbor": neighbor,
                        "equal_mm": equal,
                        "comparison": "bijective boundary edge endpoint pairs within 1mm",
                        "max_endpoint_distance_m": maximum,
                        "counts": [len(edges[side]), len(seams[neighbor][opposite])],
                    }
                )
                if not equal:
                    raise RuntimeError(f"Core {ix},{iz} mismatched seam {neighbor}")
        seams[(ix, iz)] = edges
        if not reused:
            with (out / "reopen.log").open("w") as log:
                subprocess.run(
                    [
                        command[0],
                        command[1],
                        "--reopen",
                        "--otls",
                        str(args.otls),
                        "--output",
                        str(out),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
        evidence = {
            "core": [ix, iz],
            "output_directory": str(out),
            "reused_verified_checkpoint": reused,
            "native_producer_sha256": json.loads((out / "receipt.json").read_text())[
                "producer_sha256"
            ],
            "polygons": len(faces),
            "minimum_planar_polygon_distance_m": minimum,
            "seams": checks,
            "output_sha256": sha(out / "cliffs.bgeo.sc"),
            "output_disk_reload": "PASS",
        }
        (args.output / f"validation_{ix}_{iz}.json").write_text(
            json.dumps(evidence, indent=2, allow_nan=False) + "\n"
        )
        if not reused:
            (out / "validation.json").write_text(
                json.dumps(evidence, indent=2, allow_nan=False) + "\n"
            )
        results.append(evidence)
        (args.output / "batch.json").write_text(
            json.dumps(
                {
                    "producer_sha256": sha(__file__),
                    "inventory_sha256": sha(args.batch),
                    "completed": len(results),
                    "target": len(windows),
                    "elapsed_seconds": time.time() - started,
                    "raw_source_geometry_only": True,
                    "production_admission": False,
                    "cores": results,
                },
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
        print(
            json.dumps(
                {
                    "completed": len(results),
                    "target": len(windows),
                    "core": [ix, iz],
                    "minimum_clearance_m": minimum,
                    "elapsed_seconds": round(time.time() - started, 1),
                }
            ),
            flush=True,
        )


def joined_crop_source(args, manifest, manifest_path, center):
    """Official native Tile Splice (volumesplice) on intersect-cropped inputs."""
    g = hou.node("/obj").createNode("geo", "SOURCE_TILE_SPLICE")
    pieces = []
    proof = []
    files = []
    extent = 64 + args.halo
    for tile in manifest["tiles"]:
        first, last = tile["height_output"]["pos0"], tile["height_output"]["pos_max"]
        if (
            max(first[0], last[0]) < center[0] - extent
            or min(first[0], last[0]) > center[0] + extent
            or max(first[2], last[2]) < center[1] - extent
            or min(first[2], last[2]) > center[1] + extent
        ):
            continue
        path = manifest_path.parent / tile["file"]
        if sha(path) != tile["sha256"]:
            raise RuntimeError("Join source tile changed")
        f = g.createNode("file")
        f.parm("file").set(str(path))
        c = g.createNode("heightfield_crop")
        c.setInput(0, f)
        c.setParms(
            {
                "cropmode": 2,
                "sizex": 2 * extent,
                "sizey": 2 * extent,
                "tx": center[0],
                "tz": center[1],
            }
        )
        geo = hou.Geometry(c.geometry())
        samples = 0
        for v in geo.prims():
            original = next(
                t
                for t in f.geometry().prims()
                if t.attribValue("name") == v.attribValue("name")
            )
            nx, ny, _ = v.resolution()
            rx, ry, _ = original.resolution()
            for j in range(ny):
                for i in range(nx):
                    ij = original.posToIndex(v.indexToPos((i, j, 0)))
                    ii, jj = round(ij[0]), round(ij[1])
                    if not (0 <= ii < rx and 0 <= jj < ry) or v.voxel(
                        (i, j, 0)
                    ) != original.voxel((ii, jj, 0)):
                        raise RuntimeError("Native intersect crop changes/pads source")
                    samples += 1
        target = args.output / ("source_piece_" + str(len(pieces)) + ".bgeo.sc")
        geo.saveToFile(str(target))
        pieces.append(geo)
        files.append(target)
        proof.append(
            {
                "tile": tile["file"],
                "sha256": tile["sha256"],
                "source_samples_exact": samples,
                "piece_sha256": sha(target),
            }
        )
        c.destroy()
        f.destroy()
    if len(pieces) < 2:
        raise RuntimeError("Join needs at least two intersecting verified tiles")
    merge = g.createNode("merge")
    for i, path in enumerate(files):
        f = g.createNode("file")
        f.parm("file").set(str(path))
        merge.setInput(i, f)
    previous = merge
    for name in ["height", "visibility"]:
        splice = g.createNode("volumesplice")
        splice.setInput(0, previous)
        splice.setParms({"group": "@name=" + name, "deleteorig": 1})
        previous = splice
    joined = previous.geometry()
    samples = 0
    for v in joined.prims():
        nx, ny, _ = v.resolution()
        originals = [
            next(
                p for p in geo.prims() if p.attribValue("name") == v.attribValue("name")
            )
            for geo in pieces
        ]
        for j in range(ny):
            for i in range(nx):
                values = []
                for original in originals:
                    ij = original.posToIndex(v.indexToPos((i, j, 0)))
                    ii, jj = round(ij[0]), round(ij[1])
                    rx, ry, _ = original.resolution()
                    if 0 <= ii < rx and 0 <= jj < ry:
                        if (
                            max(
                                abs(a - b)
                                for a, b in zip(
                                    original.indexToPos((ii, jj, 0)),
                                    v.indexToPos((i, j, 0)),
                                )
                            )
                            > 0.001
                        ):
                            raise RuntimeError(
                                "Native splice lattice shifts beyond 1mm"
                            )
                        values.append(original.voxel((ii, jj, 0)))
                if len(set(values)) > 1:
                    raise RuntimeError("Overlapping admitted source tiles disagree")
                if not values or v.voxel((i, j, 0)) not in values:
                    raise RuntimeError(
                        "Splice interpolates or leaves uncovered source samples"
                    )
                samples += 1
    path = args.output / "joined_source.bgeo.sc"
    joined.saveToFile(str(path))
    return (
        {"file": "joined_source.bgeo.sc", "sha256": sha(path)},
        path,
        {
            "native_node": "volumesplice",
            "cropmode": 2,
            "pieces": proof,
            "joined_samples_exact": samples,
            "uncovered": 0,
        },
    )


def current_crop(args):
    """Native crop of admitted FINAL transport height plus indexed current IDMap."""
    import numpy as np
    import OpenImageIO as oi

    record = json.loads(args.current_crop.read_text())
    chosen = (
        record["chosen_window"]
        if args.window is None
        else next(w for w in record["windows"] if [w["ix"], w["iz"]] == args.window)
    )
    center = chosen["center_xz"]
    manifest_path = Path("D:/yacs/work/lesson07-consumer-update-20261020/manifest.json")
    if (
        sha(manifest_path)
        != "760425da4a8fa46c4e201a74f0a70ced802f14dc992d1569885167fe73a8978e"
    ):
        raise RuntimeError("Verified current transport manifest changed")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["accepted_l06_sha256"]
        != "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24"
    ):
        raise RuntimeError("Unexpected final height source")
    candidates = []
    for t in manifest["tiles"]:
        first, last = t["height_output"]["pos0"], t["height_output"]["pos_max"]
        if (
            min(first[0], last[0]) <= center[0] - 64 - args.halo
            and max(first[0], last[0]) >= center[0] + 64 + args.halo
            and min(first[2], last[2]) <= center[1] - 64 - args.halo
            and max(first[2], last[2]) >= center[1] + 64 + args.halo
        ):
            candidates.append(t)
    if args.output.exists():
        raise RuntimeError("Output exists")
    args.output.mkdir(parents=True)
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    join_proof = None
    if not candidates:
        tile, path, join_proof = joined_crop_source(
            args, manifest, manifest_path, center
        )
    else:
        tile = candidates[0]
        path = manifest_path.parent / tile["file"]
    if sha(path) != tile["sha256"] or sha(record["idmap"]) != record["idmap_sha256"]:
        raise RuntimeError("Tile or current IDMap identity changed")
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    g = hou.node("/obj").createNode("geo", "CLIFF_REHEARSAL")
    src = g.createNode("file", "ADMITTED_FINAL_TILE")
    src.parm("file").set(str(path))
    crop = g.createNode("heightfield_crop", "CURRENT_128M_CROP")
    crop.setInput(0, src)
    crop.setParms(
        {
            "cropmode": 0,
            "sizex": 128 + 2 * args.halo,
            "sizey": 128 + 2 * args.halo,
            "tx": center[0],
            "tz": center[1],
        }
    )
    crop.cook(force=True)
    geo = hou.Geometry(crop.geometry())
    layers = {v.attribValue("name"): v for v in geo.prims()}
    if set(layers) != {"height", "visibility"} or any(
        not (
            256 + 4 * args.halo <= v.resolution()[0] <= 258 + 4 * args.halo
            and 256 + 4 * args.halo <= v.resolution()[1] <= 258 + 4 * args.halo
            and v.resolution()[2] == 1
        )
        for v in layers.values()
    ):
        raise RuntimeError(
            "Unexpected native crop layout: "
            + str({k: v.resolution() for k, v in layers.items()})
            + str(crop.errors())
        )
    nx, ny, _ = layers["height"].resolution()
    source_volumes = {v.attribValue("name"): v for v in src.geometry().prims()}
    measured = {}
    for name, v in layers.items():
        first = v.indexToPos((0, 0, 0))
        last = v.indexToPos((nx - 1, ny - 1, 0))
        # Native crop must retain source values exactly at native grid indices.
        original = source_volumes[name]
        ij = original.posToIndex(first)
        ix, iy = round(ij[0]), round(ij[1])
        expected = np.fromiter(
            (original.voxel((ix + i, iy + j, 0)) for j in range(ny) for i in range(nx)),
            dtype=np.float32,
        )
        actual = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32)
        if not np.array_equal(expected, actual):
            raise RuntimeError("Crop changes native samples: " + name)
        measured[name] = {
            "sha256": sha_bytes(v.allVoxelsAsString()),
            "first": list(first),
            "last": list(last),
            "source_index": [ix, iy],
        }
    height = layers["height"]
    hole_count = int(
        np.count_nonzero(
            np.frombuffer(layers["visibility"].allVoxelsAsString(), np.float32) > 0.5
        )
    )
    if hole_count:
        raise RuntimeError(
            "Selected source crop includes holes; validity exclusion must be implemented before extraction"
        )
    xs = np.array([height.indexToPos((i, 0, 0))[0] for i in range(nx)])
    zs = np.array([height.indexToPos((0, j, 0))[2] for j in range(ny)])
    cols = np.rint((xs + 3999.75) / 0.5).astype(int)
    rows = 15999 - np.rint((3999.75 - zs) / 0.5).astype(int)
    if min(cols.min(), rows.min()) < 0 or max(cols.max(), rows.max()) >= 16000:
        raise RuntimeError("Crop outside IDMap")
    inp = oi.ImageInput.open(record["idmap"])
    pixels = inp.read_image(format=oi.UINT8)
    inp.close()
    pixels = np.asarray(pixels).reshape(16000, 16000)
    ids = np.ascontiguousarray(pixels[np.ix_(rows, cols)].astype(np.float32) / 255)
    del pixels
    id_geo = hou.Geometry(geo)
    id_geo.deletePrims(
        [v for v in id_geo.prims() if v.attribValue("name") != "visibility"], True
    )
    idvol = id_geo.prims()[0]
    idvol.setAttribValue("name", "id")
    idvol.setAllVoxelsFromString(ids.tobytes())
    geo.merge(id_geo)
    # A source-validity mask is explicit, separate from encoded material IDs.
    mask_geo = hou.Geometry(id_geo)
    mask_geo.prims()[0].setAttribValue("name", "mask")
    mask_geo.prims()[0].setAllVoxelsFromString(np.zeros((ny, nx), np.float32).tobytes())
    geo.merge(mask_geo)
    geo.saveToFile(str(args.output / "current_source_crop.bgeo.sc"))
    library = args.otls / "sop_PE_Heightfield_Extract_Cliffs.1.0.hda"
    if (
        sha(library)
        != "16d7c13d9ca5ba4af221584a1fde7232fecfee0a3d173b616e1aabadf3464f70"
    ):
        raise RuntimeError("Original extraction changed")
    hou.hda.installFile(str(args.otls / "sop_PE_Heightfield_id_to_layer.hda"))
    hou.hda.installFile(str(library))
    staged = g.createNode("file", "CURRENT_SOURCE_CROP")
    staged.parm("file").set(
        str((args.output / "current_source_crop.bgeo.sc").resolve())
    )
    extract = g.createNode(
        "PE_Heightfield_Extract_Cliffs::1.0", "ORIGINAL_CURRENT_EXTRACTION"
    )
    if (
        Path(extract.type().definition().libraryFilePath()).resolve()
        != library.resolve()
    ):
        raise RuntimeError("Unexpected extraction definition")
    extract.setInput(0, staged)
    extract.allowEditingOfContents()
    decoder = extract.node("PE_Heightfield_id_to_layer1")
    decoder.setParms({"srcname1": "id", "dstname1": "mask", "id_layer": 191})
    decoder.cook(force=True)
    decoded = next(
        v for v in decoder.geometry().prims() if v.attribValue("name") == "mask"
    )
    decoded_values = np.frombuffer(decoded.allVoxelsAsString(), np.float32).reshape(
        ny, nx
    )
    expected_mask = (np.rint(ids * 255) == 191).astype(np.float32)
    decoder_error = float(np.abs(decoded_values - expected_mask).max())
    if decoder_error > 1e-4:
        raise RuntimeError(
            "Original ID decoder differs from expected categorical cliff mask"
        )
    if args.pre_flow:
        extract.node("blast2").bypass(True)
    exclusion = None
    if args.road_exclusion:
        route_path = Path(record["route_record"])
        if sha(route_path) != record["route_record_sha256"]:
            raise RuntimeError("Route record changed")
        route = json.loads(route_path.read_text())
        if sha(route["source_path"]) != route["source_sha256"]:
            raise RuntimeError("Source route changed")
        route_geo = hou.Geometry()
        for part in route["parts_epsg25831_m"]:
            poly = route_geo.createPolygon(is_closed=False)
            for e, north in part:
                point = route_geo.createPoint()
                point.setPosition((e - 483650, 0, 4409899.5 - north))
                poly.addVertex(point)
        route_geo.saveToFile(str(args.output / "registered_route.bgeo.sc"))
        road = extract.createNode("file", "SOURCE_ROUTE")
        road.parm("file").set(str(args.output / "registered_route.bgeo.sc"))
        ribbon = extract.createNode("sweep::2.0", "CANDIDATE_10M_EXCLUSION")
        ribbon.setInput(0, road)
        ribbon.setParms(
            {
                "surfaceshape": 3,
                "width": args.exclusion_width,
                "cols": 2,
                "upvectortype": 2,
            }
        )
        mask = extract.createNode("heightfield_maskbyobject", "SUBTRACT_ROAD_EXCLUSION")
        converter = extract.node("convertheightfield1")
        mask.setInput(0, converter.inputs()[0])
        mask.setInput(1, ribbon)
        mask.setParms(
            {
                "combine": 2,
                "maskdir": 0,
                "maxdist": 2000,
                "blurradius": 0,
                "dojitter": 0,
            }
        )
        converter.setInput(0, mask)
        mask.cook(force=True)
        if mask.errors():
            raise RuntimeError(str(mask.errors()))
        exclusion = {
            "route_sha256": sha(route_path),
            "native_node": mask.type().name(),
            "half_width_m": args.exclusion_width / 2,
            "required_clearance_m": 5,
            "status": "CANDIDATE_MASK_ONLY; final polygon clearance pending",
        }
    # Reindex converted source samples onto the admitted half-metre lattice.
    # Crop volume transforms carry float32 position noise; heights stay untouched.
    converter = extract.node("convertheightfield1")
    lattice = extract.createNode("attribwrangle", "SOURCE_LATTICE_PRECISION")
    lattice.setInput(0, converter)
    lattice.parm("snippet").set(
        "@P.x = rint((@P.x+3999.75)/0.5)*0.5-3999.75; @P.z = 3999.75-rint((3999.75-@P.z)/0.5)*0.5;"
    )
    extract.node("attribblur1").setInput(0, lattice)
    before = np.array([p.position() for p in converter.geometry().points()])
    after = np.array([p.position() for p in lattice.geometry().points()])
    lattice_delta = after - before
    lattice_max = float(np.linalg.norm(lattice_delta, axis=1).max())
    if lattice_max > 0.001 or np.abs(lattice_delta[:, 1]).max() != 0:
        raise RuntimeError("Source lattice correction exceeds 1mm or changes height")
    extract.parm("threshold").set(0)
    extract.cook(force=True)
    result_node = extract
    if args.halo:
        for axis, sign, offset in [(0, 1, -64), (0, -1, 64), (2, 1, -64), (2, -1, 64)]:
            clip = g.createNode(
                "clip::2.0", "CORE_" + str(axis) + "_" + str(sign).replace("-", "N")
            )
            clip.setInput(0, result_node)
            origin = [0.0, 0.0, 0.0]
            origin[axis] = center[0 if axis == 0 else 1] + offset
            direction = [0.0, 0.0, 0.0]
            direction[axis] = sign
            clip.parmTuple("origin").set(origin)
            clip.parmTuple("dir").set(direction)
            clip.parm("clipop").set(0)
            result_node = clip
    result_node.cook(force=True)
    result = result_node.geometry()
    if extract.errors() or any(
        not all(map(math.isfinite, p.position())) for p in result.points()
    ):
        raise RuntimeError(
            "Current original extraction failed: " + str(extract.errors())
        )
    result.saveToFile(str(args.output / "cliffs.bgeo.sc"))
    if args.pre_flow:
        result.saveToFile(str(args.output / "cliffs.obj"))
    cached = g.createNode("file", "CACHED_OUTPUT")
    cached.parm("file").set(str((args.output / "cliffs.bgeo.sc").resolve()))
    cached.setDisplayFlag(True)
    cached.setRenderFlag(True)
    g.layoutChildren()
    hou.hipFile.save(str(args.output / "candidate.hiplc"))
    receipt = {
        "stage": "CURRENT_FINAL_ROADSIDE_CROP_EXTRACTION",
        "producer_sha256": sha(__file__),
        "source_final_sha256": manifest["accepted_l06_sha256"],
        "native_join_proof": join_proof,
        "source_lattice_precision_max_delta_m": lattice_max,
        "source_lattice_precision_y_delta_m": 0,
        "tile": tile["file"],
        "tile_sha256": sha(path),
        "inventory_sha256": sha(args.current_crop),
        "idmap_sha256": record["idmap_sha256"],
        "chosen_window": chosen,
        "native_sample_preservation": measured,
        "actual_crop_resolution": [nx, ny, 1],
        "halo_m": args.halo,
        "pre_flow_raw_stage": args.pre_flow,
        "manifest_sha256": sha(manifest_path),
        "native_crop_rounding": "Original Crop includes edge padding; actual measured lattice recorded",
        "id_codes": np.unique(np.rint(ids * 255).astype(np.uint8)).tolist(),
        "id_mapping": "PNG row=15999-round((3999.75-Z)/0.5), col=round((X+3999.75)/0.5), nearest exact lattice",
        "visibility": "retained unchanged, holes=1; current chosen window must be checked before admission",
        "road_exclusion": exclusion,
        "visibility_holes": hole_count,
        "decoder_max_mask_error": decoder_error,
        "decoder": {
            "library_sha256": sha(decoder.type().definition().libraryFilePath()),
            "type": decoder.type().name(),
            "id_layer": 191,
            "srcname1": "id",
            "dstname1": "mask",
        },
        "points": len(result.points()),
        "primitives": len(result.prims()),
        "warnings": extract.warnings(),
        "output_sha256": sha(args.output / "cliffs.bgeo.sc"),
        "hip_sha256": sha(args.output / "candidate.hiplc"),
        "cook": "PASS",
        "road_clearance": "NOT RUN",
        "full_route": "INVENTORY_ONLY",
        "unreal": "NOT RUN",
        "production_admission": False,
        "performance_pass": False,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(receipt))


def detail(args):
    """Original PEG-05 generator, one measured class; input baseline retained."""
    import numpy as np

    prior = json.loads((args.detail / "receipt.json").read_text())
    source = args.detail / "cliffs.bgeo.sc"
    if sha(source) != prior["output_sha256"] or not (
        prior.get("source_lineage")
        or prior.get("stage") == "CURRENT_FINAL_ROADSIDE_CROP_EXTRACTION"
    ):
        raise RuntimeError("Detail requires the verified real extraction receipt")
    library = args.otls / "sop_PE_Cliff_Generator.1.0.hda"
    if (
        sha(library)
        != "3d264fdc67648609a8c83bd1d7a34d65bb15744a23114477cda4ae48b1fde3f4"
    ):
        raise RuntimeError("Original generator hash mismatch")
    hou.hda.installFile(str(library))
    bindings_path = Path("D:/yacs/work/lesson07-polyhaven-cc0-v1/bindings-v1.json")
    binding = json.loads(bindings_path.read_text())
    if binding["license"] != "CC0":
        raise RuntimeError("Expected retained CC0 binding")
    maps = [
        next(v for v in binding["houdini"] if v["role"] == role)["files"]["disp"]
        for role in ("cliff", "rock")
    ]
    for item in maps:
        if sha(item["path"]) != item["sha256"]:
            raise RuntimeError("CC0 height map differs from source binding")
    if args.output.exists():
        raise RuntimeError("Output exists; keep prior evidence")
    args.output.mkdir(parents=True)
    g = hou.node("/obj").createNode("geo", "CLIFF_REHEARSAL")
    src = g.createNode("file", "EXTRACTED_REAL_CLIFFS")
    src.parm("file").set(str(source.resolve()))
    select = g.createNode("blast", "BOUNDED_CLASS")
    select.setInput(0, src)
    select.setParms({"group": "@class=" + str(args.class_id), "negate": 1})
    n = g.createNode("PE_Cliff_Generator::1.0", "ORIGINAL_GENERATOR")
    if Path(n.type().definition().libraryFilePath()).resolve() != library.resolve():
        raise RuntimeError("Unexpected generator definition")
    n.setInput(0, select)
    n.setParms(
        {
            "displacement1": maps[0]["path"],
            "displacement2": maps[1]["path"],
            "subdivision": 1,
            "strength": args.strength,
            "scale": 0.1,
            "percentage": 80,
        }
    )
    n.allowEditingOfContents()
    if args.normal_blur_only:
        n.node("attribblur2").parm("attributes").set("N")
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    select.cook(force=True)
    if not 0 < len(select.geometry().prims()) <= 1000:
        raise RuntimeError("Selected extraction class changed")
    select.geometry().saveToFile(str(args.output / "selected_source.obj"))
    # Same source graph, zero-strength baseline isolates displacement from smoothing.
    n.parm("strength").set(0)
    n.node("restore_y_pos").cook(force=True)
    baseline = hou.Geometry(n.node("restore_y_pos").geometry())
    baseline.saveToFile(str(args.output / "zero_displacement.bgeo.sc"))
    baseline.saveToFile(str(args.output / "zero_displacement.obj"))
    before = np.array([p.position() for p in baseline.points()])
    if not np.isfinite(before).all():
        raise RuntimeError("Nonfinite zero-strength baseline")
    n.parm("strength").set(args.strength)
    n.node("restore_y_pos").cook(force=True)
    displaced = n.node("restore_y_pos").geometry()
    after = np.array([p.position() for p in displaced.points()])
    if before.shape != after.shape or not np.isfinite(after).all():
        raise RuntimeError("Invalid displacement correspondence")
    delta = after - before
    n.cook(force=True)
    geo = n.geometry()
    if (
        not geo.prims()
        or n.errors()
        or any(not all(map(math.isfinite, p.position())) for p in geo.points())
    ):
        raise RuntimeError("Original generator failed: " + str(n.errors()))
    geo.saveToFile(str(args.output / "cliffs.bgeo.sc"))
    geo.saveToFile(str(args.output / "cliffs.obj"))
    # Native closest-surface measurement only; does not alter generated geometry.
    distance_stats = {}
    for label, first, second in [
        ("output_vertices_to_source", n, select),
        ("source_vertices_to_output", select, n),
        ("subdivide1_to_source", n.node("subdivide1"), select),
        ("subdivide2_to_source", n.node("subdivide2"), select),
        ("blur_to_source", n.node("attribblur2"), select),
    ]:
        measure = g.createNode("attribwrangle", "MEASURE_" + label.upper())
        if first.parent() != g:
            bridge = g.createNode("object_merge", "READ_" + label.upper())
            bridge.parm("objpath1").set(first.path())
            first = bridge
        measure.setInput(0, first)
        measure.setInput(1, second)
        measure.parm("snippet").set("f@source_distance = xyzdist(1, @P);")
        measure.cook(force=True)
        distances = np.array(
            measure.geometry().pointFloatAttribValues("source_distance")
        )
        if measure.errors() or not len(distances) or not np.isfinite(distances).all():
            raise RuntimeError("Native surface-distance measurement failed")
        distance_stats[label] = {
            "samples": len(distances),
            "max_m": float(distances.max()),
            "mean_m": float(distances.mean()),
            "p95_m": float(np.percentile(distances, 95)),
        }
    cached = g.createNode("file", "CACHED_OUTPUT")
    cached.parm("file").set(str((args.output / "cliffs.bgeo.sc").resolve()))
    cached.setDisplayFlag(True)
    cached.setRenderFlag(True)
    g.layoutChildren()
    hou.hipFile.save(str(args.output / "candidate.hiplc"))
    receipt = {
        "stage": "ORIGINAL_GENERATOR_ONE_REAL_CLASS",
        "houdini": hou.applicationVersionString(),
        "producer_sha256": sha(__file__),
        "points": len(geo.points()),
        "primitives": len(geo.prims()),
        "hip_sha256": sha(args.output / "candidate.hiplc"),
        "output_sha256": sha(args.output / "cliffs.bgeo.sc"),
        "source_receipt_sha256": sha(args.detail / "receipt.json"),
        "source_lineage": prior.get(
            "source_lineage",
            {
                "current_final_sha256": prior.get("source_final_sha256"),
                "tile_sha256": prior.get("tile_sha256"),
            },
        ),
        "generator_sha256": sha(library),
        "maps": maps,
        "bindings_sha256": sha(bindings_path),
        "adapted_parameters": {
            "subdivision": 1,
            "strength": args.strength,
            "scale": 0.1,
            "class": args.class_id,
            "percentage": 80,
            "normal_blur_only": args.normal_blur_only,
        },
        "displacement_max_m": float(np.linalg.norm(delta, axis=1).max()),
        "displacement_mean_m": float(np.linalg.norm(delta, axis=1).mean()),
        "displacement_max_y_m": float(np.abs(delta[:, 1]).max()),
        "delta_reference": "original generator same-topology zero-strength baseline before reduction",
        "source_distance": distance_stats,
        "source_distance_limit": "Native xyzdist at vertices in both directions; not continuous Hausdorff distance or final Landscape contact proof",
        "bounds": [list(geo.boundingBox().minvec()), list(geo.boundingBox().maxvec())],
        "warnings": n.warnings(),
        "cook": "PASS",
        "road_clearance": "NOT RUN",
        "full_route": "NOT RUN",
        "unreal": "NOT RUN",
        "production_admission": False,
        "performance_pass": False,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(receipt))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--batch", type=Path, help="Guarded inventory for serial raw-source batch"
    )
    p.add_argument(
        "--reuse-batch",
        type=Path,
        help="Reuse hash-bound ece78990 checkpoint outputs with independent revalidation",
    )
    p.add_argument("--batch-limit", type=int, default=178)
    p.add_argument("--source", type=Path)
    p.add_argument("--otls", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--center", nargs=2, type=float, default=[0, 0])
    p.add_argument("--size", type=float, default=128)
    p.add_argument(
        "--crop-metadata", type=Path, help="Pinned L06 base/mask crop receipt directory"
    )
    p.add_argument(
        "--detail",
        type=Path,
        help="Verified extraction output directory for one original-generator class",
    )
    p.add_argument(
        "--class-id",
        type=int,
        default=27,
        help="Existing extraction class, at most 1000 faces",
    )
    p.add_argument(
        "--normal-blur-only",
        action="store_true",
        help="PEG-05 L03 06:29-06:46 N-only control; original HDA default P N retained otherwise",
    )
    p.add_argument(
        "--strength",
        type=float,
        default=0.15,
        help="Experimental original-generator amplitude, 0..1.2; default 0.15",
    )
    p.add_argument(
        "--inventory",
        type=Path,
        help="Read full source route record and inventory current IDMap windows",
    )
    p.add_argument(
        "--pre-flow",
        action="store_true",
        help="PEG05 L02 01:56-04:27 extraction before optional flow split",
    )
    p.add_argument(
        "--exclusion-width",
        type=int,
        choices=[10, 12, 14],
        default=10,
        help="Candidate native mask width; final required clearance is 5m",
    )
    p.add_argument(
        "--road-exclusion",
        action="store_true",
        help="Native projected Sweep 5m candidate half-band subtraction",
    )
    p.add_argument("--window", nargs=2, type=int, help="Inventory ix iz override")
    p.add_argument(
        "--halo",
        type=int,
        choices=[0, 8, 16],
        default=0,
        help="Native crop halo; clip output to 128m core",
    )
    p.add_argument(
        "--current-crop",
        type=Path,
        help="Inventory JSON choosing one verified current FINAL native tile crop",
    )
    p.add_argument("--reopen", action="store_true")
    args = p.parse_args()
    if args.batch:
        batch(args)
        return
    if args.inventory:
        inventory(args)
        return
    if hou is None or args.otls is None:
        p.error("Native modes require hython and --otls")
    if args.detail and args.reopen:
        p.error("Reopen with --output and --otls only, omitting --detail")
    if not math.isfinite(args.strength) or not 0 <= args.strength <= 1.2:
        p.error("Experimental strength must be finite and within 0..1.2")
    if hou.applicationVersion() != (22, 0, 466):
        raise RuntimeError("This candidate was verified with Houdini 22.0.466 only")
    hou.setUpdateMode(hou.updateMode.Manual)
    hou.setMaxThreads(2)
    if args.current_crop:
        current_crop(args)
        return
    if args.detail:
        detail(args)
        return
    library = args.otls / "sop_PE_Heightfield_Extract_Cliffs.1.0.hda"
    if (
        sha(library)
        != "16d7c13d9ca5ba4af221584a1fde7232fecfee0a3d173b616e1aabadf3464f70"
    ):
        raise RuntimeError("Original extraction HDA hash mismatch")
    for f in [args.otls / "sop_PE_Heightfield_id_to_layer.hda", library]:
        hou.hda.installFile(str(f))
    if args.reopen:
        receipt_path = args.output / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("stage") == "ORIGINAL_GENERATOR_ONE_REAL_CLASS":
            generator = args.otls / "sop_PE_Cliff_Generator.1.0.hda"
            if sha(generator) != receipt["generator_sha256"]:
                raise RuntimeError("Generator dependency differs from producer")
            hou.hda.installFile(str(generator))
        if sha(args.output / "candidate.hiplc") != receipt["hip_sha256"]:
            raise RuntimeError("HIP hash differs from producer receipt")
        hou.hipFile.load(
            str(args.output / "candidate.hiplc"), suppress_save_prompt=True
        )
        hou.setUpdateMode(hou.updateMode.AutoUpdate)
        node = hou.node("/obj/CLIFF_REHEARSAL/CACHED_OUTPUT")
        if (
            Path(node.parm("file").eval()).resolve()
            != (args.output / "cliffs.bgeo.sc").resolve()
        ):
            raise RuntimeError("Cached output points to a different file")
        geom = node.geometry()
        same = (
            len(geom.points()) == receipt["points"]
            and len(geom.prims()) == receipt["primitives"]
            and sha(args.output / "cliffs.bgeo.sc") == receipt["output_sha256"]
        )
        receipt["output_disk_reload"] = "PASS" if same else "FAILED"
        receipt["graph_regeneration"] = "NOT RUN"
        with (args.output / "fresh_reopen.json").open("x") as stream:
            json.dump(receipt, stream, indent=2)
        if not same:
            raise RuntimeError("Fresh disk geometry differs from receipt")
        print(json.dumps(receipt))
        return
    if (
        args.source is None
        or not 0 < args.size <= 256
        or not all(map(math.isfinite, args.center))
    ):
        p.error("--source required and bounded size must be (0,256] metres")
    if args.source.stat().st_size > 128 * 1024 * 1024:
        p.error("Rehearsal refuses source caches above 128 MiB")
    if args.output.exists():
        p.error("Output already exists; preserve prior evidence")
    args.output.mkdir(parents=True)
    g = hou.node("/obj").createNode("geo", "CLIFF_REHEARSAL")
    source = g.createNode("file", "RETAINED_SOURCE")
    source.parm("file").set(str(args.source.resolve()))
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    source.cook(force=True)
    source_geo = source.geometry()
    layers = {v.attribValue("name"): v for v in source_geo.prims()}
    if any(
        not isinstance(v, hou.Volume) or max(v.resolution()) > 2048
        for v in layers.values()
    ):
        raise RuntimeError(
            "Only bounded native source volumes up to 2048 per axis are supported"
        )
    source_lineage = None
    if args.crop_metadata:
        source_lineage = {}
        if set(layers) != {
            "height",
            "mask",
            "Alpha",
            "grass_mask",
            "sand_mask",
            "cliff_mask",
            "ramp_layer",
        }:
            raise RuntimeError("Unexpected admitted crop layer set")
        pins = {
            "base": "08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952",
            "masks": "203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8",
        }
        for stage in ("base", "masks"):
            meta_path = args.crop_metadata / (stage + "-real-crop.json")
            meta = json.loads(meta_path.read_text())
            if meta["source"]["source_sha256"] != pins[stage]:
                raise RuntimeError("Crop does not descend from admitted L06 source")
            if (
                sha(args.crop_metadata / (stage + "-real-crop.npz"))
                != meta["crop_sha256"]
            ):
                raise RuntimeError("Original crop archive differs from receipt")
            for name, spec in meta["layer_metadata"].items():
                v = layers[name]
                if sha_bytes(v.allVoxelsAsString()) != spec["sha256_float32_le"]:
                    raise RuntimeError(
                        "Native crop voxels differ from original: " + name
                    )
                for index, key in [
                    ((0, 0, 0), "first_voxel_world_xyz"),
                    ((255, 255, 0), "last_voxel_world_xyz"),
                ]:
                    if (
                        max(abs(a - b) for a, b in zip(v.indexToPos(index), spec[key]))
                        > 0.02
                    ):
                        raise RuntimeError("Native crop registration differs: " + name)
            source_lineage[stage] = {
                "receipt": str(meta_path),
                "receipt_sha256": sha(meta_path),
                "source": meta["source"],
            }
    crop = g.createNode("heightfield_crop", "BOUNDED_PATCH")
    crop.setInput(0, source)
    crop.setParms(
        {
            "cropmode": 0,
            "sizex": args.size,
            "sizey": args.size,
            "tx": args.center[0],
            "tz": args.center[1],
        }
    )
    mask = g.createNode("heightfield_maskbyfeature", "L02_OFFICIAL_SLOPE_ALTERNATIVE")
    mask.setInput(0, crop)
    mask.setParms({"min_slopeangle": 35, "max_slopeangle": 90})
    if args.crop_metadata:
        # Source mask takes precedence over the tutorial's optional slope heuristic.
        mask = g.createNode("heightfield_copylayer", "ACCEPTED_CLIFF_MASK")
        mask.setInput(0, source)
        mask.setParms({"srcname1": "cliff_mask", "dstname1": "mask"})
    extract = g.createNode("PE_Heightfield_Extract_Cliffs::1.0", "ORIGINAL_EXTRACTION")
    actual = Path(extract.type().definition().libraryFilePath()).resolve()
    if actual != library.resolve() or sha(actual) != sha(library):
        raise RuntimeError("Different extraction definition loaded")
    extract.setInput(0, mask)
    extract.allowEditingOfContents()
    # L02 01:27-01:50 explicitly permits feature masks instead of ID decoding.
    # Bypass ONLY that decoder, retaining the original downstream extraction.
    extract.node("PE_Heightfield_id_to_layer1").bypass(True)
    # Tutorial island threshold 1000 would remove a small rehearsal patch.
    extract.parm("threshold").set(0)
    extract.cook(force=True)
    geometry = extract.geometry()
    if extract.errors() or any(
        not all(map(math.isfinite, p.position())) for p in geometry.points()
    ):
        raise RuntimeError("Extraction has native errors or nonfinite coordinates")
    if not geometry.prims():
        failure = {
            "status": "FAILED_EMPTY_EXTRACTION",
            "source": str(args.source),
            "source_sha256": sha(args.source),
            "center_xz": args.center,
            "size_m": args.size,
            "full_route": "NOT RUN",
            "unreal": "NOT RUN",
            "nodes": [
                {"path": n.path(), "errors": n.errors(), "warnings": n.warnings()}
                for n in extract.allSubChildren()
            ],
        }
        (args.output / "failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise RuntimeError("No cliffs extracted at supplied patch; no PASS claimed")
    geometry.saveToFile(str(args.output / "cliffs.bgeo.sc"))
    cached = g.createNode("file", "CACHED_OUTPUT")
    cached.parm("file").set(str((args.output / "cliffs.bgeo.sc").resolve()))
    cached.setDisplayFlag(True)
    cached.setRenderFlag(True)
    g.layoutChildren()
    hou.hipFile.save(str(args.output / "candidate.hiplc"))
    receipt = {
        "houdini": hou.applicationVersionString(),
        "source": str(args.source),
        "producer_sha256": sha(__file__),
        "hip_sha256": sha(args.output / "candidate.hiplc"),
        "source_sha256": sha(args.source),
        "hda_sha256": sha(library),
        "source_lineage": source_lineage,
        "requested_center_xz": args.center,
        "requested_size_m": args.size,
        "uses_entire_verified_crop": bool(args.crop_metadata),
        "source_volume_resolution": list(layers["height"].resolution()),
        "source_first_sample": list(layers["height"].indexToPos((0, 0, 0))),
        "source_last_sample": list(
            layers["height"].indexToPos(
                tuple(v - 1 for v in layers["height"].resolution())
            )
        ),
        "warnings": extract.warnings(),
        "points": len(geometry.points()),
        "primitives": len(geometry.prims()),
        "bounds": [
            list(geometry.boundingBox().minvec()),
            list(geometry.boundingBox().maxvec()),
        ],
        "output_sha256": sha(args.output / "cliffs.bgeo.sc"),
        "node_definitions": sorted(
            {
                (
                    n.type().name(),
                    n.type().definition().libraryFilePath()
                    if n.type().definition()
                    else "native",
                )
                for n in extract.allSubChildren()
            }
        ),
        "cook": "PASS",
        "fresh_reopen": "NOT RUN",
        "road_clearance": "NOT RUN",
        "full_route": "NOT RUN",
        "displacement": "NOT RUN",
        "unreal": "NOT RUN",
        "production_admission": False,
        "performance_pass": False,
    }
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
