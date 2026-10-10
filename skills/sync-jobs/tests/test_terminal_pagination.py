import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sync_integrity import saved_records


class TerminalPagination(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'saved.json'
        self.data = {
            'card': 'SAVED', 'count': 3, 'total': 5, 'error': None,
            'pagination_complete': True, 'termination': 'last_page',
            'jobs': [{'id': str(i)} for i in (100, 200, 300)],
            'pagination_evidence': [
                {'page': 1, 'visible_pages': [1, 2, 3], 'reported_total': 5,
                 'job_ids': ['100'], 'next_control': 'enabled'},
                {'page': 2, 'visible_pages': [1, 2, 3], 'reported_total': 5,
                 'job_ids': ['200'], 'next_control': 'enabled'},
                {'page': 3, 'visible_pages': [1, 2, 3], 'reported_total': 5,
                 'job_ids': ['300'], 'next_control': 'absent'},
            ],
        }

    def read(self, data):
        self.path.write_text(json.dumps(data))
        return saved_records([self.path])

    def test_complete_populated_terminal_page_accepts_advisory_surplus(self):
        self.assertEqual(self.read(self.data), self.data['jobs'])
        self.data['pagination_evidence'][-1]['next_control'] = 'disabled'
        self.assertEqual(self.read(self.data), self.data['jobs'])

    def test_complete_single_page_and_exact_count(self):
        data = copy.deepcopy(self.data)
        data.update(count=1, total=1, jobs=[{'id': '100'}])
        data['pagination_evidence'] = [
            {'page': 1, 'visible_pages': [1], 'reported_total': 1,
             'job_ids': ['100'], 'next_control': 'absent'}]
        self.assertEqual(self.read(data), data['jobs'])

    def test_terminal_label_without_evidence_rejected_even_at_exact_count(self):
        self.data.pop('pagination_evidence')
        for total in (3, 5):
            with self.subTest(total=total):
                self.data['total'] = total
                with self.assertRaises(ValueError):
                    self.read(self.data)

    def test_missing_or_skipped_page_rejected(self):
        for index in (0, 1):
            data = copy.deepcopy(self.data)
            data['pagination_evidence'].pop(index)
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.read(data)

    def test_duplicate_missing_and_extra_page_ids_rejected(self):
        for ids in (['100'], ['999'], ['300', '999'], []):
            data = copy.deepcopy(self.data)
            data['pagination_evidence'][-1]['job_ids'] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                self.read(data)

    def test_duplicate_index_ids_rejected(self):
        self.data['jobs'][-1]['id'] = '100'
        with self.assertRaises(ValueError):
            self.read(self.data)

    def test_page_navigation_or_selection_not_terminal_rejected(self):
        changes = [(0, 'next_control', 'absent'), (2, 'next_control', 'enabled'),
                   (2, 'visible_pages', [2, 3, 4]), (1, 'visible_pages', [1, 3]),
                   (1, 'page', True), (1, 'reported_total', 6),
                   (1, 'job_ids', ['not-an-id'])]
        for index, field, value in changes:
            data = copy.deepcopy(self.data)
            data['pagination_evidence'][index][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.read(data)

    def test_non_saved_incomplete_or_failed_index_rejected(self):
        for field, value in [('card', 'IN_PROGRESS'), ('pagination_complete', False),
                             ('error', 'browser capture failed')]:
            data = copy.deepcopy(self.data)
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.read(data)


if __name__ == '__main__':
    unittest.main()
