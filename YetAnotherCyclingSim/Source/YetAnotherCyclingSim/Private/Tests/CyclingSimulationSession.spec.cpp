#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include <limits>

#include "Cycling/CyclingSimulationSession.h"

namespace CyclingSimulationSessionTest
{
	// Returns a fully valid FCyclingSimulationSessionConfig. The rider and the
	// environment fields are explicitly set to physically plausible values; the
	// rider-input controller configuration uses the controller's own defaults.
	CyclingSimulation::FCyclingSimulationSessionConfig MakeValidSessionConfig()
	{
		CyclingSimulation::FCyclingSimulationSessionConfig Config;

		// Rider parameters (SI units).
		Config.Rider.RiderMassKg = 75.0;
		Config.Rider.BikeMassKg = 8.5;
		Config.Rider.CdaM2 = 0.32;
		Config.Rider.RollingResistanceCoefficient = 0.004;
		Config.Rider.DrivetrainEfficiency = 0.97;

		// Environment (SI units).
		Config.Environment.GradeDecimal = 0.0;
		Config.Environment.WindSpeedMps = 0.0;
		Config.Environment.AirDensityKgM3 = 1.225;
		Config.Environment.SurfaceWetness = 0.0;
		Config.Environment.RollingResistanceMultiplier = 1.0;
		Config.Environment.GripMultiplier = 1.0;

		// Rider input controller configuration (defaults are valid).
		Config.RiderInput.MinPowerW = 0.0;
		Config.RiderInput.MaxPowerW = 2000.0;
		Config.RiderInput.PowerStepW = 10.0;
		Config.RiderInput.InitialPowerW = 200.0;
		Config.RiderInput.MinCadenceRpm = 0.0;
		Config.RiderInput.MaxCadenceRpm = 250.0;
		Config.RiderInput.CadenceStepRpm = 5.0;
		Config.RiderInput.InitialCadenceRpm = 90.0;

		return Config;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FCyclingSimulationSessionTest, "CyclingSession.CyclingSimulationSession",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FCyclingSimulationSessionTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSimulation;
	using namespace CyclingSimulationSessionTest;

	// --- Requirement 1: default construction is unconfigured. ---

	{
		FCyclingSimulationSession Session;
		TestFalse(TEXT("default session is not configured"), Session.IsConfigured());
		TestEqual(TEXT("default simulation state speed is zero"), Session.GetSimulationState().SpeedMps, 0.0);
		TestEqual(TEXT("default simulation state distance is zero"), Session.GetSimulationState().DistanceM, 0.0);
		TestEqual(TEXT("default simulation state elapsed time is zero"), Session.GetSimulationState().ElapsedTimeS, 0.0);
		TestEqual(TEXT("default accumulated time is zero"), Session.GetAccumulatedTimeS(), 0.0);
	}

	// --- Requirement 2: unconfigured advance is rejected transactionally. ---

	{
		FCyclingSimulationSession Session;
		FSimulationState State;
		double RemainingTimeS = -1.0;
		int32 CompletedSteps = -1;
		FString Error;
		const bool bAdvanced = Session.TryAdvance(0.1, State, RemainingTimeS, CompletedSteps, Error);

		TestFalse(TEXT("unconfigured TryAdvance returns false"), bAdvanced);
		TestTrue(TEXT("unconfigured TryAdvance produces a useful error"), !Error.IsEmpty());
		TestEqual(TEXT("unconfigured TryAdvance CompletedSteps is zero"), CompletedSteps, 0);
		TestEqual(TEXT("unconfigured TryAdvance OutState.SpeedMps is zero"), State.SpeedMps, 0.0);
		TestEqual(TEXT("unconfigured TryAdvance OutState.DistanceM is zero"), State.DistanceM, 0.0);
		TestEqual(TEXT("unconfigured TryAdvance OutState.ElapsedTimeS is zero"), State.ElapsedTimeS, 0.0);
		TestEqual(TEXT("unconfigured TryAdvance RemainingTimeS is zero"), RemainingTimeS, 0.0);
		TestFalse(TEXT("session remains unconfigured after rejected TryAdvance"), Session.IsConfigured());
	}

	// --- Requirement 3: unconfigured input mutations are rejected transactionally. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		FString LastInputError;

		Error.Reset();
		TestFalse(TEXT("unconfigured TrySetPowerW rejected"), Session.TrySetPowerW(123.4, Error));
		TestTrue(TEXT("TrySetPowerW produces a useful error"), !Error.IsEmpty());
		LastInputError = Error;

		Error.Reset();
		TestFalse(TEXT("unconfigured TrySetCadenceRpm rejected"), Session.TrySetCadenceRpm(70.0, Error));
		TestTrue(TEXT("TrySetCadenceRpm produces a useful error"), !Error.IsEmpty());
		LastInputError = Error;

		Error.Reset();
		TestFalse(TEXT("unconfigured TryIncreasePower rejected"), Session.TryIncreasePower(Error));
		TestTrue(TEXT("TryIncreasePower produces a useful error"), !Error.IsEmpty());
		LastInputError = Error;

		Error.Reset();
		TestFalse(TEXT("unconfigured TryDecreasePower rejected"), Session.TryDecreasePower(Error));
		TestTrue(TEXT("TryDecreasePower produces a useful error"), !Error.IsEmpty());
		LastInputError = Error;

		Error.Reset();
		TestFalse(TEXT("unconfigured TryIncreaseCadence rejected"), Session.TryIncreaseCadence(Error));
		TestTrue(TEXT("TryIncreaseCadence produces a useful error"), !Error.IsEmpty());

		Error.Reset();
		TestFalse(TEXT("unconfigured TryDecreaseCadence rejected"), Session.TryDecreaseCadence(Error));
		TestTrue(TEXT("TryDecreaseCadence produces a useful error"), !Error.IsEmpty());
	}

	// --- Requirement 4: valid configuration is accepted. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		const bool bConfigured = Session.TryConfigure(MakeValidSessionConfig(), Error);

		TestTrue(TEXT("valid TryConfigure returns true"), bConfigured);
		TestTrue(TEXT("valid TryConfigure clears OutError"), Error.IsEmpty());
		TestTrue(TEXT("session is configured"), Session.IsConfigured());
		TestEqual(TEXT("fresh ride speed is zero"), Session.GetSimulationState().SpeedMps, 0.0);
		TestEqual(TEXT("fresh ride distance is zero"), Session.GetSimulationState().DistanceM, 0.0);
		TestEqual(TEXT("fresh ride elapsed time is zero"), Session.GetSimulationState().ElapsedTimeS, 0.0);
		TestEqual(TEXT("fresh ride accumulated time is zero"), Session.GetAccumulatedTimeS(), 0.0);
		TestEqual(TEXT("initial rider input power matches config"),
			Session.GetRiderInput().PowerW, 200.0);
		TestEqual(TEXT("initial rider input cadence matches config"),
			Session.GetRiderInput().CadenceRpm, 90.0);
	}

	// --- Requirement 5: invalid rider configuration is rejected. ---

	{
		FCyclingSimulationSession Session;
		FCyclingSimulationSessionConfig Config = MakeValidSessionConfig();
		Config.Rider.RiderMassKg = 0.0; // Invalid (must be > 0).

		FString Error;
		TestFalse(TEXT("invalid rider rejected"), Session.TryConfigure(Config, Error));
		TestTrue(TEXT("invalid rider produces a useful error"), !Error.IsEmpty());
		TestFalse(TEXT("session stays unconfigured after invalid rider"), Session.IsConfigured());
	}

	// --- Requirement 6: invalid environment configuration is rejected. ---

	{
		FCyclingSimulationSession Session;
		FCyclingSimulationSessionConfig Config = MakeValidSessionConfig();
		Config.Environment.AirDensityKgM3 = 0.0; // Invalid (must be > 0).

		FString Error;
		TestFalse(TEXT("invalid environment rejected"), Session.TryConfigure(Config, Error));
		TestTrue(TEXT("invalid environment produces a useful error"), !Error.IsEmpty());
		TestFalse(TEXT("session stays unconfigured after invalid environment"), Session.IsConfigured());
	}

	// --- Requirement 7: invalid rider-input configuration is rejected. ---

	{
		FCyclingSimulationSession Session;
		FCyclingSimulationSessionConfig Config = MakeValidSessionConfig();
		Config.RiderInput.InitialPowerW = -1.0; // Invalid (must lie in [Min, Max]).

		FString Error;
		TestFalse(TEXT("invalid rider-input rejected"), Session.TryConfigure(Config, Error));
		TestTrue(TEXT("invalid rider-input produces a useful error"), !Error.IsEmpty());
		TestFalse(TEXT("session stays unconfigured after invalid rider-input"), Session.IsConfigured());
	}

	// --- Requirement 8: failed first configuration leaves the session unconfigured. ---

	{
		FCyclingSimulationSession Session;
		FCyclingSimulationSessionConfig Config = MakeValidSessionConfig();
		Config.Rider.BikeMassKg = 0.0; // Invalid rider.

		FString Error;
		Session.TryConfigure(Config, Error);
		TestFalse(TEXT("session unconfigured after failed first config"), Session.IsConfigured());
		// Inputs stay at controller defaults.
		TestEqual(TEXT("power stays at default after failed first config"),
			Session.GetRiderInput().PowerW, 200.0);
	}

	// --- Requirement 9: failed reconfiguration preserves the previous session state. ---

	{
		FCyclingSimulationSession Session;
		FString Error;

		// First, configure successfully.
		TestTrue(TEXT("initial config succeeds"), Session.TryConfigure(MakeValidSessionConfig(), Error));
		TestTrue(TEXT("initial OutError cleared"), Error.IsEmpty());

		// Change input and advance a bit so the session has non-default state.
		TestTrue(TEXT("set custom power succeeds"), Session.TrySetPowerW(800.0, Error));
		TestTrue(TEXT("set custom power clears OutError"), Error.IsEmpty());

		FSimulationState State;
		double RemainingTimeS = 0.0;
		int32 CompletedSteps = 0;
		TestTrue(TEXT("advance succeeds"),
			Session.TryAdvance(0.2, State, RemainingTimeS, CompletedSteps, Error));
		TestEqual(TEXT("four steps completed"), CompletedSteps, 4);
		TestEqual(TEXT("accumulator after 0.2s advance is zero"),
			RemainingTimeS, 0.0);

		// Advance by a sub-step frame to leave a non-zero accumulator that is
		// smaller than the fixed step duration, so the accumulator preservation
		// assertion below is non-trivial.
		TestTrue(TEXT("sub-step advance succeeds"),
			Session.TryAdvance(0.04, State, RemainingTimeS, CompletedSteps, Error));
		TestEqual(TEXT("sub-step advance produced zero completed steps"),
			CompletedSteps, 0);
		TestTrue(TEXT("accumulator after sub-step advance is strictly positive"),
			Session.GetAccumulatedTimeS() > 0.0);

		// Capture the pre-failure-reconfiguration state.
		const FSimulationState PreservedState = Session.GetSimulationState();
		const FRiderInput PreservedInput = Session.GetRiderInput();
		const double PreservedAccumulator = Session.GetAccumulatedTimeS();
		const FCyclingSimulationSessionConfig PreservedConfig = Session.GetConfig();

		// Attempt to reconfigure with an invalid environment.
		FCyclingSimulationSessionConfig InvalidConfig = MakeValidSessionConfig();
		InvalidConfig.Environment.WindSpeedMps = std::numeric_limits<double>::quiet_NaN();

		Error.Reset();
		TestFalse(TEXT("invalid reconfiguration rejected"), Session.TryConfigure(InvalidConfig, Error));
		TestTrue(TEXT("invalid reconfiguration produces a useful error"), !Error.IsEmpty());

		// Session must be preserved exactly.
		TestTrue(TEXT("session stays configured after failed reconfiguration"), Session.IsConfigured());
		TestEqual(TEXT("preserved simulation state speed"),
			Session.GetSimulationState().SpeedMps, PreservedState.SpeedMps);
		TestEqual(TEXT("preserved simulation state distance"),
			Session.GetSimulationState().DistanceM, PreservedState.DistanceM);
		TestEqual(TEXT("preserved simulation state elapsed time"),
			Session.GetSimulationState().ElapsedTimeS, PreservedState.ElapsedTimeS);
		TestEqual(TEXT("preserved rider input power"),
			Session.GetRiderInput().PowerW, PreservedInput.PowerW);
		TestEqual(TEXT("preserved rider input cadence"),
			Session.GetRiderInput().CadenceRpm, PreservedInput.CadenceRpm);
		TestEqual(TEXT("preserved accumulated time"),
			Session.GetAccumulatedTimeS(), PreservedAccumulator);

		// Preserved accepted configuration: every Rider, Environment, and
		// RiderInput field must be preserved exactly.
		TestEqual(TEXT("preserved config Rider.RiderMassKg"),
			Session.GetConfig().Rider.RiderMassKg, PreservedConfig.Rider.RiderMassKg);
		TestEqual(TEXT("preserved config Rider.BikeMassKg"),
			Session.GetConfig().Rider.BikeMassKg, PreservedConfig.Rider.BikeMassKg);
		TestEqual(TEXT("preserved config Rider.CdaM2"),
			Session.GetConfig().Rider.CdaM2, PreservedConfig.Rider.CdaM2);
		TestEqual(TEXT("preserved config Rider.RollingResistanceCoefficient"),
			Session.GetConfig().Rider.RollingResistanceCoefficient, PreservedConfig.Rider.RollingResistanceCoefficient);
		TestEqual(TEXT("preserved config Rider.DrivetrainEfficiency"),
			Session.GetConfig().Rider.DrivetrainEfficiency, PreservedConfig.Rider.DrivetrainEfficiency);
		TestEqual(TEXT("preserved config Environment.GradeDecimal"),
			Session.GetConfig().Environment.GradeDecimal, PreservedConfig.Environment.GradeDecimal);
		TestEqual(TEXT("preserved config Environment.WindSpeedMps"),
			Session.GetConfig().Environment.WindSpeedMps, PreservedConfig.Environment.WindSpeedMps);
		TestEqual(TEXT("preserved config Environment.AirDensityKgM3"),
			Session.GetConfig().Environment.AirDensityKgM3, PreservedConfig.Environment.AirDensityKgM3);
		TestEqual(TEXT("preserved config Environment.SurfaceWetness"),
			Session.GetConfig().Environment.SurfaceWetness, PreservedConfig.Environment.SurfaceWetness);
		TestEqual(TEXT("preserved config Environment.RollingResistanceMultiplier"),
			Session.GetConfig().Environment.RollingResistanceMultiplier, PreservedConfig.Environment.RollingResistanceMultiplier);
		TestEqual(TEXT("preserved config Environment.GripMultiplier"),
			Session.GetConfig().Environment.GripMultiplier, PreservedConfig.Environment.GripMultiplier);
		TestEqual(TEXT("preserved config RiderInput.MinPowerW"),
			Session.GetConfig().RiderInput.MinPowerW, PreservedConfig.RiderInput.MinPowerW);
		TestEqual(TEXT("preserved config RiderInput.MaxPowerW"),
			Session.GetConfig().RiderInput.MaxPowerW, PreservedConfig.RiderInput.MaxPowerW);
		TestEqual(TEXT("preserved config RiderInput.PowerStepW"),
			Session.GetConfig().RiderInput.PowerStepW, PreservedConfig.RiderInput.PowerStepW);
		TestEqual(TEXT("preserved config RiderInput.InitialPowerW"),
			Session.GetConfig().RiderInput.InitialPowerW, PreservedConfig.RiderInput.InitialPowerW);
		TestEqual(TEXT("preserved config RiderInput.MinCadenceRpm"),
			Session.GetConfig().RiderInput.MinCadenceRpm, PreservedConfig.RiderInput.MinCadenceRpm);
		TestEqual(TEXT("preserved config RiderInput.MaxCadenceRpm"),
			Session.GetConfig().RiderInput.MaxCadenceRpm, PreservedConfig.RiderInput.MaxCadenceRpm);
		TestEqual(TEXT("preserved config RiderInput.CadenceStepRpm"),
			Session.GetConfig().RiderInput.CadenceStepRpm, PreservedConfig.RiderInput.CadenceStepRpm);
		TestEqual(TEXT("preserved config RiderInput.InitialCadenceRpm"),
			Session.GetConfig().RiderInput.InitialCadenceRpm, PreservedConfig.RiderInput.InitialCadenceRpm);
	}

	// --- Requirement 10: successful reconfiguration starts a fresh ride with new initial input. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		Session.TryConfigure(MakeValidSessionConfig(), Error);

		// Advance so the session has non-zero state.
		FSimulationState State;
		double RemainingTimeS = 0.0;
		int32 CompletedSteps = 0;
		Session.TryAdvance(1.0, State, RemainingTimeS, CompletedSteps, Error);

		// Reconfigure with a different RiderInput.InitialPowerW.
		FCyclingSimulationSessionConfig NewConfig = MakeValidSessionConfig();
		NewConfig.RiderInput.InitialPowerW = 300.0;

		TestTrue(TEXT("valid reconfiguration succeeds"), Session.TryConfigure(NewConfig, Error));
		TestTrue(TEXT("valid reconfiguration clears OutError"), Error.IsEmpty());
		TestEqual(TEXT("fresh ride speed is zero after reconfiguration"),
			Session.GetSimulationState().SpeedMps, 0.0);
		TestEqual(TEXT("fresh ride distance is zero after reconfiguration"),
			Session.GetSimulationState().DistanceM, 0.0);
		TestEqual(TEXT("fresh ride elapsed time is zero after reconfiguration"),
			Session.GetSimulationState().ElapsedTimeS, 0.0);
		TestEqual(TEXT("fresh ride accumulated time is zero after reconfiguration"),
			Session.GetAccumulatedTimeS(), 0.0);
		TestEqual(TEXT("new initial rider input power"),
			Session.GetRiderInput().PowerW, 300.0);
		TestEqual(TEXT("initial rider input cadence unchanged"),
			Session.GetRiderInput().CadenceRpm, 90.0);
	}

	// --- Requirement 11: power commands delegate and clamp at configured bounds. ---

	{
		FCyclingSimulationSession Session;
		FCyclingSimulationSessionConfig Config = MakeValidSessionConfig();
		// Use a configuration in which MaxPowerW / PowerStepW = 10, so ten
		// consecutive TryDecreasePower calls reach zero exactly.
		Config.RiderInput.MinPowerW = 0.0;
		Config.RiderInput.MaxPowerW = 100.0;
		Config.RiderInput.PowerStepW = 10.0;
		Config.RiderInput.InitialPowerW = 50.0;
		FString Error;
		Session.TryConfigure(Config, Error);

		// Set above max clamps to max.
		TestTrue(TEXT("TrySetPowerW above max returns true (clamped)"),
			Session.TrySetPowerW(500.0, Error));
		TestEqual(TEXT("power clamped to max"),
			Session.GetRiderInput().PowerW, 100.0);

		// Increase saturates at max.
		TestTrue(TEXT("TryIncreasePower succeeds at max"), Session.TryIncreasePower(Error));
		TestEqual(TEXT("power stays at max after increase at max"),
			Session.GetRiderInput().PowerW, 100.0);

		// Ten decreases from 100.0 with step 10.0 reach exactly zero.
		for (int32 Step = 0; Step < 10; ++Step)
		{
			TestTrue(TEXT("decrease step succeeds"), Session.TryDecreasePower(Error));
		}
		TestEqual(TEXT("power reaches zero after ten decreases"),
			Session.GetRiderInput().PowerW, 0.0);
	}

	// --- Requirement 12: cadence commands delegate and clamp at configured bounds. ---

	{
		FCyclingSimulationSession Session;
		FCyclingSimulationSessionConfig Config = MakeValidSessionConfig();
		Config.RiderInput.MinCadenceRpm = 0.0;
		Config.RiderInput.MaxCadenceRpm = 100.0;
		Config.RiderInput.CadenceStepRpm = 5.0;
		Config.RiderInput.InitialCadenceRpm = 50.0;
		FString Error;
		Session.TryConfigure(Config, Error);

		TestTrue(TEXT("TrySetCadenceRpm above max returns true (clamped)"),
			Session.TrySetCadenceRpm(500.0, Error));
		TestEqual(TEXT("cadence clamped to max"),
			Session.GetRiderInput().CadenceRpm, 100.0);

		TestTrue(TEXT("TryIncreaseCadence succeeds at max"), Session.TryIncreaseCadence(Error));
		TestEqual(TEXT("cadence stays at max after increase at max"),
			Session.GetRiderInput().CadenceRpm, 100.0);

		for (int32 Step = 0; Step < 10; ++Step)
		{
			TestTrue(TEXT("decrease cadence step succeeds"), Session.TryDecreaseCadence(Error));
		}
		TestEqual(TEXT("cadence reaches fifty after ten decreases"),
			Session.GetRiderInput().CadenceRpm, 50.0);
	}

	// --- Requirement 13: current rider input is used by the simulation. ---

	{
		FCyclingSimulationSession SessionHigh;
		FCyclingSimulationSession SessionLow;
		FString Error;
		SessionHigh.TryConfigure(MakeValidSessionConfig(), Error);
		SessionLow.TryConfigure(MakeValidSessionConfig(), Error);

		TestTrue(TEXT("SessionHigh TrySetPowerW(800) succeeds"),
			SessionHigh.TrySetPowerW(800.0, Error));
		TestTrue(TEXT("SessionHigh TrySetPowerW clears OutError"), Error.IsEmpty());
		TestEqual(TEXT("SessionHigh rider input power is 800 W before advance"),
			SessionHigh.GetRiderInput().PowerW, 800.0);
		// SessionLow keeps initial power 200 W.

		FSimulationState StateHigh;
		FSimulationState StateLow;
		double RemainingTimeSHigh = 0.0;
		double RemainingTimeSLow = 0.0;
		int32 CompletedSteps = 0;
		SessionHigh.TryAdvance(0.05, StateHigh, RemainingTimeSHigh, CompletedSteps, Error);
		SessionLow.TryAdvance(0.05, StateLow, RemainingTimeSLow, CompletedSteps, Error);

		TestTrue(TEXT("higher power yields higher speed after one fixed step"),
			StateHigh.SpeedMps > StateLow.SpeedMps);
	}

	// --- Requirement 14: a frame delta below 0.05 s produces no physics step and is accumulated. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		Session.TryConfigure(MakeValidSessionConfig(), Error);

		FSimulationState State;
		double RemainingTimeS = 0.0;
		int32 CompletedSteps = -1;
		Session.TryAdvance(0.04, State, RemainingTimeS, CompletedSteps, Error);

		TestEqual(TEXT("sub-step frame produces zero completed steps"),
			CompletedSteps, 0);
		TestEqual(TEXT("speed is zero after sub-step frame"),
			State.SpeedMps, 0.0);
		TestEqual(TEXT("distance is zero after sub-step frame"),
			State.DistanceM, 0.0);
		TestEqual(TEXT("elapsed time is zero after sub-step frame"),
			State.ElapsedTimeS, 0.0);
		TestEqual(TEXT("accumulator equals the sub-step frame time"),
			Session.GetAccumulatedTimeS(), 0.04);
	}

	// --- Requirement 15: equivalent total time split into two equal advances produces exactly equal state. ---

	{
		FCyclingSimulationSession SessionA;
		FCyclingSimulationSession SessionB;
		FString Error;
		SessionA.TryConfigure(MakeValidSessionConfig(), Error);
		SessionB.TryConfigure(MakeValidSessionConfig(), Error);

		FSimulationState StateA;
		FSimulationState StateB;
		double RemainingTimeSA = 0.0;
		double RemainingTimeSB = 0.0;
		int32 CompletedStepsA = 0;
		int32 CompletedStepsB = 0;

		SessionA.TryAdvance(1.0, StateA, RemainingTimeSA, CompletedStepsA, Error);
		SessionB.TryAdvance(0.5, StateB, RemainingTimeSB, CompletedStepsB, Error);
		SessionB.TryAdvance(0.5, StateB, RemainingTimeSB, CompletedStepsB, Error);

		// Note: per-call CompletedSteps may differ between the single 1.0 s
		// advance and the two 0.5 s advances because the runner's float
		// boundary tolerance causes the accumulator after the first 0.5 s to
		// be a tiny positive remainder, which the second 0.5 s consumes
		// entirely. The session-level determinism proof is that the final
		// simulation state and accumulator are bit-exactly equal regardless
		// of the frame split.
		TestEqual(TEXT("equivalent split produces equal speed"),
			StateA.SpeedMps, StateB.SpeedMps);
		TestEqual(TEXT("equivalent split produces equal distance"),
			StateA.DistanceM, StateB.DistanceM);
		TestEqual(TEXT("equivalent split produces equal elapsed time"),
			StateA.ElapsedTimeS, StateB.ElapsedTimeS);
		TestEqual(TEXT("equivalent split produces zero accumulator"),
			SessionA.GetAccumulatedTimeS(), SessionB.GetAccumulatedTimeS());
	}

	// --- Requirement 16: two sessions with identical config and commands produce exactly equal state and input. ---

	{
		FCyclingSimulationSession SessionA;
		FCyclingSimulationSession SessionB;
		FString Error;
		SessionA.TryConfigure(MakeValidSessionConfig(), Error);
		SessionB.TryConfigure(MakeValidSessionConfig(), Error);

		const double Commands[] = { 50.0, 150.0, 300.0, 600.0, 1000.0 };
		for (double Cmd : Commands)
		{
			SessionA.TrySetPowerW(Cmd, Error);
			SessionB.TrySetPowerW(Cmd, Error);
		}

		FSimulationState StateA;
		FSimulationState StateB;
		double RemainingTimeSA = 0.0;
		double RemainingTimeSB = 0.0;
		int32 CompletedStepsA = 0;
		int32 CompletedStepsB = 0;

		const double Deltas[] = { 0.04, 0.06, 0.05, 0.1, 0.2, 0.5, 1.0 };
		for (double Delta : Deltas)
		{
			SessionA.TryAdvance(Delta, StateA, RemainingTimeSA, CompletedStepsA, Error);
			SessionB.TryAdvance(Delta, StateB, RemainingTimeSB, CompletedStepsB, Error);
		}

		TestEqual(TEXT("identical sessions produce equal speed"),
			SessionA.GetSimulationState().SpeedMps, SessionB.GetSimulationState().SpeedMps);
		TestEqual(TEXT("identical sessions produce equal distance"),
			SessionA.GetSimulationState().DistanceM, SessionB.GetSimulationState().DistanceM);
		TestEqual(TEXT("identical sessions produce equal elapsed time"),
			SessionA.GetSimulationState().ElapsedTimeS, SessionB.GetSimulationState().ElapsedTimeS);
		TestEqual(TEXT("identical sessions produce equal accumulated time"),
			SessionA.GetAccumulatedTimeS(), SessionB.GetAccumulatedTimeS());
		TestEqual(TEXT("identical sessions produce equal rider input power"),
			SessionA.GetRiderInput().PowerW, SessionB.GetRiderInput().PowerW);
		TestEqual(TEXT("identical sessions produce equal rider input cadence"),
			SessionA.GetRiderInput().CadenceRpm, SessionB.GetRiderInput().CadenceRpm);
	}

	// --- Requirement 17: invalid or non-finite frame delta preserves state and accumulator. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		Session.TryConfigure(MakeValidSessionConfig(), Error);

		// Establish a baseline by advancing once.
		FSimulationState State;
		double RemainingTimeS = 0.0;
		int32 CompletedSteps = 0;
		Session.TryAdvance(0.1, State, RemainingTimeS, CompletedSteps, Error);
		const FSimulationState PreservedState = Session.GetSimulationState();
		const double PreservedAccumulator = Session.GetAccumulatedTimeS();
		const FRiderInput PreservedInput = Session.GetRiderInput();

		// Sentinel values for the public output parameters of TryAdvance. Each
		// case sets these BEFORE the TryAdvance call so the wrapper cannot
		// silently leave them at a stale prior value on failure.
		const double SentinelRemainingTimeS = 999.0;
		const int32 SentinelCompletedSteps = 888;
		const double SentinelSpeedMps = 999.0;
		const double SentinelDistanceM = 999.0;
		const double SentinelElapsedTimeS = 999.0;

		// Negative delta.
		Error.Reset();
		State.SpeedMps = SentinelSpeedMps;
		State.DistanceM = SentinelDistanceM;
		State.ElapsedTimeS = SentinelElapsedTimeS;
		RemainingTimeS = SentinelRemainingTimeS;
		CompletedSteps = SentinelCompletedSteps;
		TestFalse(TEXT("negative frame delta rejected"),
			Session.TryAdvance(-0.01, State, RemainingTimeS, CompletedSteps, Error));
		TestTrue(TEXT("negative frame delta produces a useful error"), !Error.IsEmpty());
		TestEqual(TEXT("negative frame delta CompletedSteps is zero"), CompletedSteps, 0);
		TestEqual(TEXT("negative frame delta OutState.SpeedMps preserved"),
			State.SpeedMps, PreservedState.SpeedMps);
		TestEqual(TEXT("negative frame delta OutState.DistanceM preserved"),
			State.DistanceM, PreservedState.DistanceM);
		TestEqual(TEXT("negative frame delta OutState.ElapsedTimeS preserved"),
			State.ElapsedTimeS, PreservedState.ElapsedTimeS);
		TestEqual(TEXT("negative frame delta OutRemainingTimeS preserved"),
			RemainingTimeS, PreservedAccumulator);
		TestEqual(TEXT("negative frame delta preserves internal SpeedMps"),
			Session.GetSimulationState().SpeedMps, PreservedState.SpeedMps);
		TestEqual(TEXT("negative frame delta preserves internal DistanceM"),
			Session.GetSimulationState().DistanceM, PreservedState.DistanceM);
		TestEqual(TEXT("negative frame delta preserves internal ElapsedTimeS"),
			Session.GetSimulationState().ElapsedTimeS, PreservedState.ElapsedTimeS);
		TestEqual(TEXT("negative frame delta preserves accumulator"),
			Session.GetAccumulatedTimeS(), PreservedAccumulator);
		TestEqual(TEXT("negative frame delta preserves rider input power"),
			Session.GetRiderInput().PowerW, PreservedInput.PowerW);
		TestEqual(TEXT("negative frame delta preserves rider input cadence"),
			Session.GetRiderInput().CadenceRpm, PreservedInput.CadenceRpm);

		// NaN delta.
		Error.Reset();
		State.SpeedMps = SentinelSpeedMps;
		State.DistanceM = SentinelDistanceM;
		State.ElapsedTimeS = SentinelElapsedTimeS;
		RemainingTimeS = SentinelRemainingTimeS;
		CompletedSteps = SentinelCompletedSteps;
		TestFalse(TEXT("NaN frame delta rejected"),
			Session.TryAdvance(std::numeric_limits<double>::quiet_NaN(),
				State, RemainingTimeS, CompletedSteps, Error));
		TestTrue(TEXT("NaN frame delta produces a useful error"), !Error.IsEmpty());
		TestEqual(TEXT("NaN frame delta CompletedSteps is zero"), CompletedSteps, 0);
		TestEqual(TEXT("NaN frame delta OutState.SpeedMps preserved"),
			State.SpeedMps, PreservedState.SpeedMps);
		TestEqual(TEXT("NaN frame delta OutState.DistanceM preserved"),
			State.DistanceM, PreservedState.DistanceM);
		TestEqual(TEXT("NaN frame delta OutState.ElapsedTimeS preserved"),
			State.ElapsedTimeS, PreservedState.ElapsedTimeS);
		TestEqual(TEXT("NaN frame delta OutRemainingTimeS preserved"),
			RemainingTimeS, PreservedAccumulator);
		TestEqual(TEXT("NaN frame delta preserves internal SpeedMps"),
			Session.GetSimulationState().SpeedMps, PreservedState.SpeedMps);
		TestEqual(TEXT("NaN frame delta preserves internal DistanceM"),
			Session.GetSimulationState().DistanceM, PreservedState.DistanceM);
		TestEqual(TEXT("NaN frame delta preserves internal ElapsedTimeS"),
			Session.GetSimulationState().ElapsedTimeS, PreservedState.ElapsedTimeS);
		TestEqual(TEXT("NaN frame delta preserves accumulator"),
			Session.GetAccumulatedTimeS(), PreservedAccumulator);
		TestEqual(TEXT("NaN frame delta preserves rider input power"),
			Session.GetRiderInput().PowerW, PreservedInput.PowerW);
		TestEqual(TEXT("NaN frame delta preserves rider input cadence"),
			Session.GetRiderInput().CadenceRpm, PreservedInput.CadenceRpm);

		// Positive infinity delta.
		Error.Reset();
		State.SpeedMps = SentinelSpeedMps;
		State.DistanceM = SentinelDistanceM;
		State.ElapsedTimeS = SentinelElapsedTimeS;
		RemainingTimeS = SentinelRemainingTimeS;
		CompletedSteps = SentinelCompletedSteps;
		TestFalse(TEXT("+Inf frame delta rejected"),
			Session.TryAdvance(std::numeric_limits<double>::infinity(),
				State, RemainingTimeS, CompletedSteps, Error));
		TestTrue(TEXT("+Inf frame delta produces a useful error"), !Error.IsEmpty());
		TestEqual(TEXT("+Inf frame delta CompletedSteps is zero"), CompletedSteps, 0);
		TestEqual(TEXT("+Inf frame delta OutState.SpeedMps preserved"),
			State.SpeedMps, PreservedState.SpeedMps);
		TestEqual(TEXT("+Inf frame delta OutState.DistanceM preserved"),
			State.DistanceM, PreservedState.DistanceM);
		TestEqual(TEXT("+Inf frame delta OutState.ElapsedTimeS preserved"),
			State.ElapsedTimeS, PreservedState.ElapsedTimeS);
		TestEqual(TEXT("+Inf frame delta OutRemainingTimeS preserved"),
			RemainingTimeS, PreservedAccumulator);
		TestEqual(TEXT("+Inf frame delta preserves internal SpeedMps"),
			Session.GetSimulationState().SpeedMps, PreservedState.SpeedMps);
		TestEqual(TEXT("+Inf frame delta preserves internal DistanceM"),
			Session.GetSimulationState().DistanceM, PreservedState.DistanceM);
		TestEqual(TEXT("+Inf frame delta preserves internal ElapsedTimeS"),
			Session.GetSimulationState().ElapsedTimeS, PreservedState.ElapsedTimeS);
		TestEqual(TEXT("+Inf frame delta preserves accumulator"),
			Session.GetAccumulatedTimeS(), PreservedAccumulator);
		TestEqual(TEXT("+Inf frame delta preserves rider input power"),
			Session.GetRiderInput().PowerW, PreservedInput.PowerW);
		TestEqual(TEXT("+Inf frame delta preserves rider input cadence"),
			Session.GetRiderInput().CadenceRpm, PreservedInput.CadenceRpm);
	}

	// --- Requirement 18: reset clears state and accumulator and restores initial input. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		Session.TryConfigure(MakeValidSessionConfig(), Error);

		// Change input and advance to create non-default state.
		Session.TrySetPowerW(800.0, Error);
		FSimulationState State;
		double RemainingTimeS = 0.0;
		int32 CompletedSteps = 0;
		Session.TryAdvance(0.5, State, RemainingTimeS, CompletedSteps, Error);

		Session.Reset();

		TestEqual(TEXT("reset clears speed"),
			Session.GetSimulationState().SpeedMps, 0.0);
		TestEqual(TEXT("reset clears distance"),
			Session.GetSimulationState().DistanceM, 0.0);
		TestEqual(TEXT("reset clears elapsed time"),
			Session.GetSimulationState().ElapsedTimeS, 0.0);
		TestEqual(TEXT("reset clears accumulator"),
			Session.GetAccumulatedTimeS(), 0.0);
		TestEqual(TEXT("reset restores initial rider input power"),
			Session.GetRiderInput().PowerW, 200.0);
		TestEqual(TEXT("reset restores initial rider input cadence"),
			Session.GetRiderInput().CadenceRpm, 90.0);
		TestTrue(TEXT("session stays configured after reset"), Session.IsConfigured());
	}

	// Reset on an unconfigured session is a documented no-op.
	{
		FCyclingSimulationSession Session;
		Session.Reset();
		TestFalse(TEXT("reset on unconfigured session does not configure it"),
			Session.IsConfigured());
		TestEqual(TEXT("reset on unconfigured session leaves speed zero"),
			Session.GetSimulationState().SpeedMps, 0.0);
	}

	// --- Requirement 19: rerunning the same sequence after reset reproduces the exact previous result. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		Session.TryConfigure(MakeValidSessionConfig(), Error);

		// First run: advance through a sequence.
		FSimulationState State1;
		double RemainingTimeS1 = 0.0;
		int32 CompletedSteps1 = 0;
		const double Deltas[] = { 0.04, 0.05, 0.1, 0.2 };
		for (double Delta : Deltas)
		{
			Session.TryAdvance(Delta, State1, RemainingTimeS1, CompletedSteps1, Error);
		}
		const FSimulationState SnapshotState = Session.GetSimulationState();
		const double SnapshotAccumulator = Session.GetAccumulatedTimeS();

		// Reset and rerun the same sequence.
		Session.Reset();
		FSimulationState State2;
		double RemainingTimeS2 = 0.0;
		int32 CompletedSteps2 = 0;
		for (double Delta : Deltas)
		{
			Session.TryAdvance(Delta, State2, RemainingTimeS2, CompletedSteps2, Error);
		}

		TestEqual(TEXT("rerun after reset reproduces speed"),
			SnapshotState.SpeedMps, Session.GetSimulationState().SpeedMps);
		TestEqual(TEXT("rerun after reset reproduces distance"),
			SnapshotState.DistanceM, Session.GetSimulationState().DistanceM);
		TestEqual(TEXT("rerun after reset reproduces elapsed time"),
			SnapshotState.ElapsedTimeS, Session.GetSimulationState().ElapsedTimeS);
		TestEqual(TEXT("rerun after reset reproduces accumulator"),
			SnapshotAccumulator, Session.GetAccumulatedTimeS());
	}

	// --- Requirement 20: successful fallible operations clear stale errors. ---

	{
		FCyclingSimulationSession Session;
		FString Error;
		Session.TryConfigure(MakeValidSessionConfig(), Error);

		// Set a stale error by attempting to set a non-finite power.
		Error.Reset();
		TestFalse(TEXT("NaN power rejected by controller"),
			Session.TrySetPowerW(std::numeric_limits<double>::quiet_NaN(), Error));
		TestTrue(TEXT("NaN power leaves a non-empty error"), !Error.IsEmpty());
		const FString StaleError = Error;

		// A successful fallible operation must clear the stale error.
		Error.Reset();
		TestTrue(TEXT("valid power succeeds"), Session.TrySetPowerW(150.0, Error));
		TestTrue(TEXT("successful TrySetPowerW clears stale error"), Error.IsEmpty());

		// Advance should also clear the stale error (advance clears its own error on success).
		// Reintroduce a stale error first via a failing operation.
		Error = StaleError;
		TestTrue(TEXT("stale error reintroduced for advance check"), !Error.IsEmpty());

		FSimulationState State;
		double RemainingTimeS = 0.0;
		int32 CompletedSteps = 0;
		TestTrue(TEXT("valid advance succeeds"),
			Session.TryAdvance(0.05, State, RemainingTimeS, CompletedSteps, Error));
		TestTrue(TEXT("successful TryAdvance clears stale error"), Error.IsEmpty());
	}

	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
