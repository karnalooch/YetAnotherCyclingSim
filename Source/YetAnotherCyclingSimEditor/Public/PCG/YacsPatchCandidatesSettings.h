#pragma once

#include "CoreMinimal.h"
#include "PCGSettings.h"

#include "YacsPatchCandidatesSettings.generated.h"

USTRUCT(BlueprintType)
struct YETANOTHERCYCLINGSIMEDITOR_API FYacsPatchRectExclusion
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(Units="m"))
	double CenterXM = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(Units="m"))
	double CenterYM = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.0", Units="m"))
	double WidthM = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.0", Units="m"))
	double HeightM = 0.0;
};

// Generic deterministic point generator for bounded YACS world-authoring patches.
//
// The node deliberately has no knowledge of route progression, Passo Giau or a
// specific biome. Repo-owned intents/presets provide the patch bounds and seed;
// downstream PCG nodes decide what semantic asset family is spawned.
UCLASS(BlueprintType, ClassGroup=(Procedural))
class YETANOTHERCYCLINGSIMEDITOR_API UYacsPatchCandidatesSettings final
	: public UPCGSettings
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(Units="cm", PCG_Overridable))
	FVector PatchCenterCm = FVector::ZeroVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.1", Units="m", PCG_Overridable))
	double SizeXM = 10.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.1", Units="m", PCG_Overridable))
	double SizeYM = 10.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(PCG_Overridable))
	double PatchYawDeg = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="1", ClampMax="4096", PCG_Overridable))
	int32 PointCount = 15;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="1", ClampMax="16", PCG_Overridable))
	int32 ClusterCount = 3;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.01", Units="m", PCG_Overridable))
	double MinSpacingM = 0.85;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.0", Units="m", PCG_Overridable))
	double EdgeMarginM = 0.35;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.01", PCG_Overridable))
	double MinUniformScale = 0.82;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.01", PCG_Overridable))
	double MaxUniformScale = 1.22;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(ClampMin="0.0", ClampMax="1.0", PCG_Overridable))
	double Irregularity = 0.82;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring", meta=(PCG_Overridable))
	int32 GenerationSeed = 42017;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|WorldAuthoring")
	TArray<FYacsPatchRectExclusion> Exclusions;

	virtual bool UseSeed() const override { return true; }

#if WITH_EDITOR
	virtual FName GetDefaultNodeName() const override;
	virtual FText GetDefaultNodeTitle() const override;
	virtual FText GetNodeTooltipText() const override;
	virtual EPCGSettingsType GetType() const override;
#endif

protected:
	virtual TArray<FPCGPinProperties> InputPinProperties() const override;
	virtual TArray<FPCGPinProperties> OutputPinProperties() const override;
	virtual FPCGElementPtr CreateElement() const override;
};

class FYacsPatchCandidatesElement final : public IPCGElement
{
protected:
	virtual bool ExecuteInternal(FPCGContext* Context) const override;
};
