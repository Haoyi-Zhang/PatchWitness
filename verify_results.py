#!/usr/bin/env python3
"""Fail-closed cross-file verification of retained scientific results."""
from __future__ import annotations
import csv, io, json, math
from pathlib import Path
import sys
from typing import Any

ROOT=Path(__file__).resolve().parent; RESULTS=ROOT/'results'; DATA=ROOT/'data/public-study'
sys.path.insert(0,str(ROOT/'src'))
from checker import check as finite_check  # noqa:E402
from producer import Fuel  # noqa:E402
from public_study import (  # noqa:E402
 canonical_hash,check_source_record,evaluate_predictions,freeze_predictions,load_json,load_json_value,
 validate_candidates,validate_labels,validate_outcomes,validate_predictions,validate_protocol,
 validate_source_evidence,validate_source_records,validate_study_design,
)
from source_frontend import derive_evidence_document  # noqa:E402

MAX_RESULT_BYTES=4*1024*1024
RUNTIME_KEYS={'cpu_seconds','wall_seconds','peak_rss_kib','workers','child_processes','exit_status','orchestrator_child_processes','evaluation_process_read_labels','freeze_and_evaluation_are_separate_processes'}

class VerificationError(RuntimeError): pass
def require(condition:bool,reason:str)->None:
    if not condition: raise VerificationError(reason)

def read_json(path:Path,root_type:type|tuple[type,...])->Any:
    raw=path.read_bytes(); require(len(raw)<=MAX_RESULT_BYTES,f'oversized:{path}')
    def pairs(items):
      out={}
      for k,v in items: require(k not in out,f'duplicate-json-key:{path}'); out[k]=v
      return out
    def reject(v): raise VerificationError(f'nonfinite-json:{path}:{v}')
    try: value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=reject)
    except (UnicodeError,json.JSONDecodeError) as exc: raise VerificationError(f'invalid-json:{path}') from exc
    require(isinstance(value,root_type),f'json-root:{path}'); return value

def read_csv(path:Path)->tuple[list[str],list[dict[str,str]]]:
    with path.open(newline='',encoding='utf-8') as h:
      r=csv.DictReader(h); require(r.fieldnames is not None,f'csv-header:{path}'); rows=list(r)
    require(all(None not in row for row in rows),f'csv-width:{path}'); return list(r.fieldnames),rows

def _strip_runtime(value:dict[str,Any])->dict[str,Any]: return {k:v for k,v in value.items() if k not in RUNTIME_KEYS}

def verified_reference_count(path:Path)->int:
    fields,rows=read_csv(path)
    require(fields==['citation_key','authoritative_url','persistent_id','metadata_status','content_check','checked_on','notes'],'reference-verification-schema')
    require(len({r['citation_key'] for r in rows})==len(rows),'reference-verification-duplicate')
    return sum(r['metadata_status']=='verified' and r['content_check'] in {'full-text','abstract','metadata-only'} and bool(r['authoritative_url']) and bool(r['persistent_id']) for r in rows)

def verify_finite()->dict[str,int]:
    directory=RESULTS/'finite-check'; summary=read_json(directory/'summary.json',dict); cases=read_json(directory/'cases.json',list); certs=read_json(directory/'certificates.json',list); fields,rows=read_csv(directory/'cases.csv')
    require(fields==['case','family','width','assignments','repair','regression','both-safe','both-fault','search_assignments','certificate_accepted','obligations'],'finite-csv-schema')
    require(len(cases)==len(rows)==25 and len(certs)==13,'finite-count')
    by={}
    for item,row in zip(cases,rows,strict=True):
      case=item['case']; require(case['id']==row['case'] and item['family']==row['family'] and case['id'] not in by,'finite-case-binding'); by[case['id']]=case
    fuel=Fuel(20000)
    for cert in certs:
      cid=cert.get('case',{}).get('id'); require(cid in by,'finite-cert-case'); ok,reason=finite_check(by[cid],cert,fuel); require(ok,f'finite-replay:{cid}:{reason}')
    totals={k:sum(int(r[k]) for r in rows) for k in ('assignments','repair','regression','both-safe','both-fault')}
    expected={'case_count':25,'assignments':3712,'repair':424,'regression':242,'both-safe':2990,'both-fault':56,'accepted_certificates':13,'mismatches':0,'semantic_mismatches':0,'obligations':90517,'exit_status':0}
    for k,v in expected.items(): require(summary.get(k)==v,f'finite-summary:{k}')
    for k,v in totals.items(): require(summary[k]==v,f'finite-total:{k}')
    return {'cases':25,'assignments':3712,'certificates_replayed':13}

def verify_pilot()->dict[str,int]:
    summary=read_json(RESULTS/'pilot/summary.json',dict)
    for k,v in {'case_count':1,'assignments':64,'repair':8,'regression':8,'both-safe':48,'both-fault':0,'accepted_certificates':1,'mismatches':0,'semantic_mismatches':0,'obligations':1552,'exit_status':0}.items(): require(summary.get(k)==v,f'pilot:{k}')
    return {'cases':1,'assignments':64}

def verify_closure()->dict[str,int]:
    s=read_json(RESULTS/'closure-checks/summary.json',dict); require(s.get('schema')=='rbw-closure-checks-v1' and s.get('mismatches')==0 and s.get('obligations')==19834,'closure-summary')
    require(s['candidate_frame_ambiguity']['full_window_precision_extremes']==[0.0,1.0],'closure-extremes')
    return {'obligations':19834}

def verify_frontend()->dict[str,Any]:
    candidates=load_json(DATA/'candidates.json'); retained=load_json(DATA/'source-evidence-cases.json'); require(derive_evidence_document(candidates)==retained,'frontend-derived-binding')
    summary=read_json(RESULTS/'source-frontend/summary.json',dict); mismatches=read_json(RESULTS/'source-frontend/mismatches.json',list); assignments=read_json(RESULTS/'source-frontend/assignments.json',dict)
    require(summary.get('schema')=='rbw-source-frontend-validation-v2' and summary.get('status')=='pass' and summary.get('mismatches')==0,'frontend-status')
    require(summary.get('candidate_hash')==canonical_hash(candidates) and summary.get('source_evidence_hash')==canonical_hash(retained),'frontend-hash')
    require(summary.get('guard_cases')==9 and summary.get('guard_assignments')==900 and summary.get('widening_checks')==1 and summary.get('semantic_obligations')==901,'frontend-counts')
    require(summary.get('supported_records')==10 and summary.get('typed_abstentions')==22 and summary.get('raw_diff_or_source_tree_correspondence') is False,'frontend-scope')
    require(mismatches==[],'frontend-mismatches')
    require(assignments.get('schema')=='rbw-frontend-assignment-plan-v1' and len(assignments.get('rows',[]))==900,'frontend-assignment-packet')
    by_case={}
    for row in assignments['rows']: by_case.setdefault(row['case'],[]).append(row)
    require(set(by_case)=={f'W{i:02d}' for i in range(2,11)} and all(len(v)==100 for v in by_case.values()),'frontend-case-plan')
    require({r['class'] for r in by_case['W03']} >= {'boundary-65535','boundary-65536','boundary-65537'},'frontend-w03-boundaries')
    require({r['class'] for r in by_case['W10']} >= {'zero-denominator-short-circuit','actual-division-true','actual-division-false'},'frontend-w10-branches')
    return {'supported_records':10,'semantic_obligations':901,'mismatches':0}

def _expected_csv_rows(scored:list[dict[str,Any]])->list[dict[str,Any]]:
    result=[]
    for original in scored:
      row=dict(original); features=row.pop('semantic_features'); result.append({**row,**features})
    return result

def verify_public_packet(data_dir:Path, result_dir:Path, reference_path:Path, frontend_path:Path, artifact_root:Path=ROOT)->dict[str,Any]:
    candidates=load_json(data_dir/'candidates.json'); labels_doc=load_json(data_dir/'labels.json'); evidence=load_json(data_dir/'source-evidence-cases.json'); protocol=load_json(data_dir/'protocol.json'); design=load_json(data_dir/'study-design.json')
    candidate_rows=validate_candidates(candidates); validate_labels(labels_doc,{r['id']:r['group'] for r in candidate_rows}); cases=validate_source_evidence(evidence,{r['id'] for r in candidate_rows}); validate_protocol(protocol,len(candidate_rows)); validate_study_design(design)
    frozen=result_dir/'frozen'; evaluation=result_dir/'evaluation'
    predictions=load_json(frozen/'predictions-frozen.json'); outcomes=load_json_value(frozen/'outcomes.json'); source_records=load_json_value(frozen/'source-records.json')
    validate_predictions(predictions,candidates,evidence,protocol); validate_outcomes(outcomes,predictions['records']); validate_source_records(source_records,cases,candidate_rows,outcomes)
    recomputed_predictions,recomputed_outcomes,recomputed_records=freeze_predictions(candidates,evidence,protocol)
    require(predictions==recomputed_predictions,'public-predictions-not-recomputed')
    require(outcomes==recomputed_outcomes,'public-outcomes-not-recomputed')
    require(source_records==recomputed_records,'public-source-records-not-recomputed')
    refs=verified_reference_count(reference_path); frontend=load_json(frontend_path)
    computed_summary,scored,computed_ablations,computed_readiness=evaluate_predictions(candidates,labels_doc,evidence,protocol,design,predictions,outcomes,refs,frontend,source_records,artifact_root)
    retained_summary=read_json(evaluation/'summary.json',dict); retained_ablations=read_json(evaluation/'ablations.json',list); retained_readiness=read_json(evaluation/'readiness.json',dict)
    require(retained_summary.get('evaluation_process_read_labels') is True and retained_summary.get('freeze_and_evaluation_are_separate_processes') is True,'public-process-separation-metadata')
    require(_strip_runtime(retained_summary)==computed_summary,'public-summary-cross-file')
    require(retained_ablations==computed_ablations,'public-ablations-cross-file')
    require(retained_readiness==computed_readiness,'public-readiness-cross-file')
    run_summary=read_json(result_dir/'run-summary.json',dict)
    require(_strip_runtime(run_summary)==computed_summary,'public-run-summary-cross-file')
    fields,actual=read_csv(evaluation/'scores.csv')
    expected_fields=['id','group','label','syntax_score','semantic_hint','unvalidated_score','source_evidence_accepted','validated_score','syntax_rank','unvalidated_rank','validated_rank','added_guard','range_relation','error_return','type_widening','overflow_division_guard']
    require(fields==expected_fields and len(actual)==len(scored),'scores-schema')
    expected=_expected_csv_rows(scored)
    int_columns={'label','semantic_hint','source_evidence_accepted','syntax_rank','unvalidated_rank','validated_rank','added_guard','range_relation','error_return','type_widening','overflow_division_guard'}
    float_columns={'syntax_score','unvalidated_score','validated_score'}
    for a,e in zip(actual,expected,strict=True):
      for col in expected_fields:
        if col in int_columns: require(int(a[col])==e[col],f'scores-column:{e["id"]}:{col}')
        elif col in float_columns: require(math.isclose(float(a[col]),float(e[col]),rel_tol=0,abs_tol=1e-12),f'scores-column:{e["id"]}:{col}')
        else: require(a[col]==e[col],f'scores-column:{e["id"]}:{col}')
    # Source manifest binds every retained real hunk and excludes labels.
    mf,manifest=read_csv(data_dir/'source-manifest.csv')
    expected_manifest_fields=['id','group','commit','commit_timestamp','file_path','repository','commit_url','source_kind','diff_selection','commit_message_sha256','diff_context_sha256','annotation_used_for_scoring']
    require(mf==expected_manifest_fields and len(manifest)==32,'manifest-schema')
    by={r['id']:r for r in candidate_rows}; require({r['id'] for r in manifest}==set(by),'manifest-coverage')
    import hashlib
    for row in manifest:
      c=by[row['id']]; source=c['source_asset']
      expected_row={
        'id':c['id'],'group':c['group'],'commit':c['commit'],'commit_timestamp':c['commit_timestamp'],
        'file_path':c['file_path'],'repository':source['repository'],'commit_url':source['commit_url'],
        'source_kind':source['source_kind'],'diff_selection':source['diff_selection'],
        'commit_message_sha256':hashlib.sha256(c['commit_message'].encode()).hexdigest(),
        'diff_context_sha256':hashlib.sha256(c['diff_context'].encode()).hexdigest(),
        'annotation_used_for_scoring':'true' if source['annotation_used_for_scoring'] else 'false',
      }
      require(row==expected_row,f'manifest-row:{c["id"]}')
    require(computed_summary['coverage']['positive_file_conditional']['fraction']=='10/16','coverage-positive-file')
    require(computed_summary['coverage']['positive_commit_conditional']['fraction']=='10/10','coverage-positive-commit')
    require(computed_summary['coverage']['all_candidate_file_availability']['fraction']=='10/32','coverage-all-file')
    require(computed_summary['coverage']['all_candidate_commit_availability']['fraction']=='10/26','coverage-all-commit')
    require(computed_summary['formal_h2_decision']=='not-testable-as-full-cohort-file-availability','h2-decision')
    return {'units':32,'source_records_replayed':10,'syntax_p20':computed_summary['metrics']['syntax']['precision_at_20'],'unvalidated_p20':computed_summary['metrics']['unvalidated']['precision_at_20'],'validated_p20':computed_summary['metrics']['validated']['precision_at_20']}

def verify_public()->dict[str,Any]: return verify_public_packet(DATA,RESULTS/'public-study',ROOT/'reference-verification.csv',RESULTS/'source-frontend/summary.json',ROOT)
def verify_references()->dict[str,int]:
    vf,v=read_csv(ROOT/'reference-verification.csv'); sf,s=read_csv(ROOT/'literature-screening.csv'); cf,c=read_csv(ROOT/'literature-calibration.csv')
    require(len(v)==len(s)==61 and len(c)==22,'reference-count'); require({r['citation_key'] for r in v}=={r['citation_key'] for r in s},'reference-key-binding')
    depths={}
    for row in v: require(row['metadata_status']=='verified' and row['persistent_id'] and row['authoritative_url'],'reference-status'); depths[row['content_check']]=depths.get(row['content_check'],0)+1
    require(depths=={'full-text':22,'abstract':33,'metadata-only':6},'reference-depths')
    return {**depths,'total':61}
def verify_campaign()->dict[str,int]:
    c=read_json(RESULTS/'campaign.json',dict); require(c.get('overall_obligation_ceiling')==250000,'campaign-ceiling'); total=c.get('total_counted_obligations_through_clean_reproduction'); require(type(total) is int and total<=250000,'campaign-total'); require(c.get('remaining_to_overall_ceiling')==250000-total,'campaign-remaining'); return {'total':total,'remaining':250000-total}
def main()->int:
    report={'schema':'rbw-retained-result-verification-v2','finite':verify_finite(),'pilot':verify_pilot(),'closure':verify_closure(),'frontend':verify_frontend(),'public':verify_public(),'references':verify_references(),'campaign':verify_campaign(),'status':'pass'}
    print(json.dumps(report,indent=2,sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except (OSError,ValueError,TypeError,KeyError,VerificationError) as exc:
      print(json.dumps({'status':'fail','reason':str(exc)}),file=sys.stderr); raise SystemExit(1)
