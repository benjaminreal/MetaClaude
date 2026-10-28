"""Round-3.1 synthetic regressions; temporary workspaces, no external services."""
from __future__ import annotations
import copy
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock
import helpers as H
import helper_fixtures as HF
import schemas as S
import round3_fixtures as R3
from repair_fixtures import refuses

CHECKS = []
STAGE = {'path': 'pending_learnings.md', 'operation': 'stage'}
BLOCK = ('\n\n## Candidate 2\n**Type:** process\n'
         '**Insight:** Verify saved bytes before calling a local record complete.\n'
         '**Connects to:** unavailable\n**Status:** pending\n')


def case(label):
    def register(fn):
        CHECKS.append((label, fn))
        return fn
    return register


def stage_close(root, explicit=False):
    env, draft, entry = R3.proposal(root, ['project_session.md', 'project_index.md',
                                          STAGE if explicit else 'pending_learnings.md'])
    return env, R3.approve(env, draft), entry


def stage(env, receipt, content=BLOCK, expect='absent'):
    return H.write_approved_file(env, receipt, 'pending_learnings.md', content,
                                 operation='stage', expect=expect)


def clean(root):
    audit = H.audit_session_log(root)
    assert audit['journaled'] == 1 and not any(audit[k] for k in ('unjournaled', 'orphan_records', 'errors')), audit
    assert not H.capture_local_snapshot(root)['unfinished_operations']


@case('F1 verified append, current preimage, one transition, preserved legacy bytes')
def staging_permission():
    for explicit in (False, True):
        with HF.workspace() as root:
            HF._policy(root)
            pending = root / 'pending_learnings.md'
            legacy = b'## Candidate 1\r\n**Connection:** unknown\r\n**Custom:** retained'
            pending.write_bytes(legacy)
            env, receipt, entry = stage_close(root, explicit)
            assert 'M2 stage pending_learnings.md (optional; new candidate blocks only)' in receipt['scope_lines']
            assert 'delete pending_learnings.md' not in receipt['scope_lines']
            refuses('EUNFINISHED', lambda: stage(env, receipt, legacy.decode() + BLOCK, H._sha256_bytes(legacy)))
            H.append_session_entry(env, entry, receipt); R3.index_write(env, receipt)
            # Preserve even bytes appended by another device after freeze.
            current = legacy + b'\r\n**Unknown:** newer metadata'; pending.write_bytes(current)
            refuses('ESOURCECHANGED', lambda: stage(env, receipt, current.decode() + BLOCK, H._sha256_bytes(legacy)))
            result = stage(env, receipt, current.decode() + BLOCK, H._sha256_bytes(current))
            assert result['readback_ok'] and pending.read_bytes() == current + BLOCK.encode()
            record = json.loads(Path(result['journal_record_path']).read_text())
            assert record['parent_intent'].endswith('.done') and record['owner_reply'] == receipt['owner_reply']
            refuses('ESTAGE', lambda: stage(env, receipt, pending.read_text() + BLOCK, result['readback_sha256']))
            clean(root)


@case('F1 ESTAGE prefix/line-ending change, arbitrary suffix, malformed blocks, disposition')
def stage_refusals():
    with HF.workspace() as root:
        pending = root / 'pending_learnings.md'; pending.write_bytes(b'legacy\r\n')
        env, receipt, entry = stage_close(root)
        H.append_session_entry(env, entry, receipt); R3.index_write(env, receipt)
        before = pending.read_bytes(); expected = H._sha256_bytes(before)
        invalid = ['changed' + BLOCK, 'legacy\n' + BLOCK, before.decode(),
                   before.decode() + '\narbitrary text', before.decode() + '\n## Candidate 3\nno fields',
                   before.decode() + BLOCK.replace('**Status:** pending', '**Status:** discarded'),
                   before.decode() + BLOCK + '\n# Unrequested document\n']
        for text in invalid:
            refuses('ESTAGE', lambda: stage(env, receipt, text, expected))
            assert pending.read_bytes() == before
            assert not H.capture_local_snapshot(root)['unfinished_operations']
        for name in ('project_index.md', 'project_decisions_archive.md'):
            bad = HF._envelope(root); bad['mutation_scope']['M2'] = [{'path': name, 'operation': 'stage'}]
            refuses('ESTAGE', lambda: H.freeze_draft(bad))


@case('F1 skipped/zero learning creates no child, absent/existing pending untouched')
def optional_learning():
    for reason in ('skip', 'zero'):
        for existing in (False, True):
            with HF.workspace() as root:
                HF._policy(root)
                pending = root / 'pending_learnings.md'
                if existing: pending.write_bytes(b'legacy unresolved\r\n**Unknown:** keep')
                before = pending.read_bytes() if existing else None
                env, receipt, entry = stage_close(root)
                H.append_session_entry(env, entry, receipt); R3.index_write(env, receipt)
                assert (pending.read_bytes() if pending.exists() else None) == before, reason
                assert not any(r.get('operation') == 'stage' for _, r in H._load_intents(root))
                clean(root); H.resume_append(root); clean(root); R3.proposal(root)


@case('F1 failed stage resumes/abandons independently; verified append stays journaled')
def stage_recovery():
    for outcome in ('resume', 'abandon', 'foreign', 'postimage'):
        with HF.workspace() as root:
            HF._policy(root)
            env, receipt, entry = stage_close(root)
            appended = H.append_session_entry(env, entry, receipt); R3.index_write(env, receipt)
            log = (root / 'project_session.md').read_bytes(); target = root / 'pending_learnings.md'
            real_replace = H.os.replace
            def interrupted(src, dst):
                if Path(dst) == target:
                    if outcome == 'postimage': real_replace(src, dst)
                    raise OSError('synthetic stage interruption')
                return real_replace(src, dst)
            with mock.patch.object(H.os, 'replace', side_effect=interrupted):
                refuses('EPARTIAL_WRITE', lambda: stage(env, receipt))
            unfinished = H.capture_local_snapshot(root)['unfinished_operations']; assert len(unfinished) == 1
            child = json.loads((root / unfinished[0]).read_text())
            assert child['kind'] == 'write_intent' and child['operation'] == 'stage'
            assert Path(appended['journal_record_path']).suffix == '.done'
            assert H.audit_session_log(root)['journaled'] == 1
            assert H.append_session_entry(env, entry, receipt)['already_appended']
            refuses('EUNFINISHED', lambda: R3.proposal(root))
            if outcome == 'foreign':
                target.write_text('foreign content'); resumed = H.resume_append(root)
                assert resumed['state'] == 'partial_or_conflicted' and resumed['unfinished_operations']
            if outcome in ('abandon', 'foreign'):
                H.resume_append(root, abandon=unfinished[0], owner_reply='Abandon only the staged child')
                assert (not target.exists()) if outcome == 'abandon' else target.read_text() == 'foreign content'
            else:
                real = dt.datetime
                class Later(real):
                    @classmethod
                    def now(cls, tz=None): return real.now(dt.timezone.utc) + dt.timedelta(days=2)
                with mock.patch.object(H.dt, 'datetime', Later): resumed = H.resume_append(root)
                assert any(op['state'] == 'applied' for op in resumed['operations'])
                assert target.read_bytes() == BLOCK.encode()
            assert (root / 'project_session.md').read_bytes() == log
            refuses('ESTAGE', lambda: stage(env, receipt, expect=H._file_state(target)['sha256']))
            clean(root)


@case('F2 pending/archive scopes contain exactly requested operations; no implicit delete')
def exact_operations():
    for path in ('pending_learnings.md', 'project_decisions_archive.md'):
        with HF.workspace() as root:
            for operation in (None, 'replace', 'delete'):
                env = HF._envelope(root)
                env['mutation_scope'] = {'M2': [path if operation is None else {'path': path, 'operation': operation}], 'M3': [], 'M4': []}
                env['local_payload_hashes'] = {path: H._sha256_text('archive')}
                draft = H.freeze_draft(env)
                assert draft['scope_operations'] == [{'class': 'M2', 'operation': operation or 'replace', 'path': path}]
                assert len(draft['scope_lines'].splitlines()) == 1
            if path == 'pending_learnings.md':
                env, draft, _ = R3.proposal(root, [path]); receipt = R3.approve(env, draft)
                refuses('SCOPE_UNAPPROVED', lambda: H.write_approved_file(env, receipt, path, operation='delete', expect='absent', owner_reply='keep'))


@case('F5 constructor timestamps, 15-minute boundary, copied start, pre-invocation receipt')
def envelope_chains():
    for skill in ('newbeginning', 'closingtime'):
        with HF.workspace() as root:
            cli = Path(__file__).resolve().parent.parent / skill / 'scripts/runtime_cli.py'
            proc = subprocess.run([sys.executable, '-B', str(cli), 'new-envelope', str(root)], cwd=root, text=True, capture_output=True)
            assert proc.returncode == 0, proc.stderr
            env = json.loads(proc.stdout)
            assert env['invocation_started_at'] == env['local_snapshot']['captured_at']
            env['capability_profile']['external'] = {'tasks_mcp': 'absent', 'open_brain': 'absent'}
            captured = S._parse_instant(env['local_snapshot']['captured_at'])
            for seconds in (900, 901, 3600):
                candidate = copy.deepcopy(env)
                candidate['invocation_started_at'] = (captured - dt.timedelta(seconds=seconds)).isoformat()
                verdict = S.validate_envelope(candidate)
                assert verdict['valid'] if seconds == 900 else 'ESTALEEVIDENCE' in {f['code'] for f in verdict['failures']}, verdict
                if seconds > 900: refuses('ESTALEEVIDENCE', lambda: H.freeze_draft(candidate))
            old = HF._envelope(root)
            old['mcp_receipts'][0]['observed_at'] = (S._parse_instant(old['invocation_started_at']) - dt.timedelta(seconds=121)).isoformat()
            assert S.STALE_RECEIPT in {f['code'] for f in S.validate_envelope(old, old['returned_rows_by_capability'])['failures']}


@case('F1 CLI stage preserves CRLF legacy prefix from file and stdin')
def cli_stage_bytes():
    for stdin in (False, True):
        with HF.workspace() as root:
            pending = root / 'pending_learnings.md'; original = b'legacy\r\n**Custom:** retained\r\n'
            pending.write_bytes(original)
            env, receipt, entry = stage_close(root)
            H.append_session_entry(env, entry, receipt); R3.index_write(env, receipt)
            payload = original + BLOCK.encode()
            env_path = root / 'env.json'; env_path.write_text(json.dumps(env))
            receipt_path = root / 'receipt.json'; receipt_path.write_text(json.dumps(receipt))
            content = root / 'payload.txt'; content.write_bytes(payload)
            cli = Path(__file__).resolve().parent.parent / 'closingtime/scripts/runtime_cli.py'
            proc = subprocess.run([sys.executable, '-B', str(cli), 'write-approved', str(env_path), str(receipt_path),
                                   'pending_learnings.md', '-' if stdin else str(content), '--operation', 'stage',
                                   '--expect', H._sha256_bytes(original)], input=payload if stdin else None, capture_output=True)
            assert proc.returncode == 0, proc.stdout + proc.stderr
            assert json.loads(proc.stdout)['readback_ok'] and pending.read_bytes() == payload


@case('F4 final-text count CLI after last edit for opening reply and closing entry')
def final_text_counts():
    for skill in ('newbeginning', 'closingtime'):
        cli = Path(__file__).resolve().parent.parent / skill / 'scripts/runtime_cli.py'
        early = 'Earlier draft.'
        final = ('Current state verified. Pick up, discuss a task, or focus elsewhere?\n'
                 'Evidence: instructions instructions_absent; instruction_bytes_loaded 100; '
                 'projection_bytes_emitted 200; brief_words 24') if skill == 'newbeginning' else HF.ENTRY_DRAFT
        outputs = []
        for text in (early, final):
            proc = subprocess.run([sys.executable, '-B', str(cli), 'count-words', '-'], input=text, text=True, capture_output=True)
            assert proc.returncode == 0, proc.stderr
            outputs.append(json.loads(proc.stdout)['words'])
        assert outputs[-1] == len(final.split()) and outputs[-1] != outputs[0]
        if skill == 'newbeginning':
            # Substitute the count, then count the exact text that will be sent.
            final = final.rsplit(' ', 1)[0] + ' ' + str(outputs[-1])
            proc = subprocess.run([sys.executable, '-B', str(cli), 'count-words', '-'], input=final, text=True, capture_output=True)
            assert proc.returncode == 0 and json.loads(proc.stdout)['words'] == outputs[-1]


@case('D01 CLI scope approval, append/index, stage/readback before review, keep, clean audit')
def d01_sequence():
    with HF.workspace() as root:
        HF._policy(root)
        cli = Path(__file__).resolve().parent.parent / 'closingtime/scripts/runtime_cli.py'
        def command(*args):
            proc = subprocess.run([sys.executable, '-B', str(cli), *map(str, args)], cwd=root, text=True, capture_output=True)
            assert proc.returncode == 0, proc.stdout + proc.stderr
            return json.loads(proc.stdout)
        def save(name, value):
            path = root / name; path.write_text(json.dumps(value) if isinstance(value, dict) else value)
            return path
        events = []
        env = command('new-envelope', root)
        env['capability_profile']['external'] = {'tasks_mcp': 'absent', 'open_brain': 'absent'}
        env['mutation_scope']['M2'] = ['project_session.md', 'project_index.md', 'pending_learnings.md']
        entry = save('entry.txt', HF.ENTRY_DRAFT); index = save('index.txt', 'approved index')
        envelope = save('envelope.json', env); draft = command('freeze-draft', envelope, entry, index)
        events.append(('shown_scope', draft['scope_lines']))
        assert '(optional; new candidate blocks only)' in draft['scope_lines'] and 'delete' not in draft['scope_lines']
        receipt_file = save('receipt.json', draft)
        receipt = command('approve-draft', receipt_file, draft['scope_lines'], '--owner-reply', 'Approve the close including optional staging')
        save('receipt.json', receipt)
        env['approval'] = {'granted': True, 'scope_string': draft['scope_lines']}; save('envelope.json', env)
        events.append(('append', command('append', envelope, entry, receipt_file)))
        events.append(('index', command('write-approved', envelope, receipt_file, 'project_index.md', index, '--expect', receipt['m2_preimages']['project_index.md'])))
        content = save('new-candidates.txt', BLOCK)
        staged = command('write-approved', envelope, receipt_file, 'pending_learnings.md', content, '--operation', 'stage', '--expect', 'absent')
        assert staged['readback_ok']
        events.append(('readback', (root / 'pending_learnings.md').read_text()))
        events.append(('show_candidates', events[-1][1]))
        events.append(('owner', 'Keep the candidates in pending_learnings.md'))
        # Keep needs no new receipt, transition or write.
        assert events[-3][0] == 'readback' and events[-2][1] == BLOCK
        assert not command('resume', root)['unfinished_operations']; clean(root)


def run():
    failures = []
    for label, fn in CHECKS:
        try: fn()
        except Exception as exc: failures.append(f'{label}: {type(exc).__name__}: {exc}')
    return failures
