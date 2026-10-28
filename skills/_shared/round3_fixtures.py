"""Round-3 independent regression inputs; no cwd, evidence files or live services.

Named review cases are retained in labels. All workspaces resolve macOS's
/var symlink before any receipt, comparison or subprocess boundary.
"""
from __future__ import annotations
import copy
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import mock
import helpers as H
import helper_fixtures as HF
import schemas as S
from repair_fixtures import refuses

HERE = Path(__file__).resolve().parent
CHECKS = []


def case(label):
    def register(fn):
        CHECKS.append((label, fn))
        return fn
    return register


def proposal(root, paths=('project_session.md', 'project_index.md'), index='approved index', skill='closingtime'):
    env = HF._envelope(root)
    env['skill'] = skill
    env['capability_profile']['external'] = {'tasks_mcp': 'absent', 'open_brain': 'absent'}
    env['mcp_receipts'] = []; env['returned_rows_by_capability'] = {}
    env['mutation_scope'] = {'M2': list(paths), 'M3': [], 'M4': []}
    entry = HF.ENTRY_DRAFT if 'project_session.md' in paths else None
    draft = H.freeze_draft(env, entry, index if any(p in H.INDEX_NAMES for p in paths) else None)
    return env, draft, entry


def approve(env, draft):
    result = H.approve_draft(draft, draft['scope_lines'], 'Approve the displayed synthetic scope')
    env['approval'] = {'granted': True, 'scope_string': draft['scope_lines']}
    return result


def close(root):
    env, draft, entry = proposal(root)
    receipt = approve(env, draft)
    result = H.append_session_entry(env, entry, receipt)
    return env, receipt, result


def index_write(env, receipt, text='approved index'):
    return H.write_approved_file(env, receipt, 'project_index.md', text, expect=receipt['m2_preimages']['project_index.md'])


@case('S1 nb pending write; S2 E2b skipped/zero learning leaves existing file untouched')
def scope_reduction():
    with HF.workspace() as root:
        pending = root / 'pending_learnings.md'; pending.write_text('legacy unresolved; custom metadata')
        for path in ('pending_learnings.md', 'project_decisions_archive.md', 'project_session.md', 'other.md'):
            env = HF._envelope(root); env['skill'] = 'newbeginning'
            env['mutation_scope'] = {'M2': [path], 'M3': [], 'M4': []}
            refuses('ESKILL', lambda: H.freeze_draft(env))
        env, receipt, _ = close(root); index_write(env, receipt)
        assert pending.read_text() == 'legacy unresolved; custom metadata'
        assert not H.capture_local_snapshot(root)['unfinished_operations']
        proposal(root)  # next close can freeze; no no-op learning disposition
        for paths in (['project_session.md', {'path': 'pending_learnings.md', 'operation': 'replace'}], ['project_session.md', 'project_decisions_archive.md']):
            refuses('EINPUT', lambda: proposal(root, paths))


@case('R1 D5c foreign index: remaining_stale, continuation and child abandonment preserve audit')
def continuation_and_abandon():
    for abandon in (False, True):
        with HF.workspace(session_name=None) as root:
            env, receipt, append = close(root)
            log = (root / 'project_session.md').read_bytes()
            (root / 'project_index.md').write_text('foreign index')
            refuses('ESOURCECHANGED', lambda: index_write(env, receipt))
            result = H.resume_append(root)
            child = next(op for op in result['operations'] if op['state'] == 'remaining_stale')
            assert child['current_sha256'] == H._sha256_text('foreign index')
            refuses('ERECOVERY', lambda: H.resume_append(root, abandon=append['journal_record_path'], owner_reply='abandon parent'))
            refuses('EUNFINISHED', lambda: proposal(root))
            if abandon:
                H.resume_append(root, abandon=child['intent'], owner_reply='Cancel remaining index')
                assert (root / 'project_index.md').read_text() == 'foreign index'
            else:
                current = HF._envelope(root); current['mutation_scope'] = {'M2': ['project_index.md'], 'M3': [], 'M4': []}
                parent = Path(append['journal_record_path']).relative_to(root).as_posix()
                draft = H.freeze_draft(current, index_text='rebased index', continue_parent=parent)
                index_write(current, approve(current, draft), 'rebased index')
            assert (root / 'project_session.md').read_bytes() == log
            audit = H.audit_session_log(root)
            assert audit['journaled'] == 1 and not audit['unjournaled'] and not audit['orphan_records'], audit
            assert not H.resume_append(root)['unfinished_operations']
            proposal(root)


@case('R1 relocated-complete and unfinished remount; new close and nb index; journal identity mismatch')
def relocation():
    for complete in (False, True):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve(); original = base/'original'; original.mkdir()
            (original/'project_index.md').write_text(HF.INDEX_TEXT)
            env, receipt, _ = close(original)
            if complete: index_write(env, receipt)
            moved = base/'remounted'; original.rename(moved)
            result = H.resume_append(moved)
            if not complete:
                recovery = next(x['recovery_inputs'] for x in result['operations'] if 'recovery_inputs' in x)
                index_write(recovery['envelope'], recovery['approved_draft'])
            assert not H.resume_append(moved)['unfinished_operations']
            env2, receipt2, _ = close(moved); index_write(env2, receipt2)
            nb, draft, _ = proposal(moved, ['project_index.md'], 'opening index', 'newbeginning')
            index_write(nb, approve(nb, draft), 'opening index')
            assert H.audit_session_log(moved)['journaled'] == 2
            other = base/'other'; other.mkdir(); H._workspace_id(other, create=True)
            record = next((moved/'private-artifacts/session-journal').glob('*.done'))
            shutil.copy2(record, other/'private-artifacts/session-journal'/record.name)
            refuses('EWORKSPACEMISMATCH', lambda: H.resume_append(other))


@case('R2 A1 all-target preflight, aliases and changed preimages before any append')
def preflight():
    for boundary in ('freeze-alias', 'append-alias', 'append-preimage'):
        with HF.workspace() as root:
            before = (root/'project_session.md').read_bytes()
            if boundary == 'freeze-alias':
                (root/'index.md').write_text('other index')
                refuses('EAMBIGUOUSNAME', lambda: proposal(root))
            else:
                env, draft, entry = proposal(root); receipt = approve(env, draft)
                if boundary == 'append-alias':
                    (root/'index.md').write_text('other index')
                    code = 'EAMBIGUOUSNAME'
                else:
                    (root/'project_index.md').write_text('foreign edit'); code = 'ESOURCECHANGED'
                refuses(code, lambda: H.append_session_entry(env, entry, receipt))
            assert (root/'project_session.md').read_bytes() == before
            assert not H.audit_session_log(root)['journaled']


@case('R3 D1-crash-lock immediate recovery, D1b TMPDIR, live/foreign expiry, all warnings')
def locks():
    with HF.workspace(session_name=None) as root:
        env, draft, entry = proposal(root); receipt = approve(env, draft)
        script = '''import json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import helpers as H
root=Path(sys.argv[2]); e,r,entry=json.load(sys.stdin)
real=H._move_record
def crash(path,suffix):
 if suffix=='.done': os._exit(86)
 return real(path,suffix)
H._move_record=crash
H.append_session_entry(e,entry,r)
'''
        proc = subprocess.run([sys.executable,'-B','-c',script,str(HERE),str(root)], input=json.dumps([env,receipt,entry]), text=True, capture_output=True)
        assert proc.returncode == 86, proc.stderr
        result = H.resume_append(root)
        assert 'ELOCK_STALE_RECOVERED' in result['warnings'], result
        assert H.audit_session_log(root)['journaled'] == 1
        recovery = next(x['recovery_inputs'] for x in result['operations'] if 'recovery_inputs' in x)
        # A dead host-local lock is recovered by write-approved too.
        lock = H._lock_path(root)
        lock.write_text(json.dumps({'host': H.socket.gethostname(), 'pid': 99999999, 'started_at': H.time.time()}))
        assert 'ELOCK_STALE_RECOVERED' in index_write(recovery['envelope'],recovery['approved_draft'])['warnings']
    with HF.workspace() as root:
        lock = H._lock_path(root)
        for age, host, blocked in ((601,H.socket.gethostname(),True),(1,'other-host',True),(601,'other-host',False)):
            lock.write_text(json.dumps({'host':host,'pid':os.getpid(),'started_at':H.time.time()-age}))
            if blocked: refuses('ELOCK',lambda:H.resume_append(root))
            else: assert 'ELOCK_STALE_RECOVERED' in H.resume_append(root)['warnings']
            if lock.exists(): lock.unlink()
        with H._advisory_lock(root,'live writer'):
            with tempfile.TemporaryDirectory() as temp:
                code = 'import sys;sys.path.insert(0,sys.argv[1]);import helpers as H;H.resume_append(sys.argv[2])'
                proc = subprocess.run([sys.executable,'-B','-c',code,str(HERE),str(root)], env=dict(os.environ,TMPDIR=str(Path(temp).resolve())), capture_output=True,text=True)
                assert proc.returncode != 0 and 'ELOCK:' in proc.stderr
            assert not H._sync_conflicts(root)
            assert not H.audit_session_log(root)['foreign_files']


@case('R4 gap2 direct title entry, impossible dates, unicode digits, duplicate/malformed, monotonic warning; C10b')
def history_and_targets():
    direct = HF.SESSION_TEXT.replace('---\n\n','',1)
    with HF.workspace(session_text=direct) as root:
        assert H.capture_local_snapshot(root)['session']['latest_session_number'] == 2
        assert H.audit_session_log(root)['entries'] == 2
        env,draft,entry=proposal(root,['project_session.md']);H.append_session_entry(env,entry,approve(env,draft))
        assert H.audit_session_log(root)['entries'] == 3
    for text in (HF.SESSION_TEXT.replace('2026-08-02','2026-02-30'), HF.SESSION_TEXT.replace('#1','#١'), HF.SESSION_TEXT.replace('#1','#2'), HF.SESSION_TEXT.replace('#1 |','#1 —')):
        with HF.workspace(session_text=text) as root:
            env=HF._envelope(root)
            assert 'EHISTORY' in {f['code'] for f in S.validate_envelope(env, env['returned_rows_by_capability'])['failures']}
            refuses('EHISTORY',lambda:H.freeze_draft(env,HF.ENTRY_DRAFT))
            assert 'EHISTORY' in H.audit_session_log(root)['errors']
    with HF.workspace(session_text=HF.SESSION_TEXT.replace('#1','#3')) as root:
        assert 'session_non_monotonic' in H.capture_local_snapshot(root)['parse_warnings']
        proposal(root)
    with HF.workspace() as root:
        env=HF._envelope(root)
        env['local_snapshot']['parse_warnings']=[]
        env['local_snapshot']['projection']['session']['tail']=HF.SESSION_TEXT.replace('#1','#2')
        assert 'EHISTORY' in {x['code'] for x in S.validate_envelope(env,env['returned_rows_by_capability'])['failures']}
    for fake in ('project_session.md','private-artifacts/session-journal/evil.json','other.md'):
        with HF.workspace() as root:
            env=HF._envelope(root);env['local_snapshot']['index']['path']=fake
            env['mutation_scope']={'M2':[{'path':fake,'operation':'replace'}],'M3':[],'M4':[]}
            before=(root/'project_session.md').read_bytes()
            refuses('EPERM',lambda:H.freeze_draft(env,index_text='replacement'))
            assert (root/'project_session.md').read_bytes()==before


@case('R5 B7b/E6 wall-clock evidence, C3b invocation reuse, old pending approval and owner words')
def freshness_and_approval():
    with HF.workspace() as root:
        for skill in ('newbeginning','closingtime'):
            for delta in (-21601,121):
                env=HF._envelope(root);env['skill']=skill
                timestamp=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=delta)).isoformat()
                env['local_snapshot']['captured_at']=timestamp
                assert 'ESTALEEVIDENCE' in {x['code'] for x in S.validate_envelope(env)['failures']}
                refuses('ESTALEEVIDENCE',lambda:H.freeze_draft(env,HF.ENTRY_DRAFT))
        env,old,entry=proposal(root)
        reduced=copy.deepcopy(env);reduced['mutation_scope']['M2']=['project_session.md']
        new=H.freeze_draft(reduced,entry);receipt=approve(reduced,new)
        refuses('EINVOCATIONUSED',lambda:H.approve_draft(old,old['scope_lines']))
        H.append_session_entry(reduced,entry,receipt)
        forged=copy.deepcopy(receipt);forged['owner_reply']='different receipt';forged['receipt_sha256']=H._receipt_digest(forged)
        refuses('EINVOCATIONUSED',lambda:H.append_session_entry(reduced,entry,forged))
    with HF.workspace() as root:
        env,draft,_=proposal(root,['pending_learnings.md']);receipt=approve(env,draft)
        refuses('SCOPE_UNAPPROVED',lambda:H.write_approved_file(env,receipt,'pending_learnings.md','one',expect='absent'))
        result=H.write_approved_file(env,receipt,'pending_learnings.md','one',expect='absent',owner_reply='Stage one')
        real=dt.datetime
        class Later(real):
            @classmethod
            def now(cls,tz=None):return real.now(dt.timezone.utc)+dt.timedelta(days=2)
        with mock.patch.object(H.dt,'datetime',Later):
            refuses('ESTALEEVIDENCE',lambda:H.write_approved_file(env,receipt,'pending_learnings.md','two',expect=result['readback_sha256'],owner_reply='Edit one'))
        assert (root/'pending_learnings.md').read_text()=='one'
    with HF.workspace() as root:
        env,receipt,_=close(root)
        with mock.patch.object(H.dt,'datetime',Later):
            refuses('ESTALEEVIDENCE',lambda:index_write(env,receipt))
            resumed=H.resume_append(root)
            assert resumed['freshness_exemption']
            inputs=next(x['recovery_inputs'] for x in resumed['operations'] if 'recovery_inputs' in x)
            index_write(inputs['envelope'],inputs['approved_draft'])


@case('D Finder copy 2 continuity stems; unrelated numbered copies remain a stated limit')
def finder_names():
    for stem in ('project_index','project_session','pending_learnings','project_decisions_archive','index'):
        with HF.workspace() as root:
            name=stem+' copy 2.md';(root/name).write_text('copy')
            assert name in H.capture_local_snapshot(root)['sync_conflicts']
    with HF.workspace() as root:
        (root/'README 2.md').write_text('unrelated copy')
        assert not H.capture_local_snapshot(root)['sync_conflicts']


def run():
    failures=[]
    for label,fn in CHECKS:
        try:fn()
        except Exception as exc:failures.append(f'{label}: {type(exc).__name__}: {exc}')
    return failures


@case('Round-1 reasons: foreign scope, excluded approval, entry/tail, journal obstruction, Dropbox, unborn, receipts, standalone')
def round1_reasons():
    # Existing D1-D10 fault matrices remain active; these retain the exact
    # round-1 failure classes as additional self-contained regression inputs.
    with HF.workspace() as root, HF.workspace() as other:
        for skill in ('newbeginning','closingtime'):
            env=HF._envelope(root);env['skill']=skill;env['local_snapshot']=H.capture_local_snapshot(other)
            assert S.WORKSPACE_MISMATCH in {x['code'] for x in S.validate_envelope(env)['failures']}
            refuses('EWORKSPACEMISMATCH',lambda:H.freeze_draft(env,HF.ENTRY_DRAFT))
        env,draft,entry=proposal(root)
        refuses('SCOPE_UNAPPROVED',lambda:H.approve_draft(draft,'Index only; exclude session'))
        receipt=approve(env,draft)
        refuses('EDRAFTMISMATCH',lambda:H.append_session_entry(env,entry+' altered',receipt))
        before=(root/'project_session.md').read_bytes()
        with (root/'project_session.md').open('a') as stream:
            stream.write('\n\n'+H._render_entry(HF.ENTRY_DRAFT,3))
        foreign=(root/'project_session.md').read_bytes()
        refuses('ESTALE',lambda:H.append_session_entry(env,entry,receipt))
        assert (root/'project_session.md').read_bytes()==foreign and foreign.startswith(before)
    with HF.workspace() as root:
        refuses('EENTRYFORMAT',lambda:proposal_with_entry(root,HF.ENTRY_DRAFT+'\n'+HF.ENTRY_DRAFT))
    with HF.workspace(session_name=None) as root:
        env,draft,entry=proposal(root)
        journal=root/'private-artifacts/session-journal'
        journal.parent.mkdir();journal.write_text('obstruction')
        refuses('EJOURNAL',lambda:approve(env,draft))
        assert not (root/'project_session.md').exists()
    for skill in ('newbeginning','closingtime'):
        with HF.workspace() as root:
            (root/"project_session (Someone's conflicted copy 2026-10-28).md").write_text('conflict')
            env=HF._envelope(root);env['skill']=skill
            assert S.SYNC_CONFLICT in {x['code'] for x in S.validate_envelope(env)['failures']}
            refuses('EINVALIDENVELOPE',lambda:H.freeze_draft(env,HF.ENTRY_DRAFT))
    with HF.workspace(index_name=None,session_name=None) as root:
        subprocess.run(['git','-C',str(root),'init','-q'],check=True,capture_output=True)
        assert H.capture_local_snapshot(root)['git']['unborn']
        env,receipt,_=close(root);index_write(env,receipt)
        assert H.audit_session_log(root)['journaled']==1
        before=(root/'project_session.md').read_bytes()
        assert H.append_session_entry(env,HF.ENTRY_DRAFT,receipt)['already_appended']
        H.resume_append(root);H.resume_append(root)
        assert (root/'project_session.md').read_bytes()==before
        assert H.audit_session_log(root)['journaled']==1
    with HF.workspace() as root:
        env=HF._envelope(root)
        for mutate,expected in ((lambda e:e.update(invocation_started_at=''),'INVALID_TIME'),(lambda e:e['mcp_receipts'][0].update(observed_at='2999-01-01T00:00:00Z'),'FUTURE_RECEIPT'),(lambda e:e['mcp_receipts'][0]['identity'].update(project='Foreign'),'FOREIGN_ROWS'),(lambda e:e['capability_profile']['external'].update(tasks_mcp='absent'),'CONTRADICTORY')):
            bad=copy.deepcopy(env);mutate(bad)
            assert expected in {x['code'] for x in S.validate_envelope(bad,bad['returned_rows_by_capability'])['failures']}
    # Only the copied package is callable from an unrelated working directory.
    for skill in ('newbeginning','closingtime'):
        with tempfile.TemporaryDirectory() as raw:
            base=Path(raw).resolve();package=base/'package';project=base/'project';project.mkdir()
            shutil.copytree(HERE.parent/skill,package,ignore=shutil.ignore_patterns('__pycache__'))
            cli=package/'scripts/runtime_cli.py'
            proc=subprocess.run([sys.executable,'-B',str(cli),'new-envelope',str(project)],cwd=base,capture_output=True,text=True)
            env=json.loads(proc.stdout);assert proc.returncode==0 and env['skill']==skill,proc.stderr
            if skill=='newbeginning':
                env['skill']='closingtime';env['capability_profile']['external']={'tasks_mcp':'absent','open_brain':'absent'}
                source=base/'envelope.json';source.write_text(json.dumps(env))
                proc=subprocess.run([sys.executable,'-B',str(cli),'freeze-draft',str(source)],cwd=base,capture_output=True,text=True)
                assert json.loads(proc.stdout)['error']['code']=='ESKILL',proc.stdout


def proposal_with_entry(root,entry):
    env=HF._envelope(root)
    return H.freeze_draft(env,entry)


@case('R1 legacy v2 absolute intent recovery after relocation; legacy v1 journal still audits')
def legacy_intents():
    for include_pending in (False,True):
        with tempfile.TemporaryDirectory() as raw:
            base=Path(raw).resolve();root=base/'old';root.mkdir();(root/'project_index.md').write_text(HF.INDEX_TEXT)
            env,receipt,append=close(root)
            if include_pending:
                env['mutation_scope']['M2'].append('pending_learnings.md')
                receipt['scope_operations']=H._scope_operations(env,legacy=True)
            journal=root/'private-artifacts/session-journal'
            parent=Path(append['journal_record_path']);record=json.loads(parent.read_text())
            # Encode the previous release's receipt and absolute-path journal shape.
            for name in ('workspace_id','snapshot_captured_at','skill','continue_parent','warnings','invocation_started_at'):
                receipt.pop(name,None)
            receipt['snapshot_sha256']=H._sha256_bytes(H._canonical_json(env['local_snapshot']))
            receipt['scope_lines']=H._scope_text(receipt['scope_operations'],legacy=True)
            receipt['scope_sha256']=H._sha256_text(receipt['scope_lines']);receipt['scope_string']=receipt['scope_lines']
            receipt['receipt_sha256']=H._receipt_digest(receipt)
            env['approval']['scope_string']=receipt['scope_lines']
            record.update(target=str(root/'project_session.md'),approved_envelope=env,approved_draft=receipt,draft_receipt_sha256=receipt['receipt_sha256'],approved_scope=receipt['scope_lines'])
            if include_pending:
                record['m2_operations']['pending_learnings.md']={'preimage':'absent','payload_sha256':None}
            record.pop('workspace_id',None);record['record_sha256']=H._intent_digest(record)
            parent.write_text(json.dumps(record));parent.rename(parent.with_suffix('.json'))
            for path in journal.iterdir():
                if path.suffix in ('.pending','.approval') or path.name=='workspace.json':path.unlink()
            moved=base/'new';root.rename(moved)
            resumed=H.resume_append(moved)
            recovery=next(x['recovery_inputs'] for x in resumed['operations'] if 'recovery_inputs' in x)
            index_write(recovery['envelope'],recovery['approved_draft'])
            assert not H.resume_append(moved)['unfinished_operations']
            assert H.audit_session_log(moved)['journaled']==1
            assert H.capture_local_snapshot(moved)['workspace_id']
            assert not (moved/'pending_learnings.md').exists()


@case('R1 index child after rollback or torn append; no dangling or premature index write')
def child_fault_boundaries():
    for absent in (False,True):
        with HF.workspace(session_name=None if absent else 'project_session.md') as root:
            env,draft,entry=proposal(root);receipt=approve(env,draft)
            log=root/'project_session.md';before=log.read_bytes() if log.exists() else None
            with mock.patch.object(H,'_readback_entry',return_value='bad readback'):
                refuses('EREADBACK',lambda:H.append_session_entry(env,entry,receipt))
            assert (log.read_bytes() if log.exists() else None)==before
            assert not H.resume_append(root)['unfinished_operations']
            proposal(root)  # no duplicate-close blocker after a verified rollback
    with HF.workspace() as root:
        env,draft,entry=proposal(root);receipt=approve(env,draft)
        index_before=(root/'project_index.md').read_bytes()
        refuses('EUNFINISHED',lambda:index_write(env,receipt))
        def torn(path,data):
            with path.open('ab') as stream:stream.write(data[:10])
            raise OSError('injected torn append')
        with mock.patch.object(H,'_append_bytes',side_effect=torn):
            refuses('EPARTIAL_APPEND',lambda:H.append_session_entry(env,entry,receipt))
        resumed=H.resume_append(root)
        assert resumed['state']=='partial_or_conflicted'
        assert not any('recovery_inputs' in x for x in resumed['operations'])
        refuses('EUNFINISHED',lambda:index_write(env,receipt))
        assert (root/'project_index.md').read_bytes()==index_before


@case('R3.2 real-log compatibility: titles, subheadings, letter supplements and v1 headings do not block')
def legacy_history_headings():
    E = '### Session #{n} | 2026-10-0{d} | Code (Synthetic)\n**Focus:** f\n**Done:** d\n**Next:** n\n**Blockers:** None\n'
    accepted = {
        'title with suffix': ('# Session Log — Synthetic\n\n' + E.format(n=1, d=1), [1], 1),
        'title with colon': ('# Session Log: Synthetic\n\n---\n\n' + E.format(n=3, d=1), [3], 3),
        'subheadings in body': ('# Session Log\n\n' + E.format(n=1, d=1) + '## Session Context\nx\n## Session Statistics\ny\n', [1], 1),
        'letter supplements': ('# Session Log\n\n' + E.format(n=12, d=1) + '### Session #12A | 2026-10-02 | Code\nb\n#### Session #12B (supplement) | 2026-10-02 | x\n' + E.format(n=13, d=3), [12, 13], 13),
        'v1 headings then v2': ('# Session Log\n\n## Session 1 — Kickoff\nb\n## Session 2 (continued): More\nb\n' + E.format(n=19, d=1), [19], 19),
        'v1 headings only': ('# Log\n\n## Session 5 — Old\nb\n', [], 5),
        'Spanish v1 headings': ('# Registro\n\n## Sesión 3 · 3 de mayo\nb\n', [], 3),
        'multi-day date range': ('# Session Log\n\n' + E.format(n=7, d=1) + '### Session #8 | 2026-10-02–03 | Code\nb\n', [7], 8),
    }
    for label, (text, numbers, latest) in accepted.items():
        entries, warnings = S.parse_history(text)
        assert [e['session_number'] for e in entries] == numbers, label
        assert not (set(warnings) & S.HISTORY_ERRORS), (label, warnings)
        assert H._last_session_entries(text)[1] == latest, label
    for label, text in {
        'broken strict header': '# Session Log\n\n### Session #4 2026-10-01 Code\n',
        'non-ASCII digit': '# Session Log\n\n### Session #٤ | 2026-10-01 | Code\n',
    }.items():
        assert 'session_header_malformed' in S.parse_history(text)[1], label
    # A close appends after the highest legacy number and the log keeps its legacy lines.
    with HF.workspace(session_name=None) as root:
        legacy = '# Session Log — Synthetic\n\n' + E.format(n=12, d=1) + '### Session #12A | 2026-10-02 | Code\nb\n## Session Context\nx\n'
        (root / 'project_session.md').write_text(legacy)
        env, receipt, result = close(root)
        assert result['session_number'] == 13, result
        text = (root / 'project_session.md').read_text()
        assert text.startswith(legacy) and '### Session #13 |' in text
        audit = H.audit_session_log(root)
        assert not audit['errors'] and audit['journaled'] == 1, audit
