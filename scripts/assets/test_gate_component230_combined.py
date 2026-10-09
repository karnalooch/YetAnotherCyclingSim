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
                          native_source_vertices_unchanged=True,
                          complete_changed_triangle_band_certified=True,
                          band_certification='adaptive-lipschitz-and-convex-capsules-v1',
                          max_certified_triangle_band_cm=9,
                          max_displacement_cm=19, triangles=58216,
                          nonmanifold_edges=0, folded_xy_triangles=0, vertices=2,
                          source_area_m2=3969, edge_band_radius_cm=10, max_edge_band_distance_cm=9, outside_edge_surface_unchanged=True, scope='LOCAL_EDGE_BAND_AUDIT_NOT_VISUAL_ACCEPTANCE')
        self.receipt = dict(exact_sha='revision', status='COMPONENT230_CLIFF_VISUAL_PASS',
            map_saved=False, assets_saved=False, canonical_landscape_mutation=False,
            selector_policy_mutation=False, terrain_erosion_trial=dict(
                edge_only_mesh=True, terrain_import_performed=False, derived_heightfield_modified=False, erosion=dict(enabled=False), post_erosion_mesh=True, restored=True, source_heightfield_unchanged=True,
                imported_heightfield_matches=True, combined_audit=self.audit,
                limestone_uv_projection={'world_size_m': 3, 'triangles_unchanged': True},
                mesh_export={'shape_profile': 'limestone-edge-band-only-v7',
                             'native_source_vertices_unchanged': True,
                             'native_source_normals_unchanged': True,
                             'corner_taper_length_cm': 6,
                             'corner_policy': 'fixed original corner tips with six-centimetre taper transitions',
                             'bevel_linear_base_valid': True, 'bevel_profile_blend': 0.5,
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

    def test_native_corner_geometry_and_normals_must_both_be_preserved(self):
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        failure = 'Fixed original corner vertices, normals and taper proof missing'
        for key in ('native_source_vertices_unchanged', 'native_source_normals_unchanged'):
            for value in (False, None, 1, 'true'):
                with self.subTest(field=key, value=value):
                    export[key] = value
                    result = self.result()
                    self.assertEqual(result['status'], 'FAIL')
                    self.assertIn(failure, result['failures'])
                    export[key] = True
            with self.subTest(missing=key):
                del export[key]
                self.assertIn(failure, self.result()['failures'])
                export[key] = True

    def test_corner_taper_length_and_policy_cannot_be_relaxed_or_omitted(self):
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        failure = 'Fixed original corner vertices, normals and taper proof missing'
        for key, values in (
            ('corner_taper_length_cm', (0, 5.99, 6.01, 20, float('nan'), float('inf'), '6', True, None)),
            ('corner_policy', ('', 'move original corner tips', 'six-centimetre taper transitions', None)),
        ):
            expected = export[key]
            for value in values:
                with self.subTest(field=key, value=value):
                    export[key] = value
                    result = self.result()
                    self.assertEqual(result['status'], 'FAIL')
                    self.assertIn(failure, result['failures'])
                    export[key] = expected
            with self.subTest(missing=key):
                del export[key]
                self.assertIn(failure, self.result()['failures'])
                export[key] = expected

    def test_independent_vertex_identity_proof_cannot_be_replaced_by_export_claim(self):
        failure = 'Independent narrow edge geometry audit failed'
        for value in (False, None, 1, 'true'):
            with self.subTest(value=value):
                self.audit['native_source_vertices_unchanged'] = value
                result = self.result()
                self.assertEqual(result['status'], 'FAIL')
                self.assertIn(failure, result['failures'])
        del self.audit['native_source_vertices_unchanged']
        self.assertIn(failure, self.result()['failures'])

    def test_chamfer_or_unvalidated_round_profile_is_not_accepted(self):
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        for value in (None, False, True, 0, -0.1, 1.01, float('nan'), float('inf')):
            with self.subTest(blend=value):
                export['bevel_profile_blend'] = value
                self.assertEqual(self.result()['status'], 'FAIL')
        export['bevel_profile_blend'] = 0.5
        export['bevel_linear_base_valid'] = False
        self.assertEqual(self.result()['status'], 'FAIL')

    def test_vertex_only_band_proof_does_not_admit_changed_surface(self):
        self.audit['complete_changed_triangle_band_certified'] = False
        self.assertEqual(self.result()['status'], 'FAIL')
        for value in (-1, float('nan'), float('inf'), True, None):
            self.audit['max_certified_triangle_band_cm'] = value
            self.assertEqual(self.result()['status'], 'FAIL')
        self.audit['complete_changed_triangle_band_certified'] = True
        self.audit['max_certified_triangle_band_cm'] = 10.01
        self.assertEqual(self.result()['status'], 'FAIL')

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


class RockReshapeGateTests(unittest.TestCase):
    def setUp(self):
        original = CombinedGateTests()
        original.setUp()
        self.metrics, self.receipt = original.metrics, original.receipt
        self.audit = dict(status='PASS', displacement_limit_cm=50,
            source_reference='original-before-reshaping',
            source_reference_topology_unchanged=True, source_reference_vertices=29415,
            max_displacement_cm=49.5, triangles=58216, nonmanifold_edges=0,
            folded_xy_triangles=0, vertices=29415, source_area_m2=2000,
            candidate_area_m2=2000, changed_vertices=1500, locked_vertices=12000,
            scope='LOCAL_ROUNDED_DOMAIN_AUDIT_NOT_VISUAL_ACCEPTANCE')
        self.receipt['mesh'] = {'generator': 'native-source-rock-reshape'}
        trial = self.receipt['terrain_erosion_trial']
        trial.update(reshaped_rock_mesh=True, edge_only_mesh=False,
            reference_source='original-before-reshaping', combined_audit=self.audit,
            mesh_export=dict(shape_profile='rounded-limestone-reshape-v8',
                local_smoothing=True, displacement_limit_cm=50,
                max_displacement_cm=49.5, terrain_erosion=False, surface_relaxation=True,
                locked_vertex_displacement_cm=0, locked_normal_max_delta=0,
                smoothing_passes=96, tangential_redistribution_passes=0,
                triangles=58216, vertices=29415))

    def result(self):
        return evaluate(self.metrics, self.receipt, self.audit, 'revision')

    def test_owner_authorized_reshape_passes_without_old_fixed_corner_recipe(self):
        result = self.result()
        self.assertEqual(result['status'], 'PASS', result['failures'])
        self.assertEqual(result['visual_acceptance'], 'PENDING_OWNER')
        self.assertNotIn('native_source_vertices_unchanged', self.audit)
        self.assertNotIn('corner_policy', self.receipt['terrain_erosion_trial']['mesh_export'])

    def test_fifty_one_centimetre_geometry_or_export_cannot_pass(self):
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        for target in (self.audit, export):
            for key in ('max_displacement_cm', 'displacement_limit_cm'):
                with self.subTest(target='audit' if target is self.audit else 'export', field=key):
                    previous = target[key]
                    target[key] = 51
                    self.assertEqual(self.result()['status'], 'FAIL')
                    target[key] = previous

    def test_protected_vertex_or_native_normal_change_fails(self):
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        for key in ('locked_vertex_displacement_cm', 'locked_normal_max_delta'):
            with self.subTest(field=key):
                export[key] = .001
                self.assertIn('Bounded source-backed rock reshape recipe proof missing', self.result()['failures'])
                export[key] = 0

    def test_erosion_import_and_changed_frozen_heightfield_are_rejected(self):
        trial = self.receipt['terrain_erosion_trial']
        for target, key, value in (
            (trial['mesh_export'], 'terrain_erosion', True),
            (trial['erosion'], 'enabled', True),
            (trial, 'terrain_import_performed', True),
            (trial, 'derived_heightfield_modified', True),
            (trial, 'source_heightfield_unchanged', False),
        ):
            with self.subTest(field=key):
                previous = target[key]
                target[key] = value
                self.assertEqual(self.result()['status'], 'FAIL')
                target[key] = previous

    def test_stale_smoothed_reference_or_missing_source_provenance_fails(self):
        trial = self.receipt['terrain_erosion_trial']
        failure = 'Original-before-reshaping source provenance proof missing'
        for value in ('previously-smoothed-source', '', None):
            with self.subTest(reference=value):
                trial['reference_source'] = value
                self.assertIn(failure, self.result()['failures'])
        trial['reference_source'] = 'original-before-reshaping'
        for key in ('reference_source', 'reshaped_rock_mesh', 'edge_only_mesh'):
            with self.subTest(missing=key):
                previous = trial.pop(key)
                self.assertIn(failure, self.result()['failures'])
                trial[key] = previous
        self.receipt['mesh']['generator'] = 'native-source-edge-bevel-only'
        self.assertIn(failure, self.result()['failures'])

    def test_computed_original_source_proof_must_match_the_complete_mesh(self):
        failure = 'Independent original source topology provenance proof missing'
        for key, values in (
            ('source_reference', ('previously-smoothed-source', '', None)),
            ('source_reference_topology_unchanged', (False, 1, None)),
            ('source_reference_vertices', (0, -1, 29414, False, 29415.0, None)),
        ):
            previous = self.audit[key]
            for value in values:
                with self.subTest(field=key, value=value):
                    self.audit[key] = value
                    result = self.result()
                    self.assertEqual(result['status'], 'FAIL')
                    self.assertIn(failure, result['failures'])
            self.audit[key] = previous
            with self.subTest(missing=key):
                del self.audit[key]
                self.assertIn(failure, self.result()['failures'])
                self.audit[key] = previous
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        for target in (self.audit, export):
            with self.subTest(mismatched_count='audit' if target is self.audit else 'export'):
                target['vertices'] = 29416
                self.assertIn(failure, self.result()['failures'])
                target['vertices'] = 29415

    def test_pass_budget_tangential_flow_and_nonfinite_offsets_are_binding(self):
        export = self.receipt['terrain_erosion_trial']['mesh_export']
        for key, values in (
            ('smoothing_passes', (0, 97, 1.5, True, None)),
            ('tangential_redistribution_passes', (1, False, None)),
            ('max_displacement_cm', (float('nan'), float('inf'), -1, True, None)),
        ):
            previous = export[key]
            for value in values:
                with self.subTest(field=key, value=value):
                    export[key] = value
                    self.assertIn('Bounded source-backed rock reshape recipe proof missing', self.result()['failures'])
            export[key] = previous

    def test_footprint_folds_and_stale_geometry_audit_fail(self):
        failure = 'Independent 50 cm rock reshape geometry audit failed'
        for key, value in (
            ('candidate_area_m2', 2000.001), ('source_area_m2', float('nan')),
            ('folded_xy_triangles', 1), ('nonmanifold_edges', 1), ('triangles', 60001),
            ('scope', 'LOCAL_EDGE_BAND_AUDIT_NOT_VISUAL_ACCEPTANCE'),
        ):
            with self.subTest(field=key):
                previous = self.audit[key]
                self.audit[key] = value
                self.assertIn(failure, self.result()['failures'])
                self.audit[key] = previous
        self.receipt['terrain_erosion_trial']['combined_audit'] = dict(self.audit, max_displacement_cm=45)
        self.assertIn(failure, self.result()['failures'])

    def test_shared_revision_capture_material_and_restoration_proofs_still_apply(self):
        trial = self.receipt['terrain_erosion_trial']
        for target, key, value in (
            (self.receipt, 'exact_sha', 'stale-revision'),
            (trial, 'restored', False), (self.receipt, 'map_saved', True),
            (trial['limestone_uv_projection'], 'world_size_m', 6),
            (self.receipt['captures'][0], 'sha256', 'stale-frame'),
            (self.receipt['diagnostic_captures'][0], 'material_profile', 'default-material'),
        ):
            with self.subTest(field=key):
                previous = target[key]
                target[key] = value
                self.assertEqual(self.result()['status'], 'FAIL')
                target[key] = previous
