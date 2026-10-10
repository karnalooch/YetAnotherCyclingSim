#pragma once

#include "CoreMinimal.h"

struct FYacsBobOfficialSession;

/** Internal fixed proof session. No registration occurs without the trusted CLI opt-in. */
TSharedPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe> StartYacsBobOfficialSession();
void StopYacsBobOfficialSession(TSharedPtr<FYacsBobOfficialSession, ESPMode::ThreadSafe>& Session);
