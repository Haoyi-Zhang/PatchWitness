"""Owned static guard-pattern regressions; no native or upstream execution."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from source_frontend import _extract_added_if_guards, derive_case


class RejectionGuardPrefixTests(unittest.TestCase):
    def derive(self,diff):
        return derive_case({'id':'owned-lexical','source_asset':{'context_requirements':[]},'diff_context':diff})

    def test_comments_and_literals_do_not_supply_guards(self):
        snippets=[
            '// if (x < 0) { return errors::owned(); }',
            '/* if (x < 0) { return errors::owned(); } */',
            'const char* note = "if (x < 0) { return errors::owned(); }";',
            'const char* note = R"tag(if (x < 0) { return errors::owned(); })tag";',
            '// comment continued \\\nif (x < 0) { return errors::owned(); }',
        ]
        for snippet in snippets:
            with self.subTest(snippet=snippet):
                diff='@@ -0,0 +1,2 @@\n'+'\n'.join('+'+line for line in snippet.split('\n'))
                case,diag=self.derive(diff)
                self.assertIsNone(case)
                self.assertEqual(diag['status'],'abstain')

    def test_comment_opened_in_context_masks_added_guard(self):
        case,diag=self.derive('@@ -1,2 +1,3 @@\n /* retained context\n+if (x < 0) { return errors::owned(); }\n */')
        self.assertIsNone(case)
        self.assertEqual(diag['status'],'abstain')

    def test_comment_before_an_actual_return_is_whitespace(self):
        case,diag=self.derive('@@ -0,0 +1,1 @@\n+if (x < 0) { /* ignore */ return errors::owned("http://owned"); }')
        self.assertIsNotNone(case)
        self.assertEqual(case['source_tokens'],['x < 0'])

    def test_immediate_error_return_is_selected(self):
        self.assertEqual(_extract_added_if_guards(
            'if (x < 0) { return errors::InvalidArgument("owned"); }'), ['x < 0'])

    def test_nested_return_does_not_select_outer_guard(self):
        source = ('if (x < 0) { if (y == 1) { '
                  'return errors::InvalidArgument("owned"); } }')
        self.assertEqual(_extract_added_if_guards(source), ['y == 1'])

    def test_string_literal_is_not_a_return_statement(self):
        source = 'if (x < 0) { const char* note = "return errors::owned"; }'
        self.assertEqual(_extract_added_if_guards(source), [])

    def test_deferred_return_after_other_statement_is_outside_profile(self):
        source = 'if (x < 0) { note = 1; return errors::InvalidArgument("owned"); }'
        self.assertEqual(_extract_added_if_guards(source), [])

    def test_non_error_return_does_not_select_guard(self):
        self.assertEqual(_extract_added_if_guards('if (x < 0) { return 0; }'), [])

    def test_unsupported_body_remains_a_typed_abstention(self):
        record = {'id': 'owned-prefix', 'source_asset': {'context_requirements': []},
                  'diff_context': '@@ -1,0 +1,1 @@\n+if (x < 0) { note = 1; return errors::owned(); }'}
        case, diagnostic = derive_case(record)
        self.assertIsNone(case)
        self.assertEqual(diagnostic['reason'], 'no-supported-added-source-pattern')


if __name__ == '__main__':
    unittest.main()
