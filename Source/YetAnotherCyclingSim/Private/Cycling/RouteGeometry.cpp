#include "Cycling/RouteGeometry.h"

#include <cmath>

namespace CyclingSimulation
{
	namespace
	{
		bool IsFiniteVector(const FVector& Value)
		{
			return FMath::IsFinite(Value.X)
				&& FMath::IsFinite(Value.Y)
				&& FMath::IsFinite(Value.Z);
		}
	}

	bool FRouteGeometryProfile::TryConfigure(
		const TArray<FRouteGeometrySample>& InSamples,
		double LengthToleranceM,
		FString& OutError)
	{
		OutError.Reset();

		if (!std::isfinite(LengthToleranceM) || LengthToleranceM < 0.0)
		{
			OutError = TEXT("geometry length tolerance must be finite and non-negative");
			return false;
		}
		if (InSamples.Num() < 2)
		{
			OutError = TEXT("route geometry must contain at least two samples");
			return false;
		}
		if (InSamples[0].DistanceM != 0.0)
		{
			OutError = TEXT("first route geometry sample must be at exactly 0 m");
			return false;
		}

		for (int32 Index = 0; Index < InSamples.Num(); ++Index)
		{
			const FRouteGeometrySample& Sample = InSamples[Index];
			if (!std::isfinite(Sample.DistanceM) || Sample.DistanceM < 0.0)
			{
				OutError = FString::Printf(
					TEXT("route geometry sample %d distance must be finite and non-negative"),
					Index);
				return false;
			}
			if (!IsFiniteVector(Sample.PositionM))
			{
				OutError = FString::Printf(
					TEXT("route geometry sample %d position must be finite"),
					Index);
				return false;
			}

			if (Index == 0)
			{
				continue;
			}

			const FRouteGeometrySample& Previous = InSamples[Index - 1];
			const double RouteDeltaM = Sample.DistanceM - Previous.DistanceM;
			if (!(RouteDeltaM > 0.0))
			{
				OutError = FString::Printf(
					TEXT("route geometry sample %d distance must be strictly increasing"),
					Index);
				return false;
			}

			const double GeometryDeltaM = FVector::Distance(
				Sample.PositionM,
				Previous.PositionM);
			if (!std::isfinite(GeometryDeltaM) || GeometryDeltaM <= 0.0)
			{
				OutError = FString::Printf(
					TEXT("route geometry interval %d is degenerate"),
					Index - 1);
				return false;
			}
			if (FMath::Abs(GeometryDeltaM - RouteDeltaM) > LengthToleranceM)
			{
				OutError = FString::Printf(
					TEXT("route geometry interval %d length %.9f m differs from route delta %.9f m by more than tolerance %.9f m"),
					Index - 1,
					GeometryDeltaM,
					RouteDeltaM,
					LengthToleranceM);
				return false;
			}
		}

		Samples = InSamples;
		bIsConfigured = true;
		return true;
	}

	double FRouteGeometryProfile::GetTotalLengthM() const
	{
		return Samples.Num() > 0 ? Samples.Last().DistanceM : 0.0;
	}

	bool FRouteGeometryProfile::TrySamplePosition(
		double DistanceM,
		FVector& OutPositionM,
		FString& OutError) const
	{
		OutError.Reset();

		if (!bIsConfigured)
		{
			OutError = TEXT("route geometry is not configured");
			return false;
		}
		if (!std::isfinite(DistanceM))
		{
			OutError = TEXT("route geometry sample distance must be finite");
			return false;
		}
		if (DistanceM < 0.0 || DistanceM > GetTotalLengthM())
		{
			OutError = FString::Printf(
				TEXT("route geometry sample distance %.9f m is outside [0, %.9f]"),
				DistanceM,
				GetTotalLengthM());
			return false;
		}

		if (DistanceM == GetTotalLengthM())
		{
			OutPositionM = Samples.Last().PositionM;
			return true;
		}

		for (int32 Index = 1; Index < Samples.Num(); ++Index)
		{
			const FRouteGeometrySample& Right = Samples[Index];
			if (DistanceM <= Right.DistanceM)
			{
				const FRouteGeometrySample& Left = Samples[Index - 1];
				const double Denominator = Right.DistanceM - Left.DistanceM;
				const double Alpha = (DistanceM - Left.DistanceM) / Denominator;
				OutPositionM = FMath::Lerp(Left.PositionM, Right.PositionM, Alpha);
				return true;
			}
		}

		OutError = TEXT("route geometry lookup reached an invalid terminal state");
		return false;
	}

	bool FRouteGeometryProfile::TryCalculateGrade(
		double DistanceM,
		double HalfWindowM,
		double& OutGradeDecimal,
		FString& OutError) const
	{
		OutError.Reset();
		OutGradeDecimal = 0.0;

		if (!bIsConfigured)
		{
			OutError = TEXT("route geometry is not configured");
			return false;
		}
		if (!std::isfinite(DistanceM) || DistanceM < 0.0 || DistanceM > GetTotalLengthM())
		{
			OutError = TEXT("grade query distance must be finite and inside the route");
			return false;
		}
		if (!std::isfinite(HalfWindowM) || HalfWindowM <= 0.0)
		{
			OutError = TEXT("grade half-window must be finite and greater than zero");
			return false;
		}

		const double StartM = FMath::Max(0.0, DistanceM - HalfWindowM);
		const double EndM = FMath::Min(GetTotalLengthM(), DistanceM + HalfWindowM);
		if (!(EndM > StartM))
		{
			OutError = TEXT("grade query window has zero route length");
			return false;
		}

		TArray<double> QueryDistancesM;
		QueryDistancesM.Add(StartM);
		for (const FRouteGeometrySample& Sample : Samples)
		{
			if (Sample.DistanceM > StartM && Sample.DistanceM < EndM)
			{
				QueryDistancesM.Add(Sample.DistanceM);
			}
		}
		QueryDistancesM.Add(EndM);

		FVector PreviousPositionM;
		if (!TrySamplePosition(QueryDistancesM[0], PreviousPositionM, OutError))
		{
			return false;
		}

		double TotalHorizontalRunM = 0.0;
		double TotalRiseM = 0.0;

		for (int32 Index = 1; Index < QueryDistancesM.Num(); ++Index)
		{
			FVector CurrentPositionM;
			if (!TrySamplePosition(QueryDistancesM[Index], CurrentPositionM, OutError))
			{
				return false;
			}

			const FVector Delta = CurrentPositionM - PreviousPositionM;
			const double HorizontalRunM = FMath::Sqrt(
				Delta.X * Delta.X + Delta.Y * Delta.Y);
			if (!std::isfinite(HorizontalRunM) || HorizontalRunM <= 0.0)
			{
				OutError = TEXT("grade query encountered zero horizontal run");
				return false;
			}

			TotalHorizontalRunM += HorizontalRunM;
			TotalRiseM += Delta.Z;
			PreviousPositionM = CurrentPositionM;
		}

		if (!std::isfinite(TotalHorizontalRunM) || TotalHorizontalRunM <= 0.0)
		{
			OutError = TEXT("grade query accumulated invalid horizontal run");
			return false;
		}

		OutGradeDecimal = TotalRiseM / TotalHorizontalRunM;
		if (!std::isfinite(OutGradeDecimal))
		{
			OutError = TEXT("derived route grade is non-finite");
			OutGradeDecimal = 0.0;
			return false;
		}
		return true;
	}
}
