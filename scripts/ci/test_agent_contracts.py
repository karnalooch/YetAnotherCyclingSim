"""Regression tests for source-routed YACS agent contracts."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.ci.agent_contracts import (
    ROOT,
    load_registry,
    route_task,
    validate,
    verify_handoff,
)


class AgentContractsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_registry()

    def test_repository_contracts_are_valid(self):
        self.assertEqual(validate(), [])

    def test_current_role_router_owns_exactly_one_domain(self):
        owners = self.data["domain_owners"]
        self.assertEqual(len(owners), len(set(owners.values())))
        for domain, role_id in owners.items():
            self.assertEqual(route_task(self.data, domain, "M3"), role_id)

    def test_unapproved_milestone_and_missing_domain_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "milestone"):
            route_task(self.data, "road-earthworks", "M4")
        with self.assertRaisesRegex(ValueError, "no active owner"):
            route_task(self.data, "audio-authoring", "M3")

    def test_exclusive_host_requires_unreal_owner_and_unoccupied_resource(self):
        self.assertEqual(
            route_task(self.data, "unreal-integration", "M3", ("unreal-editor",)),
            "unreal-integration",
        )
        with self.assertRaisesRegex(ValueError, "already owned"):
            route_task(
                self.data,
                "unreal-integration",
                "M3",
                ("unreal-editor",),
                ("unreal-editor",),
            )
        with self.assertRaisesRegex(ValueError, "bounded Unreal"):
            route_task(self.data, "proof-review", "M3", ("gpu-proof",))
        with self.assertRaisesRegex(ValueError, "unknown exclusive"):
            route_task(self.data, "unreal-integration", "M3", ("untrusted-shell",))

    def test_handoff_requires_sha_and_denies_agent_admission(self):
        task = {
            "issue": 468,
            "milestone": "M3",
            "domain": "proof-review",
            "base_sha": "1" * 40,
            "scope": ["docs/ai/"],
            "forbidden": ["merge"],
        }
        self.assertEqual(verify_handoff(task, self.data), "proof-qa")
        with self.assertRaisesRegex(ValueError, "base SHA"):
            verify_handoff({**task, "base_sha": "main"}, self.data)
        for forbidden in ("admitted", "merged", "performance_pass"):
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "cannot self-admit"):
                    verify_handoff({**task, forbidden: True}, self.data)

    def test_role_privilege_escalation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            (target / "docs/ai").mkdir(parents=True)
            source = ROOT / "docs/ai/ROLE_REGISTRY.json"
            data = json.loads(source.read_text(encoding="utf-8"))
            data["roles"]["proof-qa"]["can_merge"] = True
            dest = target / "docs/ai/ROLE_REGISTRY.json"
            dest.write_text(json.dumps(data), encoding="utf-8")
            issues = validate(target)
            self.assertTrue(
                any("role privilege escalation" in issue for issue in issues),
                issues,
            )

    def test_missing_policy_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            (target / "docs/ai").mkdir(parents=True)
            data = json.loads(
                (ROOT / "docs/ai/ROLE_REGISTRY.json").read_text(
                    encoding="utf-8"
                )
            )
            (target / "docs/ai/ROLE_REGISTRY.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            errors = validate(target)
            self.assertTrue(
                any("missing/unsafe reference" in error for error in errors),
                errors,
            )

    def test_role_paths_must_remain_within_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            (target / "docs/ai").mkdir(parents=True)
            data = json.loads(
                (ROOT / "docs/ai/ROLE_REGISTRY.json").read_text(
                    encoding="utf-8"
                )
            )
            data["roles"]["world-data"]["card"] = "../../outside.md"
            (target / "docs/ai/ROLE_REGISTRY.json").write_text(
                json.dumps(data), encoding="utf-8"
            )
            self.assertTrue(validate(target))


if __name__ == "__main__":
    unittest.main()
