#include "Cycling/Stage3PrototypeTerrainActor.h"

#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/Material.h"
#include "Materials/MaterialInterface.h"
#include "Math/RotationMatrix.h"
#include "UObject/ConstructorHelpers.h"
#include "UObject/UObjectGlobals.h"

namespace Stage3PrototypeTerrainInternal
{
	constexpr double MetresToCentimetres = 100.0;

	constexpr double RoadWidthM = 6.0;
	constexpr double RoadThicknessM = 0.20;
	constexpr double RoadOverlapM = 2.0;

	// Stage 3F: edge-line presentation. A thin elongated rectangle is laid
	// along each road tile at ±(RoadHalfWidthM - EdgeInsetM). The lines are
	// generated from the *exact same* midpoint + orientation as the road
	// tile so they stay aligned through turns and never expose tile seams.
	constexpr double EdgeLineWidthM = 0.30;
	constexpr double EdgeLineHeightM = 0.05;
	constexpr double EdgeLineOverlapM = 2.0;
	constexpr double RoadHalfWidthM = RoadWidthM * 0.5;
	constexpr double EdgeInsetM = 0.10;
	constexpr double EdgeLineLateralOffsetM =
		RoadHalfWidthM - EdgeInsetM - (EdgeLineWidthM * 0.5);

	// Lift the edge-line plane just above the road surface so its white
	// pixels read instead of Z-fighting with the asphalt top.
	constexpr double EdgeLineVerticalOffsetM =
		EdgeLineHeightM * 0.5 + 0.02;

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

	constexpr double RockPropFirstM = 6350.0;
	constexpr double RockPropLastExclusiveM = 9950.0;
	constexpr double RockPropSpacingM = 180.0;
	constexpr double RockPropBaseLateralM = 15.0;

	// Stage 3G: low-cost, deterministic reference-environment layers.
	constexpr double ValleyRidgeFirstM = 300.0;
	constexpr double ValleyRidgeLastExclusiveM = 3700.0;
	constexpr double ValleyRidgeSpacingM = 220.0;
	constexpr double ValleyRidgeBaseLateralM = 120.0;

	constexpr double ForestCanopyFirstM = 3750.0;
	constexpr double ForestCanopyLastExclusiveM = 6250.0;
	constexpr double ForestCanopySpacingM = 100.0;

	constexpr double WaterFirstM = 600.0;
	constexpr double WaterLastExclusiveM = 3200.0;
	constexpr double WaterSpacingM = 100.0;
	constexpr double WaterLateralM = 55.0;
	constexpr double WaterWidthM = 30.0;
	constexpr double WaterThicknessM = 0.18;
	constexpr double WaterVerticalOffsetM = -1.4;

	constexpr double DistantMountainFirstM = 6500.0;
	constexpr double DistantMountainLastExclusiveM = 10000.0;
	constexpr double DistantMountainSpacingM = 500.0;

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

const TCHAR* AStage3PrototypeTerrainActor::RoadAsphaltMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3F/Materials/MI_Stage3F_Asphalt.MI_Stage3F_Asphalt");
const TCHAR* AStage3PrototypeTerrainActor::RoadEdgeLineMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3F/Materials/MI_Stage3F_Edge.MI_Stage3F_Edge");
const TCHAR* AStage3PrototypeTerrainActor::TerrainMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3F/Materials/MI_Stage3F_Terrain.MI_Stage3F_Terrain");
const TCHAR* AStage3PrototypeTerrainActor::Stage3GGrassMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Materials/MI_Stage3G_Grass.MI_Stage3G_Grass");
const TCHAR* AStage3PrototypeTerrainActor::Stage3GForestMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Materials/MI_Stage3G_Forest.MI_Stage3G_Forest");
const TCHAR* AStage3PrototypeTerrainActor::Stage3GFoliageMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Materials/MI_Stage3G_Foliage.MI_Stage3G_Foliage");
const TCHAR* AStage3PrototypeTerrainActor::Stage3GRockMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Materials/MI_Stage3G_Rock.MI_Stage3G_Rock");
const TCHAR* AStage3PrototypeTerrainActor::Stage3GDistantRockMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Materials/MI_Stage3G_DistantRock.MI_Stage3G_DistantRock");
const TCHAR* AStage3PrototypeTerrainActor::Stage3GWaterMaterialPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Materials/MI_Stage3G_Water.MI_Stage3G_Water");
const TCHAR* AStage3PrototypeTerrainActor::Stage3GBoulderMeshPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_Boulder.SM_Stage3G_Boulder");

AStage3PrototypeTerrainActor::AStage3PrototypeTerrainActor()
{
	PrimaryActorTick.bCanEverTick = false;

	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	SceneRoot->SetMobility(EComponentMobility::Static);

	RoadTiles = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RoadTiles"));
	RoadTiles->SetupAttachment(SceneRoot);

	RoadEdgeLines = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RoadEdgeLines"));
	RoadEdgeLines->SetupAttachment(SceneRoot);

	TerrainTiles = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("TerrainTiles"));
	TerrainTiles->SetupAttachment(SceneRoot);

	ForestTerrainTiles = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("ForestTerrainTiles"));
	ForestTerrainTiles->SetupAttachment(SceneRoot);

	HighAlpineTerrainTiles = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("HighAlpineTerrainTiles"));
	HighAlpineTerrainTiles->SetupAttachment(SceneRoot);

	ForestProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("ForestProps"));
	ForestProps->SetupAttachment(SceneRoot);

	MountainProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("MountainProps"));
	MountainProps->SetupAttachment(SceneRoot);

	ValleyRidgeProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("ValleyRidgeProps"));
	ValleyRidgeProps->SetupAttachment(SceneRoot);

	ForestCanopyProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("ForestCanopyProps"));
	ForestCanopyProps->SetupAttachment(SceneRoot);

	DistantMountainProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("DistantMountainProps"));
	DistantMountainProps->SetupAttachment(SceneRoot);

	RockProps = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("RockProps"));
	RockProps->SetupAttachment(SceneRoot);

	WaterTiles = CreateDefaultSubobject<UHierarchicalInstancedStaticMeshComponent>(TEXT("WaterTiles"));
	WaterTiles->SetupAttachment(SceneRoot);

	const ConstructorHelpers::FObjectFinder<UStaticMesh> CubeMesh(
		TEXT("/Engine/BasicShapes/Cube.Cube"));
	const ConstructorHelpers::FObjectFinder<UStaticMesh> CylinderMesh(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	const ConstructorHelpers::FObjectFinder<UStaticMesh> ConeMesh(
		TEXT("/Engine/BasicShapes/Cone.Cone"));

	const ConstructorHelpers::FObjectFinder<UMaterialInterface> RoadAsphaltMat(
		RoadAsphaltMaterialPath);
	const ConstructorHelpers::FObjectFinder<UMaterialInterface> RoadEdgeMat(
		RoadEdgeLineMaterialPath);
	const ConstructorHelpers::FObjectFinder<UMaterialInterface> TerrainMat(
		TerrainMaterialPath);

	if (CubeMesh.Succeeded())
	{
		RoadTiles->SetStaticMesh(CubeMesh.Object);
		RoadEdgeLines->SetStaticMesh(CubeMesh.Object);
		TerrainTiles->SetStaticMesh(CubeMesh.Object);
		ForestTerrainTiles->SetStaticMesh(CubeMesh.Object);
		HighAlpineTerrainTiles->SetStaticMesh(CubeMesh.Object);
		RockProps->SetStaticMesh(CubeMesh.Object);
		WaterTiles->SetStaticMesh(CubeMesh.Object);
	}
	if (CylinderMesh.Succeeded())
	{
		ForestProps->SetStaticMesh(CylinderMesh.Object);
	}
	if (ConeMesh.Succeeded())
	{
		MountainProps->SetStaticMesh(ConeMesh.Object);
		ValleyRidgeProps->SetStaticMesh(ConeMesh.Object);
		ForestCanopyProps->SetStaticMesh(ConeMesh.Object);
		DistantMountainProps->SetStaticMesh(ConeMesh.Object);
	}

	if (RoadAsphaltMat.Succeeded())
	{
		RoadTiles->SetMaterial(0, RoadAsphaltMat.Object);
	}
	else
	{
		// Fallback to the engine default surface material if the Stage 3F
		// material is not authored yet. The setup commandlet will rebuild
		// instances and the next save will re-bind the authored material.
		RoadTiles->SetMaterial(0, UMaterial::GetDefaultMaterial(MD_Surface));
	}

	if (RoadEdgeMat.Succeeded())
	{
		RoadEdgeLines->SetMaterial(0, RoadEdgeMat.Object);
	}
	else
	{
		RoadEdgeLines->SetMaterial(0, UMaterial::GetDefaultMaterial(MD_Surface));
	}

	if (TerrainMat.Succeeded())
	{
		TerrainTiles->SetMaterial(0, TerrainMat.Object);
		ForestTerrainTiles->SetMaterial(0, TerrainMat.Object);
		HighAlpineTerrainTiles->SetMaterial(0, TerrainMat.Object);
	}
	else
	{
		// Keep the previous behavioural baseline if the new terrain material
		// is not yet available. This keeps the codebase graceful before
		// the materials have been authored by the Python script.
		const ConstructorHelpers::FObjectFinder<UMaterialInterface> WorldGrid(
			TEXT("/Engine/EngineMaterials/WorldGridMaterial.WorldGridMaterial"));
		if (WorldGrid.Succeeded())
		{
			TerrainTiles->SetMaterial(0, WorldGrid.Object);
			ForestTerrainTiles->SetMaterial(0, WorldGrid.Object);
			HighAlpineTerrainTiles->SetMaterial(0, WorldGrid.Object);
		}
	}

	if (UStaticMesh* BoulderMesh = LoadObject<UStaticMesh>(nullptr, Stage3GBoulderMeshPath))
	{
		RockProps->SetStaticMesh(BoulderMesh);
	}

	UMaterialInterface* TerrainFallback = TerrainTiles->GetMaterial(0);
	auto ApplyOptionalStage3GMaterial =
		[TerrainFallback](UHierarchicalInstancedStaticMeshComponent* Component, const TCHAR* Path)
		{
			if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, Path))
			{
				Component->SetMaterial(0, Material);
			}
			else if (IsValid(TerrainFallback))
			{
				Component->SetMaterial(0, TerrainFallback);
			}
		};

	ApplyOptionalStage3GMaterial(TerrainTiles, Stage3GGrassMaterialPath);
	ApplyOptionalStage3GMaterial(ForestTerrainTiles, Stage3GForestMaterialPath);
	ApplyOptionalStage3GMaterial(HighAlpineTerrainTiles, Stage3GDistantRockMaterialPath);
	ApplyOptionalStage3GMaterial(ValleyRidgeProps, Stage3GGrassMaterialPath);
	ApplyOptionalStage3GMaterial(ForestProps, Stage3GFoliageMaterialPath);
	ApplyOptionalStage3GMaterial(ForestCanopyProps, Stage3GFoliageMaterialPath);
	ApplyOptionalStage3GMaterial(MountainProps, Stage3GRockMaterialPath);
	ApplyOptionalStage3GMaterial(RockProps, Stage3GRockMaterialPath);
	ApplyOptionalStage3GMaterial(DistantMountainProps, Stage3GDistantRockMaterialPath);
	ApplyOptionalStage3GMaterial(WaterTiles, Stage3GWaterMaterialPath);

	UHierarchicalInstancedStaticMeshComponent* Components[] = {
		RoadTiles,
		RoadEdgeLines,
		TerrainTiles,
		ForestTerrainTiles,
		HighAlpineTerrainTiles,
		ForestProps,
		MountainProps,
		ValleyRidgeProps,
		ForestCanopyProps,
		DistantMountainProps,
		RockProps,
		WaterTiles,
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
		|| !IsValid(MountainProps->GetStaticMesh())
		|| !IsValid(RoadEdgeLines->GetStaticMesh())
		|| !IsValid(ValleyRidgeProps->GetStaticMesh())
		|| !IsValid(ForestCanopyProps->GetStaticMesh())
		|| !IsValid(DistantMountainProps->GetStaticMesh())
		|| !IsValid(WaterTiles->GetStaticMesh()))
	{
		OutError = TEXT("prototype terrain engine basic-shape meshes are unavailable");
		return false;
	}

	Modify();
	RoadTiles->Modify();
	RoadEdgeLines->Modify();
	TerrainTiles->Modify();
	ForestProps->Modify();
	MountainProps->Modify();
	ValleyRidgeProps->Modify();
	ForestCanopyProps->Modify();
	DistantMountainProps->Modify();
	WaterTiles->Modify();

	RoadTiles->ClearInstances();
	RoadEdgeLines->ClearInstances();
	TerrainTiles->ClearInstances();
	ForestProps->ClearInstances();
	MountainProps->ClearInstances();
	ValleyRidgeProps->ClearInstances();
	ForestCanopyProps->ClearInstances();
	DistantMountainProps->ClearInstances();
	WaterTiles->ClearInstances();

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

		// Stage 3F: place a thin white edge line on each side of the road
		// along the same midpoint + orientation as the road tile.
		for (const double Side : { -1.0, 1.0 })
		{
			const FRotator RoadRotation = RoadTransform.Rotator();
			const FQuat RoadQuat = RoadRotation.Quaternion();
			const FVector LocalY = RoadQuat.RotateVector(FVector(0.0, 1.0, 0.0));

			FVector EdgeMidpointM =
				0.5 * (Samples[Index].PositionM + Samples[Index + 1].PositionM);
			EdgeMidpointM += LocalY * (Side * EdgeLineLateralOffsetM);
			// Ride just above the road top (which sits at route Z = 0).
			EdgeMidpointM.Z = EdgeLineHeightM * 0.5 + 0.02;

			const FVector EdgeScale(
				RoadTransform.GetScale3D().X,
				EdgeLineWidthM,
				EdgeLineHeightM);

			const FTransform EdgeTransform(
				RoadRotation,
				EdgeMidpointM * MetresToCentimetres,
				EdgeScale);

			if (!IsFiniteTransform(EdgeTransform))
			{
				OutError = FString::Printf(
					TEXT("prototype road edge line transform %d (side %.1f) is invalid"),
					Index, Side);
				return false;
			}
			RoadEdgeLines->AddInstance(EdgeTransform, false);
		}
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

	// Stage 3G valley silhouette: broad overlapping cone ridges sit beyond the
	// road-support tiles. They are deliberately presentation-only and sampled
	// from route geometry, so rebuilds are deterministic and physics never reads
	// their transforms.
	for (double DistanceM = ValleyRidgeFirstM;
		DistanceM < ValleyRidgeLastExclusiveM;
		DistanceM += ValleyRidgeSpacingM)
	{
		FVector RoutePositionM;
		FVector Right;
		if (!TryResolveHorizontalRight(Geometry, DistanceM, RoutePositionM, Right, OutError))
		{
			return false;
		}

		for (const double Side : { -1.0, 1.0 })
		{
			const double Phase = DistanceM * 0.004 + Side * 0.7;
			const double HeightM = 78.0 + 22.0 * FMath::Abs(FMath::Sin(Phase));
			const double RadiusScaleM = 150.0 + 35.0 * FMath::Abs(FMath::Cos(Phase * 0.8));
			const double LateralM = ValleyRidgeBaseLateralM
				+ 18.0 * FMath::Sin(DistanceM * 0.006 + Side);

			FVector PositionM = RoutePositionM + Right * (Side * LateralM);
			PositionM.Z += HeightM * 0.5 - 3.0;

			const FTransform RidgeTransform(
				FRotator(0.0, FMath::Fmod(DistanceM * 0.071 + Side * 31.0, 360.0), 0.0),
				PositionM * MetresToCentimetres,
				FVector(RadiusScaleM, RadiusScaleM, HeightM));
			if (!IsFiniteTransform(RidgeTransform))
			{
				OutError = TEXT("Stage 3G valley ridge transform is invalid");
				return false;
			}
			ValleyRidgeProps->AddInstance(RidgeTransform, false);
		}
	}

	// Stage 3G watercourse: a low-cost opaque ribbon offset from the road in the
	// lower valley. It follows route elevation intentionally (stream, not lake),
	// which avoids introducing a separate terrain/water simulation subsystem.
	for (double DistanceM = WaterFirstM;
		DistanceM < WaterLastExclusiveM;
		DistanceM += WaterSpacingM)
	{
		const double EndDistanceM = FMath::Min(
			DistanceM + WaterSpacingM,
			WaterLastExclusiveM);
		const double MidDistanceM = 0.5 * (DistanceM + EndDistanceM);

		FVector StartM;
		FVector EndM;
		FVector MidRoutePositionM;
		FVector Right;
		if (!Geometry.TrySamplePosition(DistanceM, StartM, OutError)
			|| !Geometry.TrySamplePosition(EndDistanceM, EndM, OutError)
			|| !TryResolveHorizontalRight(
				Geometry,
				MidDistanceM,
				MidRoutePositionM,
				Right,
				OutError))
		{
			return false;
		}

		StartM += Right * WaterLateralM;
		EndM += Right * WaterLateralM;
		const FTransform WaterTransform = MakeAlignedBoxTransform(
			StartM,
			EndM,
			WaterWidthM,
			WaterThicknessM,
			2.0,
			WaterVerticalOffsetM);
		if (!IsFiniteTransform(WaterTransform))
		{
			OutError = TEXT("Stage 3G water tile transform is invalid");
			return false;
		}
		WaterTiles->AddInstance(WaterTransform, false);
	}

	// Stage 3G canopy layer. Existing ForestProps remain sparse trunk markers;
	// these overlapping cone crowns make the 3.75-6.25 km sector read as a
	// forest from the rider camera without importing production foliage yet.
	const double ForestCanopyLateralsM[] = { 18.0, 36.0 };
	for (double DistanceM = ForestCanopyFirstM;
		DistanceM < ForestCanopyLastExclusiveM;
		DistanceM += ForestCanopySpacingM)
	{
		FVector RoutePositionM;
		FVector Right;
		if (!TryResolveHorizontalRight(Geometry, DistanceM, RoutePositionM, Right, OutError))
		{
			return false;
		}

		for (const double Side : { -1.0, 1.0 })
		{
			for (const double BaseLateralM : ForestCanopyLateralsM)
			{
				const double Phase = DistanceM * 0.013 + BaseLateralM * 0.17 + Side;
				const double HeightM = 13.0 + 6.0 * FMath::Abs(FMath::Sin(Phase));
				const double RadiusScaleM = 5.0 + 2.0 * FMath::Abs(FMath::Cos(Phase));
				const double LateralM = BaseLateralM
					+ 2.5 * FMath::Sin(DistanceM * 0.021 + Side * BaseLateralM);

				FVector PositionM = RoutePositionM + Right * (Side * LateralM);
				PositionM.Z += HeightM * 0.5 - 0.1;

				const FTransform CanopyTransform(
					FRotator(0.0, FMath::Fmod(DistanceM * 0.11 + BaseLateralM * 7.0, 360.0), 0.0),
					PositionM * MetresToCentimetres,
					FVector(RadiusScaleM, RadiusScaleM, HeightM));
				if (!IsFiniteTransform(CanopyTransform))
				{
					OutError = TEXT("Stage 3G forest canopy transform is invalid");
					return false;
				}
				ForestCanopyProps->AddInstance(CanopyTransform, false);
			}
		}
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

	// Stage 3G distant skyline: two depth layers per side. Larger, desaturated
	// peaks create atmospheric depth while the original MountainProps remain the
	// near-road high-Alpine markers.
	const double DistantMountainLateralsM[] = { 220.0, 480.0 };
	for (double DistanceM = DistantMountainFirstM;
		DistanceM < DistantMountainLastExclusiveM;
		DistanceM += DistantMountainSpacingM)
	{
		FVector RoutePositionM;
		FVector Right;
		if (!TryResolveHorizontalRight(Geometry, DistanceM, RoutePositionM, Right, OutError))
		{
			return false;
		}

		for (const double Side : { -1.0, 1.0 })
		{
			for (int32 Layer = 0; Layer < 2; ++Layer)
			{
				const double LateralM = DistantMountainLateralsM[Layer];
				const double Phase = DistanceM * 0.003 + Layer * 1.7 + Side;
				const double HeightM =
					(Layer == 0 ? 180.0 : 320.0)
					+ (Layer == 0 ? 45.0 : 70.0) * FMath::Abs(FMath::Sin(Phase));
				const double RadiusScaleM =
					(Layer == 0 ? 135.0 : 220.0)
					+ 35.0 * FMath::Abs(FMath::Cos(Phase * 0.7));

				FVector PositionM = RoutePositionM + Right * (Side * LateralM);
				PositionM.Z += HeightM * 0.42 - (Layer == 0 ? 12.0 : 28.0);

				const FTransform DistantPeakTransform(
					FRotator(0.0, FMath::Fmod(DistanceM * 0.049 + Layer * 53.0, 360.0), 0.0),
					PositionM * MetresToCentimetres,
					FVector(RadiusScaleM, RadiusScaleM, HeightM));
				if (!IsFiniteTransform(DistantPeakTransform))
				{
					OutError = TEXT("Stage 3G distant mountain transform is invalid");
					return false;
				}
				DistantMountainProps->AddInstance(DistantPeakTransform, false);
			}
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
	const int32 ExpectedEdgeLineInstances = ExpectedRoadInstances * 2;
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
	if (GetRoadEdgeLineInstanceCount() != ExpectedEdgeLineInstances)
	{
		OutError = FString::Printf(
			TEXT("prototype road edge line instance count mismatch: actual=%d expected=%d"),
			GetRoadEdgeLineInstanceCount(),
			ExpectedEdgeLineInstances);
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
	if (GetValleyRidgeInstanceCount() <= 0
		|| GetForestCanopyInstanceCount() <= 0
		|| GetDistantMountainInstanceCount() <= 0
		|| GetWaterTileInstanceCount() <= 0)
	{
		OutError = TEXT("Stage 3G reference-environment layers are missing");
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

int32 AStage3PrototypeTerrainActor::GetRoadEdgeLineInstanceCount() const
{
	return IsValid(RoadEdgeLines) ? RoadEdgeLines->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetValleyRidgeInstanceCount() const
{
	return IsValid(ValleyRidgeProps) ? ValleyRidgeProps->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetForestCanopyInstanceCount() const
{
	return IsValid(ForestCanopyProps) ? ForestCanopyProps->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetDistantMountainInstanceCount() const
{
	return IsValid(DistantMountainProps) ? DistantMountainProps->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetWaterTileInstanceCount() const
{
	return IsValid(WaterTiles) ? WaterTiles->GetInstanceCount() : 0;
}
