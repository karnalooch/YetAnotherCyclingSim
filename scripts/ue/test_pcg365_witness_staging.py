"""Portable contract checks for the read-only/isolated PCG365 witness stager.

These offline checks intentionally do not run PowerShell, Unreal, MCP or UBT.
"""
from pathlib import Path
import hashlib
import json
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ue/Prepare-YacsPcgWitnessStage.ps1"
DOCS = ROOT / "docs/tooling/PCG365_NATIVE_WITNESS_DEPLOYMENT.md"
PINNED_PROJECT = ROOT / "YetAnotherCyclingSim.uproject"
NATIVE_TARGET = ROOT / "Source/YetAnotherCyclingSimPcg365Editor.Target.cs"
ORDINARY_TARGET = ROOT / "Source/YetAnotherCyclingSimEditor.Target.cs"
COMMON_EDITOR = ROOT / "Source/YetAnotherCyclingSimEditor"
PLUGIN = ROOT / "Plugins/YacsPcgWitness"


class NativeWitnessStageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")

    def test_inspect_is_the_default_and_buildstage_is_explicit(self):
        self.assertIn("[ValidateSet('Inspect', 'BuildStage')]", self.script)
        self.assertIn("$Action = 'Inspect'", self.script)
        self.assertIn("if ($Action -ceq 'Inspect')", self.script)

    def test_historical_uproject_byte_pin_is_preserved(self):
        raw = PINNED_PROJECT.read_bytes()
        self.assertEqual(len(raw), 1152)
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "09fbd6cd85fbdd299a3e37cfb65658e1210183878516599c90b783acc1d8099b",
        )
        plugins = {item["Name"] for item in json.loads(raw)["Plugins"]}
        self.assertNotIn("ToolsetRegistry", plugins)
        self.assertNotIn("ModelContextProtocol", plugins)
        self.assertNotIn("YacsPcgWitness", plugins)

    def test_pcg365_mcp_plugins_only_on_opt_in_editor_target(self):
        target = NATIVE_TARGET.read_text(encoding="utf-8")
        self.assertIn("class YetAnotherCyclingSimPcg365EditorTarget", target)
        self.assertIn('EnablePlugins.Add("ToolsetRegistry")', target)
        self.assertIn('EnablePlugins.Add("ModelContextProtocol")', target)
        self.assertIn('EnablePlugins.Add("YacsPcgWitness")', target)
        self.assertIn("$BuildTarget = 'YetAnotherCyclingSimPcg365Editor'", self.script)
        self.assertIn("PINNED_LAUNCHER_PROJECT_CHANGED", self.script)
        self.assertIn("build_target = $BuildTarget", self.script)

    def test_witness_reflection_is_isolated_from_ordinary_editor(self):
        descriptor = json.loads((PLUGIN / "YacsPcgWitness.uplugin").read_text())
        self.assertIs(descriptor["EnabledByDefault"], False)
        self.assertEqual(
            descriptor["Modules"],
            [
                {
                    "Name": "YacsPcgWitness",
                    "Type": "Editor",
                    "LoadingPhase": "PostEngineInit",
                }
            ],
        )
        dependencies = {
            item["Name"] for item in descriptor["Plugins"] if item["Enabled"]
        }
        self.assertTrue(
            {"ToolsetRegistry", "ModelContextProtocol", "PCG"} <= dependencies
        )
        common_build = (COMMON_EDITOR / "YetAnotherCyclingSimEditor.Build.cs").read_text()
        common_module = (
            COMMON_EDITOR / "Private/YetAnotherCyclingSimEditor.cpp"
        ).read_text()
        self.assertNotIn("ToolsetRegistry", common_build)
        self.assertNotIn("ToolsetRegistry", common_module)
        self.assertNotIn("YacsPcgWitness", ORDINARY_TARGET.read_text())
        self.assertFalse((COMMON_EDITOR / "Public/PCG/YacsPcgWitnessToolset.h").exists())
        self.assertFalse((COMMON_EDITOR / "Private/PCG/YacsPcgWitnessToolset.cpp").exists())

    def test_exact_source_and_worktree_guards(self):
        self.assertIn("git -C $ProjectRoot rev-parse HEAD", self.script)
        self.assertIn("git -C $ProjectRoot status --porcelain --untracked-files=no", self.script)
        self.assertIn("Assert-YacsBuildIsolation -ProjectPath $ProjectFile", self.script)
        self.assertIn("The build candidate DLL is already loaded", self.script)

    def test_accepted_world_hash_is_checked_on_both_sides(self):
        self.assertIn("CANONICAL_CHECKPOINT_MUTATED", self.script)
        self.assertIn("five immutable checkpoint package hashes", self.docs)
        self.assertIn("$checkpoint = @(Check-CanonicalCheckpoint)", self.script)
        self.assertIn("$checkpointAfter = @(Check-CanonicalCheckpoint)", self.script)

    def test_no_mutation_of_owner_live_release(self):
        self.assertIn("STAGED_NOT_DEPLOYED", self.script)
        self.assertIn("owner_restart_approved = $false", self.script)
        self.assertIn("native_reader_loaded = $false", self.script)
        self.assertNotIn("Stop-Process", self.script)
        self.assertNotIn("git reset --hard", self.script)
        self.assertNotIn("git clean", self.script)
        self.assertNotIn("Restart-Computer", self.script)
        self.assertNotIn("Live Host executable replacement", self.script)

    def test_compilation_and_staging_require_fresh_verified_artifacts(self):
        self.assertIn("No freshly linked DLL for requested exact HEAD", self.script)
        self.assertIn("Editor and engine BuildId mismatch", self.script)
        self.assertIn("Staged byte identity drift", self.script)
        self.assertIn("never overwrite it", self.script)
        self.assertIn("'-NoHotReloadFromIDE'", self.script)

    def test_stage_keeps_plugin_sources_and_separate_module_manifests(self):
        for path in (
            "Source/YacsPcgWitness/YacsPcgWitness.Build.cs",
            "Source/YacsPcgWitness/Public/PCG/YacsPcgWitnessToolset.h",
            "Source/YacsPcgWitness/Private/PCG/YacsPcgWitnessToolset.cpp",
            "Source/YacsPcgWitness/Private/YacsPcgWitnessModule.cpp",
        ):
            self.assertTrue((PLUGIN / path).is_file(), path)
            self.assertIn(path, self.script)
        self.assertIn('"$WitnessPluginRelativeRoot/YacsPcgWitness.uplugin"', self.script)
        self.assertIn(
            '"$WitnessPluginRelativeRoot/Binaries/Win64/UnrealEditor.modules"',
            self.script,
        )
        self.assertIn("'Binaries/Win64/UnrealEditor.modules'", self.script)
        self.assertIn(
            "Check-ModuleManifest $ProjectModules $engineBuildId $ProjectModuleFiles",
            self.script,
        )
        self.assertIn("Check-ModuleManifest $CandidateModules $engineBuildId", self.script)
        self.assertIn("Unexpected module-to-DLL mapping", self.script)
        self.assertIn("Join-Path $StagePath $file.relative_path", self.script)
        self.assertIn("relative_path = $file.relative_path", self.script)
        self.assertIn("schema_version = 2", self.script)

    def test_runtime_plugin_enable_is_a_requirement_not_deployment(self):
        self.assertIn("$RuntimeEnableArgument = '-EnablePlugins=YacsPcgWitness'", self.script)
        self.assertIn("required_runtime_enable_argument = $RuntimeEnableArgument", self.script)
        self.assertIn("stage_layout = 'PROJECT_RELATIVE_OVERLAY_NOT_DEPLOYED'", self.script)
        self.assertIn("native_reader_loaded = $false", self.script)

    def test_docs_keep_external_witness_and_generation_gates_blocked(self):
        self.assertIn("process-local", self.docs)
        self.assertIn("newly generated UUID", self.docs)
        self.assertIn("SAFE_MCP_BLOCKED", self.docs)
        self.assertIn("WHOLE_AREA_BLOCKED", self.docs)


if __name__ == "__main__":
    unittest.main()
