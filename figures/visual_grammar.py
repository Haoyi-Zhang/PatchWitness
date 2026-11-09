"""Vector drawing primitives shared by the paper's editable figure sources."""
import os
from pathlib import Path
import matplotlib as mpl
mpl.use('Agg')
from matplotlib import font_manager as fm, pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

INK='#182630'
MUTED='#4f5b65'
GRID='#d7dee3'
# Navy and slate form the print palette. Rust is reserved for a meaningful
# exception or the opposite sign of a diverging scale. Keep the legacy
# aliases so every older editable diagram uses the same house palette.
BLUE='#264e67'
TEAL='#42677b'
RED='#864739'
OCHRE='#626970'
PURPLE='#555e66'
PALE='#eef2f4'
GREEN='#e8eff2'
WARM='#f7eeeb'
CREAM='#f5f6f7'
META={'Creator':'Python Matplotlib','CreationDate':None,'ModDate':None}
FAMILY='Linux Libertine'
FACES={('normal','normal'):'LinLibertine_Rah.ttf',
       ('normal','bold'):'LinLibertine_RBah.ttf',
       ('italic','normal'):'LinLibertine_RIah.ttf',
       ('italic','bold'):'LinLibertine_RBIah.ttf'}


def typography():
    # The ACM template uses Linux Libertine Type 1. These are its unmodified
    # TrueType counterparts for direct vector export with editable labels.
    directory=Path(os.environ.get('LIBERTINE_FONT_DIR',Path(__file__).resolve().parents[1]/'fonts'))
    for filename in FACES.values():
        f=directory/filename
        if not f.is_file() or fm.FontProperties(fname=str(f)).get_name()!=FAMILY:
            raise RuntimeError(f'Expected the Linux Libertine face {f}')
        if str(f) not in {entry.fname for entry in fm.fontManager.ttflist}:
            fm.fontManager.addfont(str(f))
    for (style,weight),filename in FACES.items():
        found=Path(fm.findfont(fm.FontProperties(family=FAMILY,style=style,weight=weight),
                              fallback_to_default=False))
        if found.name!=filename:
            raise RuntimeError(f'Unexpected Linux Libertine face: {found} (expected {filename})')
    mpl.rcParams.update({'font.family':FAMILY,'font.size':9.5,'text.usetex':False,'pdf.fonttype':42,
        'pdf.use14corefonts':False,'ps.fonttype':42,'mathtext.fontset':'custom',
        'mathtext.rm':FAMILY,'mathtext.it':FAMILY+':italic','mathtext.bf':FAMILY+':bold',
        'mathtext.bfit':FAMILY+':bold:italic','mathtext.sf':FAMILY,'mathtext.tt':FAMILY,
        'mathtext.cal':FAMILY,'mathtext.fallback':None,'axes.unicode_minus':True,
        'axes.linewidth':.55,'xtick.major.width':.5,'ytick.major.width':.5,'hatch.linewidth':.5})


def new(w,h):
    typography()
    return plt.figure(figsize=(w/72,h/72))


def plot_area(fig,box,grid='x'):
    ax=fig.add_axes(box)
    ax.set_axisbelow(True)
    if grid:ax.grid(axis=grid,color=GRID,linewidth=.55)
    ax.spines[['top','right']].set_visible(False)
    for s in ax.spines.values():s.set_color(MUTED)
    ax.tick_params(color=MUTED,length=2.5,pad=3)
    return ax


def save(fig,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,metadata=META)
    plt.close(fig)


class Diagram:
    def __init__(self,w=428,h=160):
        self.w,self.h=w,h
        self.fig=new(w,h)
        self.ax=self.fig.add_axes([0,0,1,1],xlim=(0,w),ylim=(0,h))
        self.ax.set_axis_off()
        self.labels=[]

    def text(self,x,y,s,size=9.5,c=INK,ha='center',bold=False,italic=False):
        obj=self.ax.text(x,y,s,fontsize=size,color=c,ha=ha,va='center',
            fontweight='bold' if bold else 'normal',fontstyle='italic' if italic else 'normal',
            linespacing=1.13,zorder=6)
        self.labels.append(obj)
        return obj

    def title(self,x,y,letter,s):
        self.text(x,y,letter,10,BLUE,'left',True)
        self.text(x+17,y,s,10,INK,'left',True)

    def line(self,*pts,c=GRID,lw=.85,dash=False):
        xx,yy=zip(*pts)
        self.ax.plot(xx,yy,color=c,lw=lw,ls=(0,(3,2)) if dash else '-',zorder=2)

    def arrow(self,*pts,c=MUTED,lw=.85,dash=False):
        if len(pts)>2:self.line(*pts[:-1],c=c,lw=lw,dash=dash)
        self.ax.add_patch(FancyArrowPatch(*pts[-2:],arrowstyle='-|>',mutation_scale=7,
            color=c,linewidth=lw,linestyle=(0,(3,2)) if dash else '-',
            shrinkA=0,shrinkB=0,zorder=3))

    def rect(self,x,y,w,h,fill='white',edge='none',lw=.75,dash=False,hatch=None):
        self.ax.add_patch(Rectangle((x,y),w,h,facecolor=fill,edgecolor=edge,
            linewidth=lw,linestyle=(0,(3,2)) if dash else '-',hatch=hatch,zorder=1))

    def dot(self,x,y,r=3.5,c=BLUE,fill=None):
        self.ax.add_patch(Circle((x,y),r,edgecolor=c,facecolor=fill or c,lw=.95,zorder=4))

    def token(self,x,y,s,c=BLUE,fill='white'):
        self.dot(x,y,9,c,fill);self.text(x,y,s,8.5,c,bold=True)

    def cross(self,x,y,c=RED,r=3.7):
        self.line((x-r,y-r),(x+r,y+r),c=c,lw=1.35)
        self.line((x-r,y+r),(x+r,y-r),c=c,lw=1.35)

    def check(self,x,y,c=TEAL):
        self.line((x-4,y),(x-1,y-3),(x+5,y+4),c=c,lw=1.5)

    def doc(self,x,y,c=BLUE,fill=PALE):
        self.ax.add_patch(Polygon([(x-8,y-10),(x+8,y-10),(x+8,y+6),(x+4,y+10),
             (x-8,y+10)],closed=True,edgecolor=c,facecolor=fill,lw=.85,zorder=3))
        self.ax.plot([x-4,x+4],[y,y],color=c,lw=.65,zorder=4)
        self.ax.plot([x-4,x+3],[y-4,y-4],color=c,lw=.65,zorder=4)

    def range(self,x,y,w,n,chosen=(),c=BLUE):
        for i in range(n):
            self.rect(x+w*i/n,y,w/n-1.1,8,PALE if i not in chosen else c,
                      GRID if i not in chosen else c,.6)

    def finish(self,out):
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        extents=[a.get_window_extent(renderer).transformed(self.ax.transData.inverted()) for a in self.labels]
        for i,(label,box) in enumerate(zip(self.labels,extents)):
            if min(box.x0,box.y0,self.w-box.x1,self.h-box.y1)<-0.35:
                raise ValueError(f'{out}: clipped {label.get_text()!r}: {box.bounds}')
            for j,b in enumerate(extents[:i]):
                if min(box.x1,b.x1)-max(box.x0,b.x0)>1.5 and min(box.y1,b.y1)-max(box.y0,b.y0)>2.0:
                    raise ValueError(f'{out}: overlapping {label.get_text()!r} and {self.labels[j].get_text()!r}')
        save(self.fig,out)
