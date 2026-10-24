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
        super().__init__(
            path, input_pins=[Obj(edges=[Edge(source) for source in incoming])]
        )
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
            generated=True,
            generation_in_progress=False,
            dirty_generated=False,
            collection=Obj(
                tagged_data=[
                    Obj(pin="Out", data=Data(160)),
                    Obj(pin="Out", data=Data(96)),
                ]
            ),
        )
        self.expected = {
            "actor_path": ACTOR,
            "graph_path": GRAPH,
            "source_node_path": SOURCE,
            "reduction_node_path": REDUCE,
            "reduction_class": SETTINGS,
            "output_pin": "Out",
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
        self.assertEqual(witness.status, "NATIVE_LOCAL_INSPECTION_ONLY")
        from scripts.ue.pcg365_native_reduction_witness import (
            verify_witness_authenticity,
        )

        self.assertFalse(verify_witness_authenticity(witness))

    def test_native_data_wrapper_is_supported_without_serializing_rows(self):
        self.component.collection.tagged_data = [Obj(pin="Out", data=Obj(data=Data(3)))]
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
        with self.assertRaisesRegex(
            NativeProbeWitnessError, "data property not accessible|point data"
        ):
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
    def test_cpp_witness_requires_exact_uobject_paths(self):
        from pathlib import Path

        cpp = (
            Path(__file__).resolve().parents[2]
            / "Plugins/YacsPcgWitness/Source/YacsPcgWitness/Private/PCG/YacsPcgWitnessToolset.cpp"
        ).read_text(encoding="utf-8")
        self.assertIn("ActualPath == InSourceNodePath", cpp)
        self.assertIn("ActualPath == InReductionNodePath", cpp)
        self.assertNotIn("NodeMatchesPath", cpp)
        self.assertNotIn("GetAuthoredTitleName()", cpp)
        self.assertNotIn("FindObject<UPCGNode>", cpp)

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

    def test_reject_synthetic_proxy_as_native_buffer(self):
        from scripts.ue.pcg365_native_reduction_witness import (
            LiveUObjectProxy,
            NativeProbeWitnessError,
            attest_reduced_graph_output,
        )

        proxy_comp = LiveUObjectProxy("/Game/PCG.Component")
        proxy_source = LiveUObjectProxy(SOURCE)
        proxy_reduction = LiveUObjectProxy(REDUCE)
        with self.assertRaisesRegex(
            NativeProbeWitnessError, "SYNTHETIC_PROXY_PROHIBITED"
        ):
            attest_reduced_graph_output(
                proxy_comp,
                proxy_source,
                proxy_reduction,
                actor_path=ACTOR,
                graph_path=GRAPH,
                source_node_path=SOURCE,
                reduction_node_path=REDUCE,
                reduction_class=SETTINGS,
            )

    def test_reject_mcp_total_elements_as_independent_proof(self):
        """Attesting a live node without deployed native GameThread reader FAILS CLOSED."""
        from scripts.ue.pcg365_native_reduction_witness import (
            NativeProbeWitnessBlockedError,
            attest_live_reduced_node,
        )

        with self.assertRaisesRegex(
            NativeProbeWitnessBlockedError, "BLOCKED_PENDING_NATIVE_DEPLOYMENT"
        ):
            attest_live_reduced_node(
                actor_path=ACTOR,
                graph_path=GRAPH,
                source_node_path=GRAPH + ":SourceGrid",
                reduction_node_path=REDUCE,
                reduction_class=SETTINGS,
                output_pin="Out",
            )

    def test_reject_manually_constructed_witness(self):
        from scripts.ue.pcg365_native_reduction_witness import (
            NativeProbeWitness,
            verify_witness_authenticity,
        )

        fake_witness = NativeProbeWitness(
            actor_path=ACTOR,
            graph_path=GRAPH,
            source_node_path=SOURCE,
            reduction_node_path=REDUCE,
            reduction_class=SETTINGS,
            output_pin="Out",
            native_point_count=1,
            tagged_data_count=1,
            session_pid=1234,
            generation_token="fake_token",
            auth_token="forged_token_attempt",
        )
        self.assertFalse(verify_witness_authenticity(fake_witness))

    def test_reject_different_or_previous_session(self):
        from scripts.ue.pcg365_native_reduction_witness import (
            NativeProbeWitness,
            compute_witness_token,
            verify_witness_authenticity,
        )

        gen_token = "token123"
        valid_auth = compute_witness_token(ACTOR, GRAPH, REDUCE, 10, 1111, gen_token)
        witness_session_1111 = NativeProbeWitness(
            actor_path=ACTOR,
            graph_path=GRAPH,
            source_node_path=SOURCE,
            reduction_node_path=REDUCE,
            reduction_class=SETTINGS,
            output_pin="Out",
            native_point_count=10,
            tagged_data_count=1,
            session_pid=1111,
            generation_token=gen_token,
            auth_token=valid_auth,
        )
        # A caller-created signed value was never issued by the native reader.
        self.assertFalse(
            verify_witness_authenticity(witness_session_1111, expected_pid=1111)
        )
        # REJECTED for session 2222
        self.assertFalse(
            verify_witness_authenticity(witness_session_1111, expected_pid=2222)
        )

    def test_reader_receipt_parser_checks_exact_native_schema(self):
        from scripts.ue.pcg365_native_reduction_witness import (
            _validate_native_reader_receipt,
        )

        result = _validate_native_reader_receipt(
            self._receipt(),
            actor_path=ACTOR,
            graph_path=GRAPH,
            source_node_path=SOURCE,
            reduction_node_path=REDUCE,
            reduction_class=SETTINGS,
            output_pin="Out",
            expected_pid=45868,
        )
        self.assertEqual(result["native_point_count"], 42)

    def test_production_refuses_injected_reader_before_dispatch(self):
        from scripts.ue.pcg365_native_reduction_witness import (
            NativeProbeWitnessBlockedError,
            attest_live_reduced_node,
        )

        called = []

        def injected_reader(**kwargs):
            called.append(kwargs)
            return self._receipt()

        with self.assertRaisesRegex(
            NativeProbeWitnessBlockedError, "NATIVE_READER_INJECTION_PROHIBITED"
        ):
            attest_live_reduced_node(
                actor_path=ACTOR,
                graph_path=GRAPH,
                source_node_path=SOURCE,
                reduction_node_path=REDUCE,
                reduction_class=SETTINGS,
                native_reader_fn=injected_reader,
            )
        self.assertEqual(called, [])

    def test_create_live_pcg_reduction_verifier_propagates_blocked(self):
        from scripts.ue.pcg365_native_reduction_witness import (
            NativeProbeWitnessBlockedError,
            create_live_pcg_reduction_verifier,
        )

        verifier = create_live_pcg_reduction_verifier()
        proof = {
            "source_node": "SourceGrid",
            "reduction_class": SETTINGS,
        }
        with self.assertRaisesRegex(
            NativeProbeWitnessBlockedError, "BLOCKED_PENDING_NATIVE_DEPLOYMENT"
        ):
            verifier({"refPath": ACTOR}, {"refPath": REDUCE}, proof)

    @staticmethod
    def _receipt(**changes):
        receipt = {
            "status": "NATIVE_IN_PROCESS_OUTPUT_COUNTED",
            "session_pid": 45868,
            "actor_path": ACTOR,
            "graph_path": GRAPH,
            "source_node_path": SOURCE,
            "reduction_node_path": REDUCE,
            "reduction_class": SETTINGS,
            "output_pin": "Out",
            "native_point_count": 42,
            "tagged_data_count": 1,
            "generation_token": "test_generation_token",
        }
        receipt.update(changes)
        return receipt

    def _parse_receipt(self, receipt):
        from scripts.ue.pcg365_native_reduction_witness import (
            _validate_native_reader_receipt,
        )

        return _validate_native_reader_receipt(
            receipt,
            actor_path=ACTOR,
            graph_path=GRAPH,
            source_node_path=SOURCE,
            reduction_node_path=REDUCE,
            reduction_class=SETTINGS,
            output_pin="Out",
            expected_pid=45868,
        )

    def test_reader_error_is_rejected(self):
        with self.assertRaisesRegex(NativeProbeWitnessError, "OUTPUT_BYPASS_DETECTED"):
            self._parse_receipt(
                {"status": "ERROR", "error_code": "OUTPUT_BYPASS_DETECTED"}
            )

    def test_reader_mismatched_actor_is_rejected(self):
        with self.assertRaisesRegex(NativeProbeWitnessError, "actor_path"):
            self._parse_receipt(self._receipt(actor_path="/Game/OtherActor"))

    def test_reader_missing_identity_is_rejected(self):
        receipt = self._receipt()
        receipt.pop("source_node_path")
        with self.assertRaisesRegex(NativeProbeWitnessError, "source_node_path"):
            self._parse_receipt(receipt)

    def test_reader_missing_token_is_rejected(self):
        with self.assertRaisesRegex(NativeProbeWitnessError, "generation token"):
            self._parse_receipt(self._receipt(generation_token=""))

    def test_reader_overflow_is_rejected(self):
        with self.assertRaisesRegex(
            NativeProbeWitnessError, "point count 500 out of bounds"
        ):
            self._parse_receipt(self._receipt(native_point_count=500))

    def test_reader_other_pid_is_rejected(self):
        with self.assertRaisesRegex(NativeProbeWitnessError, "session_pid"):
            self._parse_receipt(self._receipt(session_pid=1234))

    def test_reader_requires_positive_dataset_count(self):
        with self.assertRaisesRegex(NativeProbeWitnessError, "tagged data count"):
            self._parse_receipt(self._receipt(tagged_data_count=0))

    def test_attest_live_reduced_node_via_bounded_mcp_client(self):
        from unittest.mock import patch, MagicMock
        from scripts.worldgen.pcg365_bounded_transport import BoundedPcgMcpClient
        from scripts.ue.pcg365_native_reduction_witness import (
            attest_live_reduced_node,
            verify_witness_authenticity,
        )

        fake_client = MagicMock(spec=BoundedPcgMcpClient)
        fake_client.is_poisoned = False
        fake_receipt = self._receipt(session_pid=45868)
        fake_client.call_bounded.return_value = fake_receipt

        with patch(
            "scripts.ue.pcg365_native_reduction_witness.get_live_editor_pid",
            return_value=45868,
        ):
            witness = attest_live_reduced_node(
                actor_path=ACTOR,
                graph_path=GRAPH,
                source_node_path=SOURCE,
                reduction_node_path=REDUCE,
                reduction_class=SETTINGS,
                output_pin="Out",
                bounded_client=fake_client,
            )
            self.assertEqual(witness.native_point_count, 42)
            self.assertEqual(witness.session_pid, 45868)
            self.assertTrue(verify_witness_authenticity(witness, expected_pid=45868))
            fake_client.call_bounded.assert_called_once_with(
                "YacsPcgWitness.YacsPcgWitnessToolset",
                "InspectReducedNodeOutput",
                {
                    "inActorPath": ACTOR,
                    "inGraphPath": GRAPH,
                    "inSourceNodePath": SOURCE,
                    "inReductionNodePath": REDUCE,
                    "inReductionClass": SETTINGS,
                    "inOutputPin": "Out",
                    "maxAllowedPoints": 256,
                },
                timeout_seconds=5.0,
                max_response_bytes=1024 * 1024,
            )

    def test_attest_live_reduced_node_via_failing_bounded_mcp_client(self):
        from unittest.mock import patch, MagicMock
        from scripts.worldgen.pcg365_bounded_transport import (
            BoundedPcgMcpClient,
            BoundedMcpTransportError,
        )
        from scripts.ue.pcg365_native_reduction_witness import (
            attest_live_reduced_node,
            NativeProbeWitnessBlockedError,
        )

        fake_client = MagicMock(spec=BoundedPcgMcpClient)
        fake_client.is_poisoned = False
        fake_client.call_bounded.side_effect = BoundedMcpTransportError(
            "Tool not found"
        )

        with patch(
            "scripts.ue.pcg365_native_reduction_witness.get_live_editor_pid",
            return_value=45868,
        ):
            with self.assertRaisesRegex(
                NativeProbeWitnessBlockedError, "BLOCKED_PENDING_NATIVE_DEPLOYMENT"
            ):
                attest_live_reduced_node(
                    actor_path=ACTOR,
                    graph_path=GRAPH,
                    source_node_path=SOURCE,
                    reduction_node_path=REDUCE,
                    reduction_class=SETTINGS,
                    output_pin="Out",
                    bounded_client=fake_client,
                )
