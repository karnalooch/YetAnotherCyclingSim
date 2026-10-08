"""Admit the bounded combined neutral fixture, separately from PCGEx/owner gates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


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
    if (export.get('shape_profile') != 'limestone-edge-band-only-v6'
            or export.get('smoothing_passes') != 0
            or export.get('tangential_redistribution_passes') != 0
            or export.get('terrain_erosion') is not False
            or export.get('surface_relaxation') is not False
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
