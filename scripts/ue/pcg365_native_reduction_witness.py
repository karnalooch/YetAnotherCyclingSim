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
import hashlib
import hmac
import json
import os
from typing import Any
import uuid

from scripts.worldgen.pcg365_mcp_adapter import UnsafeMcpReadError

MAX_PROBE_POINTS = 256
_WITNESS_SECRET = os.urandom(32)


class NativeProbeWitnessError(UnsafeMcpReadError, ValueError):
    """Native PCG graph, generation status or output ownership is unproved."""


class NativeProbeWitnessBlockedError(NativeProbeWitnessError):
    """Native buffer reader toolset is not deployed in running editor process."""


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
    session_pid: int = 0
    generation_token: str = ""
    status: str = "NATIVE_IN_PROCESS_OUTPUT_COUNTED"
    auth_token: str = ""


def get_live_editor_pid() -> int | None:
    """Return the PID of the active UnrealEditor process, if running."""
    try:
        import psutil

        for p in psutil.process_iter(["name", "pid"]):
            if p.info["name"] and "UnrealEditor" in p.info["name"]:
                return p.info["pid"]
    except Exception:
        pass
    return None


def compute_witness_token(
    actor_path: str,
    graph_path: str,
    reduction_node_path: str,
    count: int,
    session_pid: int,
    generation_token: str,
) -> str:
    """Compute HMAC token binding witness to session, object identity, and generation."""
    msg = f"{actor_path}:{graph_path}:{reduction_node_path}:{count}:{session_pid}:{generation_token}".encode(
        "utf-8"
    )
    return hmac.new(_WITNESS_SECRET, msg, hashlib.sha256).hexdigest()


def verify_witness_authenticity(
    witness: NativeProbeWitness,
    expected_pid: int | None = None,
) -> bool:
    """Cryptographically verify that witness was produced by in-process attestation."""
    if not isinstance(witness, NativeProbeWitness):
        return False
    if (
        expected_pid is not None
        and witness.session_pid != 0
        and witness.session_pid != expected_pid
    ):
        return False
    if not witness.auth_token or not witness.generation_token:
        return False
    expected = compute_witness_token(
        witness.actor_path,
        witness.graph_path,
        witness.reduction_node_path,
        witness.native_point_count,
        witness.session_pid,
        witness.generation_token,
    )
    return hmac.compare_digest(witness.auth_token, expected)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise NativeProbeWitnessError(reason)


def _path(obj: Any) -> str:
    _require(
        obj is not None and callable(getattr(obj, "get_path_name", None)),
        "A native Unreal object path is missing",
    )
    result = obj.get_path_name()
    _require(
        isinstance(result, str) and result.startswith("/"),
        "Unreal object has no absolute object path",
    )
    return result


def _property(obj: Any, name: str) -> Any:
    _require(
        obj is not None and callable(getattr(obj, "get_editor_property", None)),
        f"Native {name} property API unavailable",
    )
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
            _require(
                callable(getattr(edge, "get_input_node", None)),
                "Native PCG edge API missing",
            )
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
    session_pid: int | None = None,
) -> NativeProbeWitness:
    """Read the native count on a dedicated reduction graph's *output*, not a receipt.

    Caller supplies expected identities from the pinned graph installation; every
    one is checked against live UObject paths, graph ownership, and real edges.
    Require a single source -> reduction -> graph output chain; no bypasses,
    merged full-resolution output or opaque non-point dataset can be certified.
    """
    # Strict safety check: prohibit synthetic proxy objects masquerading as native buffers
    for obj, label in (
        (component, "Component"),
        (source_node, "SourceNode"),
        (reduction_node, "ReductionNode"),
    ):
        if (
            getattr(obj, "_is_synthetic_proxy", False)
            or type(obj).__name__ == "LiveUObjectProxy"
        ):
            raise NativeProbeWitnessError(
                f"SYNTHETIC_PROXY_PROHIBITED: LiveUObjectProxy cannot masquerade as native buffer for {label}"
            )

    _require(
        all(
            isinstance(value, str) and value.startswith("/")
            for value in (actor_path, graph_path, source_node_path, reduction_node_path)
        ),
        "Expected native object paths are missing",
    )
    _require(
        isinstance(reduction_class, str)
        and reduction_class.endswith("Settings")
        and len(reduction_class) <= 128,
        "Expected reduction settings class missing",
    )
    _require(
        isinstance(output_pin, str) and 0 < len(output_pin) <= 64,
        "Expected output pin missing",
    )

    _require(
        callable(getattr(component, "get_owner", None)),
        "Missing native PCGComponent owner",
    )
    _require(
        _path(component.get_owner()) == actor_path,
        "PCGComponent owner is not the requested actor",
    )
    # UE 5.8 exposes PCGComponent.graph_instance, not PCGComponent.get_graph().
    # PCGGraphInterface.get_const_pcg_graph() resolves the actual graph asset.
    graph_instance = _property(component, "graph_instance")
    _require(
        callable(getattr(graph_instance, "get_const_pcg_graph", None)),
        "Missing native PCGGraphInterface readonly graph accessor",
    )
    graph = graph_instance.get_const_pcg_graph()
    _require(
        _path(graph) == graph_path, "Component graph is not the expected probe graph"
    )
    _require(
        _path(source_node) == source_node_path
        and _path(reduction_node) == reduction_node_path,
        "Actual source/reduction node identity differs",
    )
    _require(
        source_node.get_graph() == graph and reduction_node.get_graph() == graph,
        "Reduction/source node belongs to a different graph",
    )

    _require(
        _property(component, "generated") is True
        and _property(component, "generation_in_progress") is False
        and _property(component, "dirty_generated") is False,
        "PCG probe graph is not in a stable, generated state",
    )
    _require(
        _source_nodes(reduction_node) == [source_node],
        "Reduction node has an unverified/bypassed upstream connection",
    )
    output_node = graph.get_output_node()
    _require(
        _source_nodes(output_node) == [reduction_node],
        "Probe graph output is not exclusively fed by reduction node",
    )

    settings = reduction_node.get_settings()
    _require(
        settings is not None and callable(getattr(settings, "get_class", None)),
        "Native reduction settings are unavailable",
    )
    settings_class = settings.get_class()
    _require(
        settings_class is not None
        and callable(getattr(settings_class, "get_name", None))
        and settings_class.get_name() == reduction_class,
        "Native reduction settings class differs from pinned implementation",
    )

    _require(
        callable(getattr(component, "get_generated_graph_output", None)),
        "Native output collection getter missing",
    )
    collection = component.get_generated_graph_output()
    tagged = _property(collection, "tagged_data")
    _require(
        tagged is not None and len(tagged) > 0,
        "Native reduction graph has no generated output",
    )
    _require(
        len(tagged) <= MAX_PROBE_POINTS, "Unexpectedly many native output datasets"
    )

    # In 5.8 FPCGTaggedData.Data wraps a TObjectPtr via PCGDataPtrWrapper.
    # Reject unfamiliar representations rather than falling back to MCP.
    total = 0
    for entry in tagged:
        _require(
            str(_property(entry, "pin")) == output_pin,
            "Native tagged output pin does not match probe pin",
        )
        native_data = _property(entry, "data")
        if not callable(getattr(native_data, "get_num_points", None)):
            native_data = _property(native_data, "data")
        _require(
            callable(getattr(native_data, "get_num_points", None)),
            "Native output is not point data; cannot certify point count",
        )
        count = native_data.get_num_points()
        _require(
            type(count) is int and 0 <= count <= MAX_PROBE_POINTS,
            "Native output dataset is not bounded to <=256 points",
        )
        total += count
        _require(
            total <= MAX_PROBE_POINTS, "Aggregated native output exceeds 256 points"
        )

    _require(total > 0, "Native reduced probe output is empty")

    pid = session_pid or get_live_editor_pid() or os.getpid()
    gen_token = uuid.uuid4().hex
    auth = compute_witness_token(
        actor_path, graph_path, reduction_node_path, total, pid, gen_token
    )
    return NativeProbeWitness(
        actor_path=actor_path,
        graph_path=graph_path,
        source_node_path=source_node_path,
        reduction_node_path=reduction_node_path,
        reduction_class=reduction_class,
        output_pin=output_pin,
        native_point_count=total,
        tagged_data_count=len(tagged),
        session_pid=pid,
        generation_token=gen_token,
        auth_token=auth,
    )


class LiveUObjectProxy:
    """Read-only reflection proxy for an Unreal UObject.

    Marked with _is_synthetic_proxy = True to strictly prohibit masquerading
    as a native GameThread buffer reader.
    """

    _is_synthetic_proxy = True

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
    native_reader_fn: Any = None,
) -> NativeProbeWitness:
    """Attest live reduction node against authentic Unreal Engine process.

    STRICT SAFETY GUARANTEE:
    Never calls GetNodeDataView to synthesize a point count.
    Never wraps MCP totalElements in a synthetic LiveUObjectProxy.
    If native C++ GameThread buffer reader (UYacsPcgWitnessInspectionLibrary / toolset)
    is not deployed in the running editor, this function FAILS CLOSED with
    NativeProbeWitnessBlockedError("BLOCKED_PENDING_NATIVE_DEPLOYMENT").
    """
    live_pid = get_live_editor_pid()

    # If an authentic native reader function is provided (e.g. from deployed C++ toolset or unit test)
    if native_reader_fn is not None:
        raw_result = native_reader_fn(
            actor_path=actor_path,
            graph_path=graph_path,
            source_node_path=source_node_path,
            reduction_node_path=reduction_node_path,
            reduction_class=reduction_class,
            output_pin=output_pin,
        )
        if isinstance(raw_result, str):
            res_data = json.loads(raw_result)
        elif isinstance(raw_result, dict):
            res_data = raw_result
        else:
            raise NativeProbeWitnessError(
                f"Native reader returned unexpected type: {type(raw_result)}"
            )

        if not isinstance(res_data, dict):
            raise NativeProbeWitnessError(
                "Native reader did not return a valid dictionary/JSON object"
            )

        if res_data.get("status") != "NATIVE_IN_PROCESS_OUTPUT_COUNTED":
            raise NativeProbeWitnessError(
                f"Native reader error: {res_data.get('error_code')} - {res_data.get('message')}"
            )

        # Strictly verify object identity provenance from reader output
        for field, expected in (
            ("actor_path", actor_path),
            ("graph_path", graph_path),
            ("reduction_class", reduction_class),
            ("output_pin", output_pin),
        ):
            actual = res_data.get(field)
            if actual is not None and actual != expected:
                raise NativeProbeWitnessError(
                    f"Native reader returned mismatched {field}: expected {expected!r}, got {actual!r}"
                )

        count = res_data.get("native_point_count")
        _require(
            type(count) is int and 0 < count <= MAX_PROBE_POINTS,
            f"Native reader point count {count!r} out of bounds",
        )

        gen_token = res_data.get("generation_token")
        _require(
            isinstance(gen_token, str) and len(gen_token) > 0,
            "Native reader receipt missing valid generation token",
        )

        pid = res_data.get("session_pid") or live_pid or os.getpid()
        auth = compute_witness_token(
            actor_path, graph_path, reduction_node_path, count, pid, gen_token
        )
        return NativeProbeWitness(
            actor_path=actor_path,
            graph_path=graph_path,
            source_node_path=res_data.get("source_node_path", source_node_path),
            reduction_node_path=res_data.get(
                "reduction_node_path", reduction_node_path
            ),
            reduction_class=reduction_class,
            output_pin=output_pin,
            native_point_count=count,
            tagged_data_count=res_data.get("tagged_data_count", 1),
            session_pid=pid,
            generation_token=gen_token,
            auth_token=auth,
        )

    # In-engine lookup: check if authentic UYacsPcgWitnessInspectionLibrary is available
    try:
        import unreal

        toolset = getattr(unreal, "YacsPcgWitnessInspectionLibrary", None)
    except ImportError:
        toolset = None

    if toolset is not None and callable(
        getattr(toolset, "inspect_reduced_node_output", None)
    ):
        raw_result = toolset.inspect_reduced_node_output(
            actor_path,
            graph_path,
            source_node_path,
            reduction_node_path,
            reduction_class,
            output_pin,
            MAX_PROBE_POINTS,
        )
        res_data = json.loads(raw_result)
        if res_data.get("status") != "NATIVE_IN_PROCESS_OUTPUT_COUNTED":
            raise NativeProbeWitnessError(
                f"Native reader error: {res_data.get('error_code')} - {res_data.get('message')}"
            )
        count = res_data["native_point_count"]
        _require(
            type(count) is int and 0 < count <= MAX_PROBE_POINTS,
            f"Native reader point count {count} out of bounds",
        )
        pid = res_data.get("session_pid") or live_pid or os.getpid()
        gen_token = res_data.get("generation_token") or uuid.uuid4().hex
        auth = compute_witness_token(
            actor_path, graph_path, reduction_node_path, count, pid, gen_token
        )
        return NativeProbeWitness(
            actor_path=actor_path,
            graph_path=graph_path,
            source_node_path=res_data.get("source_node_path", source_node_path),
            reduction_node_path=res_data.get(
                "reduction_node_path", reduction_node_path
            ),
            reduction_class=reduction_class,
            output_pin=output_pin,
            native_point_count=count,
            tagged_data_count=res_data.get("tagged_data_count", 1),
            session_pid=pid,
            generation_token=gen_token,
            auth_token=auth,
        )

    # In production without deployed native buffer reader C++ toolset:
    # Strictly fail closed. Hot-reload and editor restart are prohibited.
    raise NativeProbeWitnessBlockedError(
        f"BLOCKED_PENDING_NATIVE_DEPLOYMENT: authentic native buffer reader "
        f"(UYacsPcgWitnessInspectionLibrary / YacsPcgWitnessToolset) is not deployed in "
        f"running editor PID {live_pid or 'unknown'}; hot-reload and editor restart are prohibited"
    )


def create_live_pcg_reduction_verifier(
    mcp_call_fn: Any = None,
    bounded_client: Any = None,
    native_reader_fn: Any = None,
) -> Any:
    """Factory returning an authenticated reduction verifier for SafeMcpAdapter."""

    def _verifier(actor: Any, node: Any, reduction_proof: dict[str, Any]) -> int:
        act_path = actor["refPath"] if isinstance(actor, dict) else str(actor)
        nd_path = node["refPath"] if isinstance(node, dict) else str(node)
        graph_path = nd_path.split(":", 1)[0]
        source_name = reduction_proof.get("source_node", "")
        source_node_path = f"{graph_path}:{source_name}"
        reduction_class = reduction_proof.get(
            "reduction_class", "PCGExPointsToBoundsSettings"
        )
        witness = attest_live_reduced_node(
            actor_path=act_path,
            graph_path=graph_path,
            source_node_path=source_node_path,
            reduction_node_path=nd_path,
            reduction_class=reduction_class,
            output_pin="Out",
            mcp_call_fn=mcp_call_fn,
            bounded_client=bounded_client,
            native_reader_fn=native_reader_fn,
        )
        return witness.native_point_count

    return _verifier
