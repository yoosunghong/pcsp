#include "PCSPPersonaCache.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"

bool UPCSPPersonaCache::LoadFromFile(const FString& AbsPath)
{
	bLoaded = false;
	Embeddings.Reset();

	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *AbsPath))
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPersonaCache: cannot read %s"), *AbsPath);
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPersonaCache: JSON parse failed for %s"), *AbsPath);
		return false;
	}

	CachedPersonaDim = Root->GetIntegerField(TEXT("persona_dim"));
	CachedObsDim     = Root->GetIntegerField(TEXT("obs_dim"));
	CachedNumActions = Root->GetIntegerField(TEXT("n_actions"));
	const int32 N   = Root->GetIntegerField(TEXT("n_personas"));

	const TArray<TSharedPtr<FJsonValue>>* EmbArray;
	if (!Root->TryGetArrayField(TEXT("embeddings"), EmbArray))
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPersonaCache: missing 'embeddings' array"));
		return false;
	}

	Embeddings.Reserve(N);
	for (const TSharedPtr<FJsonValue>& Row : *EmbArray)
	{
		const TArray<TSharedPtr<FJsonValue>>& FloatArr = Row->AsArray();
		TArray<float>& Vec = Embeddings.AddDefaulted_GetRef();
		Vec.Reserve(CachedPersonaDim);
		for (const TSharedPtr<FJsonValue>& V : FloatArr)
		{
			Vec.Add(static_cast<float>(V->AsNumber()));
		}
	}

	if (Embeddings.Num() != N)
	{
		UE_LOG(LogTemp, Error, TEXT("PCSPPersonaCache: expected %d rows, got %d"), N, Embeddings.Num());
		return false;
	}

	bLoaded = true;
	UE_LOG(LogTemp, Log, TEXT("PCSPPersonaCache: loaded %d personas, dim=%d from %s"),
		N, CachedPersonaDim, *AbsPath);
	return true;
}

TConstArrayView<float> UPCSPPersonaCache::GetEmbedding(int32 PersonaId) const
{
	const int32 Idx = PersonaId - 1;
	if (!bLoaded || !Embeddings.IsValidIndex(Idx)) { return {}; }
	return TConstArrayView<float>(Embeddings[Idx]);
}
