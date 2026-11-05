"""Review F1 and Amendment 1 reproductions. Synthetic/offline; no service calls."""
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from unittest import mock

import helpers as H
import recert_regressions as R
from repair_fixtures import refuses

REAL_DATETIME = dt.datetime
INSIGHT = 'Verify saved bytes before reporting success.'
SUCCESS = 'Captured as observation — verification | Actions: check bytes'
OP = lambda content: json.dumps({'tool': 'capture_thought', 'arguments': {'content': content}}, ensure_ascii=False)


def receipt(raw, operation='search synthetic'):
    return H.service_receipt('open_brain', raw, operation, {'service': 'Synthetic'}, 'synthetic-result')


def disposition(block, wording=INSIGHT):
    key = H._sha256_text(block)
    return {'block_sha256': key, 'disposition': 'saved', 'owner_reply': 'Save this candidate',
            'capture_approval': {'block_sha256': key, 'wording': wording, 'payload_sha256': H._sha256_text(wording),
                                 'owner_reply': 'Approved capture of this wording'},
            'capture_result': receipt(SUCCESS, OP(wording))['capture_result']}


def canonical_wording():
    b = H.pending_blocks(R.PENDING)[0]
    assert b['capture_wording'] == INSIGHT
    assert b['capture_wording_sha256'] == H._sha256_text(INSIGHT) != b['block_sha256']
    assert H.pending_blocks(R.PENDING.replace('\n', '\r\n'))[0]['capture_wording'] == INSIGHT
    ambiguous = R.PENDING + '**Insight:** Another sentence.\n'
    assert H.pending_blocks(ambiguous)[0]['capture_wording'] is None


def saved_flow(edited=False):
    with tempfile.TemporaryDirectory() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        env = l.envelope(root, scope=['project_session.md', 'pending_learnings.md',
                                     {'path': 'pending_learnings.md', 'operation': 'resolve'}])
        a = H.approve_draft(H.freeze_draft(env, R.entry()), owner_reply='Approved')
        env = H.bind_approval(env, a)
        H.append_session_entry(env, R.entry(), a)
        H.write_approved_file(env, a, 'pending_learnings.md', R.PENDING, 'stage', 'absent')
        b = l.ok('closingtime', 'pending-blocks', root / 'pending_learnings.md')[0]
        wording = 'Read back saved content before claiming success.' if edited else b['capture_wording']
        d = disposition(R.PENDING, wording)
        packet = l.ok('closingtime', 'service-receipt', 'open_brain', l.save('raw.txt', SUCCESS),
                      l.save('operation.json', OP(wording)), l.save('identity.json', {'service': 'Synthetic'}),
                      '--tool-result-id', 'synthetic-capture')
        d['capture_result'] = packet['capture_result']
        out = l.ok('closingtime', 'resolve-pending', l.save('env.json', env), l.save('approved.json', a),
                   l.save('dispositions.json', [d]), '--expect', b['block_sha256'])
        assert out['readback_sha256'] == 'absent' and not (root / 'pending_learnings.md').exists()
        assert not H.resume_append(root)['unfinished_operations']
        assert not H.audit_session_log(root)['foreign_files']


def saved_refusals():
    d = disposition(R.PENDING)
    assert H.resolved_pending_payload(R.PENDING.encode(), [d]) is None
    mutations = (
        lambda x: x['capture_approval'].update(payload_sha256=H._sha256_text('different')),
        lambda x: x['capture_result'].update(payload_sha256=H._sha256_text('different')),
        lambda x: x.update(capture_result={}),  # never captured
        lambda x: x['capture_result'].update(status='error'),
        lambda x: x['capture_result'].update(result_text='Failed to capture: offline'),
        lambda x: x['capture_approval'].update(block_sha256=H._sha256_text('different block')),
        lambda x: x['capture_approval'].pop('block_sha256'),
        lambda x: x['capture_approval'].update(wording='Unapproved substitution'),
    )
    for mutate in mutations:
        bad = copy.deepcopy(d); mutate(bad)
        refuses('ERESOLUTION', lambda: H.resolved_pending_payload(R.PENDING.encode(), [bad]))
    two = R.PENDING.replace('Candidate 1', 'Candidate 2').replace(INSIGHT, 'A different insight.')
    edited = disposition(R.PENDING, 'Owner edited wording.')
    edited['block_sha256'] = H._sha256_text(two)  # transplant approved edit to a different block
    refuses('ERESOLUTION', lambda: H.resolved_pending_payload(two.encode(), [edited]))


def prose_reads():
    samples = [('No thoughts found matching "synthetic".', 'no_results', 0),
               ('No thoughts found.', 'no_results', 0),
               ('Found 1 thought(s):\n\n--- Result 1 (90.0% match) ---\nCaptured: 11/5/2026\nType: observation\nTopics: checks\n\nSynthetic insight.', 'found', 1),
               ('2 recent thought(s):\n\n1. [11/5/2026] (observation - checks)\n   First.\n\n2. [11/5/2026] (observation)\n   Second.', 'found', 2)]
    for raw, outcome, count in samples:
        p = receipt(raw)
        assert p['receipt']['result_sha256'] == H._sha256_text(raw)
        assert p['receipt']['outcome'] == outcome and p['receipt']['row_count'] == count
        assert p['receipt']['row_fingerprint'] == H.S.canonical_row_fingerprint(p['returned_rows_by_capability']['open_brain'])
    raw = 'Total thoughts: 2\nDate range: 11/1/2026 → 11/5/2026\n\nTypes:\n  observation: 2'
    assert receipt(raw, '{"tool":"thought_stats","arguments":{}}')['receipt']['outcome'] == 'stats'
    p = receipt({'content': [{'type': 'text', 'text': samples[0][0]}]})
    assert p['receipt']['row_count'] == 0


def capture_result():
    content = 'Exact approved wording.\nIncluding Unicode: sí.'
    p = receipt(SUCCESS, OP(content))
    c = p['capture_result']
    assert c['status'] == 'success' and c['payload_sha256'] == H._sha256_text(content)
    assert c['result_text'] == SUCCESS and c['result_sha256'] == H._sha256_text(SUCCESS)
    assert p['receipt']['outcome'] == 'captured' and 'id' not in c
    for op in ('search synthetic', '{bad', OP(''), '{"tool":"search_thoughts","arguments":{"content":"x"}}'):
        refuses('EBADROWS', lambda: receipt(SUCCESS, op))


def prose_errors():
    for raw in ('Failed to capture: offline', 'Search error: offline', 'Error: offline', 'Not a documented result',
                'Found 2 thought(s):\n\n--- Result 1 (90.0% match) ---\nCaptured: today\nType: observation\n\nOnly one.'):
        refuses('EBADROWS', lambda: receipt(raw, OP(INSIGHT)))
    try:
        receipt('Failed to capture: offline', OP(INSIGHT))
    except H.HelperError as exc:
        assert exc.context['outcome'] == 'failed'
        assert exc.context['result_sha256'] == H._sha256_text('Failed to capture: offline')
    assert receipt('No thoughts found.')['receipt']['outcome'] == 'no_results'


def truncation_refusals():
    for cap in ('tasks_mcp', 'open_brain'):
        for raw in ({'rows': [], 'truncated': True}, {'structuredContent': {'rows': [], 'truncated': True}},
                    {'content': [{'type': 'text', 'text': '{"rows":[],"truncated":true}'}]},
                    '{"content":[{"type":"text","text":"No thoughts found."}],"truncated":true}'):
            refuses('EBADROWS', lambda: H.service_receipt(cap, raw, 'read', {'service': 'Synthetic'}, 'synthetic-result'))
    for raw in ('No thoughts found.\n[truncated]', 'Found 1 thought(s):\n[output truncated]'):
        refuses('EBADROWS', lambda: receipt(raw))


def decode_refusals():
    refuses('EBADROWS', lambda: H.service_receipt('tasks_mcp', {'content':[{'type':'text','text':'not JSON'}]},
                                                'read', {'service':'Synthetic'}, 'synthetic-result'))
    refuses('ERESOLUTION', lambda: H.resolved_pending_payload(b'\xff', []))
    with tempfile.TemporaryDirectory() as tmp:
        l = R.Lab(Path(tmp).resolve())
        raw = l.save('invalid.txt', ''); raw.write_bytes(b'\xff')
        l.refused('closingtime', 'service-receipt', 'open_brain', raw, l.save('op', 'search'),
                  l.save('identity', {'service':'Synthetic'}), '--tool-result-id', 'synthetic', code='EBADROWS')
        l.refused('closingtime', 'pending-blocks', raw, code='ERESOLUTION')


def opening_refuses_witness():
    with tempfile.TemporaryDirectory() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        e = l.envelope(root, 'newbeginning', scope=['project_index.md'])
        before = R.tree(root)
        l.refused('newbeginning', *l.freeze_args(e, index=R.INDEX), '--refreshable', code='ESKILL')
        refuses('ESKILL', lambda: H.freeze_draft(e, index_text=R.INDEX, refreshable=True))
        assert R.tree(root) == before


def clock_at(instant):
    class Clock(REAL_DATETIME):
        tick = 0
        @classmethod
        def now(cls, tz=None):
            cls.tick += 1
            stamp = instant + dt.timedelta(microseconds=cls.tick)
            return stamp.astimezone(tz) if tz else stamp.replace(tzinfo=None)
    return mock.patch.object(H.dt, 'datetime', Clock)


def fresh(root, original):
    env = copy.deepcopy(original)
    env['invocation_id'] = uuid.uuid4().hex
    env['local_snapshot'] = H.capture_local_snapshot(root)
    env['invocation_started_at'] = env['local_snapshot']['observed_at']
    for r in env['mcp_receipts']: r['observed_at'] = env['invocation_started_at']
    return env


def carry_age(hours, late=False):
    with tempfile.TemporaryDirectory() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        env = l.envelope(root, scope=['project_session.md'])
        f = H.freeze_draft(env, R.entry(), refreshable=True)
        parent = f if late else H.approve_draft(f, owner_reply='Approved')
        origin = H._parse_utc(parent['drafted_at'] if late else parent['approved_at'])
        with clock_at(origin + dt.timedelta(hours=hours)):
            e = fresh(root, env)
            run = lambda: H.refresh_approval(parent, e, R.entry(), owner_reply='Approved' if late else '')
            if hours > 24:
                refuses('ESTALEAPPROVAL', run)
                assert not H._approval_path(root, e['invocation_id']).exists()
            else:
                a = run()
                assert a['carry_origin_at'] == origin.isoformat().replace('+00:00', 'Z')
                H.append_session_entry(H.bind_approval(e, a), R.entry(), a)


def carry_chain():
    with tempfile.TemporaryDirectory() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        env = l.envelope(root, scope=['project_session.md'])
        a = H.approve_draft(H.freeze_draft(env, R.entry(), refreshable=True), owner_reply='Approved')
        origin = H._parse_utc(a['approved_at'])
        for hour in (7, 14, 23, 25):
            with clock_at(origin + dt.timedelta(hours=hour)):
                e = fresh(root, env)
                if hour > 24:
                    refuses('ESTALEAPPROVAL', lambda: H.refresh_approval(a, e, R.entry()))
                    refuses('ESTALEAPPROVAL', lambda: H.bind_approval(last_env, a))
                else:
                    a = H.refresh_approval(a, e, R.entry()); last_env = e


def strict_resolution_preimage():
    with tempfile.TemporaryDirectory() as tmp:
        l = R.Lab(Path(tmp).resolve()); root = l.project()
        e = l.envelope(root, scope=['project_session.md', 'pending_learnings.md',
                                    {'path':'pending_learnings.md', 'operation':'resolve'}])
        a = H.approve_draft(H.freeze_draft(e, R.entry(), refreshable=True), owner_reply='Approved')
        (root/'pending_learnings.md').write_text(R.PENDING)
        refuses('EDRAFTMISMATCH', lambda: H.refresh_approval(a, fresh(root, e), R.entry()))


def docs_binding():
    contract = (R.HERE/'candidate_quality_contract.md').read_text()
    closing = (R.SKILLS/'closingtime/SKILL.md').read_text()
    draft = closing.split('### `DRAFT_GATE`')[1].split('### ')[0]
    assert 'pre-approval' in draft and '.draft' in draft
    assert 'capture_wording_sha256' in contract and 'No second' in contract
    assert 'each need their own frozen scope' not in contract


def standalone_registration():
    # Stub bodies while exercising the real standalone registration/exit path.
    # This avoids recursively running the corpus from its own fixture hook.
    script = '''import runpy, sys
import recert_regressions as complete
complete.results = lambda: [(g, label, None) for g, label, fn in complete.CHECKS]
runpy.run_path(sys.argv[1], run_name="__main__")
'''
    proc = subprocess.run([sys.executable, '-B', '-c', script, str(R.HERE/'recert_regressions.py')],
                          cwd=R.HERE, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert '[PASS] Approval friction |' in proc.stdout, proc.stdout[-500:]
    assert '[PASS] Approval repair |' in proc.stdout, proc.stdout[-500:]


CHECKS = (canonical_wording, saved_flow, lambda: saved_flow(True), saved_refusals, prose_reads,
          capture_result, prose_errors, truncation_refusals, decode_refusals, opening_refuses_witness,
          lambda: carry_age(23), lambda: carry_age(25), lambda: carry_age(23, True),
          lambda: carry_age(25, True), carry_chain, strict_resolution_preimage, docs_binding,
          standalone_registration)
LABELS = ('canonical wording', 'saved stage/capture/resolve', 'edited wording flow', 'saved refusal matrix',
          'prose read formats', 'capture content binding', 'prose errors/count mismatch', 'truncation markers',
          'decode errors', 'opening witness refusal', '23h approval carry', '25h approval refusal',
          '23h late approval', '25h late refusal', 'refresh chain age', 'stage plus resolve preimage',
          'aligned instructions', 'standalone registration')


def run(verbose=False):
    bad = []
    for label, fn in zip(LABELS, CHECKS):
        try:
            fn()
            if verbose: print('PASS ' + label)
        except Exception as exc:
            bad.append(f'{label}: {type(exc).__name__}: {exc}')
            if verbose: print('FAIL ' + bad[-1])
    return bad


if __name__ == '__main__':
    bad = run(True)
    print(f'APPROVAL REPAIR: {len(CHECKS)-len(bad)}/{len(CHECKS)} groups passed')
    raise SystemExit(bool(bad))
