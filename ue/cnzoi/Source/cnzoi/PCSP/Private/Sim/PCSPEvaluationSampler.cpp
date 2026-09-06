#include "Sim/PCSPPerfSamplerSubsystem.h"
#include "Components/PCSPTrajectoryLogComponent.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
#include "UnrealClient.h"
#include "EngineUtils.h"
#include "Mass/PCSPMassSpawner.h"
#include "Agent/PCSPAgentCharacter.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Containers/Ticker.h"
#include "TimerManager.h"

void UPCSPPerfSamplerSubsystem::BeginEvaluation()
{
	auto* Eval = GetWorld()->GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>();
	if (!Eval || !Eval->bConfigured) { return; }
	Eval->ApplyPolicySettings();
	EvaluationResult.Axis = Eval->Axis;
	EvaluationResult.Variant = Eval->Variant;
	EvaluationResult.Count = Eval->Count;
	EvaluationResult.Seed = Eval->Seed;
	EvaluationResult.Series = Eval->Series;
	EvaluationResult.Run = ++Eval->NextRun;
	const FString Dir = FPaths::ProjectSavedDir() / TEXT("PCSP/Evaluation") / Eval->Series;
	IFileManager::Get().MakeDirectory(*Dir, true);
	EvaluationResult.CSV = Dir / FString::Printf(TEXT("run_%03d_axis%d_variant%d.csv"), EvaluationResult.Run, Eval->Axis, Eval->Variant);
	UPCSPTrajectoryLogComponent::SetEvaluationSessionDir(Dir / FString::Printf(TEXT("run_%03d_trajectories"), EvaluationResult.Run));
	bComparisonWriteError |= !FFileHelper::SaveStringToFile(
		TEXT("elapsed_s,window_s,frames,process_cpu_pct,fps,decisions,policy_us_total,latency_us_total,failures\n"), *EvaluationResult.CSV);
	bEvaluationActive = true;
	Eval->Status = TEXT("Waiting for the full population and navigation...");
	Eval->SaveResult(EvaluationResult);
}

void UPCSPPerfSamplerSubsystem::TickEvaluation(double Now)
{
	if (!bEvaluationActive) { return; }
	auto* Eval = GetWorld()->GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>();
	if (!Eval) { return; }
	if (Eval->PolicyMode() != EPCSPPolicyMode::BTOnly && !GetWorld()->GetSubsystem<UPCSPPolicySubsystem>()->IsReady())
	{
		EvaluationResult.InvalidReason = TEXT("PCSP model is unavailable");
		FinishEvaluation(false);
		return;
	}
	if (!Eval->bConfigured || Eval->Series != EvaluationResult.Series)
	{
		EvaluationResult.InvalidReason = TEXT("Evaluation setup changed during recording");
		FinishEvaluation(false);
		return;
	}
	if (!bEvaluationCameraSet)
	{
		if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
		{
			if (!Eval->bHasCamera)
			{
				PC->GetPlayerViewPoint(Eval->CameraLocation, Eval->CameraRotation);
				Eval->bHasCamera = true;
			}
			ACameraActor* Camera = GetWorld()->SpawnActor<ACameraActor>(Eval->CameraLocation, Eval->CameraRotation);
			if (Camera)
			{
				Camera->GetCameraComponent()->SetFieldOfView(Eval->CameraFOV);
				PC->SetViewTarget(Camera);
				EvaluationCamera = Camera;
				bEvaluationCameraSet = true;
			}
		}
	}
	int32 Actors = 0, Mass = 0;
	for (TActorIterator<APCSPMassSpawner> It(GetWorld()); It; ++It) { Mass += It->GetSpawnedEntityCount(); }
	for (TActorIterator<APCSPAgentCharacter> It(GetWorld()); It; ++It) { if (!It->IsPlayerControlled()) { ++Actors; } }
	const bool bActor = EvaluationResult.Axis == 1 && EvaluationResult.Variant == 0;
	const bool bPopulationReady = bActor ? Actors == EvaluationResult.Count && Mass == 0 : Mass == EvaluationResult.Count && Actors == 0;
	if (!bPopulationReady)
	{
		if (bEvaluationStarted) { EvaluationResult.InvalidReason = TEXT("Population changed"); FinishEvaluation(false); }
		else { EvaluationReadyAt = 0; Eval->Status = FString::Printf(TEXT("Waiting for NPCs: %d / %d"), Actors + Mass, EvaluationResult.Count); }
		return;
	}
	if (EvaluationReadyAt == 0) { EvaluationReadyAt = Now + Eval->WarmupSeconds; }
	if (Now < EvaluationReadyAt) { Eval->Status = FString::Printf(TEXT("Warm-up %.1fs / excluded"), EvaluationReadyAt - Now); return; }
	FIntPoint Size = FIntPoint::ZeroValue;
	if (auto* Viewport = GetWorld()->GetGameViewport(); Viewport && Viewport->Viewport) { Size = Viewport->Viewport->GetSizeXY(); }
	const int32 VSync = IConsoleManager::Get().FindConsoleVariable(TEXT("r.VSync"))->GetInt();
	const float Cap = IConsoleManager::Get().FindConsoleVariable(TEXT("t.MaxFPS"))->GetFloat();
	if (!bEvaluationStarted)
	{
		bEvaluationStarted = true;
		EvaluationLastTick = EvaluationWindowStart = Now;
		EvaluationLastCPU = EvaluationWindowCPU = ReadProcessCPUSeconds();
		EvaluationResolution = Size;
		EvaluationVSync = VSync;
		EvaluationCap = Cap;
		EvaluationResult.Context = FString::Printf(TEXT("%s|%dx%d|vsync%d|cap%.1f|%s|%s|fov%.1f"),
			*GetWorld()->GetMapName(), Size.X, Size.Y, VSync, Cap, *Eval->CameraLocation.ToString(), *Eval->CameraRotation.ToString(), Eval->CameraFOV);
		for (int32 I = 0; I < Eval->VariantCount(); ++I)
		{
			if (const auto* Previous = Eval->Latest(I); Previous && !Previous->Context.IsEmpty() && Previous->Context != EvaluationResult.Context)
			{
				EvaluationResult.InvalidReason = TEXT("Comparison context differs; change count/seed to start a new series");
				FinishEvaluation(false);
				return;
			}
		}
		return;
	}
	if (Size != EvaluationResolution || VSync != EvaluationVSync || Cap != EvaluationCap
		|| UPCSPPolicySubsystem::GetPolicyMode() != Eval->PolicyMode()
		|| IConsoleManager::Get().FindConsoleVariable(TEXT("pcsp.AsyncInference"))->GetInt() != Eval->AsyncMode()
		|| (GetWorld()->GetFirstPlayerController() && GetWorld()->GetFirstPlayerController()->GetViewTarget() != EvaluationCamera.Get()))
	{
		EvaluationResult.InvalidReason = TEXT("Camera, resolution, frame limit or policy changed");
		FinishEvaluation(false);
		return;
	}
	const double Delta = Now - EvaluationLastTick;
	EvaluationResult.Seconds += Delta;
	EvaluationResult.FrameTimes.Add(Delta * 1000.0);
	++EvaluationResult.Frames;
	EvaluationLastTick = Now;
	if (Now - EvaluationWindowStart >= 1.0 || EvaluationResult.Seconds >= Eval->DurationSeconds)
	{
		const double CPU = ReadProcessCPUSeconds();
		const double Window = Now - EvaluationWindowStart;
		const int32 Frames = EvaluationResult.Frames - EvaluationWindowFrames;
		const auto Point = MakePoint(EvaluationResult.Seconds, Window, Frames,
			CPU >= 0 && EvaluationWindowCPU >= 0 ? CPU - EvaluationWindowCPU : -1, FPlatformMisc::NumberOfCoresIncludingHyperthreads());
		if (Point.CPU >= 0) { EvaluationResult.CPUIntegral += Point.CPU * Window; EvaluationResult.CPUSeconds += Window; }
		EvaluationResult.Plot.Add(FVector(EvaluationResult.Seconds, Point.CPU, Point.FPS));
		const FString Row = FString::Printf(TEXT("%.6f,%.6f,%d,%.6f,%.6f,%lld,%.3f,%.3f,%lld\n"),
			EvaluationResult.Seconds, Window, Frames, Point.CPU, Point.FPS, EvaluationResult.Decisions,
			EvaluationResult.PolicyMicros, EvaluationResult.LatencyMicros, EvaluationResult.Failures);
		bComparisonWriteError |= !FFileHelper::SaveStringToFile(Row, *EvaluationResult.CSV,
			FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_Append | FILEWRITE_AllowRead);
		EvaluationWindowStart = Now;
		EvaluationWindowCPU = CPU;
		EvaluationWindowFrames = EvaluationResult.Frames;
		Eval->SaveResult(EvaluationResult);
	}
	Eval->Status = FString::Printf(TEXT("Recording %.1f / %.0fs"), EvaluationResult.Seconds, Eval->DurationSeconds);
	if (EvaluationResult.Seconds >= Eval->DurationSeconds) { FinishEvaluation(true); }
}

void UPCSPPerfSamplerSubsystem::RecordPolicyDecision(int32 PersonaId, EPCSPActionType Action, double ServiceMicros, double LatencyMicros, bool bWorker)
{
	if (!bEvaluationActive || !bEvaluationStarted) { return; }
	++EvaluationResult.Decisions;
	if (bWorker) { ++EvaluationResult.WorkerDecisions; }
	EvaluationResult.PolicyMicros += ServiceMicros;
	EvaluationResult.LatencyMicros += LatencyMicros;
	if (Action == EPCSPActionType::None) { ++EvaluationResult.Failures; return; }
	++EvaluationResult.Actions.FindOrAdd(static_cast<int32>(Action));
	++EvaluationResult.PersonaActions.FindOrAdd(PersonaId).FindOrAdd(static_cast<int32>(Action));
}

void UPCSPPerfSamplerSubsystem::FinishEvaluation(bool bComplete)
{
	if (!bEvaluationActive) { return; }
	bEvaluationActive = false;
	EvaluationResult.bComplete = bComplete;
	if (!bComplete && EvaluationResult.InvalidReason.IsEmpty()) { EvaluationResult.InvalidReason = TEXT("Stopped before the recording duration"); }
	if (auto* Eval = GetWorld()->GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>())
	{
		Eval->SaveResult(EvaluationResult);
		Eval->Status = bComplete ? TEXT("Complete / select another variant to restart and compare") : EvaluationResult.InvalidReason;
	}
	WriteEvaluationSummary();
	if (bComplete)
	{
		if (EvaluationResult.Axis == 2 && EvaluationResult.Variant == 0 && FParse::Param(FCommandLine::Get(), TEXT("PCSP_EvalReplay")))
		{
			const FString Replay = GetWorld()->GetSubsystem<UPCSPPolicySubsystem>()->RunFixedInputReplay();
			GetWorld()->GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>()->ReplayStatus = Replay;
			UE_LOG(LogTemp, Display, TEXT("PCSPEvaluation: %s"), *Replay);
		}
		FScreenshotRequest::RequestScreenshot(FPaths::ChangeExtension(EvaluationResult.CSV, TEXT("png")), true, false);
		auto* Eval = GetWorld()->GetGameInstance()->GetSubsystem<UPCSPEvaluationSubsystem>();
		if (FParse::Param(FCommandLine::Get(), TEXT("PCSP_EvalTravelSmoke")) && Eval->Variant + 1 < Eval->VariantCount())
		{
			FTimerHandle Handle;
			GetWorld()->GetTimerManager().SetTimer(Handle, FTimerDelegate::CreateWeakLambda(Eval,
				[Eval]() { Eval->StartVariant(Eval->Variant + 1); }), 2.f, false);
		}
		else if (FParse::Param(FCommandLine::Get(), TEXT("PCSP_EvalAutoQuit")))
		{
			FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float)
				{ FPlatformMisc::RequestExit(false); return false; }), 2.f);
		}
	}
	UE_LOG(LogTemp, Display, TEXT("PCSPEvaluation: %s axis=%d variant=%d count=%d frames=%lld decisions=%lld csv=%s"),
		bComplete ? TEXT("COMPLETE") : TEXT("INCOMPLETE"), EvaluationResult.Axis, EvaluationResult.Variant, EvaluationResult.Count,
		EvaluationResult.Frames, EvaluationResult.Decisions, *EvaluationResult.CSV);
}

void UPCSPPerfSamplerSubsystem::WriteEvaluationSummary()
{
	const auto& R = EvaluationResult;
	TSharedRef<FJsonObject> Json = MakeShared<FJsonObject>();
	Json->SetNumberField(TEXT("schema_version"), 1);
	Json->SetNumberField(TEXT("axis"), R.Axis);
	Json->SetNumberField(TEXT("variant"), R.Variant);
	Json->SetStringField(TEXT("variant_name"), UPCSPEvaluationSubsystem::VariantName(R.Axis, R.Variant));
	Json->SetStringField(TEXT("series"), R.Series);
	Json->SetStringField(TEXT("context"), R.Context);
	Json->SetNumberField(TEXT("run"), R.Run);
	Json->SetNumberField(TEXT("npc_count"), R.Count);
	Json->SetNumberField(TEXT("seed"), R.Seed);
	Json->SetBoolField(TEXT("complete"), R.bComplete);
	Json->SetStringField(TEXT("invalid_reason"), R.InvalidReason);
	Json->SetStringField(TEXT("map"), GetWorld()->GetMapName());
	Json->SetStringField(TEXT("world_type"), GetWorld()->WorldType == EWorldType::PIE ? TEXT("PIE") : TEXT("Game"));
	Json->SetNumberField(TEXT("width"), EvaluationResolution.X);
	Json->SetNumberField(TEXT("height"), EvaluationResolution.Y);
	Json->SetNumberField(TEXT("vsync"), EvaluationVSync);
	Json->SetNumberField(TEXT("fps_cap"), EvaluationCap);
	Json->SetNumberField(TEXT("seconds"), R.Seconds);
	Json->SetNumberField(TEXT("frames"), R.Frames);
	Json->SetNumberField(TEXT("cpu_pct"), R.CPU());
	Json->SetNumberField(TEXT("fps"), R.FPS());
	Json->SetNumberField(TEXT("p95_frame_ms"), R.P95());
	Json->SetNumberField(TEXT("decisions"), R.Decisions);
	Json->SetNumberField(TEXT("worker_decisions"), R.WorkerDecisions);
	Json->SetNumberField(TEXT("sync_decisions"), R.Decisions - R.WorkerDecisions);
	Json->SetNumberField(TEXT("policy_us_total"), R.PolicyMicros);
	Json->SetNumberField(TEXT("latency_us_total"), R.LatencyMicros);
	Json->SetNumberField(TEXT("inference_failures"), R.Failures);
	Json->SetNumberField(TEXT("action_entropy_bits"), R.Entropy());
	Json->SetStringField(TEXT("quality_note"), TEXT("Decision histograms are descriptive; entropy alone is not persona fidelity or completed behavior."));
	Json->SetStringField(TEXT("comparison_scope"), R.Axis == 1
		? TEXT("Whole execution stacks; representation, spawn placement, movement and interaction semantics differ. Not isolated BT overhead.")
		: R.Axis == 2 ? TEXT("End-to-end live inference scheduling; observations may diverge. Use fixed-input replay for kernel-only claims.")
		: TEXT("Same Mass execution; different action selectors. Evaluate persona fidelity from trajectories separately."));
	TSharedRef<FJsonObject> Personas = MakeShared<FJsonObject>();
	for (const auto& Persona : R.PersonaActions)
	{
		TSharedRef<FJsonObject> Actions = MakeShared<FJsonObject>();
		for (const auto& Action : Persona.Value) { Actions->SetNumberField(FString::FromInt(Action.Key), Action.Value); }
		Personas->SetObjectField(FString::FromInt(Persona.Key), Actions);
	}
	Json->SetObjectField(TEXT("persona_action_counts"), Personas);
	FString Output;
	FJsonSerializer::Serialize(Json, TJsonWriterFactory<>::Create(&Output));
	bComparisonWriteError |= !FFileHelper::SaveStringToFile(Output, *FPaths::ChangeExtension(R.CSV, TEXT("json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}
