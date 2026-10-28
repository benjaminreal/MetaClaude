"""Phase 4.5 regression oracles. Standard library; synthetic isolated workspaces."""
from __future__ import annotations
import copy
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock
import fixtures as F
import helper_fixtures as HF
import helpers as H
import schemas as S

CASES = []
CHECKS = []


def case(name):
    def decorate(fn):
        CASES.append(name)
        CHECKS.append((name, fn))
        return fn
    return decorate


def refuses(code, fn):
    try:
        fn()
    except H.HelperError as exc:
        assert exc.code == code, (code, exc.code, exc.detail)
    else:
        raise AssertionError('expected ' + code)


@case('D6-D8 identity, capability and parsed clock matrix')
@F.historical_clock()
def schema_matrix():
    def verdict(env, rows=None):
        return S.validate_envelope(env, rows or {'tasks_mcp': F.TASK_ROWS})
    def bad(env, code, rows=None):
        result = verdict(env, rows)
        assert code in {v['code'] for v in result['failures']}, result
    for field in ('invocation_started_at',):
        for value in ('', None, 7, [], 'yesterday-ish', '2026-08-03T22:00:00'):
            e = F.base_envelope(); e[field] = value; bad(e, 'INVALID_TIME')
    for value in ('', None, 7, {}, 'bad', '2026-08-03T22:31:04'):
        e = F.base_envelope(); e['mcp_receipts'][0]['observed_at'] = value; bad(e, 'INVALID_TIME')
    for value in (None, 7, 'bad', '2026-08-03T22:00:00'):
        e = F.base_envelope(); e['local_snapshot']['observed_at'] = value; bad(e, 'INVALID_TIME')
    for seconds, valid in ((-121, False), (-120, True), (-90, True), (0, True)):
        e = F.base_envelope()
        instant = S._parse_instant(e['invocation_started_at']) + dt.timedelta(seconds=seconds)
        e['mcp_receipts'][0]['observed_at'] = instant.isoformat()
        assert verdict(e)['valid'] == valid, verdict(e)
    e = F.base_envelope(); e['mcp_receipts'][0]['observed_at'] = '2026-08-04T02:00:00+05:00'; bad(e, 'STALE_RECEIPT')
    e = F.base_envelope(); e['mcp_receipts'][0]['observed_at'] = '2026-08-04T03:00:00.123+05:00'; assert verdict(e)['valid']
    e = F.base_envelope(); e['local_snapshot']['workspace_root'] = '/other'; bad(e, 'WORKSPACE_MISMATCH')
    for cap in ('tasks_mcp', 'open_brain'):
        e = F.base_envelope(); e['mcp_receipts'] = [dict(F.working_receipt(), capability=cap)]
        e['capability_profile']['external'][cap] = 'absent'; bad(e, 'CONTRADICTORY')
        e = F.base_envelope(); e['capability_profile']['external'][cap] = 'working'; e['mcp_receipts'] = []; bad(e, 'MISSING_RECEIPT')
        e = F.base_envelope(); r = dict(F.working_receipt(), capability=cap)
        e['capability_profile']['external'][cap] = 'working'
        e['mcp_receipts'] = [r, dict(r, identity={'project_ref': 'other'})]; bad(e, 'CONTRADICTORY')
    e = F.base_envelope(); e['mcp_receipts'][0].pop('identity'); bad(e, 'MISSING_RECEIPT')
    for rows in ([dict(F.TASK_ROWS[0], project='Other')], [{k:v for k,v in F.TASK_ROWS[0].items() if k != 'project'}]):
        e = F.base_envelope(mcp_receipts=[F.working_receipt(rows)]); bad(e, 'FOREIGN_ROWS', {'tasks_mcp': rows})
    e = F.base_envelope(project='Other'); bad(e, 'FOREIGN_ROWS')
    e = F.base_envelope(); e['mcp_receipts'][0]['identity']['project_ref'] = 'wrong'; bad(e, 'CONTRADICTORY')
    e = F.base_envelope(project='portfolio'); e['mcp_receipts'][0]['identity']['scope'] = 'portfolio'; assert verdict(e)['valid']
    assert S.fingerprint_operation("SELECT 'ProjectA'") != S.fingerprint_operation("SELECT 'projecta'")
    assert S.fingerprint_operation("SELECT 'a b'") != S.fingerprint_operation("SELECT 'a  b'")
    assert S.fingerprint_operation('a\r\nb  \n') == S.fingerprint_operation('a\nb')
    original = Path(__file__).resolve().parent / 'fixture_data' / 'b5_other_project_rows.json'
    e = json.loads(original.read_text()); result = S.validate_envelope(e, e.get('returned_rows_by_capability'))
    assert not result['valid'] and 'MISSING_RECEIPT' in {x['code'] for x in result['failures']}


@case('D7 git unborn, corruption, scoped NUL paths and no optional locks')
def git_matrix():
    def git(root, *args):
        return subprocess.run(['git', '-C', str(root), *args], capture_output=True, check=True)
    with HF.workspace() as root:
        git(root, 'init', '-q'); snap = H.capture_local_snapshot(root)
        assert snap['git']['unborn'] and snap['git']['head'] is None
        (root / '.git/HEAD').write_text('f' * 40 + '\n')
        assert H.capture_local_snapshot(root)['git']['state'] == 'corrupt'
    with HF.workspace() as root:
        (root / '.git').write_text('gitdir: /no-such-gitdir\n')
        assert H.capture_local_snapshot(root)['git']['state'] == 'corrupt'
    with HF.workspace() as root:
        git(root, 'init', '-q'); git(root, 'add', '.')
        git(root, '-c', 'user.name=Fixture', '-c', 'user.email=f@example.invalid', 'commit', '-qm', 'seed')
        index = root / '.git/index'; before = (index.read_bytes(), index.stat().st_mtime_ns)
        nested = root / 'nested'; nested.mkdir()
        for i in range(30): (root / f'sibling{i}').write_text('x')
        (nested / 'á space\nnewline').write_text('x')
        snap = H.capture_local_snapshot(nested)['git']
        assert snap['changed_path_count'] == 1 and snap['changed_paths'] == ['á space\nnewline'], snap
        assert (index.read_bytes(), index.stat().st_mtime_ns) == before
        git(root, 'mv', 'project_index.md', 'renamed index.md')
        assert 'renamed index.md' in H.capture_local_snapshot(root)['git']['changed_paths']
        for operation in ('status', 'diff', '--no-optional-locks'):
            real = subprocess.run
            def fail(argv, **kw):
                if operation in argv:
                    return subprocess.CompletedProcess(argv, 1, b'', b'injected failure')
                return real(argv, **kw)
            with mock.patch.object(H.subprocess, 'run', side_effect=fail):
                assert not H.capture_local_snapshot(root)['git']['available']


@case('D9 projection depth independent tail, truncation and conflict names')
def snapshot_matrix():
    with HF.workspace() as root:
        hashes = [H.capture_local_snapshot(root, entries=n)['session']['tail_sha256'] for n in (1, 2, 10)]
        assert len(set(hashes)) == 1
        for filename in ("project_session (Benjamin's conflicted copy 2026-10-27).md", 'project_session (Benjamin’s conflicted copy 2026-10-27).md', 'project_index (case conflict 1).md', 'project_session 2.md', 'pending_learnings copy.md', 'project_session (2).md', 'README (Conflicted copy).md'):
            p = root / filename; p.write_text('x'); assert filename in H.capture_local_snapshot(root)['sync_conflicts']; p.unlink()
        for filename in ('project_notes 2.md', 'conflicted_copy_notes.md', 'project_session.md.bak', 'backup.orig', 'README.md'):
            (root / filename).write_text('x')
        assert not H.capture_local_snapshot(root)['sync_conflicts']
        j = root / 'private-artifacts/session-journal'; j.mkdir(parents=True)
        (j / 'entry (conflicted copy).json').write_text('{}')
        assert H.capture_local_snapshot(root)['sync_conflicts']
        (j / 'entry (conflicted copy).json').unlink()
        (root / 'index.md').write_text('alternate')
        assert H.capture_local_snapshot(root)['index']['alternates'] == ['index.md']
        (root / 'index.md').unlink()
        (root / 'project_session.md').write_text(HF.SESSION_TEXT + '\n---\n\n' + HF.ENTRY_DRAFT.replace('#[N]', '#3') + '\nx' * 30000)
        snap = H.capture_local_snapshot(root)
        assert snap['projection']['truncated'] and snap['projection']['session']['latest_entry_truncated']
        assert snap['projection']['session']['tail'].startswith('### Session #3')
        assert snap['projection_bytes_emitted'] <= H.PROJECTION_BYTE_CAP
        child = root / 'child'; child.mkdir(); (child / 'project_index.md').write_text('x')
        assert H.capture_local_snapshot(root)['subprojects'] == ['child']


@case('Workspace root reached through a symlink')
def symlinked_root():
    with tempfile.TemporaryDirectory() as raw:
        real = Path(raw).resolve() / 'project'
        real.mkdir()
        (real / 'project_index.md').write_text(HF.INDEX_TEXT, encoding='utf-8')
        link = Path(raw).resolve() / 'link'
        link.symlink_to(real, target_is_directory=True)
        env = HF._envelope(real)
        env['workspace_root'] = str(link)
        codes = {f['code'] for f in S.validate_envelope(env, env.get('returned_rows_by_capability') or {})['failures']}
        assert S.WORKSPACE_MISMATCH not in codes, codes
        other = Path(raw).resolve() / 'other'
        other.mkdir()
        env['workspace_root'] = str(other)
        codes = {f['code'] for f in S.validate_envelope(env, env.get('returned_rows_by_capability') or {})['failures']}
        assert S.WORKSPACE_MISMATCH in codes, codes


def run():
    problems = []
    for name, fn in CHECKS:
        try:
            fn()
        except Exception as exc:
            problems.append(f'{name}: {type(exc).__name__}: {exc}')
    return problems


def approved(root, m2=None, entry=HF.ENTRY_DRAFT, index=None, skill='closingtime'):
    env = HF._envelope(root)
    env['skill'] = skill
    if m2 is not None:
        env['mutation_scope'] = {'M2': m2, 'M3': [], 'M4': []}
    if 'project_decisions_archive.md' in (m2 or []):
        env['local_payload_hashes'] = {'project_decisions_archive.md': H._sha256_text('approved archive')}
    r = H.freeze_draft(env, entry, index)
    env['approval'] = {'granted': True, 'scope_string': r['scope_lines']}
    return env, H.approve_draft(r, r['scope_lines'], 'Approved synthetic scope')


@case('D1 scope exclusions, collisions, changed classes and workspace/skill binding')
def approval_matrix():
    with HF.workspace() as root:
        e, r = approved(root)
        draft = H.freeze_draft(e, HF.ENTRY_DRAFT)
        for text in ('Approve project_index.md only. Do not write project_session.md.', 'M2 append project_session.md.bak', draft['scope_lines'] + '\nM3 update:other', ''):
            refuses('SCOPE_UNAPPROVED', lambda: H.approve_draft(draft, text))
        for cls in ('M2', 'M3', 'M4'):
            bad = copy.deepcopy(e); bad['mutation_scope'][cls].append('unexpected.md')
            refuses('EDRAFTMISMATCH', lambda: H.append_session_entry(bad, HF.ENTRY_DRAFT, r))
        bad = copy.deepcopy(e); bad['mutation_scope']['M2'] = []
        refuses('EDRAFTMISMATCH', lambda: H.append_session_entry(bad, HF.ENTRY_DRAFT, r))
        with HF.workspace() as other:
            bad = copy.deepcopy(e); bad['workspace_root'] = str(other)
            before = (other / 'project_session.md').read_bytes()
            refuses('EWORKSPACEMISMATCH', lambda: H.freeze_draft(bad, HF.ENTRY_DRAFT))
            assert (other / 'project_session.md').read_bytes() == before
        bad = copy.deepcopy(e); bad['skill'] = 'newbeginning'
        refuses('ESKILL', lambda: H.append_session_entry(bad, HF.ENTRY_DRAFT, r))
        # Correct partial approval: new index-only proposal, no append.
        partial = HF._envelope(root); partial['skill'] = 'newbeginning'; partial['mutation_scope'] = {'M2': ['project_index.md'], 'M3': [], 'M4': []}
        partial_r = H.freeze_draft(partial, None, HF.INDEX_TEXT)
        assert 'append' not in partial_r['scope_lines']


@case('D9 rendered entry refusals, malformed history, date skew and CRLF projection append')
def entry_matrix():
    invalid = [HF.ENTRY_DRAFT + '\n' + HF.ENTRY_DRAFT.replace('#[N]', '#4'), HF.ENTRY_DRAFT + '\n---',
               HF.ENTRY_DRAFT.replace('2026-08-04', '2026-02-30'), HF.ENTRY_DRAFT.replace('Code (Test)', ''),
               HF.ENTRY_DRAFT.replace('**Next:** Verify the journal.', '**Next:**  '),
               HF.ENTRY_DRAFT.replace('#[N]', '#[broken]')]
    for entry in invalid:
        with HF.workspace() as root:
            before = (root / 'project_session.md').read_bytes()
            refuses('EENTRYFORMAT', lambda: approved(root, entry=entry))
            assert (root / 'project_session.md').read_bytes() == before
    for text in (HF.SESSION_TEXT.replace('### Session #2 |', '### Session #2 —'), HF.SESSION_TEXT.replace('### Session #1 |', '### Session #2 |'), HF.SESSION_TEXT.replace(' | ', ' — ')):
        with HF.workspace(session_text=text) as root:
            before = (root / 'project_session.md').read_bytes()
            refuses('EHISTORY', lambda: approved(root))
            assert (root / 'project_session.md').read_bytes() == before
    for depth in (1, 2, 10):
        with HF.workspace() as root:
            log = root / 'project_session.md'; log.write_bytes(HF.SESSION_TEXT.replace('\n', '\r\n').encode())
            e = HF._envelope(root); e['local_snapshot'] = H.capture_local_snapshot(root, entries=depth)
            entry = HF.ENTRY_DRAFT.replace('synthetic', 'síntético').replace('\n', '\r\n')
            r = H.freeze_draft(e, entry); e['approval']['scope_string'] = r['scope_lines']; r = H.approve_draft(r, r['scope_lines'])
            before = log.read_bytes(); result = H.append_session_entry(e, entry, r)
            assert result['session_number'] == 3 and log.read_bytes().startswith(before)
            assert 'ENTRY_DATE_SKEW' in result['warnings']


@case('D2 append faults: intent write/fsync, append write/fsync, readback, rename, unlink')
def append_faults():
    # Atomic intent failures precede all log changes.
    for site in ('write', 'fsync'):
        with HF.workspace() as root:
            e, r = approved(root); before = (root / 'project_session.md').read_bytes()
            obj, attr = (H, '_atomic_record') if site == 'write' else (H.os, 'fsync')
            with mock.patch.object(obj, attr, side_effect=OSError('injected ' + site)):
                refuses('EJOURNAL', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
            assert (root / 'project_session.md').read_bytes() == before
    for first in (False, True):
        for site in ('readback-mismatch', 'readback-exception', 'append-fsync'):
            with HF.workspace(session_name=None if first else 'project_session.md') as root:
                e, r = approved(root); log = root / 'project_session.md'; before = H._file_state(log)
                real_append = H._append_bytes
                def failed_fsync(path, data):
                    real_append(path, data); raise OSError('append fsync failed')
                patch = mock.patch.object(H, '_append_bytes', side_effect=failed_fsync) if site == 'append-fsync' else mock.patch.object(H, '_readback_entry', **({'return_value': 'bad'} if site == 'readback-mismatch' else {'side_effect': OSError('read failed')}))
                with patch:
                    refuses('EREADBACK', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
                assert H._file_state(log) == before
                assert list((root / 'private-artifacts/session-journal').glob('*.abandoned'))
    with HF.workspace() as root:
        e, r = approved(root); before = (root / 'project_session.md').read_bytes()
        def torn(path, data):
            with path.open('ab') as f: f.write(data[:19])
            raise OSError('short append')
        with mock.patch.object(H, '_append_bytes', side_effect=torn):
            refuses('EPARTIAL_APPEND', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
        assert (root / 'project_session.md').read_bytes().startswith(before)
        assert H.resume_append(root)['state'] == 'partial_or_conflicted'
    with HF.workspace(session_name=None) as root:
        e, r = approved(root)
        original_unlink = Path.unlink
        def fail_log_unlink(path, *a, **kw):
            if path.name == 'project_session.md': raise OSError('unlink failed')
            return original_unlink(path, *a, **kw)
        with mock.patch.object(H, '_readback_entry', return_value='bad'), mock.patch.object(Path, 'unlink', fail_log_unlink):
            refuses('EPARTIAL_APPEND', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
        assert (root / 'project_session.md').exists()
        assert H.resume_append(root)['operations'][0]['state'] == 'appended'
    with HF.workspace() as root:
        e, r = approved(root)
        with mock.patch.object(H, '_move_record', side_effect=OSError('rename failed')):
            refuses('EPARTIAL_APPEND', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
        audit = H.audit_session_log(root)
        assert audit['pending_journal'] and not audit['journaled']
        result = H.resume_append(root); assert result['operations'][0]['state'] == 'appended'
        assert H.audit_session_log(root)['journaled'] == 1
        assert H.resume_append(root)['operations'][0]['state'] == 'appended'
        assert H.append_session_entry(e, HF.ENTRY_DRAFT, r)['already_appended']


@case('D3 foreign edits, shared local lock and journal symlink escape')
def foreign_matrix():
    with HF.workspace() as root:
        e, r = approved(root); log = root / 'project_session.md'
        def foreign_readback(*args):
            with log.open('ab') as f: f.write(b'\nFOREIGN\n')
            return 'bad'
        with mock.patch.object(H, '_readback_entry', side_effect=foreign_readback):
            refuses('EPARTIAL_APPEND', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
        assert log.read_bytes().endswith(b'FOREIGN\n')
        assert H.resume_append(root)['state'] == 'partial_or_conflicted'
    with HF.workspace() as root:
        e, r = approved(root)
        with H._advisory_lock(root, 'held'):
            refuses('ELOCK', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
            refuses('ELOCK', lambda: H.resume_append(root))
    with HF.workspace() as root, HF.workspace() as outside:
        (root / 'private-artifacts').mkdir()
        (root / 'private-artifacts/session-journal').symlink_to(outside, target_is_directory=True)
        refuses('EPERM', lambda: H.capture_local_snapshot(root))
        assert not list(outside.glob('*.pending'))


@case('D4 crash states, fresh close, root ownership, multiple matches and final readback')
def recovery_matrix():
    for boundary in ('before-append', 'after-append', 'after-final'):
        with HF.workspace() as root:
            e, r = approved(root)
            if boundary == 'before-append':
                with mock.patch.object(H, '_append_bytes', side_effect=OSError('before write')):
                    refuses('EPARTIAL_APPEND', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
            elif boundary == 'after-append':
                with mock.patch.object(H, '_move_record', side_effect=OSError('before commit')):
                    refuses('EPARTIAL_APPEND', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
            else:
                H.append_session_entry(e, HF.ENTRY_DRAFT, r)
            if boundary != 'after-final':
                fresh = HF._envelope(root)
                refuses('EUNFINISHED', lambda: H.freeze_draft(fresh, HF.ENTRY_DRAFT))
            result = H.resume_append(root)
            assert result['operations'][0]['state'] == ('not_appended' if boundary == 'before-append' else 'appended'), result
            assert not H.capture_local_snapshot(root)['unfinished_operations']
            H.resume_append(root)
    with HF.workspace() as root:
        e, r = approved(root); H.append_session_entry(e, HF.ENTRY_DRAFT, r)
        record = next((root / 'private-artifacts/session-journal').glob('*.done'))
        duplicate = record.with_name('duplicate.done'); duplicate.write_bytes(record.read_bytes())
        refuses('ERECOVERY', lambda: H.resume_append(root)); duplicate.unlink()
        with HF.workspace() as other:
            jd = other / 'private-artifacts/session-journal'; jd.mkdir(parents=True)
            (jd / record.name).write_bytes(record.read_bytes())
            H._workspace_id(other, create=True)
            refuses('EWORKSPACEMISMATCH', lambda: H.resume_append(other))
        log = root / 'project_session.md'; log.write_text('missing entry')
        refuses('ERECOVERY', lambda: H.resume_append(root))
    with HF.workspace() as root:
        e, r = approved(root)
        with mock.patch.object(H, '_append_bytes', side_effect=OSError('before write')):
            refuses('EPARTIAL_APPEND', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
        pending = next((root / 'private-artifacts/session-journal').glob('*.pending'))
        refuses('SCOPE_UNAPPROVED', lambda: H.resume_append(root, abandon=str(pending)))
        refuses('ERECOVERY', lambda: H.resume_append(root, abandon=str(pending), owner_reply='Do not abandon an append'))
        H.resume_append(root)  # not_appended is classified, not manually unjournaled


@case('D5 opening index, preimage existence, substitution, archive concurrency and paths')
def writer_matrix():
    with HF.workspace(index_name=None) as root:
        e, r = approved(root, ['project_index.md'], None, HF.INDEX_TEXT, 'newbeginning')
        result = H.write_approved_file(e, r, 'project_index.md', HF.INDEX_TEXT, expect='absent')
        assert result['readback_sha256'] == H._sha256_text(HF.INDEX_TEXT)
        refuses('EDRAFTMISMATCH', lambda: H.write_approved_file(e, r, 'project_index.md', HF.INDEX_TEXT, expect=result['readback_sha256']))
    with HF.workspace(index_text='') as root:
        e, r = approved(root, ['project_index.md'], None, HF.INDEX_TEXT, 'newbeginning')
        refuses('ESOURCECHANGED', lambda: H.write_approved_file(e, r, 'project_index.md', HF.INDEX_TEXT, expect='absent'))
        refuses('EDRAFTMISMATCH', lambda: H.write_approved_file(e, r, 'project_index.md', 'substituted', expect=H._sha256_text('')))
        (root / 'project_index.md').write_text('foreign edit')
        refuses('ESOURCECHANGED', lambda: H.write_approved_file(e, r, 'project_index.md', HF.INDEX_TEXT, expect=H._sha256_text('')))
        assert (root / 'project_index.md').read_text() == 'foreign edit'
    with HF.workspace(index_name='index.md') as root:
        e, r = approved(root, ['index.md'], None, HF.INDEX_TEXT, 'newbeginning')
        H.write_approved_file(e, r, 'index.md', HF.INDEX_TEXT, expect=e['local_snapshot']['index']['sha256'])
        assert not (root / 'project_index.md').exists()
    with HF.workspace() as root:
        e, r = approved(root, ['project_decisions_archive.md'], entry=None)
        (root / 'project_decisions_archive.md').write_text('foreign archive')
        refuses('ESOURCECHANGED', lambda: H.write_approved_file(e, r, 'project_decisions_archive.md', 'approved archive', expect='absent'))
        for name in ('../escape.md', '/private/tmp/escape.md', 'project_session.md', 'private-artifacts/session-journal/x.json', 'other.md'):
            refuses('EPERM', lambda: H._writer_target(root, e, name))
    with HF.workspace() as root, HF.workspace() as outside:
        e, r = approved(root, ['project_index.md'], None, HF.INDEX_TEXT)
        original = outside / 'foreign.md'; original.write_text('foreign')
        (root / 'project_index.md').unlink(); (root / 'project_index.md').symlink_to(original)
        refuses('EPERM', lambda: H.write_approved_file(e, r, 'project_index.md', HF.INDEX_TEXT, expect=e['local_snapshot']['index']['sha256']))
        assert original.read_text() == 'foreign'
    with HF.workspace() as root:
        e, r = approved(root, ['project_index.md'], None, HF.INDEX_TEXT)
        (root / 'project_index.md').unlink(); (root / 'project_index.md').mkdir()
        refuses('EPERM', lambda: H.write_approved_file(e, r, 'project_index.md', HF.INDEX_TEXT, expect=e['local_snapshot']['index']['sha256']))


@case('D5 pending stage, owner edit, mixed disposition, delete and restart with no scratch')
def learning_lifecycle():
    with HF.workspace() as root:
        # Existing v1 text and unknown fields are preserved by the caller; the
        # runtime deliberately does not parse or rewrite candidate semantics.
        pending = root / 'pending_learnings.md'
        legacy = '## Candidate 1\n**Connection:** unknown\n**Custom:** retained\n'
        pending.write_text(legacy)
        close, close_r = approved(root)
        H.append_session_entry(close, HF.ENTRY_DRAFT, close_r)
        assert not H.resume_append(root)['unfinished_operations']
        e, r = approved(root, ['pending_learnings.md'], entry=None)
        expected = H._sha256_text(legacy)
        for content, reply in ((legacy + '\n## Candidate 2\nstaged\n', 'Stage candidates'), (legacy + '\n## Candidate 2\nowner wording\n', 'Use this edit'), (legacy, 'Discard 2, retain 1')):
            result = H.write_approved_file(e, r, 'pending_learnings.md', content, expect=expected, owner_reply=reply)
            expected = result['readback_sha256']; assert pending.read_text() == content
        e, r = approved(root, [{'path': 'pending_learnings.md', 'operation': 'delete'}], entry=None)
        result = H.write_approved_file(e, r, 'pending_learnings.md', operation='delete', expect=expected, owner_reply='Discard remaining candidate')
        assert result['readback_sha256'] == 'absent' and not pending.exists()
        resumed = H.resume_append(root)
        assert resumed['state'] == 'inspected' and not resumed['unfinished_operations'], resumed


@case('D5 index mirror constrained after Tasks and single transition')
def mirror_matrix():
    template = HF.INDEX_TEXT + '\n## Active TODOs\noriginal mirror\n\n## Key Files\nkeep this\n'
    with HF.workspace(index_text=template) as root:
        e, r = approved(root, ['project_session.md', 'project_index.md'], index=template)
        H.append_session_entry(e, HF.ENTRY_DRAFT, r)
        e['mirror_receipt'] = F.working_receipt()
        e['mirror_receipt']['observed_at'] = H._utc_now()
        result = H.write_approved_file(e, r, 'project_index.md', template, expect=e['local_snapshot']['index']['sha256'], mirror_rows=F.TASK_ROWS)
        actual = (root / 'project_index.md').read_text()
        assert H.render_task_mirror(F.TASK_ROWS, e['local_snapshot']['local_date']) in actual and 'keep this' in actual
        assert result['readback_sha256'] == H._sha256_text(actual)
        assert not H.resume_append(root)['unfinished_operations']


@case('D5 writer faults and foreign edit at final replace boundary')
def writer_faults():
    for site in ('replace', 'fsync', 'unlink'):
        with HF.workspace() as root:
            pending = root / 'pending_learnings.md'; pending.write_text('old')
            e, r = approved(root, [{'path': 'pending_learnings.md', 'operation': 'delete' if site == 'unlink' else 'replace'}], entry=None)
            real_replace, real_fsync, real_unlink = os.replace, os.fsync, Path.unlink
            def replace(src, dst):
                if str(dst) == str(pending): raise OSError('replace fault')
                return real_replace(src, dst)
            def unlink(path, *a, **kw):
                if path == pending: raise OSError('unlink fault')
                return real_unlink(path, *a, **kw)
            if site == 'replace': patch = mock.patch.object(H.os, 'replace', side_effect=replace)
            elif site == 'unlink': patch = mock.patch.object(Path, 'unlink', unlink)
            else:
                calls = [0]
                def fsync(fd):
                    calls[0] += 1
                    if calls[0] == 3: raise OSError('payload fsync fault')
                    return real_fsync(fd)
                patch = mock.patch.object(H.os, 'fsync', side_effect=fsync)
            with patch:
                refuses('EPARTIAL_WRITE', lambda: H.write_approved_file(e, r, 'pending_learnings.md', None if site == 'unlink' else 'new', owner_reply='Approve this synthetic revision', operation='delete' if site == 'unlink' else 'replace', expect=H._sha256_text('old')))
            assert pending.read_text() == 'old'
            H.resume_append(root)
    with HF.workspace() as root:
        e, r = approved(root, ['pending_learnings.md'], entry=None)
        real = H._persist_intent
        def foreign(*a):
            path = real(*a); (root / 'pending_learnings.md').write_text('foreign'); return path
        with mock.patch.object(H, '_persist_intent', side_effect=foreign):
            refuses('EPARTIAL_WRITE', lambda: H.write_approved_file(e, r, 'pending_learnings.md', 'approved', expect='absent', owner_reply='Approve synthetic revision'))
        assert (root / 'pending_learnings.md').read_text() == 'foreign'


@case('D8 packaged CLI constructors, stdin and skip-plan without sibling access')
def packaged_commands():
    import shutil
    source = Path(__file__).resolve().parent.parent
    for skill in ('newbeginning', 'closingtime'):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve(); package = root / 'package'; project = root / 'project'; project.mkdir()
            shutil.copytree(source / skill, package)
            cli = package / 'scripts/runtime_cli.py'
            def command(*args, data=None):
                proc = subprocess.run([sys.executable, '-B', str(cli), *map(str, args)], input=data, capture_output=True, text=True)
                return proc.returncode, json.loads(proc.stdout)
            code, env = command('new-envelope', project)
            assert not code and env['skill'] == skill and env['capability_profile']['external']['tasks_mcp'] == 'unprobed'
            assert not S.validate_envelope(env)['valid']
            env['capability_profile']['external'] = {'tasks_mcp': 'absent', 'open_brain': 'absent'}
            assert S.validate_envelope(env)['valid']
            path = root / 'envelope.json'; path.write_text(json.dumps(env))
            assert command('snapshot', project, '--entries', '10')[0] == 0
            assert command('skip-plan', 'tasks,index')[1]['skipped'] == ['index', 'tasks']
            assert command('freeze-draft', '-', '-', data='{}')[1]['error']['code'] == 'EINPUT'
            if skill == 'closingtime':
                env['mutation_scope']['M2'] = ['project_session.md']; path.write_text(json.dumps(env))
                entry = root / 'entry.md'; entry.write_text(HF.ENTRY_DRAFT)
                code, frozen = command('freeze-draft', path, entry); assert not code, frozen
                receipt = root / 'receipt.json'; receipt.write_text(json.dumps(frozen))
                code, approved_r = command('approve-draft', receipt, frozen['scope_lines']); assert not code
                receipt.write_text(json.dumps(approved_r)); env['approval'] = {'granted': True, 'scope_string': frozen['scope_lines']}; path.write_text(json.dumps(env))
                code, result = command('append', path, '-', receipt, data=HF.ENTRY_DRAFT); assert not code, result
                assert command('resume', project)[0] == 0


@case('D2-D4 atomic intent boundaries and malformed/foreign recovery records')
def intent_boundaries():
    for site in ('rename-intent', 'directory-fsync'):
        with HF.workspace() as root:
            e, r = approved(root); before = (root / 'project_session.md').read_bytes()
            if site == 'rename-intent': patch = mock.patch.object(H.os, 'replace', side_effect=OSError('intent rename failed'))
            else: patch = mock.patch.object(H, '_fsync_dir', side_effect=OSError('directory durability failed'))
            with patch:
                refuses('EJOURNAL', lambda: H.append_session_entry(e, HF.ENTRY_DRAFT, r))
            assert (root / 'project_session.md').read_bytes() == before
            if site == 'directory-fsync':
                assert H.resume_append(root)['operations'][0]['state'] == 'not_appended'
            else:
                assert H.audit_session_log(root)['foreign_files']  # unpublished temp preserved
    for malformed in ('{torn', '[]', json.dumps({'kind': 'append_intent'})):
        with HF.workspace() as root:
            j = root / 'private-artifacts/session-journal'; j.mkdir(parents=True)
            p = j / 'broken.pending'; p.write_text(malformed)
            refuses('ERECOVERY', lambda: H.resume_append(root))
            assert p.read_text() == malformed
    with HF.workspace() as root:
        e, r = approved(root)
        H.append_session_entry(e, HF.ENTRY_DRAFT, r)
        p = next((root / 'private-artifacts/session-journal').glob('*.done'))
        record = json.loads(p.read_text()); record.pop('append_bytes'); record['record_sha256'] = H._intent_digest(record); p.write_text(json.dumps(record))
        refuses('ERECOVERY', lambda: H.resume_append(root))


@case('D3-D5 late conflicts, lock contention and approved archive payload identity')
def late_write_controls():
    for site in ('after-approval', 'after-intent'):
        with HF.workspace() as root:
            e, r = approved(root, ['project_index.md'], None, HF.INDEX_TEXT)
            expect = e['local_snapshot']['index']['sha256']; original = H._persist_intent
            def inject(*args):
                pending = original(*args); (root / "README (Benjamin's conflicted copy 2026-10-27).md").write_text('x'); return pending
            if site == 'after-approval':
                (root / 'project_index 2.md').write_text('conflict')
                patch = mock.patch.object(H, '_persist_intent', wraps=original)
            else: patch = mock.patch.object(H, '_persist_intent', side_effect=inject)
            before = (root / 'project_index.md').read_bytes()
            with patch:
                refuses('SYNC_CONFLICT', lambda: H.write_approved_file(e, r, 'project_index.md', HF.INDEX_TEXT, expect=expect))
            assert (root / 'project_index.md').read_bytes() == before
    with HF.workspace() as root:
        e, r = approved(root, ['project_decisions_archive.md'], entry=None)
        refuses('EDRAFTMISMATCH', lambda: H.write_approved_file(e, r, 'project_decisions_archive.md', 'substituted', expect='absent'))
        with H._advisory_lock(root, 'other writer'):
            refuses('ELOCK', lambda: H.write_approved_file(e, r, 'project_decisions_archive.md', 'approved archive', expect='absent'))
        assert H.write_approved_file(e, r, 'project_decisions_archive.md', 'approved archive', expect='absent')['readback_ok']


@case('D4 historical resume and sanctioned transition lineage across fresh closes')
def history_resume():
    with HF.workspace() as root:
        first_receipt = None
        for n in (1, 2):
            index = HF.INDEX_TEXT + '\nstate ' + str(n)
            e, r = approved(root, ['project_session.md', 'project_index.md'], index=index)
            if first_receipt is None: first_receipt = r
            H.append_session_entry(e, HF.ENTRY_DRAFT, r)
            H.write_approved_file(e, r, 'project_index.md', index, expect=e['local_snapshot']['index']['sha256'])
        assert H.resume_append(root)['state'] == 'inspected'
        assert H.resume_append(root, first_receipt)['state'] == 'inspected'


@case('D7-D9 skew future boundary, ambiguous names and first unborn close')
def remaining_snapshot_controls():
    real = dt.datetime
    class Clock(real):
        @classmethod
        def now(cls, tz=None):
            return real(2026, 8, 3, 22, 0, 0, tzinfo=dt.timezone.utc)
    with mock.patch.object(S._dt, 'datetime', Clock):
        for seconds, valid in ((120, True), (121, False)):
            e = F.base_envelope(); e['mcp_receipts'][0]['observed_at'] = (Clock.now() + dt.timedelta(seconds=seconds)).isoformat()
            assert S.validate_envelope(e, {'tasks_mcp': F.TASK_ROWS})['valid'] == valid
    with HF.workspace() as root:
        subprocess.run(['git', '-C', str(root), 'init', '-q'], check=True, capture_output=True)
        e, r = approved(root); assert e['local_snapshot']['git']['unborn']
        assert H.append_session_entry(e, HF.ENTRY_DRAFT, r)['readback_ok']
    with HF.workspace() as root:
        (root / 'session_log.md').write_text(HF.SESSION_TEXT)
        refuses('EHISTORY', lambda: approved(root))
    with HF.workspace(index_name=None) as root:
        p = root / 'Project_index.md'; q = root / 'PROJECT_INDEX.md'
        p.write_text('a'); q.write_text('b')
        if p.stat().st_ino == q.stat().st_ino:
            print('  [SKIPPED] case-sensitive dual-file fixture: scratch volume is case-insensitive')
        else:
            refuses('EAMBIGUOUSNAME', lambda: H.capture_local_snapshot(root))
    for cap in ('tasks_mcp', 'open_brain'):
        e = F.base_envelope(); e['capability_profile']['external'][cap] = 'working'
        e['capability_profile'].setdefault('external_detail', {})[cap] = {'project_ref': 'expected'}
        e['mcp_receipts'].append(dict(F.working_receipt([]), capability=cap, identity={'project_ref': 'wrong'}))
        assert 'CONTRADICTORY' in {x['code'] for x in S.validate_envelope(e)['failures']}


@case('D4 recovery inputs complete a remaining index after loss of scratch artifacts')
def scratchless_recovery():
    with HF.workspace() as root:
        index = HF.INDEX_TEXT + '\nRecovered approved draft.\n'
        env, receipt = approved(root, ['project_session.md', 'project_index.md'], index=index)
        H.append_session_entry(env, HF.ENTRY_DRAFT, receipt)
        before = (root / 'project_session.md').read_bytes()
        del env, receipt  # the next process has only its root and durable intents
        recovery = H.resume_append(root)['operations'][0]['recovery_inputs']
        envelope, receipt, index = recovery['envelope'], recovery['approved_draft'], recovery['index_draft']
        H.write_approved_file(envelope, receipt, 'project_index.md', index, expect=receipt['m2_preimages']['project_index.md'])
        assert (root / 'project_session.md').read_bytes() == before
        assert not H.resume_append(root)['unfinished_operations']
