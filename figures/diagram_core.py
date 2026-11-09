"""Typeset manuscript diagrams on the exact physical figure footprint."""
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, Polygon, Rectangle
from matplotlib.transforms import Bbox
import visual_grammar as grammar


INK, BLUE, GRAY, HAIR, WASH, RED, WARM = (
    '#1b2229', '#20485d', '#414d56', '#b1bdc4', '#f1f4f5', '#823629', '#f8eeea'
)


class Figure:
    def __init__(self, spec):
        self.s = spec
        w, h = spec['media']
        l, b, r, t = spec['trim']
        self.vw, self.vh = w-l-r, h-t-b
        self.fig = grammar.new(w, h)
        self.ax = self.fig.add_axes((l/w, b/h, self.vw/w, self.vh/h),
                                    xlim=(0, 420), ylim=(100, 0))
        self.ax.set_axis_off()
        self.scale = spec['width']/self.vw
        self.small = self.vh*self.scale < 78
        self.ieee = hasattr(grammar,'measure_face')
        self.labels = []
        self.segments = []

    def t(self, x, y, s, *, align='center', color=INK, bold=False, size=9.3, style='normal'):
        # Body-sized labels, modest headings; color is reserved for exceptions
        # and physical marks. Avoid using the diagram accent as a font color.
        if color==BLUE:
            color=INK
        size=max(size, 9.45 if not self.ieee else 9.65)
        if bold:size=max(size,9.85 if not self.ieee else 10.0)
        weight='bold' if bold else 'normal'
        options = ({'fontproperties': grammar.measure_face(style,weight)}
                   if hasattr(grammar,'measure_face') else {})
        a = self.ax.text(x, y, s, fontsize=size/self.scale, ha=align,
                         va='center', fontweight='bold' if bold else 'normal',
                         fontstyle=style, color=color, linespacing=1.12, zorder=8,**options)
        self.labels.append(a)
        return a

    def title(self, x, y, s, **kw):
        return self.t(x, y, s, bold=True, **kw)

    def line(self, *points, color=HAIR, dash=False, weight=.74, check=False):
        self.ax.add_line(Line2D(*zip(*points), color=color, linewidth=weight/self.scale,
                               linestyle=(0, (3.2, 2.5)) if dash else '-', zorder=3))
        if check:
            self.segments.extend(zip(points, points[1:]))

    def route(self, *points, color=BLUE, dash=False, weight=.88):
        if len(points)>2:
            self.line(*points[:-1], color=color, dash=dash, weight=weight, check=True)
        self.ax.add_patch(FancyArrowPatch(*points[-2:], arrowstyle='-|>',
                          mutation_scale=6.0/self.scale, color=color,
                          linewidth=weight/self.scale, shrinkA=0, shrinkB=0,
                          linestyle=(0, (3.2, 2.5)) if dash else '-', zorder=4))
        self.segments.append(points[-2:])

    def span(self, l, r, y, *, color=GRAY):
        self.line((l,y+3),(l,y),(r,y),(r,y+3),color=color,check=True)

    def knot(self, x, y, color=BLUE, solid=False):
        rx, ry = self.units(2.1)
        from matplotlib.patches import Ellipse
        self.ax.add_patch(Ellipse((x,y),2*rx,2*ry,edgecolor=color,
                         facecolor=color if solid else 'white',
                         linewidth=.85/self.scale,zorder=6))

    def rect(self, x, y, w, h, *, fill='white', edge=HAIR, dash=False,z=2):
        self.ax.add_patch(Rectangle((x,y),w,h,facecolor=fill,edgecolor=edge,
                         linewidth=.63/self.scale,
                         linestyle=(0,(3.2,2.5)) if dash else '-',zorder=z))

    def units(self, points):
        return (points*420/(self.vw*self.scale), points*100/(self.vh*self.scale))

    def icon(self, name, x, y, *, color=BLUE, scale=1.0):
        # Draw in typographic points, not canvas coordinates, so glyphs
        # stay proportional when a manuscript uses a narrower figure.
        ux,uy=self.units(scale*.88)
        def p(a,b):return x+a*ux,y+b*uy
        def path(*v):
            self.line(*(p(*q) for q in v),color=color,weight=1.01)
        def rect(a,b,w,h,fill='white'):
            xx,yy=p(a,b)
            self.rect(xx,yy,w*ux,h*uy,fill=fill,edge=color)
        def dot(a,b):
            xx,yy=p(a,b)
            self.ax.add_patch(Polygon([p(a-1.6,b),p(a,b-1.6),p(a+1.6,b),p(a,b+1.6)],
                                      facecolor=color,edgecolor=color,linewidth=.3,zorder=5))
        if name in ('source','trace','keydoc','diff','policy','cert'):
            path((-6,-8),(2,-8),(6,-4),(6,8),(-6,8),(-6,-8))
            path((2,-8),(2,-4),(6,-4))
            if name in ('source','diff'):
                path((-1,-2),(-4,0),(-1,2));path((1,-2),(4,0),(1,2))
                if name=='diff':path((-4,5),(-1,5));path((1,5),(4,5))
            elif name in ('keydoc','cert'):
                path((-4,1),(-2,4),(3,-1))
                path((-3,6),(3,6))
            else:
                for b in (-1,2,5):path((-3,b),(3,b))
        elif name in ('apk','carrier','shared','artifact','binary'):
            path((-7,-5),(0,-8),(7,-5),(7,5),(0,8),(-7,5),(-7,-5),(0,-2),(7,-5))
            path((0,-2),(0,8))
            if name=='shared': path((-4,-4),(2,-7),(6,-5),(0,-2),(-4,-4))
            if name in ('carrier','binary'):path((3,2),(5,1),(5,4))
        elif name in ('stack','stream','rows','store'):
            if name=='store':
                for b in (-5,0,5):
                    path((-7,b),(-4,b-2),(4,b-2),(7,b),(4,b+2),(-4,b+2),(-7,b))
                path((-7,-5),(-7,5));path((7,-5),(7,5))
            else:
                for b in (-6,0,6):
                    rect(-7,b-1.5,14,3)
                    path((-3,b-1.5),(-3,b+1.5))
                    if name in ('stream','rows'):dot(3,b)
        elif name in ('grid','checkgrid','match'):
            for a in (-6,0,6):
                for b in (-6,0,6):
                    rect(a-2.2,b-2.2,4.4,4.4,WASH if (a+b)%12==0 else 'white')
            if name=='match':dot(6,0)
        elif name in ('run','filter','chip','merge','compare'):
            if name=='filter':
                path((-8,-6),(8,-6),(2,1),(2,6),(-2,8),(-2,1),(-8,-6))
            elif name=='merge':
                path((-7,-6),(-3,-6),(-3,0),(7,0));path((-7,6),(-3,6),(-3,0))
                dot(-7,-6);dot(-7,6);dot(7,0)
            else:
                rect(-6,-6,12,12)
                if name=='run':path((-2,-3),(3,0),(-2,3),(-2,-3))
                if name=='chip':
                    for a in (-4,0,4):
                        path((a,-8),(a,-6));path((a,6),(a,8))
                    for b in (-4,0,4):
                        path((-8,b),(-6,b));path((6,b),(8,b))
                if name=='compare':
                    path((-3,-2),(3,-2));path((-3,2),(3,2))
        elif name in ('check','reject','partial','branch','flag','lock','key','point'):
            if name=='check':path((-6,0),(-2,4),(6,-5))
            if name=='reject':
                path((-5,-5),(5,5));path((-5,5),(5,-5))
            if name=='partial':path((-5,0),(5,0))
            if name=='branch':
                path((-7,0),(0,0),(6,-5));path((0,0),(6,5))
                for a,b in ((-7,0),(6,-5),(6,5)):dot(a,b)
            if name=='flag':
                path((-5,7),(-5,-7),(7,-7),(3,-3),(7,1),(-5,1))
            if name=='lock':
                rect(-6,-1,12,8);path((-4,-1),(-4,-5),(0,-8),(4,-5),(4,-1));dot(0,3)
            if name=='key':
                path((-7,0),(-4,-4),(0,-4),(3,0),(0,4),(-4,4),(-7,0))
                path((3,0),(8,0),(8,4))
            if name=='point':
                path((-7,0),(7,0));path((0,-7),(0,7));dot(0,0)
        elif name in ('tree','join','link','timeline'):
            path((-7,-5),(-1,-5),(-1,0),(7,0))
            path((-7,5),(-1,5),(-1,0))
            for a,b in ((-7,-5),(-7,5),(7,0)):dot(a,b)
        else:
            raise ValueError(name)

    def node(self, x, y, icon, name, *, side='below', color=BLUE, bold=False):
        self.icon(icon,x,y,color=color)
        rx,ry=self.units(12.8)
        if side=='left':self.t(x-rx,y,name,align='right',color=color,bold=bold)
        elif side=='right':self.t(x+rx,y,name,align='left',color=color,bold=bold)
        elif side=='above':self.t(x,y-ry,name,color=color,bold=bold)
        else:self.t(x,y+ry,name,color=color,bold=bold)

    def finish(self, output):
        self.fig.canvas.draw()
        renderer=self.fig.canvas.get_renderer()
        boxes=[]
        for a in self.labels:
            x0,y0,x1,y1=a.get_window_extent(renderer).transformed(self.ax.transData.inverted()).extents
            boxes.append(Bbox.from_extents(min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1)))
        for i,(a,b) in enumerate(zip(self.labels,boxes)):
            x0,y0,x1,y1=b.extents
            if min(x0,y0,420-x1,100-y1)<.4:
                raise ValueError(f'{output.name}: clipped {a.get_text()!r} at {b.bounds}')
            for k,c in enumerate(boxes[:i]):
                # Tolerance covers font bearings, not glyph overlaps.
                if min(x1,c.x1)-max(x0,c.x0)>2 and min(y1,c.y1)-max(y0,c.y0)>1.2:
                    raise ValueError(f'{output.name}: labels {a.get_text()!r} and {self.labels[k].get_text()!r} overlap')
            for (u,v),(q,z) in self.segments:
                for j in range(61):
                    f=j/60
                    if x0+1.6 < u+(q-u)*f < x1-1.6 and y0+1.0 < v+(z-v)*f < y1-1.0:
                        raise ValueError(f'{output.name}: route crosses {a.get_text()!r}')
        if hasattr(grammar,'write_exact_labels'):
            from matplotlib import pyplot
            grammar.write_exact_labels(self.fig,self.labels,output,grammar.META)
            pyplot.close(self.fig)
        else:
            grammar.save(self.fig, output)
