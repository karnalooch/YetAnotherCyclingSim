"""Routing, provenance and cost boundaries for the explicit native detail proof."""

from __future__ import annotations

import ast
import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from scripts.proof.retain_sa_calobra_tpp_survey import no_link

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/sa-calobra-cliff-component230-pcgex.yml"
MARKERS = (
    "[detail-pilot]",
    "[tpp-survey]",
    "[tpp-retain]",
    "[tpp-docs]",
    "[wholemap-material]",
    "[shoulder-contact]",
    "[material-closeout]",
)


def parse_powershell_scripts(sources):
    """Parse every workflow source in one bounded native process per test."""
    payload = [
        {"index": index, "source": source} for index, source in enumerate(sources)
    ]
    command = r"""
$rows = @(ConvertFrom-Json -InputObject ([Console]::In.ReadToEnd()))
$results = @()
foreach ($row in $rows) {
  $tokens = $null
  $errors = $null
  [void][System.Management.Automation.Language.Parser]::ParseInput(
    [string]$row.source, [ref]$tokens, [ref]$errors)
  $messages = @($errors | ForEach-Object { $_.ToString() })
  $results += [ordered]@{ index = [int]$row.index; errors = $messages }
  if ($errors.Count -gt 0) {
    ConvertTo-Json -InputObject $results -Depth 6 -Compress | Write-Output
    exit 1
  }
}
ConvertTo-Json -InputObject $results -Depth 6 -Compress | Write-Output
"""
    result = subprocess.run(
        [shutil.which("pwsh"), "-NoProfile", "-NonInteractive", "-Command", command],
        # ASCII JSON avoids a Windows console-codepage dependency; JSON decoding
        # reconstructs the original Unicode source before native ParseInput.
        input=json.dumps(payload, ensure_ascii=True, allow_nan=False),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "PowerShell parse batch failed: " + result.stdout + result.stderr
        )
    records = json.loads(result.stdout.lstrip("\ufeff"))
    if not isinstance(records, list) or [row.get("index") for row in records] != list(
        range(len(sources))
    ):
        raise AssertionError("PowerShell parser did not report every source in order")
    if any(row.get("errors") != [] for row in records):
        raise AssertionError(
            "PowerShell parser reported syntax errors: " + result.stdout
        )
    return records


class PowerShellParserBatchTests(unittest.TestCase):
    def test_one_bounded_process_preserves_all_source_bytes_and_results(self):
        sources = ['Write-Host "literal `$value"', "# Unicode Ł\n$x=@{value=1}"]
        result = subprocess.CompletedProcess(
            [],
            0,
            json.dumps(
                [
                    {"index": 0, "errors": []},
                    {"index": 1, "errors": []},
                ]
            ),
            "",
        )
        with (
            patch.object(shutil, "which", return_value="pwsh"),
            patch.object(subprocess, "run", return_value=result) as run,
        ):
            self.assertEqual(len(parse_powershell_scripts(sources)), 2)
        run.assert_called_once()
        call = run.call_args
        self.assertEqual(call.kwargs["timeout"], 30)
        self.assertEqual(
            [row["source"] for row in json.loads(call.kwargs["input"])], sources
        )

    def test_syntax_failure_and_incomplete_batch_fail_admission(self):
        for result in (
            subprocess.CompletedProcess(
                [], 1, '[{"index":0,"errors":["bad syntax"]}]', ""
            ),
            subprocess.CompletedProcess([], 0, "[]", ""),
        ):
            with (
                self.subTest(result=result),
                patch.object(shutil, "which", return_value="pwsh"),
                patch.object(subprocess, "run", return_value=result),
            ):
                with self.assertRaises(AssertionError):
                    parse_powershell_scripts(["$x = 1"])


def jobs():
    text = WORKFLOW.read_text(encoding="utf-8")
    return dict(
        re.findall(
            r"^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
            text.split("\njobs:\n", 1)[1],
            flags=re.MULTILINE | re.DOTALL,
        )
    )


def condition(job):
    lines = job.split("    if: >-\n", 1)[1].splitlines()
    expression = " ".join(
        line.strip()
        for line in itertools.takewhile(
            lambda line: line.startswith("      "),
            lines,
        )
    )
    return re.sub(
        r"!(?!=)", "not ", expression.replace("&&", " and ").replace("||", " or ")
    ).strip()


def enabled(job, message="[detail-native]", **overrides):
    context = {
        "github.event_name": "push",
        "github.repository": "karnalooch/YetAnotherCyclingSim",
        "github.actor": "karnalooch",
        "github.ref": "refs/heads/feat/phase2c-pcgex-cliff-topology",
        "github.event.head_commit.message": message,
        "inputs.tpp_survey": False,
    }
    context.update(overrides)
    expression = condition(job)
    for name in sorted(context, key=len, reverse=True):
        expression = expression.replace(name, repr(context[name]))

    # Interpret only the boolean/string subset used by these job conditions.
    # No Python eval or repository expression is executed by this contract test.
    def value(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BoolOp):
            values = [value(child) for child in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not value(node.operand)
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.Eq)
        ):
            return value(node.left) == value(node.comparators[0])
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "contains"
            and len(node.args) == 2
        ):
            return value(node.args[1]) in value(node.args[0])
        raise AssertionError("Unsupported workflow condition node: " + ast.dump(node))

    return value(ast.parse(expression, mode="eval").body)


class NativeDetailWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.jobs = jobs()
        cls.native = cls.jobs["detail-native"]

    def test_owner_intent_starts_only_the_bounded_native_job(self):
        active = [name for name, job in self.jobs.items() if enabled(job)]
        self.assertEqual(active, ["detail-native"])
        self.assertIn("runs-on: [self-hosted, yacs-ue58]", self.native)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_wrong_actor_repository_branch_or_event_cannot_start_native_detail(self):
        variants = {
            "github.actor": "contributor",
            "github.repository": "contributor/YetAnotherCyclingSim",
            "github.ref": "refs/heads/main",
            "github.event_name": "workflow_dispatch",
        }
        for key, bad in variants.items():
            with self.subTest(context=key):
                self.assertFalse(enabled(self.native, **{key: bad}))
        self.assertFalse(enabled(self.native, message="ordinary maintenance"))

    def test_mixed_native_intents_fail_closed_without_starting_full_work(self):
        for marker in MARKERS:
            with self.subTest(marker=marker):
                active = [
                    name
                    for name, job in self.jobs.items()
                    if enabled(job, message="[detail-native] " + marker)
                ]
                self.assertEqual(active, [])

    def test_existing_single_marker_lanes_keep_their_meaning(self):
        expected = {
            "[wholemap-material]": "wholemap-material",
            "[shoulder-contact]": "wholemap-material",
            "[material-closeout]": "wholemap-material",
            "[detail-pilot]": "detail-pilot",
            "[tpp-survey]": "bidirectional-survey",
            "[tpp-retain]": "retain-bidirectional-survey",
            "[tpp-docs]": "publish-survey-docs",
        }
        for marker, wanted in expected.items():
            with self.subTest(marker=marker):
                self.assertEqual(
                    [
                        name
                        for name, job in self.jobs.items()
                        if enabled(job, message=marker)
                    ],
                    [wanted],
                )

    def test_source_and_cheap_contracts_precede_build_and_single_editor_capture(self):
        ordered = (
            "Verify owner intent, exact revision and idle host",
            "Validate and copy only fixed retained source files",
            "Test fixed selection and prepare the bounded patch",
            "Materialize the unchanged accepted scene and limestone dependencies",
            "Verify installed exact-version detail API source",
            "Build exact native detail head and run scoped Automation once",
            "Capture only the two annotated cameras on native v8",
            "Verify ten primary frames, visibility and trial restoration",
            "Verify retained source and checkout are unchanged",
            "Upload compact native detail frames and proof receipts",
        )
        offsets = [self.native.index(item) for item in ordered]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(self.native.count("./scripts/ci/Invoke-YacsUnrealCi.ps1 "), 1)
        self.assertEqual(
            self.native.count("Start-Process -FilePath $engine.UnrealEditorPath"), 1
        )
        self.assertNotIn("-SkipBuild", self.native)
        self.assertNotIn("Invoke-YacsSaCalobraPcgExCliff.ps1", self.native)
        self.assertNotIn("YACS_SA_CALOBRA_TPP_SURVEY = '1'", self.native)
        self.assertIn("-ExpectedBranch 'HEAD'", self.native)
        self.assertIn(
            "CyclingSession+CyclingPhysics+CyclingInput+YACS.DetailNative", self.native
        )
        self.assertIn("$detailTests.Count -eq 0", self.native)
        self.assertIn("ref: " + "$" + "{{ github.sha }}", self.native)

    def test_fixed_capture_binding_and_readonly_checkout_are_required(self):
        for value in (
            "b1ea05b33b9f3208e7aeb6884f1a67792d9c6121/37800814004-1",
            "9ed6c9179d2df04117fcc8992224061f942d42a03a714a4a75177c43728b1cd5",
            "c9494905cbb51f5622e3a414c862eb86d21a261063d6b5adc357ee74ac2a2742",
            "41768c7680ddea2304f9968d4b2947bf65e1164ffacfa45f74dcefad955b5359",
            "6ec02a0e3dac9756923d29c8b603c0c1d79db411d06f3a20bb30956e11390953",
            "804842ef0893df0d4822caa458ca68b658bf6d9481ef64db5237dde00ec97718",
            "LOCAL_RETAINED",
            "verify_native(",
            "source_preserved",
            "destination_verified",
            "YACS_WORKSPACE_CONFIG",
            "git status --porcelain=v1 --untracked-files=no",
        ):
            with self.subTest(binding=value):
                self.assertIn(value, self.native)
        self.assertNotIn("persist-credentials: true", self.native)
        self.assertNotIn("contents: write", self.native)
        self.assertNotIn("git push", self.native)
        self.assertNotIn("prepare_sa_calobra_detail_pilot.py --mesh", self.native)
        self.assertIn("selection_recomputed=False", self.native)
        self.assertIn("output.write_bytes(data)", self.native)

    def test_upload_omits_original_archive_known_input_meshes_and_priming(self):
        upload = self.native.split(
            "Upload compact native detail frames and proof receipts", 1
        )[1]
        self.assertIn("/capture/detail-native/frames/", upload)
        self.assertIn("/input/treatment/", upload)
        self.assertIn("/source-input-verification.json", upload)
        self.assertIn("/checkout-restoration.json", upload)
        self.assertIn("retention-days: 90", upload)
        for omitted in (
            ".zip",
            "/source/",
            "/source-reference/",
            "/priming/",
            "/input/\n",
        ):
            with self.subTest(path=omitted):
                self.assertNotIn(omitted, upload)

    def test_parent_success_alone_cannot_admit_detail_evidence(self):
        verification = self.native.split(
            "Verify ten primary frames, visibility and trial restoration", 1
        )[1]
        for condition in (
            "DETAIL_NATIVE_CAPTURE_PASS",
            "DETAIL_NATIVE_SOURCE_VERIFIED",
            'report.get("cleanup", {}).get("status") == "RESTORED"',
            'trial.get("visibility_before_trial") == "VISIBLE_IN_CAPTURED_SCENE"',
            'visibility.get("min_required_pixels") == 8',
            "len(captures) == 10",
            "Native frame hash mismatch",
            "Native camera drifted from its captured pose",
            'rendered_inputs = verify_rendered_inputs(Path(os.environ["YACS_DETAIL_NATIVE"]), report)',
        ):
            with self.subTest(gate=condition):
                self.assertIn(condition, verification)

    def test_embedded_python_is_parseable(self):
        scripts = re.findall(
            r"          \$(\w+) = @'\n(.*?)\n          '@",
            self.native,
            flags=re.DOTALL,
        )
        self.assertTrue(scripts)
        for name, source in scripts:
            with self.subTest(script=name):
                compile(textwrap.dedent(source), "workflow:" + name, "exec")

    @unittest.skipUnless(
        shutil.which("pwsh"), "PowerShell 7 required; executed by hosted and native CI"
    )
    def test_embedded_powershell_is_parseable(self):
        scripts = re.findall(
            r"        run: \|\n(.*?)(?=\n      - name:|\Z)",
            self.native,
            flags=re.DOTALL,
        )
        self.assertTrue(scripts)
        parse_powershell_scripts([textwrap.dedent(source) for source in scripts])


class RenderedInputBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native = jobs()["detail-native"]
        source = re.search(
            r"          \$verify = @'\n(.*?)\n          '@", native, flags=re.DOTALL
        ).group(1)
        tree = ast.parse(textwrap.dedent(source))
        helpers = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in ("require", "verify_rendered_inputs")
        ]
        if len(helpers) != 2:
            raise AssertionError(
                "Native workflow must expose its actual input verifier"
            )
        scope = {"hashlib": hashlib, "json": json, "math": math, "no_link": no_link}
        exec(
            compile(
                ast.Module(body=helpers, type_ignores=[]), "workflow:verify", "exec"
            ),
            scope,
        )
        cls.verify = staticmethod(scope["verify_rendered_inputs"])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.bundle = Path(temp.name)
        self.paths = {
            "source": self.bundle / "source/combined-mesh.json",
            "mask": self.bundle / "pilot/triangle-bands.json",
            "pilot": self.bundle / "pilot/manifest.json",
            "trial": self.bundle / "treatment/treatment-mesh.json",
            "manifest": self.bundle / "treatment/treatment-manifest.json",
        }
        for name, path in self.paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(json.dumps({"fixture": name}).encode("utf-8"))
        hashes = {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in self.paths.items()
        }
        self.manifest = {
            "status": "BOUNDED_DETAIL_TRIAL_PREPARED",
            "source_mesh_sha256": hashes["source"],
            "mask_sha256": hashes["mask"],
            "trial_mesh_sha256": hashes["trial"],
            "trial_mesh_path": "treatment-mesh.json",
            "vertex_count": 12,
            "triangle_count": 8,
            "protected_face_count": 2,
            "selected_face_count": 2,
            "changed_vertex_count": 1,
            "selected_face_indices": [3, 4],
            "changed_vertex_ids": [6],
            "max_added_displacement_cm": 0.5,
            "max_total_source_displacement_cm": 50.00000000000475,
            "bounds": {
                "max_added_displacement_cm": 5.0,
                "max_total_source_displacement_cm": 50.0,
                "floating_point_tolerance_cm": 0.000001,
            },
        }
        self.report = {
            "inputs_sha256": hashes,
            "native_source": {
                "source_mesh_sha256": hashes["source"],
                "vertex_count": 12.0,
                "triangle_count": 8.0,
                "protected_face_count": 2.0,
                "selected_face_count": 2.0,
                "changed_vertex_count": 1.0,
                "max_additional_displacement_cm": 0.5,
                "max_source_displacement_cm": 50.0,
            },
        }
        self.write_manifest(self.manifest, self.report)

    def write_manifest(self, manifest, report):
        data = json.dumps(manifest).encode("utf-8")
        self.paths["manifest"].write_bytes(data)
        report["inputs_sha256"]["manifest"] = hashlib.sha256(data).hexdigest()

    def test_actual_inputs_and_numeric_native_counts_are_accepted(self):
        result = self.verify(self.bundle, self.report)
        self.assertEqual(result["inputs_sha256"], self.report["inputs_sha256"])
        self.assertEqual(result["selected_face_count"], 2)
        self.assertEqual(result["changed_vertex_count"], 1)
        self.assertEqual(result["max_total_source_displacement_cm"], 50.00000000000475)

    def test_every_input_mutation_after_capture_is_rejected(self):
        for name, path in self.paths.items():
            original = path.read_bytes()
            with self.subTest(input=name):
                try:
                    path.write_bytes(original + b"\n")
                    with self.assertRaisesRegex(ValueError, "Rendered input hash"):
                        self.verify(self.bundle, self.report)
                finally:
                    path.write_bytes(original)

    def test_receipt_input_inventory_must_match_all_five_files(self):
        for change in ("missing", "extra"):
            report = copy.deepcopy(self.report)
            with self.subTest(change=change):
                if change == "missing":
                    report["inputs_sha256"].pop("trial")
                else:
                    report["inputs_sha256"]["extra"] = "0" * 64
                with self.assertRaisesRegex(ValueError, "Rendered input hash"):
                    self.verify(self.bundle, report)

    def test_rehashed_manifest_cannot_claim_different_payloads(self):
        for key in ("source_mesh_sha256", "mask_sha256", "trial_mesh_sha256"):
            with self.subTest(binding=key):
                manifest, report = (
                    copy.deepcopy(self.manifest),
                    copy.deepcopy(self.report),
                )
                manifest[key] = "0" * 64
                self.write_manifest(manifest, report)
                with self.assertRaisesRegex(ValueError, "manifest payload binding"):
                    self.verify(self.bundle, report)

    def test_native_counts_and_source_must_match_uploaded_manifest(self):
        for key in (
            "vertex_count",
            "triangle_count",
            "protected_face_count",
            "selected_face_count",
            "changed_vertex_count",
            "source_mesh_sha256",
        ):
            with self.subTest(field=key):
                report = copy.deepcopy(self.report)
                actual = report["native_source"][key]
                report["native_source"][key] = (
                    "0" * 64 if key == "source_mesh_sha256" else actual + 1
                )
                with self.assertRaisesRegex(
                    ValueError, "counts disagree|rendered source bytes"
                ):
                    self.verify(self.bundle, report)

    def test_identity_lists_cannot_drift_with_unchanged_counts(self):
        cases = (
            ("selected_face_indices", [3, 3]),
            ("selected_face_indices", [3, 8]),
            ("selected_face_indices", [3]),
            ("changed_vertex_ids", [True]),
            ("changed_vertex_ids", [12]),
        )
        for key, values in cases:
            with self.subTest(field=key, values=values):
                manifest, report = (
                    copy.deepcopy(self.manifest),
                    copy.deepcopy(self.report),
                )
                manifest[key] = values
                self.write_manifest(manifest, report)
                with self.assertRaisesRegex(ValueError, "identity count or range"):
                    self.verify(self.bundle, report)

    def test_displacement_comparison_keeps_fixed_cm_tolerance(self):
        # The tolerance is 1e-6 centimetres; real v8 floating-point noise at 50 cm passes.
        report = copy.deepcopy(self.report)
        report["native_source"]["max_additional_displacement_cm"] += 0.0000005
        self.verify(self.bundle, report)
        for key in ("max_additional_displacement_cm", "max_source_displacement_cm"):
            for bad in (
                True,
                None,
                math.nan,
                math.inf,
                -1,
                0.500002 if "additional" in key else 49.999998,
            ):
                with self.subTest(field=key, value=bad):
                    report = copy.deepcopy(self.report)
                    report["native_source"][key] = bad
                    with self.assertRaisesRegex(ValueError, "displacement evidence"):
                        self.verify(self.bundle, report)

    def test_agreement_cannot_relax_either_global_displacement_ceiling(self):
        cases = (
            ("max_additional_displacement_cm", "max_added_displacement_cm", 5.000002),
            (
                "max_source_displacement_cm",
                "max_total_source_displacement_cm",
                50.000002,
            ),
        )
        for native_key, manifest_key, value in cases:
            with self.subTest(metric=native_key):
                manifest, report = (
                    copy.deepcopy(self.manifest),
                    copy.deepcopy(self.report),
                )
                manifest[manifest_key] = value
                report["native_source"][native_key] = value
                self.write_manifest(manifest, report)
                with self.assertRaisesRegex(ValueError, "displacement evidence"):
                    self.verify(self.bundle, report)
        for key in self.manifest["bounds"]:
            with self.subTest(bound=key):
                manifest, report = (
                    copy.deepcopy(self.manifest),
                    copy.deepcopy(self.report),
                )
                manifest["bounds"][key] *= 2
                self.write_manifest(manifest, report)
                with self.assertRaisesRegex(ValueError, "bounds changed"):
                    self.verify(self.bundle, report)


if __name__ == "__main__":
    unittest.main()
