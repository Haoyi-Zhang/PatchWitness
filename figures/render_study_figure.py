"""Draw the exact width-three finite counterexample."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'artifact/figures'))
from patch_panels import coexisting

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path(__file__).with_name('coexisting-outcomes.pdf'))
    coexisting(p.parse_args().output)
