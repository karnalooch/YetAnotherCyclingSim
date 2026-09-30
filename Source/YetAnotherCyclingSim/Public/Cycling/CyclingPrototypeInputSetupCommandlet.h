// Copyright YetAnotherCyclingSim. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Commandlets/Commandlet.h"
#include "CyclingPrototypeInputSetupCommandlet.generated.h"

/**
 * One-shot commandlet that creates the Stage 2 Enhanced Input assets
 * referenced by ACyclingPrototypePawn and assigns them to the placed
 * Pawn inside Content/Prototype/Maps/L_CyclingTest.
 *
 * This is the project's safe editor automation workflow for the
 * binary Input Action / Mapping Context assets and the L_CyclingTest
 * binary .umap asset. It must NOT be invoked at runtime. The full
 * dedicated one-shot workflow is:
 *
 *   1. Create (or refresh) one UInputAction asset per action under
 *      /Game/Prototype/Input/. Actions: PowerIncrease, PowerDecrease,
 *      CadenceIncrease, CadenceDecrease, StartRide, StopRide,
 *      RestartRide.
 *   2. Create (or refresh) a single UInputMappingContext under
 *      /Game/Prototype/Input/, mapping:
 *        PowerIncrease   -> Up
 *        PowerDecrease   -> Down
 *        CadenceIncrease -> Right
 *        CadenceDecrease -> Left
 *        StartRide       -> SpaceBar
 *        StopRide        -> S
 *        RestartRide     -> R
 *   3. Load Content/Prototype/Maps/L_CyclingTest.
 *   4. Locate the placed ACyclingPrototypePawn (labelled
 *      "BikePlaceholder") and assign:
 *        DefaultMappingContext  <- the IMC asset
 *        PowerIncreaseAction    <- IA asset
 *        PowerDecreaseAction    <- IA asset
 *        CadenceIncreaseAction  <- IA asset
 *        CadenceDecreaseAction  <- IA asset
 *        StartRideAction        <- IA asset
 *        StopRideAction         <- IA asset
 *        RestartRideAction      <- IA asset
 *      Set bAutoStart = false and AutoPossessPlayer = Player 0 so that
 *      PIE exhibits the documented Slice B behaviour (Ready on entry,
 *      wait for explicit Start input).
 *   5. Save the modified map.
 *   6. Verify both: every input asset is reachable from the placed
 *      Pawn; the Pawn's AutoPossessPlayer is Player0 and bAutoStart
 *      is false. Any deviation is reported and the commandlet returns
 *      non-zero.
 *
 * The commandlet is intended for the home-PC validation cycle; CI does
 * not run it because CI does not build the editor target.
 */
UCLASS()
class UCyclingPrototypeInputSetupCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UCyclingPrototypeInputSetupCommandlet();

	//~ Begin UCommandlet Interface
	virtual int32 Main(const FString& Params) override;
	//~ End UCommandlet Interface
};

#endif // WITH_EDITOR
