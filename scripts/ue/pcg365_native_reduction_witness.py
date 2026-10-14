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
