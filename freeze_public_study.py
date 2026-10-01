#!/usr/bin/env python3
"""Freeze label-free scores and restricted source-evidence records."""
from __future__ import annotations
import argparse, json, resource, signal, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from public_study import freeze_predictions, load_json  # noqa:E402
from source_frontend import derive_evidence_document  # noqa:E402

def dump(path:Path,value:object)->None:
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=ROOT/'data/public-study')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); data=a.data_dir.resolve(); out=a.output.resolve()
    if out.exists(): p.error('output must not already exist')
    resource.setrlimit(resource.RLIMIT_CPU,(20,20)); resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('wall-limit'))); signal.alarm(40)
    start_cpu=time.process_time_ns(); start_wall=time.monotonic_ns()
    candidates=load_json(data/'candidates.json'); evidence=load_json(data/'source-evidence-cases.json')
    if derive_evidence_document(candidates)!=evidence: raise ValueError('source-evidence-not-derived-from-candidates')
    protocol=load_json(data/'protocol.json')
    predictions,outcomes,source_records=freeze_predictions(candidates,evidence,protocol)
    out.mkdir(parents=True,exist_ok=False)
    dump(out/'predictions-frozen.json',predictions); dump(out/'outcomes.json',outcomes); dump(out/'source-records.json',source_records)
    summary={
      'schema':'rbw-freeze-summary-v3','phase':'label-free-source-evidence-freeze',
      'candidate_units':len(predictions['records']),
      'accepted_source_records':sum(row['source_evidence_accepted'] for row in predictions['records']),
      'frontend_derived_cases':len(evidence['cases']),
      'candidate_hash':predictions['candidate_hash'],'source_evidence_hash':predictions['source_evidence_hash'],'protocol_hash':predictions['protocol_hash'],
      'cpu_seconds':(time.process_time_ns()-start_cpu)/1e9,'wall_seconds':(time.monotonic_ns()-start_wall)/1e9,
      'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1,'child_processes':0,'exit_status':0}
    dump(out/'freeze-summary.json',summary); print(json.dumps(summary,indent=2,sort_keys=True)); return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except (TimeoutError,MemoryError,ValueError,OSError) as exc:
      print(json.dumps({'state':'resource-or-input-abstention','reason':type(exc).__name__}),file=sys.stderr); raise SystemExit(2)
