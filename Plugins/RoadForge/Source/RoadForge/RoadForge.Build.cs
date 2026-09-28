// Copyright RoadForge Contributors. Licensed under the MIT License.

using UnrealBuildTool;

public class RoadForge : ModuleRules
{
	public RoadForge(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"ProceduralMeshComponent",
		});
	}
}
