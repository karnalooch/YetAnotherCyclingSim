#pragma once

#include "CoreMinimal.h"
#include "PCGSettings.h"

#include "Stage3GBiomeCandidatesSettings.generated.h"

// Editor-only deterministic candidate generator for Stage 3G biome dressing.
//
// WorldSpec owns biome intent (distance range, density and seed). This PCG node
// owns only the presentation algorithm that turns that intent into candidate
// transforms around the canonical YACS route geometry.
UCLASS(BlueprintType, ClassGroup=(Procedural))
class YETANOTHERCYCLINGSIMEDITOR_API UStage3GBiomeCandidatesSettings final
	: public UPCGSettings
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(Units="m", PCG_Overridable))
	double StartDistanceM = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(Units="m", PCG_Overridable))
	double EndDistanceM = 3700.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="1.0", Units="m", PCG_Overridable))
	double StationSpacingM = 70.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.0", ClampMax="1.0", PCG_Overridable))
	double Density = 0.10;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="1", ClampMax="8", PCG_Overridable))
	int32 PointsPerSidePerStation = 2;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.01", Units="m", PCG_Overridable))
	double MinLateralOffsetM = 12.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.02", Units="m", PCG_Overridable))
	double MaxLateralOffsetM = 80.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.1", PCG_Overridable))
	double MinUniformScale = 0.55;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.1", PCG_Overridable))
	double MaxUniformScale = 1.20;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(PCG_Overridable))
	int32 GenerationSeed = 42017;

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

class FStage3GBiomeCandidatesElement final : public IPCGElement
{
protected:
	virtual bool ExecuteInternal(FPCGContext* Context) const override;
};
