from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRENT_GUMBALL_PIN = "03eb6f6bc6cd2260349386489bffb005c44b3236"
CANDIDATE_FIELDS = {
    "id",
    "source",
    "category",
    "problem",
    "invariant",
    "evidence",
    "do_not_copy",
    "failure_behavior",
    "status",
}


class GumballBaselineContractTests(unittest.TestCase):
    def test_unreal_consumer_manifest_preserves_local_controls(self) -> None:
        text = (ROOT / "gumball.yaml").read_text(encoding="utf-8")
        self.assertIn("profile: unreal", text)
        self.assertIn("mode: preserve-local", text)
        self.assertIn("aggregate_gate: caller-local", text)
        self.assertIn("evaluate_upstream_promotion: true", text)

    def test_repository_os_keeps_projects_consumer_owned(self) -> None:
        policy = json.loads(
            (ROOT / ".gumball" / "repository-os.json").read_text(encoding="utf-8")
        )
        self.assertFalse(policy["projects"]["enabled"])
        self.assertFalse(policy["projects"]["close_issue_on_done"])
        self.assertEqual(
            policy["labels"]["required_pr_dimensions"],
            ["type", "area", "risk", "ci"],
        )
        self.assertTrue(policy["ci_cost"]["cancel_superseded_pr_runs"])

    def test_shared_gumball_workflows_use_one_reviewed_pin(self) -> None:
        for relative in (
            ".github/workflows/ci.yml",
            ".github/workflows/scorecard.yml",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            refs = [
                token.split("@", 1)[1].split()[0]
                for token in text.splitlines()
                if "uses: karnalooch/engineering-platform/" in token
            ]
            self.assertGreater(len(refs), 0, relative)
            self.assertEqual(set(refs), {CURRENT_GUMBALL_PIN}, relative)

    def test_repository_ops_runs_trusted_default_branch_code(self) -> None:
        text = (ROOT / ".github" / "workflows" / "repository-ops.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("pull_request_target:", text)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", text)
        self.assertNotIn("ref: ${{ github.event.pull_request.head.sha }}", text)
        self.assertIn("secrets.PROJECTS_TOKEN", text)
        self.assertNotIn("permissions: write-all", text)

    def test_promotion_candidate_records_follow_contract(self) -> None:
        directory = ROOT / ".gumball" / "candidates"
        records = sorted(directory.glob("*.json"))
        self.assertGreaterEqual(len(records), 3)
        for path in records:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(CANDIDATE_FIELDS.issubset(payload), path.name)
            self.assertIn(payload["status"], {"candidate", "proven", "platform"})


if __name__ == "__main__":
    unittest.main()
