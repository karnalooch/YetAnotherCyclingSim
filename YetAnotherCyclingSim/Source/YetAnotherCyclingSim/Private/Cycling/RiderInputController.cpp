#include "Cycling/RiderInputController.h"

#include "Cycling/PhysicsValidation.h"

#include "Math/UnrealMathUtility.h"

namespace
{
	// Validates the inclusive-range relation: Min <= Max.
	bool CheckMinMaxRange(double Min, double Max, const TCHAR* MinName, const TCHAR* MaxName, FString& OutError)
	{
		if (Max < Min)
		{
			OutError = FString::Printf(TEXT("%s must be greater than or equal to %s"), MaxName, MinName);
			return false;
		}
		return true;
	}

	// Validates that an inclusive value lies within [Min, Max].
	bool CheckInRange(double Value, double Min, double Max, const TCHAR* ValueName, FString& OutError)
	{
		if (Value < Min || Value > Max)
		{
			OutError = FString::Printf(TEXT("%s must be in the inclusive interval [%f, %f]"), ValueName, Min, Max);
			return false;
		}
		return true;
	}

	// Saturating add: Result = min(Current + Step, Bound).
	// When Step is greater than or equal to the remaining distance to the
	// bound, the result is the bound; otherwise the bounded sum is returned.
	// The comparison is performed before the arithmetic so that the
	// addition is never asked to produce a non-finite intermediate.
	double SaturatingAdd(double Current, double Step, double Bound)
	{
		// If the remaining distance to the bound is less than or equal to
		// the step, clamp to the bound.
		if (!(Step < Bound - Current))
		{
			return Bound;
		}
		return Current + Step;
	}

	// Saturating subtract: Result = max(Current - Step, Bound).
	// When Step is greater than or equal to the remaining distance to the
	// bound, the result is the bound; otherwise the bounded difference is
	// returned. The comparison is performed before the arithmetic.
	double SaturatingSub(double Current, double Step, double Bound)
	{
		// If the remaining distance to the bound is less than or equal to
		// the step, clamp to the bound.
		if (!(Step < Current - Bound))
		{
			return Bound;
		}
		return Current - Step;
	}
}

FRiderInputController::FRiderInputController()
{
	// Config already holds the prototype defaults. Reset the current input
	// to the configured initial values.
	Current.PowerW = Config.InitialPowerW;
	Current.CadenceRpm = Config.InitialCadenceRpm;
}

bool FRiderInputController::TryConfigure(const FRiderInputControllerConfig& InConfig, FString& OutError)
{
	OutError.Reset();
	using namespace CyclingPhysicsValidation;

	// Validation runs in a fixed declaration order. The first failure is
	// the one reported.
	if (!CheckNonNegative(InConfig.MinPowerW, TEXT("min_power_w"), OutError))
	{
		return false;
	}
	if (!CheckFinite(InConfig.MaxPowerW, TEXT("max_power_w"), OutError))
	{
		return false;
	}
	if (!CheckMinMaxRange(InConfig.MinPowerW, InConfig.MaxPowerW, TEXT("min_power_w"), TEXT("max_power_w"), OutError))
	{
		return false;
	}
	if (!CheckPositive(InConfig.PowerStepW, TEXT("power_step_w"), OutError))
	{
		return false;
	}
	if (!CheckFinite(InConfig.InitialPowerW, TEXT("initial_power_w"), OutError))
	{
		return false;
	}
	if (!CheckInRange(InConfig.InitialPowerW, InConfig.MinPowerW, InConfig.MaxPowerW, TEXT("initial_power_w"), OutError))
	{
		return false;
	}
	if (!CheckNonNegative(InConfig.MinCadenceRpm, TEXT("min_cadence_rpm"), OutError))
	{
		return false;
	}
	if (!CheckFinite(InConfig.MaxCadenceRpm, TEXT("max_cadence_rpm"), OutError))
	{
		return false;
	}
	if (!CheckMinMaxRange(InConfig.MinCadenceRpm, InConfig.MaxCadenceRpm, TEXT("min_cadence_rpm"), TEXT("max_cadence_rpm"), OutError))
	{
		return false;
	}
	if (!CheckPositive(InConfig.CadenceStepRpm, TEXT("cadence_step_rpm"), OutError))
	{
		return false;
	}
	if (!CheckFinite(InConfig.InitialCadenceRpm, TEXT("initial_cadence_rpm"), OutError))
	{
		return false;
	}
	if (!CheckInRange(InConfig.InitialCadenceRpm, InConfig.MinCadenceRpm, InConfig.MaxCadenceRpm, TEXT("initial_cadence_rpm"), OutError))
	{
		return false;
	}

	Config = InConfig;
	Current.PowerW = InConfig.InitialPowerW;
	Current.CadenceRpm = InConfig.InitialCadenceRpm;
	return true;
}

bool FRiderInputController::TrySetPowerW(double ValueW, FString& OutError)
{
	OutError.Reset();
	if (!FMath::IsFinite(ValueW))
	{
		OutError = FString::Printf(TEXT("power_w must be a finite number"));
		return false;
	}

	if (ValueW < Config.MinPowerW)
	{
		Current.PowerW = Config.MinPowerW;
		return true;
	}
	if (ValueW > Config.MaxPowerW)
	{
		Current.PowerW = Config.MaxPowerW;
		return true;
	}
	Current.PowerW = ValueW;
	return true;
}

bool FRiderInputController::TrySetCadenceRpm(double ValueRpm, FString& OutError)
{
	OutError.Reset();
	if (!FMath::IsFinite(ValueRpm))
	{
		OutError = FString::Printf(TEXT("cadence_rpm must be a finite number"));
		return false;
	}

	if (ValueRpm < Config.MinCadenceRpm)
	{
		Current.CadenceRpm = Config.MinCadenceRpm;
		return true;
	}
	if (ValueRpm > Config.MaxCadenceRpm)
	{
		Current.CadenceRpm = Config.MaxCadenceRpm;
		return true;
	}
	Current.CadenceRpm = ValueRpm;
	return true;
}

bool FRiderInputController::TryIncreasePower(FString& OutError)
{
	OutError.Reset();
	Current.PowerW = SaturatingAdd(Current.PowerW, Config.PowerStepW, Config.MaxPowerW);
	return true;
}

bool FRiderInputController::TryDecreasePower(FString& OutError)
{
	OutError.Reset();
	Current.PowerW = SaturatingSub(Current.PowerW, Config.PowerStepW, Config.MinPowerW);
	return true;
}

bool FRiderInputController::TryIncreaseCadence(FString& OutError)
{
	OutError.Reset();
	Current.CadenceRpm = SaturatingAdd(Current.CadenceRpm, Config.CadenceStepRpm, Config.MaxCadenceRpm);
	return true;
}

bool FRiderInputController::TryDecreaseCadence(FString& OutError)
{
	OutError.Reset();
	Current.CadenceRpm = SaturatingSub(Current.CadenceRpm, Config.CadenceStepRpm, Config.MinCadenceRpm);
	return true;
}

void FRiderInputController::Reset()
{
	Current.PowerW = Config.InitialPowerW;
	Current.CadenceRpm = Config.InitialCadenceRpm;
}
