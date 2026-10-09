#include "YacsBobCheckpoint.h"

#include "Editor.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Landscape.h"
#include "UObject/Package.h"

namespace YacsBobInspection
{
bool ValidateOperationInput(const FString& ToolName, const FString& JsonInput, FString& OutError)
{
    OutError.Reset();
    if (!ToolName.Equals(OperationName, ESearchCase::CaseSensitive))
    {
        OutError = TEXT("Unsupported BOB inspection operation.");
        return false;
    }
    if (JsonInput.Len() > 64)
    {
        OutError = TEXT("BOB inspection input exceeds the fixed empty-object bound.");
        return false;
    }

    int32 Position = 0;
    const auto SkipWhitespace = [&]()
    {
        while (Position < JsonInput.Len())
        {
            const TCHAR Character = JsonInput[Position];
            if (Character != TEXT(' ') && Character != TEXT('\t') && Character != TEXT('\r') && Character != TEXT('\n'))
            {
                break;
            }
            ++Position;
        }
    };
    SkipWhitespace();
    if (Position >= JsonInput.Len() || JsonInput[Position++] != TEXT('{'))
    {
        OutError = TEXT("BOB inspection accepts only an empty JSON object.");
        return false;
    }
    SkipWhitespace();
    if (Position >= JsonInput.Len() || JsonInput[Position++] != TEXT('}'))
    {
        OutError = TEXT("BOB inspection accepts no caller-supplied fields.");
        return false;
    }
    SkipWhitespace();
    if (Position != JsonInput.Len())
    {
        OutError = TEXT("BOB inspection input has trailing tokens.");
        return false;
    }
    return true;
}

ALandscape* ResolveApprovedLandscape(FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread())
    {
        OutError = TEXT("BOB inspection requires the editor game thread.");
        return nullptr;
    }
    UWorld* World = GEditor ? GEditor->GetEditorWorldContext().World() : nullptr;
    if (!IsValid(World) || World->WorldType != EWorldType::Editor || GEditor->PlayWorld)
    {
        OutError = TEXT("BOB inspection requires a stopped editor world.");
        return nullptr;
    }
    if (!World->GetOutermost()->GetName().Equals(ApprovedMapPackage, ESearchCase::CaseSensitive))
    {
        OutError = TEXT("Current map is outside the accepted BOB inspection checkpoint.");
        return nullptr;
    }

    ALandscape* Landscape = nullptr;
    for (TActorIterator<ALandscape> It(World); It; ++It)
    {
        if (!IsValid(*It) || Landscape)
        {
            OutError = TEXT("Accepted BOB checkpoint must contain exactly one valid Landscape actor.");
            return nullptr;
        }
        Landscape = *It;
    }
    if (!Landscape)
    {
        OutError = TEXT("Accepted BOB checkpoint has no Landscape actor.");
    }
    return Landscape;
}
}
