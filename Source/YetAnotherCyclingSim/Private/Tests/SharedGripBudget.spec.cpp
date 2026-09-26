#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/SharedGripBudget.h"

#include <cmath>
#include <limits>

namespace Stage4CSharedGripBudgetTests
{
	bool NearlyEqual(double A, double B, double Tolerance = 1e-12)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CSharedGripZeroTest,
	"CyclingCornering.SharedGripBudget.ZeroDemand",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CSharedGripZeroTest::RunTest(const FString& Parameters)
{
	using namespace CyclingGripBudget;
	using namespace Stage4CSharedGripBudgetTests;

	FSharedGripBudget Budget;
	FString Error;
	TestTrue(TEXT("zero demand resolves"),
		TryCalculateSharedGripBudget(0.0, 0.0, Budget, Error));
	TestTrue(TEXT("combined usage is zero"), NearlyEqual(Budget.CombinedUsage, 0.0));
	TestTrue(TEXT("full longitudinal capacity remains"),
		NearlyEqual(Budget.RemainingLongitudinalCapacity, 1.0));
	TestTrue(TEXT("full lateral capacity remains"),
		NearlyEqual(Budget.RemainingLateralCapacity, 1.0));
	TestFalse(TEXT("zero demand does not exceed"), Budget.bExceeded);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CSharedGripAxisParityTest,
	"CyclingCornering.SharedGripBudget.AxisParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CSharedGripAxisParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingGripBudget;
	using namespace Stage4CSharedGripBudgetTests;

	FString Error;
	FSharedGripBudget Longitudinal;
	FSharedGripBudget Lateral;
	TestTrue(TEXT("pure longitudinal resolves"),
		TryCalculateSharedGripBudget(0.7, 0.0, Longitudinal, Error));
	TestTrue(TEXT("pure lateral resolves"),
		TryCalculateSharedGripBudget(0.0, 0.7, Lateral, Error));

	TestTrue(TEXT("longitudinal combined parity"),
		NearlyEqual(Longitudinal.CombinedUsage, 0.7));
	TestTrue(TEXT("lateral combined parity"),
		NearlyEqual(Lateral.CombinedUsage, 0.7));

	const double ExpectedRemaining = std::sqrt(1.0 - 0.7 * 0.7);
	TestTrue(TEXT("longitudinal demand reduces lateral reserve"),
		NearlyEqual(Longitudinal.RemainingLateralCapacity, ExpectedRemaining));
	TestTrue(TEXT("lateral demand reduces longitudinal reserve"),
		NearlyEqual(Lateral.RemainingLongitudinalCapacity, ExpectedRemaining));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CSharedGripBoundaryTest,
	"CyclingCornering.SharedGripBudget.CircleBoundary",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CSharedGripBoundaryTest::RunTest(const FString& Parameters)
{
	using namespace CyclingGripBudget;
	using namespace Stage4CSharedGripBudgetTests;

	FSharedGripBudget Budget;
	FString Error;
	TestTrue(TEXT("0.6/0.8 resolves"),
		TryCalculateSharedGripBudget(0.6, 0.8, Budget, Error));
	TestTrue(TEXT("3-4-5 normalized pair reaches exact circle"),
		NearlyEqual(Budget.CombinedUsage, 1.0));
	TestTrue(TEXT("remaining lateral capacity is 0.8"),
		NearlyEqual(Budget.RemainingLateralCapacity, 0.8));
	TestTrue(TEXT("remaining longitudinal capacity is 0.6"),
		NearlyEqual(Budget.RemainingLongitudinalCapacity, 0.6));
	TestFalse(TEXT("exact circle boundary is not exceeded"), Budget.bExceeded);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CSharedGripCombinedExceedTest,
	"CyclingCornering.SharedGripBudget.CombinedDemand",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CSharedGripCombinedExceedTest::RunTest(const FString& Parameters)
{
	using namespace CyclingGripBudget;
	using namespace Stage4CSharedGripBudgetTests;

	FSharedGripBudget Budget;
	FString Error;
	TestTrue(TEXT("0.8/0.8 resolves"),
		TryCalculateSharedGripBudget(0.8, 0.8, Budget, Error));
	TestTrue(TEXT("each axis is individually at or below full usage"),
		Budget.LongitudinalUsage <= 1.0 && Budget.LateralUsage <= 1.0);
	TestTrue(TEXT("shared budget catches combined over-demand"),
		Budget.CombinedUsage > 1.0);
	TestTrue(TEXT("combined over-demand is marked exceeded"), Budget.bExceeded);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CSharedGripNoClampTest,
	"CyclingCornering.SharedGripBudget.NoClamp",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CSharedGripNoClampTest::RunTest(const FString& Parameters)
{
	using namespace CyclingGripBudget;
	using namespace Stage4CSharedGripBudgetTests;

	FSharedGripBudget Budget;
	FString Error;
	TestTrue(TEXT("over-limit axis demand resolves"),
		TryCalculateSharedGripBudget(1.2, 0.0, Budget, Error));
	TestTrue(TEXT("input is not clamped"), NearlyEqual(Budget.LongitudinalUsage, 1.2));
	TestTrue(TEXT("combined usage remains observable"), NearlyEqual(Budget.CombinedUsage, 1.2));
	TestTrue(TEXT("lateral reserve is exhausted"),
		NearlyEqual(Budget.RemainingLateralCapacity, 0.0));
	TestTrue(TEXT("budget is exceeded"), Budget.bExceeded);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4CSharedGripValidationTest,
	"CyclingCornering.SharedGripBudget.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4CSharedGripValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingGripBudget;

	FSharedGripBudget Budget;
	FString Error;
	TestFalse(TEXT("negative longitudinal usage rejected"),
		TryCalculateSharedGripBudget(-0.01, 0.0, Budget, Error));
	TestFalse(TEXT("negative lateral usage rejected"),
		TryCalculateSharedGripBudget(0.0, -0.01, Budget, Error));
	TestFalse(TEXT("NaN longitudinal usage rejected"),
		TryCalculateSharedGripBudget(
			std::numeric_limits<double>::quiet_NaN(),
			0.0,
			Budget,
			Error));
	TestFalse(TEXT("infinite lateral usage rejected"),
		TryCalculateSharedGripBudget(
			0.0,
			std::numeric_limits<double>::infinity(),
			Budget,
			Error));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
