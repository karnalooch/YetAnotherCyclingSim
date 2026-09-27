#include "PCG/Stage3GForestCandidatesSettings.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/Stage3GForestLayout.h"
#include "Data/PCGBasePointData.h"
#include "PCGContext.h"
#include "PCGPin.h"

#define LOCTEXT_NAMESPACE "YacsStage3GForestCandidates"

namespace
{
	constexpr double MetresToCentimetres = 100.0;
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
		"Generates deterministic Stage 3G target-density forest candidates from "
		"the shared forest-layout contract around the canonical YACS route.");
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
		UE_LOG(LogTemp, Error,
			TEXT("YACS Forest Candidates: settings are unavailable."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	CyclingSimulation::FRouteGeometryProfile RouteGeometry;
	FString Error;
	if (!CyclingSimulation::TryBuildAlpineJourneyRouteGeometry(
		RouteGeometry,
		Error))
	{
		UE_LOG(LogTemp, Error,
			TEXT("YACS Forest Candidates: route geometry failed: %s"),
			*Error);
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	CyclingStage3G::FStage3GForestLayoutConfig Config =
		CyclingStage3G::MakeTargetDensityForestConfig();
	Config.StartDistanceM = Settings->StartDistanceM;
	Config.EndDistanceM = Settings->EndDistanceM;
	Config.BaseDensity = Settings->Density;
	Config.PrimaryStationSpacingM = Settings->StationSpacingM;
	Config.PrimaryPointsPerSidePerStation =
		Settings->PointsPerSidePerStation;
	Config.PrimaryMinLateralOffsetM = Settings->MinLateralOffsetM;
	Config.PrimaryMaxLateralOffsetM = Settings->MaxLateralOffsetM;
	Config.PrimaryMinUniformScale = Settings->MinUniformScale;
	Config.PrimaryMaxUniformScale = Settings->MaxUniformScale;
	Config.GenerationSeed = Settings->GenerationSeed;
	Config.LayerProfileVersion = Settings->LayerProfileVersion;

	TArray<CyclingStage3G::FStage3GForestCandidate> Candidates;
	CyclingStage3G::FStage3GForestLayoutStats Stats;
	if (!CyclingStage3G::TryGenerateForestLayout(
		RouteGeometry,
		Config,
		Candidates,
		Stats,
		Error))
	{
		UE_LOG(LogTemp, Error,
			TEXT("YACS Forest Candidates: %s"), *Error);
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	UE_LOG(LogTemp, Display,
		TEXT("YACS Forest Candidates: target-density v1 generated %d points (expected mean %.2f; primary=%d background=%d understory=%d)."),
		Stats.GeneratedCount,
		Stats.ExpectedCandidateMean,
		Stats.PrimaryCount,
		Stats.BackgroundCount,
		Stats.UnderstoryCount);

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
		const CyclingStage3G::FStage3GForestCandidate& Candidate =
			Candidates[Index];
		TransformRange[Index] = FTransform(
			FRotator(0.0, Candidate.YawDeg, 0.0),
			Candidate.PositionM * MetresToCentimetres,
			FVector(Candidate.UniformScale));
		SeedRange[Index] = Candidate.Seed;
	}

	return true;
}

#undef LOCTEXT_NAMESPACE
