"""Build the vector diagram used in the main manuscript."""
from pathlib import Path
from visual_grammar import Diagram, BLUE, RED, INK, MUTED, PALE, WARM, GRID

def draw(out):
    d=Diagram(w=408,h=105)
    for l,w,label,c,fill in ((17,104,'Only in A (+)',BLUE,PALE),(121,166,'Shared (0)',MUTED,'white'),(287,104,'Only in B (-)',RED,WARM)):
        d.line((l,51),(l+w,51),c=c,lw=1.15)
        d.text(l+w/2,65,label,10.5,INK if c!=RED else RED,bold=True)
    d.line((17,90),(17,83),(287,83),(287,90),c=BLUE)
    d.text(152,96,'Top-k set A',10.3,INK,bold=True)
    d.line((121,36),(121,42),(391,42),(391,36),c=RED)
    d.text(256,31,'Top-k set B',10.3,INK,bold=True)
    d.ax.set_ylim(21,105)
    d.fig.set_size_inches(408/72,84/72)
    d.finish(out)

if __name__ == '__main__':
    draw(Path(__file__).with_name('paired-ranking-membership.pdf'))
