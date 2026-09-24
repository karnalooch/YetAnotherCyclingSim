#include "Cycling/Stage3PrototypeTerrainActor.h"

#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "Math/RotationMatrix.h"
#include "UObject/ConstructorHelpers.h"

namespace Stage3PrototypeTerrainInternal
{
	constexpr double MetresToCentimetres = 100.0;

	constexpr double RoadWidthM = 6.0;
	constexpr double RoadThicknessM = 0.20;
	constexpr double RoadOverlapM = 2.0;

	constexpr int32 TerrainStrideSamples = 5;
	constexpr double TerrainThicknessM = 8.0;
	constexpr double ValleyTerrainWidthM = 160.0;
	constexpr double ForestTerrainWidthM = 120.0;
	constexpr double MountainTerrainWidthM = 90.0;

	constexpr double ForestStartM = 3700.0;
	constexpr double MountainStartM = 6200.0;

	constexpr double ForestPropFirstM = 3800.0;
	constexpr double ForestPropLastExclusiveM = 6200.0;
	constexpr double ForestPropSpacingM = 200.0;
	constexpr double ForestPropLateralM = 28.0;

	constexpr double MountainPropFirstM = 6300.0;
	constexpr double MountainPropLastExclusiveM = 10000.0;
	constexpr double MountainPropSpacingM = 250.0;
	constexpr double MountainPropLateralM = 42.0;

	bool IsFiniteVector(const FVector& Value)
	{
		return FMath::IsFinite(Value.X)
			&& FMath::IsFinite(Value.Y)
			&& FMath::IsFinite(Value.Z);
	}

	bool IsFiniteQuat(const FQuat& Value)
	{
		return FMath::IsFinite(Value.X)
			&& FMath::IsFinite(Value.Y)
			&& FMath::IsFinite(Value.Z)
			&& FMath::IsFinite(Value.W);
	}

	bool IsFiniteTransform(const FTransform& Transform)
	{
		const FVector Location = Transform.GetLocation();
		const FVector Scale = Transform.GetScale3D();
		const FQuat Rotation = Transform.GetRotation();
		return IsFiniteVector(Location)
			&& IsFiniteVector(Scale)
			&& IsFiniteQuat(Rotation)
			&& Rotation.IsNormalized()
			&& Scale.X > 0.0
			&& Scale.Y > 0.0
			&& Scale.Z > 0.0;
	}

	FTransform MakeAlignedBoxTransform(
		const FVector& StartM,
		const FVector& EndM,
		double WidthM,
		double ThicknessM,
		double AddedLengthM,
		double VerticalOffsetM)
	{
		const FVector DeltaM = EndM - StartM;
		const double LengthM = DeltaM.Size();
		const FVector Forward = DeltaM.GetSafeNormal();
		const FRotator Rotation = FRotationMatrix::MakeFromXZ(
			Forward,
			FVector::UpVector).Rotator();

		FVector MidpointM = 0.5 * (StartM + EndM);
		MidpointM.Z += VerticalOffsetM;

		return FTransform(
			Rotation,
			MidpointM * MetresToCentimetres,
			FVector(
				LengthM + AddedLengthM,
				WidthM,
				ThicknessM));
	}

	bool TryResolveHorizontalRight(
		const CyclingSimulation::FRouteGeometryProfile& Geometry,
		double DistanceM,
		FVector& OutPositionM,
		FVector& OutRight,
		FString& OutError)
	{
		const double TotalLengthM = Geometry.GetTotalLengthM();
		const double BeforeM = FMath::Max(0.0, DistanceM - 5.0);
		const double AfterM = FMath::Min(TotalLengthM, DistanceM + 5.0);

		FVector BeforePositionM;
		FVector AfterPositionM;
		if (!Geometry.TrySamplePosition(DistanceM, OutPositionM, OutError)
			|| !Geometry.TrySamplePosition(BeforeM, BeforePositionM, OutError)
			|| !Geometry.TrySamplePosition(AfterM, AfterPositionM, OutError))
		{
			return false;
		}

		FVector HorizontalForward = AfterPositionM - BeforePositionM;
		HorizontalForward.Z = 0.0;
		if (!HorizontalForward.Normalize())
		{
			OutError = FString::Printf(
				TEXT("prototype terrain could not resolve horizontal tangent at %.3f m"),
				DistanceM);
			return false;
		}

		OutRight = FVector(
			-HorizontalForward.Y,
			HorizontalForward.X,
			0.0);
		return true;
	}
}

AStage3PrototypeTerrainActor::AStage3PrototypeTerrainActor()
{
	PrimaryActorTick.bCanEverTick = false;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	SceneRoot->SetMobility(EComponentMobility::Static);

	RoadTiles = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RoadTiles"));
	RoadTiles->SetupAttachment(SceneRoot);

	TerrainTiles = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("TerrainTiles"));
	TerrainTiles->SetupAttachment(SceneRoot);

	ForestProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("ForestProps"));
	ForestProps->SetupAttachment(SceneRoot);

	MountainProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("MountainProps"));
	MountainProps->SetupAttachment(SceneRoot);

	const ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	const ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	const ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(
		TEXT("/Engine/BasicShapes/Cone.Cone"));

	if (CubeMesh.Succeeded())
	{
		RoadTiles->SetStaticMesh(CubeMesh.Object);
		TerrainTiles->SetStaticMesh(CubeMesh.Object);
	}
	if (CylinderMesh.Succeeded())
	{
		ForestProps->SetStaticMesh(CylinderMesh.Object);
	}
	if (ConeMesh.Succeeded())
	{
		MountainProps->SetStaticMesh(ConeMesh.Object);
	}

	UHierarchicalInstancedStaticMeshComponent* Components[] = {
		RoadTiles,
		TerrainTiles,
		ForestProps,
		MountainProps,
	};
	for (UHierarchicalInstancedStaticMeshComponent* Component : Components)
	{
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetGenerateOverlapEvents(false);
		Component->SetCanEverAffectNavigation(false);
		Component->SetMobility(EComponentMobility::Static);
	}
}

bool AStage3PrototypeTerrainActor::RebuildFromGeometry(
	const CyclingSimulation::FRouteGeometryProfile& Geometry,
	FString& OutError)
{
	using namespace Stage3PrototypeTerrainInternal;

	OutError.Reset();
	if (!Geometry.IsConfigured())
	{
		OutError = TEXT("prototype terrain requires configured route geometry");
		return false;
	}
	if (!IsValid(RoadTiles->GetStaticMesh())
		|| !IsValid(TerrainTiles->GetStaticMesh())
		|| !IsValid(ForestProps->GetStaticMesh())
		|| !IsValid(MountainProps->GetStaticMesh()))
	{
		OutError = TEXT("prototype terrain engine basic-shape meshes are unavailable");
		return false;
	}

	Modify();
	RoadTiles->Modify();
	TerrainTiles->Modify();
	ForestProps->Modify();
	MountainProps->Modify();

	RoadTiles->ClearInstances();
	TerrainTiles->ClearInstances();
	ForestProps->ClearInstances();
	MountainProps->ClearInstances();

	const TArray<CyclingSimulation::FRouteGeometrySample>& Samples =
		Geometry.GetSamples();

	for (int32 Index = 0; Index < Samples.Num() - 1; ++Index)
	{
		const FTransform RoadTransform = MakeAlignedBoxTransform(
			Samples[Index].PositionM,
			Samples[Index + 1].PositionM,
			RoadWidthM,
			RoadThicknessM,
			RoadOverlapM,
			-RoadThicknessM * 0.5);
		if (!IsFiniteTransform(RoadTransform))
		{
			OutError = FString::Printf(
				TEXT("prototype road transform %d is invalid"),
				Index);
			return false;
		}
		RoadTiles->AddInstance(RoadTransform, false);
	}

	for (int32 StartIndex = 0;
		StartIndex < Samples.Num() - 1;
		StartIndex += TerrainStrideSamples)
	{
		const int32 EndIndex = FMath::Min(
			StartIndex + TerrainStrideSamples,
			Samples.Num() - 1);
		const double MidDistanceM =
			0.5 * (Samples[StartIndex].DistanceM + Samples[EndIndex].DistanceM);

		double WidthM = ValleyTerrainWidthM;
		if (MidDistanceM >= MountainStartM)
		{
			WidthM = MountainTerrainWidthM;
		}
		else if (MidDistanceM >= ForestStartM)
		{
			WidthM = ForestTerrainWidthM;
		}

		const FTransform TerrainTransform = MakeAlignedBoxTransform(
			Samples[StartIndex].PositionM,
			Samples[EndIndex].PositionM,
			WidthM,
			TerrainThicknessM,
			5.0,
			-(TerrainThicknessM * 0.5 + RoadThicknessM));
		if (!IsFiniteTransform(TerrainTransform))
		{
			OutError = FString::Printf(
				TEXT("prototype terrain transform beginning at sample %d is invalid"),
				StartIndex);
			return false;
		}
		TerrainTiles->AddInstance(TerrainTransform, false);
	}

	for (double DistanceM = ForestPropFirstM;
		DistanceM < ForestPropLastExclusiveM;
		DistanceM += ForestPropSpacingM)
	{
		FVector RoutePositionM;
		FVector Right;
		if (!TryResolveHorizontalRight(
				Geometry,
				DistanceM,
				RoutePositionM,
				Right,
				OutError))
		{
			return false;
		}

		for (const double Side : { -1.0, 1.0 })
		{
			FVector PositionM =
				RoutePositionM + Right * (Side * ForestPropLateralM);
			const double HeightM =
				12.0 + 2.0 * FMath::Abs(FMath::Sin(DistanceM * 0.011));
			PositionM.Z += HeightM * 0.5 - 0.2;

			const FTransform TreeTransform(
				FRotator::ZeroRotator,
				PositionM * MetresToCentimetres,
				FVector(0.8, 0.8, HeightM));
			if (!IsFiniteTransform(TreeTransform))
			{
				OutError = TEXT("prototype forest prop transform is invalid");
				return false;
			}
			ForestProps->AddInstance(TreeTransform, false);
		}
	}

	for (double DistanceM = MountainPropFirstM;
		DistanceM < MountainPropLastExclusiveM;
		DistanceM += MountainPropSpacingM)
	{
		FVector RoutePositionM;
		FVector Right;
		if (!TryResolveHorizontalRight(
				Geometry,
				DistanceM,
				RoutePositionM,
				Right,
				OutError))
		{
			return false;
		}

		for (const double Side : { -1.0, 1.0 })
		{
			FVector PositionM =
				RoutePositionM + Right * (Side * MountainPropLateralM);
			const double HeightM =
				24.0 + 10.0 * FMath::Abs(FMath::Sin(DistanceM * 0.007));
			const double RadiusScaleM =
				10.0 + 4.0 * FMath::Abs(FMath::Cos(DistanceM * 0.009));
			PositionM.Z += HeightM * 0.5 - 0.2;

			const FTransform PeakTransform(
				FRotator::ZeroRotator,
				PositionM * MetresToCentimetres,
				FVector(RadiusScaleM, RadiusScaleM, HeightM));
			if (!IsFiniteTransform(PeakTransform))
			{
				OutError = TEXT("prototype mountain prop transform is invalid");
				return false;
			}
			MountainProps->AddInstance(PeakTransform, false);
		}
	}

	MarkPackageDirty();
	return ValidateAgainstGeometry(Geometry, OutError);
}

bool AStage3PrototypeTerrainActor::ValidateAgainstGeometry(
	const CyclingSimulation::FRouteGeometryProfile& Geometry,
	FString& OutError) const
{
	using namespace Stage3PrototypeTerrainInternal;

	OutError.Reset();
	if (!Geometry.IsConfigured())
	{
		OutError = TEXT("prototype terrain validation requires configured geometry");
		return false;
	}

	const TArray<CyclingSimulation::FRouteGeometrySample>& Samples =
		Geometry.GetSamples();
	const int32 ExpectedRoadInstances = Samples.Num() - 1;
	const int32 ExpectedTerrainInstances =
		FMath::DivideAndRoundUp(ExpectedRoadInstances, TerrainStrideSamples);

	if (GetRoadInstanceCount() != ExpectedRoadInstances)
	{
		OutError = FString::Printf(
			TEXT("prototype road instance count mismatch: actual=%d expected=%d"),
			GetRoadInstanceCount(),
			ExpectedRoadInstances);
		return false;
	}
	if (GetTerrainInstanceCount() != ExpectedTerrainInstances)
	{
		OutError = FString::Printf(
			TEXT("prototype terrain instance count mismatch: actual=%d expected=%d"),
			GetTerrainInstanceCount(),
			ExpectedTerrainInstances);
		return false;
	}
	if (GetForestPropInstanceCount() <= 0 || GetMountainPropInstanceCount() <= 0)
	{
		OutError = TEXT("prototype world progression props are missing");
		return false;
	}

	for (int32 Index = 0; Index < ExpectedRoadInstances; ++Index)
	{
		FTransform Transform;
		if (!RoadTiles->GetInstanceTransform(Index, Transform, false)
			|| !IsFiniteTransform(Transform))
		{
			OutError = FString::Printf(
				TEXT("prototype road instance %d is missing or invalid"),
				Index);
			return false;
		}

		FVector ExpectedMidpointM =
			0.5 * (Samples[Index].PositionM + Samples[Index + 1].PositionM);
		ExpectedMidpointM.Z -= RoadThicknessM * 0.5;
		const FVector ActualMidpointM =
			Transform.GetLocation() / MetresToCentimetres;

		if (!ActualMidpointM.Equals(ExpectedMidpointM, 0.01))
		{
			OutError = FString::Printf(
				TEXT("prototype road instance %d departed from deterministic route centre"),
				Index);
			return false;
		}
	}

	return true;
}

int32 AStage3PrototypeTerrainActor::GetRoadInstanceCount() const
{
	return IsValid(RoadTiles) ? RoadTiles->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetTerrainInstanceCount() const
{
	return IsValid(TerrainTiles) ? TerrainTiles->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetForestPropInstanceCount() const
{
	return IsValid(ForestProps) ? ForestProps->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetMountainPropInstanceCount() const
{
	return IsValid(MountainProps) ? MountainProps->GetInstanceCount() : 0;
}
