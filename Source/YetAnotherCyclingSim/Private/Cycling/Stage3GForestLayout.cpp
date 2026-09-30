#include "Cycling/Stage3GForestLayout.h"

#include <cmath>

namespace CyclingStage3G
{
	namespace
	{
		struct FLayerProfile
		{
			EStage3GForestLayer Layer = EStage3GForestLayer::Primary;
			double StationSpacingM = 0.0;
			int32 PointsPerSidePerStation = 0;
			double DensityMultiplier = 1.0;
			double MinLateralOffsetM = 0.0;
			double MaxLateralOffsetM = 0.0;
			double MinUniformScale = 1.0;
			double MaxUniformScale = 1.0;
			int32 SeedOffset = 0;
		};

		bool IsFinite(double Value)
		{
			return std::isfinite(Value);
		}

		bool ValidateConfig(
			const CyclingSimulation::FRouteGeometryProfile& RouteGeometry,
			const FStage3GForestLayoutConfig& Config,
			FString& OutError)
		{
			if (!RouteGeometry.IsConfigured())
			{
				OutError = TEXT("forest layout requires configured route geometry");
				return false;
			}
			if (!IsFinite(Config.StartDistanceM)
				|| !IsFinite(Config.EndDistanceM)
				|| Config.StartDistanceM < 0.0
				|| Config.EndDistanceM <= Config.StartDistanceM
				|| Config.EndDistanceM > RouteGeometry.GetTotalLengthM())
			{
				OutError = TEXT("forest distance range must be finite, ordered and inside the route");
				return false;
			}
			if (!IsFinite(Config.BaseDensity)
				|| Config.BaseDensity < 0.0
				|| Config.BaseDensity > 1.0)
			{
				OutError = TEXT("forest density must be finite and inside [0, 1]");
				return false;
			}
			if (!IsFinite(Config.PrimaryStationSpacingM)
				|| Config.PrimaryStationSpacingM <= 0.0)
			{
				OutError = TEXT("forest primary station spacing must be positive");
				return false;
			}
			if (Config.PrimaryPointsPerSidePerStation < 1
				|| Config.PrimaryPointsPerSidePerStation > 8)
			{
				OutError = TEXT("forest primary points-per-side must be inside [1, 8]");
				return false;
			}
			if (!IsFinite(Config.ProtectedRouteHalfWidthM)
				|| Config.ProtectedRouteHalfWidthM <= 0.0
				|| !IsFinite(Config.PrimaryMinLateralOffsetM)
				|| !IsFinite(Config.PrimaryMaxLateralOffsetM)
				|| Config.PrimaryMinLateralOffsetM <= Config.ProtectedRouteHalfWidthM
				|| Config.PrimaryMaxLateralOffsetM <= Config.PrimaryMinLateralOffsetM)
			{
				OutError = TEXT("forest primary lateral band must stay outside route clearance");
				return false;
			}
			if (!IsFinite(Config.PrimaryMinUniformScale)
				|| !IsFinite(Config.PrimaryMaxUniformScale)
				|| Config.PrimaryMinUniformScale <= 0.0
				|| Config.PrimaryMaxUniformScale < Config.PrimaryMinUniformScale)
			{
				OutError = TEXT("forest primary scale range must be finite, positive and ordered");
				return false;
			}
			if (Config.LayerProfileVersion != 2)
			{
				OutError = TEXT("forest layer profile version must be 2");
				return false;
			}
			return true;
		}
	}

	FStage3GForestLayoutConfig MakeTargetDensityForestConfig()
	{
		return FStage3GForestLayoutConfig{};
	}

	const TCHAR* Stage3GForestLayerName(EStage3GForestLayer Layer)
	{
		switch (Layer)
		{
		case EStage3GForestLayer::Primary:
			return TEXT("primary");
		case EStage3GForestLayer::Background:
			return TEXT("background");
		case EStage3GForestLayer::Understory:
			return TEXT("understory");
		default:
			return TEXT("unknown");
		}
	}

	bool TryGenerateForestLayout(
		const CyclingSimulation::FRouteGeometryProfile& RouteGeometry,
		const FStage3GForestLayoutConfig& Config,
		TArray<FStage3GForestCandidate>& OutCandidates,
		FStage3GForestLayoutStats& OutStats,
		FString& OutError)
	{
		OutCandidates.Reset();
		OutStats = FStage3GForestLayoutStats{};
		OutError.Reset();

		if (!ValidateConfig(RouteGeometry, Config, OutError))
		{
			return false;
		}

		const FLayerProfile Layers[] = {
			{
				EStage3GForestLayer::Primary,
				Config.PrimaryStationSpacingM,
				Config.PrimaryPointsPerSidePerStation,
				1.00,
				Config.PrimaryMinLateralOffsetM,
				Config.PrimaryMaxLateralOffsetM,
				Config.PrimaryMinUniformScale,
				Config.PrimaryMaxUniformScale,
				0,
			},
			{
				EStage3GForestLayer::Background,
				26.0,
				4,
				0.95,
				30.0,
				62.0,
				0.85,
				1.20,
				101,
			},
			{
				EStage3GForestLayer::Understory,
				16.0,
				3,
				0.68,
				12.0,
				50.0,
				0.40,
				0.70,
				211,
			},
		};

		for (const FLayerProfile& Layer : Layers)
		{
			const int32 ApproximateStations = FMath::CeilToInt(
				(Config.EndDistanceM - Config.StartDistanceM)
				/ Layer.StationSpacingM);
			OutStats.ReserveCount +=
				ApproximateStations * Layer.PointsPerSidePerStation * 2;
			OutStats.ExpectedCandidateMean +=
				static_cast<double>(
					ApproximateStations * Layer.PointsPerSidePerStation * 2)
				* FMath::Clamp(
					Config.BaseDensity * Layer.DensityMultiplier,
					0.0,
					1.0);
		}
		OutCandidates.Reserve(OutStats.ReserveCount);

		for (const FLayerProfile& Layer : Layers)
		{
			FRandomStream Random(Config.GenerationSeed + Layer.SeedOffset);
			const double EffectiveDensity = FMath::Clamp(
				Config.BaseDensity * Layer.DensityMultiplier,
				0.0,
				1.0);
			const double BandWidthM =
				(Layer.MaxLateralOffsetM - Layer.MinLateralOffsetM)
				/ static_cast<double>(Layer.PointsPerSidePerStation);

			for (double StationM = Config.StartDistanceM;
				StationM < Config.EndDistanceM;
				StationM += Layer.StationSpacingM)
			{
				const double LongitudinalJitterM = Random.FRandRange(
					-0.25 * Layer.StationSpacingM,
					0.25 * Layer.StationSpacingM);
				const double SampleDistanceM = FMath::Clamp(
					StationM + LongitudinalJitterM,
					Config.StartDistanceM,
					Config.EndDistanceM);

				FVector RoutePositionM;
				FString RouteError;
				if (!RouteGeometry.TrySamplePosition(
					SampleDistanceM,
					RoutePositionM,
					RouteError))
				{
					OutError = FString::Printf(
						TEXT("forest %s route sample failed at %.3f m: %s"),
						Stage3GForestLayerName(Layer.Layer),
						SampleDistanceM,
						*RouteError);
					return false;
				}

				const double TangentHalfWindowM =
					FMath::Min(5.0, Layer.StationSpacingM * 0.25);
				const double BeforeM = FMath::Max(
					0.0,
					SampleDistanceM - TangentHalfWindowM);
				const double AfterM = FMath::Min(
					RouteGeometry.GetTotalLengthM(),
					SampleDistanceM + TangentHalfWindowM);

				FVector BeforePositionM;
				FVector AfterPositionM;
				if (!RouteGeometry.TrySamplePosition(BeforeM, BeforePositionM, RouteError)
					|| !RouteGeometry.TrySamplePosition(AfterM, AfterPositionM, RouteError))
				{
					OutError = FString::Printf(
						TEXT("forest %s tangent sample failed: %s"),
						Stage3GForestLayerName(Layer.Layer),
						*RouteError);
					return false;
				}

				FVector HorizontalTangent(
					AfterPositionM.X - BeforePositionM.X,
					AfterPositionM.Y - BeforePositionM.Y,
					0.0);
				if (!HorizontalTangent.Normalize())
				{
					OutError = FString::Printf(
						TEXT("forest %s horizontal route tangent is degenerate"),
						Stage3GForestLayerName(Layer.Layer));
					return false;
				}

				const FVector Lateral(
					-HorizontalTangent.Y,
					HorizontalTangent.X,
					0.0);

				for (const double SideSign : { -1.0, 1.0 })
				{
					for (int32 BandIndex = 0;
						BandIndex < Layer.PointsPerSidePerStation;
						++BandIndex)
					{
						if (Random.FRand() > EffectiveDensity)
						{
							continue;
						}

						const double BandMinM =
							Layer.MinLateralOffsetM
							+ BandWidthM * static_cast<double>(BandIndex);
						const double BandMaxM = FMath::Min(
							Layer.MaxLateralOffsetM,
							BandMinM + BandWidthM);
						const double LateralOffsetM =
							Random.FRandRange(BandMinM, BandMaxM);

						FStage3GForestCandidate Candidate;
						Candidate.Layer = Layer.Layer;
						Candidate.RouteDistanceM = SampleDistanceM;
						Candidate.SignedLateralOffsetM =
							SideSign * LateralOffsetM;
						Candidate.PositionM =
							RoutePositionM
							+ Lateral * Candidate.SignedLateralOffsetM;
						Candidate.UniformScale = Random.FRandRange(
							Layer.MinUniformScale,
							Layer.MaxUniformScale);
						Candidate.YawDeg = Random.FRandRange(0.0, 360.0);
						Candidate.Seed = Random.RandHelper(MAX_int32);
						OutCandidates.Add(Candidate);

						switch (Layer.Layer)
						{
						case EStage3GForestLayer::Primary:
							++OutStats.PrimaryCount;
							break;
						case EStage3GForestLayer::Background:
							++OutStats.BackgroundCount;
							break;
						case EStage3GForestLayer::Understory:
							++OutStats.UnderstoryCount;
							break;
						default:
							break;
						}
					}
				}
			}
		}

		OutStats.GeneratedCount = OutCandidates.Num();
		const int32 MinCandidateSanity =
			FMath::FloorToInt(OutStats.ExpectedCandidateMean * 0.65);
		const int32 MaxCandidateSanity =
			FMath::CeilToInt(OutStats.ExpectedCandidateMean * 1.35);
		if (OutStats.GeneratedCount < MinCandidateSanity
			|| OutStats.GeneratedCount > MaxCandidateSanity)
		{
			OutError = FString::Printf(
				TEXT("forest generated %d points outside density sanity [%d, %d] around expected mean %.2f"),
				OutStats.GeneratedCount,
				MinCandidateSanity,
				MaxCandidateSanity,
				OutStats.ExpectedCandidateMean);
			return false;
		}

		return true;
	}
}
