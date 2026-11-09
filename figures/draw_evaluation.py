"""Draw statistical vectors from the fixed retained tables."""
from pathlib import Path
import csv
import io
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'artifact/figures'))
from patch_panels import availability, intervals, precision

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SNAPSHOTS = {
  "figures/precision-profile.csv": "k,syntax,hint,checked,difference\n1,1,1,1,0\n2,1,1,1,0\n3,1,1,1,0\n4,1,1,1,0\n5,1,1,1,0\n6,1,1,1,2\n7,1,1,1,2\n8,1,1,1,0\n9,1,1,1,0\n10,1,1,1,2\n11,1,1,1,2\n12,1,1,1,2\n13,1,1,1,0\n14,0.928571428571,1,1,2\n15,0.933333333333,1,0.933333333333,0\n16,0.9375,1,0.9375,0\n17,0.882352941176,0.941176470588,0.882352941176,0\n18,0.833333333333,0.888888888889,0.833333333333,0\n19,0.789473684211,0.842105263158,0.789473684211,0\n20,0.75,0.8,0.75,0\n21,0.714285714286,0.761904761905,0.714285714286,0\n22,0.681818181818,0.727272727273,0.681818181818,0\n23,0.695652173913,0.695652173913,0.695652173913,0\n24,0.666666666667,0.666666666667,0.666666666667,0\n25,0.64,0.64,0.64,0\n26,0.615384615385,0.615384615385,0.615384615385,0\n27,0.592592592593,0.592592592593,0.592592592593,0\n28,0.571428571429,0.571428571429,0.571428571429,0\n29,0.551724137931,0.551724137931,0.551724137931,0\n30,0.533333333333,0.533333333333,0.533333333333,0\n31,0.516129032258,0.516129032258,0.516129032258,0\n32,0.5,0.5,0.5,0\n",
  "figures/availability-profile.csv": "category,label,fraction,annotation\n1,Positive files,0.625,10/16\n2,Positive commits,1,10/10\n3,All files,0.3125,10/32\n4,All commits,0.384615384615,10/26\n",
  "figures/audit-intervals.csv": "row,label,lower,upper,observed\n1,Checked: h=1,0,0,0\n2,Hints: h=1,0,0.05,0.05\n3,Checked: labels hidden,0,0,0\n4,Hints: labels hidden,-0.05,0.05,0.05\n"
}


def read_rows(path):
    text=(ROOT/path).read_text(encoding='utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(text)))
    if rows!=list(csv.DictReader(io.StringIO(SNAPSHOTS[path]))):
        raise ValueError("Retained CSV changed: "+path)
    return rows


def main():
    for name,fn in [('precision-profile',precision),('availability-profile',availability),
                    ('audit-intervals',intervals)]:
        fn(read_rows('figures/'+name+'.csv'),HERE/(name+'.pdf'))


if __name__=='__main__':
    main()
