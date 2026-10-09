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
import stat
import sys
import tempfile

SKILL = Path(__file__).resolve().parents[1]

TRIAGE_WRITE_FIELDS = {
    # Legacy profile output.
    'Track', 'Estatus', 'Fit Score', 'Priority', 'Sponsor Status',
    'Next Action', 'Next Action Date', 'Triage Summary', 'Decision Driver',
    'Primary Risk / Blocker', 'Key Uplifts', 'Triage Date', 'Triage Batch',
    'Comentarios',
    # Newer generic profile output. These are result columns, not policy rules.
    'Lane', 'Market Tier', 'Eligibility', 'Priority Score', 'Match',
}


def _has_report_name_option(options):
    return any(arg == '--report-name' or arg.startswith('--report-name=')
               for arg in options)


def _extract_option(options, name):
    """Move one global option ahead of a downstream subcommand."""
    leading = []
    remaining = []
    index = 0
    while index < len(options):
        token = options[index]
        if token == name:
            leading.append(token)
            if index + 1 < len(options):
                leading.append(options[index + 1])
                index += 2
                continue
        elif token.startswith(name + '='):
            leading.append(token)
        else:
            remaining.append(token)
        index += 1
    return leading, remaining


def _unique_report_name(profile):
    workspace = profile.get('default_workspace', {})
    reports = Path(workspace.get('reports', 'JobPostings/_meta'))
    if reports.is_absolute() or '..' in reports.parts:
        raise ValueError('Profile report directory must be project-relative')
    stamp = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')
    return (reports / f'triage_{stamp}.md').as_posix()


def _parse_score_paths(options):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--worklist', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--preview', required=True)
    return parser.parse_known_args(options)


def _staged_score_options(parsed, remaining, staged_out, staged_preview):
    # Rebuild the known options so argparse abbreviations and repeated flags
    # cannot leave a caller output path in the policy's argument list.
    return [
        '--worklist', parsed.worklist,
        *remaining,
        '--out', str(staged_out),
        '--preview', str(staged_preview),
    ]


def _pin_new_score_destination(path, label):
    requested = Path(path).expanduser()
    if requested.name in {'', '.', '..'}:
        raise ValueError(f'{label} destination must name a file')
    parent = requested.parent if str(requested.parent) else Path('.')
    resolved_parent = parent.resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
    flags |= getattr(os, 'O_CLOEXEC', 0)
    directory_fd = os.open(resolved_parent, flags)
    if not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
        os.close(directory_fd)
        raise NotADirectoryError(f'{label} parent is not a directory: {parent}')
    destination = {
        'path': requested,
        'parent': resolved_parent,
        'name': requested.name,
        'fd': directory_fd,
        'identity': (os.fstat(directory_fd).st_dev, os.fstat(directory_fd).st_ino),
        'canonical': resolved_parent / requested.name,
        'label': label,
    }
    try:
        os.stat(destination['name'], dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return destination
    except BaseException:
        os.close(directory_fd)
        raise
    os.close(directory_fd)
    raise FileExistsError(f'refusing existing {label} destination: {requested}')


def _check_score_destination(destination):
    current_parent = destination['path'].parent.resolve(strict=True)
    current_info = os.stat(current_parent)
    if (current_parent != destination['parent'] or
            (current_info.st_dev, current_info.st_ino) != destination['identity']):
        raise RuntimeError(
            f"{destination['label']} parent changed during scoring: {destination['path']}"
        )
    try:
        os.stat(destination['name'], dir_fd=destination['fd'], follow_symlinks=False)
    except FileNotFoundError:
        return
    raise FileExistsError(
        f"{destination['label']} destination appeared during scoring: {destination['path']}"
    )


def _read_staged_regular_file(directory_fd, name, label):
    try:
        before = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        raise
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f'scorer {label} output is not a regular file')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
    file_fd = os.open(name, flags, dir_fd=directory_fd)
    try:
        opened = os.fstat(file_fd)
        if (not stat.S_ISREG(opened.st_mode) or
                (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError(f'scorer {label} output changed while being read')
        with os.fdopen(file_fd, 'rb', closefd=False) as stream:
            return stream.read()
    finally:
        os.close(file_fd)


def _verify_score_staging_directory(path, directory_fd):
    current = os.stat(path, follow_symlinks=False)
    pinned = os.fstat(directory_fd)
    if (not stat.S_ISDIR(current.st_mode) or
            (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino)):
        raise ValueError('scorer changed the private score staging directory')

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
        global_options, command_options = ([], rest)
        if args.command == 'ingest':
            global_options, command_options = _extract_option(rest, '--backup-dir')
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
        return module.main(['--tracker',str(tracker),*global_options,args.command,*command_options,*extra])
    if args.command=='worklist':
        module=importlib.import_module('build_worklist');module.PROJECT_ROOT=str(root)
        template_path=(directory/profile.get('judgment_template','judgment_template.json')).resolve()
        if not template_path.is_relative_to(directory):
            ap.error('Profile judgment template escaped its directory')
        module.JUDGMENT_TEMPLATE=json.loads(template_path.read_text())
        return module.main(['--tracker',str(tracker),*rest])
    if args.command=='score':
        score_options=list(rest)
        if not _has_report_name_option(score_options):
            try:
                score_options.extend(['--report-name', _unique_report_name(profile)])
            except ValueError as exc:
                ap.error(str(exc))
        output, remaining_score_options = _parse_score_paths(score_options)
        input_path = Path(output.worklist).expanduser().resolve(strict=False)
        destinations = []
        stage_directory_fd = None
        try:
            destinations.append(_pin_new_score_destination(output.out, 'score result'))
            destinations.append(_pin_new_score_destination(output.preview, 'score preview'))
            if destinations[0]['canonical'] == destinations[1]['canonical']:
                raise ValueError('score result and preview destinations must be distinct')
            if any(destination['canonical'] == input_path for destination in destinations):
                raise ValueError('score outputs must not alias the source worklist')

            with tempfile.TemporaryDirectory(prefix='sync-jobs-score-') as staging:
                os.chmod(staging, 0o700)
                staging_path = Path(staging)
                stage_flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
                stage_flags |= getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
                stage_directory_fd = os.open(staging_path, stage_flags)
                staged_out = staging_path / 'results.json'
                staged_preview = staging_path / 'preview.txt'
                staged_options = _staged_score_options(
                    output, remaining_score_options, staged_out, staged_preview
                )
                spec = importlib.util.spec_from_file_location(
                    'selected_profile_policy', policy_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                rc = module.main(staged_options)

                _verify_score_staging_directory(staging_path, stage_directory_fd)
                try:
                    result_bytes = _read_staged_regular_file(
                        stage_directory_fd, 'results.json', 'result'
                    )
                    preview_bytes = _read_staged_regular_file(
                        stage_directory_fd, 'preview.txt', 'preview'
                    )
                except FileNotFoundError:
                    if rc not in (None, 0):
                        return rc
                    raise

                payload = json.loads(result_bytes.decode('utf-8'))
                payload['profile'] = {
                    'id': profile['id'],
                    'version': profile['version'],
                    'policy_sha256': hashlib.sha256(policy_path.read_bytes()).hexdigest(),
                }
                result_bytes = json.dumps(
                    payload, indent=2, ensure_ascii=False
                ).encode('utf-8')

                # Check both leaves after scoring before publishing either. The
                # create-only helper repeats the check atomically at each link.
                for destination in destinations:
                    _check_score_destination(destination)
                from private_files import publish_private_file
                publish_private_file(
                    destinations[0]['path'], result_bytes,
                    directory_fd=destinations[0]['fd'],
                )
                publish_private_file(
                    destinations[1]['path'], preview_bytes,
                    directory_fd=destinations[1]['fd'],
                )
                return rc
        finally:
            if stage_directory_fd is not None:
                os.close(stage_directory_fd)
            for destination in destinations:
                os.close(destination['fd'])
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
        for result in payload.get('results',{}).values():
            if set(result.get('cells',{}))-TRIAGE_WRITE_FIELDS or result.get('append'):
                ap.error('Result contains fields outside sync/triage write scope')
        report=importlib.import_module('gen_report')
        with tempfile.TemporaryDirectory(prefix='sync-jobs-review-') as staging:
            report.main(['--project-root',str(root),'--worklist',checked.worklist,'--results',checked.results,'--out',str(Path(staging)/'review.md')])
        rest=['--results',checked.results,*writer_options]
        module=importlib.import_module('write_tracker')
        extra=[] if args.commit or '--dry-run' in rest else ['--dry-run']
        return module.main(['--tracker',str(tracker),*rest,*extra])
    if args.command=='report':
        checks=argparse.ArgumentParser()
        checks.add_argument('--worklist',required=True)
        checks.add_argument('--results',required=True)
        checked,_=checks.parse_known_args(rest)
        payload=json.loads(Path(checked.results).read_text())
        expected={'id':profile['id'],'version':profile['version'],'policy_sha256':hashlib.sha256(policy_path.read_bytes()).hexdigest()}
        if payload.get('profile')!=expected:
            ap.error('Results do not match the selected profile and policy version')
        work=json.loads(Path(checked.worklist).read_text())
        work_rows=work.get('rows',[])
        row_ids=[row.get('tracker_id') for row in work_rows]
        if len(set(row_ids))!=len(row_ids) or set(row_ids)!=set(payload.get('results',{})):
            ap.error('Worklist/result IDs differ or contain duplicates')
        module=importlib.import_module('gen_report');module.PROJECT_ROOT=str(root)
        return module.main(['--project-root',str(root),*rest])

if __name__=='__main__':
    raise SystemExit(main())
