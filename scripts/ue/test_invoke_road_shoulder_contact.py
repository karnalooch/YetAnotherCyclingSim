"""Exercise the production read-only bridge against disposable file/process fixtures."""

from __future__ import annotations

from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.ci import official_mcp_bob_session as session
from scripts.ci import test_sa_calobra_shoulder_contact as contact_fixtures
from scripts.proof import sa_calobra_shoulder_contact as contact

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts/ue/Invoke-YacsRoadShoulderContact.ps1"
HEAD = "a" * 40
TOKEN = "123-1"


def production_bridge():
    source = WRAPPER.read_text(encoding="utf-8")
    code = source.split("$bridgeCode = @'\n", 1)[1].split("\n'@", 1)[0]
    namespace = {"__name__": "diagnostic_bridge_fixture", "session": session}
    exec(compile(code, str(WRAPPER) + "::bridgeCode", "exec"), namespace)
    return namespace


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


class RoadShoulderBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = production_bridge()

    def test_windows_checkout_preserves_source_closure_and_raw_byte_guard(self):
        source_guard = WRAPPER.read_text(encoding="utf-8").split(
            "function Require-ExactSource {", 1
        )[1].split("\nfunction Require-IdleHost", 1)[0]
        direct = re.findall(r"^\s*'([^']+)',?$", source_guard, re.MULTILINE)
        self.assertIn("scripts/runner/Get-YacsUnrealHostState.ps1", direct)
        plugins = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "--", "Plugins/YacsBobInspection"],
            text=True,
        ).splitlines()
        paths = sorted(set(direct) | set(session.operation.BASE_SOURCE_PATHS)
                       | set(session.UTILITY_SOURCE_PATHS) | set(plugins))
        originals = {relative: (ROOT / relative).read_bytes() for relative in paths}
        attributes = (ROOT / ".gitattributes").read_bytes()
        host_state = "scripts/runner/Get-YacsUnrealHostState.ps1"
        missing_rule = (host_state + " text eol=lf\n").encode()
        self.assertIn(missing_rule, attributes)
        # Exercise real Git conversion, even on Linux. Do not execute any source
        # fixture or depend on the test host's Git filters, hooks or checkout EOL.
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_")}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_ATTR_NOSYSTEM="1")
        for pinned in (False, True):
            with self.subTest(lf_rule_present=pinned), tempfile.TemporaryDirectory() as directory:
                checkout = Path(directory)
                (checkout / ".gitattributes").write_bytes(
                    attributes if pinned else attributes.replace(missing_rule, b"", 1)
                )
                for relative, raw in originals.items():
                    target = checkout / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(raw)

                def git(*arguments):
                    return subprocess.check_output(
                        ["git", "-C", str(checkout), "-c", "core.autocrlf=true",
                         "-c", "core.eol=crlf", "-c", "core.safecrlf=false",
                         "-c", "core.hooksPath=" + str(checkout / "unused-hooks"),
                         "-c", "user.name=Disposable fixture",
                         "-c", "user.email=fixture@example.invalid", *arguments],
                        env=environment, stderr=subprocess.PIPE,
                    ).decode().splitlines()

                git("init", "--quiet")
                git("add", "--", ".")
                git("commit", "--quiet", "--no-gpg-sign", "-m", "Disposable source identity fixture")
                committed = git("rev-parse", *("HEAD:" + relative for relative in paths))
                for relative in paths:
                    (checkout / relative).unlink()
                git("checkout-index", "--all", "--force")
                physical = git("hash-object", "--no-filters", "--", *paths)
                mismatches = {relative for relative, expected, actual
                              in zip(paths, committed, physical) if expected != actual}
                self.assertEqual(len(committed), len(paths))
                self.assertEqual(len(physical), len(paths))
                self.assertEqual(mismatches, set() if pinned else {host_state})
                if not pinned:
                    self.assertEqual((checkout / host_state).read_bytes(),
                                     originals[host_state].replace(b"\n", b"\r\n"))
                    continue
                for relative, raw in originals.items():
                    self.assertEqual((checkout / relative).read_bytes(), raw, relative)
                # A normalized Git diff cannot see this altered byte. The same
                # no-filters hash used by the production guard must still reject.
                target = checkout / host_state
                target.write_bytes(originals[host_state].replace(b"\n", b"\r\n", 1))
                git("diff", "--quiet", "HEAD", "--", ".", ":(exclude)Content/**")
                self.assertNotEqual(git("hash-object", "--no-filters", "--", host_state)[0],
                                    committed[paths.index(host_state)])

    def predecessors(self):
        common = dict(schema_version=1, issue=364, exact_sha=HEAD, run_token=TOKEN,
                      error=None, secondary_errors=[])
        base = dict(common, status="ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE",
                    reader_pass=True, read_only=True, persistent_world_mutation=False,
                    owned_editor_exit_observed=True, owned_editor_exit_code=0,
                    owned_editor_stopped_on_failure=False)
        gpu = dict(common, status="ROAD_ASPHALT_GPU_LIT_REVIEW_HOST_PASS",
                   authenticated_saved_and_reloaded=True, native_lit_frames_retained=True,
                   shoulder_network_material_ids_verified=True, original_map_mutated=False,
                   geometry_mutated=False, editor_exit_observed=True, editor_exit_code=0,
                   stopped_on_failure=False, verified_frame_count=68, expected_frame_count=68)
        return base, gpu

    def test_prior_pass_requires_exact_run_real_zero_exit_and_unmodified_geometry(self):
        self.bridge["prior_contract"](*self.predecessors(), HEAD, TOKEN)
        for index, field, bad in (
            (0, "exact_sha", "b" * 40), (1, "run_token", "124-1"),
            (0, "status", "STARTED"), (1, "status", "FRAMES_EXIST"),
            (0, "owned_editor_exit_observed", False), (1, "editor_exit_observed", 1),
            (0, "owned_editor_exit_code", False), (1, "editor_exit_code", "0"),
            (1, "editor_exit_code", 7), (1, "stopped_on_failure", True),
            (0, "reader_pass", "true"), (0, "read_only", False),
            (0, "persistent_world_mutation", True), (1, "geometry_mutated", True),
            (1, "original_map_mutated", True), (1, "native_lit_frames_retained", False),
            (1, "verified_frame_count", 67), (1, "error", "lost process"),
            (1, "secondary_errors", ["locked log"]),
        ):
            with self.subTest(field=field, value=bad):
                values = list(self.predecessors())
                values[index][field] = bad
                with self.assertRaises(ValueError):
                    self.bridge["prior_contract"](*values, HEAD, TOKEN)
        values = list(self.predecessors())
        del values[1]["geometry_mutated"]
        with self.assertRaises(ValueError):
            self.bridge["prior_contract"](*values, HEAD, TOKEN)

    def test_six_installed_headers_include_public_bounds_and_remain_version_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = Path(directory)
            write_json(engine / "Engine/Build/Build.version", {
                "MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 2, "Changelist": 56702186,
            })
            entry = engine / "Engine/Content/Maps/Entry.umap"
            entry.parent.mkdir(parents=True)
            entry.write_bytes(b"disposable entry identity fixture")
            for relative, symbols in self.bridge["HEADERS"].items():
                path = engine / "Engine/Source" / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("\n".join(symbols), encoding="utf-8")
            api, pins = self.bridge["primary_api"](engine, HEAD)
            self.assertEqual(len(api["headers"]), 6)
            self.assertEqual(len(pins), 8)
            self.assertEqual(self.bridge["HEADERS"]["Runtime/Engine/Classes/Kismet/KismetSystemLibrary.h"],
                             ["GetComponentBounds"])
            self.assertEqual(api["engine_version"], "5.8.2-56702186")
            self.assertEqual(api["startup_map_sha256"], hashlib.sha256(entry.read_bytes()).hexdigest())
            for relative, symbols in self.bridge["HEADERS"].items():
                path = engine / "Engine/Source" / relative
                original = path.read_text()
                path.write_text(original.replace(symbols[0], "AbsentSymbol"))
                with self.assertRaisesRegex(ValueError, "symbol missing"):
                    self.bridge["primary_api"](engine, HEAD)
                path.write_text(original)
            write_json(engine / "Engine/Build/Build.version", {
                "MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 1, "Changelist": 56702186,
            })
            with self.assertRaisesRegex(ValueError, "version differs"):
                self.bridge["primary_api"](engine, HEAD)

    def fixture(self, directory, *, target="window0112", cut_raw=None):
        root = Path(directory) / ("rm-" + TOKEN)
        diagnostic = root / "Saved/RuntimeProof/RoadMaterialBaseline" / TOKEN / contact.target_spec(target)["output_name"]
        diagnostic.mkdir(parents=True)
        retained = Path(directory) / "original"
        retained.mkdir()
        report, frames = contact_fixtures.ShoulderContactTests().evidence(retained, target=target, cut_raw=cut_raw)
        for frame in frames:
            relative = "readiness/" + frame["frame_id"] + "/capture-readiness.json"
            path = retained / "capture" / relative
            write_json(path, dict(status="NATIVE_LOADING_AND_MIPS_READY",
                       height_edits_applied=False, saved_to_map=False,
                       height_mip_lease_requested=True, native_loading_barrier_completed=True,
                       textures_after=[dict(is_default_texture=False, is_compiling=False,
                                            mips=8, resident_mips=8)]))
            frame["native_readiness"].update(receipt=relative, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        source = Path(directory) / "frozen-input.json"
        source.write_text('{"source":"unchanged"}', encoding="utf-8")
        api = diagnostic / "native-api-evidence.json"
        api.write_text('{"disposable_fixture":true}', encoding="utf-8")
        api_pin = self.bridge["identity"](api)
        report.update(source_identity={"disposable_fixture": True}, geometry_consumers_executed=False,
                      source_scene={"lighting_modified": False}, primary_api_receipt_sha256=api_pin["sha256"])
        report["restoration"]["height_mip_leases_released"] = True
        write_json(retained / "shoulder-contact.json", report)
        write_json(retained / "capture/survey.json", {"status": "CAPTURED", "frames": frames})
        inputs = dict(exact_sha=HEAD, run_token=TOKEN, retained_root=str(retained),
                      diagnostic_target=target,
                      files=[self.bridge["identity"](source), api_pin], plan=report["plan"],
                      source_identity=report["source_identity"], api_receipt=api_pin)
        inputs_path = diagnostic / "source-inputs.json"
        input_pin = self.bridge["write_once"](inputs_path, inputs)
        return root, diagnostic, retained, source, report, input_pin

    def complete(self, fixture, *, target="window0112"):
        root, diagnostic, _retained, _source, _report, input_pin = fixture
        arguments = ["bridge", "complete", str(root), "unused-config", HEAD, TOKEN,
                     "unused-engine", "unused-engine-identity", input_pin["sha256"], target]
        output = io.StringIO()
        with patch.object(session, "ROOT", root), patch.object(session, "_assert_isolated_root"), \
                patch.object(sys, "argv", arguments), redirect_stdout(output):
            self.bridge["main"]()
        return json.loads(output.getvalue())

    def test_complete_verifies_both_original_and_artifact_copy_without_touching_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(directory)
            before = self.bridge["identity"](fixture[3])
            result = self.complete(fixture)
            self.assertEqual(result["frame_count"], 12)
            self.assertEqual(result["retained_file_count"], 26)
            self.assertTrue(result["original_and_artifact_copy_verified"])
            self.assertEqual(result["rendered_owner"], "PENDING_PAIRED_VISUAL_REVIEW")
            self.assertEqual(before, self.bridge["identity"](fixture[3]))
            for root in (fixture[1], fixture[2]):
                self.assertEqual(contact.verify(root, HEAD)["frame_count"], 12)
            original = fixture[1] / "shoulder-contact.json"
            original_bytes = original.read_bytes()
            with self.assertRaises(FileExistsError):
                self.complete(fixture)
            self.assertEqual(original.read_bytes(), original_bytes)

    def test_hairpin_target_requires_the_same_run_successful_0112_restoration(self):
        prior = dict(status="SHOULDER_CONTACT_READ_ONLY_HOST_PASS", exact_sha=HEAD, run_token=TOKEN,
                     verified_frame_count=12, editor_exit_code=0, error=None, secondary_errors=[],
                     read_only=True, geometry_mutated=False, original_map_mutated=False,
                     source_inputs_unchanged=True, restored_visibility_verified=True,
                     editor_exit_observed=True, stopped_on_failure=False)
        self.bridge["restored_window0112"](prior, HEAD, TOKEN)
        for field, value in (("exact_sha", "b" * 40), ("run_token", "124-1"),
                             ("diagnostic_target", "hairpin0081"),
                             ("verified_frame_count", 6), ("editor_exit_code", False),
                             ("editor_exit_observed", False), ("geometry_mutated", True),
                             ("restored_visibility_verified", False), ("source_inputs_unchanged", False),
                             ("secondary_errors", ["original bounds changed"])):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.bridge["restored_window0112"](dict(prior, **{field: value}), HEAD, TOKEN)

    def test_hairpin_retains_six_modes_and_exact_source_cut_in_its_own_directory(self):
        raw = json.dumps({"operation": "CUT_ONLY", "grid_step_m": 0.5,
                          "rect": {"min_x": 2080, "min_y": 990, "max_x": 2300, "max_y": 1310,
                                   "width": 221, "height": 321}}).encode()
        with (tempfile.TemporaryDirectory() as directory,
              patch.object(contact, "HAIRPIN_CUT_SHA256", hashlib.sha256(raw).hexdigest()),
              patch.object(contact, "HAIRPIN_CUT_SIZE", len(raw))):
            fixture = self.fixture(directory, target="hairpin0081", cut_raw=raw)
            result = self.complete(fixture, target="hairpin0081")
            self.assertEqual(result["frame_count"], 6)
            self.assertEqual(result["retained_file_count"], 15)
            self.assertEqual(result["diagnostic_target"], "hairpin0081")
            self.assertEqual(fixture[1].name, "shoulder-contact-0081")
            self.assertFalse(fixture[1].with_name("shoulder-contact").exists())
            self.assertEqual((fixture[1] / "source-cut-manifest.json").read_bytes(), raw)
            self.assertEqual(contact.verify(fixture[1], HEAD, target="hairpin0081")["frame_count"], 6)
            with self.assertRaises(FileNotFoundError):
                self.complete(fixture, target="window0112")
            self.assertFalse(fixture[1].with_name("shoulder-contact").exists())

    def test_failed_initialization_retains_original_error_before_any_survey_read(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = self.fixture(directory)
            _root, diagnostic, retained, _source, report, _input = fixture
            report.update(status="FAILED", error="LandscapeComponent has no component_size_quads")
            report["restoration"]["status"] = "FAILED"
            raw = json.dumps(report).encode()
            (retained / "shoulder-contact.json").write_bytes(raw)
            shutil.rmtree(retained / "capture")
            with self.assertRaisesRegex(ValueError, "LandscapeComponent has no component_size_quads"):
                self.complete(fixture)
            self.assertEqual((diagnostic / "shoulder-contact.json").read_bytes(), raw)
            self.assertEqual((retained / "shoulder-contact.json").read_bytes(), raw)
            self.assertTrue((diagnostic / "retained-files.json").exists())
            self.assertFalse((diagnostic / "verification.json").exists())
            self.assertFalse((diagnostic / "capture/survey.json").exists())

    def test_mutated_source_restoration_camera_or_api_cannot_pass_but_partial_frames_survive(self):
        for failure in ("source", "restore", "camera", "api", "readiness", "missing_frame"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                fixture = self.fixture(directory)
                _root, diagnostic, retained, source, report, _input = fixture
                if failure == "source":
                    source.write_text('{"source":"modified!"}', encoding="utf-8")
                elif failure == "restore":
                    report["restoration"]["status"] = "FAILED"
                elif failure == "camera":
                    report["plan"]["frames"][0]["camera_location_cm"][0] += 1
                elif failure == "api":
                    report["primary_api_receipt_sha256"] = "f" * 64
                elif failure == "readiness":
                    frame = copy.deepcopy(report["plan"]["frames"][0])
                    path = retained / "capture" / frame["native_readiness"]["receipt"]
                    value = json.loads(path.read_text())
                    value["textures_after"][0]["resident_mips"] = 7
                    write_json(path, value)
                    stamp = hashlib.sha256(path.read_bytes()).hexdigest()
                    frame["native_readiness"]["sha256"] = stamp
                    survey = json.loads((retained / "capture/survey.json").read_text())
                    survey["frames"][0]["native_readiness"]["sha256"] = stamp
                    write_json(retained / "capture/survey.json", survey)
                else:
                    (retained / "capture" / report["plan"]["frames"][0]["file"]).unlink()
                write_json(retained / "shoulder-contact.json", report)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.complete(fixture)
                self.assertFalse((diagnostic / "verification.json").exists())
                self.assertTrue((diagnostic / "retained-files.json").is_file())
                self.assertGreaterEqual(len(list((diagnostic / "capture/frames").glob("*.png"))), 11)

    def test_same_length_tamper_bounds_and_different_file_path_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            path.write_bytes(b"original")
            pin = self.bridge["identity"](path)
            path.write_bytes(b"changed!")
            with self.assertRaisesRegex(ValueError, "pin differs"):
                self.bridge["same_pin"](self.bridge["identity"](path), pin)
            with self.assertRaises(ValueError):
                self.bridge["identity"](path, 4)
            path.write_bytes(b"original")
            other = path.with_name("other.json")
            other.write_bytes(path.read_bytes())
            with self.assertRaisesRegex(ValueError, "another path"):
                self.bridge["same_pin"](self.bridge["identity"](other), pin)

    def test_retained_project_producer_is_exact_bounded_and_never_executed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frozen = root / "frozen"
            source = frozen / "support-consumers/network_pavement.py"
            source.parent.mkdir(parents=True)
            raw = b"raise RuntimeError('source is evidence, never execute')\n"
            source.write_bytes(raw)
            expected = {"network_pavement.py": {"sha256": hashlib.sha256(raw).hexdigest(),
                                                "size_bytes": len(raw)}}
            rows = self.bridge["retain_producer_sources"](frozen, root / "evidence", expected)
            self.assertEqual(len(rows), 1)
            self.assertEqual(Path(rows[0]["retained"]["path"]).read_bytes(), raw)
            self.assertEqual(source.read_bytes(), raw)
            with self.assertRaises(FileExistsError):
                self.bridge["retain_producer_sources"](frozen, root / "evidence", expected)
            source.write_bytes(raw.replace(b"RuntimeError", b"RuntimeErr0r"))
            with self.assertRaisesRegex(ValueError, "pin differs"):
                self.bridge["retain_producer_sources"](frozen, root / "rejected", expected)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_powershell_parser_argument_tokens_and_owned_exit_deadline(self):
        with tempfile.TemporaryDirectory(prefix="shoulder contact ") as directory:
            root = Path(directory)
            child = root / "child.py"
            child.write_text("import sys,time\nprint('fixture',flush=True)\n"
                             "time.sleep(15 if sys.argv[1]=='timeout' else 0)\n"
                             "sys.exit(0 if sys.argv[1]=='timeout' else int(sys.argv[1]))\n")
            runner = root / "contracts.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $Python, [string] $Child, [string] $OutputRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
foreach ($name in @('Assert-PlainPath', 'Invoke-OwnedProcess')) {
    $nodes = @($ast.FindAll({param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw 'Missing production function.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$root = $OutputRoot
$diagnostic = $OutputRoot
$WorkspaceConfig = Join-Path $root 'workspace with spaces.json'
$ExpectedHead = 'a' * 40
$RunToken = '123-1'
$engine = @{ Root = (Join-Path $root 'engine with spaces'); Identity = 'root=engine|version=5.8.2-56702186' }
$editorLog = Join-Path $root 'owned-editor.log'
foreach ($name in @('$common', '$arguments')) {
    $node = @($ast.FindAll({param($item)
        $item -is [System.Management.Automation.Language.AssignmentStatementAst] -and $item.Left.Extent.Text -ceq $name
    }, $true))
    if ($node.Count -ne 1) { throw 'Missing production argument array.' }
    . ([scriptblock]::Create($node[0].Extent.Text))
}
if ($common.Count -ne 6 -or $common[0] -cne ('"' + $root + '"') -or
    $common[5] -cne ('"' + $engine.Identity + '"') -or $arguments[1] -cne '/Engine/Maps/Entry' -or
    $arguments[-1] -cne ('-AbsLog="' + $editorLog + '"')) { throw 'Process argument boundaries changed.' }
$receipt = [ordered]@{ processes = @(); editor_pid = $null; editor_exit_observed = $false
    editor_exit_code = $null; stopped_on_failure = $false }
Invoke-OwnedProcess 'exit-zero' $Python @('-I', '-B', ('"' + $Child + '"'), '0') 5
if (-not $receipt.processes[0].exit_observed -or $receipt.processes[0].exit_code -ne 0) { throw 'Actual zero exit missing.' }
$rejected = $false
try { Invoke-OwnedProcess 'exit-seven' $Python @('-I', '-B', ('"' + $Child + '"'), '7') 5 } catch { $rejected = $true }
if (-not $rejected -or $receipt.processes[1].exit_code -ne 7) { throw 'Nonzero process falsely passed.' }
$rejected = $false
try { Invoke-OwnedProcess 'owned-editor' $Python @('-I', '-B', ('"' + $Child + '"'), 'timeout') 1 } catch { $rejected = $true }
if (-not $rejected -or -not $receipt.stopped_on_failure -or -not $receipt.editor_exit_observed -or
    (Get-Process -Id $receipt.editor_pid -ErrorAction SilentlyContinue)) { throw 'Owned deadline did not stop the exact process.' }
'POWERSHELL_SHOULDER_CONTACT_CASES_PASS'
''', encoding="utf-8")
            result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(WRAPPER),
                                     sys.executable, str(child), str(root)], capture_output=True,
                                    text=True, timeout=45, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("POWERSHELL_SHOULDER_CONTACT_CASES_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
