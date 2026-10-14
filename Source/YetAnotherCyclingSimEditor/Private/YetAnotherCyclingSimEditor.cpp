#include "Containers/Ticker.h"
#include "Modules/ModuleManager.h"
#include "PCG/YacsPcgWitnessToolset.h"
#include "ToolsetRegistry/UToolsetRegistry.h"

DEFINE_LOG_CATEGORY_STATIC(LogYacsPcg365Witness, Log, All);

// A PostEngineInit module can load AFTER FCoreDelegates::OnPostEngineInit has
// already fired. Also, UEditorSubsystem instances (including ToolsetRegistry)
// may not yet be available when StartupModule executes. Defer registration to
// the Editor's core ticker and verify its result before reporting success.
class FYetAnotherCyclingSimEditorModule : public IModuleInterface
{
public:
	virtual void StartupModule() override
	{
		if (!TryRegisterToolset())
		{
			UE_LOG(LogYacsPcg365Witness, Display,
				TEXT("PCG365_WITNESS_REGISTRATION_DEFERRED: waiting for ToolsetRegistry editor subsystem"));
			RegistrationTickerHandle = FTSTicker::GetCoreTicker().AddTicker(
				FTickerDelegate::CreateRaw(this, &FYetAnotherCyclingSimEditorModule::RetryRegistration),
				1.0f);
		}
	}

	virtual void ShutdownModule() override
	{
		// No callback may retain a raw module pointer after ShutdownModule.
		if (RegistrationTickerHandle.IsValid())
		{
			FTSTicker::RemoveTicker(RegistrationTickerHandle);
			RegistrationTickerHandle.Reset();
		}

		// Do not remove another module's registration if this module merely found
		// its class already registered. During teardown the registry may be gone.
		if (bOwnsRegistration && IsInGameThread() && UToolsetRegistry::IsAvailable())
		{
			UClass* ToolsetClass = UYacsPcgWitnessToolset::StaticClass();
			if (UToolsetRegistry::IsToolsetClassRegistered(ToolsetClass))
			{
				UToolsetRegistry::UnregisterToolsetClass(ToolsetClass);
				UE_LOG(LogYacsPcg365Witness, Display, TEXT("PCG365_WITNESS_TOOLSET_UNREGISTERED"));
			}
		}
		bRegistered = false;
		bOwnsRegistration = false;
	}

private:
	bool TryRegisterToolset()
	{
		if (bRegistered)
		{
			return true;
		}
		if (!IsInGameThread() || !UToolsetRegistry::IsAvailable())
		{
			return false;
		}

		UClass* ToolsetClass = UYacsPcgWitnessToolset::StaticClass();
		const bool bPreviouslyRegistered = UToolsetRegistry::IsToolsetClassRegistered(ToolsetClass);
		if (!bPreviouslyRegistered)
		{
			UToolsetRegistry::RegisterToolsetClass(ToolsetClass);
		}
		if (!UToolsetRegistry::IsToolsetClassRegistered(ToolsetClass))
		{
			UE_LOG(LogYacsPcg365Witness, Error,
				TEXT("PCG365_WITNESS_REGISTRATION_FAILED: class was not registered after RegisterToolsetClass"));
			return false;
		}

		bRegistered = true;
		bOwnsRegistration = !bPreviouslyRegistered;
		UE_LOG(LogYacsPcg365Witness, Display,
			TEXT("PCG365_WITNESS_TOOLSET_REGISTERED: class=%s; refresh MCP tool catalog with ModelContextProtocol.RefreshTools"),
			*ToolsetClass->GetPathName());
		return true;
	}

	bool RetryRegistration(float DeltaTime)
	{
		if (TryRegisterToolset())
		{
			return false; // Core ticker drops this registration after success.
		}
		if (++RegistrationAttempts >= 120)
		{
			UE_LOG(LogYacsPcg365Witness, Error,
				TEXT("PCG365_WITNESS_REGISTRATION_TIMEOUT: ToolsetRegistry unavailable after 120 seconds; MCP witness remains blocked"));
			return false; // Bounded, no retry storm and no automatic editor restart.
		}
		return true;
	}

	FTSTicker::FDelegateHandle RegistrationTickerHandle;
	uint32 RegistrationAttempts = 0;
	bool bRegistered = false;
	bool bOwnsRegistration = false;
};

IMPLEMENT_MODULE(FYetAnotherCyclingSimEditorModule, YetAnotherCyclingSimEditor)
