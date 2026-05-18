#include "PCSPTrajectoryLogComponent.h"
#include "PCSPNeedsComponent.h"
#include "PCSPPersonaComponent.h"
#include "PCSPPolicySubsystem.h"
#include "GameFramework/Actor.h"
#include "Engine/World.h"
#include "TimerManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/DateTime.h"
#include "HAL/FileManager.h"
#include "UObject/Class.h"

namespace
{
	const TCHAR* EventName(EPCSPTrajectoryEvent E)
	{
		switch (E)
		{
		case EPCSPTrajectoryEvent::Decision:            return TEXT("decision");
		case EPCSPTrajectoryEvent::InteractionComplete: return TEXT("interaction_complete");
		case EPCSPTrajectoryEvent::InteractionFailed:   return TEXT("interaction_failed");
		case EPCSPTrajectoryEvent::MoveFailed:          return TEXT("move_failed");
		}
		return TEXT("unknown");
	}

	FString ActionName(EPCSPActionType A)
	{
		const UEnum* E = StaticEnum<EPCSPActionType>();
		return E ? E->GetNameStringByValue(static_cast<int64>(A)) : FString::FromInt((int32)A);
	}

	FString CategoryName(EPCSPAffordanceCategory C)
	{
		const UEnum* E = StaticEnum<EPCSPAffordanceCategory>();
		return E ? E->GetNameStringByValue(static_cast<int64>(C)) : FString::FromInt((int32)C);
	}
}

UPCSPTrajectoryLogComponent::UPCSPTrajectoryLogComponent()
{
	PrimaryComponentTick.bCanEverTick = false;
}

FString UPCSPTrajectoryLogComponent::GetSessionDir()
{
	static FString Dir;
	if (Dir.IsEmpty())
	{
		const FString Stamp = FDateTime::Now().ToString(TEXT("%Y%m%d_%H%M%S"));
		Dir = FPaths::ProjectSavedDir() / TEXT("PCSP/Logs") / Stamp;
		IFileManager::Get().MakeDirectory(*Dir, /*Tree=*/true);
		UE_LOG(LogTemp, Log, TEXT("PCSPTrajectoryLog: session dir = %s"), *Dir);
	}
	return Dir;
}

void UPCSPTrajectoryLogComponent::BeginPlay()
{
	Super::BeginPlay();

	const UPCSPPersonaComponent* Persona = GetPersona();
	const int32 PersonaId = Persona ? Persona->GetPersonaId() : 0;
	const FString ActorName = GetOwner() ? GetOwner()->GetName() : TEXT("unknown");
	LogFilePath = GetSessionDir() / FString::Printf(TEXT("agent_p%03d_%s.jsonl"),
	                                                PersonaId, *ActorName);

	// Header line — one per file. PersonaText is intentionally omitted to avoid
	// JSON-escaping complexity; downstream tooling can join on persona_id.
	const FString ModeName = UPCSPPolicySubsystem::PolicyModeName(
		UPCSPPolicySubsystem::GetPolicyMode());
	const FString Header = FString::Printf(
		TEXT("{\"event\":\"session_start\",\"persona_id\":%d,\"actor\":\"%s\",\"t\":%.3f,\"policy_mode\":\"%s\"}"),
		PersonaId, *ActorName,
		GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f,
		*ModeName);
	AppendLine(Header);

	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().SetTimer(FlushTimerHandle, this,
			&UPCSPTrajectoryLogComponent::Flush,
			FMath::Max(1.f, PeriodicFlushSeconds), /*bLoop=*/true);
	}
}

void UPCSPTrajectoryLogComponent::EndPlay(const EEndPlayReason::Type Reason)
{
	if (UWorld* World = GetWorld())
	{
		World->GetTimerManager().ClearTimer(FlushTimerHandle);
	}
	const FString Footer = FString::Printf(
		TEXT("{\"event\":\"session_end\",\"t\":%.3f,\"reason\":%d}"),
		GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f, (int32)Reason);
	AppendLine(Footer);
	Flush();
	Super::EndPlay(Reason);
}

UPCSPNeedsComponent* UPCSPTrajectoryLogComponent::GetNeeds() const
{
	return GetOwner() ? GetOwner()->FindComponentByClass<UPCSPNeedsComponent>() : nullptr;
}

UPCSPPersonaComponent* UPCSPTrajectoryLogComponent::GetPersona() const
{
	return GetOwner() ? GetOwner()->FindComponentByClass<UPCSPPersonaComponent>() : nullptr;
}

void UPCSPTrajectoryLogComponent::AppendLine(const FString& JsonLine)
{
	PendingLines.Add(JsonLine);
}

void UPCSPTrajectoryLogComponent::Flush()
{
	if (PendingLines.Num() == 0 || LogFilePath.IsEmpty()) { return; }

	FString Blob;
	for (const FString& L : PendingLines) { Blob += L; Blob += TEXT("\n"); }

	const uint32 Flags = FILEWRITE_Append | FILEWRITE_AllowRead;
	if (!FFileHelper::SaveStringToFile(Blob, *LogFilePath,
		FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
		&IFileManager::Get(), Flags))
	{
		UE_LOG(LogTemp, Warning, TEXT("PCSPTrajectoryLog: failed to write %s"), *LogFilePath);
		return;
	}
	PendingLines.Reset();
}

void UPCSPTrajectoryLogComponent::EmitEvent(EPCSPTrajectoryEvent Event,
	EPCSPActionType Action, FGameplayTag Affordance, float Reward,
	EPCSPAffordanceCategory Category, float UrgencyScore, const FString& ExtraField)
{
	const float    T   = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.f;
	const FVector  Pos = GetOwner() ? GetOwner()->GetActorLocation() : FVector::ZeroVector;
	const UPCSPPersonaComponent* Persona = GetPersona();
	const int32 PersonaId = Persona ? Persona->GetPersonaId() : 0;

	// Needs snapshot (8 floats) — mirrors EPCSPNeed order
	FString NeedsBlob = TEXT("[");
	if (const UPCSPNeedsComponent* N = GetNeeds())
	{
		const int32 Count = N->Values.Num();
		for (int32 i = 0; i < Count; ++i)
		{
			NeedsBlob += FString::Printf(TEXT("%s%.3f"), i == 0 ? TEXT("") : TEXT(","), N->Values[i]);
		}
	}
	NeedsBlob += TEXT("]");

	FString Line = FString::Printf(
		TEXT("{\"t\":%.3f,\"persona_id\":%d,\"event\":\"%s\","
		     "\"pos\":[%.1f,%.1f],\"action\":\"%s\",\"affordance\":\"%s\","
		     "\"category\":\"%s\",\"urgency\":%.3f,\"reward\":%.3f,\"needs\":%s"),
		T, PersonaId, EventName(Event),
		Pos.X, Pos.Y, *ActionName(Action), *Affordance.ToString(),
		*CategoryName(Category), UrgencyScore, Reward, *NeedsBlob);

	if (!ExtraField.IsEmpty()) { Line += TEXT(","); Line += ExtraField; }
	Line += TEXT("}");

	AppendLine(Line);

	// Keep the in-memory mirror as well (for runtime queries / Blueprint debug).
	FPCSPTrajectoryEntry E;
	E.TimeSeconds = T;
	E.Location    = Pos;
	E.Action      = Action;
	E.Affordance  = Affordance;
	E.Reward      = Reward;
	Entries.Add(MoveTemp(E));
}

void UPCSPTrajectoryLogComponent::RecordDecision(EPCSPActionType Action, float UrgencyScore)
{
	EmitEvent(EPCSPTrajectoryEvent::Decision, Action, FGameplayTag(), 0.f,
	          EPCSPAffordanceCategory::None, UrgencyScore, FString());
}

void UPCSPTrajectoryLogComponent::RecordDecisionWithLogits(EPCSPActionType Action,
	float UrgencyScore, TArrayView<const float> Logits)
{
	FString Extra;
	if (Logits.Num() > 0)
	{
		Extra = TEXT("\"logits\":[");
		for (int32 i = 0; i < Logits.Num(); ++i)
		{
			Extra += FString::Printf(TEXT("%s%.4f"), i == 0 ? TEXT("") : TEXT(","), Logits[i]);
		}
		Extra += TEXT("]");
	}
	EmitEvent(EPCSPTrajectoryEvent::Decision, Action, FGameplayTag(), 0.f,
	          EPCSPAffordanceCategory::None, UrgencyScore, Extra);
}

void UPCSPTrajectoryLogComponent::RecordInteractionComplete(EPCSPActionType Action,
	FGameplayTag Affordance, EPCSPAffordanceCategory Category, float Reward)
{
	EmitEvent(EPCSPTrajectoryEvent::InteractionComplete, Action, Affordance, Reward,
	          Category, 0.f, FString());
}

void UPCSPTrajectoryLogComponent::RecordInteractionFailed(EPCSPActionType Action,
	FGameplayTag Affordance, const FString& Reason)
{
	const FString Extra = FString::Printf(TEXT("\"reason\":\"%s\""), *Reason);
	EmitEvent(EPCSPTrajectoryEvent::InteractionFailed, Action, Affordance, 0.f,
	          EPCSPAffordanceCategory::None, 0.f, Extra);
}

void UPCSPTrajectoryLogComponent::RecordMoveFailed(EPCSPActionType Action, int32 RetryCount,
	const FString& FailureReason, FGameplayTag IntendedZoneTag, float DistanceToTarget)
{
	// JSON-escape just the characters that can appear in our reason strings.
	FString SafeReason = FailureReason;
	SafeReason.ReplaceInline(TEXT("\\"), TEXT("\\\\"));
	SafeReason.ReplaceInline(TEXT("\""), TEXT("\\\""));

	FString Extra = FString::Printf(
		TEXT("\"retry_count\":%d,\"failure_reason\":\"%s\""),
		RetryCount, *SafeReason);

	if (IntendedZoneTag.IsValid())
	{
		Extra += FString::Printf(TEXT(",\"intended_zone\":\"%s\""), *IntendedZoneTag.ToString());
	}
	if (DistanceToTarget >= 0.f)
	{
		Extra += FString::Printf(TEXT(",\"distance_to_target\":%.1f"), DistanceToTarget);
	}

	EmitEvent(EPCSPTrajectoryEvent::MoveFailed, Action, FGameplayTag(), 0.f,
	          EPCSPAffordanceCategory::None, 0.f, Extra);
}
