"""Render genuine 3D camera views and 4 PREVIEW modes in Houdini using OpenGL ROP.

To avoid headless Vulkan driver state re-use crashes, each frame is rendered
in its own isolated hython sub-process.

Renders:
1. 4 PREVIEW modes from cam_panorama:
   - 3d_preview_global_color.png (PREVIEW_GLOBAL_COLOR)
   - 3d_preview_neutral_shading.png (PREVIEW_NEUTRAL_SHADING)
   - 3d_preview_idmap_palette.png (PREVIEW_IDMAP)
   - 3d_preview_scree_isolation.png (PREVIEW_CLASS_ISOLATION)
2. Landmark closeup 3D camera views:
   - 3d_cam_panorama.png (from /obj/cam_panorama on PREVIEW_GLOBAL_COLOR)
   - 3d_cam_puig_major.png (from /obj/cam_puig_major on PREVIEW_GLOBAL_COLOR)
   - 3d_cam_sa_calobra_cove.png (from /obj/cam_sa_calobra_cove on PREVIEW_GLOBAL_COLOR)
   - 3d_cam_scree_site.png (from /obj/cam_scree_site on PREVIEW_GLOBAL_COLOR)
   - 3d_cam_scree_site_isolation.png (from /obj/cam_scree_site on PREVIEW_CLASS_ISOLATION)
   - 3d_cam_transition.png (from /obj/cam_transition on PREVIEW_GLOBAL_COLOR)
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

PROJECT_DIR = Path("D:/yacs/project").resolve()
WORLD_DIR = PROJECT_DIR / "worldgen/houdini/sa_calobra"
L07_HIP = WORLD_DIR / "SaCalobra_Pegasus_Lesson07_Unified_v001.hiplc"
EVIDENCE_DIR = WORLD_DIR / "evidence/lesson07_unified"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = Path("D:/yacs/work/lesson07-unified-20261019/houdini_3d_render_report.json")
HYTHON_BIN = Path("D:/yacs/tools/houdini-22.0.466/bin/hython.exe")


def render_single_view(cam_name: str, node_name: str, out_file: Path, width: int = 1920, height: int = 1080):
    """Executes inside a single hython process."""
    import hou
    print(f"Loading HIP: {L07_HIP}...", flush=True)
    hou.hipFile.load(str(L07_HIP), suppress_save_prompt=True)

    net = hou.node("/obj/SA_CALOBRA_UNIFIED")
    assert net is not None, "Network /obj/SA_CALOBRA_UNIFIED not found"

    node = net.node(node_name)
    assert node is not None, f"Node {node_name} not found"
    repair = json.loads(REPORT_PATH.with_name("preview_repair_report.json").read_text(encoding="utf-8"))
    if repair["hip_after_sha256"] != hashlib.sha256(L07_HIP.read_bytes()).hexdigest():
        raise RuntimeError("Render cache belongs to a different HIP")
    cached = repair["render_caches"][node_name]
    cache_file = Path(cached["path"])
    with cache_file.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != cached["sha256"]:
            raise RuntimeError("Diagnostic geometry cache changed")
    node = net.createNode("file", "RENDER_PREVIEW_CACHE")
    node.parm("file").set(str(cache_file))
    node.setDisplayFlag(True)
    node.setRenderFlag(True)
    for selected in hou.selectedNodes():
        selected.setSelected(False)

    out = hou.node("/out")
    rop = out.node("RENDER_3D_EVIDENCE")
    if not rop:
        rop = out.createNode("opengl", "RENDER_3D_EVIDENCE")
    rop.parm("trange").set(0)
    rop.parm("camera").set(f"/obj/{cam_name}")
    rop.parm("picture").set(str(out_file).replace("\\", "/"))
    rop.parm("tres").set(1)
    rop.parm("res1").set(width)
    rop.parm("res2").set(height)
    rop.parm("lod").set(1.0)

    print(f"Executing render of {node_name} from /obj/{cam_name} to {out_file.name}...", flush=True)
    rop.parm("execute").pressButton()
    assert out_file.exists(), f"Render file was not created: {out_file}"
    print(f"Successfully rendered {out_file.name} ({out_file.stat().st_size} bytes)", flush=True)


def inspect_image(path: Path):
    from PIL import Image
    import numpy as np
    img = Image.open(path)
    arr = np.array(img.convert("RGB"))
    non_black = float(np.count_nonzero(arr > 10)) / arr.size * 100
    file_bytes = path.read_bytes()
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256,
        "shape": list(arr.shape),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min": int(arr.min()),
        "max": int(arr.max()),
        "non_black_pct": non_black,
        "chromatic_pct": float(np.mean(np.ptp(arr, axis=2) > 10) * 100),
        "red_mask_pixels": int(np.count_nonzero(
            (arr[:, :, 0] > 80)
            & (arr[:, :, 0].astype(np.int16) > arr[:, :, 1].astype(np.int16) * 2)
            & (arr[:, :, 0].astype(np.int16) > arr[:, :, 2].astype(np.int16) * 2)
        )),
    }


def main():
    parser = argparse.ArgumentParser(description="Render 3D views from Houdini")
    parser.add_argument("--single", action="store_true", help="Render a single frame inside hython")
    parser.add_argument("--cam", type=str, help="Camera name in /obj")
    parser.add_argument("--node", type=str, help="Display node name in /obj/SA_CALOBRA_UNIFIED")
    parser.add_argument("--out", type=str, help="Output path")
    args = parser.parse_args()

    if args.single:
        render_single_view(args.cam, args.node, Path(args.out))
        return

    # A render receipt is evidence of frames, not visual/terrain acceptance.
    repair_path = REPORT_PATH.with_name("preview_repair_report.json")
    repair = json.loads(repair_path.read_text(encoding="utf-8"))
    hip_sha = hashlib.sha256(L07_HIP.read_bytes()).hexdigest()
    if repair["hip_after_sha256"] != hip_sha or not repair["source_unchanged"]:
        raise RuntimeError("Preview repair receipt does not identify this HIP")
    if REPORT_PATH.exists():
        previous_hash = hashlib.sha256(REPORT_PATH.read_bytes()).hexdigest()
        archive = REPORT_PATH.parent / "render_history" / f"{previous_hash}.json"
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(REPORT_PATH, archive)
    start_time = time.time()
    print("=== STARTING HOUDINI 3D VIEWPORT EVIDENCE RENDERING ===", flush=True)

    preview_modes = [
        ("PREVIEW_GLOBAL_COLOR", "3d_preview_global_color.png", "Global color preview on 3D terrain"),
        ("PREVIEW_NEUTRAL_SHADING", "3d_preview_neutral_shading.png", "Neutral shading clay preview on 3D terrain"),
        ("PREVIEW_IDMAP", "3d_preview_idmap_palette.png", "5-class IDMap palette preview on 3D terrain"),
        ("PREVIEW_CLASS_ISOLATION", "3d_preview_scree_isolation.png", "Scree class isolation mask preview on 3D terrain"),
    ]

    rendered_previews = []
    print("\n--- Part 1: Rendering 4 PREVIEW Modes from cam_panorama ---", flush=True)
    for node_name, img_name, note in preview_modes:
        out_file = EVIDENCE_DIR / img_name
        if out_file.exists():
            out_file.unlink()
        cmd = [
            str(HYTHON_BIN),
            str(Path(__file__).resolve()),
            "--single",
            "--cam", "cam_panorama",
            "--node", node_name,
            "--out", str(out_file),
        ]
        print(f"\n[Running] {node_name} -> {img_name}...", flush=True)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error rendering {img_name}:\n{res.stderr}\n{res.stdout}", flush=True)
            raise RuntimeError(f"Failed to render {img_name}")
        stats = inspect_image(out_file)
        stats["note"] = note
        rendered_previews.append(stats)
        print(f"  [ok] {img_name}: {stats['size_bytes']} bytes, sha256={stats['sha256'][:12]}..., mean={stats['mean']:.1f}, std={stats['std']:.1f}, non_black={stats['non_black_pct']:.1f}%")

    cameras = [
        ("cam_panorama", "PREVIEW_GLOBAL_COLOR", "3d_cam_panorama.png", "Panorama view of full 8x8 km domain"),
        ("cam_puig_major", "PREVIEW_GLOBAL_COLOR", "3d_cam_puig_major.png", "Closeup view of Puig Major peak and ridgeline"),
        ("cam_sa_calobra_cove", "PREVIEW_GLOBAL_COLOR", "3d_cam_sa_calobra_cove.png", "Framed closeup view of Sa Calobra cove and beach"),
        ("cam_scree_site", "SCREE_SITE_GLOBAL_COLOR", "3d_cam_scree_site.png", "Native 0.5 m crop at a verified Scree texel"),
        ("cam_scree_site", "SCREE_FULLRES_PREVIEW", "3d_cam_scree_site_isolation.png", "Same native crop/camera with original Pegasus Scree decoder in red"),
        ("cam_transition", "PREVIEW_GLOBAL_COLOR", "3d_cam_transition.png", "Closeup view of Scree/Cliffs boundary zone"),
    ]

    rendered_cameras = []
    print("\n--- Part 2: Rendering Landmark Camera Views ---", flush=True)
    for cam_name, node_name, img_name, note in cameras:
        out_file = EVIDENCE_DIR / img_name
        if out_file.exists():
            out_file.unlink()
        cmd = [
            str(HYTHON_BIN),
            str(Path(__file__).resolve()),
            "--single",
            "--cam", cam_name,
            "--node", node_name,
            "--out", str(out_file),
        ]
        print(f"\n[Running] {cam_name} ({node_name}) -> {img_name}...", flush=True)
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Error rendering {img_name}:\n{res.stderr}\n{res.stdout}", flush=True)
            raise RuntimeError(f"Failed to render {img_name}")
        stats = inspect_image(out_file)
        stats["note"] = note
        rendered_cameras.append(stats)
        print(f"  [ok] {img_name}: {stats['size_bytes']} bytes, sha256={stats['sha256'][:12]}..., mean={stats['mean']:.1f}, std={stats['std']:.1f}, non_black={stats['non_black_pct']:.1f}%")

    by_name = {item["name"]: item for item in rendered_previews + rendered_cameras}
    signal_checks = {
        "global_color_has_chroma": by_name["3d_preview_global_color.png"]["chromatic_pct"] > 0.5,
        "neutral_is_achromatic": by_name["3d_preview_neutral_shading.png"]["chromatic_pct"] < 0.1,
        "scree_closeup_has_red_mask": by_name["3d_cam_scree_site_isolation.png"]["red_mask_pixels"] >= 20,
    }
    report = {
        "status": "RENDERS_WRITTEN_VISUAL_REVIEW_PENDING" if all(signal_checks.values()) else "FAILED_RENDER_SIGNAL_CHECK",
        "duration_seconds": time.time() - start_time,
        "hip_path": str(L07_HIP),
        "hip_sha256": hip_sha,
        "source_cache_sha256": repair["source_cache_sha256"],
        "scree_houdini_xyz_m": repair["scree_houdini_xyz_m"],
        "signal_checks": signal_checks,
        "signal_checks_are_visual_acceptance": False,
        "evidence_dir": str(EVIDENCE_DIR),
        "preview_mode_renders": rendered_previews,
        "camera_renders": rendered_cameras,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nSaved report to {REPORT_PATH}", flush=True)
    if not all(signal_checks.values()):
        raise RuntimeError(f"Preview signal check failed: {signal_checks}")
    print("=== HOUDINI 3D RENDERING COMPLETED SUCCESSFULLY ===", flush=True)


if __name__ == "__main__":
    main()
