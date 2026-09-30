#include "PCG/Stage3GRouteExclusionSettings.h"

#include "Cycling/AlpineJourneyGeometry.h"
#include "Cycling/Stage3GRouteExclusion.h"
#include "PCGContext.h"
#include "PCGData.h"
#include "PCGPin.h"

#define LOCTEXT_NAMESPACE "YacsStage3GRouteExclusion"

FName UStage3GRouteExclusionSettings::GetDefaultNodeName() const
{
	return FName(TEXT("YACSRouteExclusion"));
}

FText UStage3GRouteExclusionSettings::GetDefaultNodeTitle() const
{
	return LOCTEXT("NodeTitle", "YACS Route Exclusion");
}

FText UStage3GRouteExclusionSettings::GetNodeTooltipText() const
{
	return LOCTEXT(
		"NodeTooltip",
		"Rejects PCG points inside the protected horizontal corridor around "
		"the authoritative Stage 3 Alpine route geometry.");
}

EPCGSettingsType UStage3GRouteExclusionSettings::GetType() const
{
	return EPCGSettingsType::Filter;
}

TArray<FPCGPinProperties> UStage3GRouteExclusionSettings::InputPinProperties() const
{
	return {
		FPCGPinProperties(
			FName(TEXT("In")),
			FPCGDataTypeIdentifier(EPCGDataType::Point),
			false,
			true,
			LOCTEXT("InputPinTooltip", "Candidate world points to validate against the route corridor."))
	};
}

TArray<FPCGPinProperties> UStage3GRouteExclusionSettings::OutputPinProperties() const
{
	return {
		FPCGPinProperties(
			FName(TEXT("Out")),
			FPCGDataTypeIdentifier(EPCGDataType::Point),
			false,
			true,
			LOCTEXT("OutputPinTooltip", "Only candidates outside the protected route corridor."))
	};
}

FPCGElementPtr UStage3GRouteExclusionSettings::CreateElement() const
{
	return MakeShared<FStage3GRouteExclusionElement>();
}

bool FStage3GRouteExclusionElement::ExecuteInternal(FPCGContext* Context) const
{
	check(Context);

	const UStage3GRouteExclusionSettings* Settings =
		Context->GetInputSettings<UStage3GRouteExclusionSettings>();
	if (!Settings
		|| !FMath::IsFinite(Settings->ProtectedHalfWidthM)
		|| Settings->ProtectedHalfWidthM <= 0.0)
	{
		UE_LOG(
			LogTemp,
			Error,
			TEXT("YACS Route Exclusion: ProtectedHalfWidthM must be finite and greater than zero."));
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
			TEXT("YACS Route Exclusion: failed to build authoritative route geometry: %s"),
			*RouteError);
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	const double ProtectedHalfWidthM = Settings->ProtectedHalfWidthM;
	const TArray<FPCGTaggedData> Inputs = Context->InputData.GetInputs();
	TArray<FPCGTaggedData>& Outputs = Context->OutputData.TaggedData;

	ProcessPoints(
		Context,
		Inputs,
		Outputs,
		[&RouteGeometry, ProtectedHalfWidthM](
			const FPCGPoint& InPoint,
			FPCGPoint& OutPoint)
		{
			const FVector CandidatePositionM =
				InPoint.Transform.GetLocation() / 100.0;

			CyclingStage3G::FRouteExclusionResult Result;
			FString Error;
			if (!CyclingStage3G::TryEvaluateRouteExclusion(
				RouteGeometry,
				CandidatePositionM,
				ProtectedHalfWidthM,
				Result,
				Error))
			{
				UE_LOG(
					LogTemp,
					Error,
					TEXT("YACS Route Exclusion point rejected after query failure: %s"),
					*Error);
				return false;
			}

			if (Result.bExcluded)
			{
				return false;
			}

			OutPoint = InPoint;
			return true;
		});

	return true;
}

#undef LOCTEXT_NAMESPACE
