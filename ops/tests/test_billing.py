import json
import os
import unittest
from unittest.mock import patch
from harness import tmpdir
import billing
import orchestrator as o
import integrity


class BillingTests(unittest.TestCase):
    def test_normalizer_does_not_expose_private_fields_or_double_count_cache(self):
        row = billing.normalize({'request_id': 'r', 'created_at': 100, 'model_name': 'm',
                                 'prompt_tokens': 100, 'completion_tokens': 20, 'quota': 500,
                                 'ip': 'private', 'username': 'private', 'content': 'private',
                                 'other': '{"cache_tokens":80}'}, 500000)
        self.assertEqual(row['billed_usd'], .001)
        self.assertEqual(row['input_tokens_including_cache'], 100)
        self.assertEqual(row['cache_read_tokens'], 80)
        self.assertNotIn('private', json.dumps(row))
        with self.assertRaises(ValueError):
            billing.normalize({'prompt_tokens': 2, 'other': {'cache_tokens': 3}}, 500000)

    def test_snapshot_failure_and_age_fail_closed(self):
        root = tmpdir('billing-'); (root / 'state').mkdir()
        self.assertFalse(billing.summary(root, 100)['fresh'])
        (root / 'state/a6api-billing.json').write_text(json.dumps({'schema': 'phpretro.a6api-billing.v1', 'currency': 'USD', 'collected_at': 100}))
        self.assertTrue(billing.summary(root, 101)['fresh'])
        self.assertFalse(billing.summary(root, 401)['fresh'])
        (root / 'state/a6api-billing-error.json').write_text('{}')
        self.assertFalse(billing.summary(root, 101)['fresh'])

    def test_private_auth_rejects_symlinks_and_public_modes(self):
        root = tmpdir('billing-auth-'); path = root / 'auth.json'
        path.write_text('{"user_id":1,"access_token":"synthetic"}')
        path.chmod(0o600)
        self.assertEqual(billing.read_auth(path)['user_id'], 1)
        path.chmod(0o644)
        with self.assertRaises(ValueError): billing.read_auth(path)
        path.chmod(0o600); (root / 'link').symlink_to(path)
        with self.assertRaises(ValueError): billing.read_auth(root / 'link')

    def test_cash_exemption_preserves_records_and_other_providers(self):
        row = {'provider': 'custom:portdan', 'cost_estimate': None, 'charged_tokens': 1000000}
        self.assertTrue(billing.cash_exempt(row, {'portdan_cost_check': 'user-disabled'}))
        self.assertIsNone(row['cost_estimate'])
        self.assertFalse(billing.cash_exempt(row, {}))
        self.assertFalse(billing.cash_exempt({'provider': 'custom:a6api'}, {'portdan_cost_check': 'user-disabled'}))

    def test_collection_rejects_account_and_pagination_mismatch(self):
        def fetch(path, auth=None):
            if path == '/api/status': return {'quota_per_unit': 500000, 'quota_display_type': 'USD'}
            if path == '/api/user/self': return {'id': 2, 'quota': 500000}
            raise AssertionError('unexpected endpoint')
        with self.assertRaises(ValueError): billing.collect({'user_id': 1}, now=100, fetch=fetch)
        def good(path, auth=None):
            if path == '/api/status': return {'quota_per_unit': 500000, 'quota_display_type': 'USD'}
            if path == '/api/user/self': return {'id': 1, 'quota': 500000}
            if path.startswith('/api/log/self/stat?'): return {'quota': 500}
            return {'total': 0, 'items': [], 'page': 1, 'page_size': 100}
        result = billing.collect({'user_id': 1}, now=100, fetch=good)
        self.assertEqual(result['account_day_billed_usd'], .001)
        self.assertFalse(result['usage_complete'])

    def test_admission_needs_fresh_billing_for_new_unknown_a6_and_keeps_tokens(self):
        root = tmpdir('billing-admit-')
        row = {'record_type': 'run', 'run_id': 'new', 'ts_end': o.now(), 'provider': 'custom:a6api',
               'charged_tokens': 1000000, 'usage_complete': False, 'cost_estimate': None}
        integrity.append_record(root / 'runs.jsonl', row)
        state = {'day': o.now()[:10], 'tokens_today': 1000000, 'reservations': {}}
        unit = {'id': 'F99', 'tokens': 0}
        with (patch.object(o, 'paid_allowed', return_value=True), patch.object(o, 'STATE_DIR', root),
              patch.object(o, 'STATE_JSON', root / 'state.json'),
              patch.object(o.canary, 'allowance', return_value=1000),
              patch.object(o.canary, 'unknown_estimate', return_value=None)):
            with patch.object(billing, 'summary', return_value={'fresh': False}):
                with self.assertRaises(o.BudgetDenied): o.admit_paid(state, unit, 'builder')
            observation = {'fresh': True, 'day': state['day'], 'account_day_billed_usd': .07, 'account_balance_usd': 1.8}
            with patch.object(billing, 'summary', return_value=observation):
                self.assertTrue(o.admit_paid(state, unit, 'builder'))
            self.assertEqual(state['tokens_today'], 1000000)
            self.assertFalse(row['usage_complete'])
            self.assertIsNone(row['cost_estimate'])

    def test_portdan_priced_and_unknown_runs_are_both_exempt_from_cash_only(self):
        root = tmpdir('portdan-admit-')
        for index, cost in enumerate((999, None)):
            integrity.append_record(root / 'runs.jsonl', {'record_type': 'run', 'run_id': str(index),
                'provider': 'custom:portdan', 'ts_end': o.now(), 'charged_tokens': 100, 'cost_estimate': cost})
        state = {'day': o.now()[:10], 'tokens_today': 200, 'reservations': {}}
        with (patch.object(o, 'paid_allowed', return_value=True), patch.object(o, 'STATE_DIR', root),
              patch.object(o, 'STATE_JSON', root / 'state.json'),
              patch.object(o.canary, 'allowance', return_value=1000),
              patch.object(billing, 'summary', return_value={'fresh': False})):
            self.assertTrue(o.admit_paid(state, {'id': 'F99', 'tokens': 0}, 'builder'))
        self.assertEqual(state['tokens_today'], 200)


if __name__ == '__main__': unittest.main()

class AccountCallCoverageTest(unittest.TestCase):
    def test_other_keys_visible_without_changing_coding_total(self):
        now=100;queries=[]
        def fetch(path,auth=None):
            queries.append(path)
            if path=='/api/status':return {'quota_per_unit':500000,'quota_display_type':'USD'}
            if path=='/api/user/self':return {'id':1,'quota':500000}
            if '/stat?' in path:return {'quota':1000}
            return {'total':2,'page':1,'page_size':100,'items':[{'type':2,'token_name':name,'request_id':name,'created_at':50,'model_name':'sol','prompt_tokens':100,'completion_tokens':10,'quota':500} for name in ('coding','manual')]}
        result=billing.collect({'user_id':1},now,fetch)
        self.assertEqual(len(result['account_rows']),2)
        self.assertEqual(result['coding_requests'],1)
        self.assertEqual(result['coding_day_billed_usd'],.001)
        self.assertTrue(all('token_name=' not in q for q in queries))
