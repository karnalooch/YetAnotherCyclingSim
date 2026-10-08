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
        self.audit = dict(status='PASS', displacement_limit_cm=200,
                          max_displacement_cm=199, triangles=58216,
                          nonmanifold_edges=0, folded_xy_triangles=0)
        self.receipt = dict(exact_sha='revision', status='COMPONENT230_CLIFF_VISUAL_PASS',
            map_saved=False, assets_saved=False, canonical_landscape_mutation=False,
            selector_policy_mutation=False, terrain_erosion_trial=dict(
                post_erosion_mesh=True, restored=True, source_heightfield_unchanged=True,
                imported_heightfield_matches=True, combined_audit=self.audit,
                mesh_export={'shape_profile': 'limestone-source-feature-flow-v1'}),
            captures=[{'name': name, 'sha256': key} for name, key in (
                ('02-baseline-lighting-only', 'baseline_lighting_only'),
                ('04-candidate-lighting-only', 'candidate_lighting_only'))],
            diagnostic_captures=[{'material_profile': 'limestone-pbr', 'sha256': 'pbr'}])

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
        self.audit['max_displacement_cm'] = 200.01
        self.assertEqual(self.result()['status'], 'FAIL')
