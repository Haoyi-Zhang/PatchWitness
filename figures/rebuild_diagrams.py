"""Regenerate the diagrams consumed by the article, including PDF mirrors."""
import argparse
import json
from pathlib import Path

from diagram_core import Figure
from diagram_kim import FIGURES as KIM
from diagram_saad import FIGURES as SAAD


LAYOUTS = KIM | SAAD
HERE = Path(__file__).resolve().parent


def generate(plan, dest=None, selected=()):
    project = plan['project']
    root = HERE.parents[1]
    failures = []
    for spec in plan['figures']:
        name = spec['asset']
        if selected and name not in selected:
            continue
        output = dest / (name + '.pdf') if dest else root / spec['targets'][0]
        try:
            layout = LAYOUTS[project][name]
            d = Figure(spec)
            layout(d)
            d.finish(output)
            if dest is None:
                payload = output.read_bytes()
                for rel in spec['targets'][1:]:
                    (root / rel).write_bytes(payload)
        except Exception as err:
            failures.append((name, str(err)))
            from matplotlib import pyplot
            pyplot.close('all')
    if failures:
        raise ValueError(f'{project}: {failures}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path)
    p.add_argument('names', nargs='*')
    a = p.parse_args()
    generate(json.loads((HERE / 'diagrams.json').read_text(encoding='utf-8')),
             a.output, a.names)
