#pragma once

#include "CoreMinimal.h"
#include "PCGSettings.h"

#include "YacsSaCalobraCliffCellsSettings.generated.h"

// Adapts the frozen Phase 2B Component_230 cliff plan into closed 1 m cell paths.
//
// YACS remains authority for classification and exclusions. This node deliberately
// emits only presentation candidates; PCGEx owns the downstream union / path
// refinement / triangulation in Phase 2C.
UCLASS(BlueprintType, ClassGroup=(Procedural), meta=(DisplayName="YACS Sa Calobra Cliff Cells"))
class YETANOTHERCYCLINGSIMEDITOR_API UYacsSaCalobraCliffCellsSettings final
    : public UPCGSettings
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Sa Calobra")
    FString PlanJsonPath;

    virtual FName GetDefaultNodeName() const override;
    virtual FText GetDefaultNodeTitle() const override;
    virtual FText GetNodeTooltipText() const override;
    virtual EPCGSettingsType GetType() const override;

protected:
    virtual TArray<FPCGPinProperties> InputPinProperties() const override;
    virtual TArray<FPCGPinProperties> OutputPinProperties() const override;
    virtual FPCGElementPtr CreateElement() const override;
};

class FYacsSaCalobraCliffCellsElement final : public IPCGElement
{
protected:
    virtual bool ExecuteInternal(FPCGContext* Context) const override;
};
