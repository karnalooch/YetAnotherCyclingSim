"""Test real owned exits and source-proof admission with disposable fixtures."""

from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts.assets import run_road_decals_source_proof as host


class RoadDecalHostTests(unittest.TestCase):
    def test_exact_source_on_real_windows_style_checkout_keeps_raw_byte_gate(self):
        rule = b"scripts/assets/render_material_forge.gd text eol=lf\n"
        attributes = (host.ROOT / ".gitattributes").read_bytes()
        self.assertIn(rule, attributes)
        originals = {name: (host.ROOT / name).read_bytes() for name in host.SOURCE_FILES}
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_ATTR_NOSYSTEM="1")
        for pinned in (False, True):
            with self.subTest(exporter_lf_pinned=pinned), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / ".gitattributes").write_bytes(
                    attributes if pinned else attributes.replace(rule, b"", 1))
                for name, raw in originals.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(raw)
                recipe, upstreams = root / "fixture-recipe.json", root / "fixture-upstreams.json"
                recipe.write_bytes(b"{}\n")
                upstreams.write_bytes(b"{}\n")

                def git(directory, *arguments):
                    return subprocess.check_output(
                        ["git", "-C", str(directory), "-c", "core.autocrlf=true",
                         "-c", "core.eol=crlf", "-c", "core.safecrlf=false",
                         "-c", "core.hooksPath=" + str(root / "unused-hooks"),
                         "-c", "user.name=Disposable fixture",
                         "-c", "user.email=fixture@example.invalid", *arguments],
                        env=environment, stderr=subprocess.PIPE, text=True).strip()

                git(root, "init", "--quiet")
                git(root, "add", "--", ".")
                git(root, "commit", "--quiet", "--no-gpg-sign", "-m", "Disposable source fixture")
                head = git(root, "rev-parse", "HEAD")
                for name in originals:
                    (root / name).unlink()
                git(root, "checkout-index", "--all", "--force")
                different_raw_files = [name for name in originals
                                       if git(root, "rev-parse", head + ":" + name)
                                       != git(root, "hash-object", "--no-filters", str(root / name))]
                self.assertEqual(different_raw_files, [] if pinned else
                                 ["scripts/assets/render_material_forge.gd"])
                # Git's normalized content diff is empty even when its stat
                # cache reports a physical newline conversion as modified.
                self.assertEqual(git(root, "diff", "--quiet"), "")
                with patch.object(host, "ROOT", root), patch.object(host.admitted, "git", git), \
                        patch.object(host.decals, "DEFAULT_RECIPE", recipe), \
                        patch.object(host.decals.forge, "DEFAULT_UPSTREAMS", upstreams):
                    if not pinned:
                        with self.assertRaisesRegex(ValueError, "exact clean tracked checkout|revision: scripts/assets/render_material_forge.gd"):
                            host.exact_source(head)
                        continue
                    host.exact_source(head)
                    for name, raw in originals.items():
                        self.assertEqual((root / name).read_bytes(), raw)
                    # A clean normalized content diff cannot admit altered
                    # executable bytes; either strict source guard rejects it.
                    name = host.SOURCE_FILES[0]
                    (root / name).write_bytes(originals[name].replace(b"\n", b"\r\n", 1))
                    self.assertEqual(git(root, "diff", "--quiet"), "")
                    self.assertNotEqual(git(root, "rev-parse", head + ":" + name),
                                        git(root, "hash-object", "--no-filters", str(root / name)))
                    with self.assertRaisesRegex(ValueError, "exact clean tracked checkout|revision: " + name):
                        host.exact_source(head)

    def command(self, root, text):
        child = root / "render fixture.py"
        child.write_text(text, encoding="utf-8")
        return {"motif": "fixture", "argv": [sys.executable, str(child)],
                "log_path": str(root / "render.log"), "required_process_exit": 0}

    def test_real_zero_exit_is_observed_and_log_is_bound(self):
        with tempfile.TemporaryDirectory(prefix="crack render ") as directory:
            root = Path(directory)
            command = self.command(root, "print('fixture-render-complete')\n")
            records = []
            host.render_owned(command, 2, records)
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["exit_observed"])
            self.assertEqual(records[0]["exit_code"], 0)
            self.assertIsInstance(records[0]["pid"], int)
            self.assertFalse(records[0]["stopped_on_failure"])
            self.assertEqual(records[0]["log_sha256"], hashlib.sha256((root / "render.log").read_bytes()).hexdigest())

    def test_nonzero_fatal_output_and_timeout_never_pass(self):
        for mode, code, message in (
            ("nonzero", "raise SystemExit(7)\n", "exited nonzero"),
            ("fatal", "print('COMPUTE SHADER ERROR fixture')\n", "shader/export failure"),
            ("fatal_uppercase", "print('SHADER ERROR: fixture compiler failure')\n", "shader/export failure"),
            ("timeout", "import time\nprint('fixture',flush=True)\ntime.sleep(15)\n", "exceeded its deadline"),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                records = []
                with self.assertRaisesRegex(ValueError, message):
                    host.render_owned(self.command(root, code), 1, records)
                self.assertTrue(records[0]["exit_observed"])
                self.assertIs(type(records[0]["exit_code"]), int)
                self.assertEqual(records[0]["stopped_on_failure"], mode == "timeout")
                self.assertIn("log_sha256", records[0])

    def test_stale_output_is_not_overwritten_or_reported_as_an_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = self.command(root, "print('new')\n")
            (root / "render.log").write_bytes(b"retained original")
            records = []
            with self.assertRaises(FileExistsError):
                host.render_owned(command, 1, records)
            self.assertEqual((root / "render.log").read_bytes(), b"retained original")
            self.assertFalse(records[0]["exit_observed"])
            self.assertIsNone(records[0]["pid"])

    def runtime_fixture(self, root):
        tools = root / "tool-cache/material-forge"
        hashes = {}
        programs = {}
        for role, folder, archive_name, name in (
            ("godot", "godot-4.7.2-stable", "Godot_v4.7.2-stable_win64.exe.zip", host.admitted.GODOT_NAME),
            ("material_maker", "material-maker-1.7", "material_maker_1_7_windows.zip", "material_maker.exe"),
        ):
            executable = tools / folder / name
            executable.parent.mkdir(parents=True)
            raw = ("disposable archive executable " + role).encode()
            executable.write_bytes(raw)
            archive = tools / archive_name
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(name, raw)
            hashes[role] = hashlib.sha256(archive.read_bytes()).hexdigest()
            programs[role] = executable
        source = tools / ("material-maker-source-" + host.admitted.MM_SOURCE_SHA)
        (source / ".godot/imported").mkdir(parents=True)
        (source / "project.godot").write_text("fixture project")
        (source / ".godot/global_script_class_cache.cfg").write_text("fixture cache")
        node = programs["material_maker"].parent / "nodes/material.mmg"
        node.parent.mkdir()
        node.write_text("fixture node")
        return hashes, programs

    def test_installed_producer_must_match_archive_and_remain_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hashes, programs = self.runtime_fixture(root)
            with patch.object(host.admitted, "GODOT_ARCHIVE_SHA", hashes["godot"]), \
                    patch.object(host.admitted, "MM_ARCHIVE_SHA", hashes["material_maker"]), \
                    patch.object(host, "PBR_NODE_SHA256", hashlib.sha256(b"fixture node").hexdigest()), \
                    patch.object(host.admitted, "primed_source_identity", return_value={"fixture": "pinned"}):
                value = host.runtime({"root": str(root)})
                host.verify_runtime(value)
                node = programs["material_maker"].parent / "nodes/material.mmg"
                node.write_text("changed node")
                with self.assertRaisesRegex(ValueError, "PBR node differs"):
                    host.runtime({"root": str(root)})
                node.write_text("fixture node")
                programs["godot"].write_bytes(b"changed binary")
                with self.assertRaisesRegex(ValueError, "producer changed"):
                    host.verify_runtime(value)
                with self.assertRaisesRegex(ValueError, "approved archive"):
                    host.runtime({"root": str(root)})

    def proof_fixture(self, root, deterministic):
        """Exercise host orchestration; fixture adapter never claims real Godot pixels."""
        work = root / "work"
        work.mkdir()
        child = root / "native process fixture.py"
        child.write_text("import sys\nprint('fixture '+sys.argv[1])\n", encoding="utf-8")
        source_identity = {"disposable_fixture": True}

        def author(_install, output):
            output.mkdir()
            for index in range(8):
                (output / ("motif-" + str(index))).mkdir()
            return {"source_identity": source_identity}

        def commands(output, _godot, _source):
            return {"source_identity": source_identity, "commands": [
                {"motif": "motif-" + str(index), "argv": [sys.executable, str(child), str(index)],
                 "log_path": str(output / ("motif-" + str(index)) / "source-runner.log"),
                 "required_process_exit": 0} for index in range(8)]}

        def validate(output):
            (output / "run-manifest.json").write_text('{"disposable_fixture":true}')
            return {"status": "DECAL_MAP_CHECKS_PASS_UE_REVIEW_PENDING"}

        producer = {"workspace": root, "source": root / "unused-source", "pins": {},
                    "primed_source_identity": {"disposable_fixture": True},
                    "programs": {"godot": Path(sys.executable), "material_maker": root / "unused.exe"}}
        return (
            patch.object(host, "exact_source"),
            patch.object(host, "runtime", return_value=producer),
            patch.object(host, "verify_runtime"),
            patch.object(host, "load_workspace", return_value={"work": str(work), "root": str(root)}),
            patch.object(host.decals, "source_identity", return_value=source_identity),
            patch.object(host.decals, "author", side_effect=author),
            patch.object(host.decals, "render_commands", side_effect=commands),
            patch.object(host.decals, "validate", side_effect=validate),
            patch.object(host.decals, "compare", return_value={"deterministic": deterministic,
                         "motif_count": 8, "maps_per_motif": 5, "native_decode_verified": True}),
        )

    def test_complete_host_requires_sixteen_real_exits_and_two_run_map_match(self):
        from contextlib import ExitStack
        for match in (True, False):
            with self.subTest(match=match), tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
                root = Path(directory)
                for mocked in self.proof_fixture(root, match):
                    stack.enter_context(mocked)
                stack.enter_context(redirect_stdout(io.StringIO()))
                if match:
                    host.prove("a" * 40, "123", "1")
                else:
                    with self.assertRaisesRegex(ValueError, "map/graph bytes differ"):
                        host.prove("a" * 40, "123", "1")
                path = root / "work/material-forge/road-decals" / ("a" * 40) / "123-1/source-proof.json"
                receipt = json.loads(path.read_text())
                self.assertEqual(receipt["status"], "ROAD_DECALS_SOURCE_DETERMINISM_PASS" if match else "ROAD_DECALS_SOURCE_FAILED")
                self.assertEqual(len(receipt["processes"]), 16)
                self.assertTrue(all(row["exit_observed"] and row["exit_code"] == 0 for row in receipt["processes"]))
                self.assertEqual(receipt["native_process_exit_verified"], match)
                self.assertEqual(receipt["two_run_graph_and_map_bytes_equal"], match)
                self.assertFalse(receipt["unreal_consumption_verified"])
                self.assertFalse(receipt["world_mutation"])
                self.assertFalse(receipt["performance_pass"])


if __name__ == "__main__":
    unittest.main()
