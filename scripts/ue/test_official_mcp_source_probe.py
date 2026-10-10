"""Meaningful filesystem-only source-probe boundary tests; no Unreal required."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.ue import official_mcp_source_probe as probe


SHA = "a" * 40


class OfficialMcpSourceProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repository"
        self.engine = self.root / "engine"
        self.repo.mkdir()
        self.engine.mkdir()
        self.project = self.repo / "YetAnotherCyclingSim.uproject"
        self.project.write_text(json.dumps({"EngineAssociation": "5.8", "Plugins": []}))
        self.write("Engine/Build/Build.version", json.dumps({
            "MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 2, "Changelist": 56702186,
        }))
        for name, relative in probe.PLUGIN_ROOTS.items():
            self.plugin(name, relative)
        self.plugin("AutomationTestToolset", "Engine/Plugins/Experimental/Toolsets/AutomationTestToolset")
        # Deliberately use an unfamiliar plugin name: discover generic stock
        # modules by filenames, without assuming a documentation layout.
        self.plugin("DifferentEditorTools", "Engine/Plugins/Experimental/Toolsets/DifferentEditorTools")
        self.write("Engine/Plugins/Experimental/ModelContextProtocol/Source/Mcp.h",
                   "void StartServer();\nvoid RefreshTools();\n")
        self.write("Engine/Plugins/Experimental/ToolsetRegistry/Source/ToolsetRegistrySubsystem.h",
                   "class UToolsetRegistrySettings {\nTArray AllowedNames;\nTArray BlockedNames;\n};\n")
        self.write("Engine/Plugins/Experimental/ToolsetRegistry/Source/Toolset.h",
                   "void SetNameFilters();\nbool ExecuteTool();\n")
        self.write("Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/Source/AutomationTestToolset.h",
                   "void DiscoverTests();\nvoid ListTests();\nvoid RunTests();\nvoid GetTestResults();\n")
        for name in ("scene", "actor", "object"):
            self.write(f"Engine/Plugins/Experimental/Toolsets/DifferentEditorTools/Content/Python/{name}.py",
                       f"class {name.title()}Tools:\n    pass\n")

    def write(self, relative, text):
        path = self.engine / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def plugin(self, name, relative):
        return self.write(f"{relative}/{name}.uplugin", json.dumps({
            "Version": 7, "VersionName": "fixture-only", "EnabledByDefault": False,
            "Modules": [{"Name": name}],
        }))

    def collect(self, **overrides):
        kwargs = dict(engine_root=self.engine, project=self.project, repository_root=self.repo,
                      expected_sha=SHA, actual_sha=SHA)
        kwargs.update(overrides)
        return probe.collect(**kwargs)

    def test_inventory_pins_actual_bytes_and_versions_without_admission(self):
        before = {path: path.read_bytes() for path in self.engine.rglob("*") if path.is_file()}
        result = self.collect()
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertEqual(result["plugins"]["DifferentEditorTools"]["version_name"], "fixture-only")
        for item in result["inventory"]:
            raw = (self.engine / item["path"]).read_bytes()
            self.assertEqual(item["sha256"], hashlib.sha256(raw).hexdigest())
        for key in ("guard_parity_verified", "runtime_schema_verified", "official_mcp_admitted",
                    "mcp_server_started", "plugin_activation_performed", "performance_pass"):
            self.assertIs(result[key], False)
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_version_and_repository_mismatches_block_before_plugin_scan(self):
        result = self.collect(actual_sha="b" * 40)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("REPOSITORY_SHA_MISMATCH", result["blockers"])
        self.write("Engine/Build/Build.version", json.dumps({
            "MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 3, "Changelist": 56702186,
        }))
        result = self.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["source_file_count"], 1)
        self.assertTrue(any("ENGINE_VERSION_MISMATCH" in item for item in result["blockers"]))

    def test_different_symbol_names_require_review_without_invented_api_blocker(self):
        self.write("Engine/Plugins/Experimental/ModelContextProtocol/Source/Mcp.h",
                   "void DifferentStart();\nvoid DifferentRefresh();\n")
        result = self.collect()
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertFalse(result["candidate_symbol_observations"]["ModelContextProtocol"]["StartServer"])
        self.assertEqual(result["semantic_mapping_status"], "PRIMARY_SOURCE_REVIEW_REQUIRED")

    def test_missing_required_plugin_and_empty_sources_are_blocked(self):
        path = self.engine / "Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/AutomationTestToolset.uplugin"
        path.unlink()
        result = self.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("MISSING_PLUGIN_DESCRIPTOR: AutomationTestToolset", result["blockers"])
        (self.engine / "Engine/Plugins/Experimental/ModelContextProtocol/Source/Mcp.h").unlink()
        self.assertIn("MISSING_PLUGIN_SOURCES: ModelContextProtocol", self.collect()["blockers"])

    def test_source_link_escape_and_oversized_source_fail_closed(self):
        external = self.root / "outside.h"
        external.write_text("outside source must not be inspected")
        source = self.engine / "Engine/Plugins/Experimental/ModelContextProtocol/Source/escape.h"
        source.symlink_to(external)
        result = self.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("LINK_OR_REPARSE_POINT" in item for item in result["blockers"]))
        source.unlink()
        source.write_bytes(b"x" * (probe.MAX_FILE_BYTES + 1))
        result = self.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("OVERSIZED_FILE" in item for item in result["blockers"]))

    def test_ancestor_link_blocks_before_descriptor_tree_traversal(self):
        toolsets = self.engine / "Engine/Plugins/Experimental/Toolsets"
        renamed = self.engine / "Engine/Plugins/Experimental/OriginalToolsets"
        toolsets.rename(renamed)
        toolsets.symlink_to(renamed, target_is_directory=True)
        result = self.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("LINK_OR_REPARSE_POINT" in item for item in result["blockers"]))
        self.assertEqual(result["source_file_count"], 1)

    def test_entry_limit_caps_enumeration_before_sorting(self):
        tree = self.root / "many-files"
        tree.mkdir()
        for index in range(5):
            (tree / f"{index}.txt").write_text("fixture")
        with patch.object(probe, "MAX_ENTRIES", 3):
            with self.assertRaisesRegex(probe.ProbeBlocked, "ENTRY_LIMIT"):
                probe.bounded_files(tree)

    def test_total_byte_limit_stops_before_opening_later_plugin_files(self):
        build = self.engine / "Engine/Build/Build.version"
        descriptor = self.engine / "Engine/Plugins/Experimental/ToolsetRegistry/ToolsetRegistry.uplugin"
        limit = build.stat().st_size + descriptor.stat().st_size - 1
        with patch.object(probe, "MAX_TOTAL_BYTES", limit), patch.object(
            probe, "read_bounded", wraps=probe.read_bounded,
        ) as reads:
            result = self.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("SOURCE_TOTAL_BYTE_LIMIT", result["blockers"])
        self.assertEqual(result["source_file_count"], 1)
        self.assertEqual([call.args[1] for call in reads.call_args_list], [self.project, build])
        with patch.object(probe, "MAX_SOURCE_FILES", 1):
            count_limited = self.collect()
        self.assertEqual(count_limited["source_file_count"], 1)
        self.assertIn("SOURCE_FILE_COUNT_LIMIT", count_limited["blockers"])

    def test_outputs_are_exclusive_and_cannot_escape_saved(self):
        result = self.collect()
        saved = self.repo / "Saved"
        target = probe.write_receipt(result, repository_root=self.repo, artifact_root=saved / "probe")
        self.assertEqual(json.loads(target.read_text())["exact_sha"], SHA)
        original = target.read_bytes()
        with self.assertRaises(FileExistsError):
            probe.write_receipt(result, repository_root=self.repo, artifact_root=saved / "probe")
        self.assertEqual(original, target.read_bytes())
        for bad in (self.repo / "Content", saved / "new/../../escape"):
            with self.assertRaises(probe.ProbeBlocked):
                probe.write_receipt(result, repository_root=self.repo, artifact_root=bad)
        external = self.root / "outside-output"
        external.mkdir()
        (saved / "linked").symlink_to(external, target_is_directory=True)
        with self.assertRaises(probe.ProbeBlocked):
            probe.write_receipt(result, repository_root=self.repo, artifact_root=saved / "linked/probe")
        self.assertEqual(list(external.iterdir()), [])

    def test_wrong_running_engine_is_explicit_blocker_and_not_plugin_proof(self):
        result = self.collect(host_context={"active_engine_matches_resolver": False, "processes": [{}]})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("RUNNING_EDITOR_ENGINE_MISMATCH_OR_UNVERIFIED_PATH", result["blockers"])
        self.assertFalse(result["runtime_schema_verified"])

    def test_alternate_project_and_malformed_descriptor_are_explicit_blockers(self):
        alternate = self.repo / "alternate.uproject"
        alternate.write_bytes(self.project.read_bytes())
        result = self.collect(project=alternate)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("PROJECT_MUST_BE_CANONICAL_REPOSITORY_DESCRIPTOR", result["blockers"])
        for invalid in ([], {"EngineAssociation": "5.8", "Plugins": ["invalid"]}):
            self.project.write_text(json.dumps(invalid))
            result = self.collect()
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(any("INVALID_PROJECT" in item for item in result["blockers"]))
        self.project.write_text(json.dumps({"EngineAssociation": "5.8", "Plugins": []}))
        plugin = self.engine / "Engine/Plugins/Experimental/ModelContextProtocol/ModelContextProtocol.uplugin"
        plugin.write_text(json.dumps({"Modules": ["invalid"]}))
        result = self.collect()
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("INVALID_PLUGIN_MODULE_DESCRIPTOR" in item for item in result["blockers"]))

    def test_excerpt_budget_and_console_output_are_bounded(self):
        content = "\n".join(f"class Fixture{index};" for index in range(1000))
        excerpts, used = probe.selected_excerpts(content.encode(), 17)
        self.assertLessEqual(used, 17)
        self.assertTrue(excerpts)
        result = self.collect()
        self.assertLessEqual(len(probe.console_summary(result).splitlines()), probe.MAX_CONSOLE_LINES)

    def test_shipped_tests_cannot_consume_stock_definition_excerpt_budget(self):
        plugin = "Engine/Plugins/Experimental/Toolsets/DifferentEditorTools/Content/Python"
        noise = "\n".join(f"def test_case_{index}():\n    pass\n" for index in range(600))
        for name in ("scene", "actor", "object"):
            self.write(f"{plugin}/tests/test_{name}.py", noise)
            self.write(f"{plugin}/toolsets/{name}.py",
                       f"class {name.title()}Tools:\n    def inspect_{name}_identity():\n        return 'real-definition'\n")
        result = self.collect()
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        records = {item["path"]: item for item in result["inventory"]}
        for name in ("scene", "actor", "object"):
            actual = records[f"{plugin}/toolsets/{name}.py"]
            self.assertTrue(actual["selected_excerpts"])
            self.assertIn(f"inspect_{name}_identity", actual["selected_excerpts"][0]["text"])
        output = probe.console_summary(result)
        self.assertIn("real-definition", output)
        self.assertNotIn("test_case_", output)
        self.assertNotIn("/tests/test_", output)

    def test_console_identity_is_bounded_and_omits_process_command_lines(self):
        processes = [{
            "process_id": index, "name": "UnrealEditor.exe", "executable_path": "D:/engine/UnrealEditor.exe",
            "executable_sha256": "c" * 64, "executable_under_resolved_engine": True,
            "plugin_state_verified": False, "command_line": "SECRET_COMMAND_LINE_MUST_NEVER_PRINT",
        } for index in range(50)]
        result = self.collect(host_context={
            "status": "PROCESS_PATHS_OBSERVED", "active_engine_matches_resolver": True,
            "active_plugin_state_verified": False, "processes": processes,
        })
        for item in result["inventory"]:
            item["selected_excerpts"] = [{"start_line": 1, "end_line": 10000,
                                          "text": "\n".join("class SOURCE_EXCERPT;" for _ in range(10000))}]
        output = probe.console_summary(result)
        lines = output.splitlines()
        self.assertLessEqual(len(lines), probe.MAX_CONSOLE_LINES)
        self.assertNotIn("SECRET_COMMAND_LINE", output)
        engine = json.loads(next(line.removeprefix("ENGINE_IDENTITY ") for line in lines if line.startswith("ENGINE_IDENTITY ")))
        self.assertEqual(engine["Changelist"], 56702186)
        self.assertEqual(engine["root"], str(self.engine))
        host = json.loads(next(line.removeprefix("RUNNING_EDITOR_OBSERVATION ") for line in lines if line.startswith("RUNNING_EDITOR_OBSERVATION ")))
        self.assertEqual(host["observed_process_count"], 50)
        self.assertEqual(len(host["processes"]), 8)
        self.assertTrue(host["process_list_truncated"])
        self.assertFalse(host["active_plugin_state_verified"])
        self.assertIn('"version_name": "fixture-only"', output)

    def test_registry_filter_header_and_python_adapter_survive_large_other_sources(self):
        registry = "Engine/Plugins/Experimental/ToolsetRegistry"
        noise = "\n".join(f"class LongFixture{index};\nvoid ExecuteTool();\n" for index in range(500))
        for name in ("ToolsetRegistrySubsystem.cpp", "Toolset.cpp", "ToolsetRegistry.cpp"):
            self.write(f"{registry}/Source/{name}", noise)
        self.write(f"{registry}/Content/Python/toolset_registry/__init__.py",
                   "def tool_call(function):\n    return function\n")
        result = self.collect()
        actual = {Path(item["path"]).name: item for item in result["inventory"]}
        for name in ("ToolsetRegistrySubsystem.h", "Toolset.h", "__init__.py"):
            self.assertTrue(actual[name]["selected_excerpts"], name)
        console = probe.console_summary(result)
        self.assertIn("SetNameFilters", console)
        self.assertIn("def tool_call(function)", console)
        self.assertLessEqual(len(console.splitlines()), 500)

    def test_native_tests_modules_are_excluded_from_console_case_insensitively(self):
        root = "Engine/Plugins/Experimental/ModelContextProtocol/Source"
        for module in ("ModelContextProtocolEditorTests", "MODELContextProtocolEngineTESTS"):
            for name in ("ModelContextProtocolEditorTestsModule.cpp", "MockToolset.h"):
                path = self.write(f"{root}/{module}/Private/{name}",
                                  "class SHIPPED_TEST_MODULE_MUST_NOT_PRINT;\nvoid ExecuteTool();\n")
                self.assertEqual(probe.source_priority(path, "ModelContextProtocol")[0], 100)
        self.assertEqual(probe.source_priority(Path("TEST_case.py"), "EditorToolset")[0], 100)
        self.assertEqual(probe.source_priority(Path("test.py"), "EditorToolset")[0], 100)
        result = self.collect()
        self.assertTrue(any("EditorTests" in item["path"] for item in result["inventory"]))
        output = probe.console_summary(result)
        self.assertNotIn("SHIPPED_TEST_MODULE", output)
        self.assertNotIn("TestsModule.cpp", output)
        self.assertLessEqual(len(output.splitlines()), 500)

    def test_semantic_bodies_and_all_three_python_signature_indexes_survive_noise(self):
        automation = "Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/Source"
        run_body = "\n".join(f"    int Step{index} = {index};" for index in range(50))
        self.write(f"{automation}/AutomationTestToolset.cpp",
                   "class UnrelatedPreamble {};\nUToolCallAsyncResultString* UAutomationTestToolset::RunTests(const TArray<FString>& TestNames)\n{\n"
                   + run_body + "\n    return NATIVE_RUN_TESTS_CONTROL_FLOW_TAIL;\n}\n"
                   + "void UnrelatedMutation() { MUST_NOT_PRINT_AFTER_RUN_BODY; }\n")
        registry = "Engine/Plugins/Experimental/ToolsetRegistry/Source"
        self.write(f"{registry}/Toolset.cpp",
                   "class UnrelatedPreamble {};\nvoid FToolset::SetNameFilters()\n{\n"
                   + run_body + "\n    FILTER_CONTROL_FLOW_TAIL;\n}\n")
        plugin = "Engine/Plugins/Experimental/Toolsets/DifferentEditorTools/Content/Python"
        for name in ("scene", "actor", "object"):
            self.write(f"{plugin}/{name}.py",
                       "class ActualTools:\n    def load_mutating_noise(self):\n        NEVER_EMIT_MUTATION_BODY\n"
                       f"    def get_{name}_identity(self, reference: str) -> str:\n        return '{name}_READ_BODY'\n"
                       + "\n".join(f"    def get_later_{index}(self):\n        return '{index}'" for index in range(35)))
        result = self.collect()
        output = probe.console_summary(result)
        self.assertIn("NATIVE_RUN_TESTS_CONTROL_FLOW_TAIL", output)
        self.assertIn("FILTER_CONTROL_FLOW_TAIL", output)
        self.assertNotIn("MUST_NOT_PRINT_AFTER_RUN_BODY", output)
        self.assertNotIn("NEVER_EMIT_MUTATION_BODY", output)
        records = {Path(item["path"]).name: item for item in result["inventory"]}
        for name in ("scene", "actor", "object"):
            self.assertIn(f"{name}_READ_BODY", output)
            index = records[f"{name}.py"]["python_declarations"]
            self.assertTrue(index["truncated"])
            self.assertEqual(len(index["definitions"]), 32)
            self.assertEqual(index["definitions"][1]["line"], 4)
        self.assertLessEqual(len(output.splitlines()), 500)

    def test_domain_extension_selects_actual_declarations_not_comments_or_literals(self):
        registry = "Engine/Plugins/Experimental/ToolsetRegistry/Source"
        # Unfamiliar filenames prove declaration discovery does not invent paths.
        self.write(f"{registry}/ActualLibrary.h",
                   "/* class UToolsetRegistry { void RegisterToolsetClass(); }; */\n"
                   'const char* Example = "class UToolsetRegistry {";\n'
                   "class UToolsetRegistry;\nclass UnrelatedForwardNoise {};\n"
                   "class FIXTURE_API UToolsetRegistry\n{\npublic:\n"
                   "    static void RegisterToolsetClass(UClass* Class);\n};\n"
                   "class FIXTURE_API FToolsetRegistry\n{\npublic:\n"
                   "    FIXTURE_API bool RegisterToolset(TSharedPtr<FToolset> Handler);\n"
                   "    FIXTURE_API bool UnregisterToolset(const FString& Name);\n};\n")
        self.write(f"{registry}/ActualHandler.cpp",
                   "// FActualReflectedHandler::ExecuteToolInternal() is a comment.\n"
                   "TFuture FActualReflectedHandler::ExecuteToolInternal(const FString& JsonInput)\n{\n"
                   "    if (JsonInput.HasUnknownFields()) { return ARGUMENT_REJECTION; }\n"
                   "    return FIXED_DOMAIN_CALL;\n}\n"
                   "void Unrelated() { UNRELATED_CODE_MUST_NOT_PRINT; }\n")
        automation = "Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/Source"
        self.write(f"{automation}/ActualAutomation.h",
                   "/* RunTests() workflow\n GetTestResults() workflow */\n"
                   'const char* Example = "RunTests() is not a declaration";\n'
                   "public:\nUFUNCTION(BlueprintCallable, meta=(AICallable))\n"
                   "FIXTURE_API static UToolCallAsyncResultString* RunTests(const TArray<FString>& TestNames);\n")
        result = self.collect(evidence_focus="domain_extension")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        observations = result["domain_extension_observations"]
        self.assertEqual(len(observations["class_registration"]), 1)
        self.assertEqual(observations["class_registration"][0]["line"], 5)
        actual_prototype = next(item for item in observations["automation_prototypes"]
                                if item["path"].endswith("ActualAutomation.h"))
        self.assertEqual(actual_prototype["line"], 6)
        self.assertEqual(observations["concrete_argument_conversion"][0]["line"], 2)
        output = probe.console_summary(result)
        self.assertIn("ARGUMENT_REJECTION", output)
        self.assertIn("FIXED_DOMAIN_CALL", output)
        self.assertNotIn("UNRELATED_CODE_MUST_NOT_PRINT", output)
        self.assertIn("FIXTURE_API static UToolCallAsyncResultString* RunTests", output)
        self.assertIn("ActualLibrary.h", output)
        self.assertIn("RegisterToolset(TSharedPtr<FToolset> Handler)", output)
        self.assertIn("UnregisterToolset(const FString& Name)", output)
        self.assertLessEqual(len(output.splitlines()), 500)
        for key in ("guard_parity_verified", "runtime_schema_verified", "official_mcp_admitted",
                    "mcp_server_started", "plugin_activation_performed", "performance_pass"):
            self.assertIs(result[key], False)

    def test_domain_extension_controller_reads_only_exact_observed_fixed_include(self):
        relative = probe.CONTROLLER_HEADERS["IAutomationControllerModule.h"]
        controller = self.write(relative, "class IAutomationControllerManager {\n"
                                "virtual int GetTestState() const = 0;\n};\n")
        unrelated = self.write("Engine/Source/Developer/AutomationController/Public/Secret.h", "NEVER_READ\n")
        automation = "Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/Source/Actual.cpp"
        self.write(automation, '// #include "IAutomationControllerModule.h"\n'
                   '#include "../../../Secret.h"\n')
        with patch.object(probe, "read_bounded", wraps=probe.read_bounded) as reads:
            missing = self.collect(evidence_focus="domain_extension")
        self.assertNotIn(controller, [call.args[1] for call in reads.call_args_list])
        self.assertIn("NO_APPROVED_NAMED_INCLUDE_OBSERVED", missing["automation_controller_unestablished"])
        self.write(automation, '#include "IAutomationControllerModule.h"\n')
        with patch.object(probe, "read_bounded", wraps=probe.read_bounded) as reads:
            result = self.collect(evidence_focus="domain_extension")
        paths = [call.args[1] for call in reads.call_args_list]
        self.assertIn(controller, paths)
        self.assertNotIn(unrelated, paths)
        self.assertEqual(result["automation_controller_unestablished"], [])
        self.assertTrue(result["domain_extension_observations"]["automation_controller"])
        self.assertIn("GetTestState", probe.console_summary(result))
        controller.unlink()
        controller.symlink_to(unrelated)
        result = self.collect(evidence_focus="domain_extension")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("LINK_OR_REPARSE_POINT" in error for error in result["blockers"]))

    def test_domain_extension_window_and_global_console_caps_remain_explicit(self):
        registry = "Engine/Plugins/Experimental/ToolsetRegistry/Source/Actual.cpp"
        self.write(registry, "void FStaticToolset::ExecuteToolInternal()\n{\n"
                   + "\n".join(f"    int Step{index} = {index};" for index in range(240)) + "\n}\n")
        result = self.collect(evidence_focus="domain_extension")
        item = next(item for item in result["inventory"] if item["path"].endswith("Actual.cpp"))
        self.assertTrue(item["selected_excerpts"][0]["context_window_truncated"])
        output = probe.console_summary(result)
        self.assertIn("context_window_truncated=true", output)
        self.assertIn("budget_truncated=true", output)
        self.assertLessEqual(len(output.splitlines()), 500)
        for item in result["inventory"]:
            item["selected_excerpts"] = [
                {"topic": topic, "start_line": 1, "end_line": 1000,
                 "text": "\n".join("void SATURATED_DECLARATION();" for _ in range(1000))}
                for topic, *_ in probe.DOMAIN_RULES]
        self.assertLessEqual(len(probe.console_summary(result).splitlines()), 500)
        blocked = self.collect(evidence_focus="caller_defined_roots")
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("UNSUPPORTED_EVIDENCE_FOCUS", blocked["blockers"])
        self.assertEqual(blocked["source_file_count"], 0)

    def test_domain_extension_prioritizes_actual_conversion_and_schema_contracts(self):
        registry = "Engine/Plugins/Experimental/ToolsetRegistry/Source"
        self.write(f"{registry}/AOther.cpp", "TFuture FOtherHandler::ExecuteToolInternal()\n{\n"
                   + "\n".join(f"    int Noise{index} = {index};" for index in range(160)) + "\n}\n")
        self.write(f"{registry}/ZActualConverter.cpp",
                   "TFuture FActualConverter::ExecuteToolInternal()\n{\n"
                   "    UFunction* Reflected = nullptr;\n    return ACTUAL_CONVERSION_TAIL;\n}\n")
        self.write(f"{registry}/Toolset.cpp",
                   "FString FToolset::GetJsonSchema() const\n{\n    return FILTERED_SCHEMA_CONTRACT;\n}\n"
                   "TArray FToolset::ListToolNames() const\n{\n    return TOOL_NAMES_SCHEMA_CONTRACT;\n}\n")
        self.write("Engine/Plugins/Experimental/ModelContextProtocol/Source/ActualSchemaConsumer.cpp",
                   "int FActualSchemaAdapter::RegisterToolsFromSchema(const FString& Schema)\n{\n"
                   '    const char* Fields = "tools name description parameters";\n'
                   "    return ACTUAL_MCP_SCHEMA_CONSUMER;\n}\n")
        result = self.collect(evidence_focus="domain_extension")
        output = probe.console_summary(result)
        self.assertIn("ACTUAL_CONVERSION_TAIL", output)
        self.assertIn("FILTERED_SCHEMA_CONTRACT", output)
        self.assertIn("TOOL_NAMES_SCHEMA_CONTRACT", output)
        self.assertIn("ACTUAL_MCP_SCHEMA_CONSUMER", output)
        self.assertTrue(result["domain_extension_observations"]["mcp_schema_consumer"])
        self.assertLessEqual(len(output.splitlines()), 500)

    def material_fixture(self, *, source=None):
        relative = "Engine/Plugins/Experimental/Toolsets/ZMaterialFixture"
        self.plugin("ZMaterialFixture", relative)
        return self.write(relative + "/Content/Python/toolsets/material_instance.py", source or (
            "raise RuntimeError('EPIC_SOURCE_MUST_NEVER_EXECUTE')\n"
            "@toolset_registry.toolset(name='MaterialInstanceTools')\n"
            "class FixtureMaterialTools:\n"
            "    @toolset_registry.tool_call\n"
            "    @staticmethod\n"
            "    def get_fixture_parameter(reference: str, name: str) -> float:\n"
            "        return ACTUAL_READ_DECLARATION_BODY\n"
            "    @toolset_registry.tool_call\n"
            "    def set_fixture_parameter(reference: str, name: str, value: float) -> bool:\n"
            "        return ACTUAL_WRITE_DECLARATION_BODY\n"))

    def test_material_focus_discovers_actual_decorated_declarations_without_execution(self):
        path = self.material_fixture()
        before = {item: item.read_bytes() for item in self.engine.rglob("*") if item.is_file()}
        stock = self.collect()
        self.assertNotIn("ZMaterialFixture", stock["plugins"])
        self.assertEqual(stock["issue"], 384)
        result = self.collect(evidence_focus="material_declarations")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertEqual(result["issue"], 364)
        observed = result["material_declaration_observations"]
        self.assertEqual([item["name"] for item in observed],
                         ["FixtureMaterialTools", "get_fixture_parameter", "set_fixture_parameter"])
        self.assertIn("name='MaterialInstanceTools'", observed[0]["decorators"][0])
        self.assertEqual(observed[1]["line"], 6)
        self.assertIn("reference: str, name: str", observed[1]["signature"])
        self.assertEqual(observed[1]["decorators"], ["toolset_registry.tool_call", "staticmethod"])
        self.assertEqual(observed[0]["signature"], "class FixtureMaterialTools:")
        self.assertTrue(all(item["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest() for item in observed))
        output = probe.console_summary(result)
        self.assertIn("ACTUAL_READ_DECLARATION_BODY", output)
        self.assertIn("ACTUAL_WRITE_DECLARATION_BODY", output)
        self.assertNotIn("EPIC_SOURCE_MUST_NEVER_EXECUTE", output)
        for key in ("guard_parity_verified", "runtime_schema_verified", "official_mcp_admitted",
                    "mcp_server_started", "plugin_activation_performed", "persistent_content_mutation_performed",
                    "editor_execution_performed", "material_tool_execution_performed", "material_authoring_admitted",
                    "performance_pass"):
            self.assertIs(result[key], False)
        self.assertEqual(before, {item: item.read_bytes() for item in before})

    def test_material_focus_missing_and_literal_only_evidence_fail_closed(self):
        result = self.collect(evidence_focus="material_declarations")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("MATERIAL_METHOD_DECLARATIONS_UNESTABLISHED", result["blockers"])
        self.material_fixture(source=(
            "# class MaterialInstanceTools is not an actual declaration.\n"
            "EXAMPLE = 'class MaterialInstanceTools'\n"
            "class Unrelated:\n    def set_fixture(self):\n        return False\n"))
        result = self.collect(evidence_focus="material_declarations")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["material_declaration_observations"], [])
        self.assertEqual(result["material_declaration_unestablished"][0]["reason"],
                         "MATERIAL_TOOLSET_DECLARATION_UNESTABLISHED")
        self.material_fixture(source="class MaterialInstanceTools:\n    pass\n")
        self.assertEqual(self.collect(evidence_focus="material_declarations")["status"], "BLOCKED")

    def test_material_focus_tests_cannot_satisfy_or_spend_declaration_budget(self):
        relative = "Engine/Plugins/Experimental/Toolsets/MaterialInstanceTools"
        self.plugin("MaterialInstanceTools", relative)
        self.write(relative + "/Content/Python/Tests/material_instance.py",
                   "class MaterialInstanceTools:\n    def get_fixture(self):\n        SHIPPED_TEST_MUST_NOT_PRINT\n")
        result = self.collect(evidence_focus="material_declarations")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["material_declaration_observations"], [])
        self.assertNotIn("SHIPPED_TEST_MUST_NOT_PRINT", probe.console_summary(result))

    def test_material_focus_definition_body_and_console_budgets_are_explicit(self):
        source = "class MaterialInstanceTools:\n    def get_fixture(self):\n"
        source += "\n".join(f"        value_{index} = {index}" for index in range(120)) + "\n"
        source += "\n".join(f"    def set_fixture_{index}(self):\n        return False" for index in range(80))
        self.material_fixture(source=source)
        result = self.collect(evidence_focus="material_declarations")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertEqual(len(result["material_declaration_observations"]), probe.MAX_MATERIAL_DEFINITIONS)
        self.assertTrue(result["material_declaration_index_truncated"])
        item = next(item for item in result["inventory"] if item.get("material_declarations"))
        body = next(excerpt for excerpt in item["selected_excerpts"] if excerpt["name"] == "get_fixture")
        self.assertTrue(body["context_window_truncated"])
        self.assertTrue(body["budget_truncated"])
        self.assertEqual(len(body["text"].splitlines()), probe.MAX_MATERIAL_BODY_LINES)
        self.assertLessEqual(len(probe.console_summary(result).splitlines()), probe.MAX_CONSOLE_LINES)
        with patch.object(probe, "MAX_EXCERPT_LINES", 9):
            limited = self.collect(evidence_focus="material_declarations")
        self.assertTrue(limited["excerpt_limit_reached"])
        self.assertLessEqual(sum(len(excerpt["text"].splitlines()) for item in limited["inventory"]
                                 for excerpt in item["selected_excerpts"]), 9)

    def test_material_discovery_rejects_link_escape_and_preserves_global_read_budget(self):
        path = self.material_fixture()
        result = self.collect(evidence_focus="material_declarations")
        preceding = 0
        for item in result["inventory"]:
            if item["path"] == path.relative_to(self.engine).as_posix():
                break
            preceding += item["bytes"]
        with patch.object(probe, "MAX_TOTAL_BYTES", preceding + path.stat().st_size - 1), patch.object(
            probe, "read_bounded", wraps=probe.read_bounded,
        ) as reads:
            blocked = self.collect(evidence_focus="material_declarations")
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("SOURCE_TOTAL_BYTE_LIMIT", blocked["blockers"])
        self.assertNotIn(path, [call.args[1] for call in reads.call_args_list])
        outside = self.root / "outside-material.py"
        outside.write_text("NEVER_READ_OR_EXECUTE\n")
        path.unlink()
        path.symlink_to(outside)
        result = self.collect(evidence_focus="material_declarations")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("LINK_OR_REPARSE_POINT" in error for error in result["blockers"]))

    def stream_fixture(self):
        # Synthetic spellings test extraction only; these are not Epic CLI contracts.
        relative = probe.STREAM_PLUGIN_ROOT
        self.plugin("PixelStreaming2", relative)
        self.write(relative + "/Source/PixelStreaming2Settings/Public/FixtureSettings.h",
                   "enum class EPixelStreaming2EditorStreamTypes\n{\n"
                   "    LevelEditorViewport = 0,\n    FixtureOtherViewport = 1\n};\n")
        self.write(relative + "/Source/PixelStreaming2Settings/Private/FixtureSettings.cpp",
                   "\n".join(f'static TAutoConsoleVariable<int> CVar{symbol}(TEXT("FixtureOnly.{symbol}"), 0);'
                             for symbol in ("EditorPixelStreaming", "StartOnLaunch", "StreamType",
                                            "ViewerPort", "StreamerPort")) + "\n")
        self.write(relative + "/Source/PixelStreaming2Editor/Private/FixtureEditor.cpp",
                   "void FFixtureEditor::StartStreamingWithEditor()\n{\n"
                   "    FixtureServer.StartSignalling();\n    FixtureStream.StartStreaming();\n}\n"
                   'FAutoConsoleCommand FixtureCommand(TEXT("FixtureOnly.StopStreaming"), TEXT("fixture"), FixtureCallback);\n')
        self.write(relative + "/Config/FixtureStreaming.ini",
                   "; CommentOnly.StartOnLaunch must not establish a candidate.\n"
                   "[FixtureOnly]\nEditorPixelStreaming=false\n")
        self.write(probe.STREAM_PLUGIN_MANAGER,
                   'FParse::Value(FCommandLine::Get(), TEXT("EnablePlugins="), FixtureNames);\n')

    def test_stream_focus_is_read_only_and_retains_actual_contexts_without_admission(self):
        self.stream_fixture()
        before = {item: item.read_bytes() for item in self.engine.rglob("*") if item.is_file()}
        result = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertEqual(result["issue"], 364)
        self.assertEqual(set(result["plugins"]), {"PixelStreaming2"})
        self.assertEqual(result["level_editor_stream_missing_contexts"], [])
        self.assertEqual(result["level_editor_stream_unestablished_paths"], [])
        self.assertEqual(result["level_editor_stream_status"], "INSTALLED_SOURCE_CONTEXTS_REQUIRE_REVIEW")
        output = probe.console_summary(result)
        for symbol in probe.STREAM_SYMBOLS:
            self.assertTrue(result["level_editor_stream_observations"][symbol], symbol)
            self.assertIn(symbol, output)
        self.assertIn('TEXT("FixtureOnly.StartOnLaunch")', output)
        self.assertIn("LevelEditorViewport = 0", output)
        for item in result["inventory"]:
            self.assertEqual(item["sha256"], hashlib.sha256((self.engine / item["path"]).read_bytes()).hexdigest())
        self.assertTrue(result["source_only"])
        for key in ("guard_parity_verified", "runtime_schema_verified", "official_mcp_admitted",
                    "mcp_server_started", "plugin_activation_performed", "persistent_content_mutation_performed",
                    "editor_execution_performed", "signalling_server_started", "streaming_started",
                    "stream_connection_verified", "level_editor_stream_admitted", "performance_pass"):
            self.assertIs(result[key], False, key)
        self.assertEqual(before, {item: item.read_bytes() for item in before})

    def test_stream_focus_never_scans_toolsets_or_reads_unapproved_plugin_sources(self):
        self.stream_fixture()
        toolsets = self.engine / "Engine/Plugins/Experimental/Toolsets"
        retained = toolsets.with_name("UnusedToolsets")
        toolsets.rename(retained)
        toolsets.symlink_to(retained, target_is_directory=True)
        relative = probe.STREAM_PLUGIN_ROOT
        forbidden = [
            self.write(relative + "/Source/PixelStreaming2/Private/Unapproved.cpp", "NEVER_READ\n"),
            self.write(relative + "/Source/PixelStreaming2Editor/Private/Unapproved.py",
                       "raise RuntimeError('NEVER_IMPORT_EPIC_SOURCE')\n"),
            self.write(relative + "/Source/PixelStreaming2Editor/Tests/FixtureTest.cpp", "NEVER_READ\n"),
            self.write("Engine/Source/Runtime/Projects/Private/Unapproved.cpp", "NEVER_READ\n"),
        ]
        with patch.object(probe, "bounded_files", wraps=probe.bounded_files) as scans, patch.object(
            probe, "read_bounded", wraps=probe.read_bounded,
        ) as reads:
            result = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertEqual({call.args[0] for call in scans.call_args_list}, {
            self.engine / relative / "Source" / name for name in probe.STREAM_MODULES
        } | {self.engine / relative / "Config"})
        paths = {call.args[1] for call in reads.call_args_list}
        self.assertFalse(paths.intersection(forbidden))
        self.assertFalse(any("Experimental" in path.parts for path in paths))
        approved_fixed = {self.project, self.engine / "Engine/Build/Build.version",
                          self.engine / relative / "PixelStreaming2.uplugin",
                          self.engine / probe.STREAM_PLUGIN_MANAGER}
        approved_roots = [self.engine / relative / "Source" / name for name in probe.STREAM_MODULES]
        approved_roots.append(self.engine / relative / "Config")
        self.assertTrue(all(path in approved_fixed or any(path.is_relative_to(root) for root in approved_roots)
                            for path in paths))

    def test_stream_focus_missing_plugin_or_required_module_fails_closed(self):
        with patch.object(probe, "bounded_files", wraps=probe.bounded_files) as scans:
            missing = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(missing["status"], "BLOCKED")
        self.assertIn("MISSING_PLUGIN_DESCRIPTOR: PixelStreaming2", missing["blockers"])
        self.assertEqual(missing["source_file_count"], 1)
        scans.assert_not_called()
        self.assertFalse(missing["streaming_started"])
        self.stream_fixture()
        module = self.engine / probe.STREAM_PLUGIN_ROOT / "Source/PixelStreaming2Editor"
        for path in module.rglob("*.cpp"):
            path.unlink()
        missing = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(missing["status"], "BLOCKED")
        self.assertIn("MISSING_PLUGIN_SOURCES: PixelStreaming2Editor", missing["blockers"])
        self.assertFalse(missing["plugin_activation_performed"])

    def test_stream_focus_preserves_version_sha_and_source_budget_boundaries(self):
        self.stream_fixture()
        result = self.collect(evidence_focus="level_editor_stream", actual_sha="b" * 40)
        self.assertEqual(result["source_file_count"], 0)
        self.assertIn("REPOSITORY_SHA_MISMATCH", result["blockers"])
        baseline = self.collect(evidence_focus="level_editor_stream")
        first_source = baseline["inventory"][2]
        limit = sum(item["bytes"] for item in baseline["inventory"][:2]) + first_source["bytes"] - 1
        with patch.object(probe, "MAX_TOTAL_BYTES", limit), patch.object(
            probe, "read_bounded", wraps=probe.read_bounded,
        ) as reads:
            limited = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(limited["status"], "BLOCKED")
        self.assertIn("SOURCE_TOTAL_BYTE_LIMIT", limited["blockers"])
        self.assertNotIn(self.engine / first_source["path"], [call.args[1] for call in reads.call_args_list])
        with patch.object(probe, "MAX_SOURCE_FILES", 2):
            limited = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(limited["source_file_count"], 2)
        self.assertIn("SOURCE_FILE_COUNT_LIMIT", limited["blockers"])
        self.write("Engine/Build/Build.version", json.dumps({
            "MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 3, "Changelist": 56702186,
        }))
        with patch.object(probe, "bounded_files", wraps=probe.bounded_files) as scans:
            mismatched = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(mismatched["status"], "BLOCKED")
        self.assertTrue(any("ENGINE_VERSION_MISMATCH" in error for error in mismatched["blockers"]))
        scans.assert_not_called()

    def test_stream_focus_rejects_source_and_optional_manager_links(self):
        self.stream_fixture()
        external = self.root / "outside-stream.cpp"
        external.write_text("NEVER_READ_OUTSIDE_SOURCE\n")
        source = self.engine / probe.STREAM_PLUGIN_ROOT / "Source/PixelStreaming2Editor/Private/FixtureEditor.cpp"
        original = source.read_bytes()
        source.unlink()
        source.symlink_to(external)
        with patch.object(probe, "read_bounded", wraps=probe.read_bounded) as reads:
            result = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("LINK_OR_REPARSE_POINT" in error for error in result["blockers"]))
        self.assertNotIn(source, [call.args[1] for call in reads.call_args_list])
        source.unlink()
        source.write_bytes(original)
        manager = self.engine / probe.STREAM_PLUGIN_MANAGER
        manager.unlink()
        manager.symlink_to(external)
        result = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("LINK_OR_REPARSE_POINT" in error for error in result["blockers"]))

    def test_stream_focus_missing_optional_paths_or_symbols_are_explicitly_unverified(self):
        self.stream_fixture()
        (self.engine / probe.STREAM_PLUGIN_MANAGER).unlink()
        result = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertIn(probe.STREAM_PLUGIN_MANAGER, result["level_editor_stream_unestablished_paths"])
        self.assertIn("EnablePlugins", result["level_editor_stream_missing_contexts"])
        for path in (self.engine / probe.STREAM_PLUGIN_ROOT).rglob("*"):
            if path.suffix in probe.STREAM_SOURCE_SUFFIXES:
                comment = ";" if path.suffix == ".ini" else "//"
                path.write_text(f"{comment} StartStreaming is only a comment.\nvoid DifferentInstalledDeclaration();\n")
        result = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertEqual(result["level_editor_stream_missing_contexts"], list(probe.STREAM_SYMBOLS))
        self.assertFalse(any(result["level_editor_stream_observations"].values()))
        self.assertFalse(result["level_editor_stream_admitted"])

    def test_stream_focus_excerpt_index_and_console_caps_are_preserved(self):
        self.stream_fixture()
        noise = []
        for symbol in probe.STREAM_SYMBOLS:
            for index in range(35):
                noise.extend([f"void Fixture_{symbol}_{index}();", *("int FixtureNoise;" for _ in range(58))])
        self.write(probe.STREAM_PLUGIN_ROOT + "/Source/PixelStreaming2Editor/Private/LongFixture.cpp",
                   "\n".join(noise))
        result = self.collect(evidence_focus="level_editor_stream")
        self.assertEqual(result["status"], "SOURCE_EVIDENCE_COLLECTED")
        self.assertTrue(result["level_editor_stream_index_truncated"])
        self.assertTrue(all(len(items) <= probe.MAX_STREAM_OBSERVATIONS_PER_SYMBOL
                            for items in result["level_editor_stream_observations"].values()))
        output = probe.console_summary(result)
        self.assertIn("budget_truncated=true", output)
        self.assertLessEqual(len(output.splitlines()), probe.MAX_CONSOLE_LINES)
        self.assertLessEqual(sum(len(excerpt["text"].splitlines()) for item in result["inventory"]
                                 for excerpt in item["selected_excerpts"]), probe.MAX_EXCERPT_LINES)
        with patch.object(probe, "MAX_EXCERPT_LINES", 9):
            limited = self.collect(evidence_focus="level_editor_stream")
        self.assertTrue(limited["excerpt_limit_reached"])
        self.assertLessEqual(sum(len(excerpt["text"].splitlines()) for item in limited["inventory"]
                                 for excerpt in item["selected_excerpts"]), 9)


if __name__ == "__main__":
    unittest.main()
