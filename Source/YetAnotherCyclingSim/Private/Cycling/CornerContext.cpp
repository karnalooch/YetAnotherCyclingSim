#include "Cycling/CornerContext.h"

#include "Math/UnrealMathUtility.h"

#include <cmath>
#include <limits>

namespace CyclingCornerContext
{
	namespace
	{
		bool IsCornerContextPositiveFinite(double Value)
		{
			return std::isfinite(Value) && Value > 0.0;
		}

		bool IsCornerContextNonNegativeFinite(double Value)
		{
			return std::isfinite(Value) && Value >= 0.0;
		}

		bool IsCornerState(
			const CyclingRoadPhysics::FRoadPhysicsState& State,
			double Threshold)
		{
			return std::abs(State.HorizontalCurvaturePerM) >= Threshold;
		}

		CyclingCornering::ECornerPhase ResolvePhase(
			double DistanceM,
			double CornerStartM,
			double CornerEndM,
			double ApproachLengthM)
		{
			if (DistanceM < CornerStartM)
			{
				const double ApproachStartM =
					FMath::Max(0.0, CornerStartM - ApproachLengthM);
				return DistanceM >= ApproachStartM
					? CyclingCornering::ECornerPhase::Approach
					: CyclingCornering::ECornerPhase::Outside;
			}

			const double LengthM = CornerEndM - CornerStartM;
			if (!(LengthM > 0.0))
			{
				return CyclingCornering::ECornerPhase::Outside;
			}
			if (DistanceM < CornerStartM + 0.25 * LengthM)
			{
				return CyclingCornering::ECornerPhase::Entry;
			}
			if (DistanceM < CornerStartM + 0.75 * LengthM)
			{
				return CyclingCornering::ECornerPhase::Apex;
			}
			if (DistanceM < CornerEndM)
			{
				return CyclingCornering::ECornerPhase::Exit;
			}
			return CyclingCornering::ECornerPhase::Outside;
		}

		bool TryResolveRadiusContext(
			double CurvaturePerM,
			double LateralPositionM,
			ECornerDirection& OutDirection,
			double& OutCenterlineRadiusM,
			double& OutEffectiveRadiusM,
			FString& OutError)
		{
			OutDirection = ECornerDirection::Straight;
			OutCenterlineRadiusM = std::numeric_limits<double>::infinity();
			OutEffectiveRadiusM = std::numeric_limits<double>::infinity();

			if (!std::isfinite(CurvaturePerM))
			{
				OutError = TEXT("corner curvature must be finite");
				return false;
			}
			if (CurvaturePerM == 0.0)
			{
				return true;
			}

			const double SignedCenterlineRadiusM = 1.0 / CurvaturePerM;
			const double EffectiveSignedRadiusM =
				SignedCenterlineRadiusM - LateralPositionM;
			if (!std::isfinite(EffectiveSignedRadiusM)
				|| EffectiveSignedRadiusM == 0.0)
			{
				OutError = TEXT("lateral position collapses the effective corner radius");
				return false;
			}

			OutDirection = CurvaturePerM > 0.0
				? ECornerDirection::Right
				: ECornerDirection::Left;
			OutCenterlineRadiusM = std::abs(SignedCenterlineRadiusM);
			OutEffectiveRadiusM = std::abs(EffectiveSignedRadiusM);
			return true;
		}

		void FillRoadMetadata(
			const CyclingRoadPhysics::FRoadPhysicsState& State,
			FCornerContext& OutContext)
		{
			OutContext.RoadWidthM = State.RoadWidthM;
			OutContext.LeftMarginM =
				State.LateralPositionM - State.GetLeftEdgeM();
			OutContext.RightMarginM =
				State.GetRightEdgeM() - State.LateralPositionM;
			OutContext.CrossSlopeAngleRad = State.CrossSlopeAngleRad;
			OutContext.SurfaceId = State.SurfaceId;
			OutContext.Wetness = State.Wetness;
			OutContext.Roughness = State.Roughness;
		}
	}

	bool TryBuildCornerContext(
		const CyclingRoadPhysics::FRoadPhysicsProfile& Profile,
		double DistanceM,
		double LateralPositionM,
		const FCornerContextSettings& Settings,
		FCornerContext& OutContext,
		FString& OutError)
	{
		using namespace CyclingRoadPhysics;

		OutContext = FCornerContext{};
		OutError.Reset();

		if (!Profile.IsConfigured())
		{
			OutError = TEXT("corner context requires a configured road physics profile");
			return false;
		}
		if (!std::isfinite(DistanceM)
			|| DistanceM < 0.0
			|| DistanceM > Profile.GetTotalLengthM())
		{
			OutError = TEXT("corner context distance must lie inside the road profile");
			return false;
		}
		if (!std::isfinite(LateralPositionM))
		{
			OutError = TEXT("corner context lateral position must be finite");
			return false;
		}
		if (!IsCornerContextPositiveFinite(Settings.MinAbsCurvaturePerM))
		{
			OutError = TEXT("corner context minimum absolute curvature must be finite and greater than zero");
			return false;
		}
		if (!IsCornerContextPositiveFinite(Settings.ScanStepM))
		{
			OutError = TEXT("corner context scan step must be finite and greater than zero");
			return false;
		}
		if (!IsCornerContextNonNegativeFinite(Settings.LookAheadM))
		{
			OutError = TEXT("corner context look-ahead must be finite and non-negative");
			return false;
		}
		if (!IsCornerContextPositiveFinite(Settings.ApproachLengthM))
		{
			OutError = TEXT("corner context approach length must be finite and greater than zero");
			return false;
		}

		FRoadPhysicsState Current;
		if (!Profile.TryGetStateAt(
			DistanceM,
			LateralPositionM,
			Current,
			OutError))
		{
			return false;
		}

		const double Threshold = Settings.MinAbsCurvaturePerM;
		const double StepM = Settings.ScanStepM;
		const double RouteEndM = Profile.GetTotalLengthM();
		// Anchor detection probes to a global route-origin scan grid. Starting
		// probes from the current S would make the same physical corner drift
		// by each fixed substep (for example 100.00 -> 100.05 m), which is not
		// a stable runtime episode identity.
		const double GridIndex = std::floor(DistanceM / StepM);
		const double FloorProbeM =
			FMath::Min(RouteEndM, GridIndex * StepM);
		FRoadPhysicsState FloorProbe;
		if (!Profile.TryGetStateAt(
			FloorProbeM,
			LateralPositionM,
			FloorProbe,
			OutError))
		{
			return false;
		}

		bool bFoundCorner = IsCornerState(FloorProbe, Threshold);
		double CornerStartM = FloorProbeM;

		if (bFoundCorner)
		{
			while (CornerStartM > 0.0)
			{
				const double PreviousM = FMath::Max(0.0, CornerStartM - StepM);
				FRoadPhysicsState Previous;
				if (!Profile.TryGetStateAt(
					PreviousM,
					LateralPositionM,
					Previous,
					OutError))
				{
					return false;
				}
				if (!IsCornerState(Previous, Threshold))
				{
					break;
				}
				CornerStartM = PreviousM;
				if (PreviousM == 0.0)
				{
					break;
				}
			}
		}
		else
		{
			const double MaxDistanceM =
				FMath::Min(RouteEndM, DistanceM + Settings.LookAheadM);
			int64 ProbeIndex = static_cast<int64>(GridIndex) + 1;
			while (true)
			{
				double ProbeM = static_cast<double>(ProbeIndex) * StepM;
				if (ProbeM > RouteEndM)
				{
					ProbeM = RouteEndM;
				}
				if (ProbeM > MaxDistanceM)
				{
					break;
				}

				FRoadPhysicsState Probe;
				if (!Profile.TryGetStateAt(
					ProbeM,
					LateralPositionM,
					Probe,
					OutError))
				{
					return false;
				}
				if (IsCornerState(Probe, Threshold))
				{
					bFoundCorner = true;
					CornerStartM = ProbeM;
					break;
				}
				if (ProbeM == RouteEndM)
				{
					break;
				}
				++ProbeIndex;
			}
		}

		OutContext.DistanceM = DistanceM;
		OutContext.LateralPositionM = LateralPositionM;

		if (!bFoundCorner)
		{
			OutContext.Phase = CyclingCornering::ECornerPhase::Outside;
			OutContext.bHasCorner = false;
			OutContext.CornerStartM = DistanceM;
			OutContext.CornerEndM = DistanceM;
			OutContext.ApexDistanceM = DistanceM;
			OutContext.Direction = ECornerDirection::Straight;
			OutContext.SignedCurvaturePerM = Current.HorizontalCurvaturePerM;
			OutContext.CenterlineRadiusM =
				std::numeric_limits<double>::infinity();
			OutContext.EffectiveRadiusM =
				std::numeric_limits<double>::infinity();
			FillRoadMetadata(Current, OutContext);
			return true;
		}

		double CornerEndM = CornerStartM;
		while (CornerEndM < RouteEndM)
		{
			const double NextProbeM =
				FMath::Min(RouteEndM, CornerEndM + StepM);
			FRoadPhysicsState Probe;
			if (!Profile.TryGetStateAt(
				NextProbeM,
				LateralPositionM,
				Probe,
				OutError))
			{
				return false;
			}
			if (!IsCornerState(Probe, Threshold))
			{
				CornerEndM = NextProbeM;
				break;
			}
			CornerEndM = NextProbeM;
			if (NextProbeM == RouteEndM)
			{
				break;
			}
		}

		if (!(CornerEndM > CornerStartM))
		{
			OutError = TEXT("detected corner interval must have positive length");
			return false;
		}

		const double FocusDistanceM =
			IsCornerState(Current, Threshold) ? DistanceM : CornerStartM;
		FRoadPhysicsState Focus;
		if (!Profile.TryGetStateAt(
			FocusDistanceM,
			LateralPositionM,
			Focus,
			OutError))
		{
			return false;
		}

		OutContext.bHasCorner = true;
		OutContext.CornerStartM = CornerStartM;
		OutContext.CornerEndM = CornerEndM;
		OutContext.DistanceToCornerStartM =
			FMath::Max(0.0, CornerStartM - DistanceM);
		OutContext.ApexDistanceM =
			CornerStartM + 0.5 * (CornerEndM - CornerStartM);
		OutContext.Phase = ResolvePhase(
			DistanceM,
			CornerStartM,
			CornerEndM,
			Settings.ApproachLengthM);
		OutContext.SignedCurvaturePerM = Focus.HorizontalCurvaturePerM;
		if (!TryResolveRadiusContext(
			Focus.HorizontalCurvaturePerM,
			LateralPositionM,
			OutContext.Direction,
			OutContext.CenterlineRadiusM,
			OutContext.EffectiveRadiusM,
			OutError))
		{
			return false;
		}
		FillRoadMetadata(Focus, OutContext);
		return true;
	}
}
