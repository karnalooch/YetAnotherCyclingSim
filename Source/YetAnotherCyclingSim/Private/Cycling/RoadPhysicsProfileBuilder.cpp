#include "Cycling/RoadPhysicsProfileBuilder.h"

#include "Math/UnrealMathUtility.h"

#include <cmath>

namespace CyclingRoadPhysics
{
	namespace
	{
		bool IsBuilderPositiveFinite(double Value)
		{
			return std::isfinite(Value) && Value > 0.0;
		}

		bool TryResolveCurvatureWindow(
			const CyclingSimulation::FRouteGeometryProfile& Geometry,
			double DistanceM,
			double HalfWindowM,
			FVector& OutA,
			FVector& OutB,
			FVector& OutC,
			double& OutTangentSeparationM,
			FString& OutError)
		{
			const double TotalLengthM = Geometry.GetTotalLengthM();
			if (!IsBuilderPositiveFinite(TotalLengthM))
			{
				OutError = TEXT("route geometry total length must be finite and greater than zero");
				return false;
			}

			double StartM = 0.0;
			double MiddleM = 0.0;
			double EndM = 0.0;

			if (DistanceM - HalfWindowM >= 0.0
				&& DistanceM + HalfWindowM <= TotalLengthM)
			{
				StartM = DistanceM - HalfWindowM;
				MiddleM = DistanceM;
				EndM = DistanceM + HalfWindowM;
			}
			else if (DistanceM < HalfWindowM)
			{
				StartM = 0.0;
				EndM = FMath::Min(TotalLengthM, 2.0 * HalfWindowM);
				MiddleM = 0.5 * (StartM + EndM);
			}
			else
			{
				EndM = TotalLengthM;
				StartM = FMath::Max(0.0, TotalLengthM - 2.0 * HalfWindowM);
				MiddleM = 0.5 * (StartM + EndM);
			}

			if (!(MiddleM > StartM) || !(EndM > MiddleM))
			{
				OutError = TEXT("curvature query requires three distinct route distances");
				return false;
			}

			if (!Geometry.TrySamplePosition(StartM, OutA, OutError)
				|| !Geometry.TrySamplePosition(MiddleM, OutB, OutError)
				|| !Geometry.TrySamplePosition(EndM, OutC, OutError))
			{
				return false;
			}

			// The two chord directions approximate route tangents at their
			// respective chord midpoints. Their route-distance separation is
			// half of the full three-point window.
			OutTangentSeparationM = 0.5 * (EndM - StartM);
			if (!IsBuilderPositiveFinite(OutTangentSeparationM))
			{
				OutError = TEXT("curvature tangent separation must be finite and greater than zero");
				return false;
			}

			return true;
		}

		bool TryDeriveCurvatures(
			const CyclingSimulation::FRouteGeometryProfile& Geometry,
			double DistanceM,
			double HalfWindowM,
			double& OutHorizontalCurvaturePerM,
			double& OutVerticalCurvaturePerM,
			FString& OutError)
		{
			OutHorizontalCurvaturePerM = 0.0;
			OutVerticalCurvaturePerM = 0.0;

			FVector A;
			FVector B;
			FVector C;
			double TangentSeparationM = 0.0;
			if (!TryResolveCurvatureWindow(
				Geometry,
				DistanceM,
				HalfWindowM,
				A,
				B,
				C,
				TangentSeparationM,
				OutError))
			{
				return false;
			}

			const double ABX = B.X - A.X;
			const double ABY = B.Y - A.Y;
			const double BCX = C.X - B.X;
			const double BCY = C.Y - B.Y;
			const double ACX = C.X - A.X;
			const double ACY = C.Y - A.Y;

			const double ABHorizontalM = std::sqrt(ABX * ABX + ABY * ABY);
			const double BCHorizontalM = std::sqrt(BCX * BCX + BCY * BCY);
			const double ACHorizontalM = std::sqrt(ACX * ACX + ACY * ACY);
			if (!IsBuilderPositiveFinite(ABHorizontalM)
				|| !IsBuilderPositiveFinite(BCHorizontalM)
				|| !IsBuilderPositiveFinite(ACHorizontalM))
			{
				OutError = TEXT("curvature query encountered a degenerate horizontal chord");
				return false;
			}

			// Signed plan-view curvature from the circumcircle through A/B/C.
			// For a circular arc this is exactly +/-1/R. Straight triples have
			// zero signed area and therefore zero horizontal curvature.
			const double SignedCross2D = ABX * ACY - ABY * ACX;
			const double CircumferenceDenominator =
				ABHorizontalM * BCHorizontalM * ACHorizontalM;
			if (!IsBuilderPositiveFinite(CircumferenceDenominator))
			{
				OutError = TEXT("horizontal curvature denominator is invalid");
				return false;
			}
			OutHorizontalCurvaturePerM =
				2.0 * SignedCross2D / CircumferenceDenominator;

			// Vertical curvature is the rate of change of road pitch between
			// the two adjacent chord tangents, per route-surface metre.
			const double PitchABRad = std::atan2(B.Z - A.Z, ABHorizontalM);
			const double PitchBCRad = std::atan2(C.Z - B.Z, BCHorizontalM);
			OutVerticalCurvaturePerM =
				(PitchBCRad - PitchABRad) / TangentSeparationM;

			if (!std::isfinite(OutHorizontalCurvaturePerM)
				|| !std::isfinite(OutVerticalCurvaturePerM))
			{
				OutError = TEXT("derived road curvature is non-finite");
				OutHorizontalCurvaturePerM = 0.0;
				OutVerticalCurvaturePerM = 0.0;
				return false;
			}

			return true;
		}
	}

	bool TryBuildRoadPhysicsProfileFromGeometry(
		const FString& Name,
		const CyclingSimulation::FRouteGeometryProfile& Geometry,
		const FRoadPhysicsGeometryBuildSettings& Settings,
		FRoadPhysicsProfile& OutProfile,
		FString& OutError)
	{
		OutError.Reset();

		if (!Geometry.IsConfigured())
		{
			OutError = TEXT("road physics builder requires configured route geometry");
			return false;
		}
		if (!IsBuilderPositiveFinite(Settings.GradeHalfWindowM))
		{
			OutError = TEXT("road physics grade half-window must be finite and greater than zero");
			return false;
		}
		if (!IsBuilderPositiveFinite(Settings.CurvatureHalfWindowM))
		{
			OutError = TEXT("road physics curvature half-window must be finite and greater than zero");
			return false;
		}

		const TArray<CyclingSimulation::FRouteGeometrySample>& GeometrySamples =
			Geometry.GetSamples();
		TArray<FRoadPhysicsSampleDefinition> Definitions;
		Definitions.Reserve(GeometrySamples.Num());

		for (int32 Index = 0; Index < GeometrySamples.Num(); ++Index)
		{
			const CyclingSimulation::FRouteGeometrySample& GeometrySample =
				GeometrySamples[Index];

			double GradeDecimal = 0.0;
			if (!Geometry.TryCalculateGrade(
				GeometrySample.DistanceM,
				Settings.GradeHalfWindowM,
				GradeDecimal,
				OutError))
			{
				OutError = FString::Printf(
					TEXT("road physics grade derivation failed at sample %d: %s"),
					Index,
					*OutError);
				return false;
			}

			double HorizontalCurvaturePerM = 0.0;
			double VerticalCurvaturePerM = 0.0;
			if (!TryDeriveCurvatures(
				Geometry,
				GeometrySample.DistanceM,
				Settings.CurvatureHalfWindowM,
				HorizontalCurvaturePerM,
				VerticalCurvaturePerM,
				OutError))
			{
				OutError = FString::Printf(
					TEXT("road physics curvature derivation failed at sample %d: %s"),
					Index,
					*OutError);
				return false;
			}

			FRoadPhysicsSampleDefinition Definition;
			Definition.DistanceM = GeometrySample.DistanceM;
			Definition.ElevationM = GeometrySample.PositionM.Z;
			Definition.GradeDecimal = GradeDecimal;
			Definition.HorizontalCurvaturePerM = HorizontalCurvaturePerM;
			Definition.VerticalCurvaturePerM = VerticalCurvaturePerM;
			Definition.RoadWidthM = Settings.RoadWidthM;
			Definition.BankAngleRad = Settings.BankAngleRad;
			Definition.SurfaceId = Settings.SurfaceId;
			Definition.Wetness = Settings.Wetness;
			Definition.Roughness = Settings.Roughness;
			Definitions.Add(MoveTemp(Definition));
		}

		FRoadPhysicsProfile Candidate;
		if (!Candidate.TryConfigure(Name, Definitions, OutError))
		{
			OutError = FString::Printf(
				TEXT("derived road physics profile is invalid: %s"),
				*OutError);
			return false;
		}

		OutProfile = MoveTemp(Candidate);
		return true;
	}
}
