#include "PCG/Stage3GForestCandidatesSettings.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Data/PCGBasePointData.h"
#include "PCGContext.h"
#include "PCGPin.h"

#include <cmath>

#define LOCTEXT_NAMESPACE "YacsStage3GForestCandidates"

namespace
{
	constexpr double MetresToCentimetres = 100.0;

	bool IsFinite(double Value)
	{
		return std::isfinite(Value);
	}

	bool ValidateSettings(
		const UStage3GForestCandidatesSettings& Settings,
		FString& OutError)
	{
		OutError.Reset();
		if (!IsFinite(Settings.StartDistanceM)
			|| !IsFinite(Settings.EndDistanceM)
			|| Settings.StartDistanceM < 0.0
			|| Settings.EndDistanceM <= Settings.StartDistanceM)
		{
			OutError = TEXT("forest distance range must be finite, ordered and non-negative");
			return false;
		}
		if (!IsFinite(Settings.StationSpacingM) || Settings.StationSpacingM <= 0.0)
		{
			OutError = TEXT("forest station spacing must be finite and greater than zero");
			return false;
		}
		if (!IsFinite(Settings.Density) || Settings.Density < 0.0 || Settings.Density > 1.0)
		{
			OutError = TEXT("forest density must be finite and inside [0, 1]");
			return false;
		}
		if (Settings.PointsPerSidePerStation < 1 || Settings.PointsPerSidePerStation > 8)
		{
			OutError = TEXT("forest points-per-side must be inside [1, 8]");
			return false;
		}
		if (!IsFinite(Settings.MinLateralOffsetM)
			|| !IsFinite(Settings.MaxLateralOffsetM)
			|| Settings.MinLateralOffsetM <= 4.0
			|| Settings.MaxLateralOffsetM <= Settings.MinLateralOffsetM)
		{
			OutError = TEXT("forest lateral range must stay outside the 4 m route corridor");
			return false;
		}
		if (!IsFinite(Settings.MinUniformScale)
			|| !IsFinite(Settings.MaxUniformScale)
			|| Settings.MinUniformScale <= 0.0
			|| Settings.MaxUniformScale < Settings.MinUniformScale)
		{
			OutError = TEXT("forest scale range must be finite, positive and ordered");
			return false;
		}
		return true;
	}
}

#if WITH_EDITOR
FName UStage3GForestCandidatesSettings::GetDefaultNodeName() const
{
	return FName(TEXT("YACSForestCandidates"));
}

FText UStage3GForestCandidatesSettings::GetDefaultNodeTitle() const
{
	return LOCTEXT("NodeTitle", "YACS Forest Candidates");
}

FText UStage3GForestCandidatesSettings::GetNodeTooltipText() const
{
	return LOCTEXT(
		"NodeTooltip",
		"Generates deterministic Stage 3G forest candidate points around the canonical "
		"YACS route. WorldSpec controls biome range, density and seed.");
}

EPCGSettingsType UStage3GForestCandidatesSettings::GetType() const
{
	return EPCGSettingsType::Spatial;
}
#endif

TArray<FPCGPinProperties> UStage3GForestCandidatesSettings::InputPinProperties() const
{
	return {};
}

TArray<FPCGPinProperties> UStage3GForestCandidatesSettings::OutputPinProperties() const
{
	return DefaultPointOutputPinProperties();
}

FPCGElementPtr UStage3GForestCandidatesSettings::CreateElement() const
{
	return MakeShared<FStage3GForestCandidatesElement>();
}

bool FStage3GForestCandidatesElement::ExecuteInternal(FPCGContext* Context) const
{
	check(Context);

	const UStage3GForestCandidatesSettings* Settings =
		Context->GetInputSettings<UStage3GForestCandidatesSettings>();
	if (!Settings)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Forest Candidates: settings are unavailable."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	FString SettingsError;
	if (!ValidateSettings(*Settings, SettingsError))
	{
		UE_LOG(
			LogTemp,
			Error,
			TEXT("YACS Forest Candidates: %s"),
			*SettingsError);
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	CyclingSimulation::FRouteGeometryProfile RouteGeometry;
	FString RouteError;
	if (!CyclingSimulation::TryBuildAlpineJourneyRouteGeometry(
		RouteGeometry,
		RouteError))
	{
		UE_LOG(
			LogTemp,
			Error,
			TEXT("YACS Forest Candidates: route geometry failed: %s"),
			*RouteError);
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	if (Settings->EndDistanceM > RouteGeometry.GetTotalLengthM())
	{
		UE_LOG(
			LogTemp,
			Error,
			TEXT("YACS Forest Candidates: forest range exceeds canonical route length."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	FRandomStream Random(Settings->GenerationSeed);
	TArray<TTuple<FTransform, int32>> Candidates;

	const int32 ApproximateStations = FMath::CeilToInt(
		(Settings->EndDistanceM - Settings->StartDistanceM)
		/ Settings->StationSpacingM);
	Candidates.Reserve(
		ApproximateStations
		* Settings->PointsPerSidePerStation
		* 2);

	const double BandWidthM =
		(Settings->MaxLateralOffsetM - Settings->MinLateralOffsetM)
		/ static_cast<double>(Settings->PointsPerSidePerStation);

	for (double StationM = Settings->StartDistanceM;
		StationM < Settings->EndDistanceM;
		StationM += Settings->StationSpacingM)
	{
		const double LongitudinalJitterM =
			Random.FRandRange(
				-0.25 * Settings->StationSpacingM,
				0.25 * Settings->StationSpacingM);
		const double SampleDistanceM = FMath::Clamp(
			StationM + LongitudinalJitterM,
			Settings->StartDistanceM,
			Settings->EndDistanceM);

		FVector RoutePositionM;
		if (!RouteGeometry.TrySamplePosition(
			SampleDistanceM,
			RoutePositionM,
			RouteError))
		{
			UE_LOG(
				LogTemp,
				Error,
				TEXT("YACS Forest Candidates: route sample failed at %.3f m: %s"),
				SampleDistanceM,
				*RouteError);
			Context->OutputData.bCancelExecution = true;
			return true;
		}

		const double TangentHalfWindowM =
			FMath::Min(5.0, Settings->StationSpacingM * 0.25);
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
			UE_LOG(
				LogTemp,
				Error,
				TEXT("YACS Forest Candidates: tangent sampling failed: %s"),
				*RouteError);
			Context->OutputData.bCancelExecution = true;
			return true;
		}

		FVector HorizontalTangent(
			AfterPositionM.X - BeforePositionM.X,
			AfterPositionM.Y - BeforePositionM.Y,
			0.0);
		if (!HorizontalTangent.Normalize())
		{
			UE_LOG(
				LogTemp,
				Error,
				TEXT("YACS Forest Candidates: degenerate horizontal route tangent."));
			Context->OutputData.bCancelExecution = true;
			return true;
		}

		const FVector Lateral(-HorizontalTangent.Y, HorizontalTangent.X, 0.0);

		for (const double SideSign : { -1.0, 1.0 })
		{
			for (int32 BandIndex = 0;
				BandIndex < Settings->PointsPerSidePerStation;
				++BandIndex)
			{
				if (Random.FRand() > Settings->Density)
				{
					continue;
				}

				const double BandMinM =
					Settings->MinLateralOffsetM
					+ BandWidthM * static_cast<double>(BandIndex);
				const double BandMaxM =
					FMath::Min(
						Settings->MaxLateralOffsetM,
						BandMinM + BandWidthM);
				const double LateralOffsetM =
					Random.FRandRange(BandMinM, BandMaxM);

				const FVector CandidateM =
					RoutePositionM + Lateral * (SideSign * LateralOffsetM);
				const double UniformScale =
					Random.FRandRange(
						Settings->MinUniformScale,
						Settings->MaxUniformScale);
				const double YawDeg = Random.FRandRange(0.0, 360.0);

				const FTransform Transform(
					FRotator(0.0, YawDeg, 0.0),
					CandidateM * MetresToCentimetres,
					FVector(UniformScale));
				Candidates.Emplace(Transform, Random.RandHelper(MAX_int32));
			}
		}
	}

	TArray<FPCGTaggedData>& Outputs = Context->OutputData.TaggedData;
	FPCGTaggedData& Output = Outputs.Emplace_GetRef();
	UPCGBasePointData* PointData = FPCGContext::NewPointData_AnyThread(Context);
	Output.Data = PointData;

	PointData->SetNumPoints(Candidates.Num());
	PointData->SetDensity(1.0f);
	PointData->SetSteepness(1.0f);
	PointData->AllocateProperties(
		EPCGPointNativeProperties::Transform
		| EPCGPointNativeProperties::Seed);

	TPCGValueRange<FTransform> TransformRange =
		PointData->GetTransformValueRange(/*bAllocate=*/false);
	TPCGValueRange<int32> SeedRange =
		PointData->GetSeedValueRange(/*bAllocate=*/false);

	for (int32 Index = 0; Index < Candidates.Num(); ++Index)
	{
		TransformRange[Index] = Candidates[Index].Get<0>();
		SeedRange[Index] = Candidates[Index].Get<1>();
	}

	return true;
}

#undef LOCTEXT_NAMESPACE
