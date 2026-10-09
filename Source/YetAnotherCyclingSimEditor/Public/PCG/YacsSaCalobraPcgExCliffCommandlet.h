#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"

#include "YacsSaCalobraPcgExCliffCommandlet.generated.h"

// Executes the Phase 2C presentation-topology experiment entirely transiently.
//
// It consumes the exact Phase 2B classifier/exclusion plan and writes only a
// JSON mesh receipt under Saved/runner temp. It never saves a PCG graph, map,
// DynamicMesh asset or canonical Landscape state.
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsSaCalobraPcgExCliffCommandlet final
    : public UCommandlet
{
    GENERATED_BODY()

public:
    UYacsSaCalobraPcgExCliffCommandlet();

    virtual int32 Main(const FString& Params) override;
};
