"""Exercise actual material-workflow admission without launching the home host."""

from pathlib import Path
import re
import unittest

from scripts.ci.test_sa_calobra_detail_native_workflow import enabled


ROOT = Path(__file__).resolve().parents[2]
BRANCH = "refs/heads/codex/364-road-surface-materials"
FEATURE_MARKERS = (
    "[road-crack-canary]",
    "[road-outer-blend]",
    "[road-band-controls]",
    "[road-paint-controls]",
    "[shoulder-contact]",
    "[road-cracks-source]",
    "[road-api-read]",
    "[level-editor-review]",
)


class RoadMaterialProofIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflows = {}
        cls.jobs = {}
        for kind in ("native", "source"):
            text = (
                ROOT / f".github/workflows/road-material-{kind}-proof.yml"
            ).read_text(encoding="utf-8")
            cls.workflows[kind] = text
            for name, body in re.findall(
                r"^  ([a-z][a-z0-9_]*):\n(.*?)(?=^  [a-z][a-z0-9_]*:\n|\Z)",
                text.split("\njobs:\n", 1)[1],
                re.MULTILINE | re.DOTALL,
            ):
                cls.jobs[(kind, name)] = body

    def admitted(self, job, message, **overrides):
        context = {
            "github.repository_owner": "karnalooch",
            "github.ref": BRANCH,
            "needs.await_ci.result": "success",
            "inputs.operation": "open",
        }
        context.update(overrides)
        return enabled(job, message=message, **context)

    def test_ordinary_push_and_feature_markers_do_not_start_either_proof(self):
        self.assertEqual(
            set(self.jobs),
            {
                ("native", "await_ci"),
                ("native", "baseline"),
                ("source", "asphalt"),
            },
        )
        for message in (
            "",
            "fix: tune dry asphalt",
            *FEATURE_MARKERS,
            " ".join(FEATURE_MARKERS),
        ):
            for key, job in self.jobs.items():
                with self.subTest(message=message, job=key):
                    self.assertFalse(self.admitted(job, message))

    def test_each_explicit_intent_starts_only_its_requested_workflow(self):
        for requested, marker in (
            ("native", "[road-material-proof]"),
            ("source", "[road-source-proof]"),
        ):
            for key, job in self.jobs.items():
                with self.subTest(intent=requested, job=key):
                    self.assertEqual(self.admitted(job, marker), key[0] == requested)
                    self.assertEqual(
                        self.admitted(job, marker + " " + " ".join(FEATURE_MARKERS)),
                        key[0] == requested,
                    )

    def test_marker_cannot_override_owner_repository_branch_or_event(self):
        for key, job in self.jobs.items():
            marker = (
                "[road-material-proof]" if key[0] == "native" else "[road-source-proof]"
            )
            for field, value in (
                ("github.actor", "contributor"),
                ("github.repository_owner", "contributor"),
                ("github.repository", "contributor/YetAnotherCyclingSim"),
                ("github.ref", "refs/heads/main"),
                ("github.event_name", "pull_request"),
                ("github.event_name", "workflow_dispatch"),
            ):
                with self.subTest(job=key, field=field, value=value):
                    self.assertFalse(self.admitted(job, marker, **{field: value}))

    def test_native_host_requires_successful_exact_sha_ci(self):
        hosted = self.jobs[("native", "await_ci")]
        native = self.jobs[("native", "baseline")]
        self.assertIn("    needs: await_ci", native)
        for result in ("failure", "cancelled", "skipped", "pending", ""):
            with self.subTest(result=result):
                self.assertFalse(
                    self.admitted(
                        native,
                        "[road-material-proof]",
                        **{"needs.await_ci.result": result},
                    )
                )
        self.assertIn("head_sha=${GITHUB_SHA}&event=pull_request", hosted)
        self.assertIn('.name == "CyclingSim CI" and .head_sha == $sha', hosted)
        self.assertIn('"$conclusion" == "success"', hosted)

    def test_only_admitted_host_jobs_share_the_existing_serial_lock(self):
        lock = "    concurrency:\n      group: yacs-unreal-ci-${{ github.repository }}\n      cancel-in-progress: false"
        for kind, text in self.workflows.items():
            trigger = text.split("\njobs:\n", 1)[0]
            self.assertNotIn("\nconcurrency:", trigger)
            self.assertNotIn("paths:", trigger)
            self.assertNotIn("paths-ignore:", trigger)
            self.assertIn("branches: [codex/364-road-surface-materials]", trigger)
            host = "baseline" if kind == "native" else "asphalt"
            self.assertIn(lock, self.jobs[(kind, host)])
        self.assertNotIn("concurrency:", self.jobs[("native", "await_ci")])

    def test_persistent_editor_waits_for_ci_before_taking_the_shared_host(self):
        text = (ROOT / ".github/workflows/level-editor-review.yml").read_text(
            encoding="utf-8"
        )
        waiter = text.split("  await_ci:\n", 1)[1].split("  review:\n", 1)[0]
        review = text.split("  review:\n", 1)[1]
        self.assertNotIn("concurrency:", text.split("\njobs:\n", 1)[0])
        self.assertNotIn("paths:", text.split("\njobs:\n", 1)[0])
        self.assertNotIn("concurrency:", waiter)
        self.assertIn("runs-on: ubuntu-latest", waiter)
        self.assertIn("head_sha=${GITHUB_SHA}&event=pull_request", waiter)
        self.assertIn('"$conclusion" == "success"', waiter)
        self.assertIn(
            '.name == "Blender Material Forge reference proof" and .head_sha == $sha',
            waiter,
        )
        self.assertIn('"$reference_state" == "completed"', waiter)
        self.assertIn('"$reference_conclusion" == "success"', waiter)
        self.assertIn("sleep 20\n                  continue", waiter)
        self.assertIn("    needs: await_ci", review)
        self.assertIn(
            "    concurrency:\n      group: yacs-unreal-ci-${{ github.repository }}",
            review,
        )
        self.assertTrue(self.admitted(review, "[level-editor-review]"))
        for result in ("failure", "cancelled", "skipped", "pending", ""):
            self.assertFalse(
                self.admitted(
                    review, "[level-editor-review]", **{"needs.await_ci.result": result}
                )
            )

    def test_stream_launch_keeps_explicit_intent_and_owner_context(self):
        text = (ROOT / ".github/workflows/level-editor-review.yml").read_text(
            encoding="utf-8"
        )
        waiter = text.split("  await_ci:\n", 1)[1].split("  review:\n", 1)[0]
        review = text.split("  review:\n", 1)[1]
        for job in (waiter, review):
            self.assertFalse(self.admitted(job, "ordinary update"))
            self.assertFalse(self.admitted(job, "[road-material-proof]"))
            self.assertTrue(self.admitted(job, "[level-editor-review]"))
            self.assertTrue(
                self.admitted(job, "", **{"github.event_name": "workflow_dispatch"})
            )
            for field, value in (
                ("github.actor", "contributor"),
                ("github.repository", "contributor/YetAnotherCyclingSim"),
                ("github.ref", "refs/heads/main"),
                ("github.event_name", "pull_request"),
            ):
                self.assertFalse(
                    self.admitted(job, "[level-editor-review]", **{field: value})
                )

    def stream_jobs(self):
        text = (ROOT / ".github/workflows/level-editor-review.yml").read_text(
            encoding="utf-8"
        )
        return dict(
            re.findall(
                r"^  ([a-z][a-z0-9_]*):\n(.*?)(?=^  [a-z][a-z0-9_]*:\n|\Z)",
                text.split("\njobs:\n", 1)[1],
                re.MULTILINE | re.DOTALL,
            )
        )

    def test_material_request_reuses_a_session_without_admitting_a_new_launch(self):
        jobs = self.stream_jobs()
        self.assertEqual(set(jobs), {"await_ci", "review", "material_request"})
        for operation, expected in (
            ("open", {"await_ci", "review"}),
            ("material-request", {"await_ci", "material_request"}),
            ("", set()),
            ("execute-python", set()),
        ):
            with self.subTest(operation=operation):
                active = {
                    name
                    for name, job in jobs.items()
                    if self.admitted(
                        job,
                        "",
                        **{
                            "github.event_name": "workflow_dispatch",
                            "inputs.operation": operation,
                        },
                    )
                }
                self.assertEqual(active, expected)
        self.assertFalse(
            self.admitted(jobs["material_request"], "[level-editor-review]")
        )

    def test_material_request_preserves_owner_exact_ci_and_shared_host_boundaries(self):
        job = self.stream_jobs()["material_request"]
        context = {
            "github.event_name": "workflow_dispatch",
            "inputs.operation": "material-request",
        }
        for field, value in (
            ("github.actor", "contributor"),
            ("github.repository", "contributor/YetAnotherCyclingSim"),
            ("github.ref", "refs/heads/main"),
            ("needs.await_ci.result", "failure"),
            ("needs.await_ci.result", "cancelled"),
            ("needs.await_ci.result", "skipped"),
        ):
            with self.subTest(field=field, value=value):
                self.assertFalse(self.admitted(job, "", **(context | {field: value})))
        self.assertIn("    needs: await_ci", job)
        self.assertIn("      group: yacs-unreal-ci-${{ github.repository }}", job)
        self.assertIn("      cancel-in-progress: false", job)
        self.assertIn("ref: ${{ env.TARGET_SHA }}", job)
        self.assertNotIn("Start-YacsLevelEditorStream", job)
        self.assertNotIn("Invoke-YacsUnrealCi", job)
        self.assertNotIn("git clean", job)

    def test_request_fields_are_data_and_only_a_bounded_session_token_selects_the_receipt(
        self,
    ):
        job = self.stream_jobs()["material_request"]
        run = job.split("      - name: Send one bounded request", 1)[1].split(
            "      - name: Retain only", 1
        )[0]
        self.assertIn("YACS_PREVIEW_SESSION_TOKEN: ${{ inputs.session_token }}", job)
        self.assertIn("YACS_PREVIEW_REQUEST_JSON: ${{ inputs.request_json }}", job)
        self.assertNotIn("${{ inputs.", run)
        self.assertIn("[Text.Encoding]::UTF8.GetByteCount($rawRequest) -gt 4096", run)
        self.assertIn("^[A-Za-z0-9][A-Za-z0-9_-]{0,47}$", run)
        self.assertIn("python -m scripts.ue.level_editor_material_client", run)
        self.assertIn("--session-receipt $sessionReceipt", run)
        self.assertIn("--request $requestPath", run)


if __name__ == "__main__":
    unittest.main()
