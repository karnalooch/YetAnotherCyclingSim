"""Exercise independent lighting/provenance failures using a complete fixture."""
import copy
import unittest
from scripts.assets.gate_component230_combined import evaluate


class CombinedGateTests(unittest.TestCase):
    def setUp(self):
        thresholds = {k: {'pixels': 20, 'largest_region_pixels': 10}
                      for k in ('0.05', '0.10', '0.15')}
        self.metrics = {'baseline_readiness': {'status': 'PASS'}, 'metrics': {
            k: {'sha256': k, 'thresholds': copy.deepcopy(thresholds)}
            for k in ('baseline_lighting_only', 'candidate_lighting_only')}}
        self.audit = dict(status='PASS', displacement_limit_cm=20,
                          max_displacement_cm=19, triangles=58216,
                          nonmanifold_edges=0, folded_xy_triangles=0, vertices=2,
                          source_area_m2=3969, edge_band_radius_cm=10, max_edge_band_distance_cm=9, outside_edge_surface_unchanged=True, scope='LOCAL_EDGE_BAND_AUDIT_NOT_VISUAL_ACCEPTANCE')
        self.receipt = dict(exact_sha='revision', status='COMPONENT230_CLIFF_VISUAL_PASS',
            map_saved=False, assets_saved=False, canonical_landscape_mutation=False,
            selector_policy_mutation=False, terrain_erosion_trial=dict(
                edge_only_mesh=True, terrain_import_performed=False, derived_heightfield_modified=False, erosion=dict(enabled=False), post_erosion_mesh=True, restored=True, source_heightfield_unchanged=True,
                imported_heightfield_matches=True, combined_audit=self.audit,
                limestone_uv_projection={'world_size_m': 3, 'triangles_unchanged': True},
                mesh_export={'shape_profile': 'limestone-edge-band-only-v6',
                             'bevel_round_weight': 0.5, 'edge_band_radius_cm': 10, 'max_edge_band_distance_cm': 9,
                             'terrain_erosion': False, 'surface_relaxation': False,
                             'outside_edge_vertices_unchanged': True,
                             'movement_domain_cells': 2000,
                             'crease_preservation': False, 'smoothing_passes': 0,
                             'tangential_redistribution_passes': 0}),
            captures=[{'name': name, 'sha256': key} for name, key in (
                ('02-baseline-lighting-only', 'baseline_lighting_only'),
                ('04-candidate-lighting-only', 'candidate_lighting_only'))],
            diagnostic_captures=[{'name': 'diagnostic-limestone-pbr-lit', 'material_profile': 'limestone-pbr', 'sha256': 'pbr'}])
        for band in ('close', 'middle', 'distant'):
            for material in ('neutral', 'limestone'):
                self.receipt['diagnostic_captures'].append(dict(
                    name=f'diagnostic-review-{band}-{material}', sha256='review',
                    review_camera={'name': band}, camera_location_cm=[1, 2, 3],
                    camera_rotation_deg=[0, 0, 0], camera_fov_deg=50))

    def result(self):
        return evaluate(self.metrics, self.receipt, self.audit, 'revision')

    def test_equal_or_improved_passes_without_granting_owner_acceptance(self):
        self.assertEqual(self.result()['status'], 'PASS')
        self.assertEqual(self.result()['visual_acceptance'], 'PENDING_OWNER')

    def test_every_threshold_and_region_comparison_is_binding(self):
        for threshold in ('0.05', '0.10', '0.15'):
            for key in ('pixels', 'largest_region_pixels'):
                with self.subTest(threshold=threshold, key=key):
                    c = self.metrics['metrics']['candidate_lighting_only']['thresholds'][threshold]
                    c[key] += 1
                    self.assertEqual(self.result()['status'], 'FAIL')
                    c[key] -= 1

    def test_wrong_revision_cold_reference_and_changed_source_fail(self):
        for target, key, value in ((self.receipt, 'exact_sha', 'other'),
            (self.metrics['baseline_readiness'], 'status', 'FAIL'),
            (self.receipt['terrain_erosion_trial'], 'source_heightfield_unchanged', False)):
            old = target[key]
            target[key] = value
            self.assertEqual(self.result()['status'], 'FAIL')
            target[key] = old

    def test_mismatched_frame_hash_and_excess_displacement_fail(self):
        self.receipt['captures'][0]['sha256'] = 'different'
        self.assertEqual(self.result()['status'], 'FAIL')
        self.receipt['captures'][0]['sha256'] = 'baseline_lighting_only'
        self.audit['max_displacement_cm'] = 20.01
        self.assertEqual(self.result()['status'], 'FAIL')

    def test_changed_review_camera_fails_even_when_images_exist(self):
        self.receipt['diagnostic_captures'][-1]['camera_location_cm'] = [4, 5, 6]
        self.assertEqual(self.result()['status'], 'FAIL')

    def test_rejected_crease_profile_or_incomplete_rounding_fails(self):
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        for key, value in (('surface_relaxation', True), ('bevel_round_weight', 0), ('smoothing_passes', 24),
                           ('tangential_redistribution_passes', 3),
                           ('shape_profile', 'limestone-source-feature-flow-v2-upper-crests')):
            with self.subTest(key=key):
                old = export[key]
                export[key] = value
                self.assertEqual(self.result()['status'], 'FAIL')
                export[key] = old

    def test_wide_band_and_hidden_terrain_changes_fail(self):
        trial = self.receipt['terrain_erosion_trial']
        for target, key, value in ((trial, 'derived_heightfield_modified', True),
                (trial['erosion'], 'enabled', True),
                (trial['mesh_export'], 'max_edge_band_distance_cm', 10.01),
                (self.audit, 'outside_edge_surface_unchanged', False)):
            old = target[key]; target[key] = value
            self.assertEqual(self.result()['status'], 'FAIL')
            target[key] = old
