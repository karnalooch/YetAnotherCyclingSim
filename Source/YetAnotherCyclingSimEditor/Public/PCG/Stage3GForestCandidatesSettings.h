#pragma once

#include "CoreMinimal.h"
#include "PCGSettings.h"

#include "Stage3GForestCandidatesSettings.generated.h"

// Editor-only deterministic forest candidate generator for Stage 3G.
//
// WorldSpec owns biome intent (distance range, density and seed). This PCG node
// owns only the presentation algorithm used to turn that intent into candidate
// tree transforms around the canonical YACS route geometry.
UCLASS(BlueprintType, ClassGroup=(Procedural))
class YETANOTHERCYCLINGSIMEDITOR_API UStage3GForestCandidatesSettings final
	: public UPCGSettings
{
	GENERATED_BODY()

public:
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(Units="m", PCG_Overridable))
	double StartDistanceM = 3700.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(Units="m", PCG_Overridable))
	double EndDistanceM = 6200.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="1.0", Units="m", PCG_Overridable))
	double StationSpacingM = 20.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.0", ClampMax="1.0", PCG_Overridable))
	double Density = 0.84;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="1", ClampMax="8", PCG_Overridable))
	int32 PointsPerSidePerStation = 4;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="4.01", Units="m", PCG_Overridable))
	double MinLateralOffsetM = 10.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="4.02", Units="m", PCG_Overridable))
	double MaxLateralOffsetM = 36.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.1", PCG_Overridable))
	double MinUniformScale = 0.95;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="0.1", PCG_Overridable))
	double MaxUniformScale = 1.35;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(PCG_Overridable))
	int32 GenerationSeed = 42017;

	// Versioned presentation algorithm. v2 keeps the three deterministic strata
	// while increasing canopy mass after the v1 visual-density rejection.
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Stage3G", meta=(ClampMin="2", ClampMax="2", PCG_Overridable))
	int32 LayerProfileVersion = 2;

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

class FStage3GForestCandidatesElement final : public IPCGElement
{
protected:
	virtual bool ExecuteInternal(FPCGContext* Context) const override;
};
