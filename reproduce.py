#!/usr/bin/env python3
"""Offline single-worker clean replay of all canonical scientific outputs.

Every command is synchronous and has a wall timeout. Output must be new.
Failures preserve logs and are not reclassified as successful abstentions.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from public_study import typed_equal
from verify_results import read_json, _strip_runtime, verify_finite, verify_public_packet


def equal_file(a:Path,b:Path)->None:
    if a.suffix=='.json':
        if not typed_equal(read_json(a,(dict,list)),read_json(b,(dict,list))):
            raise RuntimeError('scientific JSON differs: '+str(a))
    elif a.read_bytes()!=b.read_bytes():
        raise RuntimeError('scientific file differs: '+str(a))


def compare_outputs(out:Path)->dict:
    checked=[]
    def compare(fresh,canonical,names):
        for name in names:
            equal_file(out/fresh/name,ROOT/'results'/canonical/name)
            checked.append(fresh+'/'+name)
    compare('finite','finite-check',['cases.json','cases.csv','certificates.json'])
    compare('pilot','pilot',['cases.json','cases.csv','certificates.json'])
    compare('frontend','source-frontend',['assignments.json','observations.json','coverage.json','mismatches.json'])
    compare('frame','finite-frame-audit',['summary.json'])
    for folder in ('finite','pilot','frontend','closure'):
        canonical={'finite':'finite-check','pilot':'pilot','frontend':'source-frontend','closure':'closure-checks'}[folder]
        if not typed_equal(_strip_runtime(read_json(out/folder/'summary.json',dict)),
                           _strip_runtime(read_json(ROOT/'results'/canonical/'summary.json',dict))):
            raise RuntimeError(folder+' non-runtime summary differs')
        checked.append(folder+'/summary.json (non-runtime)')
    compare('public/frozen','public-study/frozen',['predictions-frozen.json','outcomes.json','source-records.json'])
    compare('public/evaluation','public-study/evaluation',['scores.csv','ablations.json','readiness.json'])
    # Recompute from actual inputs rather than just compare saved files.
    finite=verify_finite(out/'finite')
    public=verify_public_packet(ROOT/'data/public-study',out/'public',
              ROOT/'reference-verification.csv',out/'frontend/summary.json',ROOT)
    return {'files_checked':checked,'finite':finite,'public':public}


def main()->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(ROOT/'results') or out==ROOT/'results' or out.exists():
        parser.error('output must be a new subdirectory of results')
    out.mkdir(parents=True);env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    py=sys.executable
    jobs=[('unit-tests',[py,'-m','unittest','discover','-s','tests','-v']),
          ('finite',[py,'run.py','--output',str(out/'finite')]),
          ('pilot',[py,'run.py','--pilot','--output',str(out/'pilot')]),
          ('frontend',[py,'run_frontend_validation.py','--output',str(out/'frontend')]),
          ('closure',[py,'run_closure_checks.py','--output',str(out/'closure')]),
          ('public',[py,'run_public_study.py','--output',str(out/'public')]),
          ('frame',[py,'run_contract_audit.py','--output',str(out/'frame')]),
          ('retained-verification',[py,'verify_results.py'])]
    report={'scope':'local single-worker reproduction, not independent external replication',
            'workers':1,'command_timeout_seconds':120,'commands':[],'status':'running'}
    wall=time.monotonic();cpu=time.process_time();child0=resource.getrusage(resource.RUSAGE_CHILDREN)
    try:
        for name,cmd in jobs:
            start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
            try:
                with (out/(name+'.stdout.txt')).open('w') as so,(out/(name+'.stderr.txt')).open('w') as se:
                    proc=subprocess.run(cmd,cwd=ROOT,env=env,stdout=so,stderr=se,timeout=120,check=False)
                code=proc.returncode
            except subprocess.TimeoutExpired:
                code=124
            after=resource.getrusage(resource.RUSAGE_CHILDREN)
            report['commands'].append({'name':name,'command':[Path(cmd[0]).name,*[str(x).replace(str(out),'$OUTPUT') for x in cmd[1:]]],
                'exit_status':code,'wall_seconds':time.monotonic()-start,
                'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime})
            if code!=0:raise RuntimeError(name+' failed; inspect retained logs')
        report['comparison']=compare_outputs(out)
        report['status']='pass'
    except Exception as exc:
        report['status']='fail';report['failure']=str(exc)
    child1=resource.getrusage(resource.RUSAGE_CHILDREN)
    report['wall_seconds']=time.monotonic()-wall
    report['parent_cpu_seconds']=time.process_time()-cpu
    report['children_cpu_seconds']=child1.ru_utime+child1.ru_stime-child0.ru_utime-child0.ru_stime
    report['parent_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['children_peak_rss_kib']=child1.ru_maxrss
    (out/'replay-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if report['status']=='pass' else 1

if __name__=='__main__':raise SystemExit(main())
