#pragma once

#include "CoreMinimal.h"

#include "Cycling/RouteGeometry.h"

namespace CyclingStage3G
{
	enum class EStage3GForestLayer : uint8
	{
		Primary,
		Background,
		Understory,
	};

	struct YETANOTHERCYCLINGSIM_API FStage3GForestLayoutConfig
	{
		double StartDistanceM = 3700.0;
		double EndDistanceM = 6200.0;
		double BaseDensity = 0.84;

		double PrimaryStationSpacingM = 20.0;
		int32 PrimaryPointsPerSidePerStation = 4;
		double PrimaryMinLateralOffsetM = 10.0;
		double PrimaryMaxLateralOffsetM = 36.0;
		double PrimaryMinUniformScale = 0.95;
		double PrimaryMaxUniformScale = 1.35;

		double ProtectedRouteHalfWidthM = 4.0;
		int32 GenerationSeed = 42017;
		int32 LayerProfileVersion = 2;
	};

	struct YETANOTHERCYCLINGSIM_API FStage3GForestCandidate
	{
		EStage3GForestLayer Layer = EStage3GForestLayer::Primary;
		double RouteDistanceM = 0.0;
		double SignedLateralOffsetM = 0.0;
		FVector PositionM = FVector::ZeroVector;
		double UniformScale = 1.0;
		double YawDeg = 0.0;
		int32 Seed = 0;
	};

	struct YETANOTHERCYCLINGSIM_API FStage3GForestLayoutStats
	{
		double ExpectedCandidateMean = 0.0;
		int32 ReserveCount = 0;
		int32 GeneratedCount = 0;
		int32 PrimaryCount = 0;
		int32 BackgroundCount = 0;
		int32 UnderstoryCount = 0;
	};

	YETANOTHERCYCLINGSIM_API FStage3GForestLayoutConfig
		MakeTargetDensityForestConfig();

	YETANOTHERCYCLINGSIM_API const TCHAR* Stage3GForestLayerName(
		EStage3GForestLayer Layer);

	YETANOTHERCYCLINGSIM_API bool TryGenerateForestLayout(
		const CyclingSimulation::FRouteGeometryProfile& RouteGeometry,
		const FStage3GForestLayoutConfig& Config,
		TArray<FStage3GForestCandidate>& OutCandidates,
		FStage3GForestLayoutStats& OutStats,
		FString& OutError);
}
