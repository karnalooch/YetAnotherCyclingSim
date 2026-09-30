// Copyright YetAnotherCyclingSim. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Commandlets/Commandlet.h"
#include "CyclingPrototypeMapSetupCommandlet.generated.h"

/**
 * One-shot commandlet that prepares Content/Prototype/Maps/L_CyclingTest for
 * the Stage 2 runtime path. It is the project's safe editor automation
 * workflow for the binary .umap asset; it must NOT be invoked at runtime.
 *
 * Operations performed in order, idempotently:
 *
 *   1. Load Content/Prototype/Maps/L_CyclingTest.
 *   2. Remove the temporary AStaticMeshActor placeholder labelled
 *      "BikePlaceholder".
 *   3. Spawn exactly one ACyclingPrototypePawn at world origin with label
 *      "BikePlaceholder".
 *   4. Assign the BP_StraightTestRoute actor reference (resolved by path),
 *      assign the /Engine/BasicShapes/Cube static mesh to the mesh
 *      component, set relative transform for the requested visual size
 *      (~1.8 m x 0.5 m x 1.2 m standing on the road), and enable
 *      bAutoStart for the Slice A PIE proof.
 *   5. Save the map.
 *   6. Run UEditorLoadingAndSavingUtils::CheckMapForErrors and emit one
 *      log line per result.
 *
 * The commandlet is intended for the home-PC validation cycle; CI does
 * not run it because CI does not build the editor target.
 */
UCLASS()
class UCyclingPrototypeMapSetupCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UCyclingPrototypeMapSetupCommandlet();

	//~ Begin UCommandlet Interface
	virtual int32 Main(const FString& Params) override;
	//~ End UCommandlet Interface
};

#endif // WITH_EDITOR