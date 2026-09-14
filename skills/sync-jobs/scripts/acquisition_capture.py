#!/usr/bin/env python3
"""Validate and atomically save browser-captured acquisition-only evidence."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from acquisition_quality import validate_quality

ID = re.compile(r'^\d+$')
URL = re.compile(r'^https://(?:www\.)?linkedin\.com/jobs/view/(\d+)/?(?:\?.*)?$')
METHODS = {'native_text', 'rendered_dom_text'}
# These are capture input fields. ``source_record_sha256``, ``quality`` and
# ``completeness_attestation`` are derived by this module and are accepted only
# by ``revalidate_record`` after the input fields have been rechecked.
RECORD_FIELDS = {'id','title','company','location','employmentType','listedAt','status','url','description','description_sha256','provenance','native_nodes','quality_evidence','source_evidence','capture_path','capture_sha256'}
DERIVED_RECORD_FIELDS = {'source_record_sha256','completeness_attestation','quality'}
PROVENANCE_FIELDS = {'browser','method','captured_at','complete_text','completion_evidence','status_certain','status_uncertainty','status_source'}
SOURCE_EVIDENCE_FIELDS = {'inline_links','inline_urls','widget_text','raw_text','rendered_text','observed_sections','boundary_notes'}
FAILURE_FIELDS = {'id','reason','attempts','status_uncertainty','last_observed_status','failure_kind','evidence','browser_evidence','captured_at','browser','method','completion_evidence','capture_path','capture_sha256','compatibility_note'}
FAILURE_KINDS = {'source_unavailable','capture_failed','unvisited'}
BUNDLE_FIELDS = {'schema','mode','created_at','selected_ids','records','failures','complete','quality_complete','quality_blocked_ids','claims','source_input_sha256'}

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def require_text(record, key):
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{record.get("id", "record")}: {key} must be nonempty text')
    return value

def validate_source_evidence(value, jid):
    """Validate retained raw/source evidence without widening quality fields."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f'{jid}: source_evidence must be an object')
    unknown = set(value) - SOURCE_EVIDENCE_FIELDS
    if unknown:
        raise ValueError(f'{jid}: source_evidence contains unsupported fields: {sorted(unknown)}')
    for key, child in value.items():
        if key in {'inline_urls', 'observed_sections'}:
            if not isinstance(child, list) or any(not isinstance(item, str) or not item.strip() for item in child):
                raise ValueError(f'{jid}: source_evidence.{key} must be a list of nonempty text')
        elif key == 'inline_links':
            if not isinstance(child, list):
                raise ValueError(f'{jid}: source_evidence.inline_links must be a list')
            for item in child:
                if isinstance(item, str):
                    if not item.strip():
                        raise ValueError(f'{jid}: source_evidence.inline_links contains empty text')
                elif isinstance(item, dict):
                    if set(item) - {'label', 'text', 'url', 'href'} or not any(isinstance(item.get(k), str) and item[k].strip() for k in ('label', 'text', 'url', 'href')):
                        raise ValueError(f'{jid}: source_evidence.inline_links item has unsupported or empty fields')
                else:
                    raise ValueError(f'{jid}: source_evidence.inline_links items must be text or labeled URL objects')
        elif not isinstance(child, str):
            raise ValueError(f'{jid}: source_evidence.{key} must be text')
    return value

def _validate_capture_path_fields(record, jid):
    if 'capture_path' in record and (not isinstance(record['capture_path'], str) or not record['capture_path'].strip()):
        raise ValueError(f'{jid}: capture_path must be nonempty text when supplied')
    if 'capture_sha256' in record and (not isinstance(record['capture_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', record['capture_sha256'])):
        raise ValueError(f'{jid}: capture_sha256 must be a lowercase SHA-256 when supplied')

def validate_record(record, selected):
    unknown = set(record) - RECORD_FIELDS
    if unknown:
        raise ValueError(f'record contains unsupported fields: {sorted(unknown)}')
    jid = str(record.get('id', ''))
    if not ID.fullmatch(jid) or jid not in selected:
        raise ValueError(f'Unexpected or invalid record ID {jid!r}')
    for key in ('title', 'company', 'url', 'description'):
        require_text(record, key)
    match = URL.match(record['url'])
    if not match or match[1] != jid:
        raise ValueError(f'{jid}: canonical LinkedIn URL does not match ID')
    validate_source_evidence(record.get('source_evidence'), jid)
    _validate_capture_path_fields(record, jid)
    provenance = record.get('provenance')
    if not isinstance(provenance, dict):
        raise ValueError(f'{jid}: provenance is required')
    unknown_provenance = set(provenance) - PROVENANCE_FIELDS
    if unknown_provenance:
        raise ValueError(f'{jid}: provenance contains unsupported fields: {sorted(unknown_provenance)}')
    for key in ('browser', 'captured_at', 'completion_evidence'):
        require_text(provenance, key)
    if provenance.get('method') not in METHODS:
        raise ValueError(f'{jid}: unsupported provenance method')
    if provenance.get('complete_text') is not True:
        raise ValueError(f'{jid}: complete_text must be explicitly true')
    if not isinstance(provenance.get('status_certain'), bool):
        raise ValueError(f'{jid}: status_certain must be boolean')
    if not provenance['status_certain'] and not str(provenance.get('status_uncertainty', '')).strip():
        raise ValueError(f'{jid}: retain status_uncertainty when status is uncertain')
    out = {key: record[key] for key in RECORD_FIELDS if key in record and key != 'description_sha256'}
    out['id'] = jid
    description_sha256 = hashlib.sha256(record['description'].encode('utf-8')).hexdigest()
    supplied_hash = record.get('description_sha256')
    if supplied_hash is not None and supplied_hash != description_sha256:
        raise ValueError(f'{jid}: supplied description_sha256 does not match transferred text')
    out['description_sha256'] = description_sha256
    # Hash only source input fields.  ``description_sha256`` is derived from
    # the same description and is deliberately excluded so revalidation of a
    # normalized emitted record yields the identical source-record digest.
    source_input = {key: value for key, value in record.items() if key != 'description_sha256'}
    out['source_record_sha256'] = digest(source_input)
    out['completeness_attestation'] = {
        'complete_text': True,
        'evidence': provenance['completion_evidence'],
        'attested_from_capture': True
    }
    out['quality'] = validate_quality(out)
    return out

def _validate_source_unavailable_evidence(failure, jid):
    evidence = failure.get('evidence') or failure.get('browser_evidence')
    if not isinstance(evidence, dict):
        raise ValueError(f'{jid}: source_unavailable requires explicit browser evidence')
    # Unavailable status is a structured observation, never a substring match
    # over arbitrary UI text.  Otherwise an open posting with an unrelated
    # note containing "closed" could be misclassified as unavailable.
    status = evidence.get('status')
    if status not in {'invalid', 'removed', 'unavailable'}:
        raise ValueError(f'{jid}: source_unavailable evidence status must be exactly invalid, removed or unavailable')

    id_values = [evidence.get(key) for key in ('id', 'linkedin_id', 'job_id') if key in evidence]
    if not id_values or any(str(value) != jid for value in id_values):
        raise ValueError(f'{jid}: source_unavailable evidence must bind the numeric ID exactly')

    canonical_url = f'https://www.linkedin.com/jobs/view/{jid}/'
    url_values = [evidence.get(key) for key in ('canonical_url', 'url', 'source_url', 'observed_url') if key in evidence]
    if not url_values or any(value != canonical_url for value in url_values):
        raise ValueError(f'{jid}: source_unavailable evidence must bind the exact canonical URL')

    browser = evidence.get('browser')
    if not isinstance(browser, str) or not browser.strip():
        raise ValueError(f'{jid}: source_unavailable evidence must identify the browser surface')
    method = evidence.get('method')
    if method not in METHODS:
        raise ValueError(f'{jid}: source_unavailable evidence method must be rendered_dom_text or native_text')
    captured_at = evidence.get('captured_at')
    if not isinstance(captured_at, str) or not captured_at.strip():
        raise ValueError(f'{jid}: source_unavailable evidence must include captured_at')

    # If duplicated at the failure level, these fields must agree with the
    # structured evidence rather than creating two competing observations.
    for key in ('browser', 'method', 'captured_at'):
        if key in failure and failure[key] != evidence[key]:
            raise ValueError(f'{jid}: source_unavailable {key} conflicts with its evidence')

def normalize_failure(failure, selected):
    if not isinstance(failure, dict):
        raise ValueError('failure must be an object')
    unknown = set(failure) - FAILURE_FIELDS
    if unknown:
        raise ValueError(f'failure contains unsupported fields: {sorted(unknown)}')
    jid = str(failure.get('id', ''))
    if not ID.fullmatch(jid) or jid not in selected:
        raise ValueError(f'unexpected failure ID {jid!r}')
    require_text(failure, 'reason')
    attempts = failure.get('attempts')
    if attempts is not None:
        if not isinstance(attempts, list) or any(not isinstance(attempt, str) or not attempt.strip() for attempt in attempts):
            raise ValueError(f'{jid}: acquisition attempts must be nonempty provenance labels')
    kind = failure.get('failure_kind')
    compatibility = None
    if kind is None:
        # Existing acquisition bundles predate the enum.  They are retained as
        # capture failures only with an explicit compatibility note.
        kind = 'capture_failed'
        compatibility = 'Legacy failure record had no failure_kind; interpreted as capture_failed.'
    if kind not in FAILURE_KINDS:
        raise ValueError(f'{jid}: unsupported failure_kind {kind!r}')
    if kind != 'source_unavailable':
        require_text(failure, 'status_uncertainty')
    elif not str(failure.get('status_uncertainty') or '').strip():
        # The browser evidence itself is the uncertainty record for an
        # unavailable source; retain a deterministic explanatory value.
        failure = dict(failure)
        failure['status_uncertainty'] = 'Unavailable status is bound to the explicit browser evidence below.'
    if kind == 'source_unavailable':
        _validate_source_unavailable_evidence(failure, jid)
    result = dict(failure)
    result['id'] = jid
    result['failure_kind'] = kind
    if compatibility:
        result['compatibility_note'] = compatibility
    return result

def revalidate_record(record, selected, require_normalized=False):
    """Revalidate an emitted acquisition record, including derived fields.

    ``acquire-save`` emits ``quality`` and ``source_record_sha256`` fields that
    are not valid capture inputs.  Strip those fields, run the input contract,
    and compare the derived values so a bundle cannot bypass recomputation.
    """
    if not isinstance(record, dict):
        raise ValueError('record must be an object')
    unknown = set(record) - RECORD_FIELDS - DERIVED_RECORD_FIELDS
    if unknown:
        raise ValueError(f'record contains unsupported fields: {sorted(unknown)}')
    capture_input = {key: record[key] for key in RECORD_FIELDS if key in record}
    normalized = validate_record(capture_input, selected)
    supplied_source_hash = record.get('source_record_sha256')
    if supplied_source_hash is not None:
        # The original input validator computed this digest before it added the
        # derived description hash.  Accept that historical digest as well as
        # the fully normalized form, while still requiring a byte-for-byte
        # digest of the source fields.
        without_description_hash = {
            key: value for key, value in capture_input.items()
            if key != 'description_sha256'
        }
        if supplied_source_hash not in {
            normalized['source_record_sha256'],
            digest(capture_input),
            digest(without_description_hash),
        }:
            raise ValueError(f'{normalized["id"]}: source_record_sha256 does not match capture input')
    supplied_quality = record.get('quality')
    if supplied_quality is not None and supplied_quality != normalized['quality']:
        raise ValueError(f'{normalized["id"]}: embedded quality result is stale or fabricated')
    if 'completeness_attestation' in record:
        attestation = record['completeness_attestation']
        expected = normalized['completeness_attestation']
        if attestation != expected:
            raise ValueError(f'{normalized["id"]}: completeness attestation mismatch')
    if require_normalized:
        for key in ('description_sha256', 'source_record_sha256', 'quality', 'completeness_attestation'):
            if key not in record:
                raise ValueError(f'{normalized["id"]}: normalized acquisition record is missing {key}')
        if record.get('description_sha256') != normalized['description_sha256']:
            raise ValueError(f'{normalized["id"]}: normalized description hash is stale')
        without_description_hash = {
            key: value for key, value in capture_input.items()
            if key != 'description_sha256'
        }
        acceptable_source_hashes = {
            normalized['source_record_sha256'],
            digest(capture_input),
            digest(without_description_hash),
        }
        if not isinstance(record.get('source_record_sha256'), str) or record['source_record_sha256'] not in acceptable_source_hashes:
            raise ValueError(f'{normalized["id"]}: normalized source_record_sha256 is missing or stale')
    return normalized

def revalidate_bundle(bundle, selected=None, allow_partial=False, require_normalized=False):
    """Recompute an emitted ``SelectedPostingAcquisitionV1`` envelope.

    Unlike the input-only CLI validator, this accepts the normalized output
    envelope and rechecks every capture record from its source fields.  Partial
    coverage is allowed only for on-demand comparison, where absent IDs become
    ``unvisited``; ordinary ``acquire-save`` remains complete-batch strict.
    """
    if not isinstance(bundle, dict) or bundle.get('schema') != 'SelectedPostingAcquisitionV1':
        raise ValueError('bundle requires schema SelectedPostingAcquisitionV1')
    unknown = set(bundle) - BUNDLE_FIELDS
    if unknown:
        raise ValueError(f'bundle contains unsupported fields: {sorted(unknown)}')
    records_raw = bundle.get('records')
    failures_raw = bundle.get('failures', [])
    if not isinstance(records_raw, list) or not isinstance(failures_raw, list):
        raise ValueError('bundle records[] and failures[] must be lists')
    envelope_selected = bundle.get('selected_ids')
    if envelope_selected is None:
        envelope_selected = []
        for item in records_raw + failures_raw:
            if isinstance(item, dict) and item.get('id') is not None:
                envelope_selected.append(str(item['id']))
    envelope_selected = [str(item) for item in envelope_selected]
    if any(not ID.fullmatch(item) for item in envelope_selected) or len(envelope_selected) != len(set(envelope_selected)):
        raise ValueError('bundle selected_ids must be unique numeric IDs')
    selected_set = set(envelope_selected)
    if selected is not None:
        selected_set = {str(item) for item in selected}
        if any(not ID.fullmatch(item) for item in selected_set) or len(selected_set) != len(list(selected)):
            raise ValueError('comparison selected IDs must be unique numeric IDs')
        if not set(envelope_selected).issubset(selected_set):
            raise ValueError('bundle contains IDs outside the frozen selection')
    normalized_records = []
    record_ids = []
    for record in records_raw:
        normalized = revalidate_record(record, selected_set, require_normalized=require_normalized)
        normalized_records.append(normalized)
        record_ids.append(normalized['id'])
    if len(record_ids) != len(set(record_ids)):
        raise ValueError('bundle contains duplicate record IDs')
    normalized_failures = []
    failure_ids = []
    for failure in failures_raw:
        normalized = normalize_failure(failure, selected_set)
        normalized_failures.append(normalized)
        failure_ids.append(normalized['id'])
    if len(failure_ids) != len(set(failure_ids)) or set(record_ids) & set(failure_ids):
        raise ValueError('bundle IDs must occur once as a record or failure')
    covered = set(record_ids) | set(failure_ids)
    if not allow_partial and covered != selected_set:
        raise ValueError('every selected ID must be retained as a record or failure')
    if allow_partial and not covered.issubset(selected_set):
        raise ValueError('bundle coverage contains an unselected ID')
    quality_blocked = [record['id'] for record in normalized_records if not record['quality']['eligible_for_ingest']]
    # An on-demand comparison may intentionally consume a bundle that covers
    # only part of a larger frozen selection.  Validate envelope claims against
    # the bundle's own selected_ids; the caller separately records the omitted
    # frozen IDs as unvisited.
    envelope_complete = covered == set(envelope_selected) and not normalized_failures and not quality_blocked
    complete = covered == selected_set and not normalized_failures and not quality_blocked
    if bundle.get('complete') is True and not envelope_complete:
        raise ValueError('bundle complete claim does not match normalized records/failures')
    if bundle.get('quality_complete') is True and (normalized_failures or quality_blocked or covered != set(envelope_selected)):
        raise ValueError('bundle quality_complete claim does not match normalized quality')
    if require_normalized:
        if not isinstance(bundle.get('created_at'), str) or not bundle.get('created_at').strip():
            raise ValueError('normalized acquisition bundle is missing created_at')
        source_hash = bundle.get('source_input_sha256')
        if not isinstance(source_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', source_hash):
            raise ValueError('normalized acquisition bundle is missing source_input_sha256')
    result = {
        'schema': 'SelectedPostingAcquisitionV1',
        'mode': bundle.get('mode', 'ACQUISITION_ONLY_NOT_OFFICIAL_NEW_IDS'),
        'created_at': bundle.get('created_at'),
        'selected_ids': envelope_selected,
        'records': normalized_records,
        'failures': normalized_failures,
        'complete': complete,
        'quality_complete': complete,
        'quality_blocked_ids': quality_blocked,
        'claims': bundle.get('claims', {}),
        'source_input_sha256': bundle.get('source_input_sha256'),
    }
    return result

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--records-json', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--selected-id', action='append', required=True)
    args = p.parse_args(argv)
    selected = [str(x) for x in args.selected_id]
    if any(not ID.fullmatch(x) for x in selected) or len(set(selected)) != len(selected):
        p.error('selected IDs must be unique numeric LinkedIn IDs')
    source_bytes = Path(args.records_json).read_bytes()
    source = json.loads(source_bytes.decode('utf-8'))
    if not isinstance(source, dict) or not isinstance(source.get('records'), list) or not isinstance(source.get('failures', []), list):
        p.error('input must contain records[] and optional failures[]')
    try:
        # ``--records-json`` is the input-only capture shape and historically
        # omitted the output envelope fields.  Add only the explicit envelope
        # defaults here; emitted normalized bundles go through the same
        # revalidation path without any bypass.
        source_for_validation = dict(source)
        source_for_validation.setdefault('schema', 'SelectedPostingAcquisitionV1')
        source_for_validation.setdefault('selected_ids', selected)
        normalized = revalidate_bundle(source_for_validation, set(selected), allow_partial=False)
    except ValueError as e:
        p.error(str(e))
    records = normalized['records']
    failures = normalized['failures']
    quality_blocked_ids = normalized['quality_blocked_ids']
    payload = {
        'schema': 'SelectedPostingAcquisitionV1',
        'mode': 'ACQUISITION_ONLY_NOT_OFFICIAL_NEW_IDS',
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'selected_ids': selected,
        'records': records,
        'failures': failures,
        'complete': not failures and not quality_blocked_ids,
        'quality_complete': not failures and not quality_blocked_ids,
        'quality_blocked_ids': quality_blocked_ids,
        'claims': {'official_new_ids': False, 'sync_completed': False, 'tracker_or_archive_gates_run': False},
        'source_input_sha256': hashlib.sha256(source_bytes).hexdigest()
    }
    out = Path(args.out).expanduser().resolve()
    if out.exists():
        p.error('output already exists; choose a new evidence path')
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + out.name + '.', suffix='.tmp', dir=out.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8') + b'\n')
            f.flush(); os.fsync(f.fileno())
        try:
            os.link(name, out)
        except FileExistsError:
            p.error('output was created concurrently; choose a new evidence path')
        os.unlink(name)
    finally:
        if os.path.exists(name): os.unlink(name)
    file_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    readback = json.loads(out.read_text(encoding='utf-8'))
    if readback != payload:
        raise RuntimeError('exact readback mismatch')
    status = 'SAVED_AND_READ_BACK' if payload['quality_complete'] else 'SAVED_AND_READ_BACK_WITH_QUALITY_BLOCKS'
    print(json.dumps({'status': status, 'path': str(out), 'sha256': file_sha, 'record_count': len(records), 'failure_count': len(failures), 'quality_complete': payload['quality_complete'], 'quality_blocked_ids': quality_blocked_ids}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
