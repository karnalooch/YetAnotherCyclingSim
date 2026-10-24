"""Preserve Ma-2141 sources in isolated Houdini diagnostic candidates.

Run inspect with repository Python (pyproj/Shapely); run build/verify with
hython. Full-route observed heights keep unsupported bridge transitions open.
Visual width is explicit assumption; bounded terrain trials are reversible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT
    / "worldgen/terrain/benchmarks/sa_calobra/ma2141_cartociudad_source_2026-10-02.json"
)
SOURCE_SHA = "6520b92486b5d1c63353b8253d388ab21d380c78fda119849311be8344d8ae36"
BLOCKERS = [
    "Full-route asphalt elevation and vertical datum are not admitted",
    "Full-route pavement width and banking are not supplied by CartoCiudad",
    "LiDAR-resolved part 4 / parts 3 and 5 crossing levels are not integrated into a 3D profile/construction",
    "Canonical route and Road Physics Profile admission cannot be inferred from a visual baseline",
]


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def prepare_profile(source, dtm, laz, output):
    """Source observations only: never interpolate an unsupported bridge transition."""
    import laspy
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from shapely import wkt
    from shapely.ops import transform

    if digest(source) != SOURCE_SHA:
        raise ValueError("Pinned route source changed")
    laz_sha = "af3b790313846225bde04f48b95609963e652d696c0a2edca0d1722eec8ec6d8"
    if digest(laz) != laz_sha:
        raise ValueError("Audited crossing LiDAR changed")
    route = transform(
        Transformer.from_crs(4326, 25831, always_xy=True).transform,
        wkt.loads(json.loads(source.read_text())["geom"]),
    )
    crossing = np.array([484251.6634679027, 4409131.131841254])
    bridge = []
    with laspy.open(laz) as reader:
        for chunk in reader.chunk_iterator(250000):
            x, y = np.asarray(chunk.x), np.asarray(chunk.y)
            keep = (
                (np.asarray(chunk.classification) == 17)
                & (abs(x - crossing[0]) <= 50)
                & (abs(y - crossing[1]) <= 50)
            )
            if keep.any():
                bridge.append(
                    np.column_stack((x[keep], y[keep], np.asarray(chunk.z)[keep]))
                )
    bridge = np.concatenate(bridge)
    parts = []
    with rasterio.open(dtm) as raster:
        if raster.crs.to_epsg() != 25831:
            raise ValueError("DTM CRS mismatch")
        for index, line in enumerate(route.geoms):
            dense = line.segmentize(2.0)
            xy = [list(p) for p in dense.coords]
            stations = np.concatenate(
                (
                    [0.0],
                    np.cumsum(np.linalg.norm(np.diff(np.asarray(xy), axis=0), axis=1)),
                )
            ).tolist()
            samples = list(raster.sample(xy, masked=True))
            observations = []
            for station, position, sample in zip(stations, xy, samples, strict=True):
                if np.ma.is_masked(sample[0]) or not math.isfinite(float(sample[0])):
                    raise ValueError("Invalid full-route DTM sample")
                upper = (index == 4 and station <= 50) or (
                    index == 5 and line.length - station <= 50
                )
                nearby = (
                    bridge[np.sum((bridge[:, :2] - position) ** 2, axis=1) <= 1.5**2]
                    if upper
                    else []
                )
                z = float(sample[0])
                kind = "DTM_GROUND_NOT_PAVEMENT_SURVEY"
                if upper:
                    z = float(np.median(nearby[:, 2])) if len(nearby) else None
                    kind = (
                        "CLASS17_LOCAL_MEDIAN_NOT_DECK_ADMITTED"
                        if len(nearby)
                        else "UNRESOLVED_UPPER_BRANCH_EXCLUDED"
                    )
                observations.append(
                    {
                        "station_m": station,
                        "easting_m": position[0],
                        "northing_m": position[1],
                        "height_m": z,
                        "dtm_height_m": float(sample[0]),
                        "source_kind": kind,
                        "class17_count_radius_1_5m": len(nearby),
                    }
                )
            parts.append(
                {
                    "source_part": index,
                    "closed_xy": line.is_ring,
                    "closed_xyz": False,
                    "observations": observations,
                }
            )
    write_new(
        output,
        {
            "status": "SOURCE_3D_OBSERVATIONS_NOT_ROAD_PROFILE",
            "producer_sha256": digest(Path(__file__)),
            "route_sha256": SOURCE_SHA,
            "dtm_sha256": digest(dtm),
            "laz_sha256": laz_sha,
            "metric_crs": "EPSG:25831",
            "origin_epsg25831_m": [483650, 4409899.5],
            "axis_mapping": "X=easting-483650; Y=observed height; Z=4409899.5-northing (L06 south-positive)",
            "bridge_aoi_class17_count": len(bridge),
            "bridge_transition_search_m": 50,
            "bridge_radius_m": 1.5,
            "bridge_warning": "Class17 includes bridge accessories; medians are observations, not admitted pavement. Unsupported upper-branch samples omitted; no transition interpolation.",
            "parts": parts,
            "road_admitted": False,
        },
    )


def profile_geometry(record_path, output, reopen=False):
    import hou

    if hou.applicationVersionString() != "22.0.466":
        raise ValueError("Revalidate native profile adapter")
    record = json.loads(record_path.read_text())
    if record["route_sha256"] != SOURCE_SHA or len(record["parts"]) != 6:
        raise ValueError("Source coverage mismatch")
    expected = []
    expected_runs = []
    expected_attributes = []
    excluded = 0
    if not reopen:
        output.mkdir(parents=True, exist_ok=False)
        geometry = hou.Geometry()
        geometry.addAttrib(hou.attribType.Point, "source_part", 0)
        geometry.addAttrib(hou.attribType.Point, "source_kind", "")
        geometry.addAttrib(hou.attribType.Point, "station_m", 0.0)
        geometry.addAttrib(hou.attribType.Point, "up", (0.0, 1.0, 0.0))
    for part in record["parts"]:
        primitive = None
        prior_kind = None
        run = None
        for observation in part["observations"]:
            if observation["height_m"] is None:
                excluded += 1
                primitive = None
                prior_kind = None
                run = None
                continue
            position = (
                observation["easting_m"] - 483650,
                observation["height_m"],
                4409899.5 - observation["northing_m"],
            )
            expected.append(position)
            if run is None or observation["source_kind"] != prior_kind:
                run = []
                expected_runs.append(run)
            run.append(len(expected) - 1)
            expected_attributes.append(
                (
                    part["source_part"],
                    observation["source_kind"],
                    observation["station_m"],
                )
            )
            if not reopen:
                if primitive is None or observation["source_kind"] != prior_kind:
                    primitive = geometry.createPolygon(is_closed=False)
                point = geometry.createPoint()
                point.setPosition(position)
                point.setAttribValue("source_part", part["source_part"])
                point.setAttribValue("source_kind", observation["source_kind"])
                point.setAttribValue("station_m", observation["station_m"])
                primitive.addVertex(point)
            prior_kind = observation["source_kind"]
    if reopen:
        prior = json.loads((output / "profile_receipt.json").read_text())
        if prior["record_sha256"] != digest(record_path):
            raise ValueError("Profile record identity changed")
        if prior["producer_sha256"] != digest(Path(__file__)):
            raise ValueError("Profile producer changed; rebuild before verification")
        for name, sha in prior["files"].items():
            if digest(output / name) != sha:
                raise ValueError("Profile artifact changed")
        hou.hipFile.load(str(output / "source_profile.hip"), suppress_save_prompt=True)
        geometry = hou.node("/obj/MA2141_SOURCE_PROFILE/OBSERVATIONS").geometry()
    else:
        geometry.saveToFile(str(output / "source_profile.bgeo.sc"))
        obj = hou.node("/obj").createNode("geo", "MA2141_SOURCE_PROFILE")
        node = obj.createNode("file", "OBSERVATIONS")
        node.parm("file").set("$HIP/source_profile.bgeo.sc")
        sweep = obj.createNode("sweep::2.0", "ASSUMED_5M_VISUAL_ONLY")
        sweep.setInput(0, node)
        sweep.setParms({"surfaceshape": 3, "width": 5, "upvectortype": 2})
        sweep.setDisplayFlag(True)
        hou.hipFile.save(str(output / "source_profile.hip"))
        sweep.geometry().saveToFile(str(output / "visual_5m.bgeo.sc"))
    if len(geometry.points()) != len(expected) or any(
        p.isClosed() for p in geometry.prims()
    ):
        raise ValueError("Profile points or open topology changed")
    if [
        [v.point().number() for v in p.vertices()] for p in geometry.prims()
    ] != expected_runs:
        raise ValueError("Profile source run connectivity changed")
    for point, (part, kind, station) in zip(
        geometry.points(), expected_attributes, strict=True
    ):
        if (
            point.attribValue("source_part") != part
            or point.attribValue("source_kind") != kind
            or abs(point.attribValue("station_m") - station) > 0.001
        ):
            raise ValueError("Profile source attributes changed")
        if tuple(point.attribValue("up")) != (0.0, 1.0, 0.0):
            raise ValueError("Profile pavement up-vector changed")
    if not all(math.isfinite(v) for p in geometry.points() for v in p.position()):
        raise ValueError("Nonfinite native profile coordinate")
    error = max(
        abs(a - b)
        for point, target in zip(geometry.points(), expected, strict=True)
        for a, b in zip(point.position(), target, strict=True)
    )
    if not math.isfinite(error) or error > 0.001:
        raise ValueError("Source profile position mismatch")
    sweep = hou.node("/obj/MA2141_SOURCE_PROFILE/ASSUMED_5M_VISUAL_ONLY")
    surface = sweep.geometry()
    if not surface.prims() or not all(
        math.isfinite(v) for p in surface.points() for v in p.position()
    ):
        raise ValueError("Empty or nonfinite visual Sweep")
    if sweep.parm("width").eval() != 5 or sweep.parm("surfaceshape").eval() != 3:
        raise ValueError("Native Sweep controls changed")
    normal_y = [p.normal()[1] for p in surface.prims()]
    if sweep.parm("upvectortype").eval() != 2 or min(normal_y) <= 0:
        raise ValueError(
            f"Native pavement has {sum(y <= 0 for y in normal_y)} inverted/vertical faces"
        )
    receipt = {
        "status": "SOURCE_PROFILE_DIAGNOSTIC_NOT_ADMITTED",
        "producer_sha256": digest(Path(__file__)),
        "record_sha256": digest(record_path),
        "observed_points": len(expected),
        "excluded_unsupported_points": excluded,
        "open_primitives": len(geometry.prims()),
        "maximum_storage_delta_m": error,
        "axis_mapping": record["axis_mapping"],
        "visual_width_m_assumption": 5,
        "native_sweep_type": sweep.type().name(),
        "minimum_face_normal_y": min(normal_y),
        "source_run_connectivity_and_attributes_verified": True,
        "native_sweep_controls": {
            "width": sweep.parm("width").eval(),
            "surfaceshape": sweep.parm("surfaceshape").eval(),
            "upvectortype": sweep.parm("upvectortype").eval(),
        },
        "surface_points": len(
            hou.node("/obj/MA2141_SOURCE_PROFILE/ASSUMED_5M_VISUAL_ONLY")
            .geometry()
            .points()
        ),
        "surface_primitives": len(
            hou.node("/obj/MA2141_SOURCE_PROFILE/ASSUMED_5M_VISUAL_ONLY")
            .geometry()
            .prims()
        ),
        "files": {
            name: digest(output / name)
            for name in [
                "source_profile.bgeo.sc",
                "source_profile.hip",
                "visual_5m.bgeo.sc",
            ]
        },
        "road_admitted": False,
    }
    write_new(
        output / ("profile_reopen.json" if reopen else "profile_receipt.json"), receipt
    )


def export_profile_fbx(profile_root, output):
    """Original FBX ROP, explicit units; consumer conversion requires its own proof."""
    import hou

    if hou.applicationVersionString() != "22.0.466":
        raise ValueError("Revalidate FBX exporter")
    receipt = json.loads((profile_root / "profile_receipt.json").read_text())
    reopen = json.loads((profile_root / "profile_reopen.json").read_text())
    if receipt["producer_sha256"] != digest(Path(__file__)) or reopen[
        "producer_sha256"
    ] != digest(Path(__file__)):
        raise ValueError("Export requires exact-producer build and reopen")
    source = profile_root / "visual_5m.bgeo.sc"
    if digest(source) != receipt["files"][source.name]:
        raise ValueError("Export source geometry changed")
    output.mkdir(parents=True, exist_ok=False)
    obj = hou.node("/obj").createNode("geo", "MA2141_SOURCE_UP")
    node = obj.createNode("file", "VERIFIED_VISUAL_SOURCE")
    node.parm("file").set(str(source))
    node.setDisplayFlag(True)
    node.setRenderFlag(True)
    geometry = node.geometry()
    if any(p.normal()[1] <= 0 for p in geometry.prims()):
        raise ValueError("Export pavement face inversion")
    rop = hou.node("/out").createNode("filmboxfbx", "SOURCE_UP_EXPORT")
    target = output / "ma2141_source_up.fbx"
    controls = {
        "startnode": obj.path(),
        "sopoutput": str(target),
        "trange": 0,
        "axissystem": 0,
        "convertaxis": 0,
        "convertunits": 1,
        "exportkind": 0,
    }
    rop.setParms(controls)
    rop.render(frame_range=(1, 1))
    hou.hipFile.save(str(output / "export.hip"))
    bounds = geometry.boundingBox()
    write_new(
        output / "export_receipt.json",
        {
            "status": "NATIVE_FBX_EXPORTED_CONSUMER_UNVERIFIED",
            "producer_sha256": digest(Path(__file__)),
            "source_sha256": digest(source),
            "fbx_sha256": digest(target),
            "source_bounds_houdini_m": [list(bounds.minvec()), list(bounds.maxvec())],
            "points": len(geometry.points()),
            "primitives": len(geometry.prims()),
            "controls": {name: rop.parm(name).eval() for name in controls},
            "axis_label": rop.parm("axissystem").menuLabels()[
                rop.parm("axissystem").eval()
            ],
            "minimum_face_normal_y": min(p.normal()[1] for p in geometry.prims()),
            "geographic_frame": receipt["axis_mapping"],
            "ue_import_verified": False,
        },
    )


def current_terrain_trial(record_path, profile_root, output, reopen=False):
    """Native-only patch of current FINAL for an interior source road interval."""
    import hou

    if hou.applicationVersionString() != "22.0.466":
        raise ValueError("Revalidate current terrain adapter")
    manifest_path = Path("D:/yacs/work/lesson07-consumer-update-20261020/manifest.json")
    if (
        digest(manifest_path)
        != "760425da4a8fa46c4e201a74f0a70ced802f14dc992d1569885167fe73a8978e"
    ):
        raise ValueError("Current FINAL manifest changed")
    manifest = json.loads(manifest_path.read_text())
    tile = next(
        t
        for t in manifest["tiles"]
        if t["file"].endswith("SaCalobra_Unified_0_0.bgeo.sc")
    )
    tile_path = manifest_path.parent / tile["file"]
    if digest(tile_path) != tile["sha256"]:
        raise ValueError("Current FINAL transport changed")
    record = json.loads(record_path.read_text())
    profile = json.loads((profile_root / "profile_receipt.json").read_text())
    road_path = profile_root / "visual_5m.bgeo.sc"
    if profile["record_sha256"] != digest(record_path) or profile["files"][
        road_path.name
    ] != digest(road_path):
        raise ValueError("Current road source identity changed")
    observations = [
        o for o in record["parts"][0]["observations"] if o["station_m"] <= 120
    ]
    if reopen:
        prior = json.loads((output / "current_terrain.json").read_text())
        if prior["producer_sha256"] != digest(Path(__file__)):
            raise ValueError("Current terrain producer changed")
        for name, sha in prior["files"].items():
            if digest(output / name) != sha:
                raise ValueError("Current terrain artifact changed")
        hou.hipFile.load(str(output / "current_terrain.hip"), suppress_save_prompt=True)
        obj = hou.node("/obj/CURRENT_ROAD_TERRAIN")
    else:
        output.mkdir(parents=True, exist_ok=False)
        obj = hou.node("/obj").createNode("geo", "CURRENT_ROAD_TERRAIN")
        src = obj.createNode("file", "CURRENT_FINAL_TILE")
        src.parm("file").set(str(tile_path))
        positions = [
            (o["easting_m"] - 483650, o["height_m"], 4409899.5 - o["northing_m"])
            for o in observations
        ]
        left, right = (
            min(p[0] for p in positions) - 10,
            max(p[0] for p in positions) + 10,
        )
        bottom, top = (
            min(p[2] for p in positions) - 10,
            max(p[2] for p in positions) + 10,
        )
        crop = obj.createNode("heightfield_crop", "SOURCE_CROP")
        crop.setInput(0, src)
        crop.setParms(
            {
                "cropmode": 0,
                "sizex": right - left,
                "sizey": top - bottom,
                "tx": (left + right) / 2,
                "tz": (bottom + top) / 2,
            }
        )
        road_geo = hou.Geometry()
        road_geo.loadFromFile(str(road_path))
        discard = [
            p
            for p in road_geo.prims()
            if any(
                v.point().attribValue("source_part") != 0
                or not 10 <= v.point().attribValue("station_m") <= 110
                for v in p.vertices()
            )
        ]
        road_geo.deletePrims(discard, keep_points=False)
        road_geo.saveToFile(str(output / "road_interval.bgeo.sc"))
        road = obj.createNode("file", "CURRENT_ROAD_INTERVAL")
        road.parm("file").set(str(output / "road_interval.bgeo.sc"))
        spine = hou.Geometry()
        spine.addAttrib(hou.attribType.Point, "up", (0.0, 1.0, 0.0))
        line = spine.createPolygon(is_closed=False)
        for position in positions:
            point = spine.createPoint()
            point.setPosition(position)
            line.addVertex(point)
        spine.saveToFile(str(output / "support_spine.bgeo.sc"))
        backbone = obj.createNode("file", "REAL_SOURCE_OVERLAP")
        backbone.parm("file").set(str(output / "support_spine.bgeo.sc"))
        support = obj.createNode("sweep::2.0", "SUPPORT_7M")
        support.setInput(0, backbone)
        support.setParms({"surfaceshape": 3, "width": 7, "upvectortype": 2})
        project = obj.createNode("heightfield_project", "PROJECT_CURRENT_ROAD")
        project.setInput(0, crop)
        project.setInput(1, support)
        project.setParms(
            {"combine": 0, "hitfarthest": 0, "maxraydist": 1000, "dojitter": 0}
        )
        blank = obj.createNode("heightfield_copylayer", "EMPTY_SUPPORT_MASK")
        blank.setInput(0, crop)
        blank.setParms({"srcname1": "height", "dstname1": "mask", "copysrc1": 0})
        mask = obj.createNode("heightfield_maskbyobject", "SUPPORT_MASK")
        mask.setInput(0, blank)
        mask.setInput(1, support)
        mask.setParms({"maskdir": 0, "maxdist": 5, "blurradius": 0, "dojitter": 0})
        layer = obj.createNode("heightfield_layer", "REVERSIBLE_CANDIDATE")
        layer.setInput(0, crop)
        layer.setInput(1, project)
        layer.setInput(2, mask)
        layer.setParms({"mode": 7, "blend": 1, "layer": "height"})
        for label, source in [
            ("SOURCE_TRIANGLES", crop),
            ("CANDIDATE_TRIANGLES", layer),
        ]:
            node = obj.createNode("convertheightfield", label)
            node.setInput(0, source)
            node.setParms({"surftype": 3, "lod": 1})
        rollback = obj.createNode("switch", "ROLLBACK_SOURCE")
        rollback.setInput(0, crop)
        rollback.setInput(1, layer)
        rollback.parm("input").set(0)
        rollback.setDisplayFlag(True)

    def volume(node, name="height"):
        return next(p for p in node.geometry().prims() if p.attribValue("name") == name)

    crop = volume(obj.node("SOURCE_CROP"))
    source = volume(obj.node("CURRENT_FINAL_TILE"))
    nx, ny, _ = crop.resolution()
    index = source.posToIndex(crop.indexToPos((0, 0, 0)))
    ix, iy = round(index[0]), round(index[1])
    actual = crop.allVoxels()
    expected = tuple(
        source.voxel((ix + i, iy + j, 0)) for j in range(ny) for i in range(nx)
    )
    if tuple(actual) != expected or any(not math.isfinite(v) for v in actual):
        raise ValueError("Current native crop changed source samples")
    if max(volume(obj.node("SOURCE_CROP"), "visibility").allVoxels()) > 0.5:
        raise ValueError("Current crop contains visibility holes")
    candidate = volume(obj.node("REVERSIBLE_CANDIDATE")).allVoxels()
    if any(not math.isfinite(v) for v in candidate):
        raise ValueError("Nonfinite current terrain candidate")
    mask = volume(obj.node("SUPPORT_MASK"), "mask").allVoxels()
    delta = [b - a for a, b in zip(actual, candidate, strict=True)]
    outside = max(
        (abs(d) for d, m in zip(delta, mask, strict=True) if m == 0), default=0
    )
    if (
        outside > 1e-6
        or obj.node("ROLLBACK_SOURCE").parm("input").eval() != 0
        or tuple(volume(obj.node("ROLLBACK_SOURCE")).allVoxels()) != tuple(actual)
    ):
        raise ValueError("Current candidate footprint or rollback failed")
    road = obj.node("CURRENT_ROAD_INTERVAL").geometry()

    def residual(node, points):
        geo = node.geometry()
        values = []
        for x, y, z in points:
            pos, normal, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
            hit = geo.intersect(
                hou.Vector3(x, y + 100, z), hou.Vector3(0, -1, 0), pos, normal, uvw
            )
            if hit < 0 or geo.prim(hit).numVertices() != 3:
                raise ValueError("Current triangle contact miss")
            values.append(y - pos[1])
        return {
            "count": len(values),
            "min_m": min(values),
            "max_m": max(values),
            "rms_m": math.sqrt(sum(v * v for v in values) / len(values)),
        }

    positions = [p.position() for p in road.points()]
    receipt = {
        "status": "CURRENT_FINAL_REVERSIBLE_PATCH_NOT_ADMITTED",
        "producer_sha256": digest(Path(__file__)),
        "manifest_sha256": digest(manifest_path),
        "source_tile_sha256": tile["sha256"],
        "axis_mapping": record["axis_mapping"],
        "road_sha256": digest(road_path),
        "record_sha256": digest(record_path),
        "source_samples_exact": len(actual),
        "source_grid_dimensions": [nx, ny],
        "source_grid_first": list(crop.indexToPos((0, 0, 0))),
        "source_grid_last": list(crop.indexToPos((nx - 1, ny - 1, 0))),
        "before": residual(obj.node("SOURCE_TRIANGLES"), positions),
        "after": residual(obj.node("CANDIDATE_TRIANGLES"), positions),
        "dtm_observation_minus_current_native_triangle": residual(
            obj.node("SOURCE_TRIANGLES"),
            [
                (
                    o["easting_m"] - 483650,
                    o["dtm_height_m"],
                    4409899.5 - o["northing_m"],
                )
                for o in observations
            ],
        ),
        "baseline_comparison_note": "DTM nearest-cell observations versus CURRENT FINAL native interpolated triangles; not a full-grid DTM difference",
        "delta_min_m": min(delta),
        "delta_max_m": max(delta),
        "changed_samples": sum(d != 0 for d in delta),
        "outside_support_max_delta_m": outside,
        "rollback_source_exact": True,
        "road_interval_requested_m": [10, 110],
        "real_support_observations_m": [
            observations[0]["station_m"],
            observations[-1]["station_m"],
        ],
        "support_width_m_assumption": 7,
        "road_width_m_assumption": 5,
        "contact_pass": False,
        "ue_modified": False,
    }
    if not reopen:
        obj.node("REVERSIBLE_CANDIDATE").geometry().saveToFile(
            str(output / "current_patch.bgeo.sc")
        )
        hou.hipFile.save(str(output / "current_terrain.hip"))
        receipt["files"] = {
            name: digest(output / name)
            for name in [
                "current_patch.bgeo.sc",
                "current_terrain.hip",
                "road_interval.bgeo.sc",
                "support_spine.bgeo.sc",
            ]
        }
    write_new(
        output / ("current_terrain_reopen.json" if reopen else "current_terrain.json"),
        receipt,
    )


def slab_trial(terrain_root, output, thickness, reopen=False):
    """Separate visual construction hypothesis; top/physics are never lifted."""
    import hou
    from collections import Counter

    if (
        hou.applicationVersionString() != "22.0.466"
        or not math.isfinite(thickness)
        or thickness <= 0
    ):
        raise ValueError(
            "Pinned runtime and explicit positive candidate thickness required"
        )
    base = json.loads((terrain_root / "current_terrain.json").read_text())
    for name, sha in base["files"].items():
        if digest(terrain_root / name) != sha:
            raise ValueError("Bounded current terrain source changed")
    if reopen:
        prior = json.loads((output / "slab_receipt.json").read_text())
        if (
            prior["producer_sha256"] != digest(Path(__file__))
            or prior["vertical_thickness_m_assumption"] != thickness
        ):
            raise ValueError("Slab producer/thickness changed")
        for name, sha in prior["files"].items():
            if digest(output / name) != sha:
                raise ValueError("Slab artifact changed")
        hou.hipFile.load(str(output / "slab_trial.hip"), suppress_save_prompt=True)
    else:
        output.mkdir(parents=True, exist_ok=False)
        hou.hipFile.load(
            str(terrain_root / "current_terrain.hip"), suppress_save_prompt=True
        )
    obj = hou.node("/obj/CURRENT_ROAD_TERRAIN")
    road = obj.node("CURRENT_ROAD_INTERVAL")
    if not reopen:
        top = obj.createNode("divide", "UNCHANGED_TOP_TRIANGLES")
        top.setInput(0, road)
        top.setParms({"convex": 1, "usemaxsides": 1, "numsides": 3})
        reverse = obj.createNode("reverse", "UNDERSIDE_EXTRUSION_ORIENTATION")
        reverse.setInput(0, top)

        def extrude(name, node, distance):
            result = obj.createNode("polyextrude::2.0", name)
            result.setInput(0, node)
            result.setParms(
                {
                    "splittype": 1,
                    "dist": 0,
                    "xformfront": 1,
                    "xformspace": 1,
                    "translatey": distance,
                    "divs": 1,
                    "outputfront": 1,
                    "outputback": 1,
                    "outputside": 1,
                    "outputfrontgrp": 1,
                    "outputbackgrp": 1,
                    "outputsidegrp": 1,
                }
            )
            return result

        extrude("PAVEMENT_SLAB", reverse, -thickness)
        underside = obj.createNode("xform", "SUPPORT_UNDERSIDE")
        underside.setInput(0, obj.node("SUPPORT_7M"))
        underside.parm("ty").set(-thickness)
        obj.node("PROJECT_CURRENT_ROAD").setInput(1, underside)
        terrain_height = next(
            p
            for p in obj.node("SOURCE_CROP").geometry().prims()
            if p.attribValue("name") == "height"
        )
        column_height = max(
            1.0,
            max(terrain_height.allVoxels())
            - top.geometry().boundingBox().minvec()[1]
            + 1.0,
        )
        above = extrude("ABOVE_TOP_TEST_VOLUME", top, column_height)
        for name, source in [
            ("TERRAIN_ABOVE_TOP_BEFORE", obj.node("SOURCE_TRIANGLES")),
            ("TERRAIN_ABOVE_TOP_AFTER", obj.node("CANDIDATE_TRIANGLES")),
        ]:
            boolean = obj.createNode("boolean::2.0", name)
            boolean.setInput(0, source)
            boolean.setInput(1, above)
            boolean.setParms(
                {
                    "asurface": 1,
                    "bsurface": 0,
                    "booleanop": 1,
                    "detriangulate": 0,
                    "removeinlinepoints": 0,
                }
            )
    slab = obj.node("PAVEMENT_SLAB").geometry()
    if not all(math.isfinite(v) for p in slab.points() for v in p.position()):
        raise ValueError("Nonfinite slab")
    edges = Counter(
        tuple(
            sorted(
                (
                    vertices[i].point().number(),
                    vertices[(i + 1) % len(vertices)].point().number(),
                )
            )
        )
        for primitive in slab.prims()
        for vertices in [primitive.vertices()]
        for i in range(len(vertices))
    )
    if any(count != 2 for count in edges.values()):
        raise ValueError("Slab is not closed manifold")
    upper = slab.findPrimGroup("extrudeBack").prims()
    lower = slab.findPrimGroup("extrudeFront").prims()
    sides = slab.findPrimGroup("extrudeSide").prims()
    if min(p.normal()[1] for p in upper) <= 0 or max(p.normal()[1] for p in lower) >= 0:
        raise ValueError("Slab top/bottom orientation invalid")
    top_positions = {tuple(v.point().position()) for p in upper for v in p.vertices()}
    expected = {tuple(p.position()) for p in road.geometry().points()}
    if top_positions != expected:
        raise ValueError("Slab moved source pavement top")

    def values(name):
        return next(
            p
            for p in obj.node(name).geometry().prims()
            if p.attribValue("name") == "height"
        ).allVoxels()

    source = values("SOURCE_CROP")
    candidate = values("REVERSIBLE_CANDIDATE")
    mask = next(
        p
        for p in obj.node("SUPPORT_MASK").geometry().prims()
        if p.attribValue("name") == "mask"
    ).allVoxels()
    delta = [b - a for a, b in zip(source, candidate, strict=True)]
    outside = max(
        (abs(d) for d, m in zip(delta, mask, strict=True) if m == 0), default=0
    )
    if (
        outside > 1e-6
        or tuple(values("ROLLBACK_SOURCE")) != tuple(source)
        or obj.node("ROLLBACK_SOURCE").parm("input").eval() != 0
    ):
        raise ValueError("Slab patch source rollback/footprint changed")
    terrain = obj.node("CANDIDATE_TRIANGLES").geometry()
    gaps = []
    for x, y, z in expected:
        pos, n, u = hou.Vector3(), hou.Vector3(), hou.Vector3()
        if (
            terrain.intersect(
                hou.Vector3(x, y + 100, z), hou.Vector3(0, -1, 0), pos, n, u
            )
            < 0
        ):
            raise ValueError("Underside contact ray missed")
        gaps.append(y - thickness - pos[1])
    intersections = {}
    for name in ["TERRAIN_ABOVE_TOP_BEFORE", "TERRAIN_ABOVE_TOP_AFTER"]:
        node = obj.node(name)
        geometry = node.geometry()
        if node.errors() or node.warnings():
            raise ValueError(
                "Native Boolean contact diagnostic: "
                + str(node.errors() + node.warnings())
            )
        intersections[name] = {
            "points": len(geometry.points()),
            "primitives": len(geometry.prims()),
        }
    if intersections["TERRAIN_ABOVE_TOP_BEFORE"]["primitives"] == 0:
        raise ValueError("Above-top Boolean positive control found no known intrusion")
    receipt = {
        "status": "VISUAL_FINITE_PAVEMENT_CANDIDATE_NOT_ADMITTED",
        "producer_sha256": digest(Path(__file__)),
        "base_terrain_receipt_sha256": digest(terrain_root / "current_terrain.json"),
        "vertical_thickness_m_assumption": thickness,
        "thickness_authority": "Explicit visual candidate; not measured Ma-2141 thickness or engineering standard",
        "source_top_points_exact": len(expected),
        "slab_points": len(slab.points()),
        "slab_primitives": len(slab.prims()),
        "top_triangles": len(upper),
        "underside_triangles": len(lower),
        "side_faces": len(sides),
        "closed_manifold_edge_incidence_verified": True,
        "underside_minus_terrain_m": {
            "count": len(gaps),
            "min": min(gaps),
            "max": max(gaps),
            "rms": math.sqrt(sum(x * x for x in gaps) / len(gaps)),
        },
        "native_boolean_surface_inside_above_top_volume": intersections,
        "terrain_above_top_native_triangles_empty": intersections[
            "TERRAIN_ABOVE_TOP_AFTER"
        ]["primitives"]
        == 0,
        "source_delta_min_m": min(delta),
        "source_delta_max_m": max(delta),
        "changed_samples": sum(d != 0 for d in delta),
        "outside_support_max_delta_m": outside,
        "rollback_source_exact": True,
        "road_top_lift_m": 0,
        "physics_modified": False,
        "ue_modified": False,
        "underside_contact_admitted": False,
    }
    if not reopen:
        slab.saveToFile(str(output / "pavement_slab.bgeo.sc"))
        obj.node("REVERSIBLE_CANDIDATE").geometry().saveToFile(
            str(output / "underside_terrain.bgeo.sc")
        )
        hou.hipFile.save(str(output / "slab_trial.hip"))
        receipt["files"] = {
            name: digest(output / name)
            for name in [
                "pavement_slab.bgeo.sc",
                "underside_terrain.bgeo.sc",
                "slab_trial.hip",
            ]
        }
    write_new(output / ("slab_reopen.json" if reopen else "slab_receipt.json"), receipt)


def prepare_preview(source, dtm, width, output):
    """A fixed 100 m source part-0 probe; terrain samples are not asphalt survey."""
    import rasterio
    from pyproj import Transformer
    from shapely import wkt
    from shapely.geometry import Point
    from shapely.ops import transform, substring

    if digest(source) != SOURCE_SHA or not math.isfinite(width) or not 0 < width <= 10:
        raise ValueError("Pinned source and explicit visual width (0,10] m required")
    raw = json.loads(source.read_text(encoding="utf-8"))
    project = Transformer.from_crs(4326, 25831, always_xy=True)
    route = transform(project.transform, wkt.loads(raw["geom"])).geoms[0]
    clip = substring(route, 0, 100)
    # Retain original corners as well as 1m samples: no smoothing/rerouting.
    distances = {float(i) for i in range(101)}
    distances.update(min(100.0, max(0.0, clip.project(Point(p)))) for p in clip.coords)
    stations = sorted(distances)
    xy = [list(clip.interpolate(s).coords[0]) for s in stations]
    with rasterio.open(dtm) as dataset:
        if dataset.crs.to_epsg() != 25831 or dataset.res != (0.5, 0.5):
            raise ValueError("Expected retained EPSG:25831 0.5 m DTM")
        samples = list(dataset.sample(xy, masked=True))
        if any(s.mask[0] or not math.isfinite(float(s[0])) for s in samples):
            raise ValueError("DTM source coverage/NoData gap")
        z = [float(s[0]) for s in samples]
    write_new(
        output,
        {
            "status": "SOURCE_ALIGNED_VISUAL_PREVIEW_ONLY",
            "source_sha256": SOURCE_SHA,
            "producer_sha256": digest(Path(__file__)),
            "source_part": 0,
            "source_station_range_m": [0, 100],
            "station_m": stations,
            "xy_epsg25831_m": xy,
            "dtm_sample_z_m": z,
            "dtm_path": str(dtm.resolve()),
            "dtm_size_bytes": dtm.stat().st_size,
            "dtm_sha256": digest(dtm),
            "width_m": width,
            "width_status": "EXPLICIT_VISUAL_ASSUMPTION_NOT_SURVEY",
            "z_status": "NEAREST_SOURCE_DTM_CELL_NOT_ASPHALT_PROFILE",
            "origin_epsg25831_m": xy[0],
            "road_admitted": False,
            "crossing": "Part 0 0-100m excludes closed part4 crossing; no inferred crossing geometry",
        },
    )


def preview_points(record):
    return [
        (
            xy[0] - record["origin_epsg25831_m"][0],
            z,
            xy[1] - record["origin_epsg25831_m"][1],
        )
        for xy, z in zip(
            record["xy_epsg25831_m"], record["dtm_sample_z_m"], strict=True
        )
    ]


def verify_preview(node, record):
    positions = preview_points(record)
    source = node.inputs()[0].geometry()
    if len(source.points()) != len(positions):
        raise ValueError("Preview backbone count mismatch")
    delta = 0.0
    for point, expected in zip(source.points(), positions, strict=True):
        if not all(math.isfinite(v) for v in point.position()):
            raise ValueError("Nonfinite preview backbone")
        delta = max(
            delta,
            *(abs(a - b) for a, b in zip(point.position(), expected, strict=True)),
        )
    surface = node.geometry()
    if (
        delta > 0.001
        or not surface.prims()
        or any(not math.isfinite(v) for p in surface.points() for v in p.position())
    ):
        raise ValueError("Native Sweep output invalid")
    points = surface.points()
    if len(points) % len(positions):
        raise ValueError("Unexpected Sweep cross-section point layout")
    columns = len(points) // len(positions)
    widths, center_errors = [], []
    for i, center in enumerate(positions):
        row = [tuple(p.position()) for p in points[i * columns : (i + 1) * columns]]
        widths.append(math.dist(row[0], row[-1]))
        midpoint = tuple((a + b) / 2 for a, b in zip(row[0], row[-1], strict=True))
        center_errors.append(math.dist(midpoint, center))
    if max(center_errors) > 0.001:
        raise ValueError("Sweep cross-section centre does not preserve source backbone")
    return {
        "backbone_points": len(positions),
        "maximum_backbone_storage_delta_m": delta,
        "surface_points": len(surface.points()),
        "surface_primitives": len(surface.prims()),
        "cross_section_columns": columns,
        "width_3d_min_m": min(widths),
        "width_3d_max_m": max(widths),
        "cross_section_centre_max_delta_m": max(center_errors),
        "bounds_houdini_m": [
            list(surface.boundingBox().minvec()),
            list(surface.boundingBox().maxvec()),
        ],
        "contact_verified": False,
        "road_admitted": False,
    }


def build_preview(record_path, output, reopen=False):
    import hou

    if hou.applicationVersionString() != "22.0.466":
        raise ValueError("Revalidate Sweep version")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if (
        record["status"] != "SOURCE_ALIGNED_VISUAL_PREVIEW_ONLY"
        or record["source_sha256"] != SOURCE_SHA
    ):
        raise ValueError("Expected source-aligned explicit candidate")
    if digest(Path(record["dtm_path"])) != record["dtm_sha256"]:
        raise ValueError("Retained source DTM bytes changed")
    if reopen:
        receipt = json.loads((output / "preview_build_receipt.json").read_text())
        if receipt["record_sha256"] != digest(record_path):
            raise ValueError("Preview source record changed")
        for name, expected in receipt["files"].items():
            if digest(output / name) != expected:
                raise ValueError("Preview artifact changed")
        hou.hipFile.load(
            str(output / "source_100m_preview.hip"), suppress_save_prompt=True
        )
        sweep = hou.node("/obj/MA2141_NEW_SOURCE_PREVIEW/SOURCE_SWEEP")
    else:
        output.mkdir(parents=True, exist_ok=False)
        geometry = hou.Geometry()
        line = geometry.createPolygon(is_closed=False)
        for xyz in preview_points(record):
            point = geometry.createPoint()
            point.setPosition(xyz)
            line.addVertex(point)
        geometry.saveToFile(str(output / "backbone.bgeo.sc"))
        obj = hou.node("/obj").createNode("geo", "MA2141_NEW_SOURCE_PREVIEW")
        for child in obj.children():
            child.destroy()
        source = obj.createNode("file", "SOURCE_DTM_BACKBONE")
        source.parm("file").set(str(output / "backbone.bgeo.sc"))
        sweep = obj.createNode("sweep::2.0", "SOURCE_SWEEP")
        sweep.setInput(0, source)
        shape = [
            p for p in sweep.parms() if p.parmTemplate().label() == "Surface Shape"
        ]
        if len(shape) != 1:
            raise ValueError("Sweep Surface Shape binding missing")
        labels = shape[0].menuLabels()
        if "Ribbon" not in labels:
            raise ValueError("Sweep Ribbon unavailable")
        shape[0].set(labels.index("Ribbon"))
        widths = [p for p in sweep.parms() if p.parmTemplate().label() == "Width"]
        if len(widths) != 1:
            raise ValueError("Sweep width binding ambiguous")
        widths[0].set(record["width_m"])
        sweep.setDisplayFlag(True)
        sweep.setRenderFlag(True)
    checks = verify_preview(sweep, record)
    native_controls = {
        p.name(): {"value": p.eval(), "label": p.parmTemplate().label()}
        for p in sweep.parms()
        if p.parmTemplate().label() in ("Surface Shape", "Width")
    }
    receipt = {
        "status": "SOURCE_VISUAL_PREVIEW_NOT_ADMITTED",
        "checks": checks,
        "record_sha256": digest(record_path),
        "producer_sha256": digest(Path(__file__)),
        "houdini": hou.applicationVersionString(),
        "native_node": sweep.type().name(),
        "native_controls": native_controls,
        "width_m": record["width_m"],
        "material_applied": False,
        "origin_epsg25831_m": record["origin_epsg25831_m"],
        "axis_mapping": "X=easting-origin_e; Y=DTM elevation; Z=northing-origin_n",
        "L07_consumer_transform_verified": False,
        "terrain_changed": False,
        "physics_changed": False,
    }
    if not reopen:
        with (output / "surface_points.csv").open("x", encoding="utf-8") as stream:
            stream.write("easting_m,northing_m,surface_z_m\n")
            for point in sweep.geometry().points():
                x, y, z = point.position()
                stream.write(
                    f"{x + record['origin_epsg25831_m'][0]:.9f},{z + record['origin_epsg25831_m'][1]:.9f},{y:.9f}\n"
                )
        sweep.geometry().saveToFile(str(output / "source_100m_preview.bgeo.sc"))
        sweep.inputs()[0].parm("file").set("$HIP/backbone.bgeo.sc")
        hou.hipFile.save(str(output / "source_100m_preview.hip"))
        receipt["files"] = {
            name: digest(output / name)
            for name in [
                "backbone.bgeo.sc",
                "source_100m_preview.bgeo.sc",
                "source_100m_preview.hip",
            ]
        }
    write_new(
        output
        / (
            "preview_fresh_reopen_receipt.json"
            if reopen
            else "preview_build_receipt.json"
        ),
        receipt,
    )


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def prepare_terrain(record_path, output):
    import rasterio
    from rasterio.windows import from_bounds

    record = json.loads(record_path.read_text())
    dtm = Path(record["dtm_path"])
    if digest(dtm) != record["dtm_sha256"]:
        raise ValueError("DTM changed before bounded terrain extraction")
    xy = record["xy_epsg25831_m"]
    output.mkdir(parents=True, exist_ok=False)
    with rasterio.open(dtm) as dataset:
        window = (
            from_bounds(
                min(p[0] for p in xy) - 10,
                min(p[1] for p in xy) - 10,
                max(p[0] for p in xy) + 10,
                max(p[1] for p in xy) + 10,
                dataset.transform,
            )
            .round_offsets()
            .round_lengths()
        )
        values = dataset.read(1, window=window, masked=True)
        if values.mask.any():
            raise ValueError("Bounded source terrain contains NoData")
        profile = dataset.profile.copy()
        profile.update(
            width=int(window.width),
            height=int(window.height),
            transform=dataset.window_transform(window),
            count=1,
        )
        with rasterio.open(output / "source_window.tif", "w", **profile) as target:
            target.write(values.filled(), 1)
        bounds = list(dataset.window_bounds(window))
        # A south-up copy changes storage order/affine only, retaining every
        # georeferenced source sample. Avoid reflected native volume axes.
        profile["transform"] = rasterio.Affine(0.5, 0, bounds[0], 0, 0.5, bounds[1])
        with rasterio.open(output / "native_south_up.tif", "w", **profile) as target:
            target.write(values.filled()[::-1, :], 1)
    write_new(
        output / "terrain_source.json",
        {
            "status": "BOUNDED_SOURCE_TERRAIN_UNCHANGED",
            "preview_record_sha256": digest(record_path),
            "dtm_sha256": record["dtm_sha256"],
            "window_sha256": digest(output / "source_window.tif"),
            "native_south_up_sha256": digest(output / "native_south_up.tif"),
            "bounds_epsg25831_m": bounds,
            "origin_epsg25831_m": record["origin_epsg25831_m"],
            "grid_spacing_m": 0.5,
            "rows": int(window.height),
            "columns": int(window.width),
            "source_heights_north_to_south": values.tolist(),
        },
    )


def terrain_trial(terrain_root, preview_root, output, reopen=False, support_margin=0):
    import hou

    if hou.applicationVersionString() != "22.0.466":
        raise ValueError("Revalidate native terrain nodes")
    metadata = json.loads((terrain_root / "terrain_source.json").read_text())
    if digest(terrain_root / "source_window.tif") != metadata["window_sha256"]:
        raise ValueError("Source terrain window changed")
    if (
        digest(terrain_root / "native_south_up.tif")
        != metadata["native_south_up_sha256"]
    ):
        raise ValueError("Native import storage-order adapter changed")
    preview_receipt = json.loads(
        (preview_root / "preview_build_receipt.json").read_text()
    )
    road_path = preview_root / "source_100m_preview.bgeo.sc"
    if digest(road_path) != preview_receipt["files"][road_path.name]:
        raise ValueError("Preview road changed")
    if metadata["preview_record_sha256"] != preview_receipt["record_sha256"]:
        raise ValueError("Terrain/road record identity mismatch")
    if reopen:
        prior = json.loads((output / "terrain_trial.json").read_text())
        if prior.get("support_margin_m", 0) != support_margin:
            raise ValueError("Reopen support margin differs from saved candidate")
        for name, expected in prior["files"].items():
            if digest(output / name) != expected:
                raise ValueError("Saved terrain candidate bytes changed")
        hou.hipFile.load(str(output / "terrain_trial.hip"), suppress_save_prompt=True)
        obj = hou.node("/obj/MA2141_TERRAIN_TRIAL")
    else:
        output.mkdir(parents=True, exist_ok=False)
        obj = hou.node("/obj").createNode("geo", "MA2141_TERRAIN_TRIAL")
        for child in obj.children():
            child.destroy()
        source = obj.createNode("heightfield_file", "SOURCE_WINDOW")
        left, bottom, right, top = metadata["bounds_epsg25831_m"]
        east, north = metadata["origin_epsg25831_m"]
        source.setParms(
            {
                "filename": str(terrain_root / "native_south_up.tif"),
                "sizemethod": 1,
                "gridspacing": 0.5,
                "heightscale": 1,
                "doclampmin": 0,
                "doclampmax": 0,
                "rotate": 90,
                "tx": (left + right) / 2 - east,
                "ty": (bottom + top) / 2 - north,
            }
        )
        road = obj.createNode("file", "NEW_SOURCE_ROAD")
        road.parm("file").set(str(road_path))
        convert = obj.createNode("convertheightfield", "SOURCE_TRIANGLES")
        convert.setInput(0, source)
        convert.setParms({"surftype": 3, "lod": 1})
    source = obj.node("SOURCE_WINDOW")
    road = obj.node("NEW_SOURCE_ROAD")
    convert = obj.node("SOURCE_TRIANGLES")
    # Validate every imported sample against georeferenced raster before any
    # contact or terrain operation. This catches flips/half-cell offsets.
    left, bottom, right, top = metadata["bounds_epsg25831_m"]
    east, north = metadata["origin_epsg25831_m"]
    import_error = 0.0
    seen = set()
    for point in convert.geometry().points():
        x, y, z = point.position()
        col = round((x + east - left) / 0.5 - 0.5)
        row = round((top - (z + north)) / 0.5 - 0.5)
        if not (0 <= row < metadata["rows"] and 0 <= col < metadata["columns"]):
            raise ValueError("Native HeightField registration outside source window")
        expected = (
            left + (col + 0.5) * 0.5 - east,
            metadata["source_heights_north_to_south"][row][col],
            top - (row + 0.5) * 0.5 - north,
        )
        import_error = max(
            import_error,
            *(abs(a - b) for a, b in zip((x, y, z), expected, strict=True)),
        )
        seen.add((row, col))
    if import_error > 0.001 or len(seen) != metadata["rows"] * metadata["columns"]:
        raise ValueError(
            f"Native HeightField raster registration failed: {import_error}m {len(seen)} samples"
        )

    def ray(name, terrain):
        geometry = terrain.geometry().freeze()
        residual, hit_primitives = [], []
        for point in road.geometry().points():
            x, y, z = point.position()
            position, normal, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
            primitive = geometry.intersect(
                hou.Vector3(x, y + 10, z), hou.Vector3(0, -1, 0), position, normal, uvw
            )
            if primitive < 0:
                raise ValueError(
                    f"Native Geometry.intersect miss in {name}: point {point.number()}"
                )
            if geometry.prim(primitive).numVertices() != 3:
                raise ValueError(
                    "Contact hit must be an actual native terrain triangle"
                )
            residual.append(y - position[1])
            hit_primitives.append(primitive)
        return {
            "hits": len(residual),
            "misses": 0,
            "min_m": min(residual),
            "max_m": max(residual),
            "hit_object": terrain.path(),
            "unique_hit_triangles": len(set(hit_primitives)),
            "method": "hou.Geometry.intersect on native Convert HeightField triangles",
            "rms_m": math.sqrt(sum(v * v for v in residual) / len(residual)),
        }

    before = ray("CONTACT_BEFORE", convert)
    if not reopen:
        if before["min_m"] >= -0.001 and before["max_m"] <= 0.001:
            raise ValueError("No material contact defect: earthworks trial unnecessary")
        support = road
        if support_margin:
            backbone_path = preview_root / "backbone.bgeo.sc"
            if digest(backbone_path) != preview_receipt["files"][backbone_path.name]:
                raise ValueError("Preview backbone changed")
            backbone = obj.createNode("file", "RETAINED_BACKBONE")
            backbone.parm("file").set(str(backbone_path))
            support = obj.createNode("sweep::2.0", "NUMERICAL_GRID_SUPPORT")
            support.setInput(0, backbone)
            support.setParms(
                {
                    "surfaceshape": 3,
                    "width": preview_receipt["width_m"] + 2 * support_margin,
                }
            )
        project = obj.createNode("heightfield_project", "ROAD_EARTHWORKS_CANDIDATE")
        project.setInput(0, source)
        project.setInput(1, support)
        project.setParms(
            {"combine": 0, "hitfarthest": 0, "maxraydist": 1000, "dojitter": 0}
        )
        mask = obj.createNode("heightfield_maskbyobject", "ROAD_FOOTPRINT")
        mask.setInput(0, source)
        mask.setInput(1, road)
        mask.setParms({"maskdir": 0, "maxdist": 5, "blurradius": 0, "dojitter": 0})
        support_mask = obj.createNode("heightfield_maskbyobject", "SUPPORT_FOOTPRINT")
        support_mask.setInput(0, source)
        support_mask.setInput(1, support)
        support_mask.setParms(
            {"maskdir": 0, "maxdist": 5, "blurradius": 0, "dojitter": 0}
        )
        layer = obj.createNode("heightfield_layer", "MASKED_REVERSIBLE_EARTHWORKS")
        layer.setInput(0, source)
        layer.setInput(1, project)
        layer.setInput(2, support_mask)
        layer.setParms({"mode": 7, "blend": 1, "layer": "height"})
        after_convert = obj.createNode("convertheightfield", "CANDIDATE_TRIANGLES")
        after_convert.setInput(0, layer)
        after_convert.setParms({"surftype": 3, "lod": 1})
        switch = obj.createNode("switch", "ROLLBACK_SOURCE_DEFAULT")
        switch.setInput(0, source)
        switch.setInput(1, layer)
        switch.parm("input").set(0)
        switch.setDisplayFlag(True)
    after = ray("CONTACT_AFTER", obj.node("CANDIDATE_TRIANGLES"))

    def height_values(node, name):
        return next(
            p for p in node.geometry().prims() if p.attribValue("name") == name
        ).allVoxels()

    original = height_values(source, "height")
    rollback = obj.node("ROLLBACK_SOURCE_DEFAULT")
    if (
        rollback.parm("input").eval() != 0
        or height_values(rollback, "height") != original
    ):
        raise ValueError("Rollback switch does not reproduce the source heights")
    candidate = height_values(obj.node("MASKED_REVERSIBLE_EARTHWORKS"), "height")
    mask_values = height_values(obj.node("ROAD_FOOTPRINT"), "mask")
    support_values = height_values(obj.node("SUPPORT_FOOTPRINT"), "mask")
    delta = [b - a for a, b in zip(original, candidate, strict=True)]
    outside = max(
        (abs(d) for d, m in zip(delta, support_values, strict=True) if m == 0),
        default=0,
    )
    if outside > 0.000001:
        raise ValueError("Terrain changed outside the native projected footprint")
    receipt = {
        "status": "REVERSIBLE_TERRAIN_TRIAL_NOT_ADMITTED",
        "producer_sha256": digest(Path(__file__)),
        "source_window_sha256": metadata["window_sha256"],
        "native_south_up_sha256": metadata["native_south_up_sha256"],
        "houdini": hou.applicationVersionString(),
        "bounds_epsg25831_m": metadata["bounds_epsg25831_m"],
        "origin_epsg25831_m": metadata["origin_epsg25831_m"],
        "axis_mapping": "X=easting-origin_e; Y=DTM elevation; Z=northing-origin_n",
        "projection_max_ray_distance_m": 1000,
        "native_import_max_delta_m": import_error,
        "native_import_samples": len(seen),
        "before": before,
        "after": after,
        "source_delta_min_m": min(delta),
        "source_delta_max_m": max(delta),
        "changed_samples": sum(d != 0 for d in delta),
        "changed_samples_outside_pavement_footprint": sum(
            d != 0 and m == 0 for d, m in zip(delta, mask_values, strict=True)
        ),
        "support_margin_m": support_margin,
        "support_status": "NUMERICAL_GRID_SUPPORT_NOT_MEASURED_SHOULDER",
        "outside_footprint_max_delta_m": outside,
        "rollback_switch": rollback.parm("input").eval(),
        "rollback_source_heights_exact": True,
        "terrain_source_modified": False,
        "road_modified": False,
        "contact_pass": False,
        "L07_consumer_transform_verified": False,
    }
    if not reopen:
        obj.node("MASKED_REVERSIBLE_EARTHWORKS").geometry().saveToFile(
            str(output / "earthworks_candidate.bgeo.sc")
        )
        hou.hipFile.save(str(output / "terrain_trial.hip"))
        receipt["files"] = {
            name: digest(output / name)
            for name in ["earthworks_candidate.bgeo.sc", "terrain_trial.hip"]
        }
    write_new(
        output / ("terrain_fresh_reopen.json" if reopen else "terrain_trial.json"),
        receipt,
    )


def inspect(source, output):
    from pyproj import Transformer
    from shapely import wkt
    from shapely.ops import transform

    if digest(source) != SOURCE_SHA:
        raise ValueError("Pinned CartoCiudad source hash mismatch")
    raw = json.loads(source.read_text(encoding="utf-8"))
    geographic = wkt.loads(raw["geom"])
    if geographic.geom_type != "MultiLineString":
        raise ValueError("Expected original multipart line geometry")
    projection = Transformer.from_crs(4326, 25831, always_xy=True)
    metric = transform(projection.transform, geographic)
    parts = [list(map(list, line.coords)) for line in metric.geoms]
    if len(parts) != 6 or sum(map(len, parts)) != 522:
        raise ValueError("Pinned full-route coverage mismatch")
    if not all(math.isfinite(v) for part in parts for point in part for v in point):
        raise ValueError("Nonfinite projected source")
    record = {
        "schema_version": 1,
        "producer_sha256": digest(Path(__file__)),
        "status": "PLANAR_SOURCE_DIAGNOSTIC_ONLY",
        "source_sha256": SOURCE_SHA,
        "source_path": str(source.resolve()),
        "source_crs": "EPSG:4326",
        "metric_crs": "EPSG:25831",
        "axis_mapping": "Houdini X=easting-origin_e; Y=0 diagnostic plane; Z=northing-origin_n",
        "origin_epsg25831_m": list(metric.bounds[:2]),
        "length_m": metric.length,
        "parts_epsg25831_m": parts,
        "closed_parts": [i for i, p in enumerate(parts) if p[0] == p[-1]],
        "road_admitted": False,
        "road_mesh_generated": False,
        "terrain_changed": False,
        "blockers": BLOCKERS,
    }
    write_new(output, record)
    return record


def read_source_record(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    # Reproduce the projection in CPython during inspect; hython checks the
    # immutable record hash passed by the caller, not a claimed source hash.
    if record.get("status") != "PLANAR_SOURCE_DIAGNOSTIC_ONLY":
        raise ValueError("Not a planar source diagnostic")
    parts = record["parts_epsg25831_m"]
    if (
        record["source_sha256"] != SOURCE_SHA
        or len(parts) != 6
        or sum(map(len, parts)) != 522
    ):
        raise ValueError("Source identity/coverage mismatch")
    if digest(Path(record["source_path"])) != SOURCE_SHA:
        raise ValueError("Retained source bytes changed")
    for part in parts:
        for point in part:
            if len(point) != 2 or not all(math.isfinite(v) for v in point):
                raise ValueError("Invalid metric source point")
    origin = record["origin_epsg25831_m"]
    if len(origin) != 2 or not all(math.isfinite(v) for v in origin):
        raise ValueError("Invalid diagnostic origin")
    return record


def verify_geometry(geometry, record):
    import hou

    parts = record["parts_epsg25831_m"]
    origin = record["origin_epsg25831_m"]
    if len(geometry.prims()) != 6 or len(geometry.points()) != 522:
        raise ValueError("Houdini source coverage changed")
    maximum = 0.0
    for part_index, (primitive, part) in enumerate(
        zip(geometry.prims(), parts, strict=True)
    ):
        if primitive.type() != hou.primType.Polygon or primitive.isClosed():
            raise ValueError(
                "Expected open source polyline with retained explicit duplicate endpoint"
            )
        if primitive.attribValue("source_part") != part_index:
            raise ValueError("Source part identity changed")
        if len(primitive.vertices()) != len(part):
            raise ValueError("Source vertex count changed")
        for index, (vertex, xy) in enumerate(
            zip(primitive.vertices(), part, strict=True)
        ):
            point = vertex.point()
            if not all(math.isfinite(v) for v in point.position()):
                raise ValueError("Nonfinite native source point")
            if point.attribValue("source_vertex") != index:
                raise ValueError("Source vertex order changed")
            expected = (xy[0] - origin[0], 0.0, xy[1] - origin[1])
            maximum = max(
                maximum,
                *(abs(a - b) for a, b in zip(point.position(), expected, strict=True)),
            )
    # Native P is float32 by default. Record loss rather than call it exact XY.
    if maximum > 0.001:
        raise ValueError("Diagnostic geometry exceeded 1 mm float storage check")
    return {"parts": 6, "vertices": 522, "maximum_storage_delta_m": maximum}


def build(record_path, output):
    import hou

    if hou.applicationVersionString() != "22.0.466":
        raise ValueError("Revalidate HOM/node binding for this Houdini version")
    record = read_source_record(record_path)
    output.mkdir(parents=True, exist_ok=False)
    geometry = hou.Geometry()
    geometry.addAttrib(hou.attribType.Prim, "source_part", 0)
    geometry.addAttrib(hou.attribType.Point, "source_vertex", 0)
    geometry.addAttrib(hou.attribType.Global, "status", "PLANAR_SOURCE_DIAGNOSTIC_ONLY")
    geometry.addAttrib(hou.attribType.Global, "source_sha256", SOURCE_SHA)
    origin = record["origin_epsg25831_m"]
    for part_index, part in enumerate(record["parts_epsg25831_m"]):
        line = geometry.createPolygon(is_closed=False)
        line.setAttribValue("source_part", part_index)
        for index, xy in enumerate(part):
            point = geometry.createPoint()
            point.setPosition((xy[0] - origin[0], 0.0, xy[1] - origin[1]))
            point.setAttribValue("source_vertex", index)
            line.addVertex(point)
    checks = verify_geometry(geometry, record)
    bgeo = output / "source_diagnostic.bgeo.sc"
    geometry.saveToFile(str(bgeo))
    obj = hou.node("/obj").createNode("geo", "MA2141_SOURCE_DIAGNOSTIC")
    for child in obj.children():
        child.destroy()
    file_node = obj.createNode("file", "RETAINED_SOURCE_POLYLINES")
    file_node.parm("file").set("$HIP/source_diagnostic.bgeo.sc")
    file_node.setComment(
        "PLANAR DIAGNOSTIC: Y=0 is not elevation. No road or earthworks admission."
    )
    file_node.setDisplayFlag(True)
    hou.hipFile.save(str(output / "source_diagnostic.hip"))
    write_new(
        output / "build_receipt.json",
        {
            "status": "DIAGNOSTIC_BUILT_NOT_ROAD",
            "houdini": hou.applicationVersionString(),
            "producer_sha256": digest(Path(__file__)),
            "record_sha256": digest(record_path),
            "bgeo_sha256": digest(bgeo),
            "hip_sha256": digest(output / "source_diagnostic.hip"),
            "checks": checks,
            "blockers": BLOCKERS,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=[
            "inspect",
            "build",
            "verify",
            "mesh",
            "prepare-preview",
            "preview",
            "preview-verify",
            "prepare-terrain",
            "terrain",
            "terrain-verify",
            "prepare-profile",
            "profile",
            "profile-verify",
            "export-profile",
            "current-terrain",
            "current-terrain-verify",
            "slab",
            "slab-verify",
        ],
    )
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--record", type=Path)
    parser.add_argument("--record-sha256")
    parser.add_argument("--dtm", type=Path)
    parser.add_argument("--laz", type=Path)
    parser.add_argument("--width-m", type=float)
    parser.add_argument("--terrain-root", type=Path)
    parser.add_argument("--thickness-m", type=float)
    parser.add_argument("--preview-root", type=Path)
    parser.add_argument("--support-margin-m", type=float, choices=[0, 1], default=0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode in ("slab", "slab-verify"):
        if args.terrain_root is None or args.thickness_m is None:
            parser.error("Slab requires --terrain-root and explicit --thickness-m")
        slab_trial(
            args.terrain_root.resolve(),
            args.output.resolve(),
            args.thickness_m,
            args.mode == "slab-verify",
        )
        return
    if args.mode == "export-profile":
        if args.preview_root is None:
            parser.error("Export requires --preview-root with verified profile")
        export_profile_fbx(args.preview_root.resolve(), args.output.resolve())
        return
    if args.mode == "prepare-profile":
        if args.dtm is None or args.laz is None:
            parser.error("Source profile requires --dtm and audited --laz")
        prepare_profile(args.source, args.dtm, args.laz, args.output)
        return
    if args.mode in ("terrain", "terrain-verify"):
        if args.terrain_root is None or args.preview_root is None:
            parser.error("Terrain trial requires --terrain-root and --preview-root")
        terrain_trial(
            args.terrain_root.resolve(),
            args.preview_root.resolve(),
            args.output.resolve(),
            args.mode == "terrain-verify",
            args.support_margin_m,
        )
        return
    if args.mode == "prepare-preview":
        if args.dtm is None or args.width_m is None:
            parser.error("Preview requires --dtm and explicit --width-m")
        prepare_preview(args.source, args.dtm, args.width_m, args.output)
        print(json.dumps({"record": str(args.output), "sha256": digest(args.output)}))
        return
    if args.mode == "mesh":
        parser.error("Final generation blocked: " + "; ".join(BLOCKERS))
    if args.mode == "inspect":
        inspect(args.source, args.output)
        print(json.dumps({"record": str(args.output), "sha256": digest(args.output)}))
        return
    if (
        not args.record
        or not args.record_sha256
        or digest(args.record) != args.record_sha256
    ):
        parser.error(
            "build/verify require the inspected record and its exact --record-sha256"
        )
    if args.mode in ("preview", "preview-verify"):
        build_preview(args.record, args.output.resolve(), args.mode == "preview-verify")
        return
    if args.mode in ("profile", "profile-verify"):
        profile_geometry(
            args.record, args.output.resolve(), args.mode == "profile-verify"
        )
        return
    if args.mode in ("current-terrain", "current-terrain-verify"):
        if args.preview_root is None:
            parser.error("Current terrain requires --preview-root")
        current_terrain_trial(
            args.record,
            args.preview_root.resolve(),
            args.output.resolve(),
            args.mode == "current-terrain-verify",
        )
        return
    if args.mode == "prepare-terrain":
        prepare_terrain(args.record, args.output.resolve())
        return
    if args.mode == "build":
        build(args.record, args.output.resolve())
    else:
        import hou

        if hou.applicationVersionString() != "22.0.466":
            raise ValueError("Revalidate HOM/node binding for this Houdini version")
        record = read_source_record(args.record)
        receipt = json.loads(
            (args.output / "build_receipt.json").read_text(encoding="utf-8")
        )
        for filename, key in [
            ("source_diagnostic.hip", "hip_sha256"),
            ("source_diagnostic.bgeo.sc", "bgeo_sha256"),
        ]:
            if digest(args.output / filename) != receipt[key]:
                raise ValueError("Saved diagnostic artifact hash mismatch")
        if receipt["record_sha256"] != args.record_sha256:
            raise ValueError("Build record identity mismatch")
        hou.hipFile.load(
            str((args.output / "source_diagnostic.hip").resolve()),
            suppress_save_prompt=True,
        )
        node = hou.node("/obj/MA2141_SOURCE_DIAGNOSTIC/RETAINED_SOURCE_POLYLINES")
        checks = verify_geometry(node.geometry(), record)
        write_new(
            args.output / "fresh_reopen_receipt.json",
            {
                "status": "DIAGNOSTIC_REOPENED_NOT_ROAD",
                "checks": checks,
                "producer_sha256": digest(Path(__file__)),
                "record_sha256": args.record_sha256,
                "houdini": hou.applicationVersionString(),
                "road_admitted": False,
                "road_mesh_generated": False,
                "blockers": BLOCKERS,
            },
        )


if __name__ == "__main__":
    main()
