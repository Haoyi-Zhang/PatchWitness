"""Editable publication schematics. Draw only the data specified in explain.json."""
import json
from pathlib import Path
from matplotlib.patches import Polygon, Rectangle
from visual_grammar import Diagram, BLUE, RED, INK, MUTED, PALE, GRID, WARM


def icon(d,x,y,key,c=BLUE):
    """Distinct small glyphs for source, recording, filtering and decisions."""
    if key in ('file','binary','apk'):
        d.doc(x,y,c,PALE)
        if key!='file':
            for a in (-3,2):
                for b in (-3,2):
                    d.ax.add_patch(Rectangle((x+a-1,y+b-1),2.7,2.7,
                                             facecolor='white',edgecolor=c,lw=.65,zorder=5))
    elif key in ('list','trace','receipt'):
        for k in range(3):
            d.rect(x-8,y-8+k*6,16,4,PALE,c,.7)
            if key=='trace':d.dot(x-5+k*5,y-6+k*6,1.8,c)
    elif key in ('rule','compare','join'):
        d.line((x-8,y+6),(x-3,y+6),(x-3,y),(x+8,y),c=c)
        d.line((x-8,y-6),(x-3,y-6),(x-3,y),c=c)
        d.dot(x-8,y+6,2,c,'white');d.dot(x-8,y-6,2,c,'white');d.dot(x+8,y,2.5,c)
    elif key in ('grid','cells','index'):
        for i in range(3):
            for j in range(3):
                d.rect(x-8+i*6,y-8+j*6,4.6,4.6,c if (i,j)==(1,1) else PALE,c,.6)
    elif key in ('accept','reject','unknown'):
        d.dot(x,y,8,c,'white')
        def fg(xs,ys):
            d.ax.plot(xs,ys,color=c,lw=1.15,zorder=6,solid_capstyle='round')
        if key=='accept':fg((x-4,x-1,x+4),(y,y-3,y+3))
        elif key=='reject':
            fg((x-3,x+3),(y-3,y+3));fg((x-3,x+3),(y+3,y-3))
        else:fg((x-4,x+4),(y,y))
    elif key=='gate':
        d.ax.add_patch(Polygon([(x,y+8),(x+8,y),(x,y-8),(x-8,y)],facecolor=PALE,edgecolor=c,lw=.85))
    elif key=='tool':
        d.rect(x-8,y-7,16,14,PALE,c,.8)
        d.arrow((x-5,y),(x+5,y),c=c)
    elif key=='link':
        d.dot(x-5,y,4,c,'white');d.dot(x+5,y,4,c,'white')
        d.line((x-5,y),(x+5,y),c=c,lw=.8)
    elif key=='key':
        d.dot(x-4,y+2,4,c,'white');d.line((x,y+2),(x+9,y+2),(x+9,y-2),c=c,lw=1.0)
        d.line((x+5,y+2),(x+5,y-2),c=c,lw=1.0)
    elif key=='mask':
        d.rect(x-8,y-7,16,14,PALE,c,.7,dash=True)
        d.line((x-6,y-5),(x+6,y+5),c=c,lw=1.1)
    else:raise ValueError(key)


def card(d,x,y,w,h,node):
    label,glyph,*flags=node
    accent=RED if 'risk' in flags else BLUE
    d.rect(x,y-h/2,w,h,WARM if 'risk' in flags else PALE,GRID,.75)
    icon(d,x+14,y,glyph,accent)
    for i,line in enumerate(label.split('|')):
        d.text(x+28,y+(len(label.split('|'))-1-2*i)*5.7,line,9.3,
               accent if i==0 else INK,'left',i==0)
        d.card_limits.append((d.labels[-1],x+w-3))


def finish_cards(d,out):
    d.fig.canvas.draw()
    renderer=d.fig.canvas.get_renderer()
    for label,right in d.card_limits:
        box=label.get_window_extent(renderer).transformed(d.ax.transData.inverted())
        if box.x1>right:
            raise ValueError(f'{out.name}: label {label.get_text()!r} extends beyond its box')
    d.finish(out)


def stack(d,x0,width,y,items,h=35):
    gap=17
    cw=(width-(len(items)-1)*gap)/len(items)
    for i,item in enumerate(items):
        x=x0+i*(cw+gap)
        card(d,x,y,cw,h,item)
        if i<len(items)-1:d.arrow((x+cw+2,y),(x+cw+gap-2,y),c=MUTED)


def route(spec,out):
    rows=spec['rows']
    h=55*len(rows)
    d=Diagram(w=426,h=h)
    d.card_limits=[]
    for i,row in enumerate(rows):
        y=h-34-55*i
        if row.get('name'):
            d.text(9,y+23,row['name'],9.5,INK,'left',True)
        stack(d,9,408,y,row['nodes'])
    finish_cards(d,out)


def fork(spec,out):
    d=Diagram(w=426,h=112)
    d.card_limits=[]
    outcomes=spec['outcomes']
    card(d,14,56,123,42,spec['source'])
    d.line((139,56),(183,56),c=MUTED)
    ys=(85,27)
    for y,note in zip(ys,outcomes,strict=True):
        node,label=note
        d.arrow((183,56),(183,y),(271,y),c=RED if 'risk' in node[2:] else BLUE)
        card(d,275,y,136,40,node)
        d.text(226,y+10,label,9,MUTED)
    finish_cards(d,out)


def mark_joint(spec,out):
    d=Diagram(w=426,h=123)
    for i,heading in enumerate(('Disjoint assignments','Coincident assignments')):
        x=125+i*207
        d.text(x,108,heading,10,INK,bold=True)
        for y,label in ((82,'Detection'),(58,'Validity'),(33,'Overlap')):
            d.text(x-86,y,label,9.3,INK,'left')
        for j in range(10):
            a=j<5
            b=(j>=5 if i==0 else j<5)
            for y,val in ((82,a),(58,b),(33,a and b)):
                x0=x-36+11*j
                d.rect(x0,y-3.8,8,7.6,BLUE if val else 'white',GRID,.7)
    d.finish(out)


def endpoint_partition(spec,out):
    d=Diagram(w=426,h=139)
    x0,y0,step=62,15,6.4
    for n in range(16):
        for k in range(16):
            valid=n<=k
            d.rect(x0+k*step,y0+n*step,step-.32,step-.32,PALE if valid else WARM,
                   BLUE if valid else RED,.31)
    d.text(45,68,'n',10,INK,italic=True)
    d.text(174,16,'d',10,INK,italic=True)
    d.text(61,128,'Declared input grid',10,BLUE,'left',True)
    d.rect(205,78,8,8,WARM,RED,.75)
    d.text(221,82,'120 old faults repaired',10,RED,'left',True)
    d.rect(205,46,8,8,PALE,BLUE,.75)
    d.text(221,50,'136 old endpoints preserved',10,BLUE,'left',True)
    assert sum(n>k for n in range(16) for k in range(16))==120
    d.finish(out)


def support(spec,out):
    d=Diagram(w=250,h=126)
    def set_marks(x,y,n):
        for j in range(n):
            d.dot(x+j*11,y,3,BLUE,'white')
    d.text(56,113,'Truth only',10,INK,bold=True)
    d.text(183,113,'Complete evidence',10,INK,bold=True)
    for x,label,y,n in ((26,'{u, v}',83,2),(152,'{u, v}',83,2),
                       (19,'{u}',47,1),(69,'{v}',47,1)):
        d.rect(x,y-12,50 if n==2 else 36,24,PALE,GRID)
        set_marks(x+8,y,n)
        d.text(x+(35 if n==2 else 24),y,label,8.6,BLUE)
    d.arrow((51,71),(37,61),c=BLUE);d.arrow((51,71),(87,61),c=BLUE)
    d.ax.set_ylim(29,126)
    d.fig.set_size_inches(250/72,97/72)
    d.finish(out)


DRAW={'route':route,'fork':fork,'joint':mark_joint,'endpoint':endpoint_partition,'support':support}

if __name__=='__main__':
    directory=Path(__file__).resolve().parent
    for spec in json.loads((directory/'explain.json').read_text(encoding='utf-8')):
        DRAW[spec['kind']](spec,directory/(spec['id']+'.pdf'))
