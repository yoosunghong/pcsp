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

bool UPCSPPersonaCache::LoadTextsFromFile(const FString& AbsPath)
{
	PersonaTexts.Reset();
	PersonaSubtitles.Reset();

	FString Raw;
	if (!FFileHelper::LoadFileToString(Raw, *AbsPath))
	{
		UE_LOG(LogTemp, Warning,
			TEXT("PCSPPersonaCache: persona text file not found at '%s'; the HUD will fall back to IDs."),
			*AbsPath);
		return false;
	}

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Raw);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		UE_LOG(LogTemp, Warning, TEXT("PCSPPersonaCache: could not parse '%s'."), *AbsPath);
		return false;
	}

	const TArray<TSharedPtr<FJsonValue>>* Personas = nullptr;
	if (!Root->TryGetArrayField(TEXT("personas"), Personas) || !Personas)
	{
		UE_LOG(LogTemp, Warning, TEXT("PCSPPersonaCache: '%s' has no personas array."), *AbsPath);
		return false;
	}

	// IDs are 1-based and may arrive unsorted, so size to the largest and place
	// each entry by ID rather than trusting array order.
	int32 MaxId = 0;
	for (const TSharedPtr<FJsonValue>& Value : *Personas)
	{
		const TSharedPtr<FJsonObject>* Entry = nullptr;
		if (Value.IsValid() && Value->TryGetObject(Entry) && Entry)
		{
			MaxId = FMath::Max(MaxId, static_cast<int32>((*Entry)->GetIntegerField(TEXT("id"))));
		}
	}
	if (MaxId <= 0) { return false; }
	PersonaTexts.SetNum(MaxId);
	PersonaSubtitles.SetNum(MaxId);

	int32 Loaded = 0;
	for (const TSharedPtr<FJsonValue>& Value : *Personas)
	{
		const TSharedPtr<FJsonObject>* Entry = nullptr;
		if (!Value.IsValid() || !Value->TryGetObject(Entry) || !Entry) { continue; }
		const int32 Id = (*Entry)->GetIntegerField(TEXT("id"));
		if (Id < 1 || Id > MaxId) { continue; }
		PersonaTexts[Id - 1] = (*Entry)->GetStringField(TEXT("text"));
		const FString Occupation = (*Entry)->HasField(TEXT("occupation"))
			? (*Entry)->GetStringField(TEXT("occupation")) : FString();
		const int32 Age = (*Entry)->HasField(TEXT("age"))
			? (*Entry)->GetIntegerField(TEXT("age")) : 0;
		PersonaSubtitles[Id - 1] = Age > 0 && !Occupation.IsEmpty()
			? FString::Printf(TEXT("%s, %d"), *Occupation, Age)
			: Occupation;
		++Loaded;
	}

	UE_LOG(LogTemp, Log, TEXT("PCSPPersonaCache: loaded %d persona texts from '%s'."),
		Loaded, *AbsPath);
	return Loaded > 0;
}

namespace
{
	// Returned by reference when a persona ID has no entry.
	static const FString EmptyPersonaField;
}

const FString& UPCSPPersonaCache::GetPersonaText(const int32 PersonaId) const
{
	return PersonaTexts.IsValidIndex(PersonaId - 1)
		? PersonaTexts[PersonaId - 1] : EmptyPersonaField;
}

const FString& UPCSPPersonaCache::GetPersonaSubtitle(const int32 PersonaId) const
{
	return PersonaSubtitles.IsValidIndex(PersonaId - 1)
		? PersonaSubtitles[PersonaId - 1] : EmptyPersonaField;
}
