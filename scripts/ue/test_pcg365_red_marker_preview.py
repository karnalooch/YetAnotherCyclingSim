"""Offline fail-closed review-marker tests; no native Unreal and no asset authoring."""
import ast
import json
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = ROOT / "worldgen/sa_calobra/pcg365_rejected_sites_review_v1.json"
SOURCE = HERE / "pcg365_red_marker_preview.py"


def helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"site_check"}
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    def require(ok, message):
        if not ok:
            raise RuntimeError(message)
    globals_ = {
        "require": require,
        "REQUIRED_PRODUCER": "d361e7651d16ff424ae4e812c7d8cbe1fe81d662",
        "REQUIRED_RUN": "38278235093-1",
        "EXPECTED_IDS": ["P0", "P1", "P2", "P3", "P4"],
        "EXPECTED_XY": [[16800,70400],[4800,96800],[184800,180800],[181600,189600],[91200,200800]],
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), globals_)
    return globals_["site_check"]


class RedMarkerReview(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.readback = {
            "code_sha": self.manifest["source_producer_sha"],
            "status": "COLLECTION_CONTACT_FRESH_READBACK",
            "placement": False,
            "cases": [
                {
                    "mesh_id": f"rock{i:02d}",
                    "point_index": n,
                    "world_xy_cm": site["xy_cm"],
                    "policy_decision": {"status": "REJECTED"},
                }
                for n, site in enumerate(self.manifest["markers"])
                for i in range(20)
            ],
        }

    def test_exact_five_sites_accept_historical_rejections_only(self):
        sites = helpers()(self.manifest, self.readback)
        self.assertEqual([s["id"] for s in sites], ["P0", "P1", "P2", "P3", "P4"])
        self.assertEqual(len(self.readback["cases"]), 100)
        self.assertFalse(self.manifest["placement"])

    def test_site_coordinate_or_decision_drift_fails(self):
        self.manifest["markers"][0]["xy_cm"] = [1, 1]
        with self.assertRaisesRegex(RuntimeError, "five frozen"):
            helpers()(self.manifest, self.readback)
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.readback["cases"][0]["policy_decision"]["status"] = "PASS_SAMPLED_CONTACT_ONLY"
        with self.assertRaisesRegex(RuntimeError, "Site input"):
            helpers()(self.manifest, self.readback)

    def test_missing_or_duplicate_case_refused(self):
        self.readback["cases"].pop()
        with self.assertRaisesRegex(RuntimeError, "complete 20x5"):
            helpers()(self.manifest, self.readback)
        self.setUp()
        self.readback["cases"][0] = dict(self.readback["cases"][1])
        with self.assertRaisesRegex(RuntimeError, "complete 20x5"):
            helpers()(self.manifest, self.readback)

    def test_scope_and_hash_pins_not_optional(self):
        self.manifest["placement"] = True
        with self.assertRaisesRegex(RuntimeError, "scope drift"):
            helpers()(self.manifest, self.readback)
        self.manifest["placement"] = False
        self.manifest["source_producer_sha"] = "f" * 40
        with self.assertRaisesRegex(RuntimeError, "Wrong producer"):
            helpers()(self.manifest, self.readback)


    def test_interactive_red_viewer_starts_only_with_explicit_persistent_flag(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        red = next(node for node in tree.body
                   if isinstance(node, ast.ClassDef) and node.name == "RedReview")
        start = next(node for node in red.body
                     if isinstance(node, ast.FunctionDef) and node.name == "start")
        self.assertIn("persistent", [arg.arg for arg in start.args.kwonlyargs])
        self.assertEqual(len(start.args.kw_defaults), 1)
        self.assertIsInstance(start.args.kw_defaults[0], ast.Constant)
        self.assertIs(start.args.kw_defaults[0].value, False)
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('self.report["status"] = "RED_LIVE_SCENE_READY"', source)
        self.assertIn("set_keep_python_script_alive(True)", source)
        self.assertIn('if __name__ == "__main__":', source)

    def test_live_stream_bootstrap_uses_only_original_rejected_site_reader(self):
        script = HERE / "bootstrap_pcg365_red_stream.py"
        source = script.read_text(encoding="utf-8")
        ast.parse(source)
        self.assertIn("RedReview(project, session / \"scene\", manifest, sha)", source)
        self.assertIn("LIVE.start(persistent=True)", source)
        self.assertNotIn("start_capture(", source)
        self.assertNotIn("save_asset(", source)



class LiveBootstrapSessionGate(unittest.TestCase):
    """An actual UE -AbsLog exists before -ExecutePythonScript begins."""

    @staticmethod
    def gate():
        path = HERE / "bootstrap_pcg365_red_stream.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        selected = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "require_fresh_live_session"
        ]
        self_ns = {}
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"),
             self_ns)
        return self_ns["require_fresh_live_session"]

    def test_fresh_session_with_only_unreal_abslog_is_allowed(self):
        gate = self.gate()
        with tempfile.TemporaryDirectory(prefix="pcg365-red-session-") as temp:
            session = Path(temp)
            gate(session)
            (session / "editor.log").write_text("Engine startup", encoding="utf-8")
            gate(session)

    def test_unrelated_old_artifacts_are_rejected(self):
        gate = self.gate()
        with tempfile.TemporaryDirectory(prefix="pcg365-red-session-") as temp:
            session = Path(temp)
            (session / "editor.log").write_text("Engine startup", encoding="utf-8")
            for unwanted in ("red-live-error.json", "pcg365-stream-session.json"):
                candidate = session / unwanted
                candidate.write_text("old", encoding="utf-8")
                with self.subTest(unwanted=unwanted), self.assertRaisesRegex(
                    RuntimeError, "unexpected prior output"
                ):
                    gate(session)
                candidate.unlink()
            (session / "scene").mkdir()
            with self.assertRaisesRegex(RuntimeError, "unexpected prior output"):
                gate(session)

    def test_missing_directory_is_rejected(self):
        gate = self.gate()
        with tempfile.TemporaryDirectory(prefix="pcg365-red-session-") as temp:
            with self.assertRaisesRegex(RuntimeError, "new session"):
                gate(Path(temp) / "not-created")

    def test_bootstrap_handles_rejections_without_uncaught_python_error(self):
        script = (HERE / "bootstrap_pcg365_red_stream.py").read_text(encoding="utf-8")
        tree = ast.parse(script)
        main = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "main")
        execution = next(node for node in main.body if isinstance(node, ast.Try))
        calls_in_try = [
            node for node in ast.walk(execution)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "require_fresh_live_session"
        ]
        self.assertEqual(len(calls_in_try), 1)
        self.assertIn("PCG365_RED_STREAM_BOOTSTRAP_FAILED", script)
        self.assertNotIn("unreal.log_error(error)", script)


if __name__ == "__main__":
    unittest.main()
