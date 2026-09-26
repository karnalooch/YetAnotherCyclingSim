#include "Cycling/Stage3GRouteExclusion.h"

#include "Math/UnrealMathUtility.h"

#include <cmath>
#include <limits>

namespace CyclingStage3G
{
	namespace
	{
		bool IsStage3GFiniteVector(const FVector& Value)
		{
			return std::isfinite(Value.X)
				&& std::isfinite(Value.Y)
				&& std::isfinite(Value.Z);
		}

		double HorizontalDistanceToSegmentM(
			const FVector& Candidate,
			const FVector& A,
			const FVector& B)
		{
			const double SegmentX = B.X - A.X;
			const double SegmentY = B.Y - A.Y;
			const double SegmentLengthSquared =
				SegmentX * SegmentX + SegmentY * SegmentY;

			double ClosestX = A.X;
			double ClosestY = A.Y;
			if (SegmentLengthSquared > 0.0)
			{
				const double CandidateX = Candidate.X - A.X;
				const double CandidateY = Candidate.Y - A.Y;
				const double Projection =
					(CandidateX * SegmentX + CandidateY * SegmentY)
					/ SegmentLengthSquared;
				const double T = FMath::Clamp(Projection, 0.0, 1.0);
				ClosestX = A.X + T * SegmentX;
				ClosestY = A.Y + T * SegmentY;
			}

			const double DeltaX = Candidate.X - ClosestX;
			const double DeltaY = Candidate.Y - ClosestY;
			return std::sqrt(DeltaX * DeltaX + DeltaY * DeltaY);
		}
	}

	bool TryEvaluateRouteExclusion(
		const CyclingSimulation::FRouteGeometryProfile& RouteGeometry,
		const FVector& CandidatePositionM,
		double ProtectedHalfWidthM,
		FRouteExclusionResult& OutResult,
		FString& OutError)
	{
		OutResult = FRouteExclusionResult{};
		OutError.Reset();

		if (!RouteGeometry.IsConfigured())
		{
			OutError = TEXT("route exclusion requires configured route geometry");
			return false;
		}
		if (!IsStage3GFiniteVector(CandidatePositionM))
		{
			OutError = TEXT("route exclusion candidate position must be finite");
			return false;
		}
		if (!std::isfinite(ProtectedHalfWidthM) || ProtectedHalfWidthM <= 0.0)
		{
			OutError = TEXT("route exclusion protected half-width must be finite and greater than zero");
			return false;
		}

		const TArray<CyclingSimulation::FRouteGeometrySample>& Samples =
			RouteGeometry.GetSamples();
		if (Samples.Num() < 2)
		{
			OutError = TEXT("route exclusion requires at least two route geometry samples");
			return false;
		}

		double MinDistanceM = std::numeric_limits<double>::infinity();
		for (int32 Index = 1; Index < Samples.Num(); ++Index)
		{
			const double DistanceM = HorizontalDistanceToSegmentM(
				CandidatePositionM,
				Samples[Index - 1].PositionM,
				Samples[Index].PositionM);
			if (!std::isfinite(DistanceM))
			{
				OutError = FString::Printf(
					TEXT("route exclusion produced non-finite distance for segment %d"),
					Index - 1);
				return false;
			}
			MinDistanceM = FMath::Min(MinDistanceM, DistanceM);
		}

		if (!std::isfinite(MinDistanceM))
		{
			OutError = TEXT("route exclusion could not resolve route distance");
			return false;
		}

		OutResult.HorizontalDistanceToRouteM = MinDistanceM;
		OutResult.ProtectedHalfWidthM = ProtectedHalfWidthM;
		OutResult.ClearanceFromProtectedCorridorM =
			MinDistanceM - ProtectedHalfWidthM;
		OutResult.bExcluded = MinDistanceM <= ProtectedHalfWidthM;
		return true;
	}
}
