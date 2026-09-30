#include "Cycling/RouteProfile.h"

#include <cmath>

namespace CyclingSimulation
{
	double FRouteSegment::GetElevationChangeM() const
	{
		return LengthM * std::sin(std::atan(GradeDecimal));
	}

	bool FRouteProfile::TryConfigure(
		const FString& InName,
		const TArray<FRouteSegmentDefinition>& InSegments,
		FString& OutError)
	{
		OutError.Reset();

		const FString TrimmedName = InName.TrimStartAndEnd();
		if (TrimmedName.IsEmpty())
		{
			OutError = TEXT("route profile name must not be empty");
			return false;
		}
		if (InSegments.Num() == 0)
		{
			OutError = TEXT("route profile must contain at least one segment");
			return false;
		}

		TArray<FRouteSegment> CandidateSegments;
		CandidateSegments.Reserve(InSegments.Num());

		double RunningDistanceM = 0.0;
		for (int32 Index = 0; Index < InSegments.Num(); ++Index)
		{
			const FRouteSegmentDefinition& Definition = InSegments[Index];
			const FString TrimmedId = Definition.Id.TrimStartAndEnd();

			if (TrimmedId.IsEmpty())
			{
				OutError = FString::Printf(TEXT("route segment %d id must not be empty"), Index);
				return false;
			}
			if (!std::isfinite(Definition.LengthM) || Definition.LengthM <= 0.0)
			{
				OutError = FString::Printf(
					TEXT("route segment '%s' length must be finite and greater than zero"),
					*TrimmedId);
				return false;
			}
			if (!std::isfinite(Definition.GradeDecimal))
			{
				OutError = FString::Printf(
					TEXT("route segment '%s' grade must be finite"),
					*TrimmedId);
				return false;
			}

			for (const FRouteSegment& Existing : CandidateSegments)
			{
				if (Existing.GetId() == TrimmedId)
				{
					OutError = FString::Printf(
						TEXT("route segment id '%s' must be unique"),
						*TrimmedId);
					return false;
				}
			}

			const double EndDistanceM = RunningDistanceM + Definition.LengthM;
			if (!std::isfinite(EndDistanceM))
			{
				OutError = FString::Printf(
					TEXT("route cumulative distance became non-finite at segment '%s'"),
					*TrimmedId);
				return false;
			}

			FRouteSegment Segment;
			Segment.Id = TrimmedId;
			Segment.StartDistanceM = RunningDistanceM;
			Segment.EndDistanceM = EndDistanceM;
			Segment.LengthM = Definition.LengthM;
			Segment.GradeDecimal = Definition.GradeDecimal;
			CandidateSegments.Add(Segment);

			RunningDistanceM = EndDistanceM;
		}

		Name = TrimmedName;
		Segments = MoveTemp(CandidateSegments);
		bIsConfigured = true;
		return true;
	}

	double FRouteProfile::GetTotalLengthM() const
	{
		return Segments.Num() > 0 ? Segments.Last().GetEndDistanceM() : 0.0;
	}

	double FRouteProfile::GetTotalElevationChangeM() const
	{
		double TotalM = 0.0;
		for (const FRouteSegment& Segment : Segments)
		{
			TotalM += Segment.GetElevationChangeM();
		}
		return TotalM;
	}

	double FRouteProfile::GetTotalAscentM() const
	{
		double TotalM = 0.0;
		for (const FRouteSegment& Segment : Segments)
		{
			const double ElevationChangeM = Segment.GetElevationChangeM();
			if (ElevationChangeM > 0.0)
			{
				TotalM += ElevationChangeM;
			}
		}
		return TotalM;
	}

	double FRouteProfile::GetTotalDescentM() const
	{
		double TotalM = 0.0;
		for (const FRouteSegment& Segment : Segments)
		{
			const double ElevationChangeM = Segment.GetElevationChangeM();
			if (ElevationChangeM < 0.0)
			{
				TotalM -= ElevationChangeM;
			}
		}
		return TotalM;
	}

	bool FRouteProfile::TryGetSegmentAtDistance(
		double DistanceM,
		const FRouteSegment*& OutSegment,
		int32& OutSegmentIndex,
		FString& OutError) const
	{
		OutError.Reset();
		OutSegment = nullptr;
		OutSegmentIndex = INDEX_NONE;

		if (!bIsConfigured)
		{
			OutError = TEXT("route profile is not configured");
			return false;
		}
		if (!std::isfinite(DistanceM))
		{
			OutError = TEXT("route distance must be finite");
			return false;
		}
		if (DistanceM < 0.0)
		{
			OutError = TEXT("route distance must not be negative");
			return false;
		}

		const double TotalLengthM = GetTotalLengthM();
		if (DistanceM > TotalLengthM)
		{
			OutError = FString::Printf(
				TEXT("route distance must not exceed total route length %.6f m"),
				TotalLengthM);
			return false;
		}

		for (int32 Index = 0; Index < Segments.Num(); ++Index)
		{
			const FRouteSegment& Segment = Segments[Index];
			if (DistanceM < Segment.GetEndDistanceM())
			{
				OutSegment = &Segment;
				OutSegmentIndex = Index;
				return true;
			}
		}

		OutSegmentIndex = Segments.Num() - 1;
		OutSegment = &Segments[OutSegmentIndex];
		return true;
	}
}
