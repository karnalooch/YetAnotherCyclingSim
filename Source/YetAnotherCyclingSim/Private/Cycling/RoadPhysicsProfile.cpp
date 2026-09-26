#include "Cycling/RoadPhysicsProfile.h"

#include <cmath>

namespace CyclingRoadPhysics
{
	namespace
	{
		constexpr double HalfPi = 1.57079632679489661923;

		double Lerp(double A, double B, double Alpha)
		{
			return A + (B - A) * Alpha;
		}

		bool IsFinite(double Value)
		{
			return std::isfinite(Value);
		}

		bool IsPositiveFinite(double Value)
		{
			return IsFinite(Value) && Value > 0.0;
		}
	}

	bool FRoadPhysicsProfile::TryConfigure(
		const FString& InName,
		const TArray<FRoadPhysicsSampleDefinition>& InSamples,
		FString& OutError)
	{
		OutError.Reset();

		const FString TrimmedName = InName.TrimStartAndEnd();
		if (TrimmedName.IsEmpty())
		{
			OutError = TEXT("road physics profile name must not be empty");
			return false;
		}
		if (InSamples.Num() < 2)
		{
			OutError = TEXT("road physics profile must contain at least two samples");
			return false;
		}

		TArray<FRoadPhysicsSample> CandidateSamples;
		CandidateSamples.Reserve(InSamples.Num());

		for (int32 Index = 0; Index < InSamples.Num(); ++Index)
		{
			const FRoadPhysicsSampleDefinition& Definition = InSamples[Index];
			const FString TrimmedSurfaceId = Definition.SurfaceId.TrimStartAndEnd();

			if (!IsFinite(Definition.DistanceM) || Definition.DistanceM < 0.0)
			{
				OutError = FString::Printf(
					TEXT("road sample %d distance must be finite and non-negative"),
					Index);
				return false;
			}
			if (Index == 0 && Definition.DistanceM != 0.0)
			{
				OutError = TEXT("first road sample distance must be exactly 0.0 m");
				return false;
			}
			if (Index > 0 && Definition.DistanceM <= InSamples[Index - 1].DistanceM)
			{
				OutError = FString::Printf(
					TEXT("road sample distances must be strictly increasing at index %d"),
					Index);
				return false;
			}
			if (!IsFinite(Definition.ElevationM)
				|| !IsFinite(Definition.GradeDecimal)
				|| !IsFinite(Definition.HorizontalCurvaturePerM)
				|| !IsFinite(Definition.VerticalCurvaturePerM))
			{
				OutError = FString::Printf(
					TEXT("road sample %d elevation, grade and curvatures must be finite"),
					Index);
				return false;
			}
			if (!IsPositiveFinite(Definition.RoadWidthM))
			{
				OutError = FString::Printf(
					TEXT("road sample %d width must be finite and greater than zero"),
					Index);
				return false;
			}
			if (!IsFinite(Definition.BankAngleRad)
				|| Definition.BankAngleRad <= -HalfPi
				|| Definition.BankAngleRad >= HalfPi)
			{
				OutError = FString::Printf(
					TEXT("road sample %d bank angle must be finite and strictly inside (-pi/2, pi/2)"),
					Index);
				return false;
			}
			if (TrimmedSurfaceId.IsEmpty())
			{
				OutError = FString::Printf(
					TEXT("road sample %d surface id must not be empty"),
					Index);
				return false;
			}
			if (!IsFinite(Definition.Wetness)
				|| Definition.Wetness < 0.0
				|| Definition.Wetness > 1.0)
			{
				OutError = FString::Printf(
					TEXT("road sample %d wetness must be finite and in [0, 1]"),
					Index);
				return false;
			}
			if (!IsFinite(Definition.Roughness) || Definition.Roughness < 0.0)
			{
				OutError = FString::Printf(
					TEXT("road sample %d roughness must be finite and non-negative"),
					Index);
				return false;
			}

			FRoadPhysicsSample Sample;
			Sample.DistanceM = Definition.DistanceM;
			Sample.ElevationM = Definition.ElevationM;
			Sample.GradeDecimal = Definition.GradeDecimal;
			Sample.HorizontalCurvaturePerM = Definition.HorizontalCurvaturePerM;
			Sample.VerticalCurvaturePerM = Definition.VerticalCurvaturePerM;
			Sample.RoadWidthM = Definition.RoadWidthM;
			Sample.BankAngleRad = Definition.BankAngleRad;
			Sample.SurfaceId = TrimmedSurfaceId;
			Sample.Wetness = Definition.Wetness;
			Sample.Roughness = Definition.Roughness;
			CandidateSamples.Add(MoveTemp(Sample));
		}

		Name = TrimmedName;
		Samples = MoveTemp(CandidateSamples);
		bIsConfigured = true;
		return true;
	}

	double FRoadPhysicsProfile::GetTotalLengthM() const
	{
		return Samples.Num() > 0 ? Samples.Last().GetDistanceM() : 0.0;
	}

	bool FRoadPhysicsProfile::TryGetStateAt(
		double DistanceM,
		double LateralPositionM,
		FRoadPhysicsState& OutState,
		FString& OutError) const
	{
		OutError.Reset();
		OutState = FRoadPhysicsState{};

		if (!bIsConfigured)
		{
			OutError = TEXT("road physics profile is not configured");
			return false;
		}
		if (!IsFinite(DistanceM)
			|| DistanceM < 0.0
			|| DistanceM > GetTotalLengthM())
		{
			OutError = FString::Printf(
				TEXT("route distance must be finite and in [0, %.6f] m"),
				GetTotalLengthM());
			return false;
		}
		if (!IsFinite(LateralPositionM))
		{
			OutError = TEXT("lateral position must be finite");
			return false;
		}

		const FRoadPhysicsSample* Left = nullptr;
		const FRoadPhysicsSample* Right = nullptr;
		double Alpha = 0.0;

		if (DistanceM == GetTotalLengthM())
		{
			Left = &Samples.Last();
			Right = Left;
		}
		else
		{
			for (int32 Index = 0; Index < Samples.Num(); ++Index)
			{
				const FRoadPhysicsSample& Current = Samples[Index];

				if (DistanceM == Current.GetDistanceM())
				{
					Left = &Current;
					Right = Index + 1 < Samples.Num() ? &Samples[Index + 1] : &Current;
					break;
				}
				if (DistanceM < Current.GetDistanceM())
				{
					Left = &Samples[Index - 1];
					Right = &Current;
					break;
				}
			}

			if (Left == nullptr || Right == nullptr)
			{
				OutError = TEXT("failed to resolve road sample interval");
				return false;
			}
			if (Left != Right)
			{
				const double SpanM = Right->GetDistanceM() - Left->GetDistanceM();
				Alpha = (DistanceM - Left->GetDistanceM()) / SpanM;
			}
		}

		const double RoadWidthM = Lerp(Left->GetRoadWidthM(), Right->GetRoadWidthM(), Alpha);
		const double HalfWidthM = 0.5 * RoadWidthM;
		if (LateralPositionM < -HalfWidthM || LateralPositionM > HalfWidthM)
		{
			OutError = FString::Printf(
				TEXT("lateral position %.6f m lies outside road bounds [%.6f, %.6f] m at S=%.6f m"),
				LateralPositionM,
				-HalfWidthM,
				HalfWidthM,
				DistanceM);
			return false;
		}

		OutState.DistanceM = DistanceM;
		OutState.LateralPositionM = LateralPositionM;
		OutState.ElevationM = Lerp(Left->GetElevationM(), Right->GetElevationM(), Alpha);
		OutState.GradeDecimal = Lerp(Left->GetGradeDecimal(), Right->GetGradeDecimal(), Alpha);
		OutState.HorizontalCurvaturePerM = Lerp(
			Left->GetHorizontalCurvaturePerM(),
			Right->GetHorizontalCurvaturePerM(),
			Alpha);
		OutState.VerticalCurvaturePerM = Lerp(
			Left->GetVerticalCurvaturePerM(),
			Right->GetVerticalCurvaturePerM(),
			Alpha);
		OutState.RoadWidthM = RoadWidthM;
		OutState.BankAngleRad = Lerp(
			Left->GetBankAngleRad(),
			Right->GetBankAngleRad(),
			Alpha);
		OutState.SurfaceId = Left->GetSurfaceId();
		OutState.Wetness = Lerp(Left->GetWetness(), Right->GetWetness(), Alpha);
		OutState.Roughness = Lerp(Left->GetRoughness(), Right->GetRoughness(), Alpha);
		return true;
	}

	bool FRoadPhysicsProfile::TryGetStateAhead(
		double DistanceM,
		double LookAheadM,
		double LateralPositionM,
		FRoadPhysicsState& OutState,
		FString& OutError) const
	{
		OutState = FRoadPhysicsState{};
		OutError.Reset();

		if (!bIsConfigured)
		{
			OutError = TEXT("road physics profile is not configured");
			return false;
		}
		if (!IsFinite(DistanceM)
			|| DistanceM < 0.0
			|| DistanceM > GetTotalLengthM())
		{
			OutError = FString::Printf(
				TEXT("route distance must be finite and in [0, %.6f] m"),
				GetTotalLengthM());
			return false;
		}
		if (!IsFinite(LookAheadM) || LookAheadM < 0.0)
		{
			OutError = TEXT("look-ahead distance must be finite and non-negative");
			return false;
		}

		const double TargetDistanceM =
			DistanceM + LookAheadM > GetTotalLengthM()
			? GetTotalLengthM()
			: DistanceM + LookAheadM;
		return TryGetStateAt(TargetDistanceM, LateralPositionM, OutState, OutError);
	}

	bool FRoadPhysicsProfile::TryValidateTransitionRates(
		const FRoadPhysicsTransitionLimits& Limits,
		FString& OutError) const
	{
		OutError.Reset();

		if (!bIsConfigured)
		{
			OutError = TEXT("road physics profile is not configured");
			return false;
		}
		if (!IsPositiveFinite(Limits.MaxAbsGradeChangePerM)
			|| !IsPositiveFinite(Limits.MaxAbsHorizontalCurvatureChangePerM2)
			|| !IsPositiveFinite(Limits.MaxAbsBankAngleChangeRadPerM))
		{
			OutError = TEXT("all road transition limits must be finite and greater than zero");
			return false;
		}

		for (int32 Index = 1; Index < Samples.Num(); ++Index)
		{
			const FRoadPhysicsSample& Previous = Samples[Index - 1];
			const FRoadPhysicsSample& Current = Samples[Index];
			const double DeltaSM = Current.GetDistanceM() - Previous.GetDistanceM();

			const double GradeRate =
				std::abs(Current.GetGradeDecimal() - Previous.GetGradeDecimal()) / DeltaSM;
			if (GradeRate > Limits.MaxAbsGradeChangePerM)
			{
				OutError = FString::Printf(
					TEXT("grade change rate exceeds limit between road samples %d and %d"),
					Index - 1,
					Index);
				return false;
			}

			const double CurvatureRate = std::abs(
				Current.GetHorizontalCurvaturePerM()
				- Previous.GetHorizontalCurvaturePerM()) / DeltaSM;
			if (CurvatureRate > Limits.MaxAbsHorizontalCurvatureChangePerM2)
			{
				OutError = FString::Printf(
					TEXT("horizontal curvature change rate exceeds limit between road samples %d and %d"),
					Index - 1,
					Index);
				return false;
			}

			const double BankRate =
				std::abs(Current.GetBankAngleRad() - Previous.GetBankAngleRad()) / DeltaSM;
			if (BankRate > Limits.MaxAbsBankAngleChangeRadPerM)
			{
				OutError = FString::Printf(
					TEXT("bank angle change rate exceeds limit between road samples %d and %d"),
					Index - 1,
					Index);
				return false;
			}
		}

		return true;
	}
}
