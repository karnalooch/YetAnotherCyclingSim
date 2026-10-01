#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "YacsTextureAuditLibrary.generated.h"

class UTexture2D;

/** Editor-only native texture metadata absent from the Python reflection API. */
UCLASS()
class YETANOTHERCYCLINGSIMEDITOR_API UYacsTextureAuditLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Read derived format/residency without changing source pixels or saving assets. */
	UFUNCTION(BlueprintCallable, Category = "YACS|Diagnostics")
	static FString DescribeTexture(UTexture2D* Texture);
};
