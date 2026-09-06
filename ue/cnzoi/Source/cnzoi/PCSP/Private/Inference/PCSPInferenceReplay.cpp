#include "Inference/PCSPPolicySubsystem.h"
#include "Inference/PCSPPersonaCache.h"
#include "Async/Async.h"
#include "HAL/PlatformTime.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

FString UPCSPPolicySubsystem::RunFixedInputReplay()
{
	if (!bReady || ReplayInputs.IsEmpty() || AsyncBatchFuture.IsValid())
	{
		return TEXT("Replay unavailable: collect PCSP decisions first; retry when the worker is idle.");
	}
	const int32 N = ReplayInputs.Num();
	TArray<float> Obs, Personas, Individual, Batched;
	Obs.SetNumZeroed(N * ObsDim); Personas.SetNumZeroed(N * PersonaDim);
	Individual.SetNumZeroed(N * NActions); Batched.SetNumZeroed(N * NActions);
	for (int32 I = 0; I < N; ++I)
	{
		const auto& Input = ReplayInputs[I];
		FMemory::Memcpy(Obs.GetData() + I * ObsDim, Input.Observation.GetData(), FMath::Min(ObsDim, Input.Observation.Num()) * sizeof(float));
		const auto Embedding = PersonaCache->GetEmbedding(Input.PersonaId);
		if (Embedding.Num() != PersonaDim) { return TEXT("Replay failed: invalid persona."); }
		FMemory::Memcpy(Personas.GetData() + I * PersonaDim, Embedding.GetData(), PersonaDim * sizeof(float));
	}
	bool bOK = true;
	auto Sync = [&]()
	{
		const double Start = FPlatformTime::Seconds();
		for (int32 I = 0; I < N; ++I)
		{
			TArray<UE::NNE::FTensorBindingCPU> Inputs = {{Obs.GetData() + I * ObsDim, ObsDim * sizeof(float)}, {Personas.GetData() + I * PersonaDim, PersonaDim * sizeof(float)}};
			TArray<UE::NNE::FTensorBindingCPU> Outputs = {{Individual.GetData() + I * NActions, NActions * sizeof(float)}};
			bOK &= ModelInstance->RunSync(Inputs, Outputs) == UE::NNE::EResultStatus::Ok;
		}
		return (FPlatformTime::Seconds() - Start) * 1.e6;
	};
	auto Batch = [&]()
	{
		return Async(EAsyncExecution::ThreadPool, [&]()
		{
			const double Start = FPlatformTime::Seconds();
			TArray<UE::NNE::FTensorShape> Shapes = {UE::NNE::FTensorShape::Make({static_cast<uint32>(N), static_cast<uint32>(ObsDim)}), UE::NNE::FTensorShape::Make({static_cast<uint32>(N), static_cast<uint32>(PersonaDim)})};
			bOK &= AsyncModelInstance->SetInputTensorShapes(Shapes) == UE::NNE::EResultStatus::Ok;
			TArray<UE::NNE::FTensorBindingCPU> Inputs = {{Obs.GetData(), static_cast<uint64>(Obs.Num() * sizeof(float))}, {Personas.GetData(), static_cast<uint64>(Personas.Num() * sizeof(float))}};
			TArray<UE::NNE::FTensorBindingCPU> Outputs = {{Batched.GetData(), static_cast<uint64>(Batched.Num() * sizeof(float))}};
			bOK &= AsyncModelInstance->RunSync(Inputs, Outputs) == UE::NNE::EResultStatus::Ok;
			return (FPlatformTime::Seconds() - Start) * 1.e6;
		}).Get();
	};
	Sync(); Batch(); // warm both models, excluded
	double SyncUs = 0, BatchUs = 0;
	for (int32 I = 0; I < 6; ++I)
	{
		if (I % 2 == 0) { SyncUs += Sync(); BatchUs += Batch(); }
		else { BatchUs += Batch(); SyncUs += Sync(); }
	}
	float MaxError = 0;
	for (int32 I = 0; I < Individual.Num(); ++I)
	{
		if (!FMath::IsFinite(Individual[I]) || !FMath::IsFinite(Batched[I])) { bOK = false; }
		MaxError = FMath::Max(MaxError, FMath::Abs(Individual[I] - Batched[I]));
	}
	if (!bOK || MaxError > 0.001f) { return TEXT("Replay failed: inference error or logits differ beyond 0.001."); }
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetStringField(TEXT("scope"), TEXT("Identical captured inputs; six alternating repetitions after warmup. Worker time excludes dispatch/wait. Not an FPS benchmark."));
	Root->SetNumberField(TEXT("requests_per_repeat"), N);
	Root->SetNumberField(TEXT("repeats"), 6);
	Root->SetNumberField(TEXT("sync_us_per_request"), SyncUs / (6 * N));
	Root->SetNumberField(TEXT("worker_us_per_request"), BatchUs / (6 * N));
	Root->SetNumberField(TEXT("max_abs_logit_error"), MaxError);
	TArray<TSharedPtr<FJsonValue>> Fixture;
	for (const auto& Input : ReplayInputs)
	{
		TSharedRef<FJsonObject> Row = MakeShared<FJsonObject>();
		Row->SetNumberField(TEXT("persona_id"), Input.PersonaId);
		TArray<TSharedPtr<FJsonValue>> Values;
		for (float Value : Input.Observation) { Values.Add(MakeShared<FJsonValueNumber>(Value)); }
		Row->SetArrayField(TEXT("observation"), Values);
		Fixture.Add(MakeShared<FJsonValueObject>(Row));
	}
	Root->SetArrayField(TEXT("inputs"), Fixture);
	const FString Dir = FPaths::ProjectSavedDir() / TEXT("PCSP/Evaluation");
	IFileManager::Get().MakeDirectory(*Dir, true);
	const FString Path = Dir / (TEXT("fixed_input_") + FGuid::NewGuid().ToString(EGuidFormats::Digits) + TEXT(".json"));
	FString Json; FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Json));
	if (!FFileHelper::SaveStringToFile(Json, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)) { return TEXT("Replay JSON write failed."); }
	return FString::Printf(TEXT("Replay: sync %.1f / worker %.1f us/request | %d inputs x 6 | logits match | JSON saved"), SyncUs / (6 * N), BatchUs / (6 * N), N);
}
