"""Read-only exact-world performance admission; never dispatch hardware work."""

from __future__ import annotations

import argparse
import csv
from fnmatch import fnmatchcase
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.ci.classify_changes import classify_paths
from scripts.ops import github_ops, proof_broker

BUDGET_MS = 1000.0 / 60.0
MAX_ARCHIVE = 32 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{40}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def requirements(paths: list[str], policy: dict) -> list[str]:
    require(policy.get("schema_version") == 1, "unsupported world proof policy")
    evidence_paths = policy.get("source_evidence_paths", [])
    require(
        isinstance(evidence_paths, list)
        and all(
            isinstance(p, str)
            and p.startswith("worldgen/")
            and p.endswith(".json")
            and not any(c in p for c in "*?[]\\")
            and ".." not in p.split("/")
            for p in evidence_paths
        ),
        "source evidence paths must be exact repository JSON paths",
    )
    result = set()
    for path in paths:
        path = path.replace("\\", "/").removeprefix("./")
        if path in evidence_paths or Path(path).suffix.lower() in {
            ".md",
            ".rst",
            ".adoc",
        }:
            continue
        matches = [
            name
            for name, scenario in policy["scenarios"].items()
            if any(fnmatchcase(path, pattern) for pattern in scenario["scope_patterns"])
        ]
        result.update(matches)
        if not matches and any(
            fnmatchcase(path, p) for p in policy["unmapped_world_patterns"]
        ):
            result.add("UNMAPPED_WORLD")
    if classify_paths(paths).asset_full:
        result.add("stage3g-environment")
    return sorted(result)


def phase(event: str, draft: str) -> str:
    require(
        event in {"pull_request", "push", "schedule", "workflow_dispatch"},
        "unsupported admission event",
    )
    require(draft in {"true", "false"}, "draft must be literal true/false")
    if event == "pull_request" and draft == "true":
        return "DEFERRED_DRAFT"
    if event in {"schedule", "workflow_dispatch"}:
        return "STATIC_ONLY"
    return "REQUIRED"


def deferred_2a_performance(
    head: str, needed: list[str], policy: dict, root: Path = ROOT
) -> dict | None:
    """Recognize the owner's frozen 2A handoff, never a changed 2B world."""
    decision = policy.get("owner_deferred_2a_performance")
    if decision is None or needed != ["sa-calobra-terrain"]:
        return None
    require(
        isinstance(decision, dict)
        and decision.get("issue") == 335
        and decision.get("due_issue") == 363
        and decision.get("owner_decision_date") == "2026-10-04"
        and isinstance(decision.get("baseline_sha"), str)
        and SHA.fullmatch(decision["baseline_sha"]) is not None,
        "invalid owner-approved 2A performance deferral",
    )
    baseline = decision["baseline_sha"]
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", baseline, head], cwd=root,
        capture_output=True, text=True,
    )
    require(ancestry.returncode in {0, 1}, "cannot verify frozen 2A baseline")
    if ancestry.returncode == 1:
        return None
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", baseline, head],
        cwd=root, text=True,
    ).splitlines()
    closeout_controls = {
        ".gumball/world-proof-policy.json",
        "scripts/ci/world_proof_gate.py",
        "scripts/ci/test_world_proof_gate.py",
        "AGENTS.md",
    }
    if any(
        path not in closeout_controls
        and not (path.startswith("docs/") and path.endswith(".md"))
        for path in changed
    ):
        return None
    return {**decision, "status": "DEFERRED_TO_2B", "performance_pass": False}


def number(value, label: str, *, positive: bool = False) -> float:
    require(
        not isinstance(value, bool) and isinstance(value, (int, float)),
        f"{label}: expected number",
    )
    require(
        math.isfinite(value) and (value > 0 if positive else value >= 0),
        f"{label}: invalid timing/count",
    )
    return float(value)


def validate_evidence(
    summary: dict, csv_text: str, scenario: dict, name: str, head: str
) -> dict:
    require(
        summary.get("Head") == head, "performance receipt is not the exact target SHA"
    )
    require(
        summary.get("Result") == "PASS" and summary.get("EditorExitCode") == 0,
        "producer did not pass",
    )
    require(
        summary.get("Resolution") == "1920x1080" and summary.get("VSync") == "disabled",
        "presentation settings mismatch",
    )
    require(summary.get("ReferenceGpuMatched") is True, "reference GPU not verified")
    require(
        isinstance(summary.get("GpuNames"), list)
        and any(
            re.search(r"RTX\s*2070.*SUPER", str(gpu), re.I)
            for gpu in summary["GpuNames"]
        ),
        "RTX 2070 SUPER identity missing",
    )
    require(
        summary.get("TargetFps") == 60
        and summary.get("AllowedOverBudgetRatio") == 0.05,
        "budget policy drift",
    )
    for key in ("FrameBudgetMs", "P95FrameBudgetMs", "P95GpuBudgetMs"):
        require(
            abs(number(summary.get(key), key, positive=True) - BUDGET_MS) < 0.00001,
            "frame budget drift",
        )
    # Legacy producer has a fixed map and three fixed sectors. New producers must
    # bind generated world state and settings explicitly, not just name a map.
    if name != "stage3g-environment":
        require(summary.get("ScenarioId") == name, "scenario mismatch")
        require(summary.get("MapPackage") == scenario["map_package"], "wrong map")
        require(
            summary.get("ComponentCount") == scenario["component_count"],
            "wrong Landscape component count",
        )
        for key in ("TerrainSha256", "SettingsSha256"):
            require(
                isinstance(summary.get(key), str)
                and re.fullmatch(r"[0-9a-f]{64}", summary[key]) is not None,
                f"missing {key}",
            )
        require(
            summary.get("ScreenPercentage") == 100
            and summary.get("DynamicResolution") is False,
            "uncontrolled render resolution",
        )
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    require(
        rows and {row.get("sector") for row in rows} == set(scenario["sectors"]),
        "missing, duplicate-scope or unknown sectors",
    )
    results = []
    reported = summary.get("Sectors", [])
    require(
        isinstance(reported, list) and len(reported) == len(scenario["sectors"]),
        "invalid sector summary",
    )
    require(
        {r.get("Sector") for r in reported} == set(scenario["sectors"]),
        "duplicate or missing sector summary",
    )
    for sector in scenario["sectors"]:
        samples = [row for row in rows if row["sector"] == sector]
        require(
            len(samples) >= scenario["minimum_samples"],
            f"{sector}: insufficient samples",
        )
        timings = {}
        for domain in ("frame_ms", "game_ms", "draw_ms", "rhi_ms", "gpu_ms"):
            values = [
                number(
                    float(row[domain]),
                    f"{sector}/{domain}",
                    positive=domain == "frame_ms",
                )
                for row in samples
            ]
            timings[domain] = values
        gpu = [v for v in timings["gpu_ms"] if v > 0.01]
        require(
            len(gpu) >= scenario["minimum_gpu_samples"],
            f"{sector}: missing GPU samples",
        )

        def p95(values):
            return sorted(values)[math.floor(0.95 * (len(values) - 1))]

        frame_p95, gpu_p95 = p95(timings["frame_ms"]), p95(gpu)
        over = sum(v > BUDGET_MS for v in timings["frame_ms"]) / len(samples)
        require(
            frame_p95 <= BUDGET_MS and gpu_p95 <= BUDGET_MS and over <= 0.05,
            f"{sector}: 60 FPS budget exceeded",
        )
        record = next(r for r in reported if r["Sector"] == sector)
        require(
            record.get("Pass") is True and record.get("SampleCount") == len(samples),
            f"{sector}: summary/sample mismatch",
        )
        require(
            record.get("PositiveGpuSampleCount") == len(gpu),
            f"{sector}: GPU count mismatch",
        )
        for field, value in (
            ("FrameP95Ms", frame_p95),
            ("GpuP95Ms", gpu_p95),
            ("OverBudgetRatio", over),
        ):
            require(
                abs(number(record.get(field), field) - value) < 0.001,
                f"{sector}: forged/inconsistent {field}",
            )
        results.append(
            {
                "sector": sector,
                "samples": len(samples),
                "frame_p95_ms": frame_p95,
                "gpu_p95_ms": gpu_p95,
                "over_budget_ratio": over,
            }
        )
    return {"scenario": name, "exact_sha": head, "result": "PASS", "sectors": results}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_archive(repo: str, token: str, artifact_id: int) -> bytes:
    # Never forward the GitHub token to the signed artifact-storage URL.
    url = (
        f"https://api.github.com/repos/{repo}/actions/artifacts/{int(artifact_id)}/zip"
    )
    request = urllib.request.Request(url, headers=github_ops._headers(token))
    try:
        response = urllib.request.build_opener(NoRedirect).open(request, timeout=30)
    except urllib.error.HTTPError as exc:
        require(
            exc.code in {301, 302, 303, 307, 308}, f"artifact download HTTP {exc.code}"
        )
        location = exc.headers.get("Location", "")
        require(location.startswith("https://"), "artifact redirect must use HTTPS")
        response = urllib.request.urlopen(location, timeout=30)
    with response:
        content = response.read(MAX_ARCHIVE + 1)
    require(
        len(content) <= MAX_ARCHIVE, "performance evidence exceeds archive size limit"
    )
    return content


def archive_text(content: bytes, filename: str) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = [i for i in archive.infolist() if Path(i.filename).name == filename]
        require(len(entries) == 1, f"expected exactly one {filename}")
        info = entries[0]
        require(info.file_size <= 8 * 1024 * 1024, "receipt/sample member too large")
        return archive.read(info).decode("utf-8-sig")


def evaluate_remote(
    repo: str, token: str, head: str, name: str, scenario: dict, broker: dict
) -> dict:
    proof_id = scenario["proof_id"]
    proof = broker.get("proofs", {}).get(proof_id)
    require(
        proof is not None and proof.get("enabled") is True,
        f"{name}: producer {proof_id} is not registered; integrate its measured proof before readiness",
    )
    require(
        proof.get("artifact_name") == "proof-$proof-$sha",
        "proof artifact must bind scenario and exact SHA",
    )
    artifact_name = proof_broker.artifact_name(
        proof_id, proof, pr_number=0, branch="", sha=head, request_id=""
    )
    # Reuse the existing broker's naming/lookup contract; do not dispatch here.
    artifact = proof_broker.find_artifact(repo, token, artifact_name)
    require(
        artifact is not None,
        f"{name}: missing/expired {artifact_name}; request /gumball proof {proof_id}, then rerun CI",
    )
    run_id = artifact.get("workflow_run", {}).get("id")
    require(isinstance(run_id, int), "artifact has no workflow provenance")
    run = github_ops.request(token, "GET", f"/repos/{repo}/actions/runs/{run_id}")
    require(
        run.get("status") == "completed" and run.get("conclusion") == "success",
        "proof run is not successful",
    )
    require(
        run.get("path", "").split("@", 1)[0]
        == ".github/workflows/" + proof["workflow"],
        "artifact from wrong workflow",
    )
    require(
        run.get("event") == "workflow_dispatch", "proof did not use admitted dispatch"
    )
    require(
        run.get("head_repository", {}).get("full_name") == repo,
        "proof from another repository",
    )
    default = proof_broker.default_branch(repo, token)
    require(
        run.get("head_branch") == default,
        "proof definition must come from trusted default branch",
    )
    content = download_archive(repo, token, artifact["id"])
    summary = json.loads(archive_text(content, scenario["summary_file"]))
    result = validate_evidence(
        summary, archive_text(content, scenario["csv_file"]), scenario, name, head
    )
    result.update(run_id=run_id, artifact_id=artifact["id"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = {
        "schema_version": 1,
        "exact_sha": args.head,
        "result": "FAIL",
        "evidence": [],
    }
    try:
        require(SHA.fullmatch(args.head) is not None, "invalid target SHA")
        admission = phase(args.event, args.draft)
        policy = json.loads((ROOT / ".gumball/world-proof-policy.json").read_text())
        if admission == "STATIC_ONLY":
            paths = []
        else:
            require(SHA.fullmatch(args.base) is not None, "invalid comparison SHA")
            paths = subprocess.check_output(
                ["git", "diff", "--name-only", "--no-renames", args.base, args.head],
                cwd=ROOT,
                text=True,
            ).splitlines()
        needed = requirements(paths, policy)
        deferred = (
            deferred_2a_performance(args.head, needed, policy)
            if admission == "REQUIRED" else None
        )
        if deferred is not None:
            admission = "DEFERRED_TO_2B"
            report["owner_deferral"] = deferred
        report.update(required_scenarios=needed, phase=admission)
        if needed and admission == "REQUIRED":
            require(
                "UNMAPPED_WORLD" not in needed,
                "new world lacks a registered scenario; old-world proof cannot substitute",
            )
            repo, token = (
                os.environ.get("GITHUB_REPOSITORY", ""),
                os.environ.get("GH_TOKEN", ""),
            )
            require(
                re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) is not None
                and bool(token),
                "missing repository/read token",
            )
            broker = json.loads((ROOT / ".gumball/proof-broker.json").read_text())
            for name in needed:
                report["evidence"].append(
                    evaluate_remote(
                        repo, token, args.head, name, policy["scenarios"][name], broker
                    )
                )
        report["result"] = (
            admission
            if admission != "REQUIRED"
            else ("PASS" if needed else "NOT_REQUIRED")
        )
    except Exception as exc:
        # Do not expose signed URLs or API/token-bearing exception payloads.
        report["error"] = (
            str(exc) if isinstance(exc, ValueError) else type(exc).__name__
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(
                "## World performance admission\n\n```json\n"
                + json.dumps(report, indent=2)
                + "\n```\n"
            )
    return 1 if report["result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
