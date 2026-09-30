#include "Cycling/AlpineJourneyRoute.h"

namespace CyclingSimulation
{
	bool TryBuildAlpineJourneyRouteProfile(
		FRouteProfile& OutProfile,
		FString& OutError)
	{
		TArray<FRouteSegmentDefinition> Segments;
		Segments.Reserve(8);

		Segments.Add({ TEXT("Village Start"), 1000.0, 0.005 });
		Segments.Add({ TEXT("River Descent"), 1200.0, -0.015 });
		Segments.Add({ TEXT("Meadow Rollers"), 1500.0, 0.015 });
		Segments.Add({ TEXT("Forest Approach"), 1000.0, 0.025 });
		Segments.Add({ TEXT("Challenge Climb"), 1500.0, 0.065 });
		Segments.Add({ TEXT("Mountain Shelf"), 1000.0, -0.010 });
		Segments.Add({ TEXT("High Valley Descent"), 1500.0, -0.030 });
		Segments.Add({ TEXT("Lakeside Finish"), 1300.0, 0.005 });

		return OutProfile.TryConfigure(TEXT("Alpine Journey"), Segments, OutError);
	}
}
