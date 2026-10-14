from __future__ import annotations

import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch
import unittest

from scripts.worldgen import pcg365_pcgex_graph as g
from scripts.worldgen import pcg365_whole_area as w
from scripts.worldgen.pcg365_wall_surface import (
    FOLDER,
    INPUT_SHA,
    SURFACE_SHA,
    check_continuous_surface,
    check_normal_transfer,
    replay,
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
        result = check_normal_transfer(self.encoded, self.encoded, self.mesh, native_total_vertices=12619)
        self.assertEqual(result["vertices"], 12619)
        self.assertEqual(result["native_vertices"], 12619)
        self.assertEqual(result["probe_vertices"], 3)
        self.assertLess(result["maximum_normal_vector_error"], 1e-5)

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
                "instance": {"actor": {"refPath": "/Game/Generated/YACS/PCG365Ex/WallSurface/Pilot01.Actor"}},
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
                    return w.MAP
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

            with patch.object(g.Author, "call", new=mock_author_call):
                proof = replay(
                    state_path=state_path,
                    source_path=source_path,
                    surface_path=surface_path,
                    adapter_path=adapter_path,
                    material_path=material_path,
                    camera_path=camera_path,
                    output=output_path,
                    hide_after=False,
                )

            # Assert proof properties
            self.assertIsNotNone(proof)
            self.assertEqual(proof["vertices"], 12619)
            self.assertEqual(proof["native_vertices"], 12619)
            self.assertLessEqual(proof["probe_vertices"], 256)
            self.assertEqual(proof["component_count"], 1)

            # Assert no variable collision on adapter["graph"] and adapter["path"]
            self.assertEqual(len(dsl_graph_written), 1)
            self.assertEqual(dsl_graph_written[0], adapter_data["graph"])
            self.assertIn(adapter_data["path"], assets_saved)

            # Assert output native-proof.json exists
            self.assertTrue((output_path / "native-proof.json").exists())


if __name__ == "__main__":
    unittest.main()
