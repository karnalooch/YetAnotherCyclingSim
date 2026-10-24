"""Build a read-only spatial draft from authenticated cliff/scree selectors."""

import argparse
import base64
import hashlib
import html
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import rasterio


COLORS = {
    "maintained": (55, 66, 76),
    "cliff": (223, 124, 71),
    "scree": (235, 198, 86),
    "protected": (97, 150, 220),
    "other_exclusions": (105, 115, 130),
    "unknown": (172, 95, 180),
}
LABELS = {
    "maintained": "Current material maintained; treatment unresolved",
    "cliff": "Cliff mesh investigation candidate",
    "scree": "Loose rock / scree investigation candidate",
    "protected": "Protected: road carriageway only",
    "other_exclusions": "Other exclusions: shoulder, BOB, buildings, water, infrastructure",
    "unknown": "Unknown terrain neighborhood: no placement",
}
GRID_TRANSFORM = [0.5, 0.0, 483000.0, 0.0, -0.5, 4409516.5]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified(path, expected):
    if digest(path) != expected:
        raise ValueError(f"Source hash mismatch: {path}")
    return Path(path)


def cell_edges(row, col):
    return [col * 0.5 - 0.25, row * 0.5 - 0.25, col * 0.5 + 0.25, row * 0.5 + 0.25]


def layers(cliff, scree, protected, road=None):
    if cliff.shape != scree.shape or cliff.shape != protected.shape:
        raise ValueError("Raster shape mismatch")
    if not set(np.unique(cliff)) <= {0, 1, 255} or not set(np.unique(scree)) <= {
        0,
        1,
        255,
    }:
        raise ValueError("Unknown selector value")
    unknown = (cliff == 255) | (scree == 255)
    if road is None:
        road = protected
    if road.shape != protected.shape or np.any(road & ~protected):
        raise ValueError("Road display must be a subset of source protected cells")
    if np.any((cliff == 1) & ((scree == 1) | protected | unknown)) or np.any(
        (scree == 1) & (protected | unknown)
    ):
        raise ValueError("Candidate intersects exclusion/unknown/other candidate")
    return {
        "maintained": ~(unknown | protected | (cliff == 1) | (scree == 1)),
        "cliff": cliff == 1,
        "scree": scree == 1,
        "protected": road,
        "other_exclusions": protected & ~road,
        "unknown": unknown,
    }


def png_bytes(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="PNG", optimize=True)
    return stream.getvalue()


def read_raster(path):
    with rasterio.open(path) as dataset:
        if (
            dataset.shape != (4033, 4033)
            or str(dataset.crs) != "EPSG:25831"
            or list(dataset.transform)[:6] != GRID_TRANSFORM
        ):
            raise ValueError("Not the accepted frozen grid")
        return dataset.read(1)


def build(selector, observations, output):
    if output.exists():
        raise FileExistsError("Preserve previous spatial plan output")
    manifest = json.loads(selector.read_text(encoding="utf-8"))
    if (
        manifest["status"] != "CLIFF_EROSION_PRESENTATION_SELECTOR_CANDIDATE"
        or manifest["geometry_mutation"]
        or manifest["canonical_landscape_mutation"]
    ):
        raise ValueError("Invalid selector authority")
    records = {row["path"]: row for row in manifest["outputs"]}
    arrays = {}
    for key in ("cliff", "scree"):
        name = key + "-candidate.tif"
        path = verified(selector.parent / name, records[name]["sha256"])
        arrays[key] = read_raster(path)
    for source in manifest["sources"]:
        verified(source["path"], source["sha256"])
    pcg_path = Path(manifest["sources"][1]["path"])
    pcg = json.loads(pcg_path.read_text(encoding="utf-8"))
    exclusion_record = next(
        row for row in pcg["outputs"] if row["path"] == "exclusion-reasons.tif"
    )
    exclusion = verified(
        pcg_path.parent / "exclusion-reasons.tif", exclusion_record["sha256"]
    )
    reasons = read_raster(exclusion)
    protected = (reasons & manifest["protected_reason_bits"]["mask"]) != 0
    masks = layers(arrays["cliff"], arrays["scree"], protected, (reasons & 1) != 0)
    for key in ("cliff", "scree"):
        if int(masks[key].sum()) != manifest["counts"][key + "_candidate_cells"]:
            raise ValueError("Selector count mismatch")
    data = json.loads(observations.read_text(encoding="utf-8"))
    verified(observations.parent / data["source_csv"], data["source_csv_sha256"])
    if any(place["surface_footprint"] is not None for place in data["places"]):
        raise ValueError("Unexpected registered surface: review before consuming")
    output.mkdir(parents=True)
    composite = np.full((4033, 4033, 3), COLORS["maintained"], dtype=np.uint8)
    images = [
        f'<rect x="-.25" y="-.25" width="2016.5" height="2016.5" fill="rgb{COLORS["maintained"]}"/>'
    ]
    for key, mask in masks.items():
        if key != "other_exclusions":
            composite[mask] = COLORS[key]
        rgba = np.zeros((4033, 4033, 4), dtype=np.uint8)
        rgba[mask, :3] = COLORS[key]
        rgba[mask, 3] = 255
        encoded = base64.b64encode(png_bytes(rgba)).decode("ascii")
        images.append(
            f'<image id="{key}" style="display:{"none" if key == "other_exclusions" else "inline"}" x="-.25" y="-.25" width="2016.5" height="2016.5" href="data:image/png;base64,{encoded}"/>'
        )
    observations_svg = []
    for window in data["windows"]:
        points = " ".join(f"{s['xy_m'][0]},{s['xy_m'][1]}" for s in window["stations"])
        observations_svg.append(
            f'<polyline points="{points}" fill="none" stroke="#e9edf2" stroke-width="1.5"/>'
        )
        for station in window["stations"]:
            x, y = station["xy_m"]
            observations_svg.append(
                f'<circle cx="{x}" cy="{y}" r="2" fill="white"><title>{html.escape(station["frame_id"])}</title></circle>'
            )
    places_svg = []
    cards = []
    for place in data["places"]:
        x, y = place["observation_xy_m"]
        ident = html.escape(place["proposal_id"])
        places_svg.append(
            f'<g><circle cx="{x}" cy="{y}" r="9" fill="none" stroke="white" stroke-width="3"/><text x="{x + 13}" y="{y - 8}" fill="white" font-size="20" paint-order="stroke" stroke="#17202a" stroke-width="4">{ident}</text></g>'
        )
        cards.append(
            f"<li><b>{ident}</b> {html.escape(place['title'])} — {html.escape('/'.join(place['displayed_observation_bands']))}; physical boundary unresolved.</li>"
        )
    counts = {key: int(mask.sum()) for key, mask in masks.items()}
    summary = {
        "schema_version": 1,
        "status": "SOURCE_BACKED_SPATIAL_DRAFT_NOT_PLACEMENT",
        "selector_fingerprint": manifest["fingerprint"],
        "selector_products": [
            records[name] for name in ("cliff-candidate.tif", "scree-candidate.tif")
        ],
        "sources": [
            {"path": str(selector), "sha256": digest(selector)},
            {"path": str(observations), "sha256": digest(observations)},
            {"path": str(exclusion), "sha256": digest(exclusion)},
            *manifest["sources"],
        ],
        "grid": manifest["grid"],
        "world_mapping": manifest["world_mapping"],
        "layers": {
            key: {"cells": value, "area_m2": value * 0.25, "label": LABELS[key]}
            for key, value in counts.items()
        },
        "protected_unknown_overlap_cells": int((protected & masks["unknown"]).sum()),
        "display_policy": "Protected shows pavement bit1 only; other hard presentation exclusions are a separate default-hidden layer. Candidate validation still uses all original protected bits.",
        "observation_stations": sum(len(w["stations"]) for w in data["windows"]),
        "disconnected_windows": len(data["windows"]),
        "physical_ABC_mapping": "UNRESOLVED",
        "texture_only_assignment": "NOT_ESTABLISHED",
        "qualified_assets": [],
        "placement": False,
        "geometry_mutation": False,
        "performance_pass": False,
    }
    (output / "spatial-plan.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    preview = Image.fromarray(composite).resize((1100, 1100), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(preview)

    def xy(point):
        return tuple((v + 0.25) / 2016.5 * 1100 for v in point)

    for window in data["windows"]:
        points = [xy(s["xy_m"]) for s in window["stations"]]
        if len(points) > 1:
            draw.line(points, fill="white", width=1)
    for place in data["places"]:
        x, y = xy(place["observation_xy_m"])
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), outline="white", width=2)
        draw.text(
            (x + 6, y),
            place["proposal_id"],
            fill="white",
            stroke_fill="black",
            stroke_width=1,
        )
    preview.save(output / "spatial-plan.png")
    legend = "".join(
        f'<label><input type="checkbox" {"" if key == "other_exclusions" else "checked"} data-layer="{key}"><i style="background:rgb{COLORS[key]}"></i>{LABELS[key]}<small>{counts[key]:,} cells · {counts[key] * 0.25:,.2f} m²</small></label>'
        for key in masks
    )
    hashes = "".join(
        f"<li>{html.escape(Path(s['path']).name)}<code>{s['sha256']}</code></li>"
        for s in summary["sources"]
    )
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><title>Sa Calobra spatial treatment draft</title><style>body{margin:0;background:#17202a;color:#eef2f6;font:15px system-ui}header,aside{padding:22px}h1{margin:0 0 8px;font-size:25px}main{display:grid;grid-template-columns:minmax(500px,1fr) 390px}svg{width:100%;height:80vh;background:#26323d;touch-action:none;image-rendering:pixelated}label{display:block;margin:16px 0}small{display:block;margin-left:24px;color:#bdc8d3}i{display:inline-block;width:13px;height:13px;margin:0 8px}code{display:block;font-size:10px;overflow-wrap:anywhere}button{margin:6px;padding:8px}li{margin:10px 0}.notice{color:#ffd380}@media(max-width:900px){main{display:block}}</style><header><h1>Sa Calobra — where to investigate rock treatment</h1><div class="notice">Draft source-derived candidates, not geological truth or placement permission. Landscape and roads stay fixed.</div><p>North up · X east / Y south · 0.5 m cells · EPSG:25831 · 2,016.5 m square. Pan by dragging; use zoom buttons. Hover a white observation dot for its original frame ID.</p><button onclick="zoom(.7)">Zoom +</button><button onclick="zoom(1.4)">Zoom −</button><button onclick="reset()">Reset</button><span id="position"></span></header><main><section><svg id="map" viewBox="-.25 -.25 2016.5 2016.5">IMAGES<g id="observations">OBSERVATIONS</g><g id="cards">CARDS</g></svg></section><aside><h2>Physical raster areas</h2>LEGEND<label><input type="checkbox" checked data-layer="observations">Road observation stations</label><label><input type="checkbox" checked data-layer="cards">Six historical proposal anchors</label><p>White lines only connect samples within each of 185 windows; they are not continuous road geometry. A/B/C are viewing needs: physical surface boundaries remain unresolved. No texture-only or hidden-D region is inferred.</p><details><summary>Existing observation cards</summary><ul>CARDLIST</ul></details><details><summary>Authenticated source hashes</summary><ul>HASHES</ul></details><p>Keep exclusions and unknowns visible when making decisions. Layer hiding changes this display only. Scree candidates still require asset contact qualification and footprint clearance; cliff candidates require separate mesh/presentation review.</p></aside></main><script>const map=document.getElementById('map');let box=[-.25,-.25,2016.5,2016.5],drag;function update(){map.setAttribute('viewBox',box.join(' '))}function zoom(f){box=[box[0]+box[2]*(1-f)/2,box[1]+box[3]*(1-f)/2,box[2]*f,box[3]*f];update()}function reset(){box=[-.25,-.25,2016.5,2016.5];update()}document.querySelectorAll('[data-layer]').forEach(e=>e.onchange=()=>document.getElementById(e.dataset.layer).style.display=e.checked?'':'none');function point(e){return new DOMPoint(e.clientX,e.clientY).matrixTransform(map.getScreenCTM().inverse())}map.onpointerdown=e=>{drag=point(e);map.setPointerCapture(e.pointerId)};map.onpointermove=e=>{let p=point(e);document.getElementById('position').textContent=`X ${p.x.toFixed(2)} m / Y ${p.y.toFixed(2)} m`;if(drag){box[0]+=drag.x-p.x;box[1]+=drag.y-p.y;update()}};map.onpointerup=()=>drag=null;map.onpointercancel=()=>drag=null;</script></html>"""
    for token, content in {
        "IMAGES": "".join(images),
        "OBSERVATIONS": "".join(observations_svg),
        "CARDS": "".join(places_svg),
        "LEGEND": legend,
        "CARDLIST": "".join(cards),
        "HASHES": hashes,
    }.items():
        page = page.replace(token, content)
    (output / "spatial-plan.html").write_text(page, encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector-manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.selector_manifest, args.observations, args.output)
    print(json.dumps({"status": result["status"], "layers": result["layers"]}))
