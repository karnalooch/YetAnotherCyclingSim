"""Admit the bounded combined neutral fixture, separately from PCGEx/owner gates."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _reshape_recipe_failures(receipt, trial, export, audit):
    """Admit the separate owner-authorized 50 cm source-backed rock recipe."""
    failures = []
    passes = export.get('smoothing_passes')
    export_triangles = export.get('triangles')
    export_shift = export.get('max_displacement_cm')
    fixed_fields = ('locked_vertex_displacement_cm', 'locked_normal_max_delta',
                    'tangential_redistribution_passes')
    if (export.get('local_smoothing') is not True
            or export.get('displacement_limit_cm') != 50
            or export.get('terrain_erosion') is not False
            or export.get('surface_relaxation') is not True
            or not all(_finite_number(export.get(k)) and export[k] == 0 for k in fixed_fields)
            or not _finite_number(passes) or not 0 < passes <= 96 or int(passes) != passes
            or not _finite_number(export_triangles) or not 0 < export_triangles <= 60000
            or int(export_triangles) != export_triangles
            or not _finite_number(export_shift) or not 0 <= export_shift <= 50.000001):
        failures.append('Bounded source-backed rock reshape recipe proof missing')
    if (receipt.get('mesh', {}).get('generator') != 'native-source-rock-reshape'
            or trial.get('reshaped_rock_mesh') is not True or trial.get('edge_only_mesh') is not False
            or trial.get('reference_source') != 'original-before-reshaping'):
        failures.append('Original-before-reshaping source provenance proof missing')
    reference_vertices = audit.get('source_reference_vertices')
    if (audit.get('source_reference') != 'original-before-reshaping'
            or audit.get('source_reference_topology_unchanged') is not True
            or not isinstance(reference_vertices, int) or isinstance(reference_vertices, bool)
            or reference_vertices <= 0
            or reference_vertices != audit.get('vertices')
            or reference_vertices != export.get('vertices')):
        failures.append('Independent original source topology provenance proof missing')
    if (trial.get('terrain_import_performed') is not False
            or trial.get('derived_heightfield_modified') is not False
            or trial.get('erosion', {}).get('enabled') is not False):
        failures.append('Rock reshape candidate changed the terrain heightfield')
    source_area, candidate_area = audit.get('source_area_m2'), audit.get('candidate_area_m2')
    shift, triangles = audit.get('max_displacement_cm'), audit.get('triangles')
    if (audit.get('status') != 'PASS'
            or audit.get('scope') != 'LOCAL_ROUNDED_DOMAIN_AUDIT_NOT_VISUAL_ACCEPTANCE'
            or audit.get('displacement_limit_cm') != 50
            or not _finite_number(shift) or not 0 <= shift <= 50.000001
            or not _finite_number(triangles) or not 0 < triangles <= 60000 or int(triangles) != triangles
            or triangles != export_triangles
            or audit.get('nonmanifold_edges') != 0 or audit.get('folded_xy_triangles') != 0
            or not _finite_number(source_area) or not _finite_number(candidate_area)
            or source_area <= 0 or abs(candidate_area-source_area) > 1e-7
            or trial.get('combined_audit') != audit):
        failures.append('Independent 50 cm rock reshape geometry audit failed')
    return failures


def evaluate(metrics: dict, receipt: dict, audit: dict, expected_sha: str) -> dict:
    failures = []
    if not expected_sha or receipt.get('exact_sha') != expected_sha:
        failures.append('Capture revision mismatch')
    if receipt.get('status') != 'COMPONENT230_CLIFF_VISUAL_PASS':
        failures.append('Capture/restoration did not pass')
    if any(receipt.get(key) is not False for key in
           ('map_saved', 'assets_saved', 'canonical_landscape_mutation', 'selector_policy_mutation')):
        failures.append('Non-persistence contract failed')
    trial = receipt.get('terrain_erosion_trial', {})
    if any(trial.get(key) is not True for key in
           ('post_erosion_mesh', 'restored', 'source_heightfield_unchanged')):
        failures.append('Combined terrain restoration/import failed')
    export = trial.get('mesh_export', {})
    if export.get('shape_profile') == 'rounded-limestone-reshape-v8':
        failures.extend(_reshape_recipe_failures(receipt, trial, export, audit))
    else:
        if (export.get('native_source_vertices_unchanged') is not True
                or export.get('native_source_normals_unchanged') is not True
                or export.get('corner_taper_length_cm') != 6
                or export.get('corner_policy') != 'fixed original corner tips with six-centimetre taper transitions'):
            failures.append('Fixed original corner vertices, normals and taper proof missing')
        profile_blend = export.get('bevel_profile_blend')
        if (export.get('bevel_linear_base_valid') is not True
                or not isinstance(profile_blend, (int, float))
                or isinstance(profile_blend, bool)
                or not math.isfinite(profile_blend) or not 0 < profile_blend <= 1):
            failures.append('Validated nonzero round profile proof missing')
        surface_bound = audit.get('max_certified_triangle_band_cm')
        if (audit.get('band_certification') != 'adaptive-lipschitz-and-convex-capsules-v1'
                or not isinstance(surface_bound, (int, float)) or isinstance(surface_bound, bool)
                or not math.isfinite(surface_bound) or not 0 <= surface_bound <= 10.000001):
            failures.append('Complete surface band certificate missing')
        if (export.get('shape_profile') != 'limestone-edge-band-only-v7'
                or export.get('smoothing_passes') != 0
                or export.get('tangential_redistribution_passes') != 0
                or export.get('terrain_erosion') is not False
                or export.get('surface_relaxation') is not False
                or export.get('bevel_round_weight') != 0.5
                or export.get('edge_band_radius_cm') != 10
                or export.get('max_edge_band_distance_cm', float('inf')) > 10.000001
                or export.get('outside_edge_vertices_unchanged') is not True):
            failures.append('Narrow edge-only limestone recipe proof missing')
        if (trial.get('edge_only_mesh') is not True or trial.get('terrain_import_performed') is not False
                or trial.get('derived_heightfield_modified') is not False
                or trial.get('erosion', {}).get('enabled') is not False):
            failures.append('Edge-only candidate changed the terrain heightfield')
        if (audit.get('status') != 'PASS' or audit.get('displacement_limit_cm') != 20
                or not 0 <= audit.get('max_displacement_cm', float('inf')) <= 20.000001
                or audit.get('edge_band_radius_cm') != 10
                or audit.get('max_edge_band_distance_cm', float('inf')) > 10.000001
                or audit.get('outside_edge_surface_unchanged') is not True
                or audit.get('native_source_vertices_unchanged') is not True
                or audit.get('complete_changed_triangle_band_certified') is not True
                or audit.get('max_certified_triangle_band_cm', float('inf')) > 10.000001
                or audit.get('scope') != 'LOCAL_EDGE_BAND_AUDIT_NOT_VISUAL_ACCEPTANCE'
                or audit.get('triangles', 60001) > 60000
                or audit.get('nonmanifold_edges') != 0 or audit.get('folded_xy_triangles') != 0
                or trial.get('combined_audit') != audit):
            failures.append('Independent narrow edge geometry audit failed')
    if metrics.get('baseline_readiness', {}).get('status') != 'PASS':
        failures.append('Neutral baseline is not ready')
    captures = {c['name']: c for c in receipt.get('captures', [])}
    for name, capture in (('baseline_lighting_only', '02-baseline-lighting-only'),
                          ('candidate_lighting_only', '04-candidate-lighting-only')):
        if metrics['metrics'][name]['sha256'] != captures.get(capture, {}).get('sha256'):
            failures.append(f'{name} image provenance mismatch')
    for threshold in ('0.05', '0.10', '0.15'):
        base = metrics['metrics']['baseline_lighting_only']['thresholds'][threshold]
        candidate = metrics['metrics']['candidate_lighting_only']['thresholds'][threshold]
        for key in ('pixels', 'largest_region_pixels'):
            if candidate[key] > base[key]:
                failures.append(f'{threshold} {key}: {candidate[key]} > {base[key]}')
    if not any(c.get('material_profile') == 'limestone-pbr' and c.get('sha256')
               for c in receipt.get('diagnostic_captures', [])):
        failures.append('Limestone material diagnostic missing')
    projection = trial.get('limestone_uv_projection', {})
    if projection.get('world_size_m') != 3 or projection.get('triangles_unchanged') is not True:
        failures.append('Limestone physical UV scale proof missing')
    diagnostics = {c['name']: c for c in receipt.get('diagnostic_captures', [])}
    for band in ('close', 'middle', 'distant'):
        pair = [diagnostics.get(f'diagnostic-review-{band}-{m}', {})
                for m in ('neutral', 'limestone')]
        if (not all(c.get('sha256') and c.get('review_camera') for c in pair)
                or any(pair[0].get(k) != pair[1].get(k) for k in
                       ('review_camera', 'camera_location_cm', 'camera_rotation_deg', 'camera_fov_deg'))):
            failures.append(f'{band} matched neutral/PBR review evidence missing')
    return dict(schema_version=1, exact_sha=expected_sha,
                status='FAIL' if failures else 'PASS', failures=failures,
                scope='LOCAL_COMBINED_TECHNICAL_ADMISSION_NOT_OWNER_ACCEPTANCE',
                visual_acceptance='PENDING_OWNER', pcgex_admission='SEPARATE_GATE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--expected-sha', required=True)
    args = parser.parse_args()
    def read(name):
        return json.loads((args.root / name).read_text(encoding='utf-8-sig'))
    result = evaluate(read('component230-cliff-metrics.json'),
                      read('component230-cliff-visual-receipt.json'),
                      read('combined-audit.json'), args.expected_sha)
    (args.root / 'combined-technical-gate.json').write_text(
        json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
