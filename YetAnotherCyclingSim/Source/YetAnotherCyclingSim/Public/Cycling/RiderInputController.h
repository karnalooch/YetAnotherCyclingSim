#pragma once

#include "Containers/UnrealString.h"
#include "Cycling/RiderInput.h"

// Configuration of a deterministic rider input controller.
//
// All fields are stored as double precision values. Power values are in
// watts (W); cadence values are in revolutions per minute (rpm).
//
// The controller that owns this configuration validates every field before
// accepting it. See FRiderInputController::TryConfigure for the rules.
struct YETANOTHERCYCLINGSIM_API FRiderInputControllerConfig
{
	// Minimum selectable power in watts (W). Must be finite and non-negative.
	double MinPowerW = 0.0;

	// Maximum selectable power in watts (W). Must be finite and greater than
	// or equal to MinPowerW.
	double MaxPowerW = 2000.0;

	// Adjustment step for power in watts (W). Must be finite and strictly
	// positive.
	double PowerStepW = 10.0;

	// Initial power restored by Reset() in watts (W). Must lie inside the
	// inclusive [MinPowerW, MaxPowerW] range and must be finite.
	double InitialPowerW = 200.0;

	// Minimum selectable cadence in revolutions per minute (rpm). Must be
	// finite and non-negative.
	double MinCadenceRpm = 0.0;

	// Maximum selectable cadence in revolutions per minute (rpm). Must be
	// finite and greater than or equal to MinCadenceRpm.
	double MaxCadenceRpm = 250.0;

	// Adjustment step for cadence in revolutions per minute (rpm). Must be
	// finite and strictly positive.
	double CadenceStepRpm = 5.0;

	// Initial cadence restored by Reset() in revolutions per minute (rpm).
	// Must lie inside the inclusive [MinCadenceRpm, MaxCadenceRpm] range
	// and must be finite.
	double InitialCadenceRpm = 90.0;
};

// Deterministic, rendering-independent rider input controller.
//
// The controller owns a current rider input (power in watts (W) and
// cadence in revolutions per minute (rpm)) and a configuration that
// defines the inclusive operating range and adjustment step for each
// field.
//
// A default-constructed controller starts in a valid state using the
// default configuration. The controller has no direct dependency on
// frame delta, Tick, rendering, random values, system time, or a
// concrete input source; identical configuration and identical command
// sequences always produce identical FRiderInput values.
class YETANOTHERCYCLINGSIM_API FRiderInputController
{
public:
	FRiderInputController();

	// Validates InConfig and, on success, replaces the controller's
	// configuration and resets the current input to the new configured
	// initial values. On failure, the previous configuration and the
	// current input are preserved unchanged and OutError receives the
	// first validation error.
	bool TryConfigure(const FRiderInputControllerConfig& InConfig, FString& OutError);

	// Sets the current power in watts (W). Finite values are clamped to
	// the configured inclusive [MinPowerW, MaxPowerW] range. Non-finite
	// values are rejected without changing the current input. On success,
	// OutError is cleared; on failure, OutError receives a useful message.
	bool TrySetPowerW(double ValueW, FString& OutError);

	// Sets the current cadence in revolutions per minute (rpm). Finite
	// values are clamped to the configured inclusive [MinCadenceRpm,
	// MaxCadenceRpm] range. Non-finite values are rejected without
	// changing the current input. On success, OutError is cleared; on
	// failure, OutError receives a useful message.
	bool TrySetCadenceRpm(double ValueRpm, FString& OutError);

	// Increases the current power by the configured PowerStepW, clamping
	// at MaxPowerW. The addition is performed with a saturating
	// comparison that avoids intermediate floating-point overflow.
	bool TryIncreasePower(FString& OutError);

	// Decreases the current power by the configured PowerStepW, clamping
	// at MinPowerW. The subtraction is performed with a saturating
	// comparison that avoids intermediate floating-point overflow.
	bool TryDecreasePower(FString& OutError);

	// Increases the current cadence by the configured CadenceStepRpm,
	// clamping at MaxCadenceRpm. Saturating comparison avoids overflow.
	bool TryIncreaseCadence(FString& OutError);

	// Decreases the current cadence by the configured CadenceStepRpm,
	// clamping at MinCadenceRpm. Saturating comparison avoids overflow.
	bool TryDecreaseCadence(FString& OutError);

	// Restores the current input to the configured initial power and
	// cadence values.
	void Reset();

	// Returns the current rider input as the physics data contract.
	const FRiderInput& GetInput() const { return Current; }

	// Returns the active configuration.
	const FRiderInputControllerConfig& GetConfig() const { return Config; }

private:
	FRiderInputControllerConfig Config;
	FRiderInput Current;
};
