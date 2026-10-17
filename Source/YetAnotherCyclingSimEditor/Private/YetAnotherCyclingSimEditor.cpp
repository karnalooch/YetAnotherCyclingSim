#include "Containers/Ticker.h"
#include "Editor.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Modules/ModuleManager.h"
#include "PCG/YacsPcgWitnessToolset.h"
#include "ToolsetRegistry/ToolsetRegistrySubsystem.h"
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
			const FString ToolsetName = TEXT("YetAnotherCyclingSimEditor.YacsPcgWitnessToolset");
			if (UToolsetRegistry::IsToolsetRegistered(ToolsetName) || UToolsetRegistry::IsToolsetClassRegistered(ToolsetClass))
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
		const FString ToolsetName = TEXT("YetAnotherCyclingSimEditor.YacsPcgWitnessToolset");
		const FString WitnessPattern = TEXT("/^YetAnotherCyclingSimEditor[.]YacsPcgWitnessToolset([.].*)?$/");

		TValueOrError<TObjectPtr<UToolsetRegistrySubsystem>, FString> SubsystemResult = UToolsetRegistrySubsystem::Get();
		if (SubsystemResult.HasValue())
		{
			UToolsetRegistrySubsystem* Subsystem = SubsystemResult.GetValue();
			if (Subsystem && Subsystem->ToolsetRegistry.GetAllowedNames().Num() > 0)
			{
				if (!Subsystem->ToolsetRegistry.GetAllowedNames().Contains(WitnessPattern))
				{
					Subsystem->ToolsetRegistry.AddAllowedName(WitnessPattern);
				}
			}
		}

		const bool bPreviouslyRegistered = UToolsetRegistry::IsToolsetRegistered(ToolsetName) ||
			UToolsetRegistry::IsToolsetClassRegistered(ToolsetClass);
		if (!bPreviouslyRegistered)
		{
			UToolsetRegistry::RegisterToolsetClass(ToolsetClass);
		}
		if (!UToolsetRegistry::IsToolsetRegistered(ToolsetName) &&
			!UToolsetRegistry::IsToolsetClassRegistered(ToolsetClass))
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

		// Refresh ModelContextProtocol so the newly registered toolset is cataloged and discoverable
		if (GEngine)
		{
			UWorld* ExecWorld = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
			GEngine->Exec(ExecWorld, TEXT("ModelContextProtocol.RefreshTools"));
		}

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
