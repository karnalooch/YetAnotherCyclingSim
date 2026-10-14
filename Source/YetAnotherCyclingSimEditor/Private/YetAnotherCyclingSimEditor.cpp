#include "Modules/ModuleManager.h"
#include "PCG/YacsPcgWitnessToolset.h"
#include "ToolsetRegistry/UToolsetRegistry.h"

class FYetAnotherCyclingSimEditorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override
	{
		if (UToolsetRegistry::IsAvailable())
		{
			UToolsetRegistry::RegisterToolsetClass(UYacsPcgWitnessToolset::StaticClass());
		}
	}

	virtual void ShutdownModule() override
	{
		if (UToolsetRegistry::IsAvailable())
		{
			UToolsetRegistry::UnregisterToolsetClass(UYacsPcgWitnessToolset::StaticClass());
		}
	}
};

IMPLEMENT_MODULE(FYetAnotherCyclingSimEditorModule, YetAnotherCyclingSimEditor)
