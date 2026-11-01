"""Round-5 guards for REPAIR-DECISIONS-R5 rev2; synthetic, offline only."""
from unittest import mock

import helpers as H
import helper_fixtures as HF


def exclusive_create():
    """R4 F1; REPAIR-DECISIONS-R5 rev2 step 1: absent means exclusive."""
    with HF.workspace(session_name=None) as root:
        path = root / 'project_session.md'
        H._append_bytes(path, b'a')
        assert path.read_bytes() == b'a'
        path.write_bytes(b'foreign')
        with mock.patch.object(H.os.path, 'lexists', return_value=False):
            try:
                H._append_bytes(path, b'x')
            except FileExistsError:
                pass
            else:
                raise AssertionError('exclusive creation must refuse an existing file')
        assert path.read_bytes() == b'foreign'


CHECKS = (exclusive_create,)


def run():
    problems = []
    for check in CHECKS:
        try:
            check()
        except Exception as exc:
            problems.append(f'{check.__name__}: {type(exc).__name__}: {exc}')
    return problems
