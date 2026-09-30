#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Commandlets/Commandlet.h"
#include "CyclingStage3RouteSetupCommandlet.generated.h"

// One-shot editor commandlet that writes deterministic Stage 3 Alpine
// geometry into the sole route spline and rebuilds the Stage 3E prototype
// terrain/road validation scaffold in L_CyclingTest.
//
// It is intentionally editor-only and idempotent. Runtime physics must never
// read authoritative route progress back from spline/Actor/terrain transforms.
UCLASS()
class UCyclingStage3RouteSetupCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UCyclingStage3RouteSetupCommandlet();
	virtual int32 Main(const FString& Params) override;
};

#endif // WITH_EDITOR
