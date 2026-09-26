#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "CoreTypes.h"

namespace CyclingSurfaceGrip
{
	// Explicit grip multipliers for one physical surface.
	//
	// Multipliers are relative factors in (0, 1]. The tyre/base friction
	// coefficient remains a separate caller-owned input to the cornering
	// model. No hidden "realistic" coefficients are stored here.
	struct YETANOTHERCYCLINGSIM_API FSurfaceGripRuleDefinition
	{
		FString SurfaceId;
		double DryGripMultiplier = 0.0;
		double FullyWetGripMultiplier = 0.0;
	};

	struct YETANOTHERCYCLINGSIM_API FSurfaceGripRule
	{
		FString SurfaceId;
		double DryGripMultiplier = 0.0;
		double FullyWetGripMultiplier = 0.0;
	};

	struct YETANOTHERCYCLINGSIM_API FResolvedSurfaceGrip
	{
		FString SurfaceId;
		double Wetness = 0.0;
		double DryGripMultiplier = 0.0;
		double FullyWetGripMultiplier = 0.0;
		double GripMultiplier = 0.0;
	};

	// Deterministic surface + wetness policy.
	//
	// Wetness in [0,1] linearly interpolates between each rule's explicit dry
	// and fully-wet multipliers. Unknown surfaces fail closed rather than
	// silently falling back to asphalt or a global coefficient.
	class YETANOTHERCYCLINGSIM_API FSurfaceGripPolicy
	{
	public:
		bool TryConfigure(
			const FString& InName,
			const TArray<FSurfaceGripRuleDefinition>& InRules,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }
		const FString& GetName() const { return Name; }
		const TArray<FSurfaceGripRule>& GetRules() const { return Rules; }

		bool TryResolve(
			const FString& SurfaceId,
			double Wetness,
			FResolvedSurfaceGrip& OutGrip,
			FString& OutError) const;

	private:
		FString Name;
		TArray<FSurfaceGripRule> Rules;
		bool bIsConfigured = false;
	};

	// Alpine Journey baseline derived from the existing ALPINE_WEATHER
	// contract: asphalt grip is 1.00 at wetness=0 and 0.75 at wetness=1,
	// with the existing keyframes lying exactly on the linear interpolation.
	YETANOTHERCYCLINGSIM_API bool TryBuildAlpineSurfaceGripPolicy(
		FSurfaceGripPolicy& OutPolicy,
		FString& OutError);
}
