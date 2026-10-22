"""Fail-closed Pegasus Lesson07 closeout contract.

This is a structural proof about the tracked execution plan, not a native
Houdini/UE execution or permission to claim visual completion.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATES = REPO / "docs/tooling/sidefx/PEGASUS_L07_GATES_20261022.json"
PLAN = REPO / "docs/tooling/sidefx/PEGASUS_L07_FINALE_20261022.md"
VALID_STATUS = {"PASS_BOUNDED", "PASS_DIAGNOSTIC", "PASS_FULL", "BLOCKED", "DEFERRED"}


def load_plan() -> dict:
    result = json.loads(GATES.read_text(encoding="utf-8"))
    assert result["schema_version"] == 1
    assert result["program"] == "YACS-M3-PEG-02-07"
    assert result["document"] == str(PLAN.relative_to(REPO)).replace("\\", "/")
    assert PLAN.is_file() and len(PLAN.read_text(encoding="utf-8")) > 15000
    return result


class Lesson07PlanTests(unittest.TestCase):
    def test_all_gates_in_expected_order_with_bounded_labels(self) -> None:
        plan = load_plan()
        gates = plan["gates"]
        self.assertEqual([row["id"] for row in gates], [f"G{i:02}" for i in range(13)])
        self.assertTrue(all(row["status"] in VALID_STATUS for row in gates))
        self.assertEqual(plan["acceptance"]["only_complete_if_all_required"], "PASS_FULL")
        all_ids = {row["id"] for row in gates}
        self.assertTrue(all(set(row["depends_on"]) <= all_ids for row in gates))
        self.assertFalse(any(row["id"] in row["depends_on"] for row in gates))
        for row in gates:
            self.assertTrue(row["title"].strip())
            self.assertTrue(row["not_proven"].strip())
            self.assertTrue(all(url.startswith("https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/")
                                for url in row["verified_runs"]))

    def test_phase_order_and_dag_acyclic(self) -> None:
        plan = load_plan()
        phases = plan["phases"]
        self.assertEqual([p["phase"] for p in phases], [f"F{i}" for i in range(10)])
        done = set()
        for phase in phases:
            with self.subTest(phase=phase["phase"]):
                self.assertTrue(set(phase["depends_on"]) <= done)
                self.assertTrue(phase["must_prove"])
                self.assertTrue(phase["expected_outputs"])
                self.assertTrue(phase["forbidden"])
                done.add(phase["phase"])

    def test_physical_terrain_identity_is_fixed(self) -> None:
        plan = load_plan()
        sha = plan["accepted_source_sha256"]
        self.assertEqual(set(sha), {"stage1_base", "stage2_masks", "stage3_historical_scree",
                                    "material_hda", "tint_hda"})
        for key, value in sha.items():
            with self.subTest(key=key):
                self.assertTrue(re.fullmatch(r"[a-f0-9]{64}", value))
        self.assertEqual(sha["stage1_base"], "08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952")
        self.assertEqual(sha["stage2_masks"], "203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8")

    def test_exact_cc0_roles_and_no_assumed_ordp_channels(self) -> None:
        plan = load_plan()
        cc0 = plan["source_adaptations"]
        self.assertEqual(len(cc0["all_eight_vendor_source_names"]), 8)
        self.assertEqual(len(set(cc0["all_eight_vendor_source_names"])), 8)
        self.assertEqual(cc0["ue_five_slice_order"], [
            "mossy_rock", "sparse_grass", "gravel_floor_02",
            "dark_rock_02", "coast_sand_rocks_02"])
        self.assertEqual(cc0["ue_ordp_packing_until_resolved"], "UNKNOWN")
        self.assertIs(cc0["demo_terrain_resolution_2016_applies_to_real_16000"], False)
        self.assertIs(cc0["nonzero_demo_displacement_may_modify_accepted_height"], False)

    def test_technical_pass_requires_every_verified_gate_and_visual_approval(self) -> None:
        plan = load_plan()
        states = {row["id"]: row["status"] for row in plan["gates"]}
        admission = plan["acceptance"]
        required = admission["required_for_technical_visual_closeout"]
        self.assertEqual(required, [f"G{i:02}" for i in range(12)])
        complete = all(states[name] == "PASS_FULL" for name in required)
        if admission["lesson07_technical_pass"]:
            self.assertTrue(complete, "Never claim full Lesson07 on a crop, proxy or metadata read.")
            self.assertTrue(admission["owner_visual_accepted"])
        if admission["owner_visual_accepted"]:
            self.assertEqual(states["G10"], "PASS_FULL")
            self.assertEqual(states["G11"], "PASS_FULL")
        self.assertEqual(admission["pr_must_remain_draft"], True)
        if not admission["performance_pass"]:
            self.assertIn(states["G12"], {"DEFERRED", "BLOCKED"})
        self.assertFalse(admission["lesson07_technical_pass"] and not complete)

    def test_preserve_native_evidence_and_owner_single_editor(self) -> None:
        plan = load_plan()
        self.assertIn("do not bypass LOCAL_BUSY", plan["safety"])
        self.assertIn("never overwrite original 16k caches", plan["safety"])
        required = plan["evidence_freshness_contract"]["each_native_receipt_requires"]
        self.assertTrue(any("fresh-process" in field for field in required))
        self.assertTrue(any("height/masks" in field for field in required))
        self.assertTrue(plan["render_constraints"]["real_screenshots_required"])
        self.assertEqual(len(plan["render_constraints"]["landscape_sites"]), 8)


if __name__ == "__main__":
    unittest.main()
