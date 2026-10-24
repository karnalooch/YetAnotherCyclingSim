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
	/** Register the engine's special Visibility target on a staged DTM tile; no pixel writes or save. */
	UFUNCTION(BlueprintCallable, Category = "Cycling|Editor")
	static bool RegisterDtmLandscapeVisibility(ALandscape* Landscape);

	UFUNCTION(BlueprintCallable, Category = "Cycling|Editor")
	static bool ApplyRoadEarthworksPatch(
		ALandscape* Landscape,
		const FString& PatchManifestPath,
		bool bDeferLandscapeUpdate = false,
		const FString& PersistentTexturePackage = TEXT(""));

	/** Flush fixed patches once before collision verification and explicit save. */
	UFUNCTION(BlueprintCallable, Category = "Cycling|Editor")
	static bool FinishRoadEarthworksBatch(ALandscape* Landscape);

	/** Apply a smooth cosine mound sculpt to a native Landscape Edit Layer. */
	UFUNCTION(BlueprintCallable, Category = "Cycling|Editor")
	static bool ApplyManualSculptMound(
		ALandscape* Landscape,
		FName LayerName,
		FVector CenterLocation,
		float RadiusCm,
		float HeightDeltaCm);

	/** Clear a native Landscape Edit Layer heightmap back to neutral zero. */
	UFUNCTION(BlueprintCallable, Category = "Cycling|Editor")
	static bool ClearManualLayer(
		ALandscape* Landscape,
		FName LayerName);
};

#endif // WITH_EDITOR
