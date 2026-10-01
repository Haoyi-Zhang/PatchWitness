#!/usr/bin/env python3
"""Open retrospective labels and evaluate a frozen descriptive packet."""
from __future__ import annotations
import argparse,csv,json,resource,signal,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from public_study import evaluate_predictions,load_json,load_json_value  # noqa:E402

def dump(path:Path,value:object)->None: path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def verified_reference_count(path:Path)->int:
    with path.open(newline='',encoding='utf-8') as h:
      r=csv.DictReader(h); required={'citation_key','authoritative_url','persistent_id','metadata_status','content_check','checked_on','notes'}
      if r.fieldnames is None or set(r.fieldnames)!=required: raise ValueError('reference-verification-schema')
      rows=list(r)
    if len({x['citation_key'] for x in rows})!=len(rows): raise ValueError('duplicate-reference-verification')
    return sum(x['metadata_status']=='verified' and x['content_check'] in {'full-text','abstract','metadata-only'} and bool(x['authoritative_url']) and bool(x['persistent_id']) for x in rows)
def main()->int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--data-dir',type=Path,default=ROOT/'data/public-study'); p.add_argument('--frozen',type=Path,required=True); p.add_argument('--reference-verification',type=Path,default=ROOT/'reference-verification.csv'); p.add_argument('--frontend-validation',type=Path,default=ROOT/'results/source-frontend/summary.json'); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    data=a.data_dir.resolve(); frozen=a.frozen.resolve(); out=a.output.resolve()
    if out.exists(): p.error('output must not already exist')
    resource.setrlimit(resource.RLIMIT_CPU,(20,20)); resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024)); signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('wall-limit'))); signal.alarm(40)
    start_cpu=time.process_time_ns(); start_wall=time.monotonic_ns()
    candidates=load_json(data/'candidates.json'); labels=load_json(data/'labels.json'); evidence=load_json(data/'source-evidence-cases.json'); protocol=load_json(data/'protocol.json'); design=load_json(data/'study-design.json'); predictions=load_json(frozen/'predictions-frozen.json'); outcomes=load_json_value(frozen/'outcomes.json'); source_records=load_json_value(frozen/'source-records.json'); refs=verified_reference_count(a.reference_verification.resolve()); frontend=load_json(a.frontend_validation.resolve())
    summary,scored,ablations,readiness=evaluate_predictions(candidates,labels,evidence,protocol,design,predictions,outcomes,refs,frontend,source_records,ROOT)
    summary.update(evaluation_process_read_labels=True,freeze_and_evaluation_are_separate_processes=True,cpu_seconds=(time.process_time_ns()-start_cpu)/1e9,wall_seconds=(time.monotonic_ns()-start_wall)/1e9,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,workers=1,child_processes=0,exit_status=0)
    out.mkdir(parents=True,exist_ok=False); dump(out/'summary.json',summary); dump(out/'readiness.json',readiness); dump(out/'ablations.json',ablations)
    fields=['id','group','label','syntax_score','semantic_hint','unvalidated_score','source_evidence_accepted','validated_score','syntax_rank','unvalidated_rank','validated_rank','added_guard','range_relation','error_return','type_widening','overflow_division_guard']
    with (out/'scores.csv').open('w',newline='',encoding='utf-8') as h:
      w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
      for original in scored:
        row=dict(original); features=row.pop('semantic_features'); w.writerow({**row,**{k:features[k] for k in fields if k in features}})
    print(json.dumps(summary,indent=2,sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except (TimeoutError,MemoryError,ValueError,OSError,json.JSONDecodeError) as exc:
      print(json.dumps({'state':'resource-or-input-abstention','reason':type(exc).__name__}),file=sys.stderr); raise SystemExit(2)
