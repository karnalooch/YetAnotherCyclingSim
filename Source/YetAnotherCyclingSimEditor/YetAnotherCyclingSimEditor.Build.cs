using UnrealBuildTool;
using System.IO;

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
			"Json",
			"AssetRegistry",
			"YetAnotherCyclingSim"
		});

		// PCGEx is deliberately an optional authoring-only dependency. The pinned
		// source checkout is materialized by Bootstrap-YacsPcgEx.ps1 for the
		// dedicated world-authoring proof. Ordinary builds remain PCGEx-free.
		string PcgExRoot = Path.GetFullPath(
			Path.Combine(ModuleDirectory, "..", "..", "Plugins", "PCGExtendedToolkit"));
		bool bWithPcgEx = File.Exists(Path.Combine(PcgExRoot, "PCGExtendedToolkit.uplugin"));
		PublicDefinitions.Add("YACS_WITH_PCGEX=" + (bWithPcgEx ? "1" : "0"));

		if (bWithPcgEx)
		{
			PrivateDependencyModuleNames.AddRange(new string[]
			{
				"PCGExCore",
				"PCGExBlending",
				"PCGExFoundations",
				"PCGExElementsPaths",
				"PCGExElementsSampling",
				"PCGExElementsTopology"
			});
		}
	}
}
