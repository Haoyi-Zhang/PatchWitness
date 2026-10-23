"""Check retained owned source outcomes and export their bounded decisions.

No public patches or historical measurements are executed or overwritten.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from bounded_decision import pack_retained, validate, KINDS


def collect():
    specs = json.loads((ROOT / 'data/functional-programs.json').read_text(encoding='utf-8'))['cases']
    retained = json.loads((ROOT / 'results/functional-diagnostics/cases.json').read_text(encoding='utf-8'))
    if len({r['id'] for r in retained}) != len(retained):
        raise ValueError('duplicate retained case')
    by_id = {r['id']: r for r in retained}
    if set(by_id) != {s['id'] for s in specs} or len(specs) != 14:
        raise ValueError('complete owned case inventory required')
    records, rows = [], []
    for spec in specs:
        record = pack_retained(spec, by_id[spec['id']])
        result = validate(spec, record)
        records.append(record)
        rows.append(dict(id=spec['id'], inputs=result['inputs_checked'],
                         existential_repair=record['counts']['repair'] > 0,
                         **result))
    summary = dict(status='PASS', cases=len(rows), inputs_checked=sum(r['inputs'] for r in rows),
                   existential_repairs=sum(r['existential_repair'] for r in rows),
                   bounded_refinements=sum(r['bounded_refinement'] for r in rows),
                   repair_with_new_fault=[r['id'] for r in rows
                                          if r['existential_repair'] and r['counts']['new-fault']],
                   counts={k: sum(r['counts'][k] for r in rows) for k in KINDS},
                   rows=rows, scope='Rechecked retained authored pure/helper sources, not public patches')
    return summary, records


def table(rows):
    text = [r'\begin{tabular}{lrrrrrr}', r'\toprule',
            r'Pair & Inputs & Repair & New fault & Changed & Both fault & Refines \\',
            r'\midrule']
    for r in rows:
        text.append(' & '.join([r['id'], str(r['inputs']), str(r['counts']['repair']),
            str(r['counts']['new-fault']), str(r['counts']['defined-changed']),
            str(r['counts']['both-fault']), 'yes' if r['bounded_refinement'] else 'no']) + r' \\')
    return '\n'.join(text + [r'\bottomrule', r'\end{tabular}', ''])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('output must be a new directory')
    summary, records = collect()
    products = {'summary.json': json.dumps(summary, indent=2, sort_keys=True) + '\n',
                'records.json': json.dumps(records, indent=2, sort_keys=True) + '\n',
                'table.tex': table(summary['rows'])}
    if args.compare:
        for name, content in products.items():
            if (args.compare / name).read_bytes() != content.encode():
                raise SystemExit('Scientific retained-consumer output differs: ' + name)
    args.output.mkdir(parents=True)
    for name, content in products.items():
        (args.output / name).write_text(content, encoding='utf-8', newline='\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
