#if WITH_DEV_AUTOMATION_TESTS

#include "Misc/AutomationTest.h"

#include "Dom/JsonObject.h"
#include "IModelContextProtocolModule.h"
#include "Misc/CommandLine.h"
#include "Misc/EngineVersion.h"
#include "Misc/Parse.h"
#include "ModelContextProtocolSettings.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "ToolsetRegistry/ToolsetRegistry.h"
#include "YacsBobCheckpoint.h"
#include "YacsBobInspectionToolset.h"
#include "YacsBobOfficialSession.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
    FYacsBobInputBoundaryTest,
    "YacsBobInspection.InputBoundary",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FYacsBobInputBoundaryTest::RunTest(const FString& Parameters)
{
    using namespace UE::ToolsetRegistry;

    const FEngineVersion& EngineVersion = FEngineVersion::Current();
    if (!TestTrue(TEXT("Native boundary proof uses the admitted engine"),
        EngineVersion.GetMajor() == 5 && EngineVersion.GetMinor() == 8 && EngineVersion.GetPatch() == 2
        && EngineVersion.GetChangelist() == 56702186))
    {
        return false;
    }

    const auto AssertMcpAbsence = [this](const TCHAR* Phase) -> bool
    {
        IModelContextProtocolModule* Module = IModelContextProtocolModule::Get();
        const bool bModuleLoaded = Module != nullptr;
        const bool bAutoStartDisabled = !UE::ModelContextProtocol::ShouldAutoStartServer();
        const bool bTrustedOptInAbsent = !FParse::Param(FCommandLine::Get(), TEXT("YacsBobOfficialProof"));
        if (!TestTrue(TEXT("Trusted official-session CLI opt-in is absent"), bTrustedOptInAbsent))
        {
            // Never invoke the factory with an opt-in that could start a session.
            return false;
        }
        const bool bFactorySessionAbsent = !StartYacsBobOfficialSession().IsValid();
        const bool bServerAbsent = bModuleLoaded && Module->GetServer() == nullptr;
        AddInfo(FString::Printf(
            TEXT("YacsBobInspection.InputBoundary.McpAbsence phase=%s module_loaded=%s server_absent=%s auto_start_disabled=%s trusted_opt_in_absent=%s factory_session_absent=%s"),
            Phase, bModuleLoaded ? TEXT("true") : TEXT("false"),
            bServerAbsent ? TEXT("true") : TEXT("false"),
            bAutoStartDisabled ? TEXT("true") : TEXT("false"),
            bTrustedOptInAbsent ? TEXT("true") : TEXT("false"),
            bFactorySessionAbsent ? TEXT("true") : TEXT("false")));
        bool bPassed = TestTrue(TEXT("The official MCP module is loaded"), bModuleLoaded);
        bPassed &= TestTrue(TEXT("The actual official MCP server is absent"), bServerAbsent);
        bPassed &= TestTrue(TEXT("The effective official MCP automatic-startup setting is disabled"), bAutoStartDisabled);
        bPassed &= TestTrue(TEXT("The actual official-session factory returns no session without opt-in"), bFactorySessionAbsent);
        return bPassed;
    };
    if (!AssertMcpAbsence(TEXT("before")))
    {
        return false;
    }

    const FString QualifiedOperation = TEXT("YacsBobInspection.InspectAcceptedCheckpoint");
    const TArray<FString> AllowPatterns = {
        TEXT("/^YacsBobInspection$/"),
        TEXT("/^YacsBobInspection[.]InspectAcceptedCheckpoint$/")
    };
    // This registry is owned by this test. No editor-global registry or MCP
    // server is configured, registered or started by the proof.
    FToolsetRegistry Registry({}, AllowPatterns);
    const TSharedRef<int32> CallbackCount = MakeShared<int32>(0);
    const TSharedPtr<FYacsBobInspectionToolset> Toolset = MakeShared<FYacsBobInspectionToolset>(
        [CallbackCount](ALandscape&) -> TFuture<FYacsBobInspectionToolset::FResult>
        {
            ++*CallbackCount;
            return MakeFulfilledPromise<FYacsBobInspectionToolset::FResult>(
                MakeError(FString(TEXT("Isolated boundary proof must never reach the BOB body.")))).GetFuture();
        });
    if (!TestTrue(TEXT("Strict domain toolset registers in the local registry"), Registry.RegisterToolset(Toolset)))
    {
        return false;
    }
    TestTrue(TEXT("Both exact allowpatterns enable the domain toolset"), Toolset->IsEnabled());
    TestTrue(TEXT("The exact qualified operation is enabled"), Toolset->IsToolEnabled(QualifiedOperation));

    const TArray<FString> ToolNames = Toolset->ListToolNames();
    TestEqual(TEXT("Actual native tool-name enumeration exposes one operation"), ToolNames.Num(), 1);
    if (ToolNames.Num() == 1)
    {
        TestEqual(TEXT("Actual native tool name is the fixed qualified operation"), ToolNames[0], QualifiedOperation);
    }

    TSharedPtr<FJsonObject> Schema;
    if (!TestTrue(TEXT("Actual enabled native schema is valid JSON"),
        FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Toolset->GetJsonSchema()), Schema)
        && Schema.IsValid()))
    {
        return false;
    }
    const TArray<TSharedPtr<FJsonValue>>* Tools = nullptr;
    if (!TestTrue(TEXT("Actual native schema contains a tools array"), Schema->TryGetArrayField(TEXT("tools"), Tools))
        || !TestEqual(TEXT("Actual native schema exposes exactly one operation"), Tools->Num(), 1))
    {
        return false;
    }
    const TSharedPtr<FJsonObject> ToolSchema = (*Tools)[0]->AsObject();
    if (!TestTrue(TEXT("Actual native operation schema is an object"), ToolSchema.IsValid()))
    {
        return false;
    }
    TestEqual(TEXT("Schema advertises only the qualified operation"), ToolSchema->GetStringField(TEXT("name")), QualifiedOperation);
    const TSharedPtr<FJsonObject>* InputSchema = nullptr;
    if (!TestTrue(TEXT("Operation schema contains inputSchema"), ToolSchema->TryGetObjectField(TEXT("inputSchema"), InputSchema)))
    {
        return false;
    }
    TestEqual(TEXT("Operation input is an object"), (*InputSchema)->GetStringField(TEXT("type")), FString(TEXT("object")));
    TestFalse(TEXT("Operation schema denies additional properties"), (*InputSchema)->GetBoolField(TEXT("additionalProperties")));
    const TSharedPtr<FJsonObject>* Properties = nullptr;
    if (!TestTrue(TEXT("Operation declares a properties object"), (*InputSchema)->TryGetObjectField(TEXT("properties"), Properties)))
    {
        return false;
    }
    TestEqual(TEXT("Operation schema exposes no caller-selected properties"), (*Properties)->Values.Num(), 0);

    const auto DenialError = [&](const FString& FullName, const FString& Input) -> FString
    {
        // The real registry future is inspected through its native result. The
        // continuation does not capture the test or any editor object.
        TFuture<FString> ErrorFuture = Registry.ExecuteTool(FullName, Input).Next(
            [](FYacsBobInspectionToolset::FResult&& Result) -> FString
            {
                return Result.HasError() ? Result.StealError() : FString();
            });
        if (!TestTrue(TEXT("Boundary denial completes without asynchronous native work"), ErrorFuture.IsReady()))
        {
            return FString();
        }
        const FString Error = ErrorFuture.Get();
        TestFalse(TEXT("Native registry result reports an explicit denial"), Error.IsEmpty());
        TestEqual(TEXT("Denied request does not call the trusted BOB body"), *CallbackCount, 0);
        return Error;
    };

    const TArray<FString> InvalidInputs = {
        TEXT(""), TEXT("null"), TEXT("true"), TEXT("false"), TEXT("0"), TEXT("\"\""), TEXT("[]"),
        TEXT("{"), TEXT("}"), TEXT("{]}"), TEXT("{}{}"), TEXT("{} null"), TEXT("{} trailing"),
        TEXT("{\"script\":\"print(1)\"}"), TEXT("{\"command\":\"save\"}"),
        TEXT("{\"test\":\"CyclingPhysics.RoadPhysics.Other\"}"), TEXT("{\"test_names\":[]}"),
        TEXT("{\"map\":\"/Game/Other\"}"), TEXT("{\"actor\":\"Other\"}"),
        TEXT("{\"evidence_root\":\"D:/other\"}"), TEXT("{\"path\":\"D:/other\"}"),
        TEXT("{\"method\":\"Other\"}"), TEXT("{\"policy\":{}}"),
        TEXT("{\"x\":1,\"x\":2}"), TEXT("{\"x\":null}"), TEXT("\u00a0{}")
    };
    for (const FString& Input : InvalidInputs)
    {
        FString LexicalError;
        TestFalse(TEXT("Caller-controlled nonempty or malformed input is rejected lexically"),
            YacsBobInspection::ValidateOperationInput(YacsBobInspection::OperationName, Input, LexicalError));
        TestEqual(TEXT("The actual registry returns the lexical denial before any checkpoint read"),
            DenialError(QualifiedOperation, Input), LexicalError);
    }

    FString OversizedInput;
    for (int32 Index = 0; Index < 65; ++Index)
    {
        OversizedInput.AppendChar(TEXT(' '));
    }
    OversizedInput += TEXT("{}");
    TestEqual(TEXT("Oversized payload is denied before native work"),
        DenialError(QualifiedOperation, OversizedInput),
        FString(TEXT("BOB inspection input exceeds the fixed empty-object bound.")));

    DenialError(TEXT("YacsBobInspection.inspectAcceptedCheckpoint"), TEXT("{}"));
    DenialError(TEXT("YacsBobInspection.INSPECTACCEPTEDCHECKPOINT"), TEXT("{}"));
    DenialError(TEXT("YacsBobInspection.Other"), TEXT("{}"));
    // These three absent toolsets produce native registry error logs. Match
    // only each complete observed message, without regex, exactly once.
    AddExpectedError(TEXT("LogToolsetRegistry: Toolset 'actor' not found"), EAutomationExpectedErrorFlags::Exact, 1, false);
    DenialError(TEXT("actor.get_label"), TEXT("{}"));
    AddExpectedError(TEXT("LogToolsetRegistry: Toolset 'scene' not found"), EAutomationExpectedErrorFlags::Exact, 1, false);
    DenialError(TEXT("scene.get_current_level"), TEXT("{}"));
    AddExpectedError(TEXT("LogToolsetRegistry: Toolset 'AutomationTestToolset' not found"), EAutomationExpectedErrorFlags::Exact, 1, false);
    DenialError(TEXT("AutomationTestToolset.RunTests"), TEXT("{\"TestNames\":[]}"));
    TArray<FAutomationExpectedMessage> ExpectedDenials;
    GetExpectedMessages(ExpectedDenials);
    TestEqual(TEXT("Only the three exact stock denial logs are expected"), ExpectedDenials.Num(), 3);
    for (const FAutomationExpectedMessage& Denial : ExpectedDenials)
    {
        TestEqual(TEXT("Each expected stock denial log actually occurs exactly once"), Denial.ActualNumberOfOccurrences, 1);
    }

    FString LexicalError;
    TestTrue(TEXT("Exact operation accepts an empty object lexically"),
        YacsBobInspection::ValidateOperationInput(YacsBobInspection::OperationName, TEXT("{}"), LexicalError));
    TestTrue(TEXT("Empty object accepts JSON whitespace lexically"),
        YacsBobInspection::ValidateOperationInput(YacsBobInspection::OperationName, TEXT(" \t{\r\n}\n"), LexicalError));

    // Parent runs this proof in BuildPlugin's isolated empty HostProject. It
    // must fail the fixed checkpoint guard, never simulate BOB inspection.
    TestEqual(TEXT("Valid native dispatch denies an isolated unapproved map"),
        DenialError(QualifiedOperation, TEXT("{}")),
        FString(TEXT("Current map is outside the accepted BOB inspection checkpoint.")));
    TestEqual(TEXT("All native boundary cases leave the trusted callback untouched"), *CallbackCount, 0);
    TestTrue(TEXT("Test-owned native toolset unregisters cleanly"), Registry.UnregisterToolset(Toolset));
    return AssertMcpAbsence(TEXT("after"));
}

#endif // WITH_DEV_AUTOMATION_TESTS
