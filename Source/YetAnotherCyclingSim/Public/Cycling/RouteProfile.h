#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "CoreTypes.h"

namespace CyclingSimulation
{
	// Input definition for one ordered route segment.
	//
	// LengthM is measured along the road surface in metres (m).
	// GradeDecimal is rise/run as a decimal fraction (unitless).
	struct YETANOTHERCYCLINGSIM_API FRouteSegmentDefinition
	{
		FString Id;
		double LengthM = 0.0;
		double GradeDecimal = 0.0;
	};

	// Configured immutable-by-interface route segment with derived route bounds.
	//
	// StartDistanceM is inclusive. EndDistanceM is exclusive for every segment
	// except that the final route distance resolves to the final segment.
	class YETANOTHERCYCLINGSIM_API FRouteSegment
	{
	public:
		FRouteSegment() = default;
		const FString& GetId() const { return Id; }
		double GetStartDistanceM() const { return StartDistanceM; }
		double GetEndDistanceM() const { return EndDistanceM; }
		double GetLengthM() const { return LengthM; }
		double GetGradeDecimal() const { return GradeDecimal; }

		// Vertical elevation change in metres (m), derived from surface length
		// and rise/run grade using LengthM * sin(atan(GradeDecimal)).
		double GetElevationChangeM() const;

	private:
		friend class FRouteProfile;

		FString Id;
		double StartDistanceM = 0.0;
		double EndDistanceM = 0.0;
		double LengthM = 0.0;
		double GradeDecimal = 0.0;
	};

	// Pure, rendering-independent ordered route profile.
	//
	// The profile owns one deterministic route-distance domain. It does not
	// depend on Actor transforms, spline components, levels, rendering or
	// system time. Stage 3C may derive geometry from this contract, but must
	// not replace authoritative DistanceM with presentation state.
	class YETANOTHERCYCLINGSIM_API FRouteProfile
	{
	public:
		FRouteProfile() = default;
		// Transactionally configures an ordered route profile.
		//
		// Requirements:
		// - Name must be non-empty after trimming;
		// - at least one segment is required;
		// - segment Ids must be non-empty after trimming and unique;
		// - LengthM must be finite and > 0;
		// - GradeDecimal must be finite;
		// - cumulative route distances must remain finite.
		//
		// On failure, any previous valid configuration is preserved.
		bool TryConfigure(
			const FString& InName,
			const TArray<FRouteSegmentDefinition>& InSegments,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }
		const FString& GetName() const { return Name; }
		const TArray<FRouteSegment>& GetSegments() const { return Segments; }

		double GetTotalLengthM() const;
		double GetTotalElevationChangeM() const;
		double GetTotalAscentM() const;
		double GetTotalDescentM() const;

		// Resolves the segment containing DistanceM.
		//
		// DistanceM must be finite and in [0, TotalLengthM].
		// Boundary semantics match the Python reference:
		// - 0 m -> first segment;
		// - exact interior boundary -> next segment;
		// - exact TotalLengthM -> final segment.
		bool TryGetSegmentAtDistance(
			double DistanceM,
			const FRouteSegment*& OutSegment,
			int32& OutSegmentIndex,
			FString& OutError) const;

	private:
		FString Name;
		TArray<FRouteSegment> Segments;
		bool bIsConfigured = false;
	};
}
