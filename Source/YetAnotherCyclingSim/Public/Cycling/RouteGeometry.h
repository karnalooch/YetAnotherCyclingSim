#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "Math/Vector.h"

namespace CyclingSimulation
{
	struct YETANOTHERCYCLINGSIM_API FRouteGeometrySample
	{
		double DistanceM = 0.0;
		FVector PositionM = FVector::ZeroVector;
	};

	// Pure route geometry sampled in SI units.
	//
	// DistanceM is authoritative route-surface distance. PositionM is a
	// deterministic geometric embedding in metres and is never read back from
	// an Actor transform. Adjacent samples form the geometry polyline used by
	// Stage 3 for deterministic grade derivation and editor spline generation.
	class YETANOTHERCYCLINGSIM_API FRouteGeometryProfile
	{
	public:
		FRouteGeometryProfile() = default;

		// Transactionally accepts an ordered sample set.
		//
		// Requirements:
		// - at least two samples;
		// - first sample at exactly 0 m;
		// - finite, strictly increasing route distances;
		// - finite positions;
		// - no degenerate geometric intervals;
		// - geometric 3D interval length must agree with route-distance delta
		//   within LengthToleranceM.
		bool TryConfigure(
			const TArray<FRouteGeometrySample>& InSamples,
			double LengthToleranceM,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }
		const TArray<FRouteGeometrySample>& GetSamples() const { return Samples; }
		double GetTotalLengthM() const;

		// Linearly interpolates geometry at authoritative route distance.
		bool TrySamplePosition(
			double DistanceM,
			FVector& OutPositionM,
			FString& OutError) const;

		// Derives grade as rise/run from the geometry polyline inside
		// [DistanceM-HalfWindowM, DistanceM+HalfWindowM], clamped to route ends.
		// Horizontal run is accumulated along the polyline, not measured as one
		// straight chord, so curved road geometry does not inflate grade.
		bool TryCalculateGrade(
			double DistanceM,
			double HalfWindowM,
			double& OutGradeDecimal,
			FString& OutError) const;

	private:
		TArray<FRouteGeometrySample> Samples;
		bool bIsConfigured = false;
	};
}
