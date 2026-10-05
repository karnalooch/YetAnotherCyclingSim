"""Author three pale limestone-family candidates with the existing MM pipeline.

Each directory uses the established channel filenames so the same validator and
bounded UE importer can consume it. These are artistic 2 m tiles, not scans.
"""

import argparse
import hashlib
import json
from pathlib import Path

import build_material_maker_limestone as base


PROFILES = {
    "fractured": ("Fractured limestone", 41, 0.71, 0.90),
    "scree": ("Loose limestone fragments", 67, 0.70, 0.80),
    "mineral": ("Fine mineral ground", 89, 0.68, 0.65),
}

# All cell counts are integral: the underlying field repeats exactly at 2 m.
# Colour contains mineral variation, not baked directional illumination.
SCREE = r"""
vec3 yacs_fragments(vec2 uv, float count, float seed) {
    vec2 p = uv*count;
    vec2 origin = floor(p);
    vec2 local = fract(p);
    vec3 result = vec3(0.0);
    for (int y=-1; y<=1; y++) {
        for (int x=-1; x<=1; x++) {
            vec2 offset = vec2(float(x),float(y));
            vec2 index = mod(origin+offset,count);
            float id = yacs_hash(index,seed+5.0);
            vec2 center = vec2(yacs_hash(index,seed),yacs_hash(index,seed+7.0));
            vec2 d = local-offset-0.1-0.8*center;
            float angle = 6.2831853*yacs_hash(index,seed+9.0);
            d = mat2(cos(angle),-sin(angle),sin(angle),cos(angle))*d;
            d.x *= mix(0.75,1.7,yacs_hash(index,seed+13.0));
            float radius = mix(0.15,0.47,id);
            float distance = max(abs(d.x)*0.85+abs(d.y)*0.38,
                                 abs(d.y)*0.91+abs(d.x)*0.20)/radius;
            float mask = 1.0-smoothstep(0.70,1.0,distance);
            float top = clamp(0.85-0.27*distance+0.3*d.x,0.0,1.0);
            float h = mask*top*mix(0.3,1.0,id);
            if (h > result.x) result = vec3(h,mask,id);
        }
    }
    return result;
}
vec4 yacs_limestone(vec2 uv, float seed, float fractures, float pores) {
    vec2 warp = vec2(yacs_noise(uv,8.0,seed),yacs_noise(uv,8.0,seed+3.0))-0.5;
    vec2 q = uv+0.014*warp;
    vec3 stones = yacs_fragments(q,21.0,seed+11.0);
    vec3 small = yacs_fragments(q,53.0,seed+71.0);
    vec3 grit = yacs_fragments(q,113.0,seed+91.0);
    float chips = yacs_noise(q,127.0,seed+19.0);
    float grain = yacs_noise(q,383.0,seed+29.0);
    float variation = yacs_noise(q,5.0,seed+31.0);
    float height = 0.32 + max(0.18*stones.x,0.065*small.x)+0.012*grit.x;
    height += 0.019*(chips-0.5)+0.008*(grain-0.5);
    float coverage = max(stones.y,small.y);
    return vec4(height,0.25*(1.0-coverage),0.0,
        clamp(0.5+0.30*(stones.z-0.5)*stones.y+0.12*coverage
        +0.18*(variation-0.5),0.0,1.0));
}
"""

MINERAL = r"""
vec4 yacs_limestone(vec2 uv, float seed, float fractures, float pores) {
    vec2 warp = vec2(yacs_noise(uv,11.0,seed),yacs_noise(uv,11.0,seed+3.0))-0.5;
    vec2 q = uv+0.01*warp;
    vec3 stones = yacs_cells(q,73.0,seed+11.0);
    float radius = mix(0.12,0.35,stones.z);
    float pebble = (1.0-smoothstep(0.02,radius,stones.x));
    pebble *= smoothstep(0.68,0.85,stones.z);
    float fine = yacs_noise(q,191.0,seed+41.0);
    float grain = yacs_noise(q,487.0,seed+47.0);
    float variation = yacs_noise(q,7.0,seed+31.0);
    float middle = yacs_noise(q,37.0,seed+51.0);
    float height = 0.45 + 0.055*pebble + 0.016*(middle-0.5);
    height += 0.017*(fine-0.5)+0.009*(grain-0.5);
    return vec4(height,0.0,0.0,
        clamp(0.5+0.25*(variation-0.5)+0.32*(middle-0.5)+0.22*pebble,0.0,1.0));
}
"""


def build(mm_dir, destination, profile):
    label, seed, brightness, normal_strength = PROFILES[profile]
    base.build(mm_dir, destination)
    graph_path = destination / "SaCalobra_PaleLimestone.ptex"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    graph["name"] = "SaCalobra " + label
    graph["seed_int"] = seed
    nodes = {node["name"]: node for node in graph["nodes"]}
    shape = nodes["Limestone_Form"]
    shape["parameters"].update(seed=seed, fractures=1.4, pores=1.1)
    shape["shader_model"]["name"] = label
    if profile != "fractured":
        helpers = base.FIELD.split("vec4 yacs_limestone(", 1)[0]
        shape["shader_model"]["global"] = helpers + (
            SCREE if profile == "scree" else MINERAL
        )
    else:
        # Interrupted fractures at two scales; do not impose horizontal strata.
        shape["shader_model"]["global"] = base.FIELD.replace(
            "q,7.0,seed+11.0", "q,11.0,seed+11.0"
        ).replace("0.065*crack+0.04*shoulder", "0.085*crack+0.05*shoulder")
    color = nodes["Limestone_Color"]
    color["parameters"]["brightness"] = brightness
    color["shader_model"]["name"] = label + " neutral albedo"
    color["shader_model"]["code"] = (
        "float $(name_uv)_tone = clamp($brightness+0.20*($variation($uv)-0.5)"
        "-0.018*$crack($uv)-0.012*$pore($uv),0.0,1.0);"
    )
    nodes["Height_Normal"]["parameters"]["strength"] = normal_strength
    graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    receipt_path = destination / "provenance.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update(
        profile=profile,
        label=label,
        graph_sha256=hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        recipe="scripts/assets/build_material_maker_surface_set.py",
        seed=seed,
        placement="Unassigned artistic sample; no inferred terrain domains",
    )
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-maker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, required=True)
    args = parser.parse_args()
    build(args.material_maker, args.output, args.profile)
