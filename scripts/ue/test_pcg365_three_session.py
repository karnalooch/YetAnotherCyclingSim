"""Offline fail-closed checks for the three-session contact producer contract."""

import ast
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).with_name("pcg365_three_session.py")


def load_functions(*names):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    selected = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]

    def require(condition, message):
        if not condition:
            raise ValueError(message)

    context = {
        "Path": Path,
        "json": json,
        "hashlib": hashlib,
        "require": require,
        "ACTIONS": {
            "collection-contact-prepare",
            "collection-contact-measure",
            "collection-contact-review",
        },
    }
    exec(
        compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"),
        context,
    )
    return context


class ThreeSessionContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pcg365-three-session-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_phase_bytes_bound_and_write_once(self):
        functions = load_functions("identity", "write_once")
        location = "proof/collection-contact-prepare/phase.json"
        value = {"code_sha": "a" * 40, "placement": False}
        proof = functions["write_once"](self.root, location, value)
        self.assertEqual(proof["path"], location)
        self.assertEqual(
            proof,
            {"path": location, **functions["identity"](self.root / location)},
        )
        (self.root / location).write_text("tampered", encoding="utf-8")
        self.assertNotEqual(
            proof["sha256"], functions["identity"](self.root / location)["sha256"]
        )
        with self.assertRaises(FileExistsError):
            functions["write_once"](self.root, location, value)

    def test_phase_path_escape_rejected(self):
        write_once = load_functions("identity", "write_once")["write_once"]
        with self.assertRaisesRegex(ValueError, "Unsafe phase output"):
            write_once(self.root, "../escape.json", {})
        self.assertFalse((self.root.parent / "escape.json").exists())

    def test_fixed_action_contract_never_accepts_extra_phases(self):
        run = load_functions("run")["run"]
        callbacks = []
        context = run.__globals__
        context["prepare"] = lambda *args: {"status": "PREPARED"}
        context["measure"] = lambda *args: {"status": "MEASURED"}
        context["review"] = lambda *args: callbacks.append("REVIEW")
        for action, status in (
            ("collection-contact-prepare", "PREPARED"),
            ("collection-contact-measure", "MEASURED"),
        ):
            result = []
            run(
                self.root,
                self.root / "proof" / action,
                "a" * 40,
                action,
                lambda: {},
                result.append,
            )
            self.assertEqual(result, [{"status": status}])
        review_result = []
        run(
            self.root,
            self.root / "proof/collection-contact-review",
            "a" * 40,
            "collection-contact-review",
            lambda: {},
            review_result.append,
        )
        self.assertEqual(callbacks, ["REVIEW"])
        self.assertEqual(review_result, [])
        with self.assertRaisesRegex(ValueError, "Unknown contact session"):
            run(
                self.root,
                self.root / "proof/collection-contact-all",
                "a" * 40,
                "collection-contact-all",
                lambda: {},
                review_result.append,
            )
        with self.assertRaisesRegex(ValueError, "Unexpected session output"):
            run(
                self.root,
                self.root / "proof/collection-contact-measure",
                "a" * 40,
                "collection-contact-prepare",
                lambda: {},
                review_result.append,
            )

    def test_binding_readback_rejects_wrong_head(self):
        source = self.root / "proof/material/binding.json"
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps({"code_sha": "a" * 40}), encoding="utf-8")
        context = load_functions("binding_readback")
        calls = []
        context["binding_readback"].__globals__["material"] = SimpleNamespace(
            verify_binding=lambda value: calls.append(value)
        )
        with self.assertRaisesRegex(ValueError, "HEAD differs"):
            context["binding_readback"](self.root, "b" * 40)
        self.assertEqual(calls, [])
        self.assertEqual(
            context["binding_readback"](self.root, "a" * 40),
            {"code_sha": "a" * 40},
        )
        self.assertEqual(calls, [{"code_sha": "a" * 40}])


if __name__ == "__main__":
    unittest.main()
