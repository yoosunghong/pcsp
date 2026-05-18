#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "PCSPPersonaComponent.generated.h"

UCLASS(ClassGroup=(PCSP), meta=(BlueprintSpawnableComponent))
class CNZOI_API UPCSPPersonaComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UPCSPPersonaComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Persona")
	FString PersonaId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="PCSP|Persona")
	FString PersonaText;

	// Projected persona vector (e.g., 64-d). Loaded from cache in Phase 3.
	UPROPERTY(BlueprintReadOnly, Category="PCSP|Persona")
	TArray<float> ProjectedVector;

	UFUNCTION(BlueprintCallable, Category="PCSP|Persona")
	void SetProjectedVector(const TArray<float>& In) { ProjectedVector = In; }

	UFUNCTION(BlueprintCallable, Category="PCSP|Persona")
	bool HasEmbedding() const { return ProjectedVector.Num() > 0; }

	// Returns PersonaId as an integer (1-based, as expected by PCSPPersonaCache).
	// Parses PersonaId FString; returns 1 on parse failure.
	UFUNCTION(BlueprintCallable, Category="PCSP|Persona")
	int32 GetPersonaId() const
	{
		int32 Id = FCString::Atoi(*PersonaId);
		return Id > 0 ? Id : 1;
	}
};
