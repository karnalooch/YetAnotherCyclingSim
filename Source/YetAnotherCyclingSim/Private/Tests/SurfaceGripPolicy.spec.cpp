#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"
#include "Math/UnrealMathUtility.h"

#include "Cycling/SurfaceGripPolicy.h"

#include <limits>

namespace Stage4BSurfaceGripTests
{
	using namespace CyclingSurfaceGrip;

	FSurfaceGripPolicy BuildTestPolicy(FString& OutError)
	{
		TArray<FSurfaceGripRuleDefinition> Rules;
		Rules.Add({TEXT("asphalt"), 1.0, 0.75});
		Rules.Add({TEXT("paint"), 0.90, 0.60});

		FSurfaceGripPolicy Policy;
		Policy.TryConfigure(TEXT("Test policy"), Rules, OutError);
		return Policy;
	}

	bool NearlyEqual(double A, double B, double Tolerance = 1e-12)
	{
		return FMath::Abs(A - B) <= Tolerance;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BSurfaceGripInterpolationTest,
	"CyclingCornering.SurfaceGrip.Interpolation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BSurfaceGripInterpolationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BSurfaceGripTests;

	FString Error;
	FSurfaceGripPolicy Policy = BuildTestPolicy(Error);
	TestTrue(TEXT("test policy configures"), Policy.IsConfigured());

	FResolvedSurfaceGrip Grip;
	TestTrue(TEXT("dry asphalt resolves"), Policy.TryResolve(TEXT("asphalt"), 0.0, Grip, Error));
	TestTrue(TEXT("dry asphalt is 1.0"), NearlyEqual(Grip.GripMultiplier, 1.0));

	TestTrue(TEXT("half-wet asphalt resolves"), Policy.TryResolve(TEXT("asphalt"), 0.5, Grip, Error));
	TestTrue(TEXT("half-wet asphalt is 0.875"), NearlyEqual(Grip.GripMultiplier, 0.875));
	TestEqual(TEXT("surface id passes through"), Grip.SurfaceId, FString(TEXT("asphalt")));
	TestTrue(TEXT("wetness passes through"), NearlyEqual(Grip.Wetness, 0.5));

	TestTrue(TEXT("fully-wet asphalt resolves"), Policy.TryResolve(TEXT("asphalt"), 1.0, Grip, Error));
	TestTrue(TEXT("fully-wet asphalt is 0.75"), NearlyEqual(Grip.GripMultiplier, 0.75));

	TestTrue(TEXT("paint resolves independently"), Policy.TryResolve(TEXT("paint"), 0.5, Grip, Error));
	TestTrue(TEXT("paint midpoint is 0.75"), NearlyEqual(Grip.GripMultiplier, 0.75));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BAlpineSurfaceGripParityTest,
	"CyclingCornering.SurfaceGrip.AlpineWeatherParity",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BAlpineSurfaceGripParityTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BSurfaceGripTests;

	FSurfaceGripPolicy Policy;
	FString Error;
	TestTrue(TEXT("Alpine policy builds"), TryBuildAlpineSurfaceGripPolicy(Policy, Error));
	TestEqual(TEXT("Alpine policy has one explicit surface"), Policy.GetRules().Num(), 1);
	TestEqual(TEXT("Alpine surface is asphalt"), Policy.GetRules()[0].SurfaceId, FString(TEXT("asphalt")));

	struct FWeatherParity
	{
		double Wetness;
		double ExistingGripMultiplier;
	};

	const FWeatherParity ExistingAlpineWeather[] = {
		{0.0, 1.00},
		{0.0, 1.00},
		{0.2, 0.95},
		{0.8, 0.80},
		{1.0, 0.75},
		{0.6, 0.85},
		{0.2, 0.95},
		{0.0, 1.00},
	};

	for (const FWeatherParity& Expected : ExistingAlpineWeather)
	{
		FResolvedSurfaceGrip Grip;
		TestTrue(
			TEXT("Alpine weather wetness resolves"),
			Policy.TryResolve(TEXT("asphalt"), Expected.Wetness, Grip, Error));
		TestTrue(
			TEXT("existing Alpine grip multiplier parity"),
			NearlyEqual(Grip.GripMultiplier, Expected.ExistingGripMultiplier));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BSurfaceGripValidationTest,
	"CyclingCornering.SurfaceGrip.Validation",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BSurfaceGripValidationTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BSurfaceGripTests;

	FString Error;
	FSurfaceGripPolicy Policy = BuildTestPolicy(Error);
	FResolvedSurfaceGrip Grip;

	TestFalse(TEXT("unknown surface fails closed"),
		Policy.TryResolve(TEXT("gravel"), 0.5, Grip, Error));
	TestTrue(TEXT("unknown surface reports configured-policy error"),
		Error.Contains(TEXT("not configured")));

	TestFalse(TEXT("negative wetness rejected"),
		Policy.TryResolve(TEXT("asphalt"), -0.01, Grip, Error));
	TestFalse(TEXT("wetness above one rejected"),
		Policy.TryResolve(TEXT("asphalt"), 1.01, Grip, Error));
	TestFalse(TEXT("NaN wetness rejected"),
		Policy.TryResolve(
			TEXT("asphalt"),
			std::numeric_limits<double>::quiet_NaN(),
			Grip,
			Error));

	TArray<FSurfaceGripRuleDefinition> Duplicate;
	Duplicate.Add({TEXT("asphalt"), 1.0, 0.75});
	Duplicate.Add({TEXT("asphalt"), 0.9, 0.7});
	FSurfaceGripPolicy Invalid;
	TestFalse(TEXT("duplicate surface rejected"),
		Invalid.TryConfigure(TEXT("duplicate"), Duplicate, Error));

	TArray<FSurfaceGripRuleDefinition> Empty;
	TestFalse(TEXT("empty rules rejected"),
		Invalid.TryConfigure(TEXT("empty"), Empty, Error));

	TArray<FSurfaceGripRuleDefinition> BadMultiplier;
	BadMultiplier.Add({TEXT("asphalt"), 0.0, 0.75});
	TestFalse(TEXT("zero dry multiplier rejected"),
		Invalid.TryConfigure(TEXT("bad"), BadMultiplier, Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FStage4BSurfaceGripTransactionalConfigTest,
	"CyclingCornering.SurfaceGrip.TransactionalConfiguration",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FStage4BSurfaceGripTransactionalConfigTest::RunTest(const FString& Parameters)
{
	using namespace CyclingSurfaceGrip;
	using namespace Stage4BSurfaceGripTests;

	FString Error;
	FSurfaceGripPolicy Policy = BuildTestPolicy(Error);
	TestTrue(TEXT("baseline policy configures"), Policy.IsConfigured());

	TArray<FSurfaceGripRuleDefinition> Duplicate;
	Duplicate.Add({TEXT("bad"), 1.0, 0.8});
	Duplicate.Add({TEXT("bad"), 0.9, 0.7});
	TestFalse(TEXT("failed reconfiguration is rejected"),
		Policy.TryConfigure(TEXT("broken"), Duplicate, Error));

	TestEqual(TEXT("previous policy name is preserved"),
		Policy.GetName(), FString(TEXT("Test policy")));
	TestEqual(TEXT("previous rules are preserved"), Policy.GetRules().Num(), 2);

	FResolvedSurfaceGrip Grip;
	TestTrue(TEXT("previous configured policy still resolves"),
		Policy.TryResolve(TEXT("asphalt"), 0.5, Grip, Error));
	TestTrue(TEXT("previous policy result remains intact"),
		NearlyEqual(Grip.GripMultiplier, 0.875));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
