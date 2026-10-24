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
    import shapely
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
            rows, columns = np.nonzero(pixels == 191)
            sample_x = x + 0.25 + columns * 0.5
            sample_z = z + 0.25 + rows * 0.5
            exact_counts = {
                distance: int(
                    np.count_nonzero(shapely.intersects_xy(polygon, sample_x, sample_z))
                )
                for distance, polygon in buffers.items()
            }
            windows.append(
                {
                    "ix": ix,
                    "iz": iz,
                    "center_xz": [x + 64, z + 64],
                    "pixel_origin_x_row": [ix * 256, iz * 256],
                    "cliff_pixels": count,
                    "cliff_sample_centers_in_64m": exact_counts[64],
                    "cliff_sample_centers_in_500m": exact_counts[500],
                    "intersects_64m_road_band": footprint.intersects(buffers[64]),
                    "route_parts": [
                        i
                        for i, line in enumerate(lines)
                        if footprint.intersects(line.buffer(64))
                    ],
                    "working_corridor_route_parts": [
                        i
                        for i, line in enumerate(lines)
                        if footprint.intersects(line.buffer(500))
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
        "windows_with_cliff_in_500m": sum(
            w["cliff_sample_centers_in_500m"] > 0 for w in windows
        ),
        "cliff_sample_centers_in_500m": sum(
            w["cliff_sample_centers_in_500m"] for w in windows
        ),
        "cliff_sample_centers_in_64m": sum(
            w["cliff_sample_centers_in_64m"] for w in windows
        ),
        "source_part_lengths_m": [line.length for line in lines],
        "classification_area_per_sample_m2": 0.25,
        "classification_count_semantics": "Exact sample-center inclusion in the declared route buffers on registered IDMap; not geological truth, surface area, visibility admission or road-volume clearance",
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
    checkpoint = None
    if args.resume:
        checkpoint = json.loads((args.resume / "batch.json").read_text())
        if (
            checkpoint["producer_sha256"]
            != "5636169a61819c976c1956cf7f62606e1de9c4bac9e956a233fdef0b8315d856"
        ):
            raise RuntimeError("Unsupported checkpoint producer")
        if (
            checkpoint["inventory_sha256"] != sha(args.batch)
            or sha(args.batch)
            != "1645af92ee8223959b65b8686ad7445f31486ec6fde631a54d4121f3b2cea430"
        ):
            raise RuntimeError("Checkpoint inventory changed")
        if sha(record["idmap"]) != record["idmap_sha256"]:
            raise RuntimeError("Current ID source changed")
        manifest_path = Path(
            "D:/yacs/work/lesson07-consumer-update-20261020/manifest.json"
        )
        if (
            sha(manifest_path)
            != "760425da4a8fa46c4e201a74f0a70ced802f14dc992d1569885167fe73a8978e"
        ):
            raise RuntimeError("Current source manifest changed")
        manifest = json.loads(manifest_path.read_text())
        for tile in manifest["tiles"]:
            if sha(manifest_path.parent / tile["file"]) != tile["sha256"]:
                raise RuntimeError("Current native source tile changed")
        cores = checkpoint["cores"]
        if checkpoint["completed"] != len(cores) or checkpoint["target"] != len(
            windows
        ):
            raise RuntimeError("Checkpoint count mismatch")
        if [c["core"] for c in cores] != [
            [w["ix"], w["iz"]] for w in windows[: len(cores)]
        ]:
            raise RuntimeError("Checkpoint is not the exact inventory prefix")
        windows = windows[: len(cores)]
        subprocess.run(
            [
                "D:/yacs/tools/houdini-22.0.466/bin/hython.exe",
                str(Path(__file__).resolve()),
                "--resume-native",
                "--resume",
                str(args.resume.resolve()),
                "--output",
                str((args.output / "native_readback").resolve()),
            ],
            check=True,
        )
    results = []
    seams = {}
    started = time.time()
    for w in windows[: args.batch_limit]:
        while (args.output / "PAUSE").exists():
            time.sleep(1)
        ix, iz = w["ix"], w["iz"]
        out = args.output / f"core_{ix}_{iz}"
        reused = False
        if checkpoint:
            saved = checkpoint["cores"][len(results)]
            out = Path(saved["output_directory"])
            prior = json.loads((out / "receipt.json").read_text())
            producer = prior["producer_sha256"]
            if (
                producer
                not in {
                    "5636169a61819c976c1956cf7f62606e1de9c4bac9e956a233fdef0b8315d856",
                    "ece78990c3ed57138441e4065e899d0060df6ce76f1a2b1169c878034a794aa5",
                }
                or producer != saved["native_producer_sha256"]
            ):
                raise RuntimeError("Per-core producer mismatch")
            if prior["chosen_window"] != w or prior["inventory_sha256"] != sha(
                args.batch
            ):
                raise RuntimeError("Per-core source window mismatch")
            if (
                prior["source_final_sha256"]
                != "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24"
                or prior["manifest_sha256"] != sha(manifest_path)
            ):
                raise RuntimeError("Per-core source lineage mismatch")
            if (
                prior["idmap_sha256"] != record["idmap_sha256"]
                or prior["halo_m"] != 8
                or not prior["pre_flow_raw_stage"]
                or prior["road_exclusion"]["half_width_m"] != 6
                or prior["road_exclusion"]["route_sha256"] != sha(route_path)
            ):
                raise RuntimeError("Per-core source configuration mismatch")
            if (
                sha(out / "cliffs.bgeo.sc") != prior["output_sha256"]
                or prior["output_sha256"] != saved["output_sha256"]
                or sha(out / "candidate.hiplc") != prior["hip_sha256"]
            ):
                raise RuntimeError("Checkpoint geometry/HIP changed")
            reload = json.loads((out / "fresh_reopen.json").read_text())
            if (
                reload["output_disk_reload"] != "PASS"
                or reload["output_sha256"] != prior["output_sha256"]
                or reload["hip_sha256"] != prior["hip_sha256"]
            ):
                raise RuntimeError("Checkpoint bound reload missing")
            reused = True
        elif args.reuse_batch:
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
        obj_path = (
            args.output / "native_readback" / f"core_{ix}_{iz}.obj"
            if checkpoint
            else out / "cliffs.obj"
        )
        for line in obj_path.read_text().splitlines():
            if line.startswith("v "):
                vertices.append(list(map(float, line.split()[1:4])))
            elif line.startswith("f "):
                faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
        if checkpoint and (
            len(vertices) != prior["points"] or len(faces) != prior["primitives"]
        ):
            raise RuntimeError("Native checkpoint counts changed")
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
                    "checkpoint_validation_only": bool(args.resume),
                    "resumed_checkpoint_sha256": sha(args.resume / "batch.json")
                    if args.resume
                    else None,
                    "remaining_generation": "NOT RUN" if args.resume else "IN PROGRESS",
                    "original_target": checkpoint["target"]
                    if checkpoint
                    else len(windows),
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


def prepare_global_flow(args):
    """Cache native source height/mask once for the complete working corridor."""
    import gc

    import numpy as np
    from PIL import Image

    record = json.loads(args.prepare_global_flow.read_text())
    if sha(record["idmap"]) != record["idmap_sha256"]:
        raise RuntimeError("Global flow ID source changed")
    manifest_path = Path("D:/yacs/work/lesson07-consumer-update-20261020/manifest.json")
    if (
        sha(manifest_path)
        != "760425da4a8fa46c4e201a74f0a70ced802f14dc992d1569885167fe73a8978e"
    ):
        raise RuntimeError("Global flow source manifest changed")
    manifest = json.loads(manifest_path.read_text())
    if args.output.exists():
        raise RuntimeError("Global preparation output exists")
    args.output.mkdir(parents=True)
    windows = record["windows"]
    # The task domain is the existing 500 m working corridor, not a new 64 m
    # placement rule. Context is an explicit input-domain adaptation, not a
    # changed erosion parameter or a claim of equivalence to the whole 8 km cache.
    xmin = -4000 + min(w["ix"] for w in windows) * 128 - 128
    xmax = -4000 + (max(w["ix"] for w in windows) + 1) * 128 + 128
    zmin = -4000 + min(w["iz"] for w in windows) * 128 - 128
    zmax = -4000 + (max(w["iz"] for w in windows) + 1) * 128 + 128
    Image.MAX_IMAGE_PIXELS = 300000000
    with Image.open(record["idmap"]) as image:
        ids = np.asarray(image)
    pieces = []
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    for index, tile in enumerate(manifest["tiles"]):
        source = manifest_path.parent / tile["file"]
        if sha(source) != tile["sha256"]:
            raise RuntimeError("Global preparation transport tile changed")
        obj = hou.node("/obj").createNode("geo", "SERIAL_SOURCE_PIECE")
        file_node = obj.createNode("file")
        file_node.parm("file").set(str(source))
        crop = obj.createNode("heightfield_crop")
        crop.setInput(0, file_node)
        crop.setParms(
            {
                "cropmode": 2,
                "sizex": xmax - xmin,
                "sizey": zmax - zmin,
                "tx": (xmin + xmax) / 2,
                "tz": (zmin + zmax) / 2,
            }
        )
        cropped = hou.Geometry(crop.geometry())
        height = next(v for v in cropped.prims() if v.attribValue("name") == "height")
        original = next(
            v for v in file_node.geometry().prims() if v.attribValue("name") == "height"
        )
        nx, ny, _ = height.resolution()
        ox, oy, _ = original.resolution()
        i, j, _ = original.posToIndex(height.indexToPos((0, 0, 0)))
        i, j = round(i), round(j)
        expected = np.frombuffer(original.allVoxelsAsString(), np.float32).reshape(
            oy, ox
        )
        observed = np.frombuffer(height.allVoxelsAsString(), np.float32).reshape(ny, nx)
        if not np.array_equal(observed, expected[j : j + ny, i : i + nx]):
            raise RuntimeError("Global intersect crop changes source heights")
        first = height.indexToPos((0, 0, 0))
        last = height.indexToPos((nx - 1, ny - 1, 0))
        columns = np.rint((np.linspace(first[0], last[0], nx) + 3999.75) / 0.5).astype(
            int
        )
        rows = np.rint((np.linspace(first[2], last[2], ny) + 3999.75) / 0.5).astype(int)
        if (
            min(columns.min(), rows.min()) < 0
            or max(columns.max(), rows.max()) >= 16000
        ):
            raise RuntimeError("Global context exceeds the current ID image")
        visibility = next(
            v for v in cropped.prims() if v.attribValue("name") == "visibility"
        )
        holes = np.frombuffer(visibility.allVoxelsAsString(), np.float32).reshape(
            ny, nx
        )
        invalid_cliffs = int(
            np.count_nonzero((holes > 0.5) & (ids[np.ix_(rows, columns)] == 191))
        )
        if invalid_cliffs:
            raise RuntimeError(
                "Current ID cliff code appears in source visibility holes"
            )
        output = args.output / f"height_piece_{index}.bgeo.sc"
        cropped.deletePrims(
            [v for v in cropped.prims() if v.attribValue("name") != "height"], True
        )
        cropped.saveToFile(str(output))
        pieces.append(
            {
                "file": str(output.resolve()),
                "sha256": sha(output),
                "source_tile": tile["file"],
                "source_sha256": tile["sha256"],
                "resolution": [nx, ny, 1],
                "height_values_exact": nx * ny,
                "visibility_cliff_conflicts": invalid_cliffs,
            }
        )
        del observed, expected, holes, cropped, height, visibility, original
        obj.destroy()
        gc.collect()
        print(
            json.dumps({"prepared_source_pieces": len(pieces), "source": tile["file"]}),
            flush=True,
        )
    obj = hou.node("/obj").createNode("geo", "GLOBAL_ORIGINAL_FLOW_PREPARATION")
    merge = obj.createNode("merge")
    for index, piece in enumerate(pieces):
        node = obj.createNode("file")
        node.parm("file").set(piece["file"])
        merge.setInput(index, node)
    splice = obj.createNode("volumesplice")
    splice.setInput(0, merge)
    splice.setParms({"group": "@name=height", "deleteorig": 1})
    joined = hou.Geometry(splice.geometry())
    height = joined.prims()[0]
    nx, ny, _ = height.resolution()
    joined_values = np.frombuffer(height.allVoxelsAsString(), np.float32).reshape(
        ny, nx
    )
    for piece in pieces:
        check = hou.Geometry()
        check.loadFromFile(piece["file"])
        field = check.prims()[0]
        sx, sy, _ = field.resolution()
        i, j, _ = height.posToIndex(field.indexToPos((0, 0, 0)))
        i, j = round(i), round(j)
        expected = np.frombuffer(field.allVoxelsAsString(), np.float32).reshape(sy, sx)
        if not np.array_equal(expected, joined_values[j : j + sy, i : i + sx]):
            raise RuntimeError("Native global splice changes source samples or overlap")
        del expected, check, field
    height_hash = sha_bytes(height.allVoxelsAsString())
    first = height.indexToPos((0, 0, 0))
    last = height.indexToPos((nx - 1, ny - 1, 0))
    del joined_values
    obj.destroy()
    gc.collect()
    columns = np.rint((np.linspace(first[0], last[0], nx) + 3999.75) / 0.5).astype(int)
    rows = np.rint((np.linspace(first[2], last[2], ny) + 3999.75) / 0.5).astype(int)
    id_geometry = hou.Geometry(joined)
    id_field = id_geometry.prims()[0]
    id_field.setAttribValue("name", "id")
    id_values = ids[np.ix_(rows, columns)].astype(np.float32) / 255.0
    id_field.setAllVoxelsFromString(id_values.tobytes())
    joined.merge(id_geometry)
    source = args.output / "registered_height_and_id.bgeo.sc"
    joined.saveToFile(str(source))
    del id_geometry, id_field, id_values, joined, height
    gc.collect()
    obj = hou.node("/obj").createNode("geo", "GLOBAL_ORIGINAL_DECODER")
    node = obj.createNode("file")
    node.parm("file").set(str(source.resolve()))
    hou.hda.installFile(str(args.otls / "sop_PE_Heightfield_id_to_layer.hda"))
    decoder = obj.createNode("PE_Heightfield_id_to_layer")
    decoder.setInput(0, node)
    decoder.setParms({"srcname1": "id", "dstname1": "mask", "id_layer": 191})
    decoded = hou.Geometry(decoder.geometry())
    mask = next(v for v in decoded.prims() if v.attribValue("name") == "mask")
    native_mask = np.frombuffer(mask.allVoxelsAsString(), np.float32).reshape(ny, nx)
    if not np.array_equal(native_mask, ids[np.ix_(rows, columns)] == 191):
        raise RuntimeError(
            "Original global ID decoder differs from current cliff classification"
        )
    mask_hash = sha_bytes(mask.allVoxelsAsString())
    mask_count = int(np.count_nonzero(native_mask))
    decoded.deletePrims(
        [v for v in decoded.prims() if v.attribValue("name") not in {"height", "mask"}],
        True,
    )
    target = args.output / "flow_input.bgeo.sc"
    decoded.saveToFile(str(target))
    receipt = {
        "stage": "GLOBAL_WORKING_CORRIDOR_NATIVE_FLOW_INPUT",
        "producer_sha256": sha(__file__),
        "inventory_sha256": sha(args.prepare_global_flow),
        "manifest_sha256": sha(manifest_path),
        "source_final_sha256": manifest["accepted_l06_sha256"],
        "idmap_sha256": record["idmap_sha256"],
        "requested_bounds_xz_m": [xmin, xmax, zmin, zmax],
        "native_first_sample": list(first),
        "native_last_sample": list(last),
        "resolution": [nx, ny, 1],
        "pieces": pieces,
        "height_voxels_sha256": height_hash,
        "mask_voxels_sha256": mask_hash,
        "cliff_mask_samples": mask_count,
        "decoder_type": decoder.type().name(),
        "decoder_sha256": sha(decoder.type().definition().libraryFilePath()),
        "flow_input_sha256": sha(target),
        "context_padding_m": 128,
        "grid_spacing_m": 0.5,
        "domain_adaptation": "One shared rectangle covering all 555 working-corridor windows plus context; not the entire available 8km source, and not proven global8km flow equivalence",
        "source_height_and_join_values_exact": True,
        "visibility_retained_in_original_tiles": True,
        "visibility_cliff_conflicts": 0,
        "native_flow_cook": "NOT RUN",
        "production_admission": False,
    }
    (args.output / "input_preparation.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(receipt), flush=True)


def prepare_global_flow_2m(args):
    """Native 2m derivative input adapter reusing verified 0.5m corridor input."""
    import gc

    import numpy as np
    from PIL import Image

    prep05_path = args.prepare_global_flow_2m / "input_preparation.json"
    source05 = args.prepare_global_flow_2m / "flow_input.bgeo.sc"
    prep05 = json.loads(prep05_path.read_text())
    if (
        prep05["flow_input_sha256"]
        != "067ae4ebdc0f68afef7dc88782834017c974a761a3e0db8e308ab9180500405e"
        or sha(source05) != prep05["flow_input_sha256"]
        or prep05["source_final_sha256"]
        != "f741335dce4cae0843a54df9a1478b321dc5e2d3401f93f301cc6647fee4ed24"
    ):
        raise RuntimeError("Verified 0.5m global flow input identity changed")
    for piece in prep05["pieces"]:
        if sha(piece["file"]) != piece["sha256"]:
            raise RuntimeError("Verified 0.5m height piece changed: " + piece["file"])
    idmap = Path(
        "D:/yacs/project/SourceContent/Pegasus/Landscape/Textures/T_PE_Terrain_IDmap.png"
    )
    if (
        sha(idmap) != prep05["idmap_sha256"]
        or prep05["idmap_sha256"]
        != "cb794170135e3b918e3d809275f9c68ba8595653453d8c8dafe1297bcf6e1bc3"
    ):
        raise RuntimeError("Global flow 2m ID source changed")
    if args.output.exists():
        raise RuntimeError("Global 2m preparation output exists")
    args.output.mkdir(parents=True)
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    obj = hou.node("/obj").createNode("geo", "GLOBAL_2M_DERIVATIVE_ADAPTER")
    file_node = obj.createNode("file", "VERIFIED_05M_FLOW_INPUT")
    file_node.parm("file").set(str(source05.resolve()))
    resample = obj.createNode("heightfield_resample", "NATIVE_2M_HEIGHT_RESAMPLE")
    resample.setInput(0, file_node)
    resample.setParms(
        {
            "fixedresample": 1,
            "divisionmode": 1,
            "gridspacing": 2.0,
        }
    )
    resample.cook(force=True)
    if resample.errors():
        raise RuntimeError("2m height resample failed: " + str(resample.errors()))
    geo05 = file_node.geometry()
    h05 = next(v for v in geo05.prims() if v.attribValue("name") == "height")
    m05 = next(v for v in geo05.prims() if v.attribValue("name") == "mask")
    nx05, ny05, _ = h05.resolution()
    if [nx05, ny05, 1] != prep05["resolution"]:
        raise RuntimeError("Unexpected 0.5m source resolution")
    v05 = np.frombuffer(h05.allVoxelsAsString(), np.float32).reshape(ny05, nx05)
    mv05 = np.frombuffer(m05.allVoxelsAsString(), np.float32).reshape(ny05, nx05)
    resampled_geo = hou.Geometry(resample.geometry())
    resampled_geo.deletePrims(
        [v for v in resampled_geo.prims() if v.attribValue("name") != "height"], True
    )
    h2 = resampled_geo.prims()[0]
    nx, ny, _ = h2.resolution()
    if (nx, ny) != (1985, 2625):
        raise RuntimeError(f"Unexpected 2m resampled resolution: {(nx, ny)}")
    v2 = np.frombuffer(h2.allVoxelsAsString(), np.float32).reshape(ny, nx)
    if not np.isfinite(v2).all():
        raise RuntimeError("Nonfinite 2m resampled heights")
    height_hash = sha_bytes(h2.allVoxelsAsString())
    first = h2.indexToPos((0, 0, 0))
    last = h2.indexToPos((nx - 1, ny - 1, 0))
    step_i_m = (last[0] - first[0]) / (nx - 1)
    step_j_m = abs(last[2] - first[2]) / (ny - 1)
    phase_offset_xz_m = [
        first[0] - prep05["native_first_sample"][0],
        first[2] - prep05["native_first_sample"][2],
    ]
    xs = np.array([h2.indexToPos((i, 0, 0))[0] for i in range(nx)])
    zs = np.array([h2.indexToPos((0, j, 0))[2] for j in range(ny)])
    u = np.array([h05.posToIndex((x, 0, first[2]))[0] for x in xs])
    v = np.array([h05.posToIndex((first[0], 0, z))[1] for z in zs])
    i_near = np.rint(u).astype(int)
    j_near = np.rint(v).astype(int)
    i_floor = np.clip(np.floor(u).astype(int), 0, nx05 - 2)
    j_floor = np.clip(np.floor(v).astype(int), 0, ny05 - 2)
    fu = (u - i_floor)[None, :]
    fv = (v - j_floor)[:, None]
    bilin05 = (
        (1.0 - fv) * (1.0 - fu) * v05[np.ix_(j_floor, i_floor)]
        + (1.0 - fv) * fu * v05[np.ix_(j_floor, i_floor + 1)]
        + fv * (1.0 - fu) * v05[np.ix_(j_floor + 1, i_floor)]
        + fv * fu * v05[np.ix_(j_floor + 1, i_floor + 1)]
    )
    delta_nearest = np.abs(v2 - v05[np.ix_(j_near, i_near)])
    delta_bilinear = np.abs(v2 - bilin05)
    b00 = v05[1:-2:4, 1:-2:4]
    b01 = v05[1:-2:4, 2:-1:4]
    b10 = v05[2:-1:4, 1:-2:4]
    b11 = v05[2:-1:4, 2:-1:4]
    delta_2x2_block = np.abs(v2[:-1, :-1] - 0.25 * (b00 + b01 + b10 + b11))
    height_deltas = {
        "vs_nearest_05m_sample_m": {
            "max": float(delta_nearest.max()),
            "mean": float(delta_nearest.mean()),
            "p95": float(np.percentile(delta_nearest, 95)),
        },
        "vs_exact_05m_bilinear_at_2m_centers_m": {
            "max": float(delta_bilinear.max()),
            "mean": float(delta_bilinear.mean()),
            "p95": float(np.percentile(delta_bilinear, 95)),
        },
        "vs_aligned_2x2_05m_block_mean_interior_m": {
            "max": float(delta_2x2_block.max()),
            "mean": float(delta_2x2_block.mean()),
            "p95": float(np.percentile(delta_2x2_block, 95)),
        },
        "filter": resample.parm("filter").eval(),
        "filterscale": resample.parm("filterscale").eval(),
    }
    del v05, v2, bilin05, delta_nearest, delta_bilinear, delta_2x2_block
    obj.destroy()
    gc.collect()
    columns = np.rint((xs + 3999.75) / 0.5).astype(int)
    rows = 15999 - np.rint((3999.75 - zs) / 0.5).astype(int)
    if (
        min(columns.min(), rows.min()) < 0
        or max(columns.max(), rows.max()) >= 16000
    ):
        raise RuntimeError("2m context exceeds current ID image")
    Image.MAX_IMAGE_PIXELS = 300000000
    with Image.open(idmap) as image:
        ids = np.asarray(image)
    sampled_ids = ids[np.ix_(rows, columns)]
    id_codes = np.unique(sampled_ids).astype(int).tolist()
    id_geometry = hou.Geometry(resampled_geo)
    id_field = id_geometry.prims()[0]
    id_field.setAttribValue("name", "id")
    id_values = np.ascontiguousarray(sampled_ids.astype(np.float32) / 255.0)
    id_field.setAllVoxelsFromString(id_values.tobytes())
    resampled_geo.merge(id_geometry)
    source = args.output / "registered_height_and_id.bgeo.sc"
    resampled_geo.saveToFile(str(source))
    m_nw_05 = mv05[1::4, 1::4]
    m_maj_2x2 = (
        (
            mv05[1:-2:4, 1:-2:4]
            + mv05[1:-2:4, 2:-1:4]
            + mv05[2:-1:4, 1:-2:4]
            + mv05[2:-1:4, 2:-1:4]
        )
        >= 2.0
    )
    categorical_stats = {
        "method": "Explicit categorical ID lookup at 2m sample centers (no bilinear ID interpolation), decoded via original PE_Heightfield_id_to_layer (id_layer=191)",
        "id_codes_present": id_codes,
        "source_05m_cliff_mask_samples": int(prep05["cliff_mask_samples"]),
        "source_05m_scaled_by_16": float(prep05["cliff_mask_samples"]) / 16.0,
        "stride4_05m_mask_samples": int(np.count_nonzero(m_nw_05)),
        "interior_2x2_majority_mask_samples": int(np.count_nonzero(m_maj_2x2)),
    }
    del ids, sampled_ids, id_values, id_geometry, id_field, resampled_geo, mv05
    gc.collect()
    obj = hou.node("/obj").createNode("geo", "GLOBAL_2M_ORIGINAL_DECODER")
    node = obj.createNode("file")
    node.parm("file").set(str(source.resolve()))
    hou.hda.installFile(str(args.otls / "sop_PE_Heightfield_id_to_layer.hda"))
    decoder = obj.createNode("PE_Heightfield_id_to_layer")
    decoder.setInput(0, node)
    decoder.setParms({"srcname1": "id", "dstname1": "mask", "id_layer": 191})
    decoded = hou.Geometry(decoder.geometry())
    mask = next(v for v in decoded.prims() if v.attribValue("name") == "mask")
    native_mask = np.frombuffer(mask.allVoxelsAsString(), np.float32).reshape(ny, nx)
    with Image.open(idmap) as image:
        ids_check = np.asarray(image)[np.ix_(rows, columns)] == 191
    if not np.array_equal(native_mask, ids_check):
        raise RuntimeError(
            "Original global 2m ID decoder differs from categorical cliff classification"
        )
    mask_hash = sha_bytes(mask.allVoxelsAsString())
    mask_count = int(np.count_nonzero(native_mask))
    categorical_stats["decoded_2m_cliff_mask_samples"] = mask_count
    decoded.deletePrims(
        [v for v in decoded.prims() if v.attribValue("name") not in {"height", "mask"}],
        True,
    )
    target = args.output / "flow_input.bgeo.sc"
    decoded.saveToFile(str(target))
    receipt = {
        "stage": "GLOBAL_WORKING_CORRIDOR_NATIVE_FLOW_INPUT_2M_DERIVATIVE",
        "producer_sha256": sha(__file__),
        "source_05m_preparation_receipt": str(prep05_path),
        "source_05m_preparation_receipt_sha256": sha(prep05_path),
        "source_05m_flow_input_sha256": prep05["flow_input_sha256"],
        "inventory_sha256": prep05["inventory_sha256"],
        "manifest_sha256": prep05["manifest_sha256"],
        "source_final_sha256": prep05["source_final_sha256"],
        "idmap_sha256": prep05["idmap_sha256"],
        "requested_bounds_xz_m": prep05["requested_bounds_xz_m"],
        "native_first_sample": list(first),
        "native_last_sample": list(last),
        "step_i_m": step_i_m,
        "step_j_m": step_j_m,
        "phase_offset_from_05m_first_sample_xz_m": phase_offset_xz_m,
        "resolution": [nx, ny, 1],
        "pieces": prep05["pieces"],
        "height_voxels_sha256": height_hash,
        "mask_voxels_sha256": mask_hash,
        "cliff_mask_samples": mask_count,
        "height_resampling_measurements": height_deltas,
        "categorical_mask_measurements": categorical_stats,
        "decoder_type": decoder.type().name(),
        "decoder_sha256": sha(decoder.type().definition().libraryFilePath()),
        "flow_input_sha256": sha(target),
        "registered_height_and_id_sha256": sha(source),
        "context_padding_m": 128,
        "grid_spacing_m": 2.0,
        "domain_adaptation": "Separate 2m derivative cliff input over the shared 555-window working corridor plus 128m context, matching measured 2m Pegasus source terrain spacing while keeping 0.5m FINAL and UE Landscape untouched",
        "source_05m_final_and_ue_untouched": True,
        "visibility_retained_in_original_tiles": True,
        "visibility_holes_in_corridor_domain": 0,
        "visibility_cliff_conflicts": 0,
        "native_flow_cook": "NOT RUN",
        "production_admission": False,
    }
    (args.output / "input_preparation.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(receipt), flush=True)


def cook_global_flow(args):
    """Execute the original flow/remap/copy branch once on the shared source."""
    import numpy as np

    prepared = json.loads(
        (args.cook_global_flow / "input_preparation.json").read_text()
    )
    source = args.cook_global_flow / "flow_input.bgeo.sc"
    if sha(source) != prepared["flow_input_sha256"]:
        raise RuntimeError("Global flow input differs from native preparation")
    library = args.otls / "sop_PE_Heightfield_Extract_Cliffs.1.0.hda"
    if (
        sha(library)
        != "16d7c13d9ca5ba4af221584a1fde7232fecfee0a3d173b616e1aabadf3464f70"
    ):
        raise RuntimeError("Global flow original definition changed")
    hou.hda.installFile(str(args.otls / "sop_PE_Heightfield_id_to_layer.hda"))
    hou.hda.installFile(str(library))
    expected = {
        "rainamount": 0.1,
        "raindensity": 0.1,
        "iterations": 100,
        "smoothiterations": 0,
        "domask": 1,
        "maskscale": 1.0,
        "doheight": 0,
        "seed": 8736.0,
    }
    if args.reopen:
        receipt = json.loads((args.output / "flow_receipt.json").read_text())
        if sha(args.output / "candidate.hiplc") != receipt["hip_sha256"]:
            raise RuntimeError("Global flow HIP changed")
        hou.hipFile.load(
            str(args.output / "candidate.hiplc"), suppress_save_prompt=True
        )
        node = hou.node(
            "/obj/GLOBAL_CLIFF_FLOW/ORIGINAL_EXTRACTOR/heightfield_copylayer1"
        )
    else:
        if args.output.exists():
            raise RuntimeError("Global flow output exists")
        args.output.mkdir(parents=True)
        obj = hou.node("/obj").createNode("geo", "GLOBAL_CLIFF_FLOW")
        file_node = obj.createNode("file", "CACHED_ORIGINAL_RESAMPLE_BOUNDARY")
        file_node.parm("file").set(str(source.resolve()))
        extract = obj.createNode(
            "PE_Heightfield_Extract_Cliffs::1.0", "ORIGINAL_EXTRACTOR"
        )
        extract.allowEditingOfContents()
        # Original Resample is fixedresample=0 / resscale=1: no reduction.
        # This cache is the same height/mask boundary, with unused ID/visibility
        # removed after the actual original decoder; source retention is external.
        if (
            extract.node("heightfield_resample1").parm("fixedresample").eval() != 0
            or extract.node("heightfield_resample1").parm("resscale").eval() != 1
        ):
            raise RuntimeError("Original resample mode changed")
        bridge = extract.createNode("object_merge", "CACHED_GLOBAL_FLOW_INPUT")
        bridge.parm("objpath1").set(file_node.path())
        bridge.parm("xformtype").set(0)
        extract.node("heightfield_flowfield1").setInput(0, bridge)
        node = extract.node("heightfield_copylayer1")
    flow_node = node.parent().node("heightfield_flowfield1")
    if any(flow_node.parm(key).eval() != value for key, value in expected.items()):
        raise RuntimeError("Original global flow parameters changed")
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    started = time.time()
    print(
        json.dumps(
            {
                "stage": "ORIGINAL_GLOBAL_FLOW_NATIVE_COOK_STARTED",
                "input_resolution": prepared["resolution"],
                "parameters": expected,
            }
        ),
        flush=True,
    )
    node.cook(force=True)
    if node.errors() or flow_node.errors():
        raise RuntimeError(
            "Original global flow cook failed: "
            + str(node.errors())
            + str(flow_node.errors())
        )
    geometry = hou.Geometry(node.geometry())
    flow = next(v for v in geometry.prims() if v.attribValue("name") == "flow")
    flow_res = list(flow.resolution())
    values = np.frombuffer(flow.allVoxelsAsString(), np.float32)
    if not np.isfinite(values).all():
        raise RuntimeError("Original global flow has nonfinite values")
    fingerprint = sha_bytes(flow.allVoxelsAsString())
    if args.reopen:
        if fingerprint != receipt["flow_voxels_sha256"]:
            raise RuntimeError("Fresh original global flow differs from saved values")
        (args.output / "flow_fresh_regeneration.json").write_text(
            json.dumps(
                {
                    "flow_voxels_sha256": fingerprint,
                    "graph_regeneration": "PASS",
                    "elapsed_seconds": time.time() - started,
                },
                indent=2,
            )
            + "\n"
        )
        print(
            json.dumps(
                {
                    "global_flow_fresh_graph_regeneration": "PASS",
                    "flow_voxels_sha256": fingerprint,
                }
            ),
            flush=True,
        )
        return
    geometry.deletePrims(
        [v for v in geometry.prims() if v.attribValue("name") != "flow"], True
    )
    output = args.output / "flow_cache.bgeo.sc"
    geometry.saveToFile(str(output))
    obj = node.parent().parent()
    cached = obj.createNode("file", "CACHED_GLOBAL_FLOW")
    cached.parm("file").set(str(output.resolve()))
    cached.setDisplayFlag(True)
    cached.setRenderFlag(True)
    hou.hipFile.save(str(args.output / "candidate.hiplc"))
    receipt = {
        "stage": "ORIGINAL_GLOBAL_WORKING_CORRIDOR_FLOW",
        "producer_sha256": sha(__file__),
        "prepared_input_receipt_sha256": sha(
            args.cook_global_flow / "input_preparation.json"
        ),
        "flow_input_sha256": sha(source),
        "input_resolution": prepared["resolution"],
        "input_first_sample": prepared["native_first_sample"],
        "input_last_sample": prepared["native_last_sample"],
        "original_extractor_sha256": sha(library),
        "parameters": expected,
        "resample_fixedresample": 0,
        "resample_resscale": 1.0,
        "inactive_gridspacing": 4.0,
        "flow_voxels_sha256": fingerprint,
        "flow_cache_sha256": sha(output),
        "hip_sha256": sha(args.output / "candidate.hiplc"),
        "resolution": flow_res,
        "range": [float(values.min()), float(values.max())],
        "elapsed_seconds": time.time() - started,
        "warnings": flow_node.warnings(),
        "domain_adaptation": prepared["domain_adaptation"],
        "flow_cook": "PASS",
        "full_8km_context_equivalence": "NOT RUN",
        "fresh_graph_regeneration": "NOT RUN",
        "geometry_generation": "NOT RUN",
        "production_admission": False,
    }
    (args.output / "flow_receipt.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(receipt), flush=True)


def split_original(args):
    """Run original PEG-05 output grouping without changing P/Cd/N/topology."""
    from collections import Counter

    prior = json.loads((args.split_input / "receipt.json").read_text())
    source = args.split_input / "cliffs.bgeo.sc"
    if (
        prior.get("stage") != "ORIGINAL_GENERATOR_ONE_REAL_CLASS"
        or sha(source) != prior["output_sha256"]
    ):
        raise RuntimeError("Original split requires verified generated cliff geometry")
    library = args.otls / "sop_PE_Cliff_Split.1.0.hda"
    if (
        sha(library)
        != "b40d2878cf6ab95d2e293120b0d4b63f89154331fa7c3baef283aa6f00016528"
    ):
        raise RuntimeError("Original split definition changed")
    hou.hda.installFile(str(library))
    if args.output.exists():
        raise RuntimeError("Original split output exists")
    args.output.mkdir(parents=True)
    obj = hou.node("/obj").createNode("geo", "ORIGINAL_CLIFF_SPLIT")
    file_node = obj.createNode("file", "VERIFIED_GENERATED_CLIFF")
    file_node.parm("file").set(str(source.resolve()))
    node = obj.createNode("PE_Cliff_Split::1.0", "ORIGINAL_SPLIT")
    node.setInput(0, file_node)
    if node.parm("gridsize").eval() != 100 or node.parm("naniteenabled").eval() != 1:
        raise RuntimeError("Original split numeric defaults changed")
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    node.cook(force=True)
    before, after = file_node.geometry(), node.geometry()
    checks = {
        "P": before.pointFloatAttribValuesAsString("P")
        == after.pointFloatAttribValuesAsString("P"),
        "Cd": before.pointFloatAttribValuesAsString("Cd")
        == after.pointFloatAttribValuesAsString("Cd"),
        "N": before.vertexFloatAttribValuesAsString("N")
        == after.vertexFloatAttribValuesAsString("N"),
        "topology": [
            tuple(v.point().number() for v in p.vertices()) for p in before.prims()
        ]
        == [tuple(v.point().number() for v in p.vertices()) for p in after.prims()],
    }
    if node.errors() or not all(checks.values()):
        raise RuntimeError(
            "Original output split changes source geometry/masks: "
            + str(checks)
            + str(node.errors())
        )
    output = args.output / "split_cliffs.bgeo.sc"
    after.saveToFile(str(output))
    node.setDisplayFlag(True)
    node.setRenderFlag(True)
    hou.hipFile.save(str(args.output / "candidate.hiplc"))
    result = {
        "stage": "ORIGINAL_CLIFF_OUTPUT_GROUPING",
        "producer_sha256": sha(__file__),
        "source_sha256": sha(source),
        "source_receipt_sha256": sha(args.split_input / "receipt.json"),
        "split_hda_sha256": sha(library),
        "gridsize": 100,
        "naniteenabled": 1,
        "material_reference": node.parm("material").eval(),
        "bake_folder": node.parm("bakefolder").eval(),
        "points": len(after.points()),
        "polygons": len(after.prims()),
        "unchanged_bytes": checks,
        "groups": dict(Counter(after.primStringAttribValues("unreal_output_name"))),
        "warnings": node.warnings(),
        "output_sha256": sha(output),
        "hip_sha256": sha(args.output / "candidate.hiplc"),
        "semantics": "Original bbox grid classification and UE output attributes only; no geometric clipping or new seam claim",
        "production_admission": False,
    }
    (args.output / "split_receipt.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps(result), flush=True)


def extract_global_2m(args):
    """Run connected global cliff extraction on the 2m derivative input and shared 2m flow cache."""
    import time
    from collections import Counter
    import numpy as np

    started = time.time()
    prep_dir = args.extract_global_2m
    prep = json.loads((prep_dir / "input_preparation.json").read_text())
    flow_source = prep_dir / "flow_input.bgeo.sc"
    if (
        prep.get("stage") != "GLOBAL_WORKING_CORRIDOR_NATIVE_FLOW_INPUT_2M_DERIVATIVE"
        or sha(flow_source) != prep["flow_input_sha256"]
        or prep["flow_input_sha256"]
        != "221586fff81841c953b3e2658ef5f5604d7d1e393f79998f878e1558dcbbe0a9"
    ):
        raise RuntimeError("Global 2m extraction requires verified 2m prepared input")
    if not args.flow_cache:
        raise RuntimeError("Global 2m extraction requires --flow-cache")
    flow_receipt = json.loads((args.flow_cache / "flow_receipt.json").read_text())
    flow_file = args.flow_cache / "flow_cache.bgeo.sc"
    library = args.otls / "sop_PE_Heightfield_Extract_Cliffs.1.0.hda"
    if (
        sha(library)
        != "16d7c13d9ca5ba4af221584a1fde7232fecfee0a3d173b616e1aabadf3464f70"
        or sha(flow_file) != flow_receipt["flow_cache_sha256"]
        or flow_receipt["flow_input_sha256"] != prep["flow_input_sha256"]
        or flow_receipt["resolution"] != [1985, 2625, 1]
    ):
        raise RuntimeError("Global 2m flow cache or extractor HDA identity differs")
    if args.original_project:
        original_hips = list(args.original_project.rglob("CliffPDG.hip"))
        if len(original_hips) != 1 or sha(original_hips[0]) != (
            "3fc1926e5d0aeea402e9984ed32e47fcc1ab7ae5e1478e3c1ce618c62489c57a"
        ):
            raise RuntimeError("Expected the hash-pinned original CliffPDG project")
    hou.hda.installFile(str(args.otls / "sop_PE_Heightfield_id_to_layer.hda"))
    hou.hda.installFile(str(library))
    if args.output.exists():
        raise RuntimeError("Global 2m extraction output already exists")
    args.output.mkdir(parents=True)
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    g = hou.node("/obj").createNode("geo", "CLIFF_REHEARSAL")
    staged = g.createNode("file", "GLOBAL_2M_FLOW_INPUT")
    staged.parm("file").set(str(flow_source.resolve()))
    extract = g.createNode(
        "PE_Heightfield_Extract_Cliffs::1.0", "ORIGINAL_CURRENT_EXTRACTION"
    )
    extract.setInput(0, staged)
    extract.allowEditingOfContents()
    # flow_input.bgeo.sc already holds the exact decoded categorical id=191 mask in layer 'mask'.
    extract.node("PE_Heightfield_id_to_layer1").bypass(True)
    flow_node = extract.createNode("file", "SHARED_ORIGINAL_SOURCE_FLOW_2M")
    flow_node.parm("file").set(str(flow_file.resolve()))
    extract.node("heightfield_layer1").setInput(1, flow_node)
    if extract.parm("threshold").eval() != 1000.0:
        raise RuntimeError("Original extraction threshold changed from 1000")
    extract.cook(force=True)
    result = extract.geometry()
    if extract.errors() or not result.prims() or any(
        not all(map(math.isfinite, p.position())) for p in result.points()
    ):
        raise RuntimeError("Global 2m cliff extraction failed: " + str(extract.errors()))
    out_bgeo = args.output / "cliffs.bgeo.sc"
    result.saveToFile(str(out_bgeo))
    cached = g.createNode("file", "CACHED_OUTPUT")
    cached.parm("file").set(str(out_bgeo.resolve()))
    cached.setDisplayFlag(True)
    cached.setRenderFlag(True)

    # Inventory all connected @class components and measure 2D/3D distance to Ma-2141 BTIB road
    classes = np.array(result.primIntAttribValues("class"), dtype=np.int32)
    counts = Counter(int(c) for c in classes)
    road_bgeo = Path("D:/yacs/work/ma2141-road-owner-20261024-btib1/pavement_top.bgeo.sc")
    road_node = g.createNode("file", "BTIB_ROAD_TOP")
    road_node.parm("file").set(str(road_bgeo.resolve()))
    dist_node = g.createNode("attribwrangle", "MEASURE_ROAD_DIST_3D")
    dist_node.setInput(0, extract)
    dist_node.setInput(1, road_node)
    dist_node.parm("snippet").set("f@road_dist_3d = xyzdist(1, @P);")
    dist_node.cook(force=True)
    dgeo = dist_node.geometry()
    pt_dists = np.array(dgeo.pointFloatAttribValues("road_dist_3d"), dtype=np.float64)

    class_summary = []
    for cid, prim_cnt in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        sel = g.createNode("blast", f"TMP_CLASS_{cid}")
        sel.setInput(0, dist_node)
        sel.setParms({"group": f"@class={cid}", "negate": 1})
        sel.cook(force=True)
        sgeo = sel.geometry()
        sdists = np.array(sgeo.pointFloatAttribValues("road_dist_3d"), dtype=np.float64)
        bb = sgeo.boundingBox()
        class_summary.append(
            {
                "class_id": int(cid),
                "primitives": int(prim_cnt),
                "points": len(sgeo.points()),
                "within_execution_budget_3000": bool(prim_cnt <= 3000),
                "min_3d_distance_to_btib_road_m": float(sdists.min()),
                "p05_3d_distance_to_btib_road_m": float(np.percentile(sdists, 5)),
                "mean_3d_distance_to_btib_road_m": float(sdists.mean()),
                "bounds_min": list(bb.minvec()),
                "bounds_max": list(bb.maxvec()),
            }
        )
        sel.destroy()
    dist_node.destroy()
    road_node.destroy()
    g.layoutChildren()
    hou.hipFile.save(str(args.output / "candidate.hiplc"))

    receipt = {
        "stage": "CURRENT_FINAL_ROADSIDE_CROP_EXTRACTION",
        "extraction_mode": "CONNECTED_GLOBAL_2M_DERIVATIVE_CORRIDOR_EXTRACTION",
        "houdini": hou.applicationVersionString(),
        "producer_sha256": sha(__file__),
        "source_final_sha256": prep["source_final_sha256"],
        "prepared_2m_input_receipt_sha256": sha(prep_dir / "input_preparation.json"),
        "flow_input_sha256": prep["flow_input_sha256"],
        "shared_original_flow": {
            "receipt_sha256": sha(args.flow_cache / "flow_receipt.json"),
            "cache_sha256": flow_receipt["flow_cache_sha256"],
            "field_voxels_sha256": flow_receipt["flow_voxels_sha256"],
            "grid_spacing_m": 2.0,
            "resolution": flow_receipt["resolution"],
        },
        "original_extraction_profile": {
            "hip_sha256": "3fc1926e5d0aeea402e9984ed32e47fcc1ab7ae5e1478e3c1ce618c62489c57a",
            "threshold": 1000.0,
            "flow_split": True,
            "road_exclusion": False,
            "input_adaptations": "Separate 2m derivative cliff input from admitted 0.5m FINAL height + exact categorical ID=191 mask; full-corridor connected extraction with shared 2m flow",
        },
        "extraction_threshold": 1000.0,
        "points": len(result.points()),
        "primitives": len(result.prims()),
        "connected_class_count": len(counts),
        "classes_within_budget_3000": sum(1 for c in class_summary if c["within_execution_budget_3000"]),
        "classes_above_budget_3000": sum(1 for c in class_summary if not c["within_execution_budget_3000"]),
        "global_min_3d_distance_to_btib_road_m": float(pt_dists.min()),
        "class_inventory": class_summary,
        "elapsed_seconds": time.time() - started,
        "warnings": extract.warnings(),
        "output_sha256": sha(out_bgeo),
        "hip_sha256": sha(args.output / "candidate.hiplc"),
        "cook": "PASS",
        "production_admission": False,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    )
    print(
        json.dumps(
            {
                "stage": receipt["extraction_mode"],
                "points": receipt["points"],
                "primitives": receipt["primitives"],
                "connected_class_count": receipt["connected_class_count"],
                "classes_within_budget_3000": receipt["classes_within_budget_3000"],
                "classes_above_budget_3000": receipt["classes_above_budget_3000"],
                "global_min_3d_distance_to_btib_road_m": receipt["global_min_3d_distance_to_btib_road_m"],
                "elapsed_seconds": receipt["elapsed_seconds"],
                "output_sha256": receipt["output_sha256"],
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

    original_extraction = None
    if args.original_project:
        original_hips = list(args.original_project.rglob("CliffPDG.hip"))
        if len(original_hips) != 1 or sha(original_hips[0]) != (
            "3fc1926e5d0aeea402e9984ed32e47fcc1ab7ae5e1478e3c1ce618c62489c57a"
        ):
            raise RuntimeError("Expected the hash-pinned original CliffPDG project")
        original_extraction = {
            "hip_sha256": sha(original_hips[0]),
            "threshold": 1000.0,
            "flow_split": True,
            "road_exclusion": False,
            "input_adaptations": "Real registered height/visibility and current IDMap cliff code 191; bounded crop input, not global flow-context equivalence",
        }
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
    is_2m_branch = args.grid_spacing == 2.0
    if is_2m_branch:
        prep2m_dir = Path("D:/yacs/work/pegasus-cliff-route-source-20261024-global-input-2m")
        prep2m = json.loads((prep2m_dir / "input_preparation.json").read_text())
        path = prep2m_dir / "registered_height_and_id.bgeo.sc"
        if (
            prep2m["flow_input_sha256"]
            != "221586fff81841c953b3e2658ef5f5604d7d1e393f79998f878e1558dcbbe0a9"
            or sha(path) != prep2m["registered_height_and_id_sha256"]
            or sha(record["idmap"]) != record["idmap_sha256"]
        ):
            raise RuntimeError("2m derivative input or current IDMap identity changed")
        tile = {
            "file": path.name,
            "sha256": prep2m["registered_height_and_id_sha256"],
        }
    elif not candidates:
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
    expected_layers = {"height", "id"} if is_2m_branch else {"height", "visibility"}
    min_res = 64 + args.halo if is_2m_branch else 256 + 4 * args.halo
    max_res = 66 + args.halo if is_2m_branch else 258 + 4 * args.halo
    if set(layers) != expected_layers or any(
        not (
            min_res <= v.resolution()[0] <= max_res
            and min_res <= v.resolution()[1] <= max_res
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
    hole_count = (
        0
        if is_2m_branch
        else int(
            np.count_nonzero(
                np.frombuffer(layers["visibility"].allVoxelsAsString(), np.float32)
                > 0.5
            )
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
    if is_2m_branch:
        mask_geo = hou.Geometry(geo)
        mask_geo.deletePrims(
            [v for v in mask_geo.prims() if v.attribValue("name") != "id"], True
        )
        mask_geo.prims()[0].setAttribValue("name", "mask")
        mask_geo.prims()[0].setAllVoxelsFromString(
            np.zeros((ny, nx), np.float32).tobytes()
        )
        geo.merge(mask_geo)
    else:
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
        mask_geo.prims()[0].setAllVoxelsFromString(
            np.zeros((ny, nx), np.float32).tobytes()
        )
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
    shared_flow = None
    if args.flow_cache:
        flow_receipt = json.loads((args.flow_cache / "flow_receipt.json").read_text())
        flow_file = args.flow_cache / "flow_cache.bgeo.sc"
        expected_flow_input = (
            "221586fff81841c953b3e2658ef5f5604d7d1e393f79998f878e1558dcbbe0a9"
            if is_2m_branch
            else "067ae4ebdc0f68afef7dc88782834017c974a761a3e0db8e308ab9180500405e"
        )
        expected_flow_res = [1985, 2625, 1] if is_2m_branch else [7938, 10498, 1]
        if (
            sha(flow_file) != flow_receipt["flow_cache_sha256"]
            or flow_receipt["flow_input_sha256"] != expected_flow_input
            or flow_receipt["resolution"] != expected_flow_res
            or flow_receipt["original_extractor_sha256"] != sha(library)
        ):
            raise RuntimeError("Shared source flow identity differs")
        flow_node = extract.createNode("file", "SHARED_ORIGINAL_SOURCE_FLOW")
        flow_node.parm("file").set(str(flow_file.resolve()))
        extract.node("heightfield_layer1").setInput(1, flow_node)
        shared_flow = {
            "receipt_sha256": sha(args.flow_cache / "flow_receipt.json"),
            "cache_sha256": flow_receipt["flow_cache_sha256"],
            "field_voxels_sha256": flow_receipt["flow_voxels_sha256"],
            "flow_input_sha256": flow_receipt["flow_input_sha256"],
            "grid_spacing_m": 2.0 if is_2m_branch else 0.5,
            "resolution": flow_receipt["resolution"],
            "domain_adaptation": flow_receipt["domain_adaptation"],
            "native_cache_boundary": "Original remap/copy output feeds original HeightField Layer; original per-crop flow dependency is unused",
        }
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
    lattice_max = 0.0
    if original_extraction:
        if extract.parm("threshold").eval() != 1000.0:
            raise RuntimeError("Original extraction threshold changed")
    else:
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
            raise RuntimeError(
                "Source lattice correction exceeds 1mm or changes height"
            )
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
        "source_lattice_precision_applied": not bool(original_extraction),
        "original_extraction_profile": original_extraction,
        "shared_original_flow": shared_flow,
        "extraction_threshold": extract.parm("threshold").eval(),
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
    original_project = None
    bindings_path = None
    if args.original_project:
        original_hips = list(args.original_project.rglob("CliffPDG.hip"))
        if len(original_hips) != 1 or sha(original_hips[0]) != (
            "3fc1926e5d0aeea402e9984ed32e47fcc1ab7ae5e1478e3c1ce618c62489c57a"
        ):
            raise RuntimeError("Expected the hash-pinned original CliffPDG project")
        texture_root = args.original_project / "SourceContent/Pegasus/Textures"
        maps = [
            {"path": str(texture_root / filename), "sha256": digest}
            for filename, digest in (
                (
                    "wepoeaw_4K_Displacement.exr",
                    "bfd92a6294d246c2ce58a2e93cbbfffa13c3653b77eb7ae00a9ed2a328f99993",
                ),
                (
                    "tlonbisya_4K_Displacement.exr",
                    "e0e7c2ddcf6e3d98d91ffa3747a9234791ebf8aae52009bddc8ab9d740279b30",
                ),
            )
        ]
        original_project = {
            "hip_sha256": sha(original_hips[0]),
            "textures": "Original tutorial Megascans displacement maps, owner-supplied bundle; retained externally, no redistribution claim",
            "scope": "Original generator numeric settings and unmodified internal graph; selected real-source component is an explicit geographic input adaptation",
        }
    else:
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
            raise RuntimeError("Height map differs from the selected source binding")
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
    source_settings = {
        "subdivision": 2,
        "edgemask": 4.0,
        "scale": 0.01,
        "strength": 10.0,
        "exp": 1.5,
        "percentage": 80.0,
    }
    if original_project:
        if any(n.parm(k).eval() != v for k, v in source_settings.items()):
            raise RuntimeError("Original generator numeric defaults changed")
        # Keep all original numeric and internal parameters. Only resolve the two
        # broken project-variable paths to the identical retained source images.
        n.setParms({"displacement1": maps[0]["path"], "displacement2": maps[1]["path"]})
        strength = n.parm("strength").eval()
    else:
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
        strength = args.strength
    n.allowEditingOfContents()
    if args.normal_blur_only:
        n.node("attribblur2").parm("attributes").set("N")
    hou.setUpdateMode(hou.updateMode.AutoUpdate)
    select.cook(force=True)
    source_primitives = len(select.geometry().prims())
    if not 0 < source_primitives <= args.max_source_primitives:
        raise RuntimeError(
            f"Selected class has {source_primitives} primitives, above the explicit execution budget {args.max_source_primitives}"
        )
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
    n.parm("strength").set(strength)
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

    # Measure 3D road clearance against BTIB 2021 3D road top surface
    road_bgeo = Path("D:/yacs/work/ma2141-road-owner-20261024-btib1/pavement_top.bgeo.sc")
    road_clearance_info = "NOT RUN"
    if road_bgeo.exists():
        rnode = g.createNode("file", "BTIB_ROAD_TOP")
        rnode.parm("file").set(str(road_bgeo.resolve()))
        rmeas = g.createNode("attribwrangle", "MEASURE_ROAD_CLEARANCE_3D")
        rmeas.setInput(0, cached)
        rmeas.setInput(1, rnode)
        rmeas.parm("snippet").set("f@road_dist_3d = xyzdist(1, @P);")
        rmeas.cook(force=True)
        rdists = np.array(
            rmeas.geometry().pointFloatAttribValues("road_dist_3d"), dtype=np.float64
        )
        road_clearance_info = {
            "road_bgeo": str(road_bgeo),
            "road_bgeo_sha256": sha(road_bgeo),
            "min_3d_distance_m": float(rdists.min()),
            "p05_3d_distance_m": float(np.percentile(rdists, 5)),
            "mean_3d_distance_m": float(rdists.mean()),
            "passes_5m_clearance": bool(rdists.min() >= 5.0),
        }
        rmeas.destroy()
        rnode.destroy()

    fbx_export = None
    if args.export_fbx:
        fbx_path = args.output / f"SM_Pegasus_2m_Class{args.class_id}.fbx"
        ropnet = hou.node("/obj").createNode("ropnet", f"FBX_EXPORT_{args.class_id}")
        fbx_rop = ropnet.createNode("filmboxfbx", "EXPORT_FBX")
        fbx_rop.setParms(
            {
                "startnode": g.path(),
                "sopoutput": str(fbx_path.resolve()),
                "trange": 0,
                "axissystem": 0,
                "convertaxis": 0,
                "convertunits": 1,
                "exportkind": 0,
            }
        )
        fbx_rop.render()
        ropnet.destroy()
        fbx_export = {
            "fbx_path": str(fbx_path),
            "fbx_sha256": sha(fbx_path),
            "bytes": fbx_path.stat().st_size,
            "controls": {
                "startnode": g.path(),
                "trange": 0,
                "axissystem": 0,
                "convertaxis": 0,
                "convertunits": 1,
                "exportkind": 0,
            },
        }

    g.layoutChildren()
    hou.hipFile.save(str(args.output / "candidate.hiplc"))
    receipt = {
        "stage": "ORIGINAL_GENERATOR_ONE_REAL_CLASS",
        "houdini": hou.applicationVersionString(),
        "producer_sha256": sha(__file__),
        "points": len(geo.points()),
        "primitives": len(geo.prims()),
        "source_primitives": source_primitives,
        "max_source_primitives_execution_budget": args.max_source_primitives,
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
        "bindings_sha256": sha(bindings_path) if bindings_path else None,
        "original_project": original_project,
        "generator_parameters": {key: n.parm(key).eval() for key in source_settings},
        "original_numeric_settings_equal": all(
            n.parm(key).eval() == value for key, value in source_settings.items()
        )
        if original_project
        else False,
        "original_internal_normal_blur_attributes": n.node("attribblur2")
        .parm("attributes")
        .eval(),
        "adapted_parameters": {
            "subdivision": n.parm("subdivision").eval(),
            "strength": strength,
            "scale": n.parm("scale").eval(),
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
        "road_clearance": road_clearance_info,
        "fbx_export": fbx_export,
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
    p.add_argument("--resume-native", action="store_true", help=argparse.SUPPRESS)
    p.add_argument(
        "--resume",
        type=Path,
        help="Validate retained V3 checkpoints only; no generation or recook",
    )
    p.add_argument("--batch-limit", type=int, default=178)
    p.add_argument("--source", type=Path)
    p.add_argument(
        "--split-input",
        type=Path,
        help="Apply original100m Cliff Split output grouping to a verified generated component",
    )
    p.add_argument(
        "--prepare-global-flow",
        type=Path,
        help="Native source height/ID preparation for one shared full-working-corridor flow context",
    )
    p.add_argument(
        "--prepare-global-flow-2m",
        type=Path,
        help="Native 2m derivative cliff input adapter from verified 0.5m global flow input directory",
    )
    p.add_argument(
        "--grid-spacing",
        type=float,
        choices=[0.5, 2.0],
        default=0.5,
        help="Grid spacing in metres for global flow preparation (0.5 or 2.0)",
    )
    p.add_argument(
        "--cook-global-flow",
        type=Path,
        help="Run the original global flow branch on prepared shared corridor height/mask",
    )
    p.add_argument(
        "--extract-global-2m",
        type=Path,
        help="Run connected global cliff extraction on the prepared 2m corridor input with shared 2m flow",
    )
    p.add_argument(
        "--flow-cache",
        type=Path,
        help="Reuse the verified original shared global flow with current native extraction",
    )
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
        "--original-project",
        type=Path,
        help="Use exact original CliffPDG generator settings and retained original displacement EXRs; paths only are adapted",
    )
    p.add_argument(
        "--regenerate",
        action="store_true",
        help="With --reopen, independently cook the saved generator and compare positions/topology to disk output",
    )
    p.add_argument(
        "--class-id",
        type=int,
        default=27,
        help="Existing extraction class; bounded by --max-source-primitives",
    )
    p.add_argument(
        "--max-source-primitives",
        type=int,
        default=1000,
        help="Explicit execution-memory budget, not a source geometry parameter; default 1000 input faces",
    )
    p.add_argument(
        "--normal-blur-only",
        action="store_true",
        help="PEG-05 L03 06:29-06:46 N-only control; original HDA default P N retained otherwise",
    )
    p.add_argument(
        "--strength",
        type=float,
        default=None,
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
    p.add_argument(
        "--export-fbx",
        action="store_true",
        help="Export generated cliff component to FBX using official UE axis/unit controls",
    )
    p.add_argument("--reopen", action="store_true")
    args = p.parse_args()
    if args.resume_native:
        if hou is None or not args.resume or args.output.exists():
            p.error(
                "Native checkpoint readback requires hython, --resume and a fresh output"
            )
        if hou.applicationVersion() != (22, 0, 466):
            raise RuntimeError("Native version changed")
        hou.setMaxThreads(2)
        args.output.mkdir(parents=True)
        checkpoint = json.loads((args.resume / "batch.json").read_text())
        for core in checkpoint["cores"]:
            source = Path(core["output_directory"]) / "cliffs.bgeo.sc"
            if sha(source) != core["output_sha256"]:
                raise RuntimeError("Native checkpoint source changed")
            geometry = hou.Geometry()
            geometry.loadFromFile(str(source))
            ix, iz = core["core"]
            geometry.saveToFile(str(args.output / f"core_{ix}_{iz}.obj"))
        return
    if args.resume and (not args.batch or args.reuse_batch):
        p.error("--resume requires --batch and cannot combine with --reuse-batch")
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
    if args.original_project and (
        not (args.detail or args.current_crop or args.extract_global_2m)
        or args.strength is not None
        or args.normal_blur_only
        or args.pre_flow
        or args.road_exclusion
        or args.halo
    ):
        p.error(
            "Original project profile requires --detail, --current-crop, or --extract-global-2m and forbids numeric/graph overrides"
        )
    if args.regenerate and not args.reopen:
        p.error("--regenerate requires --reopen")
    if not 1 <= args.max_source_primitives <= 100000:
        p.error("Source primitive execution budget must be within 1..100000")
    if args.strength is None:
        args.strength = 0.15
    if not math.isfinite(args.strength) or not 0 <= args.strength <= 1.2:
        p.error("Experimental strength must be finite and within 0..1.2")
    if hou.applicationVersion() != (22, 0, 466):
        raise RuntimeError("This candidate was verified with Houdini 22.0.466 only")
    hou.setUpdateMode(hou.updateMode.Manual)
    hou.setMaxThreads(2)
    if args.prepare_global_flow_2m:
        prepare_global_flow_2m(args)
        return
    if args.prepare_global_flow:
        if args.grid_spacing == 2.0:
            args.prepare_global_flow_2m = args.prepare_global_flow
            prepare_global_flow_2m(args)
        else:
            prepare_global_flow(args)
        return
    if args.cook_global_flow:
        cook_global_flow(args)
        return
    if args.extract_global_2m:
        extract_global_2m(args)
        return
    if args.split_input:
        split_original(args)
        return
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
        if args.regenerate:
            if receipt.get("stage") == "ORIGINAL_GENERATOR_ONE_REAL_CLASS":
                generator = hou.node("/obj/CLIFF_REHEARSAL/ORIGINAL_GENERATOR")
            elif receipt.get("original_extraction_profile"):
                generator = hou.node("/obj/CLIFF_REHEARSAL/ORIGINAL_CURRENT_EXTRACTION")
            else:
                raise RuntimeError(
                    "Graph regeneration requires a detail or original-extraction checkpoint"
                )
            generator.cook(force=True)
            regenerated = generator.geometry()
            same_positions = regenerated.pointFloatAttribValuesAsString(
                "P"
            ) == geom.pointFloatAttribValuesAsString("P")
            same_topology = [
                tuple(v.point().number() for v in p.vertices())
                for p in regenerated.prims()
            ] == [tuple(v.point().number() for v in p.vertices()) for p in geom.prims()]
            if generator.errors() or not same_positions or not same_topology:
                raise RuntimeError(
                    "Fresh graph regeneration differs from cached geometry"
                )
            receipt["graph_regeneration"] = "PASS"
            receipt["regeneration_comparison"] = (
                "Exact ordered P float bytes and oriented polygon point indices, native fresh process; other attributes are not included"
            )
            regenerated.saveToFile(str(args.output / "fresh_regenerated.bgeo.sc"))
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
