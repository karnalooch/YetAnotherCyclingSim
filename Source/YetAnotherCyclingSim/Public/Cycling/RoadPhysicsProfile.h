#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "CoreTypes.h"

namespace CyclingRoadPhysics
{
	// Authoritative route-local road sample at distance S.
	//
	// Curvatures use inverse metres (1/m). BankAngleRad uses radians.
	// Wetness is normalized to [0, 1]. Roughness is a non-negative
	// dimensionless metadata value whose detailed physical effect is post-MVP.
	struct YETANOTHERCYCLINGSIM_API FRoadPhysicsSampleDefinition
	{
		double DistanceM = 0.0;
		double ElevationM = 0.0;
		double GradeDecimal = 0.0;
		double HorizontalCurvaturePerM = 0.0;
		double VerticalCurvaturePerM = 0.0;
		double RoadWidthM = 0.0;
		double BankAngleRad = 0.0;
		FString SurfaceId;
		double Wetness = 0.0;
		double Roughness = 0.0;
	};

	class YETANOTHERCYCLINGSIM_API FRoadPhysicsSample
	{
	public:
		double GetDistanceM() const { return DistanceM; }
		double GetElevationM() const { return ElevationM; }
		double GetGradeDecimal() const { return GradeDecimal; }
		double GetHorizontalCurvaturePerM() const { return HorizontalCurvaturePerM; }
		double GetVerticalCurvaturePerM() const { return VerticalCurvaturePerM; }
		double GetRoadWidthM() const { return RoadWidthM; }
		double GetBankAngleRad() const { return BankAngleRad; }
		const FString& GetSurfaceId() const { return SurfaceId; }
		double GetWetness() const { return Wetness; }
		double GetRoughness() const { return Roughness; }

	private:
		friend class FRoadPhysicsProfile;

		double DistanceM = 0.0;
		double ElevationM = 0.0;
		double GradeDecimal = 0.0;
		double HorizontalCurvaturePerM = 0.0;
		double VerticalCurvaturePerM = 0.0;
		double RoadWidthM = 0.0;
		double BankAngleRad = 0.0;
		FString SurfaceId;
		double Wetness = 0.0;
		double Roughness = 0.0;
	};

	// Interpolated physical road state at route-local coordinates S/D.
	struct YETANOTHERCYCLINGSIM_API FRoadPhysicsState
	{
		double DistanceM = 0.0;
		double LateralPositionM = 0.0;
		double ElevationM = 0.0;
		double GradeDecimal = 0.0;
		double HorizontalCurvaturePerM = 0.0;
		double VerticalCurvaturePerM = 0.0;
		double RoadWidthM = 0.0;
		double BankAngleRad = 0.0;
		FString SurfaceId;
		double Wetness = 0.0;
		double Roughness = 0.0;

		double GetLeftEdgeM() const { return -0.5 * RoadWidthM; }
		double GetRightEdgeM() const { return 0.5 * RoadWidthM; }
	};

	// Explicit authoring-quality continuity limits.
	//
	// No hidden road-design thresholds live in FRoadPhysicsProfile. Callers
	// choose limits appropriate for the authored/generated route.
	struct YETANOTHERCYCLINGSIM_API FRoadPhysicsTransitionLimits
	{
		double MaxAbsGradeChangePerM = 0.0;
		double MaxAbsHorizontalCurvatureChangePerM2 = 0.0;
		double MaxAbsBankAngleChangeRadPerM = 0.0;
	};

	// Rendering-independent canonical physical road profile.
	//
	// Samples are ordered by S (route distance). Numeric fields interpolate
	// linearly. Surface ids use left-closed/right-open interval semantics.
	class YETANOTHERCYCLINGSIM_API FRoadPhysicsProfile
	{
	public:
		FRoadPhysicsProfile() = default;

		// Transactional configuration. On failure a previous valid profile is
		// preserved.
		//
		// Requirements:
		// - non-empty trimmed name;
		// - at least two samples;
		// - first sample exactly at S=0;
		// - strictly increasing finite S;
		// - all numeric fields finite;
		// - road width > 0;
		// - bank angle strictly inside (-pi/2, pi/2);
		// - non-empty trimmed SurfaceId;
		// - Wetness in [0, 1];
		// - Roughness >= 0.
		bool TryConfigure(
			const FString& InName,
			const TArray<FRoadPhysicsSampleDefinition>& InSamples,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }
		const FString& GetName() const { return Name; }
		const TArray<FRoadPhysicsSample>& GetSamples() const { return Samples; }
		double GetTotalLengthM() const;

		// Query physical road state at route-local coordinates S/D.
		bool TryGetStateAt(
			double DistanceM,
			double LateralPositionM,
			FRoadPhysicsState& OutState,
			FString& OutError) const;

		// Deterministic look-ahead. Target S clamps to the route end.
		bool TryGetStateAhead(
			double DistanceM,
			double LookAheadM,
			double LateralPositionM,
			FRoadPhysicsState& OutState,
			FString& OutError) const;

		// Validates configured transition rates against caller-provided limits.
		bool TryValidateTransitionRates(
			const FRoadPhysicsTransitionLimits& Limits,
			FString& OutError) const;

	private:
		FString Name;
		TArray<FRoadPhysicsSample> Samples;
		bool bIsConfigured = false;
	};
}
