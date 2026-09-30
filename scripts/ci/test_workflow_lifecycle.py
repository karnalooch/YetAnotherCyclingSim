from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
POLICY = ROOT / ".gumball" / "workflow-lifecycle.json"

ACTIVE_STATES = {"CURRENT", "BROKER-MANAGED", "UNKNOWN"}
RETIRED_STATES = {"HISTORICAL/RETIRED", "ONE-SHOT/DEAD"}
ALL_STATES = ACTIVE_STATES | RETIRED_STATES


class WorkflowLifecycleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))
        cls.rows = cls.policy["workflows"]
        cls.by_file = {row["file"]: row for row in cls.rows}

    def test_policy_has_unique_complete_state_vocabulary(self) -> None:
        self.assertEqual(set(self.policy["states"]), ALL_STATES)
        self.assertEqual(len(self.by_file), len(self.rows))
        for row in self.rows:
            self.assertIn(row["state"], ALL_STATES)
            self.assertTrue(row["reason"].strip())

    def test_every_executable_workflow_is_registered(self) -> None:
        actual = {
            path.name
            for path in WORKFLOWS.iterdir()
            if path.suffix in {".yml", ".yaml"}
        }
        expected = {
            row["file"] for row in self.rows if row["state"] in ACTIVE_STATES
        }
        self.assertEqual(actual, expected)

    def test_retired_workflows_are_not_executable(self) -> None:
        for row in self.rows:
            if row["state"] not in RETIRED_STATES:
                continue
            with self.subTest(workflow=row["file"]):
                self.assertFalse((WORKFLOWS / row["file"]).exists())

    def test_no_live_workflow_contains_permanent_false_job(self) -> None:
        pattern = re.compile(r"(?m)^\s*if:\s*\$\{\{\s*false\s*\}\}\s*$")
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            with self.subTest(workflow=path.name):
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")))

    def test_no_live_workflow_hardcodes_historical_run_cancellation(self) -> None:
        pattern = re.compile(r"actions/runs/\d+/cancel")
        for path in sorted(WORKFLOWS.glob("*.y*ml")):
            with self.subTest(workflow=path.name):
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")))

    def test_unknown_workflows_are_bounded_to_active_m3_transition(self) -> None:
        unknown = {
            row["file"] for row in self.rows if row["state"] == "UNKNOWN"
        }
        self.assertEqual(
            unknown,
            {
                "passo-giau-r4-1-landscape-author.yml",
                "passo-giau-r4-1-road-author.yml",
            },
        )


if __name__ == "__main__":
    unittest.main()
