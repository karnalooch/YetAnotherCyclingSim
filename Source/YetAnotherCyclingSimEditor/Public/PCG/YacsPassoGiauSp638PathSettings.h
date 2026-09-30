#pragma once

#include "CoreMinimal.h"
#include "PCGSettings.h"

#include "YacsPassoGiauSp638PathSettings.generated.h"

// Emits the prepared official SP638 presentation centerline as ordered PCG points.
//
// This node is deliberately only an adapter. The JSON it consumes is already derived
// from the licensed Regione del Veneto road source by prepare_passo_giau_road.py.
// It must never become authoritative route geometry or cycling-physics input.
UCLASS(BlueprintType, ClassGroup=(Procedural), meta=(DisplayName="YACS SP638 Presentation Path"))
class YETANOTHERCYCLINGSIMEDITOR_API UYacsPassoGiauSp638PathSettings final
    : public UPCGSettings
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Passo Giau")
    FString RoadJsonRelativePath =
        TEXT("ExternalAssets/Terrain/PassoGiau/PreparedRoad/passo_giau_sp638_ue_centerline.json");

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS|Passo Giau")
    bool bUseSplineControlPoints = false;

    virtual FName GetDefaultNodeName() const override;
    virtual FText GetDefaultNodeTitle() const override;
    virtual FText GetNodeTooltipText() const override;
    virtual EPCGSettingsType GetType() const override;

protected:
    virtual TArray<FPCGPinProperties> InputPinProperties() const override;
    virtual TArray<FPCGPinProperties> OutputPinProperties() const override;
    virtual FPCGElementPtr CreateElement() const override;
};

class FYacsPassoGiauSp638PathElement final : public IPCGElement
{
protected:
    virtual bool ExecuteInternal(FPCGContext* Context) const override;
};
