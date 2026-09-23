// Copyright YetAnotherCyclingSim. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Commandlets/Commandlet.h"
#include "CyclingPrototypeMapVerifyCommandlet.generated.h"

/**
 * One-shot verification commandlet for L_CyclingTest. Used after the
 * CyclingPrototypeMapSetupCommandlet runs and after every editor reopen.
 *
 * Operations performed in order:
 *
 *   1. Load Content/Prototype/Maps/L_CyclingTest.
 *   2. Enumerate actors and verify exactly one ACyclingPrototypePawn with
 *      label "BikePlaceholder", exactly one route Actor with exactly one
 *      USplineComponent, no leftover StaticMeshActor placeholder.
 *   3. Verify Pawn has a non-null RouteActor reference, a non-null
 *      BicycleMesh with a static mesh assigned, the requested relative
 *      scale/location, and bAutoStart == true.
	 *   4. (Optional, when -DriveSeconds=N is passed) start a transient
	 *      runtime-path simulation, drive rendered ticks for at most N
	 *      seconds, and require Finished with presentation clamped and Tick
	 *      disabled.
 */
UCLASS()
class UCyclingPrototypeMapVerifyCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UCyclingPrototypeMapVerifyCommandlet();

	//~ Begin UCommandlet Interface
	virtual int32 Main(const FString& Params) override;
	//~ End UCommandlet Interface
};

#endif // WITH_EDITOR
