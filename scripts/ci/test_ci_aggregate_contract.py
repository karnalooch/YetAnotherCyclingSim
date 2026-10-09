from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class AggregateCIGateContractTests(unittest.TestCase):
    def test_classifier_outputs_are_validated_fail_closed(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("require_bool()", workflow)
        expected_lines = (
            'require_bool "class-python" "${CLASS_PYTHON}"',
            'require_bool "class-cpp" "${CLASS_CPP}"',
            'require_bool "class-assets" "${CLASS_ASSETS}"',
            'require_bool "class-ci" "${CLASS_CI}"',
            'require_bool "class-ue-code" "${CLASS_UE_CODE}"',
            'require_bool "class-ue-tooling" "${CLASS_UE_TOOLING}"',
            'require_bool "class-security-base" "${CLASS_SECURITY_BASE}"',
            'require_bool "class-asset-full" "${CLASS_ASSET_FULL}"',
            'require_bool "class-stage3g-authoring" "${CLASS_STAGE3G_AUTHORING}"',
        )
        for expected in expected_lines:
            with self.subTest(expected=expected):
                self.assertIn(expected, workflow)

        self.assertIn(
            "expected literal true/false classifier output",
            workflow,
        )
        self.assertIn('require_ci_cost "${CLASS_CI_COST}"', workflow)
        self.assertIn(
            "expected light/standard/heavy classifier output",
            workflow,
        )
        self.assertIn(
            "heavy Unreal/runtime impact must classify ci_cost_class=heavy",
            workflow,
        )


class AggregateBehaviorTests(unittest.TestCase):
    """Execute the actual workflow shell; token-presence checks cannot prove it."""

    @staticmethod
    def baseline():
        return {
            "WORLD_PROOF_RESULT": "success",
            "CHANGES_RESULT": "success",
            "REPO_POLICY_RESULT": "success",
            "GOVERNANCE_RESULT": "success",
            "PYTHON_REFERENCE_RESULT": "skipped",
            "SECURITY_BASE_RESULT": "skipped",
            "SECURITY_PYTHON_RESULT": "skipped",
            "SECURITY_CPP_RESULT": "skipped",
            "UNREAL_CODE_RESULT": "skipped",
            "ASSET_VALIDATION_RESULT": "skipped",
            "STAGE3G_FULL_RESULT": "skipped",
            "CLASS_PYTHON": "false",
            "CLASS_CPP": "false",
            "CLASS_ASSETS": "false",
            "CLASS_CI": "false",
            "CLASS_UE_CODE": "false",
            "CLASS_UE_TOOLING": "false",
            "CLASS_UNREAL_COMPILE": "false",
            "CLASS_UNREAL_RUNTIME": "false",
            "CLASS_UNREAL_EXECUTION": "static",
            "CLASS_CI_COST": "light",
            "CLASS_SECURITY_BASE": "false",
            "CLASS_ASSET_FULL": "false",
            "CLASS_STAGE3G_AUTHORING": "false",
            "EVENT_NAME": "pull_request",
            "PR_DRAFT": "false",
        }

    def execute(self, values):
        import os
        import subprocess
        import textwrap

        shell = (
            WORKFLOW.read_text(encoding="utf-8")
            .split("  aggregate:\n", 1)[1]
            .split("        run: |\n", 1)[1]
        )
        return subprocess.run(
            ["bash", "-c", textwrap.dedent(shell)],
            env={**os.environ, **values},
            capture_output=True,
            text=True,
        )

    def test_docs_can_pass_with_correctly_skipped_optional_work(self):
        result = self.execute(self.baseline())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_required_evidence_missing_cancelled_skipped_or_failed_blocks(self):
        for status in ("", "skipped", "cancelled", "failure", "neutral"):
            with self.subTest(status=status):
                self.assertNotEqual(
                    self.execute(
                        {**self.baseline(), "WORLD_PROOF_RESULT": status}
                    ).returncode,
                    0,
                )

    def test_missing_or_malformed_classifier_cannot_silently_skip_tests(self):
        for field in (
            "CLASS_PYTHON",
            "CLASS_CI",
            "CLASS_ASSET_FULL",
            "CLASS_STAGE3G_AUTHORING",
            "CLASS_UNREAL_COMPILE",
        ):
            for value in ("", "False", "unknown"):
                with self.subTest(field=field, value=value):
                    self.assertNotEqual(
                        self.execute({**self.baseline(), field: value}).returncode, 0
                    )

    def test_required_python_failure_and_missing_result_block(self):
        for result in ("failure", "skipped", "cancelled", ""):
            values = {
                **self.baseline(),
                "CLASS_PYTHON": "true",
                "PYTHON_REFERENCE_RESULT": result,
                "CLASS_CI_COST": "standard",
                "SECURITY_PYTHON_RESULT": "success",
            }
            self.assertNotEqual(self.execute(values).returncode, 0)

    def test_draft_world_can_defer_but_ready_world_requires_full_proof(self):
        values = {
            **self.baseline(),
            "CLASS_ASSET_FULL": "true",
            "CLASS_ASSETS": "true",
            "ASSET_VALIDATION_RESULT": "success",
            "CLASS_CI_COST": "heavy",
            "CLASS_UNREAL_EXECUTION": "runtime",
            "PR_DRAFT": "true",
        }
        self.assertEqual(self.execute(values).returncode, 0)
        values["PR_DRAFT"] = "false"
        self.assertNotEqual(self.execute(values).returncode, 0)
        values["STAGE3G_FULL_RESULT"] = "success"
        self.assertEqual(self.execute(values).returncode, 0)

    def test_missing_unreal_result_and_inconsistent_cost_block(self):
        values = {
            **self.baseline(),
            "CLASS_UE_CODE": "true",
            "CLASS_UNREAL_RUNTIME": "true",
            "CLASS_UNREAL_COMPILE": "true",
            "CLASS_UNREAL_EXECUTION": "compile",
            "CLASS_CI_COST": "heavy",
            "SECURITY_CPP_RESULT": "success",
        }
        self.assertNotEqual(self.execute(values).returncode, 0)
        values["UNREAL_CODE_RESULT"] = "success"
        self.assertEqual(self.execute(values).returncode, 0)
        values["CLASS_CI_COST"] = "light"
        self.assertNotEqual(self.execute(values).returncode, 0)

    def test_legacy_authoring_cannot_omit_its_required_regression_gate(self):
        result = self.execute({**self.baseline(), "CLASS_STAGE3G_AUTHORING": "true"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "legacy authoring must retain its full regression gate", result.stdout
        )


if __name__ == "__main__":
    unittest.main()
