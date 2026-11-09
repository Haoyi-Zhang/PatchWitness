"""Rebuild the paper's mechanism schematics at their intended physical size."""
from pathlib import Path
from diagram_core import Figure, BLUE, GRAY, INK, RED

def replay_branch(f):
    f.t(44,20,'Old',align='left',bold=True)
    f.t(44,58,'New',align='left',bold=True)
    f.node(133,23,'run','3 + 1',side='right')
    f.route((187,23),(231,23))
    f.node(246,23,'reject','Overflow',side='right',color=RED)
    f.node(133,58,'branch','x = 3',side='right')
    f.route((190,58),(231,58))
    f.node(246,58,'check','Return 3',side='right')
    f.route((198,58),(198,85),(231,85),dash=True,color=GRAY)
    f.t(246,85,'else not run',align='left',color=GRAY,style='italic')

def finite_search(f):
    f.node(55,50,'grid','Finite domain')
    f.route((71,50),(119,50))
    f.line((119,15),(119,84),color=BLUE,check=True)
    for y,icon,l,r,color in [(15,'cert','Witness found','Replay certificate',BLUE),
                               (49,'check','Search completed','No witness found',BLUE),
                               (84,'partial','Budget exhausted','Abstention',RED)]:
        f.route((119,y),(153,y),color=color,dash=y==84)
        f.node(169,y,icon,l,side='right',color=color)
        f.route((273,y),(302,y),color=color,dash=y==84)
        f.t(316,y,r,align='left',color=color)

FIGURES = [('replay_branch', 420, 79), ('finite_search', 420, 84)]

if __name__ == '__main__':
    for name,w,h in FIGURES:
        f=Figure(dict(media=(w,h),trim=(0,0,0,0),width=w))
        globals()[name](f)
        f.finish(Path(__file__).parent/(name.replace('_','-')+'.pdf'))
