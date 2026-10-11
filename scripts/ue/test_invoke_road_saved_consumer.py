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

    def test_outer_variant_is_explicit_in_save_reload_and_both_workflow_calls(self):
        for value in (
            "[switch] $OuterTerrainCanary", "YACS_ROAD_OUTER_TERRAIN_CANARY = $outerTerrainSetting",
            "YACS_ROAD_PAINT_COVERAGE_OWNED = $null",
            "Assert-NetworkManifest $manifest.value $ExpectedHead ([bool]$OuterTerrainCanary)",
            "Assert-OuterTerrainReceipt $manifest.value $saved.value $fresh.value ([bool]$OuterTerrainCanary)",
            "outer_terrain_physical_contact_verified = $false", "outer_terrain_normal_response_verified = $false",
            "'scripts/ue/build_sa_calobra_whole_map_master.py'", "'scripts/ue/sa_calobra_whole_map_prep.py'",
        ):
            self.assertIn(value, self.host)
        self.assertEqual(self.workflow.count("-OuterTerrainCanary:"), 2)
        self.assertEqual(self.workflow.count("'[road-outer-blend]'"), 2)
        self.assertIn("-PaintCoverage:", self.workflow)

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell 7 unavailable")
    def test_actual_outer_gate_binds_five_owners_fresh_materials_and_original_uv_prefix(self):
        # Receipt-only fixture: native source, shader and mesh behavior is tested
        # separately. This runs the actual host gate on altered evidence.
        labels = [f"YACS_PERSIST_SUPPORT_{index:03d}" for index in (18, 73, 93, 112, 182)]
        prefix = "/Game/Generated/YACS/RoadAsphaltConsumer/ShoulderNetwork/"
        base = prefix + "MI_ShoulderNetwork.MI_ShoulderNetwork"
        assets = {role: prefix + "TerrainBlend/" + name + "." + name for role, name in (
            ("master", "M_ShoulderNetworkTerrain"), ("instance", "MI_ShoulderNetworkTerrain"))}
        textures = {"WeightTex": "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/T_WholeMapWeights.T_WholeMapWeights"}
        for role in ("DryGrass", "ForestLitter", "ExposedRock", "DryMineral", "Scree"):
            for channel in ("BaseColor", "Normal"):
                name = role + channel + "Tex"
                textures[name] = "/Game/Generated/YACS/TextureMaterialPrep/" + name + "." + name
        statistics = {name: 0 for name in (
            "num_samplers", "num_pixel_shader_instructions", "num_pixel_texture_samples",
            "num_vertex_shader_instructions", "num_vertex_texture_samples", "num_virtual_texture_samples",
            "num_uv_scalars", "num_interpolator_scalars")}
        source = {"landscape_component_count": 1024, "texture_objects": textures,
                  "instance": "/Game/Generated/YACS/SaCalobra/WholeMapPreparation/MI_SaCalobraWholeMapPreparation.MI_SaCalobraWholeMapPreparation"}
        material = {"schema_version": 3, "status": "SHOULDER_MATERIAL_CREATED_REVIEW_PENDING",
                    "outer_terrain_enabled": True, "assets": assets, "terrain_source": source,
                    "native_statistics": statistics, "native_compile_errors": [],
                    "unique_texture_objects": 17, "gpu_compile_verified": False}
        outer = {"owner_labels": labels, "selection": "source_owned_outer_top_faces", "uv_channel": 1,
                 "uv0_stage_witness_required": True, "physical_contact_verified": False, "material": material}
        owners = []
        for index in range(186):
            label = f"YACS_PERSIST_SUPPORT_{index:03d}"
            owner = {"support_label": label, "edge_attribute": None}
            if label in labels:
                before = {"uv_set_count": 0, "vertex_count": 54, "triangle_count": 56,
                          "positions_indices_blake3": "a" * 64, "triangle_corner_normals_uv_blake3": "b" * 64}
                inner = {**before, "uv_set_count": 1, "triangle_corner_normals_uv_blake3": "c" * 64}
                after = {**inner, "uv_set_count": 2, "triangle_corner_normals_uv_blake3": "d" * 64}
                owner.update(material_target=True, selected_triangle_count=4,
                    before_mesh=before, after_mesh=after,
                    edge_attribute={"channel": 0, "uv0_preserved": True, "inner_stage_mesh": inner,
                        "original_normals_uv_prefix_blake3": "b" * 64, "set_triangle_count": 4,
                        "uv_blake3": "e" * 64, "outer_attribute": {
                            "channel": 1, "original_normals_uv_prefix_blake3": "c" * 64,
                            "set_triangle_count": 4, "unset_nonselected_triangles": True, "uv_blake3": "f" * 64}})
            owners.append(owner)
        loaded = {"status": "SHOULDER_MATERIALS_NATIVE_READBACK_VERIFIED", "read_only": True,
                  "base_instance": base, "outer_terrain_enabled": True, "outer_instance": assets["instance"],
                  "outer_owner_labels": labels, "outer_texture_objects": textures,
                  "outer_native_statistics": {**statistics, "num_samplers": 7},
                  "landscape_instance": source["instance"], "landscape_component_count": 1024,
                  **{name: False for name in ("outer_material_reapplied", "outer_geometry_reapplied",
                      "outer_gpu_compile_verified", "physical_contact_verified", "normal_response_visual_verified",
                      "owner_visual_pass", "performance_pass")}}
        good = {"manifest": {"outer_terrain_enabled": True, "shoulder_network": {
                    "schema_version": 4, "owners": owners, "outer_terrain": outer,
                    "material": {"assets": {"instance": base}}}},
                "prepared": {"outer_terrain_enabled": True},
                "fresh": {"outer_terrain_enabled": True, "outer_terrain_fresh_reload_verified": True,
                    "outer_material_reapplied": False, "outer_geometry_reapplied": False,
                    "outer_terrain_readback": loaded}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "input.json"
            fixture.write_text(json.dumps(good), encoding="utf-8")
            runner = root / "outer-contract.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
$nodes = @($ast.FindAll({param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -ceq 'Assert-OuterTerrainReceipt'
}, $true))
if ($nodes.Count -ne 1) { throw 'Missing unique production outer material gate.' }
. ([scriptblock]::Create($nodes[0].Extent.Text))
$good = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
# Zero saved statistics and different fresh numbers are real observations,
# never a reason to claim GPU readiness or reject an otherwise valid save.
Assert-OuterTerrainReceipt $good.manifest $good.prepared $good.fresh $true
foreach ($failure in @('mode', 'prepared_mode', 'fresh_mode', 'fresh_bool', 'reload', 'reapply',
    'schema', 'labels', 'label_order', 'selection', 'channel', 'physical', 'master', 'instance',
    'texture', 'texture_count', 'landscape', 'landscape_count', 'read_only', 'owner_acceptance',
    'gpu_acceptance', 'saved_gpu_acceptance', 'compile_error', 'stat_type', 'stat_negative', 'stat_missing',
    'stat_virtual_saved', 'stat_virtual_fresh',
    'owner_order', 'uv_prefix', 'outer_prefix', 'uv0_claim', 'outer_count', 'wall_uv',
    'position', 'topology', 'final_uv_count', 'missing_hash', 'extra_owner')) {
    $data = $good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    $network = $data.manifest.shoulder_network
    $outer = $network.outer_terrain
    $loaded = $data.fresh.outer_terrain_readback
    $owner = $network.owners[18]
    switch ($failure) {
        'mode' { $data.manifest.outer_terrain_enabled = $false }
        'prepared_mode' { $data.prepared.outer_terrain_enabled = $false }
        'fresh_mode' { $data.fresh.outer_terrain_enabled = $false }
        'fresh_bool' { $data.fresh.outer_terrain_enabled = 'true' }
        'reload' { $data.fresh.outer_terrain_fresh_reload_verified = $false }
        'reapply' { $data.fresh.outer_geometry_reapplied = $true }
        'schema' { $network.schema_version = 3 }
        'labels' { $outer.owner_labels[0] = 'YACS_PERSIST_SUPPORT_022' }
        'label_order' { $outer.owner_labels = @($outer.owner_labels[4..0]) }
        'selection' { $outer.selection = 'nearest_world_point' }
        'channel' { $outer.uv_channel = 0 }
        'physical' { $outer.physical_contact_verified = $true }
        'master' { $outer.material.assets.master += '_foreign' }
        'instance' { $loaded.outer_instance += '_foreign' }
        'texture' { $loaded.outer_texture_objects.WeightTex += '_foreign' }
        'texture_count' { $loaded.outer_texture_objects.Remove('WeightTex') | Out-Null }
        'landscape' { $loaded.landscape_instance += '_foreign' }
        'landscape_count' { $loaded.landscape_component_count = 1023 }
        'read_only' { $loaded.read_only = $false }
        'owner_acceptance' { $loaded.owner_visual_pass = $true }
        'gpu_acceptance' { $loaded.outer_gpu_compile_verified = $true }
        'saved_gpu_acceptance' { $outer.material.gpu_compile_verified = $true }
        'compile_error' { $outer.material.native_compile_errors = @('failed') }
        'stat_type' { $loaded.outer_native_statistics.num_samplers = $true }
        'stat_negative' { $loaded.outer_native_statistics.num_samplers = -1 }
        'stat_missing' { $loaded.outer_native_statistics.Remove('num_samplers') | Out-Null }
        'stat_virtual_saved' { $outer.material.native_statistics.num_virtual_texture_samples = 1 }
        'stat_virtual_fresh' { $loaded.outer_native_statistics.num_virtual_texture_samples = 1 }
        'owner_order' { $network.owners[14].support_label = 'YACS_PERSIST_SUPPORT_013' }
        'uv_prefix' { $owner.edge_attribute.original_normals_uv_prefix_blake3 = 'a' * 64 }
        'outer_prefix' { $owner.edge_attribute.outer_attribute.original_normals_uv_prefix_blake3 = 'a' * 64 }
        'uv0_claim' { $owner.edge_attribute.uv0_preserved = $false }
        'outer_count' { $owner.edge_attribute.outer_attribute.set_triangle_count = 3 }
        'wall_uv' { $owner.edge_attribute.outer_attribute.unset_nonselected_triangles = $false }
        'position' { $owner.after_mesh.positions_indices_blake3 = 'f' * 64 }
        'topology' { $owner.edge_attribute.inner_stage_mesh.triangle_count += 1 }
        'final_uv_count' { $owner.after_mesh.uv_set_count = 3 }
        'missing_hash' { $owner.edge_attribute.outer_attribute.uv_blake3 = $null }
        'extra_owner' { $network.owners[22].edge_attribute = @{ outer_attribute = @{} } }
    }
    $rejected = $false
    try { Assert-OuterTerrainReceipt $data.manifest $data.prepared $data.fresh $true } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production outer material gate admitted ' + $failure) }
}
$disabled = @{ outer_terrain_enabled = $false; shoulder_network = @{schema_version = 3} }
$fresh = @{outer_terrain_enabled = $false; outer_terrain_fresh_reload_verified = $false;
    outer_material_reapplied = $false; outer_geometry_reapplied = $false; outer_terrain_readback = $null}
Assert-OuterTerrainReceipt $disabled $disabled $fresh $false
foreach ($failure in @('schema', 'unexpected_variant', 'unexpected_readback')) {
    $data = $disabled | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    $observed = $fresh | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'schema' { $data.shoulder_network.schema_version = 4 }
        'unexpected_variant' { $data.shoulder_network.outer_terrain = @{} }
        'unexpected_readback' { $observed.outer_terrain_readback = @{} }
    }
    $rejected = $false
    try { Assert-OuterTerrainReceipt $data $data $observed $false } catch { $rejected = $true }
    if (-not $rejected) { throw ('Disabled outer material mode admitted ' + $failure) }
}
'POWERSHELL_OUTER_TERRAIN_CONTRACT_CASES_PASS'
''', encoding="utf-8")
            result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(WRAPPER), str(fixture)],
                capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("POWERSHELL_OUTER_TERRAIN_CONTRACT_CASES_PASS", result.stdout)

    def test_artifact_path_remains_inside_owned_checkout_on_preflight_failure(self):
        upload = self.workflow.split("- name: Retain native inventory and owned-process evidence", 1)[1]
        self.assertIn(
            "path: ${{ github.workspace }}/rm-${{ github.run_id }}-${{ github.run_attempt }}"
            "/Saved/RuntimeProof/RoadMaterialBaseline/${{ github.run_id }}-${{ github.run_attempt }}/**",
            upload,
        )
        # The preflight may fail before it can export GITHUB_ENV. An empty
        # variable must never turn artifact retention into the drive-root /**.
        self.assertNotIn("path: ${{ env.YACS_ROAD_NATIVE_PROOF }}/**", upload)

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
        self.assertIn("road_slot_zero_network_outer_shoulder_ids_and_edge_uv", self.host)
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
        network = {"schema_version": 3, "status": "SHOULDER_NETWORK_PREPARED",
            "support_count": 186, "material_target_count": 185, "excluded_parapet_count": 1,
            "owners": [{} for _ in range(186)], "rollback_verified": True,
            "source_vertices_topology_normals_uv_prefix_preserved": True,
            "material_edge_uv_appended": True, "material_edge_uv_channel": 0,
            "original_wall_material_preserved": True,
            "excluded_parapet_unchanged": True, "whole_area_admitted": False, "performance_pass": False,
            "selected_triangle_count": 1234, "total_triangle_count": 9999}
        manifest = {"schema_version": 1, "issue": 364, "status": "SAVED_ROAD_ASPHALT_CONSUMER_PREPARED",
            "exact_sha": "a" * 40, "material_changes": "road_slot_zero_network_outer_shoulder_ids_and_edge_uv",
            "map_saved": True, "landscape_1024_unchanged": True, "canonical_saved": False,
            "source_scene_mutated": False, "road_slot_zero_only": False, "support_186_unchanged": False,
            "outer_terrain_enabled": False,
            "fresh_reload_verified": False, "performance_pass": False, "shoulder_network": network}
        fresh = {"status": "ROAD_ASPHALT_SAVED_CONSUMER_FRESH_RELOAD_PASS", "exact_sha": "a" * 40,
            "saved_manifest_sha256": "b" * 64, "evidence_manifest_sha256": "b" * 64,
            "road_profile_diagnostic_sha256": "e" * 64,
            "shoulder_support_count": 186, "shoulder_material_target_count": 185,
            "shoulder_selected_triangle_count": 1234, "owner_visual_status": "PENDING_FINAL_M3",
            "fresh_process": True, "shoulder_network_fresh_reload_verified": True,
            "shoulder_positions_indices_normals_original_uv_prefix_unchanged": True,
            "shoulder_material_edge_uv_fresh_reload_verified": True,
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
foreach ($failure in @('role', 'owners', 'geometry', 'edge_uv', 'edge_channel', 'parapet', 'rollback', 'selected_type', 'admission')) {
    $manifest = $fixture.manifest | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'role' { $manifest.shoulder_network.material_target_count = 186 }
        'owners' { $manifest.shoulder_network.owners = $manifest.shoulder_network.owners[0..184] }
        'geometry' { $manifest.shoulder_network.source_vertices_topology_normals_uv_prefix_preserved = $false }
        'edge_uv' { $manifest.shoulder_network.material_edge_uv_appended = $false }
        'edge_channel' { $manifest.shoulder_network.material_edge_uv_channel = 1 }
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
                       'buffers', 'edge_reload', 'walls', 'road_buffers', 'asphalt', 'performance')) {
    $fresh = $fixture.fresh | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    switch ($failure) {
        'head' { $fresh.exact_sha = 'd' * 40 }
        'manifest' { $fresh.evidence_manifest_sha256 = 'd' * 64 }
        'profile' { $fresh.road_profile_diagnostic_sha256 = 'f' * 64 }
        'selected' { $fresh.shoulder_selected_triangle_count += 1 }
        'supports' { $fresh.shoulder_support_count = 185 }
        'reapply' { $fresh.shoulder_material_reapplied = $true }
        'reload' { $fresh.shoulder_network_fresh_reload_verified = $false }
        'buffers' { $fresh.shoulder_positions_indices_normals_original_uv_prefix_unchanged = $false }
        'edge_reload' { $fresh.shoulder_material_edge_uv_fresh_reload_verified = $false }
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
    def test_actual_edge_marking_gate_requires_requested_native_and_fresh_proofs(self):
        # Synthetic policy fixture only: the production PS function must reject
        # changed authority, stale source witnesses and incomplete actor sets.
        paint = {"schema_version": 1, "status": "EDGE_MARKINGS_CREATED_REVIEW_PENDING",
            "plan_sha256": "a" * 64, "actors": [{} for _ in range(370)],
            "geometry": {"counts": {"source_owner_count": 186, "pavement_owner_count": 185,
                "excluded_parapet_count": 1, "mesh_count": 370}},
            "source_correspondence": {"native_source_witness_sha256": "b" * 64},
            **{key: True for key in ("material_packages_saved", "render_flags_verified_before_append",
                "full_source_buffers_preserved", "native_surface_correspondence_verified",
                "all_marking_buffers_verified")},
            **{key: False for key in ("source_geometry_changed", "source_materials_changed",
                "collision_enabled", "cast_shadow", "affects_navigation", "physics_authored",
                "map_saved", "owner_visual_pass", "performance_pass")}}
        loaded = {"schema_version": 1, "status": "EDGE_MARKINGS_FRESH_READBACK_VERIFIED",
            "plan_sha256": paint["plan_sha256"], "actor_count": 370,
            "normal_contract": "normalized_barycentric_native_road_split_corner_normals",
            "native_source_witness_sha256": "b" * 64,
            **{key: True for key in ("all_marking_buffers_verified", "full_source_buffers_preserved",
                "read_only", "caller_fresh_process_and_saved_bytes_required")},
            "owner_visual_pass": False, "performance_pass": False}
        good = {"manifest": {"edge_markings_enabled": True, "edge_markings": paint},
            "prepared": {"edge_markings_enabled": True},
            "fresh": {"edge_markings_enabled": True, "edge_marking_readback": loaded,
                "edge_marking_material_reapplied": False, "edge_marking_geometry_reapplied": False,
                "edge_markings_fresh_reload_verified": True}}
        disabled = {"manifest": {"edge_markings_enabled": False},
            "prepared": {"edge_markings_enabled": False},
            "fresh": {"edge_markings_enabled": False, "edge_marking_readback": None,
                "edge_marking_material_reapplied": False, "edge_marking_geometry_reapplied": False,
                "edge_markings_fresh_reload_verified": False}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "input.json"
            fixture.write_text(json.dumps({"good": good, "disabled": disabled}), encoding="utf-8")
            runner = root / "edge-contracts.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $InputJson)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Wrapper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
$nodes = @($ast.FindAll({ param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $node.Name -ceq 'Assert-EdgeMarkingReceipt'
}, $true))
if ($nodes.Count -ne 1) { throw 'Missing unique production edge marking gate.' }
. ([scriptblock]::Create($nodes[0].Extent.Text))
$fixture = Get-Content -LiteralPath $InputJson -Raw | ConvertFrom-Json -AsHashtable -Depth 40
function Check($row, [bool]$enabled) {
    Assert-EdgeMarkingReceipt $row.manifest $row.prepared $row.fresh $enabled
}
Check $fixture.good $true
Check $fixture.disabled $false
foreach ($failure in @('request', 'prepare_lane', 'fresh_lane', 'lane_type', 'actors', 'owners',
                       'parapet', 'plan', 'witness', 'normals', 'packages', 'native', 'buffers',
                       'collision', 'shadow', 'source', 'material_reapply', 'geometry_reapply',
                       'read_only', 'fresh', 'owner', 'performance')) {
    $data = $fixture.good | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    $requested = $true
    switch ($failure) {
        'request' { $requested = $false }
        'prepare_lane' { $data.prepared.edge_markings_enabled = $false }
        'fresh_lane' { $data.fresh.edge_markings_enabled = $false }
        'lane_type' { $data.manifest.edge_markings_enabled = 'true' }
        'actors' { $data.manifest.edge_markings.actors = $data.manifest.edge_markings.actors[0..368] }
        'owners' { $data.manifest.edge_markings.geometry.counts.pavement_owner_count = 186 }
        'parapet' { $data.manifest.edge_markings.geometry.counts.excluded_parapet_count = 0 }
        'plan' { $data.fresh.edge_marking_readback.plan_sha256 = 'c' * 64 }
        'witness' { $data.fresh.edge_marking_readback.native_source_witness_sha256 = 'c' * 64 }
        'normals' { $data.fresh.edge_marking_readback.normal_contract = 'invented_up' }
        'packages' { $data.manifest.edge_markings.material_packages_saved = $false }
        'native' { $data.manifest.edge_markings.native_surface_correspondence_verified = $false }
        'buffers' { $data.fresh.edge_marking_readback.all_marking_buffers_verified = $false }
        'collision' { $data.manifest.edge_markings.collision_enabled = $true }
        'shadow' { $data.manifest.edge_markings.cast_shadow = $true }
        'source' { $data.manifest.edge_markings.source_geometry_changed = $true }
        'material_reapply' { $data.fresh.edge_marking_material_reapplied = $true }
        'geometry_reapply' { $data.fresh.edge_marking_geometry_reapplied = $true }
        'read_only' { $data.fresh.edge_marking_readback.read_only = $false }
        'fresh' { $data.fresh.edge_markings_fresh_reload_verified = $false }
        'owner' { $data.manifest.edge_markings.owner_visual_pass = $true }
        'performance' { $data.fresh.edge_marking_readback.performance_pass = $true }
    }
    $rejected = $false
    try { Check $data $requested } catch { $rejected = $true }
    if (-not $rejected) { throw ('Production marking gate admitted ' + $failure) }
}
foreach ($unexpected in @('geometry', 'readback')) {
    $data = $fixture.disabled | ConvertTo-Json -Depth 40 | ConvertFrom-Json -AsHashtable -Depth 40
    if ($unexpected -ceq 'geometry') { $data.manifest.edge_markings = @{} }
    else { $data.fresh.edge_marking_readback = @{} }
    $rejected = $false
    try { Check $data $false } catch { $rejected = $true }
    if (-not $rejected) { throw 'Disabled lane admitted unexpected marking evidence.' }
}
'POWERSHELL_EDGE_MARKING_CASES_PASS'
''', encoding="utf-8")
            result = subprocess.run(["pwsh", "-NoProfile", "-File", str(runner), str(WRAPPER), str(fixture)],
                capture_output=True, text=True, check=False, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("POWERSHELL_EDGE_MARKING_CASES_PASS", result.stdout)

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

    @unittest.skipUnless(shutil.which("pwsh"), "PowerShell is required to execute the native host gate")
    def test_crack_canary_host_rejects_incomplete_sources_and_false_fresh_claims(self):
        crack = {
            "schema_version": 1, "status": "LOCAL_CRACKS_CREATED_NORMAL_REVIEW_PENDING",
            "plan_sha256": "a" * 64, "actors": [{}, {}],
            "owned_asset_paths": [f"/Game/Generated/YACS/RoadAsphaltConsumer/Cracks/A{i}.A{i}" for i in range(11)],
            "imports": {"texture_count": 8, "sources": {
                "status": "ROAD_CRACK_SOURCE_BYTES_AUTHENTICATED", "verified_map_count": 80,
                "verified_process_count": 16, "pins": {
                    "exact_sha": "07ebafad08bce8bc227089901cb46785079fefda", "run": "38102423216", "attempt": "1",
                    "source_proof": {"sha256": "bdfb2b889a8c8ed48960518909f497d822b5c34e7d4631a890368de984310afb"}}}},
            "source_correspondence": {"native_source_witness_sha256": "b" * 64},
            **dict.fromkeys(("asset_packages_saved", "full_source_and_existing_paint_buffers_preserved",
                "all_crack_buffers_verified", "native_surface_correspondence_verified",
                "render_flags_verified_before_append", "world_normal_canary_required"), True),
            **dict.fromkeys(("source_geometry_changed", "source_materials_changed", "existing_paint_changed",
                "collision_enabled", "cast_shadow", "affects_navigation", "physics_authored", "map_saved",
                "normal_space_verified", "owner_visual_pass", "performance_pass"), False),
        }
        loaded = {"schema_version": 1, "status": "LOCAL_CRACKS_FRESH_READBACK_VERIFIED_NORMAL_REVIEW_PENDING",
            "plan_sha256": "a" * 64, "actor_count": 2, "native_source_witness_sha256": "b" * 64,
            **dict.fromkeys(("full_source_and_existing_paint_buffers_preserved", "all_crack_buffers_verified",
                "read_only", "caller_fresh_process_and_saved_bytes_required", "world_normal_canary_required"), True),
            **dict.fromkeys(("normal_space_verified", "owner_visual_pass", "performance_pass"), False)}
        fixture = {"manifest": {"crack_canary_enabled": True, "crack_canary": crack},
            "prepared": {"crack_canary_enabled": True}, "fresh": {
                "crack_canary_enabled": True, "crack_readback": loaded,
                "crack_canary_fresh_reload_verified": True, "crack_material_reapplied": False,
                "crack_geometry_reapplied": False, "edge_marking_readback": {"aggregate_owner": "local_crack_canary"}}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "synthetic-host-fixture.json"
            source.write_text(json.dumps(fixture), encoding="utf-8")
            runner = root / "crack-host-contract.ps1"
            runner.write_text(r'''
param([string] $Wrapper, [string] $Fixture)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($Wrapper,[ref]$tokens,[ref]$errors)
if ($errors.Count) { throw ($errors.Message -join '; ') }
$nodes=@($ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -ceq 'Assert-CrackCanaryReceipt'},$true))
if ($nodes.Count -ne 1) { throw 'Missing unique production crack host gate.' }
. ([scriptblock]::Create($nodes[0].Extent.Text))
$raw=Get-Content -LiteralPath $Fixture -Raw
$good=$raw | ConvertFrom-Json -AsHashtable
Assert-CrackCanaryReceipt $good.manifest $good.prepared $good.fresh $true
foreach($change in @('source','run','hash','map_count','process_count','texture_count','missing_actor','duplicate_asset',
                     'unsaved','buffers','white','read_only','reapply','normal_pass','performance','boolean_string')) {
    $data=$raw | ConvertFrom-Json -AsHashtable
    $crack=$data.manifest.crack_canary; $fresh=$data.fresh
    switch($change) {
        'source' { $crack.imports.sources.pins.exact_sha='f'*40 }
        'run' { $crack.imports.sources.pins.run='1' }
        'hash' { $crack.imports.sources.pins.source_proof.sha256='f'*64 }
        'map_count' { $crack.imports.sources.verified_map_count=79 }
        'process_count' { $crack.imports.sources.verified_process_count=15 }
        'texture_count' { $crack.imports.texture_count=7 }
        'missing_actor' { $crack.actors=@(@{}) }
        'duplicate_asset' { $crack.owned_asset_paths[1]=$crack.owned_asset_paths[0] }
        'unsaved' { $crack.asset_packages_saved=$false }
        'buffers' { $fresh.crack_readback.all_crack_buffers_verified=$false }
        'white' { $fresh.edge_marking_readback.aggregate_owner='unchecked' }
        'read_only' { $fresh.crack_readback.read_only=$false }
        'reapply' { $fresh.crack_material_reapplied=$true }
        'normal_pass' { $fresh.crack_readback.normal_space_verified=$true }
        'performance' { $crack.performance_pass=$true }
        'boolean_string' { $crack.asset_packages_saved='true' }
    }
    $rejected=$false
    try { Assert-CrackCanaryReceipt $data.manifest $data.prepared $fresh $true } catch { $rejected=$true }
    if(-not $rejected){throw ('Crack host gate accepted '+$change)}
}
$disabled=@{crack_canary_enabled=$false}
$fresh=@{crack_canary_enabled=$false;crack_canary_fresh_reload_verified=$false;crack_readback=$null;
          crack_material_reapplied=$false;crack_geometry_reapplied=$false}
Assert-CrackCanaryReceipt $disabled $disabled $fresh $false
$disabled.crack_canary=@{}
$rejected=$false
try { Assert-CrackCanaryReceipt $disabled $disabled $fresh $false } catch { $rejected=$true }
if(-not $rejected){throw 'Disabled crack lane admitted an unexpected receipt.'}
''', encoding="utf-8")
            result = subprocess.run([shutil.which("pwsh"), "-NoProfile", "-File", str(runner), str(WRAPPER), str(source)],
                                    text=True, capture_output=True, timeout=30, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
