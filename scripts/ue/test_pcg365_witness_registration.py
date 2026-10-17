"""Static, no-Unreal checks for the delayed PCG365 MCP toolset registration.

These guards verify the lifecycle structure only. They cannot establish
runtime tool discovery, in-engine witness admission or an editor deployment.
"""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MODULE = (
    ROOT
    / "Source/YetAnotherCyclingSimEditor/Private/YetAnotherCyclingSimEditor.cpp"
)
TOOLSET = (
    ROOT
    / "Source/YetAnotherCyclingSimEditor/Public/PCG/YacsPcgWitnessToolset.h"
)
DOCS = ROOT / "docs/tooling/PCG365_NATIVE_WITNESS_DEPLOYMENT.md"


class WitnessRegistrationSourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = MODULE.read_text(encoding="utf-8")
        cls.header = TOOLSET.read_text(encoding="utf-8")
        cls.docs = DOCS.read_text(encoding="utf-8")

    def test_registers_after_registry_is_available_not_just_module_startup(self):
        self.assertIn("bool TryRegisterToolset()", self.module)
        self.assertIn("!UToolsetRegistry::IsAvailable()", self.module)
        self.assertIn("FTSTicker::GetCoreTicker().AddTicker", self.module)
        self.assertIn("RetryRegistration(float DeltaTime)", self.module)

    def test_not_dependent_on_already_fired_post_engine_init_delegate(self):
        self.assertNotIn("OnPostEngineInit.AddRaw", self.module)
        self.assertIn("PostEngineInit module can load AFTER", self.module)

    def test_registration_is_checked_for_idempotence(self):
        self.assertIn("bPreviouslyRegistered", self.module)
        self.assertIn("UToolsetRegistry::IsToolsetClassRegistered", self.module)
        self.assertIn("UToolsetRegistry::RegisterToolsetClass(ToolsetClass)", self.module)
        self.assertIn("bRegistered = true", self.module)
        self.assertIn("bOwnsRegistration = !bPreviouslyRegistered", self.module)

    def test_shutdown_unbinds_and_only_unregisters_owned_registration(self):
        self.assertIn("virtual void ShutdownModule() override", self.module)
        self.assertIn("FTSTicker::RemoveTicker(RegistrationTickerHandle)", self.module)
        self.assertIn("bOwnsRegistration && IsInGameThread()", self.module)
        self.assertIn("UToolsetRegistry::UnregisterToolsetClass(ToolsetClass)", self.module)

    def test_retries_are_bounded_without_engine_restart(self):
        self.assertIn("++RegistrationAttempts >= 120", self.module)
        self.assertIn("PCG365_WITNESS_REGISTRATION_TIMEOUT", self.module)
        self.assertNotIn("RequestExit(", self.module)
        self.assertNotIn("Stop-Process", self.module)

    def test_actual_native_toolset_remains_an_ai_callable_cpp_class(self):
        self.assertIn("public UToolsetDefinition", self.header)
        self.assertIn("UFUNCTION(meta = (AICallable)", self.header)
        self.assertIn("ModelContextProtocol.RefreshTools", self.docs)
        self.assertIn("NATIVE_WITNESS_BLOCKED", self.docs)


if __name__ == "__main__":
    unittest.main()
