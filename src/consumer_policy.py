"""Receiver-selected finite usage obligations, separate from record validity.

Global old-defined preservation always holds. Applications may additionally
require total repair or defined outputs on an explicit usage subset. Neither
an existential repair nor the legacy refinement flag approves these policies.
"""
from __future__ import annotations
import itertools
import checker
from bounded_decision import Budget, validate, classify, KINDS

def policy_inputs(spec,policy):
    from functional_frontend import translate_pair
    checker.validate_case(translate_pair(spec['id'],spec['width'],spec['domain'],spec['before'],spec['after']))
    checker._fail(type(policy) is dict and set(policy)=={'require_repair','allow_old_faults','required_inputs'},'usage-policy-fields')
    checker._fail(type(policy['require_repair']) is bool and type(policy['allow_old_faults']) is bool,'usage-policy-flags')
    inputs=policy['required_inputs']
    checker._fail(type(inputs) is list and len(inputs)<=checker.MAX_STATES,'usage-input-bound')
    seen=set()
    for row in inputs:
        checker._fail(type(row) is list and len(row)==len(spec['domain']) and all(type(v) is int for v in row),'usage-input-types')
        checker._fail(all(lo<=v<=hi for v,(lo,hi) in zip(row,spec['domain'])),'usage-input-domain')
        checker._fail(tuple(row) not in seen,'usage-input-duplicate');seen.add(tuple(row))
    return seen

def interpret(spec,rows,counts,policy):
    required=policy_inputs(spec,policy);reasons=[];missing=[]
    if policy['require_repair'] and counts['repair']==0:reasons.append('no-repaired-input')
    if counts['new-fault']:reasons.append('new-fault')
    if counts['defined-changed']:reasons.append('old-defined-output-changed')
    if not policy['allow_old_faults'] and counts['both-fault']:reasons.append('remaining-old-fault')
    for row in rows:
        if tuple(row['input']) in required and row['after'][0]!='u':missing.append(row['input'])
    if missing:reasons.append('required-usage-still-faults')
    return dict(approved=not reasons,reasons=reasons,required_faulting_inputs=missing,counts=counts)

def decide(spec,record,policy,budget=None):
    policy_inputs(spec,policy)
    validated=validate(spec,record,budget)
    return interpret(spec,record['rows'],validated['counts'],policy)

def direct(spec,policy):
    """Direct policy predicates, without the record classifier or interpreter.

    Only input-schema admission is shared with the checked path. This remains
    an implementation cross-check under the same authored mathematical policy.
    """
    from functional_reference import build_reference
    required=policy_inputs(spec,policy)
    before=build_reference(spec['before'],spec['width']);after=build_reference(spec['after'],spec['width'])
    counts=dict.fromkeys(KINDS,0);rows=[]
    for values in itertools.product(*(range(lo,hi+1) for lo,hi in spec['domain'])):
        old,new=before(list(values)),after(list(values))
        if old[0]=='fault':kind='both-fault' if new[0]=='fault' else 'repair'
        elif new[0]=='fault':kind='new-fault'
        else:kind='defined-equal' if old[1]==new[1] else 'defined-changed'
        counts[kind]+=1
        rows.append(dict(input=list(values),before=old,after=new))
    # Evaluate the mathematical obligations directly over source outcomes.
    reasons=[]
    if policy['require_repair'] and not any(r['before'][0]=='fault' and r['after'][0]=='u' for r in rows):reasons.append('no-repaired-input')
    if any(r['before'][0]=='u' and r['after'][0]=='fault' for r in rows):reasons.append('new-fault')
    if any(r['before'][0]==r['after'][0]=='u' and r['before'][1]!=r['after'][1] for r in rows):reasons.append('old-defined-output-changed')
    if not policy['allow_old_faults'] and any(r['before'][0]==r['after'][0]=='fault' for r in rows):reasons.append('remaining-old-fault')
    missing=[r['input'] for r in rows if tuple(r['input']) in required and r['after'][0]!='u']
    if missing:reasons.append('required-usage-still-faults')
    return dict(approved=not reasons,reasons=reasons,required_faulting_inputs=missing,counts=counts)
