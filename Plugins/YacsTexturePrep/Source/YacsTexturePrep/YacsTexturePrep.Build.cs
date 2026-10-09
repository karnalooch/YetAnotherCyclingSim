using UnrealBuildTool;

public class YacsTexturePrep : ModuleRules
{
    public YacsTexturePrep(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        bEnableExceptions = true; // Texture Graph public headers use exceptions.
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "ToolsetRegistry", "ImageCore" });
        PrivateDependencyModuleNames.AddRange(new[] {
            "TextureGraph", "TextureGraphEngine", "UnrealEd", "AssetRegistry",
            "Json", "JsonUtilities", "ImageCore", "RenderCore", "RHI"
        });
    }
}
