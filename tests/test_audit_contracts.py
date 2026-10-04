"""Benign regression and exact finite-frame contract tests."""
from __future__ import annotations
import copy
from fractions import Fraction
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from audit_bounds import paired_bounds, correction_bounds, precision_bounds, insertion_precision_bounds
from public_study import (load_json, make_source_record, check_source_record,
                          validate_study_design, Invalid, typed_equal)
from verify_results import verify_finite, VerificationError


class AuditContracts(unittest.TestCase):
    def test_c11_oracle_lazy_and_or_and_direct_division(self):
        from run_frontend_validation import _run_c_oracle
        from source_frontend import parse_expression, ast_to_rpn
        cases = [
            ("x > 0 && 1 / x > 0", {"x": 0}, "B:0"),
            ("x == 0 || 1 / x > 0", {"x": 0}, "B:1"),
            ("1 / x", {"x": 0}, "ERR"),
            ("7 / x", {"x": 2}, "I:3"),
            ("7 / x", {"x": -2}, "I:-3"),
            ("-9223372036854775808 / x", {"x": -1}, "ERR"),
        ]
        inputs = [" ".join(ast_to_rpn(parse_expression(e), a)) for e, a, _ in cases]
        actual, _ = _run_c_oracle(inputs)
        self.assertEqual(actual, [answer for _, _, answer in cases])

    def test_exact_enumeration_detects_a_wrong_bound_formula(self):
        import run_contract_audit
        with mock.patch.object(run_contract_audit, "paired_bounds", return_value=(Fraction(0), Fraction(0))):
            with self.assertRaises(ValueError):
                run_contract_audit.exact_checks()

    def test_w09_existing_nonempty_context_is_enforced(self):
        import copy
        from public_study import load_json, make_source_record, check_source_record
        from source_frontend import derive_evidence_document
        packet = load_json(ROOT / "data/public-study/candidates.json")
        case = next(c for c in derive_evidence_document(packet)["cases"] if c["id"] == "W09")
        row = next(r for r in packet["records"] if r["id"] == case["record"])
        self.assertEqual(case["assignment"], {"num_elements": 2})
        self.assertEqual(case["context_tokens"], ["key_tensor->NumElements() > 0"])
        evidence = make_source_record(case, row)
        self.assertTrue(check_source_record(case, row, evidence)[0])
        broken = copy.deepcopy(evidence)
        broken["assignment"]["num_elements"] = 0
        self.assertFalse(check_source_record(case, row, broken)[0])

    def test_unknown_intersection_labels_cancel(self):
        lo,hi=paired_bounds(['a','b','c'],['a','c','b'],2,{'b':1,'c':0})
        self.assertEqual((lo,hi),(Fraction(1,2),Fraction(1,2)))
        self.assertEqual(precision_bounds(['a','b','c'],2,{'b':1,'c':0}),(Fraction(1,2),Fraction(1)))
    def test_unknown_difference_bounds_are_attainable(self):
        self.assertEqual(paired_bounds(['a','b','c','d'],['c','d','a','b'],2,{}),(Fraction(-1),Fraction(1)))
    def test_fixed_total_tightens_unknown_label_bounds(self):
        self.assertEqual(paired_bounds(['a','b','c','d'],['c','d','a','b'],2,{},1),(Fraction(-1,2),Fraction(1,2)))
    def test_one_label_correction_can_erase_single_swap_gain(self):
        labels={'a':1,'b':1,'c':0}
        self.assertEqual(correction_bounds(['a','b','c'],['a','c','b'],2,labels,1),(Fraction(0),Fraction(1,2)))
    def test_equal_top_sets_force_zero_under_all_corrections(self):
        self.assertEqual(correction_bounds(['a','b','c'],['b','a','c'],2,{'a':0,'b':1,'c':1},3),(Fraction(0),Fraction(0)))
    def test_bounds_reject_bool_labels_and_float_totals(self):
        for y in (True,1.0):
            with self.assertRaises(ValueError):paired_bounds(['a'],['a'],1,{'a':y})
        with self.assertRaises(ValueError):paired_bounds(['a'],['a'],1,{},1.0)
    def test_bounds_reject_mismatched_frames_and_impossible_totals(self):
        with self.assertRaises(ValueError):paired_bounds(['a'],['b'],1,{})
        with self.assertRaises(ValueError):paired_bounds(['a'],['a'],1,{'a':1},0)
    def test_bounded_missing_frame_narrows_only_under_stated_budget(self):
        order=['a','b','c'];labels={'a':1,'b':0,'c':1}
        self.assertEqual(insertion_precision_bounds(order,2,labels,0),(Fraction(1,2),Fraction(1,2)))
        self.assertEqual(insertion_precision_bounds(order,2,labels,1),(Fraction(1,2),Fraction(1)))
        self.assertEqual(insertion_precision_bounds(order,2,labels,2),(Fraction(0),Fraction(1)))
    def test_w01_checker_does_not_call_record_producer(self):
        cases=load_json(ROOT/'data/public-study/source-evidence-cases.json')['cases']
        c=next(x for x in cases if x['id']=='W01')
        r=next(x for x in load_json(ROOT/'data/public-study/candidates.json')['records'] if x['id']==c['record'])
        e=make_source_record(c,r)
        with mock.patch('public_study.make_source_record',side_effect=RuntimeError('producer must not be trusted')):
            self.assertTrue(check_source_record(c,r,e)[0])
        self.assertNotIn('before',e);self.assertNotIn('after',e)
        self.assertEqual(e['relation'],'destination-range-separation')
    def test_w01_rejects_changed_width_assumption(self):
        c=next(x for x in load_json(ROOT/'data/public-study/source-evidence-cases.json')['cases'] if x['id']=='W01')
        r=next(x for x in load_json(ROOT/'data/public-study/candidates.json')['records'] if x['id']==c['record'])
        e=make_source_record(c,r);e['assumed_signed_widths']=[64,64]
        self.assertFalse(check_source_record(c,r,e)[0])
    def test_gate_rejects_existing_file_as_retrospective_label_seal(self):
        design=load_json(ROOT/'data/public-study/study-design.json')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'seal.json';p.write_text('{"accepted":true}')
            import hashlib
            design['label_sealing']={'seal_record':{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},'method_freeze_timestamp':'2000-01-01T00:00:00Z'}
            with self.assertRaises(Invalid):validate_study_design(design)
    def test_gate_rejects_coordinated_historical_boolean_relabeling(self):
        design=load_json(ROOT/'data/public-study/study-design.json')
        design['candidate_frame']['class_lists_used']=False
        design['candidate_frame']['selection_method']='label-independent'
        with self.assertRaises(Invalid):validate_study_design(design)
    def test_finite_verifier_rejects_duplicate_certificate(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'finite';shutil.copytree(ROOT/'results/finite-check',d)
            p=d/'certificates.json';ev=json.loads(p.read_text());ev[-1]=copy.deepcopy(ev[0]);p.write_text(json.dumps(ev))
            with self.assertRaisesRegex(VerificationError,'bijection'):verify_finite(d)
    def test_finite_verifier_rejects_balanced_row_counter_tamper(self):
        import csv
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'finite';shutil.copytree(ROOT/'results/finite-check',d)
            p=d/'cases.csv'
            with p.open(newline='') as h:r=csv.DictReader(h);fields=r.fieldnames;rows=list(r)
            rows[0]['repair']=str(int(rows[0]['repair'])+1)
            rows[1]['repair']=str(int(rows[1]['repair'])-1)
            with p.open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=fields);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(VerificationError,'row-count'):verify_finite(d)

if __name__=='__main__':unittest.main()
