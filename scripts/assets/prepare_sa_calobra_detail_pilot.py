#!/usr/bin/env python3
"""Project manually proposed image ROIs onto immutable Component 230 candidate faces.

No unseen-to-D inference. Component-only nearest hits are not world occlusion proof.
Rows are [vertex_id, source XYZ, candidate XYZ, movable]; triangle IDs are source
vertex IDs. Output triangle indexes are ordered-row indexes scoped by input SHA256.
Only standard library and numpy are required. No engine or generation is executed.
"""

import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path
import numpy as np

BANDS = ("A", "B", "C")
TAGS = (
    "GEO_FIX",
    "SILHOUETTE_CRITICAL",
    "HERO_DETAIL",
    "BACKGROUND_LOW_PRIORITY",
    "MATERIAL_TEST_CANDIDATE",
)
NEAR_CM = 0.01


def integer(value, label):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or int(value) != value
    ):
        raise ValueError(f"{label} must be a finite integer")
    return int(value)


def validate_mesh(mesh):
    rows = mesh.get("vertices_cm", mesh.get("vertices"))
    faces = mesh.get("triangles")
    if (
        not isinstance(rows, list)
        or not rows
        or not isinstance(faces, list)
        or not faces
    ):
        raise ValueError("mesh requires nonempty vertices_cm and triangles")
    ids, source, candidate, movable = [], [], [], []
    for row in rows:
        if not isinstance(row, list) or len(row) != 8:
            raise ValueError("vertex row must contain exactly eight fields")
        ids.append(integer(row[0], "vertex ID"))
        if not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
            for v in row[1:7]
        ):
            raise ValueError("vertex positions must be finite numeric XYZ")
        if row[7] not in (0, 1, False, True):
            raise ValueError("movable must be boolean or 0/1")
        source.append(row[1:4])
        candidate.append(row[4:7])
        movable.append(bool(row[7]))
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate vertex ID")
    lookup = {v: i for i, v in enumerate(ids)}
    mapped = []
    for face in faces:
        if not isinstance(face, list) or len(face) != 3:
            raise ValueError("each triangle must contain three source vertex IDs")
        keys = [integer(v, "triangle vertex ID") for v in face]
        if len(set(keys)) != 3 or any(v not in lookup for v in keys):
            raise ValueError("invalid triangle source vertex IDs")
        mapped.append([lookup[v] for v in keys])
    source, candidate = (
        np.asarray(source, dtype=float),
        np.asarray(candidate, dtype=float),
    )
    movable = np.asarray(movable, dtype=bool)
    if np.any(np.linalg.norm(candidate - source, axis=1) > 50.000001):
        raise ValueError("candidate movement exceeds 50 cm source contract")
    if not np.array_equal(source[~movable], candidate[~movable]):
        raise ValueError("locked source vertex moved")
    return (
        np.asarray(ids, dtype=np.int64),
        source,
        candidate,
        movable,
        np.asarray(mapped, dtype=np.int64),
    )


def camera_basis(camera, target):
    camera, target = np.asarray(camera, float), np.asarray(target, float)
    if (
        camera.shape != (3,)
        or target.shape != (3,)
        or not np.isfinite(camera).all()
        or not np.isfinite(target).all()
    ):
        raise ValueError("camera and target require finite XYZ")
    forward = target - camera
    length = np.linalg.norm(forward)
    if length <= 1e-10:
        raise ValueError("camera target must differ from camera location")
    forward /= length
    right = np.cross(np.array([0.0, 0.0, 1.0]), forward)
    length = np.linalg.norm(right)
    if length <= 1e-10:
        raise ValueError("roll-zero camera cannot point vertically")
    right /= length
    up = np.cross(forward, right)
    return forward, right, up


def projection_parameters(fov, width, height):
    width, height = integer(width, "width"), integer(height, "height")
    if width <= 0 or height <= 0 or not math.isfinite(fov) or not 0 < fov < 180:
        raise ValueError("invalid projection dimensions/FOV")
    return width / (2 * math.tan(math.radians(fov) / 2))


def project_vertices(vertices, camera, target, fov, width, height):
    scale = projection_parameters(fov, width, height)
    forward, right, up = camera_basis(camera, target)
    relative = np.asarray(vertices, float) - np.asarray(camera, float)
    depth = relative @ forward
    with np.errstate(divide="ignore", invalid="ignore"):
        xy = np.column_stack(
            (
                width / 2 + scale * (relative @ right) / depth,
                height / 2 - scale * (relative @ up) / depth,
            )
        )
    return xy, depth


def clip_near(points):
    result = []
    for current, previous in zip(points, np.roll(points, 1, axis=0)):
        cin, pin = current[2] >= NEAR_CM, previous[2] >= NEAR_CM
        if cin != pin:
            t = (NEAR_CM - previous[2]) / (current[2] - previous[2])
            result.append(previous + t * (current - previous))
        if cin:
            result.append(current)
    return np.asarray(result, float)


def rasterize(vertices, triangles, camera, target, fov, width, height):
    scale = projection_parameters(fov, width, height)
    forward, right, up = camera_basis(camera, target)
    relative = np.asarray(vertices, float) - np.asarray(camera, float)
    transformed = np.column_stack((relative @ right, relative @ up, relative @ forward))
    owners = np.full((height, width), -1, np.int64)
    depth_buffer = np.full((height, width), np.inf)
    for face_id, indexes in enumerate(triangles):
        points = transformed[indexes]
        if np.max(points[:, 2]) < NEAR_CM:
            continue
        clipped = clip_near(points) if np.min(points[:, 2]) < NEAR_CM else points
        for j in range(1, len(clipped) - 1):
            tri = clipped[[0, j, j + 1]]
            xy = np.column_stack(
                (
                    width / 2 + scale * tri[:, 0] / tri[:, 2],
                    height / 2 - scale * tri[:, 1] / tri[:, 2],
                )
            )
            xmin = max(0, int(math.ceil(float(xy[:, 0].min()) - 0.5)))
            xmax = min(width - 1, int(math.floor(float(xy[:, 0].max()) - 0.5)))
            ymin = max(0, int(math.ceil(float(xy[:, 1].min()) - 0.5)))
            ymax = min(height - 1, int(math.floor(float(xy[:, 1].max()) - 0.5)))
            if xmin > xmax or ymin > ymax:
                continue
            a, b, c = xy
            denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(denominator) < 1e-12:
                continue
            ys, xs = np.mgrid[ymin : ymax + 1, xmin : xmax + 1]
            xs, ys = xs + 0.5, ys + 0.5
            w0 = (
                (b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])
            ) / denominator
            w1 = (
                (c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])
            ) / denominator
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
            reciprocal = w0 / tri[0, 2] + w1 / tri[1, 2] + w2 / tri[2, 2]
            with np.errstate(divide="ignore", invalid="ignore"):
                depths = 1 / reciprocal
            old = depth_buffer[ymin : ymax + 1, xmin : xmax + 1]
            update = inside & (reciprocal > 0) & (depths < old)
            old[update] = depths[update]
            owners[ymin : ymax + 1, xmin : xmax + 1][update] = face_id
    return owners, depth_buffer


def polygon_mask(polygon, width, height):
    polygon = np.asarray(polygon, float)
    if (
        polygon.ndim != 2
        or polygon.shape[1] != 2
        or len(polygon) < 3
        or not np.isfinite(polygon).all()
        or np.any(polygon < 0)
        or np.any(polygon > 1)
    ):
        raise ValueError("polygon needs at least three finite normalized UV points")
    ys, xs = np.mgrid[:height, :width]
    xs, ys = (xs + 0.5) / width, (ys + 0.5) / height
    inside = np.zeros((height, width), bool)
    for a, b in zip(polygon, np.roll(polygon, 1, axis=0)):
        if a[1] == b[1]:
            continue
        crosses = (a[1] > ys) != (b[1] > ys)
        line_x = a[0] + (ys - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        inside ^= crosses & (xs < line_x)
    return inside


def classify_frame(owners, regions):
    height, width = owners.shape
    scores = {}
    # Union same-band ROIs so overlapping annotations cannot double-count pixels.
    for band in BANDS:
        mask = np.zeros(owners.shape, bool)
        for region in regions:
            if region["band"] == band:
                mask |= polygon_mask(region["polygon"], width, height)
        values, counts = np.unique(owners[mask & (owners >= 0)], return_counts=True)
        for face, count in zip(values, counts):
            scores.setdefault(int(face), {b: 0 for b in BANDS})[band] = int(count)
    return scores


def merge_scores(scores_by_frame, triangle_count):
    bands = ["U"] * triangle_count
    for scores in scores_by_frame:
        for face, hits in scores.items():
            if not 0 <= face < triangle_count:
                raise ValueError("face index outside mesh")
            for band in BANDS:
                if hits.get(band, 0) > 0 and (
                    bands[face] == "U" or BANDS.index(band) < BANDS.index(bands[face])
                ):
                    bands[face] = band
    return bands


def validate_annotations(data, mesh_sha, frame_index):
    if data.get("schema_version") != 1 or data.get("mesh_sha256") != mesh_sha:
        raise ValueError("annotation schema or exact mesh SHA256 mismatch")
    records = data.get("frames")
    if not isinstance(records, list) or not records:
        raise ValueError("annotations require nonempty frames")
    seen = set()
    for record in records:
        fid = record.get("frame_id")
        if fid not in frame_index or fid in seen:
            raise ValueError("annotation frame ID unknown or duplicate")
        seen.add(fid)
        image = record.get("original_image", f"{fid}.png")
        safe_sibling = image == f"../source/{fid}.png"
        if (
            Path(image).is_absolute()
            or (not safe_sibling and ".." in Path(image).parts)
            or ":" in image
        ):
            raise ValueError("original_image must be a safe relative local path")
        if not isinstance(record.get("regions"), list) or not record["regions"]:
            raise ValueError("each frame requires manually annotated regions")
        region_ids = set()
        for region in record["regions"]:
            rid = region.get("region_id")
            if (
                not isinstance(rid, str)
                or not rid
                or rid in region_ids
                or region.get("band") not in BANDS
            ):
                raise ValueError("region ID/band invalid")
            region_ids.add(rid)
            polygon_mask(region["polygon"], 1, 1)
            tags = region.get("tags", [])
            if (
                not isinstance(tags, list)
                or any(t not in TAGS for t in tags)
                or len(set(tags)) != len(tags)
            ):
                raise ValueError("region tags invalid or duplicated")
    return records


def write_obj(path, candidate, triangles, bands, eligible=None):
    if len(bands) != len(triangles) or any(b not in (*BANDS, "U") for b in bands):
        raise ValueError("invalid OBJ candidate bands")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(
            "# Immutable candidate geometry; grouped AI proposals, U is unknown, never D.\n"
        )
        stream.write("mtllib candidate-bands.mtl\n")
        for point in candidate:
            stream.write(
                "v " + " ".join(format(float(v), ".17g") for v in point) + "\n"
            )
        # Preserve face order and winding: group changes may repeat, geometry never changes.
        group = None
        for face_index, (face, band) in enumerate(zip(triangles, bands)):
            protected = eligible is not None and not eligible[face_index]
            face_group = band + "_protected" if protected else band
            if group != face_group:
                stream.write(f"g {face_group}\nusemtl {'P' if protected else band}\n")
                group = face_group
            stream.write("f " + " ".join(str(int(v) + 1) for v in face) + "\n")
    colors = {
        "A": (0.906, 0.435, 0.318),
        "B": (0.914, 0.769, 0.416),
        "C": (0.165, 0.616, 0.561),
        "U": (0.204, 0.259, 0.325),
        "P": (0.247, 0.247, 0.275),
    }
    material = "".join(
        f"newmtl {band}\nKd {r} {g} {b}\nKa 0.05 0.05 0.05\n\n"
        for band, (r, g, b) in colors.items()
    )
    Path(path).with_name("candidate-bands.mtl").write_text(material, encoding="utf-8")


def write_overlay(
    path, owners, bands, original_image, width, height, regions, eligible=None
):
    colors = {
        "A": "#e76f51",
        "B": "#e9c46a",
        "C": "#2a9d8f",
        "U": "#728096",
        "P": "#3f3f46",
    }
    grid = np.full(owners.shape, "X", dtype="<U1")
    visible = owners >= 0
    grid[visible] = np.asarray(bands)[owners[visible]]
    if eligible is not None:
        protected = visible.copy()
        protected[visible] = ~eligible[owners[visible]]
        protected &= grid != "U"
        grid[protected] = "P"
    h, w = owners.shape
    content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        "<title>Component-only candidate projection; U unknown, no world visibility proof</title>",
        f'<image href="{html.escape(original_image, quote=True)}" width="{width}" height="{height}"/>',
        '<g opacity="0.45" shape-rendering="crispEdges">',
    ]
    for y in range(h):
        start = 0
        while start < w:
            band = grid[y, start]
            end = start + 1
            while end < w and grid[y, end] == band:
                end += 1
            if band not in ("X", "U"):
                content.append(
                    f'<rect x="{start * width / w:g}" y="{y * height / h:g}" width="{(end - start) * width / w:g}" height="{height / h:g}" fill="{colors[band]}"/>'
                )
            start = end
    content.append('</g><g fill="none" stroke-width="3">')
    for region in regions:
        points = " ".join(f"{u * width:g},{v * height:g}" for u, v in region["polygon"])
        content.append(
            f'<polygon points="{points}" stroke="{colors[region["band"]]}"/>'
        )
    content.append("</g></svg>")
    Path(path).write_text("\n".join(content), encoding="utf-8")


def write_coverage(path, owners, original_image, width, height):
    """Separate vector layer showing all nearest component hits, without band claims."""
    h, w = owners.shape
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
        "<title>Nearest Component 230 coverage only; other world occluders unresolved</title>",
        f'<image href="{html.escape(original_image, quote=True)}" width="{width}" height="{height}"/>',
        '<g fill="#64748b" opacity="0.5" shape-rendering="crispEdges">',
    ]
    for y in range(h):
        row = owners[y] >= 0
        edges = np.flatnonzero(np.diff(np.r_[False, row, False]))
        for start, end in zip(edges[::2], edges[1::2]):
            parts.append(
                f'<rect x="{start * width / w:g}" y="{y * height / h:g}" width="{(end - start) * width / w:g}" height="{height / h:g}"/>'
            )
    parts.append("</g></svg>")
    Path(path).write_text("\n".join(parts), encoding="utf-8")


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--frames", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("output directory must not exist")
    mesh_hash = file_hash(args.mesh)
    ids, source, candidate, movable, triangles = validate_mesh(
        json.loads(Path(args.mesh).read_text())
    )
    frames = {}
    for row in csv.DictReader(Path(args.frames).open()):
        fid = row["frame_id"]
        if fid in frames:
            raise ValueError("duplicate CSV frame ID")
        camera, target = (
            json.loads(row["camera_location_cm"]),
            json.loads(row["target_cm"]),
        )
        width, height, fov = (
            integer(float(row["width_px"]), "width"),
            integer(float(row["height_px"]), "height"),
            float(row["fov_deg"]),
        )
        camera_basis(camera, target)
        projection_parameters(fov, width, height)
        frames[fid] = {
            "camera": camera,
            "target": target,
            "width": width,
            "height": height,
            "fov": fov,
            "source_sha256": row["sha256"],
        }
    annotations = validate_annotations(
        json.loads(Path(args.annotations).read_text()), mesh_hash, frames
    )
    results, per_frame = [], []
    for annotation in annotations:
        fid = annotation["frame_id"]
        frame = frames[fid]
        sample_width = 320
        sample_height = max(1, round(sample_width * frame["height"] / frame["width"]))
        owners, _ = rasterize(
            candidate,
            triangles,
            frame["camera"],
            frame["target"],
            frame["fov"],
            sample_width,
            sample_height,
        )
        scores = classify_frame(owners, annotation["regions"])
        results.append(scores)
        per_frame.append((annotation, frame, owners, scores))
    bands = merge_scores(results, len(triangles))
    eligible = movable[triangles].all(axis=1)
    proposed_tag_masks = np.zeros(len(triangles), dtype=np.uint8)
    for annotation, frame, owners, scores in per_frame:
        for region in annotation["regions"]:
            tag_bits = sum(1 << TAGS.index(t) for t in region.get("tags", []))
            if tag_bits:
                hit_faces = np.unique(
                    owners[
                        polygon_mask(
                            region["polygon"], owners.shape[1], owners.shape[0]
                        )
                        & (owners >= 0)
                    ]
                )
                proposed_tag_masks[hit_faces] |= tag_bits
    output.mkdir(parents=True, exist_ok=False)
    write_obj(output / "candidate-bands.obj", candidate, triangles, bands, eligible)
    evidence = [[] for _ in triangles]
    frame_metadata = []
    for annotation, frame, owners, scores in per_frame:
        fid = annotation["frame_id"]
        for face, hits in scores.items():
            evidence[face].append({"frame_id": fid, "sample_pixel_counts": hits})
        write_overlay(
            output / f"{fid}-projection.svg",
            owners,
            bands,
            annotation.get("original_image", f"{fid}.png"),
            frame["width"],
            frame["height"],
            annotation["regions"],
            eligible,
        )
        write_coverage(
            output / f"{fid}-coverage.svg",
            owners,
            annotation.get("original_image", f"{fid}.png"),
            frame["width"],
            frame["height"],
        )
        frame_metadata.append(
            {
                "frame_id": fid,
                **frame,
                "sample_width": owners.shape[1],
                "sample_height": owners.shape[0],
                "component_hit_pixels": int((owners >= 0).sum()),
                "annotated_face_count": len(scores),
            }
        )
    status = {
        "schema_version": 1,
        "review_status": "AI_PROPOSED",
        "owner_review": "PENDING",
        "component": 230,
        "mesh_sha256": mesh_hash,
        "frames_csv_sha256": file_hash(args.frames),
        "annotations_sha256": file_hash(args.annotations),
        "producer_sha256": file_hash(__file__),
        "geometry_basis": "candidate XYZ columns 4:7; source XYZ columns 1:4",
        "triangle_identity": "ordered row index scoped to mesh SHA256, not native Unreal triangle ID",
        "vertex_count": len(ids),
        "triangle_count": len(triangles),
        "locked_vertices": int((~movable).sum()),
        "movable_vertices": int(movable.sum()),
        "geometry_and_topology_unchanged": True,
        "candidate_band_counts": {b: bands.count(b) for b in (*BANDS, "U")},
        "eligible_faces": int(eligible.sum()),
        "protected_faces": int((~eligible).sum()),
        "limitations": [
            "Component-only nearest-hit projection is not world occlusion proof.",
            "Unseen or unannotated faces are U, never D.",
            "Pixel sampling is preliminary, not full-resolution coverage proof.",
            "No runtime changes, geometry generation, materials, performance measurements or canonical tags.",
        ],
        "frames": frame_metadata,
    }
    compact = {
        "schema_version": 1,
        "review_status": "AI_PROPOSED",
        "owner_review": "PENDING",
        "mesh_sha256": mesh_hash,
        "triangle_identity": "ordered row index scoped to mesh SHA256; not native Unreal triangle ID",
        "bands": "".join(bands),
        "tag_bit_order": list(TAGS),
        "proposed_tag_masks": proposed_tag_masks.tolist(),
        "eligible_all_vertices_movable": "".join("1" if v else "0" for v in eligible),
        "protected_faces_require_no_treatment": True,
        "selected_faces": [
            {
                "triangle_row_index": i,
                "source_vertex_ids": ids[triangles[i]].tolist(),
                "evidence": evidence[i],
            }
            for i, b in enumerate(bands)
            if b != "U"
        ],
    }
    (output / "triangle-bands.json").write_text(
        json.dumps(compact, separators=(",", ":")) + "\n"
    )
    (output / "manifest.json").write_text(json.dumps(status, indent=2) + "\n")
    (output / "source-mesh.json").write_bytes(Path(args.mesh).read_bytes())
    print(
        json.dumps(
            {
                "output": str(output),
                "candidate_band_counts": status["candidate_band_counts"],
            }
        )
    )


if __name__ == "__main__":
    main()
