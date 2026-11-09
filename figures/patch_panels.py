"""PatchWitness figures: original vector designs drawn from declared evidence."""
from collections import Counter
import numpy as np
from matplotlib.ticker import PercentFormatter
from visual_grammar import *


def evidence_ladder(out):
    d=Diagram(h=127)
    d.title(9,116,'A','What enters replay')
    d.title(272,116,'B','What replay does not settle')
    d.line((257,15),(257,104),c=GRID,dash=True)
    for x,code,title,detail,c in [(35,'1','Acquire','Revision / file',BLUE),
                                 (112,'2','Represent','Declared IR',BLUE),
                                 (201,'3','Replay','Typed relation',TEAL)]:
        d.token(x,70,code,c,GREEN if x==201 else PALE)
        d.text(x,48,title,10,c,bold=True)
        d.text(x,32,detail,8.8)
    d.arrow((46,70),(101,70),c=BLUE)
    d.arrow((123,70),(190,70),c=TEAL)
    d.rect(163,22,77,71,GREEN,TEAL,.6)
    d.dot(284,73,3,RED,'white')
    d.text(296,73,'Ranking rule and budget',9.4,INK,'left')
    d.dot(284,41,3,RED,'white')
    d.text(296,41,'Held-out utility',9.4,INK,'left')
    d.finish(out)


def trust_boundary(out):
    d=Diagram(h=149)
    d.rect(115,86,189,48,WARM,RED,.75,dash=True)
    d.text(122,124,'Untrusted producer',9,RED,'left',True)
    d.rect(115,17,305,53,GREEN,TEAL,.75)
    d.text(122,28,'Receiver-owned check',9,TEAL,'left',True)
    d.doc(50,69,BLUE)
    d.text(50,42,'Expected IR case',9,BLUE,bold=True)
    d.arrow((59,69),(86,69),(86,103),(153,103),c=BLUE)
    d.arrow((59,69),(86,69),(86,48),(210,48),c=BLUE)
    d.token(165,103,'P',RED)
    d.arrow((176,103),(219,103),c=RED)
    d.doc(231,103,RED,WARM)
    d.text(244,104,'Certificate',9,RED,'left')
    d.arrow((231,91),(231,59),c=RED,dash=True)
    d.token(231,48,'V',TEAL)
    d.arrow((242,48),(299,48),c=TEAL)
    d.check(313,48)
    d.text(326,53,'One input',9.2,TEAL,'left',True)
    d.text(326,39,'Fault → defined',8.7,INK,'left')
    d.finish(out)


def study_pipeline(out):
    d=Diagram(h=147)
    d.title(9,135,'A','Freeze predictions')
    d.title(264,135,'B','Open labels and score')
    d.line((247,20),(247,123),c=MUTED,dash=True)
    d.text(247,11,'Process boundary',8.8,MUTED)
    d.doc(53,96);d.text(53,78,'Candidates',9,BLUE,bold=True)
    d.doc(53,47);d.text(53,29,'Cases + rule',9,BLUE,bold=True)
    d.arrow((64,96),(119,96),(119,89),(166,89),c=BLUE)
    d.arrow((64,47),(119,47),(119,89),c=BLUE)
    d.doc(182,89,TEAL,GREEN)
    d.text(182,69,'Frozen predictions',9,TEAL,bold=True)
    d.arrow((193,89),(295,89),c=TEAL)
    d.token(307,89,'E',TEAL)
    d.arrow((318,89),(353,89),c=TEAL)
    d.text(381,89,'Metrics',9.5,TEAL,bold=True)
    d.doc(307,37,RED,WARM)
    d.text(324,37,'Separate labels',9,RED,'left',True)
    d.arrow((307,49),(307,78),c=RED,dash=True)
    d.finish(out)


def precision(rows,out):
    fig=new(424,194)
    a=plot_area(fig,(.152,.500,.806,.349),'y')
    b=plot_area(fig,(.152,.194,.806,.219),'y')
    x=np.array([int(r['k']) for r in rows])
    assert x.tolist()==list(range(1,33))
    p={f:np.array([float(r[f]) for r in rows]) for f in ('syntax','hint','checked')}
    for k,label,c,ls,mark in [('syntax','Syntax',MUTED,'-','o'),('hint','Unchecked hints',RED,'--','^'),
                             ('checked','Checked',TEAL,':','s')]:
        a.plot(x,p[k],c=c,ls=ls,lw=1.42,marker=mark,ms=3.6,mfc='white',markevery=4,label=label)
    a.set(ylim=(.46,1.035),yticks=[.5,.75,1],ylabel='Precision')
    a.yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    a.tick_params(labelbottom=False)
    a.legend(loc='lower center',bbox_to_anchor=(.52,1.03),ncol=3,frameon=False,fontsize=9.7)
    for ax in (a,b):
        ax.tick_params(labelsize=9.65)
        ax.set(xlim=(.6,32.4),xticks=[1,5,10,15,20,25,32])
        ax.axvline(20,c=MUTED,ls='--',lw=.65,zorder=0)
    b.axhline(0,color=MUTED,lw=.6)
    for k,c,m,ls in [('hint',RED,'^','--'),('checked',TEAL,'s',':')]:
        b.plot(x,100*(p[k]-p['syntax']),c=c,lw=1.2,ls=ls,marker=m,markevery=[19],ms=4,
               mfc='white',zorder=3)
    b.set(ylim=(-1.5,9.4),yticks=[0,4,8],xlabel='Review cutoff k',ylabel='Difference (pp)')
    save(fig,out)


def availability(rows,out):
    fig=new(412,112)
    ax=plot_area(fig,(.255,.29,.67,.63),'x')
    yy=[0,.8,2,2.8]
    ax.set(xlim=(0,1.13),ylim=(3.35,-.55),yticks=yy,yticklabels=[r['label'] for r in rows],
           xticks=[0,.25,.5,.75,1],xlabel='Share with an accepted source record')
    ax.xaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    ax.tick_params(axis='y',length=0,labelsize=9.7)
    ax.tick_params(axis='x',labelsize=9.7)
    ax.spines['left'].set_visible(False)
    for i,(y,r) in enumerate(zip(yy,rows)):
        c=BLUE
        v=float(r['fraction'])
        ax.barh(y,v,color=c if i<2 else PALE,edgecolor=c,height=.46,
                hatch=None if i<2 else '//',lw=.7,zorder=3)
        ax.text(v+.026,y,r['annotation'],color=INK,va='center',fontsize=9.8,weight='bold')
    save(fig,out)


def intervals(rows,out):
    fig=new(412,124)
    ax=plot_area(fig,(.365,.27,.59,.65),'x')
    order=(2,3,0,1);ys=(0,.75,2,2.75)
    ax.set(xlim=(-6.5,6.5),ylim=(3.27,-.55),xticks=[-5,-2.5,0,2.5,5],
           yticks=ys,yticklabels=['Checked · labels hidden','Hints · labels hidden',
                                  'Checked · one correction','Hints · one correction'],
           xlabel='Change in P@20 vs syntax (percentage points)')
    ax.tick_params(axis='y',length=0,labelsize=9.7)
    ax.tick_params(axis='x',labelsize=9.7)
    ax.spines['left'].set_visible(False)
    ax.axvline(0,color=MUTED,linewidth=.85)
    for y,i in zip(ys,order):
        lo,hi,obs=[float(rows[i][x])*100 for x in ('lower','upper','observed')]
        c=TEAL if i%2==0 else RED
        ax.hlines(y,lo,hi,color=c,lw=1.65)
        ax.vlines([lo,hi],y-.14,y+.14,color=c,lw=1.15)
        ax.scatter(obs,y,marker='s' if i%2==0 else '^',s=29,edgecolors=c,
                   facecolors='white' if i%2==0 else c,zorder=5)
    save(fig,out)


def coexisting(out):
    d=Diagram(w=377,h=151)
    d.title(9,140,'A','64 exact assignments')
    d.title(190,140,'B','Outcome key')
    x0,y0,step=45,31,12
    m=8
    counts=Counter()
    for x in range(m):
        d.text(x0+x*step,y0-12,str(x),9.75)
        for y in range(m):
            old=x+1<m
            new=((x-1)%m)+1<m
            state='repair' if not old and new else 'regression' if old and not new else 'both'
            counts[state]+=1
            pos=(x0+x*step,y0+y*step)
            c,fill={'repair':(TEAL,GREEN),'regression':(RED,WARM),'both':(BLUE,PALE)}[state]
            d.rect(pos[0]-5.5,pos[1]-5.5,11,11,fill,GRID,.55)
            if state=='repair':d.check(*pos,c)
            elif state=='regression':d.cross(*pos,c,r=2.7)
            else:d.dot(*pos,1.35,c,'white')
    assert counts=={'repair':8,'regression':8,'both':48}
    for y in range(m):d.text(x0-14,y0+y*step,str(y),9.75)
    d.text(13,75,'y',9,INK,italic=True);d.text(87,7,'x',9,INK,italic=True)
    for y,k,text,c,mark in [(109,'repair','Old fault → defined',TEAL,d.check),
                             (82,'regression','Old defined → fault',RED,d.cross)]:
        mark(198,y,c)
        d.text(212,y,text,10,c,'left',True)
        d.text(340,y,str(counts[k]),10,c,bold=True)
    d.dot(198,55,2.1,BLUE,'white')
    d.text(212,55,'Defined in both',10,INK,'left')
    d.text(340,55,str(counts['both']),10,BLUE,bold=True)
    d.finish(out)
