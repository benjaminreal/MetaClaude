"""Offline tests for openrouter_spend.py: no network call, no real key, temporary files only.

Run from the project root:
  python3 -m unittest tools/test_openrouter_spend.py
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import openrouter_spend as spend

AGENT_KEY = 'sk-or-v1-agent-test-only'
OTHER_KEY = 'sk-or-v1-opencode-test-only'
MASKED_LABEL = 'sk-or-v1-abc...xyz'


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def key_payload(**data):
    return FakeResponse(json.dumps({'data': {'label': MASKED_LABEL, **data}}).encode())


def run_main(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = spend.main(list(args))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


class SpendCheckTests(unittest.TestCase):
    """Runs main() end to end with urlopen mocked per key."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.auth = Path(self.tmp.name) / 'auth.json'
        self.patches = [
            mock.patch.dict(os.environ, {'OPENROUTER_AGENT_KEY': AGENT_KEY, 'OPENROUTER_AGENT_ALLOWANCE_USD': ''}),
            mock.patch.object(spend, 'AGENT_KEY_FILE', Path(self.tmp.name) / 'missing.key'),
            mock.patch.object(spend, 'OPENCODE_AUTH', self.auth),
        ]
        for p in self.patches:
            p.start()
        self.responses = {}

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def fake_urlopen(self, request, timeout):
        self.assertEqual(request.full_url, spend.KEY_URL)
        self.assertFalse(request.headers, 'the key must only be sent as an unredirected header')
        key = request.unredirected_hdrs['Authorization'].split(' ', 1)[1]
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response

    def check(self):
        with mock.patch('urllib.request.urlopen', side_effect=self.fake_urlopen):
            code, out, _ = run_main()
        self.assertNotIn('sk-or', out)  # neither the key nor the masked label is ever printed
        return code, json.loads(out)

    def test_ok_with_daily_hard_cap(self):
        self.responses[AGENT_KEY] = key_payload(usage_daily=0.2, limit=0.5, limit_remaining=0.3, limit_reset='daily')
        code, out = self.check()
        self.assertEqual((code, out['status'], out['remaining_today_usd'], out['keys_counted']), (0, 'ok', 0.3, 1))
        self.assertTrue(out['hard_cap_enforced_by_openrouter'] and out['key_limit_within_policy'])
        self.assertNotIn('warning', out)

    def test_key_limit_above_policy_warns(self):
        self.responses[AGENT_KEY] = key_payload(usage_daily=0.1, limit=1, limit_remaining=0.9, limit_reset='daily')
        code, out = self.check()
        self.assertEqual((code, out['remaining_today_usd'], out['key_limit_within_policy']), (0, 0.4, False))
        self.assertIn('overshoot', out['warning'])

    def test_no_key_limit_warns_advisory(self):
        self.responses[AGENT_KEY] = key_payload(usage_daily=0, limit=None, limit_remaining=None)
        code, out = self.check()
        self.assertEqual((code, out['hard_cap_enforced_by_openrouter']), (0, False))
        self.assertIn('advisory', out['warning'])

    def test_key_limit_remaining_caps_the_allowance(self):
        self.responses[AGENT_KEY] = key_payload(usage_daily=0.1, limit=0.15, limit_remaining=0.05, limit_reset='daily')
        self.assertEqual(self.check()[1]['remaining_today_usd'], 0.05)

    def test_exhausted_and_rounding_to_zero_exit_3(self):
        for used in (0.5, 0.4999999):
            with self.subTest(used=used):
                self.responses[AGENT_KEY] = key_payload(usage_daily=used, limit=0.5, limit_remaining=0.5 - used, limit_reset='daily')
                code, out = self.check()
                self.assertEqual((code, out['status'], out['remaining_today_usd']), (3, 'allowance_exhausted', 0))

    def test_different_opencode_key_counts_against_allowance(self):
        self.auth.write_text(json.dumps({'openrouter': {'type': 'api', 'key': OTHER_KEY}}))
        self.responses[AGENT_KEY] = key_payload(usage_daily=0.1, limit=1, limit_remaining=0.9, limit_reset='daily')
        self.responses[OTHER_KEY] = key_payload(usage_daily=0.35)
        code, out = self.check()
        self.assertEqual((code, out['used_today_usd'], out['remaining_today_usd'], out['keys_counted']), (0, 0.45, 0.05, 2))

    def test_same_opencode_key_is_counted_once(self):
        self.auth.write_text(json.dumps({'openrouter': {'type': 'api', 'key': AGENT_KEY}}))
        self.responses[AGENT_KEY] = key_payload(usage_daily=0.1, limit=0.5, limit_remaining=0.4, limit_reset='daily')
        self.assertEqual(self.check()[1]['keys_counted'], 1)

    def test_untrustworthy_answers_exit_2(self):
        cases = {
            'missing usage': key_payload(limit=1),
            'text usage': key_payload(usage_daily='0.1'),
            'infinite usage': FakeResponse(b'{"data": {"usage_daily": Infinity}}'),
            'null data': FakeResponse(b'{"data": null}'),
            'not json': FakeResponse(b'<html>'),
            'http error': spend.urllib.error.HTTPError(spend.KEY_URL, 401, 'Unauthorized', {}, None),
            'bad key header': ValueError(f'Invalid header value b"Bearer {AGENT_KEY}"'),
            'timeout': TimeoutError(),
        }
        for name, response in cases.items():
            with self.subTest(name):
                self.responses[AGENT_KEY] = response
                code, out = self.check()
                self.assertEqual(code, 2)
                self.assertNotIn(out['status'], ('ok', 'allowance_exhausted'))

    def test_failing_opencode_key_lookup_exits_2(self):
        self.auth.write_text(json.dumps({'openrouter': {'key': OTHER_KEY}}))
        self.responses[AGENT_KEY] = key_payload(usage_daily=0, limit=0.5, limit_remaining=0.5, limit_reset='daily')
        self.responses[OTHER_KEY] = TimeoutError()
        self.assertEqual(self.check()[0], 2)
        self.auth.write_text('not json')
        self.responses[AGENT_KEY] = key_payload(usage_daily=0, limit=0.5, limit_remaining=0.5, limit_reset='daily')
        self.assertEqual(self.check()[1]['status'], 'key_unavailable')

    def test_invalid_allowance_override_exits_2(self):
        self.responses[AGENT_KEY] = key_payload(usage_daily=0, limit=None, limit_remaining=None)
        for raw in ('inf', 'nan', '-1', '0', 'lots'):
            with self.subTest(raw=raw), mock.patch.dict(os.environ, {'OPENROUTER_AGENT_ALLOWANCE_USD': raw}):
                code, out = self.check()
                self.assertEqual((code, out['status']), (2, 'invalid_allowance'))

    def test_valid_allowance_override(self):
        self.responses[AGENT_KEY] = key_payload(usage_daily=0.25, limit=None, limit_remaining=None)
        with mock.patch.dict(os.environ, {'OPENROUTER_AGENT_ALLOWANCE_USD': '1'}):
            self.assertEqual(self.check()[1]['remaining_today_usd'], 0.75)

    def test_no_agent_key_exits_2_without_network(self):
        with mock.patch.dict(os.environ, {'OPENROUTER_AGENT_KEY': ''}), \
                mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network expected')):
            code, out, _ = run_main()
        self.assertEqual((code, json.loads(out)['status']), (2, 'no_agent_key'))

    def test_record_fields_without_record_are_rejected_before_any_request(self):
        with mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network expected')):
            code, _, err = run_main('--route', 'local', '--purpose', 'x')
        self.assertEqual(code, 2)
        self.assertIn('only apply with --record', err)


class RecordTests(unittest.TestCase):
    BASE = ('--record', '--harness', 'opencode', '--model', 'qwen/qwen3', '--purpose', 'summarise public docs', '--private', 'no')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / 'sub' / 'agent-runs.jsonl'
        self.env = mock.patch.dict(os.environ, {'AGENT_RUN_LOG': str(self.log)})
        self.env.start()
        self.no_network = mock.patch('urllib.request.urlopen', side_effect=AssertionError('no network expected'))
        self.no_network.start()

    def tearDown(self):
        self.no_network.stop()
        self.env.stop()
        self.tmp.cleanup()

    def entries(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_metered_run_is_appended_with_owner_only_mode(self):
        code, out, _ = run_main(*self.BASE, '--route', 'openrouter-allowance', '--requests', '3', '--cost', '0.0123')
        self.assertEqual((code, json.loads(out)['status']), (0, 'recorded'))
        [entry] = self.entries()
        self.assertEqual((entry['route'], entry['requests'], entry['cost_usd'], entry['private_data']),
                         ('openrouter-allowance', 3, 0.0123, False))
        self.assertNotIn('policy_violation', entry)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)

    def test_existing_log_is_tightened_to_owner_only(self):
        self.log.parent.mkdir(parents=True)
        self.log.touch(mode=0o644)
        os.chmod(self.log, 0o644)
        run_main(*self.BASE, '--route', 'local')
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)

    def test_unknown_cost_and_count_stay_unknown(self):
        run_main(*self.BASE, '--route', 'approved-metered', '--cost', 'unknown')
        self.assertEqual((self.entries()[0]['cost_usd'], self.entries()[0]['requests']), ('unknown', 'unknown'))

    def test_runs_append_rather_than_overwrite(self):
        run_main(*self.BASE, '--route', 'local')
        run_main(*self.BASE, '--route', 'subscription')
        self.assertEqual([e['route'] for e in self.entries()], ['local', 'subscription'])
        self.assertEqual(self.entries()[0]['cost_usd'], 'not_metered')

    def test_private_data_on_non_private_route_is_recorded_and_flagged(self):
        code, out, _ = run_main(*self.BASE[:-1], 'yes', '--route', 'openrouter-free')
        self.assertEqual(code, 0)
        self.assertIn('tell the owner', json.loads(out)['warning'])
        self.assertIn('openrouter-free', self.entries()[0]['policy_violation'])

    def test_private_data_on_approved_route_is_not_flagged(self):
        run_main(*self.BASE[:-1], 'yes', '--route', 'approved-metered', '--cost', '0.2')
        self.assertNotIn('policy_violation', self.entries()[0])

    def test_unwritable_log_exits_2(self):
        with mock.patch.dict(os.environ, {'AGENT_RUN_LOG': self.tmp.name}):  # a directory
            code, out, _ = run_main(*self.BASE, '--route', 'local')
        self.assertEqual((code, json.loads(out)['status']), (2, 'error'))

    def test_invalid_records_are_rejected_and_not_written(self):
        cases = [
            [*self.BASE, '--route', 'openrouter-allowance'],                       # metered without cost
            [*self.BASE, '--route', 'openrouter-allowance', '--cost', '-1'],        # negative cost
            [*self.BASE, '--route', 'openrouter-allowance', '--cost', 'nan'],       # not a finite cost
            [*self.BASE, '--route', 'openrouter-allowance', '--cost', 'cheap'],     # not a number
            [*self.BASE, '--route', 'local', '--cost', '0.01'],                     # cost on unmetered route
            [*self.BASE, '--route', 'paid'],                                        # unknown route
            [*self.BASE, '--route', 'local', '--requests', '-2'],                   # negative count
            ['--record', '--harness', 'codex', '--route', 'local'],                 # missing fields
            [*self.BASE[:6], 'x' * 201, '--private', 'no', '--route', 'local'],     # purpose too long
        ]
        for args in cases:
            with self.subTest(args=args[-3:]):
                code, _, err = run_main(*args)
                self.assertEqual(code, 2)
                self.assertTrue(err)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
