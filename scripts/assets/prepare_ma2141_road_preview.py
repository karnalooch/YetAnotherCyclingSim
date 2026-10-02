"""Build an explicitly inferred pavement contact trial, never admitted road truth.

Reuse the established asymmetric corridor mesh kernel. The trial retains GIS XY,
uses separately interpreted edges, and samples native DTM across the full width.
No terrain carving or route/physics promotion is performed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.assets.prepare_ma2141_diagnostic import (  # noqa: E402
    SOURCE, SOURCE_SHA, sample_encoded, select_alignment, sha256,
)
from scripts.geometry.sp638_local_corridor import (  # noqa: E402
    CrossSectionPoint, Vec3, build_corridor_mesh,
)

from scripts.worldgen.adaptive_terrain_solver import review_pavement_contact_trial  # noqa: E402

PROFILE = SOURCE.with_name("ma2141_pavement_preview_profile.json")
PAVEMENT_THICKNESS_M = 0.08  # Nominal visual construction parameter, not survey.
BURIAL_M = 0.04


def read_profile(path=PROFILE):
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data["status"] != "INFERRED_PREVIEW_ONLY"
            or data["geographic_width_admitted"]
            or data["earthworks_admitted"] or data["physics_admitted"]):
        raise ValueError("Preview must not promote inferred edges to authority")
    if sha256(path.parent / data["imagery_file"]) != data["imagery_sha256"]:
        raise ValueError("PNOA review image hash mismatch")
    samples = np.array([[p[k] for k in ("station_m", "min_offset_m", "max_offset_m")]
                        for p in data["samples"]], dtype=float)
    if (samples.ndim != 2 or samples.shape[1] != 3 or not 13 <= len(samples) <= 121
            or not np.isfinite(samples).all()
            or samples[0, 0] != 0 or samples[-1, 0] != 300
            or (np.diff(samples[:, 0]) <= 0).any()
            or (np.diff(samples[:, 0]) > 25).any()
            or (samples[:, 1] >= 0).any() or (samples[:, 2] <= 0).any()
            or ((samples[:, 2] - samples[:, 1]) > 12).any()):
        raise ValueError("Invalid bounded edge observations")
    return data, samples


def triangle_candidates(heights, manifest, x, y):
    """Two possible native quad diagonals, to verify against UE collision.

    These are diagnostic candidates, not a guessed native topology contract.
    """
    u = (x - manifest["origin_epsg_m"][0]) / 0.5
    v = (manifest["origin_epsg_m"][1] - y) / 0.5
    if not (0 <= u < heights.shape[1]-1 and 0 <= v < heights.shape[0]-1):
        raise ValueError("Triangle probe outside native terrain")
    c, r = int(u), int(v)
    u, v = u-c, v-r
    a,b,c,d = (float(heights[r,c]), float(heights[r,c+1]),
               float(heights[r+1,c]), float(heights[r+1,c+1]))
    ad = a+(b-a)*u+(d-b)*v if u >= v else a+(d-c)*u+(c-a)*v
    bc = a+(b-a)*u+(c-a)*v if u+v <= 1 else d+(c-d)*(1-u)+(b-d)*(1-v)
    return [((z-32768)*manifest["scale_z"]/128+manifest["location_z_cm"])/100
            for z in (ad,bc)]


def build_trial(samples, height_at, origin):
    _, clip, _ = select_alignment()
    stations = np.linspace(0, 300, 601)
    centers = []
    sections = []
    for s in stations:
        p = clip.interpolate(s)
        centers.append(Vec3(p.x - origin[0], origin[1] - p.y, 0))
        lo = float(np.interp(s, samples[:, 0], samples[:, 1]))
        hi = float(np.interp(s, samples[:, 0], samples[:, 2]))
        # EPSG north-up -> UE south-up reverses the signed lateral frame.
        sections.append(tuple(CrossSectionPoint(float(v), 0, f"sample_{i}")
                              for i, v in enumerate(np.linspace(-hi, -lo, 25))))
    mesh = build_corridor_mesh(centers, sections, tangent_half_window_stations=4)
    ground = [float(height_at(origin[0] + v.x, origin[1] - v.y)) for v in mesh.vertices]
    if not np.isfinite(ground).all():
        raise ValueError("Nonfinite terrain under pavement trial")
    top = [[v.x, v.y, z + PAVEMENT_THICKNESS_M - BURIAL_M]
           for v, z in zip(mesh.vertices, ground)]
    bottom = [[v.x, v.y, z - BURIAL_M] for v, z in zip(mesh.vertices, ground)]
    n = len(top)
    faces = list(mesh.triangles)
    triangles = faces + [(a+n, c+n, b+n) for a, b, c in faces]
    edges = Counter(tuple(sorted(edge)) for a,b,c in faces
                    for edge in ((a,b),(b,c),(c,a)))
    for a,b,c in faces:
        for u,v in ((a,b),(b,c),(c,a)):
            if edges[tuple(sorted((u,v)))] == 1:
                triangles.extend([(v,u,u+n),(v,u+n,v+n)])
    # Centroids test the interpolation between native samples, not just vertices.
    gaps = []
    for a,b,c in faces:
        xyz = np.mean([top[a],top[b],top[c]], axis=0)
        ground_z = height_at(origin[0]+xyz[0], origin[1]-xyz[1])
        gaps.append(float(xyz[2] - ground_z))
    diagnostics = {
        "sample_count": len(ground),
        "triangle_centroid_count": len(gaps),
        "surface_minus_dtm_min_m": min(gaps),
        "surface_minus_dtm_max_m": max(gaps),
        "floating_centroid_count": sum(g > PAVEMENT_THICKNESS_M for g in gaps),
        "penetrating_centroid_count": sum(g < 0 for g in gaps),
        "worst_centroids": [
            {"triangle_index": i, "station_start_m": (i // 48) * 0.5,
             "lateral_band_index": (i % 48) // 2,
             "surface_minus_dtm_m": gaps[i]}
            for i in sorted(range(len(gaps)), key=lambda i: abs(gaps[i]-0.04), reverse=True)[:20]
        ],
        "native_unreal_contact_status": "PENDING",
        "r16_contact_status": "PASS" if all(0 <= g <= PAVEMENT_THICKNESS_M for g in gaps) else "FAIL",
    }
    return top + bottom, triangles, diagnostics


def prepare(prepared, output, exact_sha):
    if len(exact_sha) != 40 or any(c not in "0123456789abcdef" for c in exact_sha):
        raise ValueError("Exact lowercase SHA required")
    if output.exists():
        raise FileExistsError("Preserve existing road preview evidence")
    profile, samples = read_profile()
    manifest = json.loads((prepared / "terrain-import.json").read_text())
    r16 = prepared / "terrain.r16"
    if (manifest["region_id"] != "sa_calobra" or manifest["vertices"] != [4033,4033]
            or manifest["source_crs"] != "EPSG:25831" or manifest["nodata_sample_count"] != 0
            or manifest["source_sha256"] != "6092a48a949b7b7e8ccf120cb46d59cfd7fdd3522085e8a55162fd52fe5a139a"
            or r16.stat().st_size != 4033*4033*2 or sha256(r16) != manifest["heightmap_sha256"]):
        raise ValueError("Unadmitted native terrain")
    heights = np.fromfile(r16, dtype="<u2").reshape(4033,4033)
    vertices, triangles, contact = build_trial(
        samples, lambda x,y: sample_encoded(heights, manifest, x,y), manifest["origin_epsg_m"])
    result = {
        "schema_version": 1, "exact_sha": exact_sha, "region_id": "sa_calobra",
        "status": "INFERRED_CONTACT_TRIAL", "length_m": 300,
        "source_sha256": SOURCE_SHA, "profile_sha256": sha256(PROFILE),
        "imagery_sha256": profile["imagery_sha256"],
        "heightmap_sha256": manifest["heightmap_sha256"],
        "geographic_width_admitted": False, "authoritative_route_geometry": False,
        "authoritative_physics": False, "earthworks_authored": False,
        "human_visual_status": "PENDING", "performance_status": "PENDING",
        "pavement_thickness_m": PAVEMENT_THICKNESS_M, "burial_m": BURIAL_M,
        "thickness_evidence_class": "Decorative presentation; nominal, not survey",
        "height_interpretation": "Raw native DTM contact trial; not regularized asphalt or physics profile",
        "vertices_local_m": vertices, "triangles": triangles,
        "native_triangle_candidates_m": [triangle_candidates(
            heights, manifest, manifest["origin_epsg_m"][0]+v[0],
            manifest["origin_epsg_m"][1]-v[1]) for v in vertices[:15025]],
        "contact_diagnostic": contact, "attribution": profile["attribution"],
        "bob_review": review_pavement_contact_trial(contact, geographic_width_admitted=False),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, separators=(",", ":")) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-terrain", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exact-sha", required=True)
    args = parser.parse_args()
    result = prepare(args.prepared_terrain, args.output, args.exact_sha)
    print(json.dumps({"status": result["status"], "contact": result["contact_diagnostic"]}))
