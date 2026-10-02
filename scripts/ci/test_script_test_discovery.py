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


if __name__ == "__main__":
    unittest.main()
