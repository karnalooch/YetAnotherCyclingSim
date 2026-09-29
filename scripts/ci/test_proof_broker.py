from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from scripts.ops import proof_broker


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / ".gumball" / "proof-broker.json"
BROKER_WORKFLOW = ROOT / ".github" / "workflows" / "proof-broker.yml"
TARGET_WORKFLOW = (
    ROOT / ".github" / "workflows" / "passo-giau-r4-1b3-geometry-probe.yml"
)


class YacsProofBrokerContractTests(unittest.TestCase):
    def policy(self) -> dict:
        return json.loads(POLICY.read_text(encoding="utf-8"))

    def test_policy_is_valid(self):
        self.assertEqual(proof_broker.validate_policy(self.policy()), [])

    def test_r4_1b3_target_workflow_matches_policy(self):
        proof = self.policy()["proofs"]["r4-1b3-geometry"]
        workflow = TARGET_WORKFLOW.read_text(encoding="utf-8")
        self.assertEqual(
            proof_broker.validate_workflow_contract(workflow, proof),
            [],
        )

    def test_r4_1b3_is_explicit_heavy_nonautomatic_proof(self):
        proof = self.policy()["proofs"]["r4-1b3-geometry"]
        self.assertEqual(proof["cost_class"], "heavy")
        self.assertFalse(proof["merge_critical"])
        self.assertFalse(proof["automatic"]["enabled"])
        self.assertEqual(proof["artifact_name"], "proof-$proof-$sha")

    def test_comment_contract_supports_run_retry_and_status(self):
        self.assertEqual(
            proof_broker.parse_comment("/gumball proof r4-1b3-geometry"),
            ("r4-1b3-geometry", "run"),
        )
        self.assertEqual(
            proof_broker.parse_comment("/gumball proof r4-1b3-geometry retry"),
            ("r4-1b3-geometry", "retry"),
        )
        self.assertEqual(
            proof_broker.parse_comment("/gumball proof r4-1b3-geometry status"),
            ("r4-1b3-geometry", "status"),
        )

    def test_request_id_is_exact_revision_bound(self):
        sha = "a" * 40
        request_id = proof_broker.make_request_id(
            "r4-1b3-geometry",
            239,
            sha,
        )
        self.assertIn("pr239", request_id)
        self.assertTrue(request_id.endswith("a" * 12))

    def test_rendered_inputs_bind_exact_sha_and_request_id(self):
        proof = self.policy()["proofs"]["r4-1b3-geometry"]
        rendered = proof_broker.render_inputs(
            "r4-1b3-geometry",
            proof,
            pr_number=239,
            branch="feat/example",
            sha="b" * 40,
            request_id="gb-r4-1b3-geometry-pr239-bbbbbbbbbbbb",
        )
        self.assertEqual(rendered["exact_sha"], "b" * 40)
        self.assertEqual(
            rendered["gumball_request_id"],
            "gb-r4-1b3-geometry-pr239-bbbbbbbbbbbb",
        )

    def test_explicit_request_dispatches_exact_sha_workflow(self):
        policy = self.policy()
        with (
            mock.patch.object(
                proof_broker,
                "authorize_actor",
                return_value="admin",
            ),
            mock.patch.object(
                proof_broker,
                "get_pr",
                return_value={
                    "state": "open",
                    "head": {
                        "ref": "feat/example",
                        "sha": "c" * 40,
                        "repo": {"full_name": "karnalooch/YetAnotherCyclingSim"},
                    },
                },
            ),
            mock.patch.object(
                proof_broker,
                "find_artifact",
                return_value=None,
            ),
            mock.patch.object(
                proof_broker,
                "find_existing_run",
                return_value=None,
            ),
            mock.patch.object(
                proof_broker,
                "get_pr_paths",
                return_value=["scripts/geometry/example.py"],
            ),
            mock.patch.object(
                proof_broker,
                "default_branch",
                return_value="main",
            ),
            mock.patch.object(
                proof_broker,
                "fetch_workflow_text",
                return_value=TARGET_WORKFLOW.read_text(encoding="utf-8"),
            ),
            mock.patch.object(proof_broker, "set_status_label"),
            mock.patch.object(proof_broker, "ensure_request_label"),
            mock.patch.object(proof_broker, "dispatch_workflow") as dispatch,
        ):
            result = proof_broker.evaluate_proof(
                repo="karnalooch/YetAnotherCyclingSim",
                token="token",
                policy=policy,
                proof_id="r4-1b3-geometry",
                pr_number=239,
                actor="karnalooch",
                explicit=True,
                retry=False,
                status_only=False,
                apply=True,
            )

        self.assertEqual(result["action"], "DISPATCH")
        dispatched_inputs = dispatch.call_args.args[4]
        self.assertEqual(dispatched_inputs["exact_sha"], "c" * 40)

    def test_reusable_artifact_is_created_only_after_success(self):
        workflow = TARGET_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if: ${{ success() }}", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn("diagnostic-r4-1b3-geometry-", workflow)

    def test_broker_workflow_keeps_trusted_default_branch_boundary(self):
        workflow = BROKER_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Checkout trusted default branch", workflow)
        self.assertIn(
            "ref: ${{ github.event.repository.default_branch }}",
            workflow,
        )
        self.assertIn("actions: write", workflow)
        self.assertNotIn("permissions: write-all", workflow)


if __name__ == "__main__":
    unittest.main()
