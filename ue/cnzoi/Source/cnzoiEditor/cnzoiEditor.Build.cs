using UnrealBuildTool;

public class cnzoiEditor : ModuleRules
{
	public cnzoiEditor(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PrivateDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"UnrealEd",
			"AssetRegistry",
			"GameplayTags",
			"cnzoi"
		});
	}
}
