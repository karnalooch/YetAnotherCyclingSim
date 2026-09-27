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
            'require_bool "class-security-base" "${CLASS_SECURITY_BASE}"',
            'require_bool "class-asset-full" "${CLASS_ASSET_FULL}"',
        )
        for expected in expected_lines:
            with self.subTest(expected=expected):
                self.assertIn(expected, workflow)

        self.assertIn(
            "expected literal true/false classifier output",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
