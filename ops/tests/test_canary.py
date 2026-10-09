import json
from unittest.mock import patch
import unittest
from harness import tmpdir
import canary
import runtime_policy


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir('canary-')
        (self.root / 'state').mkdir()
        self.data = {'schema': 'phpretro.canary.v1', 'authorized_by': 'user',
                     'authorized_at': 100, 'expires_at': 200, 'per_role_tokens': 600000,
                     'per_unit_tokens': 1800000, 'units': {'F39b': {'tokens': 10, 'attempts': 0}, 'F61': {'tokens': 0, 'attempts': 0}},
                     'historical_a6api_runs': ['old'], 'portdan_spend_override': True,
                     'a6api_sol_operator_confirmation': True}
        (self.root / 'state/canary-admission.json').write_text(json.dumps(self.data))
        self.paths = patch.object(canary, 'OPS', self.root)
        self.clock = patch.object(canary.time, 'time', return_value=150)
        self.paths.start()
        self.clock.start()
        self.addCleanup(self.paths.stop)
        self.addCleanup(self.clock.stop)

    def test_scope_attempts_allowances_and_expiration(self):
        self.assertFalse(canary.allowed({'id': 'F62'}))
        self.assertEqual(canary.allowance({'id': 'F39b', 'tokens': 10, 'attempts': 0}, 'builder', 3000000), 600000)
        self.assertEqual(canary.allowance({'id': 'F39b', 'tokens': 10, 'attempts': 1}, 'builder', 3000000), 0)
        self.assertEqual(canary.allowance({'id': 'F39b', 'tokens': 1700010, 'attempts': 1}, 'reviewer', 3000000), 100000)
        with patch.object(canary.time, 'time', return_value=201):
            self.assertFalse(canary.allowed())
            self.assertFalse(canary.operator_route('a6api', 'gpt-6.1-sol'))

    def test_exclusion_is_not_ledger_mutation_and_new_a6_unknown_stops(self):
        row = {'provider': 'custom:a6api', 'run_id': 'old', 'charged_tokens': 1000000, 'cost_estimate': None}
        self.assertEqual(canary.unknown_estimate(row, .45), .45)
        self.assertIsNone(row['cost_estimate'])
        row['run_id'] = 'new'
        self.assertIsNone(canary.unknown_estimate(row, .45))
        row['provider'] = 'custom:portdan'
        self.assertEqual(canary.unknown_estimate(row, .45), 0)
        self.assertIsNone(row['cost_estimate'])

    def test_operator_route_preserves_primary_order_without_probe_claim(self):
        with patch.object(runtime_policy, 'model_settings', return_value={'provider_order': ['a6api', 'portdan']}):
            evidence = {'provider_models': {'portdan': {'gpt-6.1-sol': {'tool_calls': True, 'usage': True, 'checked_at': 149}}}}
            self.assertEqual(runtime_policy.verified_providers('gpt-6.1-sol', evidence), ['a6api', 'portdan'])
            self.assertFalse(canary.operator_route('a6api', 'gpt-6-luna'))

    def test_terminal_canary_stops_without_expanding_scope(self):
        self.assertTrue(canary.finished({'F39b': {'status': 'merged'}, 'F61': {'status': 'todo', 'attempts': 1}}))

    def test_separate_confirmation_preserves_primary_after_canary_expiration(self):
        data={'schema':'phpretro.operator-route.v1','authorized_by':'user',
              'confirmed_at':100,'routes':{'a6api':['gpt-6.1-sol']}}
        path=self.root/'state/provider-operator-admission.json'
        path.write_text(json.dumps(data))
        with patch.object(canary.time,'time',return_value=201):
            self.assertFalse(canary.allowed())
            self.assertTrue(canary.operator_route('a6api','gpt-6.1-sol'))
            self.assertFalse(canary.operator_route('a6api','gpt-6-luna'))
            self.assertFalse(canary.operator_route('portdan','gpt-6.1-sol'))
        data['routes']['a6api'].append('gpt-6-luna');path.write_text(json.dumps(data))
        with self.assertRaises(canary.control.IntegrityError):canary.operator_route('a6api','gpt-6.1-sol')


if __name__ == '__main__':
    unittest.main()
