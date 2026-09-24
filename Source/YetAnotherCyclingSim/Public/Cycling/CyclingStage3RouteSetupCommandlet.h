#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Commandlets/Commandlet.h"
#include "CyclingStage3RouteSetupCommandlet.generated.h"

// One-shot editor commandlet that writes the deterministic Stage 3C Alpine
// geometry into the sole route actor's USplineComponent in L_CyclingTest.
//
// It is intentionally editor-only and idempotent. Runtime physics must never
// read authoritative route progress back from the spline/Actor transform.
UCLASS()
class UCyclingStage3RouteSetupCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UCyclingStage3RouteSetupCommandlet();
	virtual int32 Main(const FString& Params) override;
};

#endif // WITH_EDITOR
