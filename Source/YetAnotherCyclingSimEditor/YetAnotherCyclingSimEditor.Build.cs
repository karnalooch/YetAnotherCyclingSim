using UnrealBuildTool;

public class YetAnotherCyclingSimEditor : ModuleRules
{
	public YetAnotherCyclingSimEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"UnrealEd",
			"PCG",
			"YetAnotherCyclingSim"
		});
	}
}
