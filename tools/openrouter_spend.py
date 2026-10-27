#!/usr/bin/env python3
"""Check today's OpenRouter spend against the agent allowance, or record an agent run. Never prints a key.

Usage:
  python3 openrouter_spend.py             # spend check
  python3 openrouter_spend.py --record --harness codex --model <id> --route <route> \\
      --purpose "<short, no private details>" --private no [--requests N] [--cost USD|unknown]

Spend check
  The allowance key is the first match of:
    1. OPENROUTER_AGENT_KEY environment variable
    2. ~/.config/openrouter/agents.key (one line, file mode 0600)
  If OpenCode stores a different OpenRouter key (~/.local/share/opencode/auth.json),
  its spend today is added, so the allowance covers all agents. Keys kept elsewhere,
  such as project .env files, are not counted unless they are one of these.
  Calls GET https://openrouter.ai/api/v1/key once per key; this is free and runs no model.
  OpenRouter's day is the UTC day. The key's label is never printed: OpenRouter returns
  a masked key fragment there. The allowance defaults to $0.50 and can be overridden
  with OPENROUTER_AGENT_ALLOWANCE_USD.
  This check is advisory: agents running at the same moment can both spend the same
  remainder. Only a daily limit set on the key in OpenRouter is enforced.
  Exit codes: 0 allowance left, 3 allowance exhausted, 2 anything else (no key,
  request failed, unexpected response). Proceed only on exit 0.

Run log (--record)
  Appends one JSON line per run to ~/Library/Application Support/MetaClaude/agent-runs.jsonl
  (override with AGENT_RUN_LOG). Makes no network call. Metered routes need --cost; a
  missing cost is recorded as "unknown", never as zero. A run that broke the data rule
  (private data on a free or allowance route) is still recorded, with a policy_violation field.
  Exit codes: 0 recorded, 2 invalid arguments or the log could not be written.
"""
import argparse
import datetime
import fcntl
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_ALLOWANCE_USD = 0.50
AGENT_KEY_FILE = Path.home() / '.config/openrouter/agents.key'
OPENCODE_AUTH = Path.home() / '.local/share/opencode/auth.json'
DEFAULT_RUN_LOG = Path.home() / 'Library/Application Support/MetaClaude/agent-runs.jsonl'
KEY_URL = 'https://openrouter.ai/api/v1/key'
METERED_ROUTES = {'openrouter-allowance', 'approved-metered'}
NON_PRIVATE_ROUTES = {'openrouter-free', 'openrouter-allowance'}
ROUTES = sorted(METERED_ROUTES | {'subscription', 'local', 'openrouter-free'})
RECORD_FIELDS = ('harness', 'model', 'route', 'purpose', 'private', 'requests', 'cost')
MAX_PURPOSE = 200


class SpendError(Exception):
    """A spend check that cannot give a trustworthy answer; detail never contains a key."""

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status, self.detail = status, detail


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise SpendError('unexpected_response', f'{name} is not a finite number')
    return float(value)


def allowance_usd():
    raw = os.environ.get('OPENROUTER_AGENT_ALLOWANCE_USD')
    if not raw:
        return DEFAULT_ALLOWANCE_USD
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not (math.isfinite(value) and value > 0):
        raise SpendError('invalid_allowance', 'OPENROUTER_AGENT_ALLOWANCE_USD must be a positive number')
    return value


def agent_key():
    if os.environ.get('OPENROUTER_AGENT_KEY', '').strip():
        return os.environ['OPENROUTER_AGENT_KEY'].strip()
    if AGENT_KEY_FILE.exists():
        return AGENT_KEY_FILE.read_text().strip() or None
    return None


def opencode_key():
    if not OPENCODE_AUTH.exists():
        return None
    try:
        entry = json.loads(OPENCODE_AUTH.read_text()).get('openrouter')
    except (OSError, ValueError, AttributeError) as exc:
        raise SpendError('key_unavailable', f'OpenCode auth file unreadable ({type(exc).__name__})') from None
    key = entry.get('key') if isinstance(entry, dict) else None
    return key.strip() if isinstance(key, str) and key.strip() else None


def fetch_key_data(key):
    request = urllib.request.Request(KEY_URL)
    # Unredirected: urllib would otherwise resend the key to wherever a redirect points.
    request.add_unredirected_header('Authorization', 'Bearer ' + key)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise SpendError('request_failed', f'HTTP {exc.code}') from None
    except Exception as exc:  # noqa: BLE001 - network, TLS, malformed key header or body: report the type only
        raise SpendError('request_failed', type(exc).__name__) from None
    data = payload.get('data') if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise SpendError('unexpected_response', 'no data object')
    return data


def summarize(agent_data, other_usage, allowance):
    """Summary and exit code from the agent key's /key data plus other keys' daily usage."""
    if agent_data.get('usage_daily') is None:
        raise SpendError('usage_unavailable', 'OpenRouter did not report usage_daily; treat the allowance as unknown')
    used_today = number(agent_data['usage_daily'], 'usage_daily') + sum(other_usage)
    key_limit, key_remaining = agent_data.get('limit'), agent_data.get('limit_remaining')
    remaining = allowance - used_today
    if key_remaining is not None:
        remaining = min(remaining, number(key_remaining, 'limit_remaining'))
    remaining = round(max(remaining, 0), 6)
    hard_cap = key_limit is not None and agent_data.get('limit_reset') == 'daily'
    within_policy = key_limit is not None and number(key_limit, 'limit') <= allowance
    summary = {
        'status': 'ok' if remaining > 0 else 'allowance_exhausted',
        'used_today_usd': round(used_today, 6),
        'keys_counted': 1 + len(other_usage),
        'policy_allowance_usd': allowance,
        'remaining_today_usd': remaining,
        'key_limit_usd': key_limit,
        'key_limit_reset': agent_data.get('limit_reset'),
        'hard_cap_enforced_by_openrouter': hard_cap,
        'key_limit_within_policy': within_policy,
    }
    if not hard_cap:
        summary['warning'] = 'The agent key has no daily limit in OpenRouter; this check is advisory only.'
    elif not within_policy:
        summary['warning'] = 'The key limit is above the allowance; agents running at once can overshoot it, up to the key limit.'
    return summary, 0 if remaining > 0 else 3


def check_spend():
    key = agent_key()
    if not key:
        return {'status': 'no_agent_key', 'meaning': 'No agent allowance is configured; ask the owner before any paid OpenRouter call.'}, 2
    allowance = allowance_usd()
    agent_data = fetch_key_data(key)
    other = opencode_key()
    other_usage = []
    if other and other != key:
        data = fetch_key_data(other)
        if data.get('usage_daily') is None:
            raise SpendError('usage_unavailable', "OpenRouter did not report usage_daily for OpenCode's key")
        other_usage.append(number(data['usage_daily'], 'usage_daily'))
    return summarize(agent_data, other_usage, allowance)


def parse_count(value):
    if value == 'unknown':
        return value
    count = int(value)
    if count < 0:
        raise ValueError
    return count


def build_record(args):
    """Validate --record arguments and return the log entry; raises ValueError with a message."""
    purpose = ' '.join(args.purpose.split())
    if not purpose or len(purpose) > MAX_PURPOSE:
        raise ValueError(f'--purpose must be 1-{MAX_PURPOSE} characters')
    if args.route in METERED_ROUTES:
        if args.cost is None:
            raise ValueError(f'--cost is required for route {args.route} (use "unknown" if OpenRouter gave none)')
        if args.cost == 'unknown':
            cost = 'unknown'
        else:
            try:
                cost = float(args.cost)
            except ValueError:
                raise ValueError('--cost must be a number or "unknown"') from None
            if not (math.isfinite(cost) and cost >= 0):
                raise ValueError('--cost must be zero or more')
    else:
        if args.cost is not None:
            raise ValueError(f'route {args.route} is not metered; omit --cost')
        cost = 'not_metered'
    entry = {
        'recorded_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),  # noqa: UP017 (Python 3.9)
        'harness': args.harness,
        'model': args.model,
        'route': args.route,
        'purpose': purpose,
        'private_data': args.private == 'yes',
        'requests': args.requests,
        'cost_usd': cost,
        'cwd': os.getcwd(),
    }
    if entry['private_data'] and args.route in NON_PRIVATE_ROUTES:
        entry['policy_violation'] = f'private data sent on route {args.route}'
    return entry


def append_record(entry, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, 'a') as log:
        fcntl.flock(log, fcntl.LOCK_EX)
        log.write(json.dumps(entry) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--record', action='store_true', help='append an agent run to the run log instead of checking spend')
    parser.add_argument('--harness', help='harness that ran the model, e.g. codex, claude-code, opencode, ollama, direct-script')
    parser.add_argument('--model', help='model ID as the provider names it')
    parser.add_argument('--route', choices=ROUTES, help='billing route')
    parser.add_argument('--purpose', help=f'what the run was for, at most {MAX_PURPOSE} characters, no private details')
    parser.add_argument('--private', choices=['yes', 'no'], help='whether private data was sent')
    parser.add_argument('--requests', type=parse_count, help='request count including retries, or "unknown" (default)')
    parser.add_argument('--cost', help='actual cost in USD from OpenRouter, or "unknown"; required for metered routes')
    args = parser.parse_args(argv)

    if not args.record:
        stray = [f'--{name}' for name in RECORD_FIELDS if getattr(args, name) is not None]
        if stray:
            parser.error(' '.join(stray) + ' only apply with --record')
        try:
            summary, code = check_spend()
        except SpendError as exc:
            summary, code = {'status': exc.status, 'detail': exc.detail}, 2
        except Exception as exc:  # noqa: BLE001 - never let a crash look like permission to spend
            summary, code = {'status': 'error', 'detail': type(exc).__name__}, 2
        print(json.dumps(summary))
        return code

    missing = [f'--{name}' for name in RECORD_FIELDS[:5] if getattr(args, name) is None]
    if missing:
        parser.error('--record needs ' + ', '.join(missing))
    if args.requests is None:
        args.requests = 'unknown'
    try:
        entry = build_record(args)
    except ValueError as exc:
        parser.error(str(exc))
    path = Path(os.environ.get('AGENT_RUN_LOG') or DEFAULT_RUN_LOG)
    try:
        append_record(entry, path)
    except OSError as exc:
        print(json.dumps({'status': 'error', 'detail': f'run log not written ({type(exc).__name__})', 'log': str(path)}))
        return 2
    result = {'status': 'recorded', 'log': str(path)}
    if 'policy_violation' in entry:
        result['warning'] = entry['policy_violation'] + '; tell the owner'
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
