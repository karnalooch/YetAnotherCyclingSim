#include "Cycling/CyclingStage3RouteVerifyCommandlet.h"

#if WITH_EDITOR

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/CyclingPrototypePawn.h"

#include "Components/SplineComponent.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "UObject/Package.h"

DEFINE_LOG_CATEGORY_STATIC(LogCyclingStage3RouteVerify, Log, All);

namespace CyclingStage3RouteVerifyInternal
{
	const TCHAR* MapPackagePath = TEXT("/Game/Prototype/Maps/L_CyclingTest");
	constexpr double MetresToCentimetres = 100.0;

	bool IsFiniteVector(const FVector& Value)
	{
		return FMath::IsFinite(Value.X)
			&& FMath::IsFinite(Value.Y)
			&& FMath::IsFinite(Value.Z);
	}
}

UCyclingStage3RouteVerifyCommandlet::UCyclingStage3RouteVerifyCommandlet()
{
	IsClient = false;
	IsServer = false;
	IsEditor = true;
	LogToConsole = true;
}

int32 UCyclingStage3RouteVerifyCommandlet::Main(const FString& Params)
{
	using namespace CyclingSimulation;
	using namespace CyclingStage3RouteVerifyInternal;

	UE_LOG(LogCyclingStage3RouteVerify, Display,
		TEXT("CyclingStage3RouteVerifyCommandlet: starting fresh-load verification."));

	UPackage* MapPackage = LoadPackage(nullptr, MapPackagePath, LOAD_None);
	if (!MapPackage)
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Failed to load map package '%s'."), MapPackagePath);
		return 1;
	}

	UWorld* MapWorld = UWorld::FindWorldInPackage(MapPackage);
	if (!MapWorld)
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Map package '%s' does not contain a UWorld."), MapPackagePath);
		return 1;
	}
	MapWorld->WorldType = EWorldType::Editor;

	AActor* RouteActor = nullptr;
	USplineComponent* Spline = nullptr;
	ACyclingPrototypePawn* Pawn = nullptr;
	int32 RouteActorCount = 0;
	int32 PawnCount = 0;

	for (AActor* Actor : MapWorld->GetCurrentLevel()->Actors)
	{
		if (!IsValid(Actor))
		{
			continue;
		}

		if (ACyclingPrototypePawn* CandidatePawn =
			Cast<ACyclingPrototypePawn>(Actor))
		{
			++PawnCount;
			Pawn = CandidatePawn;
			continue;
		}

		TArray<USplineComponent*> Splines;
		Actor->GetComponents<USplineComponent>(Splines);
		if (Splines.Num() == 0)
		{
			continue;
		}
		++RouteActorCount;
		if (Splines.Num() != 1)
		{
			UE_LOG(LogCyclingStage3RouteVerify, Error,
				TEXT("Route actor '%s' has %d splines; exactly one required."),
				*Actor->GetName(),
				Splines.Num());
			return 1;
		}
		RouteActor = Actor;
		Spline = Splines[0];
	}

	if (RouteActorCount != 1 || !IsValid(RouteActor) || !IsValid(Spline))
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Expected one route actor; found %d."), RouteActorCount);
		return 1;
	}
	if (PawnCount != 1 || !IsValid(Pawn))
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Expected one cycling Pawn; found %d."), PawnCount);
		return 1;
	}
	if (Pawn->RouteActor != RouteActor)
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Pawn RouteActor does not reference the verified Stage 3 route actor."));
		return 1;
	}

	FRouteGeometryProfile ExpectedGeometry;
	FString Error;
	if (!TryBuildAlpineJourneyRouteGeometry(ExpectedGeometry, Error))
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Failed to build expected geometry: %s"), *Error);
		return 1;
	}

	const TArray<FRouteGeometrySample>& ExpectedSamples =
		ExpectedGeometry.GetSamples();
	const int32 ActualPointCount = Spline->GetNumberOfSplinePoints();
	if (ActualPointCount != ExpectedSamples.Num())
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Spline point count mismatch: actual=%d expected=%d."),
			ActualPointCount,
			ExpectedSamples.Num());
		return 1;
	}

	const double ExpectedLengthCm =
		ExpectedGeometry.GetTotalLengthM() * MetresToCentimetres;
	const double ActualLengthCm =
		static_cast<double>(Spline->GetSplineLength());
	if (!FMath::IsNearlyEqual(ActualLengthCm, ExpectedLengthCm, 1.0))
	{
		UE_LOG(LogCyclingStage3RouteVerify, Error,
			TEXT("Spline length mismatch: actual=%.3f cm expected=%.3f cm."),
			ActualLengthCm,
			ExpectedLengthCm);
		return 1;
	}

	const int32 RepresentativeIndices[] = {
		0,
		65,
		100,
		535,
		755,
		925,
		1000,
	};
	for (const int32 Index : RepresentativeIndices)
	{
		const FVector ActualLocalCm =
			Spline->GetLocationAtSplinePoint(
				Index,
				ESplineCoordinateSpace::Local);
		const FVector ExpectedLocalCm =
			ExpectedSamples[Index].PositionM * MetresToCentimetres;

		if (!CyclingStage3RouteVerifyInternal::IsFiniteVector(ActualLocalCm))
		{
			UE_LOG(LogCyclingStage3RouteVerify, Error,
				TEXT("Spline point %d contains non-finite coordinates."), Index);
			return 1;
		}
		if (!ActualLocalCm.Equals(ExpectedLocalCm, 0.1))
		{
			UE_LOG(LogCyclingStage3RouteVerify, Error,
				TEXT("Spline point %d differs from deterministic geometry."), Index);
			return 1;
		}
		if (Spline->GetSplinePointType(Index) != ESplinePointType::Linear)
		{
			UE_LOG(LogCyclingStage3RouteVerify, Error,
				TEXT("Spline point %d is not Linear; exact geometry preservation is required."), Index);
			return 1;
		}
	}

	for (double DistanceCm = 0.0;
		DistanceCm <= ActualLengthCm;
		DistanceCm += 10000.0)
	{
		const FVector Location =
			Spline->GetLocationAtDistanceAlongSpline(
				static_cast<float>(DistanceCm),
				ESplineCoordinateSpace::Local);
		const FVector Tangent =
			Spline->GetTangentAtDistanceAlongSpline(
				static_cast<float>(DistanceCm),
				ESplineCoordinateSpace::Local);
		if (!CyclingStage3RouteVerifyInternal::IsFiniteVector(Location)
			|| !CyclingStage3RouteVerifyInternal::IsFiniteVector(Tangent)
			|| Tangent.IsNearlyZero())
		{
			UE_LOG(LogCyclingStage3RouteVerify, Error,
				TEXT("Invalid route sample at spline distance %.3f cm."),
				DistanceCm);
			return 1;
		}
	}

	UE_LOG(LogCyclingStage3RouteVerify, Display,
		TEXT("Stage 3 route verified after reload: actor='%s' points=%d length=%.3f m."),
		*RouteActor->GetName(),
		ActualPointCount,
		ActualLengthCm / MetresToCentimetres);
	UE_LOG(LogCyclingStage3RouteVerify, Display,
		TEXT("CyclingStage3RouteVerifyCommandlet: PASS."));
	return 0;
}

#endif // WITH_EDITOR
