#pragma once

#include "Containers/UnrealString.h"
#include "CoreTypes.h"

#include "Cycling/CornerContext.h"
#include "Cycling/CornerLateralLimit.h"
#include "Cycling/SharedGripBudget.h"

namespace CyclingCornerGrip
{
	// One fixed-step normalized grip-demand snapshot.
	//
	// LongitudinalUsage is the explicit normalized brake command from Stage
	// 4C-B1. LateralUsage is derived from actual cornering acceleration demand
	// divided by the Stage 4B-C physical lateral acceleration limit.
	struct YETANOTHERCYCLINGSIM_API FCornerGripDemand
	{
		double SpeedMps = 0.0;
		double LateralAccelerationDemandMps2 = 0.0;
		double LongitudinalUsage = 0.0;
		double LateralUsage = 0.0;
		CyclingGripBudget::FSharedGripBudget Budget;
	};

	// Bridges Stage 4B corner physics into the Stage 4C shared friction circle.
	//
	// This function accounts for demand only. It deliberately does not apply
	// braking force to forward speed and does not invent a brake-force
	// coefficient or hardware model.
	YETANOTHERCYCLINGSIM_API bool TryCalculateCornerGripDemand(
		const CyclingCornerContext::FCornerContext& Context,
		const CyclingCornerLimit::FCornerLateralLimit& LateralLimit,
		double SpeedMps,
		double BrakeRatio,
		FCornerGripDemand& OutDemand,
		FString& OutError);
}
