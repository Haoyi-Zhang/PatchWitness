"""Three receiver usage policies on the unchanged fourteen owned source pairs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
from bounded_decision import pack_retained
from consumer_policy import decide,direct
from public_study import load_json_value,typed_equal

SOURCE_FILES=('data/functional-programs.json','results/functional-diagnostics/cases.json',
              'src/consumer_policy.py','src/bounded_decision.py','src/functional_reference.py')
POLICIES=dict(partial_repair=dict(require_repair=True,allow_old_faults=True,required_inputs=[]),
    total_repair=dict(require_repair=True,allow_old_faults=False,required_inputs=[]),
    full_usage=dict(require_repair=False,allow_old_faults=True,required_inputs='all registered inputs'))

def registration_for(bindings):
    return dict(policies=copy.deepcopy(POLICIES),source_bindings=bindings,pairs=14,
        scope='Re-derive existing complete owned outcomes under new receiver requirements, not a new independent source sample',
        same_information='Both arms get the same separate source, domain and policy; direct receives no record',performance_claim=False)

def summary_for(rows,bindings):
    return dict(status='PASS',source_pairs=len({r['case'] for r in rows}),decisions=len(rows),
        same_information_agreements=len(rows),
        approved={name:sum(r['checked']['approved'] for r in rows if r['policy_name']==name) for name in POLICIES},
        refinement_insufficient_for_policy=sum(r['legacy_bounded_refinement'] and not r['checked']['approved'] for r in rows),
        new_independent_programs=0,source_bindings=bindings,performance_claim=False)

def save(p,v):p.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def run(out):
    if out.exists() or out.resolve().is_relative_to(ROOT.resolve()):raise ValueError('new output outside artifact required')
    out.mkdir(parents=True)
    files=SOURCE_FILES
    bindings={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
    policies=copy.deepcopy(POLICIES)
    save(out/'registration.json',registration_for(bindings))
    specs=json.loads((ROOT/files[0]).read_text())['cases']
    retained={r['id']:r for r in json.loads((ROOT/files[1]).read_text())}
    rows=[]
    for spec in specs:
        record=pack_retained(spec,retained[spec['id']])
        for name,definition in policies.items():
            policy=dict(definition)
            if name=='full_usage':policy['required_inputs']=[r['input'] for r in record['rows']]
            checked=decide(spec,record,policy);reference=direct(spec,policy)
            if not typed_equal(checked,reference):raise ValueError('same-information policy disagreement')
            rows.append(dict(case=spec['id'],policy_name=name,policy=policy,checked=checked,direct=reference,
                legacy_bounded_refinement=record['bounded_refinement'],input_count=len(record['rows'])))
    summary=summary_for(rows,bindings)
    save(out/'records.json',rows);save(out/'summary.json',summary)
    print(json.dumps(summary));return summary
def check_saved(path):
    registration=load_json_value(path/'registration.json')
    rows=load_json_value(path/'records.json');summary=load_json_value(path/'summary.json')
    if type(registration) is not dict:raise ValueError('registration schema')
    bindings=registration.get('source_bindings')
    if (type(bindings) is not dict or set(bindings)!=set(SOURCE_FILES)
        or any(type(digest) is not str or len(digest)!=64
               or any(c not in '0123456789abcdef' for c in digest) for digest in bindings.values())):
        raise ValueError('source binding inventory')
    if not typed_equal(registration,registration_for(bindings)):raise ValueError('registration differs')
    if type(rows) is not list or len(rows)!=42:raise ValueError('policy coverage')
    changed=[]
    for rel,digest in bindings.items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:
            captured=path/'source-preimage'/rel
            if not captured.is_file() or hashlib.sha256(captured.read_bytes()).hexdigest()!=digest:
                raise ValueError('saved input preimage missing or differs')
            changed.append(rel)
    source_specs=json.loads((ROOT/'data/functional-programs.json').read_text())['cases']
    source_retained=json.loads((ROOT/'results/functional-diagnostics/cases.json').read_text())
    specs={s['id']:s for s in source_specs};retained={s['id']:s for s in source_retained}
    if len(source_specs)!=len(specs) or len(specs)!=14 or len(source_retained)!=len(retained) or set(retained)!=set(specs):
        raise ValueError('complete unique owned case inventory required')
    seen=set();expected_rows=[]
    for row in rows:
        if (type(row) is not dict or type(row.get('case')) is not str
            or type(row.get('policy_name')) is not str):raise ValueError('policy row schema')
        key=(row['case'],row['policy_name'])
        if key in seen or key[0] not in specs or key[1] not in POLICIES:raise ValueError('policy coverage')
        seen.add(key);spec=specs[key[0]];record=pack_retained(spec,retained[key[0]])
        policy=copy.deepcopy(POLICIES[key[1]])
        if key[1]=='full_usage':policy['required_inputs']=[r['input'] for r in record['rows']]
        checked=decide(spec,record,policy);reference=direct(spec,policy)
        if not typed_equal(checked,reference):raise ValueError('same-information policy disagreement')
        expected=dict(case=key[0],policy_name=key[1],policy=policy,checked=checked,direct=reference,
            legacy_bounded_refinement=record['bounded_refinement'],input_count=len(record['rows']))
        if not typed_equal(row,expected):raise ValueError('policy decision differs')
        expected_rows.append(expected)
    if seen!={(ident,name) for ident in specs for name in POLICIES}:raise ValueError('policy coverage')
    expected_summary=summary_for(expected_rows,bindings)
    if not typed_equal(summary,expected_summary):raise ValueError('summary differs')
    approved=expected_summary['approved']
    print(json.dumps(dict(status='PASS',decisions=len(seen),approved=approved,
        measured_sources_differ_from_current=changed,current_direct_policy_recalculated=True)))
if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--output',type=Path);g.add_argument('--check',type=Path)
    a=p.parse_args();check_saved(a.check) if a.check else run(a.output)
