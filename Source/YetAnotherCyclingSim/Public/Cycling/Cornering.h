#pragma once

#include "Containers/Array.h"
#include "Containers/UnrealString.h"
#include "CoreTypes.h"

namespace CyclingCornering
{
	enum class ECornerPhase : uint8
	{
		Outside,
		Approach,
		Entry,
		Apex,
		Exit,
	};

	enum class ECornerGripStatus : uint8
	{
		Safe,
		NearLimit,
		GripExceeded,
	};

	enum class ECornerTechniqueRating : uint8
	{
		Excellent,
		Good,
		NeedsImprovement,
		Poor,
	};

	enum class ECornerTechniqueFeedback : uint8
	{
		GoodTechnique,
		ReduceSpeed,
		ReleaseEarlier,
		StayOffPowerAtApex,
		AccelerateOnExit,
	};

	enum class ECornerOutcome : uint8
	{
		Clean,
		WideLine,
		ControlledSlip,
	};

	enum class ECornerHudFeedback : uint8
	{
		CleanCorner,
		WiderSlowerLine,
		RearWheelSlip,
	};

	struct YETANOTHERCYCLINGSIM_API FCornerDefinition
	{
		FString Name;
		double StartDistanceM = 0.0;
		double LengthM = 0.0;
		double RadiusM = 0.0;
	};

	class YETANOTHERCYCLINGSIM_API FCorner
	{
	public:
		FCorner() = default;

		bool IsConfigured() const { return bIsConfigured; }
		const FString& GetName() const { return Name; }
		double GetStartDistanceM() const { return StartDistanceM; }
		double GetLengthM() const { return LengthM; }
		double GetRadiusM() const { return RadiusM; }
		double GetEndDistanceM() const { return StartDistanceM + LengthM; }

	private:
		friend class FCornerProfile;

		FString Name;
		double StartDistanceM = 0.0;
		double LengthM = 0.0;
		double RadiusM = 0.0;
		bool bIsConfigured = false;
	};

	class YETANOTHERCYCLINGSIM_API FCornerProfile
	{
	public:
		FCornerProfile() = default;

		// Transactional configuration mirroring the Python CornerProfile:
		// an empty corner list is valid, touching corners are valid, overlap is
		// rejected and each corner occupies [start, end).
		bool TryConfigure(
			const FString& InName,
			double InTotalLengthM,
			const TArray<FCornerDefinition>& InCorners,
			FString& OutError);

		bool IsConfigured() const { return bIsConfigured; }
		const FString& GetName() const { return Name; }
		double GetTotalLengthM() const { return TotalLengthM; }
		const TArray<FCorner>& GetCorners() const { return Corners; }

		// Returns true for a valid route distance even when that distance is
		// outside every corner. In that case OutCorner is null and
		// OutCornerIndex is INDEX_NONE.
		bool TryGetCornerAtDistance(
			double DistanceM,
			const FCorner*& OutCorner,
			int32& OutCornerIndex,
			FString& OutError) const;

	private:
		FString Name;
		double TotalLengthM = 0.0;
		TArray<FCorner> Corners;
		bool bIsConfigured = false;
	};

	struct YETANOTHERCYCLINGSIM_API FCornerTechniqueSample
	{
		double DistanceM = 0.0;
		double PowerW = 0.0;
		double CadenceRpm = 0.0;
		double GripUsage = 0.0;
	};

	struct YETANOTHERCYCLINGSIM_API FCornerTechniqueSummary
	{
		double ApproachPowerW = 0.0;
		double EntryPowerW = 0.0;
		double ApexPowerW = 0.0;
		double ExitPowerW = 0.0;
		double ApproachCadenceRpm = 0.0;
		double EntryCadenceRpm = 0.0;
		double ApexCadenceRpm = 0.0;
		double ExitCadenceRpm = 0.0;
		double MaxGripUsage = 0.0;

		double GetEntryPowerRatio() const;
		double GetApexPowerRatio() const;
		double GetExitPowerRatio() const;
		double GetEntryCadenceRatio() const;
		double GetApexCadenceRatio() const;
		double GetExitCadenceRatio() const;
	};

	struct YETANOTHERCYCLINGSIM_API FCornerTechniqueAssessment
	{
		double Score = 0.0;
		ECornerTechniqueRating Rating = ECornerTechniqueRating::Poor;
		ECornerTechniqueFeedback Feedback = ECornerTechniqueFeedback::GoodTechnique;
		ECornerGripStatus GripStatus = ECornerGripStatus::Safe;
	};

	struct YETANOTHERCYCLINGSIM_API FCornerConsequence
	{
		ECornerOutcome Outcome = ECornerOutcome::Clean;
		double ExitSpeedMultiplier = 1.0;
		double LineDeviationRatio = 0.0;
		ECornerHudFeedback HudFeedback = ECornerHudFeedback::CleanCorner;
	};

	YETANOTHERCYCLINGSIM_API bool TryCalculateEffectiveFrictionCoefficient(
		double BaseFrictionCoefficient,
		double GripMultiplier,
		double& OutEffectiveFrictionCoefficient,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryCalculateMaximumCornerSpeedMps(
		double RadiusM,
		double BaseFrictionCoefficient,
		double GripMultiplier,
		double& OutMaximumSpeedMps,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryCalculateCornerGripUsage(
		double SpeedMps,
		double RadiusM,
		double BaseFrictionCoefficient,
		double GripMultiplier,
		double& OutGripUsage,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryClassifyCornerGripUsage(
		double GripUsage,
		ECornerGripStatus& OutStatus,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryGetCornerPhase(
		const FCorner& Corner,
		double DistanceM,
		double ApproachLengthM,
		ECornerPhase& OutPhase,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryGetDistanceToCornerStartM(
		const FCorner& Corner,
		double DistanceM,
		double& OutDistanceM,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TrySummarizeCornerTechnique(
		const FCorner& Corner,
		const TArray<FCornerTechniqueSample>& Samples,
		double ApproachLengthM,
		FCornerTechniqueSummary& OutSummary,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryAssessCornerTechnique(
		const FCornerTechniqueSummary& Summary,
		FCornerTechniqueAssessment& OutAssessment,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryCalculateCornerConsequence(
		double GripUsage,
		FCornerConsequence& OutConsequence,
		FString& OutError);

	YETANOTHERCYCLINGSIM_API bool TryApplyCornerExitSpeedMps(
		double SpeedMps,
		const FCornerConsequence& Consequence,
		double& OutSpeedMps,
		FString& OutError);
}
