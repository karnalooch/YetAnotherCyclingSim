"""Check fail-closed paired-capture handoff without loading Unreal."""

import ast
import copy
import hashlib
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace


class PairedCaptureTests(unittest.TestCase):
    def run_handoff(self, *, destroy=True, scene_matches=True):
        source = (
            Path(__file__).parents[1] / "ue/capture_sa_calobra_component230_cliff.py"
        )
        if not source.exists():
            source = Path(__file__).with_name("paired_capture.py")
        tree = ast.parse(source.read_text(encoding="utf-8"))
        function = next(
            n
            for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == "_begin_paired_candidate"
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = root / "custom", root / "pcgex"
            a.mkdir()
            b.mkdir()
            reference = a / "01-baseline-lit.png"
            reference.write_bytes(b"actual acquired reference")
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            captures = [
                {
                    "candidate": False,
                    "path": str(reference),
                    "sha256": digest(reference),
                },
                {"candidate": True},
            ]
            mesh = {"lighting": {"sun": "fixed"}, "generator": "custom"}
            state = {
                "copy": copy,
                "shutil": shutil,
                "Path": Path,
                "_digest": digest,
                "_mesh_receipt": mesh,
                "_captures": captures,
                "_candidate_actors": ["custom actor"],
                "_paired_scene": ["base"],
                "_scene_snapshot": lambda: ["base" if scene_matches else "drift"],
                "_paired_pcgex_output": b,
                "_paired_pcgex_mesh": {"generator": "pcgex"},
                "_pcgex_mesh": None,
                "_shared_baseline": {},
                "OUTPUT": a,
                "unreal": SimpleNamespace(
                    EditorActorSubsystem=object,
                    get_editor_subsystem=lambda _: SimpleNamespace(
                        destroy_actor=lambda _: destroy
                    ),
                ),
            }
            exec(  # noqa: S102 - execute only the repository-owned handoff function
                compile(
                    ast.Module(body=[function], type_ignores=[]), str(source), "exec"
                ),
                state,
            )
            if not destroy or not scene_matches:
                with self.assertRaises(RuntimeError):
                    state["_begin_paired_candidate"]()
                self.assertIsNone(state["_pcgex_mesh"])
                self.assertEqual(list(b.iterdir()), [])
                return
            state["_begin_paired_candidate"]()
            self.assertEqual(state["_candidate_actors"], [])
            self.assertEqual(state["_paired_custom_record"]["mesh"], mesh)
            self.assertEqual(len(state["_captures"]), 1)
            self.assertEqual((b / reference.name).read_bytes(), reference.read_bytes())
            self.assertTrue(state["_shared_baseline"]["custom_removed_before_pcgex"])
            self.assertEqual(state["_pcgex_mesh"], {"generator": "pcgex"})

    def test_common_reference_and_separate_candidates(self):
        self.run_handoff()

    def test_failed_removal_blocks_candidate(self):
        self.run_handoff(destroy=False)

    def test_scene_drift_blocks_candidate(self):
        self.run_handoff(scene_matches=False)


if __name__ == "__main__":
    unittest.main()
