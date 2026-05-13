// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class cnzoi : ModuleRules
{
	public cnzoi(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[] {
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"AIModule",
			"NavigationSystem",
			"GameplayTags",
			"GameplayTasks",
			"StateTreeModule",
			"GameplayStateTreeModule",
			"UMG",
			"Slate"
		});

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.AddRange(new string[] {
			"cnzoi",
			"cnzoi/PCSP",
			"cnzoi/PCSP/Components",
			"cnzoi/PCSP/Affordance",
			"cnzoi/PCSP/Agent",
			"cnzoi/PCSP/Sim",
			"cnzoi/PCSP/BT",
			"cnzoi/Variant_Platforming",
			"cnzoi/Variant_Platforming/Animation",
			"cnzoi/Variant_Combat",
			"cnzoi/Variant_Combat/AI",
			"cnzoi/Variant_Combat/Animation",
			"cnzoi/Variant_Combat/Gameplay",
			"cnzoi/Variant_Combat/Interfaces",
			"cnzoi/Variant_Combat/UI",
			"cnzoi/Variant_SideScrolling",
			"cnzoi/Variant_SideScrolling/AI",
			"cnzoi/Variant_SideScrolling/Gameplay",
			"cnzoi/Variant_SideScrolling/Interfaces",
			"cnzoi/Variant_SideScrolling/UI"
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
