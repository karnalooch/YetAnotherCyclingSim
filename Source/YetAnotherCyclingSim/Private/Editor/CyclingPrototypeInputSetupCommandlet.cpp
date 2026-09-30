// Copyright YetAnotherCyclingSim. All Rights Reserved.

#include "Cycling/CyclingPrototypeInputSetupCommandlet.h"

#if WITH_EDITOR

#include "Cycling/CyclingPrototypePawn.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Engine/World.h"
#include "EnhancedInputSubsystems.h"
#include "FileHelpers.h"
#include "Framework/Notifications/NotificationManager.h"
#include "GameFramework/Pawn.h"
#include "HAL/FileManager.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"
#include "UObject/SavePackage.h"
#include "Widgets/Notifications/SNotificationList.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingInputSetup, Log, All);

namespace CyclingInputSetupInternal
{
	// Asset locations.
	const TCHAR* InputFolderPath = TEXT("/Game/Prototype/Input");
	const TCHAR* MapPackagePath   = TEXT("/Game/Prototype/Maps/L_CyclingTest");

	// Input Action asset names. The asset file name in /Game must match
	// the IInputActionFName argument; UE creates one .uasset per
	// UInputAction.
	const TCHAR* PowerIncreaseActionName   = TEXT("IA_PowerIncrease");
	const TCHAR* PowerDecreaseActionName   = TEXT("IA_PowerDecrease");
	const TCHAR* CadenceIncreaseActionName = TEXT("IA_CadenceIncrease");
	const TCHAR* CadenceDecreaseActionName = TEXT("IA_CadenceDecrease");
	const TCHAR* StartRideActionName       = TEXT("IA_StartRide");
	const TCHAR* StopRideActionName        = TEXT("IA_StopRide");
	const TCHAR* RestartRideActionName     = TEXT("IA_RestartRide");
	const TCHAR* DefaultMappingContextName = TEXT("IMC_CyclingPrototype_Default");

	const TCHAR* PlaceholderLabel = TEXT("BikePlaceholder");

	// Build a full /Game path for a named asset under InputFolderPath.
	FString BuildActionPath(const TCHAR* AssetName)
	{
		return FString::Printf(TEXT("%s/%s.%s"), InputFolderPath, AssetName, AssetName);
	}

	// Create-or-reuse a UInputAction as a UDataAsset under /Game.
	// Returns the existing asset if one already exists; otherwise
	// constructs a new one and saves the package. Boolean value type is
	// correct for each of our actions: pressed key -> one Started
	// event.
	UInputAction* LoadOrCreateInputAction(const TCHAR* AssetName)
	{
		const FString FullObjectPath = BuildActionPath(AssetName);

		if (UInputAction* Existing = Cast<UInputAction>(StaticLoadObject(
			UInputAction::StaticClass(), nullptr, *FullObjectPath)))
		{
			return Existing;
		}

		const FString PackagePath = FString::Printf(TEXT("%s/%s"), InputFolderPath, AssetName);
		UPackage* Package = CreatePackage(*PackagePath);
		if (!Package)
		{
			UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to create package '%s'."), *PackagePath);
			return nullptr;
		}
		Package->FullyLoad();

		UInputAction* Action = NewObject<UInputAction>(
			Package, UInputAction::StaticClass(),
			FName(AssetName),
			RF_Public | RF_Standalone);
		if (!Action)
		{
			UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to create UInputAction '%s'."), *FullObjectPath);
			return nullptr;
		}
		// Boolean event value: each started trigger is one mutation.
		Action->ValueType = EInputActionValueType::Boolean;

		FAssetRegistryModule::AssetCreated(Action);
		Package->MarkPackageDirty();

		const FString FilePath = FPackageName::LongPackageNameToFilename(
			PackagePath, FPackageName::GetAssetPackageExtension());

		FSavePackageArgs SaveArgs;
		SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
		SaveArgs.SaveFlags = SAVE_NoError;
		const bool bSaved = UPackage::SavePackage(Package, Action, *FilePath, SaveArgs);
		if (!bSaved)
		{
			UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to save UInputAction '%s'."), *FullObjectPath);
			return nullptr;
		}
		UE_LOG(LogCyclingInputSetup, Display, TEXT("Created UInputAction '%s'."), *FullObjectPath);
		return Action;
	}

	// Ensure a UInputMappingContext exists with the documented bindings.
	// Existing IMC content is preserved; the Mappings are rewritten to
	// match the documented keyboard layout every run, so the asset is the
	// single source of truth.
	UInputMappingContext* LoadOrCreateMappingContext(
		UInputAction* PowerInc,
		UInputAction* PowerDec,
		UInputAction* CadenceInc,
		UInputAction* CadenceDec,
		UInputAction* StartRide,
		UInputAction* StopRide,
		UInputAction* RestartRide)
	{
		const FString FullObjectPath = FString::Printf(TEXT("%s/%s.%s"),
			InputFolderPath, DefaultMappingContextName, DefaultMappingContextName);

		UInputMappingContext* IMC = Cast<UInputMappingContext>(StaticLoadObject(
			UInputMappingContext::StaticClass(), nullptr, *FullObjectPath));

		bool bNeedsCreate = false;
		bool bNeedsSave = false;

		if (!IMC)
		{
			bNeedsCreate = true;
			const FString PackagePath = FString::Printf(TEXT("%s/%s"), InputFolderPath, DefaultMappingContextName);
			UPackage* Package = CreatePackage(*PackagePath);
			if (!Package)
			{
				UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to create package '%s'."), *PackagePath);
				return nullptr;
			}
			Package->FullyLoad();
			IMC = NewObject<UInputMappingContext>(
				Package, UInputMappingContext::StaticClass(),
				FName(DefaultMappingContextName),
				RF_Public | RF_Standalone);
			if (!IMC)
			{
				UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to create UInputMappingContext."));
				return nullptr;
			}
			FAssetRegistryModule::AssetCreated(IMC);
			Package->MarkPackageDirty();
			bNeedsSave = true;
		}

		// Public API: UnmapAll() clears every existing default and profile
		// override mapping; we re-bind the documented keyboard layout on
		// every run so this commandlet is the single source of truth for
		// the binding layout. UE 5.8 deprecated direct access to the
		// legacy TArray<FEnhancedActionKeyMapping> Mappings member.
		IMC->UnmapAll();

		auto AddMapping = [&IMC, &bNeedsSave](UInputAction* Action, FKey Key)
		{
			if (!Action) { return; }
			IMC->MapKey(Action, Key);
			bNeedsSave = true;
		};

		AddMapping(PowerInc,    EKeys::Up);
		AddMapping(PowerDec,    EKeys::Down);
		AddMapping(CadenceInc,  EKeys::Right);
		AddMapping(CadenceDec,  EKeys::Left);
		AddMapping(StartRide,   EKeys::SpaceBar);
		AddMapping(StopRide,    EKeys::S);
		AddMapping(RestartRide, EKeys::R);

		if (bNeedsSave)
		{
			const FString PackagePath = FString::Printf(TEXT("%s/%s"),
				InputFolderPath, DefaultMappingContextName);
			const FString FilePath = FPackageName::LongPackageNameToFilename(
				PackagePath, FPackageName::GetAssetPackageExtension());

			UPackage* Package = IMC->GetOutermost();
			Package->MarkPackageDirty();
			FSavePackageArgs SaveArgs;
			SaveArgs.TopLevelFlags = RF_Public | RF_Standalone;
			SaveArgs.SaveFlags = SAVE_NoError;
			const bool bSaved = UPackage::SavePackage(Package, IMC, *FilePath, SaveArgs);
			if (!bSaved)
			{
				UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to save UInputMappingContext '%s'."), *FullObjectPath);
				return nullptr;
			}
			if (bNeedsCreate)
			{
				UE_LOG(LogCyclingInputSetup, Display, TEXT("Created UInputMappingContext '%s'."), *FullObjectPath);
			}
			else
			{
				UE_LOG(LogCyclingInputSetup, Display, TEXT("Saved UInputMappingContext '%s' (refreshed)."), *FullObjectPath);
			}
		}
		return IMC;
	}

	// Locate the placed ACyclingPrototypePawn inside the map by label.
	// Returns nullptr when no Pawn or more than one Pawn is found, so
	// the commandlet fails loudly instead of leaving the map in a
	// half-configured state.
	ACyclingPrototypePawn* FindPlacedPawn(UWorld* MapWorld)
	{
		ACyclingPrototypePawn* Match = nullptr;
		int32 PawnCount = 0;
		for (AActor* Actor : MapWorld->GetCurrentLevel()->Actors)
		{
			ACyclingPrototypePawn* Candidate = Cast<ACyclingPrototypePawn>(Actor);
			if (!IsValid(Candidate))
			{
				continue;
			}
			++PawnCount;
			Match = Candidate;
		}
		if (PawnCount != 1)
		{
			UE_LOG(LogCyclingInputSetup, Error,
				TEXT("Expected exactly 1 ACyclingPrototypePawn in '%s', found %d."),
				MapPackagePath, PawnCount);
			return nullptr;
		}
		if (Match->GetActorLabel() != PlaceholderLabel)
		{
			UE_LOG(LogCyclingInputSetup, Error,
				TEXT("Placed ACyclingPrototypePawn is labelled '%s', expected '%s'."),
				*Match->GetActorLabel(), PlaceholderLabel);
			return nullptr;
		}
		return Match;
	}
}

UCyclingPrototypeInputSetupCommandlet::UCyclingPrototypeInputSetupCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
}

int32 UCyclingPrototypeInputSetupCommandlet::Main(const FString& Params)
{
	using namespace CyclingInputSetupInternal;

	UE_LOG(LogCyclingInputSetup, Display, TEXT("CyclingPrototypeInputSetupCommandlet: starting."));

	// Step 1: create-or-reuse all UInputAction assets.
	UInputAction* PowerInc    = LoadOrCreateInputAction(PowerIncreaseActionName);
	UInputAction* PowerDec    = LoadOrCreateInputAction(PowerDecreaseActionName);
	UInputAction* CadenceInc  = LoadOrCreateInputAction(CadenceIncreaseActionName);
	UInputAction* CadenceDec  = LoadOrCreateInputAction(CadenceDecreaseActionName);
	UInputAction* StartRide   = LoadOrCreateInputAction(StartRideActionName);
	UInputAction* StopRide    = LoadOrCreateInputAction(StopRideActionName);
	UInputAction* RestartRide = LoadOrCreateInputAction(RestartRideActionName);

	if (!PowerInc || !PowerDec || !CadenceInc || !CadenceDec ||
		!StartRide || !StopRide || !RestartRide)
	{
		return 1;
	}

	// Step 2: create-or-reuse the UInputMappingContext.
	UInputMappingContext* IMC = LoadOrCreateMappingContext(
		PowerInc, PowerDec, CadenceInc, CadenceDec,
		StartRide, StopRide, RestartRide);
	if (!IMC)
	{
		return 1;
	}

	// Step 3: load the map.
	UWorld* MapWorld = nullptr;
	{
		UPackage* MapPackage = LoadPackage(nullptr, MapPackagePath, LOAD_None);
		if (!MapPackage)
		{
			UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to load map package '%s'."), MapPackagePath);
			return 1;
		}
		MapWorld = UWorld::FindWorldInPackage(MapPackage);
		if (!MapWorld)
		{
			UE_LOG(LogCyclingInputSetup, Error, TEXT("Map package '%s' does not contain a UWorld."), MapPackagePath);
			return 1;
		}
		MapWorld->WorldType = EWorldType::Editor;
	}
	UE_LOG(LogCyclingInputSetup, Display, TEXT("Loaded map '%s'."), MapPackagePath);

	// Step 4: locate the placed Pawn and assign references + possession.
	ACyclingPrototypePawn* Pawn = FindPlacedPawn(MapWorld);
	if (!Pawn)
	{
		return 1;
	}

	// Assign input assets.
	Pawn->DefaultMappingContext  = IMC;
	Pawn->PowerIncreaseAction    = PowerInc;
	Pawn->PowerDecreaseAction    = PowerDec;
	Pawn->CadenceIncreaseAction  = CadenceInc;
	Pawn->CadenceDecreaseAction  = CadenceDec;
	Pawn->StartRideAction        = StartRide;
	Pawn->StopRideAction         = StopRide;
	Pawn->RestartRideAction      = RestartRide;

	// Slice B behaviour: do not auto-start; auto-possess Player 0.
	Pawn->bAutoStart = false;
	Pawn->AutoPossessPlayer = EAutoReceiveInput::Player0;

	UE_LOG(LogCyclingInputSetup, Display,
		TEXT("Assigned input references on Pawn '%s'; bAutoStart=false; AutoPossessPlayer=Player0."),
		*Pawn->GetName());

	// Step 5: save the map.
	{
		const bool bSaved = UEditorLoadingAndSavingUtils::SaveMap(MapWorld, MapPackagePath);
		if (!bSaved)
		{
			UE_LOG(LogCyclingInputSetup, Error, TEXT("Failed to save map '%s'."), MapPackagePath);
			return 1;
		}
		UE_LOG(LogCyclingInputSetup, Display, TEXT("Saved map '%s'."), MapPackagePath);
	}

	// Step 6: verification. We verify every input asset reference plus
	// the possession setting on the (reloaded) map. Any deviation
	// returns non-zero.
	{
		bool bAllOk = true;
		UPackage* MapPackage = LoadPackage(nullptr, MapPackagePath, LOAD_None);
		UWorld* ReloadedWorld = MapPackage ? UWorld::FindWorldInPackage(MapPackage) : nullptr;
		ACyclingPrototypePawn* ReloadedPawn = ReloadedWorld ? FindPlacedPawn(ReloadedWorld) : nullptr;
		if (!ReloadedPawn)
		{
			UE_LOG(LogCyclingInputSetup, Error, TEXT("Verification: could not re-locate the placed Pawn."));
			bAllOk = false;
		}
		else
		{
			auto CheckRef = [&](const TCHAR* Label, const UObject* Expected, const UObject* Actual) -> bool
			{
				if (Expected != Actual)
				{
					UE_LOG(LogCyclingInputSetup, Error,
						TEXT("Verification: Pawn ref '%s' mismatch."), Label);
					return false;
				}
				return true;
			};

			bAllOk &= CheckRef(TEXT("DefaultMappingContext"),  IMC,         ReloadedPawn->DefaultMappingContext);
			bAllOk &= CheckRef(TEXT("PowerIncreaseAction"),    PowerInc,    ReloadedPawn->PowerIncreaseAction);
			bAllOk &= CheckRef(TEXT("PowerDecreaseAction"),    PowerDec,    ReloadedPawn->PowerDecreaseAction);
			bAllOk &= CheckRef(TEXT("CadenceIncreaseAction"),  CadenceInc,  ReloadedPawn->CadenceIncreaseAction);
			bAllOk &= CheckRef(TEXT("CadenceDecreaseAction"),  CadenceDec,  ReloadedPawn->CadenceDecreaseAction);
			bAllOk &= CheckRef(TEXT("StartRideAction"),        StartRide,   ReloadedPawn->StartRideAction);
			bAllOk &= CheckRef(TEXT("StopRideAction"),         StopRide,    ReloadedPawn->StopRideAction);
			bAllOk &= CheckRef(TEXT("RestartRideAction"),      RestartRide, ReloadedPawn->RestartRideAction);

			if (ReloadedPawn->bAutoStart)
			{
				UE_LOG(LogCyclingInputSetup, Error,
					TEXT("Verification: bAutoStart is true (expected false)."));
				bAllOk = false;
			}
			if (ReloadedPawn->AutoPossessPlayer != EAutoReceiveInput::Player0)
			{
				UE_LOG(LogCyclingInputSetup, Error,
					TEXT("Verification: AutoPossessPlayer is not Player0."));
				bAllOk = false;
			}
		}

		if (bAllOk)
		{
			UE_LOG(LogCyclingInputSetup, Display,
				TEXT("Verification: OK."));
		}
		else
		{
			UE_LOG(LogCyclingInputSetup, Error,
				TEXT("Verification: FAILED."));
			return 1;
		}
	}

	UE_LOG(LogCyclingInputSetup, Display, TEXT("CyclingPrototypeInputSetupCommandlet: done."));
	return 0;
}

#endif // WITH_EDITOR
