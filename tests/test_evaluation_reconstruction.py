"""Bounded score-packet admission regressions; no upstream program execution."""
import copy
import csv
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
import public_study as public
import verify_results as verifier


class EvaluationReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = ROOT/'data/public-study'
        cls.candidates, cls.evidence, cls.protocol, cls.labels, cls.design = [
            public.load_json(data/name) for name in
            ('candidates.json', 'source-evidence-cases.json', 'protocol.json', 'labels.json', 'study-design.json')]
        cls.frontend = public.load_json(ROOT/'results/source-frontend/summary.json')
        frozen = ROOT/'results/public-study/frozen'
        cls.predictions = public.load_json(frozen/'predictions-frozen.json')
        cls.outcomes = public.load_json_value(frozen/'outcomes.json')
        cls.records = public.load_json_value(frozen/'source-records.json')

    def evaluate(self, predictions):
        return public.evaluate_predictions(
            self.candidates, self.labels, self.evidence, self.protocol, self.design,
            predictions, self.outcomes, 67, self.frontend, self.records, ROOT)

    def rerank(self, document):
        # Re-sort from supplied scores so a mere ordering check cannot detect it.
        for method, score in (('syntax', 'syntax_score'), ('unvalidated', 'unvalidated_score'),
                              ('validated', 'validated_score')):
            document['rankings'][method] = [row['id'] for row in sorted(
                document['records'], key=lambda row: (-row[score], -row['syntax_score'], row['id']))]
        return document

    def forged_base_scores(self):
        document = copy.deepcopy(self.predictions)
        row = next(row for row in document['records'] if row['id'] == 'U001')
        row['syntax_score'] = 1000.0
        row['unvalidated_score'] = round(1000.0 + float(self.protocol['semantic_hint_bonus'])*row['semantic_hint'], 9)
        row['validated_score'] = round(1000.0 + float(self.protocol['source_evidence_bonus'])*row['source_evidence_accepted'], 9)
        return self.rerank(document)

    def assert_reconstruction_rejects(self, document):
        for name in ('candidate_hash', 'source_evidence_hash', 'protocol_hash'):
            self.assertEqual(document[name], self.predictions[name])
        with self.assertRaisesRegex(public.Invalid, 'prediction-reconstruction'):
            self.evaluate(document)

    def test_coherent_base_scores_and_rankings_are_rejected(self):
        document = self.forged_base_scores()
        self.assertEqual(document['rankings']['syntax'][0], 'U001')
        self.assert_reconstruction_rejects(document)

    def test_coherent_bonus_score_and_ranking_are_rejected(self):
        for field in ('unvalidated_score', 'validated_score'):
            document = copy.deepcopy(self.predictions)
            document['records'][0][field] += 1000.0
            with self.subTest(field=field):
                self.assert_reconstruction_rejects(self.rerank(document))

    def test_coherent_hint_features_bonus_and_ranking_are_rejected(self):
        document = copy.deepcopy(self.predictions)
        row = document['records'][0]
        flag = 1 - row['semantic_hint']
        row['semantic_features'] = {key: flag for key in row['semantic_features']}
        row['semantic_hint'] = flag
        row['unvalidated_score'] = round(row['syntax_score'] + float(self.protocol['semantic_hint_bonus'])*flag, 9)
        self.assert_reconstruction_rejects(self.rerank(document))

    def test_substituted_group_is_rejected(self):
        document = copy.deepcopy(self.predictions)
        document['records'][0]['group'] = document['records'][1]['group']
        self.assert_reconstruction_rejects(document)

    def test_valid_results_and_negative_decisions_remain_exact(self):
        reconstructed, outcomes, records = public.freeze_predictions(self.candidates, self.evidence, self.protocol)
        self.assertTrue(public.typed_equal(reconstructed, self.predictions))
        self.assertTrue(public.typed_equal(outcomes, self.outcomes))
        self.assertTrue(public.typed_equal(records, self.records))
        summary, scored, ablations, readiness = self.evaluate(self.predictions)
        retained = ROOT/'results/public-study/evaluation'
        self.assertTrue(public.typed_equal(summary, verifier._strip_runtime(public.load_json(retained/'summary.json'))))
        self.assertTrue(public.typed_equal(ablations, public.load_json_value(retained/'ablations.json')))
        self.assertTrue(public.typed_equal(readiness, public.load_json(retained/'readiness.json')))
        with (retained/'scores.csv').open(newline='', encoding='utf-8') as stream:
            actual = list(csv.DictReader(stream))
        expected = []
        for original in scored:
            row = dict(original)
            features = row.pop('semantic_features')
            expected.append({key: str(value) for key, value in {**row, **features}.items() if key in actual[0]})
        self.assertEqual(actual, expected)
        self.assertEqual(summary['validated_minus_syntax_at_20'], 0.0)
        self.assertEqual(summary['formal_h1_decision'], 'not-testable-with-label-selected-nontemporal-cohort')
        self.assertEqual(summary['formal_h2_decision'], 'not-testable-as-full-cohort-file-availability')
        self.assertEqual(len(summary['failed_readiness_gates']), 6)

    def test_full_verifier_keeps_its_existing_independent_guard(self):
        document = self.forged_base_scores()
        original = verifier.load_json
        def substituted(path):
            return copy.deepcopy(document) if path.name == 'predictions-frozen.json' else original(path)
        with mock.patch.object(verifier, 'load_json', side_effect=substituted):
            with self.assertRaisesRegex(verifier.VerificationError, 'public-predictions-not-recomputed'):
                verifier.verify_public()


if __name__ == '__main__':
    unittest.main()
