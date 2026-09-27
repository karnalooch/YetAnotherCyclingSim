#pragma once

#include "CoreTypes.h"
#include "Containers/UnrealString.h"

#include "Cycling/Cornering.h"
#include "Cycling/RoadPhysicsProfile.h"

namespace CyclingCornerContext
{
	enum class ECornerDirection : uint8
	{
		Straight,
		Left,
		Right,
	};

	// Explicit Stage 4B-A scanning policy.
	//
	// These values are supplied by the caller so corner detection and
	// look-ahead never depend on hidden road-design thresholds.
	struct YETANOTHERCYCLINGSIM_API FCornerContextSettings
	{
		double MinAbsCurvaturePerM = 0.0;
		double ScanStepM = 0.0;
		double LookAheadM = 0.0;
		double ApproachLengthM = 0.0;
	};

	// Rendering-independent road context available to one fixed-step query.
	//
	// Surface/wetness/roughness are metadata only in 4B-A. This contract does
	// not resolve tyre friction or the shared braking/cornering grip budget;
	// that remains Stage 4B-B/4C.
	struct YETANOTHERCYCLINGSIM_API FCornerContext
	{
		double DistanceM = 0.0;
		double LateralPositionM = 0.0;
		CyclingCornering::ECornerPhase Phase = CyclingCornering::ECornerPhase::Outside;
		bool bHasCorner = false;
		double CornerStartM = 0.0;
		double CornerEndM = 0.0;
		double DistanceToCornerStartM = 0.0;
		double ApexDistanceM = 0.0;
		ECornerDirection Direction = ECornerDirection::Straight;
		double SignedCurvaturePerM = 0.0;
		double CenterlineRadiusM = 0.0;
		double EffectiveRadiusM = 0.0;
		double RoadWidthM = 0.0;
		double LeftMarginM = 0.0;
		double RightMarginM = 0.0;
		double CrossSlopeAngleRad = 0.0;
		FString SurfaceId;
		double Wetness = 0.0;
		double Roughness = 0.0;
	};

	// Derives deterministic corner context directly from the canonical
	// Road Physics Profile at route-local S/D.
	//
	// Positive signed curvature turns toward +D (rider right); negative signed
	// curvature turns toward -D (rider left). For a centerline signed radius
	// R=1/k, a route-local lateral displacement D uses R-D, so moving toward
	// the inside of a corner tightens the effective radius.
	YETANOTHERCYCLINGSIM_API bool TryBuildCornerContext(
		const CyclingRoadPhysics::FRoadPhysicsProfile& Profile,
		double DistanceM,
		double LateralPositionM,
		const FCornerContextSettings& Settings,
		FCornerContext& OutContext,
		FString& OutError);
}
