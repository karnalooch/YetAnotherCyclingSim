"""Rebuild a metadata-only concordance from the owner-retained SideFX corpus.

Never changes the source corpus, executes its assets, or copies transcript prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zlib
from pathlib import Path


STAGES = {
    0: "Package, folders and version control",
    1: "HeightField creation, shaping, erosion and HDA packaging",
    2: "Layered terrain workflow, masks, trails and vegetation handoff",
    3: "Landscape ID-map and Unreal material consumer",
    4: "RGB HeightFields and point advection",
    5: "Cliff generation, tiling, PDG and Unreal handoff",
    6: "Pile simulation, collision input and HDA handoff",
    7: "Nanite prop generation, UVs, map baking and PDG",
    8: "Architecture slicing, placement and terrain sampling",
    9: "Object variation, data tables and stone fences",
    10: "Cloud generation and Unreal cloud consumers",
    11: "Flora tools and tree construction",
    12: "HeightField masks, color layers and color-map export",
    13: "Pathfinding, authored splines and river-tool integration",
    14: "Architecture placement, shapes and facades",
    15: "Unreal utility widgets and Houdini Engine control",
}
TIME = re.compile(r"(?m)^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def digest(path):
    h = hashlib.sha256()
    crc = 0
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
            crc = zlib.crc32(block, crc)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest(), "crc32": f"{crc & 0xffffffff:08x}"}


def safe_file(root, rel):
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Missing or unsafe corpus reference: {rel}")
    return path


def esc(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def implementation_records():
    """Preserve registered implementation evidence when rebuilding source metadata."""
    path = Path(__file__).parent / 'catalog/catalog.json'
    if not path.exists():
        return {}
    return {part['id']: {key: part[key] for key in
            ('implementation_status', 'implementation_receipt') if key in part}
            for series in read_json(path)['series'] for part in series['parts']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--talks", type=Path, required=True)
    ap.add_argument("--hda-audit", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    root, out = args.corpus.resolve(), args.output.resolve()
    implementations = implementation_records()
    out.mkdir(parents=True, exist_ok=True)
    tm = read_json(root / "manifest_transkrypcji.json")
    mm = read_json(root / "manifest_materialow.json")
    talks_manifest = read_json(args.talks / "manifest.json")
    hdas = read_json(args.hda_audit) if args.hda_audit else {"libraries": []}
    hda_by_file = {x["file"]: x for x in hdas["libraries"]}
    materials = []
    for item in mm["extracted_files"]:
        actual = digest(safe_file(root, item["path"]))
        if actual["bytes"] != item["bytes"] or actual["crc32"] != item["crc32"]:
            raise ValueError(f"Material mismatch: {item['path']}")
        record = {**item, **actual, "verification": "BYTES_AND_CRC_VERIFIED; SHA256_RECORDED; NOT_COOK_PROOF"}
        if item["path"] in hda_by_file:
            audit = hda_by_file[item["path"]]
            if audit["sha256"] != actual["sha256"]:
                raise ValueError(f"HDA audit mismatch: {item['path']}")
            record["hda_definition_audit"] = {"houdini": hdas["houdini"], "definitions": audit["definitions"], "scope": "Definition and parameter inspection only; no cook/admission claim"}
        materials.append(record)

    catalog = {
        "schema_version": 1,
        "snapshot_date": tm["retrieved_date"],
        "method": "Read all registered local transcript files and material bytes; verify original VTT SHA256 and material CRC32; record exact local paths and hashes. Indexing is not semantic study, execution or production admission.",
        "roots": {"transcripts_and_materials": "YACS_SIDEFX_CORPUS", "supporting_talks": "YACS_SIDEFX_TALKS"},
        "manifest_integrity": {name: digest(root / name) for name in ("manifest_transkrypcji.json", "manifest_materialow.json")},
        "series": [], "materials": materials, "archives": mm["archives"],
        "downloads": mm["sources"], "extras": [], "supporting_talks": [],
    }
    index = ["# SideFX source concordance", "", "Metadata snapshot: 2026-10-16. [Workflow and fidelity contract](../README.md).", "", "This catalog maps every registered lesson and material to its retained source. It does not claim every lesson was studied, ported, cooked or admitted in YACS. Source descriptions are identified as source descriptions. Shared series materials are not guessed to belong to a particular lesson.", "", "## Series", "", "| ID | Original series | Parts | Material files | Stage |", "|---|---|---:|---:|---|"]
    for series in tm["series"]:
        order = series["order"]
        sid = f"PEG-{order:02d}"
        folder = Path(series["parts"][0]["txt"]).parts[0]
        related = [x for x in materials if x["path"].startswith(folder + "/")]
        downloads = [x for x in mm["sources"]["files"] if x["series_order"] == order]
        nozip = [x for x in mm["sources"]["series_without_zip"] if x["order"] == order]
        item = {"id": sid, "original_order": order, "title": series["title"], "source_url": series["source_url"], "stage": STAGES[order], "corpus_folder": folder, "material_paths": [x["path"] for x in related], "material_association": "Series-level download bundle only; per-lesson dependency mapping must be verified in the original project before implementation", "source_archives": downloads, "missing_material_status": nozip, "parts": []}
        rows = [f"# {sid}: {series['title']}", "", f"[Official series]({series['source_url']}) · [Catalog](README.md) · [Workflow](../README.md)", "", f"Stage: **{STAGES[order]}**. Corpus folder: `{folder}`.", "", "## Lesson concordance", "", "All listed TXT/VTT files were read and the original VTT hashes checked. `INDEXED` means source availability and integrity, not semantic study or a successful Houdini cook. Paths below resolve relative to `YACS_SIDEFX_CORPUS`.", ""]
        for part in series["parts"]:
            pid = f"{sid}-{part['package_order']:02d}"
            vtt_path = safe_file(root, part["vtt"])
            txt_path = safe_file(root, part["txt"])
            vd, td = digest(vtt_path), digest(txt_path)
            vtt_text = vtt_path.read_text(encoding="utf-8-sig")
            txt_path.read_text(encoding="utf-8-sig")
            timings = TIME.findall(vtt_text)
            if vd["sha256"] != part["vtt_sha256"] or not timings:
                raise ValueError(f"Transcript mismatch: {pid}")
            p = {**part, "id": pid, "txt_integrity": td, "vtt_integrity": vd, "parsed_timing_count": len(timings), "verification": "INDEXED; ORIGINAL_VTT_HASH_VERIFIED", "implementation_status": "NO_PER_LESSON_YACS_IMPLEMENTATION_RECEIPT_REGISTERED", "material_association": f"Shared {sid} series bundle; no inferred per-lesson pairing"}
            item["parts"].append(p)
            p.update(implementations.get(pid, {}))
            rows += [f"### {pid}: {part['title']}", "", f"[Original video]({part['url']}) · [Caption resource]({part['caption_resource']})", "", f"- Language: `{part['language']}`; source track: `{part['source_language']}`; automatic: `{str(part.get('automatic', 'unspecified')).lower()}`.", f"- Text coverage: `{part['first_text_start']}` → `{part['last_text_end']}`; {part['nonempty_cue_count']} nonempty cues; original timestamps retained.", f"- TXT: `{part['txt']}`", f"- VTT: `{part['vtt']}`", f"- Original VTT SHA-256: `{vd['sha256']}`", f"- Source lesson objective: {part.get('description') or 'Not supplied in the captured source listing.'}", f"- Materials: shared `{sid}` bundle listed below. Per-lesson dependency mapping has not been established.", f"- Verification: `INDEXED`; implementation: `{p['implementation_status']}`." + (f" Receipt: [{p['implementation_receipt']}]({p['implementation_receipt']})." if p.get("implementation_receipt") else ""), ""]
        rows += ["## Original material bundle", "", "The filenames and HDA type names below are evidence of supplied files. They are not a claim that every dependency is present, licensed for redistribution, version-compatible or successfully cooked.", ""]
        for download in downloads:
            rows += [f"- [{download['filename']}]({download['download_url']}) — original archive SHA-256 `{download['sha256']}`."]
        if nozip:
            rows += ["- `NO_SERIES_ZIP_LISTED`: no downloadable ZIP was listed on the captured official page. Other series are not silently substituted."]
        rows += ["", "| Corpus-relative material path | Kind / inspected HDA definitions | Bytes | CRC32 |", "|---|---|---:|---|"]
        for m in related:
            names = ", ".join(d["name"] for d in m.get("hda_definition_audit", {}).get("definitions", []))
            rows.append(f"| `{m['path']}` | {esc(names or Path(m['path']).suffix or 'file')} | {m['bytes']} | `{m['crc32']}` |")
        rows += ["", "Exact SHA-256 for every material and inspected HDA parameter schemas are in [catalog.json](catalog.json).", ""]
        (out / f"{sid}.md").write_text("\n".join(rows), encoding="utf-8")
        index.append(f"| {sid} | [{esc(series['title'])}]({sid}.md) | {len(series['parts'])} | {len(related)} | {STAGES[order]} |")
        catalog["series"].append(item)

    extra_rows = ["# Supporting transcripts and availability", "", "[Catalog](README.md) · [Workflow](../README.md)", "", "## Pegasus supplementary videos", "", "| Original title / video | Availability | Timing | Corpus-relative file |", "|---|---|---|---|"]
    for extra in tm["extras"]:
        e = {k: v for k, v in extra.items() if k != "status_note"}
        if e.get("txt"):
            file = safe_file(root, e["txt"])
            file.read_text(encoding="utf-8-sig")
            e["integrity"] = digest(file)
        catalog["extras"].append(e)
        extra_rows.append(f"| [{esc(e['title'])}]({e['url']}) | `{e['status']}`; {e.get('caption_type', 'no original English captions captured')} | {e.get('first_start','n/a')} → {e.get('last_start','n/a')}; start times only | `{e.get('txt','UNAVAILABLE')}` |")
    extra_rows += ["", "These five exports contain source start timestamps only. No VTT end times are invented. Eight supplementary videos lack captured original English transcripts; unavailable does not mean nonexistent in every platform or future version.", "", "## Embark and Far Cry 5", ""]
    by_integrity = {x["file"]: x for x in talks_manifest["file_integrity"]}
    for talk in talks_manifest["lectures"]:
        t = {k: v for k, v in talk.items() if k not in ("automatic_status", "vtt_status")}
        t["file_integrity"] = []
        for rel in talk["files"]:
            file = safe_file(args.talks, rel)
            file.read_text(encoding="utf-8-sig")
            d = digest(file)
            if d["sha256"] != by_integrity[rel]["sha256"]:
                raise ValueError(f"Supporting talk mismatch: {rel}")
            t["file_integrity"].append({"path": rel, **d})
        t["caption_limit"] = "Original Vimeo VTT; automatic/authored status unspecified by Vimeo label" if any(x.endswith('.vtt') for x in talk['files']) else "YouTube automatic transcript; original start timestamps only; VTT and cue end times unavailable"
        t["implementation_status"] = "ARCHITECTURAL_REFERENCE; NO_ORIGINAL_PROPRIETARY_HIP_OR_HDA_SUPPLIED"
        catalog["supporting_talks"].append(t)
        extra_rows += [f"### {talk['title']}", "", f"{talk['speaker']} · {talk['event']} · language `{talk['language']}`", "", f"[SideFX]({talk['sidefx']}) · [YouTube]({talk['youtube']}) · [Vimeo]({talk['vimeo']})", "", t["caption_limit"] + ".", "", "Files relative to `YACS_SIDEFX_TALKS`:", ""]
        extra_rows += [f"- `{x['path']}` — SHA-256 `{x['sha256']}`." for x in t["file_integrity"]]
        extra_rows += ["", "Scope: production architecture evidence. These talks do not supply their proprietary working node graphs. Do not claim a 1:1 implementation of unseen Embark or Ubisoft internals.", ""]
    (out / "SUPPORTING.md").write_text("\n".join(extra_rows), encoding="utf-8")
    counts = {"series": len(catalog["series"]), "parts": sum(len(x['parts']) for x in catalog['series']), "material_files": len(materials), "top_level_archives": len(mm['sources']['files']), "archives_including_nested": len(mm['archives']), "hda_libraries_inspected": sum('hda_definition_audit' in x for x in materials), "supplementary_videos": len(catalog['extras']), "supplementary_txt": sum(bool(x.get('txt')) for x in catalog['extras']), "supporting_talks": len(catalog['supporting_talks'])}
    catalog['counts'] = counts
    if counts['parts'] != tm['tutorial_part_count'] or counts['series'] != tm['series_count']:
        raise ValueError('Source count mismatch')
    save_json(out / "catalog.json", catalog)
    index += ["", "## Supporting evidence and precise metadata", "", "- [Supplementary Pegasus videos, Embark and Far Cry 5](SUPPORTING.md)", "- [Machine-readable catalog: all paths, checksums, source metadata and HDA parameter schemas](catalog.json)", "", "## Verified inventory", ""]
    index += [f"- `{k}`: **{v}**." for k, v in counts.items()]
    index += ["", "Material CRCs were checked against the extraction manifest. Original archive checksums are retained acquisition evidence; this catalog rebuild does not re-download or re-check the ZIP containers. No executable asset or auto-run project script was executed by the catalog builder.", ""]
    (out / "README.md").write_text("\n".join(index), encoding="utf-8")
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
