"""No-Unreal regression tests for the real-object, no-MCP PCG reduction witness."""
from __future__ import annotations

import unittest

from scripts.ue.pcg365_native_reduction_witness import (
    NativeProbeWitnessError,
    attest_reduced_graph_output,
)

ACTOR = "/Game/PCG365/Preview.Preview:ProbeActor"
GRAPH = "/Game/PCG365/Reduction.Reduction"
SOURCE = GRAPH + ":SourceNode"
REDUCE = GRAPH + ":ReducedNode"
SETTINGS = "PCGExDownsampleSettings"


class Obj:
    def __init__(self, path=None, **kwargs):
        self.path = path
        self.__dict__.update(kwargs)

    def get_path_name(self):
        return self.path

    def get_editor_property(self, name):
        return getattr(self, name)


class Edge:
    def __init__(self, source):
        self.source = source

    def get_input_node(self):
        return self.source


class Data:
    def __init__(self, count):
        self.count = count

    def get_num_points(self):
        return self.count


class Node(Obj):
    def __init__(self, path, graph, incoming):
        super().__init__(path, input_pins=[Obj(edges=[Edge(source) for source in incoming])])
        self.graph = graph

    def get_graph(self):
        return self.graph

    def get_settings(self):
        return Obj(get_class=lambda: Obj(get_name=lambda: SETTINGS))


class Graph(Obj):
    def get_output_node(self):
        return self.output


class Component(Obj):
    def get_owner(self):
        return Obj(ACTOR)

    def get_generated_graph_output(self):
        return self.collection


class NativeReductionWitnessTests(unittest.TestCase):
    def setUp(self):
        self.graph = Graph(GRAPH)
        self.source = Node(SOURCE, self.graph, [])
        self.reduction = Node(REDUCE, self.graph, [self.source])
        self.graph.output = Node(GRAPH + ":OutputNode", self.graph, [self.reduction])
        self.component = Component(
            graph_instance=Obj(get_const_pcg_graph=lambda: self.graph),
            generated=True, generation_in_progress=False,
            dirty_generated=False, collection=Obj(
                tagged_data=[Obj(pin="Out", data=Data(160)), Obj(pin="Out", data=Data(96))]
            )
        )
        self.expected = {
            "actor_path": ACTOR, "graph_path": GRAPH,
            "source_node_path": SOURCE, "reduction_node_path": REDUCE,
            "reduction_class": SETTINGS, "output_pin": "Out",
        }

    def attest(self):
        return attest_reduced_graph_output(
            self.component, self.source, self.reduction, **self.expected
        )

    def test_count_is_read_from_actual_native_data_not_receipt(self):
        witness = self.attest()
        self.assertEqual(witness.native_point_count, 256)
        self.assertEqual(witness.tagged_data_count, 2)
        self.assertEqual(witness.reduction_node_path, REDUCE)
        self.assertEqual(witness.status, "NATIVE_IN_PROCESS_OUTPUT_COUNTED")

    def test_native_data_wrapper_is_supported_without_serializing_rows(self):
        self.component.collection.tagged_data = [Obj(
            pin="Out", data=Obj(data=Data(3))
        )]
        self.assertEqual(self.attest().native_point_count, 3)

    def test_actual_native_data_over_limit_rejected_even_with_small_claim(self):
        self.component.collection.tagged_data[0].data = Data(100000)
        with self.assertRaisesRegex(NativeProbeWitnessError, "256"):
            self.attest()

    def test_combined_native_output_over_limit_rejected(self):
        self.component.collection.tagged_data[1].data = Data(97)
        with self.assertRaisesRegex(NativeProbeWitnessError, "Aggregated"):
            self.attest()

    def test_bypassed_reduction_node_rejected(self):
        self.graph.output.input_pins[0].edges = [Edge(self.source)]
        with self.assertRaisesRegex(NativeProbeWitnessError, "exclusively"):
            self.attest()

    def test_additional_full_resolution_branch_rejected(self):
        self.graph.output.input_pins[0].edges.append(Edge(self.source))
        with self.assertRaisesRegex(NativeProbeWitnessError, "exclusively"):
            self.attest()

    def test_reduction_input_drift_rejected(self):
        self.reduction.input_pins[0].edges = []
        with self.assertRaisesRegex(NativeProbeWitnessError, "upstream"):
            self.attest()

    def test_node_path_drift_rejected(self):
        self.reduction.path = REDUCE + "_Other"
        with self.assertRaisesRegex(NativeProbeWitnessError, "identity differs"):
            self.attest()

    def test_missing_graph_instance_rejected_before_count(self):
        del self.component.graph_instance
        with self.assertRaisesRegex(NativeProbeWitnessError, "graph_instance property"):
            self.attest()

    def test_graph_instance_resolves_wrong_asset_rejected(self):
        self.component.graph_instance = Obj(
            get_const_pcg_graph=lambda: Graph("/Game/Unrelated/PCG")
        )
        with self.assertRaisesRegex(NativeProbeWitnessError, "expected probe graph"):
            self.attest()

    def test_unrelated_graph_rejected(self):
        self.reduction.graph = Graph("/Game/Wrong/Wrong")
        with self.assertRaisesRegex(NativeProbeWitnessError, "different graph"):
            self.attest()

    def test_native_settings_class_drift_rejected(self):
        self.expected["reduction_class"] = "PCGExAnythingSettings"
        with self.assertRaisesRegex(NativeProbeWitnessError, "settings class differs"):
            self.attest()

    def test_generation_in_progress_is_rejected(self):
        self.component.generation_in_progress = True
        with self.assertRaisesRegex(NativeProbeWitnessError, "stable, generated"):
            self.attest()

    def test_dirty_generation_is_rejected(self):
        self.component.dirty_generated = True
        with self.assertRaisesRegex(NativeProbeWitnessError, "stable, generated"):
            self.attest()

    def test_forged_or_missing_native_data_rejected(self):
        self.component.collection.tagged_data = [Obj(pin="Out", data=Obj())]
        with self.assertRaisesRegex(NativeProbeWitnessError, "data property not accessible|point data"):
            self.attest()

    def test_empty_output_does_not_certify_a_probe(self):
        self.component.collection.tagged_data = [Obj(pin="Out", data=Data(0))]
        with self.assertRaisesRegex(NativeProbeWitnessError, "empty"):
            self.attest()

    def test_wrong_output_pin_rejected(self):
        self.component.collection.tagged_data[0].pin = "Main"
        with self.assertRaisesRegex(NativeProbeWitnessError, "pin"):
            self.attest()


class LiveWitnessProxyTests(unittest.TestCase):
    def test_proxy_alias_and_attribute_resolution(self):
        from scripts.ue.pcg365_native_reduction_witness import LiveUObjectProxy
        proxy = LiveUObjectProxy(
            "/Game/Test.Test",
            bGenerated=True,
            bGenerationInProgress=False,
            GraphInstance="Instance",
            taggedData=[1, 2],
        )
        self.assertEqual(proxy.get_path_name(), "/Game/Test.Test")
        self.assertTrue(proxy.get_editor_property("generated"))
        self.assertTrue(proxy.get_editor_property("bGenerated"))
        self.assertFalse(proxy.get_editor_property("generation_in_progress"))
        self.assertFalse(proxy.get_editor_property("bGenerationInProgress"))
        self.assertEqual(proxy.get_editor_property("graph_instance"), "Instance")
        self.assertEqual(proxy.get_editor_property("tagged_data"), [1, 2])
        with self.assertRaises(AttributeError):
            proxy.get_editor_property("unknown_prop")

    def test_attest_live_reduced_node_success(self):
        import json
        from scripts.ue.pcg365_native_reduction_witness import (
            attest_live_reduced_node,
            create_live_pcg_reduction_verifier,
        )

        def mock_call(toolset, name, args):
            if name == "GetGraphStructure":
                return {
                    "returnValue": {
                        "nodes": [
                            {"name": "SourceGrid", "path": GRAPH + ":SourceGrid"},
                            {"name": "ReducedNode", "path": REDUCE},
                            {"name": "DefaultOutputNode", "path": GRAPH + ":DefaultOutputNode", "nodeType": "Output Node"},
                        ],
                        "edges": [
                            {"srcNode": "SourceGrid", "destNode": "ReducedNode"},
                            {"srcNode": "ReducedNode", "destNode": "DefaultOutputNode"},
                        ],
                    }
                }
            if name == "get_properties":
                instance_path = args["instance"]["refPath"]
                if "ReducedNode" in instance_path or "ReduceToBounds" in instance_path:
                    return {"returnValue": json.dumps({"settingsInterface": {"refPath": REDUCE + ".Settings"}})}
                if "PCG Component" in instance_path:
                    return {"returnValue": json.dumps({"bGenerated": True, "bGenerationInProgress": False, "bDirtyGenerated": False})}
            if name == "get_class":
                return {"returnValue": {"refPath": "/Script/PCGExElementsSpatial." + SETTINGS}}
            raise ValueError(f"Unexpected mock call: {toolset}.{name}")

        class MockBoundedClient:
            def call_bounded(self, toolset, name, args, **kwargs):
                return {"totalElements": 42}

        witness = attest_live_reduced_node(
            actor_path=ACTOR,
            graph_path=GRAPH,
            source_node_path=GRAPH + ":SourceGrid",
            reduction_node_path=REDUCE,
            reduction_class=SETTINGS,
            output_pin="Out",
            mcp_call_fn=mock_call,
            bounded_client=MockBoundedClient(),
        )
        self.assertEqual(witness.native_point_count, 42)
        self.assertEqual(witness.actor_path, ACTOR)
        self.assertEqual(witness.reduction_node_path, REDUCE)

        # Verify through verifier factory
        verifier = create_live_pcg_reduction_verifier(
            mcp_call_fn=mock_call,
            bounded_client=MockBoundedClient(),
        )
        proof = {
            "source_node": "SourceGrid",
            "reduction_class": SETTINGS,
        }
        count = verifier({"refPath": ACTOR}, {"refPath": REDUCE}, proof)
        self.assertEqual(count, 42)

    def test_attest_live_reduced_node_rejects_unstable_component(self):
        import json
        from scripts.ue.pcg365_native_reduction_witness import (
            NativeProbeWitnessError,
            attest_live_reduced_node,
        )

        def mock_call(toolset, name, args):
            if name == "GetGraphStructure":
                return {
                    "returnValue": {
                        "nodes": [
                            {"name": "SourceGrid", "path": GRAPH + ":SourceGrid"},
                            {"name": "ReducedNode", "path": REDUCE},
                            {"name": "DefaultOutputNode", "path": GRAPH + ":DefaultOutputNode", "nodeType": "Output Node"},
                        ],
                        "edges": [
                            {"srcNode": "SourceGrid", "destNode": "ReducedNode"},
                            {"srcNode": "ReducedNode", "destNode": "DefaultOutputNode"},
                        ],
                    }
                }
            if name == "get_properties":
                instance_path = args["instance"]["refPath"]
                if "ReducedNode" in instance_path or "ReduceToBounds" in instance_path:
                    return {"returnValue": json.dumps({"settingsInterface": {"refPath": REDUCE + ".Settings"}})}
                if "PCG Component" in instance_path:
                    # In progress!
                    return {"returnValue": json.dumps({"bGenerated": True, "bGenerationInProgress": True, "bDirtyGenerated": False})}
            if name == "get_class":
                return {"returnValue": {"refPath": "/Script/PCGExElementsSpatial." + SETTINGS}}
            raise ValueError(f"Unexpected mock call: {toolset}.{name}")

        class MockBoundedClient:
            def call_bounded(self, toolset, name, args, **kwargs):
                return {"totalElements": 10}

        with self.assertRaisesRegex(NativeProbeWitnessError, "stable, generated"):
            attest_live_reduced_node(
                actor_path=ACTOR,
                graph_path=GRAPH,
                source_node_path=GRAPH + ":SourceGrid",
                reduction_node_path=REDUCE,
                reduction_class=SETTINGS,
                output_pin="Out",
                mcp_call_fn=mock_call,
                bounded_client=MockBoundedClient(),
            )

