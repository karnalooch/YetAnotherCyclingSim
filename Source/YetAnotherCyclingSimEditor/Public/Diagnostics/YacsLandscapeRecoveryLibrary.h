#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "YacsLandscapeRecoveryLibrary.generated.h"

class ALandscape;
class UWorld;

/** Bounded editor diagnostic for the existing 4033-square Passo Giau DTM. */
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsLandscapeRecoveryLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()
public:
	/** Import source heights into a new actor; no spline deformation or source-map save. */
	UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
	static ALandscape* ImportCleanBaseline(UWorld* World, const FString& HeightmapPath,
		const FVector& Scale, const FVector& Location);

	/** Compare every stored height sample to the supplied R16, without writing heights. */
	UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
	static FString VerifyBaselineHeights(ALandscape* Landscape, const FString& HeightmapPath);
};
