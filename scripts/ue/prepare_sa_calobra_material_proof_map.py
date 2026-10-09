"""Prepare/reload an isolated material consumer map; never author geometry."""

import json
import os
import runpy
import subprocess
from pathlib import Path

import unreal

REPO = Path(__file__).resolve().parents[2]


def main():
    foundation = runpy.run_path(
        str(REPO / "scripts/ue/sa_calobra_material_foundation.py")
    )
    config = foundation["load_workspace"]()
    canonical = Path(config["project"]).resolve()
    actual_project = Path(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
    ).resolve()
    if REPO == canonical or actual_project != REPO:
        raise RuntimeError("Proof-map preparation requires an isolated checkout")
    head = os.environ["YACS_2B_EXPECTED_HEAD"]
    if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
        raise RuntimeError("Invalid exact SHA")
    if (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
        != head
    ):
        raise RuntimeError("Proof-map exact SHA differs")
    if not unreal.SystemLibrary.get_engine_version().startswith("5.8.2-56702186"):
        raise RuntimeError("Unverified engine version")
    mode = os.environ["YACS_2B_PROOF_MAP_ACTION"]
    if mode not in {"prepare", "reload"}:
        raise RuntimeError("Explicit prepare or reload action required")
    output = Path(os.environ["YACS_2B_PROOF_MAP_REPORT"])
    if not output.is_absolute() or output.exists():
        raise RuntimeError("Use a new absolute proof-map report path")
    recipe = json.loads(
        (REPO / "worldgen/materials/sa_calobra_foundation.json").read_text()
    )
    receipt = json.loads(
        (REPO / "worldgen/materials/sa_calobra_foundation_asset.json").read_text()
    )
    relative = Path("Content") / (recipe["map"].removeprefix("/Game/") + ".umap")
    canonical_map, proof_map = canonical / relative, REPO / relative
    digest = foundation["digest"]
    if (
        digest(REPO / "worldgen/materials/sa_calobra_foundation.json")
        != receipt["recipe_sha256"]
        or digest(REPO / "scripts/ue/sa_calobra_material_foundation.py")
        != receipt["producer_sha256"]
    ):
        raise RuntimeError("Candidate recipe/producer identity differs")
    for asset in receipt["assets"]:
        path = (REPO / asset["path"]).resolve()
        if (
            not path.is_relative_to(
                REPO / "Content/Generated/YACS/SaCalobra/MaterialFoundation"
            )
            or path.stat().st_size != asset["size_bytes"]
            or digest(path) != asset["sha256"]
        ):
            raise RuntimeError("Candidate asset identity differs")
    if digest(canonical_map) != receipt["saved_map_sha256"]:
        raise RuntimeError("Canonical frozen map identity differs")

    if mode == "prepare":
        # The existing fresh verifier rejects wrong hashes and missing native
        # audit registration before material application. It saves no map.
        runpy.run_path(
            str(REPO / "scripts/ue/verify_saved_sa_calobra_material_foundation.py")
        )["verify"]()
        consumed = json.loads(Path(os.environ["YACS_2B_RELOAD_REPORT"]).read_text())
    else:
        prepared = json.loads(
            Path(os.environ["YACS_2B_PREPARED_MAP_REPORT"]).read_text()
        )
        if (
            prepared["exact_sha"] != head
            or prepared["status"] != "ISOLATED_CONSUMER_MAP_PREPARED"
            or prepared["canonical_map_sha256"] != digest(canonical_map)
            or prepared["proof_map_sha256"] != digest(proof_map)
            or prepared["producer_sha256"] != digest(__file__)
            or Path(prepared["consumed"]["verification_checkout"]).resolve() != REPO
            or prepared["consumed"]["receipt_sha256"]
            != digest(REPO / "worldgen/materials/sa_calobra_foundation_asset.json")
        ):
            raise RuntimeError("Prepared consumer-map receipt differs")
        consumed = prepared["consumed"]
        world = unreal.EditorLoadingAndSavingUtils.load_map(str(proof_map))
        if world is None:
            raise RuntimeError("Prepared consumer map did not load")

    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world.get_path_name().split(".")[0] != recipe["map"]:
        raise RuntimeError("Wrong proof world")
    landscapes = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Landscape)
    if len(landscapes) != 1:
        raise RuntimeError("Expected one frozen Landscape")
    landscape = landscapes[0]
    material = landscape.get_editor_property("landscape_material")
    if material is None or material.get_path_name() != consumed["material"]:
        raise RuntimeError("Prepared material assignment differs")
    components = landscape.get_components_by_class(unreal.LandscapeComponent)
    if len(components) != 1024:
        raise RuntimeError("Proof Landscape component count differs")
    instance_count = 0
    for component in components:
        audit = json.loads(
            unreal.YacsTextureAuditLibrary.describe_landscape_material_instances(
                component, material
            )
        )
        if not audit.get("all_instances_match"):
            raise RuntimeError("Prepared native material instances differ")
        instance_count += audit["render_instance_count"]

    def snapshot():
        value = foundation["scene_snapshot"](world, landscape, proof_map)
        del value["saved_map_sha256"]
        # Normalize tuples for stable JSON readback comparison.
        return json.loads(json.dumps(value, sort_keys=True))

    before = snapshot()
    if mode == "prepare":
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, recipe["map"]):
            raise RuntimeError("Isolated consumer map save failed")
        if snapshot() != before:
            raise RuntimeError("Bounded scene invariants changed during proof-map save")
    elif before != prepared["scene_snapshot"]:
        raise RuntimeError("Bounded scene invariants changed after proof-map reload")
    if digest(canonical_map) != receipt["saved_map_sha256"]:
        raise RuntimeError("Canonical map changed during isolated proof")
    for asset in receipt["assets"]:
        if digest(REPO / asset["path"]) != asset["sha256"]:
            raise RuntimeError("Candidate asset changed during isolated map save")
    report = {
        "status": "ISOLATED_CONSUMER_MAP_PREPARED"
        if mode == "prepare"
        else "ISOLATED_CONSUMER_MAP_RELOADED",
        "exact_sha": head,
        "producer_sha256": digest(__file__),
        "map_package": recipe["map"],
        "canonical_map_sha256": digest(canonical_map),
        "proof_map_sha256": digest(proof_map),
        "material": material.get_path_name(),
        "render_instances_verified": instance_count,
        "scene_snapshot": before,
        "consumed": consumed,
        "canonical_map_saved": False,
        "isolated_map_saved": mode == "prepare",
        "render_admission": "NOT_PROVEN",
        "performance": "NOT_MEASURED",
    }
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    unreal.log("YACS 2B isolated consumer map " + mode + "; no runtime admission")


if __name__ == "__main__":
    main()
