"""Contract for exact-HEAD native saved road consumer execution and evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/road-material-native-proof.yml"
WRAPPER = ROOT / "scripts/ue/Invoke-YacsRoadSavedConsumer.ps1"
SCRIPT = ROOT / "scripts/ue/road_asphalt_saved_consumer.py"


def run_profile_sidecar_contract_cases(case, wrapper: Path, identity_function: str) -> None:
    """Execute production PS hash/path gates against disposable real files."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        proof = root / "proof"
        retained = root / "work/road-materials/saved-consumers" / ("a" * 40) / "123-1"
        proof.mkdir()
        retained.mkdir(parents=True)
        config = root / "workspace.json"
        config.write_text('{"schema_version":1,"work":"work"}', encoding="utf-8")
        name = "road-network-profile-diagnostic.json"
        # Exceed the manifest's 4 MiB cap, staying inside the sidecar's 8 MiB.
        # These disposable bytes are a hash fixture, never native evidence.
        raw = b'{"synthetic_fixture":"' + b"x" * (4 * 1024 * 1024) + b'"}\n'
        for parent in (proof, retained):
            (parent / name).write_bytes(raw)
        fixture = root / "input.json"
        fixture.write_text(json.dumps({
            "proof": str(proof), "retained": str(retained), "config": str(config),
            "pin": {"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)},
        }), encoding="utf-8")
        runner = root / "profile-contracts.ps1"
        runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson, [string] $IdentityFunction)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$PROFILE_DIAGNOSTIC = 'road-network-profile-diagnostic.json'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
foreach ($name in @('Assert-PlainPath', $IdentityFunction, 'Resolve-ProfileRetainedRoot', 'Get-ProfileCopies')) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw 'Missing unique production profile validation function.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$fixture = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
$work = @{ schema_version = 1; work = 'work' }
$retained = Resolve-ProfileRetainedRoot $work $fixture.config ('a' * 40) '123-1' $fixture.retained
$original = Get-ProfileCopies $fixture.pin $fixture.proof $retained
if ($original.proof.sha256 -cne $original.retained.sha256 -or $original.proof.size_bytes -le 4MB) {
    throw 'Valid distinct large diagnostic copies did not pass.'
}
foreach ($failure in @('name', 'traversal', 'extra', 'case', 'hash', 'empty', 'oversize', 'type')) {
    $pin = $fixture.pin | ConvertTo-Json | ConvertFrom-Json -AsHashtable
    switch ($failure) {
        'name' { $pin.file = 'different.json' }
        'traversal' { $pin.file = '../road-network-profile-diagnostic.json' }
        'extra' { $pin.path = $original.proof.path }
        'case' { $pin.Remove('file') | Out-Null; $pin.File = $PROFILE_DIAGNOSTIC }
        'hash' { $pin.sha256 = 'f' * 64 }
        'empty' { $pin.size_bytes = 0 }
        'oversize' { $pin.size_bytes = 8MB + 1 }
        'type' { $pin.size_bytes = [string]$pin.size_bytes }
    }
    $rejected = $false
    try { Get-ProfileCopies $pin $fixture.proof $retained | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw ('Profile pin admitted ' + $failure) }
}
foreach ($path in @($original.proof.path, $original.retained.path)) {
    $bytes = [IO.File]::ReadAllBytes($path)
    $changed = [byte[]]$bytes.Clone()
    $changed[25] = $changed[25] -bxor 1
    [IO.File]::WriteAllBytes($path, $changed)
    $rejected = $false
    try { Get-ProfileCopies $fixture.pin $fixture.proof $retained | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw 'Changed same-length diagnostic bytes passed.' }
    [IO.File]::WriteAllBytes($path, $bytes)
    $stream = [IO.File]::Open($path, [IO.FileMode]::Open, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.SetLength(8MB + 1) } finally { $stream.Dispose() }
    $rejected = $false
    try { Get-ProfileCopies $fixture.pin $fixture.proof $retained | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw 'Actual oversized diagnostic bytes passed.' }
    [IO.File]::WriteAllBytes($path, $bytes)
}
foreach ($badWork in @('../escape', '/rooted', 'work/../escape')) {
    $rejected = $false
    try {
        Resolve-ProfileRetainedRoot @{ schema_version = 1; work = $badWork } $fixture.config ('a' * 40) '123-1' $fixture.retained | Out-Null
    } catch { $rejected = $true }
    if (-not $rejected) { throw 'Profile work root escaped the pinned workspace.' }
}
$rejected = $false
try {
    Resolve-ProfileRetainedRoot $work $fixture.config ('b' * 40) '123-1' $fixture.retained | Out-Null
} catch { $rejected = $true }
if (-not $rejected) { throw 'Different retained head was admitted.' }
$rejected = $false
try { Get-ProfileCopies $fixture.pin $fixture.proof $fixture.proof | Out-Null } catch { $rejected = $true }
if (-not $rejected) { throw 'One physical path was admitted as two diagnostic copies.' }
'POWERSHELL_PROFILE_SIDECAR_CASES_PASS'
''', encoding="utf-8")
        result = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(runner), str(wrapper), str(fixture), identity_function],
            capture_output=True, text=True, check=False, timeout=60,
        )
        case.assertEqual(result.returncode, 0, result.stderr)
        case.assertIn("POWERSHELL_PROFILE_SIDECAR_CASES_PASS", result.stdout)


class RoadSavedHostContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.host = WRAPPER.read_text(encoding="utf-8")

    def test_reader_then_canary_then_saved_reopen_order(self):
        steps = (
            "Stage verified consumer and read native baseline",
            "Run isolated reversible road asphalt canary",
            "Save and fresh-reopen the isolated road asphalt consumer",
            "Retain native inventory and owned-process evidence",
        )
        offsets = [self.workflow.index(step) for step in steps]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("Invoke-YacsRoadSavedConsumer.ps1", self.workflow)
        self.assertIn("    concurrency:", self.workflow)
        self.assertIn("    needs: await_ci", self.workflow)

    def test_exact_git_and_predecessor_proofs_gate_both_editors(self):
        for field in (
            "Require-ExactSource",
            "Require-IdleHost",
            "ROAD_MATERIAL_BASELINE_READ_ONLY_COMPLETE",
            "ROAD_ASPHALT_TRANSIENT_HOST_PASS",
            "native_baseline.sha256",
            "native_canary.sha256",
            "source_scene_mutated",
            "Editor executable",
            "Assert-Identity",
            "Native save code/config differs from Git HEAD",
            "Invoke-OwnedEditor 'prepare'",
            "Invoke-OwnedEditor 'reload'",
            "Assert-NetworkManifest",
            "Assert-FreshNetworkReceipt",
            "shoulder_network_fresh_reload_verified",
            "shoulder_selected_triangle_count",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.host)

    def test_scoped_native_reopened_result_never_claims_gpu_owner_or_fps(self):
        for field in (
            "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_HOST_PASS",
            "road-asphalt-saved-prepared.json",
            "road-asphalt-saved-reloaded.json",
            "saved-road-host-receipt.json",
            "PENDING_FINAL_M3",
            "DEFERRED_AFTER_M3",
            "-NullRHI",
            "420",
            "Get-ClosedLog",
            "CreateNew",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.host)
        self.assertNotIn("save_asset(", self.host)
        self.assertNotIn("clean -fd", self.host)

    def test_exact_power_shell_lf_and_native_workflow_triggers(self):
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn(
            "scripts/ue/Invoke-YacsRoadSavedConsumer.ps1 text eol=lf",
            attributes,
        )
        self.assertNotIn(b"\r", WRAPPER.read_bytes())
        triggers = self.workflow.split("permissions:", 1)[0]
        for path in (
            "scripts/ue/road_asphalt_saved_consumer.py",
            "scripts/ue/test_road_asphalt_saved_consumer.py",
            "scripts/ue/Invoke-YacsRoadSavedConsumer.ps1",
            "scripts/ue/road_shoulder_sources.py",
            "scripts/ue/road_shoulder_network.py",
            "scripts/ue/road_material_views.py",
            "Source/YetAnotherCyclingSimEditor/Public/Diagnostics/YacsRoadMaterialInspectionLibrary.h",
            "Source/YetAnotherCyclingSimEditor/Private/Diagnostics/YacsRoadMaterialInspectionLibrary.cpp",
        ):
            self.assertIn(f"- '{path}'", triggers)
            if not Path(path).name.startswith("test_"):
                self.assertIn("'" + path + "'", self.host)

    def test_full_network_manifest_bound_is_separate_from_small_receipts(self):
        # Measured network metadata is ~1.99 MB before material/API/assets;
        # manifest alone gets 4 MiB. Prepared/fresh/host logs keep existing caps.
        self.assertIn("param([string] $Path, [long] $Limit = 2MB)", self.host)
        self.assertIn("'road-asphalt-saved-manifest.json') 4MB", self.host)
        self.assertIn("Assert-Identity $manifest.identity 4MB", self.host)
        self.assertIn("$raw.Length -gt 2MB", self.host)
        self.assertIn("road_slot_zero_and_network_outer_shoulder_ids", self.host)
        self.assertNotIn("window0112_selected_triangle_count", self.host)
        self.assertIn("$selectedTriangles = Assert-NetworkManifest", self.host)

    def test_profile_sidecar_uses_two_named_hash_only_copies_with_own_cap(self):
        for value in (
            "$PROFILE_DIAGNOSTIC = 'road-network-profile-diagnostic.json'",
            "$Pin.size_bytes -gt 8MB", "$Pin.Count -ne 3",
            "Get-Identity (Join-Path $ProofRoot $PROFILE_DIAGNOSTIC) 8MB",
            "Get-Identity (Join-Path $RetainedRoot $PROFILE_DIAGNOSTIC) 8MB",
            "Resolve-ProfileRetainedRoot $workspace.value $WorkspaceConfig",
            "$baseline.value.proof_files.workspace_config.sha256",
            "$saved.value.retained_root", "$manifest.value.road_profile_diagnostic",
            "$Fresh.road_profile_diagnostic_sha256 -cne $ProfileSha",
            "Assert-Identity $profileCopies.proof 8MB",
            "Assert-Identity $profileCopies.retained 8MB",
            "Assert-Identity $workspace.identity 2MB",
        ):
            self.assertIn(value, self.host)
        self.assertLess(self.host.index("$profileCopies = Get-ProfileCopies"),
                        self.host.index("Invoke-OwnedEditor 'reload'"))
        self.assertGreater(self.host.index("Assert-Identity $profileCopies.retained 8MB"),
                           self.host.index("Invoke-OwnedEditor 'reload'"))

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_profile_sidecar_rejects_changed_bytes_bounds_and_retained_path(self):
        run_profile_sidecar_contract_cases(self, WRAPPER, "Get-Identity")

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_powershell_saved_gate_rejects_changed_ids_roles_and_false_proof(self):
        # Pure receipt validation fixture, without any native geometry or save.
        network = {"schema_version": 2, "status": "SHOULDER_NETWORK_PREPARED",
            "support_count": 186, "material_target_count": 185, "excluded_parapet_count": 1,
            "owners": [{} for _ in range(186)], "rollback_verified": True,
            "source_vertices_topology_normals_uv_preserved": True, "original_wall_material_preserved": True,
            "excluded_parapet_unchanged": True, "whole_area_admitted": False, "performance_pass": False,
            "selected_triangle_count": 1234, "total_triangle_count": 9999}
        manifest = {"schema_version": 1, "issue": 364, "status": "SAVED_ROAD_ASPHALT_CONSUMER_PREPARED",
            "exact_sha": "a" * 40, "material_changes": "road_slot_zero_and_network_outer_shoulder_ids",
            "map_saved": True, "landscape_1024_unchanged": True, "canonical_saved": False,
            "source_scene_mutated": False, "road_slot_zero_only": False, "support_186_unchanged": False,
            "fresh_reload_verified": False, "performance_pass": False, "shoulder_network": network}
        fresh = {"status": "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS", "exact_sha": "a" * 40,
            "saved_manifest_sha256": "b" * 64, "evidence_manifest_sha256": "b" * 64,
            "road_profile_diagnostic_sha256": "e" * 64,
            "shoulder_support_count": 186, "shoulder_material_target_count": 185,
            "shoulder_selected_triangle_count": 1234, "owner_visual_status": "PENDING_FINAL_M3",
            "fresh_process": True, "shoulder_network_fresh_reload_verified": True,
            "shoulder_positions_indices_normals_uv_unchanged": True,
            "shoulder_wall_materials_unchanged": True, "road_full_buffers_unchanged": True,
            "dry_asphalt_response_verified": True,
            "new_saved_asset_bytes_unchanged": True, "road_material_reapplied": False,
            "shoulder_material_reapplied": False, "source_scene_mutated": False, "performance_pass": False}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "input.json"
            fixture.write_text(json.dumps({"manifest": manifest, "fresh": fresh}), encoding="utf-8")
            runner = root / "contracts.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
foreach ($name in @('Assert-NetworkManifest', 'Assert-FreshNetworkReceipt')) {
    $nodes = @($ast.FindAll({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq $name
    }, $true))
    if ($nodes.Count -ne 1) { throw 'Missing unique production saved validation function.' }
    . ([scriptblock]::Create($nodes[0].Extent.Text))
}
$fixture = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
$selected = Assert-NetworkManifest $fixture.manifest ('a' * 40)
if ($selected -ne 1234) { throw 'Selected count did not come from the manifest.' }
Assert-FreshNetworkReceipt $fixture.fresh ('a' * 40) ('b' * 64) $selected ('e' * 64)
foreach ($failure in @('role', 'owners', 'geometry', 'parapet', 'rollback', 'selected_type', 'admission')) {
    $manifest = $fixture.manifest | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'role' { $manifest.shoulder_network.material_target_count = 186 }
        'owners' { $manifest.shoulder_network.owners = $manifest.shoulder_network.owners[0..184] }
        'geometry' { $manifest.shoulder_network.source_vertices_topology_normals_uv_preserved = $false }
        'parapet' { $manifest.shoulder_network.excluded_parapet_unchanged = $false }
        'rollback' { $manifest.shoulder_network.rollback_verified = $false }
        'selected_type' { $manifest.shoulder_network.selected_triangle_count = '1234' }
        'admission' { $manifest.shoulder_network.whole_area_admitted = $true }
    }
    $rejected = $false
    try { Assert-NetworkManifest $manifest ('a' * 40) | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production manifest gate admitted ' + $failure) }
}
foreach ($failure in @('head', 'manifest', 'profile', 'selected', 'supports', 'reapply', 'reload',
                       'buffers', 'walls', 'road_buffers', 'asphalt', 'performance')) {
    $fresh = $fixture.fresh | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'head' { $fresh.exact_sha = 'd' * 40 }
        'manifest' { $fresh.evidence_manifest_sha256 = 'd' * 64 }
        'profile' { $fresh.road_profile_diagnostic_sha256 = 'f' * 64 }
        'selected' { $fresh.shoulder_selected_triangle_count += 1 }
        'supports' { $fresh.shoulder_support_count = 185 }
        'reapply' { $fresh.shoulder_material_reapplied = $true }
        'reload' { $fresh.shoulder_network_fresh_reload_verified = $false }
        'buffers' { $fresh.shoulder_positions_indices_normals_uv_unchanged = $false }
        'walls' { $fresh.shoulder_wall_materials_unchanged = $false }
        'road_buffers' { $fresh.road_full_buffers_unchanged = $false }
        'asphalt' { $fresh.dry_asphalt_response_verified = $false }
        'performance' { $fresh.performance_pass = $true }
    }
    $rejected = $false
    try { Assert-FreshNetworkReceipt $fresh ('a' * 40) ('b' * 64) $selected ('e' * 64) } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production fresh gate admitted ' + $failure) }
}
'POWERSHELL_SAVED_CONTRACT_CASES_PASS'
''', encoding="utf-8")
            result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(WRAPPER), str(fixture)],
                capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("POWERSHELL_SAVED_CONTRACT_CASES_PASS", result.stdout)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_real_powershell_parser_accepts_owned_host_wrapper(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "parse.ps1"
            fixture.write_text(
                """
param([string] $Script)
$tokens = $null
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $Script, [ref] $tokens, [ref] $errors
) | Out-Null
if ($errors.Count) { throw ($errors.Message -join "\u0060n") }
""",
                encoding="utf-8",
            )
            process = subprocess.run(
                ["pwsh", "-NoProfile", "-File", str(fixture), str(WRAPPER)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stderr)

    def test_frozen_recipe_checkout_preserves_raw_bytes_with_windows_autocrlf(self):
        relative = "worldgen/terrain/benchmarks/sa_calobra/world_data/frozen_road_recipe_2026-10-04.json"
        source = (ROOT / relative).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*arguments):
                result = subprocess.run(["git", "-C", str(root), *arguments],
                    capture_output=True, timeout=30, check=False)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                return result.stdout
            git("init", "-q")
            git("config", "core.autocrlf", "true")
            git("config", "core.safecrlf", "false")
            (root / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(source)
            control = root / "unmatched.json"
            control.write_bytes(b'{"control": true}\n')
            git("add", ".gitattributes", relative, "unmatched.json")
            path.unlink()
            control.unlink()
            git("checkout-index", "--", relative, "unmatched.json")
            self.assertIn(b"\r\n", control.read_bytes())
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(git("hash-object", "--no-filters", relative).strip(),
                             git("rev-parse", ":" + relative).strip())


if __name__ == "__main__":
    unittest.main()
