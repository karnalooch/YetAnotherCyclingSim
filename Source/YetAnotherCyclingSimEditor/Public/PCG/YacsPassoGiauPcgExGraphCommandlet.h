#pragma once

#include "CoreMinimal.h"
#include "Commandlets/Commandlet.h"

#include "YacsPassoGiauPcgExGraphCommandlet.generated.h"

// Creates the repo-owned Passo Giau PCGEx corridor graph from code.
//
// The commandlet is always compiled into the editor module, but it fails closed
// unless the exact PCGEx checkout has been materialized for the authoring run.
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsPassoGiauPcgExGraphCommandlet final
    : public UCommandlet
{
    GENERATED_BODY()

public:
    UYacsPassoGiauPcgExGraphCommandlet();

    virtual int32 Main(const FString& Params) override;
};
