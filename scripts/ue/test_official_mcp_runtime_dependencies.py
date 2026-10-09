"""Synthetic installed-source fixtures, never native UE/MCP admission evidence.

Only the repository's constant embedded collector runs. Fixture C++ is data;
none of these tests imports or executes installed source, an Editor or a server.
"""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


HELPER = Path(__file__).with_name("Read-YacsOfficialMcpRuntimeDependencies.ps1")
AUTO = "Engine/Plugins/Experimental/Toolsets/AutomationTestToolset/Source/AutomationTestToolset/"
MCP = "Engine/Plugins/Experimental/ModelContextProtocol/Source/"
AUTO_IMPL = AUTO + "Private/AutomationTestToolset.cpp"
SERVER_IMPL = MCP + "ModelContextProtocol/Private/ModelContextProtocolModule.cpp"
TRANSPORT_IMPL = MCP + "ModelContextProtocol/Private/ModelContextProtocolServer.cpp"
HTTP_IMPL = "Engine/Source/Runtime/Online/HTTPServer/Private/HttpServerModule.cpp"
LISTENER_IMPL = "Engine/Source/Runtime/Online/HTTPServer/Private/HttpListener.cpp"
CONFIG_HEADER = "Engine/Source/Runtime/Online/HTTPServer/Private/HttpServerConfig.h"
CONFIG_IMPL = "Engine/Source/Runtime/Online/HTTPServer/Private/HttpServerConfig.cpp"
CORE_HEADER = "Engine/Source/Runtime/Core/Public/Misc/AutomationTest.h"
CORE_IMPL = "Engine/Source/Runtime/Core/Private/Misc/AutomationTest.cpp"
PROJECTS_HEADER = "Engine/Source/Runtime/Projects/Public/Interfaces/IPluginManager.h"
PROJECTS_IMPL = "Engine/Source/Runtime/Projects/Private/PluginManager.cpp"
PYTHON = "Engine/Plugins/Experimental/PythonScriptPlugin/Source/PythonScriptPlugin/"
PYTHON_HEADER = PYTHON + "Public/IPythonScriptPlugin.h"
PYTHON_IMPL = PYTHON + "Private/PythonScriptPlugin.cpp"
FIXED_ENGINE_PATHS = {CORE_HEADER, CORE_IMPL, PROJECTS_HEADER, PROJECTS_IMPL, PYTHON_HEADER, PYTHON_IMPL}
RUNTIME_FLAGS = (
    "official_mcp_transport_verified", "official_mcp_admitted", "argument_policy_parity_verified",
    "local_only_binding_verified", "existing_project_test_verified", "native_bob_capture_verified",
    "persistent_world_mutation",
)


class OfficialMcpRuntimeDependenciesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = HELPER.read_text(encoding="utf-8")
        opening, closing = "$DependencyReader = @'\n", "\n'@"
        if source.count(opening) != 1:
            raise AssertionError("expected one constant embedded dependency reader")
        cls.program = source.split(opening, 1)[1].split(closing, 1)[0]
        cls.compiled = compile(cls.program, str(HELPER) + "::DependencyReader", "exec")
        cls.reader_directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.reader_directory.cleanup)
        cls.reader = Path(cls.reader_directory.name) / "synthetic-source-collector.py"
        cls.reader.write_text(cls.program, encoding="utf-8")

    def setUp(self):
        # Reuse the source author's bounded fixture layout. Matching version
        # numbers are synthetic parser input; they say nothing about this host.
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.engine, self.output = self.base / "engine", self.base / "evidence"
        self.output.mkdir()
        self.attempt = 0
        self.write("Engine/Build/Build.version", json.dumps({
            "MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 2, "Changelist": 56702186,
        }))
        self.write(AUTO_IMPL,
            "static UAutomationTestToolsetSubsystem* GetSubsystem() { return nullptr; }\n" +
            "".join("void UAutomationTestToolset::" + name + "() {\n"
                    ' const char* value=R"tag({ fake })tag";\n}\n'
                    for name in ("DiscoverTests", "ListTests", "RunTests", "GetTestResults", "GetTestStatus")))
        self.write(AUTO + "Public/AutomationTestToolsetSubsystem.h",
                   "class UAutomationTestToolsetSubsystem {};\n")
        self.write(AUTO + "Private/AutomationTestToolsetSubsystem.cpp",
            "".join("void UAutomationTestToolsetSubsystem::" + name + "() {}\n"
                    for name in ("FormatResultsJson", "CollectLeafReports", "EnableRunResultPolling",
                                 "Initialize", "PollRunResults")))
        self.write(MCP + "ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h",
                   "class UModelContextProtocolSettings {};\n")
        self.write(MCP + "ModelContextProtocolEngine/Private/ModelContextProtocolSettings.cpp",
                   'const char* URL="http://synthetic.invalid/";\n')
        self.write(MCP + "ModelContextProtocolEditor/Private/ModelContextProtocolEditor.cpp",
                   "void FEditor::StartupModule() {}\n")
        self.write(MCP + "ModelContextProtocol/Public/IModelContextProtocolModule.h",
                   "class IModelContextProtocolModule { virtual bool StartServer(int port)=0; };\n")
        self.write(SERVER_IMPL, '#include "HttpServerModule.h"\n'
            "void FModule::StartServer() {\n// AddTool(fake);\n"
            'const char* text="AddTool(fake);";\n AddTool(Real);\n}\n'
            "void FModule::ShutdownModule() {}\n" +
            "".join("void FModelContextProtocolModule::" + name + "\n() {}\n"
                    for name in ("AddTool", "RemoveTool", "RefreshTools", "FindTool", "GetTools")))
        self.write(MCP + "ModelContextProtocol/Public/IModelContextProtocolTool.h",
                   "class IModelContextProtocolTool { virtual bool ExecuteSynthetic() = 0; };\n")
        self.write(MCP + "ModelContextProtocol/Public/ModelContextProtocolServer.h",
                   "class FModelContextProtocolServer {};\n")
        self.write(TRANSPORT_IMPL, "void FModelContextProtocolServer::HandleRequest() {}\n")
        self.write(MCP + "ModelContextProtocolEngine/Public/ModelContextProtocolToolLibrary.h",
                   "class UModelContextProtocolToolLibrary {};\n")
        self.write(MCP + "ModelContextProtocolEngine/Private/ModelContextProtocolToolLibrary.cpp",
                   "void UModelContextProtocolToolLibrary::SyntheticControl() {}\n")
        self.write(MCP + "ModelContextProtocolEditor/Private/ModelContextProtocolToolsetRegistryAdapter.cpp",
                   "void FToolsetRegistryToolAdapter::Execute() {}\n")
        self.write(CORE_HEADER, "enum class EAutomationExpectedMessageFlags { Contains, Exact };\n"
                   "struct FAutomationExpectedLogMessage { int Occurrences; };\n"
                   "void AddExpectedError();\nvoid AddExpectedMessage();\nvoid AddExpectedLogMessage();\n")
        self.write(CORE_IMPL,
                   "FAutomationExpectedMessage::FAutomationExpectedMessage() : Occurrences(1) {}\n"
                   "bool FAutomationExpectedMessage::Matches() { return MatchSynthetic(); }\n"
                   "bool FAutomationExpectedLogMessage::HasMetExpectedOccurrences() { return Occurrences == 1; }\n"
                   "void FAutomationTestBase::AddExpectedError() { RecordSynthetic(); }\n")
        self.write(PROJECTS_HEADER, "virtual bool ConfigureEnabledPlugin() = 0;\n")
        self.write(PROJECTS_IMPL, "bool FPluginManager::ConfigureEnabledPlugins() {\n"
                   " auto ParsePluginsList = [](const char* value) { ParseSynthetic(value); };\n"
                   ' ParseSynthetic(TEXT("EnablePlugins="));\n ParseSynthetic(TEXT("DisablePlugins="));\n return true;\n}\n')
        self.write(PYTHON_HEADER, "class IPythonScriptPlugin {\n"
                   " virtual bool ExecPythonCommand(const char* command) = 0;\n"
                   " virtual bool ExecPythonCommandEx(FSyntheticCommand& result) = 0;\n};\n")
        self.write(PYTHON_IMPL, "bool FPythonScriptPlugin::ExecPythonCommand(const char* command) { return SyntheticExecute(command); }\n"
                   "bool FPythonScriptPlugin::ExecPythonCommandEx(FSyntheticCommand& result) { return SyntheticExecuteResult(result); }\n")

    def write(self, relative, text):
        path = self.engine / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def next_output(self):
        self.attempt += 1
        destination = self.output / str(self.attempt)
        destination.mkdir()
        return destination

    def receipt(self, destination):
        value = json.loads((destination / "runtime-dependencies.json").read_text(encoding="utf-8"))
        self.assertIs(value["source_only"], True)
        self.assertIs(value["declarations_require_primary_review"], True)
        for name in RUNTIME_FLAGS:
            self.assertIs(value[name], False)
        return value

    def run_reader(self, *, program_suffix=""):
        destination = self.next_output()
        process = subprocess.run(
            [sys.executable, "-", str(self.engine), str(destination), "a" * 40],
            input=self.reader.read_text(encoding="utf-8") + program_suffix,
            check=False, capture_output=True, text=True, timeout=30,
        )
        self.assertTrue((destination / "runtime-dependencies.json").exists(), process.stderr)
        return process, self.receipt(destination)

    def test_large_owned_program_executes_without_windows_command_line_overflow(self):
        program_suffix = "\n# " + "synthetic-owned-comment " * 2000 + "\n"
        self.assertGreater(len(program_suffix), 32767)
        command = [sys.executable, "-", str(self.engine), str(self.output), "a" * 40]
        self.assertLess(len(subprocess.list2cmdline(command)), 32767)
        process, receipt = self.run_reader(program_suffix=program_suffix)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(receipt["status"], "PARTIAL_DEPENDENCY_EVIDENCE")

    def test_constant_program_collects_primary_hashes_without_runtime_claims(self):
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(receipt["status"], "PARTIAL_DEPENDENCY_EVIDENCE")
        self.assertFalse(any(item.get("reason") == "SOURCE_MISSING" for item in receipt["gaps"]))
        self.assertTrue(any(item.get("reason") == "NAMED_DECLARATION_CONTEXT_REQUIRES_PRIMARY_REVIEW"
                            for item in receipt["gaps"]))
        self.assertTrue(receipt["mcp_callsite_index_complete"])
        self.assertEqual(len(receipt["direct_registration_calls"]), 1)
        self.assertEqual(receipt["direct_registration_calls"][0]["line"], 5)
        excerpt = next(item for item in receipt["excerpts"] if item["topic"] == "server_start")
        self.assertTrue(excerpt["body_complete"])
        self.assertEqual((excerpt["line_start"], excerpt["line_end"]), (2, 6))
        self.assertEqual(excerpt["sha256"], hashlib.sha256((self.engine / SERVER_IMPL).read_bytes()).hexdigest())
        self.assertEqual(receipt["observed_server_dependency_includes"][0]["include"], "HttpServerModule.h")
        self.assertTrue(all(item["path"] == "Engine/Build/Build.version"
            or item["path"] in FIXED_ENGINE_PATHS
            or item["path"].startswith((AUTO, MCP)) for item in receipt["source_files"]))
        for topic in ("expected_error_declarations", "expected_matcher_constructor_context",
                      "expected_FAutomationExpectedMessage_Matches",
                      "expected_FAutomationExpectedLogMessage_HasMetExpectedOccurrences",
                      "fixed_plugin_activation_context", "fixed_plugin_list_parser", "direct_tool_interface",
                      "module_FindTool", "module_GetTools", "python_bridge_public_declarations",
                      "python_bridge_ExecPythonCommand", "python_bridge_ExecPythonCommandEx"):
            self.assertTrue(any(item["topic"] == topic for item in receipt["excerpts"]))
        parser_console = process.stdout.split("PURPOSE plugin_activation ", 1)[1].split("END_PURPOSE plugin_activation", 1)[0]
        self.assertIn("topic=fixed_plugin_list_parser", next(line for line in parser_console.splitlines() if line.startswith("SOURCE ")))
        python_bodies = [item for item in receipt["excerpts"]
                         if item["topic"] in {"python_bridge_ExecPythonCommand", "python_bridge_ExecPythonCommandEx"}]
        self.assertTrue(all(item["body_complete"] for item in python_bodies))

    def test_engine_identity_mismatch_stops_before_plugin_read(self):
        self.write("Engine/Build/Build.version", json.dumps({
            "MajorVersion": 5, "MinorVersion": 8, "PatchVersion": 1, "Changelist": 56702186,
        }))
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(receipt["error"], "ENGINE_IDENTITY_MISMATCH")
        self.assertEqual(receipt["source_file_count"], 1)

    def test_missing_truncated_and_invocation_bodies_never_become_complete_definitions(self):
        cases = (
            ("comment", "// void UAutomationTestToolset::RunTests() {}\n", None),
            ("declaration", "void UAutomationTestToolset::RunTests();\n", None),
            ("invocation", "void Other() {\n if (UAutomationTestToolset::RunTests(x)) {\n return;\n }\n}\n", None),
            ("truncated", "void UAutomationTestToolset::RunTests() {\n RealBody();\n", False),
            ("lambda_parameter", "void UAutomationTestToolset::RunTests(Fn callback = []() { return 1; }) {\n RealBody();\n}\n", True),
        )
        for name, source, complete in cases:
            with self.subTest(name=name):
                self.write(AUTO_IMPL, source)
                process, receipt = self.run_reader()
                self.assertEqual(process.returncode, 0, process.stderr)
                observations = [item for item in receipt["excerpts"] if item["topic"] == "RunTests"]
                if complete is None:
                    self.assertEqual(observations, [])
                    self.assertTrue(any(item.get("topic") == "RunTests" for item in receipt["gaps"]))
                else:
                    self.assertEqual(len(observations), 1)
                    self.assertIs(observations[0]["body_complete"], complete)
                    if complete:
                        self.assertEqual(observations[0]["line_end"], 3)
        self.write(SERVER_IMPL, "void FModule::StartServer() { /* unfinished")
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(receipt["error"], "UNTERMINATED_CPP_COMMENT")
        self.assertFalse(any(item["topic"] == "server_start" for item in receipt["excerpts"]))

    def test_comments_strings_and_raw_literals_cannot_invent_calls_or_includes(self):
        self.write(SERVER_IMPL, '#include "HttpServerModule.h"\n'
            'const char* text = R"tag(\n#include "HttpFakeServer.h"\n AddTool(RawFake);\n)tag";\n'
            "void FModule::StartServer() {\n"
            "// Continued comment \\\r\n AddTool(CommentFake);\r\n"
            ' const char* escaped="\\\" AddTool(StringFake); { }";\n'
            " /* AddTool(BlockFake); */\n AddTool(Real);\n}\n")
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(receipt["direct_registration_calls"]), 1)
        self.assertIn("AddTool(Real)", receipt["direct_registration_calls"][0]["text"])
        self.assertEqual([item["include"] for item in receipt["observed_server_dependency_includes"]],
                         ["HttpServerModule.h"])

    def test_symlink_and_synthetic_windows_junction_metadata_are_denied(self):
        path = self.engine / AUTO_IMPL
        original = path.read_bytes()
        outside = self.base / "outside-source.cpp"
        outside.write_text("OUTSIDE_SOURCE_MUST_NEVER_BE_READ", encoding="utf-8")
        path.unlink()
        path.symlink_to(outside)
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(receipt["error"], "LINK_OR_REPARSE_POINT")
        self.assertNotIn("OUTSIDE_SOURCE_MUST_NEVER_BE_READ", json.dumps(receipt))
        path.unlink()
        path.write_bytes(original)
        destination, real_lstat = self.next_output(), Path.lstat

        def synthetic_reparse(candidate):
            value = real_lstat(candidate)
            if candidate == path:
                return SimpleNamespace(st_mode=value.st_mode,
                    st_file_attributes=getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
            return value

        # Execute only the trusted embedded program while substituting a Windows
        # metadata observation; no fixture source is executable Python.
        with mock.patch.object(Path, "lstat", synthetic_reparse), mock.patch.object(
                sys, "argv", [str(self.reader), str(self.engine), str(destination), "a" * 40]), \
                redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                exec(self.compiled, {"__name__": "__main__"})
        self.assertEqual(failure.exception.code, 1)
        self.assertEqual(self.receipt(destination)["error"], "LINK_OR_REPARSE_POINT")

    def test_per_file_and_total_byte_budgets_stop_before_oversized_read(self):
        original = (self.engine / AUTO_IMPL).read_text()
        self.write(AUTO_IMPL, "x" * (2 * 1024 * 1024 + 1))
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(receipt["source_file_count"], 1)
        self.write(AUTO_IMPL, original)
        large = "/*" + "x" * (1900 * 1024) + "*/\n"
        for relative in (AUTO_IMPL, AUTO + "Public/AutomationTestToolsetSubsystem.h",
                AUTO + "Private/AutomationTestToolsetSubsystem.cpp",
                MCP + "ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h",
                MCP + "ModelContextProtocolEngine/Private/ModelContextProtocolSettings.cpp"):
            self.write(relative, large + (self.engine / relative).read_text())
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(receipt["error"], "GLOBAL_SOURCE_BUDGET")
        self.assertLessEqual(receipt["total_source_bytes"], 8 * 1024 * 1024)
        self.assertFalse(any(item["path"].endswith("ModelContextProtocolSettings.cpp")
                             for item in receipt["source_files"]))

    def test_file_budget_and_cache_leave_unread_inventory_explicit(self):
        for index in range(20):
            self.write(MCP + f"ModelContextProtocol/Private/Extra{index:02d}.cpp",
                       "void Synthetic() { AddTool(Synthetic); }\n")
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(receipt["source_file_count"], 21)
        self.assertFalse(receipt["mcp_callsite_index_complete"])
        self.assertTrue(any(not item["scanned"] for item in receipt["mcp_callsite_inventory"]))
        sources = receipt["source_files"]
        self.assertEqual(len(sources), len({item["path"] for item in sources}))
        self.assertEqual(receipt["total_source_bytes"], sum(item["byte_count"] for item in sources))

    def test_excerpt_and_console_bounds_include_large_summary_observations(self):
        self.write(MCP + "ModelContextProtocolEngine/Public/ModelContextProtocolSettings.h",
                   "int SyntheticValue;\n" * 1600)
        self.write(SERVER_IMPL, '#include "HttpServerModule.h"\n' * 600 +
                   "void FModule::StartServer() {}\n")
        self.write(TRANSPORT_IMPL, "void FModelContextProtocolServer::HandleRequest() {\n" +
                   "int SyntheticValue;\n" * 1600 + "}\n")
        self.write(MCP + "ModelContextProtocolEngine/Private/ModelContextProtocolToolLibrary.cpp",
                   "void UModelContextProtocolToolLibrary::SyntheticControl() {\n" +
                   "int SyntheticValue;\n" * 1600 + "}\n")
        self.write(PYTHON_HEADER, "int SyntheticPythonInterfaceValue;\n" * 1600)
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 0, process.stderr)
        excerpt = next(item for item in receipt["excerpts"] if item["topic"] == "settings_declarations")
        self.assertFalse(excerpt["body_complete"])
        self.assertEqual(len(excerpt["lines"]), 1200)
        for purpose in ("automation", "expected_errors", "plugin_activation", "python_bridge", "mcp_transport", "mcp"):
            section = process.stdout.split("PURPOSE " + purpose + " ", 1)[1].split("END_PURPOSE " + purpose, 1)[0]
            self.assertLessEqual(len(section.splitlines()) + 1, 500)
        self.assertIn("PURPOSE mcp console_truncated=True", process.stdout)
        self.assertIn("PURPOSE mcp_transport console_truncated=True", process.stdout)
        self.assertIn("PURPOSE python_bridge console_truncated=True", process.stdout)
        self.assertLessEqual(max(map(len, process.stdout.splitlines())), 1100)

    def test_actual_http_include_chain_is_bounded_and_has_source_provenance(self):
        self.write(TRANSPORT_IMPL, '#include "HttpServerModule.h"\n'
                   "void FModelContextProtocolServer::HandleRequest() {}\n")
        self.write(HTTP_IMPL, '#include "HttpListener.h"\n'
                   "void FHttpServerModule::StartAllListeners() {}\n"
                   "void FHttpServerModule::GetHttpRouter() {\n"
                   " CachedSyntheticConfigCallback = []() { return SyntheticConfiguration(); };\n}\n")
        self.write(LISTENER_IMPL, '#include "HttpServerConfig.h"\nvoid FHttpListener::StartListening() {}\n')
        self.write(CONFIG_HEADER, "struct FHttpServerConfig {};\n")
        self.write(CONFIG_IMPL, 'const FString IniSectionNameHTTPServerListeners(TEXT("SYNTHETIC_LISTENER_SECTION"));\n'
                   "int FHttpServerConfig::GetListenerConfig() { return SyntheticBindConfiguration(); }\n"
                   "void FHttpServerConfig::OnConfigSectionsChanged(const FString& Filename, const TSet<FString>& Sections) {\n"
                   " if (Sections.Contains(IniSectionNameHTTPServerListeners)) { SyntheticCacheDirty = true; }\n}\n")
        # The collector may follow only the two fixed backend dependencies,
        # even with an unrelated escaping link and abundant optional source.
        unrelated = self.engine / "Engine/Source/Runtime/Unrelated"
        unrelated.parent.mkdir(parents=True, exist_ok=True)
        unrelated.symlink_to(self.base / "outside-unread", target_is_directory=True)
        for index in range(20):
            self.write(MCP + f"ModelContextProtocol/Private/Extra{index:02d}.cpp",
                       "void Synthetic() {}\n")
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 0, process.stderr)
        follows = receipt["followed_binding_dependencies"]
        self.assertEqual([item["path"] for item in follows], [HTTP_IMPL, LISTENER_IMPL, CONFIG_HEADER])
        self.assertEqual([item["from_path"] for item in follows], [TRANSPORT_IMPL, HTTP_IMPL, LISTENER_IMPL])
        for item in follows:
            self.assertEqual(item["include_line"], 1)
            self.assertEqual(item["from_sha256"],
                             hashlib.sha256((self.engine / item["from_path"]).read_bytes()).hexdigest())
        self.assertLessEqual(receipt["source_file_count"], 26)
        self.assertLessEqual(receipt["total_source_bytes"], 8 * 1024 * 1024)
        self.assertFalse(receipt["mcp_callsite_index_complete"])
        outside = [item["path"] for item in receipt["source_files"]
                   if not item["path"].startswith((AUTO, MCP)) and item["path"] != "Engine/Build/Build.version"
                   and item["path"] not in FIXED_ENGINE_PATHS]
        self.assertEqual(outside, [HTTP_IMPL, LISTENER_IMPL, CONFIG_HEADER, CONFIG_IMPL])
        self.assertTrue(any(item["topic"] == "http_config_getter" and item["body_complete"]
                            for item in receipt["excerpts"]))
        self.assertTrue(any(item["topic"] == "http_config_section_name" for item in receipt["excerpts"]))
        cache = next(item for item in receipt["excerpts"] if item["topic"] == "http_config_cache_invalidation")
        self.assertTrue(cache["body_complete"])
        self.assertTrue(any("SyntheticCacheDirty = true" in line["text"] for line in cache["lines"]))
        self.assertIn('IniSectionNameHTTPServerListeners(TEXT("SYNTHETIC_LISTENER_SECTION"))', process.stdout)
        self.assertIn("topic=http_config_cache_invalidation body_complete=True", process.stdout)
        router = next(item for item in receipt["excerpts"] if item["topic"] == "http_GetHttpRouter")
        self.assertTrue(router["body_complete"])
        self.assertTrue(any("CachedSyntheticConfigCallback" in line["text"] for line in router["lines"]))
        for topic in ("module_AddTool", "module_RemoveTool", "module_RefreshTools", "adapter_Execute"):
            self.assertTrue(any(item["topic"] == topic and item["body_complete"] for item in receipt["excerpts"]))

    def test_literal_http_includes_never_follow_and_real_backend_link_is_denied(self):
        self.write(HTTP_IMPL, '#include "HttpListener.h"\nvoid FHttpServerModule::StartAllListeners() {}\n')
        self.write(LISTENER_IMPL, "void FHttpListener::StartListening() {}\n")
        for source in ('// #include "HttpServerModule.h"\n',
                       'const char* text=R"tag(\n#include "HttpServerModule.h"\n)tag";\n'):
            with self.subTest(source=source):
                self.write(TRANSPORT_IMPL, source + "void FModelContextProtocolServer::HandleRequest() {}\n")
                process, receipt = self.run_reader()
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(receipt["followed_binding_dependencies"], [])
                self.assertFalse(any(item["path"].startswith("Engine/Source/")
                    and item["path"] not in FIXED_ENGINE_PATHS for item in receipt["source_files"]))
        self.write(TRANSPORT_IMPL, '#include "HttpServerModule.h"\nvoid FModelContextProtocolServer::HandleRequest() {}\n')
        self.write(HTTP_IMPL, 'const char* text=R"tag(\n#include "HttpListener.h"\n)tag";\n'
                   "void FHttpServerModule::StartAllListeners() {}\n")
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual([item["path"] for item in receipt["followed_binding_dependencies"]], [HTTP_IMPL])
        backend = self.engine / HTTP_IMPL
        outside = self.base / "outside-http.cpp"
        outside.write_text("OUTSIDE_BACKEND_MUST_NOT_BE_READ", encoding="utf-8")
        backend.unlink()
        backend.symlink_to(outside)
        process, receipt = self.run_reader()
        self.assertEqual(process.returncode, 1)
        self.assertEqual(receipt["error"], "LINK_OR_REPARSE_POINT")
        self.assertNotIn("OUTSIDE_BACKEND_MUST_NOT_BE_READ", json.dumps(receipt))


if __name__ == "__main__":
    unittest.main()
