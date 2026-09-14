#!/usr/bin/env python3
"""Skill-owned entry point. All project data paths are explicit; no project-code imports."""
import argparse
import datetime
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

SKILL = Path(__file__).resolve().parents[1]

def load_profile(name):
    directory = (SKILL / 'profiles' / name).resolve()
    if not directory.is_relative_to((SKILL / 'profiles').resolve()):
        raise ValueError('Profile must be inside this skill')
    data = json.loads((directory / 'profile.json').read_text())
    policy = (directory / data['policy']).resolve()
    if not policy.is_relative_to(directory):
        raise ValueError('Profile policy escaped its directory')
    return directory, data, policy

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project-root')
    ap.add_argument('--profile')
    ap.add_argument('--tracker', help='Absolute or project-relative tracker path')
    ap.add_argument('--commit', action='store_true', help="Enable the selected command's authorized writes")
    ap.add_argument('command', choices=['acquire-save','acquire-url','resume-url','external-ingest','audit-existing','refresh-existing','diff','ingest','reconcile','worklist','score','write','report'])
    args, rest = ap.parse_known_args(argv)
    if args.command in {'acquire-save', 'acquire-url', 'resume-url'} and args.commit:
        ap.error(f'{args.command} is acquisition-only and does not accept --commit')
    if args.command == 'acquire-save':
        module = importlib.import_module('acquisition_capture')
        return module.main(rest)
    if args.command == 'acquire-url':
        module = importlib.import_module('source_acquisition')
        return module.main(rest)
    if args.command == 'resume-url':
        module = importlib.import_module('source_acquisition')
        return module.resume_main(rest)
    if not args.project_root:
        ap.error('--project-root is required for tracker and archive commands')
    if not args.profile:
        ap.error('--profile is required for tracker and triage commands')
    root = Path(args.project_root).expanduser().resolve()
    if not root.is_dir(): ap.error('Project root does not exist')
    directory, profile, policy_path = load_profile(args.profile)
    tracker = Path(args.tracker or profile['default_workspace']['tracker_name'])
    if not tracker.is_absolute(): tracker = root / tracker
    tracker = tracker.resolve()
    if not tracker.is_relative_to(root): ap.error('Tracker must be inside the selected workspace')
    if any(x in rest for x in ['--tracker','--project-root']):ap.error('Pass workspace options before the command')
    os.environ['SYNC_JOBS_ROOT'] = str(root)
    import posting_compensation
    import posting_eligibility
    posting_compensation.ROOT = root
    posting_compensation.TRACKER = tracker
    posting_compensation.OUTPUT_DIR = root / 'JobPostings/_meta/compensation'
    posting_eligibility.ROOT = root
    posting_eligibility.OUTPUT_DIR = root / 'JobPostings/_meta/eligibility'
    if args.command == 'audit-existing':
        # ``audit-existing`` owns its explicit prepare/compare/local-check
        # phases.  It consumes captures; it never opens a browser or invokes
        # any retired private-endpoint helper.
        module = importlib.import_module('source_verification')
        return module.main(['--project-root', str(root), '--tracker', str(tracker), *rest])
    if args.command == 'refresh-existing':
        module = importlib.import_module('refresh_existing')
        refresh_args = ['--project-root', str(root), '--tracker', str(tracker), *rest]
        if args.commit:
            refresh_args.append('--commit')
        return module.main(refresh_args)
    if args.command in {'ingest','external-ingest','write'} and args.commit:
        if (tracker.parent / ('~$' + tracker.name)).exists():ap.error('Excel lock exists; close Excel before writing')
    if not tracker.exists() and args.command not in {'score','report'}:ap.error('Tracker does not exist')
    if args.command == 'external-ingest':
        module=importlib.import_module('external_intake')
        options=['--project-root',str(root),'--tracker',str(tracker),*rest]
        if not args.commit and '--dry-run' not in rest:options.append('--dry-run')
        return module.main(options)
    if args.command in {'diff','ingest','reconcile'}:
        module = importlib.import_module('sync_ingest')
        module.PROJECT_ROOT = str(root)
        module.DEFAULT_TRACKER = str(tracker)
        module.POSTINGS_DIR = str(root / 'JobPostings/postings')
        module.JOBPOSTINGS_TREE = str(root / 'JobPostings')
        module.META_DIR = str(root / 'JobPostings/_meta')
        if args.command == 'reconcile':
            p = argparse.ArgumentParser();p.add_argument('--saved-json', nargs='+', required=True)
            p.add_argument('--out-dir', required=True)
            options = p.parse_args(rest)
            output = Path(options.out_dir).resolve();output.mkdir(parents=True,exist_ok=True)
            opts=argparse.Namespace(tracker=str(tracker),saved_json=options.saved_json,backup_dir=str(output),dry_run=True)
            now=datetime.datetime.now()
            module._reconcile_and_report(opts,[],now.date().isoformat(),now.isoformat())
            return 0
        extra=[]
        if args.command=='ingest' and not args.commit and '--dry-run' not in rest:extra=['--dry-run']
        return module.main(['--tracker',str(tracker),args.command,*rest,*extra])
    if args.command=='worklist':
        module=importlib.import_module('build_worklist');module.PROJECT_ROOT=str(root)
        template_path=(directory/profile.get('judgment_template','judgment_template.json')).resolve()
        if not template_path.is_relative_to(directory):
            ap.error('Profile judgment template escaped its directory')
        module.JUDGMENT_TEMPLATE=json.loads(template_path.read_text())
        return module.main(['--tracker',str(tracker),*rest])
    if args.command=='score':
        spec=importlib.util.spec_from_file_location('selected_profile_policy',policy_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        rc=module.main(rest)
        parsed=argparse.ArgumentParser();parsed.add_argument('--out',required=True)
        output,_=parsed.parse_known_args(rest)
        path=Path(output.out);payload=json.loads(path.read_text())
        payload['profile']={'id':profile['id'],'version':profile['version'],'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest()}
        path.write_text(json.dumps(payload,indent=2,ensure_ascii=False))
        return rc
    if args.command=='write':
        checks=argparse.ArgumentParser();checks.add_argument('--results',required=True);checks.add_argument('--worklist',required=True)
        checked,writer_options=checks.parse_known_args(rest)
        payload=json.loads(Path(checked.results).read_text())
        expected={'id':profile['id'],'version':profile['version'],'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest()}
        if payload.get('profile')!=expected:ap.error('Results do not match the selected profile and policy version')
        work=json.loads(Path(checked.worklist).read_text())
        rows={row['tracker_id']:row for row in work.get('rows',[])}
        if len(rows)!=len(work.get('rows',[])) or set(rows)!=set(payload.get('results',{})):
            ap.error('Worklist/result IDs differ or contain duplicates')
        spec=importlib.util.spec_from_file_location('write_check_policy',policy_path)
        policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
        for tid, result in payload.get('results',{}).items():
            scored_date=result.get('cells',{}).get('Triage Date') or datetime.date.today().isoformat()
            expected_result=policy.derive(rows[tid],scored_date,payload['report_batch'])
            if result!=expected_result:
                ap.error('Worklist judgments differ from scored results; score again before writing')
        allowed={'Track','Estatus','Fit Score','Priority','Sponsor Status','Next Action','Next Action Date','Triage Summary','Decision Driver','Primary Risk / Blocker','Key Uplifts','Triage Date','Triage Batch','Comentarios'}
        for result in payload.get('results',{}).values():
            if set(result.get('cells',{}))-allowed or result.get('append'):
                ap.error('Result contains fields outside sync/triage write scope')
        report=importlib.import_module('gen_report')
        with tempfile.TemporaryDirectory(prefix='sync-jobs-review-') as staging:
            report.main(['--project-root',str(root),'--worklist',checked.worklist,'--results',checked.results,'--out',str(Path(staging)/'review.md')])
        rest=['--results',checked.results,*writer_options]
        module=importlib.import_module('write_tracker')
        extra=[] if args.commit or '--dry-run' in rest else ['--dry-run']
        return module.main(['--tracker',str(tracker),*rest,*extra])
    if args.command=='report':
        module=importlib.import_module('gen_report');module.PROJECT_ROOT=str(root)
        return module.main(['--project-root',str(root),*rest])

if __name__=='__main__':
    raise SystemExit(main())
