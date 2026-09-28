#!/usr/bin/env python3
"""Render and validate the lightweight YACS experiment journal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ALLOWED_STATUSES = {
    "IN_PROGRESS",
    "BLOCKED",
    "TECHNICAL_PASS",
    "VISUAL_FAIL",
    "ACCEPTED",
    "SUPERSEDED",
}
STATUS_DISPLAY = {
    "IN_PROGRESS": "IN PROGRESS",
    "BLOCKED": "BLOCKED",
    "TECHNICAL_PASS": "TECHNICAL PASS",
    "VISUAL_FAIL": "VISUAL FAIL",
    "ACCEPTED": "ACCEPTED",
    "SUPERSEDED": "SUPERSEDED",
}
REQUIRED_FIELDS = {
    "id", "date", "area", "stage", "title", "status", "hypothesis",
    "technical", "visual", "keep", "reject", "learnings", "next", "evidence",
}


def load_records(records_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in sorted(records_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        missing = sorted(REQUIRED_FIELDS - record.keys())
        if missing:
            raise ValueError(f"{path}: missing fields: {', '.join(missing)}")
        if record["status"] not in ALLOWED_STATUSES:
            raise ValueError(f"{path}: unsupported status {record['status']!r}")
        if path.stem != record["id"]:
            raise ValueError(f"{path}: filename must match id {record['id']!r}")
        if record["id"] in seen_ids:
            raise ValueError(f"{path}: duplicate experiment id {record['id']!r}")
        for field in ("technical", "visual", "keep", "reject", "learnings", "next", "evidence"):
            if not isinstance(record[field], list):
                raise ValueError(f"{path}: {field} must be a list")
        seen_ids.add(record["id"])
        records.append(record)
    return sorted(records, key=lambda item: (item["date"], item["id"]), reverse=True)


def render_index(records: list[dict[str, Any]]) -> str:
    lines = [
        "# YACS Experiment Journal",
        "",
        "<!-- Generated/validated by scripts/evidence/render_experiment_journal.py. -->",
        "",
        "This journal keeps successful, failed and superseded experiments in the repository so the team does not repeat disproven work or lose the reasoning behind accepted decisions.",
        "",
        "Heavy runtime evidence (for example 4K Unreal captures) stays in GitHub Actions artifacts. The repository keeps the durable decision record and links back to the exact PR/commit/run. A visually failed experiment can still be a successful diagnostic experiment.",
        "",
        "## Status vocabulary",
        "",
        "- `TECHNICAL PASS` — the pipeline/implementation proved what it was meant to prove; visual acceptance may still be pending.",
        "- `VISUAL FAIL` — technically valid enough to inspect, but rejected from the rider-camera visual gate.",
        "- `ACCEPTED` — accepted as the current baseline/decision.",
        "- `SUPERSEDED` — useful historical result replaced by a better path.",
        "- `BLOCKED` — experiment could not reach its intended proof.",
        "- `IN PROGRESS` — evidence is still being gathered.",
        "",
        "## Fast path for new experiments",
        "",
        "1. Add one small JSON record under `docs/experiments/records/`.",
        "2. Run `python scripts/evidence/render_experiment_journal.py`.",
        "3. Commit the record plus refreshed index with the experiment code/decision.",
        "4. Keep large screenshots/log bundles in Actions artifacts unless a human accepts one as a long-term visual baseline.",
        "",
        "The renderer is standard-library-only and intentionally not coupled to the heavy Unreal authoring workflow.",
        "",
        "## History",
        "",
        "| Date | Stage | Area | Status | Experiment record | PR | Run |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for record in records:
        pr = (
            f"[#{record['pr']}](https://github.com/karnalooch/YetAnotherCyclingSim/pull/{record['pr']})"
            if record.get("pr") else "—"
        )
        run = (
            f"[{record['run']}](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/{record['run']})"
            if record.get("run") else "—"
        )
        lines.append(
            f"| {record['date']} | {record['stage']} | {record['area']} | "
            f"**{STATUS_DISPLAY[record['status']]}** | "
            f"[{record['title']}](records/{record['id']}.json) | {pr} | {run} |"
        )
    lines.extend([
        "",
        "## Policy",
        "",
        "- Never delete a meaningful failed record merely because the next attempt works.",
        "- Prefer `SUPERSEDED` over rewriting history.",
        "- A green CI result never overrides a human rider-camera visual rejection.",
        "- Record the hypothesis, result, retained pieces, rejected pieces and next decision.",
        "- Keep physics/simulation truth separate from presentation experiments unless an explicit reviewed migration changes that contract.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records-dir", type=Path, default=Path("docs/experiments/records"))
    parser.add_argument("--index", type=Path, default=Path("docs/experiments/README.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = render_index(load_records(args.records_dir))
    if args.check:
        if not args.index.exists() or args.index.read_text(encoding="utf-8") != rendered:
            raise SystemExit("experiment journal index is stale; run scripts/evidence/render_experiment_journal.py")
        return 0

    args.index.parent.mkdir(parents=True, exist_ok=True)
    args.index.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
