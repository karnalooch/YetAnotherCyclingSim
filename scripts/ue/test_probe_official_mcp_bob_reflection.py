"""Offline trust-boundary tests; these do not mock or claim Unreal execution."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("probe_official_mcp_bob_reflection.py")
REPOSITORY = SCRIPT.parents[2]
SPEC = importlib.util.spec_from_file_location("bob_reflection_probe", SCRIPT)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class NativePythonSettingsAdmissionTests(unittest.TestCase):
    """Admission rules only; actual load_class/CDO binding requires the Editor."""

    def test_only_fixed_native_class_and_false_boolean_are_admitted(self):
        PROBE._validate_python_remote_execution(PROBE.PYTHON_SETTINGS_CLASS, False)

    def test_foreign_or_missing_class_cannot_supply_disabled_settings(self):
        for class_path in (None, "", "/Script/UnrealEd.EditorPerformanceSettings"):
            with self.subTest(class_path=class_path):
                with self.assertRaisesRegex(RuntimeError, "unexpected Python settings class"):
                    PROBE._validate_python_remote_execution(class_path, False)

    def test_unknown_enabled_or_false_like_values_are_rejected(self):
        for remote_execution in (None, True, 0, "False"):
            with self.subTest(remote_execution=remote_execution):
                with self.assertRaisesRegex(RuntimeError, "remote execution disabled"):
                    PROBE._validate_python_remote_execution(PROBE.PYTHON_SETTINGS_CLASS, remote_execution)


class NativeReflectionContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="yacs-reflection-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repository = self.root / "repo"
        self.script = self.repository / "scripts/ue" / PROBE.SCRIPT_NAME
        self.script.parent.mkdir(parents=True)
        self.script.write_bytes(SCRIPT.read_bytes())
        self.host = self.root / "work/HostProject"
        self.plugin = self.host / "Plugins/YacsBobInspection"
        self.header = self.plugin / "Source/YacsBobInspection/Public/YacsBobLandscapeHit.h"
        self.header.parent.mkdir(parents=True)
        self.header.write_bytes((REPOSITORY / "Plugins/YacsBobInspection/Source/YacsBobInspection/Public/YacsBobLandscapeHit.h").read_bytes())
        self.plugin_descriptor = self.plugin / "YacsBobInspection.uplugin"
        self.plugin_descriptor.write_bytes((REPOSITORY / "Plugins/YacsBobInspection/YacsBobInspection.uplugin").read_bytes())
        self.project_descriptor = self.host / "HostProject.uproject"
        self.project = {
            "FileVersion": 3,
            "Plugins": [
                {"Name": "YacsBobInspection", "Enabled": True},
                {"Name": "PythonScriptPlugin", "Enabled": True},
                {"Name": "ModelContextProtocol", "Enabled": False},
            ],
        }
        self.project_descriptor.write_text(json.dumps(self.project), encoding="utf-8")
        self.engine_config = self.host / "Config/DefaultEngine.ini"
        self.engine_config.parent.mkdir()
        self.engine_config.write_text(
            "[/Script/PythonScriptPlugin.PythonScriptPluginSettings]\nbRemoteExecution=False\n",
            encoding="utf-8",
        )
        self.artifacts = self.repository / "Saved/RuntimeProof/OfficialMcpNativeProbe/12345-1"
        self.artifacts.mkdir(parents=True)
        self.exact_sha = "a" * 40
        self.marker_path = self.host / PROBE.MARKER_NAME
        self.marker = {
            "schema_version": 1, "exact_sha": self.exact_sha,
            "host_project_root": str(self.host), "artifact_root": str(self.artifacts),
            "script_sha256": self.digest(self.script),
            "public_header_sha256": self.digest(self.header),
            "plugin_descriptor_sha256": self.digest(self.plugin_descriptor),
            "host_project_descriptor_sha256": self.digest(self.project_descriptor),
            "host_engine_config_sha256": self.digest(self.engine_config),
        }
        self.write_marker()
        self.environment = {
            "YACS_MCP_NATIVE_HOST_PROJECT_ROOT": str(self.host),
            "YACS_MCP_NATIVE_ARTIFACT_ROOT": str(self.artifacts),
            "YACS_MCP_NATIVE_EXPECTED_HEAD": self.exact_sha,
        }

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_marker(self):
        self.marker_path.write_text(json.dumps(self.marker), encoding="utf-8")

    def refresh_project(self):
        self.project_descriptor.write_text(json.dumps(self.project), encoding="utf-8")
        self.marker["host_project_descriptor_sha256"] = self.digest(self.project_descriptor)
        self.write_marker()

    def context(self):
        return PROBE._load_context(self.script, self.environment)

    def test_exact_private_context_binds_real_sources_without_unreal(self):
        context = self.context()
        self.assertEqual(context["exact_sha"], self.exact_sha)
        self.assertEqual(context["host"], self.host)
        self.assertEqual(context["receipt"], self.artifacts / PROBE.RECEIPT_NAME)
        self.assertFalse(context["module_metadata"]["ai_callable"])
        self.assertEqual(context["module_metadata"]["evidence_kind"], "hashed_public_source_declarations")
        PROBE._unchanged(context)

    def test_missing_launcher_context_is_rejected_before_receipt_write(self):
        del self.environment["YACS_MCP_NATIVE_EXPECTED_HEAD"]
        with self.assertRaisesRegex(RuntimeError, "missing trusted"):
            self.context()
        self.assertFalse((self.artifacts / PROBE.RECEIPT_NAME).exists())

    def test_live_project_root_cannot_be_used_as_hostproject(self):
        live = self.root / "project"
        live.mkdir()
        self.environment["YACS_MCP_NATIVE_HOST_PROJECT_ROOT"] = str(live)
        with self.assertRaisesRegex(RuntimeError, "isolated BuildPlugin HostProject"):
            self.context()

    def test_marker_cannot_select_another_operation(self):
        self.marker["method"] = "RunTests"
        self.write_marker()
        with self.assertRaisesRegex(RuntimeError, "fixed contract"):
            self.context()

    def test_marker_revision_must_match_trusted_exact_sha(self):
        self.marker["exact_sha"] = "b" * 40
        self.write_marker()
        with self.assertRaisesRegex(RuntimeError, "disagrees"):
            self.context()

    def test_stale_compiled_header_is_rejected(self):
        self.header.write_text(self.header.read_text() + "\n// changed after compile\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "differs from its trusted marker"):
            self.context()

    def test_startup_config_rewrite_is_identified_and_rejected_before_receipt(self):
        expected = self.marker["host_engine_config_sha256"]
        changed = self.engine_config.read_bytes() + b"\n[StartupGenerated]\nValue=True\n"
        self.engine_config.write_bytes(changed)
        observed = self.digest(self.engine_config)
        with self.assertRaises(RuntimeError) as failure:
            self.context()
        self.assertEqual(str(failure.exception),
                         "Reflection proof source differs from its trusted marker: "
                         f"field=host_engine_config_sha256, expected_sha256={expected}, observed_sha256={observed}")
        self.assertEqual(self.engine_config.read_bytes(), changed)
        self.assertEqual(json.loads(self.marker_path.read_text())["host_engine_config_sha256"], expected)
        self.assertFalse((self.artifacts / PROBE.RECEIPT_NAME).exists())

    def test_ai_callable_metadata_is_rejected_even_if_hash_matches(self):
        self.header.write_text(self.header.read_text().replace(
            'UFUNCTION(BlueprintCallable, Category="YACS BOB Inspection")',
            'UFUNCTION(BlueprintCallable, Category="YACS BOB Inspection", meta=(AICallable))',
            1,
        ), encoding="utf-8")
        self.marker["public_header_sha256"] = self.digest(self.header)
        self.write_marker()
        with self.assertRaisesRegex(RuntimeError, "non-AICallable"):
            self.context()

    def test_official_mcp_cannot_be_enabled_by_reflection_fixture(self):
        self.project["Plugins"][2]["Enabled"] = True
        self.refresh_project()
        with self.assertRaisesRegex(RuntimeError, "fixed generated-project dependencies"):
            self.context()

    def test_bare_project_does_not_globally_disable_engine_plugins(self):
        self.project["DisableEnginePluginsByDefault"] = True
        self.refresh_project()
        with self.assertRaisesRegex(RuntimeError, "minimal bare HostProject"):
            self.context()

    def test_receipt_is_exclusive_and_cannot_overwrite_prior_evidence(self):
        context = self.context()
        receipt = {"status": "OFFLINE_STORAGE_TEST", "reflection_verified": False,
                   **dict.fromkeys(PROBE.FALSE_CLAIMS, False)}
        PROBE._write_receipt(context, receipt)
        with self.assertRaises(FileExistsError):
            PROBE._write_receipt(context, receipt)
        self.assertEqual(json.loads(context["receipt"].read_text()), receipt)

    def test_artifact_root_cannot_escape_fixed_ignored_run_directory(self):
        other = self.root / "other-evidence"
        other.mkdir()
        self.environment["YACS_MCP_NATIVE_ARTIFACT_ROOT"] = str(other)
        with self.assertRaisesRegex(RuntimeError, "fixed ignored artifact root"):
            self.context()

    def test_source_and_startup_config_drift_are_rejected_after_bind(self):
        context = self.context()
        self.engine_config.write_text("bRemoteExecution=True\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "source changed during execution"):
            PROBE._unchanged(context)

    def test_reparse_output_destination_is_rejected(self):
        context = self.context()
        target = self.root / "unrelated.json"
        target.write_text("preserve", encoding="utf-8")
        context["receipt"].symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, "symlink or junction"):
            PROBE._write_receipt(context, {"reflection_verified": False})
        self.assertEqual(target.read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
