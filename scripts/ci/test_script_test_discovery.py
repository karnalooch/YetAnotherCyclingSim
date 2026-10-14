"""Guard against silently omitted tests and successful empty discovery."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.ci.run_script_tests import discover, run_module


class ScriptDiscoveryTests(unittest.TestCase):
    def test_new_nested_test_is_discovered_without_workflow_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nested = root / "scripts/new_domain/deeper/test_new.py"
            nested.parent.mkdir(parents=True)
            nested.write_text("", encoding="utf-8")
            self.assertEqual(discover(root), ["scripts/new_domain/deeper/test_new.py"])

    def test_empty_and_all_skipped_suites_cannot_pass(self):
        for body in (
            "",
            "import unittest\nclass T(unittest.TestCase):\n @unittest.skip('missing')\n def test_x(self): pass\n",
        ):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                test = root / "scripts/test_empty.py"
                test.parent.mkdir()
                test.write_text(body, encoding="utf-8")
                with patch("sys.path", list(__import__("sys").path)):
                    if body:
                        self.assertFalse(
                            run_module(root, "scripts/test_empty.py")["passed"]
                        )
                    else:
                        with self.assertRaisesRegex(ValueError, "non-empty"):
                            run_module(root, "scripts/test_empty.py")

    def test_import_error_is_not_a_passing_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            test = root / "scripts/test_missing.py"
            test.parent.mkdir()
            test.write_text("raise ImportError('fixture')", encoding="utf-8")
            with self.assertRaises(ImportError):
                run_module(root, "scripts/test_missing.py")

    def test_external_module_is_rejected(self):
        with self.assertRaises(ValueError):
            run_module(Path(__file__).resolve().parents[2], "../test_escape.py")


    def test_plan_rejects_skipping_discovered_full_suite(self):
        from scripts.ci.run_script_tests import validate_plan
        import json
        import subprocess

        root = Path(__file__).resolve().parents[2]
        all_tests = discover(root)
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        with tempfile.TemporaryDirectory() as temp:
            plan_path = Path(temp) / "plan.json"
            plan = {
                "schema_version": 1,
                "head": head,
                "full_module_count": len(all_tests),
                "mode": "FULL",
                "reason": "test",
                "modules": all_tests[:-1],
            }
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cannot omit"):
                validate_plan(root, plan_path)
            plan["mode"] = "DRAFT_SCOPED"
            plan["modules"] = []
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid, missing"):
                validate_plan(root, plan_path)
            plan["mode"] = "FULL"
            plan["modules"] = all_tests
            plan["head"] = "0" * 40
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA does not match"):
                validate_plan(root, plan_path)

    def test_parallel_worker_uses_bounded_isolated_subprocess(self):
        from scripts.ci.run_script_tests import run_isolated
        import json
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            relative = "scripts/ci/test_script_test_discovery.py"
            folder = output / relative.removesuffix(".py")
            folder.mkdir(parents=True)
            with patch("scripts.ci.run_script_tests.subprocess.run") as run:
                def fake_run(arguments, **kwargs):
                    Path(arguments[arguments.index("--output") + 1], "result.json").write_text(
                        json.dumps({"tests": 4, "skipped": 0, "passed": True}),
                        encoding="utf-8",
                    )
                    return Mock(returncode=0)
                run.side_effect = fake_run
                result = run_isolated(relative, output)
            self.assertTrue(result["passed"])
            self.assertEqual(result["tests"], 4)
            self.assertEqual(run.call_args.kwargs["timeout"], 120)


if __name__ == "__main__":
    unittest.main()
