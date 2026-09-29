#include "PCG/YacsPatchCandidatesSettings.h"

#include "Data/PCGBasePointData.h"
#include "PCGContext.h"
#include "PCGPin.h"

#define LOCTEXT_NAMESPACE "YacsPatchCandidates"

namespace
{
	constexpr double MetresToCentimetres = 100.0;
	constexpr double MinRandomUnit = 1.0e-9;

	double NextGaussian(FRandomStream& Random)
	{
		const double U1 = FMath::Max(static_cast<double>(Random.FRand()), MinRandomUnit);
		const double U2 = static_cast<double>(Random.FRand());
		return FMath::Sqrt(-2.0 * FMath::Loge(U1))
			* FMath::Cos(2.0 * UE_DOUBLE_PI * U2);
	}

	bool IsInsideExclusion(
		const FVector2D& Point,
		const FYacsPatchRectExclusion& Exclusion)
	{
		if (Exclusion.WidthM <= 0.0 || Exclusion.HeightM <= 0.0)
		{
			return false;
		}

		return FMath::Abs(Point.X - Exclusion.CenterXM) <= Exclusion.WidthM * 0.5
			&& FMath::Abs(Point.Y - Exclusion.CenterYM) <= Exclusion.HeightM * 0.5;
	}
}

#if WITH_EDITOR
FName UYacsPatchCandidatesSettings::GetDefaultNodeName() const
{
	return FName(TEXT("YACSPatchCandidates"));
}

FText UYacsPatchCandidatesSettings::GetDefaultNodeTitle() const
{
	return LOCTEXT("NodeTitle", "YACS Patch Candidates");
}

FText UYacsPatchCandidatesSettings::GetNodeTooltipText() const
{
	return LOCTEXT(
		"NodeTooltip",
		"Generates deterministic clustered points inside an arbitrary bounded "
		"world-authoring patch. Intended for semantic forest/rocks/shrubs/props "
		"composition; route and physics authority remain external.");
}

EPCGSettingsType UYacsPatchCandidatesSettings::GetType() const
{
	return EPCGSettingsType::Spatial;
}
#endif

TArray<FPCGPinProperties> UYacsPatchCandidatesSettings::InputPinProperties() const
{
	return {};
}

TArray<FPCGPinProperties> UYacsPatchCandidatesSettings::OutputPinProperties() const
{
	return DefaultPointOutputPinProperties();
}

FPCGElementPtr UYacsPatchCandidatesSettings::CreateElement() const
{
	return MakeShared<FYacsPatchCandidatesElement>();
}

bool FYacsPatchCandidatesElement::ExecuteInternal(FPCGContext* Context) const
{
	check(Context);

	const UYacsPatchCandidatesSettings* Settings =
		Context->GetInputSettings<UYacsPatchCandidatesSettings>();
	if (!Settings)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: settings are unavailable."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	if (Settings->SizeXM <= 0.0 || Settings->SizeYM <= 0.0)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: patch dimensions must be positive."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}
	if (Settings->PointCount <= 0 || Settings->ClusterCount <= 0)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: point/cluster counts must be positive."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}
	if (Settings->MinSpacingM <= 0.0 || Settings->EdgeMarginM < 0.0)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: spacing/margin contract is invalid."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}
	if (Settings->MinUniformScale <= 0.0
		|| Settings->MaxUniformScale < Settings->MinUniformScale)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: scale range is invalid."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}
	if (Settings->Irregularity < 0.0 || Settings->Irregularity > 1.0)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: irregularity must be inside [0,1]."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}
	if (Settings->SizeXM <= 2.0 * Settings->EdgeMarginM
		|| Settings->SizeYM <= 2.0 * Settings->EdgeMarginM)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: edge margin consumes the patch."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	FRandomStream Random(Settings->GenerationSeed);
	const double CentreMarginX =
		FMath::Max(Settings->EdgeMarginM + 0.5, Settings->SizeXM * 0.16);
	const double CentreMarginY =
		FMath::Max(Settings->EdgeMarginM + 0.5, Settings->SizeYM * 0.16);
	if (Settings->SizeXM <= 2.0 * CentreMarginX
		|| Settings->SizeYM <= 2.0 * CentreMarginY)
	{
		UE_LOG(LogTemp, Error, TEXT("YACS Patch Candidates: patch is too small for clustered placement."));
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	TArray<FVector2D> ClusterCentres;
	ClusterCentres.Reserve(Settings->ClusterCount);
	for (int32 Index = 0; Index < Settings->ClusterCount; ++Index)
	{
		ClusterCentres.Emplace(
			Random.FRandRange(
				-Settings->SizeXM * 0.5 + CentreMarginX,
				Settings->SizeXM * 0.5 - CentreMarginX),
			Random.FRandRange(
				-Settings->SizeYM * 0.5 + CentreMarginY,
				Settings->SizeYM * 0.5 - CentreMarginY));
	}

	const double SigmaX =
		FMath::Max(0.35, Settings->SizeXM * (0.12 + 0.16 * Settings->Irregularity));
	const double SigmaY =
		FMath::Max(0.35, Settings->SizeYM * (0.12 + 0.16 * Settings->Irregularity));
	const double FreeSampleProbability = 0.10 + 0.22 * Settings->Irregularity;
	const double MinSpacingSq = FMath::Square(Settings->MinSpacingM);
	const int32 MaxAttempts = FMath::Max(500, Settings->PointCount * 180);

	TArray<FVector2D> LocalPositions;
	TArray<double> LocalYawDeg;
	TArray<double> UniformScales;
	LocalPositions.Reserve(Settings->PointCount);
	LocalYawDeg.Reserve(Settings->PointCount);
	UniformScales.Reserve(Settings->PointCount);

	for (int32 Attempt = 0;
		Attempt < MaxAttempts && LocalPositions.Num() < Settings->PointCount;
		++Attempt)
	{
		const int32 ClusterIndex = Attempt % Settings->ClusterCount;
		const FVector2D Centre = ClusterCentres[ClusterIndex];

		FVector2D Candidate;
		if (static_cast<double>(Random.FRand()) < FreeSampleProbability)
		{
			Candidate.X = Random.FRandRange(
				-Settings->SizeXM * 0.5 + Settings->EdgeMarginM,
				Settings->SizeXM * 0.5 - Settings->EdgeMarginM);
			Candidate.Y = Random.FRandRange(
				-Settings->SizeYM * 0.5 + Settings->EdgeMarginM,
				Settings->SizeYM * 0.5 - Settings->EdgeMarginM);
		}
		else
		{
			Candidate.X = Centre.X + NextGaussian(Random) * SigmaX;
			Candidate.Y = Centre.Y + NextGaussian(Random) * SigmaY;
		}

		if (Candidate.X < -Settings->SizeXM * 0.5 + Settings->EdgeMarginM
			|| Candidate.X > Settings->SizeXM * 0.5 - Settings->EdgeMarginM
			|| Candidate.Y < -Settings->SizeYM * 0.5 + Settings->EdgeMarginM
			|| Candidate.Y > Settings->SizeYM * 0.5 - Settings->EdgeMarginM)
		{
			continue;
		}

		bool bExcluded = false;
		for (const FYacsPatchRectExclusion& Exclusion : Settings->Exclusions)
		{
			if (IsInsideExclusion(Candidate, Exclusion))
			{
				bExcluded = true;
				break;
			}
		}
		if (bExcluded)
		{
			continue;
		}

		bool bTooClose = false;
		for (const FVector2D& Existing : LocalPositions)
		{
			if (FVector2D::DistSquared(Existing, Candidate) < MinSpacingSq)
			{
				bTooClose = true;
				break;
			}
		}
		if (bTooClose)
		{
			continue;
		}

		LocalPositions.Add(Candidate);
		LocalYawDeg.Add(Random.FRandRange(0.0, 360.0));
		const double ScaleAlpha =
			(static_cast<double>(Random.FRand()) + static_cast<double>(Random.FRand())) * 0.5;
		UniformScales.Add(
			FMath::Lerp(Settings->MinUniformScale, Settings->MaxUniformScale, ScaleAlpha));
	}

	if (LocalPositions.Num() != Settings->PointCount)
	{
		UE_LOG(
			LogTemp,
			Error,
			TEXT("YACS Patch Candidates: placement failed requested=%d placed=%d size=%.2fx%.2fm spacing=%.2fm."),
			Settings->PointCount,
			LocalPositions.Num(),
			Settings->SizeXM,
			Settings->SizeYM,
			Settings->MinSpacingM);
		Context->OutputData.bCancelExecution = true;
		return true;
	}

	const double PatchYawRad = FMath::DegreesToRadians(Settings->PatchYawDeg);
	const double CosYaw = FMath::Cos(PatchYawRad);
	const double SinYaw = FMath::Sin(PatchYawRad);

	TArray<FPCGTaggedData>& Outputs = Context->OutputData.TaggedData;
	FPCGTaggedData& Output = Outputs.Emplace_GetRef();
	UPCGBasePointData* PointData = FPCGContext::NewPointData_AnyThread(Context);
	Output.Data = PointData;

	PointData->SetNumPoints(LocalPositions.Num());
	PointData->SetDensity(1.0f);
	PointData->SetSteepness(1.0f);
	PointData->AllocateProperties(
		EPCGPointNativeProperties::Transform
		| EPCGPointNativeProperties::Seed);

	TPCGValueRange<FTransform> TransformRange =
		PointData->GetTransformValueRange(/*bAllocate=*/false);
	TPCGValueRange<int32> SeedRange =
		PointData->GetSeedValueRange(/*bAllocate=*/false);

	for (int32 Index = 0; Index < LocalPositions.Num(); ++Index)
	{
		const FVector2D Local = LocalPositions[Index];
		const double WorldOffsetXM = Local.X * CosYaw - Local.Y * SinYaw;
		const double WorldOffsetYM = Local.X * SinYaw + Local.Y * CosYaw;
		const FVector PositionCm = Settings->PatchCenterCm + FVector(
			WorldOffsetXM * MetresToCentimetres,
			WorldOffsetYM * MetresToCentimetres,
			0.0);
		const double Scale = UniformScales[Index];

		TransformRange[Index] = FTransform(
			FRotator(0.0, Settings->PatchYawDeg + LocalYawDeg[Index], 0.0),
			PositionCm,
			FVector(Scale));
		SeedRange[Index] = static_cast<int32>(
			HashCombine(GetTypeHash(Settings->GenerationSeed), GetTypeHash(Index)));
	}

	UE_LOG(
		LogTemp,
		Display,
		TEXT("YACS Patch Candidates: generated %d deterministic points in %.2fx%.2fm patch seed=%d."),
		LocalPositions.Num(),
		Settings->SizeXM,
		Settings->SizeYM,
		Settings->GenerationSeed);

	return true;
}

#undef LOCTEXT_NAMESPACE
