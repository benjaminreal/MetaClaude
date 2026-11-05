"""Approval-friction behaviour and safety checks; synthetic/offline only."""
import copy
import datetime as dt
import json
import tempfile
from pathlib import Path
from unittest import mock

import helpers as H
import schemas as S
import recert_regressions as R
from repair_fixtures import refuses


def lab():
    return tempfile.TemporaryDirectory()


def construction():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        a = l.ok('closingtime', 'new-invocation', root)
        b = l.ok('closingtime', 'new-invocation', root)
        assert a['scratch_dir'] != b['scratch_dir']
        env = a['envelope']; env['project'] = 'Synthetic'
        for cap in ('tasks_mcp', 'open_brain'):
            rows = [{'id': 'synthetic-row', 'project': 'Synthetic', 'updated_at': 'v1'}]
            packet = H.service_receipt(cap, {'rows': rows}, 'bounded read', {'project': 'Synthetic', 'service': cap}, 'result-synthetic')
            env = H.attach_evidence(env, packet)
        assert S.validate_envelope(env, env['returned_rows_by_capability'])['valid']
        broken = copy.deepcopy(env); broken['mcp_receipts'][0]['row_count'] = 0
        assert 'FINGERPRINT_MISMATCH' in {x['code'] for x in S.validate_envelope(broken, broken['returned_rows_by_capability'])['failures']}
        local = l.ok('closingtime', 'new-envelope', root, '--local-only')
        assert set(local['capability_profile']['external'].values()) == {'not_claimed'}
        assert S.validate_envelope(local)['valid']
        local['mutation_scope']['M3'] = ['update synthetic']
        assert 'LOCAL_ONLY' in {x['code'] for x in S.validate_envelope(local)['failures']}


def approval_without_scope():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        env = l.envelope(root, scope=['project_index.md'])
        frozen = l.freeze(env, index=R.INDEX)
        approved = l.ok('closingtime', 'approve-draft', l.save('f.json', frozen), '--owner-reply', 'Approved')
        assert approved['scope_string'] == frozen['scope_lines']
        refuses('SCOPE_UNAPPROVED', lambda: H.approve_draft(frozen, owner_reply=' '))


def cleanup():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        one = R.PENDING; two = one.replace('Candidate 1', 'Candidate 2')
        pending = root / 'pending_learnings.md'; pending.write_text(one + two)
        env = l.envelope(root, scope=['project_session.md', {'path':'pending_learnings.md','operation':'resolve'}])
        frozen = l.freeze(env, R.entry()); approved = H.approve_draft(frozen, frozen['scope_lines'], 'Approved conditional cleanup')
        env = H.bind_approval(env, approved)
        H.append_session_entry(env, R.entry(), approved)
        disposition = {'block_sha256': H._sha256_text(one), 'disposition':'discarded', 'owner_reply':'Discard candidate 1'}
        result = H.resolve_pending(env, approved, [disposition], H._sha256_text(one + two))
        assert result['readback_ok'] and pending.read_text() == two
        refuses('EDRAFTMISMATCH', lambda: H.resolve_pending(env, approved, [disposition], H._sha256_text(two)))
        # A new local-only approval can resolve the last block, never arbitrary content.
        env = l.ok('closingtime', 'new-envelope', root, '--local-only')
        env['mutation_scope']['M2'] = [{'path':'pending_learnings.md','operation':'resolve'}]
        f = H.freeze_draft(env); a = H.approve_draft(f, owner_reply='Approved cleanup'); env = H.bind_approval(env, a)
        refuses('ESOURCECHANGED', lambda: H.resolve_pending(env, a, [], 'absent'))
        bad = dict(disposition, block_sha256=H._sha256_text(two), disposition='saved', capture_result={'status':'error'})
        refuses('ERESOLUTION', lambda: H.resolve_pending(env, a, [bad], H._sha256_text(two)))
        d = dict(disposition, block_sha256=H._sha256_text(two))
        assert H.resolve_pending(env, a, [d], H._sha256_text(two))['readback_sha256'] == 'absent'
        assert not pending.exists()
        pending.write_text(one)
        env = l.envelope(root, scope=[{'path':'pending_learnings.md','operation':'resolve'}])
        a = H.approve_draft(H.freeze_draft(env), owner_reply='Approved')
        env = H.bind_approval(env,a)
        pending.write_text(one + two)
        refuses('ESOURCECHANGED', lambda: H.resolve_pending(env,a,[disposition],H._sha256_text(one)))
        assert pending.read_text() == one + two



def cleanup_preserves_unknown():
    one = R.PENDING
    raw = 'Unknown preamble\r\n' + one.replace('\n', '\r\n') + one.replace('Candidate 1','Candidate 2') + '**Unknown:** retain\n'
    out = H.resolved_pending_payload(raw.encode(), [{'block_sha256':H._sha256_text(one.replace('\n','\r\n')), 'disposition':'discarded','owner_reply':'Discard'}])
    assert out == ('Unknown preamble\r\n' + one.replace('Candidate 1','Candidate 2') + '**Unknown:** retain\n').encode()
    refuses('ERESOLUTION', lambda: H.resolved_pending_payload(one.encode(), [{'block_sha256':H._sha256_text(one), 'disposition':'discarded','owner_reply':''}]))
    # Substitution: a successful capture for different wording never resolves this block.
    d = {'block_sha256':H._sha256_text(one),'disposition':'saved','owner_reply':'Save',
         'capture_approval':{'payload_sha256':'sha256:other','owner_reply':'Approved capture'},
         'capture_result':{'status':'success','id':'synthetic-capture','payload_sha256':'sha256:other'}}
    refuses('ERESOLUTION', lambda: H.resolved_pending_payload(one.encode(), [d]))
    # Amendment 1: capture canonical wording, with the service's prose success.
    d['capture_approval']['block_sha256'] = H._sha256_text(one)
    d['capture_approval']['payload_sha256'] = d['capture_result']['payload_sha256'] = H.pending_blocks(one)[0]['capture_wording_sha256']
    d['capture_result'].update(result_text='Captured as observation', result_sha256=H._sha256_text('Captured as observation'))
    assert H.resolved_pending_payload(one.encode(), [d]) is None
    assert H.resolved_pending_payload(one.encode(), []) == one.encode()
    for suffix in ('**Custom:** preserve\n', 'unrecognized_metadata: preserve\n', '### Notes\nPreserve.\n'):
        unknown = one + suffix
        d = {'block_sha256':H._sha256_text(unknown), 'disposition':'discarded','owner_reply':'Discard'}
        assert H.resolved_pending_payload(unknown.encode(), [d]) == unknown.encode()



def refresh_and_exclusion():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        env = l.envelope(root, scope=['project_session.md','project_index.md','pending_learnings.md'])
        # Explicit opt-in stores a durable freeze witness, preventing copied/backdated stamps.
        f = H.freeze_draft(env, R.entry(), R.INDEX, refreshable=True)
        a = H.approve_draft(f, owner_reply='Approved, skip learnings')
        env = H.bind_approval(env, a)
        assert not any(op['operation']=='stage' for op in a['scope_operations'])
        refuses('EINVOCATIONUSED', lambda: H.approve_draft(f, owner_reply='Approved'))
        newer = l.envelope(root, scope=env['mutation_scope']['M2'])
        real_now = dt.datetime.now
        class Later(dt.datetime):
            @classmethod
            def now(cls, tz=None): return real_now(tz) + dt.timedelta(hours=7)
        with mock.patch.object(H.dt, 'datetime', Later), mock.patch.object(S._dt, 'datetime', Later):
            # Capture actual fresh local evidence using the helper clock.
            newer['local_snapshot'] = H.capture_local_snapshot(root)
            newer['invocation_started_at'] = newer['local_snapshot']['observed_at']
            for receipt in newer['mcp_receipts']:
                receipt['observed_at'] = newer['invocation_started_at']
            r = H.refresh_approval(a, newer, R.entry(), R.INDEX)
            assert r['parent_approval_sha256'] == a['receipt_sha256']
            newer = H.bind_approval(newer, r)
            H.append_session_entry(newer, R.entry(), r)
            refuses('EINVOCATIONUSED', lambda: H.refresh_approval(a, newer, R.entry(), R.INDEX))
        refuses('EINVOCATIONUSED', lambda: H._check_invocation(root, a))


def refresh_refusals():
    for change in ('entry','index','log_preimage','index_preimage','tasks','destination','backdate','copied','consumed'):
        with lab() as tmp:
            l = R.Lab(Path(tmp).resolve()); root = l.project()
            e = l.envelope(root, scope=['project_session.md','project_index.md'])
            f = H.freeze_draft(e, R.entry(), R.INDEX, refreshable=True)
            a = H.approve_draft(f, owner_reply='Approved'); fresh = l.envelope(root, scope=e['mutation_scope']['M2'])
            text, index = R.entry(), R.INDEX
            if change == 'entry': text += 'Material change.\n'
            if change == 'index': index += 'Material change.\n'
            if change == 'tasks': fresh['task_expected_versions'] = {'synthetic-task':'v2'}
            if change == 'destination': fresh['project'] = 'Other'
            if change in ('log_preimage','index_preimage'):
                field = 'session' if change=='log_preimage' else 'index'
                fresh['local_snapshot'][field]['sha256'] = 'sha256:other'
            if change in ('backdate','copied'):
                fresh['local_snapshot']['captured_at'] = a['snapshot_captured_at']
                if change == 'backdate': a = dict(a, drafted_at='2000-01-01T00:00:00Z'); a['receipt_sha256'] = H._receipt_digest(a)
            if change == 'consumed': H.append_session_entry(H.bind_approval(e,a), R.entry(), a)
            code = 'ECHRONOLOGY' if change == 'copied' else 'EINVOCATIONUSED' if change in ('backdate','consumed') else 'EDRAFTMISMATCH'
            refuses(code, lambda: H.refresh_approval(a, fresh, text, index))


def optional_stage_refresh():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        e = l.envelope(root, scope=['project_session.md','pending_learnings.md'])
        f = H.freeze_draft(e, R.entry(), refreshable=True)
        (root/'pending_learnings.md').write_text(R.PENDING)
        fresh = l.envelope(root, scope=e['mutation_scope']['M2'])
        a = H.refresh_approval(f, fresh, R.entry(), owner_reply='Approved')
        assert a['parent_approval_sha256'] == f['receipt_sha256']
        assert not H.audit_session_log(root)['foreign_files']
        H.append_session_entry(H.bind_approval(fresh,a), R.entry(), a)
        refuses('EINVOCATIONUSED', lambda: H.approve_draft(f, owner_reply='Approved'))
        refuses('SCOPE_UNAPPROVED', lambda: H._approval_selection(f, 'Skip learnings'))
        refuses('SCOPE_UNAPPROVED', lambda: H._approval_selection(f, 'Approve, change the summary'))


def stage_then_resolve_cli():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        env = l.envelope(root, scope=['project_session.md', 'pending_learnings.md', {'path':'pending_learnings.md','operation':'resolve'}])
        f = H.freeze_draft(env, R.entry(), refreshable=True)
        a = l.ok('closingtime','approve-draft',l.save('f.json',f),'--owner-reply','Approved')
        env = l.ok('closingtime','bind-approval',l.save('e.json',env),l.save('a.json',a))
        H.append_session_entry(env,R.entry(),a)
        H.write_approved_file(env,a,'pending_learnings.md',R.PENDING,'stage','absent')
        d = {'block_sha256':H._sha256_text(R.PENDING),'disposition':'discarded','owner_reply':'Discard'}
        result = l.ok('closingtime','resolve-pending',l.save('env.json',env),l.save('a.json',a),l.save('d.json',[d]),'--expect',H._sha256_text(R.PENDING))
        assert result['readback_sha256'] == 'absent'
        assert not H.resume_append(root)['unfinished_operations']
        assert not H.audit_session_log(root)['foreign_files']
        l.refused('newbeginning','new-envelope',root,'--local-only',code='ESKILL')


def raw_receipt_cli():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        env = l.envelope(root)
        for raw in ([{'id':'synthetic'}], {'results':[]}, {'content':[{'type':'text','text':'{"rows":[]}'}]}):
            packet = l.ok('closingtime','service-receipt','open_brain',l.save('raw.json',raw),l.save('op.txt','search synthetic'),l.save('id.json',{'service':'Synthetic'}),'--tool-result-id','synthetic-result')
            env = l.ok('closingtime','attach-evidence',l.save('env.json',env),l.save('packet.json',packet))
            assert S.validate_envelope(env,env['returned_rows_by_capability'])['valid']
        l.refused('closingtime','service-receipt','open_brain',l.save('error.json',{'isError':True}),l.save('op.txt','search synthetic'),l.save('id.json',{'service':'Synthetic'}),'--tool-result-id','synthetic-result',code='EBADROWS')


def late_exclusion_refresh():
    with lab() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        e = l.envelope(root, scope=['project_session.md','pending_learnings.md'])
        f = H.freeze_draft(e, R.entry(), refreshable=True)
        (root/'pending_learnings.md').write_text(R.PENDING)
        real_now = dt.datetime.now
        class Later(dt.datetime):
            @classmethod
            def now(cls,tz=None): return real_now(tz) + dt.timedelta(hours=7)
        with mock.patch.object(H.dt,'datetime',Later), mock.patch.object(S._dt,'datetime',Later):
            # Rebuild current envelope through the constructor's fresh observation,
            # retaining the independently verified unavailable-service identity.
            fresh = copy.deepcopy(e)
            fresh['invocation_id'] += '-refresh'
            fresh['local_snapshot'] = H.capture_local_snapshot(root)
            fresh['invocation_started_at'] = fresh['local_snapshot']['observed_at']
            fresh['mutation_scope']['M2'] = ['project_session.md']
            fresh['mcp_receipts'][0]['observed_at'] = fresh['invocation_started_at']
            a = H.refresh_approval(f,fresh,R.entry(),owner_reply='Approved, skip learnings')
            assert len(a['scope_operations']) == 1
            H.append_session_entry(H.bind_approval(fresh,a),R.entry(),a)
            assert (root/'pending_learnings.md').read_text() == R.PENDING
            refuses('EINVOCATIONUSED',lambda: H.refresh_approval(f,fresh,R.entry(),owner_reply='Approved'))


CHECKS = (construction, approval_without_scope, cleanup, cleanup_preserves_unknown, refresh_and_exclusion, refresh_refusals, optional_stage_refresh, stage_then_resolve_cli, raw_receipt_cli, late_exclusion_refresh)


def run():
    failures = []
    for check in CHECKS:
        try: check()
        except Exception as exc: failures.append(f'{check.__name__}: {type(exc).__name__}: {exc}')
    return failures

if __name__ == '__main__':
    bad = run()
    print('\n'.join(bad) if bad else 'FRICTION FIXTURES: PASSED (10 groups)')
    raise SystemExit(bool(bad))
