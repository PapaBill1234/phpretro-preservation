import json
import unittest
from unittest.mock import patch
from harness import tmpdir
import dashboard_state as d


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.root = tmpdir('activity-'); (self.root / 'state').mkdir()
        self.units = {'F61': {'status': 'queued', 'tokens': 10}, 'F39b': {'status': 'merged', 'tokens': 0}}

    def test_only_allowlisted_metadata_reaches_activity(self):
        secret = 'synthetic-private-content'
        rows = [{'unit': 'F61', 'role': 'reviewer', 'model': secret, 'provider': secret,
                 'outcome': secret, 'ts_end': '2026-10-09T15:00:00Z', 'total_tokens': 123,
                 'charged_tokens': 1000123, 'usage_complete': False, 'prompt': secret, 'output': secret}]
        events = [{'unit': 'F61', 'kind': 'failed', 'ts': '2026-10-09T15:00:00Z', 'reason': secret}]
        result = d.builder_activity(self.root, self.units, rows, events, [], True, 100)
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result['recent'][0]['observed_tokens'], 123)
        self.assertEqual(result['recent'][0]['charged_tokens'], 1000123)
        self.assertFalse(result['recent'][0]['usage_complete'])
        self.assertEqual(result['timeline'][0]['label'], 'Run failed')

    def test_stale_unit_counter_cannot_hide_exhausted_allowance(self):
        scope = {'units': {'F61': {'tokens': 1000000}}, 'per_unit_tokens': 800000, 'expires_at': 200}
        (self.root / 'state/canary-admission.json').write_text(json.dumps(scope))
        rows = [{'unit': 'F61', 'charged_tokens': 2690606, 'role': 'reviewer', 'ts_end': '2026-10-09T15:00:00Z'}]
        result = d.builder_activity(self.root, self.units, rows, [], [], True, 100)
        self.assertEqual(result['bounded'][0]['remaining_tokens'], 0)
        self.assertIn('exhausted', result['reason'])
        self.assertEqual(result['mode'], 'paused')

    def test_prepared_and_dead_receipts_are_not_live_workers(self):
        (self.root / 'state/receipts').mkdir()
        rec = {'runtime': 'openhands', 'status': 'prepared', 'unit': 'F61', 'worker_pid': 123}
        path = self.root / 'state/receipts/example.json'
        path.write_text(json.dumps(rec))
        with patch.object(d.worker, 'alive', return_value=False):
            self.assertEqual(d.live_workers(self.root, self.units, 100), [])
            rec['status'] = 'running'; path.write_text(json.dumps(rec))
            self.assertEqual(d.live_workers(self.root, self.units, 100), [])

    def test_run_history_is_bounded_and_excludes_reservations(self):
        row = {'unit': 'F61', 'role': 'builder', 'ts_end': '2026-10-09T15:00:00Z'}
        rows = [dict(row, record_type='reservation')] + [dict(row) for _ in range(40)]
        result = d.builder_activity(self.root, self.units, rows, [], [], False, 100)
        self.assertEqual(len(result['recent']), 20)
        self.assertEqual(result['mode'], 'idle')

    def test_nested_sdk_usage_and_completed_run_do_not_infer_review_verdict(self):
        rows = [{'unit': 'F61', 'role': 'reviewer', 'ts_end': '2026-10-09T15:00:00Z',
                 'outcome': 'other', 'rc': 0, 'usage': {'total_tokens': 264538}, 'charged_tokens': 1264538}]
        result = d.builder_activity(self.root, self.units, rows, [], [], True, 100)
        self.assertEqual(result['recent'][0]['observed_tokens'], 264538)
        self.assertEqual(result['recent'][0]['outcome'], 'completed')


if __name__ == '__main__': unittest.main()
