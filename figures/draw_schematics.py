"""Draw the manuscript schematics directly as font-embedded vector PDFs.

Run: python figures/draw_schematics.py --output figures
Requires Python 3.9+ and Matplotlib. No TeX engine or network is used.
The diagrams express the defined model; they are not measurement plots.
"""
import argparse
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch

plt.rcParams.update({'font.family':'STIXGeneral', 'mathtext.fontset':'stix',
                     'font.size':9, 'pdf.fonttype':42, 'ps.fonttype':42,
                     'text.usetex':False, 'axes.unicode_minus':False})
CM = 1 / 2.54

class Drawing:
    def __init__(self, bounds):
        x0,y0,x1,y1 = bounds
        self.fig = plt.figure(figsize=((x1-x0)*CM,(y1-y0)*CM))
        self.ax = self.fig.add_axes([0,0,1,1], xlim=(x0,x1), ylim=(y0,y1))
        self.ax.set_aspect('equal'); self.ax.axis('off')
        self.nodes = {}
        self.labels = []

    def text(self,x,y,label,size=9,ha='center',va='center'):
        artist=self.ax.text(x,y,label,fontsize=size,ha=ha,va=va,
                            linespacing=1.15,clip_on=False,zorder=4)
        self.labels.append([artist,None])
        return artist

    def box(self,name,x,y,w,h,label,dashed=False,shape='rect',size=9):
        style = {'edgecolor':'black','facecolor':'white','linewidth':.55,
                 'linestyle':(0,(4,3)) if dashed else 'solid', 'zorder':2}
        if shape == 'diamond':
            obj = Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],**style)
        elif shape == 'circle': obj = Circle((x,y),w/2,**style)
        else: obj = Rectangle((x-w/2,y-h/2),w,h,**style)
        self.ax.add_patch(obj); self.text(x,y,label,size)
        self.labels[-1][1]=(x-w/2,y-h/2,x+w/2,y+h/2)
        self.nodes[name] = (x,y,w,h,shape)

    def point(self,name,side):
        x,y,w,h,_ = self.nodes[name]
        return {'n':(x,y+h/2),'s':(x,y-h/2),'e':(x+w/2,y),
                'w':(x-w/2,y),'nw':(x-w/2,y+h/2),
                'ne':(x+w/2,y+h/2),'c':(x,y)}[side]

    def line(self,points,dashed=False):
        xs,ys=zip(*points)
        self.ax.plot(xs,ys,color='black',linewidth=.55,
                     linestyle=(0,(4,3)) if dashed else 'solid',zorder=1)

    def arrow(self,p,q,dashed=False,via=()):
        points=[p,*via,q]
        if via:self.line(points[:-1],dashed)
        self.ax.add_patch(FancyArrowPatch(points[-2],points[-1],
                         arrowstyle='-|>',mutation_scale=7.5,linewidth=.55,
                         color='black',shrinkA=0,shrinkB=0,
                         linestyle=(0,(4,3)) if dashed else 'solid',zorder=1))

    def edge(self,a,b,sa='s',sb='n',**kwargs):
        self.arrow(self.point(a,sa),self.point(b,sb),**kwargs)

    def frame(self,x,y,w,h):
        self.ax.add_patch(Rectangle((x,y),w,h,fill=False,edgecolor='black',
                                   linewidth=.55,linestyle=(0,(4,3)),zorder=0))

    def save(self,out,name):
        # Fixed physical canvas: do not enlarge or rasterize the scientific figure.
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        x0,x1=self.ax.get_xlim();y0,y1=self.ax.get_ylim()
        for artist,node in self.labels:
            b=artist.get_window_extent(renderer).transformed(self.ax.transData.inverted())
            if b.x0<x0-.02 or b.x1>x1+.02 or b.y0<y0-.02 or b.y1>y1+.02:
                raise ValueError(name+': clipped label '+repr(artist.get_text()))
            if node and (b.x0<node[0]-.02 or b.x1>node[2]+.02 or b.y0<node[1]-.02 or b.y1>node[3]+.02):
                raise ValueError(name+': label exceeds node '+repr(artist.get_text()))
        self.fig.savefig(out/(name+'.pdf'),format='pdf',
                         metadata={'Creator':'Python Matplotlib','Producer':None,
                                   'CreationDate':None,'ModDate':None})
        plt.close(self.fig)



def draw(out):
    # Expected object binding and separate replay are required before acceptance.
    d=Drawing((-1.85,-1.25,9.75,2.65))
    d.box('case',0,1.7,3.2,1.3,'Expected IR case $C$\nand input domain')
    d.box('producer',0,-.4,3.2,1.3,'Untrusted producer\ncertificate $W$',dashed=True)
    d.box('checker',4,1,3,1.3,'Structural binding\nand separate replay')
    d.box('claim',8,1,3,1.3,'One input $x\\in D$\nold fault, new defined')
    d.edge('case','checker','e','w',via=((2.1,1.7),(2.1,1)))
    d.edge('case','producer');d.text(.18,.65,'$C$',ha='left')
    d.edge('producer','checker','e','s',via=((4,-.4),));d.text(4.17,-.03,'$W$',ha='left')
    d.edge('checker','claim','e','w');d.text(6,1.28,'accept')
    d.save(out,'trust-boundary')

    # Each arrow is a further justification obligation, not automatic implication.
    d=Drawing((-1.9,-4.2,10.1,1.15))
    for name,x,y,label in [('a',0,0,'Acquisition\nrevision, date,\nlabel provenance'),
                           ('b',4.1,0,'Representation\nsource/IR relation'),
                           ('c',8.2,0,'Replay\nspecified relation\ntyped outcomes'),
                           ('d',8.2,-3.1,'Ranking\nfrozen rule and budget'),
                           ('e',4.1,-3.1,'Utility\nheld-out precision\nand coverage')]:d.box(name,x,y,3.1,1.8,label)
    d.edge('a','b','e','w');d.edge('b','c','e','w');d.edge('c','d');d.edge('d','e','w','e')
    d.save(out,'evidence-ladder')

    # Labels feed only evaluation. The prediction file precedes label opening.
    d=Drawing((-2.4,-3.5,7.6,1.2))
    d.box('inputs',0,0,4.3,1.8,'1. Label-free inputs\n32 candidates, ten\nsource-evidence cases,\nfrozen protocol',size=8.5)
    d.box('freeze',5.2,0,4.3,1.8,'2. Freeze predictions\nsyntax, unvalidated hints,\nchecked source records,\ninput bindings',size=8.5)
    d.box('labels',0,-2.4,4.3,1.8,'3. Separate labels\nopened only after\nprediction file exists',size=8.5)
    d.box('eval',5.2,-2.4,4.3,1.8,'4. Evaluate and gate\nP@20, grouping,\nintervals, ablations,\nreadiness',size=8.5)
    d.edge('inputs','freeze','e','w');d.edge('freeze','eval')
    d.edge('labels','eval','e','w',dashed=True)
    d.save(out,'study-pipeline')

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parent)
    output=parser.parse_args().output
    output.mkdir(parents=True,exist_ok=True)
    draw(output)
