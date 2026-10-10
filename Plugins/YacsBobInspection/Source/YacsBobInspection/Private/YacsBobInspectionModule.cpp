#include "Modules/ModuleManager.h"

#include "YacsBobOfficialSession.h"

class FYacsBobInspectionModule final : public IModuleInterface
{
public:
    void StartupModule() override
    {
        // The fixed session factory returns null without its trusted CLI opt-in.
        // Registration/listening also require the admitted native checkpoint context.
        Session = StartYacsBobOfficialSession();
    }

    void ShutdownModule() override
    {
        StopYacsBobOfficialSession(Session);
    }

private:
    TSharedPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe> Session;
};

IMPLEMENT_MODULE(FYacsBobInspectionModule, YacsBobInspection)
