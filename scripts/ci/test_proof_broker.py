from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from scripts.ops import proof_broker


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / ".gumball" / "proof-broker.json"
BROKER_WORKFLOW = ROOT / ".github" / "workflows" / "proof-broker.yml"
TARGET_WORKFLOWS = {
    "r4-1b3-geometry": ROOT
    / ".github"
    / "workflows"
    / "passo-giau-r4-1b3-geometry-probe.yml",
    "m3-hairpin-corridor": ROOT
    / ".github"
    / "workflows"
    / "passo-giau-r4-1-hairpin-corridor.yml",
    "m3-terrain": ROOT / ".github" / "workflows" / "passo-giau-embark-terrain.yml",
    "world-authoring-sp638": ROOT
    / ".github"
    / "workflows"
    / "passo-giau-r4-1-roadside-house.yml",
    "environment-performance": ROOT
    / ".github"
    / "workflows"
    / "stage3g-environment-performance.yml",
    "source-asset-audit": ROOT
    / ".github"
    / "workflows"
    / "stage3g-source-asset-audit.yml",
}


class YacsProofBrokerContractTests(unittest.TestCase):
    def policy(self) -> dict:
        return json.loads(POLICY.read_text(encoding="utf-8"))

    def test_policy_is_valid(self):
        self.assertEqual(proof_broker.validate_policy(self.policy()), [])

    def test_all_target_workflows_match_policy(self):
        policy = self.policy()
        self.assertEqual(set(policy["proofs"]), set(TARGET_WORKFLOWS))
        for proof_id, path in TARGET_WORKFLOWS.items():
            with self.subTest(proof=proof_id):
                proof = policy["proofs"][proof_id]
                workflow = path.read_text(encoding="utf-8")
                self.assertEqual(
                    proof_broker.validate_workflow_contract(workflow, proof),
                    [],
                )

    def test_all_proofs_are_explicit_heavy_nonautomatic_and_read_only(self):
        for proof_id, proof in self.policy()["proofs"].items():
            with self.subTest(proof=proof_id):
                self.assertEqual(proof["cost_class"], "heavy")
                self.assertFalse(proof["merge_critical"])
                self.assertFalse(proof["automatic"]["enabled"])
                self.assertEqual(proof["artifact_name"], "proof-$proof-$sha")
                self.assertEqual(proof["allowed_write_permissions"], [])

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

    def test_github_api_failure_diagnostics_are_structured_and_redacted(self):
        exc = RuntimeError(
            "POST https://api.github.com/repos/acme/repo/actions/workflows/"
            "proof.yml/dispatches?ref=main&token=query-secret: HTTP 422: "
            '{"message":"workflow blocked",'
            '"token":"body-secret",'
            '"nested":{"authorization":"Bearer bearer-secret"}}'
        )
        message = proof_broker._safe_github_api_failure(exc)

        self.assertIn(
            "POST /repos/acme/repo/actions/workflows/proof.yml/dispatches",
            message,
        )
        self.assertIn("HTTP 422", message)
        self.assertIn('"token":"***REDACTED***"', message)
        self.assertIn('"authorization":"***REDACTED***"', message)
        self.assertNotIn("query-secret", message)
        self.assertNotIn("body-secret", message)
        self.assertNotIn("bearer-secret", message)

    def test_unstructured_github_error_details_are_not_echoed(self):
        message = proof_broker._safe_github_api_failure(
            RuntimeError("opaque token=do-not-print")
        )
        self.assertEqual(
            message,
            "GitHub API request failed (unstructured details redacted)",
        )

    def test_repository_owner_is_explicit_trusted_actor(self):
        policy = self.policy()
        self.assertEqual(policy["defaults"]["trusted_actor_logins"], ["karnalooch"])
        with mock.patch.object(proof_broker, "actor_permission") as permission:
            result = proof_broker.authorize_actor(
                "karnalooch/YetAnotherCyclingSim",
                "token",
                "karnalooch",
                policy,
            )
        self.assertEqual(result, "trusted-actor")
        permission.assert_not_called()

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
                return_value=TARGET_WORKFLOWS["r4-1b3-geometry"].read_text(
                    encoding="utf-8"
                ),
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

    def test_reusable_artifacts_are_created_only_after_success(self):
        for proof_id, path in TARGET_WORKFLOWS.items():
            with self.subTest(proof=proof_id):
                workflow = path.read_text(encoding="utf-8")
                self.assertIn("if: ${{ success() }}", workflow)
                self.assertIn("if-no-files-found: error", workflow)
                if proof_id == "m3-terrain":
                    # M3 validates its input before downstream checkout and keeps
                    # the established internal artifact names as diagnostics.
                    self.assertIn(
                        "proof-m3-terrain-${{ needs.classify.outputs.source_sha }}",
                        workflow,
                    )
                    self.assertIn(
                        "passo-giau-m3-pcgex-${{ github.run_id }}-${{ github.run_attempt }}",
                        workflow,
                    )
                    author, validate = workflow.split("\n  validate:", 1)
                    self.assertNotIn("name: proof-m3-terrain-", author)
                    self.assertIn("needs: [classify, prepare, author]", validate)
                    self.assertLess(
                        validate.index("validate_pcgex_corridor_output.py"),
                        validate.index("name: proof-m3-terrain-"),
                    )
                    self.assertIn('"human_visual_status": "PENDING"', validate)
                else:
                    self.assertIn(
                        f"proof-{proof_id}-${{{{ inputs.exact_sha }}}}",
                        workflow,
                    )
                    self.assertIn(f"diagnostic-{proof_id}-", workflow)

    def test_broker_workflow_keeps_trusted_default_branch_boundary(self):
        workflow = BROKER_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Checkout trusted default branch", workflow)
        self.assertIn(
            "ref: ${{ github.event.repository.default_branch }}",
            workflow,
        )
        self.assertIn("actions: write", workflow)
        self.assertEqual(workflow.count("pull-requests: write"), 2)
        self.assertNotIn("pull-requests: read", workflow)
        self.assertNotIn("permissions: write-all", workflow)


if __name__ == "__main__":
    unittest.main()
