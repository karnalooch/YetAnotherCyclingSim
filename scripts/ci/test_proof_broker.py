from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from scripts.ops import proof_broker


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "proof-broker.yml"
POLICY = ROOT / ".gumball" / "proof-broker.json"


def enabled_policy(*, automatic: bool = False, merge_critical: bool = False):
    return {
        "schema_version": 1,
        "defaults": {
            "allowed_permissions": ["write", "maintain", "admin"],
            "dispatch_ref": "default",
            "allow_branch_workflow_definition": False,
            "require_exact_sha_input": True,
            "require_request_id_run_name": True,
            "manual_workflow_dispatch_fallback": True,
            "status_label_template": "proof-status:$proof:$status",
            "trusted_actor_logins": [],
            "forbid_target_write_permissions": True,
        },
        "proofs": {
            "geometry": {
                "enabled": True,
                "workflow": "geometry-proof.yml",
                "label": "proof:geometry",
                "cost_class": "heavy",
                "merge_critical": merge_critical,
                "dispatch_ref": "default",
                "request_id_input": "gumball_request_id",
                "inputs": {
                    "source_ref": "$branch",
                    "exact_sha": "$sha",
                    "pull_request": "$pr_number",
                    "gumball_request_id": "$request_id",
                },
                "artifact_name": "proof-$proof-$sha",
                "allowed_write_permissions": [],
                "automatic": {
                    "enabled": automatic,
                    "require_ci_class": "heavy",
                },
            }
        },
    }


def valid_target_workflow():
    return """name: Geometry proof
run-name: geometry ${{ inputs.gumball_request_id }}
on:
  workflow_dispatch:
    inputs:
      source_ref:
        required: true
        type: string
      exact_sha:
        required: true
        type: string
      pull_request:
        required: true
        type: string
      gumball_request_id:
        required: true
        type: string
permissions:
  contents: read
jobs:
  proof:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ inputs.exact_sha }}"
"""


class PolicyTests(unittest.TestCase):
    def test_repository_policy_is_valid(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(proof_broker.validate_policy(policy), [])

    def test_branch_workflow_definition_is_rejected_by_default(self):
        policy = enabled_policy()
        policy["proofs"]["geometry"]["dispatch_ref"] = "$branch"
        problems = proof_broker.validate_policy(policy)
        self.assertTrue(
            any("branch workflow definition disabled" in item for item in problems),
            problems,
        )

    def test_artifact_key_must_include_revision_identity(self):
        policy = enabled_policy()
        policy["proofs"]["geometry"]["artifact_name"] = "geometry-proof"
        problems = proof_broker.validate_policy(policy)
        self.assertTrue(any("artifact_name" in item for item in problems), problems)

    def test_comment_parser(self):
        self.assertEqual(
            proof_broker.parse_comment("/gumball proof geometry retry"),
            ("geometry", "retry"),
        )
        self.assertEqual(
            proof_broker.parse_comment("/gumball proof geometry"),
            ("geometry", "run"),
        )
        self.assertIsNone(proof_broker.parse_comment("please run geometry"))


class RequestTests(unittest.TestCase):
    def test_request_id_is_deterministic(self):
        first = proof_broker.make_request_id("geometry", 23, "a" * 40)
        second = proof_broker.make_request_id("geometry", 23, "a" * 40)
        self.assertEqual(first, second)
        self.assertIn("pr23", first)
        self.assertTrue(first.endswith("a" * 12))

    def test_render_inputs_binds_exact_revision(self):
        policy = enabled_policy()
        proof = policy["proofs"]["geometry"]
        result = proof_broker.render_inputs(
            "geometry",
            proof,
            pr_number=23,
            branch="feat/example",
            sha="b" * 40,
            request_id="request-1",
        )
        self.assertEqual(result["source_ref"], "feat/example")
        self.assertEqual(result["exact_sha"], "b" * 40)
        self.assertEqual(result["pull_request"], "23")
        self.assertEqual(result["gumball_request_id"], "request-1")


class AuthorizationTests(unittest.TestCase):
    def test_explicit_trusted_actor_bypasses_collaborator_lookup(self):
        policy = enabled_policy()
        policy["defaults"]["trusted_actor_logins"] = ["trusted-bot[bot]"]
        with mock.patch.object(proof_broker, "actor_permission") as permission:
            result = proof_broker.authorize_actor(
                "owner/repo",
                "token",
                "trusted-bot[bot]",
                policy,
            )
        self.assertEqual(result, "trusted-actor")
        permission.assert_not_called()


class WorkflowContractTests(unittest.TestCase):
    def test_valid_target_contract_passes(self):
        policy = enabled_policy()
        proof = policy["proofs"]["geometry"]
        self.assertEqual(
            proof_broker.validate_workflow_contract(
                valid_target_workflow(),
                proof,
            ),
            [],
        )

    def test_run_name_request_id_is_required(self):
        policy = enabled_policy()
        proof = policy["proofs"]["geometry"]
        workflow = valid_target_workflow().replace(
            "run-name: geometry ${{ inputs.gumball_request_id }}",
            "run-name: geometry",
        )
        problems = proof_broker.validate_workflow_contract(workflow, proof)
        self.assertTrue(any("run-name" in item for item in problems), problems)

    def test_exact_sha_must_be_referenced(self):
        policy = enabled_policy()
        proof = policy["proofs"]["geometry"]
        workflow = valid_target_workflow().replace(
            '      - run: echo "${{ inputs.exact_sha }}"',
            "      - run: echo proof",
        )
        problems = proof_broker.validate_workflow_contract(workflow, proof)
        self.assertTrue(
            any("declared but never referenced" in item for item in problems),
            problems,
        )

    def test_target_write_permission_requires_explicit_allowlist(self):
        policy = enabled_policy()
        proof = policy["proofs"]["geometry"]
        workflow = valid_target_workflow().replace(
            "permissions:\n  contents: read",
            "permissions:\n  contents: write",
        )
        problems = proof_broker.validate_workflow_contract(workflow, proof)
        self.assertTrue(
            any("write permission 'contents'" in item for item in problems),
            problems,
        )

    def test_exact_sha_input_is_required(self):
        policy = enabled_policy()
        proof = policy["proofs"]["geometry"]
        workflow = valid_target_workflow().replace(
            "      exact_sha:\n        required: true\n        type: string\n",
            "",
        )
        problems = proof_broker.validate_workflow_contract(workflow, proof)
        self.assertTrue(any("exact-SHA" in item for item in problems), problems)


class BrokerDecisionTests(unittest.TestCase):
    def common_patches(self):
        return [
            mock.patch.object(proof_broker, "authorize_actor", return_value="write"),
            mock.patch.object(
                proof_broker,
                "get_pr",
                return_value={
                    "state": "open",
                    "head": {
                        "ref": "feat/example",
                        "sha": "c" * 40,
                        "repo": {"full_name": "owner/repo"},
                    },
                },
            ),
            mock.patch.object(proof_broker, "find_artifact", return_value=None),
            mock.patch.object(proof_broker, "find_existing_run", return_value=None),
            mock.patch.object(
                proof_broker,
                "get_pr_paths",
                return_value=["Source/Game/Foo.cpp"],
            ),
            mock.patch.object(proof_broker, "default_branch", return_value="main"),
            mock.patch.object(
                proof_broker,
                "fetch_workflow_text",
                return_value=valid_target_workflow(),
            ),
            mock.patch.object(proof_broker, "set_status_label"),
            mock.patch.object(proof_broker, "ensure_request_label"),
        ]

    def test_explicit_request_dispatches_heavy_proof(self):
        patches = self.common_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
            with mock.patch.object(proof_broker, "dispatch_workflow") as dispatch:
                result = proof_broker.evaluate_proof(
                    repo="owner/repo",
                    token="token",
                    policy=enabled_policy(),
                    proof_id="geometry",
                    pr_number=23,
                    actor="owner",
                    explicit=True,
                    retry=False,
                    status_only=False,
                    apply=True,
                )
        self.assertEqual(result["action"], "DISPATCH")
        dispatch.assert_called_once()
        self.assertIn("exact_sha", result["input_keys"])
        dispatched_inputs = dispatch.call_args.args[4]
        self.assertEqual(dispatched_inputs["exact_sha"], "c" * 40)

    def test_automatic_noncritical_heavy_proof_is_deferred(self):
        patches = self.common_patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[7]:
            result = proof_broker.evaluate_proof(
                repo="owner/repo",
                token="token",
                policy=enabled_policy(automatic=True, merge_critical=False),
                proof_id="geometry",
                pr_number=23,
                actor=None,
                explicit=False,
                retry=False,
                status_only=False,
                apply=True,
            )
        self.assertEqual(result["action"], "DEFER")

    def test_existing_success_is_reused_without_dispatch(self):
        policy = enabled_policy()
        with mock.patch.object(proof_broker, "authorize_actor", return_value="write"):
            with mock.patch.object(proof_broker, "ensure_request_label"):
                with mock.patch.object(
                    proof_broker,
                    "get_pr",
                    return_value={
                        "state": "open",
                        "head": {
                            "ref": "feat/example",
                            "sha": "d" * 40,
                            "repo": {"full_name": "owner/repo"},
                        },
                    },
                ):
                    with mock.patch.object(proof_broker, "find_artifact", return_value=None):
                        with mock.patch.object(
                            proof_broker,
                            "find_existing_run",
                            return_value={
                                "id": 17,
                                "status": "completed",
                                "conclusion": "success",
                                "html_url": "https://example/run/17",
                            },
                        ):
                            with mock.patch.object(proof_broker, "set_status_label"):
                                with mock.patch.object(proof_broker, "dispatch_workflow") as dispatch:
                                    result = proof_broker.evaluate_proof(
                                        repo="owner/repo",
                                        token="token",
                                        policy=policy,
                                        proof_id="geometry",
                                        pr_number=23,
                                        actor="owner",
                                        explicit=True,
                                        retry=False,
                                        status_only=False,
                                        apply=True,
                                    )
        self.assertEqual(result["action"], "REUSE_RUN")
        dispatch.assert_not_called()

    def test_failed_run_requires_explicit_retry(self):
        run = {
            "id": 19,
            "status": "completed",
            "conclusion": "failure",
            "html_url": "https://example/run/19",
        }
        with mock.patch.object(proof_broker, "authorize_actor", return_value="write"):
            with mock.patch.object(proof_broker, "ensure_request_label"):
                with mock.patch.object(
                    proof_broker,
                    "get_pr",
                    return_value={
                        "state": "open",
                        "head": {
                            "ref": "feat/example",
                            "sha": "e" * 40,
                            "repo": {"full_name": "owner/repo"},
                        },
                    },
                ):
                    with mock.patch.object(proof_broker, "find_artifact", return_value=None):
                        with mock.patch.object(proof_broker, "find_existing_run", return_value=run):
                            with mock.patch.object(proof_broker, "set_status_label"):
                                result = proof_broker.evaluate_proof(
                                    repo="owner/repo",
                                    token="token",
                                    policy=enabled_policy(),
                                    proof_id="geometry",
                                    pr_number=23,
                                    actor="owner",
                                    explicit=True,
                                    retry=False,
                                    status_only=False,
                                    apply=True,
                                )
        self.assertEqual(result["action"], "FAILED_EXISTING")

    def test_retry_reruns_existing_failed_workflow(self):
        run = {
            "id": 19,
            "status": "completed",
            "conclusion": "failure",
            "html_url": "https://example/run/19",
        }
        with mock.patch.object(proof_broker, "authorize_actor", return_value="write"):
            with mock.patch.object(proof_broker, "ensure_request_label"):
                with mock.patch.object(
                    proof_broker,
                    "get_pr",
                    return_value={
                        "state": "open",
                        "head": {
                            "ref": "feat/example",
                            "sha": "f" * 40,
                            "repo": {"full_name": "owner/repo"},
                        },
                    },
                ):
                    with mock.patch.object(proof_broker, "find_artifact", return_value=None):
                        with mock.patch.object(proof_broker, "find_existing_run", return_value=run):
                            with mock.patch.object(proof_broker, "set_status_label"):
                                with mock.patch.object(proof_broker, "rerun_workflow") as rerun:
                                    result = proof_broker.evaluate_proof(
                                        repo="owner/repo",
                                        token="token",
                                        policy=enabled_policy(),
                                        proof_id="geometry",
                                        pr_number=23,
                                        actor="owner",
                                        explicit=True,
                                        retry=True,
                                        status_only=False,
                                        apply=True,
                                    )
        self.assertEqual(result["action"], "RERUN")
        rerun.assert_called_once_with("owner/repo", "token", 19)


class EventTests(unittest.TestCase):
    def test_repository_dispatch_drives_automatic_policy(self):
        event = {
            "client_payload": {
                "proof": "geometry",
                "pr_number": 23,
            }
        }
        with mock.patch.object(
            proof_broker,
            "evaluate_proof",
            return_value={"action": "DEFER", "proof": "geometry", "pr_number": 23},
        ) as evaluate:
            results = proof_broker.handle_event(
                "owner/repo",
                "token",
                enabled_policy(automatic=True),
                "repository_dispatch",
                event,
                apply=True,
            )

        self.assertEqual(results[0][0]["action"], "DEFER")
        kwargs = evaluate.call_args.kwargs
        self.assertFalse(kwargs["explicit"])
        self.assertEqual(kwargs["pr_number"], 23)

    def test_comment_request_is_explicit(self):
        event = {
            "issue": {"number": 23, "pull_request": {}},
            "comment": {"body": "/gumball proof geometry"},
            "sender": {"login": "owner"},
        }
        with mock.patch.object(
            proof_broker,
            "evaluate_proof",
            return_value={"action": "DISPATCH", "proof": "geometry", "pr_number": 23},
        ) as evaluate:
            results = proof_broker.handle_event(
                "owner/repo",
                "token",
                enabled_policy(),
                "issue_comment",
                event,
                apply=True,
            )

        self.assertTrue(results[0][1])
        self.assertTrue(evaluate.call_args.kwargs["explicit"])


class StatusLabelTests(unittest.TestCase):
    def test_status_update_preserves_other_proof_status(self):
        policy = enabled_policy()
        policy["proofs"]["visual"] = {
            **policy["proofs"]["geometry"],
            "label": "proof:visual",
        }
        issue = {
            "labels": [
                {"name": "proof:geometry"},
                {"name": "proof:visual"},
                {"name": "proof-status:geometry:running"},
                {"name": "proof-status:visual:passed"},
            ]
        }
        calls = []

        def fake_request(token, method, path, payload=None):
            if method == "GET":
                return issue
            calls.append((method, path, payload))
            return {}

        with mock.patch.object(proof_broker.github_ops, "request", side_effect=fake_request):
            proof_broker.set_status_label(
                "owner/repo",
                "token",
                23,
                policy,
                "geometry",
                "passed",
                True,
            )

        self.assertEqual(calls[0][0], "PUT")
        labels = set(calls[0][2]["labels"])
        self.assertIn("proof-status:geometry:passed", labels)
        self.assertNotIn("proof-status:geometry:running", labels)
        self.assertIn("proof-status:visual:passed", labels)


class BrokerWorkflowSafetyTests(unittest.TestCase):
    def test_broker_workflow_uses_trusted_default_branch(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("pull_request_target:", text)
        self.assertIn("issue_comment:", text)
        self.assertIn("repository_dispatch:", text)
        self.assertNotIn("      - synchronize", text)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("ref: ${{ github.event.pull_request.head.sha }}", text)

    def test_write_permission_is_not_global(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("permissions: {}", text)
        self.assertIn("actions: write", text)
        reconcile = text.split("  reconcile:", 1)[1]
        self.assertIn("actions: read", reconcile)
        self.assertNotIn("actions: write", reconcile)

    def test_broker_entrypoint_is_contract_tested(self):
        text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "python -m unittest scripts/ci/test_proof_broker.py -v",
            text,
        )


if __name__ == "__main__":
    unittest.main()


class YacsProofBrokerConsumerTests(unittest.TestCase):
    def test_r4_1b3_target_workflow_matches_enabled_policy(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        proof = policy["proofs"]["r4-1b3-geometry"]
        workflow = (
            ROOT
            / ".github"
            / "workflows"
            / "passo-giau-r4-1b3-geometry-probe.yml"
        ).read_text(encoding="utf-8")
        self.assertEqual(
            proof_broker.validate_workflow_contract(workflow, proof),
            [],
        )

    def test_r4_1b3_policy_is_explicit_heavy_and_nonautomatic(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        proof = policy["proofs"]["r4-1b3-geometry"]
        self.assertEqual(proof["cost_class"], "heavy")
        self.assertFalse(proof["merge_critical"])
        self.assertFalse(proof["automatic"]["enabled"])
        self.assertEqual(proof["artifact_name"], "proof-$proof-$sha")
