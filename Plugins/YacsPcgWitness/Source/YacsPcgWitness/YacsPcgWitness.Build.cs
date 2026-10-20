using UnrealBuildTool;

public class YacsPcgWitness : ModuleRules
{
    public YacsPcgWitness(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        // The public reflected types inherit from Engine and ToolsetRegistry classes.
        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "ToolsetRegistry"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "UnrealEd",
            "PCG",
            "Json"
        });
    }
}
