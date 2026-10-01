"""Tests for the descriptive public source-evidence audit."""
from __future__ import annotations
import copy, csv, hashlib, json, os
from pathlib import Path
import shutil, subprocess, sys, tempfile, unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT))
from public_study import (  # noqa:E402
 INT64_MAX,INT64_MIN,Invalid,check_source_record,derive_readiness,evaluate_predictions,
 freeze_predictions,load_json,load_json_value,make_source_record,producer_eval,replay,
 typed_equal,validate_candidates,validate_expr,validate_labels,validate_outcomes,
 validate_predictions,validate_protocol,validate_source_evidence,validate_source_records,
 validate_study_design,
)
from source_frontend import derive_case,derive_evidence_document,parse_expression  # noqa:E402
from source_frontend_reference import evaluate as reference_evaluate  # noqa:E402
from verify_results import VerificationError,verify_public_packet  # noqa:E402

class PublicStudyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=ROOT/'data/public-study'
  cls.candidates=load_json(cls.data/'candidates.json'); cls.labels=load_json(cls.data/'labels.json'); cls.evidence=load_json(cls.data/'source-evidence-cases.json'); cls.protocol=load_json(cls.data/'protocol.json'); cls.design=load_json(cls.data/'study-design.json'); cls.frontend=load_json(ROOT/'results/source-frontend/summary.json')
  cls.records=validate_candidates(cls.candidates); cls.by={r['id']:r for r in cls.records}; cls.cases=validate_source_evidence(cls.evidence,set(cls.by)); cls.case_by_id={c['id']:c for c in cls.cases}
 def frozen(self): return freeze_predictions(self.candidates,self.evidence,self.protocol)
 def evaluated(self,reference_count=61):
  p,o,s=self.frozen(); return evaluate_predictions(self.candidates,self.labels,self.evidence,self.protocol,self.design,p,o,reference_count,self.frontend,s,ROOT)

 def test_all_input_schemas_validate(self):
  validate_protocol(self.protocol,32); validate_study_design(self.design); validate_labels(self.labels,{k:v['group'] for k,v in self.by.items()}); self.assertEqual(len(self.cases),10)
 def test_candidates_are_real_asset_bound_and_label_free(self):
  self.assertEqual(len(self.records),32); self.assertNotIn('"label"',json.dumps(self.candidates,sort_keys=True))
  for row in self.records:
   self.assertTrue(row['file_path'].startswith('tensorflow/')); self.assertIn('@@',row['diff_context']); self.assertTrue(row['source_asset']['commit_url'].endswith(row['commit'])); self.assertFalse(row['source_asset']['annotation_used_for_scoring'])
 def test_neutral_ids_use_full_paths(self):
  digests=[]
  for row in self.records:
   digest=hashlib.sha256((row['commit']+'\0'+row['file_path']).encode()).hexdigest(); self.assertEqual(row['identity_digest'],digest); digests.append(digest)
  self.assertEqual(digests,sorted(digests)); self.assertEqual([r['id'] for r in self.records],[f'U{i:03d}' for i in range(1,33)])
 def test_3218043_message_is_not_file_annotation(self):
  rows=[r for r in self.records if r['commit'].startswith('3218043')]
  self.assertEqual(len(rows),3)
  for row in rows:
   self.assertTrue(row['commit_message'].startswith('Internal change\n\nPiperOrigin-RevId: 411896058'))
   self.assertNotEqual(row['commit_message'],row['source_asset']['file_annotation'])
 def test_source_manifest_binds_original_fields_without_labels(self):
  with (self.data/'source-manifest.csv').open(newline='',encoding='utf-8') as h: reader=csv.DictReader(h); rows=list(reader); fields=reader.fieldnames
  self.assertEqual(len(rows),32); self.assertNotIn('label',fields); by={r['id']:r for r in rows}
  for rid,c in self.by.items():
   self.assertEqual(by[rid]['file_path'],c['file_path']); self.assertEqual(by[rid]['commit_message_sha256'],hashlib.sha256(c['commit_message'].encode()).hexdigest()); self.assertEqual(by[rid]['diff_context_sha256'],hashlib.sha256(c['diff_context'].encode()).hexdigest())
 def test_label_file_is_separate_and_complete(self):
  labels=validate_labels(self.labels,{k:v['group'] for k,v in self.by.items()}); self.assertEqual(len(labels),32); self.assertEqual(sum(labels.values()),16)
 def test_candidate_schema_rejects_manual_label_or_annotation_as_score_input(self):
  bad=copy.deepcopy(self.candidates); bad['records'][0]['label']=1
  with self.assertRaises(Invalid): validate_candidates(bad)
  bad=copy.deepcopy(self.candidates); bad['records'][0]['source_asset']['annotation_used_for_scoring']=True
  with self.assertRaisesRegex(Invalid,'annotation-score-leakage'): validate_candidates(bad)
 def test_json_gate_rejects_duplicate_depth_size_nonfinite(self):
  samples=[b'{"a":1,"a":2}',b'{"a":NaN}',b'['*70+b'0'+b']'*70,b' '*(1_048_576+1),b'\xff']
  with tempfile.TemporaryDirectory(dir=ROOT/'results') as d:
   p=Path(d)/'x.json'
   for raw in samples:
    p.write_bytes(raw)
    with self.assertRaises(Invalid): load_json(p)
   p.write_text('[1,{"x":2}]')
   self.assertEqual(load_json_value(p),[1,{'x':2}])
 def test_expression_types_and_exact_division(self):
  self.assertEqual(validate_expr(['lt',['var','x'],['const',0]],{'x'}),'bool')
  for expr in (["and",["const",1],["const",0]],["not",["const",1]],["eq",["lt",["var","x"],["const",0]],["const",1]]):
   with self.assertRaises(Invalid): validate_expr(expr,{'x'})
  expr=['div',['const',INT64_MAX],['const',3]]; value=producer_eval(expr,{},[]); self.assertEqual(value,{'tag':'int','payload':3074457345618258602}); self.assertEqual(replay(expr,{})[0],value)
  with self.assertRaises(Invalid): producer_eval(['div',['const',INT64_MIN],['const',-1]],{},[])
 def test_source_evidence_is_not_finite_certificate_contract(self):
  self.assertEqual(self.evidence['construction']['evidence_contract'],'guard-trigger-or-source-difference-not-old-fault-new-defined')
  for case in self.cases:
   self.assertNotIn('hazard',case); self.assertNotIn('before',case); self.assertNotIn('after',case)
 def test_w10_restores_nonzero_context_and_uses_negative_dim(self):
  case=self.case_by_id['W10']; self.assertEqual(case['context_tokens'],['dims(i) != 0']); self.assertEqual(case['assignment']['dim'],-1); self.assertNotEqual(case['assignment']['dim'],0)
  context=producer_eval(case['context_preconditions'][0],case['assignment'],[]); self.assertEqual(context,{'tag':'bool','payload':True})
 def test_primary_and_reference_parser_agree_on_saved_guards(self):
  for case in self.cases:
   if case['kind']!='guard-trigger': continue
   raw=(' && ' if case['frontend_rule']=='require' else ' || ').join(f'({x})' for x in case['source_tokens'])
   self.assertEqual(parse_expression(raw),case['guard']); primary=producer_eval(case['guard'],case['assignment'],[]); self.assertEqual(primary,{'tag':'bool','payload':reference_evaluate(raw,case['assignment'])})
 def test_public_trace_is_position_tag_payload_and_short_circuit_omits_branch(self):
  case=self.case_by_id['W10']; trace=[]; value=producer_eval(case['guard'],case['assignment'],trace); self.assertEqual(value,{'tag':'bool','payload':False}); self.assertTrue(all(type(x) is list and len(x)==3 for x in trace)); self.assertFalse(any(pos.startswith('1') for pos,_,_ in trace))
  self.assertEqual((value,trace),replay(case['guard'],case['assignment']))
 def test_exact_nested_typed_equality(self):
  self.assertFalse(typed_equal(False,0)); self.assertFalse(typed_equal(1,1.0)); self.assertFalse(typed_equal({'x':[1,False]},{'x':[1,0]})); self.assertTrue(typed_equal({'x':[1,False]},{'x':[1,False]}))
 def test_w02_false_to_zero_is_rejected(self):
  case=self.case_by_id['W02']; record=self.by[case['record']]; evidence=make_source_record(case,record); self.assertTrue(check_source_record(case,record,evidence)[0]); bad=copy.deepcopy(evidence); self.assertIs(bad['guard_result']['payload'],False); bad['guard_result']['payload']=0; self.assertFalse(check_source_record(case,record,bad)[0])
 def test_w01_integer_to_equal_float_is_rejected(self):
  case=self.case_by_id['W01']; record=self.by[case['record']]; evidence=make_source_record(case,record); bad=copy.deepcopy(evidence); bad['after']['payload']=float(bad['after']['payload']); self.assertFalse(check_source_record(case,record,bad)[0])
 def test_w10_unvisited_assignment_int_to_true_is_rejected(self):
  case=self.case_by_id['W10']; record=self.by[case['record']]; evidence=make_source_record(case,record); self.assertEqual(evidence['assignment']['prod'],1); bad=copy.deepcopy(evidence); bad['assignment']['prod']=True; self.assertFalse(check_source_record(case,record,bad)[0])
 def test_source_records_are_unique_and_bound(self):
  p,o,s=self.frozen(); validate_predictions(p,self.candidates,self.evidence,self.protocol); validate_outcomes(o,p['records']); validate_source_records(s,self.cases,self.records,o); self.assertEqual(len(s),10); self.assertEqual(len({x['case'] for x in s}),10); self.assertEqual(len({x['record'] for x in s}),10)
 def test_frontend_rederives_exact_packet_and_typed_abstentions(self):
  derived=derive_evidence_document(self.candidates); self.assertEqual(derived,self.evidence); self.assertEqual(sum(x['status']=='supported' for x in derived['diagnostics']),10); self.assertEqual(sum(x['status']=='abstain' for x in derived['diagnostics']),22)
 def test_unclosed_guard_becomes_typed_extraction_abstention(self):
  record=copy.deepcopy(self.records[0]); record['diff_context']='@@ -1 +1 @@\n+if (x > 0 {'
  case,diag=derive_case(record); self.assertIsNone(case); self.assertEqual((diag['status'],diag['stage'],diag['reason']),('abstain','extract','unbalanced-parentheses'))
 def test_unclosed_guard_does_not_swallow_system_error(self):
  record=copy.deepcopy(self.records[0]); record['diff_context']='@@ -1 +1 @@\n+if (x > 0) {'
  with mock.patch('source_frontend._extract_added_if_guards',side_effect=RuntimeError('system-failure')):
   with self.assertRaisesRegex(RuntimeError,'system-failure'): derive_case(record)
 def test_prediction_freeze_is_label_free_and_keeps_denominator(self):
  p,o,s=self.frozen(); self.assertFalse(p['label_fields_present']); self.assertEqual(len(p['records']),len(o),32); self.assertEqual(len(s),10); self.assertEqual(sum(x['typed_outcome']=='unsupported-syntax' for x in o),22); self.assertFalse(any(k == 'label' for obj in ([p] + p['records']) for k in obj))
 def test_descriptive_metrics_and_four_denominators(self):
  summary,rows,ablations,readiness=self.evaluated(); self.assertEqual(len(rows),32); self.assertEqual(len(ablations),5); self.assertEqual(summary['metrics']['syntax']['precision_at_20'],0.75); self.assertEqual(summary['metrics']['unvalidated']['precision_at_20'],0.8); self.assertEqual(summary['metrics']['validated']['precision_at_20'],0.75); self.assertEqual(summary['validated_minus_syntax_at_20'],0.0)
  self.assertEqual(summary['coverage']['positive_file_conditional']['fraction'],'10/16'); self.assertEqual(summary['coverage']['positive_commit_conditional']['fraction'],'10/10'); self.assertEqual(summary['coverage']['all_candidate_file_availability']['fraction'],'10/32'); self.assertEqual(summary['coverage']['all_candidate_commit_availability']['fraction'],'10/26'); self.assertEqual(summary['formal_h2_decision'],'not-testable-as-full-cohort-file-availability'); self.assertEqual(len(readiness['failed_readiness_gates']),6)
 def test_gate_distinguishes_machine_facts_from_design_assertions(self):
  _,_,_,readiness=self.evaluated(); basis={g['id']:g['basis'] for g in readiness['gates']}; self.assertEqual(basis['restricted_source_evidence_cross_checked'],'machine-recomputed'); self.assertEqual(basis['temporal_holdout'],'trusted-design-assertion-with-file-evidence-required')
 def test_gate_cannot_be_forged_by_bool_or_accepted_text(self):
  bad=copy.deepcopy(self.design); bad['candidate_frame']['temporal_holdout']=True
  with self.assertRaises(Invalid): validate_study_design(bad)
  bad=copy.deepcopy(self.design); bad['temporal_split']['holdout_manifest']='accepted'
  with self.assertRaises(Invalid): validate_study_design(bad)
  p,o,s=self.frozen(); frontend=copy.deepcopy(self.frontend); frontend['status']='accepted'
  summary,_,_,_=evaluate_predictions(self.candidates,self.labels,self.evidence,self.protocol,self.design,p,o,61,frontend,s,ROOT); self.assertIn('restricted_source_evidence_cross_checked',summary['failed_readiness_gates'])
 def test_reference_gate_is_fail_closed(self):
  summary,_,_,_=self.evaluated(reference_count=54); self.assertIn('reference_count_at_least_55',summary['failed_readiness_gates'])
 def test_freeze_cli_runs_without_label_file(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'results') as d:
   d=Path(d); data=d/'data'; data.mkdir()
   for name in ('candidates.json','source-evidence-cases.json','protocol.json'): shutil.copy2(self.data/name,data/name)
   out=d/'frozen'; completed=subprocess.run([sys.executable,str(ROOT/'freeze_public_study.py'),'--data-dir',str(data),'--output',str(out)],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},text=True,capture_output=True,timeout=20); self.assertEqual(completed.returncode,0,completed.stderr); self.assertFalse((data/'labels.json').exists()); self.assertTrue((out/'source-records.json').exists())
 def _tamper_packet(self):
  temp=tempfile.TemporaryDirectory(dir=ROOT/'results'); base=Path(temp.name); data=base/'data'; result=base/'public'; shutil.copytree(self.data,data); shutil.copytree(ROOT/'results/public-study',result); refs=base/'reference-verification.csv'; shutil.copy2(ROOT/'reference-verification.csv',refs); frontend=base/'frontend.json'; shutil.copy2(ROOT/'results/source-frontend/summary.json',frontend); return temp,data,result,refs,frontend
 def test_verify_results_rejects_changed_score(self):
  temp,data,result,refs,frontend=self._tamper_packet()
  try:
   p=result/'frozen/predictions-frozen.json'
   with p.open(encoding='utf-8') as h: doc=json.load(h)
   doc['records'][0]['syntax_score']+=1; p.write_text(json.dumps(doc))
   with self.assertRaises((VerificationError,Invalid)): verify_public_packet(data,result,refs,frontend,ROOT)
  finally: temp.cleanup()
 def test_verify_results_rejects_duplicate_replacement_source_record(self):
  temp,data,result,refs,frontend=self._tamper_packet()
  try:
   p=result/'frozen/source-records.json'
   with p.open(encoding='utf-8') as h: doc=json.load(h)
   doc[-1]=copy.deepcopy(doc[0]); p.write_text(json.dumps(doc))
   with self.assertRaises((VerificationError,Invalid)): verify_public_packet(data,result,refs,frontend,ROOT)
  finally: temp.cleanup()
 def test_verify_results_rejects_csv_column_tamper(self):
  temp,data,result,refs,frontend=self._tamper_packet()
  try:
   p=result/'evaluation/scores.csv'
   with p.open(newline='',encoding='utf-8') as h: rows=list(csv.DictReader(h))
   fields=list(rows[0]); rows[0]['validated_score']=str(float(rows[0]['validated_score'])+0.5)
   with p.open('w',newline='') as h: w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)
   with self.assertRaises(VerificationError): verify_public_packet(data,result,refs,frontend,ROOT)
  finally: temp.cleanup()
 def test_verify_results_rejects_ranking_order_tamper(self):
  temp,data,result,refs,frontend=self._tamper_packet()
  try:
   p=result/'frozen/predictions-frozen.json'
   with p.open(encoding='utf-8') as h: doc=json.load(h)
   doc['records'][0],doc['records'][1]=doc['records'][1],doc['records'][0]
   p.write_text(json.dumps(doc))
   with self.assertRaises((VerificationError,Invalid)): verify_public_packet(data,result,refs,frontend,ROOT)
  finally: temp.cleanup()
 def test_verify_results_rejects_duplicate_replacement_outcome(self):
  temp,data,result,refs,frontend=self._tamper_packet()
  try:
   p=result/'frozen/outcomes.json'
   with p.open(encoding='utf-8') as h: doc=json.load(h)
   doc[-1]=copy.deepcopy(doc[0]); p.write_text(json.dumps(doc))
   with self.assertRaises((VerificationError,Invalid)): verify_public_packet(data,result,refs,frontend,ROOT)
  finally: temp.cleanup()

if __name__=='__main__': unittest.main()
