#include "YacsBobOfficialSession.h"

#include "YacsBobCheckpoint.h"
#include "YacsBobInspectionToolset.h"

#include "Async/Async.h"
#include "AutomationTestToolset.h"
#include "AutomationTestToolsetSubsystem.h"
#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Editor.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "IModelContextProtocolModule.h"
#include "IModelContextProtocolTool.h"
#include "IPythonScriptPlugin.h"
#include "Landscape.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/CoreDelegates.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ModelContextProtocolSettings.h"
#include "ModelContextProtocolToolLibrary.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "ToolsetRegistry/ToolsetRegistry.h"
#include "ToolsetRegistry/ToolsetRegistrySubsystem.h"
#include "UObject/StrongObjectPtr.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/UObjectIterator.h"
#include "UObject/UnrealType.h"

#include <atomic>

namespace
{
using FResult = FYacsBobInspectionToolset::FResult;
constexpr TCHAR FullName[] = TEXT("YacsBobInspection.InspectAcceptedCheckpoint");
constexpr TCHAR InputError[] = TEXT("YacsBobInspection requires an explicit empty arguments object.");
constexpr TCHAR PythonSettingsClass[] = TEXT("/Script/PythonScriptPlugin.PythonScriptPluginSettings");
constexpr TCHAR TestName[] = TEXT("CyclingPhysics.RoadPhysics.ProfileInterpolation");
constexpr TCHAR SessionRelative[] = TEXT("Saved/RuntimeProof/OfficialMcpBob");
constexpr TCHAR HttpSection[] = TEXT("HTTPServer.Listeners");
constexpr TCHAR BlockAll[] = TEXT("/^.*$/");
constexpr uint32 Port = 18784;
constexpr int64 MaxJsonBytes = 32 * 1024 * 1024;

TSharedPtr<FJsonObject> ParseObject(const FString& Text)
{
    TSharedPtr<FJsonObject> Object;
    if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Object))
    {
        return nullptr;
    }
    return Object;
}

FString JsonText(const TSharedRef<FJsonObject>& Object)
{
    FString Text;
    FJsonSerializer::Serialize(Object, TJsonWriterFactory<>::Create(&Text));
    return Text + TEXT("\n");
}

bool ExactFields(const TSharedPtr<FJsonObject>& Object, std::initializer_list<const TCHAR*> Fields)
{
    if (!Object || Object->Values.Num() != static_cast<int32>(Fields.size()))
    {
        return false;
    }
    for (const TCHAR* Field : Fields)
    {
        if (!Object->HasField(Field))
        {
            return false;
        }
    }
    return true;
}

bool ReadFixedJson(const FString& Path, FString& Text, TSharedPtr<FJsonObject>& Object)
{
    const int64 Size = IFileManager::Get().FileSize(*Path);
    const FDateTime Timestamp = IFileManager::Get().GetTimeStamp(*Path);
    if (Size <= 0 || Size > MaxJsonBytes)
    {
        return false;
    }
    TUniquePtr<FArchive> Reader(IFileManager::Get().CreateFileReader(*Path));
    if (!Reader || Reader->TotalSize() != Size)
    {
        return false;
    }
    TArray<uint8> Bytes;
    Bytes.SetNumUninitialized(static_cast<int32>(Size));
    Reader->Serialize(Bytes.GetData(), Size);
    if (Reader->IsError() || Bytes.Contains(0) || IFileManager::Get().FileSize(*Path) != Size
        || IFileManager::Get().GetTimeStamp(*Path) != Timestamp)
    {
        return false;
    }
    const FUTF8ToTCHAR Converted(reinterpret_cast<const ANSICHAR*>(Bytes.GetData()), Bytes.Num());
    Text = FString(Converted.Length(), Converted.Get());
    Object = ParseObject(Text);
    return Object.IsValid();
}

bool NumberIs(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, double Expected)
{
    double Actual = 0;
    return Object && Object->TryGetNumberField(Key, Actual) && Actual == Expected;
}

bool StringIs(const TSharedPtr<FJsonObject>& Object, const TCHAR* Key, const TCHAR* Expected)
{
    FString Actual;
    return Object && Object->TryGetStringField(Key, Actual) && Actual == Expected;
}

bool HasFixedTest()
{
    const TSharedPtr<FJsonObject> Listing = ParseObject(UAutomationTestToolset::ListTests(TestName, TEXT(""), 2));
    const TArray<TSharedPtr<FJsonValue>>* Tests = nullptr;
    FString Name;
    return NumberIs(Listing, TEXT("total"), 1) && NumberIs(Listing, TEXT("returned"), 1)
        && Listing->TryGetArrayField(TEXT("tests"), Tests) && Tests->Num() == 1
        && (*Tests)[0]->TryGetString(Name) && Name == TestName;
}

bool TestSucceeded(const TSharedPtr<FJsonObject>& Result)
{
    const TArray<TSharedPtr<FJsonValue>>* Tests = nullptr;
    if (!NumberIs(Result, TEXT("total"), 1) || !NumberIs(Result, TEXT("passed"), 1)
        || !NumberIs(Result, TEXT("failed"), 0) || !NumberIs(Result, TEXT("skipped"), 0)
        || !Result->TryGetArrayField(TEXT("tests"), Tests) || Tests->Num() != 1)
    {
        return false;
    }
    const TSharedPtr<FJsonObject>* TestPointer = nullptr;
    if (!(*Tests)[0]->TryGetObject(TestPointer)) { return false; }
    const TSharedPtr<FJsonObject> Test = *TestPointer;
    const TArray<TSharedPtr<FJsonValue>>* Errors = nullptr;
    const TArray<TSharedPtr<FJsonValue>>* Warnings = nullptr;
    return StringIs(Test, TEXT("name"), TestName)
        && Test->TryGetArrayField(TEXT("errors"), Errors) && Errors->IsEmpty()
        && Test->TryGetArrayField(TEXT("warnings"), Warnings) && Warnings->IsEmpty();
}
}

struct FYacsBobOfficialSession : TSharedFromThis<FYacsBobOfficialSession, ESPMode::ThreadSafe>
{
    enum class EPhase { WaitingInputs, Discovering, Ready, Running, Completed, Failed };
    EPhase Phase = EPhase::WaitingInputs;
    FString Root;
    FString ExactSha;
    FString ContextText;
    FString TransportText;
    FString LandscapePath;
    FString Error;
    FString CounterText;
    TWeakObjectPtr<ALandscape> Landscape;
    TWeakObjectPtr<UToolsetRegistrySubsystem> GlobalRegistry;
    TSharedPtr<IModelContextProtocolTool> OfficialTool;
    TUniquePtr<UE::ToolsetRegistry::FToolsetRegistry> PrivateRegistry;
    TSharedPtr<FYacsBobInspectionToolset> Domain;
    TStrongObjectPtr<UToolCallAsyncResultString> AsyncResult;
    TSharedPtr<TPromise<FResult>, ESPMode::ThreadSafe> Pending;
    TSharedPtr<FJsonObject> AutomationResult;
    TArray<FString> LibraryClasses;
    TArray<TStrongObjectPtr<UModelContextProtocolToolLibrary>> Libraries;
    TArray<bool> OriginalAutoRegister;
    std::atomic<int32> BodyInvocations{0};
    std::atomic<int32> DeniedInputs{0};
    bool bRequestReserved = false;
    bool bPythonStartupComplete = false;
    bool bTrustedInputs = false;
    bool bNativePythonSettingsRead = false;
    bool bPythonRemoteExecution = false;
    bool bOwnServer = false;
    bool bAddedGlobalBlock = false;
    bool bChangedHttpConfig = false;
    bool bHadBindAddress = false;
    FString OriginalBindAddress;
    TArray<FString> OriginalOverrides;
    TArray<FString> ActiveOverrides;
    double StartedAt = FPlatformTime::Seconds();
    FTSTicker::FDelegateHandle TickHandle;

    FString File(const TCHAR* Name) const { return Root / SessionRelative / Name; }

    TArray<FString> Census() const
    {
        TArray<FString> Paths;
        for (TObjectIterator<UClass> It; It; ++It)
        {
            if (It->IsChildOf(UModelContextProtocolToolLibrary::StaticClass())
                && !It->HasAnyClassFlags(CLASS_Abstract | CLASS_Deprecated | CLASS_NewerVersionExists))
            {
                Paths.Add(It->GetPathName());
            }
        }
        Paths.Sort();
        return Paths;
    }

    bool CheckNativePythonSettings()
    {
        check(IsInGameThread());
        bNativePythonSettingsRead = false;
        UClass* SettingsClass = FindObject<UClass>(nullptr, PythonSettingsClass);
        if (!SettingsClass || SettingsClass->GetPathName() != PythonSettingsClass)
        {
            Error = TEXT("The fixed private Python settings class is unavailable.");
            return false;
        }
        UObject* Settings = SettingsClass->GetDefaultObject();
        FBoolProperty* RemoteExecution = FindFProperty<FBoolProperty>(SettingsClass, TEXT("bRemoteExecution"));
        if (!Settings || Settings->GetClass() != SettingsClass || !RemoteExecution)
        {
            Error = TEXT("The actual native Python remote-execution property is unavailable.");
            return false;
        }
        bPythonRemoteExecution = RemoteExecution->GetPropertyValue_InContainer(Settings);
        bNativePythonSettingsRead = true;
        if (bPythonRemoteExecution)
        {
            Error = TEXT("The actual native Python remote-execution setting is enabled.");
            return false;
        }
        return true;
    }

    bool CheckCheckpoint()
    {
        ALandscape* Current = YacsBobInspection::ResolveApprovedLandscape(Error);
        FString CurrentContext, CurrentTransport;
        TSharedPtr<FJsonObject> Ignored;
        if (!Current || Current != Landscape.Get() || Current->GetPathName() != LandscapePath
            || Current->GetClass() != ALandscape::StaticClass()
            || !ReadFixedJson(File(TEXT("session-context.json")), CurrentContext, Ignored)
            || !ReadFixedJson(File(TEXT("transport-context.json")), CurrentTransport, Ignored)
            || CurrentContext != ContextText || CurrentTransport != TransportText)
        {
            if (Error.IsEmpty()) { Error = TEXT("The fixed native checkpoint or trusted context changed."); }
            return false;
        }
        return true;
    }

    bool CheckInventory()
    {
        if (!CheckNativePythonSettings()) { return false; }
        IModelContextProtocolModule* Module = IModelContextProtocolModule::Get();
        if (!Module || !GlobalRegistry.IsValid() || !GlobalRegistry->ToolsetRegistry.GetBlockedNames().Contains(BlockAll)
            || Census() != LibraryClasses || Module->GetTools().Num() != 1
            || &Module->GetTools()[0].Get() != OfficialTool.Get() || OfficialTool->GetName() != FullName
            || (bOwnServer && !Module->GetServer()))
        {
            Error = TEXT("The bounded official tool inventory or loaded library census changed.");
            return false;
        }
        for (const TStrongObjectPtr<UModelContextProtocolToolLibrary>& Library : Libraries)
        {
            if (!Library.IsValid() || Library->ShouldAutoRegisterTools())
            {
                Error = TEXT("A prepared legacy tool library regained automatic registration.");
                return false;
            }
        }
        if (!CounterText.IsEmpty())
        {
            FString Observed;
            TSharedPtr<FJsonObject> CounterObject;
            if (!ReadFixedJson(File(TEXT("native-counter.json")), Observed, CounterObject) || Observed != CounterText)
            {
                Error = TEXT("The owned native invocation counter changed.");
                return false;
            }
        }
        if (bChangedHttpConfig)
        {
            FString Address;
            TArray<FString> Overrides;
            GConfig->GetString(HttpSection, TEXT("DefaultBindAddress"), Address, GEngineIni);
            GConfig->GetArray(HttpSection, TEXT("ListenerOverrides"), Overrides, GEngineIni);
            if (Address != TEXT("localhost") || Overrides != ActiveOverrides)
            {
                Error = TEXT("The owned loopback listener settings changed.");
                return false;
            }
        }
        return CheckCheckpoint();
    }

    bool Counter(int32 Value, bool bFirst)
    {
        if (!bFirst)
        {
            FString Previous;
            TSharedPtr<FJsonObject> Object;
            if (!ReadFixedJson(File(TEXT("native-counter.json")), Previous, Object) || Previous != CounterText)
            {
                Error = TEXT("The module-owned invocation counter changed externally.");
                return false;
            }
        }
        TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
        Object->SetNumberField(TEXT("schema_version"), 1);
        Object->SetStringField(TEXT("exact_sha"), ExactSha);
        Object->SetNumberField(TEXT("body_invocation_count"), Value);
        CounterText = JsonText(Object);
        return FFileHelper::SaveStringToFile(CounterText, *File(TEXT("native-counter.json")),
            FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), bFirst ? FILEWRITE_NoReplaceExisting : 0);
    }

    void Receipt()
    {
        if (!bTrustedInputs) { return; }
        TSharedRef<FJsonObject> Object = MakeShared<FJsonObject>();
        Object->SetNumberField(TEXT("schema_version"), 1);
        Object->SetStringField(TEXT("exact_sha"), ExactSha);
        Object->SetStringField(TEXT("status"), Phase == EPhase::Completed ? TEXT("NATIVE_BODY_COMPLETED") : TEXT("NATIVE_SESSION_FAILED"));
        Object->SetStringField(TEXT("error"), Error);
        Object->SetNumberField(TEXT("owned_editor_pid"), FPlatformProcess::GetCurrentProcessId());
        Object->SetStringField(TEXT("map_package"), YacsBobInspection::ApprovedMapPackage);
        Object->SetStringField(TEXT("landscape_path"), LandscapePath);
        Object->SetBoolField(TEXT("python_startup_complete"), bPythonStartupComplete);
        if (bNativePythonSettingsRead)
        {
            Object->SetStringField(TEXT("python_settings_class_path"), PythonSettingsClass);
            Object->SetBoolField(TEXT("python_remote_execution"), bPythonRemoteExecution);
        }
        Object->SetNumberField(TEXT("body_invocation_count"), BodyInvocations.load());
        Object->SetNumberField(TEXT("denied_input_count"), DeniedInputs.load());
        TArray<TSharedPtr<FJsonValue>> Classes;
        for (const FString& Path : LibraryClasses) { Classes.Add(MakeShared<FJsonValueString>(Path)); }
        Object->SetArrayField(TEXT("prepared_tool_library_classes"), Classes);
        Object->SetStringField(TEXT("operation"), FullName);
        if (AutomationResult) { Object->SetObjectField(TEXT("official_automation_result"), AutomationResult); }
        Object->SetStringField(TEXT("bundle_hash_verification"), TEXT("fixed_producer_and_client; not_native_sha256"));
        Object->SetBoolField(TEXT("official_mcp_transport_verified"), false);
        Object->SetBoolField(TEXT("native_bob_capture_verified"), false);
        Object->SetBoolField(TEXT("official_mcp_admitted"), false);
        Object->SetBoolField(TEXT("performance_pass"), false);
        FFileHelper::SaveStringToFile(JsonText(Object), *File(TEXT("native-session.json")),
            FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
    }

    void Shutdown()
    {
        check(IsInGameThread());
        IModelContextProtocolModule* Module = IModelContextProtocolModule::Get();
        if (Pending)
        {
            const TSharedPtr<TPromise<FResult>, ESPMode::ThreadSafe> Completion = MoveTemp(Pending);
            Completion->SetValue(MakeError(FString(Error.IsEmpty() ? TEXT("The owned official session closed.") : *Error)));
        }
        if (Module && bOwnServer) { Module->StopServer(); bOwnServer = false; }
        if (Module && OfficialTool) { Module->RemoveTool(OfficialTool.ToSharedRef()); }
        OfficialTool.Reset();
        // Restore only this session's transient settings, without saving any CDO or ini.
        for (int32 Index = 0; Index < Libraries.Num(); ++Index)
        {
            if (Libraries[Index].IsValid())
            {
                if (FBoolProperty* Property = FindFProperty<FBoolProperty>(Libraries[Index]->GetClass(), TEXT("bAutoRegisterTools")))
                {
                    Property->SetPropertyValue_InContainer(Libraries[Index].Get(), OriginalAutoRegister[Index]);
                }
            }
        }
        Libraries.Reset();
        if (GlobalRegistry.IsValid() && bAddedGlobalBlock)
        {
            GlobalRegistry->ToolsetRegistry.RemoveBlockedName(BlockAll);
            bAddedGlobalBlock = false;
        }
        if (GConfig && bChangedHttpConfig)
        {
            if (bHadBindAddress) { GConfig->SetString(HttpSection, TEXT("DefaultBindAddress"), *OriginalBindAddress, GEngineIni); }
            else { GConfig->RemoveKey(HttpSection, TEXT("DefaultBindAddress"), GEngineIni); }
            GConfig->SetArray(HttpSection, TEXT("ListenerOverrides"), OriginalOverrides, GEngineIni);
            FCoreDelegates::TSOnConfigSectionsChanged().Broadcast(GEngineIni, TSet<FString>{HttpSection});
            bChangedHttpConfig = false;
        }
    }

    void Fail(const FString& Message)
    {
        Error = Message;
        Phase = EPhase::Failed;
        Receipt();
        Shutdown();
    }

    bool Inputs()
    {
        Root = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
        FPaths::NormalizeDirectoryName(Root);
        FString ExpectedRoot = FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_MCP_BOB_PROJECT_ROOT"));
        FPaths::NormalizeDirectoryName(ExpectedRoot);
        ExactSha = FPlatformMisc::GetEnvironmentVariable(TEXT("YACS_MCP_BOB_EXPECTED_HEAD"));
        if (!Root.Equals(ExpectedRoot, ESearchCase::IgnoreCase) || !Root.StartsWith(TEXT("D:/yacs/runner/_work/"), ESearchCase::IgnoreCase)
            || ExactSha.Len() != 40)
        {
            Error = TEXT("The fixed official session lacks its isolated checkout context.");
            return false;
        }
        for (TCHAR Character : ExactSha)
        {
            if (!((Character >= TEXT('0') && Character <= TEXT('9')) || (Character >= TEXT('a') && Character <= TEXT('f'))))
            {
                Error = TEXT("The official session revision must be a lowercase exact SHA.");
                return false;
            }
        }
        TSharedPtr<FJsonObject> Context, Transport;
        if (!ReadFixedJson(File(TEXT("session-context.json")), ContextText, Context)
            || !ReadFixedJson(File(TEXT("transport-context.json")), TransportText, Transport)
            || !ExactFields(Context, {TEXT("schema_version"), TEXT("exact_sha"), TEXT("source_sha256"), TEXT("profile_sha256"), TEXT("profile_source_sha"), TEXT("consumer_source_sha"), TEXT("consumer_assets"), TEXT("landscape")})
            || !ExactFields(Transport, {TEXT("schema_version"), TEXT("exact_sha"), TEXT("project_root"), TEXT("owned_editor_pid"), TEXT("source_sha256"), TEXT("session_context_sha256")})
            || !NumberIs(Context, TEXT("schema_version"), 1) || !NumberIs(Transport, TEXT("schema_version"), 1)
            || !StringIs(Context, TEXT("exact_sha"), *ExactSha) || !StringIs(Transport, TEXT("exact_sha"), *ExactSha)
            || !NumberIs(Transport, TEXT("owned_editor_pid"), FPlatformProcess::GetCurrentProcessId()))
        {
            Error = TEXT("The fixed trusted session contexts are invalid.");
            return false;
        }
        FString TransportRoot;
        if (!Transport->TryGetStringField(TEXT("project_root"), TransportRoot))
        {
            Error = TEXT("The fixed trusted native project root is invalid.");
            return false;
        }
        FPaths::NormalizeDirectoryName(TransportRoot);
        const TSharedPtr<FJsonObject>* Identity = nullptr;
        if (!TransportRoot.Equals(Root, ESearchCase::IgnoreCase) || !Context->TryGetObjectField(TEXT("landscape"), Identity)
            || !ExactFields(*Identity, {TEXT("path"), TEXT("class_path")})
            || !StringIs(*Identity, TEXT("class_path"), TEXT("/Script/Landscape.Landscape"))
            || !(*Identity)->TryGetStringField(TEXT("path"), LandscapePath))
        {
            Error = TEXT("The fixed trusted native actor identity is invalid.");
            return false;
        }
        Landscape = YacsBobInspection::ResolveApprovedLandscape(Error);
        if (!CheckCheckpoint() || IFileManager::Get().DirectoryExists(*File(TEXT("bundle")))
            || IFileManager::Get().FileExists(*File(TEXT("native-counter.json")))
            || IFileManager::Get().FileExists(*File(TEXT("native-session.json"))))
        {
            if (Error.IsEmpty()) { Error = TEXT("The owned operation evidence is not fresh."); }
            return false;
        }
        bTrustedInputs = true;
        return true;
    }

    bool PrepareLibraries()
    {
        // Materialize all already-loaded concrete legacy CDOs before the listener.
        // CDO construction may reveal further loaded classes; require convergence.
        for (int32 Round = 0; Round < 4; ++Round)
        {
            const TArray<FString> Before = Census();
            for (TObjectIterator<UClass> It; It; ++It)
            {
                if (Before.Contains(It->GetPathName())) { It->GetDefaultObject(); }
            }
            if (Before != Census()) { continue; }
            LibraryClasses = Before;
            for (TObjectIterator<UClass> It; It; ++It)
            {
                if (!LibraryClasses.Contains(It->GetPathName())) { continue; }
                UModelContextProtocolToolLibrary* Library = Cast<UModelContextProtocolToolLibrary>(It->GetDefaultObject());
                FBoolProperty* Property = FindFProperty<FBoolProperty>(*It, TEXT("bAutoRegisterTools"));
                if (!Library || !Property) { Error = TEXT("Legacy auto-registration property is unavailable."); return false; }
                Libraries.Emplace(Library);
                OriginalAutoRegister.Add(Library->ShouldAutoRegisterTools());
                Property->SetPropertyValue_InContainer(Library, false);
                Library->DeregisterTools();
            }
            return Census() == LibraryClasses;
        }
        Error = TEXT("The loaded legacy tool-library census did not stabilize.");
        return false;
    }

    TFuture<FResult> Inspect(ALandscape& Actor)
    {
        check(IsInGameThread());
        int32 Expected = 0;
        if (Phase != EPhase::Ready || &Actor != Landscape.Get() || !CheckInventory()
            || !BodyInvocations.compare_exchange_strong(Expected, 1))
        {
            return MakeFulfilledPromise<FResult>(MakeError(FString(TEXT("The one owned BOB inspection cannot begin.")))).GetFuture();
        }
        Pending = MakeShared<TPromise<FResult>, ESPMode::ThreadSafe>();
        TFuture<FResult> Future = Pending->GetFuture();
        if (!Counter(1, false)) { Fail(Error); return Future; }
        const TSharedPtr<FJsonObject> Status = ParseObject(UAutomationTestToolset::GetTestStatus());
        if (!StringIs(Status, TEXT("state"), TEXT("Ready")))
        {
            Fail(TEXT("The owned Automation controller is not idle."));
            return Future;
        }
        AsyncResult.Reset(UAutomationTestToolset::RunTests({FString(TestName)}));
        if (!AsyncResult.IsValid()) { Fail(TEXT("The official fixed test returned no async result.")); return Future; }
        Phase = EPhase::Running;
        return Future;
    }

    void Capture()
    {
        if (!AsyncResult->Error.IsEmpty() || !TestSucceeded(ParseObject(AsyncResult->Value)))
        {
            Fail(TEXT("The existing project test did not pass through the official Automation backend."));
            return;
        }
        AutomationResult = ParseObject(AsyncResult->Value);
        IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
        if (!CheckInventory() || !Python || !Python->IsPythonAvailable() || !Python->IsPythonInitialized()
            || !Python->ExecPythonCommand(TEXT("from scripts.ue.official_mcp_bob_operation import capture_and_inspect; capture_and_inspect()")))
        {
            Fail(Error.IsEmpty() ? TEXT("The trusted fixed BOB Python body failed.") : Error);
            return;
        }
        const TCHAR* Names[] = {TEXT("bundle/result.json"), TEXT("bundle/proof.json"), TEXT("bundle/receipt.json"), TEXT("bundle/capture-proof.json")};
        FString Parts[4];
        int64 Total = 0;
        for (int32 Index = 0; Index < 4; ++Index)
        {
            TSharedPtr<FJsonObject> Object;
            Total += IFileManager::Get().FileSize(*File(Names[Index]));
            if (Total > MaxJsonBytes / 2 || !ReadFixedJson(File(Names[Index]), Parts[Index], Object))
            {
                Fail(TEXT("The real fixed BOB result bundle is missing or outside its JSON bound."));
                return;
            }
        }
        if (!CheckInventory()) { Fail(Error); return; }
        // Preserve producer number spellings and raw JSON. The fixed producer and
        // client independently verify actual file hashes and the domain comparison.
        FString Envelope = TEXT("{\"result\":") + Parts[0] + TEXT(",\"proof\":") + Parts[1]
            + TEXT(",\"receipt\":") + Parts[2] + TEXT(",\"capture\":") + Parts[3] + TEXT("}");
        Phase = EPhase::Completed;
        const TSharedPtr<TPromise<FResult>, ESPMode::ThreadSafe> Completion = MoveTemp(Pending);
        Completion->SetValue(MakeValue(MoveTemp(Envelope)));
    }

    bool Activate();
    bool Tick(float)
    {
        check(IsInGameThread());
        if (Phase == EPhase::Failed) { return false; }
        if (FPlatformTime::Seconds() - StartedAt > 180)
        {
            Fail(TEXT("The owned official session exceeded its fixed time bound."));
            return false;
        }
        if (Phase == EPhase::WaitingInputs)
        {
            if (!bPythonStartupComplete) { return true; }
            const FString Project = FPaths::ConvertRelativePathToFull(FPaths::ProjectDir());
            if (!IFileManager::Get().FileExists(*(Project / SessionRelative / TEXT("transport-context.json")))) { return true; }
            if (!Inputs()) { Fail(Error); return false; }
            IPythonScriptPlugin* Python = IPythonScriptPlugin::Get();
            if (!Python || !Python->IsPythonInitialized() || !Python->IsPythonAvailable()
                || UE::ModelContextProtocol::ShouldAutoStartServer())
            {
                Fail(TEXT("The fully initialized private Python/MCP startup prerequisites are unsafe."));
                return false;
            }
            if (!CheckNativePythonSettings()) { Fail(Error); return false; }
            // Bind all imports before closing the CDO census. No caller script/path.
            if (!Python->ExecPythonCommand(TEXT("import unreal; _yacs_python_settings_class = unreal.load_class(None, '/Script/PythonScriptPlugin.PythonScriptPluginSettings'); assert _yacs_python_settings_class is not None and _yacs_python_settings_class.get_path_name() == '/Script/PythonScriptPlugin.PythonScriptPluginSettings'; from scripts.ue.official_mcp_bob_operation import capture_and_inspect; import scripts.ue.bob_road_earthworks_cut; import scripts.geometry.smooth_road_ribbon; import scripts.worldgen.bob_mcp_inspection")))
            {
                Fail(TEXT("The trusted Python imports or private remote-execution setting failed."));
                return false;
            }
            AsyncResult.Reset(UAutomationTestToolset::DiscoverTests(false));
            if (!AsyncResult.IsValid()) { Fail(TEXT("Official discovery returned no async object.")); return false; }
            Phase = EPhase::Discovering;
        }
        if (Phase == EPhase::Discovering && AsyncResult->bIsComplete)
        {
            UAutomationTestToolsetSubsystem* Subsystem = GEditor->GetEditorSubsystem<UAutomationTestToolsetSubsystem>();
            const TSharedPtr<FJsonObject> Status = ParseObject(UAutomationTestToolset::GetTestStatus());
            if (!AsyncResult->Error.IsEmpty() || !Subsystem || !Subsystem->IsControllerReady()
                || !Subsystem->GetAutomationController().IsValid() || !StringIs(Status, TEXT("state"), TEXT("Ready"))
                || !HasFixedTest() || !Activate())
            {
                Fail(Error.IsEmpty() ? TEXT("Owned official discovery/fixed-test prerequisites did not complete.") : Error);
                return false;
            }
            Phase = EPhase::Ready;
        }
        if (Phase == EPhase::Ready || Phase == EPhase::Running || Phase == EPhase::Completed)
        {
            if (!CheckInventory()) { Fail(Error); return false; }
        }
        if (Phase == EPhase::Running && AsyncResult->bIsComplete) { Capture(); }
        if (Phase == EPhase::Completed && IFileManager::Get().FileSize(*File(TEXT("transport-receipt.json"))) > 0)
        {
            // The fixed client publishes this exclusive file after the result,
            // counter, inventory and bundle comparison. This is a stop signal,
            // not native admission of its declared claims or hashes.
            FString ClientText;
            TSharedPtr<FJsonObject> Client;
            bool bTransportVerified = false;
            // The client reserves this file before the first HTTP request and
            // fills it at close. A positive size can precede the writer's close.
            // Await a complete stable object within the same whole-session bound.
            if (!ReadFixedJson(File(TEXT("transport-receipt.json")), ClientText, Client)) { return true; }
            if (!StringIs(Client, TEXT("exact_sha"), *ExactSha)
                || !StringIs(Client, TEXT("status"), TEXT("LOCAL_TRANSPORT_AND_BOB_ARTIFACTS_VERIFIED"))
                || !Client->TryGetBoolField(TEXT("official_mcp_transport_verified"), bTransportVerified)
                || !bTransportVerified || !CheckInventory())
            {
                Fail(TEXT("The fixed client completion or final native census changed."));
                return false;
            }
            Receipt();
            Shutdown();
            return false;
        }
        return Phase != EPhase::Failed;
    }
};

namespace
{
class FYacsBobOfficialTool final : public IModelContextProtocolTool
{
public:
    explicit FYacsBobOfficialTool(TSharedRef<FYacsBobOfficialSession, ESPMode::ThreadSafe> InSession) : Session(MoveTemp(InSession)) {}
    FString GetName() const override { return FullName; }
    FString GetDescription() const override { return TEXT("Read-only inspection of the fixed accepted Sa Calobra checkpoint."); }
    TSharedPtr<FJsonObject> GetInputJsonSchema() const override
    {
        return ParseObject(TEXT("{\"type\":\"object\",\"properties\":{},\"additionalProperties\":false,\"maxProperties\":0}"));
    }
    void RunAsync(const FModelContextProtocolToolRequestId&, const TSharedPtr<FJsonObject>& Params, const FResultCallback& OnComplete) override
    {
        // Official stock adapter normalizes null to {}; this direct tool does not.
        // No native work or GT queue occurs before the complete argument gate.
        if (!Params || !Params->Values.IsEmpty())
        {
            Session->DeniedInputs.fetch_add(1);
            OnComplete(UE::ModelContextProtocol::MakeErrorResult(InputError));
            return;
        }
        const TSharedRef<FYacsBobOfficialSession, ESPMode::ThreadSafe> Owned = Session;
        AsyncTask(ENamedThreads::GameThread, [Owned, Complete = OnComplete]()
        {
            if (Owned->Phase != FYacsBobOfficialSession::EPhase::Ready || Owned->bRequestReserved || !Owned->CheckInventory())
            {
                Complete(UE::ModelContextProtocol::MakeErrorResult(TEXT("The one owned inspection is unavailable.")));
                return;
            }
            Owned->bRequestReserved = true;
            Owned->PrivateRegistry->ExecuteTool(FullName, TEXT("{}")).Next([Owned, Complete](FResult&& Result)
            {
                check(IsInGameThread());
                if (Result.HasError()) { Complete(UE::ModelContextProtocol::MakeErrorResult(Result.GetError())); }
                else { Complete(UE::ModelContextProtocol::MakeTextResult(Result.GetValue())); }
            });
        });
    }
private:
    TSharedRef<FYacsBobOfficialSession, ESPMode::ThreadSafe> Session;
};
}

bool FYacsBobOfficialSession::Activate()
{
    IModelContextProtocolModule* Module = IModelContextProtocolModule::Get();
    UToolsetRegistrySubsystem* Registry = GEditor->GetEditorSubsystem<UToolsetRegistrySubsystem>();
    FString EngineIni = FPaths::ConvertRelativePathToFull(GEngineIni);
    FPaths::NormalizeFilename(EngineIni);
    if (!Module || Module->GetServer() || !Registry || !GConfig
        || !EngineIni.StartsWith(Root + TEXT("/"), ESearchCase::IgnoreCase) || !PrepareLibraries())
    {
        if (Error.IsEmpty()) { Error = TEXT("The owned official pre-listener prerequisites are unavailable."); }
        return false;
    }
    GlobalRegistry = Registry;
    bAddedGlobalBlock = !Registry->ToolsetRegistry.GetBlockedNames().Contains(BlockAll);
    if (bAddedGlobalBlock) { Registry->ToolsetRegistry.AddBlockedName(BlockAll); }
    Module->RefreshTools();
    const TArray<TSharedRef<IModelContextProtocolTool>> Existing = Module->GetTools();
    for (const TSharedRef<IModelContextProtocolTool>& Tool : Existing) { Module->RemoveTool(Tool); }
    const TWeakPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe> Weak = AsShared();
    Domain = MakeShared<FYacsBobInspectionToolset>([Weak](ALandscape& Actor)
    {
        if (const TSharedPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe> Owned = Weak.Pin()) { return Owned->Inspect(Actor); }
        return MakeFulfilledPromise<FResult>(MakeError(FString(TEXT("The owned native body closed.")))).GetFuture();
    });
    PrivateRegistry = MakeUnique<UE::ToolsetRegistry::FToolsetRegistry>(TArray<FString>{},
        TArray<FString>{TEXT("/^YacsBobInspection$/"), TEXT("/^YacsBobInspection[.]InspectAcceptedCheckpoint$/")});
    if (!PrivateRegistry->RegisterToolset(Domain)) { Error = TEXT("The private fixed native toolset could not register."); return false; }
    OfficialTool = MakeShared<FYacsBobOfficialTool>(AsShared());
    if (!Module->AddTool(OfficialTool.ToSharedRef()) || !CheckInventory()) { return false; }

    bHadBindAddress = GConfig->GetString(HttpSection, TEXT("DefaultBindAddress"), OriginalBindAddress, GEngineIni);
    GConfig->GetArray(HttpSection, TEXT("ListenerOverrides"), OriginalOverrides, GEngineIni);
    if (OriginalOverrides.Num() > 128) { Error = TEXT("HTTP listener overrides exceed the owned session bound."); return false; }
    TArray<FString> Overrides;
    for (FString Entry : OriginalOverrides)
    {
        if (Entry.Len() > 1024) { Error = TEXT("An HTTP listener override exceeds the owned session bound."); return false; }
        Entry.ReplaceInline(TEXT("("), TEXT(""));
        Entry.ReplaceInline(TEXT(")"), TEXT(""));
        uint32 OverridePort = 0;
        if (!FParse::Value(*Entry, TEXT("Port="), OverridePort)) { Error = TEXT("An HTTP listener override has no verified port."); return false; }
        if (OverridePort != Port) { Overrides.Add(Entry); }
    }
    bChangedHttpConfig = true;
    ActiveOverrides = Overrides;
    GConfig->SetString(HttpSection, TEXT("DefaultBindAddress"), TEXT("localhost"), GEngineIni);
    GConfig->SetArray(HttpSection, TEXT("ListenerOverrides"), Overrides, GEngineIni);
    FCoreDelegates::TSOnConfigSectionsChanged().Broadcast(GEngineIni, TSet<FString>{HttpSection});
    FString BoundAddress;
    TArray<FString> VerifiedOverrides;
    GConfig->GetString(HttpSection, TEXT("DefaultBindAddress"), BoundAddress, GEngineIni);
    GConfig->GetArray(HttpSection, TEXT("ListenerOverrides"), VerifiedOverrides, GEngineIni);
    if (BoundAddress != TEXT("localhost") || VerifiedOverrides != Overrides)
    {
        Error = TEXT("The owned listener/counter prerequisites could not be established.");
        return false;
    }
    bOwnServer = true;
    Module->StartServer(Port, TEXT("/mcp"));
    return Module->GetServer() != nullptr && CheckInventory() && Counter(0, true);
}

TSharedPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe> StartYacsBobOfficialSession()
{
    if (!FParse::Param(FCommandLine::Get(), TEXT("YacsBobOfficialProof"))) { return nullptr; }
    const TSharedRef<FYacsBobOfficialSession, ESPMode::ThreadSafe> Session = MakeShared<FYacsBobOfficialSession, ESPMode::ThreadSafe>();
    if (IPythonScriptPlugin* Python = IPythonScriptPlugin::Get())
    {
        const TWeakPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe> Weak = Session;
        Python->RegisterOnPythonInitialized(FSimpleDelegate::CreateLambda([Weak]()
        {
            if (const TSharedPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe> Owned = Weak.Pin()) { Owned->bPythonStartupComplete = true; }
        }));
    }
    Session->TickHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Session](float Delta) { return Session->Tick(Delta); }));
    return Session;
}

void StopYacsBobOfficialSession(TSharedPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe>& Session)
{
    if (!Session) { return; }
    FTSTicker::GetCoreTicker().RemoveTicker(Session->TickHandle);
    Session->Shutdown();
    Session.Reset();
}
