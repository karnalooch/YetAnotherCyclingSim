#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"
#include <limits>

#include "Cycling/RiderInputController.h"
#include "Cycling/RiderInput.h"

namespace RiderInputControllerTest
{
	const double NaNValue = std::numeric_limits<double>::quiet_NaN();
	const double PositiveInfinity = std::numeric_limits<double>::infinity();
	const double NegativeInfinity = -std::numeric_limits<double>::infinity();
	const double DoubleMax = std::numeric_limits<double>::max();
	const double DoubleMaxOverTwo = std::numeric_limits<double>::max() / 2.0;

	FRiderInputControllerConfig MakeDefaultConfig()
	{
		FRiderInputControllerConfig Config;
		Config.MinPowerW = 0.0;
		Config.MaxPowerW = 2000.0;
		Config.PowerStepW = 10.0;
		Config.InitialPowerW = 200.0;
		Config.MinCadenceRpm = 0.0;
		Config.MaxCadenceRpm = 250.0;
		Config.CadenceStepRpm = 5.0;
		Config.InitialCadenceRpm = 90.0;
		return Config;
	}

	FRiderInputControllerConfig MakeLargeConfig()
	{
		FRiderInputControllerConfig Config;
		Config.MinPowerW = 0.0;
		Config.MaxPowerW = DoubleMax;
		Config.PowerStepW = DoubleMax;
		Config.InitialPowerW = DoubleMaxOverTwo;
		Config.MinCadenceRpm = 0.0;
		Config.MaxCadenceRpm = DoubleMax;
		Config.CadenceStepRpm = DoubleMax;
		Config.InitialCadenceRpm = DoubleMaxOverTwo;
		return Config;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FRiderInputControllerTest, "CyclingInput.RiderInputController",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FRiderInputControllerTest::RunTest(const FString& Parameters)
{
	using namespace RiderInputControllerTest;

	// --- Requirement 1: Default configuration values are exact. ---

	{
		const FRiderInputControllerConfig DefaultConfig;
		TestEqual(TEXT("default MinPowerW"), DefaultConfig.MinPowerW, 0.0);
		TestEqual(TEXT("default MaxPowerW"), DefaultConfig.MaxPowerW, 2000.0);
		TestEqual(TEXT("default PowerStepW"), DefaultConfig.PowerStepW, 10.0);
		TestEqual(TEXT("default InitialPowerW"), DefaultConfig.InitialPowerW, 200.0);
		TestEqual(TEXT("default MinCadenceRpm"), DefaultConfig.MinCadenceRpm, 0.0);
		TestEqual(TEXT("default MaxCadenceRpm"), DefaultConfig.MaxCadenceRpm, 250.0);
		TestEqual(TEXT("default CadenceStepRpm"), DefaultConfig.CadenceStepRpm, 5.0);
		TestEqual(TEXT("default InitialCadenceRpm"), DefaultConfig.InitialCadenceRpm, 90.0);
	}

	// --- Requirement 2: Default controller input is exactly 200 W and 90 rpm. ---

	{
		FRiderInputController Controller;
		TestEqual(TEXT("default power"), Controller.GetInput().PowerW, 200.0);
		TestEqual(TEXT("default cadence"), Controller.GetInput().CadenceRpm, 90.0);
	}

	// --- Requirement 3: Valid custom configuration accepted; initial values published. ---

	{
		FRiderInputControllerConfig Config;
		Config.MinPowerW = 50.0;
		Config.MaxPowerW = 800.0;
		Config.PowerStepW = 25.0;
		Config.InitialPowerW = 150.0;
		Config.MinCadenceRpm = 30.0;
		Config.MaxCadenceRpm = 180.0;
		Config.CadenceStepRpm = 3.0;
		Config.InitialCadenceRpm = 75.0;

		FRiderInputController Controller;
		FString Error = TEXT("stale");
		const bool bConfigured = Controller.TryConfigure(Config, Error);
		TestTrue(TEXT("valid custom config accepted"), bConfigured);
		if (bConfigured)
		{
			TestTrue(TEXT("valid config clears error"), Error.IsEmpty());
			TestEqual(TEXT("config published: MinPowerW"), Controller.GetConfig().MinPowerW, 50.0);
			TestEqual(TEXT("config published: MaxPowerW"), Controller.GetConfig().MaxPowerW, 800.0);
			TestEqual(TEXT("config published: PowerStepW"), Controller.GetConfig().PowerStepW, 25.0);
			TestEqual(TEXT("config published: InitialPowerW"), Controller.GetConfig().InitialPowerW, 150.0);
			TestEqual(TEXT("config published: MinCadenceRpm"), Controller.GetConfig().MinCadenceRpm, 30.0);
			TestEqual(TEXT("config published: MaxCadenceRpm"), Controller.GetConfig().MaxCadenceRpm, 180.0);
			TestEqual(TEXT("config published: CadenceStepRpm"), Controller.GetConfig().CadenceStepRpm, 3.0);
			TestEqual(TEXT("config published: InitialCadenceRpm"), Controller.GetConfig().InitialCadenceRpm, 75.0);
			TestEqual(TEXT("initial power published"), Controller.GetInput().PowerW, 150.0);
			TestEqual(TEXT("initial cadence published"), Controller.GetInput().CadenceRpm, 75.0);
		}
	}

	// --- Requirement 4: Every config field rejects NaN, +Inf, -Inf. ---

	{
		// Helper: try configure with one field replaced by BadValue, expect failure + non-empty error.
		auto ExpectFieldRejects = [&](const TCHAR* Label, double BadValue, auto Setter)
		{
			FRiderInputControllerConfig Config = MakeDefaultConfig();
			Setter(Config, BadValue);
			FRiderInputController Controller;
			FString Error;
			TestFalse(FString::Printf(TEXT("%s rejects non-finite"), Label), Controller.TryConfigure(Config, Error));
			TestTrue(FString::Printf(TEXT("%s error non-empty"), Label), !Error.IsEmpty());
		};

		ExpectFieldRejects(TEXT("MinPowerW=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.MinPowerW = V; });
		ExpectFieldRejects(TEXT("MinPowerW=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MinPowerW = V; });
		ExpectFieldRejects(TEXT("MinPowerW=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MinPowerW = V; });

		ExpectFieldRejects(TEXT("MaxPowerW=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.MaxPowerW = V; });
		ExpectFieldRejects(TEXT("MaxPowerW=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MaxPowerW = V; });
		ExpectFieldRejects(TEXT("MaxPowerW=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MaxPowerW = V; });

		ExpectFieldRejects(TEXT("PowerStepW=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.PowerStepW = V; });
		ExpectFieldRejects(TEXT("PowerStepW=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.PowerStepW = V; });
		ExpectFieldRejects(TEXT("PowerStepW=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.PowerStepW = V; });

		ExpectFieldRejects(TEXT("InitialPowerW=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.InitialPowerW = V; });
		ExpectFieldRejects(TEXT("InitialPowerW=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.InitialPowerW = V; });
		ExpectFieldRejects(TEXT("InitialPowerW=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.InitialPowerW = V; });

		ExpectFieldRejects(TEXT("MinCadenceRpm=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.MinCadenceRpm = V; });
		ExpectFieldRejects(TEXT("MinCadenceRpm=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MinCadenceRpm = V; });
		ExpectFieldRejects(TEXT("MinCadenceRpm=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MinCadenceRpm = V; });

		ExpectFieldRejects(TEXT("MaxCadenceRpm=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.MaxCadenceRpm = V; });
		ExpectFieldRejects(TEXT("MaxCadenceRpm=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MaxCadenceRpm = V; });
		ExpectFieldRejects(TEXT("MaxCadenceRpm=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.MaxCadenceRpm = V; });

		ExpectFieldRejects(TEXT("CadenceStepRpm=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.CadenceStepRpm = V; });
		ExpectFieldRejects(TEXT("CadenceStepRpm=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.CadenceStepRpm = V; });
		ExpectFieldRejects(TEXT("CadenceStepRpm=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.CadenceStepRpm = V; });

		ExpectFieldRejects(TEXT("InitialCadenceRpm=NaN"), NaNValue,
			[](FRiderInputControllerConfig& C, double V) { C.InitialCadenceRpm = V; });
		ExpectFieldRejects(TEXT("InitialCadenceRpm=+Inf"), PositiveInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.InitialCadenceRpm = V; });
		ExpectFieldRejects(TEXT("InitialCadenceRpm=-Inf"), NegativeInfinity,
			[](FRiderInputControllerConfig& C, double V) { C.InitialCadenceRpm = V; });
	}

	// --- Requirement 5: Negative power minimum and cadence minimum rejected. ---

	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.MinPowerW = -1.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("negative MinPowerW rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}
	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.MinCadenceRpm = -1.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("negative MinCadenceRpm rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}

	// --- Requirement 6: Max below min rejected (power and cadence). ---

	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.MaxPowerW = -10.0; // below MinPowerW = 0
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("MaxPowerW below MinPowerW rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}
	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.MaxCadenceRpm = -10.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("MaxCadenceRpm below MinCadenceRpm rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}

	// --- Requirement 7: Zero and negative power step rejected. ---

	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.PowerStepW = 0.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("zero PowerStepW rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}
	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.PowerStepW = -5.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("negative PowerStepW rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}

	// --- Requirement 8: Zero and negative cadence step rejected. ---

	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.CadenceStepRpm = 0.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("zero CadenceStepRpm rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}
	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.CadenceStepRpm = -5.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("negative CadenceStepRpm rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}

	// --- Requirement 9: Initial power below and above its inclusive range rejected. ---

	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.InitialPowerW = -1.0; // below MinPowerW=0
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("InitialPowerW below range rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}
	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.InitialPowerW = 5000.0; // above MaxPowerW=2000
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("InitialPowerW above range rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}

	// --- Requirement 10: Initial cadence below and above its inclusive range rejected. ---

	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.InitialCadenceRpm = -1.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("InitialCadenceRpm below range rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}
	{
		FRiderInputControllerConfig Config = MakeDefaultConfig();
		Config.InitialCadenceRpm = 500.0;
		FRiderInputController Controller;
		FString Error;
		TestFalse(TEXT("InitialCadenceRpm above range rejected"), Controller.TryConfigure(Config, Error));
		TestTrue(TEXT("error non-empty"), !Error.IsEmpty());
	}

	// --- Requirement 11: Failed reconfiguration preserves every previous field and both input values. ---

	{
		FRiderInputControllerConfig GoodConfig;
		GoodConfig.MinPowerW = 0.0;
		GoodConfig.MaxPowerW = 1000.0;
		GoodConfig.PowerStepW = 10.0;
		GoodConfig.InitialPowerW = 300.0;
		GoodConfig.MinCadenceRpm = 0.0;
		GoodConfig.MaxCadenceRpm = 200.0;
		GoodConfig.CadenceStepRpm = 5.0;
		GoodConfig.InitialCadenceRpm = 80.0;

		FRiderInputController Controller;
		FString Error;
		const bool bGoodConfig = Controller.TryConfigure(GoodConfig, Error);
		TestTrue(TEXT("good config accepted"), bGoodConfig);

		// Mutate the input so we can verify it is NOT reset by a failed reconfigure.
		const bool bSetPower = Controller.TrySetPowerW(500.0, Error);
		TestTrue(TEXT("set power 500"), bSetPower);
		const bool bSetCadence = Controller.TrySetCadenceRpm(120.0, Error);
		TestTrue(TEXT("set cadence 120"), bSetCadence);

		if (bGoodConfig && bSetPower && bSetCadence)
		{
			const FRiderInputControllerConfig PrevConfig = Controller.GetConfig();
			const double PrevPower = Controller.GetInput().PowerW;
			const double PrevCadence = Controller.GetInput().CadenceRpm;

			// Attempt a bad reconfiguration.
			FRiderInputControllerConfig BadConfig = GoodConfig;
			BadConfig.MaxPowerW = -100.0; // invalid: below MinPowerW
			const bool bBadConfig = Controller.TryConfigure(BadConfig, Error);
			TestFalse(TEXT("bad reconfiguration rejected"), bBadConfig);
			TestTrue(TEXT("error non-empty"), !Error.IsEmpty());

			// Every field of the previous configuration must be preserved exactly.
			TestEqual(TEXT("MinPowerW preserved"), Controller.GetConfig().MinPowerW, PrevConfig.MinPowerW);
			TestEqual(TEXT("MaxPowerW preserved"), Controller.GetConfig().MaxPowerW, PrevConfig.MaxPowerW);
			TestEqual(TEXT("PowerStepW preserved"), Controller.GetConfig().PowerStepW, PrevConfig.PowerStepW);
			TestEqual(TEXT("InitialPowerW preserved"), Controller.GetConfig().InitialPowerW, PrevConfig.InitialPowerW);
			TestEqual(TEXT("MinCadenceRpm preserved"), Controller.GetConfig().MinCadenceRpm, PrevConfig.MinCadenceRpm);
			TestEqual(TEXT("MaxCadenceRpm preserved"), Controller.GetConfig().MaxCadenceRpm, PrevConfig.MaxCadenceRpm);
			TestEqual(TEXT("CadenceStepRpm preserved"), Controller.GetConfig().CadenceStepRpm, PrevConfig.CadenceStepRpm);
			TestEqual(TEXT("InitialCadenceRpm preserved"), Controller.GetConfig().InitialCadenceRpm, PrevConfig.InitialCadenceRpm);

			// Current input must be preserved exactly.
			TestEqual(TEXT("power preserved"), Controller.GetInput().PowerW, PrevPower);
			TestEqual(TEXT("cadence preserved"), Controller.GetInput().CadenceRpm, PrevCadence);
		}
	}

	// --- Requirement 12: Power setter: in-range accepted, below/above clamp. ---

	{
		FRiderInputController Controller;
		FString Error;

		const bool bSet1 = Controller.TrySetPowerW(123.4, Error);
		TestTrue(TEXT("power setter in-range accepted"), bSet1);
		if (bSet1)
		{
			TestEqual(TEXT("power setter in-range value"), Controller.GetInput().PowerW, 123.4);
		}

		const bool bSet2 = Controller.TrySetPowerW(-50.0, Error);
		TestTrue(TEXT("power setter below min clamps"), bSet2);
		if (bSet2)
		{
			TestEqual(TEXT("power clamped to min"), Controller.GetInput().PowerW, 0.0);
		}

		const bool bSet3 = Controller.TrySetPowerW(9999.0, Error);
		TestTrue(TEXT("power setter above max clamps"), bSet3);
		if (bSet3)
		{
			TestEqual(TEXT("power clamped to max"), Controller.GetInput().PowerW, 2000.0);
		}
	}

	// --- Requirement 13: Cadence setter: in-range accepted, below/above clamp. ---

	{
		FRiderInputController Controller;
		FString Error;

		const bool bSet1 = Controller.TrySetCadenceRpm(77.0, Error);
		TestTrue(TEXT("cadence setter in-range accepted"), bSet1);
		if (bSet1)
		{
			TestEqual(TEXT("cadence setter in-range value"), Controller.GetInput().CadenceRpm, 77.0);
		}

		const bool bSet2 = Controller.TrySetCadenceRpm(-10.0, Error);
		TestTrue(TEXT("cadence setter below min clamps"), bSet2);
		if (bSet2)
		{
			TestEqual(TEXT("cadence clamped to min"), Controller.GetInput().CadenceRpm, 0.0);
		}

		const bool bSet3 = Controller.TrySetCadenceRpm(999.0, Error);
		TestTrue(TEXT("cadence setter above max clamps"), bSet3);
		if (bSet3)
		{
			TestEqual(TEXT("cadence clamped to max"), Controller.GetInput().CadenceRpm, 250.0);
		}
	}

	// --- Requirement 14: Both setters reject NaN/+Inf/-Inf without changing either field. ---

	{
		FRiderInputController Controller;
		FString Error;
		// Establish known input.
		const bool bSeedPower = Controller.TrySetPowerW(123.0, Error);
		TestTrue(TEXT("seed power"), bSeedPower);
		const bool bSeedCadence = Controller.TrySetCadenceRpm(45.0, Error);
		TestTrue(TEXT("seed cadence"), bSeedCadence);
		if (!(bSeedPower && bSeedCadence))
		{
			return false;
		}
		const double SeedPower = Controller.GetInput().PowerW;
		const double SeedCadence = Controller.GetInput().CadenceRpm;

		for (double BadPower : { NaNValue, PositiveInfinity, NegativeInfinity })
		{
			FString OutError = TEXT("stale");
			const bool bSet = Controller.TrySetPowerW(BadPower, OutError);
			TestFalse(FString::Printf(TEXT("TrySetPowerW rejects non-finite %f"), BadPower), bSet);
			TestTrue(TEXT("error non-empty"), !OutError.IsEmpty());
			// Immediately verify both fields still equal the seed values after this rejection.
			TestEqual(TEXT("power unchanged after non-finite power reject"), Controller.GetInput().PowerW, SeedPower);
			TestEqual(TEXT("cadence unchanged after non-finite power reject"), Controller.GetInput().CadenceRpm, SeedCadence);
		}
		for (double BadCadence : { NaNValue, PositiveInfinity, NegativeInfinity })
		{
			FString OutError = TEXT("stale");
			const bool bSet = Controller.TrySetCadenceRpm(BadCadence, OutError);
			TestFalse(FString::Printf(TEXT("TrySetCadenceRpm rejects non-finite %f"), BadCadence), bSet);
			TestTrue(TEXT("error non-empty"), !OutError.IsEmpty());
			// Immediately verify both fields still equal the seed values after this rejection.
			TestEqual(TEXT("power unchanged after non-finite cadence reject"), Controller.GetInput().PowerW, SeedPower);
			TestEqual(TEXT("cadence unchanged after non-finite cadence reject"), Controller.GetInput().CadenceRpm, SeedCadence);
		}
	}

	// --- Requirement 15: Increase and decrease power use exactly PowerStepW. ---

	{
		FRiderInputController Controller;
		FString Error;
		// Defaults: InitialPowerW=200, PowerStepW=10, Min=0, Max=2000.
		const bool bInc1 = Controller.TryIncreasePower(Error);
		TestTrue(TEXT("increase power"), bInc1);
		if (bInc1)
		{
			TestEqual(TEXT("increased by exactly one step"), Controller.GetInput().PowerW, 210.0);
		}
		const bool bDec1 = Controller.TryDecreasePower(Error);
		TestTrue(TEXT("decrease power"), bDec1);
		if (bDec1)
		{
			TestEqual(TEXT("decreased by exactly one step"), Controller.GetInput().PowerW, 200.0);
		}
		// Two increases.
		const bool bInc2 = Controller.TryIncreasePower(Error);
		TestTrue(TEXT("increase #2"), bInc2);
		const bool bInc3 = Controller.TryIncreasePower(Error);
		TestTrue(TEXT("increase #3"), bInc3);
		if (bInc2 && bInc3)
		{
			TestEqual(TEXT("two steps up"), Controller.GetInput().PowerW, 220.0);
		}
	}

	// --- Requirement 16: Increase and decrease cadence use exactly CadenceStepRpm. ---

	{
		FRiderInputController Controller;
		FString Error;
		// Defaults: InitialCadenceRpm=90, CadenceStepRpm=5, Min=0, Max=250.
		const bool bInc1 = Controller.TryIncreaseCadence(Error);
		TestTrue(TEXT("increase cadence"), bInc1);
		if (bInc1)
		{
			TestEqual(TEXT("increased by exactly one step"), Controller.GetInput().CadenceRpm, 95.0);
		}
		const bool bDec1 = Controller.TryDecreaseCadence(Error);
		TestTrue(TEXT("decrease cadence"), bDec1);
		if (bDec1)
		{
			TestEqual(TEXT("decreased by exactly one step"), Controller.GetInput().CadenceRpm, 90.0);
		}
		const bool bInc2 = Controller.TryIncreaseCadence(Error);
		TestTrue(TEXT("increase cadence #2"), bInc2);
		const bool bInc3 = Controller.TryIncreaseCadence(Error);
		TestTrue(TEXT("increase cadence #3"), bInc3);
		if (bInc2 && bInc3)
		{
			TestEqual(TEXT("two steps up"), Controller.GetInput().CadenceRpm, 100.0);
		}
	}

	// --- Requirement 17: Repeated adjustments clamp at all four boundaries. ---

	{
		// Min power.
		FRiderInputController ControllerA;
		FString Error;
		bool bAllDecreasesToMinSucceeded = true;
		for (int32 i = 0; i < 1000; ++i)
		{
			const bool bStepSucceeded = ControllerA.TryDecreasePower(Error);
			bAllDecreasesToMinSucceeded = bAllDecreasesToMinSucceeded && bStepSucceeded;
		}
		TestTrue(TEXT("every decrease-to-min power step succeeded"), bAllDecreasesToMinSucceeded);
		if (bAllDecreasesToMinSucceeded)
		{
			TestEqual(TEXT("power clamped at min"), ControllerA.GetInput().PowerW, 0.0);
		}

		// Max power.
		FRiderInputController ControllerB;
		bool bAllIncreasesToMaxSucceeded = true;
		for (int32 i = 0; i < 1000; ++i)
		{
			const bool bStepSucceeded = ControllerB.TryIncreasePower(Error);
			bAllIncreasesToMaxSucceeded = bAllIncreasesToMaxSucceeded && bStepSucceeded;
		}
		TestTrue(TEXT("every increase-to-max power step succeeded"), bAllIncreasesToMaxSucceeded);
		if (bAllIncreasesToMaxSucceeded)
		{
			TestEqual(TEXT("power clamped at max"), ControllerB.GetInput().PowerW, 2000.0);
		}

		// Min cadence.
		FRiderInputController ControllerC;
		bool bAllDecreasesCadenceToMinSucceeded = true;
		for (int32 i = 0; i < 1000; ++i)
		{
			const bool bStepSucceeded = ControllerC.TryDecreaseCadence(Error);
			bAllDecreasesCadenceToMinSucceeded = bAllDecreasesCadenceToMinSucceeded && bStepSucceeded;
		}
		TestTrue(TEXT("every decrease-to-min cadence step succeeded"), bAllDecreasesCadenceToMinSucceeded);
		if (bAllDecreasesCadenceToMinSucceeded)
		{
			TestEqual(TEXT("cadence clamped at min"), ControllerC.GetInput().CadenceRpm, 0.0);
		}

		// Max cadence.
		FRiderInputController ControllerD;
		bool bAllIncreasesCadenceToMaxSucceeded = true;
		for (int32 i = 0; i < 1000; ++i)
		{
			const bool bStepSucceeded = ControllerD.TryIncreaseCadence(Error);
			bAllIncreasesCadenceToMaxSucceeded = bAllIncreasesCadenceToMaxSucceeded && bStepSucceeded;
		}
		TestTrue(TEXT("every increase-to-max cadence step succeeded"), bAllIncreasesCadenceToMaxSucceeded);
		if (bAllIncreasesCadenceToMaxSucceeded)
		{
			TestEqual(TEXT("cadence clamped at max"), ControllerD.GetInput().CadenceRpm, 250.0);
		}
	}

	// --- Requirement 18: Large finite values; saturating logic avoids overflow. ---

	{
		// Use very large finite config. A naive `Current + Step` from
		// DoubleMax/2 + DoubleMax overflows IEEE 754 to +infinity.
		// The saturating logic must clamp to MaxPowerW = DoubleMax.
		FRiderInputControllerConfig LargeConfig = MakeLargeConfig();
		FRiderInputController Controller;
		FString Error;
		const bool bConfigured = Controller.TryConfigure(LargeConfig, Error);
		TestTrue(TEXT("large config accepted"), bConfigured);
		if (bConfigured)
		{
			TestEqual(TEXT("large config initial power"), Controller.GetInput().PowerW, DoubleMaxOverTwo);
			TestEqual(TEXT("large config initial cadence"), Controller.GetInput().CadenceRpm, DoubleMaxOverTwo);

			// Increase power: Step = DoubleMax, Remaining = DoubleMax/2.
			// Naive (DoubleMax/2 + DoubleMax) overflows to +inf.
			// Saturating clamps to MaxPowerW = DoubleMax.
			const bool bIncP = Controller.TryIncreasePower(Error);
			TestTrue(TEXT("large increase power succeeds"), bIncP);
			if (bIncP)
			{
				TestEqual(TEXT("large increase power clamped to max"), Controller.GetInput().PowerW, DoubleMax);
				TestTrue(TEXT("power is finite after large increase"), FMath::IsFinite(Controller.GetInput().PowerW));
			}

			// Decrease power: Step = DoubleMax, Remaining = DoubleMax/2.
			// Naive (DoubleMax - DoubleMax) = 0 (no overflow but wrong bound path);
			// the saturating logic clamps to MinPowerW = 0 regardless because
			// Step >= Remaining. This exercises the same clamp mechanism.
			const bool bDecP = Controller.TryDecreasePower(Error);
			TestTrue(TEXT("large decrease power succeeds"), bDecP);
			if (bDecP)
			{
				TestEqual(TEXT("large decrease power clamped to min"), Controller.GetInput().PowerW, 0.0);
				TestTrue(TEXT("power is finite after large decrease"), FMath::IsFinite(Controller.GetInput().PowerW));
			}

			// Increase cadence: same overflow risk.
			const bool bIncC = Controller.TryIncreaseCadence(Error);
			TestTrue(TEXT("large increase cadence succeeds"), bIncC);
			if (bIncC)
			{
				TestEqual(TEXT("large increase cadence clamped to max"), Controller.GetInput().CadenceRpm, DoubleMax);
				TestTrue(TEXT("cadence is finite after large increase"), FMath::IsFinite(Controller.GetInput().CadenceRpm));
			}

			// Decrease cadence: clamp to min.
			const bool bDecC = Controller.TryDecreaseCadence(Error);
			TestTrue(TEXT("large decrease cadence succeeds"), bDecC);
			if (bDecC)
			{
				TestEqual(TEXT("large decrease cadence clamped to min"), Controller.GetInput().CadenceRpm, 0.0);
				TestTrue(TEXT("cadence is finite after large decrease"), FMath::IsFinite(Controller.GetInput().CadenceRpm));
			}
		}
	}

	// --- Requirement 19: Reset restores configured initial power and cadence exactly. ---

	{
		FRiderInputControllerConfig Config;
		Config.MinPowerW = 10.0;
		Config.MaxPowerW = 500.0;
		Config.PowerStepW = 20.0;
		Config.InitialPowerW = 77.0;
		Config.MinCadenceRpm = 20.0;
		Config.MaxCadenceRpm = 150.0;
		Config.CadenceStepRpm = 4.0;
		Config.InitialCadenceRpm = 66.0;

		FRiderInputController Controller;
		FString Error;
		const bool bConfigured = Controller.TryConfigure(Config, Error);
		TestTrue(TEXT("config accepted"), bConfigured);
		if (bConfigured)
		{
			// Mutate input away from initial.
			const bool bIncP1 = Controller.TryIncreasePower(Error);
			TestTrue(TEXT("mutate inc power 1"), bIncP1);
			const bool bIncP2 = Controller.TryIncreasePower(Error);
			TestTrue(TEXT("mutate inc power 2"), bIncP2);
			const bool bIncP3 = Controller.TryIncreasePower(Error);
			TestTrue(TEXT("mutate inc power 3"), bIncP3);
			const bool bIncC1 = Controller.TryIncreaseCadence(Error);
			TestTrue(TEXT("mutate inc cadence 1"), bIncC1);
			const bool bIncC2 = Controller.TryIncreaseCadence(Error);
			TestTrue(TEXT("mutate inc cadence 2"), bIncC2);
			if (bIncP1 && bIncP2 && bIncP3 && bIncC1 && bIncC2)
			{
				TestEqual(TEXT("power mutated"), Controller.GetInput().PowerW, 77.0 + 3.0 * 20.0);
				TestEqual(TEXT("cadence mutated"), Controller.GetInput().CadenceRpm, 66.0 + 2.0 * 4.0);
			}

			Controller.Reset();
			TestEqual(TEXT("reset restores power exactly"), Controller.GetInput().PowerW, 77.0);
			TestEqual(TEXT("reset restores cadence exactly"), Controller.GetInput().CadenceRpm, 66.0);
		}
	}

	// --- Requirement 20: Power operations never modify cadence. ---

	{
		FRiderInputController Controller;
		FString Error;
		const double InitialCadence = Controller.GetInput().CadenceRpm;

		const bool bIncP = Controller.TryIncreasePower(Error);
		TestTrue(TEXT("power inc ok"), bIncP);
		const bool bDecP = Controller.TryDecreasePower(Error);
		TestTrue(TEXT("power dec ok"), bDecP);
		const bool bSetMaxP = Controller.TrySetPowerW(999.0, Error);  // clamp to max
		TestTrue(TEXT("power set max ok"), bSetMaxP);
		const bool bSetMinP = Controller.TrySetPowerW(-999.0, Error); // clamp to min
		TestTrue(TEXT("power set min ok"), bSetMinP);
		Controller.TrySetPowerW(NaNValue, Error); // fails; cadence must stay unchanged

		TestEqual(TEXT("cadence unchanged after power ops"), Controller.GetInput().CadenceRpm, InitialCadence);
	}

	// --- Requirement 21: Cadence operations never modify power. ---

	{
		FRiderInputController Controller;
		FString Error;
		const double InitialPower = Controller.GetInput().PowerW;

		const bool bIncC = Controller.TryIncreaseCadence(Error);
		TestTrue(TEXT("cadence inc ok"), bIncC);
		const bool bDecC = Controller.TryDecreaseCadence(Error);
		TestTrue(TEXT("cadence dec ok"), bDecC);
		const bool bSetMaxC = Controller.TrySetCadenceRpm(999.0, Error);
		TestTrue(TEXT("cadence set max ok"), bSetMaxC);
		const bool bSetMinC = Controller.TrySetCadenceRpm(-999.0, Error);
		TestTrue(TEXT("cadence set min ok"), bSetMinC);
		Controller.TrySetCadenceRpm(NaNValue, Error); // fails; power must stay unchanged

		TestEqual(TEXT("power unchanged after cadence ops"), Controller.GetInput().PowerW, InitialPower);
	}

	// --- Requirement 22: Successful fallible operation clears stale OutError. ---

	{
		FRiderInputController Controller;
		FString Error = TEXT("stale-error-from-previous-failure");

		// Seed a failure so OutError becomes non-empty.
		Controller.TrySetPowerW(NaNValue, Error);
		TestTrue(TEXT("stale error seeded"), !Error.IsEmpty());

		// Successful operation must clear it.
		const bool bOk = Controller.TrySetPowerW(150.0, Error);
		TestTrue(TEXT("successful op succeeded"), bOk);
		if (bOk)
		{
			TestTrue(TEXT("successful op clears stale error"), Error.IsEmpty());
		}
	}

	// --- Requirement 23: Every failed operation produces a non-empty useful error. ---

	{
		FRiderInputController Controller;
		FRiderInputControllerConfig Bad;
		Bad.MaxPowerW = -1.0;
		FString Error;

		const bool bBadConfig = Controller.TryConfigure(Bad, Error);
		TestFalse(TEXT("TryConfigure bad"), bBadConfig);
		TestTrue(TEXT("TryConfigure error non-empty"), !Error.IsEmpty());

		const bool bNaNSet = Controller.TrySetPowerW(NaNValue, Error);
		TestFalse(TEXT("TrySetPowerW NaN"), bNaNSet);
		TestTrue(TEXT("TrySetPowerW error non-empty"), !Error.IsEmpty());

		const bool bInfSet = Controller.TrySetCadenceRpm(PositiveInfinity, Error);
		TestFalse(TEXT("TrySetCadenceRpm +Inf"), bInfSet);
		TestTrue(TEXT("TrySetCadenceRpm error non-empty"), !Error.IsEmpty());
	}

	// --- Requirement 24: Identical config + identical command sequences -> exactly equal outputs. ---

	{
		auto RunSequence = [](FRiderInputController& C) -> bool
		{
			FString E;
			if (!C.TryIncreasePower(E)) { return false; }
			if (!C.TryIncreasePower(E)) { return false; }
			if (!C.TryDecreasePower(E)) { return false; }
			if (!C.TrySetPowerW(123.456, E)) { return false; }
			if (!C.TryIncreaseCadence(E)) { return false; }
			if (!C.TryIncreaseCadence(E)) { return false; }
			if (!C.TryIncreaseCadence(E)) { return false; }
			if (!C.TryDecreaseCadence(E)) { return false; }
			if (!C.TrySetCadenceRpm(88.8, E)) { return false; }
			if (!C.TryIncreasePower(E)) { return false; }
			if (!C.TryDecreaseCadence(E)) { return false; }
			if (!C.TryDecreasePower(E)) { return false; }
			if (!C.TrySetPowerW(0.0, E)) { return false; }      // clamp to min
			if (!C.TrySetCadenceRpm(500.0, E)) { return false; } // clamp to max
			return true;
		};

		FRiderInputControllerConfig Config;
		Config.MinPowerW = 0.0;
		Config.MaxPowerW = 400.0;
		Config.PowerStepW = 5.0;
		Config.InitialPowerW = 50.0;
		Config.MinCadenceRpm = 0.0;
		Config.MaxCadenceRpm = 200.0;
		Config.CadenceStepRpm = 2.0;
		Config.InitialCadenceRpm = 40.0;

		FRiderInputController A;
		FRiderInputController B;
		FString E;
		const bool bA = A.TryConfigure(Config, E);
		TestTrue(TEXT("A configured"), bA);
		const bool bB = B.TryConfigure(Config, E);
		TestTrue(TEXT("B configured"), bB);

		const bool bSeqA = bA ? RunSequence(A) : false;
		const bool bSeqB = bB ? RunSequence(B) : false;
		TestTrue(TEXT("A sequence succeeded"), bSeqA);
		TestTrue(TEXT("B sequence succeeded"), bSeqB);

		if (bA && bB && bSeqA && bSeqB)
		{
			TestEqual(TEXT("deterministic PowerW"), A.GetInput().PowerW, B.GetInput().PowerW);
			TestEqual(TEXT("deterministic CadenceRpm"), A.GetInput().CadenceRpm, B.GetInput().CadenceRpm);
		}
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
