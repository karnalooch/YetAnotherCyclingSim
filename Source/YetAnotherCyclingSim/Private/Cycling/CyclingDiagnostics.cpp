// Copyright YetAnotherCyclingSim. All Rights Reserved.
//
// Stage 2 prototype diagnostic overlay - presentation-only.
//
// Pure formatter and observer implementations. See CyclingDiagnostics.h
// for the architectural rules.

#include "Cycling/CyclingDiagnostics.h"

#include "Math/UnrealMathUtility.h"

namespace CyclingDiagnostics
{
	// -----------------------------------------------------------------
	// Lifecycle mapping.
	// -----------------------------------------------------------------
	ECyclingDiagnosticsLifecycle MapLifecycle(int32 PawnLifecycleValue)
	{
		switch (static_cast<ECyclingDiagnosticsLifecycle>(PawnLifecycleValue))
		{
		case ECyclingDiagnosticsLifecycle::Uninitialized: return ECyclingDiagnosticsLifecycle::Uninitialized;
		case ECyclingDiagnosticsLifecycle::Ready:         return ECyclingDiagnosticsLifecycle::Ready;
		case ECyclingDiagnosticsLifecycle::Running:       return ECyclingDiagnosticsLifecycle::Running;
		case ECyclingDiagnosticsLifecycle::Stopped:       return ECyclingDiagnosticsLifecycle::Stopped;
		case ECyclingDiagnosticsLifecycle::Finished:      return ECyclingDiagnosticsLifecycle::Finished;
		case ECyclingDiagnosticsLifecycle::Error:         return ECyclingDiagnosticsLifecycle::Error;
		}
		return ECyclingDiagnosticsLifecycle::Uninitialized;
	}

	// -----------------------------------------------------------------
	// Snapshot assembly.
	// -----------------------------------------------------------------
	FCyclingDiagnosticsSnapshot MakeSnapshot(
		ECyclingDiagnosticsLifecycle Lifecycle,
		double PowerW,
		double CadenceRpm,
		const FSimulationState& State,
		int32 LastCompletedSteps,
		double AccumulatorS,
		double CachedRouteLengthM,
		const FString& LastError,
		double ConfiguredPowerStepW,
		double ConfiguredCadenceStepRpm,
		const FCyclingLastInputFeedback& LastInputFeedback)
	{
		FCyclingDiagnosticsSnapshot Snap;
		Snap.Lifecycle = Lifecycle;
		Snap.PowerW = PowerW;
		Snap.CadenceRpm = CadenceRpm;
		Snap.SpeedMps = State.SpeedMps;
		Snap.DistanceM = State.DistanceM;
		Snap.ElapsedTimeS = State.ElapsedTimeS;
		Snap.LastCompletedSteps = LastCompletedSteps;
		Snap.AccumulatorS = AccumulatorS;
		Snap.CachedRouteLengthM = CachedRouteLengthM;
		Snap.LastError = LastError;
		Snap.ConfiguredPowerStepW = ConfiguredPowerStepW;
		Snap.ConfiguredCadenceStepRpm = ConfiguredCadenceStepRpm;
		Snap.LastInputFeedback = LastInputFeedback;
		return Snap;
	}

	// -----------------------------------------------------------------
	// Command labels.
	// -----------------------------------------------------------------
	const TCHAR* GetInputCommandKeyTag(ECyclingInputCommand Command)
	{
		switch (Command)
		{
		case ECyclingInputCommand::PowerIncrease:   return TEXT("UP");
		case ECyclingInputCommand::PowerDecrease:   return TEXT("DOWN");
		case ECyclingInputCommand::CadenceIncrease: return TEXT("RIGHT");
		case ECyclingInputCommand::CadenceDecrease: return TEXT("LEFT");
		case ECyclingInputCommand::StartOrResume:   return TEXT("SPACE");
		case ECyclingInputCommand::Stop:            return TEXT("S");
		case ECyclingInputCommand::Restart:         return TEXT("R");
		case ECyclingInputCommand::None:            return TEXT("-");
		}
		return TEXT("-");
	}

	FString GetInputCommandLabel(ECyclingInputCommand Command,
		double ConfiguredPowerStepW, double ConfiguredCadenceStepRpm)
	{
		const double PowerStep = FMath::IsFinite(ConfiguredPowerStepW) && ConfiguredPowerStepW > 0.0
			? ConfiguredPowerStepW : 10.0;
		const double CadenceStep = FMath::IsFinite(ConfiguredCadenceStepRpm) && ConfiguredCadenceStepRpm > 0.0
			? ConfiguredCadenceStepRpm : 5.0;
		switch (Command)
		{
		case ECyclingInputCommand::PowerIncrease:   return FString::Printf(TEXT("POWER +%.0f W"), PowerStep);
		case ECyclingInputCommand::PowerDecrease:   return FString::Printf(TEXT("POWER -%.0f W"), PowerStep);
		case ECyclingInputCommand::CadenceIncrease: return FString::Printf(TEXT("CADENCE +%.0f rpm"), CadenceStep);
		case ECyclingInputCommand::CadenceDecrease: return FString::Printf(TEXT("CADENCE -%.0f rpm"), CadenceStep);
		case ECyclingInputCommand::StartOrResume:   return TEXT("START / RESUME");
		case ECyclingInputCommand::Stop:            return TEXT("STOP");
		case ECyclingInputCommand::Restart:         return TEXT("RESTART");
		case ECyclingInputCommand::None:            return TEXT("-");
		}
		return TEXT("-");
	}

	// -----------------------------------------------------------------
	// Input snapshot capture.
	// -----------------------------------------------------------------
	FCyclingInputSnapshot CaptureInputSnapshot(
		ECyclingDiagnosticsLifecycle Lifecycle,
		double PowerW,
		double CadenceRpm,
		const FSimulationState& State)
	{
		FCyclingInputSnapshot Snap;
		Snap.Lifecycle = Lifecycle;
		Snap.PowerW = PowerW;
		Snap.CadenceRpm = CadenceRpm;
		Snap.SpeedMps = State.SpeedMps;
		Snap.DistanceM = State.DistanceM;
		Snap.ElapsedTimeS = State.ElapsedTimeS;
		return Snap;
	}

	// -----------------------------------------------------------------
	// Last-input feedback assembly.
	// -----------------------------------------------------------------
	FString FormatLifecycleName(ECyclingDiagnosticsLifecycle L)
	{
		switch (L)
		{
		case ECyclingDiagnosticsLifecycle::Uninitialized: return TEXT("UNINITIALIZED");
		case ECyclingDiagnosticsLifecycle::Ready:         return TEXT("READY");
		case ECyclingDiagnosticsLifecycle::Running:       return TEXT("RUNNING");
		case ECyclingDiagnosticsLifecycle::Stopped:       return TEXT("STOPPED");
		case ECyclingDiagnosticsLifecycle::Finished:      return TEXT("FINISHED");
		case ECyclingDiagnosticsLifecycle::Error:         return TEXT("ERROR");
		}
		return TEXT("UNKNOWN");
	}

	static bool IsPowerCommand(ECyclingInputCommand C)
	{
		return C == ECyclingInputCommand::PowerIncrease || C == ECyclingInputCommand::PowerDecrease;
	}
	static bool IsCadenceCommand(ECyclingInputCommand C)
	{
		return C == ECyclingInputCommand::CadenceIncrease || C == ECyclingInputCommand::CadenceDecrease;
	}
	static bool IsLifecycleCommand(ECyclingInputCommand C)
	{
		return C == ECyclingInputCommand::StartOrResume
			|| C == ECyclingInputCommand::Stop
			|| C == ECyclingInputCommand::Restart;
	}

	FCyclingLastInputFeedback BuildLastInputFeedback(
		ECyclingInputCommand Command,
		const FCyclingInputSnapshot& Before,
		const FCyclingInputSnapshot& After,
		double ConfiguredPowerStepW,
		double ConfiguredCadenceStepRpm)
	{
		FCyclingLastInputFeedback Feedback;
		Feedback.Command = Command;
		Feedback.Before = Before;
		Feedback.After = After;

		// Acceptance rule: any successful input mutation MUST change
		// at least one observable field by at least one step OR
		// transition the lifecycle. Otherwise the command was ignored.
		const double PowerStep = FMath::IsFinite(ConfiguredPowerStepW) && ConfiguredPowerStepW > 0.0
			? ConfiguredPowerStepW : 10.0;
		const double CadenceStep = FMath::IsFinite(ConfiguredCadenceStepRpm) && ConfiguredCadenceStepRpm > 0.0
			? ConfiguredCadenceStepRpm : 5.0;

		if (IsPowerCommand(Command))
		{
			const double Delta = After.PowerW - Before.PowerW;
			Feedback.bAccepted = !FMath::IsNearlyZero(Delta) &&
				FMath::IsNearlyEqual(FMath::Abs(Delta), PowerStep, 1e-6);
		}
		else if (IsCadenceCommand(Command))
		{
			const double Delta = After.CadenceRpm - Before.CadenceRpm;
			Feedback.bAccepted = !FMath::IsNearlyZero(Delta) &&
				FMath::IsNearlyEqual(FMath::Abs(Delta), CadenceStep, 1e-6);
		}
		else if (IsLifecycleCommand(Command))
		{
			// For Restart the lifecycle stays Running both before and
			// after, so the simple transition test fails. Detect a
			// real restart by observing authoritative reset semantics:
			// distance dropped (or was zero and stayed zero AND power/
			// cadence returned to configured initial). The simplest
			// invariant is "distance moved down or values were reset".
			if (Command == ECyclingInputCommand::Restart)
			{
				const bool bDistanceReset =
					Before.DistanceM > 0.0
						? After.DistanceM < Before.DistanceM
						: FMath::IsNearlyZero(After.DistanceM);
				const bool bPowerReset = !FMath::IsNearlyEqual(
					Before.PowerW, After.PowerW);
				const bool bCadenceReset = !FMath::IsNearlyEqual(
					Before.CadenceRpm, After.CadenceRpm);
				Feedback.bAccepted = bDistanceReset || bPowerReset || bCadenceReset;
			}
			else
			{
				Feedback.bAccepted = (Before.Lifecycle != After.Lifecycle);
			}
		}
		else
		{
			Feedback.bAccepted = false;
		}

		return Feedback;
	}

	// -----------------------------------------------------------------
	// Overlay formatter.
	// -----------------------------------------------------------------
	static const TCHAR* GuidedStepPrompt(ECyclingGuidedAcceptanceStep Step)
	{
		switch (Step)
		{
		case ECyclingGuidedAcceptanceStep::Ready_WaitStart:
			return TEXT("Press SPACE");
		case ECyclingGuidedAcceptanceStep::Running_WaitPowerUp:
			return TEXT("Press UP");
		case ECyclingGuidedAcceptanceStep::Running_WaitCadenceUp:
			return TEXT("Press RIGHT");
		case ECyclingGuidedAcceptanceStep::Running_WaitStop:
			return TEXT("Press S");
		case ECyclingGuidedAcceptanceStep::Stopped_WaitStart:
			return TEXT("Press SPACE");
		case ECyclingGuidedAcceptanceStep::Running_WaitRestart:
			return TEXT("Press R");
		case ECyclingGuidedAcceptanceStep::Finished:
			return TEXT("Press R to Restart");
		}
		return TEXT("-");
	}

	static int32 GuidedStepNumber(ECyclingGuidedAcceptanceStep Step)
	{
		return static_cast<int32>(Step) + 1;
	}

	static FString GuidedStepExpected(ECyclingGuidedAcceptanceStep Step,
		double ConfiguredPowerStepW,
		double ConfiguredCadenceStepRpm)
	{
		const double PowerStep = FMath::IsFinite(ConfiguredPowerStepW) && ConfiguredPowerStepW > 0.0
			? ConfiguredPowerStepW : 10.0;
		const double CadenceStep = FMath::IsFinite(ConfiguredCadenceStepRpm) && ConfiguredCadenceStepRpm > 0.0
			? ConfiguredCadenceStepRpm : 5.0;
		switch (Step)
		{
		case ECyclingGuidedAcceptanceStep::Ready_WaitStart:
			return TEXT("READY -> RUNNING");
		case ECyclingGuidedAcceptanceStep::Running_WaitPowerUp:
			return FString::Printf(TEXT("power +%.0f W (exactly one step)"), PowerStep);
		case ECyclingGuidedAcceptanceStep::Running_WaitCadenceUp:
			return FString::Printf(TEXT("cadence +%.0f rpm (exactly one step)"), CadenceStep);
		case ECyclingGuidedAcceptanceStep::Running_WaitStop:
			return TEXT("RUNNING -> STOPPED");
		case ECyclingGuidedAcceptanceStep::Stopped_WaitStart:
			return TEXT("STOPPED -> RUNNING, distance preserved");
		case ECyclingGuidedAcceptanceStep::Running_WaitRestart:
			return TEXT("distance -> 0, power -> initial, cadence -> initial");
		case ECyclingGuidedAcceptanceStep::Finished:
			return TEXT("Visible route end reached");
		}
		return TEXT("");
	}

	FString FormatOverlay(const FCyclingDiagnosticsSnapshot& Snapshot,
		const FCyclingGuidedAcceptanceState& Guided,
		bool bEnableGuidedAcceptance)
	{
		// Stage 2 spec: km/h is a presentation-only conversion.
		const double SpeedKmh = Snapshot.SpeedMps * 3.6;

		// Distance presentation: clamp to [0, route length] without
		// rewriting the authoritative state. Authoritative value is
		// used verbatim for the display as the runtime contract
		// already preserves a possible small overshoot; the route
		// length is shown as the upper bound.
		const double PresDist = FMath::Clamp(Snapshot.DistanceM, 0.0,
			FMath::Max(Snapshot.CachedRouteLengthM, 0.0));
		const double TotalDist = Snapshot.CachedRouteLengthM;

		FString Output;
		Output.Reserve(2048);

		// 1. DEV HUD.
		Output += TEXT("YACS - STAGE 2 DEV HUD\n");
		Output += FString::Printf(TEXT("STATE       %s\n"),
			*FormatLifecycleName(Snapshot.Lifecycle));
		Output += FString::Printf(TEXT("POWER       %.0f W\n"), Snapshot.PowerW);
		Output += FString::Printf(TEXT("CADENCE     %.0f rpm\n"), Snapshot.CadenceRpm);
		Output += FString::Printf(TEXT("SPEED       %.3f m/s   (%.2f km/h)\n"),
			Snapshot.SpeedMps, SpeedKmh);
		Output += FString::Printf(TEXT("DISTANCE    %.2f / %.2f m\n"), PresDist, TotalDist);
		Output += FString::Printf(TEXT("TIME        %.2f s\n"), Snapshot.ElapsedTimeS);
		Output += TEXT("\n");
		Output += FString::Printf(TEXT("FIXED STEPS   %d\n"), Snapshot.LastCompletedSteps);
		Output += FString::Printf(TEXT("ACCUMULATOR   %.3f s\n"), Snapshot.AccumulatorS);
		Output += FString::Printf(TEXT("ERROR         %s\n"),
			Snapshot.LastError.IsEmpty() ? TEXT("none") : *Snapshot.LastError);

		// 2. Controls legend (step values come from the configured
		// controller).
		const double PowerStep = FMath::IsFinite(Snapshot.ConfiguredPowerStepW) && Snapshot.ConfiguredPowerStepW > 0.0
			? Snapshot.ConfiguredPowerStepW : 10.0;
		const double CadenceStep = FMath::IsFinite(Snapshot.ConfiguredCadenceStepRpm) && Snapshot.ConfiguredCadenceStepRpm > 0.0
			? Snapshot.ConfiguredCadenceStepRpm : 5.0;
		Output += TEXT("\nCONTROLS\n");
		Output += TEXT("[SPACE] Start / Resume\n");
		Output += TEXT("[S]     Stop\n");
		Output += TEXT("[R]     Restart\n");
		Output += FString::Printf(TEXT("[UP]    Power +%.0f W\n"), PowerStep);
		Output += FString::Printf(TEXT("[DOWN]  Power -%.0f W\n"), PowerStep);
		Output += FString::Printf(TEXT("[RIGHT] Cadence +%.0f rpm\n"), CadenceStep);
		Output += FString::Printf(TEXT("[LEFT]  Cadence -%.0f rpm\n"), CadenceStep);

		// 3. LAST INPUT.
		Output += TEXT("\nLAST INPUT\n");
		if (Snapshot.LastInputFeedback.Command != ECyclingInputCommand::None)
		{
			const FCyclingLastInputFeedback& Feedback = Snapshot.LastInputFeedback;
			const TCHAR* Tag = GetInputCommandKeyTag(Feedback.Command);
			const FString Label = GetInputCommandLabel(Feedback.Command,
				Snapshot.ConfiguredPowerStepW, Snapshot.ConfiguredCadenceStepRpm);
			const FString Status = Feedback.bAccepted ? TEXT("PASS") : TEXT("IGNORED");
			const FString BeforeName = FormatLifecycleName(Feedback.Before.Lifecycle);
			const FString AfterName  = FormatLifecycleName(Feedback.After.Lifecycle);

			if (IsPowerCommand(Feedback.Command))
			{
				Output += FString::Printf(TEXT("%s - %s\n%.0f W -> %.0f W\n%s\n"),
					Tag, *Label,
					Feedback.Before.PowerW, Feedback.After.PowerW,
					*Status);
			}
			else if (IsCadenceCommand(Feedback.Command))
			{
				Output += FString::Printf(TEXT("%s - %s\n%.0f rpm -> %.0f rpm\n%s\n"),
					Tag, *Label,
					Feedback.Before.CadenceRpm, Feedback.After.CadenceRpm,
					*Status);
			}
			else if (Feedback.Command == ECyclingInputCommand::Restart)
			{
				Output += FString::Printf(
					TEXT("%s - %s\n")
					TEXT("distance %.2f m -> %.2f m\n")
					TEXT("time %.2f s -> %.2f s\n")
					TEXT("power %.0f W -> %.0f W\n")
					TEXT("cadence %.0f rpm -> %.0f rpm\n")
					TEXT("%s -> %s\n%s\n"),
					Tag, *Label,
					Feedback.Before.DistanceM, Feedback.After.DistanceM,
					Feedback.Before.ElapsedTimeS, Feedback.After.ElapsedTimeS,
					Feedback.Before.PowerW, Feedback.After.PowerW,
					Feedback.Before.CadenceRpm, Feedback.After.CadenceRpm,
					*BeforeName, *AfterName,
					*Status);
			}
			else if (Feedback.Command == ECyclingInputCommand::StartOrResume)
			{
				if (Feedback.Before.Lifecycle == ECyclingDiagnosticsLifecycle::Stopped)
				{
					Output += FString::Printf(
						TEXT("%s - RESUME\n%s -> %s\ndistance preserved: %.2f m\n%s\n"),
						Tag, *BeforeName, *AfterName,
						Feedback.After.DistanceM,
						*Status);
				}
				else
				{
					Output += FString::Printf(
						TEXT("%s - START\n%s -> %s\n%s\n"),
						Tag, *BeforeName, *AfterName,
						*Status);
				}
			}
			else if (Feedback.Command == ECyclingInputCommand::Stop)
			{
				Output += FString::Printf(
					TEXT("%s - STOP\n%s -> %s\n%s\n"),
					Tag, *BeforeName, *AfterName,
					*Status);
			}
			else
			{
				Output += FString::Printf(
					TEXT("%s - %s\n%s -> %s\n%s\n"),
					Tag, *Label, *BeforeName, *AfterName,
					*Status);
			}
		}
		else
		{
			Output += TEXT("(none)\n");
		}

		// 4. MANUAL ACCEPTANCE.
		if (bEnableGuidedAcceptance)
		{
			Output += TEXT("\nMANUAL ACCEPTANCE\n");
			const int32 Total = 7;
			const int32 StepNum = GuidedStepNumber(Guided.CurrentStep);
			Output += FString::Printf(TEXT("%d/%d - %s\n"), StepNum, Total,
				GuidedStepPrompt(Guided.CurrentStep));
			Output += FString::Printf(TEXT("Expected: %s\n"),
				*GuidedStepExpected(Guided.CurrentStep,
					Snapshot.ConfiguredPowerStepW,
					Snapshot.ConfiguredCadenceStepRpm));
			if (!Guided.StepStatus.IsEmpty())
			{
				Output += FString::Printf(TEXT("Status: %s"),
					*Guided.StepStatus);
				if (!Guided.StepNote.IsEmpty())
				{
					Output += FString::Printf(TEXT(" (%s)"), *Guided.StepNote);
				}
				Output += TEXT("\n");
			}

			// Stop stability sub-block (only relevant in step 4).
			if (Guided.CurrentStep == ECyclingGuidedAcceptanceStep::Running_WaitStop
				&& !Guided.StopStabilityStatus.IsEmpty())
			{
				Output += FString::Printf(TEXT("STOPPED stability: %s\n"),
					*Guided.StopStabilityStatus);
			}
		}

		return Output;
	}

	// -----------------------------------------------------------------
	// Guided acceptance observer.
	// -----------------------------------------------------------------
	FCyclingGuidedAcceptanceState AdvanceGuidedAcceptance(
		const FCyclingGuidedAcceptanceState& Current,
		const FCyclingLastInputFeedback& LastFeedback,
		const FCyclingInputSnapshot& CurrentSnapshot,
		bool bEnableGuidedAcceptance)
	{
		FCyclingGuidedAcceptanceState Next = Current;
		if (!bEnableGuidedAcceptance)
		{
			return Next;
		}

		// No feedback yet: stay at current step.
		if (LastFeedback.Command == ECyclingInputCommand::None)
		{
			return Next;
		}

		auto AdvanceWithStatus = [&Next](
			ECyclingGuidedAcceptanceStep ToStep,
			const FString& Status,
			const FString& Note)
		{
			Next.CurrentStep = ToStep;
			Next.StepStatus = Status;
			Next.StepNote = Note;
		};

		switch (Current.CurrentStep)
		{
		case ECyclingGuidedAcceptanceStep::Ready_WaitStart:
			if (LastFeedback.Command == ECyclingInputCommand::StartOrResume
				&& LastFeedback.bAccepted
				&& CurrentSnapshot.Lifecycle == ECyclingDiagnosticsLifecycle::Running)
			{
				AdvanceWithStatus(
					ECyclingGuidedAcceptanceStep::Running_WaitPowerUp,
					TEXT("PASS"), TEXT("READY -> RUNNING"));
			}
			break;

		case ECyclingGuidedAcceptanceStep::Running_WaitPowerUp:
			if (LastFeedback.Command == ECyclingInputCommand::PowerIncrease
				&& LastFeedback.bAccepted)
			{
				AdvanceWithStatus(
					ECyclingGuidedAcceptanceStep::Running_WaitCadenceUp,
					TEXT("PASS"), TEXT("power +1 step"));
			}
			else if (IsPowerCommand(LastFeedback.Command) && !LastFeedback.bAccepted)
			{
				Next.StepStatus = TEXT("FAIL");
				Next.StepNote = TEXT("expected power +1 step");
			}
			break;

		case ECyclingGuidedAcceptanceStep::Running_WaitCadenceUp:
			if (LastFeedback.Command == ECyclingInputCommand::CadenceIncrease
				&& LastFeedback.bAccepted)
			{
				AdvanceWithStatus(
					ECyclingGuidedAcceptanceStep::Running_WaitStop,
					TEXT("PASS"), TEXT("cadence +1 step"));
			}
			else if (IsCadenceCommand(LastFeedback.Command) && !LastFeedback.bAccepted)
			{
				Next.StepStatus = TEXT("FAIL");
				Next.StepNote = TEXT("expected cadence +1 step");
			}
			break;

		case ECyclingGuidedAcceptanceStep::Running_WaitStop:
			if (LastFeedback.Command == ECyclingInputCommand::Stop
				&& LastFeedback.bAccepted)
			{
				AdvanceWithStatus(
					ECyclingGuidedAcceptanceStep::Stopped_WaitStart,
					TEXT("PASS"), TEXT("RUNNING -> STOPPED"));
				// Capture StopEntrySnapshot only now (on real
				// transition) so the stability check has a useful
				// reference.
				Next.StopEntrySnapshot = CurrentSnapshot;
				Next.StopStabilityObservedTicks = 0;
				Next.bStopStable = false;
				Next.StopStabilityStatus.Reset();
			}
			break;

		case ECyclingGuidedAcceptanceStep::Stopped_WaitStart:
			if (LastFeedback.Command == ECyclingInputCommand::StartOrResume
				&& LastFeedback.bAccepted)
			{
				AdvanceWithStatus(
					ECyclingGuidedAcceptanceStep::Running_WaitRestart,
					TEXT("PASS"), TEXT("STOPPED -> RUNNING, preserved"));
			}
			break;

		case ECyclingGuidedAcceptanceStep::Running_WaitRestart:
			if (LastFeedback.Command == ECyclingInputCommand::Restart
				&& LastFeedback.bAccepted)
			{
				AdvanceWithStatus(
					ECyclingGuidedAcceptanceStep::Finished,
					TEXT("PASS"), TEXT("state reset"));
			}
			break;

		case ECyclingGuidedAcceptanceStep::Finished:
			// Stay. The overlay shows "Press R to Restart".
			break;
		}

		// Stop stability reset: when leaving Running_WaitStop.
		if (Current.CurrentStep == ECyclingGuidedAcceptanceStep::Running_WaitStop
			&& Next.CurrentStep != ECyclingGuidedAcceptanceStep::Running_WaitStop)
		{
			Next.StopEntrySnapshot = FCyclingInputSnapshot();
			Next.StopStabilityObservedTicks = 0;
			Next.bStopStable = false;
			Next.StopStabilityStatus.Reset();
		}

		return Next;
	}

	FCyclingGuidedAcceptanceState ObserveStopStability(
		const FCyclingGuidedAcceptanceState& Current,
		const FCyclingInputSnapshot& CurrentSnapshot)
	{
		FCyclingGuidedAcceptanceState Next = Current;

		const bool bHasSnapshot =
			Current.StopEntrySnapshot.Lifecycle != ECyclingDiagnosticsLifecycle::Uninitialized;

		if (!bHasSnapshot)
		{
			return Next;
		}

		const bool bDistStable = FMath::IsNearlyEqual(
			Current.StopEntrySnapshot.DistanceM, CurrentSnapshot.DistanceM, 1e-6);
		const bool bTimeStable = FMath::IsNearlyEqual(
			Current.StopEntrySnapshot.ElapsedTimeS, CurrentSnapshot.ElapsedTimeS, 1e-9);

		Next.bStopStable = bDistStable && bTimeStable;
		if (Next.bStopStable)
		{
			Next.StopStabilityObservedTicks += 1;
		}
		else
		{
			Next.StopStabilityObservedTicks = 0;
		}

		// PASS after at least one full observation (>= 1 tick) so
		// the user cannot see a transient PASS that flips to FAIL
		// on the very next refresh.
		if (Next.StopStabilityObservedTicks >= 1)
		{
			Next.StopStabilityStatus = FString::Printf(
				TEXT("Distance stable: %s, Time stable: %s"),
				bDistStable ? TEXT("PASS") : TEXT("FAIL"),
				bTimeStable ? TEXT("PASS") : TEXT("FAIL"));
		}
		else
		{
			Next.StopStabilityStatus.Reset();
		}

		return Next;
	}
}