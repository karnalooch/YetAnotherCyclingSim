#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Kismet/BlueprintFunctionLibrary.h"
#include "CyclingLandscapeEarthworksLibrary.generated.h"

class ALandscape;

/**
 * Editor-only bounded Landscape earthworks helpers used by YACS proof tooling.
 *
 * These functions never save a map. The caller must independently verify the
 * resulting merged Landscape/collision state before any production admission.
 */
UCLASS()
class UCyclingLandscapeEarthworksLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category = "Cycling|Editor")
	static bool ApplyRoadEarthworksPatch(
		ALandscape* Landscape,
		const FString& PatchManifestPath,
		bool bDeferLandscapeUpdate = false,
		const FString& PersistentTexturePackage = TEXT(""));

	/** Flush fixed patches once before collision verification and explicit save. */
	UFUNCTION(BlueprintCallable, Category = "Cycling|Editor")
	static bool FinishRoadEarthworksBatch(ALandscape* Landscape);
};

#endif // WITH_EDITOR
