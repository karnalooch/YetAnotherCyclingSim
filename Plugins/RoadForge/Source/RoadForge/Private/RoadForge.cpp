// Copyright RoadForge Contributors. Licensed under the MIT License.

#include "RoadForge.h"

#define LOCTEXT_NAMESPACE "FRoadForgeModule"

DEFINE_LOG_CATEGORY_STATIC(LogRoadForgeModule, Log, All);

void FRoadForgeModule::StartupModule()
{
	UE_LOG(LogRoadForgeModule, Log, TEXT("RoadForge runtime module started."));
}

void FRoadForgeModule::ShutdownModule()
{
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FRoadForgeModule, RoadForge)
