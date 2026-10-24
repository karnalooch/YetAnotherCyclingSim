"""Produce the verified portion of PEG-05 L13 through official UE toolsets.

This is the body of ProgrammaticToolset.execute_tool_script, not an Unreal
Python entrypoint. The host provides execute_tool; only json/re are imported.
The orchestrator must first read get_execution_environment and the schemas in
Saved/correct-owner-world-20261024. This file never assigns a material to an
actor, changes a Landscape, saves a map, imports a texture or edits a source
asset. Existing destination assets are never overwritten.

MODE='preflight' is read-only. 'author_surface' creates an unassigned material
with the verified triplanar PBR, slope blend and all three Cd-color overlays.
RGB and final opacity values were read in official L04/L13 source frames, not
estimated from swatch pixels. 'author_complete' remains blocked until actual
consumer RVT assets and the final blend are proved. No partial graph is claimed
to be the completed L13 material or byte-identical to the original textures.

Sources: https://www.sidefx.com/tutorials/project-pegasus-cliff-generation/
L13 official mirror: https://www.youtube.com/watch?v=XeQqHUrjvI0
L04 official mirror: https://www.youtube.com/watch?v=jp5S76eleE8
Original L13 captions: https://captions.vimeo.com/captions/122485596.vtt
See SOURCE_MAP below for exact times. ASR is not proof of an unreadable number.
"""

# ruff: noqa: F821
import json
import re


def material_create(folder, name):
    return execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.create_material",
        json.dumps({"folder_path": folder, "asset_name": name}),
    )["returnValue"]


def expression_add(material, kind, x, y):
    return execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.add_expression",
        json.dumps({"material_or_function": material,
                    "expression_class": {"refPath": "/Script/Engine." + kind},
                    "x": x, "y": y}),
    )["returnValue"]


def expression_inputs(expression):
    return execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.get_expression_input_names",
        json.dumps({"expression": expression}),
    )["returnValue"]


def expression_outputs(expression):
    return execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.get_expression_output_names",
        json.dumps({"expression": expression}),
    )["returnValue"]


def expression_connect(source, output, target, input_name):
    execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.connect_expressions",
        json.dumps({"from_expression": source, "from_output_name": output,
                    "to_expression": target, "to_input_name": input_name}),
    )


def expression_wiring(material, expression):
    return execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.get_expression_inputs",
        json.dumps({"material_or_function": material, "expression": expression}),
    )["returnValue"]


def material_output(expression):
    execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.connect_to_output",
        json.dumps({"expression": expression, "output_name": "",
                    "material_property": "MP_MaterialAttributes"}),
    )


def material_output_read(material):
    return execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.get_property_input",
        json.dumps({"material": material,
                    "material_property": "MP_MaterialAttributes"}),
    )["returnValue"]


def material_compile(material):
    execute_tool(
        "editor_toolset.toolsets.material.MaterialTools.recompile",
        json.dumps({"material_or_function": material}),
    )


def properties_list(instance):
    return json.loads(execute_tool(
        "editor_toolset.toolsets.object.ObjectTools.list_properties",
        json.dumps({"instance": instance}),
    )["returnValue"])


def properties_set(instance, values):
    if not execute_tool(
        "editor_toolset.toolsets.object.ObjectTools.set_properties",
        json.dumps({"instance": instance, "values": json.dumps(values)}),
    )["returnValue"]:
        raise RuntimeError("Native property assignment returned false: "
                           + instance["refPath"])


def properties_get(instance, names):
    return json.loads(execute_tool(
        "editor_toolset.toolsets.object.ObjectTools.get_properties",
        json.dumps({"instance": instance, "properties": names}),
    )["returnValue"])


def assets_find(folder, name):
    return execute_tool(
        "editor_toolset.toolsets.asset.AssetTools.find_assets",
        json.dumps({"folder_path": folder, "name": name, "recursive": False}),
    )["returnValue"]


def asset_load(path):
    return execute_tool(
        "editor_toolset.toolsets.asset.AssetTools.load_asset",
        json.dumps({"asset_path": path}),
    )["returnValue"]


def asset_save(path):
    if not execute_tool(
        "editor_toolset.toolsets.asset.AssetTools.save_assets",
        json.dumps({"asset_paths": [path]}),
    )["returnValue"]:
        raise RuntimeError("Native save returned false: " + path)


MODE = "preflight"
SAVE_CANDIDATE = False
DESTINATION = "/Game/Generated/YACS/PegasusCliffs/Materials"
ASSET_NAME = "M_Cliff_Pegasus_L13_Confirmed_20261024"

# These are the current, owner-accepted appearance inputs. Their package names
# do not establish that their bytes are the Megascans scans shown in L13.
TEXTURES = {
    "01": {
        "BaseColor": "/Game/Megascans/Surfaces/Mossy_Ground_tkekcgfn/T_0_forest_leaves_02_Colour",
        "Normal": "/Game/Megascans/Surfaces/Mossy_Ground_tkekcgfn/T_0_forest_leaves_02_Normal",
        "ORDP": "/Game/Megascans/Surfaces/Mossy_Ground_tkekcgfn/T_0_forest_leaves_02_Masks",
    },
    "02": {
        "BaseColor": "/Game/Megascans/Surfaces/Layered_Rock_Cliff_ultncbnlw/T_3_marble_cliff_02_Colour",
        "Normal": "/Game/Megascans/Surfaces/Layered_Rock_Cliff_ultncbnlw/T_3_marble_cliff_02_Normal",
        "ORDP": "/Game/Megascans/Surfaces/Layered_Rock_Cliff_ultncbnlw/T_3_marble_cliff_02_Masks",
    },
}
# L13 uses ORDP.G for roughness only, not AO/displacement shader connections.
# Accepted consumer proof: Saved/cliff-material-native-20261024/
# accepted-roughness-graph.json: MF_PE_Material.Roughness <-
# BreakOutFloat3Components.G. No texture bytes or channel packing were changed.
MASK_GREEN_ROUGHNESS_VERIFIED = True
# Verified in Saved/argon-handoff-20261024/argon-first-readback.json: all six
# accepted textures are non-VT (virtualTextureStreaming=false) with TC_Default
# (sRGB=true), TC_Normalmap (sRGB=false), and TC_Masks (sRGB=false), matching
# SAMPLERTYPE_Color, SAMPLERTYPE_Normal, and SAMPLERTYPE_Masks in _pbr.
ACCEPTED_TEXTURE_VT_SETTINGS_VERIFIED = True

FUNCTIONS = {
    "WorldAlignedTexture": "/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedTexture",
    "WorldAlignedNormal": "/Engine/Functions/Engine_MaterialFunctions01/Texturing/WorldAlignedNormal",
    "FlattenNormal": "/Engine/Functions/Engine_MaterialFunctions01/Texturing/FlattenNormal",
    "CheapContrast_RGB": "/Engine/Functions/Engine_MaterialFunctions01/ImageAdjustment/CheapContrast_RGB",
    "CheapContrast": "/Engine/Functions/Engine_MaterialFunctions01/ImageAdjustment/CheapContrast",
    "HueShift": "/Engine/Functions/Engine_MaterialFunctions02/HueShift",
}

SOURCE_MAP = {
    "attributes": "L04 00:24-00:58; L13 00:23-01:22: Make/BlendMaterialAttributes",
    "triplanar": "L13 02:55-04:58: texture objects, WorldAlignedTexture/Normal, XYZ outputs",
    "texture_size": "L13 04:59-05:56,16:24-16:48: (1,1,1)*100*MapTiling, MapTiling=10, all six projections",
    "base_color": "L13 06:00-09:19,12:36-13:24: Desaturation(1-Saturation), CheapContrast_RGB, HueShift, Multiply Brightness",
    "normal": "L13 10:04-10:53: WorldAlignedNormal.XYZ -> FlattenNormal; Flatness=1-NormalIntensity",
    "roughness": "L13 10:54-12:16: WorldAlignedTexture(ORDP).XYZ -> G -> Multiply RoughnessIntensity",
    "rock_branch": "L13 13:37-16:48: duplicate grass PBR branch as 02 with cliff textures",
    "slope": "L13 16:50-18:48: raw cliff WorldAlignedNormal.XYZ -> Transform TangentToWorld -> B -> SmoothStep; Min=.6 Max=.8",
    "blend_order": "L04 05:11-05:19: cliff=A, grass=B, slope alpha",
    "Cd_export": "L03 18:23-21:42: R convexity, G concavity, B AO; Cd becomes UE vertex color",
    "Cd_masks": "L13 22:12-23:44,25:57-26:14,27:25-29:42: Power -> Multiply -> CheapContrast -> Multiply Opacity",
    "Cd_overlays": "L13 24:00-25:31: base -> AO(1-B) -> convexity(R) -> concavity(G) -> rock BaseColor",
    "mask_values": "L13 final frames30:36/32:53: convexity .5/1/.1/1, AO .4/2/.1/.5, concavity .5/2/.1/.6; earlier spoken/demo values are superseded",
    "overlay_rgb": "L04 frame04:27 and L13 frame00:40: exact displayed linear RGB, all three constants; L13 32:53 retains matching vector parameters",
    "RVT": "L13 frames35:55/37:15: SmoothStep.Value=WorldPosition.Z-RVT.WorldHeight, source Min=0 Max=1; landscape RVT attributes A, cliff/grass B (corrected37:04). Source MI at37:46 uses Min=1.701348 Max=130.948547cm; actual consumer RVT assets unproved",
}

# Linear values as displayed to six decimal places in the source UI. Display
# precision is the recoverable precision; original float32 bytes are unavailable.
OVERLAY_VALUES = {
    "OcclusionColor": [0.0625, 0.052529, 0.05013, 1.0],
    "ConvexityColor": [0.322917, 0.296007, 0.296007, 1.0],
    "ConcavityColor": [0.078125, 0.02874, 0.018584, 1.0],
    "OcclusionOpacity": 0.5,
    "ConcavityOpacity": 0.6,
}
OVERLAY_EVIDENCE = {
    "OcclusionColor": "Saved/asphalt-research-20261024/source-L04-267s.png + source-L13-40s.png",
    "ConvexityColor": "Saved/asphalt-research-20261024/source-L04-267s.png + source-L13-40s.png",
    "ConcavityColor": "Saved/asphalt-research-20261024/source-L04-267s.png + source-L13-40s.png",
    "OcclusionOpacity": "Saved/asphalt-research-20261024/source-L13-1973s.png",
    "ConcavityOpacity": "Saved/asphalt-research-20261024/source-L13-1836s.png + source-L13-1973s.png",
}


def _normal(name):
    return re.sub("[^a-z0-9]", "", name.lower())


def _parameter_name(label):
    prefix = ""
    match = re.match(r"^(0[12])(.+)$", label)
    if match:
        prefix, label = str(int(match.group(1))) + ". ", match.group(2)
    names = {
        "BaseColor": "BaseColor", "ORDP": "ORDp",
        "BaseColorSaturation": "BaseColor Saturation",
        "BaseColorContrast": "BaseColor Contrast",
        "BaseColorHue": "BaseColor Hue",
        "BaseColorBrightness": "BaseColor Brightness",
    }
    return prefix + names.get(label, re.sub(r"(?<=[a-z])(?=[A-Z])", " ", label))


def _resolve(names, expected):
    if expected in names:
        return expected
    # Material functions may append their native type to a displayed pin name.
    # L13's native projection functions label their texture input 'Tex';
    # Epic's documentation also calls this input TextureObject. Both names
    # denote the existing native pin, never a fabricated function signature.
    # Stock UE MaterialExpression nodes (OneMinus, Desaturation, ComponentMask,
    # Transform) leave their unnamed primary FExpressionInput pin as FName("None").
    aliases = ([expected, "Tex"] if expected == "TextureObject" else
               [expected, "None"] if expected == "Input" else [expected])
    matches = [n for n in names if any(
        _normal(n.split(" (")[0]) == _normal(alias) for alias in aliases)]
    if len(matches) != 1:
        raise RuntimeError("Expected one native field/pin " + repr(expected)
                           + "; available=" + repr(names))
    return matches[0]


def _package(path):
    return path.split(".")[0]


def _same(expected, actual):
    # Reflected scalar/LinearColor fields use float32; JSON input uses double.
    if isinstance(expected, float) and isinstance(actual, (int, float)):
        return abs(expected - actual) <= max(1e-6, abs(expected) * 1e-6)
    if isinstance(expected, dict) and isinstance(actual, dict):
        return set(expected) == set(actual) and all(
            _same(value, actual[key]) for key, value in expected.items())
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            _same(a, b) for a, b in zip(expected, actual))
    return expected == actual


def _load_exact(path):
    folder, name = path.rsplit("/", 1)
    matches = [p for p in assets_find(folder, name) if _package(p) == path]
    if len(matches) != 1:
        raise RuntimeError("Expected one existing dependency: " + path
                           + "; found=" + repr(matches))
    loaded = asset_load(matches[0])
    if _package(loaded["refPath"]) != path:
        raise RuntimeError("Unexpected loaded dependency: " + repr(loaded))
    return loaded


class Graph:
    def __init__(self, material):
        self.material = material
        self.nodes = {}
        self.kinds = {}
        self.schemas = {}
        self.pins = {}
        self.outputs = {}
        self.edges = []
        self.values = {}

    def set(self, instance, kind, values):
        if kind not in self.schemas:
            schema = properties_list(instance)
            self.schemas[kind] = list(schema)
        resolved = {_resolve(self.schemas[kind], k): v for k, v in values.items()}
        properties_set(instance, resolved)
        actual = properties_get(instance, list(resolved))
        if not _same(resolved, actual):
            raise RuntimeError("Native property readback differs: "
                               + json.dumps({"expected": resolved, "actual": actual}))

    def node(self, name, kind, properties=None):
        if name in self.nodes:
            raise RuntimeError("Duplicate graph label: " + name)
        index = len(self.nodes)
        result = expression_add(self.material, "MaterialExpression" + kind,
                                -4200 + (index % 12) * 340, (index // 12) * 420)
        self.nodes[name] = result
        self.kinds[name] = kind
        if properties:
            self.set(result, kind, properties)
            self.values[name] = properties
        return name

    def link(self, source, target, input_name, output=""):
        if target not in self.pins:
            self.pins[target] = expression_inputs(self.nodes[target])
        pin = _resolve(self.pins[target], input_name)
        if output:
            if source not in self.outputs:
                self.outputs[source] = expression_outputs(self.nodes[source])
            output = _resolve(self.outputs[source], output)
        expression_connect(self.nodes[source], output, self.nodes[target], pin)
        self.edges = [e for e in self.edges
                      if not (e["to"] == target and e["input"] == pin)]
        self.edges.append({"from": source, "output": output,
                           "to": target, "input": pin})

    def fn(self, name, function, dependencies):
        result = self.node(name, "MaterialFunctionCall",
                           {"MaterialFunction": dependencies[function]})
        # PostEditChangeProperty must have rebuilt the native function pins.
        self.pins[result] = expression_inputs(self.nodes[result])
        if not self.pins[result]:
            raise RuntimeError("Function property did not refresh native pins: " + function)
        return result

    def scalar(self, name, value, group, lower=0.0, upper=0.0):
        return self.node(name, "ScalarParameter", {
            "ParameterName": _parameter_name(name), "DefaultValue": float(value), "Group": group,
            "SliderMin": float(lower), "SliderMax": float(upper),
        })

    def unary(self, name, kind, source, output=""):
        result = self.node(name, kind)
        self.link(source, result, "Input", output)
        return result

    def multiply(self, name, a, b, output_a=""):
        result = self.node(name, "Multiply")
        self.link(a, result, "A", output_a)
        self.link(b, result, "B")
        return result

    def verify(self):
        actual_by_node = {}
        for name in {e["to"] for e in self.edges}:
            actual_by_node[name] = expression_wiring(self.material, self.nodes[name])
        for edge in self.edges:
            matches = [v for v in actual_by_node[edge["to"]]
                       if v["input_name"] == edge["input"]]
            if len(matches) != 1 or matches[0]["expression"] != self.nodes[edge["from"]]:
                raise RuntimeError("Native wiring readback differs: " + json.dumps(edge))
        return actual_by_node


def _pbr(graph, prefix, dependencies, texture_refs, texture_size):
    group = str(int(prefix)) + ". Parameters"
    maps = str(int(prefix)) + ". Maps"
    projected = {}
    for channel in ("BaseColor", "Normal", "ORDP"):
        name = prefix + channel
        texture = graph.node(name, "TextureObjectParameter", {
            "ParameterName": _parameter_name(name), "Texture": texture_refs[prefix][channel],
            "SamplerType": "SAMPLERTYPE_Normal" if channel == "Normal" else
                           "SAMPLERTYPE_Masks" if channel == "ORDP" else "SAMPLERTYPE_Color",
            "Group": maps,
        })
        fn = graph.fn(name + "Projection", "WorldAlignedNormal" if channel == "Normal"
                      else "WorldAlignedTexture", dependencies)
        graph.link(texture, fn, "TextureObject")
        graph.link(texture_size, fn, "TextureSize")
        projected[channel] = fn

    saturation = graph.scalar(prefix + "BaseColorSaturation", 1, group, upper=2)
    inverse = graph.unary(prefix + "OneMinusSaturation", "OneMinus", saturation)
    desat = graph.node(prefix + "Desaturation", "Desaturation")
    graph.link(projected["BaseColor"], desat, "Input", "XYZ Texture")
    graph.link(inverse, desat, "Fraction")
    contrast = graph.fn(prefix + "ColorContrast", "CheapContrast_RGB", dependencies)
    graph.link(desat, contrast, "In")
    graph.link(graph.scalar(prefix + "BaseColorContrast", 0, group, -1, 1),
               contrast, "Contrast")
    hue = graph.fn(prefix + "HueShift", "HueShift", dependencies)
    graph.link(contrast, hue, "Texture")
    graph.link(graph.scalar(prefix + "BaseColorHue", 0, group, upper=1),
               hue, "Hue Shift Percentage")
    color = graph.multiply(prefix + "Brightness", hue,
                           graph.scalar(prefix + "BaseColorBrightness", 1, group, upper=2))

    flatness = graph.unary(prefix + "OneMinusNormalIntensity", "OneMinus",
                          graph.scalar(prefix + "NormalIntensity", 1, group, upper=5))
    normal = graph.fn(prefix + "FlattenNormal", "FlattenNormal", dependencies)
    graph.link(projected["Normal"], normal, "Normal", "XYZ Texture")
    graph.link(flatness, normal, "Flatness")

    green = graph.node(prefix + "RoughnessG", "ComponentMask",
                       {"R": False, "G": True, "B": False, "A": False})
    graph.link(projected["ORDP"], green, "Input", "XYZ Texture")
    roughness = graph.multiply(prefix + "Roughness", green,
                               graph.scalar(prefix + "RoughnessIntensity", 1, group, upper=2))
    attributes = graph.node(prefix + "Attributes", "MakeMaterialAttributes")
    graph.link(color, attributes, "BaseColor")
    graph.link(normal, attributes, "Normal")
    graph.link(roughness, attributes, "Roughness")
    return {"attributes": attributes, "color": color,
            "raw_normal": projected["Normal"]}


def _mask(graph, name, source, output, defaults, dependencies):
    group = "3. " + name
    power = graph.node(name + "PowerNode", "Power")
    graph.link(source, power, "Base", output)
    graph.link(graph.scalar(name + "Power", defaults[0], group), power, "Exp")
    multiplied = graph.multiply(name + "MultiplyNode", power,
                                graph.scalar(name + "Multiplier", defaults[1], group))
    contrast = graph.fn(name + "ContrastNode", "CheapContrast", dependencies)
    graph.link(multiplied, contrast, "In")
    graph.link(graph.scalar(name + "Contrast", defaults[2], group), contrast, "Contrast")
    opacity = defaults[3]
    if opacity is None:
        return {"pre_opacity": contrast, "alpha": None}
    return {"pre_opacity": contrast, "alpha": graph.multiply(name + "Alpha", contrast,
            graph.scalar(name + "Opacity", opacity, group))}


def preflight():
    if MODE not in ("preflight", "author_surface", "author_complete"):
        raise ValueError("Unknown MODE")
    target = DESTINATION + "/" + ASSET_NAME
    if any(_package(p) == target for p in assets_find(DESTINATION, ASSET_NAME)):
        raise RuntimeError("Destination already exists; refuse overwrite: " + target)
    dependencies = {k: _load_exact(v) for k, v in FUNCTIONS.items()}
    textures = {prefix: {k: _load_exact(v) for k, v in values.items()}
                for prefix, values in TEXTURES.items()}
    missing = [k for k, value in OVERLAY_VALUES.items()
               if value is None or not OVERLAY_EVIDENCE.get(k)]
    if MODE == "author_complete":
        raise RuntimeError("Complete L13 is not admitted: missing source values="
                           + repr(missing) + "; consumer RVT source binding unproved")
    if MODE != "preflight" and missing:
        raise RuntimeError("Source surface values are not proved: " + repr(missing))
    if MODE != "preflight" and not MASK_GREEN_ROUGHNESS_VERIFIED:
        raise RuntimeError("Prove accepted Masks.G roughness before authoring PBR branches")
    if MODE != "preflight" and not ACCEPTED_TEXTURE_VT_SETTINGS_VERIFIED:
        raise RuntimeError("Accepted texture VT settings and matching sampler types are NOT RUN")
    return target, dependencies, textures, missing


def run():
    target, dependencies, textures, missing = preflight()
    receipt = {
        "status": "READ_ONLY_PREFLIGHT" if MODE == "preflight" else "SOURCE_SURFACE_RECONSTRUCTION_RVT_PENDING",
        "material_path": target, "source_lesson": SOURCE_MAP,
        "source_value_gaps": missing,
        "overlay_source_evidence": OVERLAY_EVIDENCE,
        "rgb_precision": "Source UI numeric precision; unavailable original float32 bytes are not claimed",
        "source_1_to_1_complete": False,
        "texture_provenance": "Existing accepted appearance adapter; original Megascans bytes not established",
        "accepted_masks_green_roughness_verified": MASK_GREEN_ROUGHNESS_VERIFIED,
        "accepted_texture_vt_settings_verified": ACCEPTED_TEXTURE_VT_SETTINGS_VERIFIED,
        "rvt_status": "NOT_AUTHORED: actual consumer RVT dependencies require proof; source sign is WorldPosition.Z minus RVT.WorldHeight",
        "assigned_to_scene": False, "map_saved": False,
        "owner_visual_acceptance": "PENDING", "performance_pass": False,
        "dependencies": dependencies, "textures": textures,
    }
    if MODE == "preflight":
        return receipt

    graph = Graph(material_create(DESTINATION, ASSET_NAME))
    graph.set(graph.material, "Material", {"bUseMaterialAttributes": True,
                                          "bTangentSpaceNormal": True})
    white = graph.node("TextureSizeUnitVector", "Constant3Vector",
                       {"Constant": {"r": 1.0, "g": 1.0, "b": 1.0, "a": 1.0}})
    hundred = graph.node("Centimetres", "Constant", {"R": 100.0})
    size = graph.multiply("TextureSize100", white, hundred)
    size = graph.multiply("TextureSize", size,
                          graph.scalar("MapTiling", 10, "0. Common Parameters"))
    grass = _pbr(graph, "01", dependencies, textures, size)
    rock = _pbr(graph, "02", dependencies, textures, size)

    world_normal = graph.node("RockNormalTangentToWorld", "Transform", {
        "TransformSourceType": "TRANSFORMSOURCE_Tangent", "TransformType": "TRANSFORM_World"})
    graph.link(rock["raw_normal"], world_normal, "Input", "XYZ Texture")
    upward = graph.node("RockNormalWorldZ", "ComponentMask",
                        {"R": False, "G": False, "B": True, "A": False})
    graph.link(world_normal, upward, "Input")
    slope = graph.node("GrassRockSmoothStep", "SmoothStep")
    graph.link(upward, slope, "Value")
    graph.link(graph.scalar("BlendMin", .6, "0. Common Parameters"), slope, "Min")
    graph.link(graph.scalar("BlendMax", .8, "0. Common Parameters"), slope, "Max")
    blend = graph.node("RockGrassAttributes", "BlendMaterialAttributes")
    graph.link(rock["attributes"], blend, "A")
    graph.link(grass["attributes"], blend, "B")
    graph.link(slope, blend, "Alpha")

    cd = graph.node("PegasusCd", "VertexColor")
    ao_inverse = graph.unary("OcclusionOneMinusB", "OneMinus", cd, "B")
    masks = {
        "Occlusion": _mask(graph, "Occlusion", ao_inverse, "", (.4, 2, .1, OVERLAY_VALUES["OcclusionOpacity"]), dependencies),
        "Convexity": _mask(graph, "Convexity", cd, "R", (.5, 1, .1, 1), dependencies),
        "Concavity": _mask(graph, "Concavity", cd, "G", (.5, 2, .1, OVERLAY_VALUES["ConcavityOpacity"]), dependencies),
    }
    color = rock["color"]
    for name in ("Occlusion", "Convexity", "Concavity"):
        parameter = name + "Color"
        rgba = OVERLAY_VALUES[parameter]
        vector = graph.node(parameter, "VectorParameter", {
            "ParameterName": _parameter_name(parameter), "Group": "3. Color",
            "DefaultValue": dict(zip(("r", "g", "b", "a"), rgba)),
        })
        overlay = graph.node(name + "ColorBlend", "LinearInterpolate")
        graph.link(color, overlay, "A")
        graph.link(vector, overlay, "B")
        graph.link(masks[name]["alpha"], overlay, "Alpha")
        color = overlay
    graph.link(color, rock["attributes"], "BaseColor")
    material_output(graph.nodes[blend])
    wiring = graph.verify()
    actual_output = material_output_read(graph.material)
    if actual_output["expression"] != graph.nodes[blend]:
        raise RuntimeError("MaterialAttributes native output differs")
    material_compile(graph.material)
    if SAVE_CANDIDATE:
        asset_save(target)
    receipt.update({
        "material": graph.material, "node_count": len(graph.nodes),
        "nodes": graph.nodes, "values": graph.values, "expected_edges": graph.edges,
        "native_wiring": wiring, "native_output": actual_output,
        "mask_endpoints": masks, "native_recompile": "SUCCEEDED",
        "candidate_saved": SAVE_CANDIDATE,
        "overlay_status": "CONNECTED: AO -> convexity -> concavity, with final source values",
        "source_surface_graph_complete": True,
    })
    return receipt
