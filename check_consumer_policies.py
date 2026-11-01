"""Three receiver usage policies on the unchanged fourteen owned source pairs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from bounded_decision import pack_retained
from consumer_policy import decide,direct
def save(p,v):p.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def run(out):
    if out.exists() or out.resolve().is_relative_to(ROOT.resolve()):raise ValueError('new output outside artifact required')
    out.mkdir(parents=True)
    files=['data/functional-programs.json','results/functional-diagnostics/cases.json','src/consumer_policy.py','src/bounded_decision.py','src/functional_reference.py']
    bindings={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    policies=dict(partial_repair=dict(require_repair=True,allow_old_faults=True,required_inputs=[]),
        total_repair=dict(require_repair=True,allow_old_faults=False,required_inputs=[]),
        full_usage=dict(require_repair=False,allow_old_faults=True,required_inputs='all registered inputs'))
    save(out/'registration.json',dict(policies=policies,source_bindings=bindings,pairs=14,
        scope='Re-derive existing complete owned outcomes under new receiver requirements, not a new independent source sample',
        same_information='Both arms get the same separate source, domain and policy; direct receives no record',performance_claim=False))
    specs=json.loads((ROOT/files[0]).read_text())['cases']
    retained={r['id']:r for r in json.loads((ROOT/files[1]).read_text())}
    rows=[]
    for spec in specs:
        record=pack_retained(spec,retained[spec['id']])
        for name,definition in policies.items():
            policy=dict(definition)
            if name=='full_usage':policy['required_inputs']=[r['input'] for r in record['rows']]
            checked=decide(spec,record,policy);reference=direct(spec,policy)
            if checked!=reference:raise ValueError('same-information policy disagreement')
            rows.append(dict(case=spec['id'],policy_name=name,policy=policy,checked=checked,direct=reference,
                legacy_bounded_refinement=record['bounded_refinement'],input_count=len(record['rows'])))
    summary=dict(status='PASS',source_pairs=len(specs),decisions=len(rows),same_information_agreements=len(rows),
        approved={name:sum(r['checked']['approved'] for r in rows if r['policy_name']==name) for name in policies},
        refinement_insufficient_for_policy=sum(r['legacy_bounded_refinement'] and not r['checked']['approved'] for r in rows),
        new_independent_programs=0,source_bindings=bindings,performance_claim=False)
    save(out/'records.json',rows);save(out/'summary.json',summary)
    print(json.dumps(summary));return summary
def check_saved(path):
    registration=json.loads((path/'registration.json').read_text())
    rows=json.loads((path/'records.json').read_text());summary=json.loads((path/'summary.json').read_text())
    changed=[]
    for rel,digest in registration['source_bindings'].items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:
            captured=path/'source-preimage'/rel
            if not captured.is_file() or hashlib.sha256(captured.read_bytes()).hexdigest()!=digest:
                raise ValueError('saved input preimage missing or differs')
            changed.append(rel)
    specs={s['id']:s for s in json.loads((ROOT/'data/functional-programs.json').read_text())['cases']}
    retained={s['id']:s for s in json.loads((ROOT/'results/functional-diagnostics/cases.json').read_text())}
    seen=set();approved={name:0 for name in registration['policies']}
    for row in rows:
        key=(row['case'],row['policy_name'])
        if key in seen or key[0] not in specs or key[1] not in approved:raise ValueError('policy coverage')
        seen.add(key);spec=specs[key[0]];record=pack_retained(spec,retained[key[0]])
        policy=dict(registration['policies'][key[1]])
        if key[1]=='full_usage':policy['required_inputs']=[r['input'] for r in record['rows']]
        if row['policy']!=policy or decide(spec,record,policy)!=row['checked'] or direct(spec,policy)!=row['direct']:raise ValueError('policy decision differs')
        approved[key[1]]+=row['checked']['approved']
    if len(seen)!=42 or approved!=summary['approved']:raise ValueError('summary differs')
    print(json.dumps(dict(status='PASS',decisions=len(seen),approved=approved,
        measured_sources_differ_from_current=changed,current_direct_policy_recalculated=True)))
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--output',type=Path);g.add_argument('--check',type=Path)
    a=p.parse_args();check_saved(a.check) if a.check else run(a.output)
