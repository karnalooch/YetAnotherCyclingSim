#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "YacsTextureAuditLibrary.generated.h"

class UTexture2D;
class UActorComponent;
class UMaterialInterface;

/** Editor-only native rendering metadata absent from the Python reflection API. */
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsTextureAuditLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Read derived format/residency without changing source pixels or saving assets. */
	UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
	static FString DescribeTexture(UTexture2D* Texture);

	/** Read Landscape render-instance parents absent from Python editor properties. */
	UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
	static FString DescribeLandscapeMaterialInstances(UActorComponent* Component, UMaterialInterface* ExpectedMaterial);

	/** Finish only the explicitly selected texture builds; never change source art. */
	UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
	static bool FinishTextureCompilation(const TArray<UTexture2D*>& Textures);

	/**
	 * Drain all in-flight asset and shader compilation, then run full GC.
	 * Returns a JSON receipt with shader-job/worker memory so Python proofs can
	 * distinguish retained material memory from external compile-worker memory.
	 */
	UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
	static FString DrainAssetCompilationAndCollectGarbage();
};
