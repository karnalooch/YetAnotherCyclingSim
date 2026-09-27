#pragma once

#include "CoreMinimal.h"

#if WITH_EDITOR

#include "Commandlets/Commandlet.h"
#include "CyclingPassoGiauLandscapeSpikeCommandlet.generated.h"

/**
 * One-shot editor commandlet for the Stage 3G R4.1B Passo Giau Landscape spike.
 *
 * The commandlet imports the prepared 1009x1009 little-endian R16 heightmap
 * into the isolated /Game/Prototype/Maps/L_PassoGiauTerrainSpike map only.
 *
 * It must never mutate L_CyclingTest and it must never become authoritative
 * route/physics geometry.
 */
UCLASS()
class UCyclingPassoGiauLandscapeSpikeCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UCyclingPassoGiauLandscapeSpikeCommandlet();
	virtual int32 Main(const FString& Params) override;
};

#endif // WITH_EDITOR
