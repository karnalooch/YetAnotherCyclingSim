// PCG365 native authoring is a separate opt-in Editor target.
// Do not modify the byte-pinned YetAnotherCyclingSim.uproject launcher
// or the ordinary YetAnotherCyclingSimEditor target to enable MCP toolsets.
using UnrealBuildTool;

public class YetAnotherCyclingSimPcg365EditorTarget : TargetRules
{
    public YetAnotherCyclingSimPcg365EditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("YetAnotherCyclingSim");
        ExtraModuleNames.Add("YetAnotherCyclingSimEditor");

        // Official UBT TargetRules.EnablePlugins opt-in (UE 5.8).
        // Keep the reflected witness and its registry lifecycle out of the common Editor module.
        EnablePlugins.Add("YacsPcgWitness");
        EnablePlugins.Add("ToolsetRegistry");
        EnablePlugins.Add("ModelContextProtocol");
    }
}
