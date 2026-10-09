"""Deterministic quality checks for captured posting descriptions.

These checks detect known failure shapes and bind evidence to bytes. A PASS is
eligibility evidence for the ingest gate; it is not proof that a source is true.
"""
import hashlib
import json
import re

HEX64 = re.compile(r'^[0-9a-f]{64}$')
NODE_ROLES = {'text', 'link'}
CHECK_KINDS = {'independent_comparison', 'reacquisition'}
INDEPENDENT_METHODS = {'rendered_dom_text', 'reference_description'}
SOURCE_METHODS = {'official_api', 'public_json_ld', 'public_html', 'owner_provided_artifact'}
EXPLICIT_TRUNCATION = re.compile(
    r'(?:\.\.\.|…)(?:\s*$|\s*(?:read|show|see|continue)\s+more\b)|'
    r'\b(?:read|show|see|continue)\s+more\b|\b(?:content|description|text)\s+(?:was\s+)?(?:clipped|truncated)\b',
    re.I,
)

def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()

def _norm(value):
    return re.sub(r'\s+', ' ', value).strip()

def ordered_native_text(nodes):
    """Return text and link labels in observed order; reject ambiguous nodes."""
    if not isinstance(nodes, list) or not nodes:
        raise ValueError('native_nodes must be a nonempty ordered list')
    values = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or set(node) != {'role', 'text'}:
            raise ValueError(f'native_nodes[{index}] must contain only role and text')
        if node['role'] not in NODE_ROLES or not isinstance(node['text'], str) or not node['text'].strip():
            raise ValueError(f'native_nodes[{index}] has invalid role or text')
        values.append(node['text'])
    return '\n'.join(values)

def validate_quality(record, require_pass=False):
    """Recompute capture quality; optionally raise unless the result passes."""
    jid = str(record.get('id', 'record'))
    description = record.get('description')
    provenance = record.get('provenance')
    evidence = record.get('quality_evidence')
    flags, hard, suspicions = [], [], []
    if not isinstance(description, str) or not description.strip():
        hard.append('DESCRIPTION_MISSING')
        description = ''
    description_sha = hashlib.sha256(description.encode('utf-8')).hexdigest()
    if not isinstance(provenance, dict):
        hard.append('PROVENANCE_MISSING')
        provenance = {}
    method = provenance.get('method')
    if not isinstance(evidence, dict):
        hard.append('QUALITY_EVIDENCE_MISSING')
        evidence = {}
    allowed_evidence = {
        'end_verified', 'end_marker', 'truncation_flags', 'native_scope', 'independent_check',
        'http_status', 'response_sha256', 'endpoint', 'provider_job_id',
        'structured_type', 'single_job_bound', 'container_count', 'container_closed',
        'artifact_sha256', 'artifact_path', 'availability_verified',
        'capture_sha256', 'capture_path',
        'description_length', 'truncation_scan_sha256', 'structural_identity',
    }
    unknown = set(evidence) - allowed_evidence
    if unknown:
        hard.append('QUALITY_EVIDENCE_UNKNOWN_FIELDS')
    marker = evidence.get('end_marker')
    if evidence.get('end_verified') is not True or not isinstance(marker, str) or not marker.strip():
        hard.append('END_NOT_VERIFIED')
    elif not _norm(description).endswith(_norm(marker)):
        hard.append('END_MARKER_MISMATCH')
    reported = evidence.get('truncation_flags')
    if not isinstance(reported, list) or any(not isinstance(x, str) or not x.strip() for x in reported):
        hard.append('TRUNCATION_FLAGS_INVALID')
    elif reported:
        suspicions.append('EXPLICIT_TRUNCATION_FLAG')
    recomputed_flags = (['EXPLICIT_CLIPPED_OR_READ_MORE_SIGNAL']
                        if EXPLICIT_TRUNCATION.search(_norm(description)) else [])
    if reported != recomputed_flags:
        hard.append('TRUNCATION_SCAN_MISMATCH')
    if recomputed_flags and 'EXPLICIT_TRUNCATION_FLAG' not in suspicions:
        suspicions.append('EXPLICIT_TRUNCATION_FLAG')
    if evidence.get('description_length') is not None:
        if evidence.get('description_length') != len(description):
            hard.append('DESCRIPTION_LENGTH_MISMATCH')
        expected_scan = _digest({
            'method': method, 'description': description, 'flags': recomputed_flags,
        })
        if evidence.get('truncation_scan_sha256') != expected_scan:
            hard.append('TRUNCATION_SCAN_HASH_MISMATCH')
    if method == 'native_text':
        if evidence.get('native_scope') != 'job_description_only':
            hard.append('NATIVE_SCOPE_NOT_JOB_DESCRIPTION_ONLY')
        try:
            nodes_text = ordered_native_text(record.get('native_nodes'))
            if _norm(nodes_text) != _norm(description):
                hard.append('ORDERED_NATIVE_TEXT_MISMATCH')
            lengths = [len(node['text']) for node in record['native_nodes']]
            if any(length == 512 for length in lengths):
                suspicions.append('NATIVE_NODE_EXACT_512')
        except ValueError:
            hard.append('NATIVE_NODES_MISSING_OR_INVALID')
    elif method == 'official_api':
        if evidence.get('http_status') != 200:
            hard.append('OFFICIAL_API_HTTP_STATUS_NOT_200')
        if not isinstance(evidence.get('response_sha256'), str) or not HEX64.fullmatch(evidence['response_sha256']):
            hard.append('OFFICIAL_API_RESPONSE_HASH_MISSING')
        endpoint = evidence.get('endpoint')
        if not isinstance(endpoint, str) or not endpoint.startswith('https://'):
            hard.append('OFFICIAL_API_ENDPOINT_INVALID')
        if not isinstance(evidence.get('provider_job_id'), str) or not evidence['provider_job_id'].strip():
            hard.append('OFFICIAL_API_JOB_ID_MISSING')
        if evidence.get('single_job_bound') is not True:
            hard.append('OFFICIAL_API_NOT_SINGLE_JOB_BOUND')
        if evidence.get('structural_identity') not in {
            'greenhouse:content', 'lever:description+lists+additional',
            'smartrecruiters:jobAd.sections',
        }:
            hard.append('OFFICIAL_API_STRUCTURE_INVALID')
    elif method == 'public_json_ld':
        if evidence.get('http_status') != 200:
            hard.append('JSON_LD_HTTP_STATUS_NOT_200')
        if not isinstance(evidence.get('response_sha256'), str) or not HEX64.fullmatch(evidence['response_sha256']):
            hard.append('JSON_LD_RESPONSE_HASH_MISSING')
        if str(evidence.get('structured_type', '')).casefold() != 'jobposting':
            hard.append('JSON_LD_TYPE_NOT_JOB_POSTING')
        if evidence.get('single_job_bound') is not True:
            hard.append('JSON_LD_NOT_SINGLE_JOB_BOUND')
        if not isinstance(evidence.get('container_count'), int) or evidence['container_count'] < 1:
            hard.append('JSON_LD_CONTAINER_COUNT_INVALID')
        if evidence.get('structural_identity') != 'schema.org:JobPosting.description':
            hard.append('JSON_LD_STRUCTURE_INVALID')
    elif method == 'public_html':
        if evidence.get('http_status') != 200:
            hard.append('PUBLIC_HTML_HTTP_STATUS_NOT_200')
        if not isinstance(evidence.get('response_sha256'), str) or not HEX64.fullmatch(evidence['response_sha256']):
            hard.append('PUBLIC_HTML_RESPONSE_HASH_MISSING')
        if evidence.get('single_job_bound') is not True or evidence.get('container_count') != 1:
            hard.append('PUBLIC_HTML_NOT_SINGLE_JOB_BOUND')
        if evidence.get('container_closed') is not True:
            hard.append('PUBLIC_HTML_END_BOUNDARY_MISSING')
        if evidence.get('structural_identity') != 'html:closed-job-description-container':
            hard.append('PUBLIC_HTML_STRUCTURE_INVALID')
    elif method == 'owner_provided_artifact':
        if not isinstance(evidence.get('artifact_sha256'), str) or not HEX64.fullmatch(evidence['artifact_sha256']):
            hard.append('OWNER_ARTIFACT_HASH_MISSING')
        if not isinstance(evidence.get('artifact_path'), str) or not evidence['artifact_path'].strip():
            hard.append('OWNER_ARTIFACT_PATH_MISSING')
        if evidence.get('availability_verified') is not False:
            hard.append('OWNER_ARTIFACT_MUST_NOT_CLAIM_LIVE_AVAILABILITY')
    elif method == 'rendered_dom_text':
        if evidence.get('capture_sha256') is not None:
            if not isinstance(evidence.get('capture_sha256'), str) or not HEX64.fullmatch(evidence['capture_sha256']):
                hard.append('RENDERED_CAPTURE_HASH_INVALID')
            if not isinstance(evidence.get('capture_path'), str) or not evidence['capture_path'].strip():
                hard.append('RENDERED_CAPTURE_PATH_MISSING')
    else:
        hard.append('CAPTURE_METHOD_UNSUPPORTED')
    independent = evidence.get('independent_check')
    independent_ok = False
    if independent is not None:
        if not isinstance(independent, dict) or set(independent) != {'kind','browser','method','captured_at','description','description_sha256','complete','evidence'}:
            hard.append('INDEPENDENT_CHECK_INVALID')
        else:
            independent_ok = (
                independent.get('kind') in CHECK_KINDS
                and isinstance(independent.get('browser'), str) and independent['browser'].strip()
                and independent.get('method') in INDEPENDENT_METHODS
                and isinstance(independent.get('captured_at'), str) and independent['captured_at'].strip()
                and independent.get('complete') is True
                and isinstance(independent.get('evidence'), str) and independent['evidence'].strip()
                and isinstance(independent.get('description'), str)
                and independent['description'] == description
                and isinstance(independent.get('description_sha256'), str)
                and HEX64.fullmatch(independent['description_sha256'])
                and independent['description_sha256'] == description_sha
                and independent['description_sha256'] == hashlib.sha256(independent['description'].encode('utf-8')).hexdigest()
                and independent['browser'].strip().casefold() != str(provenance.get('browser', '')).strip().casefold()
                and independent['method'].strip().casefold() != str(provenance.get('method', '')).strip().casefold()
            )
            if not independent_ok:
                hard.append('INDEPENDENT_CHECK_NOT_DISTINCT_COMPLETE_TEXT_MATCH')
    unresolved = suspicions if suspicions and not independent_ok else []
    flags.extend(hard); flags.extend(suspicions)
    quality_input = {
        'id': jid, 'description_sha256': description_sha,
        'provenance': provenance, 'native_nodes': record.get('native_nodes'),
        'quality_evidence': evidence,
    }
    status = 'PASS' if not hard and not unresolved else 'BLOCKED'
    result = {
        'schema': 'CaptureQualityV1', 'status': status,
        'eligible_for_ingest': status == 'PASS',
        'flags': flags, 'unresolved_flags': hard + unresolved,
        'description_sha256': description_sha,
        'quality_input_sha256': _digest(quality_input),
        'limitations': 'Deterministic checks detect known truncation and binding failures; PASS does not prove source truth or completeness beyond supplied evidence.'
    }
    result['quality_result_sha256'] = _digest(result)
    if require_pass and status != 'PASS':
        raise ValueError(f'{jid}: acquisition quality blocked: {", ".join(result["unresolved_flags"])}')
    return result

def require_ingest_quality(record):
    """Compatibility wrapper for callers that require a passing result."""
    return validate_quality(record, require_pass=True)
