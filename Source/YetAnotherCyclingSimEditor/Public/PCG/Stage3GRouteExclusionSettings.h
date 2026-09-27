#pragma once

#include "CoreMinimal.h"
#include "Elements/PCGPointProcessingElementBase.h"
#include "PCGSettings.h"

#include "Stage3GRouteExclusionSettings.generated.h"

// Editor-only PCG bridge for the Stage 3G route-clearance contract.
//
// PCG is a consumer of the authoritative YACS route geometry. This node does
// not inspect road meshes, terrain, actor transforms or PCG-generated output
// to decide where the protected cycling corridor is.
UCLASS(BlueprintType, ClassGroup=(Procedural))
class YETANOTHERCYCLINGSIMEDITOR_API UStage3GRouteExclusionSettings final
	: public UPCGSettings
{
	GENERATED_BODY()

public:
	UPROPERTY(
		EditAnywhere,
		BlueprintReadWrite,
		Category="YACS|Stage3G",
		meta=(ClampMin="0.01", Units="m", PCG_Overridable))
	double ProtectedHalfWidthM = 4.0;

	virtual FName GetDefaultNodeName() const override;
	virtual FText GetDefaultNodeTitle() const override;
	virtual FText GetNodeTooltipText() const override;
	virtual EPCGSettingsType GetType() const override;

protected:
	virtual TArray<FPCGPinProperties> InputPinProperties() const override;
	virtual TArray<FPCGPinProperties> OutputPinProperties() const override;
	virtual FPCGElementPtr CreateElement() const override;
};

class FStage3GRouteExclusionElement final : public FPCGPointProcessingElementBase
{
protected:
	virtual bool ExecuteInternal(FPCGContext* Context) const override;
};
