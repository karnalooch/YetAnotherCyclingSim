#pragma once

#include "CoreMinimal.h"
#include "Engine/HitResult.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "YacsBobLandscapeHit.generated.h"

class AActor;
class UPrimitiveComponent;

/** Native collision ownership; rejection never supplies a usable terrain height. */
USTRUCT(BlueprintType)
struct YACSBOBINSPECTION_API FYacsBobLandscapeHit
{
    GENERATED_BODY()

    // Accepted interpretation can still be an explicit miss; Status owns that distinction.
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") bool bAccepted = false;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FString Status = TEXT("REJECTED");
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FString Error;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") bool bBlockingHit = false;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FVector ImpactPoint = FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FString MapPackage;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FString ActorPath;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FString ActorClassPath;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FString ComponentPath;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") FString ComponentClassPath;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") TObjectPtr<AActor> HitActor = nullptr;
    UPROPERTY(BlueprintReadOnly, Category="YACS BOB Inspection") TObjectPtr<UPrimitiveComponent> HitComponent = nullptr;
};

/** Internal fixed-domain bridge. These functions are never MCP tool definitions. */
UCLASS()
class YACSBOBINSPECTION_API UYacsBobLandscapeHitLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category="YACS BOB Inspection")
    static FYacsBobLandscapeHit InspectAcceptedCheckpointIdentity();

    UFUNCTION(BlueprintCallable, Category="YACS BOB Inspection")
    static FYacsBobLandscapeHit InspectAcceptedLandscapeHit(const FHitResult& HitResult);
};
