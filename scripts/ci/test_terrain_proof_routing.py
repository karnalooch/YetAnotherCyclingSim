from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/passo-giau-embark-terrain.yml"


def job(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^  {name}:\n.*?(?=^  [a-z_]+:|\Z)", text)
    if not match:
        raise AssertionError(f"missing job: {name}")
    return match.group(0)


class TerrainProofRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_expensive_jobs_require_explicit_admission(self) -> None:
        for name in ("prepare", "author", "validate"):
            with self.subTest(job=name):
                block = job(self.workflow, name)
                self.assertIn("needs.classify.outputs.execute_proof == 'true'", block)
        author = job(self.workflow, "author")
        self.assertIn("github.event_name == 'workflow_dispatch'", author)
        self.assertIn("github.repository == 'karnalooch/YetAnotherCyclingSim'", author)

    def test_static_push_and_requested_proof_have_distinct_concurrency(self) -> None:
        global_block = self.workflow.split("\njobs:", 1)[0]
        self.assertIn("${{ github.event_name }}", global_block)
        self.assertIn("inputs.gumball_request_id || github.ref", global_block)
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'push' }}", global_block
        )
        author = job(self.workflow, "author")
        self.assertIn("group: yacs-pcgex-author-workspace-", author)
        self.assertIn("cancel-in-progress: false", author)
        self.assertIn("queue: max", author)

    def test_target_sha_is_used_by_every_proof_consumer(self) -> None:
        for name in ("contract", "prepare", "author", "validate"):
            with self.subTest(job=name):
                block = job(self.workflow, name)
                self.assertIn("ref: ${{ needs.classify.outputs.source_sha }}", block)
                self.assertNotIn("${{ github.sha }}", block)
        self.assertEqual(self.workflow.count("ref: ${{ github.sha }}"), 1)
        self.assertIn('git for-each-ref --contains="$SOURCE_SHA"', self.workflow)
        self.assertIn("refs/remotes/origin/", self.workflow)

    def test_request_inputs_are_not_interpolated_into_shell(self) -> None:
        self.assertIn("YACS_REQUESTED_SHA: ${{ inputs.exact_sha }}", self.workflow)
        self.assertNotIn("-ExpectedHead '${{ inputs.exact_sha }}'", self.workflow)
        self.assertIn("terrain_proof_request.py --github-output", self.workflow)

    def test_compile_reuse_and_all_six_geometry_proofs_are_preserved(self) -> None:
        author = job(self.workflow, "author")
        for token in (
            "PCGEx compile cache HIT: kind=none",
            "compile-fingerprint-mismatch",
            "environment-identity-mismatch",
            "$purgeProjectBuild = $false",
            "$state.compile_passed = $false",
            "$variants = @('A','B','C','D','E')",
            "foreach ($variant in $variants)",
            "-Variant C3",
            "-Variant H",
        ):
            self.assertIn(token, author)

    def test_broker_success_artifact_is_downstream_of_deviation(self) -> None:
        author = job(self.workflow, "author")
        validate = job(self.workflow, "validate")
        self.assertNotIn("name: proof-m3-terrain-", author)
        self.assertIn("needs: [classify, prepare, author]", validate)
        self.assertLess(
            validate.index("validate_pcgex_corridor_output.py"),
            validate.index("name: proof-m3-terrain-"),
        )
        self.assertIn(
            "success() && (inputs.ride_probe_mode == 'off' || inputs.ride_probe_mode == '')",
            validate,
        )
        self.assertIn(
            "name: ride-probe-${{ github.run_id }}-${{ github.run_attempt }}", validate
        )
        self.assertIn('"human_visual_status": "PENDING"', validate)
        self.assertIn('"exact_sha": os.environ["SOURCE_SHA"]', validate)

    def test_each_attempt_has_one_isolated_evidence_root(self) -> None:
        global_block = self.workflow.split("\njobs:", 1)[0]
        self.assertIn(
            "YACS_M3_EVIDENCE_ROOT: Saved/RuntimeProof/CI/M3/PCGExCorridor/"
            "${{ github.run_id }}-${{ github.run_attempt }}",
            global_block,
        )
        author = job(self.workflow, "author")
        init = author.split("- name: Initialize isolated proof output", 1)[1].split(
            "- name: Build or reuse binaries", 1
        )[0]
        self.assertIn("$env:GITHUB_RUN_ID-$env:GITHUB_RUN_ATTEMPT", init)
        self.assertIn("if (Test-Path -LiteralPath $root)", init)
        self.assertIn("throw 'M3 run evidence already exists", init)
        self.assertNotIn("Remove-Item", init)
        self.assertNotIn("Binaries", init)
        self.assertNotIn("BuildCache", init)

    def test_authoring_and_captures_share_only_current_output(self) -> None:
        author = job(self.workflow, "author")
        self.assertIn("ArtifactRoot = '${{ env.YACS_M3_EVIDENCE_ROOT }}'", author)
        for suffix in (
            "/Traversal",
            "/Visual/{0}",
            "/Visual/C3",
            "/Visual/H",
            "/pcgex_graph_output.json",
        ):
            self.assertIn("${{ env.YACS_M3_EVIDENCE_ROOT }}" + suffix, author)
        compact = author.split("- name: Upload compact H candidate evidence", 1)[
            1
        ].split("- name: Upload PCGEx authoring evidence", 1)[0]
        self.assertIn(
            "passo-giau-m3-h-candidate-${{ github.run_id }}-${{ github.run_attempt }}",
            compact,
        )
        self.assertIn("/Visual/H/sp638_surface_h_rider_3840x2160.png", compact)
        self.assertIn("/Visual/H/surface_ownership_h_proof.json", compact)

        upload = author.split("- name: Upload PCGEx authoring evidence", 1)[1].split(
            "- name: Clean self-hosted workspace", 1
        )[0]
        self.assertIn(
            "_terrain-recovery-worktree/${{ env.YACS_M3_EVIDENCE_ROOT }}/**", upload
        )
        self.assertNotIn("_terrain-recovery-worktree/Content", upload)
        self.assertNotIn("_embark-terrain-worktree/", upload)
        self.assertNotIn("/PCGExCorridor/**", upload)
        self.assertIn("'Saved/BuildCache/PCGEx/compile-state.json'", author)

    def test_deviation_rejects_ambiguous_sources_and_execution(self) -> None:
        validate = job(self.workflow, "validate")
        self.assertIn('test "${#SOURCES[@]}" -eq 1', validate)
        self.assertIn('test "${#EXECUTIONS[@]}" -eq 1', validate)
        self.assertNotIn("-print -quit", validate)
        self.assertIn(
            "--output ${{ env.YACS_M3_EVIDENCE_ROOT }}/pcgex_corridor_deviation.json",
            validate,
        )

    def test_broker_registration_is_explicit_exact_sha_and_read_only(self) -> None:
        policy = json.loads((ROOT / ".gumball/proof-broker.json").read_text())
        proof = policy["proofs"]["m3-terrain"]
        self.assertTrue(proof["enabled"])
        self.assertFalse(proof["automatic"]["enabled"])
        self.assertFalse(proof["merge_critical"])
        self.assertEqual(proof["dispatch_ref"], "default")
        self.assertEqual(proof["inputs"]["exact_sha"], "$sha")
        self.assertEqual(proof["allowed_write_permissions"], [])
        self.assertEqual(proof["artifact_name"], "proof-$proof-$sha")
        registry = json.loads((ROOT / ".gumball/workflow-lifecycle.json").read_text())
        record = next(
            row for row in registry["workflows"] if row["file"] == WORKFLOW.name
        )
        self.assertEqual(record["state"], "BROKER-MANAGED")


if __name__ == "__main__":
    unittest.main()
