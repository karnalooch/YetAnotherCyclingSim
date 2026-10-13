"""PCG365 input adaptation and official PCG/PCGEx MCP orchestration.

All slope, support, spacing and staging decisions run in installed native nodes.
This module replaces the earlier unexecuted direct-Unreal-Python candidate.
"""

from __future__ import annotations
import hashlib
import http.client
import json
import math
from pathlib import Path
import time

EX = "PCGExAssistant.PCGExToolset"
PCG = "PCGToolset.PCGToolset"
OBJECT = "editor_toolset.toolsets.object.ObjectTools"
ASSET = "editor_toolset.toolsets.asset.AssetTools"
MESH = "editor_toolset.toolsets.static_mesh.StaticMeshTools"
ACTOR = "editor_toolset.toolsets.actor.ActorTools"
SCENE = "editor_toolset.toolsets.scene.SceneTools"

POLICY = {
    "id": "PCG365_PCGEX_SLOPE_ALIGNED_PREVIEW_V3",
    "maximum_slope_degrees": 42.0,
    "uniform_scale": 1.0,
    "seed": 36501,
    "source_clearance_cm": 50.0,
    "support_plane_tolerance_cm": 20.0,
    "embed_along_normal_cm": 5.0,
    "support_status": "PCGEX_FIVE_PROBE_SCREEN_NOT_V2_CONTACT_QUALIFICATION",
}
MAP = "/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface"
LABEL = "PCG365_PCGEx_V3_Preview"
RECIPE_REVISION = "native-mcp-v3-20cm-manual-generation"


def require(value, message):
    if not value:
        raise ValueError(message)


def verify_input(document):
    require(
        document["schema_version"] == 1 and document["policy"] == POLICY,
        "Input policy differs",
    )
    require(document["map_package"] == MAP, "Wrong world")
    rows = document["points"]
    require(0 < len(rows) <= 50000, "Expected at most 50,000 exact source cells")
    seen = set()
    for row, col, slope, clearance in rows:
        require(
            type(row) is int
            and type(col) is int
            and 0 <= row < 4033
            and 0 <= col < 4033,
            "Source cell outside the accepted grid",
        )
        require((row, col) not in seen, "Duplicate source cell")
        seen.add((row, col))
        require(
            all(
                type(v) in (int, float) and math.isfinite(v) for v in (slope, clearance)
            )
            and 0 <= slope <= 90
            and clearance >= 0,
            "Invalid source sample",
        )
    require(
        math.isfinite(document["radius_cm"]) and 0 < document["radius_cm"] <= 250,
        "Invalid asset radius",
    )


class Client:
    def __init__(self):
        self.connection = http.client.HTTPConnection("127.0.0.1", 8000, timeout=180)
        self.session = None
        self.index = 0
        self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "YACS-PCG365-authoring", "version": "1"},
            },
        )
        self.rpc("notifications/initialized", None, True)

    def rpc(self, method, params=None, notification=False):
        self.index += 1
        body = {"jsonrpc": "2.0", "method": method}
        if not notification:
            body["id"] = self.index
        if params is not None:
            body["params"] = params
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.session:
            headers.update(
                {"Mcp-Session-Id": self.session, "Mcp-Protocol-Version": "2025-06-18"}
            )
        self.connection.request("POST", "/mcp", json.dumps(body).encode(), headers)
        response = self.connection.getresponse()
        raw = response.read(32 * 1024 * 1024 + 1)
        assert len(raw) <= 32 * 1024 * 1024, "MCP response exceeds bound"
        if notification:
            assert response.status == 202 and not raw
            return None
        assert response.status == 200, (response.status, raw[:1000])
        if method == "initialize":
            self.session = response.getheader("Mcp-Session-Id")
        result = json.loads(raw)
        assert result.get("id") == self.index and "error" not in result, result
        return result["result"]

    def call(self, name, arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            raise RuntimeError(result)
        return result


def unpack(result):
    contents = result.get("content", [])
    texts = [v["text"] for v in contents if v.get("type") == "text"]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except ValueError:
            return texts[0]
    return result


def ref(path):
    return {"refPath": path}


def v(x=0, y=0, z=0):
    return {"x": x, "y": y, "z": z}


def const(value):
    return {"input": "Constant", "constant": value}


class Author:
    def __init__(self, source, expected_sha256, output):
        self.root = Path(output)
        self.source = Path(source)
        self.expected_sha256 = expected_sha256
        self.state_file = self.root / "graph-state.json"
        require(
            not self.state_file.exists(),
            "Preserve an existing run; use a new output directory",
        )
        (self.root / "schemas").mkdir(exist_ok=True)
        self.client = Client()
        self.state = {"nodes": {}, "input_sha256": expected_sha256}
        self.folder = "/Game/Generated/YACS/PCG365Ex/R" + expected_sha256[:16] + "_s2"
        self.graph_path = self.folder + "/PCG365_Rocks"
        self.collection_path = self.folder + "/DA_Rocks"

    def save(self):
        self.state_file.write_text(json.dumps(self.state, indent=2))

    def call(self, group, name, args):
        out = unpack(
            self.client.call(
                "call_tool",
                {"toolset_name": group, "tool_name": name, "arguments": args},
            )
        )
        with (self.root / "author-calls.jsonl").open("a") as f:
            f.write(
                json.dumps(
                    {
                        "time": time.time(),
                        "tool": name,
                        "arguments_sha256": hashlib.sha256(
                            json.dumps(args).encode()
                        ).hexdigest(),
                        "result": out,
                    }
                )
                + "\n"
            )
        value = out.get("returnValue", out) if isinstance(out, dict) else out
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        if isinstance(value, dict) and "error" in value:
            raise RuntimeError(value)
        return value

    def create(self, name, cls, props=None):
        if name in self.state["nodes"]:
            return self.state["nodes"][name]
        s = self.call(EX, "GetNodeSchema", {"settingsClass": cls})
        (self.root / "schemas" / f"{cls}.json").write_text(json.dumps(s, indent=2))
        assert set(props or {}) <= set(s["properties"]), (
            name,
            set(props or {}) - set(s["properties"]),
        )
        result = self.call(
            EX,
            "CreateNode",
            {
                "graph": self.state["graph"],
                "settingsClass": cls,
                "nodeName": name,
                "jsonParams": json.dumps(props or {}),
                "nodeTitle": name,
                "xPosition": len(self.state["nodes"]) * 260,
                "yPosition": 0,
            },
        )
        assert result.get("refPath"), result
        self.state["nodes"][name] = result
        self.save()
        print("NODE", name, flush=True)
        return result

    def edge(self, a, b, source="Out", target="In"):
        result = self.call(
            PCG,
            "ConnectNodePins",
            {
                "fromNode": self.state["nodes"][a],
                "fromPinLabel": source,
                "toNode": self.state["nodes"][b],
                "toPinLabel": target,
            },
        )
        for added in result:
            info = self.call(PCG, "GetNodeInfo", {"node": added})
            assert info["nodeType"] == "Filter Data - Primitive", (
                "Unexpected conversion",
                info,
            )
            self.state["nodes"][info["name"]] = added
            self.save()

    def filters(self, name, previous, rules, source="Out"):
        self.create(name, "PCGExUberFilterSettings", {"bOutputDiscardedElements": True})
        self.edge(previous, name, source)
        subs = [
            {
                "class": "PCGExNumericCompareFilterProviderSettings",
                "name": f"{name}_rule{i}",
                "params": {
                    "config": {
                        "operandA": attr,
                        "comparison": op,
                        "operandBValue": const(value),
                    }
                },
            }
            for i, (attr, op, value) in enumerate(rules)
        ]
        key = name + "_providers"
        if key not in self.state:
            self.state[key] = self.call(
                EX,
                "AddSubnodes",
                {
                    "graph": self.state["graph"],
                    "targetNode": self.state["nodes"][name],
                    "targetPinLabel": "Filters",
                    "subnodesJson": json.dumps(subs),
                },
            )
            self.save()
        return name

    def trace(self, name, previous, apply, distance, rotation="Z", cross=None, normal_name="GroundNormal"):
        self.create(
            name,
            "PCGExSampleSurfaceGuidedSettings",
            {
                "surfaceSource": "ActorReferences",
                "actorReference": "ActorReference",
                "origin": "$Position",
                "direction": "TraceDirection",
                "distance": const(distance),
                "bPruneFailedSamples": True,
                "bWriteNormal": True,
                "normalAttributeName": normal_name,
                "bWriteDistance": True,
                "distanceAttributeName": "GroundDistance",
                "bWriteSuccess": True,
                "successAttributeName": "GroundHit",
                "rotationConstruction": rotation,
                "crossAxis": const(cross or v(1, 0, 0)),
                "collisionSettings": {"bTraceComplex": True},
                "applySampling": {
                    "bApplyTransform": apply,
                    "transformPosition": 7 if apply else 0,
                    "transformRotation": 7 if apply else 0,
                    "transformScale": 0,
                },
            },
        )
        self.edge(previous, name, target="Sources")
        self.edge("ground", name, target="ActorReferences")
        return name

    def ex_move(self, name, previous, xyz, absolute=False, source="Out", scaling=None, attribute=None):
        offset = {"input": "Attribute", "attribute": attribute} if attribute else const(v(*xyz))
        props = {"offsetMin": offset, "offsetMax": offset, "absoluteOffset": const(absolute)}
        if scaling:
            props["offsetScaling"] = scaling
        self.create(name, "PCGExTransformPointsSettings", props)
        self.edge(previous, name, source)
        return name

    def move(self, name, previous, xyz, absolute, source="Out"):
        if getattr(self, "pcgex_transforms", False):
            return self.ex_move(name, previous, xyz, absolute, source)
        self.create(
            name,
            "PCGTransformPointsSettings",
            {
                "offsetMin": v(*xyz),
                "offsetMax": v(*xyz),
                "bAbsoluteOffset": absolute,
                "bRecomputeSeed": False,
            },
        )
        self.edge(previous, name, source)
        return name


def build(a):
    raw = a.source.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == a.expected_sha256, "Input hash changed")
    d = json.loads(raw)
    verify_input(d)
    build_nodes(a, d, POLICY)


def available_extent_cm(clearance_cm, policy):
    """Encode a clearance sphere as an inscribed box; PCGEx chooses the mesh scale."""
    extent = max(0.0, clearance_cm - policy["source_clearance_cm"]
                 - policy["embed_along_normal_cm"]) / math.sqrt(3)
    return min(extent, policy.get("fit_extent_cap_cm", math.inf))


def input_clearance_cm(clearance_cm, policy):
    """Trace the complete admitted input envelope, capped by its mesh-sized box."""
    if "fit_extent_cap_cm" not in policy:
        return clearance_cm
    return min(clearance_cm, math.sqrt(3) * policy["fit_extent_cap_cm"]
               + policy["source_clearance_cm"] + policy["embed_along_normal_cm"])


def build_nodes(a, d, policy):
    """Wire reusable native nodes; callers authenticate their own input contract."""
    radius = d["radius_cm"]
    auto_fit = policy.get("native_best_fit", False)
    a.pcgex_transforms = auto_fit
    if "graph" not in a.state:
        a.state["graph"] = a.call(
            PCG, "CreateGraph", {"name": "PCG365_Rocks", "path": a.folder}
        )
        a.save()
    a.create("input", "PCGMergeSettings")
    for chunk, start in enumerate(range(0, len(d["points"]), 4000)):
        pts = [
            {
                "transform": {
                    "location": v(col * 50, row * 50, 1000000),
                    "scale": v(*([policy["uniform_scale"]] * 3)),
                },
                "density": 1,
                "boundsMin": v(*([-available_extent_cm(clearance, policy) if auto_fit else -radius] * 3)),
                "boundsMax": v(*([available_extent_cm(clearance, policy) if auto_fit else radius] * 3)),
                "color": dict(x=slope, y=input_clearance_cm(clearance, policy),
                              z=available_extent_cm(clearance, policy) if auto_fit else 0, w=1),
                "seed": (row * 4033 + col) ^ policy["seed"],
                "steepness": 1,
                "metadataEntry": -1,
            }
            for row, col, slope, clearance in d["points"][start : start + 4000]
        ]
        a.create(
            f"cells_{chunk:02}",
            "PCGCreatePointsSettings",
            {
                "coordinateSpace": "World",
                "bCullPointsOutsideVolume": False,
                "pointsToCreate": pts,
            },
        )
        a.edge(f"cells_{chunk:02}", "input")
    for name, cls in [("ground", "/Script/Landscape.Landscape")]:
        a.create(
            name,
            "PCGDataFromActorSettings",
            {
                "actorSelector": {
                    "actorFilter": "AllWorldActors",
                    "actorSelection": "ByClass",
                    "actorSelectionClass": ref(cls),
                    "bSelectMultiple": True,
                    "bMustOverlapSelf": False,
                },
                "mode": "GetSinglePoint",
                "bMergeSinglePointData": True,
                "bAlwaysRequeryActors": True,
                "bComponentsMustOverlapSelf": False,
            },
        )
    source = a.filters(
        "source_masks",
        "input",
        [
            ("$Color.X", "EqualOrSmaller", policy["maximum_slope_degrees"]),
            ("$Color.Y", "StrictlyGreater" if auto_fit else "EqualOrGreater",
             policy["source_clearance_cm"] + (policy["embed_along_normal_cm"] if auto_fit else radius)),
        ],
    )
    a.create(
        "direction",
        "PCGAddAttributeSettings",
        {
            "outputTarget": "TraceDirection",
            "attributeTypes": {"type": "Vector", "vectorValue": v(0, 0, -1)},
        },
    )
    a.edge(source, "direction", "Inside")
    projected = a.trace("project_and_align", "direction", True, 2000000,
                        policy.get("rotation_axis", "Z"), policy.get("cross_axis"))
    slope = a.filters(
        "native_slope",
        projected,
        [
            (
                "GroundNormal.Z",
                "EqualOrGreater",
                math.cos(math.radians(policy["maximum_slope_degrees"])),
            )
        ],
    )
    slope_pin = "Inside"
    if policy.get("fuse_footprint_cm"):
        a.create("cliff_fragments", "PCGExFusePointsSettings", {
            "mode": "MostCentral", "bPreserveOrder": True, "fusedBoundsMode": "None",
            "pointPointIntersectionDetails": {"fuseDetails": {
                "fuseMethod": "Voxel", "toleranceInput": "Constant",
                "tolerance": policy["fuse_footprint_cm"],
                "sourceDistance": "Center", "targetDistance": "Center",
                "bComponentWiseTolerance": False,
            }},
        })
        a.edge(slope, "cliff_fragments", slope_pin)
        slope, slope_pin = "cliff_fragments", "Out"
    a.create("merge_assets", "PCGMergeAttributesSettings")
    for i, asset in enumerate(d["assets"]):
        path = asset.get("mesh_package", mesh_path(asset))
        a.create(
            f"asset_{i}",
            "PCGCreateAttributeSetSettings",
            {
                "outputTarget": "AssetPath",
                "attributeTypes": {
                    "type": "SoftObjectPath",
                    "softObjectPathValue": ref(path + "." + path.rsplit("/", 1)[1]),
                },
            },
        )
        a.edge(f"asset_{i}", "merge_assets")
    a.create(
        "build_collection",
        "PCGExBuildAssetCollectionSettings",
        {
            "outputAttributeName": "Collection",
            "bSaveToAsset": True,
            "saveTarget": {
                "assetPath": a.folder,
                "assetName": "DA_Rocks",
                "bSaveToDiskImmediately": True,
            },
        },
    )
    a.edge("merge_assets", "build_collection", target="AttributeSet")
    a.create(
        "attach_collection",
        "PCGAddAttributeSettings",
        {"inputSource": "Collection", "outputTarget": "Collection"},
    )
    if not auto_fit:
        a.edge(slope, "attach_collection", "Inside")
    a.edge("build_collection", "attach_collection", target="Attributes")
    a.create(
        "stage_assets",
        "PCGExAssetStagingSettings",
        {
            "sourceCollection": const(ref(a.collection_path + ".DA_Rocks")),
            "outputMode": "CollectionMap",
            "selectorMode": "External",
            "bApplyFitting": True,
            "scaleToFit": {"scaleToFitMode": "Uniform", "scaleToFit": "Min"} if auto_fit else {"scaleToFitMode": "None"},
            "justification": {
                "bDoJustifyX": auto_fit,
                "bDoJustifyY": auto_fit,
                "bDoJustifyZ": auto_fit,
            },
            "bConsiderEntryScaleToFit": False,
            "bConsiderEntryJustification": False,
        },
    )
    if not auto_fit:
        a.edge("attach_collection", "stage_assets")
    a.create(
        "asset_choice",
        "PCGExSelectorBestFitFactoryProviderSettings" if auto_fit else "PCGExSelectorClassicFactoryProviderSettings",
        {} if auto_fit else {"config": {"mode": "WeightedRandom"}},
    )
    a.edge("asset_choice", "stage_assets", "Selector", "Selector")
    a.create(
        "road_primitives",
        "PCGDataFromActorSettings",
        {
            "actorSelector": {
                "actorFilter": "AllWorldActors",
                "actorSelection": "ByClass",
                "actorSelectionClass": ref(
                    "/Script/GeometryFramework.DynamicMeshActor"
                ),
                "bSelectMultiple": True,
                "bMustOverlapSelf": False,
            },
            "mode": "ParseActorComponents",
            "bAlwaysRequeryActors": True,
            "bComponentsMustOverlapSelf": False,
        },
    )
    a.move("road_check_above", slope if auto_fit else "stage_assets", (0, 0, 1000), True,
           slope_pin if auto_fit else "Out")
    a.create(
        "road_geometry_clearance",
        "PCGExSampleSurfaceGuidedSettings",
        {
            "surfaceSource": "Primitives",
            "origin": "$Position",
            "direction": "TraceDirection",
            "distance": const(2000),
            "bPruneFailedSamples": False,
            "bWriteSuccess": True,
            "successAttributeName": "RoadHit",
            "bWriteNormal": False,
            "bWriteDistance": False,
            "applySampling": {"bApplyTransform": False},
            "collisionSettings": {
                "traceMode": "Sphere",
                "sphereRadius": {"input": "Attribute", "attribute": "$Color.Y"} if auto_fit else const(radius + policy["source_clearance_cm"]),
                "bTraceComplex": True,
            },
        },
    )
    a.edge("road_check_above", "road_geometry_clearance", target="Sources")
    a.edge("road_primitives", "road_geometry_clearance", target="Primitives")
    a.move("road_check_restore", "road_geometry_clearance", (0, 0, -1000), True)
    a.filters(
        "protect_current_road", "road_check_restore", [("RoadHit", "StrictlyEqual", 0)]
    )
    previous = a.create(
        "rock_spacing",
        "PCGExSelfPruningSettings",
        {
            "bRandomize": True,
            "bPreciseTest": True,
            "primaryMode": "After",
            "primaryExpansionValue": const(25),
            "secondaryMode": "After",
            "secondaryExpansionValue": const(25),
            "bOutputDiscard": True,
        },
    )
    if not auto_fit:
        a.edge("protect_current_road", "rock_spacing", "Inside")
    previous = "protect_current_road" if auto_fit else "rock_spacing"
    previous_pin = "Inside" if auto_fit else "Out"
    probes = ((radius, 0), (-radius, 0), (0, radius), (0, -radius)) if policy.get("five_probe", True) else ()
    for i, (x, y) in enumerate(probes):
        if auto_fit:
            direction = (1 if x > 0 else -1 if x < 0 else 0,
                         1 if y > 0 else -1 if y < 0 else 0, 0)
            previous = a.ex_move(f"probe{i}_offset", previous, direction, source=previous_pin,
                                 scaling={"input": "Attribute", "attribute": "$Color.Z"})
        else:
            previous = a.move(f"probe{i}_offset", previous, (x, y, 0), False)
        previous_pin = "Out"
        previous = a.move(f"probe{i}_above", previous, (0, 0, 1000), True)
        normal_name = "SupportNormal" if auto_fit else "GroundNormal"
        previous = a.trace(f"probe{i}_trace", previous, False, 2000, normal_name=normal_name)
        previous = a.filters(
            f"probe{i}_support",
            previous,
            [
                (
                    "GroundDistance",
                    "EqualOrGreater",
                    1000 - policy["support_plane_tolerance_cm"],
                ),
                (
                    "GroundDistance",
                    "EqualOrSmaller",
                    1000 + policy["support_plane_tolerance_cm"],
                ),
                (
                    normal_name + ".Z",
                    "EqualOrGreater",
                    math.cos(math.radians(policy.get("support_maximum_slope_degrees", policy["maximum_slope_degrees"]))),
                ),
            ],
        )
        previous = a.move(
            f"probe{i}_restore_z", previous, (0, 0, -1000), True, "Inside"
        )
        if auto_fit:
            previous = a.ex_move(f"probe{i}_restore_xy", previous, tuple(-v for v in direction),
                                 scaling={"input": "Attribute", "attribute": "$Color.Z"})
        else:
            previous = a.move(f"probe{i}_restore_xy", previous, (-x, -y, 0), False)
    # Correct the supplied scan's axes before PCGEx solves its fitted bounds/pivot.
    if policy.get("model_rotation"):
        a.create("fit_scan_axes", "PCGExTransformPointsSettings", {
            "rotationMin": const(policy["model_rotation"]),
            "rotationMax": const(policy["model_rotation"]),
        })
        a.edge(previous, "fit_scan_axes", previous_pin)
        previous, previous_pin = "fit_scan_axes", "Out"
    if auto_fit:
        a.edge(previous, "attach_collection", previous_pin)
        a.edge("attach_collection", "stage_assets")
        a.state["staging_input"] = [previous, previous_pin]
        a.save()
        a.edge("stage_assets", "rock_spacing")
        # Native justification seats the variable-sized mesh; only the declared
        # visual embedding remains, applied along the measured center normal.
        a.ex_move("seat_rock", "rock_spacing", (0, 0, 0), absolute=True,
                  attribute="GroundNormal", scaling=const(v(*([-policy["embed_along_normal_cm"]] * 3))))
    else:
        a.move("seat_rock", previous, (0, 0, -policy["embed_along_normal_cm"]), False)
    a.create(
        "spawn",
        "PCGStaticMeshSpawnerSettings",
        {
            "meshSelectorType": ref("/Script/PCGExCollections.PCGExMeshSelectorStaged"),
            "bSynchronousLoad": True,
        },
    )
    settings = a.call(
        OBJECT,
        "get_properties",
        {"instance": a.state["nodes"]["spawn"], "properties": ["SettingsInterface"]},
    )["SettingsInterface"]
    selector = a.call(
        OBJECT,
        "get_properties",
        {"instance": settings, "properties": ["MeshSelectorParameters"]},
    )["MeshSelectorParameters"]
    require(
        a.call(
            OBJECT,
            "set_properties",
            {
                "instance": selector,
                "values": json.dumps({"bForceDisableCollisions": True}),
            },
        ),
        "Cannot disable decorative collision",
    )
    require(
        a.call(
            OBJECT,
            "get_properties",
            {"instance": selector, "properties": ["bForceDisableCollisions"]},
        )["bForceDisableCollisions"]
        is True,
        "Collision readback differs",
    )
    a.edge("stage_assets", "spawn", "Map", "Overrides")
    a.edge("seat_rock", "spawn")
    a.state["nodes"]["output"] = ref(a.state["graph"]["refPath"] + ":DefaultOutputNode")
    a.save()
    a.edge("spawn", "output", target="Out")


def finalize_collection(a):
    """Keep collection construction out of the persisted generation graph.

    PCGEx 0.79 BuildAssetCollection asserted in OutputPath after loading a saved
    world. Use that installed node only to prepare the saved input asset, then
    let normal Asset Staging consume it directly on subsequent generations.
    """
    if "build_collection" not in a.state["nodes"]:
        return
    require(
        a.call(ASSET, "exists", {"path": a.collection_path}),
        "Native collection preparation did not create its saved asset",
    )
    temporary = ["build_collection", "attach_collection", "merge_assets"] + [
        key
        for key in a.state["nodes"]
        if key.startswith("asset_") and key != "asset_choice"
    ]
    for key in temporary:
        node = a.state["nodes"][key]
        require(
            a.call(PCG, "RemoveNode", {"graph": a.state["graph"], "node": node}),
            "Could not detach collection preparation node",
        )
        del a.state["nodes"][key]
    previous, pin = a.state.get("staging_input", ["native_slope", "Inside"])
    a.edge(previous, "stage_assets", source=pin)
    a.state["collection_prepared_once"] = True
    a.save()


def recipe(collection_path, radius_cm):
    """Human-readable orchestration manifest; the native author below owns wiring."""
    return {
        "policy": POLICY.copy(),
        "entrypoint": "build_pcg365_world.py --mode build-pcgex",
        "toolsets": [EX, PCG, ASSET, OBJECT, MESH, SCENE],
        "radius_cm": radius_cm,
        "collection_path": collection_path,
        "implementation": "scripts/worldgen/pcg365_pcgex_graph.py",
        "stages": [
            "exact source points",
            "native source mask filters",
            "Landscape projection and alignment",
            "native slope filter",
            "PCGEx collection/staging/selector",
            "road primitive sphere sweep",
            "PCGEx self pruning",
            "four native support probes",
            "embedding",
            "staged mesh spawner",
        ],
        "placement_logic": "EXISTING_PCG_AND_PCGEX_NODES_ONLY",
    }


def mesh_path(asset):
    return (
        "/Game/Generated/YACS/PCG365RemotePreview/Rf3acaeb8a89a3600/SM_" + asset["id"]
    )


def prepare_assets(a, data, stage):
    """Only input import/material adaptation; native tools own mesh processing."""
    assets = []
    for asset in data["assets"]:
        path = mesh_path(asset)
        mesh = ref(path + ".SM_" + asset["id"])
        material = ref(asset["material_package"] + ".MI_MaterialForge")
        if not a.call(ASSET, "exists", {"path": path}):
            source = Path(stage) / asset["fbx"]["path"]
            require(
                source.is_file() and source.stat().st_size == asset["fbx"]["bytes"],
                "Mesh source missing",
            )
            require(
                hashlib.sha256(source.read_bytes()).hexdigest()
                == asset["fbx"]["sha256"],
                "Mesh source hash changed",
            )
            a.call(
                MESH,
                "import_file",
                {
                    "folder_path": path.rsplit("/", 1)[0],
                    "asset_name": path.rsplit("/", 1)[1],
                    "source_file": str(source),
                    "import_materials": False,
                    "import_textures": False,
                    "combine_meshes": True,
                },
            )
            for slot in a.call(MESH, "get_material_slots", {"mesh": mesh}):
                require(
                    a.call(
                        MESH,
                        "set_material",
                        {"mesh": mesh, "slot_name": slot, "material": material},
                    ),
                    "Material assignment failed",
                )
        require(
            a.call(MESH, "get_triangle_count", {"mesh": mesh, "lod_index": 0})
            == asset["expected_lod0_triangles"],
            "Imported triangle count differs",
        )
        slots = a.call(MESH, "get_material_slots", {"mesh": mesh})
        require(slots, "Rock has no material slot")
        for slot in slots:
            require(
                a.call(MESH, "get_material", {"mesh": mesh, "slot_name": slot})
                == material,
                "Existing material differs",
            )
        assets.append(path)
    return assets


def inspect_instances(a, actor):
    components = a.call(
        ACTOR,
        "get_components",
        {
            "actor": actor,
            "component_type": ref("/Script/Engine.InstancedStaticMeshComponent"),
        },
    )
    proof = []
    for component in components:
        values = a.call(
            OBJECT,
            "get_properties",
            {
                "instance": component,
                "properties": [
                    "PerInstanceSMData",
                    "StaticMesh",
                    "OverrideMaterials",
                    "BodyInstance",
                ],
            },
        )
        require(
            values["BodyInstance"]["collisionEnabled"] == "NoCollision",
            "Decorative component collision is enabled",
        )
        proof.append({"component": component, **values})
    return proof


def build_preview(input_path, expected_sha256, output_directory, stage, save_map=False):
    """Run against the existing localhost Editor through official MCP tools.

    Network mutation timeouts have unknown outcomes and are never retried.
    The original map is never saved. Optional output is a new level asset.
    """
    a = Author(input_path, expected_sha256, output_directory)
    raw = a.source.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, "Input hash changed")
    data = json.loads(raw)
    verify_input(data)
    require(
        a.call(SCENE, "get_current_level", {}) == MAP,
        "Open the authenticated source map first",
    )
    roads = a.call(
        SCENE,
        "find_actors",
        {
            "root": None,
            "name": "",
            "actor_type": ref("/Script/GeometryFramework.DynamicMeshActor"),
            "tag": "",
            "bounds": None,
            "collision_channels": [],
        },
    )
    require(len(roads) == 559, "Expected current road/CUT inventory")
    all_instances = a.call(PCG, "ListGraphInstances", {})
    expected_graph = ref(a.graph_path + ".PCG365_Rocks")
    require(
        not any(
            LABEL in item["actor"]["refPath"] and item["graph"] != expected_graph
            for item in all_instances
        ),
        "A different PCG365 preview is present; preserve or remove it explicitly before rebuilding",
    )
    assets = prepare_assets(a, data, stage)
    if a.call(ASSET, "exists", {"path": a.graph_path}):
        tags = a.call(ASSET, "get_metadata_tags", {"asset_path": a.graph_path})
        require(
            tags.get("YACS.PCG365.InputSHA256") == expected_sha256
            and tags.get("YACS.PCG365.Recipe") == RECIPE_REVISION,
            "Existing graph is not an authenticated completed build",
        )
        a.state["graph"] = a.call(ASSET, "load_asset", {"asset_path": a.graph_path})
    else:
        build(a)
    instances = [item for item in all_instances if item["graph"] == a.state["graph"]]
    require(
        len(instances) <= 1,
        "Multiple instances of the same graph; preserve scene for inspection",
    )
    if instances:
        a.state["instance"] = instances[0]
    else:
        a.state["instance"] = a.call(
            PCG,
            "SpawnGraphInstance",
            {
                "graph": a.state["graph"],
                "name": LABEL + "_" + expected_sha256[:8],
                "transform": {
                    "location": v(100825, 100825, 0),
                    "scale": v(1100, 1100, 1100),
                },
                "jsonParams": "{}",
            },
        )
    a.save()
    # Allow the native on-change generation to finish before requesting explicit proof.
    time.sleep(3)
    messages = a.call(
        PCG, "ExecuteGraphInstance", {"pCGVolume": a.state["instance"]["actor"]}
    )
    (a.root / "generation-messages.json").write_text(json.dumps(messages, indent=2))
    require(
        not messages,
        "Native graph reports generation messages; inspect before admission",
    )
    components = a.call(
        ACTOR,
        "get_components",
        {
            "actor": a.state["instance"]["actor"],
            "component_type": ref("/Script/PCG.PCGComponent"),
        },
    )
    require(len(components) == 1, "Expected one PCG component")
    require(
        a.call(
            OBJECT,
            "set_properties",
            {
                "instance": components[0],
                "values": json.dumps({"bRegenerateInEditor": False}),
            },
        ),
        "Could not select explicit editor generation",
    )
    require(
        a.call(
            OBJECT,
            "get_properties",
            {
                "instance": components[0],
                "properties": ["bRegenerateInEditor"],
            },
        )["bRegenerateInEditor"]
        is False,
        "PCG still regenerates while editing",
    )
    finalize_collection(a)
    messages = a.call(
        PCG, "ExecuteGraphInstance", {"pCGVolume": a.state["instance"]["actor"]}
    )
    (a.root / "generation-messages.json").write_text(json.dumps(messages, indent=2))
    require(not messages, "Final graph reports generation messages")
    proof = inspect_instances(a, a.state["instance"]["actor"])
    count = sum(len(item["PerInstanceSMData"]) for item in proof)
    require(count > 0, "Native graph produced no mesh instances")
    (a.root / "native-instances.json").write_text(json.dumps(proof, indent=2))
    a.call(
        ASSET,
        "update_metadata_tags",
        {
            "asset_path": a.graph_path,
            "set_tags": {
                "YACS.PCG365.InputSHA256": expected_sha256,
                "YACS.PCG365.Recipe": RECIPE_REVISION,
            },
            "remove_tags": [],
        },
    )
    saved = assets + [a.graph_path, a.collection_path]
    require(
        a.call(ASSET, "save_assets", {"asset_paths": saved}),
        "Generated assets could not be saved",
    )
    level = None
    if save_map:
        level = a.folder + "/L_PCG365_Rocks"
        require(
            not a.call(ASSET, "exists", {"path": level}),
            "Output level exists; preserve it and reuse the saved graph",
        )
        require(
            a.call(ASSET, "duplicate", {"path": MAP, "new_path": level}),
            "Native level copy failed",
        )
        require(
            a.call(ASSET, "save_assets", {"asset_paths": [level]}),
            "Output level save failed",
        )
    receipt = {
        "status": "PCGEX_NATIVE_ROCKS_SAVED",
        "input_sha256": expected_sha256,
        "recipe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy": POLICY,
        "recipe_revision": RECIPE_REVISION,
        "fresh_reload_verified": False,
        "graph": a.state["graph"],
        "actor": a.state["instance"]["actor"],
        "native_instances": count,
        "saved_assets": saved,
        "saved_preview_map": level,
        "source_map_saved": False,
        "terrain_modified": False,
        "whole_area_complete": False,
        "cliff_consumer": "NOT_IMPLEMENTED",
        "owner_visual": "PENDING_FINAL_M3",
        "performance": "DEFERRED_AFTER_M3",
        "performance_pass": False,
    }
    (a.root / "native-result.json").write_text(json.dumps(receipt, indent=2))
    return receipt
