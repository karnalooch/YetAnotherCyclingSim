// Copyright YetAnotherCyclingSim. All Rights Reserved.

#include "Cycling/CyclingPrototypeMapVerifyCommandlet.h"

#if WITH_EDITOR

#include "Cycling/CyclingPrototypePawn.h"

#include "Components/SplineComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingMapVerify, Log, All);

namespace CyclingMapVerifyInternal
{
	const TCHAR* MapPackagePath = TEXT("/Game/Prototype/Maps/L_CyclingTest");
	const TCHAR* PlaceholderLabel = TEXT("BikePlaceholder");

	// Expected Pawn mesh relative transform (must match CyclingPrototypeMapSetupCommandlet).
	const FVector ExpectedScale = FVector(1.8, 0.5, 1.2);
	const FVector ExpectedLocation = FVector(0.0, 0.0, 60.0);
	const double ScaleTolerance = 1e-3;
}

UCyclingPrototypeMapVerifyCommandlet::UCyclingPrototypeMapVerifyCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
}

int32 UCyclingPrototypeMapVerifyCommandlet::Main(const FString& Params)
{
	using namespace CyclingMapVerifyInternal;

	UE_LOG(LogCyclingMapVerify, Display, TEXT("CyclingPrototypeMapVerifyCommandlet: starting."));

	// Optional command-line flags.
	float DriveSeconds = 0.0f;
	FParse::Value(*Params, TEXT("DriveSeconds="), DriveSeconds);

	// Step 1: load the map.
	UPackage* MapPackage = LoadPackage(nullptr, MapPackagePath, LOAD_None);
	if (!MapPackage)
	{
		UE_LOG(LogCyclingMapVerify, Error, TEXT("Failed to load map '%s'."), MapPackagePath);
		return 1;
	}
	UWorld* MapWorld = UWorld::FindWorldInPackage(MapPackage);
	if (!MapWorld)
	{
		UE_LOG(LogCyclingMapVerify, Error, TEXT("Map package '%s' has no UWorld."), MapPackagePath);
		return 1;
	}
	MapWorld->WorldType = EWorldType::Editor;
	UE_LOG(LogCyclingMapVerify, Display, TEXT("Loaded map '%s'."), *MapWorld->GetName());

	bool bAllOk = true;

	// Step 2: enumerate actors and classify them.
	int32 PawnCount = 0;
	int32 PlaceholderStaticMeshCount = 0;
	int32 RouteActorCount = 0;
	ACyclingPrototypePawn* Pawn = nullptr;
	AActor* SoleRouteActor = nullptr;

	for (AActor* Actor : MapWorld->GetCurrentLevel()->Actors)
	{
		if (!IsValid(Actor))
		{
			continue;
		}
		if (Actor->IsA(ACyclingPrototypePawn::StaticClass()))
		{
			++PawnCount;
			Pawn = Cast<ACyclingPrototypePawn>(Actor);
			continue;
		}
		if (Actor->IsA(AStaticMeshActor::StaticClass()))
		{
			if (Actor->GetActorLabel() == PlaceholderLabel)
			{
				++PlaceholderStaticMeshCount;
			}
			continue;
		}
		TArray<USplineComponent*> Splines;
		Actor->GetComponents<USplineComponent>(Splines);
		if (Splines.Num() >= 1)
		{
			++RouteActorCount;
			SoleRouteActor = Actor;
			if (Splines.Num() != 1)
			{
				UE_LOG(LogCyclingMapVerify, Error,
					TEXT("Route actor '%s' has %d splines; exactly one is required."),
					*Actor->GetName(), Splines.Num());
				bAllOk = false;
			}
		}
	}

	if (PawnCount != 1)
	{
		UE_LOG(LogCyclingMapVerify, Error, TEXT("Expected exactly 1 ACyclingPrototypePawn, found %d."), PawnCount);
		bAllOk = false;
	}
	if (PlaceholderStaticMeshCount != 0)
	{
		UE_LOG(LogCyclingMapVerify, Error, TEXT("Expected 0 StaticMeshActor placeholder, found %d."), PlaceholderStaticMeshCount);
		bAllOk = false;
	}
	if (RouteActorCount != 1)
	{
		UE_LOG(LogCyclingMapVerify, Error, TEXT("Expected exactly 1 route Actor with >=1 spline, found %d."), RouteActorCount);
		bAllOk = false;
	}

	// Step 3: verify Pawn configuration.
	if (Pawn)
	{
		if (Pawn->GetActorLabel() != PlaceholderLabel)
		{
			UE_LOG(LogCyclingMapVerify, Error, TEXT("Pawn label is '%s', expected '%s'."),
				*Pawn->GetActorLabel(), PlaceholderLabel);
			bAllOk = false;
		}
		if (!IsValid(Pawn->RouteActor))
		{
			UE_LOG(LogCyclingMapVerify, Error, TEXT("Pawn RouteActor is null."));
			bAllOk = false;
		}
		else
		{
			UE_LOG(LogCyclingMapVerify, Display, TEXT("Pawn RouteActor = '%s'."), *Pawn->RouteActor->GetName());
			if (RouteActorCount == 1 && Pawn->RouteActor != SoleRouteActor)
			{
				UE_LOG(LogCyclingMapVerify, Error,
					TEXT("Pawn RouteActor does not reference the sole route Actor in the map."));
				bAllOk = false;
			}
		}
		if (!IsValid(Pawn->BicycleMesh))
		{
			UE_LOG(LogCyclingMapVerify, Error, TEXT("Pawn BicycleMesh is null."));
			bAllOk = false;
		}
		else
		{
			if (!Pawn->BicycleMesh->GetStaticMesh())
			{
				UE_LOG(LogCyclingMapVerify, Error, TEXT("Pawn BicycleMesh has no static mesh."));
				bAllOk = false;
			}
			const FVector ActualScale = Pawn->BicycleMesh->GetRelativeScale3D();
			const FVector ActualLocation = Pawn->BicycleMesh->GetRelativeLocation();
			if (FMath::Abs(ActualScale.X - ExpectedScale.X) > ScaleTolerance ||
				FMath::Abs(ActualScale.Y - ExpectedScale.Y) > ScaleTolerance ||
				FMath::Abs(ActualScale.Z - ExpectedScale.Z) > ScaleTolerance)
			{
				UE_LOG(LogCyclingMapVerify, Error,
					TEXT("Pawn BicycleMesh scale mismatch: actual=(%.3f, %.3f, %.3f), expected=(%.3f, %.3f, %.3f)."),
					ActualScale.X, ActualScale.Y, ActualScale.Z,
					ExpectedScale.X, ExpectedScale.Y, ExpectedScale.Z);
				bAllOk = false;
			}
			if (FMath::Abs(ActualLocation.X - ExpectedLocation.X) > ScaleTolerance ||
				FMath::Abs(ActualLocation.Y - ExpectedLocation.Y) > ScaleTolerance ||
				FMath::Abs(ActualLocation.Z - ExpectedLocation.Z) > ScaleTolerance)
			{
				UE_LOG(LogCyclingMapVerify, Error,
					TEXT("Pawn BicycleMesh relative location mismatch: actual=(%.3f, %.3f, %.3f), expected=(%.3f, %.3f, %.3f)."),
					ActualLocation.X, ActualLocation.Y, ActualLocation.Z,
					ExpectedLocation.X, ExpectedLocation.Y, ExpectedLocation.Z);
				bAllOk = false;
			}
			UE_LOG(LogCyclingMapVerify, Display,
				TEXT("Pawn BicycleMesh scale=(%.3f, %.3f, %.3f), location=(%.3f, %.3f, %.3f), mobility=%d."),
				ActualScale.X, ActualScale.Y, ActualScale.Z,
				ActualLocation.X, ActualLocation.Y, ActualLocation.Z,
				static_cast<int32>(Pawn->BicycleMesh->Mobility));
		}
		if (!Pawn->bAutoStart)
		{
			UE_LOG(LogCyclingMapVerify, Error, TEXT("Pawn bAutoStart is false (expected true for Slice A)."));
			bAllOk = false;
		}
	}

	UE_LOG(LogCyclingMapVerify, Display, TEXT("Static verification: %s."),
		bAllOk ? TEXT("PASS") : TEXT("FAIL"));

	if (DriveSeconds > 0.0f && Pawn)
	{
		UE_LOG(LogCyclingMapVerify, Display, TEXT("Driving simulation for %.1f s on saved map pawn..."), DriveSeconds);
		Pawn->bAutoStart = false; // we will start manually so we control the trigger
		Pawn->InitializeRide();
		Pawn->StartRide();

		const float FrameDt = 1.0f / 60.0f;
		double Elapsed = 0.0;
		int32 TotalSteps = 0;
		double LastReport = 0.0;
		while (Elapsed < DriveSeconds)
		{
			Pawn->Tick(FrameDt);
			Elapsed += FrameDt;
			if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Finished)
			{
				UE_LOG(LogCyclingMapVerify, Display, TEXT("Lifecycle reached Finished at t=%.2f s."), Elapsed);
				break;
			}
			if (Elapsed - LastReport >= 5.0)
			{
				LastReport = Elapsed;
				const FSimulationState& S = Pawn->GetAuthoritativeState();
				UE_LOG(LogCyclingMapVerify, Display,
					TEXT("  t=%.1f s: lifecycle=%d, speed=%.3f m/s, distance=%.3f m, elapsed=%.3f s, x=%.1f cm."),
					Elapsed, static_cast<int32>(Pawn->GetLifecycle()),
					S.SpeedMps, S.DistanceM, S.ElapsedTimeS,
					Pawn->GetActorLocation().X);
			}
		}

		const FSimulationState& Final = Pawn->GetAuthoritativeState();
		UE_LOG(LogCyclingMapVerify, Display, TEXT("Drive complete: lifecycle=%d, speed=%.3f m/s, distance=%.3f m, elapsed=%.3f s, visible x=%.1f cm (spline end at 50000.0 cm)."),
			static_cast<int32>(Pawn->GetLifecycle()),
			Final.SpeedMps, Final.DistanceM, Final.ElapsedTimeS,
			Pawn->GetActorLocation().X);

		// If we drove until Finished, confirm authoritative distance can
		// have a small fixed-step overshoot but the visible X is clamped to
		// the spline end.
		if (Pawn->GetLifecycle() == ECyclingPrototypeLifecycle::Finished)
		{
			if (Final.DistanceM >= 500.0 && Final.DistanceM <= 510.0)
			{
				UE_LOG(LogCyclingMapVerify, Display,
					TEXT("Finished DistanceM overshoot %.3f m is within (500, 510] m contract."),
					Final.DistanceM);
			}
			else
			{
				UE_LOG(LogCyclingMapVerify, Error,
					TEXT("Finished DistanceM %.3f m is outside expected (500, 510] m contract."),
					Final.DistanceM);
				bAllOk = false;
			}
			if (FMath::IsNearlyEqual(Pawn->GetActorLocation().X, 50000.0f, 0.5f))
			{
				UE_LOG(LogCyclingMapVerify, Display,
					TEXT("Finished visible X = %.2f cm (clamped to spline end 50000 cm)."),
					Pawn->GetActorLocation().X);
			}
			else
			{
				UE_LOG(LogCyclingMapVerify, Error,
					TEXT("Finished visible X = %.2f cm NOT clamped to spline end 50000 cm."),
					Pawn->GetActorLocation().X);
				bAllOk = false;
			}
			if (!Pawn->IsActorTickEnabled())
			{
				UE_LOG(LogCyclingMapVerify, Display, TEXT("Finished Tick is disabled."));
			}
			else
			{
				UE_LOG(LogCyclingMapVerify, Error, TEXT("Finished Tick is still enabled."));
				bAllOk = false;
			}
		}
		else
		{
			UE_LOG(LogCyclingMapVerify, Error,
				TEXT("Pawn did not reach Finished within %.1f supplied seconds."), DriveSeconds);
			bAllOk = false;
		}
	}

	UE_LOG(LogCyclingMapVerify, Display, TEXT("CyclingPrototypeMapVerifyCommandlet: %s."),
		bAllOk ? TEXT("OK") : TEXT("FAILED"));
	return bAllOk ? 0 : 1;
}

#endif // WITH_EDITOR
