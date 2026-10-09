#include "YacsBobLandscapeHit.h"

#include "YacsBobCheckpoint.h"
#include "Landscape.h"
#include "LandscapeHeightfieldCollisionComponent.h"

FYacsBobLandscapeHit UYacsBobLandscapeHitLibrary::InspectAcceptedCheckpointIdentity()
{
    FYacsBobLandscapeHit Result;
    ALandscape* Landscape = YacsBobInspection::ResolveApprovedLandscape(Result.Error);
    if (!Landscape)
    {
        return Result;
    }
    Result.bAccepted = true;
    Result.Status = TEXT("CHECKPOINT_IDENTITY");
    Result.MapPackage = YacsBobInspection::ApprovedMapPackage;
    Result.ActorPath = Landscape->GetPathName();
    Result.ActorClassPath = Landscape->GetClass()->GetPathName();
    Result.HitActor = Landscape;
    return Result;
}

FYacsBobLandscapeHit UYacsBobLandscapeHitLibrary::InspectAcceptedLandscapeHit(const FHitResult& HitResult)
{
    FYacsBobLandscapeHit Result;
    ALandscape* Landscape = YacsBobInspection::ResolveApprovedLandscape(Result.Error);
    if (!Landscape)
    {
        return Result;
    }
    Result.MapPackage = YacsBobInspection::ApprovedMapPackage;
    Result.bBlockingHit = HitResult.bBlockingHit;
    if (!HitResult.bBlockingHit)
    {
        Result.bAccepted = true;
        Result.Status = TEXT("MISSING_HIT");
        Result.Error = TEXT("Landscape sample has no blocking hit.");
        return Result;
    }
    if (HitResult.bStartPenetrating)
    {
        Result.Error = TEXT("Landscape sample has no unambiguous blocking hit.");
        return Result;
    }
    auto* Component = Cast<ULandscapeHeightfieldCollisionComponent>(HitResult.GetComponent());
    if (HitResult.GetActor() != Landscape || !IsValid(Component) || Component->GetOwner() != Landscape
        || Component->GetClass() != ULandscapeHeightfieldCollisionComponent::StaticClass())
    {
        Result.Error = TEXT("Landscape sample collision ownership is unknown or foreign.");
        return Result;
    }
    if (!FMath::IsFinite(HitResult.ImpactPoint.X) || !FMath::IsFinite(HitResult.ImpactPoint.Y)
        || !FMath::IsFinite(HitResult.ImpactPoint.Z))
    {
        Result.Error = TEXT("Landscape sample impact point is non-finite.");
        return Result;
    }

    Result.bAccepted = true;
    Result.Status = TEXT("OWNED_LANDSCAPE_HIT");
    Result.bBlockingHit = HitResult.bBlockingHit;
    Result.ImpactPoint = HitResult.ImpactPoint;
    Result.ActorPath = Landscape->GetPathName();
    Result.ActorClassPath = Landscape->GetClass()->GetPathName();
    Result.ComponentPath = Component->GetPathName();
    Result.ComponentClassPath = Component->GetClass()->GetPathName();
    Result.HitActor = Landscape;
    Result.HitComponent = Component;
    return Result;
}
