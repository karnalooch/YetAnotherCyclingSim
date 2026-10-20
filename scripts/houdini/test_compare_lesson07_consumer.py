"""Synthetic receipt-chain rejection tests; no Houdini or Unreal execution."""

from copy import deepcopy
import hashlib
import json
import math
import unittest
from unittest.mock import patch

from scripts.houdini import compare_lesson07_consumer as compare
from scripts.ue import readback_lesson07_geometry as reader
from scripts.ue import test_lesson07_readback as fixtures


class ConsumerLineageTests(unittest.TestCase):
    def setUp(self):
        # Reuse the reader's tiny physical map/backup/inventory fixture. This
        # exercises its real validator through the comparator, not a fake PASS.
        self.fixture = fixtures.RepairedPreparationBoundaryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.loader = patch.object(compare, "readback_validator", return_value=reader)
        self.loader.start()
        self.addCleanup(self.loader.stop)
        self.report = {
            "source_head": self.fixture.value["source_head"],
            "project_root": str(self.fixture.project), "level": compare.LEVEL,
            "engine_version": "5.8.2-56702186-fixture",
            "geometry_accepted": False, "candidate_map_unchanged": True,
            "map_before": deepcopy(self.fixture.value["map"]["source_identity"]),
            "map_after": deepcopy(self.fixture.value["map"]["source_identity"]),
            "repair_receipts_authenticated": True,
        }
        self.bind_staging()

    def bind_staging(self):
        self.report["map_lineage"] = deepcopy(self.fixture.value["map"])
        self.report["preparation_identity"] = reader.file_identity(self.fixture.manifest, 8 * 1024**2)
        self.fixture.report.write_text(json.dumps(self.report), encoding="utf-8")

    def validate(self):
        compare.validate_native_map(self.report, self.fixture.report)

    def test_repaired_map_revalidates_physical_receipts_and_preserves_source_pins(self):
        self.validate()
        self.assertFalse(self.report["geometry_accepted"])
        # Tampering after a valid measurement is rejected despite the retained
        # `repair_receipts_authenticated=true` boolean in the native JSON.
        self.fixture.receipt_path.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Untrusted repair"):
            self.validate()

    def test_claimed_authentication_without_the_real_chain_is_rejected(self):
        self.fixture.value["map"]["repair_receipts"] = []
        self.fixture.write_manifest()
        self.bind_staging()
        with self.assertRaisesRegex(ValueError, "receipt chain"):
            self.validate()
        self.fixture.write_receipt()
        self.bind_staging()
        self.report["repair_receipts_authenticated"] = False
        with self.assertRaisesRegex(ValueError, "requires an authenticated"):
            self.validate()

    def test_substituted_preparation_task_map_and_reader_cannot_inherit_lineage(self):
        original = deepcopy(self.fixture.value)
        for key, bad in (
            ("source_head", "b" * 40), ("level", "/Game/Other"),
            ("report_path", str(self.fixture.proof / "another-report.json")),
            ("candidate_root", str(self.fixture.project.parent / "unrelated")),
            ("geometry_accepted", True), ("dependency_closure_complete", True),
            ("reader_identity", {"sha256": "f" * 64}),
        ):
            self.fixture.value = {**deepcopy(original), key: bad}
            self.fixture.write_manifest()
            self.bind_staging()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate()

    def test_broken_map_chain_and_unauthorized_asset_change_fail_inside_shared_validator(self):
        self.fixture.receipt["files"][reader.MAP_FILE] = "f" * 64
        self.fixture.write_receipt()
        self.bind_staging()
        with self.assertRaisesRegex(ValueError, "broke map lineage"):
            self.validate()
        self.fixture.receipt["files"][reader.MAP_FILE] = self.fixture.original["sha256"]
        self.fixture.write_receipt()
        self.bind_staging()
        (self.fixture.project / self.fixture.material_relative).write_bytes(b"unapproved replacement")
        with self.assertRaisesRegex(ValueError, "Candidate asset"):
            self.validate()

    def test_current_map_drift_and_false_conservation_cannot_reuse_saved_report(self):
        self.report["map_after"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "map identity"):
            self.validate()
        self.report["map_after"] = deepcopy(self.report["map_before"])
        self.fixture.map.write_bytes(b"changed since readback")
        with self.assertRaisesRegex(ValueError, "changed since native"):
            self.validate()

    def test_original_receipt_requires_original_bytes_identity_without_repair_promotion(self):
        self.report["map_before"] = deepcopy(self.fixture.original)
        self.report["map_after"] = deepcopy(self.fixture.original)
        with self.assertRaisesRegex(ValueError, "cannot claim a repaired"):
            self.validate()
        self.report["repair_receipts_authenticated"] = False
        self.report["map_lineage"].pop("repair_receipts")
        self.validate()
        self.report["map_before"]["size_bytes"] += 1
        self.report["map_after"] = deepcopy(self.report["map_before"])
        with self.assertRaisesRegex(ValueError, "requires an authenticated"):
            self.validate()

    def test_repaired_current_pin_still_requires_the_entire_original_chain(self):
        current = self.report["map_before"]
        with patch.multiple(reader, MAP_SHA256=current["sha256"], MAP_SIZE=current["size_bytes"]):
            self.validate()
            self.report["repair_receipts_authenticated"] = False
            with self.assertRaisesRegex(ValueError, "staged task/map/lineage"):
                self.validate()
            self.report["repair_receipts_authenticated"] = True
            self.fixture.value["map"]["original_identity"] = current
            self.fixture.write_manifest()
            self.bind_staging()
            with self.assertRaisesRegex(ValueError, "original pinned"):
                self.validate()
            self.fixture.value["map"]["original_identity"] = self.fixture.original
            self.fixture.receipt["files"][reader.MAP_FILE] = current["sha256"]
            self.fixture.write_receipt()
            self.bind_staging()
            with self.assertRaisesRegex(ValueError, "broke map lineage"):
                self.validate()

    def test_current_copied_report_requires_authenticated_staging_and_both_material_pins(self):
        self.fixture = fixtures.PreparationBoundaryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        current = self.fixture.value["map"]["source_identity"]
        self.report.update(project_root=str(self.fixture.project), map_before=deepcopy(current),
                           map_after=deepcopy(current), repair_receipts_authenticated=False)
        self.bind_staging()
        self.validate()
        reference = self.report.pop("preparation_identity")
        with self.assertRaisesRegex(ValueError, "authenticated staging"):
            self.validate()
        self.report["preparation_identity"] = reference
        for relative in reader.CURRENT_MATERIAL_PINS:
            path = self.fixture.project / relative
            original = path.read_bytes()
            path.write_bytes(b"unapproved material")
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, "Candidate current material"):
                self.validate()
            path.write_bytes(original)

    def test_source_manifest_and_accepted_cache_pins_remain_mandatory_before_native_comparison(self):
        manifest = self.fixture.proof / "source-manifest.json"
        manifest.write_text(json.dumps({"accepted_l06_sha256": "f" * 64}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pinned 39390349735"):
            compare.validate_inputs(manifest, self.fixture.report)
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        with patch.object(compare, "MANIFEST_SHA256", digest):
            with self.assertRaisesRegex(ValueError, "another L06 cache"):
                compare.validate_inputs(manifest, self.fixture.report)


class InteriorSelectionTests(unittest.TestCase):
    class Volume:
        def __init__(self, value):
            self.value = value

        def posToIndex(self, position):
            return (round(position[0]*2), round(position[2]*2), 0)

        def indexToPos(self, index):
            return (index[0]/2, 0, index[1]/2)

        def isValidIndex(self, index):
            return all(0 <= n <= 8128 for n in index)

        def voxel(self, _index):
            return self.value

        def sample(self, _position):
            return self.value

    def setUp(self):
        self.actor = {"name": "SaCalobra_Unified_0_0", "location_cm": [0, 0, 0],
                      "rotation_deg_pitch_yaw_roll": [0, 0, 0], "scale": [50, 50, 128]}
        self.path = compare.LEVEL + ".World:PersistentLevel.SaCalobra_Unified_0_0.Component0"
        self.layout = {"observed": True, "component_path": self.path, "fields": {
            "component_size_quads": 254, "subsection_size_quads": 127, "num_subsections": 2,
            "section_base_x": 0, "section_base_y": 0}}
        self.height = self.Volume(1.0)

    def test_uniform_buffer_selects_both_real_source_classes_without_requiring_nodata_everywhere(self):
        for value in (0.0, 1.0):
            row, reason = compare.interior_candidate(self.height, self.Volume(value), self.actor, self.layout)
            self.assertIsNone(reason)
            self.assertEqual(row["source_validity"], int(value))
            self.assertEqual(row["uniform_source_patch_samples"], 64)
            self.assertEqual(len(row["source_corners"]), 4)
        self.assertEqual(compare.spread_interior_candidates([]), [])

    def test_mixed_patch_padding_and_changed_layout_cannot_be_selected(self):
        mixed = self.Volume(1.0)
        mixed.voxel = lambda index: float(index[0] >= 127)
        self.assertEqual(compare.interior_candidate(self.height, mixed, self.actor, self.layout),
                         (None, "mixed_source_validity_patch"))
        actor = {**self.actor, "location_cm": [394000, 0, 0]}
        self.assertEqual(compare.interior_candidate(self.height, self.Volume(0.0), actor, self.layout),
                         (None, "outside_original_source_rectangle"))
        bad = deepcopy(self.layout)
        bad["fields"]["section_base_x"] = 0
        bad["fields"]["num_subsections"] = 1
        with self.assertRaisesRegex(ValueError, "component lattice"):
            compare.interior_candidate(self.height, self.Volume(0.0), self.actor, bad)

    def test_source_selection_follows_rotated_actor_grid_and_is_independent_of_old_scale_z(self):
        actor = {**self.actor, "rotation_deg_pitch_yaw_roll": [0, -90, 0],
                 "location_cm": [0, 12800, 0], "scale": [50, 50, 561]}
        probe, reason = compare.interior_candidate(self.height, self.Volume(1), actor, self.layout)
        self.assertIsNone(reason)
        self.assertEqual([row["source_voxel_index"] for row in probe["source_corners"]],
                         [[127, 129, 0], [127, 128, 0], [128, 129, 0], [128, 128, 0]])
        actor["scale"][2] = 185
        self.assertEqual(compare.interior_candidate(self.height, self.Volume(1), actor, self.layout)[0], probe)

    def fixture_probe(self, validity):
        mask = self.Volume(float(validity))
        probe, _ = compare.interior_candidate(self.height, mask, self.actor, self.layout)
        probe["id"] = "fixture"
        samples = []
        for corner in probe["source_corners"]:
            x, _, y = corner["source_voxel_center_houdini_m"]
            q = compare.quantization_model(1.0, 128, 0)
            samples.append([q["predicted_height_u16_non_fused_float32"], x*100, y*100,
                            q["predicted_world_z_cm"], 0 if validity else 255])
        center = [math.fsum(row[i] for row in samples)/4 for i in (1, 2)]
        native = {"id": "fixture", "actor": probe["actor"], "component_path": self.path,
                  "observed": True, "error": None,
                  "native_corners": {"actor_name": probe["actor"], "component_path": self.path,
                                     "world_package": compare.LEVEL, "samples": samples,
                                     "vertex_indices": probe["local_vertex_indices"]},
                  "center_collision": {"observed": True, "hit": bool(validity),
                                       "query_xy_cm": center, "hit_actor": probe["actor"],
                                       "hit_render_component": self.path}}
        return mask, probe, native

    def test_interior_comparison_distinguishes_mask_unknown_mismatch_and_collision_class(self):
        for source_class in (0, 1):
            mask, probe, native = self.fixture_probe(source_class)
            value = compare.compare_interior_probe(self.height, mask, probe, native, self.actor)
            self.assertTrue(value["sampled_visibility_matches_source"])
            self.assertTrue(value["sampled_collision_hit_matches_source_class"])
            self.assertFalse(value["geometry_accepted"])
            self.assertFalse(value["source_triangle_interpolation_proved"])
            native["native_corners"]["samples"][0][4] = None
            self.assertIsNone(compare.compare_interior_probe(
                self.height, mask, probe, native, self.actor)["sampled_visibility_matches_source"])
            native["native_corners"]["samples"][0][4] = 255 if source_class else 0
            self.assertFalse(compare.compare_interior_probe(
                self.height, mask, probe, native, self.actor)["sampled_visibility_matches_source"])
            native["center_collision"]["hit"] = not bool(source_class)
            self.assertFalse(compare.compare_interior_probe(
                self.height, mask, probe, native, self.actor)["sampled_collision_hit_matches_source_class"])

    def test_actual_native_source_index_and_collision_component_are_not_assumed(self):
        mask, probe, native = self.fixture_probe(1)
        bad = deepcopy(native)
        bad["native_corners"]["samples"][0][1] += 50
        with self.assertRaisesRegex(ValueError, "another source voxel"):
            compare.compare_interior_probe(self.height, mask, probe, bad, self.actor)
        bad = deepcopy(native)
        bad["center_collision"]["hit_render_component"] = self.path + "Other"
        with self.assertRaisesRegex(ValueError, "render component"):
            compare.compare_interior_probe(self.height, mask, probe, bad, self.actor)

    def test_center_uses_fsum_and_still_rejects_a_one_ulp_coordinate_difference(self):
        mask, probe, native = self.fixture_probe(1)
        values = [6349.999999999998, 6399.999999999998, 6349.999999999998, 6400.000000000001]
        for sample, value in zip(native["native_corners"]["samples"], values):
            sample[1] = value
        accurate = math.fsum(values)/4
        sequential = ((values[0]+values[1])+values[2]+values[3])/4
        self.assertNotEqual(accurate, sequential)
        native["center_collision"]["query_xy_cm"][0] = accurate
        result = compare.compare_interior_probe(self.height, mask, probe, native, self.actor)
        self.assertTrue(result["sampled_collision_hit_matches_source_class"])
        native["center_collision"]["query_xy_cm"][0] = sequential
        with self.assertRaisesRegex(ValueError, "not the native quad center"):
            compare.compare_interior_probe(self.height, mask, probe, native, self.actor)


if __name__ == "__main__":
    unittest.main()
