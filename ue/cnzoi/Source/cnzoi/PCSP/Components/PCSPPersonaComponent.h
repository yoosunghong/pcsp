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
};
