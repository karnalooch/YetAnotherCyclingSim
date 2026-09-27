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
	constexpr double MountainPropLateralM = 55.0;

	constexpr double RockPropFirstM = 6350.0;
	constexpr double RockPropLastExclusiveM = 9950.0;
	constexpr double RockPropSpacingM = 180.0;
	constexpr double RockPropBaseLateralM = 15.0;

	// Stage 3G: low-cost, deterministic reference-environment layers.
	constexpr double ValleyRidgeFirstM = 300.0;
	constexpr double ValleyRidgeLastExclusiveM = 3700.0;
	constexpr double ValleyRidgeSpacingM = 220.0;
	constexpr double ValleyRidgeBaseLateralM = 150.0;

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

	bool TryMakeGroundedMeshTransform(
		UStaticMesh* Mesh,
		const FVector& GroundPositionM,
		const FVector& TargetSizeM,
		const FRotator& Rotation,
		FTransform& OutTransform,
		FString& OutError)
	{
		if (!IsValid(Mesh)
			|| !IsFiniteVector(GroundPositionM)
			|| !IsFiniteVector(TargetSizeM)
			|| TargetSizeM.X <= 0.0
			|| TargetSizeM.Y <= 0.0
			|| TargetSizeM.Z <= 0.0)
		{
			OutError = TEXT("Stage 3G grounded mesh transform inputs are invalid");
			return false;
		}

		const FBoxSphereBounds Bounds = Mesh->GetBounds();
		const FVector MeshSizeCm = Bounds.BoxExtent * 2.0;
		if (!IsFiniteVector(MeshSizeCm)
			|| MeshSizeCm.X <= UE_SMALL_NUMBER
			|| MeshSizeCm.Y <= UE_SMALL_NUMBER
			|| MeshSizeCm.Z <= UE_SMALL_NUMBER)
		{
			OutError = TEXT("Stage 3G grounded mesh bounds are invalid");
			return false;
		}

		const FVector Scale(
			(TargetSizeM.X * MetresToCentimetres) / MeshSizeCm.X,
			(TargetSizeM.Y * MetresToCentimetres) / MeshSizeCm.Y,
			(TargetSizeM.Z * MetresToCentimetres) / MeshSizeCm.Z);
		const double MeshMinZCm =
			static_cast<double>(Bounds.Origin.Z - Bounds.BoxExtent.Z);

		FVector PositionM = GroundPositionM;
		PositionM.Z -=
			(MeshMinZCm * Scale.Z) / MetresToCentimetres;

		OutTransform = FTransform(
			Rotation,
			PositionM * MetresToCentimetres,
			Scale);
		if (!IsFiniteTransform(OutTransform))
		{
			OutError = TEXT("Stage 3G grounded mesh transform is invalid");
			return false;
		}
		return true;
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
const TCHAR* AStage3PrototypeTerrainActor::Stage3GConiferMeshPath =
	TEXT("/Game/Prototype/Environment/Stage3G/Imported/Meshes/SM_Stage3G_FirSaplingMedium.SM_Stage3G_FirSaplingMedium");

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
		// R3 reuses the validated project-owned boulder mesh for valley and
		// high-Alpine massing so the persisted reference map no longer falls
		// back to Engine Cone silhouettes outside the forest sector.
		ValleyRidgeProps->SetStaticMesh(BoulderMesh);
		MountainProps->SetStaticMesh(BoulderMesh);
		DistantMountainProps->SetStaticMesh(BoulderMesh);
		RockProps->SetStaticMesh(BoulderMesh);
	}
	if (UStaticMesh* ConiferMesh = LoadObject<UStaticMesh>(nullptr, Stage3GConiferMeshPath))
	{
		ForestProps->SetStaticMesh(ConiferMesh);
		ForestCanopyProps->SetStaticMesh(ConiferMesh);
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
	// ForestProps / ForestCanopyProps intentionally keep the validated conifer's
	// authored branch + masked-twig material slots. Overriding slot 0 with the
	// legacy generic foliage material would turn the real mesh back into a
	// presentation placeholder in the 4900 m acceptance capture.
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
		|| !IsValid(ForestTerrainTiles->GetStaticMesh())
		|| !IsValid(HighAlpineTerrainTiles->GetStaticMesh())
		|| !IsValid(ForestProps->GetStaticMesh())
		|| !IsValid(MountainProps->GetStaticMesh())
		|| !IsValid(RoadEdgeLines->GetStaticMesh())
		|| !IsValid(ValleyRidgeProps->GetStaticMesh())
		|| !IsValid(ForestCanopyProps->GetStaticMesh())
		|| !IsValid(DistantMountainProps->GetStaticMesh())
		|| !IsValid(RockProps->GetStaticMesh())
		|| !IsValid(WaterTiles->GetStaticMesh()))
	{
		OutError = TEXT("prototype terrain engine/basic presentation meshes are unavailable");
		return false;
	}

	if (ForestProps->GetStaticMesh()->GetPathName() != Stage3GConiferMeshPath
		|| ForestCanopyProps->GetStaticMesh()->GetPathName() != Stage3GConiferMeshPath)
	{
		OutError = TEXT("Stage 3G forest presentation requires the validated Fir Sapling Medium mesh");
		return false;
	}
	if (ValleyRidgeProps->GetStaticMesh()->GetPathName() != Stage3GBoulderMeshPath
		|| MountainProps->GetStaticMesh()->GetPathName() != Stage3GBoulderMeshPath
		|| DistantMountainProps->GetStaticMesh()->GetPathName() != Stage3GBoulderMeshPath
		|| RockProps->GetStaticMesh()->GetPathName() != Stage3GBoulderMeshPath)
	{
		OutError = TEXT("Stage 3G valley/high-Alpine presentation requires the validated Boulder 01 mesh");
		return false;
	}

	Modify();
	RoadTiles->Modify();
	RoadEdgeLines->Modify();
	TerrainTiles->Modify();
	ForestTerrainTiles->Modify();
	HighAlpineTerrainTiles->Modify();
	ForestProps->Modify();
	MountainProps->Modify();
	ValleyRidgeProps->Modify();
	ForestCanopyProps->Modify();
	DistantMountainProps->Modify();
	RockProps->Modify();
	WaterTiles->Modify();

	RoadTiles->ClearInstances();
	RoadEdgeLines->ClearInstances();
	TerrainTiles->ClearInstances();
	ForestTerrainTiles->ClearInstances();
	HighAlpineTerrainTiles->ClearInstances();
	ForestProps->ClearInstances();
	MountainProps->ClearInstances();
	ValleyRidgeProps->ClearInstances();
	ForestCanopyProps->ClearInstances();
	DistantMountainProps->ClearInstances();
	RockProps->ClearInstances();
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
		UHierarchicalInstancedStaticMeshComponent* TargetTerrain = TerrainTiles;
		if (MidDistanceM >= MountainStartM)
		{
			TargetTerrain = HighAlpineTerrainTiles;
		}
		else if (MidDistanceM >= ForestStartM)
		{
			TargetTerrain = ForestTerrainTiles;
		}
		TargetTerrain->AddInstance(TerrainTransform, false);
	}

	// Stage 3G R3 valley silhouette: broad, bounds-aware instances of the
	// validated Boulder 01 mesh replace the former Engine Cone placeholders.
	// The grass material keeps the meadow read while the real mesh supplies an
	// irregular landform silhouette. Physics never reads these transforms.
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
			const double LateralM = ValleyRidgeBaseLateralM
				+ 18.0 * FMath::Sin(DistanceM * 0.006 + Side);
			const FVector TargetSizeM(
				32.0 + 12.0 * FMath::Abs(FMath::Cos(Phase * 0.8)),
				24.0 + 10.0 * FMath::Abs(FMath::Sin(Phase * 1.3)),
				16.0 + 8.0 * FMath::Abs(FMath::Sin(Phase)));

			FVector GroundPositionM =
				RoutePositionM + Right * (Side * LateralM);
			GroundPositionM.Z -= RoadThicknessM;

			FTransform RidgeTransform;
			if (!TryMakeGroundedMeshTransform(
				ValleyRidgeProps->GetStaticMesh(),
				GroundPositionM,
				TargetSizeM,
				FRotator(
					0.0,
					FMath::Fmod(DistanceM * 0.071 + Side * 31.0, 360.0),
					0.0),
				RidgeTransform,
				OutError))
			{
				OutError = FString::Printf(
					TEXT("Stage 3G valley ridge transform is invalid at %.3f m: %s"),
					DistanceM,
					*OutError);
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

	// Stage 3G R2 real conifer layer. The same validated mass-forest mesh that
	// backs PCG_Forest replaces the old Engine Cone/Cylinder placeholders in
	// the persisted reference map. Scale is derived from actual mesh bounds so
	// source-unit differences cannot create giant or microscopic trees.
	const FBoxSphereBounds ConiferBounds =
		ForestCanopyProps->GetStaticMesh()->GetBounds();
	const double ConiferMeshHeightCm =
		static_cast<double>(ConiferBounds.BoxExtent.Z) * 2.0;
	const double ConiferMeshMinZCm =
		static_cast<double>(ConiferBounds.Origin.Z - ConiferBounds.BoxExtent.Z);
	if (!FMath::IsFinite(ConiferMeshHeightCm)
		|| !FMath::IsFinite(ConiferMeshMinZCm)
		|| ConiferMeshHeightCm <= UE_SMALL_NUMBER)
	{
		OutError = TEXT("Stage 3G conifer mesh bounds are invalid");
		return false;
	}

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
				const double LateralM = BaseLateralM
					+ 2.5 * FMath::Sin(DistanceM * 0.021 + Side * BaseLateralM);

				const double UniformScale =
					(HeightM * MetresToCentimetres) / ConiferMeshHeightCm;
				FVector PositionM = RoutePositionM + Right * (Side * LateralM);
				PositionM.Z -=
					(ConiferMeshMinZCm * UniformScale) / MetresToCentimetres;
				PositionM.Z -= 0.1;
				const FTransform CanopyTransform(
					FRotator(0.0, FMath::Fmod(DistanceM * 0.11 + BaseLateralM * 7.0, 360.0), 0.0),
					PositionM * MetresToCentimetres,
					FVector(UniformScale));
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
			const double UniformScale =
				(HeightM * MetresToCentimetres) / ConiferMeshHeightCm;
			PositionM.Z -=
				(ConiferMeshMinZCm * UniformScale) / MetresToCentimetres;
			PositionM.Z -= 0.2;
			const FTransform TreeTransform(
				FRotator(
					0.0,
					FMath::Fmod(DistanceM * 0.083 + Side * 43.0, 360.0),
					0.0),
				PositionM * MetresToCentimetres,
				FVector(UniformScale));
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
			const double Phase = DistanceM * 0.007 + Side * 0.6;
			const FVector TargetSizeM(
				10.0 + 7.0 * FMath::Abs(FMath::Cos(DistanceM * 0.009 + Side)),
				8.0 + 5.0 * FMath::Abs(FMath::Sin(Phase * 1.4)),
				9.0 + 7.0 * FMath::Abs(FMath::Sin(Phase)));

			FVector GroundPositionM =
				RoutePositionM + Right * (Side * MountainPropLateralM);
			GroundPositionM.Z -= RoadThicknessM;

			FTransform PeakTransform;
			if (!TryMakeGroundedMeshTransform(
				MountainProps->GetStaticMesh(),
				GroundPositionM,
				TargetSizeM,
				FRotator(
					0.0,
					FMath::Fmod(DistanceM * 0.083 + Side * 47.0, 360.0),
					0.0),
				PeakTransform,
				OutError))
			{
				OutError = FString::Printf(
					TEXT("Stage 3G high-Alpine massing transform is invalid at %.3f m: %s"),
					DistanceM,
					*OutError);
				return false;
			}
			MountainProps->AddInstance(PeakTransform, false);
		}
	}

	// Stage 3G R1 real rock dressing. The imported boulder mesh is scaled
	// from its actual bounds to a deterministic target diameter so source-unit
	// differences cannot silently create kilometre-sized or microscopic rocks.
	const FVector RockMeshSizeCm = RockProps->GetStaticMesh()->GetBounds().BoxExtent * 2.0;
	const double RockMeshMaxDimensionCm = FMath::Max3(
		static_cast<double>(RockMeshSizeCm.X),
		static_cast<double>(RockMeshSizeCm.Y),
		static_cast<double>(RockMeshSizeCm.Z));
	if (!FMath::IsFinite(RockMeshMaxDimensionCm) || RockMeshMaxDimensionCm <= UE_SMALL_NUMBER)
	{
		OutError = TEXT("Stage 3G rock mesh bounds are invalid");
		return false;
	}

	for (double DistanceM = RockPropFirstM;
		DistanceM < RockPropLastExclusiveM;
		DistanceM += RockPropSpacingM)
	{
		FVector RoutePositionM;
		FVector Right;
		if (!TryResolveHorizontalRight(Geometry, DistanceM, RoutePositionM, Right, OutError))
		{
			return false;
		}

		for (const double Side : { -1.0, 1.0 })
		{
			const double Phase = DistanceM * 0.017 + Side * 0.9;
			const double TargetDiameterM =
				1.8 + 1.2 * FMath::Abs(FMath::Sin(Phase));
			const double LateralM =
				RockPropBaseLateralM
				+ 6.0 * FMath::Abs(FMath::Cos(DistanceM * 0.009 + Side));
			const double UniformScale =
				(TargetDiameterM * MetresToCentimetres) / RockMeshMaxDimensionCm;

			FVector PositionM = RoutePositionM + Right * (Side * LateralM);
			PositionM.Z += TargetDiameterM * 0.35;

			const FTransform RockTransform(
				FRotator(
					0.0,
					FMath::Fmod(DistanceM * 0.137 + Side * 71.0, 360.0),
					0.0),
				PositionM * MetresToCentimetres,
				FVector(UniformScale));
			if (!IsFiniteTransform(RockTransform))
			{
				OutError = TEXT("Stage 3G rock dressing transform is invalid");
				return false;
			}
			RockProps->AddInstance(RockTransform, false);
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
				const FVector TargetSizeM(
					(Layer == 0 ? 55.0 : 85.0)
						+ (Layer == 0 ? 20.0 : 30.0) * FMath::Abs(FMath::Cos(Phase * 0.7)),
					(Layer == 0 ? 40.0 : 62.0)
						+ (Layer == 0 ? 15.0 : 22.0) * FMath::Abs(FMath::Sin(Phase * 0.9)),
					(Layer == 0 ? 35.0 : 58.0)
						+ (Layer == 0 ? 16.0 : 22.0) * FMath::Abs(FMath::Sin(Phase)));

				FVector GroundPositionM =
					RoutePositionM + Right * (Side * LateralM);
				GroundPositionM.Z -=
					Layer == 0 ? 2.0 : 6.0;

				FTransform DistantPeakTransform;
				if (!TryMakeGroundedMeshTransform(
					DistantMountainProps->GetStaticMesh(),
					GroundPositionM,
					TargetSizeM,
					FRotator(
						0.0,
						FMath::Fmod(
							DistanceM * 0.049 + Layer * 53.0 + Side * 17.0,
							360.0),
						0.0),
					DistantPeakTransform,
					OutError))
				{
					OutError = FString::Printf(
						TEXT("Stage 3G distant mountain transform is invalid at %.3f m: %s"),
						DistanceM,
						*OutError);
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
		|| GetRockPropInstanceCount() <= 0
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
	int32 Count = IsValid(TerrainTiles) ? TerrainTiles->GetInstanceCount() : 0;
	Count += IsValid(ForestTerrainTiles) ? ForestTerrainTiles->GetInstanceCount() : 0;
	Count += IsValid(HighAlpineTerrainTiles) ? HighAlpineTerrainTiles->GetInstanceCount() : 0;
	return Count;
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

int32 AStage3PrototypeTerrainActor::GetRockPropInstanceCount() const
{
	return IsValid(RockProps) ? RockProps->GetInstanceCount() : 0;
}

int32 AStage3PrototypeTerrainActor::GetWaterTileInstanceCount() const
{
	return IsValid(WaterTiles) ? WaterTiles->GetInstanceCount() : 0;
}