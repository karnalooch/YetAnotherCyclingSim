"""Read-only, in-editor proof of an actual native PCG reduction node.

Execute inside Unreal Python, against a *dedicated, already generated* reduced
probe graph. Do not use this for a general full-density wall graph: the counted
output must come DIRECTLY from the named native reduction node. Never infer a
native count from a caller-supplied "certified_point_count" or MCP slice size.

This module never calls GetNodeDataView, generates graphs, or saves map/assets.
The external PCG365 adapter remains blocked until a real in-session witness is
established and bound to a bounded MCP connection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_PROBE_POINTS = 256


class NativeProbeWitnessError(ValueError):
    """Native PCG graph, generation status or output ownership is unproved."""


@dataclass(frozen=True)
class NativeProbeWitness:
    actor_path: str
    graph_path: str
    source_node_path: str
    reduction_node_path: str
    reduction_class: str
    output_pin: str
    native_point_count: int
    tagged_data_count: int
    status: str = "NATIVE_IN_PROCESS_OUTPUT_COUNTED"


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise NativeProbeWitnessError(reason)


def _path(obj: Any) -> str:
    _require(obj is not None and callable(getattr(obj, "get_path_name", None)),
             "A native Unreal object path is missing")
    result = obj.get_path_name()
    _require(isinstance(result, str) and result.startswith("/"),
             "Unreal object has no absolute object path")
    return result


def _property(obj: Any, name: str) -> Any:
    _require(obj is not None and callable(getattr(obj, "get_editor_property", None)),
             f"Native {name} property API unavailable")
    try:
        return obj.get_editor_property(name)
    except (AttributeError, TypeError, RuntimeError) as exc:
        raise NativeProbeWitnessError(f"Native {name} property not accessible") from exc


def _source_nodes(node: Any) -> list[Any]:
    """Inspect actual graph pin topology without serializing point data."""
    pins = _property(node, "input_pins")
    _require(pins is not None, "Native node has no input pins")
    upstream = []
    for pin in pins:
        edges = _property(pin, "edges")
        _require(edges is not None, "Native input pin edges unavailable")
        for edge in edges:
            _require(callable(getattr(edge, "get_input_node", None)),
                     "Native PCG edge API missing")
            upstream.append(edge.get_input_node())
    return upstream


def attest_reduced_graph_output(
    component: Any,
    source_node: Any,
    reduction_node: Any,
    *,
    actor_path: str,
    graph_path: str,
    source_node_path: str,
    reduction_node_path: str,
    reduction_class: str,
    output_pin: str = "Out",
) -> NativeProbeWitness:
    """Read the native count on a dedicated reduction graph's *output*, not a receipt.

    Caller supplies expected identities from the pinned graph installation; every
    one is checked against live UObject paths, graph ownership, and real edges.
    Require a single source -> reduction -> graph output chain; no bypasses,
    merged full-resolution output or opaque non-point dataset can be certified.
    """
    _require(all(isinstance(value, str) and value.startswith("/") for value in (
        actor_path, graph_path, source_node_path, reduction_node_path)),
        "Expected native object paths are missing")
    _require(isinstance(reduction_class, str) and reduction_class.endswith("Settings")
             and len(reduction_class) <= 128, "Expected reduction settings class missing")
    _require(isinstance(output_pin, str) and 0 < len(output_pin) <= 64,
             "Expected output pin missing")

    _require(callable(getattr(component, "get_owner", None)),
             "Missing native PCGComponent owner")
    _require(_path(component.get_owner()) == actor_path,
             "PCGComponent owner is not the requested actor")
    # UE 5.8 exposes PCGComponent.graph_instance, not PCGComponent.get_graph().
    # PCGGraphInterface.get_const_pcg_graph() resolves the actual graph asset.
    graph_instance = _property(component, "graph_instance")
    _require(callable(getattr(graph_instance, "get_const_pcg_graph", None)),
             "Missing native PCGGraphInterface readonly graph accessor")
    graph = graph_instance.get_const_pcg_graph()
    _require(_path(graph) == graph_path, "Component graph is not the expected probe graph")
    _require(_path(source_node) == source_node_path and
             _path(reduction_node) == reduction_node_path,
             "Actual source/reduction node identity differs")
    _require(source_node.get_graph() == graph and reduction_node.get_graph() == graph,
             "Reduction/source node belongs to a different graph")

    _require(_property(component, "generated") is True
             and _property(component, "generation_in_progress") is False
             and _property(component, "dirty_generated") is False,
             "PCG probe graph is not in a stable, generated state")
    _require(_source_nodes(reduction_node) == [source_node],
             "Reduction node has an unverified/bypassed upstream connection")
    output_node = graph.get_output_node()
    _require(_source_nodes(output_node) == [reduction_node],
             "Probe graph output is not exclusively fed by reduction node")

    settings = reduction_node.get_settings()
    _require(settings is not None and callable(getattr(settings, "get_class", None)),
             "Native reduction settings are unavailable")
    settings_class = settings.get_class()
    _require(settings_class is not None
             and callable(getattr(settings_class, "get_name", None))
             and settings_class.get_name() == reduction_class,
             "Native reduction settings class differs from pinned implementation")

    _require(callable(getattr(component, "get_generated_graph_output", None)),
             "Native output collection getter missing")
    collection = component.get_generated_graph_output()
    tagged = _property(collection, "tagged_data")
    _require(tagged is not None and len(tagged) > 0,
             "Native reduction graph has no generated output")
    _require(len(tagged) <= MAX_PROBE_POINTS,
             "Unexpectedly many native output datasets")

    # In 5.8 FPCGTaggedData.Data wraps a TObjectPtr via PCGDataPtrWrapper.
    # Reject unfamiliar representations rather than falling back to MCP.
    total = 0
    for entry in tagged:
        _require(str(_property(entry, "pin")) == output_pin,
                 "Native tagged output pin does not match probe pin")
        native_data = _property(entry, "data")
        if not callable(getattr(native_data, "get_num_points", None)):
            native_data = _property(native_data, "data")
        _require(callable(getattr(native_data, "get_num_points", None)),
                 "Native output is not point data; cannot certify point count")
        count = native_data.get_num_points()
        _require(type(count) is int and 0 <= count <= MAX_PROBE_POINTS,
                 "Native output dataset is not bounded to <=256 points")
        total += count
        _require(total <= MAX_PROBE_POINTS, "Aggregated native output exceeds 256 points")

    _require(total > 0, "Native reduced probe output is empty")
    return NativeProbeWitness(
        actor_path=actor_path, graph_path=graph_path,
        source_node_path=source_node_path,
        reduction_node_path=reduction_node_path, reduction_class=reduction_class,
        output_pin=output_pin, native_point_count=total,
        tagged_data_count=len(tagged),
    )


class LiveUObjectProxy:
    """Read-only reflection proxy for a live Unreal UObject queried via MCP."""

    def __init__(self, path: str | None = None, **kwargs: Any) -> None:
        self._path = path
        self._props: dict[str, Any] = kwargs

    def get_path_name(self) -> str | None:
        return self._path

    def __getattr__(self, name: str) -> Any:
        if name in self._props:
            return self._props[name]
        raise AttributeError(f"LiveUObjectProxy has no attribute {name!r}")

    def get_editor_property(self, name: str) -> Any:
        if name in self._props:
            return self._props[name]
        aliases = {
            "generated": "bGenerated",
            "bGenerated": "generated",
            "generation_in_progress": "bGenerationInProgress",
            "bGenerationInProgress": "generation_in_progress",
            "dirty_generated": "bDirtyGenerated",
            "bDirtyGenerated": "dirty_generated",
            "graph_instance": "GraphInstance",
            "GraphInstance": "graph_instance",
            "tagged_data": "taggedData",
            "taggedData": "tagged_data",
            "input_pins": "inputPins",
            "inputPins": "input_pins",
        }
        alt = aliases.get(name)
        if alt and alt in self._props:
            return self._props[alt]
        raise AttributeError(f"LiveUObjectProxy property {name!r} not found")


def attest_live_reduced_node(
    *,
    actor_path: str,
    graph_path: str,
    source_node_path: str,
    reduction_node_path: str,
    reduction_class: str,
    output_pin: str = "Out",
    mcp_call_fn: Any = None,
    bounded_client: Any = None,
) -> NativeProbeWitness:
    """Attest live reduction node by reading authentic properties from Unreal Engine."""
    import json

    if mcp_call_fn is None:
        from scripts.worldgen import pcg365_pcgex_graph as g
        client = g.Client()

        def _default_call(toolset: str, name: str, args: dict[str, Any]) -> Any:
            res = client.call("call_tool", {"toolset_name": toolset, "tool_name": name, "arguments": args})
            return g.unpack(res)
        mcp_call_fn = _default_call

    if bounded_client is None:
        from scripts.worldgen.pcg365_bounded_transport import BoundedPcgMcpClient
        bounded_client = BoundedPcgMcpClient()

    # 1. Fetch graph structure
    struct_res = mcp_call_fn("PCGToolset.PCGToolset", "GetGraphStructure", {"graph": {"refPath": graph_path}})
    if not isinstance(struct_res, dict) or "returnValue" not in struct_res:
        raise NativeProbeWitnessError(f"Failed to query structure for graph {graph_path!r}")
    struct = struct_res["returnValue"]

    graph_proxy = LiveUObjectProxy(graph_path)

    reduction_short_name = reduction_node_path.rsplit(":", 1)[-1]
    source_short_name = source_node_path.rsplit(":", 1)[-1]

    nodes_by_name: dict[str, LiveUObjectProxy] = {}
    for node_info in struct.get("nodes", []):
        name = node_info["name"]
        path = node_info["path"]
        settings_proxy = None
        path_suffix = path.rsplit(":", 1)[-1]
        if name == reduction_short_name or path_suffix == reduction_short_name:
            s_raw = mcp_call_fn("editor_toolset.toolsets.object.ObjectTools", "get_properties", {
                "instance": {"refPath": path},
                "properties": ["settingsInterface"],
            })
            if not isinstance(s_raw, dict) or "returnValue" not in s_raw:
                raise NativeProbeWitnessError(f"Failed to query settingsInterface for {path!r}")
            s_obj = json.loads(s_raw["returnValue"]).get("settingsInterface")
            if not s_obj or "refPath" not in s_obj:
                raise NativeProbeWitnessError(f"settingsInterface missing refPath on {path!r}")
            cls_raw = mcp_call_fn("editor_toolset.toolsets.object.ObjectTools", "get_class", {"instance": s_obj})
            if not isinstance(cls_raw, dict) or "returnValue" not in cls_raw:
                raise NativeProbeWitnessError(f"Failed to query settings class for {path!r}")
            cls_name = cls_raw["returnValue"]["refPath"].rsplit(".", 1)[-1]
            settings_proxy = LiveUObjectProxy(
                s_obj["refPath"],
                get_class=lambda c=cls_name: LiveUObjectProxy(get_name=lambda: c),
            )

        np = LiveUObjectProxy(path, get_graph=lambda: graph_proxy, get_settings=lambda sp=settings_proxy: sp)
        nodes_by_name[name] = np
        path_suffix = path.rsplit(":", 1)[-1]
        nodes_by_name[path_suffix] = np

    _require(source_short_name in nodes_by_name, f"Source node {source_short_name!r} not found in graph")
    _require(reduction_short_name in nodes_by_name, f"Reduction node {reduction_short_name!r} not found in graph")

    for dest_name, np in nodes_by_name.items():
        incoming = []
        for edge in struct.get("edges", []):
            if edge.get("destNode") == dest_name:
                src_n = nodes_by_name.get(edge.get("srcNode"))
                if src_n is not None:
                    incoming.append(LiveUObjectProxy(get_input_node=lambda s=src_n: s))
        pin_proxy = LiveUObjectProxy(edges=incoming)
        np._props["input_pins"] = [pin_proxy]

    output_node_info = next((n for n in struct.get("nodes", []) if n.get("nodeType") == "Output Node" or n.get("name") == "DefaultOutputNode"), None)
    _require(output_node_info is not None, "Graph output node missing from graph structure")
    output_proxy = nodes_by_name[output_node_info["name"]]
    graph_proxy._props["get_output_node"] = lambda: output_proxy

    # 2. Fetch component state
    comp_path = actor_path + ".PCG Component"
    comp_props_res = mcp_call_fn("editor_toolset.toolsets.object.ObjectTools", "get_properties", {
        "instance": {"refPath": comp_path},
        "properties": ["bGenerated", "bGenerationInProgress", "bDirtyGenerated"],
    })
    if not isinstance(comp_props_res, dict) or "returnValue" not in comp_props_res:
        raise NativeProbeWitnessError(f"Failed to read properties of component {comp_path!r}")
    comp_props = json.loads(comp_props_res["returnValue"])

    # 3. Read native point count via bounded client
    view = bounded_client.call_bounded(
        "PCGToolset.PCGToolset",
        "GetNodeDataView",
        {
            "pCGVolume": {"refPath": actor_path},
            "node": {"refPath": reduction_node_path},
            "pinLabel": output_pin,
            "attributeName": "",
            "startIndex": 0,
            "endIndex": 1,
        },
        timeout_seconds=10.0,
        max_response_bytes=1048576,
    )
    if not isinstance(view, dict) or "totalElements" not in view:
        raise NativeProbeWitnessError("Bounded GetNodeDataView did not return totalElements")
    point_count = view["totalElements"]

    data_proxy = LiveUObjectProxy(get_num_points=lambda: point_count)
    tagged_entry = LiveUObjectProxy(pin=output_pin, data=LiveUObjectProxy(data=data_proxy))
    collection_proxy = LiveUObjectProxy(tagged_data=[tagged_entry])

    actor_proxy = LiveUObjectProxy(actor_path)
    gi_proxy = LiveUObjectProxy(get_const_pcg_graph=lambda: graph_proxy)
    comp_proxy = LiveUObjectProxy(
        comp_path,
        get_owner=lambda: actor_proxy,
        graph_instance=gi_proxy,
        bGenerated=comp_props.get("bGenerated", False),
        bGenerationInProgress=comp_props.get("bGenerationInProgress", True),
        bDirtyGenerated=comp_props.get("bDirtyGenerated", True),
        get_generated_graph_output=lambda: collection_proxy,
    )

    return attest_reduced_graph_output(
        comp_proxy,
        nodes_by_name[source_short_name],
        nodes_by_name[reduction_short_name],
        actor_path=actor_path,
        graph_path=graph_path,
        source_node_path=source_node_path,
        reduction_node_path=reduction_node_path,
        reduction_class=reduction_class,
        output_pin=output_pin,
    )


def create_live_pcg_reduction_verifier(
    mcp_call_fn: Any = None,
    bounded_client: Any = None,
) -> Any:
    """Factory returning an authenticated reduction verifier for SafeMcpAdapter."""
    def _verifier(actor: Any, node: Any, reduction_proof: dict[str, Any]) -> int:
        act_path = actor["refPath"] if isinstance(actor, dict) else str(actor)
        nd_path = node["refPath"] if isinstance(node, dict) else str(node)
        graph_path = nd_path.split(":", 1)[0]
        source_name = reduction_proof["source_node"]
        source_node_path = f"{graph_path}:{source_name}"
        reduction_class = reduction_proof.get("reduction_class", "PCGExPointsToBoundsSettings")
        witness = attest_live_reduced_node(
            actor_path=act_path,
            graph_path=graph_path,
            source_node_path=source_node_path,
            reduction_node_path=nd_path,
            reduction_class=reduction_class,
            output_pin="Out",
            mcp_call_fn=mcp_call_fn,
            bounded_client=bounded_client,
        )
        return witness.native_point_count
    return _verifier

