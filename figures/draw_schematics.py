"""Draw the contract and study process as editable vectors."""
import argparse
from pathlib import Path
from patch_panels import evidence_ladder, study_pipeline, trust_boundary


def draw(out):
    for name,fn in [('study-pipeline',study_pipeline),('trust-boundary',trust_boundary),
                    ('evidence-ladder',evidence_ladder)]:
        fn(out/(name+'.pdf'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    draw(p.parse_args().output)
