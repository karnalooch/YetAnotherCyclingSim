#pragma once
#include "CoreMinimal.h"
class UYacsTextureJob;
class UTexture2D;
bool BuildYacsTextureGraph(UYacsTextureJob& Job, UTexture2D* Source, FString& Error);
