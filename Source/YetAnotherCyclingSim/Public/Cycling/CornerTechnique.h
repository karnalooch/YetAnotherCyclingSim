#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/CornerConsequence.h"
#include "Cycling/Cornering.h"

namespace CyclingCornerTechnique
{
	struct YETANOTHERCYCLINGSIM_API FRouteCornerTechniqueObservation
	{
		CyclingCornering::ECornerPhase Phase = CyclingCornering::ECornerPhase::Outside;
		double PowerW = 0.0;
		double CadenceRpm = 0.0;
	};

	struct YETANOTHERCYCLINGSIM_API FRouteCornerTechniqueSummary
	{
		double ApproachPowerW = 0.0;
		double EntryPowerW = 0.0;
		double ApexPowerW = 0.0;
		double ExitPowerW = 0.0;
		double ApproachCadenceRpm = 0.0;
		double EntryCadenceRpm = 0.0;
		double ApexCadenceRpm = 0.0;
		double ExitCadenceRpm = 0.0;
	};

	struct YETANOTHERCYCLINGSIM_API FRouteCornerTechniqueScore
	{
		double Score = 0.0;
		double EntryPowerReleaseScore = 0.0;
		double ApexPowerReleaseScore = 0.0;
		double ExitPowerRecoveryScore = 0.0;
		double EntryCadenceReleaseScore = 0.0;
		double ApexCadenceReleaseScore = 0.0;
		double ExitCadenceRecoveryScore = 0.0;
		double LineRetentionScore = 0.0;
		double SpeedRetentionScore = 0.0;
	};

	// Stage 4C-C2 aggregation over route-derived CornerContext phases.
	// Stage 4A corner definitions are intentionally not consulted here.
	YETANOTHERCYCLINGSIM_API bool TrySummarizeRouteCornerTechnique(
		const TArray<FRouteCornerTechniqueObservation>& Observations,
		FRouteCornerTechniqueSummary& OutSummary,
		FString& OutError);

	// Continuous threshold-free Stage 4C technique score.
	//
	// Entry/apex score toward released effort relative to the Approach
	// baseline; Exit scores toward recovered effort. C1 contributes physical
	// line and speed retention. All eight components are equally weighted.
	YETANOTHERCYCLINGSIM_API bool TryScoreRouteCornerTechnique(
		const FRouteCornerTechniqueSummary& Summary,
		const CyclingCornerConsequence::FCornerGeometryConsequence& Consequence,
		FRouteCornerTechniqueScore& OutScore,
		FString& OutError);
}
