#pragma once

#include "CoreMinimal.h"
#include "ToolsetRegistry/Toolset.h"

class ALandscape;

/** Single fixed YACS operation; no caller-selected forwarding or script interface. */
class FYacsBobInspectionToolset final : public UE::ToolsetRegistry::FToolset
{
public:
    using FResult = TValueOrError<FString, FString>;
    using FInspectAcceptedCheckpoint = TFunction<TFuture<FResult>(ALandscape&)>;

    explicit FYacsBobInspectionToolset(FInspectAcceptedCheckpoint InInspection);

    virtual FString GetToolsetName() const override;
    virtual FString GetToolsetVersion() const override;
    virtual FString GetToolsetDescription() const override;

protected:
    virtual TFuture<FResult> ExecuteToolInternal(const FString& ToolName, const FString& JsonInput) override;
    virtual FString GetJsonSchemaInternal() const override;

private:
    FInspectAcceptedCheckpoint Inspection;
};
