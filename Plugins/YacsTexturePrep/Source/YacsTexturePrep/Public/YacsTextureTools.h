#pragma once

#include "CoreMinimal.h"
#include "ImageCore.h"
#include "ToolsetRegistry/ToolsetDefinition.h"
#include "YacsTextureTools.generated.h"

class UTextureGraph;
class UTG_AsyncRenderTask;
class UTextureRenderTarget2D;

USTRUCT(BlueprintType)
struct FYacsTextureRecipe
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") int32 Resolution = 256;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") FVector2D WorldSizeMeters = FVector2D(2, 2);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") float SeamBlendWidth = 0.05f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") float DeLightStrength = 0;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") FLinearColor ColorGain = FLinearColor::White;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") float HeightStrength = 0.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") float NormalStrength = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") float RoughnessMin = 0.55f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") float RoughnessMax = 0.9f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="YACS Texture") float MacroVariation = 0;
};

UCLASS()
class UYacsTextureJob : public UObject
{
    GENERATED_BODY()
public:
    UPROPERTY() TObjectPtr<UTextureGraph> Graph;
    UPROPERTY() TObjectPtr<UTG_AsyncRenderTask> RenderTask;
    UPROPERTY() TObjectPtr<UTextureGraph> WorkingGraph;
    UPROPERTY() FYacsTextureRecipe Recipe;
    FString Id, Folder, Evidence, SourcePath, SourceId, GraphHash, State, Error;
    double Started = 0;
    bool bDraining = false;
    bool bTimedOut = false;
    bool bValidated = false;
    int32 RenderRole = 0;
    TMap<FString, FImage> RenderedImages;
    void StartNextRender();
    UFUNCTION() void OnRendered(const TArray<UTextureRenderTarget2D*>& Targets);
};

/** Narrow editor toolset. Register explicitly behind the existing MCP guard. */
UCLASS()
class YACSTEXTUREPREP_API UYacsTextureTools : public UToolsetDefinition
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable, Category="YACS Texture", meta=(AICallable))
    static FString InspectCapabilities();
    UFUNCTION(BlueprintCallable, Category="YACS Texture", meta=(AICallable))
    static FString PrepareTexture(const FString& SourceAssetPath, FYacsTextureRecipe Recipe);
    UFUNCTION(BlueprintCallable, Category="YACS Texture", meta=(AICallable))
    static FString RenderPreview(const FString& JobId);
    UFUNCTION(BlueprintCallable, Category="YACS Texture", meta=(AICallable))
    static FString ExportPbrSet(const FString& JobId);
    UFUNCTION(BlueprintCallable, Category="YACS Texture", meta=(AICallable))
    static FString ValidateTexture(const FString& JobId);
    UFUNCTION(BlueprintCallable, Category="YACS Texture", meta=(AICallable))
    static FString GetJobStatus(const FString& JobId);

private:
    // The rooted class default object owns jobs throughout asynchronous callbacks.
    UPROPERTY() TMap<FString, TObjectPtr<UYacsTextureJob>> Jobs;
    static UYacsTextureJob* FindJob(const FString& Id);
    static bool Busy();
};
