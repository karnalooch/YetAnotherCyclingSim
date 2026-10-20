"""Safety checks for the bounded material adapter; no native proof claim."""
import copy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json

from scripts.ue import repair_lesson07_materials as repair


class MaterialRepairPreflight(unittest.TestCase):
    def setUp(self):
        self.project = Path("D:/yacs/work/candidate")
        self.files = {"Content/world.umap": "map", "Content/material.uasset": "material"}
        self.audit = {
            "status": "AUDIT_COMPLETE", "project": str(self.project),
            "files": self.files, "material": {"use_material_attributes": False},
            "instance_parent": repair.MASTER,
        }

    def test_unchanged_audit_passes(self):
        repair.validate_audit(self.audit, self.project, self.files)

    def test_stale_map_or_material_prevents_apply(self):
        for path in self.files:
            changed = {**self.files, path: "changed"}
            with self.assertRaisesRegex(RuntimeError, "changed since AUDIT"):
                repair.validate_audit(self.audit, self.project, changed)

    def test_asset_added_after_audit_prevents_apply(self):
        with self.assertRaisesRegex(RuntimeError, "changed since AUDIT"):
            repair.validate_audit(self.audit, self.project, {**self.files, "new": "bytes"})

    def test_different_project_failed_audit_and_unknown_parent_rejected(self):
        for key, value in (("status", "FAILED"), ("project", "another"),
                           ("instance_parent", "/Game/Other")):
            audit = copy.deepcopy(self.audit)
            audit[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                repair.validate_audit(audit, self.project, self.files)

    def test_attributes_graph_not_blindly_rewired(self):
        self.audit["material"]["use_material_attributes"] = True
        with self.assertRaisesRegex(RuntimeError, "separately inspected"):
            repair.validate_audit(self.audit, self.project, self.files)

    def test_attributes_requires_actual_engine_function_pins(self):
        self.audit["material"].update(use_material_attributes=True, attributes_node="ObservedTerminal")
        self.audit["opacity_override_function"] = {
            "path": repair.OPACITY_OVERRIDE,
            "expressions": [{"input_name": name} for name in ("Material", "Mask", "NewOpacityMask")],
        }
        repair.validate_audit(self.audit, self.project, self.files)
        self.audit["opacity_override_function"]["expressions"].pop()
        with self.assertRaisesRegex(RuntimeError, "pins were not authenticated"):
            repair.validate_audit(self.audit, self.project, self.files)

    def test_mi_blend_override_must_be_inspected_before_edit(self):
        self.audit["instance_blend_override"] = {"enabled": True}
        with self.assertRaisesRegex(RuntimeError, "blend override"):
            repair.validate_audit(self.audit, self.project, self.files)

    def test_inventory_detects_map_change_and_preserves_source_material_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            map_file = repair.package_file(root, repair.MAP, ".umap")
            material = repair.package_file(root, repair.MASTER)
            for file in (map_file, material):
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(b"original")
            before = repair.inventory(root)
            map_file.write_bytes(b"changed")
            after = repair.inventory(root)
            self.assertEqual(len(before), 2)
            self.assertNotEqual(before[str(map_file.relative_to(root))],
                                after[str(map_file.relative_to(root))])
            self.assertEqual(before[str(material.relative_to(root))],
                             after[str(material.relative_to(root))])

    def test_saved_visibility_graph_requires_real_three_input_wiring(self):
        graph = {
            "blend_mode": "BLEND_MASKED", "attributes_node": "override",
            "expressions": [
                {"name": "override", "class": "MaterialExpressionMaterialFunctionCall",
                 "material_function": repair.OPACITY_OVERRIDE,
                 "input_names": ["Material", "NewOpacityMask", "Mask"],
                 "inputs": ["MaterialExpressionSetMaterialAttributes_9", "visibility", "mask"]},
                {"name": "MaterialExpressionSetMaterialAttributes_9",
                 "class": "MaterialExpressionSetMaterialAttributes"},
                {"name": "visibility", "class": "MaterialExpressionLandscapeVisibilityMask"},
                {"name": "mask", "class": "MaterialExpressionConstant", "properties": {"r": 1.0}},
            ],
        }
        self.assertTrue(repair.visibility_contract(graph)["graph_contract_pass"])
        for index, replacement in ((0, "unknown"), (1, "mask"), (2, "visibility")):
            bad = copy.deepcopy(graph)
            bad["expressions"][0]["inputs"][index] = replacement
            with self.subTest(index=index):
                self.assertFalse(repair.visibility_contract(bad)["graph_contract_pass"])
        graph["expressions"][-1]["properties"]["r"] = 0.0
        self.assertFalse(repair.visibility_contract(graph)["graph_contract_pass"])

    def test_map_refresh_rejects_partial_native_work_before_save(self):
        valid = {"success": True, "actor_count": 4, "component_count": 4096,
                 "grass_type_reference_count_after": 0}
        repair.validate_refresh(valid)
        for key, value in (("success", False), ("actor_count", 3),
                           ("component_count", 4095), ("grass_type_reference_count_after", 1)):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                repair.validate_refresh({**valid, key: value})

    def test_whole_height_snapshot_rejects_missing_or_partial_proof(self):
        valid = {"success": True, "component_count": 4096,
                 "textures": [{"path": "native", "sha256": "digest"}]}
        repair.validate_height_snapshot(valid)
        for key, value in (("success", False), ("component_count", 1), ("textures", [])):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                repair.validate_height_snapshot({**valid, key: value})

    def test_actual_refresh_refuses_save_when_native_height_content_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            map_file = repair.package_file(project, repair.MAP, ".umap")
            map_file.parent.mkdir(parents=True)
            map_file.write_bytes(b"existing world")
            before = repair.inventory(project)
            world = Mock()
            world.get_path_name.return_value = repair.MAP + ".L_SaCalobra_Lesson07"
            material = Mock()
            material.get_path_name.return_value = repair.INSTANCE + ".MI_Landscape_Instance_YACS"
            class Landscape:
                def get_editor_property(self, key):
                    return material
            actors = [Landscape() for _ in range(4)]
            snapshot = {"success": True, "component_count": 4096,
                        "textures": [{"digest": "before"}]}
            changed = {**snapshot, "textures": [{"digest": "changed"}]}
            native = SimpleNamespace(
                read_lesson07_heightmap_hashes=Mock(side_effect=[json.dumps(snapshot), json.dumps(changed)]),
                refresh_lesson07_grass_caches=Mock(return_value=json.dumps({
                    "success": True, "actor_count": 4, "component_count": 4096,
                    "grass_type_reference_count_after": 0})),
            )
            saving = SimpleNamespace(load_map=Mock(return_value=world), save_map=Mock())
            fake = SimpleNamespace(
                EditorLoadingAndSavingUtils=saving, LandscapeProxy=Landscape,
                EditorActorSubsystem=object,
                get_editor_subsystem=Mock(return_value=SimpleNamespace(get_all_level_actors=lambda: actors)),
                YacsLandscapeMeshDiagnosticLibrary=native,
            )
            result = {"instance_parent": repair.DERIVATIVE,
                      "visibility_graph_contract": {"graph_contract_pass": True},
                      "instance_blend_override": {"enabled": False}}
            with patch.object(repair, "prior_receipt"), patch.object(
                repair.shutil, "disk_usage", return_value=SimpleNamespace(free=100 * 1024**3)
            ), self.assertRaisesRegex(RuntimeError, "content or identity changed"):
                repair.refresh_map(fake, project, project / "refresh.json", result, before)
            saving.save_map.assert_not_called()
            self.assertEqual(map_file.read_bytes(), b"existing world")


if __name__ == "__main__":
    unittest.main()
