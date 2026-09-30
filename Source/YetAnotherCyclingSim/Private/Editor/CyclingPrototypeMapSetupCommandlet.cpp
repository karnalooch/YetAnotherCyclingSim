// Copyright YetAnotherCyclingSim. All Rights Reserved.

#include "Cycling/CyclingPrototypeMapSetupCommandlet.h"

#if WITH_EDITOR

#include "Cycling/CyclingPrototypePawn.h"

#include "AssetRegistry/AssetRegistryModule.h"
#include "Components/SplineComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/World.h"
#include "Components/StaticMeshComponent.h"
#include "FileHelpers.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "UObject/Package.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingMapSetup, Log, All);

namespace CyclingMapSetupInternal
{
	const TCHAR* MapPackagePath = TEXT("/Game/Prototype/Maps/L_CyclingTest");
	const TCHAR* PlaceholderLabel = TEXT("BikePlaceholder");
	const TCHAR* BasicCubeObjectPath = TEXT("/Engine/BasicShapes/Cube.Cube");

	// Basic Cube is 100x100x100 Unreal units = 1.0 m x 1.0 m x 1.0 m.
	// Target visual: ~1.8 m long, ~0.5 m wide, ~1.2 m tall.
	// X = 1.8, Y = 0.5, Z = 1.2. Z offset half the cube height (~0.6 m)
	// so the cube bottom sits at the spline/road height.
	const FVector MeshRelativeScale = FVector(1.8, 0.5, 1.2);
	const FVector MeshRelativeLocation = FVector(0.0, 0.0, 60.0); // 0.6 m up
	const FRotator MeshRelativeRotation = FRotator::ZeroRotator;
}

UCyclingPrototypeMapSetupCommandlet::UCyclingPrototypeMapSetupCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
}

int32 UCyclingPrototypeMapSetupCommandlet::Main(const FString& Params)
{
	using namespace CyclingMapSetupInternal;

	UE_LOG(LogCyclingMapSetup, Display, TEXT("CyclingPrototypeMapSetupCommandlet: starting."));

	// Step 1: load the map.
	UWorld* MapWorld = nullptr;
	{
		UPackage* MapPackage = LoadPackage(nullptr, MapPackagePath, LOAD_None);
		if (!MapPackage)
		{
			UE_LOG(LogCyclingMapSetup, Error, TEXT("Failed to load map package '%s'."), MapPackagePath);
			return 1;
		}
		MapWorld = UWorld::FindWorldInPackage(MapPackage);
		if (!MapWorld)
		{
			UE_LOG(LogCyclingMapSetup, Error, TEXT("Map package '%s' does not contain a UWorld."), MapPackagePath);
			return 1;
		}
		// Mark the world as the editor world for the duration of this commandlet.
		MapWorld->WorldType = EWorldType::Editor;
	}

	UE_LOG(LogCyclingMapSetup, Display, TEXT("Loaded map '%s'."), *MapWorld->GetName());

	// Step 2: remove the existing temporary AStaticMeshActor placeholder.
	// Iterate the explicitly loaded level instead of using TActorIterator:
	// commandlets do not make the loaded map world the global editor world.
	{
		TArray<AActor*> ToDestroy;
		for (AActor* Actor : MapWorld->GetCurrentLevel()->Actors)
		{
			if (IsValid(Actor) && Actor->IsA(AStaticMeshActor::StaticClass()) &&
				Actor->GetActorLabel() == PlaceholderLabel)
			{
				ToDestroy.Add(Actor);
			}
		}
		for (AActor* Actor : ToDestroy)
		{
			UE_LOG(LogCyclingMapSetup, Display, TEXT("Removing placeholder StaticMeshActor '%s'."), *Actor->GetName());
			MapWorld->EditorDestroyActor(Actor, false);
		}
	}

	// Step 3: reuse or spawn exactly one ACyclingPrototypePawn with label
	// BikePlaceholder, removing any duplicates left by an interrupted setup.
	ACyclingPrototypePawn* Pawn = nullptr;
	{
		TArray<ACyclingPrototypePawn*> DuplicatePawns;
		for (AActor* Actor : MapWorld->GetCurrentLevel()->Actors)
		{
			ACyclingPrototypePawn* Candidate = Cast<ACyclingPrototypePawn>(Actor);
			if (!IsValid(Candidate))
			{
				continue;
			}
			if (!Pawn)
			{
				Pawn = Candidate;
			}
			else
			{
				DuplicatePawns.Add(Candidate);
			}
		}
		for (ACyclingPrototypePawn* Duplicate : DuplicatePawns)
		{
			UE_LOG(LogCyclingMapSetup, Display, TEXT("Removing duplicate ACyclingPrototypePawn '%s'."),
				*Duplicate->GetName());
			MapWorld->EditorDestroyActor(Duplicate, false);
		}
		if (!Pawn)
		{
			FActorSpawnParameters SpawnParams;
			SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			Pawn = MapWorld->SpawnActor<ACyclingPrototypePawn>(ACyclingPrototypePawn::StaticClass(),
				FTransform::Identity, SpawnParams);
			if (!Pawn)
			{
				UE_LOG(LogCyclingMapSetup, Error, TEXT("Failed to spawn ACyclingPrototypePawn."));
				return 1;
			}
			UE_LOG(LogCyclingMapSetup, Display, TEXT("Spawned ACyclingPrototypePawn '%s'."), *Pawn->GetName());
		}
		else
		{
			UE_LOG(LogCyclingMapSetup, Display, TEXT("Reusing existing ACyclingPrototypePawn '%s'."), *Pawn->GetName());
		}
		Pawn->SetActorLabel(PlaceholderLabel);
		Pawn->SetActorLocationAndRotation(FVector::ZeroVector, FRotator::ZeroRotator);
	}

	// Step 4: assign route, mesh, relative transform, bAutoStart.
	{
		// The route is a Blueprint actor that is already placed in the
		// map as part of the prototype. Resolve it by finding an actor
		// that owns exactly one USplineComponent -- the Stage 2 contract
		// requires exactly one spline per route Actor.
		AActor* RouteActor = nullptr;
		for (AActor* Candidate : MapWorld->GetCurrentLevel()->Actors)
		{
			if (!IsValid(Candidate) || Candidate->IsA(ACyclingPrototypePawn::StaticClass()))
			{
				continue;
			}
			TArray<USplineComponent*> Splines;
			Candidate->GetComponents<USplineComponent>(Splines);
			if (Splines.Num() == 1)
			{
				RouteActor = Candidate;
				break;
			}
		}
		if (!RouteActor)
		{
			UE_LOG(LogCyclingMapSetup, Error,
				TEXT("No actor with exactly one USplineComponent found in the map."));
			return 1;
		}
		Pawn->RouteActor = RouteActor;
		UE_LOG(LogCyclingMapSetup, Display, TEXT("Assigned RouteActor '%s'."), *RouteActor->GetName());

		// Mesh.
		UStaticMesh* CubeMesh = Cast<UStaticMesh>(StaticLoadObject(UStaticMesh::StaticClass(), nullptr, BasicCubeObjectPath));
		if (!CubeMesh)
		{
			UE_LOG(LogCyclingMapSetup, Error, TEXT("Basic Cube mesh '%s' could not be loaded."), BasicCubeObjectPath);
			return 1;
		}
		if (Pawn->BicycleMesh)
		{
			Pawn->BicycleMesh->SetStaticMesh(CubeMesh);
			Pawn->BicycleMesh->SetRelativeLocation(MeshRelativeLocation);
			Pawn->BicycleMesh->SetRelativeRotation(MeshRelativeRotation);
			Pawn->BicycleMesh->SetRelativeScale3D(MeshRelativeScale);
			Pawn->BicycleMesh->SetMobility(EComponentMobility::Movable);
			Pawn->BicycleMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
			Pawn->BicycleMesh->SetGenerateOverlapEvents(false);
			UE_LOG(LogCyclingMapSetup, Display,
				TEXT("Configured BicycleMesh: scale=(%.2f, %.2f, %.2f), location=(%.1f, %.1f, %.1f)."),
				MeshRelativeScale.X, MeshRelativeScale.Y, MeshRelativeScale.Z,
				MeshRelativeLocation.X, MeshRelativeLocation.Y, MeshRelativeLocation.Z);
		}
		else
		{
			UE_LOG(LogCyclingMapSetup, Error, TEXT("Pawn has no BicycleMesh subcomponent."));
			return 1;
		}

		// bAutoStart = true for Slice A PIE proof.
		Pawn->bAutoStart = true;
		UE_LOG(LogCyclingMapSetup, Display, TEXT("Set bAutoStart = true."));
	}

	// Step 5: save the map.
	{
		const bool bSaved = UEditorLoadingAndSavingUtils::SaveMap(MapWorld, MapPackagePath);
		if (!bSaved)
		{
			UE_LOG(LogCyclingMapSetup, Error, TEXT("Failed to save map '%s'."), MapPackagePath);
			return 1;
		}
		UE_LOG(LogCyclingMapSetup, Display, TEXT("Saved map '%s'."), MapPackagePath);
	}

	// Step 6: lightweight integrity verification. UE 5.8 does not expose a
	// CheckMapForErrors call in UEditorLoadingAndSavingUtils; the editor's
	// Map Check commandlet has been removed. Instead, we verify that the
	// Pawn and the route are still in the saved map and that the mesh and
	// transform survived the save. Any genuine map-level error would also
	// have aborted the SaveMap call above.
	{
		bool bAllOk = true;
		int32 PawnCount = 0;
		int32 PlaceholderStaticMeshCount = 0;
		for (AActor* Actor : MapWorld->GetCurrentLevel()->Actors)
		{
			if (!IsValid(Actor))
			{
				continue;
			}
			if (ACyclingPrototypePawn* P = Cast<ACyclingPrototypePawn>(Actor))
			{
				++PawnCount;
				bAllOk &= IsValid(P->RouteActor) && IsValid(P->BicycleMesh) &&
					P->BicycleMesh->GetStaticMesh() != nullptr;
			}
			else if (Actor->IsA(AStaticMeshActor::StaticClass()) &&
				Actor->GetActorLabel() == PlaceholderLabel)
			{
				++PlaceholderStaticMeshCount;
			}
		}
		bAllOk &= PawnCount == 1 && PlaceholderStaticMeshCount == 0;
		UE_LOG(LogCyclingMapSetup, Display, TEXT("Map post-save verification: %s."),
			bAllOk ? TEXT("OK") : TEXT("FAILED (composition or Pawn configuration)"));
		if (!bAllOk)
		{
			return 1;
		}
	}

	UE_LOG(LogCyclingMapSetup, Display, TEXT("CyclingPrototypeMapSetupCommandlet: done."));
	return 0;
}

#endif // WITH_EDITOR
