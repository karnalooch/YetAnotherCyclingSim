from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import unittest

from scripts.worldgen import pcg365_pcgex_graph as g
from scripts.worldgen.pcg365_wall_surface import (
    FOLDER,
    INPUT_SHA,
    ROLLOUT_MAP,
    SURFACE_SHA,
    check_continuous_surface,
    check_normal_transfer,
    replay,
    require_native_wall_admission,
)


class WallProofTests(unittest.TestCase):
    def setUp(self):
        def point(index, x, y, z, alpha):
            return {"@Points.$Transform": {"translation": [x, y, z], "rotation": [0, 0, 0, 1]},
                    "@Points.$Color": [0, 0, 1, alpha], "@Points.$Density": 1,
                    "@Points.PCGEx/VData": str(((index+1) << 32) | 2), "@Points.GroundHit": "true"}
        self.mesh = {"element_"+str(i): point(i, x, y, 3, a)
                     for i, (x, y, a) in enumerate([(0, 0, 0), (50, 0, .5), (50, 50, 1)])}
        self.encoded = deepcopy(self.mesh)
        self.ground, self.flat = deepcopy(self.mesh), deepcopy(self.mesh)
        for p in self.ground.values():
            p["@Points.$Transform"]["translation"][2] = 0
        for p in self.flat.values():
            p["@Points.$Transform"]["translation"][2] = 1000000
        self.source = {"records": [[0, 0, 1, 150], [0, 1, 1, 150], [1, 1, 1, 150]]}
        self.edges = {"element_"+str(i): {"@Points.PCGEx/EData": str((a << 32) | b)}
                      for i, (a, b) in enumerate([(1, 2), (2, 3), (1, 3)])}
        self.probes = {"element_"+str(i): {"@Points.GroundHit": "true", "@Points.GroundDistance": 1003} for i in range(3)}

    def verify(self):
        return check_continuous_surface(self.source, self.flat, self.ground,
                                        self.encoded, self.mesh, self.edges, self.probes)

    def test_valid_native_triangle(self):
        self.assertEqual(self.verify()["connected_surface_regions"], 1)
        self.assertEqual(check_normal_transfer(self.encoded, self.encoded, self.mesh)["vertices"], 3)

    def test_merged_but_disconnected_mesh_is_rejected(self):
        self.edges = [self.edges, deepcopy(self.edges)]
        with self.assertRaisesRegex(ValueError, "one connected"):
            self.verify()

    def test_missing_protected_input_is_rejected(self):
        self.source["records"].pop()
        with self.assertRaisesRegex(ValueError, "protected input"):
            self.verify()

    def test_insufficient_clearance_is_rejected(self):
        self.source["records"][0][3] = 60
        with self.assertRaisesRegex(ValueError, "clearance"):
            self.verify()

    def test_lost_material_alpha_is_rejected(self):
        self.mesh["element_1"]["@Points.$Color"][3] = 1
        with self.assertRaisesRegex(ValueError, "weight changed"):
            self.verify()

    def test_landscape_intersection_is_rejected(self):
        self.probes["element_1"]["@Points.GroundDistance"] = 999
        with self.assertRaisesRegex(ValueError, "intersects Landscape"):
            self.verify()

    def test_geometry_motion_is_rejected(self):
        self.mesh["element_1"]["@Points.$Transform"]["translation"][2] += 1
        with self.assertRaisesRegex(ValueError, "separation"):
            self.verify()

    def test_normal_drift_is_rejected(self):
        self.mesh["element_1"]["@Points.$Transform"]["rotation"] = [1, 0, 0, 0]
        with self.assertRaisesRegex(ValueError, "normal transfer"):
            check_normal_transfer(self.encoded, self.encoded, self.mesh)

    def test_check_normal_transfer_distinguishes_native_total_from_bounded_probe(self):
        result = check_normal_transfer(self.encoded, self.encoded, self.mesh, source_record_count=12619)
        self.assertEqual(result["vertices"], 3)
        self.assertIsNone(result["native_vertices"])
        self.assertFalse(result["native_vertex_count_verified"])
        self.assertEqual(result["source_record_count"], 12619)
        self.assertEqual(result["probe_vertices"], 3)
        self.assertLess(result["maximum_normal_vector_error"], 1e-5)

    def test_replay_refuses_unverified_native_work_before_client_or_files(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "must-not-exist"
            with patch.object(g, "Client") as client:
                with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_MCP_UNVERIFIED"):
                    replay(Path("missing"), Path("missing"), Path("missing"),
                           Path("missing"), Path("missing"), Path("missing"), output)
                client.assert_not_called()
            self.assertFalse(output.exists())

    @patch("scripts.worldgen.pcg365_wall_surface.validate_surface")
    @patch("scripts.worldgen.pcg365_whole_area.digest")
    @patch("scripts.worldgen.pcg365_pcgex_graph.Client")
    def test_replay_full_preparation_and_execution_without_variable_shadowing(
        self, mock_client_cls, mock_digest, mock_validate_surface
    ):
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            source_path = tmp_dir / "source.json"
            source_path.write_text("{}")
            surface_path = tmp_dir / "surface.json"
            surface_path.write_text("{}")
            camera_path = tmp_dir / "camera.json"
            camera_path.write_text(json.dumps({"translation": [0, 0, 0], "rotation": [0, 0, 0, 1]}))
            output_path = tmp_dir / "output_pilot"

            # Mock digests
            mock_digest.side_effect = lambda p: INPUT_SHA if p == source_path else "dummy_sha"

            # Mock surface with 12619 records
            records = [[0, 0, 1, 150], [0, 1, 1, 150], [1, 1, 1, 150]] + [[0, 0, 1, 150]] * 12616
            self.assertEqual(len(records), 12619)
            mock_validate_surface.return_value = {"records": records}

            # State JSON
            state_nodes = {
                "spawn_wall": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_spawn_wall"},
                "wall_envelope": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_wall_envelope"},
                "inside_wall": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_inside_wall"},
                "connected_cells": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_connected_cells"},
                "landscape_surface": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_landscape_surface"},
                "project_normals": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_project_normals"},
                "encode_normals": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_encode_normals"},
                "read_mesh": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_read_mesh"},
                "wall_surface": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_wall_surface"},
                "surface_separation": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_surface_separation"},
                "restore_wall_blend": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_restore_wall_blend"},
                "edge_probe": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface:Node_edge_probe"},
            }
            # Add chunk nodes
            for chunk in range(4):
                state_nodes[f"surface_grid_{chunk}"] = {
                    "refPath": FOLDER + f"/PCG365_WallSurface.PCG365_WallSurface:Node_surface_grid_{chunk}"
                }
            state = {
                "input_sha256": INPUT_SHA,
                "graph": {"refPath": FOLDER + "/PCG365_WallSurface.PCG365_WallSurface"},
                "continuous_wired": True,
                "material_blend_wired": True,
                "continuous_input_sha256": SURFACE_SHA,
                "normal_transfer_wired": True,
                "merged_mesh_wired": True,
                "nodes": state_nodes,
                "instance": {"actor": {"refPath": ROLLOUT_MAP + ".PCG365_WallSurface_Pilot"}},
            }
            state_path = tmp_dir / "state.json"
            state_path.write_text(json.dumps(state))

            # Adapter JSON
            adapter_data = {
                "path": FOLDER + "/BP_PCG365_VertexNormals",
                "graph": {"refPath": FOLDER + "/BP_PCG365_VertexNormals.BP_PCG365_VertexNormals:ProcessDynamicMesh"},
            }
            adapter_path = tmp_dir / "adapter.json"
            adapter_path.write_text(json.dumps(adapter_data))

            # Material JSON
            material_data = {
                "path": FOLDER + "/M_Cliff_BoundaryBlend",
                "instance_path": FOLDER + "/MI_Cliff_BoundaryBlend",
                "material": {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend"},
                "instance": {"refPath": FOLDER + "/MI_Cliff_BoundaryBlend.MI_Cliff_BoundaryBlend"},
                "targets": [
                    {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend:T0"},
                    {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend:T1"},
                    {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend:T2"},
                    {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend:T3"},
                ],
                "nodes": {
                    "rock": {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend:rock"},
                    "weights": {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend:weights"},
                    "vertex": {"refPath": FOLDER + "/M_Cliff_BoundaryBlend.M_Cliff_BoundaryBlend:vertex"},
                },
            }
            material_path = tmp_dir / "material.json"
            material_path.write_text(json.dumps(material_data))

            # Set up mock client
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.call.return_value = {
                "returnValue": {"image": {"data": base64.b64encode(b"PNG_DATA").decode()}}
            }

            dsl_graph_written = []
            assets_saved = []
            last_link = {}

            def mock_author_call(author_self, group, name, args):
                if name == "get_current_level":
                    return ROLLOUT_MAP
                if name == "find_actors":
                    actor_type = args.get("actor_type", {}).get("refPath", "")
                    if "PCGVolume" in actor_type:
                        return [state["instance"]["actor"]]
                    if "DynamicMeshActor" in actor_type:
                        return [f"road_{i}" for i in range(559)]
                    if "Landscape" in actor_type:
                        return ["landscape_0"]
                    return []
                if name == "ListGraphInstances":
                    return [{"actor": state["instance"]["actor"], "graph": state["graph"]}]
                if name == "get_properties":
                    instance = args.get("instance")
                    if instance == "landscape_0":
                        return {"LandscapeMaterial": "Landscape_Material_Ref"}
                    return {
                        "BodyInstance": {"collisionEnabled": "NoCollision"},
                        "OverrideMaterials": [material_data["instance"]],
                        "ParameterName": "WeightTex",
                        "bVisible": True,
                    }
                if name == "GetCameraTransform":
                    return {"translation": [0, 0, 0], "rotation": [0, 0, 0, 1]}
                if name == "SetCameraTransform":
                    return True
                if name == "GetNodeSchema":
                    return {"properties": ["bCopyAllAttributes", "inputSource", "outputTarget", "attributes", "baseRemap", "outputClampDetails", "config"]}
                if name == "CreateNode":
                    return {"refPath": FOLDER + f"/PCG365_WallSurface.PCG365_WallSurface:Node_{args.get('nodeName')}"}
                if name == "ConnectNodePins":
                    return []
                if name == "connect_expressions":
                    last_link["source"] = args.get("from_expression")
                    last_link["pin"] = args.get("to_input_name", "None") or "None"
                    return True
                if name == "get_expression_inputs":
                    return [{"expression": last_link.get("source"), "input_name": last_link.get("pin", "None")}]
                if name in ("UpdateNode", "set_properties", "recompile"):
                    return True
                if name == "ExecuteGraphInstance":
                    return []
                if name == "write_graph_dsl":
                    dsl_graph_written.append(args.get("graph"))
                    return True
                if name == "GetNodeDataView":
                    node_name = args.get("node", {}).get("refPath", "")
                    pin = args.get("pinLabel", "")
                    if "surface_separation" in node_name:
                        return self.encoded
                    if "restore_wall_blend" in node_name:
                        return self.encoded
                    if "read_mesh" in node_name:
                        return self.edges if pin == "Edges" else self.mesh
                    if "connected_cells" in node_name:
                        return self.flat
                    if "landscape_surface" in node_name:
                        return self.ground
                    if "edge_probe" in node_name:
                        return self.probes
                    return self.encoded
                if name == "get_components":
                    return ["wall_dynamic_mesh_comp"]
                if name == "save_assets":
                    assets_saved.extend(args.get("asset_paths", []))
                    return True
                return True

            # Synthetic replay is allowed only inside this isolated mocked unit
            # test. Production must remain blocked before Client.initialize.
            receipt_names = ("surface_separation", "restore_wall_blend", "read_mesh",
                             "connected_cells", "landscape_surface", "edge_probe")
            receipts = {name: {
                "reduction_node": name, "reduction_method": "BOUNDED_PROBE_NODE",
                "certified_point_count": 3, "source_node": name,
            } for name in receipt_names}
            with (
                patch.object(g.Author, "call", new=mock_author_call),
                patch("scripts.worldgen.pcg365_wall_surface.require_native_wall_admission"),
                patch("scripts.worldgen.pcg365_wall_surface.SafeMcpAdapter") as bounded_adapter,
            ):
                bounded_adapter.return_value.safe_get_node_data_view.side_effect = (
                    lambda **kw: mock_author_call(None, "", "GetNodeDataView",
                                                  {"node": kw["node"], "pinLabel": kw["pin_label"]})
                )
                proof = replay(
                    state_path=state_path,
                    source_path=source_path,
                    surface_path=surface_path,
                    adapter_path=adapter_path,
                    material_path=material_path,
                    camera_path=camera_path,
                    output=output_path,
                    hide_after=False,
                    native_probe_receipts=receipts,
                )

            # Assert proof properties
            self.assertIsNotNone(proof)
            self.assertEqual(proof["vertices"], 3)
            self.assertIsNone(proof["native_vertices"])
            self.assertFalse(proof["native_vertex_count_verified"])
            self.assertEqual(proof["source_record_count"], 12619)
            self.assertLessEqual(proof["probe_vertices"], 256)
            self.assertEqual(proof["component_count"], 1)

            # Assert no variable collision on adapter["graph"] and adapter["path"]
            self.assertEqual(len(dsl_graph_written), 1)
            self.assertEqual(dsl_graph_written[0], adapter_data["graph"])
            self.assertIn(adapter_data["path"], assets_saved)

            # Assert output native-proof.json exists
            self.assertTrue((output_path / "native-proof.json").exists())


class WallAdmissionGateTests(unittest.TestCase):
    def setUp(self):
        from scripts.ue.pcg365_native_reduction_witness import (
            NativeProbeWitness,
            compute_witness_token,
            get_live_editor_pid,
        )
        from scripts.worldgen.pcg365_bounded_transport import BoundedPcgMcpClient
        self.pid = get_live_editor_pid() or 0
        self.gen_token = "valid_generation_token"
        self.actor_path = ROLLOUT_MAP + ".PCGVolume"
        self.graph_path = "/Game/PCG/Graph.Graph"
        self.reduction_node_path = "/Game/PCG/Graph.Graph:Reduce"
        auth = compute_witness_token(
            self.actor_path,
            self.graph_path,
            self.reduction_node_path,
            1,
            self.pid,
            self.gen_token,
        )
        self.witness = NativeProbeWitness(
            actor_path=self.actor_path,
            graph_path=self.graph_path,
            source_node_path="/Game/PCG/Graph.Graph:Source",
            reduction_node_path=self.reduction_node_path,
            reduction_class="PCGExPointsToBoundsSettings",
            output_pin="Out",
            native_point_count=1,
            tagged_data_count=1,
            session_pid=self.pid,
            generation_token=self.gen_token,
            status="NATIVE_IN_PROCESS_OUTPUT_COUNTED",
            auth_token=auth,
        )
        self.client = BoundedPcgMcpClient()

    def test_admission_passes_with_authentic_witness_and_client(self):
        self.assertTrue(require_native_wall_admission(
            witness=self.witness,
            bounded_client=self.client,
            target_map_package=ROLLOUT_MAP,
            actor_path=self.actor_path,
        ))

    def test_admission_rejects_none(self):
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_MCP_UNVERIFIED"):
            require_native_wall_admission()

    def test_admission_rejects_target_map_none(self):
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_TARGET_MAP_REQUIRED"):
            require_native_wall_admission(
                witness=self.witness,
                bounded_client=self.client,
                target_map_package=None,
            )

    def test_admission_rejects_dict_witness(self):
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_INVALID_WITNESS"):
            require_native_wall_admission(
                witness={"native_point_count": 1},
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_forged_witness(self):
        from dataclasses import replace
        bad_witness = replace(self.witness, auth_token="forged_signature_value")
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_FORGED_WITNESS"):
            require_native_wall_admission(
                witness=bad_witness,
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_wrong_session_pid(self):
        from dataclasses import replace
        bad_witness = replace(self.witness, session_pid=999999)
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_FORGED_WITNESS|NATIVE_BLOCKED_SESSION_MISMATCH"):
            require_native_wall_admission(
                witness=bad_witness,
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_uncounted_status(self):
        from dataclasses import replace
        from scripts.ue.pcg365_native_reduction_witness import compute_witness_token
        auth = compute_witness_token(self.actor_path, self.graph_path, self.reduction_node_path, 1, self.pid, self.gen_token)
        bad_witness = replace(self.witness, status="UNVERIFIED_ESTIMATE", auth_token=auth)
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_UNCONFIRMED_STATUS"):
            require_native_wall_admission(
                witness=bad_witness,
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_unsafe_point_count(self):
        from dataclasses import replace
        from scripts.ue.pcg365_native_reduction_witness import compute_witness_token
        auth = compute_witness_token(self.actor_path, self.graph_path, self.reduction_node_path, 257, self.pid, self.gen_token)
        bad_witness = replace(self.witness, native_point_count=257, auth_token=auth)
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_UNSAFE_COUNT"):
            require_native_wall_admission(
                witness=bad_witness,
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_non_settings_class(self):
        from dataclasses import replace
        from scripts.ue.pcg365_native_reduction_witness import compute_witness_token
        auth = compute_witness_token(self.actor_path, self.graph_path, self.reduction_node_path, 1, self.pid, self.gen_token)
        bad_witness = replace(self.witness, reduction_class="PCGExCustomNode", auth_token=auth)
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_INVALID_SETTINGS"):
            require_native_wall_admission(
                witness=bad_witness,
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_untrusted_transport(self):
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_UNTRUSTED_TRANSPORT"):
            require_native_wall_admission(
                witness=self.witness,
                bounded_client=object(),
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_poisoned_transport(self):
        self.client._poisoned = True
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_POISONED_TRANSPORT"):
            require_native_wall_admission(
                witness=self.witness,
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
            )

    def test_admission_rejects_canonical_source_map_mutation(self):
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_PROTECTED_SOURCE_MAP"):
            require_native_wall_admission(
                witness=self.witness,
                bounded_client=self.client,
                target_map_package="/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface",
            )

    def test_admission_rejects_actor_assigned_to_wrong_level(self):
        with self.assertRaisesRegex(RuntimeError, "NATIVE_BLOCKED_ACTOR_LEVEL_MISMATCH"):
            require_native_wall_admission(
                witness=self.witness,
                bounded_client=self.client,
                target_map_package=ROLLOUT_MAP,
                actor_path="/Game/Generated/YACS/LiveCheckpoints/R2a00f7ebba40/L_RoadSurface.ForeignActor",
            )


if __name__ == "__main__":
    unittest.main()

