#pragma once

#include "CoreMinimal.h"

class ALandscape;

namespace YacsBobInspection
{
inline constexpr TCHAR ApprovedMapPackage[] = TEXT("/Game/Generated/YACS/SaCalobra/WholeMapPreparation/L_SaCalobraMaterialReview");
inline constexpr TCHAR ToolsetName[] = TEXT("YacsBobInspection");
inline constexpr TCHAR OperationName[] = TEXT("InspectAcceptedCheckpoint");

/** Must run on the game thread. Does not load a map or change the editor. */
ALandscape* ResolveApprovedLandscape(FString& OutError);

/** Lexical boundary runs before any world, object, Python or Automation access. */
bool ValidateOperationInput(const FString& ToolName, const FString& JsonInput, FString& OutError);
}
