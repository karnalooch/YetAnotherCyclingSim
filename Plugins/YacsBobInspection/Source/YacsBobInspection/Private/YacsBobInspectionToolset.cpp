#include "YacsBobInspectionToolset.h"

#include "YacsBobCheckpoint.h"

namespace
{
TFuture<FYacsBobInspectionToolset::FResult> Rejected(const FString& Error)
{
    return MakeFulfilledPromise<FYacsBobInspectionToolset::FResult>(MakeError(FString(Error))).GetFuture();
}
}

FYacsBobInspectionToolset::FYacsBobInspectionToolset(FInspectAcceptedCheckpoint InInspection)
    : Inspection(MoveTemp(InInspection))
{
}

FString FYacsBobInspectionToolset::GetToolsetName() const
{
    return YacsBobInspection::ToolsetName;
}

FString FYacsBobInspectionToolset::GetToolsetVersion() const
{
    return TEXT("0.1.0");
}

FString FYacsBobInspectionToolset::GetToolsetDescription() const
{
    return TEXT("Read-only BOB inspection of the fixed accepted Sa Calobra material checkpoint.");
}

TFuture<FYacsBobInspectionToolset::FResult> FYacsBobInspectionToolset::ExecuteToolInternal(
    const FString& ToolName, const FString& JsonInput)
{
    FString Error;
    if (!YacsBobInspection::ValidateOperationInput(ToolName, JsonInput, Error))
    {
        return Rejected(Error);
    }
    if (!Inspection)
    {
        return Rejected(TEXT("The trusted BOB checkpoint inspection body has not been bound."));
    }
    ALandscape* Landscape = YacsBobInspection::ResolveApprovedLandscape(Error);
    if (!Landscape)
    {
        return Rejected(Error);
    }
    return Inspection(*Landscape);
}

FString FYacsBobInspectionToolset::GetJsonSchemaInternal() const
{
    // The installed native registry and MCP adapter consume root tools[].
    // Full tool names use GetToolsetName() + "." + the bare operation name.
    // Schema validation supplements, but never replaces, the raw input gate.
    return TEXT("{\"name\":\"YacsBobInspection\",\"version\":\"0.1.0\",\"tools\":[{"
        "\"name\":\"YacsBobInspection.InspectAcceptedCheckpoint\","
        "\"description\":\"Read-only BOB inspection of the fixed accepted Sa Calobra material checkpoint.\","
        "\"inputSchema\":{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false,\"maxProperties\":0}}]}");
}
