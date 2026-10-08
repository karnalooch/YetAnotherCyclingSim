#!/usr/bin/env python3
"""Prepare one bounded, reversible face-local fairing trial on the retained v8 mesh.

Coordinates use the existing mesh's Unreal centimetres. Only candidate XYZ may
change; source coordinates, flags, topology and every outside-incident vertex
remain exact. This offline proposal neither changes Unreal nor admits appearance.
"""

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from .prepare_sa_calobra_detail_pilot import TAGS, integer, validate_mesh
    from .run_sa_calobra_detail_pilot import LIMIT, MESH
else:
    from prepare_sa_calobra_detail_pilot import TAGS, integer, validate_mesh
    from run_sa_calobra_detail_pilot import LIMIT, MESH


MASK = "6ec02a0e3dac9756923d29c8b603c0c1d79db411d06f3a20bb30956e11390953"
FAIRING_FACTOR = 0.5
MAX_ADDED_CM = 5.0
MAX_SOURCE_CM = 50.0
BOUND_TOLERANCE_CM = 1e-6
MIN_CHANGE_CM = 1e-6
MIN_AREA_RATIO = 0.5
TRIANGLE_IDENTITY = (
    "ordered row index scoped to mesh SHA256; not native Unreal triangle ID"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_mask(mask, mesh_sha256, ids, movable, triangles):
    """Cross-check every face label/ownership row against the actual source mesh."""
    require(isinstance(mask, dict), "mask must be an object")
    require(
        mask.get("schema_version") == 1
        and mask.get("mesh_sha256") == mesh_sha256,
        "mask schema or exact source mesh SHA256 mismatch",
    )
    require(
        mask.get("triangle_identity") == TRIANGLE_IDENTITY
        and mask.get("protected_faces_require_no_treatment") is True,
        "mask triangle identity or protected-face contract mismatch",
    )
    bands = mask.get("bands")
    require(
        isinstance(bands, str)
        and len(bands) == len(triangles)
        and set(bands) <= set("ABCU"),
        "mask bands must address every ordered triangle; D is not inferred",
    )
    eligible = movable[triangles].all(axis=1)
    require(
        mask.get("eligible_all_vertices_movable")
        == "".join("1" if value else "0" for value in eligible),
        "mask eligibility disagrees with actual protected vertices",
    )
    tags = mask.get("proposed_tag_masks")
    require(
        mask.get("tag_bit_order") == list(TAGS)
        and isinstance(tags, list)
        and len(tags) == len(triangles),
        "mask tag order or length mismatch",
    )
    tag_values = [integer(value, "tag mask") for value in tags]
    require(
        all(0 <= value < 1 << len(TAGS) for value in tag_values),
        "mask contains undeclared tag bits",
    )
    selected = mask.get("selected_faces")
    require(isinstance(selected, list), "mask requires selected face records")
    expected = [index for index, band in enumerate(bands) if band != "U"]
    require(len(selected) == len(expected), "selected face record count mismatch")
    for record, index in zip(selected, expected):
        require(isinstance(record, dict), "selected face record must be an object")
        require(
            integer(record.get("triangle_row_index"), "selected face index")
            == index,
            "selected face rows are missing, duplicated or out of order",
        )
        vertex_ids = record.get("source_vertex_ids")
        require(
            isinstance(vertex_ids, list)
            and len(vertex_ids) == 3
            and [integer(value, "source vertex ID") for value in vertex_ids]
            == ids[triangles[index]].tolist(),
            "selected face source vertex IDs or winding mismatch",
        )
    silhouette = 1 << TAGS.index("SILHOUETTE_CRITICAL")
    return (
        eligible,
        (np.asarray(list(bands)) == "A")
        & eligible
        & ((np.asarray(tag_values) & silhouette) == 0),
    )


def mesh_adjacency(triangles, vertex_count):
    """Reject nonmanifold/duplicate topology and inconsistent shared-edge winding."""
    edge_faces = {}
    vertex_faces = [set() for _ in range(vertex_count)]
    neighbors = [set() for _ in range(vertex_count)]
    face_neighbors = [set() for _ in triangles]
    seen = set()
    for face_index, triangle in enumerate(triangles):
        face = tuple(int(value) for value in triangle)
        identity = tuple(sorted(face))
        require(identity not in seen, "duplicate source triangle")
        seen.add(identity)
        for vertex in face:
            vertex_faces[vertex].add(face_index)
        for a, b in zip(face, (face[1], face[2], face[0])):
            edge = (min(a, b), max(a, b))
            edge_faces.setdefault(edge, []).append((face_index, a < b))
            neighbors[a].add(b)
            neighbors[b].add(a)
    border_vertices = set()
    for edge, records in edge_faces.items():
        require(len(records) <= 2, "nonmanifold source edge")
        if len(records) == 1:
            border_vertices.update(edge)
        else:
            (first, direction), (second, opposite) = records
            require(direction != opposite, "inconsistent source triangle winding")
            face_neighbors[first].add(second)
            face_neighbors[second].add(first)
    # An edge-manifold mesh can still have a bow-tie vertex with two separate fans.
    for incident in vertex_faces:
        if not incident:
            continue
        remaining = set(incident)
        stack = [min(remaining)]
        remaining.remove(stack[0])
        while stack:
            for other in sorted(face_neighbors[stack.pop()] & remaining):
                remaining.remove(other)
                stack.append(other)
        require(not remaining, "nonmanifold source vertex fan")
    return vertex_faces, neighbors, face_neighbors, border_vertices


def select_patch(eligible_a, triangles, vertex_faces, face_neighbors, border):
    """Pick largest edge-connected A component with an interior, then lowest row."""
    remaining = set(np.flatnonzero(eligible_a).tolist())
    components = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        stack, component = [seed], {seed}
        while stack:
            for other in sorted(face_neighbors[stack.pop()] & remaining):
                remaining.remove(other)
                component.add(other)
                stack.append(other)
        components.append(component)
    for component in sorted(components, key=lambda item: (-len(item), min(item))):
        vertices = set(triangles[sorted(component)].ravel().tolist())
        interior = {
            vertex
            for vertex in vertices
            if vertex not in border and vertex_faces[vertex] <= component
        }
        if interior:
            return component, vertices - interior, interior, len(components)
    raise ValueError("no connected eligible A patch has strictly interior vertices")


def triangle_normals(points, triangles):
    return np.cross(
        points[triangles[:, 1]] - points[triangles[:, 0]],
        points[triangles[:, 2]] - points[triangles[:, 0]],
    )


def bound_step(before, source, step):
    """Intersect a straight candidate step with both displacement balls."""
    require(
        float(np.linalg.norm(before - source))
        <= MAX_SOURCE_CM + BOUND_TOLERANCE_CM,
        "input is outside the total source displacement cap",
    )
    step = np.asarray(step, dtype=float).copy()
    length = float(np.linalg.norm(step))
    if length < MIN_CHANGE_CM:
        return np.zeros(3)
    if length > MAX_ADDED_CM:
        step *= MAX_ADDED_CM / length
    relative = before - source
    a = float(np.sum(step * step))
    b = 2 * float(np.sum(relative * step))
    # Native serialization can exceed 50 cm by a few floating-point ulps.
    c = min(0.0, float(np.sum(relative * relative)) - MAX_SOURCE_CM**2)
    discriminant = math.sqrt(max(0.0, b * b - 4 * a * c))
    # Stable positive quadratic root, including an outward step at the source cap.
    if b >= 0:
        denominator = b + discriminant
        allowed = -2 * c / denominator if denominator else 0.0
    else:
        allowed = (-b + discriminant) / (2 * a)
    if allowed < 1:
        step *= max(0.0, allowed) * (1 - 1e-10)
    return step


def normal_residual(points, vertices, neighbors, normals):
    """Normal-projected one-ring mean offset, using fixed baseline normals (cm)."""
    return np.asarray(
        [
            np.sum(
                (np.mean(points[sorted(neighbors[vertex])], axis=0) - points[vertex])
                * normals[index]
            )
            for index, vertex in enumerate(vertices)
        ]
    )


def create_treatment(mesh, mask, source_mesh_sha256, mask_sha256):
    """Pure array/JSON transform; the file entrypoint additionally pins both inputs."""
    require(isinstance(mesh, dict), "mesh must be an object")
    ids, source, before, movable, triangles = validate_mesh(mesh)
    eligible, eligible_a = validate_mask(
        mask, source_mesh_sha256, ids, movable, triangles
    )
    vertex_faces, neighbors, face_neighbors, border = mesh_adjacency(
        triangles, len(ids)
    )
    selected, fixed_boundary, interior, component_count = select_patch(
        eligible_a, triangles, vertex_faces, face_neighbors, border
    )
    vertices = sorted(interior)
    before_normals = triangle_normals(before, triangles)
    before_areas = np.linalg.norm(before_normals, axis=1)
    require(np.all(before_areas > 1e-8), "degenerate source candidate triangle")
    require(
        np.all(np.abs(before_normals[:, 2]) > 1e-8),
        "degenerate source candidate XY projection",
    )
    normals = np.asarray(
        [
            before_normals[sorted(vertex_faces[vertex])].sum(axis=0)
            for vertex in vertices
        ]
    )
    normal_lengths = np.linalg.norm(normals, axis=1)
    require(np.all(normal_lengths > 1e-8), "undefined interior surface normal")
    normals /= normal_lengths[:, None]
    residual_before = normal_residual(before, vertices, neighbors, normals)
    steps = np.asarray(
        [
            bound_step(
                before[vertex],
                source[vertex],
                FAIRING_FACTOR * residual_before[index] * normals[index],
            )
            for index, vertex in enumerate(vertices)
        ]
    )
    before_rms = float(np.sqrt(np.mean(residual_before**2)))
    # One Jacobi pass only; reduce its strength if local geometry would collapse.
    for attempt in range(21):
        scale = 0.5**attempt
        after = before.copy()
        after[vertices] += steps * scale
        added = np.linalg.norm(after - before, axis=1)
        require(float(added.max()) >= MIN_CHANGE_CM, "no safe nonzero fairing change")
        after_normals = triangle_normals(after, triangles)
        after_areas = np.linalg.norm(after_normals, axis=1)
        area_ratios = after_areas / before_areas
        projected_ratios = after_normals[:, 2] / before_normals[:, 2]
        dots = np.sum(after_normals * before_normals, axis=1)
        after_rms = float(
            np.sqrt(np.mean(normal_residual(after, vertices, neighbors, normals) ** 2))
        )
        if (
            np.all(dots > 0)
            and np.all(area_ratios >= MIN_AREA_RATIO)
            and np.all(projected_ratios >= MIN_AREA_RATIO)
            and after_rms < before_rms
        ):
            break
    else:
        raise ValueError(
            "no safe fairing step preserves triangles and reduces residual"
        )
    changed = np.flatnonzero(np.any(after != before, axis=1))
    fixed = sorted(set(range(len(ids))) - interior)
    outside_faces = sorted(set(range(len(triangles))) - selected)
    outside_incident = set(triangles[outside_faces].ravel().tolist())
    require(np.array_equal(after[fixed], before[fixed]), "fixed vertex changed")
    require(
        np.array_equal(
            after[triangles[outside_faces]], before[triangles[outside_faces]]
        )
        and np.array_equal(after[triangles[~eligible]], before[triangles[~eligible]]),
        "outside or protected face changed",
    )
    total = np.linalg.norm(after - source, axis=1)
    require(
        float(added.max()) <= MAX_ADDED_CM + BOUND_TOLERANCE_CM
        and float(total.max()) <= MAX_SOURCE_CM + BOUND_TOLERANCE_CM,
        "trial exceeds an added or source-relative displacement bound",
    )
    trial = copy.deepcopy(mesh)
    rows = trial.get("vertices_cm", trial.get("vertices"))
    for vertex in changed:
        rows[vertex][4:7] = after[vertex].tolist()
    # Reuse the original consumer contract against the serialized candidate rows.
    validate_mesh(trial)
    manifest = {
        "schema_version": 1,
        "status": "BOUNDED_DETAIL_TRIAL_PREPARED",
        "review_status": "AI_PROPOSED",
        "owner_review": "PENDING",
        "component": 230,
        "source_mesh_sha256": source_mesh_sha256,
        "mask_sha256": mask_sha256,
        "trial_mesh_path": "treatment-mesh.json",
        "triangle_identity": TRIANGLE_IDENTITY,
        "algorithm": "one-pass-normal-fairing-v1",
        "fairing_factor": FAIRING_FACTOR,
        "accepted_step_scale": scale,
        "selection_rule": (
            "largest edge-connected eligible A component with interior; "
            "lowest face row breaks ties"
        ),
        "boundary_policy": (
            "freeze every vertex incident to an outside face "
            "and every source boundary vertex"
        ),
        "extra_frozen_one_ring": False,
        "eligible_a_face_count": int(eligible_a.sum()),
        "eligible_a_component_count": component_count,
        "selected_face_indices": sorted(selected),
        "selected_face_count": len(selected),
        "selected_vertex_count": len(interior) + len(fixed_boundary),
        "fixed_boundary_vertex_ids": sorted(
            int(ids[index]) for index in fixed_boundary
        ),
        "interior_vertex_ids": sorted(int(ids[index]) for index in interior),
        "changed_vertex_ids": [int(ids[index]) for index in changed],
        "changed_vertex_count": len(changed),
        "fixed_vertex_count": len(fixed),
        "outside_incident_vertex_count": len(outside_incident),
        "protected_face_count": int((~eligible).sum()),
        "vertex_count": len(ids),
        "triangle_count": len(triangles),
        "max_added_displacement_cm": float(added.max()),
        "max_total_source_displacement_cm": float(total.max()),
        "max_changed_source_displacement_cm": float(total[changed].max()),
        "bounds": {
            "max_added_displacement_cm": MAX_ADDED_CM,
            "max_total_source_displacement_cm": MAX_SOURCE_CM,
            "floating_point_tolerance_cm": BOUND_TOLERANCE_CM,
        },
        "geometric_audit": {
            "min_triangle_area_ratio": float(area_ratios.min()),
            "min_xy_projected_area_ratio": float(projected_ratios.min()),
            "min_face_normal_cosine": float(
                np.min(dots / (before_areas * after_areas))
            ),
            "no_triangle_flips_or_degeneracy": True,
            "xy_orientation_preserved": True,
            "edge_and_vertex_manifold": True,
            "self_intersection_test": "NOT_PERFORMED",
        },
        "fairing_residual": {
            "metric": (
                "RMS normal-projected one-ring mean offset at interior vertices; "
                "fixed v8 normals"
            ),
            "before_cm": before_rms,
            "after_cm": after_rms,
            "visual_quality_score": False,
        },
        "source_coordinates_unchanged": True,
        "movable_flags_unchanged": True,
        "topology_and_winding_unchanged": True,
        "source_boundary_vertices_unchanged": True,
        "outside_incident_vertices_unchanged": True,
        "unselected_faces_unchanged": True,
        "protected_faces_unchanged": True,
        "canonical_landscape_mutation": False,
        "map_saved": False,
        "assets_saved": False,
        "production_admission": False,
        "world_occlusion": "NOT_MEASURED",
        "limitations": [
            "A local fairing residual is not an appearance score or owner acceptance.",
            "Native consumer, whole-scene occlusion and visual comparison "
            "require separate proof.",
            "No topology, source boundary or protected face changes; "
            "no inferred D or mask expansion.",
        ],
        "changed_vertices": [
            {
                "vertex_id": int(ids[index]),
                "row_index": int(index),
                "source_cm": source[index].tolist(),
                "before_cm": before[index].tolist(),
                "after_cm": after[index].tolist(),
                "added_delta_cm": (after[index] - before[index]).tolist(),
                "added_displacement_cm": float(added[index]),
                "total_source_displacement_cm": float(total[index]),
                "allowed_added_displacement_cm": MAX_ADDED_CM,
                "allowed_source_displacement_cm": MAX_SOURCE_CM,
            }
            for index in changed
        ],
    }
    return trial, manifest


def read_fixed(path, expected, label):
    path = Path(path)
    require(0 < path.stat().st_size < LIMIT, f"{label} exceeds bounded input size")
    data = path.read_bytes()
    require(
        hashlib.sha256(data).hexdigest() == expected, f"fixed {label} SHA256 mismatch"
    )
    return json.loads(data)


def prepare(mesh_path, mask_path, output):
    output = Path(output)
    require(not output.exists(), "output directory must not exist")
    mesh = read_fixed(mesh_path, MESH, "v8 source mesh")
    mask = read_fixed(mask_path, MASK, "detail mask")
    trial, manifest = create_treatment(mesh, mask, MESH, MASK)
    encoded = (
        json.dumps(trial, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()
    manifest["trial_mesh_sha256"] = hashlib.sha256(encoded).hexdigest()
    manifest["producer_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    output.mkdir(parents=True, exist_ok=False)
    (output / "treatment-mesh.json").write_bytes(encoded)
    (output / "treatment-manifest.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("mesh", "mask", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    manifest = prepare(args.mesh, args.mask, args.output)
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in (
                    "status",
                    "selected_face_count",
                    "changed_vertex_count",
                    "max_added_displacement_cm",
                    "trial_mesh_sha256",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
