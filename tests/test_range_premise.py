"""Owned string-pattern fixtures only; no source application or native execution."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import source_frontend as frontend


def declaration_record(old_rhs, new_rhs=None, *, newline='\n', trailing=''):
    new_rhs = old_rhs if new_rhs is None else new_rhs
    return {'id': 'owned-range', 'source_asset': {'context_requirements': []},
            'diff_context': f'-const int min_rank = {old_rhs};{trailing}{newline}'
                            f'+const int64 min_rank = {new_rhs};{trailing}{newline}'}


class RangePremise(unittest.TestCase):
    def test_conditional_premise_is_recognized(self):
        for rhs in ('concat_dim < 0 ? -concat_dim : concat_dim',
                    'concat_dim < 0 ? -concat_dim : concat_dim + 1'):
            with self.subTest(rhs=rhs):
                case, diagnostic = frontend.derive_case(declaration_record(rhs))
                self.assertEqual(case['kind'], 'source-difference')
                self.assertEqual(case['assignment'], {'concat_dim': frontend.INT32_MIN})
                self.assertEqual(diagnostic['status'], 'supported')

    def test_plain_identity_is_not_a_magnitude_premise(self):
        case, diagnostic = frontend.derive_case(declaration_record('concat_dim'))
        self.assertIsNone(case)
        self.assertEqual(diagnostic['status'], 'abstain')
        self.assertEqual(diagnostic['reason'], 'no-supported-added-source-pattern')

    def test_lf_and_crlf_have_same_conditional_match(self):
        for rhs in ('concat_dim < 0 ? -concat_dim : concat_dim',
                    'concat_dim < 0 ? -concat_dim : concat_dim + 1'):
            for trailing in ('', ' \t'):
                with self.subTest(rhs=rhs, trailing=trailing):
                    lf = declaration_record(rhs, newline='\n', trailing=trailing)
                    crlf = declaration_record(rhs, newline='\r\n', trailing=trailing)
                    self.assertTrue(frontend._is_widening_record(lf))
                    self.assertTrue(frontend._is_widening_record(crlf))
                    self.assertEqual(frontend.derive_case(crlf), frontend.derive_case(lf))

    def test_lf_and_crlf_keep_unsupported_rhs_rejected(self):
        for rhs in ('concat_dim',
                    'concat_dim < 0 ? -concat_dim : concat_dim + 2',
                    'concat_dim < 0 ? concat_dim : concat_dim + 1'):
            for newline in ('\n', '\r\n'):
                for trailing in ('', ' \t'):
                    with self.subTest(rhs=rhs, newline=newline, trailing=trailing):
                        record = declaration_record(rhs, newline=newline, trailing=trailing)
                        self.assertFalse(frontend._is_widening_record(record))
                        case, diagnostic = frontend.derive_case(record)
                        self.assertIsNone(case)
                        self.assertEqual(diagnostic['status'], 'abstain')
                        self.assertEqual(diagnostic['reason'], 'no-supported-added-source-pattern')

    def test_both_declarations_need_the_same_restricted_rhs(self):
        rhs = 'concat_dim < 0 ? -concat_dim : concat_dim + 1'
        for old, new in ((rhs, 'concat_dim'), ('concat_dim', rhs),
                         (rhs, 'concat_dim < 0 ? -concat_dim : concat_dim')):
            for newline in ('\n', '\r\n'):
                with self.subTest(old=old, new=new, newline=newline):
                    self.assertFalse(frontend._is_widening_record(
                        declaration_record(old, new, newline=newline)))


if __name__ == '__main__':
    unittest.main()
