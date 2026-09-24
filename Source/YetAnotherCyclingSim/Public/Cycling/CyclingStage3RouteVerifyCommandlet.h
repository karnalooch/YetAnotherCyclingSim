#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Commandlets/Commandlet.h"
#include "CyclingStage3RouteVerifyCommandlet.generated.h"

// Fresh-process verifier for the Stage 3C route asset.
// Run after CyclingStage3RouteSetup so save/reopen persistence is proved by
// loading the binary map again in a separate editor commandlet process.
UCLASS()
class UCyclingStage3RouteVerifyCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UCyclingStage3RouteVerifyCommandlet();
	virtual int32 Main(const FString& Params) override;
};

#endif // WITH_EDITOR
