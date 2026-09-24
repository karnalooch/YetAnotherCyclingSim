#include "Cycling/AlpineJourneyGeometry.h"

#include "Cycling/AlpineJourneyRoute.h"
#include "Cycling/RouteProfile.h"

#include <cmath>

namespace CyclingSimulation
{
	namespace
	{
		double SmoothStep01(double T)
		{
			const double Clamped = FMath::Clamp(T, 0.0, 1.0);
			return Clamped * Clamped * (3.0 - 2.0 * Clamped);
		}

		bool TryResolveSmoothedGrade(
			const FRouteProfile& Route,
			double DistanceM,
			double& OutGradeDecimal,
			FString& OutError)
		{
			const FRouteSegment* Segment = nullptr;
			int32 SegmentIndex = INDEX_NONE;
			if (!Route.TryGetSegmentAtDistance(
				FMath::Clamp(DistanceM, 0.0, Route.GetTotalLengthM()),
				Segment,
				SegmentIndex,
				OutError))
			{
				return false;
			}

			OutGradeDecimal = Segment->GetGradeDecimal();
			const TArray<FRouteSegment>& Segments = Route.GetSegments();

			for (int32 BoundaryIndex = 0; BoundaryIndex < Segments.Num() - 1; ++BoundaryIndex)
			{
				const double BoundaryM = Segments[BoundaryIndex].GetEndDistanceM();
				const double StartBlendM = BoundaryM - AlpineGradeBlendHalfWindowM;
				const double EndBlendM = BoundaryM + AlpineGradeBlendHalfWindowM;
				if (DistanceM < StartBlendM || DistanceM > EndBlendM)
				{
					continue;
				}

				const double T = (DistanceM - StartBlendM)
					/ (2.0 * AlpineGradeBlendHalfWindowM);
				const double Alpha = SmoothStep01(T);
				OutGradeDecimal = FMath::Lerp(
					Segments[BoundaryIndex].GetGradeDecimal(),
					Segments[BoundaryIndex + 1].GetGradeDecimal(),
					Alpha);
				return true;
			}

			return true;
		}

		double ResolveSignedCurvature(
			double DistanceM,
			const TArray<FAlpineCornerGeometryDefinition>& Corners)
		{
			for (const FAlpineCornerGeometryDefinition& Corner : Corners)
			{
				const double StartM = Corner.CenterDistanceM - Corner.LengthM * 0.5;
				const double EndM = Corner.CenterDistanceM + Corner.LengthM * 0.5;
				if (DistanceM >= StartM && DistanceM <= EndM)
				{
					return Corner.DirectionSign / Corner.RadiusM;
				}
			}
			return 0.0;
		}
	}

	void BuildAlpineCornerGeometryDefinitions(
		TArray<FAlpineCornerGeometryDefinition>& OutCorners)
	{
		OutCorners.Reset();
		OutCorners.Reserve(8);

		OutCorners.Add({ TEXT("Village Bend"), 650.0, 80.0, 55.0, 1.0 });
		OutCorners.Add({ TEXT("River Left"), 1550.0, 110.0, 40.0, -1.0 });
		OutCorners.Add({ TEXT("Forest Entrance"), 4050.0, 90.0, 32.0, 1.0 });
		OutCorners.Add({ TEXT("Climb Hairpin"), 5350.0, 70.0, 18.0, -1.0 });
		OutCorners.Add({ TEXT("Shelf Right"), 6650.0, 100.0, 30.0, 1.0 });
		OutCorners.Add({ TEXT("Valley Hairpin"), 7550.0, 80.0, 22.0, -1.0 });
		OutCorners.Add({ TEXT("High Valley Sweep"), 8150.0, 140.0, 48.0, 1.0 });
		OutCorners.Add({ TEXT("Lakeside Final Bend"), 9250.0, 100.0, 35.0, -1.0 });
	}

	bool TryBuildAlpineJourneyRouteGeometry(
		FRouteGeometryProfile& OutGeometry,
		FString& OutError)
	{
		OutError.Reset();

		FRouteProfile Route;
		if (!TryBuildAlpineJourneyRouteProfile(Route, OutError))
		{
			return false;
		}

		TArray<FAlpineCornerGeometryDefinition> Corners;
		BuildAlpineCornerGeometryDefinitions(Corners);

		TArray<FRouteGeometrySample> Samples;
		const int32 FullStepCount = static_cast<int32>(
			FMath::FloorToDouble(Route.GetTotalLengthM() / AlpineGeometrySampleSpacingM));
		Samples.Reserve(FullStepCount + 2);

		double DistanceM = 0.0;
		double HeadingRad = 0.0;
		FVector PositionM = FVector::ZeroVector;
		Samples.Add({ DistanceM, PositionM });

		while (DistanceM < Route.GetTotalLengthM())
		{
			const double StepM = FMath::Min(
				AlpineGeometrySampleSpacingM,
				Route.GetTotalLengthM() - DistanceM);
			const double MidDistanceM = DistanceM + StepM * 0.5;

			double GradeDecimal = 0.0;
			if (!TryResolveSmoothedGrade(Route, MidDistanceM, GradeDecimal, OutError))
			{
				return false;
			}

			const double HorizontalRunM = StepM / FMath::Sqrt(
				1.0 + GradeDecimal * GradeDecimal);
			const double RiseM = GradeDecimal * HorizontalRunM;

			const double CurvaturePerM = ResolveSignedCurvature(MidDistanceM, Corners);
			const double DeltaHeadingRad = CurvaturePerM * HorizontalRunM;
			const double MidHeadingRad = HeadingRad + DeltaHeadingRad * 0.5;

			PositionM.X += HorizontalRunM * FMath::Cos(MidHeadingRad);
			PositionM.Y += HorizontalRunM * FMath::Sin(MidHeadingRad);
			PositionM.Z += RiseM;
			HeadingRad += DeltaHeadingRad;
			DistanceM += StepM;

			Samples.Add({ DistanceM, PositionM });
		}

		// Each integration interval is constructed so its 3D chord length
		// equals StepM to floating-point precision.
		return OutGeometry.TryConfigure(Samples, 1e-6, OutError);
	}
}
