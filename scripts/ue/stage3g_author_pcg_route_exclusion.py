"""Author the Stage 3G R2 PCG_RouteExclusion graph deterministically."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import traceback

import unreal


PACKAGE = "/Game/YACS/WorldGen/PCG"
ASSET_NAME = "PCG_RouteExclusion"
ASSET_PATH = PACKAGE + "/" + ASSET_NAME
PROTECTED_HALF_WIDTH_M = 4.0


def fail(message: str) -> None:
    raise RuntimeError(message)


def log(message: str) -> None:
    unreal.log("[Stage3GR2PCGRouteExclusion] {}".format(message))


def first_pin_label(node: unreal.PCGNode, property_name: str) -> unreal.Name:
    pins = list(node.get_editor_property(property_name) or [])
    if not pins:
        fail("{} exposes no {}".format(node.get_name(), property_name))
    props = pins[0].get_editor_property("properties")
    return props.get_editor_property("label")


def main() -> None:
    proof_value = os.environ.get(
        "YACS_STAGE3G_R2_PCG_ROUTE_EXCLUSION_PROOF", ""
    )
    if not proof_value:
        fail("YACS_STAGE3G_R2_PCG_ROUTE_EXCLUSION_PROOF is not set")

    if not hasattr(unreal, "Stage3GRouteExclusionSettings"):
        fail("editor module did not expose Stage3GRouteExclusionSettings to Python")

    if not unreal.EditorAssetLibrary.does_directory_exist(PACKAGE):
        if not unreal.EditorAssetLibrary.make_directory(PACKAGE):
            fail("failed to create {}".format(PACKAGE))

    if unreal.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        if not unreal.EditorAssetLibrary.delete_asset(ASSET_PATH):
            fail("failed to replace existing {}".format(ASSET_PATH))

    graph = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        ASSET_NAME,
        PACKAGE,
        unreal.PCGGraph,
        unreal.PCGGraphFactory(),
    )
    if not graph or not isinstance(graph, unreal.PCGGraph):
        fail("failed to create {}".format(ASSET_PATH))

    filter_node, settings = graph.add_node_of_type(
        unreal.Stage3GRouteExclusionSettings
    )
    if not filter_node or not settings:
        fail("failed to add YACS Route Exclusion node")

    settings.set_editor_property(
        "protected_half_width_m", PROTECTED_HALF_WIDTH_M
    )
    filter_node.set_node_position(-100, 0)

    input_node = graph.get_editor_property("input_node")
    output_node = graph.get_editor_property("output_node")
    if not input_node or not output_node:
        fail("PCG graph input/output nodes are unavailable")

    input_output_label = first_pin_label(input_node, "output_pins")
    filter_input_label = first_pin_label(filter_node, "input_pins")
    filter_output_label = first_pin_label(filter_node, "output_pins")
    graph_output_label = first_pin_label(output_node, "input_pins")

    if not graph.add_edge(
        input_node,
        input_output_label,
        filter_node,
        filter_input_label,
    ):
        fail("failed to connect graph input to route exclusion")
    if not graph.add_edge(
        filter_node,
        filter_output_label,
        output_node,
        graph_output_label,
    ):
        fail("failed to connect route exclusion to graph output")

    graph.set_editor_property(
        "description",
        unreal.Text(
            "Stage 3G deterministic 4 m route-clearance filter. "
            "Consumes authoritative YACS route geometry; never owns route truth."
        ),
    )
    graph.set_editor_property("expose_to_library", True)

    if not unreal.EditorAssetLibrary.save_asset(
        ASSET_PATH, only_if_is_dirty=False
    ):
        fail("failed to save {}".format(ASSET_PATH))

    reloaded = unreal.EditorAssetLibrary.load_asset(ASSET_PATH)
    if not reloaded or not isinstance(reloaded, unreal.PCGGraph):
        fail("saved PCG_RouteExclusion cannot be reloaded")

    custom_nodes = [
        node
        for node in list(reloaded.get_editor_property("nodes") or [])
        if isinstance(
            node.get_settings(),
            unreal.Stage3GRouteExclusionSettings,
        )
    ]
    if len(custom_nodes) != 1:
        fail(
            "expected exactly one YACS Route Exclusion node after reload; found {}"
            .format(len(custom_nodes))
        )

    saved_settings = custom_nodes[0].get_settings()
    saved_half_width = float(
        saved_settings.get_editor_property("protected_half_width_m")
    )
    if abs(saved_half_width - PROTECTED_HALF_WIDTH_M) > 1e-9:
        fail(
            "saved protected half-width is {}, expected {}"
            .format(saved_half_width, PROTECTED_HALF_WIDTH_M)
        )

    proof = {
        "stage3g_r2_pcg_route_exclusion": "success",
        "asset_path": ASSET_PATH,
        "protected_half_width_m": saved_half_width,
        "node_class": saved_settings.get_class().get_name(),
        "graph_node_count": len(
            list(reloaded.get_editor_property("nodes") or [])
        ),
        "route_truth": "FRouteGeometryProfile",
        "worldspec_seed": 42017,
    }

    proof_path = Path(proof_value)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(
        json.dumps(proof, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log("SUCCESS: authored {}".format(ASSET_PATH))


try:
    main()
except Exception as exc:
    unreal.log_error(
        "[Stage3GR2PCGRouteExclusion] FAILURE: {}".format(exc)
    )
    unreal.log_error(traceback.format_exc())
    sys.exit(1)
