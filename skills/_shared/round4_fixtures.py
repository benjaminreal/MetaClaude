"""Additional round-4 guards beyond the frozen reviewer corpus (offline only)."""
from __future__ import annotations

import copy
import json
from unittest import mock

import helpers as H
import schemas as S
import workflow
import helper_fixtures as HF
from repair_fixtures import approved, refuses


def run() -> list[str]:
    problems = []
    for check in (not_used_choice, abandoned_transition, removed_finished_entry, adoption_policy_shape):
        try:
            check()
        except Exception as exc:
            problems.append(f'{check.__name__}: {type(exc).__name__}: {exc}')
    return problems


def not_used_choice():
    with HF.workspace() as root:
        env = HF._envelope(root)
        env['capability_profile']['external']['open_brain'] = 'not_used'
        assert S.validate_envelope(env, env['returned_rows_by_capability'])['valid']
        foreign = copy.deepcopy(env)
        foreign['capability_profile']['external']['tasks_mcp'] = 'not_used'
        assert not S.validate_envelope(foreign, foreign['returned_rows_by_capability'])['valid']
        rows = dict(env['returned_rows_by_capability'], open_brain=[])
        assert S.CONTRADICTORY in {f['code'] for f in S.validate_envelope(env, rows)['failures']}
        env['mcp_receipts'].append({'schema_version': '1.0', 'capability': 'open_brain', 'status': 'unavailable', 'capability_state': 'not_used'})
        assert S.CONTRADICTORY in {f['code'] for f in S.validate_envelope(env, env['returned_rows_by_capability'])['failures']}
    for kind in ('learning', 'openbrain'):
        plan = workflow.plan_skip_paths({kind})
        assert plan['open_brain_choice'] == 'not_used'
        assert not plan['allow']['openbrain_search'] and not plan['allow']['openbrain_capture']


def abandoned_transition():
    with HF.workspace() as root:
        env, receipt = approved(root, ['pending_learnings.md'], entry=None, pending_payload='bound')
        target = root / 'pending_learnings.md'
        real = H.os.replace
        def fail_target(source, destination):
            if destination == target:
                raise OSError('synthetic target replacement failure')
            return real(source, destination)
        with mock.patch.object(H.os, 'replace', side_effect=fail_target):
            refuses('EPARTIAL_WRITE', lambda: H.write_approved_file(env, receipt, target.name, 'bound', expect='absent', owner_reply='Approve bound bytes'))
        H.resume_append(root)
        assert not target.exists()
        refuses('EDRAFTMISMATCH', lambda: H.write_approved_file(env, receipt, target.name, 'bound', expect='absent', owner_reply='Same approval cannot retry'))
        assert not target.exists()


def removed_finished_entry():
    with HF.workspace() as root:
        env, receipt = approved(root)
        H.append_session_entry(env, HF.ENTRY_DRAFT, receipt)
        (root / 'project_session.md').unlink()
        assert any(op['state'] == 'missing_after_close' for op in H.resume_append(root)['operations'])


def adoption_policy_shape():
    with HF.workspace() as root:
        journal = root / 'private-artifacts/session-journal'
        journal.mkdir(parents=True)
        policy = journal / '_policy.json'
        for item in ({'session_number': True, 'entry_sha256': 'sha256:' + '0' * 64},
                     {'session_number': 1, 'entry_sha256': 'invalid'}):
            policy.write_text(json.dumps({'schema_version': '2.0', 'grandfather_session_ceiling': 0, 'historical_entries': [item]}))
            assert any(error.startswith('EBADPOLICY:') for error in H.audit_session_log(root)['errors'])
