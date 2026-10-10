from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ci import classify_changes as classifier
from scripts.ci import unreal_ci_workspace as cache

ROOT = Path(__file__).resolve().parents[2]


class UnrealWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.name = "_unreal-build-100-1"
        self.root = self.workspace / self.name
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "fixture",
            ],
            cwd=self.root,
            check=True,
        )
        self.head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True
        ).strip()
        for name in cache.BINARY_NAMES:
            path = self.root / "Binaries/Win64" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture binary")
        self.state = {
            "SchemaVersion": 3,
            "CompilePassed": True,
            "ProofPassed": True,
            "CompileFingerprint": "compile",
            "ProofFingerprint": "proof",
            "CompileHead": self.head,
            "ProofHead": self.head,
            "EnvironmentIdentity": "environment",
            "EngineIdentity": "engine",
            "ToolchainIdentity": "toolchain",
            "EngineRoot": "fixture-engine",
            "UpdatedUtc": "2026-10-03T00:00:00Z",
        }
        self.write_state()
        self.summary = self.root / "Saved/RuntimeProof/CI/Unreal/unreal_ci_summary.json"
        self.summary.parent.mkdir(parents=True)
        self.summary.write_text(
            json.dumps(
                {
                    "Head": self.head,
                    "ExpectedHead": self.head,
                    "Failed": 0,
                    "Errors": 0,
                    "Discovered": 26,
                }
            )
        )

    def write_state(self):
        path = self.root / cache.STATE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.state), encoding="utf-8")

    def publish(self):
        cache.publish(self.workspace, self.name, self.head, "compile", "proof")

    def test_migration_recovers_verified_isolated_build_instead_of_stale_warm(self):
        warm = self.workspace / cache.WARM
        warm.mkdir()
        (warm / cache.STATE).parent.mkdir(parents=True)
        (warm / cache.STATE).write_text('{"CompilePassed": false}')
        self.assertEqual(cache.select(self.workspace), self.name)
        self.assertTrue((self.workspace / cache.POINTER).exists())

    def test_raw_checkout_drift_preserves_pointer_and_uses_fresh_build(self):
        self.publish()
        env_file = self.workspace / "github-env"
        with (
            patch.dict(os.environ, {"GITHUB_ENV": str(env_file)}),
            patch(
                "sys.argv",
                [
                    "workspace",
                    "select",
                    "--workspace",
                    str(self.workspace),
                    "--run",
                    "101-1",
                ],
            ),
            patch.object(cache, "has_untrusted_source_checkout", return_value=True),
            patch.object(cache, "cleanup") as cleanup,
        ):
            cache.main()
        cleanup.assert_not_called()
        self.assertEqual(
            env_file.read_text(), "YACS_UNREAL_WORKTREE=_unreal-build-101-1\n"
        )
        self.assertEqual(cache.select(self.workspace), self.name)
        self.assertTrue((self.root / "Binaries/Win64" / cache.BINARY_NAMES[0]).exists())
        self.assertFalse((self.workspace / "_unreal-build-101-1").exists())

    def test_detects_raw_crlf_against_git_blob_even_if_git_filters_it(self):
        from scripts.ci import materialize_unreal_cache_inputs as source

        attr = self.root / ".gitattributes"
        attr.write_bytes(b"*.cs text eol=lf\n")
        cs = self.root / "Source/Module/Module.Build.cs"
        cs.parent.mkdir(parents=True)
        cs.write_bytes(b"first\nsecond\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "source fixture",
            ],
            cwd=self.root,
            check=True,
        )
        before = (self.root / cache.STATE).read_bytes()
        with patch.object(
            source, "critical_paths", return_value=["Source/Module/Module.Build.cs"]
        ):
            self.assertFalse(cache.has_untrusted_source_checkout(self.root))
            cs.write_bytes(b"first\r\nsecond\r\n")
            original_git = source.git

            def stale_git_filter(root, *args):
                if args == ("diff", "--name-only", "-z", "HEAD"):
                    return b""
                return original_git(root, *args)

            with patch.object(source, "git", side_effect=stale_git_filter):
                self.assertTrue(cache.has_untrusted_source_checkout(self.root))
        self.assertEqual((self.root / cache.STATE).read_bytes(), before)

    def test_binary_probe_preserves_bytes_and_verified_pointer(self):
        self.publish()
        before = {
            name: (self.root / "Binaries/Win64" / name).read_bytes()
            for name in cache.BINARY_NAMES
        }
        self.assertFalse(cache.has_unwritable_binary(self.root))
        for name, data in before.items():
            self.assertEqual((self.root / "Binaries/Win64" / name).read_bytes(), data)
        self.assertEqual(cache.select(self.workspace), self.name)

    def test_locked_binary_selects_fresh_checkout_without_retiring_old_cache(self):
        self.publish()
        env_file = self.workspace / "github-env"
        original_open = Path.open
        locked = self.root / "Binaries/Win64" / cache.BINARY_NAMES[1]

        def open_with_lock(path, mode="r", *args, **kwargs):
            if path == locked and mode == "r+b":
                raise PermissionError("DLL is mapped by an exited Windows process")
            return original_open(path, mode, *args, **kwargs)

        with (
            patch.object(Path, "open", open_with_lock),
            patch.dict(os.environ, {"GITHUB_ENV": str(env_file)}),
            patch(
                "sys.argv",
                [
                    "workspace",
                    "select",
                    "--workspace",
                    str(self.workspace),
                    "--run",
                    "101-1",
                ],
            ),
            patch.object(cache, "cleanup") as cleanup,
        ):
            cache.main()
        cleanup.assert_not_called()
        self.assertEqual(
            env_file.read_text(), "YACS_UNREAL_WORKTREE=_unreal-build-101-1\n"
        )
        self.assertEqual(cache.select(self.workspace), self.name)
        self.assertEqual(cache.verified(self.root), self.state)

    def test_publication_survives_downstream_failure_and_cleanup(self):
        self.publish()
        other = self.workspace / "_unreal-build-99-1"
        shutil.copytree(self.root, other)
        # A downstream preparation failure has no authority over compile state.
        cache.cleanup(self.workspace, self.name, "101-1")
        self.assertFalse(other.exists())
        self.assertEqual(cache.select(self.workspace), self.name)
        self.assertEqual(cache.verified(self.root)["CompileHead"], self.head)
        self.assertTrue((self.root / "Binaries/Win64" / cache.BINARY_NAMES[0]).exists())

    def test_interrupted_publication_keeps_previous_pointer_and_binaries(self):
        self.publish()
        other_name = "_unreal-build-101-1"
        other = self.workspace / other_name
        shutil.copytree(self.root, other)
        with (
            patch.object(cache.os, "replace", side_effect=OSError("interrupted")),
            self.assertRaisesRegex(OSError, "interrupted"),
        ):
            cache.publish(self.workspace, other_name, self.head, "compile", "proof")
        self.assertEqual(cache.select(self.workspace), self.name)
        self.assertEqual(cache.verified(self.root), self.state)

    def test_failed_or_interrupted_build_never_publishes_green(self):
        self.publish()
        self.state["CompilePassed"] = False
        self.state["ProofPassed"] = False
        self.write_state()
        with self.assertRaisesRegex(ValueError, "not verified"):
            self.publish()
        # Preserve the invalidated candidate for resolver-driven recovery.
        self.assertEqual(cache.select(self.workspace), self.name)
        cache.cleanup(self.workspace, self.name, "101-1")
        self.assertFalse(cache.read_state(self.root)["CompilePassed"])

    def test_publication_rejects_wrong_head_fingerprints_missing_dll_and_failed_proof(
        self,
    ):
        for head, compile_fp, proof_fp in (
            ("wrong", "compile", "proof"),
            (self.head, "wrong", "proof"),
            (self.head, "compile", "wrong"),
        ):
            with (
                self.subTest(head=head, compile_fp=compile_fp, proof_fp=proof_fp),
                self.assertRaises(ValueError),
            ):
                cache.publish(self.workspace, self.name, head, compile_fp, proof_fp)
        self.summary.write_text(
            json.dumps(
                {
                    "Head": self.head,
                    "ExpectedHead": self.head,
                    "Failed": 1,
                    "Errors": 0,
                    "Discovered": 26,
                }
            )
        )
        with self.assertRaisesRegex(ValueError, "green Automation"):
            self.publish()
        (self.root / "Binaries/Win64" / cache.BINARY_NAMES[0]).unlink()
        with self.assertRaisesRegex(ValueError, "binaries missing"):
            self.publish()
        self.assertFalse((self.workspace / cache.POINTER).exists())

    def test_publication_rejects_green_summary_from_another_revision(self):
        for field in ("Head", "ExpectedHead"):
            with self.subTest(field=field):
                summary = {
                    "Head": self.head,
                    "ExpectedHead": self.head,
                    "Failed": 0,
                    "Errors": 0,
                    "Discovered": 26,
                }
                summary[field] = "older-head"
                self.summary.write_text(json.dumps(summary))
                with self.assertRaisesRegex(ValueError, "summary HEAD mismatch"):
                    self.publish()
                self.assertFalse((self.workspace / cache.POINTER).exists())

    def test_corrupt_pointer_fails_before_cleanup(self):
        path = self.workspace / cache.POINTER
        path.parent.mkdir()
        path.write_text('{"schema_version": 1, "worktree": "../escape"}')
        with self.assertRaises(ValueError):
            cache.cleanup(self.workspace, self.name, "101-1")
        self.assertTrue(self.root.exists())

    def test_links_fail_closed_and_unverified_migration_is_not_selected(self):
        self.state["CompilePassed"] = False
        self.write_state()
        self.assertEqual(cache.select(self.workspace), cache.WARM)
        link = self.root / "Binaries/escape"
        link.symlink_to(self.workspace, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "link/junction"):
            cache.select(self.workspace)

    def test_fresh_fallback_avoids_incomplete_locked_warm_directory(self):
        self.state["CompilePassed"] = False
        self.state["ProofPassed"] = False
        self.write_state()

        warm = self.workspace / cache.WARM
        warm.mkdir()
        payload = warm / "Saved/RuntimeProof/CI/Unreal/Proof/automation_editor.log"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"locked fixture")

        selected = cache.select(self.workspace, fallback="_unreal-build-101-1")

        self.assertEqual(selected, "_unreal-build-101-1")
        self.assertTrue(warm.exists())
        self.assertEqual(payload.read_bytes(), b"locked fixture")
        self.assertFalse((self.workspace / selected).exists())

    def test_incomplete_warm_checkout_is_quarantined_without_deleting_outputs(self):
        warm = self.workspace / cache.WARM
        warm.mkdir()
        payload = warm / "Intermediate/huge-cache.bin"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"preserve me")

        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "karnalooch/YetAnotherCyclingSim",
                "GITHUB_SERVER_URL": "https://github.com",
            },
        ):
            cache.prepare_checkout_directory(self.workspace, cache.WARM, "101-1")

        quarantine = (
            self.workspace / "_yacs-unreal-ci/quarantine" / f"101-1-{cache.WARM}"
        )
        self.assertFalse(warm.exists())
        self.assertEqual(
            (quarantine / "Intermediate/huge-cache.bin").read_bytes(),
            b"preserve me",
        )

    def test_checkout_origin_is_normalized_before_actions_checkout(self):
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://example.invalid/wrong/repository.git",
            ],
            cwd=self.root,
            check=True,
        )
        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "karnalooch/YetAnotherCyclingSim",
                "GITHUB_SERVER_URL": "https://github.com",
            },
        ):
            cache.prepare_checkout_directory(self.workspace, self.name, "101-1")

        self.assertEqual(
            subprocess.check_output(
                ["git", "remote", "get-url", "origin"],
                cwd=self.root,
                text=True,
            ).strip(),
            "https://github.com/karnalooch/YetAnotherCyclingSim",
        )

    def test_linked_metadata_migration_preserves_outputs_and_origin(self):
        subprocess.run(
            [
                "git",
                "remote",
                "add",
                "origin",
                "https://github.com/karnalooch/YetAnotherCyclingSim",
            ],
            cwd=self.root,
            check=True,
        )
        linked = self.workspace / "_unreal-build-102-1"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(linked), self.head],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        binary = linked / "Binaries/fixture.dll"
        binary.parent.mkdir()
        binary.write_bytes(b"preserved build")
        cache.standalone(linked)
        self.assertTrue((linked / ".git").is_dir())
        self.assertEqual(binary.read_bytes(), b"preserved build")
        self.assertEqual(
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=linked, text=True
            ).strip(),
            self.head,
        )
        self.assertEqual(
            subprocess.check_output(
                ["git", "remote", "get-url", "origin"], cwd=linked, text=True
            ).strip(),
            "https://github.com/karnalooch/YetAnotherCyclingSim",
        )
        self.assertFalse((linked / ".git/objects/info/alternates").exists())

    def test_cleanup_retains_materialized_assets_before_deletion(self):
        self.publish()
        other = self.workspace / "_unreal-build-99-1"
        shutil.copytree(self.root, other)
        asset = other / "Content/fixture.uasset"
        asset.parent.mkdir()
        asset.write_bytes(b"materialized fixture")
        cache.cleanup(self.workspace, self.name, "101-1")
        retained = (
            self.workspace
            / "_yacs-retained-lfs/cache-101-1-_unreal-build-99-1/Content/fixture.uasset"
        )
        self.assertEqual(retained.read_bytes(), b"materialized fixture")
        self.assertTrue(self.root.exists())

    def test_cleanup_quarantines_incomplete_old_build_without_deleting_outputs(self):
        self.publish()
        other = self.workspace / "_unreal-build-99-1"
        other.mkdir()
        payload = other / "Saved/RuntimeProof/CI/Unreal/Proof/automation_editor.log"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"preserve interrupted build")

        cache.cleanup(self.workspace, self.name, "101-1")

        quarantine = (
            self.workspace
            / "_yacs-unreal-ci/quarantine/101-1-_unreal-build-99-1-cleanup"
        )
        self.assertFalse(other.exists())
        self.assertEqual(
            (
                quarantine / "Saved/RuntimeProof/CI/Unreal/Proof/automation_editor.log"
            ).read_bytes(),
            b"preserve interrupted build",
        )
        self.assertTrue(self.root.exists())
        self.assertEqual(cache.select(self.workspace), self.name)

    def test_cleanup_preserves_locked_incomplete_old_build(self):
        self.publish()
        other = self.workspace / "_unreal-build-99-1"
        other.mkdir()
        payload = other / "Intermediate/locked.bin"
        payload.parent.mkdir(parents=True)
        payload.write_bytes(b"locked fixture")

        real_replace = cache.os.replace

        def locked_replace(source, destination):
            if Path(source) == other:
                raise PermissionError("fixture lock")
            return real_replace(source, destination)

        with patch.object(cache.os, "replace", side_effect=locked_replace):
            cache.cleanup(self.workspace, self.name, "101-1")

        self.assertTrue(other.exists())
        self.assertEqual(payload.read_bytes(), b"locked fixture")
        self.assertTrue(self.root.exists())
        self.assertEqual(cache.select(self.workspace), self.name)

    def test_cleanup_archives_private_lfs_objects_without_deleting_bytes(self):
        self.publish()
        other = self.workspace / "_unreal-build-99-1"
        shutil.copytree(self.root, other)
        obj = other / ".git/lfs/objects/ab/cd/payload"
        obj.parent.mkdir(parents=True)
        obj.write_bytes(b"private LFS fixture")
        cache.cleanup(self.workspace, self.name, "101-1")
        retained = (
            self.workspace
            / "_yacs-retained-lfs/cache-101-1-_unreal-build-99-1/git-lfs-objects/ab/cd/payload"
        )
        self.assertEqual(retained.read_bytes(), b"private LFS fixture")
        self.assertFalse(other.exists())

    def test_cleanup_preserves_locked_retired_verified_build(self):
        self.publish()
        other = self.workspace / "_unreal-build-99-1"
        shutil.copytree(self.root, other)

        real_rmtree = cache.shutil.rmtree

        def locked_rmtree(path, *args, **kwargs):
            if Path(path) == other:
                raise PermissionError("fixture locked pack")
            return real_rmtree(path, *args, **kwargs)

        with patch.object(cache.shutil, "rmtree", side_effect=locked_rmtree):
            cache.cleanup(self.workspace, self.name, "101-1")

        self.assertTrue(other.exists())
        self.assertTrue(self.root.exists())
        self.assertEqual(cache.select(self.workspace), self.name)

    def test_selection_retains_assets_before_checkout_and_exports_active_path(self):
        asset = self.root / "Content/fixture.uasset"
        asset.parent.mkdir()
        asset.write_bytes(b"owner asset before checkout")
        env_file = self.workspace / "github-env.txt"
        subprocess.run(
            [
                os.sys.executable,
                "-m",
                "scripts.ci.unreal_ci_workspace",
                "select",
                "--workspace",
                str(self.workspace),
                "--run",
                "101-1",
            ],
            cwd=ROOT,
            env=dict(os.environ, GITHUB_ENV=str(env_file)),
            check=True,
            capture_output=True,
            text=True,
        )
        archive = (
            self.workspace
            / "_yacs-retained-lfs"
            / f"checkout-101-1-{self.name}/Content/fixture.uasset"
        )
        self.assertEqual(archive.read_bytes(), b"owner asset before checkout")
        self.assertFalse(asset.exists())
        self.assertEqual(env_file.read_text(), f"YACS_UNREAL_WORKTREE={self.name}\n")

    @unittest.skipUnless(
        shutil.which("pwsh"), "PowerShell 7 required; executed by hosted CI"
    )
    def test_next_job_resolver_reuses_compile_but_reruns_changed_proof(self):
        # Execute the real cache resolver against a deterministic environment
        # fixture; no installed engine or compiler is impersonated as live proof.
        scripts = self.root / "scripts/ci"
        scripts.mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/ci/Resolve-YacsUnrealCiCache.ps1", scripts)
        (scripts / "Resolve-YacsUnrealBuildEnvironment.ps1").write_text(
            "function Resolve-YacsUnrealBuildEnvironment { param($ProjectPath) "
            "[pscustomobject]@{ Engine=[pscustomobject]@{ Identity='engine'; Root='fixture-engine' }; "
            "Toolchain=[pscustomobject]@{ Identity='toolchain' }; Identity='environment' } }"
        )
        self.publish()
        for compile_fp, proof_fp, expected, reason in (
            ("compile", "new-proof", "runtime", "proof-fingerprint-mismatch"),
            ("new-compile", "proof", "compile", "compile-fingerprint-mismatch"),
        ):
            self.write_state()
            name = cache.select(self.workspace)
            subprocess.run(
                [
                    "pwsh",
                    "-NoProfile",
                    "-File",
                    str(scripts / "Resolve-YacsUnrealCiCache.ps1"),
                    "-RepoRoot",
                    str(self.workspace / name),
                    "-ExpectedHead",
                    self.head,
                    "-ExpectedCompileFingerprint",
                    compile_fp,
                    "-ExpectedProofFingerprint",
                    proof_fp,
                ],
                check=True,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            evidence = json.loads(
                (
                    self.root / "Saved/RuntimeProof/CI/Unreal/cache_resolution.json"
                ).read_text(encoding="utf-8-sig")
            )
            self.assertEqual(evidence["Mode"], expected)
            self.assertEqual(evidence["Reason"], reason)
            self.assertFalse(evidence["PurgeBuildCache"])

    def test_workspace_helper_change_requires_proof_without_compile_fingerprint_drift(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "scripts/ci/unreal_ci_workspace.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("first helper revision")
            compile_before = classifier.unreal_compile_fingerprint(root)
            proof_before = classifier.unreal_proof_fingerprint(root)
            helper.write_text("second helper revision")
            self.assertEqual(
                compile_before, classifier.unreal_compile_fingerprint(root)
            )
            self.assertNotEqual(proof_before, classifier.unreal_proof_fingerprint(root))
            result = classifier.classify_paths(["scripts/ci/unreal_ci_workspace.py"])
            self.assertTrue(result.ue_code)
            self.assertEqual(result.unreal_execution_class, "runtime")

    def test_workflow_publishes_before_import_and_selects_before_checkout(self):
        workflow = (ROOT / ".github/workflows/reusable-unreal.yml").read_text()
        self.assertLess(
            workflow.index("Select persistent Unreal cache"),
            workflow.index("Checkout exact caller revision"),
        )
        self.assertLess(
            workflow.index("Record verified Unreal state"),
            workflow.index("Publish verified Unreal cache"),
        )
        self.assertLess(
            workflow.index("Publish verified Unreal cache"),
            workflow.index("Materialize verified Sa Calobra source"),
        )
        self.assertIn(
            "_unreal-build-${{ github.run_id }}-${{ github.run_attempt }}", workflow
        )
        self.assertIn("Resolve verified Unreal execution mode", workflow)


if __name__ == "__main__":
    unittest.main()
