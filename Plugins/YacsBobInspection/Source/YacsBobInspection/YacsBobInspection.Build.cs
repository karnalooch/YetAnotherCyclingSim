using UnrealBuildTool;

public class YacsBobInspection : ModuleRules
{
    public YacsBobInspection(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "ToolsetRegistry" });
        PrivateDependencyModuleNames.AddRange(new[] {
            "UnrealEd", "Landscape", "Json", "JsonUtilities", "DeveloperSettings", "AutomationController",
            "AutomationTestToolset", "ModelContextProtocol", "ModelContextProtocolEngine",
            "PythonScriptPlugin"
        });
    }
}
