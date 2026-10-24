"""Sampled terrain visibility for the existing TPP cameras; planning only."""

import argparse
import csv
import gzip
import hashlib
import re
import json
import math
from pathlib import Path
import numpy as np
from build_sa_calobra_spatial_treatment_plan import (
    digest,
    verified,
    read_raster,
    png_bytes,
)
import base64
from prepare_sa_calobra_cliff_erosion import classify


def ray_visibility(z, distance, camera_z, lift=0):
    """Strict running horizon; NoData blocks all subsequent samples."""
    valid = np.isfinite(z) & (z > -32000)
    slopes = np.where(valid, (z - camera_z) / distance, np.inf)
    previous = np.concatenate(
        [
            np.full((z.shape[0], 1), -np.inf),
            np.maximum.accumulate(slopes, axis=1)[:, :-1],
        ],
        axis=1,
    )
    return valid & (((z + lift - camera_z) / distance) >= previous - 1e-6)


def build(root, output, render_only=False):
    if output.exists() and not render_only:
        raise FileExistsError("Preserve previous visibility output")
    plan_path = (
        root
        / "docs/experiments/sa-calobra-spatial-treatment-plan-20261013/spatial-plan.json"
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    for s in plan["sources"]:
        verified(root / Path(s["path"]), s["sha256"])
    norm = Path(plan["sources"][3]["path"])
    manifest = json.loads(norm.read_text(encoding="utf-8"))
    record = next(r for r in manifest["outputs"] if r["path"] == "elevation.tif")
    elevation = verified(norm.parent / "elevation.tif", record["sha256"])
    terrain = read_raster(elevation)
    csv_path = root / "docs/experiments/sa-calobra-tpp-survey-20261008/frames.csv"
    obs_path = (
        root
        / "docs/experiments/sa-calobra-detail-planning-map-20261008/planning-data.json"
    )
    obs = json.loads(obs_path.read_text(encoding="utf-8"))
    verified(csv_path, obs["source_csv_sha256"])
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    if len(rows) != 1338 or len({r["frame_id"] for r in rows}) != 1338:
        raise ValueError("Survey camera inventory differs")
    prestudy_path = (
        root
        / "docs/experiments/sa-calobra-roadside-visibility-prestudy-20261008/observations.json"
    )
    prestudy = json.loads(prestudy_path.read_text(encoding="utf-8"))
    view_requirements = {}
    for station in prestudy["stations"]:
        for frame in station["frames"].values():
            view_requirements[frame["frame_id"]] = {
                k: station[k]
                for k in ("near_profile", "dominant_wall", "panorama", "reason")
            }
    if set(view_requirements) != {r["frame_id"] for r in rows}:
        raise ValueError("Prestudy/capture frame identities differ")
    n = 505
    hits = np.zeros((n, n), np.uint16)
    tested = np.zeros((n, n), np.uint16)
    elevated = np.zeros((n, n), np.uint16)
    pixels = np.zeros((n, n), np.float32)
    nearest = np.full((n, n), np.inf, np.float32)
    witness = np.full((n, n), -1, np.int16)
    distance = np.arange(1.0, 2854.0, 1.0, dtype=np.float32)[None, :]
    per_frame = []
    output.mkdir(parents=True, exist_ok=render_only)
    if not render_only:
        (output / "producer-executed.py").write_bytes(Path(__file__).read_bytes())
    if render_only:
        with np.load(output / "visibility-arrays.npz") as cached:
            hits, tested, elevated, pixels, nearest, witness = (
                cached[k].copy()
                for k in (
                    "hits",
                    "tested",
                    "elevated",
                    "pixels_per_m",
                    "nearest_m",
                    "witness",
                )
            )
        per_frame = json.loads((output / "frame-coverage.json").read_text())
    for i, row in enumerate([] if render_only else rows):
        c = np.array(json.loads(row["camera_location_cm"]), float) / 100
        t = np.array(json.loads(row["target_cm"]), float) / 100
        forward = t - c
        forward /= np.linalg.norm(forward)
        right = np.cross([0, 0, 1], forward)
        right /= np.linalg.norm(right)
        up = np.cross(forward, right)
        hfov = math.radians(float(row["fov_deg"]))
        vfov = 2 * math.atan(
            math.tan(hfov / 2) * int(row["height_px"]) / int(row["width_px"])
        )
        center = math.atan2(forward[1], forward[0])
        # Wider than horizontal FOV: actual 3D projection below filters pitch effects.
        angles = center + np.deg2rad(np.arange(-50, 50.001, 0.25, dtype=np.float32))
        x = c[0] + np.cos(angles[:, None]) * distance
        y = c[1] + np.sin(angles[:, None]) * distance
        cc = np.rint(x * 2).astype(np.int32)
        rr = np.rint(y * 2).astype(np.int32)
        inside = (rr >= 0) & (rr < 4033) & (cc >= 0) & (cc < 4033)
        z = terrain[np.clip(rr, 0, 4032), np.clip(cc, 0, 4032)]
        z = np.where(inside, z, np.nan)
        dz = z - c[2]
        dx = x - c[0]
        dy = y - c[1]
        depth = dx * forward[0] + dy * forward[1] + dz * forward[2]
        lateral = dx * right[0] + dy * right[1] + dz * right[2]
        vertical = dx * up[0] + dy * up[1] + dz * up[2]
        frustum = (
            inside
            & (depth > 0)
            & (np.abs(lateral) <= depth * math.tan(hfov / 2))
            & (np.abs(vertical) <= depth * math.tan(vfov / 2))
        )
        visible = ray_visibility(z, distance, c[2]) & frustum
        # Raised object may emerge even when its ground is occluded. Review only.
        lifted = ray_visibility(z, distance, c[2], 2) & frustum
        bins = (rr // 8) * n + cc // 8
        flat = visible.ravel()
        ids = bins.ravel()[flat]
        unique = np.unique(ids)
        hits.ravel()[unique] += 1
        tested.ravel()[np.unique(bins[frustum])] += 1
        elevated.ravel()[np.unique(bins[lifted])] += 1
        depth_visible = depth.ravel()[flat]
        scale = (
            int(row["width_px"])
            / (2 * math.tan(hfov / 2))
            / np.maximum(depth_visible, 1)
        )
        np.maximum.at(pixels.ravel(), ids, scale)
        np.minimum.at(
            nearest.ravel(), ids, np.broadcast_to(distance, visible.shape).ravel()[flat]
        )
        unset = unique[witness.ravel()[unique] < 0]
        witness.ravel()[unset] = i
        per_frame.append(
            {
                "frame_id": row["frame_id"],
                "visible_4m_bins": len(unique),
                "direction": row["direction"],
                "window_id": row["window_id"],
            }
        )
        if i % 50 == 0:
            (output / "progress.json").write_text(
                json.dumps({"processed": i + 1, "total": len(rows)})
            )
            print(f"{i + 1}/{len(rows)} cameras", flush=True)
    selector = Path(plan["sources"][0]["path"])
    sm = json.loads(selector.read_text(encoding="utf-8"))
    for name in ("cliff-candidate.tif", "scree-candidate.tif"):
        record = next(r for r in sm["outputs"] if r["path"] == name)
        verified(selector.parent / name, record["sha256"])
    if render_only and len(per_frame) != len(rows):
        raise ValueError("Cached camera inventory differs")

    def coarse(a):
        padded = np.pad(a, ((0, 7), (0, 7)), constant_values=False)
        return padded.reshape(n, 8, n, 8).any(axis=(1, 3))

    original_cliff = read_raster(selector.parent / "cliff-candidate.tif")
    original_scree = read_raster(selector.parent / "scree-candidate.tif")
    reasons = read_raster(Path(plan["sources"][2]["path"]))
    exact_exclusions = ((reasons & 17) != 0) | (reasons == 65535)
    former_holdback = coarse((reasons & 63) != 0)
    released = ((reasons & 46) != 0) & ~exact_exclusions
    derivative_paths = []
    derivatives = {}
    for name in ("slope.tif", "roughness.tif"):
        record = next(r for r in manifest["outputs"] if r["path"] == name)
        path = verified(norm.parent / name, record["sha256"])
        derivative_paths.append(path)
        derivatives[name] = read_raster(path)
    # Planning-only reclassification inside the owner-selected former holdbacks.
    # Canonical selectors and live consumer exclusions are never overwritten.
    diagnostic = classify(
        derivatives["slope.tif"],
        derivatives["roughness.tif"],
        terrain,
        exact_exclusions,
        parameters=sm["parameters"],
    )
    filled_cliff = np.where(released, diagnostic["cliff_selector"], original_cliff)
    filled_scree = np.where(released, diagnostic["scree_selector"], original_scree)
    cliff = coarse(filled_cliff == 1)
    scree = coarse(filled_scree == 1)
    unknown = coarse((filled_cliff == 255) | (filled_scree == 255))
    # Operational proposals, not geological labels, placement masks or accepted LODs.
    treatment = np.zeros((n, n), np.uint8)
    treatment[hits > 0] = 1
    treatment[(hits > 0) & cliff] = 2
    treatment[(hits > 0) & scree & (pixels >= 8)] = 3
    treatment[(hits == 0) & (elevated > 0) & (cliff | scree)] = 4
    treatment[unknown] = 6
    labels = {
        0: "Simplified objects — obiekty uproszczone",
        1: "Material-first proposal: visible terrain; no selected cliff/near scree requirement",
        2: "Cliff mesh review: visible steep/rough source candidate; preserve major forms",
        3: "Rock trial review: visible scree candidate; 1 m feature projects to >=8 px",
        4: "Raised-form review: 2 m form may emerge above occluded ground",
        5: "Road/water exclusion overlay (exact source pixels)",
        6: "Unknown terrain neighborhood: no placement",
    }
    colors = np.array(
        [
            [55, 66, 76],
            [82, 132, 126],
            [223, 124, 71],
            [235, 198, 86],
            [172, 95, 180],
            [105, 115, 130],
            [180, 50, 80],
        ],
        np.uint8,
    )
    np.savez_compressed(
        output / "visibility-arrays.npz",
        hits=hits,
        tested=tested,
        elevated=elevated,
        pixels_per_m=pixels,
        nearest_m=nearest,
        witness=witness,
        treatment=treatment,
    )
    layer = []
    for k in (0, 1, 2, 3, 4, 6, 5):
        label = labels[k]
        if k == 5:
            mask = ((reasons & 17) != 0) & (reasons != 65535)
            label = "Hard exclusions: roads and watercourses only"
            rgba = np.zeros((*reasons.shape, 4), np.uint8)
        else:
            rgba = np.zeros((n, n, 4), np.uint8)
            mask = treatment == k
        rgba[mask, :3] = colors[k]
        rgba[mask, 3] = 220
        url = "data:image/png;base64," + base64.b64encode(png_bytes(rgba)).decode()
        layer.append(
            {
                "id": f"visibility-{k}",
                "label": label,
                "cells": int(mask.sum()),
                "extent_m": 2016.5 if k == 5 else 2020,
                "cell_label": "source cells (0.5 m); water holdback includes 5 m buffer"
                if k == 5
                else "planning bins",
                "url": url,
            }
        )
    summary = {
        "status": "SAMPLED_TERRAIN_VISIBILITY_TREATMENT_PROPOSAL",
        "issue": 365,
        "milestone": "M3",
        "reanalysis": {
            "scope": "former technical holdbacks outside exact road/water exclusions; terrain criteria reused, then existing 1338-camera visibility applied",
            "released_source_cells": int(released.sum()),
            "released_source_area_m2": float(released.sum()) * 0.25,
            "released_cliff_candidate_cells": int(
                ((filled_cliff == 1) & released).sum()
            ),
            "released_scree_candidate_cells": int(
                ((filled_scree == 1) & released).sum()
            ),
            "former_holdback_bin_treatments": {
                labels[k]: int((former_holdback & (treatment == k)).sum())
                for k in labels
            },
            "filled_planning_bins": int(coarse(released).sum()),
            "released_bin_treatments": {
                labels[k]: int((coarse(released) & (treatment == k)).sum())
                for k in labels
            },
            "consumer_exclusions_changed": False,
            "native_modified_surfaces": "Base_DTM inference only; BOB/native presentation may differ and still requires review",
        },
        "frames": len(rows),
        "station_pairs": 669,
        "windows": 185,
        "owner_unsampled_treatment": "Simplified objects: simple major forms and limited detail; not a confirmed hidden region or automatic placement permission",
        "hard_exclusions_display": {
            "bits": [1, 16],
            "source_cell_m": 0.5,
            "aggregation": "none",
            "water": "existing source water holdback; includes 5 m decorative buffer, not measured channel width",
            "technical_consumer_holdbacks": "unchanged",
        },
        "grid_cell_m": 4,
        "grid_origin_edges_local_m": [-0.25, -0.25],
        "grid_shape": [505, 505],
        "grid_rule": "ANY terrain candidate within each 8x8 source-cell block; visibility may hit another point in that block. Classification covers former technical holdbacks; exact road/water overlay is separate. Planning bins are not fill polygons; consumer masks remain binding.",
        "array_file_sha256": digest(output / "visibility-arrays.npz"),
        "array_logical_sha256": {
            name: hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
            for name, value in {
                "hits": hits,
                "tested": tested,
                "elevated": elevated,
                "pixels_per_m": pixels,
                "nearest_m": nearest,
                "witness": witness,
                "treatment": treatment,
            }.items()
        },
        "ray_step_m": 1,
        "ray_angle_step_deg": 0.25,
        "nominal_feature_review_threshold": {
            "feature_m": 1,
            "pixels": 8,
            "authority": "explicit planning heuristic; not accepted LOD/performance limit",
        },
        "compute_script_sha256": digest(output / "producer-executed.py"),
        "render_script_sha256": digest(Path(__file__)),
        "sources": [
            {"path": str(p), "sha256": digest(p)}
            for p in (
                plan_path,
                csv_path,
                elevation,
                selector,
                prestudy_path,
                *derivative_paths,
            )
        ],
        "counts": {labels[k]: int((treatment == k).sum()) for k in labels},
        "limits": [
            "TPP camera poses, not a continuous rider traversal or look-around proof",
            "Base_DTM only; excludes v8 mesh, earthworks, buildings and vegetation occluders",
            "Radial 1 m/.25 degree sampling and 4 m bins; sampled hits do not prove every point in a bin",
            "No observed hit: owner-selected simplified-object treatment; visibility remains unverified, never confirmed hidden D",
            "Material-first is a review proposal; visibility cannot establish geological need or geometry correctness",
            "2 m raised-form test is a diagnostic proxy, not an asset-placement test",
            "Original PNG correspondence and live native checks required before regional placement",
            "ANY-source 4 m planning bins may include unselected neighboring source cells; never fill a whole bin with geometry",
            "Geometry review means inspect existing geometry first; it does not prescribe adding another mesh over an existing accepted surface",
            "Missing or occluded ground does not prove a larger rock, skyline, shadow or reflection contribution unnecessary",
        ],
        "placement": False,
        "qualified_assets": [],
        "performance_pass": False,
        "layers": [{k: v for k, v in item.items() if k != "url"} for item in layer],
    }
    (output / "visibility-plan.json").write_text(json.dumps(summary, indent=2) + "\n")
    (output / "frame-coverage.json").write_text(
        json.dumps(per_frame, separators=(",", ":"))
    )
    # Extend the existing artifact with separately switchable, correctly registered layers.
    preserved = plan_path.parent / "spatial-plan-source.html.gz"
    if preserved.exists():
        page = gzip.decompress(preserved.read_bytes()).decode("utf-8")
    else:
        page = (plan_path.parent / "spatial-plan.html").read_text(encoding="utf-8")
    imgs = "".join(
        f'<image id="{item["id"]}" x="-.25" y="-.25" width="{item["extent_m"]}" height="{item["extent_m"]}" href="{item["url"]}"/>'
        for item in layer
    )
    # The combined road/water source mask is the sole exclusion display.
    for old_layer in ("protected", "other_exclusions"):
        page = re.sub(r'<image id="' + old_layer + r'"[^>]+/>', "", page)
        page = re.sub(
            r'<label><input[^>]*data-layer="' + old_layer + r'"[^>]*>.*?</label>',
            "",
            page,
            flags=re.S,
        )
    legend = (
        "<h2>Sampled visibility / proposed treatment</h2><p>1338 TPP cameras · 669 paired stations · 185 disconnected windows. 4 m planning bins. Every class requires review; no regional planting authorization.</p>"
        + "".join(
            f'<label><input type="checkbox" checked data-layer="{item["id"]}">{item["label"]}<small>{item["cells"]:,} {item["cell_label"]}</small></label>'
            for item in layer
        )
        + "<details><summary>Analysis limits</summary><ul>"
        + "".join(f"<li>{s}</li>" for s in summary["limits"])
        + "</ul></details>"
    )
    page = page.replace(
        '<g id="observations">', imgs + '<g id="observations">'
    ).replace(
        "<h2>Physical raster areas</h2>", legend + "<h2>Original source candidates</h2>"
    )
    page = page.replace(
        "Sa Calobra — where to investigate rock treatment",
        "Sa Calobra — sampled visibility and treatment proposals",
    )
    inspect_data = {
        "labels": labels,
        "hits": hits.ravel().tolist(),
        "witness": witness.ravel().tolist(),
        "treatment": treatment.ravel().tolist(),
        "pixels": np.round(pixels, 1).ravel().tolist(),
        "frames": [r["frame_id"] for r in rows],
        "view_requirements": view_requirements,
    }
    script = """<script>
const visibilityData=VISIBILITY_DATA;
map.addEventListener('click',e=>{if(!e.shiftKey)return;let p=point(e),c=Math.floor((p.x+.25)/4),r=Math.floor((p.y+.25)/4);if(c<0||r<0||c>=505||r>=505)return;let i=r*505+c,w=visibilityData.witness[i],box=document.getElementById('visibility-inspector');box.replaceChildren();let title=document.createElement('strong');title.textContent=visibilityData.labels[visibilityData.treatment[i]];box.append(title);let text=document.createElement('p');text.textContent=`X ${c*4-.25}–${c*4+3.75} m / Y ${r*4-.25}–${r*4+3.75} m; sampled visible-ground cameras: ${visibilityData.hits[i]}; nominal maximum pixels per 1 m: ${visibilityData.pixels[i]}.`;box.append(text);if(w>=0){let frame=visibilityData.frames[w],a=document.createElement('a');a.textContent='First terrain visibility witness: '+frame;a.href='../sa-calobra-tpp-survey-20261008/windows/'+frame.slice(0,11)+'.md';a.target='_blank';box.append(a);let req=visibilityData.view_requirements[frame],context=document.createElement('p');context.textContent='Existing visual prestudy for this view (not a world-surface assignment): near '+req.near_profile+'; B '+req.dominant_wall+'; C '+req.panorama+'. '+req.reason;box.append(context);}let note=document.createElement('p');note.textContent='Witness identifies a computed DTM hit, not a visually confirmed rock or physical surface owner.';box.append(note);});
</script>""".replace("VISIBILITY_DATA", json.dumps(inspect_data, separators=(",", ":")))
    page = page.replace(
        "</aside>",
        '<p>Shift-click a planning bin for its camera witness and treatment reason.</p><div id="visibility-inspector"></div></aside>',
    )
    page = page.replace("</html>", script + "</html>")
    (output / "spatial-plan.html").write_text(page, encoding="utf-8")
    (output / "progress.json").write_text(
        json.dumps({"processed": len(rows), "total": len(rows), "status": "COMPLETE"})
    )
    print(json.dumps(summary["counts"]), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--render-only", action="store_true")
    args = p.parse_args()
    build(args.root.resolve(), args.output, args.render_only)
