// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;
using System.IO;

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
			"Slate",
			"NNE",
			"Json",
			"JsonUtilities",
			"MassEntity",
			"MassCommon",
			"MassSpawner",
			"MassSimulation"
		});

		// UE 5.8 split the foundational Mass reflected types out of MassEntity.
		// Keep the version guard explicit for future engine migration checks.
		if (Target.Version.MajorVersion > 5 || Target.Version.MinorVersion >= 8)
		{
			PublicDependencyModuleNames.Add("MassCore");
		}

		PrivateDependencyModuleNames.AddRange(new string[] { });

		PublicIncludePaths.AddRange(new string[] {
			"cnzoi",
			Path.Combine(ModuleDirectory, "PCSP/Public"),
			Path.Combine(ModuleDirectory, "PCSP/Public/Components"),
			Path.Combine(ModuleDirectory, "PCSP/Public/Affordance"),
			Path.Combine(ModuleDirectory, "PCSP/Public/Agent"),
			Path.Combine(ModuleDirectory, "PCSP/Public/Sim"),
			Path.Combine(ModuleDirectory, "PCSP/Public/BT"),
			Path.Combine(ModuleDirectory, "PCSP/Public/Inference"),
			Path.Combine(ModuleDirectory, "PCSP/Public/Mass"),
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

		PrivateIncludePaths.AddRange(new string[] {
			Path.Combine(ModuleDirectory, "PCSP/Private"),
			Path.Combine(ModuleDirectory, "PCSP/Private/Components"),
			Path.Combine(ModuleDirectory, "PCSP/Private/Affordance"),
			Path.Combine(ModuleDirectory, "PCSP/Private/Agent"),
			Path.Combine(ModuleDirectory, "PCSP/Private/Sim"),
			Path.Combine(ModuleDirectory, "PCSP/Private/BT"),
			Path.Combine(ModuleDirectory, "PCSP/Private/Inference"),
			Path.Combine(ModuleDirectory, "PCSP/Private/Mass")
		});

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });

		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
