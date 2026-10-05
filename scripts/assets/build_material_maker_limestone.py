"""Build the bounded Sa Calobra limestone candidate for Material Maker 1.7.

The PBR output node is adapted from the user's installed MIT Material Maker.
Its exact bytes and notice are retained beside the generated graph. No UE writes.
"""

import argparse
import hashlib
import json
from pathlib import Path


FIELD = r"""
float yacs_hash(vec2 p, float salt) {
    return fract(sin(dot(p, vec2(127.13, 311.71)) + salt * 37.19) * 43758.5453);
}
vec2 yacs_gradient(vec2 p, float salt) {
    float angle = 6.28318530718*yacs_hash(p,salt);
    return vec2(cos(angle),sin(angle));
}
float yacs_noise(vec2 uv, float cells, float salt) {
    vec2 p = uv * cells;
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 weight = f*f*f*(f*(f*6.0-15.0)+10.0);
    float a = dot(yacs_gradient(mod(i,cells),salt),f);
    float b = dot(yacs_gradient(mod(i+vec2(1.0,0.0),cells),salt),f-vec2(1.0,0.0));
    float c = dot(yacs_gradient(mod(i+vec2(0.0,1.0),cells),salt),f-vec2(0.0,1.0));
    float d = dot(yacs_gradient(mod(i+vec2(1.0),cells),salt),f-vec2(1.0));
    return 0.5+0.7*mix(mix(a,b,weight.x),mix(c,d,weight.x),weight.y);
}
vec3 yacs_cells(vec2 uv, float count, float salt) {
    vec2 p = uv*count;
    vec2 origin = floor(p);
    vec2 local = fract(p);
    float first = 100.0;
    float second = 100.0;
    float cell_id = 0.0;
    for (int y=-1; y<=1; y++) {
        for (int x=-1; x<=1; x++) {
            vec2 offset = vec2(float(x),float(y));
            vec2 index = mod(origin+offset,count);
            vec2 point = vec2(yacs_hash(index,salt),yacs_hash(index,salt+7.0));
            vec2 delta = offset+0.15+0.7*point-local;
            float distance2 = dot(delta,delta);
            if (distance2 < first) {
                second = first;
                first = distance2;
                cell_id = yacs_hash(index,salt+19.0);
            } else {
                second = min(second,distance2);
            }
        }
    }
    return vec3(sqrt(first),sqrt(second)-sqrt(first),cell_id);
}
vec4 yacs_limestone(vec2 uv, float seed, float fractures, float pores) {
    vec2 warp = vec2(yacs_noise(uv,8.0,seed),yacs_noise(uv,8.0,seed+3.0))-0.5;
    vec2 detail_warp = vec2(yacs_noise(uv,24.0,seed+5.0),yacs_noise(uv,24.0,seed+9.0))-0.5;
    vec2 q = uv+0.025*warp+0.004*detail_warp;
    vec3 slab = yacs_cells(q,7.0,seed+11.0);
    float variation = yacs_noise(q,4.0,seed+31.0);
    float middle = yacs_noise(q,32.0,seed+41.0);
    float fine = yacs_noise(q,128.0,seed+47.0);
    float grain = yacs_noise(q,384.0,seed+51.0);
    float width = mix(0.013,0.045,yacs_noise(q,16.0,seed+13.0));
    float crack = 1.0-smoothstep(0.0,width,slab.y);
    float shoulder = 1.0-smoothstep(0.01,0.16,slab.y);
    float broken = smoothstep(0.42,0.65,yacs_noise(q,12.0,seed+17.0));
    crack *= broken;
    shoulder *= broken;
    vec3 secondary = yacs_cells(q,19.0,seed+83.0);
    float small_cracks = (1.0-smoothstep(0.0,0.055,secondary.y));
    small_cracks *= smoothstep(0.50,0.72,yacs_noise(q,20.0,seed+85.0));
    vec3 holes = yacs_cells(q,91.0,seed+61.0);
    float pits = (1.0-smoothstep(0.015,0.15,holes.x))*smoothstep(0.72,0.87,holes.z);
    float flakes = smoothstep(0.18,0.52,abs(2.0*middle-1.0));
    float chips = smoothstep(0.18,0.52,abs(2.0*yacs_noise(q,69.0,seed+67.0)-1.0));
    float height = 0.55 + 0.10*(variation-0.5) + 0.065*(middle-0.5);
    height += 0.030*(fine-0.5) + 0.011*(grain-0.5);
    height -= fractures*(0.065*crack+0.04*shoulder+0.024*small_cracks);
    height -= pores*0.022*pits + 0.042*flakes+0.018*chips;
    return vec4(clamp(height,0.0,1.0),max(crack,0.45*small_cracks),pits,
                clamp(0.42*variation+0.35*middle+0.23*fine,0.0,1.0));
}
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar(name, label, value, low, high, step=0.01):
    return dict(
        name=name,
        label=label,
        shortdesc=label,
        type="float",
        default=value,
        min=low,
        max=high,
        step=step,
        control="None",
    )


def shader(name, title, x, y, inputs, outputs, parameters=(), code="", global_code=""):
    return {
        "name": name,
        "type": "shader",
        "node_position": {"x": x, "y": y},
        "parameters": {p["name"]: p["default"] for p in parameters},
        "shader_model": {
            "name": title,
            "inputs": inputs,
            "outputs": outputs,
            "parameters": list(parameters),
            "code": code,
            "instance": "",
            "global": global_code,
        },
    }


def source(name, kind="f", default="0.0"):
    return dict(name=name, type=kind, default=default, label=name, function=True)


def output(name, expression, kind="f"):
    return {"type": kind, kind: expression, "shortdesc": name}


def build(mm_dir, destination):
    destination.mkdir(parents=True, exist_ok=True)
    graph_path = destination / "SaCalobra_PaleLimestone.ptex"
    if graph_path.exists():
        raise FileExistsError(
            "Use a new candidate directory; never replace an accepted graph"
        )
    material_source = mm_dir / "nodes/material.mmg"
    material = json.loads(material_source.read_text(encoding="utf-8"))
    material.update(name="PBR_Output", node_position={"x": 1040, "y": 100})
    material["parameters"].update(
        size=11, metallic=0, depth_scale=0, flags_transparent=False, normal=1
    )
    profiles = {"BaseColor.png": 0, "ORM.png": 1, "Normal_DX.png": 10, "Height.exr": 8}
    material["shader_model"]["exports"] = {
        "YACS/Textures": {
            "name": "YACS/Textures",
            "files": [
                {
                    "type": "texture",
                    "file_name": "$(path_prefix)_" + suffix,
                    "output": index,
                }
                for suffix, index in profiles.items()
            ],
        }
    }
    shape = shader(
        "Limestone_Form",
        "Limestone: fractures and weathering",
        0,
        0,
        [],
        [
            output("Height", "$(name_uv)_field.r"),
            output("Fractures", "$(name_uv)_field.g"),
            output("Pores", "$(name_uv)_field.b"),
            output("Variation", "$(name_uv)_field.a"),
        ],
        [
            scalar("seed", "Seed", 23, 1, 999, 1),
            scalar("fractures", "Fracture depth", 0.85, 0, 2),
            scalar("pores", "Pore depth", 0.8, 0, 2),
        ],
        "vec4 $(name_uv)_field = yacs_limestone($uv,$seed,$fractures,$pores);",
        FIELD,
    )
    color = shader(
        "Limestone_Color",
        "Pale neutral limestone",
        420,
        -220,
        [source("crack"), source("pore"), source("variation")],
        [
            output(
                "Base Color",
                "vec3($(name_uv)_tone+0.002,$(name_uv)_tone+0.003,$(name_uv)_tone+0.004)",
                "rgb",
            )
        ],
        [scalar("brightness", "Brightness (sRGB)", 0.72, 0.5, 0.85)],
        "float $(name_uv)_tone = clamp($brightness+0.12*($variation($uv)-0.5)"
        "-0.055*$crack($uv)-0.016*$pore($uv),0.0,1.0);",
    )
    response = shader(
        "Limestone_Response",
        "Roughness and shallow cavity",
        420,
        130,
        [source("crack"), source("pore"), source("variation"), source("height")],
        [
            output(
                "Roughness", "clamp(0.74+0.09*$variation($uv)+0.04*$pore($uv),0.0,1.0)"
            ),
            output("AO", "clamp(1.0-0.16*$crack($uv)-0.12*$pore($uv),0.0,1.0)"),
            output("Depth", "1.0-$height($uv)"),
        ],
    )
    normal = {
        "name": "Height_Normal",
        "type": "normal_map2",
        "node_position": {"x": 450, "y": 450},
        "parameters": {"size": 11, "strength": 0.85, "buffer": 1, "param2": 0},
    }
    nodes = [shape, color, response, normal, material]
    connections = []

    def connect(a, ai, b, bi):
        connections.append({"from": a, "from_port": ai, "to": b, "to_port": bi})

    for i, port in enumerate((1, 2, 3)):
        connect("Limestone_Form", port, "Limestone_Color", i)
        connect("Limestone_Form", port, "Limestone_Response", i)
    connect("Limestone_Form", 0, "Limestone_Response", 3)
    connect("Limestone_Form", 0, "Height_Normal", 0)
    # Resolve ports against the actual installed PBR node, never hardcode indices.
    ports = {p["name"]: i for i, p in enumerate(material["shader_model"]["inputs"])}
    for node, index, port in [
        ("Limestone_Color", 0, "albedo_tex"),
        ("Limestone_Response", 0, "roughness_tex"),
        ("Limestone_Response", 1, "ao_tex"),
        ("Limestone_Response", 2, "depth_tex"),
        ("Height_Normal", 0, "normal_tex"),
    ]:
        connect(node, index, "PBR_Output", ports[port])
    graph = {
        "type": "graph",
        "name": "SaCalobra Pale Limestone",
        "parameters": {},
        "seed_int": 2301,
        "nodes": nodes,
        "connections": connections,
    }
    graph_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    notice = (
        Path(__file__).resolve().parents[2]
        / "docs/legal/notices/material-maker-MIT.txt"
    )
    (destination / "MATERIAL_MAKER_LICENSE.txt").write_bytes(notice.read_bytes())
    receipt = {
        "status": "graph_ready_render_pending",
        "tile_metres": 2.0,
        "graph": str(graph_path),
        "graph_sha256": sha(graph_path),
        "tool": "Material Maker 1.7",
        "tool_exe_sha256": sha(mm_dir / "material_maker.exe"),
        "adapted_source": "nodes/material.mmg",
        "adapted_source_sha256": sha(material_source),
        "upstream": "https://github.com/RodZill4/material-maker",
        "license": "MIT",
        "notice": "MATERIAL_MAKER_LICENSE.txt",
        "expected_maps": list(profiles),
        "normal_convention": "DirectX",
        "scope": "procedural artistic candidate; not a geological scan; no world mutation",
    }
    (destination / "provenance.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(graph_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--material-maker", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.material_maker, args.output)
