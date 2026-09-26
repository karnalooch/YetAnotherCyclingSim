#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/Braking.h"
#include "Cycling/CyclingForces.h"

#include <cmath>
#include <limits>

namespace Stage4CBrakingTests
{
	FRiderParameters MakeRider()
	{
		FRiderParameters Rider;
		Rider.RiderMassKg = 75.0;
		Rider.BikeMassKg = 8.5;
		Rider.CdaM2 = 0.32;
		Rider.RollingResistanceCoefficient = 0.004;
		Rider.DrivetrainEfficiency = 0.97;
		return Rider;
	}

	bool NearlyEqual(double A, double B, double Tolerance = 1e-9)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakingZeroTest,
	"CyclingCornering.Braking.ZeroDemand",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakingZeroTest::RunTest(const FString& Parameters)
{
	using namespace CyclingBraking;
	using namespace Stage4CBrakingTests;

	FBrakingForceDemand Demand;
	FString Error;
	TestTrue(TEXT("zero brake resolves"),
		TryCalculateBrakingForceDemand(
			MakeRider(), 0.0, 0.0, 0.8, 0.0, 0.0, Demand, Error));
	TestTrue(TEXT("zero applied usage"), NearlyEqual(Demand.AppliedLongitudinalUsage, 0.0));
	TestTrue(TEXT("zero brake force"), NearlyEqual(Demand.AppliedBrakeForceN, 0.0));
	TestTrue(TEXT("zero brake acceleration"), NearlyEqual(Demand.AppliedBrakeAccelerationMps2, 0.0));
	TestFalse(TEXT("zero demand not saturated"), Demand.bSaturatedBySharedBudget);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakingFlatCapacityTest,
	"CyclingCornering.Braking.FlatCapacity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakingFlatCapacityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingBraking;
	using namespace Stage4CBrakingTests;

	const FRiderParameters Rider = MakeRider();
	const double TotalMassKg = Rider.GetTotalMassKg();
	const double Mu = 0.8;

	FBrakingForceDemand Demand;
	FString Error;
	TestTrue(TEXT("full flat brake resolves"),
		TryCalculateBrakingForceDemand(
			Rider, 0.0, 0.0, Mu, 1.0, 0.0, Demand, Error));

	const double ExpectedNormalN =
		TotalMassKg * CyclingForces::StandardGravityMps2;
	const double ExpectedForceN = Mu * ExpectedNormalN;

	TestTrue(TEXT("flat normal load parity"),
		NearlyEqual(Demand.StaticNormalLoadN, ExpectedNormalN));
	TestTrue(TEXT("flat force capacity parity"),
		NearlyEqual(Demand.StandaloneLongitudinalForceCapacityN, ExpectedForceN));
	TestTrue(TEXT("full brake uses full capacity"),
		NearlyEqual(Demand.AppliedBrakeForceN, ExpectedForceN));
	TestTrue(TEXT("flat brake acceleration parity"),
		NearlyEqual(
			Demand.AppliedBrakeAccelerationMps2,
			Mu * CyclingForces::StandardGravityMps2));
	TestFalse(TEXT("full straight brake is not shared-budget saturated"),
		Demand.bSaturatedBySharedBudget);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakingSharedBudgetTest,
	"CyclingCornering.Braking.SharedBudgetSaturation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakingSharedBudgetTest::RunTest(const FString& Parameters)
{
	using namespace CyclingBraking;
	using namespace Stage4CBrakingTests;

	FBrakingForceDemand Demand;
	FString Error;
	TestTrue(TEXT("0.8 brake / 0.8 lateral resolves"),
		TryCalculateBrakingForceDemand(
			MakeRider(), 0.0, 0.0, 0.8, 0.8, 0.8, Demand, Error));

	TestTrue(TEXT("requested shared budget is exceeded"),
		Demand.RequestedBudget.bExceeded);
	TestTrue(TEXT("requested combined usage exceeds one"),
		Demand.RequestedBudget.CombinedUsage > 1.0);
	TestTrue(TEXT("remaining longitudinal capacity is 0.6"),
		NearlyEqual(Demand.RequestedBudget.RemainingLongitudinalCapacity, 0.6));
	TestTrue(TEXT("applied longitudinal usage is capped to 0.6"),
		NearlyEqual(Demand.AppliedLongitudinalUsage, 0.6));
	TestTrue(TEXT("shared budget saturation is reported"),
		Demand.bSaturatedBySharedBudget);
	TestTrue(TEXT("force uses applied rather than requested usage"),
		NearlyEqual(
			Demand.AppliedBrakeForceN,
			0.6 * Demand.StandaloneLongitudinalForceCapacityN));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakingSurfaceTiltTest,
	"CyclingCornering.Braking.SurfaceAndTilt",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakingSurfaceTiltTest::RunTest(const FString& Parameters)
{
	using namespace CyclingBraking;
	using namespace Stage4CBrakingTests;

	FString Error;
	FBrakingForceDemand FlatDry;
	FBrakingForceDemand TiltedDry;
	FBrakingForceDemand FlatWet;

	TestTrue(TEXT("flat dry resolves"),
		TryCalculateBrakingForceDemand(
			MakeRider(), 0.0, 0.0, 0.8, 1.0, 0.0, FlatDry, Error));
	TestTrue(TEXT("tilted dry resolves"),
		TryCalculateBrakingForceDemand(
			MakeRider(),
			0.10,
			FMath::DegreesToRadians(8.0),
			0.8,
			1.0,
			0.0,
			TiltedDry,
			Error));
	TestTrue(TEXT("flat lower-friction resolves"),
		TryCalculateBrakingForceDemand(
			MakeRider(), 0.0, 0.0, 0.6, 1.0, 0.0, FlatWet, Error));

	TestTrue(TEXT("tilt reduces static gravity-normal load"),
		TiltedDry.StaticNormalLoadN < FlatDry.StaticNormalLoadN);
	TestTrue(TEXT("lower friction reduces standalone brake capacity"),
		FlatWet.StandaloneLongitudinalForceCapacityN
			< FlatDry.StandaloneLongitudinalForceCapacityN);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CBrakingValidationTest,
	"CyclingCornering.Braking.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CBrakingValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingBraking;
	using namespace Stage4CBrakingTests;

	FBrakingForceDemand Demand;
	FString Error;
	const double NaN = std::numeric_limits<double>::quiet_NaN();

	TestFalse(TEXT("zero friction rejected"),
		TryCalculateBrakingForceDemand(
			MakeRider(), 0.0, 0.0, 0.0, 0.5, 0.0, Demand, Error));
	TestFalse(TEXT("brake above one rejected"),
		TryCalculateBrakingForceDemand(
			MakeRider(), 0.0, 0.0, 0.8, 1.01, 0.0, Demand, Error));
	TestFalse(TEXT("negative lateral usage rejected"),
		TryCalculateBrakingForceDemand(
			MakeRider(), 0.0, 0.0, 0.8, 0.5, -0.01, Demand, Error));
	TestFalse(TEXT("NaN grade rejected"),
		TryCalculateBrakingForceDemand(
			MakeRider(), NaN, 0.0, 0.8, 0.5, 0.0, Demand, Error));
	TestFalse(TEXT("cross-slope boundary rejected"),
		TryCalculateBrakingForceDemand(
			MakeRider(),
			0.0,
			0.5 * std::acos(-1.0),
			0.8,
			0.5,
			0.0,
			Demand,
			Error));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
